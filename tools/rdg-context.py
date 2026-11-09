#!/usr/bin/env python3
"""Read-only, project-scoped canon-directed RDG lookup with dated applicability."""
import argparse, importlib.machinery, json, re, sys
from datetime import date, datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
INDEX=ROOT/"graphs/index.json"

def iso_date(value):
    if not isinstance(value,str) or not value:return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}",value):return date.fromisoformat(value)
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
        if parsed.tzinfo is not None:parsed=parsed.astimezone(timezone.utc)
        return parsed.date()
    except ValueError:return None

def applicability(record,target_scope,as_of):
    day=iso_date(as_of)
    if day is None:raise ValueError("as-of must be YYYY-MM-DD or ISO datetime")
    since=record.get("effectiveAt",record.get("validFrom"))
    until=record.get("validUntil",record.get("validTo"))
    start=iso_date(since) if since is not None else None
    end=iso_date(until) if until is not None else None
    if (since is not None and start is None) or (until is not None and end is None):
        t="invalid-time"
    elif start is not None and start>day:t="future"
    elif end is not None and day>end:t="expired"
    elif start is None and end is None:t="undated"
    else:t="effective"
    source_scope=record.get("scope")
    if source_scope in ("project","global","*"):sc="project-wide"
    elif source_scope in (None,""):sc="unspecified"
    elif target_scope is None:sc="not-checked"
    elif source_scope==target_scope:sc="matched"
    else:sc="not-proven"
    if t in ("future","expired","invalid-time"):verdict="not-current"
    elif t=="undated" or sc in ("unspecified","not-checked","not-proven"):
        verdict="needs-assessment"
    else:verdict="applicable"
    return {"verdict":verdict,"timeStatus":t,"scopeStatus":sc,
            "targetScope":target_scope,"asOf":day.isoformat()}

def lookup(space,graph_slug,option_id,target_scope=None,as_of=None):
    as_of=as_of or datetime.now(timezone.utc).date().isoformat()
    manifest=json.loads(INDEX.read_text(encoding="utf-8"))
    ctx=manifest.get("projectContexts",{}).get(space)
    if not ctx:raise ValueError("no indexed writable project for identitySpace")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*",graph_slug):
        raise ValueError("invalid graph slug")
    entries=[g for g in manifest["graphs"] if g["slug"]==graph_slug and g["group"]=="workspaces"]
    if len(entries)!=1 or graph_slug not in ctx["graphSlugs"]:
        raise ValueError("graph is not part of selected writable identitySpace")
    file=(ROOT/"graphs"/entries[0]["file"]).resolve()
    if not file.is_relative_to((ROOT/"graphs/workspaces").resolve()):
        raise ValueError("only writable workspace graphs are supported")
    graph=json.loads(file.read_text(encoding="utf-8"))
    if graph.get("identitySpace")!=space:
        raise ValueError("project identity changed since catalog build; rebuild index")
    matches=[n for n in graph["nodes"] if n["id"]==option_id and n["kind"]=="option"]
    if len(matches)!=1:raise ValueError("option not found in selected graph")
    option=matches[0]
    if target_scope is None:target_scope=option.get("scope")
    records=ctx["records"]
    by_id={}
    for r in records:by_id.setdefault(r["id"],[]).append(r)
    groups={(col["graphSlug"],col["id"]):col for col in ctx["collections"]}
    checks=[]
    for polarity in ("recommended","contraindicated"):
        for case in option["canonBlock"][polarity]:
            matched=[];gaps=[];queries=[]
            for rid in case.get("checkRequirements",[]):
                found=by_id.get(rid,[])
                matched.extend(found)
                if not found:gaps.append({"requirementId":rid,"status":"unknown"})
                queries.append({"requirementId":rid,"status":"indexed-present" if found else "unknown"})
            for ref in case.get("checkCollections",[]):
                if isinstance(ref,str):owner,collid=graph_slug,ref
                elif isinstance(ref,dict):owner,collid=ref["graphSlug"],ref["collectionId"]
                else:raise ValueError("invalid collection reference")
                item={"graphSlug":owner,"collectionId":collid}
                col=groups.get((owner,collid))
                if not col:
                    gaps.append({**item,"status":"unknown"})
                    queries.append({**item,"status":"unknown"})
                    continue
                ids=set(col["memberRefs"])
                found=[r for r in records if r["graphSlug"]==owner and r["id"] in ids]
                matched.extend(found)
                queries.append({**item,"status":"indexed-collection","activeMembers":len(found)})
            for category in case.get("checkCategories",[]):
                queries.append({"category":category,"status":"not-fully-checked"})
                gaps.append({"categoryDirection":category,"status":"not-fully-checked",
                             "reason":"Semantic category coverage needs independent investigation"})
            if not queries:
                gaps.append({"status":"not-fully-checked",
                             "reason":"Canon provides no machine-checkable queries"})
            annotated=[]
            for record in sorted({r["graphSlug"]+":"+r["id"]:r for r in matched}.values(),
                                 key=lambda r:(r["graphSlug"],r["id"])):
                annotated.append({**record,"applicability":applicability(record,target_scope,as_of)})
            good=[r for r in annotated if r["applicability"]["verdict"]=="applicable"]
            uncertain=[r for r in annotated if r["applicability"]["verdict"]=="needs-assessment"]
            excluded=[r for r in annotated if r["applicability"]["verdict"]=="not-current"]
            if uncertain:
                gaps.append({"status":"applicability-unverified",
                             "recordRefs":[r["graphSlug"]+":"+r["id"] for r in uncertain]})
            checks.append({"caseId":case["id"],"polarity":polarity,"canonText":case["text"],
                           "queries":queries,"relevantCandidates":good,
                           "candidatesNeedingAssessment":uncertain,
                           "excludedCandidates":excluded,"uncertainties":gaps,
                           "conclusion":"needs-human-assessment"})
    return {"identitySpace":space,"graphSlug":graph_slug,"optionId":option_id,
            "asOf":iso_date(as_of).isoformat(),"targetScope":target_scope,
            "projectGraphSlugs":ctx["graphSlugs"],"availableProjectRecords":len(records),
            "canonChecks":checks,
            "coverage":"indexed workspace files only; external and unavailable sources are unknown",
            "selectedDecision":False,"overallVerdict":"not-evaluated"}

