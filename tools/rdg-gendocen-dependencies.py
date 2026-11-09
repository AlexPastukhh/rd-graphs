#!/usr/bin/env python3
"""Scoped freshness inputs for the candidate, one-event Temporal Plan pilot.

Read-only projection/registration contract; not truth, authority or a full
Finding evaluator. Recompute after every source change before engine checks.
"""
import copy
import json
from pathlib import Path

VERSION = "rdg-temporal-review/v2"
READ_MATRIX = {
    "identity": ["identitySpace", "planId", "planStatus", "sourcePath", "actionRefsByStep/{step}"],
    "branches": ["branchesById/*/eventStepId", "branchesById/*/cases",
                 "stepsById/*/state", "stepsById/*/outcomes"],
    "steps": ["stepsById/*/{id,kind,title,state,actionRef,outcomes}"],
    "sequence": ["sequenceByPair/*/{before,after,minDelayDays}"],
    "timeConstraints": ["timeConstraintsByStep/*/{stepId,type,at,strength,basis}"],
}
GRAPH_READS = ["identitySpace", "graphFile", "rootRequirementId", "actionModel",
               "nodesById/{action}/{id,kind,title,status,actionType,canonBlock,qrpe,selectionBasis}"]


def require(value, code):
    if not value:
        raise ValueError("RDG_REVIEW_COVERAGE_" + code)


def pointer(value):
    return value.replace("~", "~0").replace("/", "~1")


def resource_ref(resource):
    return "resource://" + resource["$docengine"]["resource_id"].replace(".", "/", 1)


def graph_views(data):
    identity = {k: data[k] for k in
                ("identitySpace", "graphFile", "rootRequirementId", "actionModel")}
    nodes = {
        aid: {k: node.get(k) for k in
              ("id", "kind", "title", "status", "actionType", "canonBlock", "qrpe", "selectionBasis")}
        for aid, node in data["nodesById"].items() if node.get("kind") == "action"
    }
    return copy.deepcopy({"reviewIdentity": identity, "reviewNodesById": nodes})


def closure(seed, edges, direction):
    result, todo = set(seed), list(seed)
    while todo:
        sid = todo.pop()
        for edge in edges:
            start, end = ((edge["before"], edge["after"]) if direction == "forward"
                          else (edge["after"], edge["before"]))
            if start == sid and end not in result:
                result.add(end)
                todo.append(end)
    return result


def plan_views(data):
    branches = list(data["branchesById"].values())
    coverage = {"contract": VERSION, "scope": "one-conditional-event/current-projection",
                "complete": len(branches) <= 1 and not any(s.get("kind") == "requirement" for s in data["stepsById"].values()), "sourceReads": READ_MATRIX,
                "graphReads": GRAPH_READS,
                "historicalSnapshotAvailable": False}
    if not coverage["complete"]:
        coverage["diagnostic"] = "REQUIREMENT_STEPS_NOT_COVERED" if any(s.get("kind") == "requirement" for s in data["stepsById"].values()) else "MULTI_BRANCH_NOT_COVERED"
        return {"reviewCoverage": coverage, "reviewInputsByStep": {}}
    steps = data["stepsById"]
    possible = {sid for sid, step in steps.items() if step["state"] == "possible"}
    branch = branches[0] if branches else None
    cases = branch["cases"] if branch else [{"outcome": None, "stepIds": []}]
    views = {}
    produced_groups = {"identity", "branches", "steps", "sequence", "timeConstraints"}
    require(set(READ_MATRIX) == produced_groups, "SOURCE_GROUPS_INCOMPLETE_OR_UNKNOWN")
    for sid, step in sorted(steps.items()):
        if step["kind"] != "action":
            continue
        facets = {key: {} for key in ("branches", "steps", "sequence", "timeConstraints")}
        facets["identity"] = {k: data[k] for k in ("identitySpace", "planId", "planStatus")}
        facets["identity"]["sourcePath"] = data.get("sourcePath")
        facets["identity"]["actionRef"] = data["actionRefsByStep"][sid]
        # Computed groups are the independent producer obligation. A mutable
        # declaration cannot remove a group that the extractor still produces.
        require(set(READ_MATRIX) == set(facets), "SOURCE_GROUPS_INCOMPLETE_OR_UNKNOWN")
        for case in sorted(cases, key=lambda c: c["outcome"] or ""):
            active = (set(steps) - possible) | set(case["stepIds"])
            if sid not in active:
                continue
            edges = [e for e in data["sequenceByPair"].values()
                     if e["before"] in active and e["after"] in active]
            # The existing review includes all active deadlines, including the
            # shared delivery milestone; their indirect prerequisites matter.
            deadlines = {key for key, rules in data["timeConstraintsByStep"].items()
                         if key in active and any(r["type"] == "deadline" for r in rules)}
            related = (closure({sid}, edges, "forward") |
                       closure({sid} | deadlines, edges, "reverse"))
            if branch:
                related.add(branch["eventStepId"])
            label = case["outcome"] or "unconditional"
            facets["branches"][label] = {
                "branchId": branch["id"] if branch else None,
                "eventStepId": branch["eventStepId"] if branch else None,
                "outcome": case["outcome"],
                "stepIds": sorted(set(case["stepIds"]) & related),
            }
            facets["steps"][label] = {
                key: dict(steps[key])
                for key in sorted(related)
            }
            facets["sequence"][label] = sorted(
                [e for e in edges if e["before"] in related and e["after"] in related],
                key=lambda e: (e["before"], e["after"]))
            facets["timeConstraints"][label] = {
                key: data["timeConstraintsByStep"][key] for key in sorted(related)
            }
        views[sid] = facets
    return copy.deepcopy({"reviewCoverage": coverage, "reviewInputsByStep": views})


