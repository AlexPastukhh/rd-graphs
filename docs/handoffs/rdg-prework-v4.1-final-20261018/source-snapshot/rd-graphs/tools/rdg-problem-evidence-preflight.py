#!/usr/bin/env python3
"""Preflight evidence for a possible CURRENT F-P, NEVER issue/commit F-P.

Local pins/scope/recording time can be verified. Trusted human/independent
fact verification and F-P publishing do not yet exist; fail closed.
"""
import argparse
import datetime as dt
import json
import re
from importlib.machinery import SourceFileLoader
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVIEW = SourceFileLoader("canon_context_for_problem_gate",
                          str(HERE / "rdg-canon-context-review.py")).load_module()
REF = re.compile(r"graph-node:([A-Za-z0-9_-]+)@([0-9a-f]{64})\Z")


def ensure(ok, code):
    if not ok:
        raise ValueError("PROBLEM_PREFLIGHT_" + code)


def assess(graph, request):
    ensure(isinstance(request, dict) and set(request) ==
           {"graphFile", "identitySpace", "observedRevision", "targetId",
            "findingId", "statement", "targetScope", "asOf", "evidenceRefs",
            "reviewQuestions"}, "SCHEMA")
    ensure(request.get("identitySpace") == graph.get("identitySpace") and
           isinstance(request.get("graphFile"), str) and
           REVIEW.GRAPH_REF.fullmatch(request["graphFile"]),
           "OWNER_REFERENCE")
    ensure(type(request.get("observedRevision")) is int and
           request["observedRevision"] >= 1 and
           isinstance(request.get("targetId"), str) and
           isinstance(request.get("findingId"), str) and
           isinstance(request.get("statement"), str) and
           bool(request["statement"].strip()) and
           isinstance(request.get("targetScope"), str) and
           bool(request["targetScope"].strip()), "REQUEST_IDENTITY")
    on = REVIEW.date(request.get("asOf"))
    nodes = graph.get("nodes")
    ensure(isinstance(nodes, list) and
           all(isinstance(n, dict) and isinstance(n.get("id"), str) for n in nodes)
           and len({n["id"] for n in nodes}) == len(nodes), "GRAPH_NODES_INVALID")
    target = [n for n in nodes if n["id"] == request["targetId"] and
              n.get("kind") in {"requirement", "option", "decision", "action"}]
    ensure(len(target) == 1, "TARGET_NOT_FOUND")
    ensure(isinstance(request.get("evidenceRefs"), list) and
           bool(request["evidenceRefs"]) and
           all(isinstance(x, str) for x in request["evidenceRefs"]) and
           len(request["evidenceRefs"]) == len(set(request["evidenceRefs"])) and
           isinstance(request.get("reviewQuestions"), list) and
           bool(request["reviewQuestions"]) and
           all(isinstance(q, str) and bool(q.strip()) for q in
               request["reviewQuestions"]), "EVIDENCE_AND_REVIEW_REQUIRED")
    pinned = graph.get("revision") == request["observedRevision"]
    lookup = {n["id"]: n for n in nodes}
    checks = []
    for ref in request["evidenceRefs"]:
        match = REF.fullmatch(ref)
        if not match:
            checks.append({"ref": ref, "status": "invalid-reference"})
            continue
        ident, expected = match.groups()
        source = lookup.get(ident)
        if source is None:
            verdict = "missing-node"
        elif REVIEW.sha(source) != expected:
            verdict = "changed-node"
        else:
            verdict = REVIEW.context_check(source, request["targetScope"], on)
        checks.append({"ref": ref, "status": verdict})
    local_ready = pinned and all(x["status"] == "locally-current-record"
                                 for x in checks)
    today = dt.datetime.now(dt.timezone.utc).date()
    # Historical T1/T2 analysis is a different task from CURRENT attestation.
    is_current_date = on == today
    blockers = []
    if not pinned:
        blockers.append("source-revision-stale")
    if not local_ready:
        blockers.append("local-evidence-not-current-or-not-pinned")
    if not is_current_date:
        blockers.append("as-of-not-current-utc-date")
    # This remains blocking even with impeccable hashes and a bearer grant.
    blockers.append("trusted-independent-factual-attestation-not-implemented")
    return {
        "findingId": request["findingId"],
        "candidateFindingType": "F-P",
        "findingScope": "CURRENT",
        "targetId": request["targetId"], "graphFile": request["graphFile"],
        "identitySpace": request["identitySpace"],
        "sourceRevision": graph.get("revision"),
        "pinMatches": pinned, "asOf": on.isoformat(),
        "localEvidenceChecks": checks,
        "localEvidenceReadyForReview": local_ready and is_current_date,
        "readOnly": True, "confirmedProblem": False,
        "mayAppendFP": False, "trustProofValidated": False,
        "humanIdentityVerified": False, "missingGates": blockers,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--request", type=Path, required=True)
    a = p.parse_args()
    request = json.loads(a.request.read_text(encoding="utf8"))
    ensure(isinstance(request, dict) and isinstance(request.get("graphFile"), str)
           and a.graph.resolve().as_posix().endswith("/" + request["graphFile"]),
           "GRAPH_PATH_REF_MISMATCH")
    graph = json.loads(a.graph.read_text(encoding="utf8"))
    print(json.dumps(assess(graph, request), ensure_ascii=False,
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as e:
        import sys
        print("ERROR: " + str(e), file=sys.stderr)
        sys.exit(1)
