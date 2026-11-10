#!/usr/bin/env python3
"""Candidate applicability owner on explicit synthetic roots.

Stores unverified assertions and exact pins, never a factual event or accepted
baseline. A prepared journal is durable acceptance; availability is witnessed
only after the store write. This is not an OS security boundary.
"""
import argparse
import copy
import datetime as dt
import hashlib
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
MODEL = SourceFileLoader("applicability_rule", str(HERE / "rdg-two-time-scenario.py")).load_module()
HISTORY = MODEL.HISTORY
OWNER = MODEL.OWNER
ID = MODEL.ID
JOURNAL = "_rdg-applicability-journal.json"
NAME = ".rdg-applicability.json"
TX = re.compile(r"[A-Za-z0-9_-]{1,120}\Z")


def require(ok, code):
    if not ok:
        raise ValueError("APPLICABILITY_OWNER_" + code)


def target_path(root, plan_file):
    OWNER.safe(root, plan_file)
    path = OWNER.safe(root, plan_file).with_name(NAME)
    require(not path.is_symlink() and path.resolve().is_relative_to(root), "PATH_INVALID")
    return path


def journal_path(root):
    path = root / JOURNAL
    require(not path.is_symlink() and path.resolve().is_relative_to(root), "JOURNAL_PATH_INVALID")
    return path


def receipt_path(root, plan_file, revision):
    require(type(revision) is int and revision >= 1, "REVISION_INVALID")
    path = OWNER.safe(root, plan_file).with_name(f".rdg-applicability-available-r{revision}.json")
    require(not path.is_symlink() and path.resolve().is_relative_to(root), "RECEIPT_PATH_INVALID")
    return path


def validate_assertion(assertion):
    require(isinstance(assertion, dict) and
            set(assertion) == {"id", "effectiveAt", "supersedes", "source", "eventClaim"} and
            isinstance(assertion["id"], str) and ID.fullmatch(assertion["id"]) and
            (assertion["supersedes"] is None or
             isinstance(assertion["supersedes"], str) and ID.fullmatch(assertion["supersedes"])),
            "ASSERTION_SCHEMA")
    MODEL.effective(assertion["effectiveAt"])
    source = assertion["source"]
    HISTORY.validate_query(source)
    require("knownAt" not in source and
            isinstance(source["scenario"]["branchId"], str) and
            isinstance(source["scenario"]["outcome"], str), "EXACT_SOURCE_REQUIRED")
    claim = assertion["eventClaim"]
    if claim is not None:
        require(isinstance(claim, dict) and
                set(claim) == {"eventStepId", "outcome", "verification"} and
                isinstance(claim["eventStepId"], str) and
                claim["outcome"] == source["scenario"]["outcome"] and
                claim["verification"] == "unverified", "EVENT_CLAIM_INVALID")
    return assertion


def validate_store(store, plan_file):
    require(isinstance(store, dict) and set(store) == {"schemaVersion", "kind", "planFile",
            "revision", "records", "transactions"} and store["schemaVersion"] == 1 and
            store["kind"] == "candidateApplicabilityOwner" and store["planFile"] == plan_file and
            type(store["revision"]) is int and store["revision"] >= 1 and
            isinstance(store["records"], list) and len(store["records"]) == store["revision"] and
            isinstance(store["transactions"], dict), "STORE_SCHEMA")
    previous, clock, txs, ids, plan_key, branch, precision = None, None, {}, {}, None, None, None
    for number, record in enumerate(store["records"], 1):
        require(isinstance(record, dict) and
                set(record) == {"revision", "assertion", "recordedAt", "previousDigest",
                                "digest", "transactionId", "requestSHA256", "receipt"} and
                type(record["revision"]) is int and record["revision"] == number and
                record["previousDigest"] == previous and
                record["digest"] == OWNER.digest({k:v for k,v in record.items() if k != "digest"}),
                "RECORD_HASH")
        assertion = validate_assertion(record["assertion"])
        source = assertion["source"]
        pin = source["plan"]
        key = pin["file"], pin["identitySpace"], pin["planId"]
        current_precision, current_effective = MODEL.effective(assertion["effectiveAt"])
        require(pin["file"] == plan_file and
                (plan_key is None or key == plan_key) and
                (branch is None or source["scenario"]["branchId"] == branch) and
                (precision is None or current_precision == precision) and
                assertion["id"] not in ids and
                all(pin["revision"] != r["assertion"]["source"]["plan"]["revision"]
                    for r in store["records"][:number-1]), "SCOPE_OR_REVISION_CONFLICT")
        prior = ids.get(assertion["supersedes"])
        require(assertion["supersedes"] is None or
                prior is not None and
                prior["assertion"]["source"]["plan"]["revision"] < pin["revision"] and
                MODEL.effective(prior["assertion"]["effectiveAt"])[1] <= current_effective and
                (prior["assertion"]["eventClaim"] is None) == (assertion["eventClaim"] is None) and
                (assertion["eventClaim"] is None or
                 prior["assertion"]["eventClaim"]["eventStepId"] == assertion["eventClaim"]["eventStepId"]),
                "CORRECTION_CHAIN_INVALID")
        now = OWNER.instant(record["recordedAt"])
        require(clock is None or now >= clock, "CLOCK_ORDER")
        receipt = record["receipt"]
        require(isinstance(receipt, dict) and
                set(receipt) == {"mode", "grantId", "grantRevision", "principal"} and
                receipt["mode"] == "bearer" and
                receipt["principal"] == "bearer:" + receipt["grantId"] and
                type(receipt["grantRevision"]) is int, "TECHNICAL_RECEIPT_INVALID")
        tx = record["transactionId"]
        require(isinstance(tx, str) and TX.fullmatch(tx) and tx not in txs and
                isinstance(record["requestSHA256"], str), "TRANSACTION_INVALID")
        txs[tx] = {"requestSHA256": record["requestSHA256"],
                   "revision": number, "recordDigest": record["digest"]}
        previous, clock, plan_key, branch, precision = record["digest"], now, key, source["scenario"]["branchId"], current_precision
        ids[assertion["id"]] = record
    require(store["transactions"] == txs, "TRANSACTION_INDEX_INVALID")
    return store


