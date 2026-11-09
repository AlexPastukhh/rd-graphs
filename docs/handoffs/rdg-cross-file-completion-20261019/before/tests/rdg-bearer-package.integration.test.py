#!/usr/bin/env python3
"""Isolated writer integration contract for RDG bearer authority."""
import importlib.machinery
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NAMES = ("rdg-authority.py graph-package.py graph-apply.py graph-index.py "
         "rdg-v7-model.py rdg-v6-action-reconsider.py rdg-v6-action-trust.py "
         "rdg-state.py rdg-state.js rdg-state-cli.cjs rdg-catalog.py "
         "rdg-catalog.js rdg-graph-api.py").split()

class BearerPackage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdg-authority-writer-")
        self.home = pathlib.Path(self.temp.name)
        (self.home / "tools").mkdir()
        for filename in NAMES:
            shutil.copy2(ROOT / "tools" / filename, self.home / "tools" / filename)
        self.store = self.home / "grants.json"
        self.rel = "workspaces/demo/graph.json"
        self.path = self.home / "graphs" / self.rel
        self.env = {**os.environ, "RDG_AUTH_STORE": str(self.store),
                    "PYTHONDONTWRITEBYTECODE": "1"}
        self.env.pop("RDG_V6_TRUST_KEY", None)
        self.owner = json.loads(self.admin("init").stdout)["token"]
        self.graph = {"schemaVersion": 1, "revision": 1, "id": "demo",
                      "title": "Demo", "planningScale": "module", "identitySpace": "demo",
                      "rootRequirementId": "R0", "actionModel": "candidate-v6",
                      "nodes": [{"id": "R0", "kind": "requirement",
                                 "title": "Root", "status": "active"}],
                      "edges": [], "events": []}
    def tearDown(self):
        self.temp.cleanup()
    def admin(self, command, payload=None, token=None):
        result = subprocess.run(
            ["python3", str(self.home / "tools/rdg-authority.py"), command,
             "--store", str(self.store)], input=json.dumps(payload) if payload else "",
            text=True, capture_output=True,
            env={**self.env, "RDG_AUTH_TOKEN": token or ""})
        if command == "init" or (token and command in ("issue", "amend", "revoke")):
            self.assertEqual(result.returncode, 0, result.stderr)
        return result
    def grant(self, permissions, scopes=None):
        return json.loads(self.admin("issue", {
            "permissions": permissions, "scopes": scopes or [self.rel]}, self.owner).stdout)
    def create(self, graph=None, tid="create"):
        return {"schemaVersion": 1, "transactionId": tid,
                "changes": [{"file": self.rel, "create": graph or self.graph}]}
    def patch(self, operations, revision, tid):
        return {"schemaVersion": 1, "transactionId": tid,
                "changes": [{"file": self.rel, "patch": {
                    "schemaVersion": 1, "expectedRevision": revision, "operations": operations}}]}
    def write(self, package, token):
        inp = self.home / "package.json"
        inp.write_text(json.dumps(package), encoding="utf8")
        return subprocess.run(["python3", str(self.home / "tools/graph-apply.py"),
                               "--package", "--patch", str(inp)], capture_output=True,
                              text=True, env={**self.env, "RDG_AUTH_TOKEN": token})
    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
    def assert_denied(self, result, reason):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(reason, result.stderr)
    @staticmethod
    def action():
        return {"op": "add_action", "requirementId": "R0",
                "action": {"id": "A1", "kind": "action", "title": "Candidate",
                           "status": "candidate"}}
    @staticmethod
    def select(by="assistant"):
        return {"op": "select_action", "actionId": "A1",
                "event": {"id": "E1", "type": "action_selected", "actionId": "A1",
                          "driverRequirementId": "R0", "by": by, "note": "Verified choice"}}
    def test_create_candidate_only_including_legacy(self):
        grant = self.grant(["graph.create"])
        legacy = dict(self.graph)
        legacy["actionModel"] = "legacy"
        legacy["nodes"] = self.graph["nodes"] + [
            {"id": "D1", "kind": "decision", "title": "Already accepted", "status": "committed"}]
        legacy["events"] = [{"id": "DE1", "type": "decision_selected",
                             "decisionId": "D1", "by": "assistant", "note": "selection"}]
        self.assert_denied(self.write(self.create(legacy, "legacy"), grant["token"]),
                           "AUTH_CREATE_CANDIDATES_ONLY")
        self.assertFalse(self.path.exists())
        selected = dict(self.graph)
        selected["nodes"] = self.graph["nodes"] + [
            {"id": "A1", "kind": "action", "title": "Selected", "status": "selected"}]
        self.assert_denied(self.write(self.create(selected, "selected"), grant["token"]),
                           "AUTH_CREATE_CANDIDATES_ONLY")
        self.assertFalse(self.path.exists())
        self.assert_ok(self.write(self.create(), grant["token"]))
    def test_author_and_selector_are_distinct_and_receipt_is_internal(self):
        g = self.grant(["graph.create", "graph.add_action"])
        self.assert_ok(self.write(self.create(), g["token"]))
        self.assert_ok(self.write(self.patch([self.action()], 1, "add"), g["token"]))
        before = self.path.read_bytes()
        denied = self.write(self.patch([self.select()], 2, "denied"), g["token"])
        self.assert_denied(denied, "AUTH_MISSING_PERMISSION: graph.select_action")
        self.assertIn("file=workspaces/demo/graph.json", denied.stderr)
        self.assertEqual(before, self.path.read_bytes())
        self.admin("amend", {"id": g["id"], "grant": {
            "permissions": ["graph.create", "graph.add_action", "graph.select_action"],
            "scopes": [self.rel]}}, self.owner)
        self.assert_ok(self.write(self.patch([self.select()], 2, "selected"), g["token"]))
        data = json.loads(self.path.read_text())
        self.assertEqual(next(n for n in data["nodes"] if n["id"] == "A1")["status"], "selected")
        receipt = data["events"][-1]["verifiedTrustReceipt"]
        self.assertEqual(receipt["mode"], "bearer")
        self.assertEqual(receipt["grantId"], g["id"])
        self.assertNotIn("signature", receipt)
        self.assertNotIn(g["token"], self.path.read_text())
    def test_legacy_option_selection_uses_separate_permission_and_internal_receipt(self):
        graph = dict(self.graph)
        graph.pop("actionModel")
        g = self.grant(["graph.create", "graph.add_option"])
        self.assert_ok(self.write(self.create(graph), g["token"]))
        add = {"op": "add_option", "requirementId": "R0",
               "option": {"id": "O1", "kind": "option", "title": "Candidate",
                          "origin": "situational", "status": "candidate",
                          "canonBlock": {"recommended": [], "contraindicated": []}}}
        self.assert_ok(self.write(self.patch([add], 1, "legacy-option"), g["token"]))
        select = {"op": "select_option", "optionId": "O1", "driverId": "R0",
                  "decision": {"id": "D1", "kind": "decision", "title": "Chosen", "status": "committed"},
                  "event": {"id": "EV-D1", "type": "decision_selected", "decisionId": "D1",
                            "by": "assistant", "note": "Chosen with delegated permission"}}
        before = self.path.read_bytes()
        self.assert_denied(self.write(self.patch([select], 2, "legacy-denied"), g["token"]),
                           "AUTH_MISSING_PERMISSION: graph.select_option")
        self.assertEqual(before, self.path.read_bytes())
        self.admin("amend", {"id": g["id"], "grant": {
            "permissions": ["graph.create", "graph.add_option", "graph.select_option"],
            "scopes": [self.rel]}}, self.owner)
        self.assert_ok(self.write(self.patch([select], 2, "legacy-chosen"), g["token"]))
        data = json.loads(self.path.read_text())
        self.assertEqual(next(n for n in data["nodes"] if n["id"] == "D1")["status"], "committed")
        receipt = data["events"][-1]["verifiedTrustReceipt"]
        self.assertEqual(receipt["mode"], "bearer")
        self.assertEqual(receipt["grantId"], g["id"])

    def test_user_claim_cannot_be_forged_by_bearer(self):
        grant = self.grant(["graph.write"])
        self.assert_ok(self.write(self.create(), grant["token"]))
        self.assert_ok(self.write(self.patch([self.action()], 1, "add"), grant["token"]))
        before = self.path.read_bytes()
        self.assert_denied(self.write(self.patch([self.select("user")], 2, "forged"),
                                      grant["token"]), "BEARER_CANNOT_CLAIM_USER_IDENTITY")
        self.assertEqual(before, self.path.read_bytes())
    def test_generic_node_and_event_operations_cannot_commit_a_decision(self):
        g = self.grant(["graph.write"])
        self.assert_ok(self.write(self.create(), g["token"]))
        before = self.path.read_bytes()
        committed = {"op": "add_node", "node": {"id": "D1", "kind": "decision",
                     "title": "Accepted", "status": "committed"}}
        self.assert_denied(self.write(self.patch([committed], 1, "smuggle-node"),
                                      g["token"]), "AUTH_CANDIDATE_MUTATION_ONLY")
        event = {"op": "append_event", "event": {"id": "E2",
                 "type": "decision_selected", "decisionId": "D1",
                 "by": "assistant", "note": "Forged selection"}}
        self.assert_denied(self.write(self.patch([event], 1, "smuggle-event"),
                                      g["token"]), "AUTH_SELECTION_EVENT_REQUIRES_DEDICATED_OPERATION")
        self.assertEqual(before, self.path.read_bytes())

    @staticmethod
    def typed_finding(kind="F-R"):
        item = {"id": "F-1", "text": "Review possible future delivery constraint",
                "status": "open", "findingType": kind, "findingScope": "UPSTREAM",
                "questions": ["Is the future plan deadline an actual commitment?"],
                "evidenceRefs": [], "proposalRefs": [],
                "temporalContext": {
                    "planId": "P-DEMO", "planRevision": 1, "stepId": "S-A1",
                    "branchId": "B-RESULT", "outcome": "positive",
                    "dependencyDigest": "a"*64, "status": "candidate"}}
        if kind == "F-U":
            item["alternatives"] = ["A1", "A2"]
        return item

    def test_finding_requires_separate_grant_and_is_qrpe_not_a_second_registry(self):
        g = self.grant(["graph.create", "graph.append_qrpe"])
        self.assert_ok(self.write(self.create(), g["token"]))
        finding = self.typed_finding()
        proposed = {"op": "append_finding", "targetId": "R0", "finding": finding}
        original = self.path.read_bytes()
        self.assert_denied(self.write(self.patch([proposed], 1, "finding-denied"), g["token"]),
                           "AUTH_MISSING_PERMISSION: graph.append_finding")
        self.assertEqual(original, self.path.read_bytes())
        bypass = {"op": "append_qrpe", "targetId": "R0", "issue": finding}
        self.assert_denied(self.write(self.patch([bypass], 1, "qrpe-bypass"), g["token"]),
                           "typed Finding needs append_finding")
        self.assertEqual(original, self.path.read_bytes())
        self.admin("amend", {"id": g["id"], "grant": {
            "permissions": ["graph.create", "graph.append_qrpe", "graph.append_finding"],
            "scopes": [self.rel]}}, self.owner)
        self.assert_ok(self.write(self.patch([proposed], 1, "finding-accepted"), g["token"]))
        graph = json.loads(self.path.read_text())
        self.assertEqual(graph["nodes"][0]["qrpe"][0], finding)
        self.assertEqual(graph["revision"], 2)
        self.assertNotIn("findings", graph)

    def test_unverified_problem_and_invalid_uncertainty_are_rejected_without_write(self):
        g = self.grant(["graph.create", "graph.append_finding"])
        self.assert_ok(self.write(self.create(), g["token"]))
        before = self.path.read_bytes()
        problem = {"op": "append_finding", "targetId": "R0",
                   "finding": self.typed_finding("F-P")}
        self.assert_denied(self.write(self.patch([problem], 1, "unverified-problem"), g["token"]),
                           "F-P requires independently verified")
        uncertain = self.typed_finding("F-U")
        uncertain["alternatives"] = ["A1", "A1"]
        self.assert_denied(self.write(self.patch([{"op": "append_finding",
            "targetId": "R0", "finding": uncertain}], 1, "bad-alternatives"), g["token"]),
                           "at least two distinguishable alternatives")
        self.assertEqual(before, self.path.read_bytes())

    def test_uncertainty_finding_reuses_existing_qrpe_transition_history(self):
        g = self.grant(["graph.create", "graph.append_finding", "graph.transition_qrpe"])
        self.assert_ok(self.write(self.create(), g["token"]))
        item = self.typed_finding("F-U")
        self.assert_ok(self.write(self.patch([{"op": "append_finding",
            "targetId": "R0", "finding": item}], 1, "uncertainty"), g["token"]))
        transition = {"op": "transition_qrpe", "targetId": "R0", "issueId": "F-1",
            "transition": {"id": "F-1-REVIEW", "recordedAt": "2026-10-18",
                           "status": "resolved", "note": "Alternatives evaluated"}}
        self.assert_ok(self.write(self.patch([transition], 2, "finding-review"), g["token"]))
        graph = json.loads(self.path.read_text())
        finding = graph["nodes"][0]["qrpe"][0]
        self.assertEqual(finding["status"], "resolved")
        self.assertEqual(finding["findingType"], "F-U")
        self.assertEqual(finding["alternatives"], ["A1", "A2"])
        self.assertEqual(finding["statusHistory"][-1]["id"], "F-1-REVIEW")
        self.assertEqual(finding["statusHistory"][-1]["verifiedTrustReceipt"]["mode"], "bearer")
        self.assertEqual(graph["events"], [])

    def test_findings_on_selected_action_do_not_rewrite_T1_or_accept_proposal(self):
        g = self.grant(["graph.write"])
        self.assert_ok(self.write(self.create(), g["token"]))
        self.assert_ok(self.write(self.patch([self.action()], 1, "add-a1"), g["token"]))
        self.assert_ok(self.write(self.patch([self.select()], 2, "select-a1"), g["token"]))
        selected_before = json.loads(self.path.read_text())
        basis = next(n for n in selected_before["nodes"] if n["id"] == "A1")["selectionBasis"]
        finding = self.typed_finding("F-O")
        self.assert_ok(self.write(self.patch([{"op": "append_finding",
            "targetId": "A1", "finding": finding}], 3, "finding-after-T1"), g["token"]))
        selected_after = json.loads(self.path.read_text())
        action = next(n for n in selected_after["nodes"] if n["id"] == "A1")
        self.assertEqual(action["status"], "selected")
        self.assertEqual(action["selectionBasis"], basis)
        self.assertEqual(action["qrpe"][-1]["findingType"], "F-O")
        self.assertEqual(selected_before["events"], selected_after["events"])
        self.assertNotIn("proposals", selected_after)

    def test_mixed_scope_denied_without_partial_graph(self):
        grant = self.grant(["graph.create"])
        request = self.create()
        request["changes"].append({"file": "workspaces/other/graph.json", "create": {
            **self.graph, "id": "other", "identitySpace": "other"}})
        self.assert_denied(self.write(request, grant["token"]), "AUTH_SCOPE_DENIED")
        self.assertFalse(self.path.exists())
    def test_revoke_between_prepare_and_commit_prevents_write(self):
        g = self.grant(["graph.create"])
        package_file = self.home / "request.json"
        package_file.write_text(json.dumps(self.create()))
        code = """
import importlib.machinery, json, os
from pathlib import Path
root = Path(os.environ["RDG_TEST_HOME"])
writer = importlib.machinery.SourceFileLoader("writer", str(root/"tools/graph-package.py")).load_module()
authority = importlib.machinery.SourceFileLoader("authority", str(root/"tools/rdg-authority.py")).load_module()
real_prepare = writer.prepare
def between(pkg):
    records = real_prepare(pkg)
    authority.Authority(os.environ["RDG_AUTH_STORE"]).manage(
        "revoke", os.environ["RDG_TEST_OWNER"], {"id": os.environ["RDG_TEST_GRANT"]})
    return records
writer.prepare = between
writer.execute(json.loads((root/"request.json").read_text()))
"""
        r = subprocess.run(["python3", "-c", code], capture_output=True, text=True,
            env={**self.env, "RDG_AUTH_TOKEN": g["token"],
                 "RDG_TEST_HOME": str(self.home), "RDG_TEST_OWNER": self.owner,
                 "RDG_TEST_GRANT": g["id"]})
        self.assert_denied(r, "AUTH_TOKEN_REVOKED")
        self.assertFalse(self.path.exists())
        self.assertFalse((self.home/"graphs/workspaces/.transactions/create.json").exists())
    def test_revoke_waits_for_durable_commit_boundary(self):
        """Two processes: revocation cannot overtake an accepted journal."""
        import time
        g = self.grant(["graph.create"])
        request = self.create()
        (self.home / "race2.json").write_text(json.dumps(request))
        ready, release = self.home / "journal-ready", self.home / "release-journal"
        runner = """
import importlib.machinery, json, os, time
from pathlib import Path
base = Path(os.environ["RDG_TEST_HOME"])
writer = importlib.machinery.SourceFileLoader("writer", str(base/"tools/graph-package.py")).load_module()
real_write = writer.write_json
def paused(path, obj):
    real_write(path, obj)
    if path.name == "create.json" and obj.get("state") == "prepared":
        (base/"journal-ready").write_text("ready")
        limit = time.monotonic() + 20
        while not (base/"release-journal").exists():
            if time.monotonic() > limit:
                raise RuntimeError("timed out waiting to finish accepted journal")
            time.sleep(0.02)
writer.write_json = paused
writer.execute(json.loads((base/"race2.json").read_text()))
"""
        env = {**self.env, "RDG_AUTH_TOKEN": g["token"],
               "RDG_TEST_HOME": str(self.home)}
        writer = subprocess.Popen(["python3", "-c", runner],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, env=env)
        revoker = None
        try:
            limit = time.monotonic() + 20
            while not ready.exists() and writer.poll() is None and time.monotonic() < limit:
                time.sleep(0.025)
            self.assertTrue(ready.exists(), "writer did not persist prepared journal")
            revoker = subprocess.Popen(["python3", str(self.home / "tools/rdg-authority.py"),
                                        "revoke", "--store", str(self.store)],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True,
                                       env={**self.env, "RDG_AUTH_TOKEN": self.owner})
            revoker.stdin.write(json.dumps({"id": g["id"]}))
            revoker.stdin.close()
            time.sleep(0.4)
            self.assertIsNone(revoker.poll(), "revocation overtook the writer commit lock")
        finally:
            release.write_text("go")
        out, err = writer.communicate(timeout=25)
        self.assertEqual(writer.returncode, 0, err or out)
        self.assertTrue(self.path.exists())
        if revoker is not None:
            try:
                code = revoker.wait(timeout=25)
                err = revoker.stderr.read()
                self.assertEqual(code, 0, err)
            finally:
                revoker.stdout.close()
                revoker.stderr.close()
        # Once the transaction is durably accepted, later revoke blocks replay,
        # not the recovery of already accepted writes.
        self.assert_denied(self.write(request, g["token"]), "AUTH_TOKEN_REVOKED")

    def test_revoke_blocks_replay(self):
        g = self.grant(["graph.create"])
        req = self.create()
        self.assert_ok(self.write(req, g["token"]))
        snap = self.path.read_bytes()
        self.admin("revoke", {"id": g["id"]}, self.owner)
        self.assert_denied(self.write(req, g["token"]), "AUTH_TOKEN_REVOKED")
        self.assertEqual(snap, self.path.read_bytes())

if __name__ == "__main__":
    unittest.main()
