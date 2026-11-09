#!/usr/bin/env python3
"""Opt-in local candidate Plan owner: guarded writes, immutable versions, recovery.

Explicit root only. Not production storage, event attestation, Action selection,
accepted-future workflow, trusted human identity, or an OS security boundary.
"""
import argparse
from contextlib import contextmanager
import copy
import datetime as dt
import fcntl
import hashlib
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import re
import tempfile

HERE = Path(__file__).resolve().parent
PLAN = SourceFileLoader("owner_temporal_model", str(HERE / "rdg-temporal-plan.py")).load_module()
AUTH = SourceFileLoader("owner_bearer_authority", str(HERE / "rdg-authority.py")).load_module()
TARGET = re.compile(r"plans/(?:[a-z0-9][a-z0-9_-]*/)+plan\.json\Z")
INDEX = "_rdg-plan-index.json"
JOURNAL = "_rdg-plan-journal.json"
LOCK = "_rdg-plan.lock"


def require(ok, code):
    if not ok:
        raise ValueError("PLAN_OWNER_" + code)


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2,
                       allow_nan=False) + "\n").encode("utf8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def raw_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def root_path(root):
    root = Path(root).resolve(strict=True)
    require(root.is_dir(), "EXPLICIT_ROOT_REQUIRED")
    return root


def safe(root, relative, internal=False):
    require(isinstance(relative, str) and
            (relative in (INDEX, JOURNAL, LOCK) if internal else bool(TARGET.fullmatch(relative))),
            "PATH_INVALID")
    current = root
    for part in relative.split("/"):
        current = current / part
        require(not current.is_symlink(), "SYMLINK_DENIED")
    require(current.resolve().is_relative_to(root), "PATH_OUTSIDE_ROOT")
    return current


@contextmanager
def root_lock(root, exclusive):
    path = safe(root, LOCK, True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield


def sync_dir(path):
    fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".plan-write-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        sync_dir(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def identity(plan):
    return digest({"identitySpace": plan["identitySpace"], "planId": plan["id"]})


def availability_path(root, relative, revision):
    target = safe(root, relative)
    require(type(revision) is int and revision >= 1, "AVAILABILITY_REVISION")
    path = target.with_name(f".rdg-plan-available-r{revision}.json")
    require(not path.is_symlink() and path.resolve().is_relative_to(root),
            "AVAILABILITY_PATH_INVALID")
    return path


def availability_receipt(root, relative, record):
    path = availability_path(root, relative, record["revision"])
    if not path.exists():
        return None
    receipt = json.loads(path.read_text())
    require(isinstance(receipt, dict) and
            set(receipt) == {"schemaVersion", "sourcePath", "revision", "recordDigest", "availableBy"} and
            receipt["schemaVersion"] == 1 and receipt["sourcePath"] == relative and
            type(receipt["revision"]) is int and receipt["revision"] == record["revision"] and
            receipt["recordDigest"] == record["digest"], "AVAILABILITY_RECEIPT_INVALID")
    available = instant(receipt["availableBy"])
    raw = dt.datetime.fromisoformat(receipt["availableBy"].replace("Z", "+00:00"))
    require(raw.utcoffset() == dt.timedelta(0) and available >= instant(record["recordedAt"]),
            "AVAILABILITY_TIME_INVALID")
    return receipt


def instant(value):
    require(isinstance(value, str) and "T" in value, "RECORDED_AT_INVALID")
    result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None and result.utcoffset() is not None, "RECORDED_AT_TIMEZONE")
    return result.astimezone(dt.timezone.utc)


def validate_index(index):
    require(set(index) == {"schemaVersion", "bindings"} and index["schemaVersion"] == 1 and
            isinstance(index["bindings"], dict), "INDEX_INVALID")
    paths = set()
    for key, owner in index["bindings"].items():
        require(set(owner) == {"identitySpace", "planId", "sourcePath"} and
                isinstance(owner["identitySpace"], str) and PLAN.ident(owner["planId"]) and
                TARGET.fullmatch(owner["sourcePath"]) and owner["sourcePath"] not in paths and
                key == digest({"identitySpace": owner["identitySpace"], "planId": owner["planId"]}),
                "INDEX_BINDING_INVALID")
        paths.add(owner["sourcePath"])
    return index


def load_index(root):
    path = safe(root, INDEX, True)
    return validate_index(json.loads(path.read_text())) if path.exists() else {"schemaVersion": 1, "bindings": {}}


def validate_store(store, target):
    require(set(store) == {"schemaVersion", "kind", "owner", "revision", "versions", "transactions"} and
            store["schemaVersion"] == 1 and store["kind"] == "temporalPlanOwner", "STORE_SCHEMA")
    owner = store["owner"]
    require(set(owner) == {"identitySpace", "planId", "sourcePath"} and owner["sourcePath"] == target,
            "OWNER_PATH_MISMATCH")
    require(type(store["revision"]) is int and store["revision"] >= 1 and
            isinstance(store["versions"], list) and len(store["versions"]) == store["revision"], "HISTORY_INVALID")
    previous, clock, transactions = None, None, {}
    for number, record in enumerate(store["versions"], 1):
        require(set(record) == {"revision", "plan", "recordedAt", "previousDigest", "digest",
                               "transactionId", "operation", "requestSHA256", "receipt"}, "RECORD_SCHEMA")
        PLAN.validate(record["plan"])
        require(record["revision"] == number and record["plan"]["revision"] == number and
                record["plan"]["identitySpace"] == owner["identitySpace"] and
                record["plan"]["id"] == owner["planId"] and record["previousDigest"] == previous and
                record["digest"] == digest({k:v for k,v in record.items() if k != "digest"}), "HISTORY_HASH_OR_IDENTITY")
        current_clock = instant(record["recordedAt"])
        require(clock is None or current_clock >= clock, "HISTORY_CLOCK_ORDER")
        require(record["operation"] in (("create",) if number == 1 else ("edit", "branch")), "HISTORY_OPERATION")
        receipt = record["receipt"]
        require(set(receipt) == {"mode", "grantId", "grantRevision", "principal"} and receipt["mode"] == "bearer" and
                receipt["principal"] == "bearer:" + receipt["grantId"] and
                type(receipt["grantRevision"]) is int, "RECEIPT_INVALID")
        tx = record["transactionId"]
        require(isinstance(tx, str) and tx and tx not in transactions, "HISTORY_TRANSACTION")
        transactions[tx] = {"requestSHA256": record["requestSHA256"], "revision": number, "recordDigest": record["digest"]}
        previous, clock = record["digest"], current_clock
    require(store["transactions"] == transactions, "TRANSACTION_INDEX_INVALID")
    return store


def branch_signature(plan):
    return {
        "branches": sorted([{**b, "cases": sorted(
            [{**c, "stepIds": sorted(c["stepIds"])} for c in b["cases"]], key=lambda c:c["outcome"])}
            for b in plan.get("branches", [])], key=lambda b: b["id"]),
        "events": sorted([{k:(sorted(v) if k == "outcomes" else v) for k,v in s.items() if k != "title"} for s in plan["steps"] if s["kind"] == "event"], key=lambda s:s["id"]),
        "possible": sorted(s["id"] for s in plan["steps"] if s["state"] == "possible"),
    }


def failpoint(name):
    if os.environ.get("RDG_PLAN_TEST_CRASH") == name:
        os._exit(91)


def replay(root, journal):
    require(set(journal) == {"schemaVersion", "state", "target", "transactionId", "writes"} and
            journal["schemaVersion"] == 1 and journal["state"] == "prepared" and
            bool(TARGET.fullmatch(journal["target"])) and len(journal["writes"]) == 2,
            "JOURNAL_INVALID")
    require([w["path"] for w in journal["writes"]] == [journal["target"], INDEX], "JOURNAL_TARGETS")
    store = validate_store(journal["writes"][0]["after"], journal["target"])
    index = validate_index(journal["writes"][1]["after"])
    require(store["versions"][-1]["transactionId"] == journal["transactionId"] and
            index["bindings"].get(identity(store["versions"][-1]["plan"])) == store["owner"], "JOURNAL_OWNER")
    # Preflight every destination before any recovery write; unexpected bytes
    # require an operator decision instead of overwriting concurrent/raw edits.
    for entry in journal["writes"]:
        require(set(entry) == {"path", "beforeSHA256", "afterSHA256", "after"} and
                digest(entry["after"]) == entry["afterSHA256"], "JOURNAL_HASH")
        path = safe(root, entry["path"], entry["path"] == INDEX)
        require(raw_hash(path) in (entry["beforeSHA256"], entry["afterSHA256"]), "RECOVERY_CONFLICT")
    record = store["versions"][-1]
    existing_receipt = availability_receipt(root, journal["target"], record)
    prior_receipt = (availability_receipt(root, journal["target"], store["versions"][-2])
                     if len(store["versions"]) > 1 else None)
    if existing_receipt and prior_receipt:
        require(instant(existing_receipt["availableBy"]) >= instant(prior_receipt["availableBy"]),
                "AVAILABILITY_CLOCK_REGRESSION")
    for position, entry in enumerate(journal["writes"]):
        path = safe(root, entry["path"], entry["path"] == INDEX)
        if raw_hash(path) != entry["afterSHA256"]:
            atomic(path, entry["after"])
        if position == 0:
            failpoint("after-plan-write")
    if existing_receipt is None:
        # Plan store and owner binding have been written and fsynced. This
        # observation bounds their availability, even if recovery ran later.
        now = dt.datetime.now(dt.timezone.utc)
        require(now >= instant(record["recordedAt"]) and
                (prior_receipt is None or now >= instant(prior_receipt["availableBy"])),
                "AVAILABILITY_CLOCK_REGRESSION")
        atomic(availability_path(root, journal["target"], record["revision"]), {
            "schemaVersion": 1, "sourcePath": journal["target"],
            "revision": record["revision"], "recordDigest": record["digest"],
            "availableBy": now.isoformat()})
    failpoint("after-availability-write")
    safe(root, JOURNAL, True).unlink()
    sync_dir(root)


def recover(root):
    root = root_path(root)
    with root_lock(root, True):
        path = safe(root, JOURNAL, True)
        if not path.exists():
            return {"recovered": False, "idempotent": True}
        journal = json.loads(path.read_text())
        replay(root, journal)
        return {"recovered": True, "transactionId": journal["transactionId"], "policy": "finish-durably-prepared"}


def read_snapshot(root, path, revision=None):
    root = root_path(root)
    path = Path(path)
    relative = str(path.relative_to(root)) if path.is_absolute() else str(path)
    target = safe(root, relative)
    with root_lock(root, False):
        require(not safe(root, JOURNAL, True).exists(), "RECOVERY_REQUIRED")
        require(target.is_file(), "PLAN_NOT_FOUND")
        store = validate_store(json.loads(target.read_text()), relative)
        index = load_index(root)
        require(index["bindings"].get(identity(store["versions"][-1]["plan"])) == store["owner"], "OWNER_BINDING_MISMATCH")
        number = store["revision"] if revision is None else revision
        require(type(number) is int and 1 <= number <= store["revision"], "SNAPSHOT_NOT_FOUND")
        record = store["versions"][number-1]
        return {"plan": copy.deepcopy(record["plan"]), "provenance": {
            **store["owner"], "revision": number, "recordedAt": record["recordedAt"],
            "recordDigest": record["digest"], "snapshotSHA256": digest(record["plan"]),
            "exactPlanSnapshotResolved": True, "historicalRdgSnapshotResolved": False,
            "acceptanceVerified": False, "eventsAttested": False}}


def read_availability(root, path, revision, record_digest):
    """Return a durable availability witness, if this revision has one."""
    root = root_path(root)
    relative = str(Path(path).relative_to(root)) if Path(path).is_absolute() else str(path)
    target = safe(root, relative)
    with root_lock(root, False):
        require(not safe(root, JOURNAL, True).exists(), "RECOVERY_REQUIRED")
        require(target.is_file(), "PLAN_NOT_FOUND")
        store = validate_store(json.loads(target.read_text()), relative)
        require(load_index(root)["bindings"].get(identity(store["versions"][-1]["plan"])) ==
                store["owner"], "OWNER_BINDING_MISMATCH")
        require(type(revision) is int and 1 <= revision <= store["revision"], "SNAPSHOT_NOT_FOUND")
        record = store["versions"][revision-1]
        require(record["digest"] == record_digest, "AVAILABILITY_RECORD_MISMATCH")
        receipt = availability_receipt(root, relative, record)
        return copy.deepcopy(receipt)


def apply_request(root, authority_store, token, request, before_prepare=None):
    root = root_path(root)
    require(isinstance(request, dict) and set(request) == {"transactionId", "op", "file", "expectedRevision", "plan"}, "REQUEST_SCHEMA")
    op, relative, tx = request["op"], request["file"], request["transactionId"]
    require(op in ("create", "edit", "branch"), "CANDIDATE_OPERATIONS_ONLY")
    require(isinstance(tx, str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,120}", tx)), "TRANSACTION_ID")
    require(type(request["expectedRevision"]) is int and request["expectedRevision"] >= 0, "EXPECTED_REVISION")
    target = safe(root, relative)
    auth_path = Path(authority_store).resolve()
    require(not auth_path.is_relative_to(root), "AUTH_STORE_MUST_BE_OUTSIDE_PLAN_ROOT")
    authority = AUTH.Authority(auth_path)
    permissions = ["plan.create"] if op == "create" else ["plan.edit"]
    if op == "branch":
        permissions.append("plan.branch")
    authority.authorize_plan(token, permissions, relative)
    plan = copy.deepcopy(request["plan"])
    PLAN.validate(plan)
    request_hash = digest(request)
    with root_lock(root, True):
        require(not safe(root, JOURNAL, True).exists(), "RECOVERY_REQUIRED")
        index_path = safe(root, INDEX, True)
        index_bytes = index_path.read_bytes() if index_path.exists() else None
        index_before_hash = hashlib.sha256(index_bytes).hexdigest() if index_bytes is not None else None
        index = validate_index(json.loads(index_bytes)) if index_bytes is not None else {"schemaVersion": 1, "bindings": {}}
        source_bytes = target.read_bytes() if target.exists() else None
        source_before_hash = hashlib.sha256(source_bytes).hexdigest() if source_bytes is not None else None
        old = validate_store(json.loads(source_bytes), relative) if source_bytes is not None else None
        if old and tx in old["transactions"]:
            item = old["transactions"][tx]
            require(item["requestSHA256"] == request_hash, "TRANSACTION_REPLAY_CONFLICT")
            authority.authorize_plan(token, permissions, relative)
            return {"idempotent": True, **item}
        expected = old["revision"] if old else 0
        require(request["expectedRevision"] == expected, "CAS_MISMATCH")
        require((op == "create") == (old is None), "CREATE_OR_EDIT_STATE")
        require(plan["revision"] == expected + 1, "NEXT_REVISION_REQUIRED")
        # Replays retain the acceptance rule of their saved transaction. New
        # writes require explicit placement; historical snapshots remain readable.
        PLAN.validate_future_write(plan)
        owner = {"identitySpace": plan["identitySpace"], "planId": plan["id"], "sourcePath": relative}
        require(not old or old["owner"] == owner, "OWNER_IDENTITY_IMMUTABLE")
        key = identity(plan)
        binding = index["bindings"].get(key)
        require(binding is None or binding == owner, "DUPLICATE_WRITABLE_OWNER")
        require(not old or binding == owner, "OWNER_BINDING_MISMATCH")
        require(all(o["sourcePath"] != relative or o == owner for o in index["bindings"].values()), "PATH_ALREADY_OWNED")
        if (old and branch_signature(old["versions"][-1]["plan"]) != branch_signature(plan)) or (not old and plan.get("branches")):
            if "plan.branch" not in permissions:
                permissions.append("plan.branch")
        if before_prepare:
            before_prepare()
        with authority.checked_plan_transaction(token, permissions, relative) as verified:
            recorded = dt.datetime.now(dt.timezone.utc)
            require(not old or recorded >= instant(old["versions"][-1]["recordedAt"]), "CLOCK_REGRESSION")
            record = {"revision": plan["revision"], "plan": plan, "recordedAt": recorded.isoformat(),
                      "previousDigest": old["versions"][-1]["digest"] if old else None,
                      "transactionId": tx, "operation": op, "requestSHA256": request_hash,
                      "receipt": {"mode": "bearer", **verified, "principal": "bearer:" + verified["grantId"]}}
            record["digest"] = digest(record)
            store = copy.deepcopy(old) if old else {"schemaVersion": 1, "kind": "temporalPlanOwner", "owner": owner, "revision": 0, "versions": [], "transactions": {}}
            store["revision"] = plan["revision"]
            store["versions"].append(record)
            store["transactions"][tx] = {"requestSHA256": request_hash, "revision": plan["revision"], "recordDigest": record["digest"]}
            index["bindings"][key] = owner
            validate_store(store, relative)
            require(raw_hash(target) == source_before_hash and raw_hash(index_path) == index_before_hash,
                    "SOURCE_CHANGED_DURING_PREPARE")
            writes = [{"path": rel, "beforeSHA256": source_before_hash if rel == relative else index_before_hash,
                       "afterSHA256": digest(value), "after": value}
                      for rel, value in ((relative, store), (INDEX, index))]
            journal = {"schemaVersion": 1, "state": "prepared", "target": relative, "transactionId": tx, "writes": writes}
            # Durable prepared journal is the acceptance point. The grant lock
            # covers it and every subsequent write; recover may finish after revoke.
            atomic(safe(root, JOURNAL, True), journal)
            failpoint("prepared")
            replay(root, journal)
            return {"idempotent": False, **store["transactions"][tx], "technicalReceipt": record["receipt"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("apply", "read", "recover"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--store", default=os.environ.get("RDG_AUTH_STORE"))
    parser.add_argument("--request", type=Path)
    parser.add_argument("--file")
    parser.add_argument("--revision", type=int)
    args = parser.parse_args()
    token = os.environ.get("RDG_AUTH_TOKEN")
    if args.command == "recover":
        result = recover(args.root)
    elif args.command == "apply":
        require(args.store and args.request, "STORE_AND_REQUEST_REQUIRED")
        result = apply_request(args.root, args.store, token, json.loads(args.request.read_text()))
    else:
        require(args.store and args.file, "STORE_AND_FILE_REQUIRED")
        AUTH.Authority(args.store).authorize_plan(token, ["plan.read"], args.file)
        result = read_snapshot(args.root, args.file, args.revision)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        import sys
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
