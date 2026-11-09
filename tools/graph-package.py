#!/usr/bin/env python3
"""Recoverable all-validated-before-write R-D workspace transactions.

Files are replaced individually; this is NOT a filesystem-wide atomic rename.
The journal, common writer lock and published catalog give a recoverable commit
boundary. A crashed transaction must be recovered before a new writer proceeds.
"""
import copy
import datetime as dt
from contextlib import nullcontext
import fcntl
import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from importlib.machinery import SourceFileLoader

BASE = Path(__file__).resolve().parent.parent
GRAPHS = BASE / "graphs"
WORKSPACES = GRAPHS / "workspaces"
apply_module = SourceFileLoader("rdg_apply_library", str(BASE / "tools/graph-apply.py")).load_module()
index_module = SourceFileLoader("rdg_index_library", str(BASE / "tools/graph-index.py")).load_module()
check, load_json = apply_module.check, apply_module.load_json
reference_io = SourceFileLoader("package_reference_barrier", str(BASE / "tools/rdg-transaction-io.py")).load_module()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    index_module.atomic_write(path, encoded(value))
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)



# The authorized writer transaction is the acceptance boundary.
# An event and its attribution are historical content, not a separate signature
# requirement. Malformed events, revision races and unsafe sources are still rejected.

def target_path(relative):
    check(isinstance(relative, str) and re.fullmatch(r"workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json", relative),
          "NON_WORKSPACE_GRAPH: package paths must be normalized graph.json paths inside workspaces/")
    path = GRAPHS / relative
    check(path.resolve().is_relative_to(WORKSPACES.resolve()), "PATH_OUTSIDE_WORKSPACE")
    check(not any(part.is_symlink() for part in [path, *path.parents] if part != BASE.parent),
          "SYMLINK_GRAPH: use the real workspace path")
    check(reference_io.portable_container(path,GRAPHS) is None,'WRITER_REQUIRES_PACKAGE_ID')
    reference_io.require_current_legacy(path)
    return path


def read_if_exists(path):
    return load_json(path) if path.exists() else None


def require_package_authority(package):
    """Opt-in bearer guard; never serialize RDG_AUTH_TOKEN into graph/package."""
    store = os.environ.get("RDG_AUTH_STORE")
    if not store:
        return None  # Legacy compatibility; NOT a production authorization mode.
    authority = SourceFileLoader("rdg_authority",
        str(BASE / "tools/rdg-authority.py")).load_module()
    return authority.Authority(store).authorize_package(
        os.environ.get("RDG_AUTH_TOKEN"), package)


def checked_package_authority(package):
    """Keep grants locked from final authorization through durable publication."""
    store = os.environ.get("RDG_AUTH_STORE")
    if not store:
        return nullcontext(None)
    authority = SourceFileLoader("rdg_authority_commit",
        str(BASE / "tools/rdg-authority.py")).load_module()
    return authority.Authority(store).checked_transaction(
        os.environ.get("RDG_AUTH_TOKEN"), package)


def completion_context(package):
    seeds={}
    for change in package['changes']:
        path=target_path(change.get('file'))
        graph=change.get('create') if 'create' in change else read_if_exists(path)
        if isinstance(graph,dict) and graph.get('actionModel')=='candidate-v6' and not graph.get('coreModel'):
            seeds[change['file']]=graph
    if not seeds:return None
    source=BASE/'tools/rdg-completion-context.py'
    if not source.exists():
        # Older isolated single-file installations remain compatible, but never
        # silently pretend a missing cross-file engine is a local result.
        index=load_json(GRAPHS/'index.json') if (GRAPHS/'index.json').exists() else {'graphs':[]}
        for graph in seeds.values():
            check(not graph.get('expansionOf') and not any(n.get('projectionOf') for n in graph['nodes']) and
                sum(r.get('identitySpace')==graph.get('identitySpace') for r in index['graphs'])<=1,
                'COMPLETION_RESOLVER_UNAVAILABLE')
        return None
    engine=SourceFileLoader('rdg_package_completion',str(source)).load_module()
    context=engine.load(GRAPHS,seeds,authorize=authorize_completion_reads)
    return context if context.cross else None


