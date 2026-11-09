#!/usr/bin/env python3
"""Read-only exact candidate Plan + RDG snapshots; not a two-time as-of resolver.

Completed local Graph writer journals contain full images, not trusted recordedAt.
Explicit canonical SHA pins are mandatory. No current-file or latest-version fallback.
"""
import argparse
import copy
import fcntl
import hashlib
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
OWNER = SourceFileLoader("exact_history_owner", str(HERE / "rdg-temporal-plan-owner.py")).load_module()
IMPACT = SourceFileLoader("exact_history_impact", str(HERE / "rdg-temporal-impact.py")).load_module()
GRAPH = SourceFileLoader("exact_history_graph_validator", str(HERE / "graph-apply.py")).load_module()
SHA = re.compile(r"[a-f0-9]{64}\Z")
TX = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z")


def require(ok, code):
    if not ok:
        raise ValueError("EXACT_HISTORY_" + code)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def load_bytes(raw):
    return json.loads(raw, object_pairs_hook=unique_object)


def safe(root, relative):
    path = root
    for part in relative.split("/"):
        require(part not in ("", ".", ".."), "PATH_INVALID")
        path = path / part
        require(not path.is_symlink(), "SYMLINK_DENIED")
    require(path.resolve().is_relative_to(root), "PATH_OUTSIDE_ROOT")
    return path


def graph_key(pin):
    return pin["identitySpace"], pin["graphFile"], pin["revision"]


def validate_query(query):
    require(isinstance(query, dict), "REQUEST_SCHEMA")
    require(not ({"knownAt", "effectiveAt"} & set(query)), "TWO_TIME_QUERY_NOT_SUPPORTED")
    require(set(query) == {"schemaVersion", "mode", "lifecycle", "plan", "graphs", "scenario"} and
            type(query["schemaVersion"]) is int and query["schemaVersion"] == 1 and
            query["mode"] == "exact-reference" and query["lifecycle"] == "candidate", "REQUEST_SCHEMA")
    plan = query["plan"]
    require(isinstance(plan, dict) and set(plan) == {"file", "identitySpace", "planId", "revision", "snapshotSHA256", "recordDigest"}, "PLAN_PIN_SCHEMA")
    require(isinstance(plan["file"], str) and OWNER.TARGET.fullmatch(plan["file"]) and
            OWNER.PLAN.named(plan["identitySpace"]) and OWNER.PLAN.ident(plan["planId"]) and
            type(plan["revision"]) is int and plan["revision"] >= 1 and
            all(isinstance(plan[k], str) and SHA.fullmatch(plan[k]) for k in ("snapshotSHA256", "recordDigest")), "PLAN_PIN_INVALID")
    pins = query["graphs"]
    require(isinstance(pins, list) and pins, "GRAPH_PINS_REQUIRED")
    keys = set()
    for pin in pins:
        require(isinstance(pin, dict) and set(pin) == {"graphFile", "identitySpace", "revision", "snapshotSHA256"}, "GRAPH_PIN_SCHEMA")
        require(isinstance(pin["graphFile"], str) and OWNER.PLAN.GRAPH_REF.fullmatch(pin["graphFile"]) and
                OWNER.PLAN.named(pin["identitySpace"]) and type(pin["revision"]) is int and pin["revision"] >= 1 and
                isinstance(pin["snapshotSHA256"], str) and SHA.fullmatch(pin["snapshotSHA256"]), "GRAPH_PIN_INVALID")
        key = graph_key(pin)
        require(key not in keys, "DUPLICATE_GRAPH_PIN")
        keys.add(key)
    scenario = query["scenario"]
    require(isinstance(scenario, dict) and set(scenario) == {"branchId", "outcome"} and
            all(v is None or OWNER.PLAN.ident(v) for v in scenario.values()), "SCENARIO_SCHEMA")


