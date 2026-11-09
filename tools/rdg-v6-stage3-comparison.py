#!/usr/bin/env python3
"""Read-only RDG v6 stage-3 comparison: legacy O/D identity and canon alternatives.

This is a source-grounded candidate *projection* of schemaVersion 1, never a
writer, migration, evaluator for arbitrary canon prose, or authorization engine.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def identity_projection(graph, strategy):
    """Represent legacy Option as Action and D as a historical selection occurrence."""
    if strategy not in ("reuse-option-id", "new-action-id"):
        raise ValueError("Unsupported identity strategy")
    if not isinstance(graph, dict) or graph.get("schemaVersion") != 1:
        raise ValueError("Expected legacy schemaVersion 1")
    nodes = graph["nodes"]
    ids = [n["id"] for n in nodes]
    if len(set(ids)) != len(ids):
        raise ValueError("Source contains duplicate node IDs")
    original = {n["id"]: n for n in nodes}
    options = [n for n in nodes if n["kind"] == "option"]
    decisions = [n for n in nodes if n["kind"] == "decision"]
    actions = []
    action_by_option = {}
    owner = {"graphIdentitySpace": graph.get("identitySpace"),
             "graphId": graph.get("id")}
    for option in options:
        action_id = option["id"] if strategy == "reuse-option-id" else "action:" + option["id"]
        if action_id in action_by_option.values() or (strategy == "new-action-id" and action_id in original):
            raise ValueError("Action ID collision")
        action_by_option[option["id"]] = action_id
        actions.append({
            "actionId": action_id, "legacyOptionId": option["id"],
            "qualifiedActionRef": {**owner, "localActionId": action_id},
            "origin": option.get("origin"),
            "sourceVersionPin": copy.deepcopy(option.get("preparedSource")),
            "canonDigest": digest(option.get("canonBlock")),
            "candidateQrpe": copy.deepcopy(option.get("qrpe", [])),
            "candidateStatus": option.get("status", "candidate"),
        })

    selections, unresolved, introduced = [], [], []
    for dec in decisions:
        oid = dec.get("selectedOptionId")
        if not oid or oid not in action_by_option:
            unresolved.append({
                "legacyDecisionId": dec["id"], "reason": "NO_VERIFIED_OPTION_LINK",
                "status": dec.get("status"), "decisionSnapshot": copy.deepcopy(dec),
                "relatedEdges": copy.deepcopy([e for e in graph["edges"]
                    if e.get("from") == dec["id"] or e.get("to") == dec["id"]]),
                "eventSnapshots": copy.deepcopy([e for e in graph.get("events", [])
                    if e.get("decisionId") == dec["id"]]),
                "sourceDecisionDigest": digest(dec)
            })
            continue
        basis = dec.get("selectionBasis")
        if isinstance(basis, dict) and isinstance(basis.get("optionSnapshot"), dict):
            pinned = basis["optionSnapshot"].get("id")
            if pinned is not None and pinned != oid:
                raise ValueError("T1 optionSnapshot disagrees with selectedOptionId")
        events = [e for e in graph.get("events", []) if e.get("decisionId") == dec["id"]
            and e.get("type") in ("decision_selected", "decision_revised")]
        if dec.get("selectedInExampleOnly") is True or events and all(
                e.get("by") == "example" for e in events):
            authority = "illustrative"
        elif events and any(e.get("by") in ("user", "assistant") for e in events):
            authority = "event-backed"
        else:
            authority = "unverified-history"
        selections.append({
            "actionId": action_by_option[oid], "legacyDecisionId": dec["id"],
            "legacyOptionId": oid, "legacyDecisionStatus": dec.get("status"),
            "sourceAuthority": authority,
            "scope": dec.get("scope", "default"),
            "selectionBasis": copy.deepcopy(basis),
            "decisionQrpe": copy.deepcopy(dec.get("qrpe", [])),
            "eventSnapshots": copy.deepcopy(events),
            "decisionDigest": digest(dec),
        })
        for edge in graph["edges"]:
            if edge.get("type") == "INTRODUCES" and edge.get("from") == dec["id"]:
                introduced.append({
                    "actionId": action_by_option[oid],
                    "legacyDecisionId": dec["id"], "edgeId": edge["id"],
                    "requirementId": edge["to"], "parentId": edge.get("parent"),
                    "role": edge.get("childRole"), "archived": edge.get("archived", False),
                    "legacyEdgeDigest": digest(edge),
                })

    return {
        "strategy": strategy, "sourceGraphId": graph.get("id"),
        "sourceIdentitySpace": graph.get("identitySpace"),
        "sourceRevision": graph.get("revision"),
        "sourceDigest": digest(graph),
        "actions": actions, "selectionOccurrences": selections,
        "unmappedDecisions": unresolved, "introducedRequirements": introduced,
        "originalCounts": {
            "options": len(options), "decisions": len(decisions),
            "introducedEdges": sum(e.get("type") == "INTRODUCES" for e in graph["edges"]),
        },
        "note": "Derived read-only projection; no writer schema committed. Unlinked legacy D remains unresolved."
    }


def check_projection(graph, projection):
    """Check derived records against original O/D/T1/QRPE/edge/event evidence."""
    if projection["sourceDigest"] != digest(graph):
        raise ValueError("SOURCE_CHANGED")
    source_nodes = {n["id"]: n for n in graph["nodes"]}
    if len(projection["actions"]) != projection["originalCounts"]["options"]:
        raise ValueError("OPTION_COUNT_LOST")
    if (len(projection["selectionOccurrences"]) + len(projection["unmappedDecisions"])
            != projection["originalCounts"]["decisions"]):
        raise ValueError("DECISION_COUNT_LOST")
    mapping = {a["legacyOptionId"]: a["actionId"] for a in projection["actions"]}
    if len(mapping) != len(projection["actions"]) or len(set(mapping.values())) != len(mapping):
        raise ValueError("ACTION_MAPPING_COLLISION")
    strategy = projection["strategy"]
    for a in projection["actions"]:
        expected = a["legacyOptionId"] if strategy == "reuse-option-id" else "action:" + a["legacyOptionId"]
        if a["actionId"] != expected or a.get("qualifiedActionRef") != {
            "graphIdentitySpace": graph.get("identitySpace"),
            "graphId": graph.get("id"), "localActionId": expected}:
            raise ValueError("ACTION_ID_BINDING_INVALID")
        src = source_nodes[a["legacyOptionId"]]
        if src["kind"] != "option" or a["canonDigest"] != digest(src.get("canonBlock")):
            raise ValueError("OPTION_CANON_MISMATCH")
        if a["candidateQrpe"] != src.get("qrpe", []):
            raise ValueError("OPTION_QRPE_LOST")
        if a["sourceVersionPin"] != src.get("preparedSource"):
            raise ValueError("PREPARED_PIN_LOST")
    for s in projection["selectionOccurrences"]:
        dec = source_nodes[s["legacyDecisionId"]]
        if dec["selectedOptionId"] != s["legacyOptionId"] or mapping.get(s["legacyOptionId"]) != s["actionId"]:
            raise ValueError("SELECTION_LINK_MISMATCH")
        if s["selectionBasis"] != dec.get("selectionBasis"):
            raise ValueError("T1_SNAPSHOT_LOST")
        if s["decisionQrpe"] != dec.get("qrpe", []):
            raise ValueError("DECISION_QRPE_LOST")
        originals = [e for e in graph.get("events", []) if e.get("decisionId") == dec["id"]
            and e.get("type") in ("decision_selected", "decision_revised")]
        if s["eventSnapshots"] != originals:
            raise ValueError("EVENT_LOST")
    for x in projection["unmappedDecisions"]:
        dec = source_nodes[x["legacyDecisionId"]]
        if x["decisionSnapshot"] != dec or x["sourceDecisionDigest"] != digest(dec):
            raise ValueError("UNMAPPED_DECISION_SNAPSHOT_LOST")
        originals = [e for e in graph["edges"] if e.get("from") == dec["id"] or e.get("to") == dec["id"]]
        if x["relatedEdges"] != originals:
            raise ValueError("UNMAPPED_DECISION_EDGES_LOST")
        events = [e for e in graph.get("events", []) if e.get("decisionId") == dec["id"]]
        if x["eventSnapshots"] != events:
            raise ValueError("UNMAPPED_DECISION_EVENTS_LOST")
    edges = {e["id"]: e for e in graph["edges"]}
    for entry in projection["introducedRequirements"]:
        edge = edges[entry["edgeId"]]
        if (entry["legacyEdgeDigest"] != digest(edge)
            or edge.get("to") != entry["requirementId"]):
            raise ValueError("CHILD_EDGE_LOST")
    mapped_introduces = {x["edgeId"] for x in projection["introducedRequirements"]}
    unmapped_introduces = {e["id"] for x in projection["unmappedDecisions"]
        for e in x["relatedEdges"] if e.get("type") == "INTRODUCES"}
    if len(mapped_introduces | unmapped_introduces) != projection["originalCounts"]["introducedEdges"]:
        raise ValueError("INTRODUCED_CHILD_TRACE_LOST")
    # We cannot assert a fully lossless *migration* until unlinked legacy Decisions
    # have been resolved and the future writer has a documented round trip.
    return {
        "traceVerified": True,
        "migrationFullyResolved": not projection["unmappedDecisions"],
        "unmappedDecisionIds": [d["legacyDecisionId"] for d in projection["unmappedDecisions"]],
    }


CANON_RESULTS = {"applicable", "inapplicable", "unknown", "stale"}


def record_ai_assessment(canon_case, submitted):
    """Validate an argued, source-scoped assessment, NOT its factual correctness."""
    if not isinstance(canon_case, dict) or not canon_case.get("id"):
        raise ValueError("Canon case ID required")
    if not isinstance(submitted, dict) or submitted.get("result") not in CANON_RESULTS:
        raise ValueError("Unsupported assessment result")
    if not isinstance(submitted.get("rationale"), str) or not submitted["rationale"].strip():
        raise ValueError("Rationale required")
    refs = submitted.get("evidenceRefs")
    if not isinstance(refs, list) or not all(isinstance(x, str) and x for x in refs):
        raise ValueError("Evidence ref list required, possibly empty for unknown")
    if submitted["result"] in {"applicable", "inapplicable"} and not refs:
        raise ValueError("Cannot verify concrete canon outcome without sources")
    if not isinstance(submitted.get("contextVersion"), str) or not submitted["contextVersion"]:
        raise ValueError("Context version required")
    return {"caseId": canon_case["id"], "status": submitted["result"],
            "evidenceRefs": copy.deepcopy(refs), "contextVersion": submitted["contextVersion"],
            "rationale": submitted["rationale"],
            "verifiedByEngine": False, "kind": "candidate_ai_assessment"}


def evaluate_typed_predicate(predicate, inputs):
    """Tiny explicitly authored evaluator; never synthesize a DSL from canon prose."""
    if not isinstance(predicate, dict):
        raise ValueError("Predicate object required")
    op, field = predicate.get("op"), predicate.get("field")
    if op not in {"requirement_present", "context_equals"} or not isinstance(field, str):
        raise ValueError("Unsupported typed predicate")
    if not isinstance(inputs, dict) or inputs.get("version") is None:
        return {"status": "unknown", "why": "Missing versioned inputs"}
    if inputs.get("stale") is True:
        return {"status": "stale", "why": "Input is stale"}
    domain = "requirements" if op == "requirement_present" else "context"
    actual = inputs.get(domain)
    if not isinstance(actual, (list if domain == "requirements" else dict)):
        return {"status": "unknown", "why": "Missing declared input"}
    value = field in actual if op == "requirement_present" else actual.get(field)
    if op == "context_equals" and field not in actual:
        return {"status": "unknown", "why": "Context fact unavailable"}
    expected = True if op == "requirement_present" else predicate.get("equals")
    if op == "context_equals" and "equals" not in predicate:
        raise ValueError("Typed predicate missing equals")
    return {"status": "applicable" if value == expected else "inapplicable",
            "why": "Explicit typed predicate only", "contextVersion": str(inputs["version"])}


def cli():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph", help="Existing schemaVersion 1 graph.json; read-only")
    p.add_argument("--strategy", choices=["reuse-option-id", "new-action-id"])
    p.add_argument("--case", choices=["assessment", "typed"])
    p.add_argument("--payload", help="JSON payload for canon assessment/evaluation")
    a = p.parse_args()
    if a.graph:
        graph = json.loads(Path(a.graph).read_text(encoding="utf-8"))
        strategies = [a.strategy] if a.strategy else ["reuse-option-id", "new-action-id"]
        result = []
        for strategy in strategies:
            projection = identity_projection(graph, strategy)
            result.append({"projection": projection, "checks": check_projection(graph, projection)})
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif a.case:
        body = json.loads(a.payload or "{}")
        if a.case == "assessment":
            result = record_ai_assessment(body["canon"], body["assessment"])
        else:
            result = evaluate_typed_predicate(body["predicate"], body["inputs"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        p.error("Supply --graph or --case")


if __name__ == "__main__":
    cli()
