#!/usr/bin/env python3
"""Stage 4: synthetic, authorized RDG T1 -> QRPE revisions -> real Gendocen.

No working graph files, user authentication, Plan execution or real-world F-P.
Tests actual isolated bearer-authorized writer transactions and their immutable
T1 event through later Finding lifecycle, dependency invalidation and rollback.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from importlib.machinery import SourceFileLoader

ROOT = Path(__file__).resolve().parent.parent
ADAPTER = SourceFileLoader(
    "t1_gendocen_adapter", str(ROOT / "tools/rdg-gendocen-adapter.py")).load_module()
TOOLS = ("rdg-authority.py graph-package.py graph-apply.py graph-index.py "
         "rdg-v7-model.py rdg-v6-action-reconsider.py rdg-v6-action-trust.py "
         "rdg-state.py rdg-state.js rdg-state-cli.cjs rdg-catalog.py "
         "rdg-catalog.js rdg-graph-api.py").split()
REL = "workspaces/temporal-fixture/graph.json"


def require(value, code):
    if not value:
        raise AssertionError("T1_HISTORY_" + code)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf8")


def uri(resource):
    return "resource://" + resource["$docengine"]["resource_id"].replace(".", "/", 1)


def snapshot(path):
    return json.loads(path.read_text(encoding="utf8"))


def run(engine):
    source = Path(engine).resolve() / "src"
    require((source / "docengine/cli.py").is_file(), "ENGINE_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="rdg-t1-stage4-") as root_name:
        workspace = Path(root_name)
        (workspace / "tools").mkdir()
        for name in TOOLS:
            shutil.copy2(ROOT / "tools" / name, workspace / "tools" / name)
        graph_path = workspace / "graphs" / REL
        auth_store = workspace / "grants.json"
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
               "RDG_AUTH_STORE": str(auth_store)}
        env.pop("RDG_V6_TRUST_KEY", None)

        def admin(command, token="", request=None):
            response = subprocess.run(
                [sys.executable, str(workspace / "tools/rdg-authority.py"),
                 command, "--store", str(auth_store)],
                text=True, input=json.dumps(request) if request else "",
                capture_output=True, env={**env, "RDG_AUTH_TOKEN": token})
            require(response.returncode == 0,
                    "ADMIN_" + command + "_" + response.stderr)
            return json.loads(response.stdout)

        owner = admin("init")["token"]
        def grant(perms):
            return admin("issue", owner, {"permissions": perms,
                                         "scopes": [REL]})["token"]
        author = grant(["graph.create", "graph.add_action"])
        selector = grant(["graph.select_action"])
        finding_writer = grant(["graph.append_finding", "graph.transition_qrpe"])
        misc_writer = grant(["graph.write"])

        def graph_package(ops, revision, txid):
            return {"schemaVersion": 1, "transactionId": txid,
                    "changes": [{"file": REL, "patch": {
                        "schemaVersion": 1, "expectedRevision": revision,
                        "operations": ops}}]}

        def write_package(package, bearer, expected_ok=True):
            input_path = workspace / "writer-input.json"
            save(input_path, package)
            result = subprocess.run(
                [sys.executable, str(workspace / "tools/graph-apply.py"),
                 "--package", "--patch", str(input_path)],
                capture_output=True, text=True,
                env={**env, "RDG_AUTH_TOKEN": bearer})
            if expected_ok:
                require(result.returncode == 0,
                        "WRITER_" + package["transactionId"] + "_" + result.stderr)
            else:
                require(result.returncode != 0,
                        "WRITER_UNEXPECTED_ALLOW_" + package["transactionId"])
            return result

        initial = {
            "schemaVersion": 1, "id": "synthetic-T1", "title": "Synthetic T1 proof",
            "revision": 1, "identitySpace": "temporal-demo",
            "planningScale": "module", "rootRequirementId": "R0",
            "actionModel": "candidate-v6",
            "nodes": [{"id": "R0", "kind": "requirement", "title": "Synthetic root",
                       "status": "active"}],
            "edges": [], "events": []
        }
        write_package({"schemaVersion": 1, "transactionId": "T1-create",
                       "changes": [{"file": REL, "create": initial}]}, author)
        actions = [
            {"op": "add_action", "requirementId": "R0", "action": {
                "id": ident, "kind": "action", "title": "Alternative " + ident,
                "status": "candidate", "qrpe": [],
                "canonBlock": {"recommended": [
                    {"id": "C-" + ident, "text": "Synthetic canon requires review"}],
                    "contraindicated": []}}}
            for ident in ("A1", "A2")
        ]
        write_package(graph_package(actions, 1, "T1-candidates"), author)
        selected = {"op": "select_action", "actionId": "A1",
                    "event": {"id": "EV-T1", "type": "action_selected",
                              "actionId": "A1", "driverRequirementId": "R0",
                              "by": "assistant",
                              "note": "Synthetic bearer-granted selection, NOT user approval"}}
        denial = write_package(graph_package([selected], 2, "T1-denied"), author, False)
        require("AUTH_MISSING_PERMISSION: graph.select_action" in denial.stderr,
                "T1_AUTH_SEPARATION_NOT_VERIFIED")
        require(snapshot(graph_path)["revision"] == 2 and
                snapshot(graph_path)["events"] == [],
                "DENIED_T1_CHANGED_GRAPH")
        write_package(graph_package([selected], 2, "T1-selected"), selector)
        t1_graph = snapshot(graph_path)
        require(t1_graph["revision"] == 3, "T1_REVISION")
        selected_action = next(n for n in t1_graph["nodes"] if n["id"] == "A1")
        require(selected_action["status"] == "selected" and
                len(t1_graph["events"]) == 1 and
                t1_graph["events"][0]["type"] == "action_selected" and
                t1_graph["events"][0]["verifiedTrustReceipt"]["mode"] == "bearer",
                "T1_EVENT_AND_INTERNAL_RECEIPT_MISSING")
        require(selected_action["selectionBasis"]["actionSnapshot"]["status"] ==
                "candidate", "T1_HISTORICAL_ACTION_SNAPSHOT_WRONG")
        t1_event = copy.deepcopy(t1_graph["events"][0])
        t1_basis = copy.deepcopy(selected_action["selectionBasis"])
        t1_sha = hashlib.sha256(graph_path.read_bytes()).hexdigest()

        def confirm_t1():
            current = snapshot(graph_path)
            act = next(n for n in current["nodes"] if n["id"] == "A1")
            alt = next(n for n in current["nodes"] if n["id"] == "A2")
            require(current["events"] == [t1_event] and
                    act["status"] == "selected" and
                    act["selectionBasis"] == t1_basis and
                    alt["status"] == "candidate" and
                    not any(e.get("type") == "action_reconsidered" for e in current["events"]),
                    "T1_CHANGED_OR_DECISION_SILENTLY_REVISED")
            return current

        # Generic event injection cannot bypass the dedicated selection path,
        # even with a broad opt-in bearer graph.write grant.
        before_injection = graph_path.read_bytes()
        tamper = {"op": "append_event", "event": {
            "id": "EV-FORGE", "type": "action_selected",
            "actionId": "A2", "driverRequirementId": "R0",
            "by": "assistant", "note": "Forbidden generic event"}}
        blocked = write_package(graph_package([tamper], 3, "T1-forged-event"),
                                misc_writer, False)
        require("AUTH_SELECTION_EVENT_REQUIRES_DEDICATED_OPERATION" in blocked.stderr and
                graph_path.read_bytes() == before_injection,
                "T1_EVENT_INJECTION_NOT_DENIED")

        plan_file = workspace / "plan.json"
        plan = snapshot(ROOT / "docs/examples/temporal-plan-candidate-v1.json")
        for step in plan["steps"]:
            if step["kind"] == "action":
                step["actionRef"]["observedGraphRevision"] = 3
        save(plan_file, plan)
        project = workspace / "gendocen"
        (project / "docs/_structured/rdg").mkdir(parents=True)
        (project / "docs/review").mkdir(parents=True)
        (project / "docengine_project").mkdir(parents=True)
        (project / "docengine.toml").write_text(
            '[docengine]\nconfig_version = 1\n'
            'documentation_root = "docs"\nstructured_dir = "_structured"\n'
            'dependency_dir = "_dependency"\nproject_package = "docengine_project"\n',
            encoding="utf8")
        gproj = project / "docs/_structured/rdg/graph.json"
        pproj = project / "docs/_structured/rdg/plan.json"

        def project_graph():
            save(gproj, ADAPTER.graph_resource(graph_path, REL))

        def project_plan():
            save(plan_file, plan)
            save(pproj, ADAPTER.plan_resource(plan_file))

        project_graph()
        project_plan()
        graph_uri, plan_uri = uri(snapshot(gproj)), uri(snapshot(pproj))
        registration = ADAPTER.DEPENDENCIES.project_config(
            "_structured/rdg/graph.json", "_structured/rdg/plan.json",
            [("A1", "S-A1"), ("A2", "S-A2")], "synthetic-t1-review")
        (project / "docengine_project/__init__.py").write_text(
            registration, encoding="utf8")
        docs = {}
        for aid in ("A1", "A2"):
            docs[aid] = project / ("docs/review/" + aid + ".md")
            docs[aid].write_text("# T1 synthetic review " + aid +
                                 "\n\nNot user-approved.\n", encoding="utf8")
        prose = {aid: path.read_bytes() for aid, path in docs.items()}
        genenv = {**os.environ, "PYTHONPATH": str(source),
                  "PYTHONDONTWRITEBYTECODE": "1"}

        def cli(*args, extra_env=None):
            proc = subprocess.run(
                [sys.executable, "-m", "docengine.cli", *args,
                 "--project-root", str(project), "--json"],
                capture_output=True, text=True,
                env={**genenv, **(extra_env or {})})
            require(bool(proc.stdout.strip()), "GENDOCEN_NO_JSON_" + proc.stderr)
            body = json.loads(proc.stdout)
            require(body["meta"]["engine_version"] == "0.1.0.dev25",
                    "GENDOCEN_WRONG_VERSION")
            return proc.returncode, body

        def status_expect(expected, label):
            _, state = cli("check")
            rows = {entry["target"].rsplit("/", 1)[-1][:-3]: entry["status"]
                    for entry in state["data"]["results"]}
            require(rows == expected, label + "_" + str(rows))
            for aid, path in docs.items():
                require(path.read_bytes() == prose[aid],
                        "GENDOCEN_REWROTE_MARKDOWN_" + aid)

        def context(aid):
            _, packet = cli("explain", "file://review/" + aid + ".md")
            return packet["data"]["review_context_id"]

        def validate(aid):
            code, response = cli(
                "validate", "file://review/" + aid + ".md", "--result",
                "still-valid", "--reason", "Synthetic test, NOT authenticated approval",
                "--review-context", context(aid))
            require(code == 0 and response["ok"], "GENDOCEN_VALIDATION_FAILED")

        cli("sync")
        validate("A1")
        validate("A2")
        status_expect({"A1": "valid", "A2": "valid"}, "INITIAL_BASELINE")
        confirm_t1()

        finding = {
            "id": "F-R-POST-T1", "text": "Potential schedule risk discovered after T1",
            "status": "open", "findingType": "F-R", "findingScope": "UPSTREAM",
            "questions": ["Is the assumed Plan deadline a real constraint?"],
            "evidenceRefs": [], "proposalRefs": [],
            "temporalContext": {
                "planId": plan["id"], "planRevision": plan["revision"],
                "stepId": "S-A1", "branchId": "B-RESULT", "outcome": "positive",
                "dependencyDigest": "a" * 64, "status": "candidate"}
        }
        write_package(graph_package([{"op": "append_finding",
                                     "targetId": "A1", "finding": finding}],
                                    3, "post-T1-FR"), finding_writer)
        require(confirm_t1()["revision"] == 4, "POST_T1_FINDING_REVISION")
        project_graph()
        status_expect({"A1": "review_required", "A2": "valid"},
                      "LATER_T2_QRPE_FINDING")
        validate("A1")
        status_expect({"A1": "valid", "A2": "valid"}, "T2_REVIEWED")
        pre_t3_context = context("A1")

        transition = {
            "op": "transition_qrpe", "targetId": "A1", "issueId": finding["id"],
            "transition": {"id": "QRPE-T3", "recordedAt": "2026-10-18",
                           "status": "resolved",
                           "note": "Synthetic later investigation, NOT attested event"}
        }
        write_package(graph_package([transition], 4, "post-T1-QRPE-T3"),
                      finding_writer)
        graph_t3 = confirm_t1()
        require(graph_t3["revision"] == 5, "QRPE_T3_REVISION")
        qrpe = next(n for n in graph_t3["nodes"] if n["id"] == "A1")["qrpe"]
        require(len(qrpe) == 1 and qrpe[0]["status"] == "resolved" and
                qrpe[0]["statusHistory"][-1]["id"] == "QRPE-T3" and
                qrpe[0]["statusHistory"][-1]["verifiedTrustReceipt"]["mode"] ==
                "bearer", "T3_QRPE_HISTORY_NOT_RECORDED")
        project_graph()
        status_expect({"A1": "review_required", "A2": "valid"},
                      "LATER_T3_QRPE_TRANSITION")
        stale_state = (project / "docs/_dependency/state/dependency_state.json").read_bytes()
        stale_receipts = {
            q.name: q.read_bytes()
            for q in (project / "docs/_dependency/receipts").glob("receipt-*.json")}
        denied_code, stale_result = cli(
            "validate", "file://review/A1.md", "--result", "still-valid",
            "--reason", "Synthetic outdated assessment",
            "--review-context", pre_t3_context)
        require(denied_code != 0 and
                stale_result["meta"]["status"] == "validation_failed" and
                "stale" in json.dumps(stale_result).lower() and
                (project / "docs/_dependency/state/dependency_state.json").read_bytes() ==
                stale_state and
                {q.name: q.read_bytes() for q in
                 (project / "docs/_dependency/receipts").glob("receipt-*.json")} ==
                stale_receipts, "T3_ACCEPTED_STALE_T2_REVIEW")
        confirm_t1()

        dep = project / "docs/_dependency"
        state = dep / "state/dependency_state.json"
        events = dep / "events/dependency_events.jsonl"
        receipts = dep / "receipts"
        before_state, before_events = state.read_bytes(), events.read_bytes()
        before_receipts = {p.name: p.read_bytes()
                           for p in receipts.glob("receipt-*.json")}
        before_graph, before_plan = graph_path.read_bytes(), plan_file.read_bytes()
        t3_history_code, t3_history = cli("history", "file://review/A1.md")
        require(t3_history_code == 0, "HISTORY_T3_READ_FAILED")

        proc = subprocess.run(
            [sys.executable, "-m", "docengine.cli",
             "validate", "file://review/A1.md", "--result", "still-valid",
             "--reason", "Injected interruption only",
             "--review-context", context("A1"),
             "--project-root", str(project), "--json"],
            text=True, capture_output=True,
            env={**genenv, "DOCENGINE_TEST_CRASH_AFTER_WRITES": "1"})
        require(proc.returncode == 91, "EXPECTED_CRASH_91_" + str(proc.returncode))
        code, halted = cli("status")
        require(code != 0 and halted["meta"]["status"] == "recovery_required",
                "CRASH_DID_NOT_BLOCK_STATUS")
        code, verified = cli("verify")
        require(code != 0 and verified["meta"]["status"] == "verification_failed" and
                any(f.get("code") == "recovery_required" for f in
                    verified["data"]["report"]["findings"]),
                "CRASH_NOT_DETECTED_BY_VERIFY")
        code, restored = cli("recover")
        require(code == 0 and restored["ok"] and
                restored["data"]["remaining"] == 0, "RECOVERY_FAILED")
        require(state.read_bytes() == before_state and
                events.read_bytes() == before_events and
                {p.name: p.read_bytes() for p in receipts.glob("receipt-*.json")} ==
                before_receipts, "ROLLBACK_CHANGED_PRECRASH_DEPENDENCY_HISTORY")
        require(graph_path.read_bytes() == before_graph and
                plan_file.read_bytes() == before_plan,
                "RECOVERY_CHANGED_CANONICAL_GRAPH_OR_PLAN")
        confirm_t1()
        _, after_history = cli("history", "file://review/A1.md")
        require(after_history["data"] == t3_history["data"],
                "CRASH_REWROTE_PUBLIC_HISTORY")
        status_expect({"A1": "review_required", "A2": "valid"},
                      "CRASH_RECOVERY_PRESERVES_PENDING_REVIEW")
        validate("A1")
        status_expect({"A1": "valid", "A2": "valid"}, "POST_RECOVERY_FRESH_REVIEW")
        confirm_t1()

        # Even though A1 is selected at T1, the Temporal Plan still owns
        # conditional possibilities independently. A branch-only A2 change
        # must never force A1 to be selected again or invalidate A1's review.
        plan["revision"] += 1
        plan["timeConstraints"].append({
            "stepId": "S-A2", "type": "notBefore", "at": "2026-11-15",
            "strength": "hypothetical", "basis": "Synthetic alternative constraint"})
        project_plan()
        status_expect({"A1": "valid", "A2": "review_required"},
                      "POST_T1_A2_ALTERNATIVE_ONLY")
        confirm_t1()
        validate("A2")
        status_expect({"A1": "valid", "A2": "valid"},
                      "A2_ALTERNATIVE_REVIEWED")
        plan["revision"] += 1
        for rule in plan["timeConstraints"]:
            if rule["stepId"] == "S-DELIVERY" and rule["type"] == "deadline":
                rule["at"] = "2026-11-17"
        project_plan()
        status_expect({"A1": "review_required", "A2": "review_required"},
                      "LATER_PLAN_SHARED_DEADLINE")
        confirm_t1()
        require(snapshot(graph_path)["revision"] == 5 and
                hashlib.sha256(graph_path.read_bytes()).hexdigest() != t1_sha,
                "MISSING_LATER_REVISIONS")

        result = {
            "status": "PASS", "engine": "Gendocen 0.1.0.dev25",
            "syntheticWriter": "real isolated graph-apply.py bearer package",
            "T1Event": t1_event["id"], "T1RecordedBy": "assistant bearer",
            "T1GraphRevision": 3, "afterFindingRevision": 4,
            "afterQrpeTransitionRevision": 5,
            "originalSelectionBasisPreserved": True,
            "originalSelectionEventPreserved": True,
            "genericSelectionEventInjectionDenied": True,
            "authorCannotSelect": True,
            "laterFinding": "F-R (research risk), not F-P",
            "laterQrpeTransition": "resolved (technical bearer receipt)",
            "actualExternalT2T3EventsAttested": False,
            "T2FindingReview": {"A1": "review_required", "A2": "valid"},
            "T3TransitionReview": {"A1": "review_required", "A2": "valid"},
            "staleT2ReviewAfterT3Rejected": True,
            "postCrashReviewRequired": {"A1": "review_required", "A2": "valid"},
            "A2AlternativeAfterSelectedT1": {"A1": "valid", "A2": "review_required"},
            "sharedDeadlineReview": {"A1": "review_required", "A2": "review_required"},
            "injectedCrashCode": 91, "recoveredPreCrashHistory": True,
            "recoveryPreservedHistoricalT1": True,
            "historyA1ReceiptsBeforeCrash": len(t3_history["data"]["receipt_ids"]),
            "realUserIdentityVerified": False,
            "actualRealWorldProblemVerified": False,
            "productionStage4Accepted": False,
            "temporarySourcesOnly": True,
        }
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engine-source", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(run(args.engine_source), ensure_ascii=False,
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

