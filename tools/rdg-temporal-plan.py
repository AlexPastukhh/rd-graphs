#!/usr/bin/env python3
"""Stage 2P: read-only validation/inspection of an independent Temporal Plan.

This is NOT an execution engine, event attestation, acceptance API or RDG writer.
A candidate Plan's hard-looking deadline is not a committed project constraint.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path

GRAPH_REF = re.compile(r"workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json\Z")
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
from importlib.machinery import SourceFileLoader
MODULES = SourceFileLoader('rdg_modules_plan',
    str(Path(__file__).with_name('rdg-modules.py'))).load_module()
ALLOWED_STEPS = set(MODULES.base()['planStepKinds'])
ALLOWED_STATES = {"planned", "possible", "expected"}
ALLOWED_STRENGTHS = {"hard", "soft", "hypothetical"}


def ensure(condition, code):
    if not condition:
        raise ValueError("TEMPORAL_PLAN_" + code)


def named(value):
    return isinstance(value, str) and bool(value.strip())


def ident(value):
    return isinstance(value, str) and bool(IDENT.fullmatch(value))


def temporal_literal(value):
    """Date-only = calendar day, timezone must be explicit for an instant."""
    ensure(named(value), "TIME_REQUIRED")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        dt.date.fromisoformat(value)
        return "date"
    ensure("T" in value and re.search(r"(Z|[+-]\d{2}:\d{2})\Z", value),
           "TIMEZONE_REQUIRED")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    ensure(parsed.tzinfo is not None and parsed.utcoffset() is not None,
           "TIMEZONE_REQUIRED")
    return "instant"


def validate(plan):
    ensure(isinstance(plan, dict), "SCHEMA")
    ensure("preselected" not in plan and "selectedCase" not in plan and
           "executions" not in plan, "NO_HIDDEN_COMMIT_OR_EXECUTION")
    ensure(plan.get("schemaVersion") == 1 and
           plan.get("kind") == "temporalPlan" and
           set(plan) <= {"schemaVersion", "kind", "id", "title", "identitySpace",
                         "revision", "status", "steps", "sequence", "branches",
                         "timeConstraints", "modules", "moduleData", "disabledModules"}, "SCHEMA")
    ensure(ident(plan.get("id")) and named(plan.get("title")) and
           named(plan.get("identitySpace")) and type(plan.get("revision")) is int and
           plan["revision"] >= 1, "IDENTITY")
    ensure(plan.get("status") == "candidate", "CANDIDATE_ONLY")
    MODULES.validate_plan(plan)
    steps = plan.get("steps")
    ensure(isinstance(steps, list), "STEPS_REQUIRED")
    by_id = {}
    for step in steps:
        ensure(isinstance(step, dict), "INVALID_STEP")
        ensure(not any(k in step for k in
                   ("selected", "preselected", "performed", "observedAt")),
               "STEP_CANNOT_COMMIT_OR_ATTEST")
        ensure(set(step) <= {"id", "kind", "title", "state", "actionRef", "requirementRef", "outcomes"} and
               ident(step.get("id")) and
               step["id"] not in by_id and named(step.get("title")) and
               step.get("kind") in ALLOWED_STEPS and
               step.get("state") in ALLOWED_STATES, "INVALID_STEP")
        if step["kind"] in {"action", "requirement"}:
            field = "actionRef" if step["kind"] == "action" else "requirementRef"
            ensure(("requirementRef" if field == "actionRef" else "actionRef") not in step, "REF_KIND_MISMATCH")
            ref = step.get(field)
            ensure(isinstance(ref, dict) and
                   set(ref) <= {"graphFile", "identitySpace", "nodeId",
                                "observedGraphRevision"} and
                   isinstance(ref.get("graphFile"), str) and
                   GRAPH_REF.fullmatch(ref["graphFile"]) and
                   named(ref.get("identitySpace")) and
                   ident(ref.get("nodeId")), "INVALID_ACTION_REF")
            if "observedGraphRevision" in ref:
                ensure(type(ref["observedGraphRevision"]) is int and
                       ref["observedGraphRevision"] >= 1, "REF_REVISION")
        else:
            ensure("actionRef" not in step and "requirementRef" not in step, "ACTION_REF_ON_NON_ACTION")
        if step["kind"] != "event":
            ensure("outcomes" not in step, "OUTCOMES_ONLY_ON_EVENT")
        if step["kind"] == "event":
            outcomes = step.get("outcomes")
            ensure(isinstance(outcomes, list) and len(outcomes) >= 2 and
                   all(ident(x) for x in outcomes) and
                   len(outcomes) == len(set(outcomes)), "EVENT_OUTCOMES")
            ensure(step["state"] == "expected", "EVENT_NOT_ATTESTED")
        if step["kind"] == "decision_gate":
            ensure(step["state"] != "expected", "GATE_CANNOT_OCCUR")
        by_id[step["id"]] = step
    sequence = plan.get("sequence", [])
    ensure(isinstance(sequence, list), "SEQUENCE")
    links, successors = set(), {key: [] for key in by_id}
    for link in sequence:
        ensure(isinstance(link, dict) and
               set(link) <= {"before", "after", "minDelayDays"} and
               link.get("before") in by_id and link.get("after") in by_id and
               link["before"] != link["after"], "SEQUENCE_REFERENCE")
        pair = (link["before"], link["after"])
        ensure(pair not in links, "DUPLICATE_SEQUENCE")
        links.add(pair)
        if "minDelayDays" in link:
            ensure(type(link["minDelayDays"]) is int and
                   link["minDelayDays"] >= 0, "NEGATIVE_DELAY")
        successors[pair[0]].append(pair[1])
    visited, visiting = set(), set()
    def visit(node):
        ensure(node not in visiting, "TEMPORAL_CYCLE")
        if node in visited:
            return
        visiting.add(node)
        for nxt in successors[node]:
            visit(nxt)
        visiting.remove(node)
        visited.add(node)
    for node in by_id:
        visit(node)
    branches = plan.get("branches", [])
    ensure(isinstance(branches, list), "BRANCHES")
    branched_steps, branch_ids, event_ids = set(), set(), set()
    for branch in branches:
        ensure(isinstance(branch, dict) and
               set(branch) == {"id", "eventStepId", "cases"} and
               ident(branch.get("id")) and
               branch["id"] not in branch_ids and
               branch.get("eventStepId") in by_id and
               by_id[branch["eventStepId"]]["kind"] == "event", "BRANCH_EVENT")
        branch_ids.add(branch["id"])
        ensure(branch["eventStepId"] not in event_ids, "BRANCH_EVENT_DUPLICATED")
        event_ids.add(branch["eventStepId"])
        cases = branch.get("cases")
        ensure(isinstance(cases, list) and len(cases) >= 2, "BRANCH_CASES")
        outcomes = set()
        for case in cases:
            ensure(isinstance(case, dict) and set(case) == {"outcome", "stepIds"} and
                   ident(case.get("outcome")) and case["outcome"] not in outcomes and
                   case["outcome"] in by_id[branch["eventStepId"]]["outcomes"] and
                   isinstance(case.get("stepIds"), list) and case["stepIds"] and
                   len(case["stepIds"]) == len(set(case["stepIds"])), "BRANCH_CASE")
            outcomes.add(case["outcome"])
            for sid in case["stepIds"]:
                ensure(sid in by_id and
                       by_id[sid]["state"] == "possible" and
                       sid not in branched_steps and sid != branch["eventStepId"],
                       "BRANCH_STEP_NOT_POSSIBLE_OR_REUSED")
                ensure((branch["eventStepId"], sid) in links,
                       "BRANCH_WITHOUT_EVENT_ORDER")
                branched_steps.add(sid)
        ensure(outcomes == set(by_id[branch["eventStepId"]]["outcomes"]),
               "BRANCH_OUTCOMES_NOT_COVERED")
        # An exclusive case must never require steps in its alternative case.
        def reachable(start, goal):
            todo, seen = [start], set()
            while todo:
                current = todo.pop()
                if current == goal:
                    return True
                if current not in seen:
                    seen.add(current)
                    todo.extend(successors[current])
            return False
        for i, left in enumerate(cases):
            for right in cases[i+1:]:
                for x in left["stepIds"]:
                    for y in right["stepIds"]:
                        ensure(not reachable(x, y) and not reachable(y, x),
                               "EXCLUSIVE_BRANCH_DEPENDENCY")
    for step in steps:
        if step["state"] == "possible":
            ensure(step["id"] in branched_steps, "POSSIBLE_STEP_WITHOUT_BRANCH")
    constraints = plan.get("timeConstraints", [])
    ensure(isinstance(constraints, list), "TIME_CONSTRAINTS")
    temporal = []
    for rule in constraints:
        ensure(isinstance(rule, dict) and
               set(rule) == {"stepId", "type", "at", "strength", "basis"} and
               rule.get("stepId") in by_id and
               rule.get("type") in ("deadline", "notBefore") and
               rule.get("strength") in ALLOWED_STRENGTHS and
               named(rule.get("basis")), "TIME_CONSTRAINT")
        kind = temporal_literal(rule.get("at"))
        temporal.append({"stepId": rule["stepId"], "type": rule["type"],
                         "at": rule["at"], "precision": kind,
                         "strength": rule["strength"], "basis": rule["basis"],
                         "effectiveAsCommitment": False})
    return by_id, temporal


def validate_future_write(plan):
    """Current write rule; immutable v1 snapshots retain structural readability."""
    by_id, temporal = validate(plan)
    placed = {rule["stepId"] for rule in temporal}
    for edge in plan.get("sequence", []):
        placed.update((edge["before"], edge["after"]))
    for sid, step in by_id.items():
        if step["kind"] in {"action", "requirement"}:
            ensure(sid in placed, "ACTION_STEP_NOT_PLACED" if step["kind"] == "action" else "REQUIREMENT_STEP_NOT_PLACED")
    return by_id, temporal


def apply_placements(plan, operations):
    """Convenient placement edits inside the existing owner CAS transaction."""
    import copy
    result = copy.deepcopy(plan)
    ensure(isinstance(operations, list) and operations, "PLACEMENT_OPERATIONS_REQUIRED")
    for op in operations:
        ensure(isinstance(op, dict), "PLACEMENT_OPERATION_INVALID")
        if op.get("op") in ("configure_modules", "set_module_data"):
            MODULES.apply_plan(result, op)
        elif op.get("op") == "place":
            ensure(set(op) <= {"op", "step", "timeConstraints", "sequence"}, "PLACE_SCHEMA")
            step = copy.deepcopy(op.get("step"))
            ensure(isinstance(step, dict) and step.get("kind") in {"action", "requirement"}, "PLACE_GRAPH_ENTITY_REQUIRED")
            sid = step.get("id")
            old = next((s for s in result["steps"] if s["id"] == sid), None)
            if old:
                field = "actionRef" if old["kind"] == "action" else "requirementRef"
                ensure(old["kind"] == step["kind"] and all(old.get(field, {}).get(k) ==
                       step.get(field, {}).get(k) for k in ("graphFile", "identitySpace", "nodeId")),
                       "PLACEMENT_IDENTITY_IMMUTABLE")
                result["steps"].remove(old)
            result["steps"].append(step)
            if "timeConstraints" in op:
                ensure(isinstance(op["timeConstraints"], list), "PLACE_TIME_CONSTRAINTS")
                rules = []
                for rule in op["timeConstraints"]:
                    ensure(isinstance(rule, dict) and rule.get("stepId", sid) == sid, "PLACE_TIME_TARGET")
                    rules.append({**copy.deepcopy(rule), "stepId": sid})
                result["timeConstraints"] = [r for r in result.get("timeConstraints", []) if r["stepId"] != sid] + rules
            if "sequence" in op:
                links = copy.deepcopy(op["sequence"])
                ensure(isinstance(links, list) and all(isinstance(e, dict) and sid in
                       (e.get("before"), e.get("after")) for e in links), "PLACE_SEQUENCE_TARGET")
                result["sequence"] = [e for e in result.get("sequence", []) if sid not in (e["before"], e["after"])] + links
        elif op.get("op") == "unplace":
            ensure(set(op) == {"op", "stepId"}, "UNPLACE_SCHEMA")
            sid = op["stepId"]
            ensure(any(s["id"] == sid for s in result["steps"]), "PLACEMENT_NOT_FOUND")
            result["steps"] = [s for s in result["steps"] if s["id"] != sid]
            result["sequence"] = [e for e in result.get("sequence", []) if sid not in (e["before"], e["after"])]
            result["timeConstraints"] = [r for r in result.get("timeConstraints", []) if r["stepId"] != sid]
        else:
            raise ValueError("TEMPORAL_PLAN_UNKNOWN_PLACEMENT_OPERATION")
    validate_future_write(result)
    return result


def inspect(plan, graphs_root=None):
    by_id, temporal = validate(plan)
    refs = []
    for step in plan["steps"]:
        if step["kind"] not in {"action", "requirement"}:
            continue
        ref = step["actionRef" if step["kind"] == "action" else "requirementRef"]
        result = {"stepId": step["id"], "graphFile": ref["graphFile"],
                  "nodeId": ref["nodeId"], "verification": "not-checked"}
        if graphs_root is not None:
            root = Path(graphs_root).resolve()
            file = root / ref["graphFile"]
            ensure(file.resolve().is_relative_to(root), "REF_OUTSIDE_GRAPH_ROOT")
            if not file.is_file():
                result["verification"] = "missing-graph"
            else:
                graph = json.loads(file.read_text(encoding="utf-8"))
                ensure(graph.get("identitySpace") == ref["identitySpace"],
                       "REF_IDENTITY_SPACE_MISMATCH")
                matches = [n for n in graph.get("nodes", [])
                           if n.get("id") == ref["nodeId"]]
                ensure(len(matches) == 1 and matches[0].get("kind") == step["kind"],
                       "REF_ACTION_NOT_FOUND")
                result["verification"] = "resolved"
                result["actionStatus"] = matches[0].get("status")
                result["graphRevision"] = graph.get("revision")
                if "observedGraphRevision" in ref:
                    result["revisionChanged"] = (
                        graph.get("revision") != ref["observedGraphRevision"])
        result["targetKind"] = step["kind"]
        refs.append(result)
    return {
        "planId": plan["id"], "planRevision": plan["revision"],
        "planStatus": plan["status"], "executionPerformed": False,
        "decisionCommitted": False, "eventsAttested": False,
        "steps": [{"id": s["id"], "kind": s["kind"], "state": s["state"]}
                  for s in plan["steps"]],
        "sequence": plan.get("sequence", []),
        "branches": plan.get("branches", []),
        "timeConstraints": temporal,
        "actionReferences": [{k:v for k,v in r.items() if k != "targetKind"} for r in refs if r["targetKind"] == "action"],
        "requirementReferences": [{k:v for k,v in r.items() if k != "targetKind"} for r in refs if r["targetKind"] == "requirement"],
        "reviewLeads": [
            {"kind": "time-context", "stepId": t["stepId"],
             "strength": t["strength"], "planStatus": plan["status"],
             "findingType": None, "requiresAssessment": True}
            for t in temporal],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--graphs-root", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    print(json.dumps(inspect(plan, args.graphs_root),
                     ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        import sys
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
