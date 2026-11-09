#!/usr/bin/env python3
"""Read saved graph edits, Action executions and R achievements from one owner.

No scheduling, source writes, inferred human authors or invented old timestamps.
"""
import argparse
import fcntl
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import re

TOOLS = Path(__file__).resolve().parent
IO=SourceFileLoader('activity_current_routes',str(TOOLS/'rdg-transaction-io.py')).load_module()
MODEL = SourceFileLoader("rdg_activity_model", str(TOOLS/"rdg-v7-model.py")).load_module()


def read_activity(graph_root, graph_refs, token=None, authority_store=None, include_sources=False):
    root = Path(graph_root).resolve()
    lock_path = root/"workspaces/.writer.lock"
    if lock_path.exists():
        if any(p.is_symlink() for p in [lock_path, *lock_path.parents] if p != root.parent):
            raise ValueError("ACTIVITY_UNSAFE_LOCK")
        with os.fdopen(os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            return _read_activity_unlocked(root, graph_refs, token, authority_store, include_sources)
    return _read_activity_unlocked(root, graph_refs, token, authority_store, include_sources)


def _read_activity_unlocked(graph_root, graph_refs, token=None, authority_store=None, include_sources=False):
    root = Path(graph_root).resolve()
    refs = list(dict.fromkeys(graph_refs))
    if not refs:
        raise ValueError("ACTIVITY_GRAPH_REFS_REQUIRED")
    paths = {}
    for ref in refs:
        if not isinstance(ref, str) or not re.fullmatch(r"workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json", ref):
            raise ValueError("ACTIVITY_GRAPH_PATH_INVALID")
        path = root/ref
        if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
            raise ValueError("ACTIVITY_UNSAFE_SOURCE")
        paths[ref] = path
    store = authority_store or os.environ.get("RDG_AUTH_STORE")
    if store:
        auth = SourceFileLoader("rdg_activity_auth", str(TOOLS/"rdg-authority.py")).load_module()
        auth.Authority(store).authorize_graph_read(token or os.environ.get("RDG_AUTH_TOKEN"), refs)
    for path in paths.values():IO.require_current_legacy(path)
    graphs = {ref: json.loads(path.read_text(encoding="utf-8")) for ref, path in paths.items()}
    engine=SourceFileLoader("rdg_activity_completion",str(TOOLS/"rdg-completion-context.py")).load_module()
    authorize=(lambda files: auth.Authority(store).authorize_graph_read(token or os.environ.get("RDG_AUTH_TOKEN"),files)) if store else None
    context=engine.load(root,{f:g for f,g in graphs.items() if not g.get("coreModel")},authorize=authorize)
    if context.cross:
        graphs={**graphs,**context.graphs};refs=list(graphs)
    validator = SourceFileLoader("rdg_activity_validate", str(TOOLS/"graph-apply.py")).load_module()
    for graph in graphs.values():
        validator.validate(graph)
    rows, seen = [], set()

    def graph_change_kind(before, after, appended):
        """Type an accepted diff without pretending it is an Action execution.

        The writer may also carry a generic graph_changed event. That must
        not obscure a real R creation/deactivation or a candidate declaration.
        """
        before_nodes={n['id']:n for n in before.get('nodes',[])}
        after_nodes={n['id']:n for n in after.get('nodes',[])}
        added=[n for nid,n in after_nodes.items() if nid not in before_nodes]
        removed=[n for nid,n in before_nodes.items() if nid not in after_nodes]
        if not before.get('revision'):
            return 'graph_created',None
        if len(added)==1 and not removed:
            node=added[0]
            if node['kind']=='context':return 'context_added',node
            if node['kind']=='action':return 'action_added',node
            if node['kind']=='requirement':
                return ('requirement_prepared' if node.get('status') in ('potential','candidate')
                        else 'requirement_added'),node
        if len(removed)==1 and not added:
            if removed[0]['kind']=='action':return 'action_removed',removed[0]
            if removed[0]['kind']=='requirement':return 'requirement_removed',removed[0]
        if not added and not removed:
            old_edges={e['id']:e for e in before.get('edges',[])}
            new_edges={e['id']:e for e in after.get('edges',[])}
            inserted=[e for eid,e in new_edges.items() if eid not in old_edges]
            deleted=[e for eid,e in old_edges.items() if eid not in new_edges]
            if len(inserted)==1 and not deleted and inserted[0].get('type')=='CONTEXT_FOR':
                return 'context_link_added',after_nodes.get(inserted[0]['to'])
            changed=[(before_nodes[nid],after_nodes[nid]) for nid in before_nodes
                     if before_nodes[nid]!=after_nodes[nid]]
            if len(changed)==1:
                old,new=changed[0]
                if old['kind']=='requirement' and new['kind']=='requirement':
                    old_status=old.get('status','active');new_status=new.get('status','active')
                    if old_status in ('candidate','potential','inactive') and new_status=='active':
                        return 'requirement_activated',new
                    if old_status=='active' and new_status=='inactive':
                        return 'requirement_deactivated',new
        return 'graph_saved',None

    def events(ref, entries, recorded_at, transaction_id, ordered=False, before=None, after=None):
        for event in entries:
            key = (ref, event["id"])
            if key in seen:
                continue
            seen.add(key)
            if graphs[ref].get('coreModel'):
                target=event.get('targetId')
                snapshot=event.get('after',{}).get(target,{})
                rows.append({'id':ref+'::'+event['id'],'kind':event['type'],'sourceEventType':event['type'],
                    'graphFile':ref,'recordedAt':recorded_at,'transactionId':transaction_id,
                    'eventOrder':next(i for i,e in enumerate(graphs[ref]['events']) if e['id']==event['id']),
                    'targetId':target,'targetIds':event.get('targetIds'), 'title':snapshot.get('title'),
                    'nodeSnapshot':snapshot,'materialSnapshotAvailable':bool(snapshot),
                    'snapshotProvenance':'core-accepted-event','before':event.get('before'), 'after':event.get('after'),
                    'previousRelation':event.get('previousRelation'),'newRelation':event.get('newRelation'),
                    'affectedIds':event.get('affectedIds',[]),'evidenceRefs':event.get('evidenceRefs'),
                    'by':event.get('by'),'authorityPrincipal':event.get('authorityPrincipal'),
                    'note':event['note'],'summary':event['note']})
                continue
            if event.get("type") in ('module_event','modules_configured'):
                row = {"id":ref+"::"+event["id"], "kind":event["type"], "sourceEventType":event["type"],
                       "graphFile":ref,"recordedAt":recorded_at,"transactionId":transaction_id,
                       "targetId":event.get('targetId'),"module":event.get('module'),
                       "nodeSnapshot":event.get('nodeSnapshot'),"priorNodeSnapshot":event.get('priorNodeSnapshot'),
                       "previousModules":event.get('previousModules'),"newModules":event.get('newModules'),
                       "note":event.get('note'),"by":event.get('by'),
                       "authorityPrincipal":event.get('authorityPrincipal'),
                       "snapshotProvenance":"module-event-snapshot","materialSnapshotAvailable":False}
                row['summary'] = (event['label']
                    if event['type']=='module_event' else 'Изменены подключённые модули Graph')
                rows.append(row)
                continue
            if event.get("type") not in MODEL.COMPLETION_EVENTS | {"action_withdrawn", "action_reconsidered", "requirement_reformulated", "action_selected"}:
                continue
            withdrawal = event.get("type") in {"action_withdrawn", "action_reconsidered"}
            selecting = event.get("type") == "action_selected"
            # selectionBasis.actionSnapshot was captured by the accepted
            # Action selection and is immutable even if the current Action
            # changes. Never manufacture an old canon from today's node.
            selected_node=next((n for n in graphs[ref]["nodes"] if n.get('id')==event.get('actionId')
                                and n.get('kind')=='action'),None) if selecting else None
            selection_snapshot=(selected_node or {}).get('selectionBasis',{}).get('actionSnapshot')
            snapshot = (event.get("priorActionSnapshot") if withdrawal else
                        selection_snapshot if selecting else
                        event.get('previousRequirementSnapshot') if event.get('type')=='requirement_reformulated' else
                        event.get("viewSnapshot") or event.get("basis", {}).get("node", {})) or {}
            material_available = withdrawal or bool(selecting and selection_snapshot) or event.get('type')=='requirement_reformulated' or "viewSnapshot" in event
            introduced=[]
            if selecting and before is not None and after is not None:
                # A selection introduces active subgoals by creating an R or
                # promoting a prepared potential/candidate R. Read only from
                # the same completed writer transaction, not the latest graph.
                old_nodes={n['id']:n for n in before.get('nodes',[])}
                old_intro={(e['from'],e['to']) for e in before.get('edges',[])
                           if e.get('type')=='INTRODUCES' and e.get('archived') is not True}
                for edge in after.get('edges',[]):
                    if (edge.get('type')!='INTRODUCES' or edge.get('from')!=event['actionId'] or
                        edge.get('archived') is True or
                        (edge['from'],edge['to']) in old_intro):continue
                    requirement=next((n for n in after['nodes'] if n['id']==edge['to'] and
                                      n['kind']=='requirement'),None)
                    if requirement is None:continue
                    previous=old_nodes.get(requirement['id'])
                    mode=('created' if previous is None else
                          'activated' if previous.get('status') in ('potential','candidate') and
                          requirement.get('status')=='active' else 'linked')
                    introduced.append({'nodeId':requirement['id'],'title':requirement['title'],
                        'kind':'requirement','status':requirement.get('status'),
                        'previousStatus':previous.get('status') if previous else None,
                        'introductionMode':mode,'childRole':edge.get('childRole'),
                        'graphFile':ref})
            rows.append({"id": ref+"::"+event["id"], "graphFile": ref,
                         "kind": event["type"],
                         "sourceEventType": event["type"],
                         "targetId": event["actionId"] if withdrawal or selecting else event["targetId"],
                         "previousRequirementSnapshot": event.get('previousRequirementSnapshot'),
                         "newRequirementSnapshot": event.get('newRequirementSnapshot'),
                         "title": snapshot.get("title"),
                         "nodeSnapshot": snapshot,
                         "materialSnapshotAvailable": material_available,
                         "snapshotProvenance": "prior-action-snapshot" if withdrawal else
                             "action-selection-basis" if selecting and material_available else
                             "event-view-snapshot" if material_available else "completion-basis",
                         "viewSnapshotSHA256": event.get("viewSnapshotSHA256"),
                         "eventOrder": next(i for i,e in enumerate(graphs[ref]["events"]) if e["id"] == event["id"]),
                         "compositionOrder": event.get("compositionOrder") if ordered else None,
                         "recordedAt": recorded_at, "occurredAt": event.get("occurredAt"),
                         "by": event.get("by"), "authorityPrincipal": event.get("authorityPrincipal"),
                         "completionMode": event.get("completionMode"),
                         "reviewActionId": event.get("reviewActionId") if withdrawal else None,
                         "transition": event.get("transition") if event["type"] == "action_reconsidered" else None,
                         "introducedRequirements": introduced if selecting and before is not None and after is not None else None,
                         "basisSHA256": event.get("basisSHA256"), "note": event.get("note"),
                         "transactionId": transaction_id})

    directory = root/"workspaces/.transactions"
    if directory.exists() and (directory.is_symlink() or any(p.is_symlink() for p in directory.parents if p != root.parent)):
        raise ValueError("ACTIVITY_UNSAFE_JOURNAL")
    for journal_path in sorted(directory.glob("*.json")):
        if journal_path.is_symlink():
            raise ValueError("ACTIVITY_UNSAFE_JOURNAL")
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        if journal.get("state") != "completed":
            if any(r.get("file") in refs for r in journal.get("records", [])):
                raise ValueError("ACTIVITY_RECOVERY_REQUIRED")
            continue
        for record in journal.get("records", []):
            ref = record.get("file")
            if ref not in graphs or record.get("changed") is False:
                continue
            before, after = record.get("before") or {}, record["after"]
            previous = {e["id"] for e in before.get("events", [])}
            added = [e for e in after.get("events", []) if e["id"] not in previous]
            principal = sorted({e["authorityPrincipal"] for e in added if e.get("authorityPrincipal")})
            if journal.get("authorityPrincipal"):
                principal = sorted(set(principal) | {journal["authorityPrincipal"]})
            changed = {}
            for field in ("nodes", "edges"):
                old = {x["id"]: x for x in before.get(field, [])}
                new = {x["id"]: x for x in after.get(field, [])}
                changed[field] = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
            change_kind,subject=graph_change_kind(before,after,added)
            change_title=(subject or {}).get('title') or after.get('title') or ref
            change_summary={
                'graph_created':'Создан рабочий Graph: '+change_title,
                'context_added':'Добавлен контекст: '+change_title,
                'context_link_added':'Добавлена связь контекста с Action: '+change_title,
                'action_added':'Добавлен '+('кандидат Action' if subject.get('status')=='candidate' else 'Action')+': '+change_title if subject else '',
                'requirement_added':'Создана активная Requirement: '+change_title,
                'requirement_prepared':'Подготовлена потенциальная Requirement: '+change_title,
                'requirement_activated':'Активирована Requirement: '+change_title,
                'requirement_deactivated':'Деактивирована Requirement: '+change_title,
                'action_removed':'Удалён Action: '+change_title,
                'requirement_removed':'Удалена Requirement: '+change_title,
            }.get(change_kind)
            rows.append({"id": journal["transactionId"]+"::"+ref+"::saved", "graphFile": ref,
                         "kind": "graph_saved", "recordedAt": journal.get("recordedAt"),
                         "transactionId": journal["transactionId"], "revision": after["revision"],
                         "previousRevision": before.get("revision"), "changed": changed,
                         "changeKind": change_kind, "changeTargetId": subject.get('id') if subject else None,
                         "changeTargetKind": subject.get('kind') if subject else None,
                         "changeTargetSnapshot": subject,
                         "authorityPrincipals": principal,
                         "note": "; ".join(dict.fromkeys(e.get('note','') for e in added
                                     if e.get('type')=='graph_changed' and e.get('note'))),
                         "summary": change_summary or
                                    "; ".join(dict.fromkeys(e.get("note", "") for e in added if e.get("note") and e.get("type") not in MODEL.COMPLETION_EVENTS)) or
                                    "Изменены: " + ", ".join(next((n["title"] for n in after.get("nodes", []) if n["id"] == nid), nid) for nid in changed["nodes"]),
                         "operations": [e.get("operation", e.get("type")) for e in added
                                        if e.get("type") not in MODEL.COMPLETION_EVENTS]})
            events(ref, added, journal.get("recordedAt"), journal["transactionId"],
                   ordered=any(r.get("completionReadSet") for r in journal["records"]),
                   before=before,after=after)
    for ref, graph in graphs.items():
        # Historical events without a completed journal retain unknown save time.
        events(ref, graph.get("events", []), None, None)
    rows.sort(key=lambda r: (r.get("recordedAt") is None, r.get("recordedAt") or "",
                             r.get("transactionId") or r.get("graphFile"),
                             r.get("compositionOrder") if r.get("compositionOrder") is not None else -1,
                             r.get("graphFile"), r.get("eventOrder", -1), r["id"]))
    evaluated=context.evaluate() if context.cross else {ref:MODEL.completion_state(graph)
        for ref,graph in graphs.items() if graph.get("actionModel")=="candidate-v6"}
    evaluated.update({ref:MODEL.completion_state(graph) for ref,graph in graphs.items() if graph.get("coreModel")})
    states={ref:{nid:{k:v for k,v in row.items() if k!="basis"} for nid,row in rows.items()}
            for ref,rows in evaluated.items()}
    owners = {ref: {"identitySpace": graph.get("identitySpace"), "revision": graph["revision"],
                    "nodes": {n["id"]: {k:n[k] for k in ("id", "kind", "title", "status", "active", "projectionOf") if k in n}
                              for n in graph["nodes"] if n["kind"] in {"requirement", "action"}}}
              for ref,graph in graphs.items()}
    return {"schemaVersion": 1, "activities": rows, "currentCompletion": states, "graphOwners": owners,
            **({"sourceGraphs": graphs} if include_sources else {}),
            "completionProvenance": {"sources": context.pins_for_journal(), "catalogSHA256": context.index_hash},
            "coverage": "published workspace composition with authorized identity owners",
            "sourcesChanged": False}


def markdown(report, outcomes_only=False):
    labels = {"graph_saved": "Сохранён граф", "action_executed": "Выполнен Action",
              "requirement_achieved": "Достигнута цель / Requirement", "action_withdrawn": "Отозван Action",
              "action_selected": "Выбран Action", "action_reconsidered": "Action пересмотрен",
              "requirement_reformulated": "Переформулирована Requirement",
              "plan_created": "Создан Plan",
              "plan_placement_saved": "Размещён шаг Plan", "plan_placement_removed": "Удалено размещение Plan"}
    lines = []
    for row in report["activities"]:
        if outcomes_only and row["kind"] == "graph_saved":
            continue
        target = row.get("targetId") or "revision="+str(row.get("revision"))
        lines.append("- "+(row.get("recordedAt") or "Время записи неизвестно")+" · "+
                     labels[row["kind"]]+" · "+target+" · "+row["graphFile"]+
                     (" · "+row["title"] if row.get("title") else "") +
                     (" · "+row["summary"] if row.get("summary") else ""))
    return "\n".join(lines)+"\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-root", required=True)
    parser.add_argument("--graph", action="append", required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--outcomes-only", action="store_true")
    args = parser.parse_args()
    report = read_activity(args.graph_root, args.graph)
    if args.outcomes_only:
        report["activities"] = [r for r in report["activities"] if r["kind"] != "graph_saved"]
    print(markdown(report) if args.format == "markdown" else json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit("ERROR: "+str(exc))