def authorize_completion_reads(refs):
    store=os.environ.get('RDG_AUTH_STORE')
    if store:
        authority=SourceFileLoader('rdg_completion_read_auth',str(BASE/'tools/rdg-authority.py')).load_module()
        authority.Authority(store).authorize_graph_read(os.environ.get('RDG_AUTH_TOKEN'),refs)


def completion_authority_package(package,records):
    result=copy.deepcopy(package)
    requested={change['file'] for change in package['changes']}
    if not any(r.get('completionReadSet') for r in records):return result
    for record in records:
        if not record['changed']:continue
        old={e['id'] for e in (record['before'] or {}).get('events',[])}
        added=[e for e in record['after']['events'] if e['id'] not in old]
        derived=[e for e in added if e.get('type') in apply_module.V7.COMPLETION_EVENTS and
                 e.get('completionMode')=='derived']
        if record['file'] not in requested:
            check(added and len(derived)==len(added),'COMPLETION_EXTERNAL_WRITE_NOT_DERIVED')
        if not derived:continue
        # Explicitly listing an owner with an ordinary edit never authorizes its
        # derived results. Check every new result, including requested owners.
        result['changes'].append({'file':record['file'],'patch':{
            'operations':[{'op':'record_action_execution' if e['type']=='action_executed' else
                           'record_requirement_achievement','event':e,'targetId':e['targetId']} for e in derived]}})
    return result


def check_completion_reads(records,replay=False):
    for record in records:
        read_set=record.get('completionReadSet')
        if not read_set:continue
        authorize_completion_reads([p['file'] for p in read_set['sources']])
        after={r['file']:r['after'] for r in records if r['changed']} if replay else {}
        for pin in read_set['sources']:
            path=target_path(pin['file'])
            current=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            expected=(hashlib.sha256(encoded(after[pin['file']]).encode()).hexdigest()
                      if pin['file'] in after else pin['sha256'])
            check(current==expected,'COMPLETION_DEPENDENCY_CHANGED: '+pin['file'])
        if not replay:
            path=GRAPHS/'index.json'
            actual=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            check(actual==read_set['catalogSHA256'],'COMPLETION_CATALOG_CHANGED')


def derive_completion_records(context,records):
    if context is None:return
    overrides={r['file']:r['after'] for r in records if r['file'] in context.graphs}
    current=context.updated(overrides)
    states=current.evaluate()
    trigger=None
    for record in records:
        previous={e['id'] for e in (record['before'] or {}).get('events',[])}
        for event in record['after'].get('events',[]):
            if (event['id'] not in previous and event.get('authorityPrincipal') and
                event.get('recordedAt') and event.get('verifiedTrustReceipt') and
                event.get('type') in {'graph_changed','action_selected','action_withdrawn',
                    'action_reconsidered','action_executed','requirement_achieved'}):
                trigger=event
    if trigger:
        by_file={r['file']:r for r in records}
        for file,rows in states.items():
            own={nid:row for nid,row in rows.items() if not row['projection']}
            ready=[row for row in own.values() if row['complete'] and not row['eventId']]
            if not ready:continue
            graph=current.graphs[file]
            for row in ready:
                node=next(n for n in graph['nodes'] if n['id']==row['nodeId'])
                apply_module.guard_policy(node,trigger)
            record=by_file.get(file)
            if record is None:
                record={'file':file,'before':copy.deepcopy(graph),
                        'after':copy.deepcopy(graph),'changed':False}
                records.append(record);by_file[file]=record
            apply_module.V7.append_derived_completion(record['after'],trigger,states=own)
            if not record['changed']:
                record['after']['revision']+=1;record['changed']=True
            apply_module.validate(record['after'])
    # Preserve causal fact order across physical owners in one publication.
    explicit=[];derived=[]
    for record in records:
        previous={e['id'] for e in (record['before'] or {}).get('events',[])}
        for event in record['after'].get('events',[]):
            if event['id'] in previous:continue
            if event.get('completionMode')=='derived':derived.append((record['file'],event))
            else:explicit.append(event)
    rank={key:i for i,key in enumerate(current.evaluation_order)}
    derived.sort(key=lambda row:rank[(row[0],row[1]['targetId'])])
    for order,event in enumerate(explicit+[e for _,e in derived]):event['compositionOrder']=order
    records[0]['completionReadSet']={'sources':context.pins_for_journal(),
                                     'catalogSHA256':context.index_hash}
