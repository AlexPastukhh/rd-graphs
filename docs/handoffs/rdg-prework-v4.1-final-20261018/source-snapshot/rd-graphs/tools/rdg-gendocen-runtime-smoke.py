#!/usr/bin/env python3
"""Execute real Gendocen dev25 against synthetic RDG/Plan adapter projections.

Explicit --engine-source is an already-reviewed local Gendocen source checkout.
No engine install, working-graph write, user acceptance or F-P confirmation.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from importlib.machinery import SourceFileLoader

ROOT = Path(__file__).resolve().parent.parent
adapter = SourceFileLoader("rdg_runtime_smoke_adapter",
    str(ROOT / "tools/rdg-gendocen-adapter.py")).load_module()


def require(value, error):
    if not value:
        raise AssertionError(error)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf8")


def engine_ref(resource):
    return "resource://" + resource["$docengine"]["resource_id"].replace(".", "/", 1)


def smoke(engine_source):
    source = Path(engine_source).resolve() / "src"
    require((source / "docengine/cli.py").is_file(), "GENDOCEN_SOURCE_UNAVAILABLE")
    env = {**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"}
    with tempfile.TemporaryDirectory(prefix="rdg-gendocen-runtime-") as name:
        root = Path(name)
        original = root / "graphs/workspaces/temporal-fixture/graph.json"
        graph = {
            "schemaVersion": 1, "revision": 1, "id": "synthetic",
            "identitySpace": "temporal-demo", "actionModel": "candidate-v6",
            "rootRequirementId": "R0",
            "nodes": [{"id": "R0", "kind": "requirement", "title": "R"},
                      *[{"id": aid, "kind": "action", "title": aid,
                         "status": "candidate", "canonBlock": {
                             "recommended": [{"id": "C-" + aid, "text": "Needs review"}],
                             "contraindicated": []}} for aid in ("A1", "A2")]],
            "edges": [], "events": []
        }
        plan = json.loads((ROOT / "docs/examples/temporal-plan-candidate-v1.json")
                          .read_text(encoding="utf8"))
        plan_path = root / "plan.json"
        save(original, graph)
        save(plan_path, plan)
        project = root / "gendocen-project"
        (project / "docengine_project").mkdir(parents=True)
        (project / "docs/review").mkdir(parents=True)
        (project / "docengine.toml").write_text(
            '[docengine]\nconfig_version = 1\n'
            'documentation_root = "docs"\nstructured_dir = "_structured"\n'
            'dependency_dir = "_dependency"\nproject_package = "docengine_project"\n')
        graph_projection = project / "docs/_structured/rdg/graph.json"
        plan_projection = project / "docs/_structured/rdg/plan.json"
        graph_obj = adapter.graph_resource(
            original, "workspaces/temporal-fixture/graph.json")
        plan_obj = adapter.plan_resource(plan_path)
        save(graph_projection, graph_obj)
        save(plan_projection, plan_obj)
        gref, pref = engine_ref(graph_obj), engine_ref(plan_obj)
        (project / "docengine_project/__init__.py").write_text(
            "def register_builders(registry):\n    pass\n\n"
            "def register_semantic_dependencies(registry):\n"
            "    for aid in ('A1', 'A2'):\n"
            "        registry.register(\n"
            "            f'file://review/{aid}.md',\n"
            "            [(f'" + pref + "#/timeConstraintsByStep/S-{aid}', 'exact'),\n"
            "             ('" + pref + "#/timeConstraintsByStep/S-DELIVERY', 'exact'),\n"
            "             (f'" + gref + "#/nodesById/{aid}/canonBlock', 'exact')],\n"
            "            rule_id=f'rdg-temporal-review.{aid}',\n"
            "            dependency_type='semantic_review')\n")
        docs = {}
        for aid in ("A1", "A2"):
            docs[aid] = project / ("docs/review/" + aid + ".md")
            docs[aid].write_text("# Synthetic " + aid + "\n\nNot user-approved.\n")
        prose = {aid: p.read_bytes() for aid, p in docs.items()}

        def cli(*parts):
            proc = subprocess.run(
                [sys.executable, "-m", "docengine.cli", *parts,
                 "--project-root", str(project), "--json"],
                capture_output=True, text=True, env=env)
            require(proc.stdout.strip(), "DOCENGINE_NO_JSON " + proc.stderr)
            body = json.loads(proc.stdout)
            require(body["meta"]["engine_version"] == "0.1.0.dev25",
                    "DOCENGINE_VERSION_MISMATCH")
            return proc.returncode, body

        def statuses():
            _, body = cli("check")
            return {i["target"].rsplit("/", 1)[-1][:-3]: i["status"]
                    for i in body["data"]["results"]}

        def review_context(aid):
            _, data = cli("explain", "file://review/" + aid + ".md")
            return data["data"]["review_context_id"]

        def accept_synthetic_baseline(aid):
            code, result = cli(
                "validate", "file://review/" + aid + ".md",
                "--result", "still-valid",
                "--reason", "Only a synthetic test baseline, no RDG decision",
                "--review-context", review_context(aid))
            require(code == 0 and result["ok"],
                    "SYNTHETIC_BASELINE_INVALID " + str(result))

        def check_expected(a1, a2, reason):
            actual = statuses()
            require(actual == {"A1": a1, "A2": a2}, reason + ":" + str(actual))
            for aid in docs:
                require(docs[aid].read_bytes() == prose[aid],
                        "REVIEW_MARKDOWN_AUTO_REWRITTEN")

        def reproject():
            save(plan_path, plan)
            save(plan_projection, adapter.plan_resource(plan_path))

        _, initial = cli("sync")
        require(set(initial["data"]["attention_targets"]) ==
                {"file://review/A1.md", "file://review/A2.md"},
                "INITIAL_REVIEW_NOT_REQUIRED")
        for aid in ("A1", "A2"):
            accept_synthetic_baseline(aid)
        check_expected("valid", "valid", "initial")
        # All CLI calls above were separate processes. Inspect the on-disk
        # dependency state, receipts and history: statuses alone are not proof
        # that baseline approvals survive restarts.
        dep_root = project / "docs/_dependency"
        state_path = dep_root / "state/dependency_state.json"
        event_path = dep_root / "events/dependency_events.jsonl"
        receipts_dir = dep_root / "receipts"
        require(state_path.is_file(), "PERSISTED_DEPENDENCY_STATE_MISSING")
        stored = json.loads(state_path.read_text(encoding="utf8"))
        require(set(stored["targets"]) ==
                {"file://review/A1.md", "file://review/A2.md"} and
                all(v["status"] == "valid" for v in stored["targets"].values()),
                "BASELINE_STATE_NOT_PERSISTED")
        stored_receipts = sorted(receipts_dir.glob("receipt-*.json"))
        require(len(stored_receipts) >= 2 and
                all((receipts_dir / (v["last_receipt_id"] + ".json")).is_file()
                    for v in stored["targets"].values()), "BASELINE_RECEIPTS_MISSING")
        require(event_path.is_file() and event_path.read_text().strip(),
                "DEPENDENCY_EVENTS_MISSING")
        state_revision = stored["state_revision"]
        receipt_count = len(stored_receipts)
        event_count = len(event_path.read_text().splitlines())
        require(state_revision > 0, "BASELINE_REVISION_MISSING")
        check_expected("valid", "valid", "new process persisted read")
        require(json.loads(state_path.read_text())["state_revision"] ==
                state_revision and
                len(list(receipts_dir.glob("receipt-*.json"))) == receipt_count and
                len(event_path.read_text().splitlines()) == event_count,
                "READ_ONLY_CHECK_MUTATED_PERSISTED_DATA")

        # Neither JSON formatting nor unordered steps + metadata revision
        # are input to the precise semantic rules.
        graph["nodes"].reverse()
        graph["revision"] += 1
        plan["steps"].reverse()
        plan["revision"] += 1
        save(original, graph)
        save(graph_projection, adapter.graph_resource(
            original, "workspaces/temporal-fixture/graph.json"))
        reproject()
        check_expected("valid", "valid", "reordered")

        plan["timeConstraints"].append({
            "stepId": "S-A2", "type": "notBefore", "at": "2026-11-14",
            "strength": "hypothetical", "basis": "Synthetic only"})
        plan["revision"] += 1
        reproject()
        check_expected("valid", "review_required", "A2 branch only")
        _, a2_explain = cli("explain", "file://review/A2.md")
        require(a2_explain["data"]["changed_dependencies"] ==
                [pref + "#/timeConstraintsByStep/S-A2"],
                "A2_DEPENDENCY_NOT_PRECISE")
        accept_synthetic_baseline("A2")
        check_expected("valid", "valid", "A2 review completed")

        for c in plan["timeConstraints"]:
            if c["stepId"] == "S-DELIVERY":
                c["at"] = "2026-11-17"
        plan["revision"] += 1
        reproject()
        check_expected("review_required", "review_required", "shared deadline")
        old_context = review_context("A1")

        for c in plan["timeConstraints"]:
            if c["stepId"] == "S-DELIVERY":
                c["at"] = "2026-11-16"
        plan["revision"] += 1
        reproject()
        state_before_stale = state_path.read_bytes()
        receipts_before_stale = len(list(receipts_dir.glob("receipt-*.json")))
        code, response = cli(
            "validate", "file://review/A1.md",
            "--result", "still-valid", "--reason", "Stale synthetic review",
            "--review-context", old_context)
        require(code != 0 and
                response["meta"]["status"] == "validation_failed" and
                "stale" in json.dumps(response).lower(),
                "STALE_REVIEW_CONTEXT_ACCEPTED")
        require(state_path.read_bytes() == state_before_stale and
                len(list(receipts_dir.glob("receipt-*.json"))) == receipts_before_stale,
                "STALE_REVIEW_CHANGED_DEPENDENCY_STATE")
        check_expected("review_required", "review_required",
                       "rejection did not clear review-required")
        for aid in ("A1", "A2"):
            accept_synthetic_baseline(aid)
        check_expected("valid", "valid", "common baseline renewed")

        for action in graph["nodes"]:
            if action["id"] == "A1":
                action["canonBlock"]["recommended"][0]["text"] = "Changed canon"
        graph["revision"] += 1
        save(original, graph)
        save(graph_projection, adapter.graph_resource(
            original, "workspaces/temporal-fixture/graph.json"))
        check_expected("review_required", "valid", "canon A1 only")
        require(all(n.get("status") == "candidate"
                    for n in graph["nodes"] if n.get("kind") == "action"),
                "ACTION_WAS_SELECTED")

        # Stage 4: A real hard crash in the middle of a transactional Gendocen
        # semantic validation. The baseline A1 review has already become
        # review_required from its Canon change. The crash must not mint a
        # false valid review, change history or write back to RDG.
        source_before_crash = original.read_bytes()
        plan_before_crash = plan_path.read_bytes()
        graph_projection_before = graph_projection.read_bytes()
        plan_projection_before = plan_projection.read_bytes()
        state_before_crash = state_path.read_bytes()
        events_before_crash = event_path.read_bytes()
        receipts_before_crash = {
            q.name: q.read_bytes() for q in receipts_dir.glob("receipt-*.json")
        }
        a1_receipt_before = json.loads(state_before_crash)["targets"][
            "file://review/A1.md"]["last_receipt_id"]
        history_code, old_history_reply = cli("history", "file://review/A1.md")
        require(history_code == 0 and old_history_reply["ok"],
                "A1_HISTORY_UNAVAILABLE_BEFORE_CRASH")
        a1_history_before = old_history_reply["data"]
        require(a1_receipt_before in a1_history_before["receipt_ids"] and
                len(a1_history_before["events"]) >= 1,
                "HISTORICAL_A1_RECEIPT_UNINDEXED")
        crash_context = review_context("A1")
        crashed = subprocess.run(
            [sys.executable, "-m", "docengine.cli", "validate",
             "file://review/A1.md", "--result", "still-valid",
             "--reason", "Synthetic interrupted review, NOT owner authorization",
             "--review-context", crash_context, "--project-root", str(project),
             "--json"],
            text=True, capture_output=True,
            env={**env, "DOCENGINE_TEST_CRASH_AFTER_WRITES": "1"})
        require(crashed.returncode == 91,
                "EXPECTED_HARD_CRASH_NOT_REACHED: " + str(crashed.returncode) +
                " " + crashed.stderr + " " + crashed.stdout)
        code, blocked = cli("status")
        require(code != 0 and blocked["meta"]["status"] == "recovery_required",
                "CRASH_DID_NOT_BLOCK_READS")
        code, verify = cli("verify")
        require(code != 0 and
                verify["meta"]["status"] == "verification_failed" and
                any(f.get("code") == "recovery_required" for f in
                    verify["data"]["report"]["findings"]),
                "CRASH_DID_NOT_TRIGGER_RECOVERY_REQUIRED")
        require(source_before_crash == original.read_bytes() and
                plan_before_crash == plan_path.read_bytes() and
                graph_projection_before == graph_projection.read_bytes() and
                plan_projection_before == plan_projection.read_bytes(),
                "CRASH_CHANGED_RDG_OR_PLAN_SOURCE")
        code, recovered = cli("recover")
        require(code == 0 and recovered["ok"] and
                recovered["data"]["remaining"] == 0 and
                bool(recovered["data"]["recovered"]),
                "RECOVERY_FAILED: " + str(recovered))
        require(state_path.read_bytes() == state_before_crash and
                event_path.read_bytes() == events_before_crash and
                {q.name: q.read_bytes() for q in
                 receipts_dir.glob("receipt-*.json")} == receipts_before_crash,
                "RECOVERY_DID_NOT_ROLL_BACK_DEPENDENCY_HISTORY")
        require(source_before_crash == original.read_bytes() and
                plan_before_crash == plan_path.read_bytes() and
                graph_projection_before == graph_projection.read_bytes() and
                plan_projection_before == plan_projection.read_bytes(),
                "RECOVERY_MODIFIED_RDG_OR_PLAN")
        check_expected("review_required", "valid", "crash recovery restores A1 pending review")
        state_after_recovery = json.loads(state_path.read_text(encoding="utf8"))
        require(state_after_recovery["targets"][
            "file://review/A1.md"]["last_receipt_id"] == a1_receipt_before,
            "RECOVERY_REPLACED_HISTORICAL_A1_RECEIPT")
        history_code, rolled_back_history_reply = cli(
            "history", "file://review/A1.md")
        require(history_code == 0 and
                rolled_back_history_reply["data"] == a1_history_before,
                "CRASH_RECOVERY_REWROTE_A1_VALIDATION_HISTORY")
        recovery_log = dep_root / "hardening/recovery_events.jsonl"
        require(recovery_log.is_file(), "RECOVERY_AUDIT_MISSING")
        audited_recovery = [
            json.loads(line) for line in recovery_log.read_text(encoding="utf8").splitlines()
            if line.strip()]
        require(any(e.get("action") == "rolled_back_interrupted_transaction"
                    for e in audited_recovery), "RECOVERY_ROLLBACK_NOT_AUDITED")
        recovery_audit_bytes = recovery_log.read_bytes()
        code, again = cli("recover")
        require(code == 0 and again["ok"] and again["data"]["remaining"] == 0,
                "RECOVERY_NOT_IDEMPOTENT")
        require(recovery_log.read_bytes() == recovery_audit_bytes,
                "SECOND_RECOVERY_APPENDED_AUDIT")
        # A fresh review after successful recovery is a *new* synthetic
        # acknowledgement; the interrupted attempt cannot be adopted.
        accept_synthetic_baseline("A1")
        check_expected("valid", "valid", "fresh review after crash recovery")
        history_code, current_history_reply = cli(
            "history", "file://review/A1.md")
        require(history_code == 0, "A1_HISTORY_UNAVAILABLE_AFTER_NEW_REVIEW")
        current_history = current_history_reply["data"]
        require(set(a1_history_before["receipt_ids"]).issubset(
                    current_history["receipt_ids"]) and
                len(current_history["receipt_ids"]) ==
                    len(a1_history_before["receipt_ids"]) + 1 and
                current_history["events"][:len(a1_history_before["events"])] ==
                    a1_history_before["events"] and
                len(current_history["events"]) ==
                    len(a1_history_before["events"]) + 1,
                "NEW_REVIEW_DID_NOT_APPEND_HISTORICAL_EVIDENCE")
        require(original.read_bytes() == source_before_crash and
                plan_path.read_bytes() == plan_before_crash and
                graph_projection.read_bytes() == graph_projection_before and
                plan_projection.read_bytes() == plan_projection_before,
                "POST_RECOVERY_VALIDATION_CHANGED_SOURCE")
        return {
            "runtime": "docengine 0.1.0.dev25",
            "test": "actual Gendocen semantic rules on RDG+Plan adapter outputs",
            "initial": "A1 valid, A2 valid",
            "jsonReordering": "both valid",
            "branchA2": "A1 valid, A2 review_required",
            "sharedDeadline": "both review_required",
            "staleReviewContext": "rejected",
            "canonA1": "A1 review_required, A2 valid",
            "sourceMode": "synthetic, all temporary; no RDG writes",
            "decisionsSelected": False, "reviewProseAutoRewritten": False,
            "persistedDependencyState": True,
            "baselineDependencyReceiptCount": receipt_count,
            "baselineDependencyEventCount": event_count,
            "readOnlyStatusDidNotMutatePersistence": True,
            "rejectedStaleValidationLeftStateUnchanged": True,
            "injectedHardCrashExitCode": 91,
            "statusAfterCrash": "recovery_required",
            "verifyAfterCrash": "verification_failed (finding: recovery_required)",
            "rollbackRecovered": True,
            "recoveredDependencyHistoryIdentical": True,
            "historicalA1ReceiptPreserved": True,
            "publicHistoryUnchangedByRollback": True,
            "newReviewPreservedOldHistoryAndAppendedNewReceipt": True,
            "a1HistoryEventsBeforeCrash": len(a1_history_before["events"]),
            "a1HistoryEventsAfterNewValidation": len(current_history["events"]),
            "recoveryAuditAction": "rolled_back_interrupted_transaction",
            "recoverIdempotent": True,
            "reviewAfterRecovery": "A1 valid, A2 valid",
            "canonicalRDGAndPlanBytesUnchangedDuringCrash": True,
            "genuineHistoricalT1EventUsed": False
        }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engine-source", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(smoke(args.engine_source),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
