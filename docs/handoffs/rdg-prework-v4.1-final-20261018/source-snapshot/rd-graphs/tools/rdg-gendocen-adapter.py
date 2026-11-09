#!/usr/bin/env python3
"""Read-only Gendocen-shaped RDG and Temporal Plan resources.

NOT a docengine runtime, subscription evaluator, or trusted evidence producer.
Stable qualified resource IDs; semantic field paths instead of raw-file hash.
"""
import argparse
import hashlib
import json
import re
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = SourceFileLoader("rdg_temporal_for_gendocen", str(ROOT / "rdg-temporal-plan.py")).load_module()
GRAPH_REF = re.compile(r"workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json\Z")


def require(ok, code):
    if not ok:
        raise ValueError("RDG_GENDOCEN_" + code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf8")
                           ).hexdigest()


def path_ref(path, declared=None):
    parts = Path(path).parts
    if declared is not None:
        require(isinstance(declared, str) and bool(GRAPH_REF.fullmatch(declared)),
                "GRAPH_REF_INVALID")
        known = ["/".join(parts[i:]) for i, value in enumerate(parts)
                 if value == "workspaces" and bool(
                     GRAPH_REF.fullmatch("/".join(parts[i:])))]
        require(not known or declared in known, "GRAPH_REF_PATH_MISMATCH")
        return declared
    choices = ["/".join(parts[i:]) for i, value in enumerate(parts)
               if value == "workspaces" and bool(GRAPH_REF.fullmatch("/".join(parts[i:])))]
    require(len(choices) == 1, "EXPLICIT_GRAPH_REF_REQUIRED")
    return choices[0]


def graph_resource(path, graph_ref=None):
    graph = json.loads(Path(path).read_text(encoding="utf8"))
    require(isinstance(graph, dict) and graph.get("schemaVersion") == 1,
            "GRAPH_SCHEMA")
    owner = graph.get("identitySpace")
    require(isinstance(owner, str) and owner.strip() and
            isinstance(graph.get("rootRequirementId"), str) and
            graph["rootRequirementId"], "GRAPH_OWNER")
    ref = path_ref(path, graph_ref)
    nodes = graph.get("nodes")
    edges = graph.get("edges", [])
    require(isinstance(nodes, list) and
            all(isinstance(n, dict) and isinstance(n.get("id"), str) and n["id"]
                for n in nodes), "GRAPH_NODES")
    require(isinstance(edges, list) and
            all(isinstance(e, dict) and isinstance(e.get("id"), str) and e["id"]
                for e in edges), "GRAPH_EDGES")
    nodes_by = {n["id"]: n for n in nodes}
    edges_by = {e["id"]: e for e in edges}
    require(len(nodes_by) == len(nodes) and len(edges_by) == len(edges),
            "DUPLICATE_ID")
    require(graph["rootRequirementId"] in nodes_by and
            nodes_by[graph["rootRequirementId"]].get("kind") == "requirement",
            "GRAPH_ROOT_NOT_FOUND")
    events = graph.get("events", [])
    require(isinstance(events, list), "GRAPH_EVENTS")
    content = {
        "identitySpace": owner, "graphFile": ref,
        "rootRequirementId": graph["rootRequirementId"],
        "nodesById": nodes_by, "edgesById": edges_by,
        "events": events, "actionModel": graph.get("actionModel"),
    }
    data = {**content,
            "sourceRevision": graph.get("revision"),
            "semanticSHA256": digest(content)}
    ident = "rdg.graph." + digest({"identitySpace": owner, "graphFile": ref})[:24]
    return {"$docengine": {"resource_id": ident, "materialize": []}, "data": data}


def plan_resource(path):
    plan = json.loads(Path(path).read_text(encoding="utf8"))
    PLAN.validate(plan)
    # Outcome/case ordering is presentation, not temporal meaning.
    steps = {
        s["id"]: ({**s, "outcomes": sorted(s["outcomes"])}
                  if s["kind"] == "event" else s)
        for s in plan["steps"]
    }
    branches = {
        b["id"]: {
            **b, "cases": sorted(
                [{**case, "stepIds": sorted(case["stepIds"])}
                 for case in b["cases"]],
                key=lambda x: x["outcome"])
        }
        for b in plan.get("branches", [])
    }
    sequence_by = {
        e["before"] + "->" + e["after"]: e
        for e in plan.get("sequence", [])
    }
    # Empty lists must exist for ALL steps: a field-level subscription to an
    # initially unconstrained step must be resolvable and detect its first rule.
    time_by = {sid: [] for sid in steps}
    for entry in plan.get("timeConstraints", []):
        time_by.setdefault(entry["stepId"], []).append(entry)
    for group in time_by.values():
        group.sort(key=lambda x: (x["type"], x["at"], x["strength"], x["basis"]))
    # A resource points to its own Plan, not an RDG Action lifecycle.
    refs_by_step = {s["id"]: s["actionRef"] for s in plan["steps"]
                    if s["kind"] == "action"}
    content = {
        "identitySpace": plan["identitySpace"], "planId": plan["id"],
        "planStatus": plan["status"], "stepsById": steps,
        "branchesById": branches,
        "sequenceByPair": sequence_by,
        "timeConstraintsByStep": time_by,
        "actionRefsByStep": refs_by_step,
    }
    data = {**content, "sourceRevision": plan["revision"],
            "semanticSHA256": digest(content)}
    ident = "rdg.plan." + digest({"identitySpace": plan["identitySpace"],
                                  "planId": plan["id"]})[:24]
    return {"$docengine": {"resource_id": ident, "materialize": []}, "data": data}


# Legacy API retained for earlier adapter consumers.
def adapt(path):
    return graph_resource(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--graph", type=Path)
    group.add_argument("--plan", type=Path)
    p.add_argument("--graph-ref", help="workspace-relative path, e.g. workspaces/demo/graph.json")
    args = p.parse_args()
    require(args.graph is not None or args.graph_ref is None,
            "GRAPH_REF_ONLY_FOR_GRAPH")
    data = (graph_resource(args.graph, args.graph_ref) if args.graph
            else plan_resource(args.plan))
    print(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as err:
        import sys
        print("ERROR: " + str(err), file=sys.stderr)
        sys.exit(1)
