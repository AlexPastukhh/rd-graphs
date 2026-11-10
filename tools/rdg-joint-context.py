#!/usr/bin/env python3
"""Scoped joint historical context from existing local owners.

Candidate applicability is selected by two times. Accepted-future mode requires
an exact baseline state revision; automatic effective-time lifecycle selection
and factual event verification remain unsupported.
"""
import argparse
import copy
import datetime as dt
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = SourceFileLoader("joint_applicability", str(HERE/"rdg-applicability-owner.py")).load_module()
BASELINE = SourceFileLoader("joint_baseline", str(HERE/"rdg-future-baseline-owner.py")).load_module()
EVENT_PROJECTION = SourceFileLoader("joint_event_projection", str(HERE/"rdg-event-gendocen.py")).load_module()
MODEL, OWNER, HISTORY = APP.MODEL, APP.OWNER, APP.HISTORY
GROUPS = ("query", "lifecycle", "applicability", "plan", "graphs", "event",
          "assessment", "boundaries")
VERSION = "rdg-joint-review/v1"
READ_MATRIX = {key:[key+"/*"] for key in (
    "query","lifecycle","applicability","plan","graphs","event","assessment","boundaries")}
BOUNDARIES = {"readOnly":True,"scenarioOnly":True,
    "scopedExactContextResolved":True,"knownAtCutoffsChecked":True,
    "completeApplicableContextVerified":False,
    "automaticBaselineEffectiveSelectionComplete":False,
    "applicabilityAttested":False,"factualEventVerified":False,
    "factualBranchResolved":False,"historicalT1KnowledgeVerified":False,
    "actionSelected":False,"productionAccepted":False}


def require(ok, code):
    if not ok:
        raise ValueError("JOINT_CONTEXT_"+code)


def validate_query(query):
    require(isinstance(query, dict) and set(query) == {
        "schemaVersion", "mode", "lifecycle", "planFile", "knownAt",
        "effectiveAt", "scenario", "occurrenceId", "baselineStateRevision"} and
        type(query["schemaVersion"]) is int and query["schemaVersion"] == 1 and
        query["mode"] == "scoped-joint-context" and
        query["lifecycle"] in ("candidate", "accepted-future") and
        isinstance(query["planFile"], str) and OWNER.TARGET.fullmatch(query["planFile"]) and
        isinstance(query["occurrenceId"], str) and MODEL.ID.fullmatch(query["occurrenceId"]),
        "REQUEST_SCHEMA")
    MODEL.known(query["knownAt"])
    MODEL.effective(query["effectiveAt"])
    scenario = query["scenario"]
    require(isinstance(scenario, dict) and set(scenario) == {"branchId","outcome"} and
            all(isinstance(v,str) and OWNER.PLAN.ident(v) for v in scenario.values()),
            "SCENARIO_REQUIRED")
    revision = query["baselineStateRevision"]
    require((revision is None if query["lifecycle"] == "candidate" else
             type(revision) is int and revision >= 1), "EXACT_BASELINE_STATE_REQUIRED")


def known_applicability(root, plan_file, cutoff):
    path = APP.target_path(root, plan_file)
    require(path.is_file(), "APPLICABILITY_HISTORY_NOT_FOUND")
    store = APP.validate_store(HISTORY.load_bytes(path.read_bytes()), plan_file)
    result, previous = [], None
    for record in store["records"]:
        receipt = APP.read_receipt(root, plan_file, record)
        require(receipt is not None, "APPLICABILITY_AVAILABILITY_MISSING")
        available = MODEL.known(receipt["availableBy"])
        require(previous is None or available >= previous, "AVAILABILITY_CLOCK_ORDER")
        previous = available
        if available <= cutoff:
            result.append({"assertion":copy.deepcopy(record["assertion"]),
                           "recordDigest":record["digest"],
                           "recordedAt":record["recordedAt"],
                           "availableBy":receipt["availableBy"]})
    require(result, "NO_KNOWN_APPLICABILITY")
    return result


