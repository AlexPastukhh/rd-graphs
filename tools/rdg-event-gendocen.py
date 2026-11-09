#!/usr/bin/env python3
"""Explicit Gendocen projection for technical event history, contract v1.

Dependency validity concerns the projected context only. It is not factual
verification, a Plan/RDG as-of resolver or authority to select an Action.
"""
import argparse
import copy
import hashlib
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENT = SourceFileLoader("gendocen_event_owner", str(HERE / "rdg-event-owner.py")).load_module()
VERSION = "rdg-event-review/v1"
GROUPS = ("identity", "knowledge", "claims", "attestations", "reviews",
          "resolution", "boundaries")
READ_MATRIX = {
    "identity": ["planFile", "occurrenceId", "claims/*/payload/planPin/{identitySpace,planId}"],
    "knowledge": ["knownAt"],
    "claims": ["claims/*/{payload,recordDigest,recordedAt,availableBy}"],
    "attestations": ["attestations/*/{payload,recordDigest,availableBy}"],
    "reviews": ["reviews/*/{payload,recordDigest,availableBy}"],
    "resolution": ["unresolvedClaimIds", "claimConflict"],
    "boundaries": ["status", "readOnly", "provenance/*"],
}
TRUE_FLAGS = {"exactPlanSnapshotsResolved", "stagedRecordsDurable",
              "distinctBearerGrantsEnforced"}
FALSE_FLAGS = {"humanIdentityVerified", "evidenceContentsVerified",
               "factualEventVerified", "factualBranchResolved", "actionSelected",
               "completeApplicableContextVerified", "productionAccepted"}


def require(ok, code):
    if not ok:
        raise ValueError("EVENT_REVIEW_" + code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode("utf8")).hexdigest()


def validate_history(history):
    require(isinstance(history, dict) and set(history) == {
        "status", "planFile", "occurrenceId", "knownAt", "claims",
        "attestations", "reviews", "unresolvedClaimIds", "claimConflict",
        "readOnly", "provenance"} and
        history["status"] == "technical-event-history" and history["readOnly"] is True and
        isinstance(history["planFile"], str) and EVENT.OWNER.TARGET.fullmatch(history["planFile"]) and
        isinstance(history["occurrenceId"], str) and EVENT.ID.fullmatch(history["occurrenceId"]),
        "HISTORY_SCHEMA")
    if history["knownAt"] is not None:
        EVENT.MODEL.known(history["knownAt"])
    provenance = history["provenance"]
    require(isinstance(provenance, dict) and set(provenance) == TRUE_FLAGS | FALSE_FLAGS and
            all(provenance[k] is True for k in TRUE_FLAGS) and
            all(provenance[k] is False for k in FALSE_FLAGS), "UNSUPPORTED_TRUST_OR_SCOPE")
    claims, attestations, ids, superseded, owner_scope, precision = {}, {}, set(), set(), None, None
    reviewed = set()
    require(isinstance(history["claims"], list) and history["claims"], "CLAIMS_REQUIRED")
    for field, kind in (("claims", "claim"), ("attestations", "attest"), ("reviews", "verify")):
        require(isinstance(history[field], list), "RECORD_LIST_SCHEMA")
        for record in history[field]:
            keys = {"payload", "recordDigest", "availableBy"} | (
                {"recordedAt"} if kind == "claim" else set())
            require(isinstance(record, dict) and set(record) == keys and
                    isinstance(record["recordDigest"], str) and
                    EVENT.HISTORY.SHA.fullmatch(record["recordDigest"]), "RECORD_SCHEMA")
            payload = EVENT.validate_payload(kind, record["payload"], history["planFile"])
            require(payload["id"] not in ids, "DUPLICATE_RECORD_ID")
            ids.add(payload["id"])
            available = EVENT.MODEL.known(record["availableBy"])
            require(history["knownAt"] is None or
                    available <= EVENT.MODEL.known(history["knownAt"]), "RECORD_AFTER_CUTOFF")
            if kind == "claim":
                require(EVENT.MODEL.known(record["recordedAt"]) <= available,
                        "RECORD_AVAILABILITY_ORDER")
                pin = payload["planPin"]
                scope = pin["identitySpace"], pin["planId"], payload["eventStepId"]
                current_precision, _ = EVENT.MODEL.effective(payload["occurredAt"])
                require(payload["occurrenceId"] == history["occurrenceId"] and
                        (owner_scope is None or owner_scope == scope) and
                        (precision is None or precision == current_precision),
                        "OCCURRENCE_SCOPE")
                require(payload["supersedes"] is None or
                        payload["supersedes"] in claims and
                        pin["revision"] >= claims[payload["supersedes"]]["payload"]["planPin"]["revision"],
                        "CORRECTION_CHAIN")
                if payload["supersedes"] is not None:
                    superseded.add(payload["supersedes"])
                claims[payload["id"]] = record
                owner_scope, precision = scope, current_precision
            elif kind == "attest":
                require(payload["claimId"] in claims and
                        all(x["payload"]["claimId"] != payload["claimId"]
                            for x in attestations.values()), "CLAIM_REFERENCE")
                attestations[payload["id"]] = record
            else:
                require(payload["attestationId"] in attestations and
                        payload["attestationId"] not in reviewed, "ATTESTATION_REFERENCE")
                reviewed.add(payload["attestationId"])
    leaves = sorted(set(claims) - superseded)
    require(isinstance(history["unresolvedClaimIds"], list) and
            sorted(history["unresolvedClaimIds"]) == leaves and
            type(history["claimConflict"]) is bool and
            history["claimConflict"] == (len(leaves) != 1), "RESOLUTION_MISMATCH")
    return owner_scope


