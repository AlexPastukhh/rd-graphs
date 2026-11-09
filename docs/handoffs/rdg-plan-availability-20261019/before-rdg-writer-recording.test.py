#!/usr/bin/env python3
"""Real Graph package journal timestamp, crash recovery and knownAt cutoffs."""
import datetime as dt
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = SourceFileLoader("recording_bearer_fixture", str(ROOT / "tests/rdg-bearer-package.integration.test.py")).load_module()
HISTORY = SourceFileLoader("recording_exact_history", str(ROOT / "tools/rdg-exact-history.py")).load_module()
OWNER = HISTORY.OWNER
REL = "workspaces/demo/graph.json"
PLANREL = "plans/demo/plan.json"


class WriterRecordingTest(unittest.TestCase):
    def setUp(self):
        self.writer = BASE.BearerPackage(methodName="test_create_candidate_only_including_legacy")
        self.writer.setUp()
        self.addCleanup(self.writer.tearDown)
        self.grant = self.writer.grant(["graph.create", "graph.add_action"])

    def journal(self, tx):
        return self.writer.home / "graphs/workspaces/.transactions" / (tx + ".json")

    def test_prepared_time_survives_crash_and_exact_cutoff(self):
        package = self.writer.create(tid="commit-create")
        payload = self.writer.home / "prepared-input.json"
        payload.write_text(json.dumps(package))
        script = """import json,os,sys
from importlib.machinery import SourceFileLoader
m=SourceFileLoader('writer_under_crash',sys.argv[1]).load_module()
m.finish=lambda *args: os._exit(91)
m.execute(json.load(open(sys.argv[2])))
"""
        crashed = subprocess.run([sys.executable, "-c", script,
                str(self.writer.home / "tools/graph-package.py"), str(payload)],
                capture_output=True, text=True,
                env={**self.writer.env, "RDG_AUTH_TOKEN": self.grant["token"]})
        self.assertEqual(crashed.returncode, 91, crashed.stderr)
        pending = json.loads(self.journal("commit-create").read_text())
        self.assertEqual(pending["schemaVersion"], 2)
        self.assertEqual(pending["state"], "prepared")
        prepared_time = pending["preparedAt"]
        self.assertIsNone(pending["recordedAt"])
        self.assertIsNone(pending["records"][0]["before"])
        self.assertFalse(self.writer.path.exists())
        self.writer.assert_ok(self.writer.write(
            self.writer.patch([self.writer.action()], 1, "commit-add"), self.grant["token"]))
        recovered = json.loads(self.journal("commit-create").read_text())
        added = json.loads(self.journal("commit-add").read_text())
        self.assertEqual(recovered["state"], "completed")
        self.assertEqual(recovered["preparedAt"], prepared_time)
        self.assertGreaterEqual(OWNER.instant(recovered["recordedAt"]), OWNER.instant(prepared_time))
        self.assertEqual(added["schemaVersion"], 2)
        self.assertGreaterEqual(OWNER.instant(added["recordedAt"]), OWNER.instant(prepared_time))
        graph = json.loads(self.writer.path.read_text())
        self.assertEqual(graph["revision"], 2)
        # Replaying an older transaction after a later graph revision is
        # correctly denied by the existing writer; it must not retime it.
        self.writer.assert_denied(self.writer.write(package, self.grant["token"]),
                                  "REPLAY_STATE_CHANGED")
        self.assertEqual(json.loads(self.journal("commit-create").read_text())["recordedAt"],
                         recovered["recordedAt"])

        store = self.writer.home / "plan-auth.json"
        auth = OWNER.AUTH.Authority(store)
        admin = auth.init_local(plan_capable=True)["token"]
        def issue(perms):
            return auth.manage("issue", admin, {"permissions": perms,
                    "scopes": [PLANREL, REL]})["token"]
        plan = json.loads((ROOT / "docs/examples/temporal-plan-candidate-v1.json").read_text())
        plan["identitySpace"] = "demo"
        for step in plan["steps"]:
            if step["kind"] == "action":
                step["actionRef"].update(graphFile=REL, identitySpace="demo",
                                         observedGraphRevision=2)
        plan_root = self.writer.home / "plan-owner"
        plan_root.mkdir()
        OWNER.apply_request(plan_root, store, issue(["plan.create", "plan.branch"]), {
            "transactionId": "candidate-r1", "op": "create", "file": PLANREL,
            "expectedRevision": 0, "plan": plan})
        meta = OWNER.read_snapshot(plan_root, PLANREL, 1)["provenance"]
        next_plan = json.loads(json.dumps(plan))
        next_plan["revision"] = 2
        OWNER.apply_request(plan_root, store, issue(["plan.edit"]), {
            "transactionId": "candidate-r2", "op": "edit", "file": PLANREL,
            "expectedRevision": 1, "plan": next_plan})
        plan_bound = OWNER.read_snapshot(plan_root, PLANREL, 2)["provenance"]["recordedAt"]
        query = {"schemaVersion": 1, "mode": "exact-reference", "lifecycle": "candidate",
                 "plan": {"file": PLANREL, "identitySpace": "demo", "planId": plan["id"],
                          "revision": 1, "snapshotSHA256": meta["snapshotSHA256"],
                          "recordDigest": meta["recordDigest"]},
                 "graphs": [{"graphFile": REL, "identitySpace": "demo", "revision": 2,
                             "snapshotSHA256": OWNER.digest(graph)}],
                 "scenario": {"branchId": "B-RESULT", "outcome": "positive"},
                 "knownAt": (max(OWNER.instant(plan_bound),
                           OWNER.instant(added["recordedAt"])) + dt.timedelta(seconds=1)).isoformat()}
        resolved = HISTORY.resolve(plan_root, self.writer.home / "graphs", store,
                                   issue(["plan.read", "graph.read"]), query)
        self.assertTrue(resolved["provenance"]["recordingCutoffVerified"])
        self.assertFalse(resolved["provenance"]["twoTimeAsOfResolved"])
        self.assertEqual(resolved["graphSnapshots"][0]["provenance"]["recordedAt"],
                         added["recordedAt"])

    def test_clock_regression_does_not_create_new_journal(self):
        self.writer.assert_ok(self.writer.write(self.writer.create(tid="clock-base"),
                                                self.grant["token"]))
        base = self.journal("clock-base")
        content = json.loads(base.read_text())
        content["recordedAt"] = "2999-01-01T00:00:00+00:00"
        base.write_text(json.dumps(content))
        result = self.writer.write(self.writer.patch([self.writer.action()], 1,
                                                          "clock-regression"), self.grant["token"])
        self.writer.assert_denied(result, "WRITER_CLOCK_REGRESSION")
        self.assertFalse(self.journal("clock-regression").exists())
        self.assertEqual(json.loads(self.writer.path.read_text())["revision"], 1)


if __name__ == "__main__":
    unittest.main()