def baseline_ancestry(records, pin):
    matches = [r for r in records if r["assertion"]["source"]["plan"] == pin]
    require(len(matches) == 1, "BASELINE_APPLICABILITY_NOT_FOUND")
    by_id = {r["assertion"]["id"]:r for r in records}
    selected, current = set(), matches[0]
    while current is not None:
        ident = current["assertion"]["id"]
        require(ident not in selected, "APPLICABILITY_CYCLE")
        selected.add(ident)
        prior = current["assertion"]["supersedes"]
        require(prior is None or prior in by_id, "APPLICABILITY_ANCESTOR_MISSING")
        current = by_id[prior] if prior is not None else None
    return [r for r in records if r["assertion"]["id"] in selected]


def graph_context(exact, cutoff):
    graphs = []
    for item in exact["graphSnapshots"]:
        provenance = item["provenance"]
        after = [s for s in provenance["sources"] if s["side"] == "after" and
                 s["recordedAt"] is not None and MODEL.known(s["recordedAt"]) <= cutoff]
        require(len(after) == 1, "DIRECT_GRAPH_AVAILABILITY_PROOF_REQUIRED")
        # Later before-images are supporting current history, not evidence
        # known at the historical cutoff. Keep only the direct after witness.
        graphs.append({"pin":{k:provenance[k] for k in (
                            "graphFile","identitySpace","revision","snapshotSHA256")},
                       "snapshot":copy.deepcopy(item["graph"]),
                       "recordedAt":provenance["recordedAt"],
                       "source":copy.deepcopy(after[0])})
    return sorted(graphs,key=lambda g:(g["pin"]["identitySpace"],g["pin"]["graphFile"],
                                      g["pin"]["revision"]))