def read_receipt(root, plan_file, record):
    path = receipt_path(root, plan_file, record["revision"])
    if not path.exists():
        return None
    receipt = HISTORY.load_bytes(path.read_bytes())
    require(isinstance(receipt, dict) and
            set(receipt) == {"schemaVersion", "planFile", "revision", "recordDigest", "availableBy"} and
            receipt["schemaVersion"] == 1 and receipt["planFile"] == plan_file and
            receipt["revision"] == record["revision"] and
            receipt["recordDigest"] == record["digest"], "AVAILABILITY_RECEIPT_INVALID")
    raw = dt.datetime.fromisoformat(receipt["availableBy"].replace("Z", "+00:00"))
    require(raw.utcoffset() == dt.timedelta(0) and
            OWNER.instant(receipt["availableBy"]) >= OWNER.instant(record["recordedAt"]),
            "AVAILABILITY_TIME_INVALID")
    return receipt


def failpoint(name):
    if os.environ.get("RDG_APPLICABILITY_TEST_CRASH") == name:
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
        require(store["revision"] > 1 and
                OWNER.digest({**store, "revision": store["revision"] - 1,
                    "records": store["records"][:-1],
                    "transactions": {k:v for k,v in store["transactions"].items()
                        if k != record["transactionId"]}}) == journal["beforeSHA256"],
                "JOURNAL_CHAIN_INVALID")
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


def apply(root, graphs_root, authority_store, token, request, before_prepare=None):
    root = OWNER.root_path(root)
    require(isinstance(request, dict) and
            set(request) == {"transactionId", "file", "expectedRevision", "assertion"} and
            isinstance(request["transactionId"], str) and TX.fullmatch(request["transactionId"]) and
            type(request["expectedRevision"]) is int and request["expectedRevision"] >= 0,
            "REQUEST_SCHEMA")
    plan_file, assertion = request["file"], copy.deepcopy(request["assertion"])
    target_path(root, plan_file)
    validate_assertion(assertion)
    require(assertion["source"]["plan"]["file"] == plan_file, "PLAN_SCOPE_MISMATCH")
    auth_path = Path(authority_store).resolve()
    require(not auth_path.is_relative_to(root), "AUTH_STORE_MUST_BE_OUTSIDE_PLAN_ROOT")
    authority = OWNER.AUTH.Authority(auth_path)
    authority.authorize_plan(token, ["plan.applicability.write"], plan_file)
    targets = sorted({p["graphFile"] for p in assertion["source"]["graphs"]})
    authority.authorize_snapshot_read(token, plan_file, targets)
    exact = HISTORY.resolve(root, graphs_root, auth_path, token, assertion["source"])
    branch = next(b for b in exact["plan"]["branches"]
                  if b["id"] == assertion["source"]["scenario"]["branchId"])
    if assertion["eventClaim"] is not None:
        require(assertion["eventClaim"]["eventStepId"] == branch["eventStepId"],
                "EVENT_STEP_MISMATCH")
    request_hash = OWNER.digest(request)
    with OWNER.root_lock(root, True):
        require(not journal_path(root).exists() and
                not OWNER.safe(root, OWNER.JOURNAL, True).exists(), "RECOVERY_REQUIRED")
        path = target_path(root, plan_file)
        old_hash = OWNER.raw_hash(path)
        old = validate_store(HISTORY.load_bytes(path.read_bytes()), plan_file) if path.exists() else None
        if old:
            require(read_receipt(root, plan_file, old["records"][-1]) is not None,
                    "PREVIOUS_AVAILABILITY_BOUND_NOT_AVAILABLE")
        tx = request["transactionId"]
        if old and tx in old["transactions"]:
            item = old["transactions"][tx]
            require(item["requestSHA256"] == request_hash, "TRANSACTION_REPLAY_CONFLICT")
            authority.authorize_plan(token, ["plan.applicability.write"], plan_file)
            authority.authorize_snapshot_read(token, plan_file, targets)
            return {"idempotent": True, **item}
        expected = old["revision"] if old else 0
        require(request["expectedRevision"] == expected, "CAS_MISMATCH")
        if before_prepare:
            before_prepare()
        with authority.checked_plan_transaction(token, ["plan.applicability.write"], plan_file) as verified:
            authority.authorize_snapshot_read(token, plan_file, targets)
            recorded = dt.datetime.now(dt.timezone.utc)
            require(not old or recorded >= OWNER.instant(old["records"][-1]["recordedAt"]),
                    "CLOCK_ORDER")
            record = {"revision": expected + 1, "assertion": assertion,
                      "recordedAt": recorded.isoformat(),
                      "previousDigest": old["records"][-1]["digest"] if old else None,
                      "transactionId": tx, "requestSHA256": request_hash,
                      "receipt": {"mode": "bearer", **verified,
                                  "principal": "bearer:" + verified["grantId"]}}
            record["digest"] = OWNER.digest(record)
            store = copy.deepcopy(old) if old else {"schemaVersion": 1,
                    "kind": "candidateApplicabilityOwner", "planFile": plan_file,
                    "revision": 0, "records": [], "transactions": {}}
            store["revision"] += 1
            store["records"].append(record)
            store["transactions"][tx] = {"requestSHA256": request_hash,
                    "revision": record["revision"], "recordDigest": record["digest"]}
            validate_store(store, plan_file)
            require(OWNER.raw_hash(path) == old_hash, "SOURCE_CHANGED_DURING_PREPARE")
            journal = {"schemaVersion": 1, "state": "prepared", "planFile": plan_file,
                       "transactionId": tx, "beforeSHA256": old_hash,
                       "afterSHA256": OWNER.digest(store), "after": store}
            OWNER.atomic(journal_path(root), journal)
            failpoint("prepared")
            replay(root, journal)
            return {"idempotent": False, **store["transactions"][tx],
                    "technicalReceipt": record["receipt"]}


