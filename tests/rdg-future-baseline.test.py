#!/usr/bin/env python3
"""Technical accepted-future baseline, isolated rights and durable recovery."""
import copy
import datetime as dt
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = SourceFileLoader("test_future_baseline", str(ROOT / "tools/rdg-future-baseline-owner.py")).load_module()
FIXTURE = SourceFileLoader("baseline_plan_fixture", str(ROOT / "tests/rdg-temporal-plan-owner.test.py")).load_module()
PLANREL = FIXTURE.REL


class FutureBaselineTest(unittest.TestCase):
    def setUp(self):
        self.fixture = FIXTURE.PlanOwnerTest("test_create_edit_history_exact_snapshot_and_idempotency")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.apply(self.fixture.request())
        self.auth = self.fixture.auth
        self.admin = self.fixture.admin
        self.root = self.fixture.root
        self.store = self.fixture.store
        self.acceptor = self.fixture.grant(["plan.accept", "plan.read"])[1]
        self.reader = self.fixture.grant(["plan.read"])[1]
        self.pin1 = self.pin(1)

    def pin(self, revision):
        meta = BASELINE.OWNER.read_snapshot(self.root, PLANREL, revision)["provenance"]
        return {"file": PLANREL, "identitySpace": meta["identitySpace"],
                "planId": meta["planId"], "revision": revision,
                "snapshotSHA256": meta["snapshotSHA256"],
                "recordDigest": meta["recordDigest"]}

    def edit_plan(self, revision, title):
        plan = copy.deepcopy(self.fixture.plan)
        plan["revision"] = revision
        plan["title"] = title
        BASELINE.OWNER.apply_request(self.root, self.store, self.fixture.author, {
            "transactionId": "plan-r" + str(revision), "op": "edit",
            "file": PLANREL, "expectedRevision": revision-1, "plan": plan})
        return self.pin(revision)

    def request(self, tx="accept-r1", op="accept", expected=0, pin=None):
        return {"transactionId": tx, "op": op, "file": PLANREL,
                "expectedStateRevision": expected, "planPin": copy.deepcopy(pin or self.pin1),
                "basis": "synthetic technical approval"}

    def apply(self, request=None, token=None, callback=None):
        return BASELINE.apply(self.root, self.store, token or self.acceptor,
                              request or self.request(), before_prepare=callback)

    def read(self, revision=None, known=None, token=None, callback=None):
        return BASELINE.read(self.root, self.store, token or self.reader, PLANREL,
                             revision, known, before_return=callback)

    def receipt(self, revision):
        return json.loads(BASELINE.receipt_path(self.root, PLANREL, revision).read_text())

    @staticmethod
    def after(value, millis=1):
        return (BASELINE.OWNER.instant(value) +
                dt.timedelta(milliseconds=millis)).isoformat()

    def test_new_candidate_does_not_replace_accepted_exact_baseline(self):
        original = (self.root / PLANREL).read_bytes()
        self.apply()
        self.assertEqual((self.root / PLANREL).read_bytes(), original)
        accepted = self.read()
        self.assertEqual(accepted["state"], "accepted")
        self.assertEqual(accepted["planPin"], self.pin1)
        self.assertFalse(accepted["provenance"]["humanAcceptanceVerified"])
        self.assertFalse(accepted["provenance"]["actionSelected"])
        self.assertFalse(accepted["provenance"]["eventsAttested"])
        later = self.edit_plan(2, "New candidate after acceptance")
        self.assertEqual(self.read()["planPin"], self.pin1)
        self.assertEqual(self.read()["plan"]["status"], "candidate")
        self.assertEqual(BASELINE.OWNER.read_snapshot(self.root, PLANREL)["plan"]["title"],
                         "New candidate after acceptance")
        self.assertNotEqual(later, self.read()["planPin"])
        self.assertFalse((self.root / "workspaces").exists())

    def test_replace_requires_explicit_operation_and_preserves_old_baseline(self):
        self.apply()
        old = BASELINE.target_path(self.root, PLANREL).read_bytes()
        pin2 = self.edit_plan(2, "Candidate r2")
        time.sleep(0.02)
        r = self.apply(self.request("replace-r2", "replace", 1, pin2))
        self.assertEqual(r["stateRevision"], 2)
        self.assertEqual(self.read(1)["planPin"], self.pin1)
        self.assertEqual(self.read(2)["planPin"], pin2)
        records = json.loads(BASELINE.target_path(self.root, PLANREL).read_text())["records"]
        self.assertEqual(records[0], json.loads(old)["records"][0])
        self.assertEqual([x["op"] for x in records], ["accept", "replace"])
        self.assertTrue(self.apply(self.request("replace-r2", "replace", 1, pin2))["idempotent"])
        before = BASELINE.target_path(self.root, PLANREL).read_bytes()
        with self.assertRaisesRegex(ValueError, "CAS_MISMATCH"):
            self.apply(self.request("stale", "replace", 1, pin2))
        with self.assertRaisesRegex(ValueError, "TRANSACTION_REPLAY_CONFLICT"):
            other = self.request("replace-r2", "replace", 1, pin2)
            other["basis"] = "different"
            self.apply(other)
        self.assertEqual(BASELINE.target_path(self.root, PLANREL).read_bytes(), before)

    def test_known_at_preserves_old_baseline_and_withdrawal_history(self):
        self.apply()
        early = self.after(self.receipt(1)["availableBy"])
        time.sleep(0.02)
        pin2 = self.edit_plan(2, "Replacement candidate")
        self.apply(self.request("replace-r2", "replace", 1, pin2))
        self.assertLess(BASELINE.OWNER.instant(early),
                        BASELINE.OWNER.instant(self.receipt(2)["availableBy"]))
        self.assertEqual(self.read(known=early)["stateRevision"], 1)
        late = self.after(self.receipt(2)["availableBy"], 1000)
        self.assertEqual(self.read(known=late)["stateRevision"], 2)
        with self.assertRaisesRegex(ValueError, "BASELINE_NOT_PROVEN_KNOWN"):
            self.read(revision=2, known=early)
        self.apply(self.request("withdraw-r2", "withdraw", 2, pin2))
        self.assertEqual(self.read()["state"], "withdrawn")
        self.assertEqual(self.read(1)["state"], "accepted")
        with self.assertRaisesRegex(ValueError, "LIFECYCLE_INVALID"):
            self.apply(self.request("replace-r3", "replace", 3, pin2))
        with self.assertRaisesRegex(ValueError, "KNOWN_AT_INSTANT_REQUIRED"):
            self.read(known="2026-10-18")

    def test_accept_right_is_distinct_and_revocation_blocks_commit(self):
        editor = self.fixture.grant(["plan.edit", "plan.read"])[1]
        before = (self.root / PLANREL).read_bytes()
        with self.assertRaisesRegex(ValueError, "MISSING_PERMISSION: plan.accept"):
            self.apply(token=editor)
        accept_only = self.fixture.grant(["plan.accept"])[1]
        with self.assertRaisesRegex(ValueError, "MISSING_PERMISSION: plan.read"):
            self.apply(token=accept_only)
        ident, revocable = self.fixture.grant(["plan.accept", "plan.read"])
        with self.assertRaisesRegex(ValueError, "AUTH_TOKEN_REVOKED"):
            self.apply(token=revocable,
                callback=lambda: self.auth.manage("revoke", self.admin, {"id": ident}))
        self.assertFalse(BASELINE.target_path(self.root, PLANREL).exists())
        self.assertFalse(BASELINE.journal_path(self.root).exists())
        self.assertEqual((self.root / PLANREL).read_bytes(), before)

    def test_concurrent_accept_has_one_cas_winner(self):
        before = (self.root / PLANREL).read_bytes()
        paths = [self.fixture.base / ("accept-" + n + ".json") for n in ("a", "b")]
        for path, tx in zip(paths, ("accept-a", "accept-b")):
            path.write_text(json.dumps(self.request(tx=tx)))
        env = dict(os.environ, RDG_AUTH_TOKEN=self.acceptor,
                   PYTHONDONTWRITEBYTECODE="1")
        processes = [subprocess.Popen([sys.executable,
            str(ROOT / "tools/rdg-future-baseline-owner.py"),
            "apply", "--root", str(self.root), "--store", str(self.store),
            "--request", str(path)], env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True) for path in paths]
        results = [(p.returncode, out, err) for p in processes
                   for out, err in [p.communicate(timeout=15)]]
        self.assertEqual(sorted(code for code, _, _ in results), [0, 1])
        self.assertTrue(any("CAS_MISMATCH" in err for _, _, err in results))
        self.assertEqual(self.read()["stateRevision"], 1)
        self.assertEqual((self.root / PLANREL).read_bytes(), before)

    def test_forged_pin_and_reader_revoke_fail_closed(self):
        bad = self.request()
        bad["planPin"]["recordDigest"] = "0"*64
        with self.assertRaisesRegex(ValueError, "PLAN_PIN_MISMATCH"):
            self.apply(bad)
        self.apply()
        ident, reader = self.fixture.grant(["plan.read"])
        with self.assertRaisesRegex(ValueError, "AUTH_TOKEN_REVOKED"):
            self.read(token=reader,
                callback=lambda: self.auth.manage("revoke", self.admin, {"id": ident}))
        witness = BASELINE.receipt_path(self.root, PLANREL, 1)
        value = json.loads(witness.read_text())
        value["recordDigest"] = "0"*64
        witness.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "AVAILABILITY_RECEIPT_INVALID"):
            self.read()

    def crash(self, name):
        request_file = self.fixture.base / "baseline-request.json"
        request_file.write_text(json.dumps(self.request()))
        env = dict(os.environ, RDG_AUTH_TOKEN=self.acceptor,
                   RDG_BASELINE_TEST_CRASH=name, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(ROOT / "tools/rdg-future-baseline-owner.py"),
            "apply", "--root", str(self.root), "--store", str(self.store),
            "--request", str(request_file)], env=env, capture_output=True, text=True)

    def test_crash_prepared_then_recover_is_idempotent(self):
        p = self.crash("prepared")
        self.assertEqual(p.returncode, 91, p.stderr)
        with self.assertRaisesRegex(ValueError, "RECOVERY_REQUIRED"):
            self.read()
        self.assertTrue(BASELINE.recover(self.root)["recovered"])
        self.assertEqual(self.read()["stateRevision"], 1)
        self.assertFalse(BASELINE.recover(self.root)["recovered"])
        self.assertTrue(self.apply()["idempotent"])

    def test_crash_after_store_recover(self):
        p = self.crash("after-store-write")
        self.assertEqual(p.returncode, 91, p.stderr)
        self.assertFalse(BASELINE.receipt_path(self.root, PLANREL, 1).exists())
        self.assertTrue(BASELINE.recover(self.root)["recovered"])
        self.assertEqual(self.read()["stateRevision"], 1)

    def test_crash_after_receipt_preserves_availability(self):
        p = self.crash("after-availability-write")
        self.assertEqual(p.returncode, 91, p.stderr)
        witness = BASELINE.receipt_path(self.root, PLANREL, 1)
        old = witness.read_bytes()
        self.assertTrue(BASELINE.recover(self.root)["recovered"])
        self.assertEqual(witness.read_bytes(), old)
        self.assertEqual(self.read()["state"], "accepted")


if __name__ == "__main__":
    unittest.main()
