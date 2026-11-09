#!/usr/bin/env python3
"""Read saved graph edits, Action executions and R achievements from one owner.

No scheduling, source writes, inferred human authors or invented old timestamps.
"""
import argparse
import fcntl
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import re

TOOLS = Path(__file__).resolve().parent
MODEL = SourceFileLoader("rdg_activity_model", str(TOOLS/"rdg-v7-model.py")).load_module()


def read_activity(graph_root, graph_refs, token=None, authority_store=None):
    root = Path(graph_root).resolve()
    lock_path = root/"workspaces/.writer.lock"
    if lock_path.exists():
        if any(p.is_symlink() for p in [lock_path, *lock_path.parents] if p != root.parent):
            raise ValueError("ACTIVITY_UNSAFE_LOCK")
        with os.fdopen(os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            return _read_activity_unlocked(root, graph_refs, token, authority_store)
    return _read_activity_unlocked(root, graph_refs, token, authority_store)


def _read_activity_unlocked(graph_root, graph_refs, token=None, authority_store=None):
    root = Path(graph_root).resolve()
    refs = list(dict.fromkeys(graph_refs))
    if not refs:
        raise ValueError("ACTIVITY_GRAPH_REFS_REQUIRED")
    paths = {}
    for ref in refs:
        if not isinstance(ref, str) or not re.fullmatch(r"workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json", ref):
            raise ValueError("ACTIVITY_GRAPH_PATH_INVALID")
        path = root/ref
        if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
            raise ValueError("ACTIVITY_UNSAFE_SOURCE")
        paths[ref] = path
    store = authority_store or os.environ.get("RDG_AUTH_STORE")
    if store:
        auth = SourceFileLoader("rdg_activity_auth", str(TOOLS/"rdg-authority.py")).load_module()
        auth.Authority(store).authorize_graph_read(token or os.environ.get("RDG_AUTH_TOKEN"), refs)
    graphs = {ref: json.loads(path.read_text(encoding="utf-8")) for ref, path in paths.items()}
    validator = SourceFileLoader("rdg_activity_validate", str(TOOLS/"graph-apply.py")).load_module()
    for graph in graphs.values():
        validator.validate(graph)
    rows, seen = [], set()

    def events(ref, entries, recorded_at, transaction_id):
        for event in entries:
            key = (ref, event["id"])
            if key in seen:
                continue
            seen.add(key)
            if event.get("type") not in MODEL.COMPLETION_EVENTS | {"action_withdrawn", "action_reconsidered"}:
                continue
            withdrawal = event.get("type") in {"action_withdrawn", "action_reconsidered"}
            rows.append({"id": ref+"::"+event["id"], "graphFile": ref,
                         "kind": "action_withdrawn" if withdrawal else event["type"],
                         "sourceEventType": event["type"],
                         "targetId": event["actionId"] if withdrawal else event["targetId"],
                         "title": (event.get("priorActionSnapshot", {}) if withdrawal else event.get("basis", {}).get("node", {})).get("title"),
                         "eventOrder": next(i for i,e in enumerate(graphs[ref]["events"]) if e["id"] == event["id"]),
                         "recordedAt": recorded_at, "occurredAt": event.get("occurredAt"),
                         "by": event.get("by"), "authorityPrincipal": event.get("authorityPrincipal"),
                         "completionMode": event.get("completionMode"),
                         "basisSHA256": event.get("basisSHA256"), "note": event.get("note"),
                         "transactionId": transaction_id})

    directory = root/"workspaces/.transactions"
    if directory.exists() and (directory.is_symlink() or any(p.is_symlink() for p in directory.parents if p != root.parent)):
        raise ValueError("ACTIVITY_UNSAFE_JOURNAL")
    for journal_path in sorted(directory.glob("*.json")):
        if journal_path.is_symlink():
            raise ValueError("ACTIVITY_UNSAFE_JOURNAL")
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        if journal.get("state") != "completed":
            if any(r.get("file") in refs for r in journal.get("records", [])):
                raise ValueError("ACTIVITY_RECOVERY_REQUIRED")
            continue
        for record in journal.get("records", []):
            ref = record.get("file")
            if ref not in graphs or record.get("changed") is False:
                continue
            before, after = record.get("before") or {}, record["after"]
            previous = {e["id"] for e in before.get("events", [])}
            added = [e for e in after.get("events", []) if e["id"] not in previous]
            principal = sorted({e["authorityPrincipal"] for e in added if e.get("authorityPrincipal")})
            if journal.get("authorityPrincipal"):
                principal = sorted(set(principal) | {journal["authorityPrincipal"]})
            changed = {}
            for field in ("nodes", "edges"):
                old = {x["id"]: x for x in before.get(field, [])}
                new = {x["id"]: x for x in after.get(field, [])}
                changed[field] = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
            rows.append({"id": journal["transactionId"]+"::"+ref+"::saved", "graphFile": ref,
                         "kind": "graph_saved", "recordedAt": journal.get("recordedAt"),
                         "transactionId": journal["transactionId"], "revision": after["revision"],
                         "previousRevision": before.get("revision"), "changed": changed,
                         "authorityPrincipals": principal,
                         "summary": "; ".join(dict.fromkeys(e.get("note", "") for e in added if e.get("note") and e.get("type") not in MODEL.COMPLETION_EVENTS)) or
                                    "Изменены: " + ", ".join(next((n["title"] for n in after.get("nodes", []) if n["id"] == nid), nid) for nid in changed["nodes"]),
                         "operations": [e.get("operation", e.get("type")) for e in added
                                        if e.get("type") not in MODEL.COMPLETION_EVENTS]})
            events(ref, added, journal.get("recordedAt"), journal["transactionId"])
    for ref, graph in graphs.items():
        # Historical events without a completed journal retain unknown save time.
        events(ref, graph.get("events", []), None, None)
    rows.sort(key=lambda r: (r.get("recordedAt") is None, r.get("recordedAt") or "",
                             r.get("graphFile"), r.get("eventOrder", -1), r["id"]))
    states = {ref: {nid: {k: v for k, v in row.items() if k != "basis"}
                    for nid, row in MODEL.completion_state(graph).items()}
              for ref, graph in graphs.items() if graph.get("actionModel") == "candidate-v6"}
    owners = {ref: {"identitySpace": graph.get("identitySpace"), "revision": graph["revision"],
                    "nodes": {n["id"]: {k:n[k] for k in ("id", "kind", "title", "status", "active", "projectionOf") if k in n}
                              for n in graph["nodes"] if n["kind"] in {"requirement", "action"}}}
              for ref,graph in graphs.items()}
    return {"schemaVersion": 1, "activities": rows, "currentCompletion": states, "graphOwners": owners,
            "coverage": "requested-graph-owners; cross-file completion requires owner resolution",
            "sourcesChanged": False}


def markdown(report, outcomes_only=False):
    labels = {"graph_saved": "Сохранён граф", "action_executed": "Выполнен Action",
              "requirement_achieved": "Достигнута цель / Requirement", "action_withdrawn": "Отозван Action"}
    lines = []
    for row in report["activities"]:
        if outcomes_only and row["kind"] == "graph_saved":
            continue
        target = row.get("targetId") or "revision="+str(row.get("revision"))
        lines.append("- "+(row.get("recordedAt") or "Время записи неизвестно")+" · "+
                     labels[row["kind"]]+" · "+target+" · "+row["graphFile"]+
                     (" · "+row["title"] if row.get("title") else "") +
                     (" · "+row["summary"] if row.get("summary") else ""))
    return "\n".join(lines)+"\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-root", required=True)
    parser.add_argument("--graph", action="append", required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--outcomes-only", action="store_true")
    args = parser.parse_args()
    report = read_activity(args.graph_root, args.graph)
    if args.outcomes_only:
        report["activities"] = [r for r in report["activities"] if r["kind"] != "graph_saved"]
    print(markdown(report) if args.format == "markdown" else json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit("ERROR: "+str(exc))
