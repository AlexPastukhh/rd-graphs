#!/usr/bin/env python3
"""Stage 3P: read-only, branch-specific Temporal Plan -> RDG review signals.

A temporal conflict in a candidate Plan is an assumption-bound review lead,
NEVER a confirmed Finding or a permission to select/execute an Action.
"""
import argparse
import datetime as dt
import hashlib
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

HERE = Path(__file__).resolve().parent
temporal = SourceFileLoader("rdg_temporal_stage3p", str(HERE / "rdg-temporal-plan.py")).load_module()


def ensure(ok, code):
    if not ok:
        raise ValueError("PLAN_IMPACT_" + code)


def digest(data):
    encoded = json.dumps(data, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_time(text):
    precision = temporal.temporal_literal(text)
    return precision, (dt.date.fromisoformat(text) if precision == "date"
                       else dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
                       .astimezone(dt.timezone.utc))


def review_cases(plan):
    """One conditional event is supported. Multiple events require a later gate."""
    branches = plan.get("branches", [])
    ensure(len(branches) <= 1, "MULTI_BRANCH_NOT_YET_SUPPORTED")
    if not branches:
        return [{"branchId": None, "outcome": None, "possibleSteps": set()}]
    branch = branches[0]
    return [{"branchId": branch["id"], "outcome": case["outcome"],
             "possibleSteps": set(case["stepIds"])}
            for case in branch["cases"]]


def path_closure(node, edges):
    forward, reverse = {}, {}
    for a, b in edges:
        forward.setdefault(a, set()).add(b)
        reverse.setdefault(b, set()).add(a)
    def traverse(table):
        result, frontier = {node}, [node]
        while frontier:
            for nxt in table.get(frontier.pop(), ()):
                if nxt not in result:
                    result.add(nxt)
                    frontier.append(nxt)
        return result
    return traverse(reverse), traverse(forward)


def earliest_bounds(nodes, edges, constraints):
    """Necessary lower bounds only, using explicitly hard notBefore values.

    Date-only and timezone-aware instants are independent precision lanes.
    Neither is converted to a fabricated timestamp.
    """
    lower = {sid: {} for sid in nodes}
    for rule in constraints:
        if rule["type"] != "notBefore" or rule["strength"] != "hard":
            continue
        precision, value = parse_time(rule["at"])
        old = lower[rule["stepId"]].get(precision)
        if old is None or value > old:
            lower[rule["stepId"]][precision] = value
    remaining = set(nodes)
    deps = {sid: set() for sid in nodes}
    for edge in edges:
        deps[edge["after"]].add(edge["before"])
    while remaining:
        ready = sorted(sid for sid in remaining if not (deps[sid] & remaining))
        ensure(ready, "CYCLE")
        for sid in ready:
            for edge in edges:
                if edge["before"] != sid:
                    continue
                after = edge["after"]
                lag = dt.timedelta(days=edge.get("minDelayDays", 0))
                for precision, value in lower[sid].items():
                    bound = value + lag
                    old = lower[after].get(precision)
                    if old is None or bound > old:
                        lower[after][precision] = bound
            remaining.remove(sid)
    return lower


def scope_action(graphs_root, plan, step):
    ref = step["actionRef"]
    root = Path(graphs_root).resolve()
    path = root / ref["graphFile"]
    ensure(path.resolve().is_relative_to(root), "REF_OUTSIDE_GRAPH_ROOT")
    ensure(path.is_file(), "ACTION_GRAPH_NOT_AVAILABLE")
    graph = json.loads(path.read_text(encoding="utf-8"))
    # Plan may reference another RDG identitySpace. The reference must name
    # that owner explicitly; this read-only pilot grants no remote write rights.
    ensure(graph.get("identitySpace") == ref["identitySpace"],
           "IDENTITY_SPACE_MISMATCH")
    matches = [n for n in graph.get("nodes", [])
               if n.get("id") == ref["nodeId"] and n.get("kind") == "action"]
    ensure(len(matches) == 1, "ACTION_NOT_FOUND")
    action = matches[0]
    block = action.get("canonBlock")
    canons = []
    if isinstance(block, dict):
        for polarity in ("recommended", "contraindicated"):
            cases = block.get(polarity)
            if isinstance(cases, list):
                for case in cases:
                    if isinstance(case, dict) and isinstance(case.get("id"), str):
                        canons.append({"id": case["id"], "polarity": polarity})
    return {
        "graphFile": ref["graphFile"], "actionId": action["id"],
        "identitySpace": ref["identitySpace"],
        "actionStatus": action.get("status"), "graphRevision": graph.get("revision"),
        "revisionChanged": ("observedGraphRevision" in ref and
                            graph.get("revision") != ref["observedGraphRevision"]),
        "canonCases": canons,
        "canonCoverage": "indexed-not-evaluated" if canons else "unknown-or-not-provided",
        "canonDigest": digest(block) if isinstance(block, dict) else None,
    }


def assess(plan, graphs_root):
    temporal.validate(plan)
    ensure(graphs_root is not None, "GRAPH_ROOT_REQUIRED")
    cases = review_cases(plan)
    all_steps = {s["id"]: s for s in plan["steps"]}
    result = {"planId": plan["id"], "planRevision": plan["revision"],
              "planStatus": plan["status"], "readOnly": True,
              "committedFindings": [], "selectedActions": [],
              "executionPerformed": False, "branches": []}
    possible = {s["id"] for s in plan["steps"] if s["state"] == "possible"}
    for case in cases:
        active = (set(all_steps) - possible) | case["possibleSteps"]
        edges = [e for e in plan.get("sequence", [])
                 if e["before"] in active and e["after"] in active]
        pairs = [(e["before"], e["after"]) for e in edges]
        constraints = [r for r in plan.get("timeConstraints", [])
                       if r["stepId"] in active]
        bounds = earliest_bounds(active, edges, constraints)
        checks = []
        for rule in constraints:
            if rule["type"] != "deadline":
                continue
            precision, deadline = parse_time(rule["at"])
            earliest = bounds[rule["stepId"]].get(precision)
            mismatch = earliest is None and bool(bounds[rule["stepId"]])
            proof = (earliest is not None and earliest > deadline and
                     rule["strength"] == "hard")
            checks.append({
                "stepId": rule["stepId"], "deadline": rule["at"],
                "strength": rule["strength"], "basis": rule["basis"],
                "comparison": ("candidate-plan-hard-constraint-conflict" if proof
                    else "precision-not-comparable" if mismatch
                    else "no-hard-lower-bound" if earliest is None
                    else "nonbinding-deadline" if rule["strength"] != "hard"
                    else "no-conflict-proven"),
                "earliestHardBound": earliest.isoformat() if earliest else None,
                "assumptionOnly": True, "findingType": None,
                "requiresAssessment": True,
            })
        action_leads = []
        for step_id in sorted(active):
            step = all_steps[step_id]
            if step["kind"] != "action":
                continue
            upstream, downstream = path_closure(step_id, pairs)
            affected = upstream | downstream
            related_constraints = [r for r in constraints if r["stepId"] in affected]
            related_edges = [e for e in edges
                             if e["before"] in affected and e["after"] in affected]
            relevant_checks = [c for c in checks if c["stepId"] in downstream]
            action = scope_action(graphs_root, plan, step)
            source = {
                "stepId": step_id, "branchId": case["branchId"],
                "outcome": case["outcome"], "planId": plan["id"],
                "actionRef": {"graphFile": action["graphFile"],
                              "identitySpace": action["identitySpace"],
                              "nodeId": action["actionId"]},
                "sequence": sorted(related_edges, key=lambda e: (e["before"], e["after"])),
                "timeConstraints": sorted(related_constraints,
                    key=lambda r: (r["stepId"], r["type"], r["at"])),
                "canonDigest": action["canonDigest"],
                "actionStatus": action["actionStatus"],
            }
            action_leads.append({
                "stepId": step_id, "branchId": case["branchId"],
                "outcome": case["outcome"], "action": action,
                "relatedTemporalSteps": sorted(affected),
                "relatedTimeConstraints": related_constraints,
                "deadlineChecks": relevant_checks,
                "timeConflictReview": any(c["comparison"] ==
                    "candidate-plan-hard-constraint-conflict" for c in relevant_checks),
                "canonReview": {"cases": action["canonCases"],
                                "coverage": action["canonCoverage"],
                                "applicability": "not-evaluated"},
                "findingProposal": None, "findingType": None,
                "requiresHumanAssessment": True,
                "dependencyDigest": digest(source),
            })
        result["branches"].append({
            "branchId": case["branchId"], "outcome": case["outcome"],
            "activeSteps": sorted(active),
            "deadlineChecks": checks, "actionReviewLeads": action_leads,
        })
    return result


def changed_actions(before, after):
    ensure(before["planId"] == after["planId"], "PLAN_ID_MISMATCH")
    def indexing(report):
        return {(case["branchId"], case["outcome"], a["stepId"],
                 a["action"]["graphFile"], a["action"]["actionId"]): a
                for case in report["branches"] for a in case["actionReviewLeads"]}
    old, new = indexing(before), indexing(after)
    items = []
    for key in sorted(set(old) | set(new), key=str):
        first, last = old.get(key), new.get(key)
        old_digest = first["dependencyDigest"] if first else None
        new_digest = last["dependencyDigest"] if last else None
        if old_digest == new_digest:
            classification = "unchanged"
        else:
            classification = ("added" if first is None else
                              "removed" if last is None else "review-required")
        items.append({"branchId": key[0], "outcome": key[1],
                      "stepId": key[2], "actionId": key[4],
                      "change": classification,
                      "priorDependencyDigest": old_digest,
                      "currentDependencyDigest": new_digest})
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--graphs-root", required=True, type=Path)
    parser.add_argument("--before-plan", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    current = assess(plan, args.graphs_root)
    if args.before_plan:
        previous = json.loads(args.before_plan.read_text(encoding="utf-8"))
        current["deltaFromBefore"] = changed_actions(
            assess(previous, args.graphs_root), current)
    print(json.dumps(current, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        import sys
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