def resolve(plan_root, graphs_root, authority_store, token, request, before_return=None):
    validate_query(request)
    root = OWNER.root_path(plan_root)
    cutoff = MODEL.known(request["knownAt"])
    require(cutoff <= dt.datetime.now(dt.timezone.utc), "FUTURE_KNOWN_AT_UNSUPPORTED")
    query = copy.deepcopy(request)
    query["knownAt"] = cutoff.isoformat()
    effective_precision,effective_value = MODEL.effective(query["effectiveAt"])
    if effective_precision == "instant":query["effectiveAt"] = effective_value.isoformat()
    plan_file = query["planFile"]
    authority = OWNER.AUTH.Authority(authority_store)
    authority.authorize_plan(token, ["plan.read"], plan_file)
    # All four Plan-root writers use this same lock. Nested readers take
    # shared locks; no owner append can split this combined source read.
    with OWNER.IO.reference_lock(Path(graphs_root).absolute().parent, False, create=False), OWNER.root_lock(root, False):
        journals = [OWNER.safe(root,OWNER.JOURNAL,True),APP.journal_path(root),
                    BASELINE.journal_path(root),EVENT_PROJECTION.EVENT.journal_path(root)]
        require(not any(p.exists() for p in journals), "RECOVERY_REQUIRED")
        records = known_applicability(root,plan_file,cutoff)
        if query["lifecycle"] == "accepted-future":
            baseline = BASELINE.read(root,authority_store,token,plan_file,
                query["baselineStateRevision"],query["knownAt"])
            require(baseline["state"] == "accepted", "BASELINE_WITHDRAWN")
            records = baseline_ancestry(records,baseline["planPin"])
            lifecycle = {k:copy.deepcopy(baseline[k]) for k in (
                "lifecycle","state","stateRevision","recordDigest","recordedAt",
                "availableBy","planPin","basis")}
            lifecycle["selectionMode"] = "exact-baseline-state"
        else:
            lifecycle = {"lifecycle":"candidate","selectionMode":"candidate-applicability",
                         "baselineStateRevision":None}
        for record in records:
            bound,_ = MODEL.availability(root,record["assertion"]["source"]["plan"])
            require(bound is not None and MODEL.known(bound)<=cutoff,
                    "APPLICABILITY_SOURCE_NOT_PROVEN_KNOWN")
        result = MODEL.resolve(root,graphs_root,authority_store,token,{
            "schemaVersion":1,"mode":"candidate-two-time-scenario",
            "knownAt":query["knownAt"],"effectiveAt":query["effectiveAt"],
            "assertions":[r["assertion"] for r in records]})
        selected = next(r for r in records if
                        r["assertion"]["id"] == result["selectedAssertionId"])
        source, exact = selected["assertion"]["source"], result["exactSource"]
        require(source["scenario"] == query["scenario"], "SCENARIO_APPLICABILITY_MISMATCH")
        if query["lifecycle"] == "accepted-future":
            require(source["plan"] == lifecycle["planPin"], "BASELINE_NOT_APPLICABLE")
        event = EVENT_PROJECTION.from_owner(root,authority_store,token,plan_file,
                                            query["occurrenceId"],query["knownAt"])
        EVENT_PROJECTION.build_contract(event)
        event_inputs = event["data"]["reviewInputs"]
        require(not event_inputs["resolution"]["claimConflict"] and
                len(event_inputs["resolution"]["unresolvedClaimIds"]) == 1,
                "EVENT_CLAIM_CONFLICT")
        leaf_id = event_inputs["resolution"]["unresolvedClaimIds"][0]
        leaf = event_inputs["claims"][leaf_id]["payload"]
        require(leaf["planPin"] == source["plan"], "EVENT_PLAN_PIN_MISMATCH")
        branch = next(b for b in exact["plan"]["branches"]
                      if b["id"] == query["scenario"]["branchId"])
        require(leaf["eventStepId"] == branch["eventStepId"] and
                leaf["outcome"] == query["scenario"]["outcome"],
                "EVENT_SCENARIO_MISMATCH")
        precision, effective = MODEL.effective(query["effectiveAt"])
        event_precision, occurred = MODEL.effective(leaf["occurredAt"])
        require(precision == event_precision, "EVENT_TIME_PRECISION_MISMATCH")
        require(occurred <= effective, "EVENT_AFTER_EFFECTIVE_AT")
        context = {"schemaVersion":1,"status":"scoped-joint-context","query":query,
            "lifecycle":lifecycle,
            "applicability":{"selectedAssertionId":result["selectedAssertionId"],
                "selectedRecordDigest":selected["recordDigest"],
                "records":records,"excluded":result["excluded"],
                "scope":"candidate-history" if query["lifecycle"]=="candidate" else
                        "exact-baseline-assertion-and-ancestors"},
            "plan":{"pin":copy.deepcopy(source["plan"]),"snapshot":exact["plan"],
                    "recordedAt":exact["planProvenance"]["recordedAt"],
                    "availableBy":exact["planAvailableBy"],
                    "availabilitySource":exact["planAvailabilitySource"]},
            "graphs":graph_context(exact,cutoff),"event":event,
            "assessment":exact["impact"],
            "boundaries":copy.deepcopy(BOUNDARIES)}
        targets = sorted({p["graphFile"] for r in records
                          for p in r["assertion"]["source"]["graphs"]})
    validate_context(context)
    if before_return:
        before_return()
    authority.authorize_snapshot_read(token,plan_file,targets)
    return context


