#!/usr/bin/env python3
"""Read-only check of canon assessments against exact current RDG context refs.

Local context existence/hash/time/scope are verifiable. Context truth and the
semantic claim 'this canon applies' are NOT independently established.
No graph edits, Findings, proposals, selection or Plan execution.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

REF = re.compile(r"graph-node:([A-Za-z0-9_-]+)@([0-9a-f]{64})\Z")
GRAPH_REF = re.compile(r"workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json\Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
CASE_STATUS = {"applicable", "inapplicable", "unknown"}


def ensure(condition, code):
    if not condition:
        raise ValueError("CANON_REVIEW_" + code)


def sha(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf8")
    return hashlib.sha256(encoded).hexdigest()


def date(value):
    ensure(isinstance(value, str) and bool(DATE.fullmatch(value)), "DATE_REQUIRED")
    return dt.date.fromisoformat(value)


def context_check(node, target_scope, on):
    if not isinstance(node, dict) or node.get("kind") != "context":
        return "not-a-context"
    if node.get("active") is False or node.get("status") in ("inactive", "superseded"):
        return "inactive"
    # A recorded answer is not evidence of its own objective truth. It is
    # nevertheless an inspectable material assertion with explicit provenance.
    if node.get("evidenceStatus") != "checked-present" or not isinstance(
            node.get("contextValue"), dict) or not node.get("contextValue"):
        return "not-confirmed-in-record"
    scope = node.get("scope")
    if scope not in (target_scope, "project", "global", "*"):
        return "scope-not-proven"
    observed = node.get("recordedAt")
    if not isinstance(observed, str) or not DATE.fullmatch(observed):
        return "record-time-not-proven"
    try:
        recorded = date(observed)
    except ValueError:
        return "invalid-dates"
    # T2 discovered later is not contemporaneous T1 knowledge. Record-time
    # is separate from effective-time; both must be valid for this as-of.
    if recorded > on:
        return "not-recorded-as-of"
    since = node.get("effectiveAt")
    until = node.get("validUntil")
    if since is None or not isinstance(since, str) or not DATE.fullmatch(since):
        return "date-not-proven"
    try:
        start = date(since)
        end = date(until) if until is not None else None
    except ValueError:
        return "invalid-dates"
    if (start > on or (end is not None and end < on)):
        return "outside-effective-window"
    return "locally-current-record"


def validate_source(graph, packet):
    ensure(isinstance(graph, dict) and isinstance(graph.get("nodes"), list) and
           isinstance(graph.get("identitySpace"), str), "GRAPH_INVALID")
    ensure(isinstance(packet, dict) and set(packet) ==
           {"identitySpace", "graphFile", "targetId", "targetScope", "asOf",
            "observedRevision", "observedCanonSHA256", "assessments"},
           "ASSESSMENT_SCHEMA")
    ensure(packet["identitySpace"] == graph["identitySpace"], "IDENTITY_MISMATCH")
    ensure(isinstance(packet["graphFile"], str) and
           GRAPH_REF.fullmatch(packet["graphFile"]), "GRAPH_FILE_REF_REQUIRED")
    ensure(isinstance(packet["targetScope"], str) and
           bool(packet["targetScope"].strip()), "SCOPE_REQUIRED")
    as_of = date(packet["asOf"])
    nodes = graph["nodes"]
    ensure(all(isinstance(n, dict) and isinstance(n.get("id"), str)
               for n in nodes) and len({n["id"] for n in nodes}) == len(nodes),
           "GRAPH_NODE_IDS")
    matches = [n for n in nodes if n["id"] == packet["targetId"] and
               n.get("kind") in ("action", "option")]
    ensure(len(matches) == 1, "ACTION_OR_OPTION_NOT_FOUND")
    item = matches[0]
    block = item.get("canonBlock")
    ensure(isinstance(block, dict) and
           all(isinstance(block.get(k), list) for k in
               ("recommended", "contraindicated")), "CANON_REQUIRED")
    by_case = {}
    for polarity in ("recommended", "contraindicated"):
        for case in block[polarity]:
            ensure(isinstance(case, dict) and isinstance(case.get("id"), str) and
                   case["id"] not in by_case, "CANON_CASE_IDS")
            by_case[case["id"]] = polarity
    ensure(isinstance(packet["observedCanonSHA256"], str) and
           re.fullmatch(r"[0-9a-f]{64}", packet["observedCanonSHA256"]) and
           type(packet["observedRevision"]) is int and
           packet["observedRevision"] >= 1, "SOURCE_PIN_REQUIRED")
    ensure(isinstance(packet["assessments"], list), "ASSESSMENTS_REQUIRED")
    seen = set()
    for claim in packet["assessments"]:
        ensure(isinstance(claim, dict) and set(claim) ==
               {"caseId", "result", "reason", "evidenceRefs"} and
               claim.get("caseId") in by_case and claim["caseId"] not in seen,
               "CLAIM_CASE_UNKNOWN_OR_DUPLICATE")
        seen.add(claim["caseId"])
        ensure(claim.get("result") in CASE_STATUS and
               isinstance(claim.get("reason"), str) and
               bool(claim["reason"].strip()) and
               isinstance(claim.get("evidenceRefs"), list) and
               all(isinstance(ref, str) for ref in claim["evidenceRefs"]) and
               len(set(claim["evidenceRefs"])) == len(claim["evidenceRefs"]),
               "CLAIM_MALFORMED")
        ensure(claim["result"] == "unknown" or bool(claim["evidenceRefs"]),
               "EVIDENCE_REQUIRED_FOR_CLAIM")
    return item, block, by_case, as_of


def evaluate(graph, packet, impact=None):
    item, block, by_case, as_of = validate_source(graph, packet)
    pinned = (graph.get("revision") == packet["observedRevision"] and
              sha(block) == packet["observedCanonSHA256"])
    index = {n["id"]: n for n in graph["nodes"]}
    claims = {x["caseId"]: x for x in packet["assessments"]}
    cases = []
    for polarity in ("recommended", "contraindicated"):
        for case in block[polarity]:
            claim = claims.get(case["id"])
            evidence = []
            for ref in claim.get("evidenceRefs", []) if claim else []:
                match = REF.fullmatch(ref)
                if not match:
                    evidence.append({"ref": ref, "result": "invalid-ref"})
                    continue
                nid, expected = match.groups()
                source = index.get(nid)
                if source is None:
                    outcome = "missing-source"
                elif sha(source) != expected:
                    outcome = "stale-source"
                else:
                    outcome = context_check(source, packet["targetScope"], as_of)
                evidence.append({"ref": ref, "result": outcome})
            claim_result = claim["result"] if claim else "missing"
            evidence_ok = bool(evidence) and all(
                entry["result"] == "locally-current-record" for entry in evidence)
            if not pinned:
                verification = "stale-action-or-canon-pin"
            elif claim is None or claim_result == "unknown":
                verification = "not-assessed"
            elif not evidence_ok:
                verification = "evidence-needs-review"
            else:
                verification = "record-backed-claim-needs-semantic-review"
            cases.append({
                "caseId": case["id"], "polarity": polarity,
                "claimResult": claim_result, "verification": verification,
                "sourceCurrent": pinned, "evidence": evidence,
                "semanticApplicabilityProven": False,
                "reason": claim["reason"] if claim else None,
            })
    temporal = None
    if impact is not None:
        ensure(isinstance(impact, dict) and impact.get("readOnly") is True and
               impact.get("planStatus") == "candidate" and
               impact.get("committedFindings") == [] and
               impact.get("selectedActions") == [] and
               isinstance(impact.get("branches"), list), "IMPACT_UNTRUSTED")
        candidates = [lead for branch in impact["branches"]
                      for lead in branch.get("actionReviewLeads", [])
                      if lead.get("action", {}).get("actionId") == item["id"] and
                      lead.get("action", {}).get("identitySpace") == graph["identitySpace"] and
                      lead.get("action", {}).get("graphFile") == packet["graphFile"]]
        temporal = {
            "planId": impact.get("planId"), "planRevision": impact.get("planRevision"),
            "matchingActionLeads": [
                {"stepId": x["stepId"], "branchId": x["branchId"],
                 "outcome": x["outcome"], "dependencyDigest": x["dependencyDigest"],
                 "timeConflictReview": x["timeConflictReview"],
                 "comparison": [check["comparison"] for check in x["deadlineChecks"]]}
                for x in candidates
            ],
            "status": "candidate-context-only", "authoritative": False,
        }
    return {
        "identitySpace": graph["identitySpace"], "graphFile": packet["graphFile"],
        "targetId": item["id"],
        "targetKind": item["kind"], "targetStatus": item.get("status"),
        "graphRevision": graph.get("revision"),
        "observedRevision": packet["observedRevision"],
        "canonSHA256": sha(block), "pinMatches": pinned,
        "asOf": as_of.isoformat(), "targetScope": packet["targetScope"],
        "canonCases": cases, "temporalReview": temporal,
        "positiveClaimsWithLocallyCurrentRefs": [
            c["caseId"] for c in cases if c["polarity"] == "recommended" and
            c["claimResult"] == "applicable" and
            c["verification"] == "record-backed-claim-needs-semantic-review"],
        "contraindicationClaimsWithLocallyCurrentRefs": [
            c["caseId"] for c in cases if c["polarity"] == "contraindicated" and
            c["claimResult"] == "applicable" and
            c["verification"] == "record-backed-claim-needs-semantic-review"],
        "canonVerdict": "needs-semantic-assessment",
        "actionSelected": False, "committedFindings": [], "readOnly": True,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph", required=True, type=Path)
    ap.add_argument("--assessment", required=True, type=Path)
    ap.add_argument("--impact-report", type=Path)
    args = ap.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf8"))
    packet = json.loads(args.assessment.read_text(encoding="utf8"))
    ensure(isinstance(packet, dict) and isinstance(packet.get("graphFile"), str) and
           args.graph.resolve().as_posix().endswith("/" + packet["graphFile"]),
           "GRAPH_PATH_REF_MISMATCH")
    impact = json.loads(args.impact_report.read_text(encoding="utf8")) if args.impact_report else None
    print(json.dumps(evaluate(graph, packet, impact), ensure_ascii=False,
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        import sys
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