def views(history):
    scope = validate_history(history)
    known = (EVENT.MODEL.known(history["knownAt"]).isoformat()
             if history["knownAt"] is not None else None)
    result = {
        "identity": {"planFile": history["planFile"],
                     "identitySpace": scope[0], "planId": scope[1],
                     "eventStepId": scope[2], "occurrenceId": history["occurrenceId"]},
        "knowledge": {"mode": "fixed-knownAt" if known else "current-known-records",
                      "knownAt": known},
        "claims": {r["payload"]["id"]: copy.deepcopy(r) for r in history["claims"]},
        "attestations": {r["payload"]["id"]: copy.deepcopy(r) for r in history["attestations"]},
        "reviews": {r["payload"]["id"]: copy.deepcopy(r) for r in history["reviews"]},
        "resolution": {"unresolvedClaimIds": sorted(history["unresolvedClaimIds"]),
                       "claimConflict": history["claimConflict"]},
        "boundaries": {"status": history["status"], "readOnly": history["readOnly"],
                       **copy.deepcopy(history["provenance"])},
    }
    # The producer groups are fixed independently of the mutable declaration.
    require(set(result) == set(GROUPS) == set(READ_MATRIX),
            "SOURCE_GROUPS_INCOMPLETE_OR_UNKNOWN")
    return result


def project(history):
    require(isinstance(history, dict), "HISTORY_SCHEMA")
    raw = copy.deepcopy(history)
    if raw.get("knownAt") is not None:
        raw["knownAt"] = EVENT.MODEL.known(raw["knownAt"]).isoformat()
    inputs = views(raw)
    coverage = {"contract": VERSION, "scope": "one-technical-event-occurrence",
                "completeForDeclaredScope": True, "sourceReads": copy.deepcopy(READ_MATRIX),
                "factualEventVerified": False, "completePlanRdgContext": False}
    ident = "rdg.event." + digest({
        "identity": inputs["identity"], "knowledge": inputs["knowledge"]})[:24]
    return {"$docengine": {"resource_id": ident, "materialize": []},
            "data": {"sourceHistory": raw, "reviewCoverage": coverage,
                     "reviewInputs": inputs, "semanticSHA256": digest(inputs)}}


def from_owner(root, authority_store, token, plan_file, occurrence_id, known_at=None):
    return project(EVENT.read(root, authority_store, token, plan_file,
                              occurrence_id, known_at))


def resource_ref(resource):
    return "resource://" + resource["$docengine"]["resource_id"].replace(".", "/", 1)


def build_contract(resource):
    require(isinstance(resource, dict) and set(resource) == {"$docengine", "data"} and
            isinstance(resource["data"], dict) and set(resource["data"]) == {
                "sourceHistory", "reviewCoverage", "reviewInputs", "semanticSHA256"},
            "RESOURCE_SCHEMA")
    expected = project(resource["data"]["sourceHistory"])
    require(resource == expected, "PROJECTION_INCOMPLETE_OR_STALE")
    ref = resource_ref(resource)
    return {"contract": VERSION, "completeForDeclaredScope": True,
            "subscriptions": [(ref + "#/reviewCoverage", "exact")] +
                [(ref + "#/reviewInputs/" + key, "exact") for key in GROUPS],
            "provenance": {"scope": "one-technical-event-occurrence",
                           "factualEventVerified": False,
                           "completePlanRdgContext": False}}


def assert_coverage(contract, declared):
    require(contract.get("contract") == VERSION and
            contract.get("completeForDeclaredScope") is True, "UNKNOWN_CONTRACT")
    expected = {tuple(x) for x in contract["subscriptions"]}
    actual = {tuple(x) for x in declared}
    require(expected == actual and len(declared) == len(expected),
            "SUBSCRIPTIONS_INCOMPLETE")


def project_config(targets):
    """Register explicit event-review documents in a synthetic local project."""
    return (
        "import json\nfrom pathlib import Path\n"
        "from importlib.machinery import SourceFileLoader\n"
        f"event_dep = SourceFileLoader('event_review_contract', {str(Path(__file__).resolve())!r}).load_module()\n"
        "def register_builders(registry):\n    pass\n\n"
        "def register_semantic_dependencies(registry):\n"
        "    docs = Path(__file__).resolve().parents[1] / 'docs'\n"
        f"    for target, relative in {targets!r}:\n"
        "        resource = json.loads((docs / relative).read_text(encoding='utf8'))\n"
        "        contract = event_dep.build_contract(resource)\n"
        "        sources = contract['subscriptions']\n"
        "        event_dep.assert_coverage(contract, sources)\n"
        "        registry.register('file://review/' + target + '.md', sources,\n"
        f"                          rule_id={VERSION.replace('/', '.')!r} + '.' + target,\n"
        "                          dependency_type='semantic_review')\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--store", default=os.environ.get("RDG_AUTH_STORE"))
    parser.add_argument("--file", required=True)
    parser.add_argument("--occurrence-id", required=True)
    parser.add_argument("--known-at")
    args = parser.parse_args()
    require(args.store, "AUTH_STORE_REQUIRED")
    print(json.dumps(from_owner(args.root, args.store, os.environ.get("RDG_AUTH_TOKEN"),
        args.file, args.occurrence_id, args.known_at), ensure_ascii=False,
        sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
