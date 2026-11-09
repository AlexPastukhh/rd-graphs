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
               "nodesById/{action}/{id,kind,title,status,canonBlock,qrpe,selectionBasis}"]


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
              ("id", "kind", "title", "status", "canonBlock", "qrpe", "selectionBasis")}
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
                "complete": len(branches) <= 1, "sourceReads": READ_MATRIX,
                "graphReads": GRAPH_READS,
                "historicalSnapshotAvailable": False}
    if not coverage["complete"]:
        coverage["diagnostic"] = "MULTI_BRANCH_NOT_COVERED"
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
    require(expected["reviewCoverage"]["complete"], "MULTI_BRANCH_NOT_COVERED")
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