def build_contract(graph, plan, action_id, step_id):
    gd, pd = graph["data"], plan["data"]
    expected = plan_views(pd)
    require(expected["reviewCoverage"]["complete"], expected["reviewCoverage"].get("diagnostic", "MULTI_BRANCH_NOT_COVERED"))
    for key, value in expected.items():
        require(pd.get(key) == value, "PLAN_PROJECTION_INCOMPLETE_OR_STALE_" + key)
    for key, value in graph_views(gd).items():
        require(gd.get(key) == value, "GRAPH_PROJECTION_INCOMPLETE_OR_STALE_" + key)
    require(action_id in gd["reviewNodesById"], "ACTION_NOT_FOUND")
    require(step_id in pd["reviewInputsByStep"], "STEP_NOT_FOUND")
    ref = pd["actionRefsByStep"][step_id]
    require(ref["identitySpace"] == gd["identitySpace"] and
            ref["graphFile"] == gd["graphFile"] and ref["nodeId"] == action_id,
            "ACTION_OWNER_MISMATCH")
    gref, pref = resource_ref(graph), resource_ref(plan)
    sources = [(gref + "#/reviewIdentity", "exact"),
               (gref + "#/reviewNodesById/" + pointer(action_id), "exact"),
               (pref + "#/reviewCoverage", "exact")]
    sources += [(pref + "#/reviewInputsByStep/" + pointer(step_id) + "/" + key, "exact")
                for key in READ_MATRIX]
    return {"contract": VERSION, "complete": True,
            "subscriptions": sources,
            "provenance": {"graphResource": gref, "planResource": pref,
                           "graphRevision": gd["sourceRevision"],
                           "planRevision": pd["sourceRevision"],
                           "observedGraphRevision": ref.get("observedGraphRevision"),
                           "planOwnerVersion": pd.get("ownerVersion"),
                           "asOfMode": "current-projection",
                           "historicalSnapshotAvailable": False}}


def build_action_contract(graph, plan, action_id, step_ids):
    """One Action review must cover every occurrence in this Plan/graph scope."""
    require(isinstance(step_ids, (list, tuple)) and step_ids and
            all(isinstance(sid, str) for sid in step_ids) and
            len(step_ids) == len(set(step_ids)), "ACTION_OCCURRENCES_INVALID")
    contracts = {sid: build_contract(graph, plan, action_id, sid)
                 for sid in sorted(step_ids)}
    gd, pd = graph["data"], plan["data"]
    expected = {sid for sid, ref in pd["actionRefsByStep"].items()
                if ref["identitySpace"] == gd["identitySpace"] and
                   ref["graphFile"] == gd["graphFile"] and
                   ref["nodeId"] == action_id}
    require(set(step_ids) == expected, "ACTION_OCCURRENCES_INCOMPLETE")
    return {"contract": VERSION, "complete": True,
            "subscriptions": sorted({tuple(source) for contract in contracts.values()
                                     for source in contract["subscriptions"]}),
            "provenance": {"actionId": action_id, "stepIds": sorted(step_ids),
                           "occurrences": {sid: contract["provenance"]
                                           for sid, contract in contracts.items()}}}


def assert_coverage(contract, declared):
    require(contract.get("contract") == VERSION and contract.get("complete"),
            "UNKNOWN_CONTRACT")
    expected = {tuple(x) for x in contract["subscriptions"]}
    actual = {tuple(x) for x in declared}
    missing, extra = expected - actual, actual - expected
    require(not missing and not extra and len(declared) == len(expected),
            "SUBSCRIPTIONS_INCOMPLETE missing=" + repr(sorted(missing)) +
            " extra=" + repr(sorted(extra)))