def validate_context(context):
    require(isinstance(context,dict) and set(context) == {
        "schemaVersion","status",*GROUPS} and type(context["schemaVersion"]) is int and
        context["schemaVersion"] == 1 and context["status"] == "scoped-joint-context",
        "CONTEXT_SCHEMA")
    query = context["query"];validate_query(query)
    cutoff = MODEL.known(query["knownAt"])
    require(cutoff <= dt.datetime.now(dt.timezone.utc),"FUTURE_KNOWN_AT_UNSUPPORTED")
    require(isinstance(context["boundaries"],dict) and
            set(context["boundaries"]) == set(BOUNDARIES) and
            all(context["boundaries"][k] is v for k,v in BOUNDARIES.items()),
            "UNSUPPORTED_TRUST_OR_SCOPE")
    app = context["applicability"]
    require(isinstance(app,dict) and set(app) == {"selectedAssertionId",
        "selectedRecordDigest","records","excluded","scope"} and
        isinstance(app["records"],list) and app["records"],"APPLICABILITY_SCHEMA")
    by_id,eligible = {},[]
    precision,effective = MODEL.effective(query["effectiveAt"])
    for record in app["records"]:
        require(isinstance(record,dict) and set(record) == {
            "assertion","recordDigest","recordedAt","availableBy"} and
            isinstance(record["recordDigest"],str) and
            HISTORY.SHA.fullmatch(record["recordDigest"]),"APPLICABILITY_RECORD_SCHEMA")
        assertion = APP.validate_assertion(record["assertion"])
        ident = assertion["id"]
        require(ident not in by_id and
                assertion["source"]["plan"]["file"] == query["planFile"],
                "APPLICABILITY_SCOPE")
        require(MODEL.known(record["recordedAt"]) <=
                MODEL.known(record["availableBy"]) <= cutoff,"APPLICABILITY_CUTOFF")
        p,value = MODEL.effective(assertion["effectiveAt"])
        require(p == precision,"EFFECTIVE_AT_PRECISION_MISMATCH")
        prior = by_id.get(assertion["supersedes"])
        require(assertion["supersedes"] is None or prior is not None and
                prior["assertion"]["source"]["plan"]["revision"] <
                assertion["source"]["plan"]["revision"] and
                MODEL.effective(prior["assertion"]["effectiveAt"])[1] <= value,
                "APPLICABILITY_CHAIN")
        by_id[ident] = record
        if value <= effective:eligible.append(record)
    superseded = {r["assertion"]["supersedes"] for r in eligible}
    leaves = [r for r in eligible if r["assertion"]["id"] not in superseded]
    require(len(leaves)==1 and leaves[0]["assertion"]["id"]==app["selectedAssertionId"],
            "APPLICABILITY_SELECTION")
    selected = by_id[app["selectedAssertionId"]]
    source = selected["assertion"]["source"]
    excluded = [{"id":r["assertion"]["id"],"reason":"effective-after-query"}
                for r in app["records"] if MODEL.effective(r["assertion"]["effectiveAt"])[1]>effective]
    require(app["excluded"]==excluded,"APPLICABILITY_EXCLUSION_MISMATCH")
    require(all(r["assertion"]["source"]["plan"]["identitySpace"]==source["plan"]["identitySpace"] and
                r["assertion"]["source"]["plan"]["planId"]==source["plan"]["planId"] and
                r["assertion"]["source"]["scenario"]["branchId"]==query["scenario"]["branchId"]
                for r in app["records"]),"APPLICABILITY_OWNER_SCOPE")
    require(selected["recordDigest"] == app["selectedRecordDigest"] and
            source["scenario"] == query["scenario"],"SELECTED_SOURCE_MISMATCH")
    plan = context["plan"]
    require(isinstance(plan,dict) and set(plan) == {
        "pin","snapshot","recordedAt","availableBy","availabilitySource"} and
        plan["pin"] == source["plan"],"PLAN_CONTEXT_SCHEMA")
    OWNER.PLAN.validate(plan["snapshot"])
    require(OWNER.digest(plan["snapshot"]) == plan["pin"]["snapshotSHA256"] and
            plan["snapshot"]["identitySpace"] == plan["pin"]["identitySpace"] and
            plan["snapshot"]["id"] == plan["pin"]["planId"] and
            plan["snapshot"]["revision"] == plan["pin"]["revision"],"PLAN_SNAPSHOT_MISMATCH")
    require(MODEL.known(plan["recordedAt"]) <= MODEL.known(plan["availableBy"]) <= cutoff,
            "PLAN_AVAILABILITY_CUTOFF")
    life = context["lifecycle"]
    if query["lifecycle"] == "candidate":
        require(life == {"lifecycle":"candidate","selectionMode":"candidate-applicability",
                         "baselineStateRevision":None} and
                app["scope"]=="candidate-history","CANDIDATE_LIFECYCLE")
    else:
        require(isinstance(life,dict) and set(life) == {
            "lifecycle","state","stateRevision","recordDigest","recordedAt",
            "availableBy","planPin","basis","selectionMode"} and
            life["lifecycle"]=="accepted-future" and life["state"]=="accepted" and
            life["stateRevision"]==query["baselineStateRevision"] and
            life["selectionMode"]=="exact-baseline-state" and
            life["planPin"]==plan["pin"] and
            isinstance(life["basis"],str) and bool(life["basis"].strip()) and
            isinstance(life["recordDigest"],str) and HISTORY.SHA.fullmatch(life["recordDigest"]) and
            app["scope"]=="exact-baseline-assertion-and-ancestors",
            "BASELINE_CONTEXT_MISMATCH")
        require(MODEL.known(life["recordedAt"]) <= MODEL.known(life["availableBy"]) <= cutoff,
                "BASELINE_AVAILABILITY_CUTOFF")
        require(baseline_ancestry(app["records"],life["planPin"])==app["records"],
                "BASELINE_ANCESTRY_SCOPE")
    graphs,expected = {},{HISTORY.graph_key(p):p for p in source["graphs"]}
    require(isinstance(context["graphs"],list) and
            len(context["graphs"])==len(expected),"GRAPH_CONTEXT_REQUIRED")
    for graph in context["graphs"]:
        require(isinstance(graph,dict) and set(graph)=={
            "pin","snapshot","recordedAt","source"},"GRAPH_CONTEXT_SCHEMA")
        key = HISTORY.graph_key(graph["pin"])
        require(key in expected and key not in graphs and graph["pin"]==expected[key],
                "GRAPH_PINS_MISMATCH")
        HISTORY.GRAPH.validate(graph["snapshot"])
        require(OWNER.digest(graph["snapshot"])==graph["pin"]["snapshotSHA256"] and
                graph["snapshot"]["identitySpace"]==key[0] and
                graph["snapshot"]["revision"]==key[2],"GRAPH_SNAPSHOT_MISMATCH")
        proof = graph["source"]
        require(isinstance(proof,dict) and set(proof)=={
            "journal","journalSHA256","transactionId","side","recordedAt"} and
            proof["side"]=="after" and isinstance(proof["transactionId"],str) and
            HISTORY.TX.fullmatch(proof["transactionId"]) and
            proof["journal"]=="workspaces/.transactions/"+proof["transactionId"]+".json" and
            isinstance(proof["journalSHA256"],str) and
            HISTORY.SHA.fullmatch(proof["journalSHA256"]) and
            proof["recordedAt"]==graph["recordedAt"] and
            MODEL.known(graph["recordedAt"])<=cutoff,"GRAPH_PROOF_CUTOFF")
        graphs[key] = graph["snapshot"]
    EVENT_PROJECTION.build_contract(context["event"])
    event = context["event"]["data"]["reviewInputs"]
    require(event["identity"]["planFile"]==query["planFile"] and
            event["identity"]["occurrenceId"]==query["occurrenceId"] and
            event["knowledge"]["knownAt"]==query["knownAt"] and
            not event["resolution"]["claimConflict"] and
            len(event["resolution"]["unresolvedClaimIds"])==1,"EVENT_CONTEXT_MISMATCH")
    leaf = event["claims"][event["resolution"]["unresolvedClaimIds"][0]]["payload"]
    branch = next(b for b in plan["snapshot"]["branches"]
                  if b["id"]==query["scenario"]["branchId"])
    require(leaf["planPin"]==plan["pin"] and leaf["eventStepId"]==branch["eventStepId"] and
            leaf["outcome"]==query["scenario"]["outcome"],"EVENT_SCENARIO_MISMATCH")
    p,occurred = MODEL.effective(leaf["occurredAt"])
    require(p==precision and occurred<=effective,"EVENT_TIME_MISMATCH")
    expected_assessment = HISTORY.IMPACT.assess(plan["snapshot"],None,
        graph_resolver=lambda ref:copy.deepcopy(graphs[
            (ref["identitySpace"],ref["graphFile"],ref["observedGraphRevision"])]),
        scenario=query["scenario"])
    require(context["assessment"]==expected_assessment,"ASSESSMENT_INCOMPLETE_OR_STALE")