def prepare(package):
    check(isinstance(package, dict) and package.get("schemaVersion") == 1, "package schemaVersion must be 1")
    bearer = require_package_authority(package)
    changes = package.get("changes")
    # Active canonical writers support one action model. Older Option/Decision
    # source files remain readable off-line for migration, not writable workspaces.
    for change in changes or []:
        if isinstance(change,dict) and isinstance(change.get('file'),str) and change['file'].startswith('workspaces/'):
            candidate=change.get('create') or read_if_exists(target_path(change['file']))
            check(isinstance(candidate,dict) and candidate.get('actionModel')=='candidate-v6' and
                  not any(candidate.get(k) for k in ('readOnly','templateOnly','exampleOnly')),
                  'ACTIVE_ONLY_CANDIDATE_V6: old Graph model disabled')
    check(isinstance(changes, list) and changes, "changes must be a non-empty array")
    # Load new gate only for opt-in material Action operations. Legacy writer
    # remains unaffected and its isolated test harness needs no new helper.
    trust_required = any(op.get('op') in
        {'select_action', 'link_action_requirement', 'reconsider_action', 'withdraw_action', 'transition_qrpe', 'graph_edit', 'record_action_execution', 'record_requirement_achievement', 'configure_modules', 'module_operation'}
        for change in changes for op in (change.get('patch') or {}).get('operations', [])) or any(
        (c.get('create') or {}).get('actionModel') == 'candidate-v6' and
        (bool((c.get('create') or {}).get('events')) or any(
            n.get('kind') == 'action' and n.get('status') in ('selected','superseded')
            for n in (c.get('create') or {}).get('nodes', []))) for c in changes)
    local_manual = False
    if trust_required:
        trust = SourceFileLoader('rdg_v6_action_trust',
            str(BASE / 'tools/rdg-v6-action-trust.py')).load_module()
        if bearer is None:
            trust.verify_transaction(package)  # Legacy signed package unchanged.
        else:
            if 'trustedApproval' in package:
                check(os.environ.get('RDG_LOCAL_MANUAL_SESSION') == '1',
                      'BEARER_CLIENT_MUST_NOT_SUPPLY_HMAC_APPROVAL')
                trust.verify_transaction(package)
                check(package['trustedApproval']['principal'] == 'bearer:' + bearer['grantId'],
                      'MANUAL_SESSION_GRANT_MISMATCH')
                local_manual = True
    context=completion_context(package)
    seen, records, overrides = set(), [], {}
    for change in changes:
        check(isinstance(change, dict), "invalid package change")
        relative = change.get("file")
        path = target_path(relative)
        check(relative not in seen, "duplicate package file")
        seen.add(relative)
        before = read_if_exists(path)
        if "create" in change:
            check(before is None, "CREATE_CONFLICT: graph already exists")
            after = copy.deepcopy(change["create"])
            check(not after.get('coreModel') or not any(after.get(k) for k in
                  ('inheritedHistory','factLineage','relationLineage','entityLineage','externalRefs')),
                  'PORTABLE_LINEAGE_REQUIRES_PACKAGE_COORDINATOR')
            apply_module.validate(after)
            check(not any(n.get('module') for n in after['nodes']) and
                  not any(e.get('type')=='module_event' for e in after['events']),
                  'MODULE_ENTITY_CREATION_REQUIRES_OPERATION')
            check(after.get("readOnly") is not True and not after.get("templateOnly"),
                  "workspace create must be a concrete plan, not a prepared source")
            check(after["revision"] == 1, "created graph revision must be 1")
            check(after.get("planningScale") in {"module", "unit"} and
                  isinstance(after.get("identitySpace"), str) and after["identitySpace"].strip() and
                  isinstance(after.get("rootRequirementId"), str), "new graph needs scale, identitySpace and rootRequirementId")
            committed = {n["id"] for n in after["nodes"] if n["kind"] == "decision" and n.get("status") == "committed"}
            selected = {e["decisionId"] for e in after["events"] if e["type"] in {"decision_selected", "decision_revised"}}
            check(committed <= selected, "new committed Decision requires decision_selected event")
            changed = True
        else:
            check(before is not None, "MISSING_GRAPH")
            check(before.get("readOnly") is not True, "READ_ONLY_GRAPH")
            apply_module.validate(before)
            for op in (change.get('patch') or {}).get('operations', []):
                if op.get('op') == 'reconsider_action':
                    check(trust_required, 'TRUST_REQUIRED')
                    trust.verify_local_evidence(before, op)
            authoritatively_scoped_patch = copy.deepcopy(change.get("patch"))
            if before.get('coreModel'):
                evidence=SourceFileLoader('core_file_evidence',str(BASE/'tools/rdg-evidence.py')).load_module()
                for op in authoritatively_scoped_patch.get('operations',[]):
                    refs=(op.get('event') or {}).get('evidenceRefs')
                    if refs:
                        evidence.verify(BASE,refs,protected=[os.environ.get('RDG_AUTH_STORE')])
            if trust_required:
                for op in authoritatively_scoped_patch.get('operations', []):
                    if op.get('op') in {'select_action', 'link_action_requirement', 'reconsider_action', 'withdraw_action', 'transition_qrpe', 'graph_edit', 'record_action_execution', 'record_requirement_achievement', 'configure_modules', 'module_operation'}:
                        receipt_target = op.get('transition') if op.get('op') == 'transition_qrpe' else op.get('event')
                        check(isinstance(receipt_target, dict), 'TRUST_RECEIPT_TARGET_MISSING')
                        if bearer is None:
                            proof = package['trustedApproval']
                            receipt_target['verifiedTrustReceipt'] = {
                                'principal': proof['principal'], 'purpose': proof['purpose'],
                                'expiresAt': proof['expiresAt'],
                                'signature': proof['signature'],
                                'transactionId': package['transactionId'],
                                'signedChangesSHA256': trust.fingerprint(package['changes'])}
                        else:
                            # Ordinary bearers do not prove a human. The explicit local
                            # manual session binds its exact MAC to this grant;
                            # it remains local attribution, not remote identity.
                            if op.get('op') != 'transition_qrpe':
                                check(receipt_target.get('by') != 'user' or local_manual,
                                      'BEARER_CANNOT_CLAIM_USER_IDENTITY')
                            principal = 'bearer:' + bearer['grantId']
                            claimed = (op.get('authorityPrincipal') if op.get('op') == 'transition_qrpe'
                                       else receipt_target.get('authorityPrincipal'))
                            check(claimed in (None, principal),
                                  'BEARER_AUTHORITY_PRINCIPAL_MISMATCH')
                            if op.get('op') == 'transition_qrpe':
                                op['authorityPrincipal'] = principal
                            else:
                                receipt_target['authorityPrincipal'] = principal
                            receipt_target['verifiedTrustReceipt'] = {
                                'mode': 'local-manual-session' if local_manual else 'bearer', 'principal': principal,
                                'grantId': bearer['grantId'],
                                'grantRevision': bearer['grantRevision'],
                                'transactionId': package.get('transactionId'),
                                'changesSHA256': trust.fingerprint(package['changes'])}
            if bearer is not None:
                # Legacy Option/Decision has dedicated selection operations too.
                # No second client HMAC; record the API's bearer verification.
                for op in authoritatively_scoped_patch.get('operations', []):
                    if op.get('op') not in {'select_option', 'revise_decision'}:
                        continue
                    ev = op.get('event')
                    check(isinstance(ev, dict) and ev.get('by') != 'user',
                          'BEARER_CANNOT_CLAIM_USER_IDENTITY')
                    principal = 'bearer:' + bearer['grantId']
                    check(ev.get('authorityPrincipal') in (None, principal),
                          'BEARER_AUTHORITY_PRINCIPAL_MISMATCH')
                    ev['authorityPrincipal'] = principal
                    ev['verifiedTrustReceipt'] = {
                        'mode': 'local-manual-session' if local_manual else 'bearer', 'principal': principal,
                        'grantId': bearer['grantId'],
                        'grantRevision': bearer['grantRevision'],
                        'transactionId': package.get('transactionId'),
                        'changesSHA256': trust.fingerprint(package['changes']) if trust_required else
                            hashlib.sha256(json.dumps(package['changes'],
                                sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()}
            provider=None
            if context is not None:
                def provider(graph, file=relative):
                    staged={f:g for f,g in overrides.items() if f in context.graphs}
                    staged[file]=graph
                    return context.updated(staged).evaluate()[file]
            after, changed = apply_module.apply(before, authoritatively_scoped_patch,
                trusted_verified=trust_required,completion_provider=provider,
                defer_completion=context is not None)
            metadata = change.get("metadata")
            if metadata is not None:
                check(before.get('actionModel') != 'candidate-v6',
                      'ACTION_MODEL_GUARD: owner/root metadata requires dedicated history')
                check(isinstance(metadata, dict) and set(metadata) <= {"identitySpace", "rootRequirementId", "planningScale"},
                      "only identity/root/scale graph metadata may change")
                for k, v in metadata.items():
                    check(k not in before or before[k] == v, "graph identity/scale cannot be silently replaced")
                    after[k] = v
                if after != before and not changed:
                    after["revision"] += 1
                changed = after != before
        overrides[relative] = after
        records.append({"file": relative, "before": before, "after": after, "changed": changed})
    # The same catalog builder checks owners, identities, prepared versions and
    # cross-file lineage both before publication and on read-back.
    derive_completion_records(context,records)
    overrides.update({r["file"]:r["after"] for r in records})
    require_package_authority(completion_authority_package(package,records))
    manifest,payload=index_module.build_catalog(overrides)
    scoped_graphs={item['file']:item['graph'] for item in payload['graphs']}
    module_reads=[]
    for item in payload['graphs']:
        graph=item['graph']
        if graph.get('actionModel')!='candidate-v6':continue
        apply_module.MODULES.validate_references(graph,scoped_graphs)
        if item['file'] in overrides:
            module_reads.extend(r['graphFile'] for r in apply_module.MODULES.requirement_references(graph))
    if bearer is not None and module_reads:
        auth_module=SourceFileLoader('rdg_module_reference_auth',str(BASE/'tools/rdg-authority.py')).load_module()
        auth_module.Authority(os.environ['RDG_AUTH_STORE']).authorize_graph_read(
            os.environ.get('RDG_AUTH_TOKEN'),list(set(module_reads)))

    # Reconsideration can retire an introduced R only if no separate graph
    # currently owns/projects/depends on that R. Do not trust a caller's
    # single_graph_verified claim when the catalog proves otherwise.
    for record in records:
        before, after = record["before"], record["after"]
        if not before or after.get("actionModel") != "candidate-v6":
            continue
        previous = {n["id"]: n for n in before["nodes"]}
        retired = {n["id"] for n in after["nodes"]
                   if n["kind"] == "requirement" and
                   n.get("status") == "inactive" and
                   previous.get(n["id"], {}).get("status") != "inactive"}
        deleted = {rid for rid, n in previous.items() if n["kind"] == "requirement" and
                   not any(current["id"] == rid for current in after["nodes"])}
        for rid in retired | deleted:
            if rid in deleted:
                check(any(e.get("type") == "graph_changed" and
                          e.get("operation") == "delete_orphan_requirement" and
                          e.get("targetId") == rid and e.get("targetDeleted") is True and
                          isinstance(e.get("verifiedTrustReceipt"), dict)
                          for e in after["events"]), "REQUIREMENT_DELETION_EVENT_REQUIRED")
            else:
                check(any((e.get("type") in {"action_reconsidered", "action_withdrawn"} and
                       isinstance(e.get("verifiedTrustReceipt"), dict) and
                       any(d.get("requirementId") == rid and d.get("effect") == "deactivate"
                           for d in e.get("childDispositions", []))) or
                      (e.get("type") == "graph_changed" and
                       e.get("operation") == "deactivate_requirement" and
                       e.get("targetId") == rid and
                       e.get("priorNodeSnapshot", {}).get("status", "active") == "active" and
                       isinstance(e.get("verifiedTrustReceipt"), dict)) or
                      (after.get("coreModel") == "rdg-core-v1" and
                       e.get("type") == "core_requirement_necessity_changed" and
                       e.get("targetId") == rid and isinstance(e.get("decisionActionId"), str) and
                       isinstance(e.get("verifiedTrustReceipt"), dict) and
                       any(n["id"] == e["decisionActionId"] and n["kind"] == "action"
                           for n in after["nodes"]))
                      for e in after["events"]), "REQUIREMENT_RETIREMENT_EVENT_REQUIRED")
            for item in payload["graphs"]:
                other = item["graph"]
                if item["file"] == record["file"] or other.get("identitySpace") != after.get("identitySpace"):
                    continue
                check(other.get("rootRequirementId") != rid and
                      all(n.get("id") != rid and
                          n.get("projectionOf", {}).get("nodeId") != rid and
                          n.get("expansionOf", {}).get("nodeId") != rid
                          for n in other["nodes"]) and
                      not any(e.get("to") == rid or e.get("from") == rid or
                              e.get("parent") == rid for e in other.get("edges", [])),
                      "RECONSIDER_CROSS_GRAPH_DEPENDENCY: " + rid)
    bridge=SourceFileLoader("rdg_state_package",str(BASE/"tools/rdg-state.py")).load_module()
    for record in records:
        g=record["after"]
        old_ids={n["id"] for n in (record["before"] or {}).get("nodes",[])}
        for n in g["nodes"]:
            if n["id"] in old_ids or n.get("kind")!="decision" or not n.get("selectionBasis"):
                continue
            if bridge.has_state(g):
                snapshot=bridge.state_call({"items":payload["graphs"],"manifest":manifest,
                    "graphSlug":next(i["slug"] for i in payload["graphs"] if i["file"]==record["file"]),
                    "scope":n.get("scope","project")})
                n["selectionBasis"]["contextSnapshot"]=snapshot
    return records


def journal_dir():
    directory = WORKSPACES / ".transactions"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def writer_recorded_at(ignore_path=None):
    """Reject local clock regression while holding the existing writer lock."""
    now = dt.datetime.now(dt.timezone.utc)
    latest = None
    for path in journal_dir().glob("*.json"):
        if path == ignore_path:
            continue
        entry = load_json(path)
        if entry.get("schemaVersion") != 2:
            continue  # Historical v1 journals have no commit-time observation.
        check(entry.get("state") == "completed" and
              isinstance(entry.get("recordedAt"), str),
              "RECORDED_AT_HISTORY_INVALID")
        try:
            moment = dt.datetime.fromisoformat(entry["recordedAt"].replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("RECORDED_AT_HISTORY_INVALID") from error
        check(moment.tzinfo is not None and moment.utcoffset() == dt.timedelta(0),
              "RECORDED_AT_HISTORY_INVALID")
        if latest is None or moment > latest:
            latest = moment
    check(latest is None or now >= latest, "WRITER_CLOCK_REGRESSION")
    return now.isoformat()


def finish(path, journal):
    records = journal["records"]
    for record in records:
        current = read_if_exists(target_path(record["file"]))
        check(current == record["before"] or current == record["after"],
              "RECOVERY_CONFLICT: external edit in " + record["file"])
    index_module.build_catalog({r["file"]: r["after"] for r in records})
    for record in records:
        if record["changed"] and read_if_exists(target_path(record["file"])) != record["after"]:
            write_json(target_path(record["file"]), record["after"])
    for record in records:
        check(read_if_exists(target_path(record["file"])) == record["after"], "package read-back differs")
    index_module.rebuild_index()
    if journal.get("schemaVersion") == 2:
        # The graph image has been durably written and read back before this
        # observation. Recovery records its own conservative upper bound.
        check(journal.get("recordedAt") is None, "RECORDED_AT_ALREADY_SET")
        journal["recordedAt"] = writer_recorded_at(ignore_path=path)
    journal["state"] = "completed"
    write_json(path, journal)


def _recover_unlocked():
    recovered = 0
    for path in sorted(journal_dir().glob("*.json")):
        journal = load_json(path)
        if journal.get("state") == "prepared":
            finish(path, journal)
            recovered += 1
    return recovered


def recover():
    with reference_io.reference_lock(GRAPHS.parent, True):
        return _recover_unlocked()


def execute(package, dry_run=False):
    with reference_io.reference_lock(GRAPHS.parent, not dry_run, create=not dry_run):
        return _execute_unlocked(package, dry_run)


def _execute_unlocked(package, dry_run=False):
    check(isinstance(package, dict), "package must be object")
    explicit = package.get("transactionId")
    check(explicit is not None or len(package.get("changes", [])) == 1,
          "multi-file package requires transactionId")
    tid = explicit or "single-" + uuid.uuid4().hex
    check(isinstance(tid, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", tid),
          "invalid transactionId")
    digest = hashlib.sha256(encoded(package).encode()).hexdigest()
    # dry-run does not create journals, graph locks or missing graph directories.
    if dry_run:
        pending = list((WORKSPACES / ".transactions").glob("*.json"))
        check(not any(load_json(p).get("state") == "prepared" for p in pending),
              "RECOVERY_REQUIRED: apply a transaction to recover pending writes first")
        records = prepare(package)
        check_completion_reads(records)
        if explicit is None:
            r = records[0]
            print(f"DRY_RUN changed={r['changed']} revision={r['before']['revision']} -> {r['after']['revision']}")
            return records
        print("DRY_RUN changed=" + str(any(r["changed"] for r in records)) + " " +
              " ".join(f"{r['file']} revision={r['before']['revision'] if r['before'] else 0} -> {r['after']['revision']}" for r in records))
        return records
    WORKSPACES.mkdir(parents=True, exist_ok=True)
    with (WORKSPACES / ".writer.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        recovered = _recover_unlocked()
        path = journal_dir() / (tid + ".json")
        if path.exists():
            # A revoked bearer may not replay a previously accepted transaction.
            journal = load_json(path)
            require_package_authority(completion_authority_package(package,journal["records"]))
            check_completion_reads(journal["records"],replay=True)
            check(journal.get("requestSHA256") == digest, "TRANSACTION_ID_CONFLICT")
            check(journal.get("state") == "completed", "transaction did not complete")
            for record in journal["records"]:
                check(read_if_exists(target_path(record["file"])) == record["after"],
                      "REPLAY_STATE_CHANGED: the saved result was modified after this transaction")
            print(f"ALREADY_APPLIED transactionId={tid} recovered={recovered}")
            return journal["records"]
        records = prepare(package)
        if not any(r["changed"] for r in records):
            print("NO_CHANGE " + " ".join(f"revision={r['after']['revision']}" for r in records))
            return records
        # Grant changes serialize with this final check AND durable acceptance.
        # The prepared journal is the commit point: recovery finishes accepted
        # transactions even if the token is revoked after journal persistence.
        with checked_package_authority(completion_authority_package(package,records)) as accepted_actor:
            check_completion_reads(records)
            for record in records:
                check(read_if_exists(target_path(record["file"])) == record["before"],
                      "GRAPH_CHANGED_EXTERNALLY")
            # preparedAt is the technical acceptance attempt, not proof that
            # graph images were available yet. recordedAt is set only by finish
            # after graph and catalog durable writes (or later recovery).
            prepared_at = writer_recorded_at()
            journal = {"schemaVersion": 2, "transactionId": tid, "requestSHA256": digest,
                       "preparedAt": prepared_at, "recordedAt": None,
                       "state": "prepared", "records": records}
            if accepted_actor is not None:
                journal["authorityPrincipal"] = "bearer:" + accepted_actor["grantId"]
            write_json(path, journal)
            finish(path, journal)
        if explicit is None:
            r = records[0]
            print(f"APPLIED revision={r['before']['revision']} -> {r['after']['revision']} nodes={len(r['after']['nodes'])} edges={len(r['after']['edges'])}")
            return records
        print("APPLIED transactionId=" + tid + " " +
              " ".join(f"{r['file']} revision={r['before']['revision'] if r['before'] else 0} -> {r['after']['revision']}" for r in records))
        return records
