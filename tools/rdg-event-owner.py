#!/usr/bin/env python3
"""Local staged event records: claim, technical attestation, technical review.

No factual outcome, human identity, Action selection or production truth is
established by bearer grants or client evidence references.
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
OWNER = SourceFileLoader("event_plan_owner", str(HERE / "rdg-temporal-plan-owner.py")).load_module()
HISTORY = SourceFileLoader("event_exact_history", str(HERE / "rdg-exact-history.py")).load_module()
MODEL = SourceFileLoader("event_time_rule", str(HERE / "rdg-two-time-scenario.py")).load_module()
ID = MODEL.ID
TX = re.compile(r"[A-Za-z0-9_-]{1,120}\Z")
NAME = ".rdg-event-history.json"
JOURNAL = "_rdg-event-journal.json"
PERMISSIONS = {"claim": ["plan.edit", "plan.read"],
               "attest": ["plan.event_attest", "plan.read"],
               "verify": ["plan.event_verify", "plan.read"]}


def require(ok, code):
    if not ok:
        raise ValueError("EVENT_OWNER_" + code)


def target_path(root, plan_file):
    path = OWNER.safe(root, plan_file).with_name(NAME)
    require(not path.is_symlink() and path.resolve().is_relative_to(root), "PATH_INVALID")
    return path


def receipt_path(root, plan_file, revision):
    require(type(revision) is int and revision >= 1, "REVISION_INVALID")
    path = OWNER.safe(root, plan_file).with_name(f".rdg-event-available-r{revision}.json")
    require(not path.is_symlink() and path.resolve().is_relative_to(root), "RECEIPT_PATH_INVALID")
    return path


def journal_path(root):
    path = root / JOURNAL
    require(not path.is_symlink() and path.resolve().is_relative_to(root), "JOURNAL_PATH_INVALID")
    return path


def evidence(value):
    require(isinstance(value, list) and value and len(value) == len(set(value)) and
            all(isinstance(x, str) and ID.fullmatch(x) for x in value),
            "EVIDENCE_REFS_REQUIRED")


def validate_pin(pin, plan_file):
    require(isinstance(pin, dict) and
            set(pin) == {"file", "identitySpace", "planId", "revision",
                         "snapshotSHA256", "recordDigest"} and
            pin["file"] == plan_file and OWNER.PLAN.named(pin["identitySpace"]) and
            OWNER.PLAN.ident(pin["planId"]) and
            type(pin["revision"]) is int and pin["revision"] >= 1 and
            all(isinstance(pin[k], str) and HISTORY.SHA.fullmatch(pin[k])
                for k in ("snapshotSHA256", "recordDigest")), "PLAN_PIN_INVALID")
    return pin


def validate_payload(kind, payload, plan_file):
    require(isinstance(payload, dict) and isinstance(payload.get("id"), str) and
            ID.fullmatch(payload["id"]), "PAYLOAD_ID")
    if kind == "claim":
        require(set(payload) == {"id", "occurrenceId", "planPin", "eventStepId",
                 "outcome", "occurredAt", "evidenceRefs", "supersedes"} and
                isinstance(payload["occurrenceId"], str) and ID.fullmatch(payload["occurrenceId"]) and
                isinstance(payload["eventStepId"], str) and ID.fullmatch(payload["eventStepId"]) and
                isinstance(payload["outcome"], str) and ID.fullmatch(payload["outcome"]) and
                (payload["supersedes"] is None or isinstance(payload["supersedes"], str) and
                 ID.fullmatch(payload["supersedes"])), "CLAIM_SCHEMA")
        validate_pin(payload["planPin"], plan_file)
        MODEL.effective(payload["occurredAt"])
        evidence(payload["evidenceRefs"])
    elif kind == "attest":
        require(set(payload) == {"id", "claimId", "evidenceRefs"} and
                isinstance(payload["claimId"], str) and ID.fullmatch(payload["claimId"]),
                "ATTEST_SCHEMA")
        evidence(payload["evidenceRefs"])
    elif kind == "verify":
        require(set(payload) == {"id", "attestationId", "decision", "evidenceRefs"} and
                isinstance(payload["attestationId"], str) and ID.fullmatch(payload["attestationId"]) and
                payload["decision"] in ("reviewed-supported", "disputed"),
                "VERIFY_SCHEMA")
        evidence(payload["evidenceRefs"])
    else:
        raise ValueError("EVENT_OWNER_KIND_INVALID")
    return payload


def validate_store(store, plan_file):
    require(isinstance(store, dict) and
            set(store) == {"schemaVersion", "kind", "planFile", "revision",
                           "records", "transactions"} and
            store["schemaVersion"] == 1 and store["kind"] == "candidateEventHistory" and
            store["planFile"] == plan_file and type(store["revision"]) is int and
            store["revision"] >= 1 and isinstance(store["records"], list) and
            len(store["records"]) == store["revision"] and
            isinstance(store["transactions"], dict), "STORE_SCHEMA")
    previous, clock, txs, ids, claims, attestations = None, None, {}, set(), {}, {}
    occurrence_scope, attested, reviewed = {}, set(), set()
    for number, record in enumerate(store["records"], 1):
        require(isinstance(record, dict) and
                set(record) == {"revision", "kind", "payload", "recordedAt",
                                "previousDigest", "digest", "transactionId",
                                "requestSHA256", "receipt"} and
                type(record["revision"]) is int and record["revision"] == number and
                record["previousDigest"] == previous and
                record["digest"] == OWNER.digest({k:v for k,v in record.items() if k != "digest"}),
                "RECORD_HASH")
        kind, payload = record["kind"], record["payload"]
        validate_payload(kind, payload, plan_file)
        require(payload["id"] not in ids, "DUPLICATE_RECORD_ID")
        ids.add(payload["id"])
        if kind == "claim":
            pin, occ = payload["planPin"], payload["occurrenceId"]
            scope = pin["identitySpace"], pin["planId"], payload["eventStepId"]
            precision, _ = MODEL.effective(payload["occurredAt"])
            require(occ not in occurrence_scope or
                    occurrence_scope[occ] == (scope, precision), "OCCURRENCE_SCOPE_CONFLICT")
            prior = claims.get(payload["supersedes"])
            require(payload["supersedes"] is None or
                    prior is not None and prior["payload"]["occurrenceId"] == occ and
                    pin["revision"] >= prior["payload"]["planPin"]["revision"],
                    "CORRECTION_CHAIN_INVALID")
            occurrence_scope[occ] = scope, precision
            claims[payload["id"]] = record
        elif kind == "attest":
            claim = claims.get(payload["claimId"])
            require(claim is not None and payload["claimId"] not in attested,
                    "CLAIM_REFERENCE_INVALID")
            attestations[payload["id"]] = record
            attested.add(payload["claimId"])
        else:
            attestation = attestations.get(payload["attestationId"])
            require(attestation is not None and
                    payload["attestationId"] not in reviewed, "ATTESTATION_REFERENCE_INVALID")
            reviewed.add(payload["attestationId"])
        raw = dt.datetime.fromisoformat(record["recordedAt"].replace("Z", "+00:00"))
        now = OWNER.instant(record["recordedAt"])
        require(raw.utcoffset() == dt.timedelta(0) and
                (clock is None or now >= clock), "CLOCK_ORDER")
        receipt = record["receipt"]
        require(isinstance(receipt, dict) and
                set(receipt) == {"mode", "grantId", "grantRevision", "principal"} and
                receipt["mode"] == "bearer" and
                receipt["principal"] == "bearer:" + receipt["grantId"] and
                type(receipt["grantRevision"]) is int, "TECHNICAL_RECEIPT_INVALID")
        if kind == "attest":
            require(receipt["grantId"] != claims[payload["claimId"]]["receipt"]["grantId"],
                    "ACTOR_SEPARATION_REQUIRED")
        if kind == "verify":
            attestation = attestations[payload["attestationId"]]
            claim = claims[attestation["payload"]["claimId"]]
            require(receipt["grantId"] not in
                    (attestation["receipt"]["grantId"], claim["receipt"]["grantId"]),
                    "ACTOR_SEPARATION_REQUIRED")
        tx = record["transactionId"]
        require(isinstance(tx, str) and TX.fullmatch(tx) and tx not in txs and
                isinstance(record["requestSHA256"], str) and
                HISTORY.SHA.fullmatch(record["requestSHA256"]), "TRANSACTION_INVALID")
        txs[tx] = {"requestSHA256": record["requestSHA256"],
                   "revision": number, "recordDigest": record["digest"]}
        previous, clock = record["digest"], now
    require(store["transactions"] == txs, "TRANSACTION_INDEX_INVALID")
    return store


def read_receipt(root, plan_file, record):
    path = receipt_path(root, plan_file, record["revision"])
    if not path.exists():
        return None
    value = HISTORY.load_bytes(path.read_bytes())
    require(isinstance(value, dict) and
            set(value) == {"schemaVersion", "planFile", "revision",
                           "recordDigest", "availableBy"} and
            value["schemaVersion"] == 1 and value["planFile"] == plan_file and
            value["revision"] == record["revision"] and
            value["recordDigest"] == record["digest"], "AVAILABILITY_RECEIPT_INVALID")
    raw = dt.datetime.fromisoformat(value["availableBy"].replace("Z", "+00:00"))
    require(raw.utcoffset() == dt.timedelta(0) and
            OWNER.instant(value["availableBy"]) >= OWNER.instant(record["recordedAt"]),
            "AVAILABILITY_TIME_INVALID")
    return value


def failpoint(name):
    if os.environ.get("RDG_EVENT_TEST_CRASH") == name:
        os._exit(91)


def replay(root, journal):
    require(isinstance(journal, dict) and
            set(journal) == {"schemaVersion", "state", "planFile", "transactionId",
                             "beforeSHA256", "afterSHA256", "after"} and
            journal["schemaVersion"] == 1 and journal["state"] == "prepared" and
            isinstance(journal["planFile"], str) and OWNER.TARGET.fullmatch(journal["planFile"]),
            "JOURNAL_INVALID")
    plan_file = journal["planFile"]
    path = target_path(root, plan_file)
    store = validate_store(journal["after"], plan_file)
    record = store["records"][-1]
    require(record["transactionId"] == journal["transactionId"] and
            OWNER.digest(store) == journal["afterSHA256"] and
            OWNER.raw_hash(path) in (journal["beforeSHA256"], journal["afterSHA256"]),
            "RECOVERY_CONFLICT")
    if journal["beforeSHA256"] is None:
        require(store["revision"] == 1, "JOURNAL_CHAIN_INVALID")
    else:
        before = copy.deepcopy(store)
        before["revision"] -= 1
        before["records"].pop()
        before["transactions"].pop(record["transactionId"])
        require(OWNER.digest(before) == journal["beforeSHA256"], "JOURNAL_CHAIN_INVALID")
    existing = read_receipt(root, plan_file, record)
    prior = read_receipt(root, plan_file, store["records"][-2]) if len(store["records"]) > 1 else None
    require(len(store["records"]) == 1 or prior is not None,
            "PREVIOUS_AVAILABILITY_BOUND_NOT_AVAILABLE")
    if existing and prior:
        require(OWNER.instant(existing["availableBy"]) >= OWNER.instant(prior["availableBy"]),
                "AVAILABILITY_CLOCK_ORDER")
    if OWNER.raw_hash(path) != journal["afterSHA256"]:
        OWNER.atomic(path, store)
    failpoint("after-store-write")
    if existing is None:
        now = dt.datetime.now(dt.timezone.utc)
        require(now >= OWNER.instant(record["recordedAt"]) and
                (prior is None or now >= OWNER.instant(prior["availableBy"])),
                "AVAILABILITY_CLOCK_ORDER")
        OWNER.atomic(receipt_path(root, plan_file, record["revision"]), {
            "schemaVersion": 1, "planFile": plan_file, "revision": record["revision"],
            "recordDigest": record["digest"], "availableBy": now.isoformat()})
    failpoint("after-availability-write")
    journal_path(root).unlink()
    OWNER.sync_dir(root)


def recover(root):
    root = OWNER.root_path(root)
    with OWNER.root_lock(root, True):
        path = journal_path(root)
        if not path.exists():
            return {"recovered": False, "idempotent": True}
        journal = HISTORY.load_bytes(path.read_bytes())
        replay(root, journal)
        return {"recovered": True, "transactionId": journal["transactionId"],
                "policy": "finish-durably-prepared"}


def verify_claim_pin(root, payload):
    pin = payload["planPin"]
    snap = OWNER.read_snapshot(root, pin["file"], pin["revision"])
    plan, provenance = snap["plan"], snap["provenance"]
    require(plan["identitySpace"] == pin["identitySpace"] and plan["id"] == pin["planId"] and
            provenance["snapshotSHA256"] == pin["snapshotSHA256"] and
            provenance["recordDigest"] == pin["recordDigest"], "PLAN_PIN_MISMATCH")
    matches = [s for s in plan["steps"] if s["id"] == payload["eventStepId"]]
    require(len(matches) == 1 and matches[0]["kind"] == "event" and
            matches[0]["state"] == "expected" and
            payload["outcome"] in matches[0]["outcomes"], "EVENT_OUTCOME_NOT_IN_PLAN")
    return snap


def apply(root, authority_store, token, request, before_prepare=None):
    root = OWNER.root_path(root)
    require(isinstance(request, dict) and
            set(request) == {"transactionId", "kind", "file", "expectedRevision", "payload"} and
            isinstance(request["transactionId"], str) and TX.fullmatch(request["transactionId"]) and
            request["kind"] in PERMISSIONS and
            type(request["expectedRevision"]) is int and
            request["expectedRevision"] >= 0, "REQUEST_SCHEMA")
    plan_file, kind = request["file"], request["kind"]
    target_path(root, plan_file)
    payload = copy.deepcopy(validate_payload(kind, request["payload"], plan_file))
    auth_path = Path(authority_store).resolve()
    require(not auth_path.is_relative_to(root), "AUTH_STORE_MUST_BE_OUTSIDE_PLAN_ROOT")
    authority = OWNER.AUTH.Authority(auth_path)
    permissions = PERMISSIONS[kind]
    authority.authorize_plan(token, permissions, plan_file)
    if kind == "claim":
        verify_claim_pin(root, payload)
    request_hash = OWNER.digest(request)
    with OWNER.root_lock(root, True):
        require(not journal_path(root).exists() and
                not OWNER.safe(root, OWNER.JOURNAL, True).exists(), "RECOVERY_REQUIRED")
        path = target_path(root, plan_file)
        before_hash = OWNER.raw_hash(path)
        old = validate_store(HISTORY.load_bytes(path.read_bytes()), plan_file) if path.exists() else None
        if old:
            require(read_receipt(root, plan_file, old["records"][-1]) is not None,
                    "PREVIOUS_AVAILABILITY_BOUND_NOT_AVAILABLE")
        tx = request["transactionId"]
        if old and tx in old["transactions"]:
            item = old["transactions"][tx]
            require(item["requestSHA256"] == request_hash, "TRANSACTION_REPLAY_CONFLICT")
            authority.authorize_plan(token, permissions, plan_file)
            return {"idempotent": True, **item}
        expected = old["revision"] if old else 0
        require(request["expectedRevision"] == expected, "CAS_MISMATCH")
        if kind == "claim":
            pin = payload["planPin"]
            plan_store = OWNER.validate_store(HISTORY.load_bytes(
                OWNER.safe(root, plan_file).read_bytes()), plan_file)
            require(pin["revision"] <= plan_store["revision"] and
                    OWNER.digest(plan_store["versions"][pin["revision"]-1]["plan"]) ==
                    pin["snapshotSHA256"] and
                    plan_store["versions"][pin["revision"]-1]["digest"] ==
                    pin["recordDigest"], "PLAN_PIN_CHANGED")
        if before_prepare:
            before_prepare()
        with authority.checked_plan_transaction(token, permissions, plan_file) as verified:
            recorded = dt.datetime.now(dt.timezone.utc)
            require(not old or recorded >= OWNER.instant(old["records"][-1]["recordedAt"]),
                    "CLOCK_ORDER")
            record = {"revision": expected + 1, "kind": kind, "payload": payload,
                      "recordedAt": recorded.isoformat(),
                      "previousDigest": old["records"][-1]["digest"] if old else None,
                      "transactionId": tx, "requestSHA256": request_hash,
                      "receipt": {"mode": "bearer", **verified,
                                  "principal": "bearer:" + verified["grantId"]}}
            record["digest"] = OWNER.digest(record)
            store = copy.deepcopy(old) if old else {"schemaVersion": 1,
                    "kind": "candidateEventHistory", "planFile": plan_file,
                    "revision": 0, "records": [], "transactions": {}}
            store["revision"] += 1
            store["records"].append(record)
            store["transactions"][tx] = {"requestSHA256": request_hash,
                    "revision": record["revision"], "recordDigest": record["digest"]}
            validate_store(store, plan_file)
            require(OWNER.raw_hash(path) == before_hash, "SOURCE_CHANGED_DURING_PREPARE")
            journal = {"schemaVersion": 1, "state": "prepared", "planFile": plan_file,
                       "transactionId": tx, "beforeSHA256": before_hash,
                       "afterSHA256": OWNER.digest(store), "after": store}
            OWNER.atomic(journal_path(root), journal)
            failpoint("prepared")
            replay(root, journal)
            return {"idempotent": False, **store["transactions"][tx],
                    "technicalReceipt": record["receipt"]}


def read(root, authority_store, token, plan_file, occurrence_id, known_at=None,
         before_return=None):
    root = OWNER.root_path(root)
    target_path(root, plan_file)
    require(isinstance(occurrence_id, str) and ID.fullmatch(occurrence_id),
            "OCCURRENCE_ID_INVALID")
    cutoff = MODEL.known(known_at) if known_at is not None else None
    authority = OWNER.AUTH.Authority(authority_store)
    authority.authorize_plan(token, ["plan.read"], plan_file)
    with OWNER.root_lock(root, False):
        require(not journal_path(root).exists() and
                not OWNER.safe(root, OWNER.JOURNAL, True).exists(), "RECOVERY_REQUIRED")
        path = target_path(root, plan_file)
        require(path.is_file(), "HISTORY_NOT_FOUND")
        store = validate_store(HISTORY.load_bytes(path.read_bytes()), plan_file)
        receipts = [read_receipt(root, plan_file, r) for r in store["records"]]
        require(all(x is not None for x in receipts), "AVAILABILITY_BOUND_NOT_AVAILABLE")
        present = [(r, x) for r, x in zip(store["records"], receipts)
                   if cutoff is None or OWNER.instant(x["availableBy"]) <= cutoff]
    available = {r["revision"]: receipt["availableBy"] for r, receipt in present}
    claims = [r for r, _ in present if r["kind"] == "claim" and
              r["payload"]["occurrenceId"] == occurrence_id]
    require(claims, "NO_KNOWN_CLAIM")
    claim_ids = {r["payload"]["id"] for r in claims}
    attestations = [r for r, _ in present if r["kind"] == "attest" and
                    r["payload"]["claimId"] in claim_ids]
    attestation_ids = {r["payload"]["id"] for r in attestations}
    reviews = [r for r, _ in present if r["kind"] == "verify" and
               r["payload"]["attestationId"] in attestation_ids]
    for record in claims:
        verify_claim_pin(root, record["payload"])
        if cutoff is not None:
            bound, _ = MODEL.availability(root, record["payload"]["planPin"])
            require(bound is not None and OWNER.instant(bound) <= cutoff,
                    "PLAN_NOT_PROVEN_KNOWN")
    superseded = {r["payload"]["supersedes"] for r in claims
                  if r["payload"]["supersedes"] is not None}
    leaves = [r["payload"]["id"] for r in claims
              if r["payload"]["id"] not in superseded]
    if before_return:
        before_return()
    authority.authorize_plan(token, ["plan.read"], plan_file)
    return {"status": "technical-event-history", "planFile": plan_file,
            "occurrenceId": occurrence_id, "knownAt": known_at,
            "claims": [{"payload": copy.deepcopy(r["payload"]),
                        "recordDigest": r["digest"], "recordedAt": r["recordedAt"],
                        "availableBy": available[r["revision"]]} for r in claims],
            "attestations": [{"payload": copy.deepcopy(r["payload"]),
                              "recordDigest": r["digest"],
                              "availableBy": available[r["revision"]]}
                             for r in attestations],
            "reviews": [{"payload": copy.deepcopy(r["payload"]),
                         "recordDigest": r["digest"],
                         "availableBy": available[r["revision"]]} for r in reviews],
            "unresolvedClaimIds": leaves,
            "claimConflict": len(leaves) != 1,
            "readOnly": True,
            "provenance": {"exactPlanSnapshotsResolved": True,
                           "stagedRecordsDurable": True,
                           "distinctBearerGrantsEnforced": True,
                           "humanIdentityVerified": False,
                           "evidenceContentsVerified": False,
                           "factualEventVerified": False,
                           "factualBranchResolved": False,
                           "actionSelected": False,
                           "completeApplicableContextVerified": False,
                           "productionAccepted": False}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("apply", "read", "recover"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--store", default=os.environ.get("RDG_AUTH_STORE"))
    parser.add_argument("--request", type=Path)
    parser.add_argument("--file")
    parser.add_argument("--occurrence-id")
    parser.add_argument("--known-at")
    args = parser.parse_args()
    token = os.environ.get("RDG_AUTH_TOKEN")
    if args.command == "recover":
        result = recover(args.root)
    elif args.command == "apply":
        require(args.store and args.request, "ARGUMENTS_REQUIRED")
        result = apply(args.root, args.store, token,
                       HISTORY.load_bytes(args.request.read_bytes()))
    else:
        require(args.store and args.file and args.occurrence_id, "ARGUMENTS_REQUIRED")
        result = read(args.root, args.store, token, args.file,
                      args.occurrence_id, args.known_at)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
