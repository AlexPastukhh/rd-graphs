#!/usr/bin/env python3
"""Opt-in technical accepted-future baseline, separate from candidate Plan.

This local owner records a named exact Plan revision under plan.accept. A bearer
grant is not independent human approval; no event or RDG Action is selected.
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
OWNER = SourceFileLoader("baseline_plan_owner", str(HERE / "rdg-temporal-plan-owner.py")).load_module()
HISTORY = SourceFileLoader("baseline_exact_history", str(HERE / "rdg-exact-history.py")).load_module()
MODEL = SourceFileLoader("baseline_two_time", str(HERE / "rdg-two-time-scenario.py")).load_module()
NAME = ".rdg-future-baseline.json"
JOURNAL = "_rdg-future-baseline-journal.json"
TX = re.compile(r"[A-Za-z0-9_-]{1,120}\Z")


def require(ok, code):
    if not ok:
        raise ValueError("FUTURE_BASELINE_" + code)


def target_path(root, plan_file):
    path = OWNER.safe(root, plan_file).with_name(NAME)
    require(not path.is_symlink() and path.resolve().is_relative_to(root), "PATH_INVALID")
    return path


def receipt_path(root, plan_file, revision):
    require(type(revision) is int and revision >= 1, "REVISION_INVALID")
    path = OWNER.safe(root, plan_file).with_name(f".rdg-future-baseline-available-r{revision}.json")
    require(not path.is_symlink() and path.resolve().is_relative_to(root), "RECEIPT_PATH_INVALID")
    return path


def journal_path(root):
    path = root / JOURNAL
    require(not path.is_symlink() and path.resolve().is_relative_to(root), "JOURNAL_PATH_INVALID")
    return path


def validate_pin(pin, plan_file):
    require(isinstance(pin, dict) and
            set(pin) == {"file", "identitySpace", "planId", "revision",
                         "snapshotSHA256", "recordDigest"} and
            pin["file"] == plan_file and
            OWNER.PLAN.named(pin["identitySpace"]) and
            OWNER.PLAN.ident(pin["planId"]) and
            type(pin["revision"]) is int and pin["revision"] >= 1 and
            all(isinstance(pin[k], str) and HISTORY.SHA.fullmatch(pin[k])
                for k in ("snapshotSHA256", "recordDigest")), "PLAN_PIN_INVALID")
    return pin


def validate_store(store, plan_file):
    require(isinstance(store, dict) and
            set(store) == {"schemaVersion", "kind", "planFile", "stateRevision",
                           "records", "transactions"} and
            store["schemaVersion"] == 1 and
            store["kind"] == "acceptedFutureBaselineOwner" and
            store["planFile"] == plan_file and
            type(store["stateRevision"]) is int and store["stateRevision"] >= 1 and
            isinstance(store["records"], list) and
            len(store["records"]) == store["stateRevision"] and
            isinstance(store["transactions"], dict), "STORE_SCHEMA")
    previous, previous_record, clock, txs, identity = None, None, None, {}, None
    for number, record in enumerate(store["records"], 1):
        require(isinstance(record, dict) and
                set(record) == {"stateRevision", "op", "planPin", "basis",
                                "recordedAt", "previousDigest", "digest",
                                "transactionId", "requestSHA256", "receipt"} and
                type(record["stateRevision"]) is int and record["stateRevision"] == number and
                record["previousDigest"] == previous and
                record["digest"] == OWNER.digest({k:v for k,v in record.items() if k != "digest"}),
                "RECORD_HASH")
        pin = validate_pin(record["planPin"], plan_file)
        key = pin["identitySpace"], pin["planId"]
        require(identity is None or key == identity, "IDENTITY_CHANGED")
        require(isinstance(record["basis"], str) and
                1 <= len(record["basis"].strip()) <= 1000, "BASIS_REQUIRED")
        op = record["op"]
        if number == 1:
            require(op == "accept", "FIRST_ACCEPT_REQUIRED")
        else:
            require(previous_record["op"] in ("accept", "replace") and
                    op in ("replace", "withdraw"), "LIFECYCLE_INVALID")
            prior_pin = previous_record["planPin"]
            require((pin["revision"] > prior_pin["revision"] if op == "replace"
                     else pin == prior_pin), "PLAN_REVISION_ORDER")
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
        tx = record["transactionId"]
        require(isinstance(tx, str) and TX.fullmatch(tx) and tx not in txs and
                isinstance(record["requestSHA256"], str) and
                HISTORY.SHA.fullmatch(record["requestSHA256"]), "TRANSACTION_INVALID")
        txs[tx] = {"requestSHA256": record["requestSHA256"],
                   "stateRevision": number, "recordDigest": record["digest"]}
        previous, previous_record, clock, identity = record["digest"], record, now, key
    require(store["transactions"] == txs, "TRANSACTION_INDEX_INVALID")
    return store


def read_receipt(root, plan_file, record):
    path = receipt_path(root, plan_file, record["stateRevision"])
    if not path.exists():
        return None
    value = HISTORY.load_bytes(path.read_bytes())
    require(isinstance(value, dict) and
            set(value) == {"schemaVersion", "planFile", "stateRevision",
                           "recordDigest", "availableBy"} and
            value["schemaVersion"] == 1 and value["planFile"] == plan_file and
            value["stateRevision"] == record["stateRevision"] and
            value["recordDigest"] == record["digest"], "AVAILABILITY_RECEIPT_INVALID")
    raw = dt.datetime.fromisoformat(value["availableBy"].replace("Z", "+00:00"))
    require(raw.utcoffset() == dt.timedelta(0) and
            OWNER.instant(value["availableBy"]) >= OWNER.instant(record["recordedAt"]),
            "AVAILABILITY_TIME_INVALID")
    return value


def failpoint(name):
    if os.environ.get("RDG_BASELINE_TEST_CRASH") == name:
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
        require(store["stateRevision"] == 1, "JOURNAL_CHAIN_INVALID")
    else:
        before = copy.deepcopy(store)
        before["stateRevision"] -= 1
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
        OWNER.atomic(receipt_path(root, plan_file, record["stateRevision"]), {
            "schemaVersion": 1, "planFile": plan_file,
            "stateRevision": record["stateRevision"], "recordDigest": record["digest"],
            "availableBy": now.isoformat()})
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


def verify_plan_pin(root, pin):
    snapshot = OWNER.read_snapshot(root, pin["file"], pin["revision"])
    provenance = snapshot["provenance"]
    require(snapshot["plan"]["identitySpace"] == pin["identitySpace"] and
            snapshot["plan"]["id"] == pin["planId"] and
            provenance["snapshotSHA256"] == pin["snapshotSHA256"] and
            provenance["recordDigest"] == pin["recordDigest"], "PLAN_PIN_MISMATCH")
    return snapshot


def apply(root, authority_store, token, request, before_prepare=None):
    root = OWNER.root_path(root)
    require(isinstance(request, dict) and
            set(request) == {"transactionId", "op", "file", "expectedStateRevision",
                             "planPin", "basis"} and
            isinstance(request["transactionId"], str) and TX.fullmatch(request["transactionId"]) and
            request["op"] in ("accept", "replace", "withdraw") and
            type(request["expectedStateRevision"]) is int and
            request["expectedStateRevision"] >= 0, "REQUEST_SCHEMA")
    plan_file = request["file"]
    target_path(root, plan_file)
    pin = copy.deepcopy(validate_pin(request["planPin"], plan_file))
    require(isinstance(request["basis"], str) and
            1 <= len(request["basis"].strip()) <= 1000, "BASIS_REQUIRED")
    auth_path = Path(authority_store).resolve()
    require(not auth_path.is_relative_to(root), "AUTH_STORE_MUST_BE_OUTSIDE_PLAN_ROOT")
    authority = OWNER.AUTH.Authority(auth_path)
    permissions = ["plan.accept", "plan.read"]
    authority.authorize_plan(token, permissions, plan_file)
    verify_plan_pin(root, pin)
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
        expected = old["stateRevision"] if old else 0
        require(request["expectedStateRevision"] == expected, "CAS_MISMATCH")
        # The Plan owner is serialized by the same root lock. Its current
        # store may have newer candidate versions; the pinned old one is immutable.
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
            record = {"stateRevision": expected + 1, "op": request["op"],
                      "planPin": pin, "basis": request["basis"],
                      "recordedAt": recorded.isoformat(),
                      "previousDigest": old["records"][-1]["digest"] if old else None,
                      "transactionId": tx, "requestSHA256": request_hash,
                      "receipt": {"mode": "bearer", **verified,
                                  "principal": "bearer:" + verified["grantId"]}}
            record["digest"] = OWNER.digest(record)
            store = copy.deepcopy(old) if old else {"schemaVersion": 1,
                    "kind": "acceptedFutureBaselineOwner", "planFile": plan_file,
                    "stateRevision": 0, "records": [], "transactions": {}}
            store["stateRevision"] += 1
            store["records"].append(record)
            store["transactions"][tx] = {"requestSHA256": request_hash,
                    "stateRevision": record["stateRevision"], "recordDigest": record["digest"]}
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


def read(root, authority_store, token, plan_file, state_revision=None, known_at=None, before_return=None):
    root = OWNER.root_path(root)
    target_path(root, plan_file)
    cutoff = MODEL.known(known_at) if known_at is not None else None
    authority = OWNER.AUTH.Authority(authority_store)
    authority.authorize_plan(token, ["plan.read"], plan_file)
    with OWNER.root_lock(root, False):
        require(not journal_path(root).exists() and
                not OWNER.safe(root, OWNER.JOURNAL, True).exists(), "RECOVERY_REQUIRED")
        path = target_path(root, plan_file)
        require(path.is_file(), "BASELINE_NOT_FOUND")
        store = validate_store(HISTORY.load_bytes(path.read_bytes()), plan_file)
        receipts = [read_receipt(root, plan_file, r) for r in store["records"]]
        require(all(x is not None for x in receipts),
                "AVAILABILITY_BOUND_NOT_AVAILABLE")
        if state_revision is not None:
            require(type(state_revision) is int and
                    1 <= state_revision <= store["stateRevision"], "STATE_REVISION_NOT_FOUND")
            selected = store["records"][state_revision-1]
            receipt = receipts[state_revision-1]
            require(cutoff is None or OWNER.instant(receipt["availableBy"]) <= cutoff,
                    "BASELINE_NOT_PROVEN_KNOWN")
        else:
            eligible = [(r, x) for r, x in zip(store["records"], receipts)
                        if cutoff is None or OWNER.instant(x["availableBy"]) <= cutoff]
            require(eligible, "NO_KNOWN_BASELINE")
            selected, receipt = eligible[-1]
    pin = selected["planPin"]
    snapshot = verify_plan_pin(root, pin)
    if cutoff is not None:
        bound, _ = MODEL.availability(root, pin)
        require(bound is not None and OWNER.instant(bound) <= cutoff,
                "PLAN_NOT_PROVEN_KNOWN")
    if before_return:
        before_return()
    authority.authorize_plan(token, ["plan.read"], plan_file)
    return {"status": "technical-future-baseline", "lifecycle": "accepted-future",
            "state": "withdrawn" if selected["op"] == "withdraw" else "accepted",
            "stateRevision": selected["stateRevision"],
            "recordDigest": selected["digest"], "recordedAt": selected["recordedAt"],
            "availableBy": receipt["availableBy"], "knownAt": known_at,
            "planPin": copy.deepcopy(pin), "plan": snapshot["plan"],
            "basis": selected["basis"], "readOnly": True,
            "provenance": {"exactPlanSnapshotResolved": True,
                           "technicalAcceptanceRecorded": True,
                           "humanAcceptanceVerified": False,
                           "actionSelected": False, "eventsAttested": False,
                           "completeApplicableContextVerified": False,
                           "productionAccepted": False}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("apply", "read", "recover"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--store", default=os.environ.get("RDG_AUTH_STORE"))
    parser.add_argument("--request", type=Path)
    parser.add_argument("--file")
    parser.add_argument("--state-revision", type=int)
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
        require(args.store and args.file, "ARGUMENTS_REQUIRED")
        result = read(args.root, args.store, token, args.file,
                      args.state_revision, args.known_at)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