# Separate extension: do not silently expand the tested one-event v2 contract.
# This opt-in contract uses a conservative full-graph/full-Plan read set. It
# catches new edges, changes of childRole, execution/withdrawal and Requirement
# placements even if a narrowly keyed review would miss a new prerequisite.
# Unrelated edits can therefore request review; full semantic precision is NOT
# claimed. The caller must use a single authorized, coherent owner snapshot.
WORKFLOW_VERSION = "rdg-workflow-review/v1"
WORKFLOW_GRAPH_FIELDS = ("identitySpace", "graphFile", "rootRequirementId",
                         "actionModel", "nodesById", "edgesById", "events",
                         "expansionOf", "readOnly")
WORKFLOW_PLAN_FIELDS = ("identitySpace", "planId", "planStatus", "stepsById",
                        "branchesById", "sequenceByPair", "timeConstraintsByStep",
                        "actionRefsByStep")


def build_workflow_contract(graph, plan, target_kind, target_id, step_ids):
    """Optional current-context review of Action/Requirement, not actual truth.

    This is a dependency declaration over existing read-only resources, not a
    replacement Plan owner, an Action completion engine or a historical T1 proof.
    """
    require(target_kind in ("action", "requirement"), "WORKFLOW_TARGET_KIND")
    require(isinstance(step_ids, (list, tuple)) and step_ids and
            all(isinstance(s, str) and s for s in step_ids) and
            len(set(step_ids)) == len(step_ids), "WORKFLOW_STEPS_INVALID")
    gd, pd = graph["data"], plan["data"]
    require(gd.get("actionModel") == "candidate-v6", "WORKFLOW_ACTION_MODEL_UNSUPPORTED")
    require(gd.get("identitySpace") == pd.get("identitySpace"), "WORKFLOW_IDENTITY_MISMATCH")
    require(all(key in gd for key in WORKFLOW_GRAPH_FIELDS) and
            all(key in pd for key in WORKFLOW_PLAN_FIELDS),
            "WORKFLOW_SOURCE_GROUPS_MISSING")
    require(all(gd.get(key) == value for key, value in graph_views(gd).items()),
            "WORKFLOW_GRAPH_PROJECTION_STALE")
    require(all(pd.get(key) == value for key, value in plan_views(pd).items()),
            "WORKFLOW_PLAN_PROJECTION_STALE")
    # The older one-branch reviewCoverage is *not* evidence for this contract.
    # Its explicit incomplete result for Requirement-steps remains unchanged.
    # Current pilot covers a single semantic owner. A projection/root
    # expansion requires extra authorized owner files; never claim complete
    # simply because its current child graph has all local nodes.
    require(gd["expansionOf"] is None, "WORKFLOW_CROSS_OWNER_CONTEXT_NOT_COVERED")
    nodes = gd["nodesById"]
    require(isinstance(nodes, dict) and all(
            isinstance(n, dict) and not n.get('projectionOf') for n in nodes.values()),
            "WORKFLOW_CROSS_OWNER_CONTEXT_NOT_COVERED")
    require(target_id in nodes and
            nodes[target_id].get("kind") == target_kind,
            "WORKFLOW_TARGET_NOT_FOUND")
    edges = gd["edgesById"]
    require(isinstance(edges, dict) and isinstance(gd["events"], list),
            "WORKFLOW_GRAPH_CONTENT_INVALID")
    for edge in edges.values():
        require(isinstance(edge, dict) and isinstance(edge.get("from"), str) and
                isinstance(edge.get("to"), str) and
                edge["from"] in nodes and edge["to"] in nodes,
                "WORKFLOW_EDGE_UNRESOLVED")
        if edge.get("type") == "INTRODUCES" and edge.get("archived") is not True:
            require(edge.get("childRole") in ("subgoal", "method_correctness") and
                    nodes[edge["from"]].get("kind") == "action" and
                    nodes[edge["to"]].get("kind") == "requirement",
                    "WORKFLOW_CHILD_ROLE_UNKNOWN")
    events = gd["events"]
    require(all(isinstance(e, dict) and isinstance(e.get("id"), str) and
                isinstance(e.get("type"), str) for e in events) and
            len({e["id"] for e in events}) == len(events),
            "WORKFLOW_EVENT_INVALID")
    material_events = {"action_executed", "action_withdrawn",
                       "action_reconsidered", "requirement_achieved"}
    for event in events:
        if event["type"] in material_events:
            ident = event.get("actionId") if event["type"] in (
                "action_withdrawn", "action_reconsidered") else event.get("targetId")
            require(isinstance(ident, str) and ident in nodes,
                    "WORKFLOW_EVENT_TARGET_UNRESOLVED")
    steps = pd["stepsById"]
    require(isinstance(steps, dict), "WORKFLOW_PLAN_STEPS_INVALID")
    matched = set()
    for sid, step in steps.items():
        if step.get("kind") != target_kind:
            continue
        ref = step.get("actionRef" if target_kind == "action" else "requirementRef")
        require(isinstance(ref, dict), "WORKFLOW_REFERENCE_MISSING")
        if ref.get("graphFile") == gd["graphFile"] and ref.get("identitySpace") == gd["identitySpace"] and ref.get("nodeId") == target_id:
            matched.add(sid)
    require(set(step_ids) == matched, "WORKFLOW_OCCURRENCES_INCOMPLETE")
    gref, pref = resource_ref(graph), resource_ref(plan)
    # Exact subscriptions to *groups* also track NEW edges/events/steps. A
    # per-existing-ID list would silently miss newly introduced dependencies.
    subscriptions = [(gref + "#/" + key, "exact") for key in WORKFLOW_GRAPH_FIELDS]
    subscriptions += [(pref + "#/" + key, "exact") for key in WORKFLOW_PLAN_FIELDS]
    return {"contract": WORKFLOW_VERSION, "complete": True,
            "granularity": "whole-graph-and-plan; conservative rechecks",
            "subscriptions": subscriptions,
            "provenance": {"graphResource": gref, "planResource": pref,
                           "targetKind": target_kind, "targetId": target_id,
                           "stepIds": sorted(step_ids),
                           "graphRevision": gd.get("sourceRevision"),
                           "planRevision": pd.get("sourceRevision"),
                           "asOfMode": "current-projection",
                           "historicalSnapshotAvailable": False,
                           "completionTruthAttested": False}}