def journal_snapshots(graphs_root, pins):
    """Shared writer lock, completed journals only, no current graph reads/writes."""
    root = Path(graphs_root).resolve(strict=True)
    require(root.is_dir(), "GRAPH_ROOT_REQUIRED")
    lock_path = safe(root, "workspaces/.writer.lock")
    require(lock_path.is_file(), "WRITER_HISTORY_NOT_AVAILABLE")
    directory = safe(root, "workspaces/.transactions")
    require(directory.is_dir(), "WRITER_HISTORY_NOT_AVAILABLE")
    found = {graph_key(pin): {} for pin in pins}
    sources = {key: [] for key in found}
    files = {pin["graphFile"] for pin in pins}
    owners = {pin["graphFile"]: pin["identitySpace"] for pin in pins}
    require(len(owners) == len({(p["graphFile"], p["identitySpace"]) for p in pins}), "GRAPH_OWNER_CONFLICT")
    with os.fdopen(os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        for path in sorted(directory.glob("*.json")):
            path = safe(root, path.relative_to(root).as_posix())
            raw = path.read_bytes()
            journal = load_bytes(raw)
            require(isinstance(journal, dict) and set(journal) == {"schemaVersion", "transactionId", "requestSHA256", "state", "records"} and
                    type(journal["schemaVersion"]) is int and journal["schemaVersion"] == 1 and
                    isinstance(journal["transactionId"], str) and TX.fullmatch(journal["transactionId"]) and
                    path.stem == journal["transactionId"] and isinstance(journal["requestSHA256"], str) and
                    SHA.fullmatch(journal["requestSHA256"]), "JOURNAL_SCHEMA")
            require(journal["state"] != "prepared", "GRAPH_RECOVERY_REQUIRED")
            require(journal["state"] == "completed" and isinstance(journal["records"], list) and journal["records"], "JOURNAL_STATE")
            seen = set()
            for record in journal["records"]:
                require(isinstance(record, dict) and set(record) == {"file", "before", "after", "changed"} and
                        isinstance(record["file"], str) and OWNER.PLAN.GRAPH_REF.fullmatch(record["file"]) and
                        record["file"] not in seen and type(record["changed"]) is bool, "JOURNAL_RECORD_SCHEMA")
                seen.add(record["file"])
                if record["file"] not in files:
                    continue
                before, after = record["before"], record["after"]
                for image in (before, after):
                    if image is None:
                        continue
                    require(isinstance(image, dict) and image.get("identitySpace") == owners[record["file"]], "GRAPH_IDENTITY_MISMATCH")
                    GRAPH.validate(image)
                require(isinstance(after, dict) and type(after.get("revision")) is int and
                        after["revision"] == (before["revision"] + int(record["changed"]) if before else 1) and
                        record["changed"] == (before != after), "JOURNAL_REVISION_CHAIN")
                for side, image in (("before", before), ("after", after)):
                    if image is None:
                        continue
                    key = image["identitySpace"], record["file"], image["revision"]
                    if key not in found:
                        continue
                    sha = OWNER.digest(image)
                    found[key][sha] = copy.deepcopy(image)
                    sources[key].append({"journal": path.relative_to(root).as_posix(),
                                         "journalSHA256": hashlib.sha256(raw).hexdigest(),
                                         "transactionId": journal["transactionId"], "side": side})
    results = {}
    for pin in pins:
        key = graph_key(pin)
        require(found[key], "GRAPH_SNAPSHOT_NOT_FOUND")
        require(len(found[key]) == 1, "AMBIGUOUS_GRAPH_REVISION")
        sha, graph = next(iter(found[key].items()))
        require(sha == pin["snapshotSHA256"], "GRAPH_SNAPSHOT_HASH_MISMATCH")
        results[key] = {"graph": graph, "provenance": {
            **pin, "sourceKind": "completed-writer-journal", "sources": sources[key],
            "exactRdgSnapshotResolved": True, "recordedAt": None,
            "knowledgeTimeVerified": False, "humanIdentityVerified": False}}
    return results


def resolve(plan_root, graphs_root, authority_store, token, query, before_return=None):
    validate_query(query)
    plan_pin, pins = query["plan"], query["graphs"]
    authority = OWNER.AUTH.Authority(authority_store)
    targets = sorted({p["graphFile"] for p in pins})
    authority.authorize_snapshot_read(token, plan_pin["file"], targets)
    snapshot = OWNER.read_snapshot(plan_root, plan_pin["file"], plan_pin["revision"])
    plan, provenance = snapshot["plan"], snapshot["provenance"]
    require(plan["identitySpace"] == plan_pin["identitySpace"] and plan["id"] == plan_pin["planId"], "PLAN_IDENTITY_MISMATCH")
    require(provenance["snapshotSHA256"] == plan_pin["snapshotSHA256"] and provenance["recordDigest"] == plan_pin["recordDigest"], "PLAN_SNAPSHOT_HASH_MISMATCH")
    cases = [c for c in IMPACT.review_cases(plan) if c["branchId"] == query["scenario"]["branchId"] and c["outcome"] == query["scenario"]["outcome"]]
    require(len(cases) == 1, "SCENARIO_NOT_FOUND")
    active = {s["id"] for s in plan["steps"] if s["state"] != "possible"} | cases[0]["possibleSteps"]
    refs = [s["actionRef"] for s in plan["steps"] if s["kind"] == "action" and s["id"] in active]
    require(refs and all(type(ref.get("observedGraphRevision")) is int for ref in refs), "EXACT_ACTION_REVISIONS_REQUIRED")
    expected = {(ref["identitySpace"], ref["graphFile"], ref["observedGraphRevision"]) for ref in refs}
    require(expected == {graph_key(pin) for pin in pins}, "SCENARIO_GRAPH_PINS_MISMATCH")
    graphs = journal_snapshots(graphs_root, pins)
    def graph_resolver(ref):
        key = ref["identitySpace"], ref["graphFile"], ref["observedGraphRevision"]
        require(key in graphs, "GRAPH_SNAPSHOT_NOT_FOUND")
        return copy.deepcopy(graphs[key]["graph"])
    impact = IMPACT.assess(plan, None, graph_resolver=graph_resolver, scenario=query["scenario"])
    if before_return:
        before_return()
    # Recheck after both owner locks have been released; a read must not return
    # its snapshot after a revocation that completed while resolution was running.
    read_receipt = authority.authorize_snapshot_read(token, plan_pin["file"], targets)
    return {"status": "resolved", "mode": "exact-reference", "lifecycle": "candidate",
            "scenario": copy.deepcopy(query["scenario"]), "scenarioOnly": True, "readOnly": True,
            "plan": plan, "planProvenance": provenance,
            "graphSnapshots": [graphs[key] for key in sorted(graphs)], "impact": impact,
            "readAuthorization": read_receipt,
            "provenance": {"exactPlanSnapshotResolved": True, "exactRdgSnapshotsResolved": True,
                           "knowledgeTimeVerified": False, "twoTimeAsOfResolved": False,
                           "historicalT1KnowledgeVerified": False, "semanticTruthVerified": False,
                           "eventsAttested": False, "productionAccepted": False},
            "evidenceGaps": ["RDG writer journals have no trusted recordedAt; knownAt/effectiveAt are unsupported",
                             "Exact local hashes do not prove human identity, factual truth, or complete historical context"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-root", required=True, type=Path)
    parser.add_argument("--graphs-root", required=True, type=Path)
    parser.add_argument("--store", default=os.environ.get("RDG_AUTH_STORE"))
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args()
    require(args.store is not None, "AUTH_STORE_REQUIRED")
    result = resolve(args.plan_root, args.graphs_root, args.store, os.environ.get("RDG_AUTH_TOKEN"), load_bytes(args.request.read_bytes()))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        import sys
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