def fields_lookup(graph_slug=None,root_graph_slug=None,space=None,target_scope="project"):
    from importlib.machinery import SourceFileLoader
    bridge=SourceFileLoader("rdg_state_query",str(ROOT/"tools/rdg-state.py")).load_module()
    manifest=json.loads(INDEX.read_text(encoding="utf-8"))
    items=[]
    for entry in manifest["graphs"]:
        path=(ROOT/"graphs"/entry["file"]).resolve()
        if not path.is_relative_to((ROOT/"graphs").resolve()):
            raise ValueError("catalog path outside graphs")
        if path.is_file():
            items.append({**entry,"graph":json.loads(path.read_text(encoding="utf-8"))})
    return bridge.state_call({"items":items,"manifest":manifest,"graphSlug":graph_slug,"rootGraphSlug":root_graph_slug,
                              "identitySpace":space,"scope":target_scope or "project"})

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--identity-space")
    ap.add_argument("--graph-slug")
    ap.add_argument("--root-graph-slug")
    ap.add_argument("--fields",action="store_true",help="List declared context fields and shared project answers")
    ap.add_argument("--option-id")
    ap.add_argument("--target-scope",help="Explicit target scope (no default global scope)")
    ap.add_argument("--as-of",help="YYYY-MM-DD date for effective-time filtering (UTC today default)")
    x=ap.parse_args()
    if x.fields:
        if bool(x.graph_slug)==bool(x.root_graph_slug):ap.error("--fields needs exactly one of --graph-slug / --root-graph-slug")
        if x.as_of:ap.error("--as-of belongs to the legacy canon lookup; --fields reads current project state")
        print(json.dumps(fields_lookup(x.graph_slug,x.root_graph_slug,x.identity_space,x.target_scope),ensure_ascii=False,indent=2))
        return
    if not all((x.identity_space,x.graph_slug,x.option_id)):ap.error("canon lookup needs --identity-space, --graph-slug and --option-id")
    print(json.dumps(lookup(x.identity_space,x.graph_slug,x.option_id,
                            x.target_scope,x.as_of),ensure_ascii=False,indent=2))
if __name__=="__main__":
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print("ERROR: "+str(exc),file=sys.stderr);sys.exit(2)