def assert_workflow_coverage(contract, declared):
    require(contract.get("contract") == WORKFLOW_VERSION and contract.get("complete"),
            "WORKFLOW_CONTRACT_INVALID")
    expected = {tuple(item) for item in contract["subscriptions"]}
    actual = {tuple(item) for item in declared}
    require(len(actual) == len(declared) and actual == expected,
            "WORKFLOW_SUBSCRIPTIONS_INCOMPLETE")


def workflow_project_config(graph_relative, plan_relative, targets, rule_prefix):
    """Trusted Gendocen config on verified local synthetic projections."""
    return (
        "import json\nfrom pathlib import Path\n"
        "from importlib.machinery import SourceFileLoader\n"
        f"dependency = SourceFileLoader('rdg_workflow_deps', {str(Path(__file__).resolve())!r}).load_module()\n"
        "def register_builders(registry):\n    pass\n\n"
        "def register_semantic_dependencies(registry):\n"
        "    docs = Path(__file__).resolve().parents[1] / 'docs'\n"
        f"    graph = json.loads((docs / {graph_relative!r}).read_text(encoding='utf8'))\n"
        f"    plan = json.loads((docs / {plan_relative!r}).read_text(encoding='utf8'))\n"
        f"    for kind, nid, steps in {targets!r}:\n"
        "        contract = dependency.build_workflow_contract(graph, plan, kind, nid, steps)\n"
        "        dependency.assert_workflow_coverage(contract, contract['subscriptions'])\n"
        "        registry.register('file://review/' + nid + '.md', contract['subscriptions'],\n"
        f"                          rule_id={rule_prefix!r} + '.' + nid,\n"
        "                          dependency_type='semantic_review')\n"
    )

def project_config(graph_relative, plan_relative, targets, rule_prefix):
    """Trusted local project config, validated on every Gendocen CLI startup."""
    return (
        "import json\nfrom pathlib import Path\n"
        "from importlib.machinery import SourceFileLoader\n"
        f"dependency = SourceFileLoader('rdg_review_dependencies', {str(Path(__file__).resolve())!r}).load_module()\n"
        "def register_builders(registry):\n    pass\n\n"
        "def register_semantic_dependencies(registry):\n"
        "    docs = Path(__file__).resolve().parents[1] / 'docs'\n"
        f"    graph = json.loads((docs / {graph_relative!r}).read_text(encoding='utf8'))\n"
        f"    plan = json.loads((docs / {plan_relative!r}).read_text(encoding='utf8'))\n"
        "    by_action = {}\n"
        f"    for aid, sid in {targets!r}:\n"
        "        by_action.setdefault(aid, []).append(sid)\n"
        "    for aid, sids in sorted(by_action.items()):\n"
        "        contract = dependency.build_action_contract(graph, plan, aid, sids)\n"
        "        sources = contract['subscriptions']\n"
        "        dependency.assert_coverage(contract, sources)\n"
        "        registry.register(f'file://review/{aid}.md', sources,\n"
        f"                          rule_id={rule_prefix!r} + '.' + aid,\n"
        "                          dependency_type='semantic_review')\n"
    )
