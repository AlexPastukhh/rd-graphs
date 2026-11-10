#!/usr/bin/env python3
"""Read-only two-time rule probe over exact candidate Plan/RDG snapshots.

Applicability assertions are caller-supplied, unverified scenario input. This
is not an owner journal, factual event, accepted baseline or historical as-of.
"""
import argparse
import copy
import datetime as dt
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
HISTORY = SourceFileLoader("two_time_exact_history", str(HERE / "rdg-exact-history.py")).load_module()
OWNER = HISTORY.OWNER
ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,99}\Z")
OFFSET = re.compile(r"(?:Z|[+-]\d{2}:\d{2})\Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def require(ok, code):
    if not ok:
        raise ValueError("TWO_TIME_SCENARIO_" + code)


def effective(value):
    require(isinstance(value, str), "EFFECTIVE_AT_REQUIRED")
    if DATE.fullmatch(value):
        try:
            return "date", dt.date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("TWO_TIME_SCENARIO_EFFECTIVE_AT_INVALID") from error
    require("T" in value and OFFSET.search(value), "EFFECTIVE_AT_PRECISION_REQUIRED")
    try:
        return "instant", OWNER.instant(value)
    except (ValueError, TypeError) as error:
        raise ValueError("TWO_TIME_SCENARIO_EFFECTIVE_AT_INVALID") from error


def known(value):
    require(isinstance(value, str) and "T" in value and OFFSET.search(value),
            "KNOWN_AT_INSTANT_REQUIRED")
    try:
        return OWNER.instant(value)
    except (ValueError, TypeError) as error:
        raise ValueError("TWO_TIME_SCENARIO_KNOWN_AT_INVALID") from error


def availability(plan_root, pin):
    receipt = OWNER.read_availability(plan_root, pin["file"], pin["revision"],
                                      pin["recordDigest"])
    if receipt is not None:
        return receipt["availableBy"], "owner-after-durable-store"
    try:
        following = OWNER.read_snapshot(plan_root, pin["file"], pin["revision"] + 1)
    except ValueError as error:
        if "SNAPSHOT_NOT_FOUND" in str(error):
            return None, None
        raise
    return following["provenance"]["recordedAt"], "next-guarded-plan-edit"


def resolve(plan_root, graphs_root, authority_store, token, request, before_return=None):
    require(isinstance(request, dict) and
            set(request) == {"schemaVersion", "mode", "knownAt", "effectiveAt", "assertions"} and
            type(request["schemaVersion"]) is int and request["schemaVersion"] == 1 and
            request["mode"] == "candidate-two-time-scenario" and
            isinstance(request["assertions"], list) and request["assertions"], "REQUEST_SCHEMA")
    cutoff = known(request["knownAt"])
    precision, effective_cutoff = effective(request["effectiveAt"])
    assertions, by_id, revisions = [], {}, set()
    owner_key, branch_id = None, None
    targets = set()
    for assertion in request["assertions"]:
        require(isinstance(assertion, dict) and
                set(assertion) == {"id", "effectiveAt", "supersedes", "source", "eventClaim"} and
                isinstance(assertion["id"], str) and ID.fullmatch(assertion["id"]) and
                assertion["id"] not in by_id and
                (assertion["supersedes"] is None or
                 isinstance(assertion["supersedes"], str) and ID.fullmatch(assertion["supersedes"])),
                "ASSERTION_SCHEMA")
        claim_precision, effective_from = effective(assertion["effectiveAt"])
        require(claim_precision == precision, "EFFECTIVE_AT_PRECISION_MISMATCH")
        source = assertion["source"]
        HISTORY.validate_query(source)
        require("knownAt" not in source, "SOURCE_MUST_BE_EXACT_ONLY")
        pin = source["plan"]
        key = pin["file"], pin["identitySpace"], pin["planId"]
        require(owner_key is None or key == owner_key, "PLAN_OWNER_SCOPE_CONFLICT")
        owner_key = key
        require(branch_id is None or source["scenario"]["branchId"] == branch_id,
                "BRANCH_SCOPE_CONFLICT")
        branch_id = source["scenario"]["branchId"]
        require(isinstance(branch_id, str) and
                isinstance(source["scenario"]["outcome"], str), "BRANCH_REQUIRED")
        require(pin["revision"] not in revisions, "DUPLICATE_PLAN_REVISION")
        revisions.add(pin["revision"])
        # Resolve every exact pin and graph even when the assertion is outside
        # the cutoff. A malformed fixture cannot silently disappear by date.
        resolved = HISTORY.resolve(plan_root, graphs_root, authority_store, token, source)
        branches = [b for b in resolved["plan"]["branches"] if b["id"] == branch_id]
        require(len(branches) == 1, "BRANCH_SCOPE_INVALID")
        branch = branches[0]
        event_claim = assertion["eventClaim"]
        if event_claim is not None:
            require(isinstance(event_claim, dict) and
                    set(event_claim) == {"eventStepId", "outcome", "verification"} and
                    event_claim["eventStepId"] == branch["eventStepId"] and
                    event_claim["outcome"] == source["scenario"]["outcome"] and
                    event_claim["verification"] == "unverified", "EVENT_CLAIM_INVALID")
        targets.update(pin["graphFile"] for pin in source["graphs"])
        bound, bound_source = availability(plan_root, pin)
        item = {"id": assertion["id"], "supersedes": assertion["supersedes"],
                "source": source, "effectiveAt": assertion["effectiveAt"],
                "effectiveValue": effective_from, "eventClaim": event_claim,
                "availableBy": bound, "availabilitySource": bound_source,
                "revision": pin["revision"]}
        assertions.append(item)
        by_id[item["id"]] = item
    for item in assertions:
        if item["supersedes"] is None:
            continue
        prior = by_id.get(item["supersedes"])
        require(prior is not None and prior["revision"] < item["revision"] and
                prior["effectiveValue"] <= item["effectiveValue"] and
                (prior["eventClaim"] is None) == (item["eventClaim"] is None) and
                (prior["eventClaim"] is None or
                 prior["eventClaim"]["eventStepId"] == item["eventClaim"]["eventStepId"]),
                "CORRECTION_CHAIN_INVALID")
    eligible, excluded = [], []
    for item in assertions:
        if item["effectiveValue"] > effective_cutoff:
            excluded.append({"id": item["id"], "reason": "effective-after-query"})
        else:
            require(item["availableBy"] is not None, "AVAILABILITY_BOUND_NOT_AVAILABLE")
            if OWNER.instant(item["availableBy"]) > cutoff:
                excluded.append({"id": item["id"], "reason": "not-proven-known"})
            else:
                eligible.append(item)
    superseded = {item["supersedes"] for item in eligible if item["supersedes"] is not None}
    leaves = [item for item in eligible if item["id"] not in superseded]
    require(leaves, "NO_KNOWN_APPLICABLE_ASSERTION")
    require(len(leaves) == 1, "UNRESOLVED_APPLICABILITY_CONFLICT")
    selected = leaves[0]
    exact = copy.deepcopy(selected["source"])
    exact["knownAt"] = request["knownAt"]
    resolved = HISTORY.resolve(plan_root, graphs_root, authority_store, token, exact)
    if before_return:
        before_return()
    OWNER.AUTH.Authority(authority_store).authorize_snapshot_read(token, owner_key[0],
                                                                  sorted(targets))
    return {"status": "candidate-scenario", "mode": request["mode"],
            "knownAt": request["knownAt"], "effectiveAt": request["effectiveAt"],
            "selectedAssertionId": selected["id"], "selectedEffectiveAt": selected["effectiveAt"],
            "selectedAvailableBy": selected["availableBy"],
            "selectedAvailabilitySource": selected["availabilitySource"],
            "eventClaim": copy.deepcopy(selected["eventClaim"]),
            "excluded": excluded, "exactSource": resolved,
            "provenance": {"exactPinnedSourcesResolved": True,
                           "twoTimeRuleEvaluated": True,
                           "applicabilityAttested": False,
                           "eventClaimVerified": False,
                           "completeApplicableContextVerified": False,
                           "twoTimeAsOfResolved": False,
                           "historicalT1KnowledgeVerified": False,
                           "productionAccepted": False},
            "evidenceGaps": ["Applicability and event claims are caller-supplied unverified scenario input",
                             "Other applicable owners, events and lifecycle records are not proven complete",
                             "No historical Gendocen subscription or factual T1 verification"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-root", required=True, type=Path)
    parser.add_argument("--graphs-root", required=True, type=Path)
    parser.add_argument("--store", default=os.environ.get("RDG_AUTH_STORE"))
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args()
    require(args.store is not None, "AUTH_STORE_REQUIRED")
    result = resolve(args.plan_root, args.graphs_root, args.store,
                     os.environ.get("RDG_AUTH_TOKEN"), HISTORY.load_bytes(args.request.read_bytes()))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