def resolve(root, graphs_root, authority_store, token, plan_file, known_at, effective_at):
    root = OWNER.root_path(root)
    cutoff = MODEL.known(known_at)
    MODEL.effective(effective_at)
    authority = OWNER.AUTH.Authority(authority_store)
    authority.authorize_plan(token, ["plan.read"], plan_file)
    with OWNER.root_lock(root, False):
        require(not journal_path(root).exists() and
                not OWNER.safe(root, OWNER.JOURNAL, True).exists(), "RECOVERY_REQUIRED")
        path = target_path(root, plan_file)
        require(path.is_file(), "HISTORY_NOT_FOUND")
        store = validate_store(HISTORY.load_bytes(path.read_bytes()), plan_file)
        present = []
        for record in store["records"]:
            receipt = read_receipt(root, plan_file, record)
            require(receipt is not None, "AVAILABILITY_BOUND_NOT_AVAILABLE")
            if OWNER.instant(receipt["availableBy"]) <= cutoff:
                present.append((record, receipt))
    require(present, "NO_KNOWN_APPLICABILITY_RECORD")
    assertions = [copy.deepcopy(r["assertion"]) for r, _ in present]
    candidate = MODEL.resolve(root, graphs_root, authority_store, token,
                              {"schemaVersion": 1, "mode": "candidate-two-time-scenario",
                               "knownAt": known_at, "effectiveAt": effective_at,
                               "assertions": assertions})
    authority.authorize_snapshot_read(token, plan_file,
        sorted({pin["graphFile"] for assertion in assertions
                for pin in assertion["source"]["graphs"]}))
    candidate["ownerHistory"] = {"kind": "candidateApplicabilityOwner",
            "planFile": plan_file, "revision": store["revision"],
            "availableRecords": [{"id": r["assertion"]["id"],
                                  "recordDigest": r["digest"],
                                  "recordedAt": r["recordedAt"],
                                  "availableBy": receipt["availableBy"]}
                                 for r, receipt in present],
            "assertionsDurablyRecorded": True,
            "completeApplicableContextVerified": False}
    candidate["provenance"]["applicabilityAttested"] = False
    candidate["provenance"]["twoTimeAsOfResolved"] = False
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("apply", "read", "recover"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--graphs-root", type=Path)
    parser.add_argument("--store", default=os.environ.get("RDG_AUTH_STORE"))
    parser.add_argument("--request", type=Path)
    parser.add_argument("--file")
    parser.add_argument("--known-at")
    parser.add_argument("--effective-at")
    args = parser.parse_args()
    token = os.environ.get("RDG_AUTH_TOKEN")
    if args.command == "recover":
        result = recover(args.root)
    elif args.command == "apply":
        require(args.graphs_root and args.store and args.request, "ARGUMENTS_REQUIRED")
        result = apply(args.root, args.graphs_root, args.store, token,
                       HISTORY.load_bytes(args.request.read_bytes()))
    else:
        require(args.graphs_root and args.store and args.file and args.known_at and
                args.effective_at, "ARGUMENTS_REQUIRED")
        result = resolve(args.root, args.graphs_root, args.store, token,
                         args.file, args.known_at, args.effective_at)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