def views(context):
    validate_context(context)
    result = {key:copy.deepcopy(context[key]) for key in GROUPS}
    result["event"] = copy.deepcopy(context["event"]["data"]["reviewInputs"])
    require(set(result)==set(GROUPS)==set(READ_MATRIX),
            "SOURCE_GROUPS_INCOMPLETE_OR_UNKNOWN")
    return result


def project(context):
    inputs = views(context)
    ident = "rdg.context."+EVENT_PROJECTION.digest({
        "query":context["query"],"identitySpace":context["plan"]["pin"]["identitySpace"],
        "planId":context["plan"]["pin"]["planId"]})[:24]
    return {"$docengine":{"resource_id":ident,"materialize":[]},
            "data":{"sourceContext":copy.deepcopy(context),
                "reviewCoverage":{"contract":VERSION,"scope":"declared-plan-branch-occurrence",
                    "completeForDeclaredScope":True,"sourceReads":copy.deepcopy(READ_MATRIX),
                    "completeApplicableContextVerified":False},
                "reviewInputs":inputs,"semanticSHA256":EVENT_PROJECTION.digest(inputs)}}


def build_contract(resource):
    require(isinstance(resource,dict) and set(resource)=={"$docengine","data"} and
            isinstance(resource["data"],dict) and set(resource["data"])=={
                "sourceContext","reviewCoverage","reviewInputs","semanticSHA256"},
            "RESOURCE_SCHEMA")
    require(resource==project(resource["data"]["sourceContext"]),
            "PROJECTION_INCOMPLETE_OR_STALE")
    ref = EVENT_PROJECTION.resource_ref(resource)
    return {"contract":VERSION,"completeForDeclaredScope":True,
            "subscriptions":[(ref+"#/reviewCoverage","exact")]+[
                (ref+"#/reviewInputs/"+key,"exact") for key in GROUPS]}


def assert_coverage(contract,declared):
    require(contract.get("contract")==VERSION and
            contract.get("completeForDeclaredScope") is True,"UNKNOWN_CONTRACT")
    expected = {tuple(x) for x in contract["subscriptions"]}
    require(expected=={tuple(x) for x in declared} and len(declared)==len(expected),
            "SUBSCRIPTIONS_INCOMPLETE")


def project_config(targets):
    return (
        "import json\nfrom pathlib import Path\n"
        "from importlib.machinery import SourceFileLoader\n"
        f"joint = SourceFileLoader('joint_review_contract', {str(Path(__file__).resolve())!r}).load_module()\n"
        "def register_builders(registry):\n    pass\n\n"
        "def register_semantic_dependencies(registry):\n"
        "    docs = Path(__file__).resolve().parents[1] / 'docs'\n"
        f"    for target,relative in {targets!r}:\n"
        "        resource = json.loads((docs/relative).read_text(encoding='utf8'))\n"
        "        contract = joint.build_contract(resource)\n"
        "        sources = contract['subscriptions']\n"
        "        joint.assert_coverage(contract,sources)\n"
        "        registry.register('file://review/'+target+'.md',sources,\n"
        f"                          rule_id={VERSION.replace('/','.')!r}+'.'+target,\n"
        "                          dependency_type='semantic_review')\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-root",required=True,type=Path)
    parser.add_argument("--graphs-root",required=True,type=Path)
    parser.add_argument("--store",default=os.environ.get("RDG_AUTH_STORE"))
    parser.add_argument("--request",required=True,type=Path)
    parser.add_argument("--projection",action="store_true")
    args = parser.parse_args()
    require(args.store,"AUTH_STORE_REQUIRED")
    context = resolve(args.plan_root,args.graphs_root,args.store,
        os.environ.get("RDG_AUTH_TOKEN"),HISTORY.load_bytes(args.request.read_bytes()))
    print(json.dumps(project(context) if args.projection else context,
        ensure_ascii=False,sort_keys=True,indent=2))


if __name__=="__main__":
    main()
