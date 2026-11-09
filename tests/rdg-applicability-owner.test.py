#!/usr/bin/env python3
"""Durable candidate applicability records, recovery and two-time reconstruction."""
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
OWNER = SourceFileLoader("test_applicability_owner", str(ROOT / "tools/rdg-applicability-owner.py")).load_module()
FIXTURE = SourceFileLoader("applicability_exact_fixture", str(ROOT / "tests/rdg-exact-history.test.py")).load_module()
PLANREL = FIXTURE.PLANREL


class ApplicabilityOwnerTest(unittest.TestCase):
    def setUp(self):
        self.fixture = FIXTURE.ExactHistoryTest("test_exact_source_is_stable_after_current_graph_changes")
        self.fixture.applicability_capable = True
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.add_journal("graph-create", None, self.fixture.graph,
            recorded_at=dt.datetime.now(dt.timezone.utc).isoformat())
        self.auth = self.fixture.auth
        self.admin = self.fixture.admin
        self.writer = self.fixture.grant(["plan.applicability.write", "plan.read", "graph.read"],
                                          [PLANREL, FIXTURE.REL])
        self.reader = self.fixture.reader
        self.source1 = copy.deepcopy(self.fixture.query)
        self.first = self.assertion("C1", "2026-10-18T10:00:00+00:00", None, self.source1)
        self.apply("app-r1", 0, self.first)
        self.bound1 = self.receipt(1)["availableBy"]
        time.sleep(0.02)
        later = copy.deepcopy(self.fixture.plan)
        later["revision"] = 2
        later["title"] = "Later recorded correction"
        OWNER.OWNER.apply_request(self.fixture.plans, self.fixture.authpath,
                                  self.fixture.writer, {"transactionId": "plan-r2",
            "op": "edit", "file": PLANREL, "expectedRevision": 1, "plan": later})
        meta = OWNER.OWNER.read_snapshot(self.fixture.plans, PLANREL, 2)["provenance"]
        self.source2 = copy.deepcopy(self.source1)
        self.source2["plan"].update(revision=2, snapshotSHA256=meta["snapshotSHA256"],
                                     recordDigest=meta["recordDigest"])
        self.second = self.assertion("C2", "2026-10-18T10:30:00+00:00",
                                      "C1", self.source2)

    @staticmethod
    def assertion(ident, when, supersedes, source, outcome="positive"):
        source = copy.deepcopy(source)
        source["scenario"]["outcome"] = outcome
        return {"id": ident, "effectiveAt": when, "supersedes": supersedes,
                "source": source, "eventClaim": {"eventStepId": "S-RESULT",
                    "outcome": outcome, "verification": "unverified"}}

    def request(self, tx, expected, assertion):
        return {"transactionId": tx, "file": PLANREL, "expectedRevision": expected,
                "assertion": copy.deepcopy(assertion)}

    def apply(self, tx, expected, assertion, token=None, callback=None):
        return OWNER.apply(self.fixture.plans, self.fixture.graphs, self.fixture.authpath,
                           token or self.writer, self.request(tx, expected, assertion),
                           before_prepare=callback)

    def receipt(self, revision):
        path = OWNER.receipt_path(self.fixture.plans, PLANREL, revision)
        return json.loads(path.read_text())

    def read(self, known, effective="2026-10-18T10:45:00+00:00", token=None):
        return OWNER.resolve(self.fixture.plans, self.fixture.graphs, self.fixture.authpath,
                             token or self.reader, PLANREL, known, effective)

    def after(self, value):
        return (OWNER.OWNER.instant(value) + dt.timedelta(seconds=1)).isoformat()

    def test_durable_late_correction_has_two_distinct_knowledge_results(self):
        early = (OWNER.OWNER.instant(self.bound1) + dt.timedelta(milliseconds=1)).isoformat()
        self.apply("app-r2", 1, self.second)
        self.assertLess(OWNER.OWNER.instant(early),
                        OWNER.OWNER.instant(self.receipt(2)["availableBy"]))
        late = self.after(self.receipt(2)["availableBy"])
        old = self.read(early)
        new = self.read(late)
        self.assertEqual(old["selectedAssertionId"], "C1")
        self.assertEqual(new["selectedAssertionId"], "C2")
        self.assertEqual(new["exactSource"]["plan"]["revision"], 2)
        self.assertEqual(len(new["ownerHistory"]["availableRecords"]), 2)
        self.assertTrue(new["ownerHistory"]["assertionsDurablyRecorded"])
        self.assertFalse(new["provenance"]["applicabilityAttested"])
        self.assertFalse(new["provenance"]["twoTimeAsOfResolved"])
        self.assertFalse(new["provenance"]["historicalT1KnowledgeVerified"])
        self.assertEqual(self.read(late, "2026-10-18T10:15:00+00:00")["selectedAssertionId"], "C1")

    def test_cas_replay_and_correction_chain_preserve_old_record(self):
        before = OWNER.target_path(self.fixture.plans, PLANREL).read_bytes()
        old_record = json.loads(before)["records"][0]
        result = self.apply("app-r2", 1, self.second)
        saved = OWNER.target_path(self.fixture.plans, PLANREL).read_bytes()
        self.assertEqual(json.loads(saved)["records"][0], old_record)
        self.assertTrue(self.apply("app-r2", 1, self.second)["idempotent"])
        self.assertEqual(OWNER.target_path(self.fixture.plans, PLANREL).read_bytes(), saved)
        with self.assertRaisesRegex(ValueError, "TRANSACTION_REPLAY_CONFLICT"):
            self.apply("app-r2", 1, self.assertion("C3", "2026-10-18T10:30:00+00:00",
                                                  "C1", self.source2))
        with self.assertRaisesRegex(ValueError, "CAS_MISMATCH"):
            self.apply("app-other", 1, self.second)
        self.assertEqual(OWNER.target_path(self.fixture.plans, PLANREL).read_bytes(), saved)
        self.assertNotEqual(before, saved)
        later = copy.deepcopy(self.fixture.plan)
        later["revision"] = 3
        later["title"] = "Earlier effective boundary"
        OWNER.OWNER.apply_request(self.fixture.plans, self.fixture.authpath,
            self.fixture.writer, {"transactionId": "plan-r3", "op": "edit",
            "file": PLANREL, "expectedRevision": 2, "plan": later})
        meta = OWNER.OWNER.read_snapshot(self.fixture.plans, PLANREL, 3)["provenance"]
        source3 = copy.deepcopy(self.source2)
        source3["plan"].update(revision=3, snapshotSHA256=meta["snapshotSHA256"],
                                recordDigest=meta["recordDigest"])
        invalid = self.assertion("C3", "2026-10-18T09:00:00+00:00", "C2", source3)
        with self.assertRaisesRegex(ValueError, "CORRECTION_CHAIN_INVALID"):
            self.apply("app-r3", 2, invalid)

    def test_permissions_and_revoke_before_prepare_block_write(self):
        no_right = self.fixture.grant(["plan.edit", "plan.read", "graph.read"],
                                      [PLANREL, FIXTURE.REL])
        with self.assertRaisesRegex(ValueError, "MISSING_PERMISSION: plan.applicability.write"):
            self.apply("not-allowed", 1, self.second, token=no_right)
        ident, revocable = self.fixture.grant(
            ["plan.applicability.write", "plan.read", "graph.read"],
            [PLANREL, FIXTURE.REL], with_id=True)
        before = OWNER.target_path(self.fixture.plans, PLANREL).read_bytes()
        with self.assertRaisesRegex(ValueError, "AUTH_TOKEN_REVOKED"):
            self.apply("revoked", 1, self.second, token=revocable,
                callback=lambda: self.auth.manage("revoke", self.admin, {"id": ident}))
        self.assertEqual(OWNER.target_path(self.fixture.plans, PLANREL).read_bytes(), before)
        self.assertFalse(OWNER.journal_path(self.fixture.plans).exists())

    def test_conflict_is_preserved_and_reported(self):
        self.apply("app-r2", 1, self.second)
        later = copy.deepcopy(self.fixture.plan)
        later["revision"] = 3
        later["title"] = "Independent claim"
        OWNER.OWNER.apply_request(self.fixture.plans, self.fixture.authpath,
            self.fixture.writer, {"transactionId": "plan-r3", "op": "edit",
            "file": PLANREL, "expectedRevision": 2, "plan": later})
        meta = OWNER.OWNER.read_snapshot(self.fixture.plans, PLANREL, 3)["provenance"]
        source = copy.deepcopy(self.source2)
        source["plan"].update(revision=3, snapshotSHA256=meta["snapshotSHA256"],
                              recordDigest=meta["recordDigest"])
        self.apply("app-r3", 2, self.assertion("C3", "2026-10-18T10:30:00+00:00",
                                             None, source, "negative"))
        with self.assertRaisesRegex(ValueError, "UNRESOLVED_APPLICABILITY_CONFLICT"):
            self.read(self.after(self.receipt(3)["availableBy"]))

    def test_crash_after_store_write_requires_recovery(self):
        request_file = self.fixture.base / "app-request.json"
        request_file.write_text(json.dumps(self.request("app-r2", 1, self.second)))
        env = dict(os.environ, RDG_AUTH_TOKEN=self.writer,
                   RDG_APPLICABILITY_TEST_CRASH="after-store-write",
                   PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.run([sys.executable, str(ROOT / "tools/rdg-applicability-owner.py"),
            "apply", "--root", str(self.fixture.plans), "--graphs-root", str(self.fixture.graphs),
            "--store", str(self.fixture.authpath), "--request", str(request_file)],
            env=env, capture_output=True, text=True)
        self.assertEqual(process.returncode, 91, process.stderr)
        with self.assertRaisesRegex(ValueError, "RECOVERY_REQUIRED"):
            self.read(self.after(self.bound1))
        self.assertTrue(OWNER.recover(self.fixture.plans)["recovered"])
        receipt = self.receipt(2)
        bytes_before = OWNER.receipt_path(self.fixture.plans, PLANREL, 2).read_bytes()
        self.assertFalse(OWNER.recover(self.fixture.plans)["recovered"])
        self.assertEqual(OWNER.receipt_path(self.fixture.plans, PLANREL, 2).read_bytes(), bytes_before)
        self.assertEqual(self.read(self.after(receipt["availableBy"]))["selectedAssertionId"], "C2")

    def crash_at(self, failpoint):
        request_file = self.fixture.base / "app-request.json"
        request_file.write_text(json.dumps(self.request("app-r2", 1, self.second)))
        env = dict(os.environ, RDG_AUTH_TOKEN=self.writer,
                   RDG_APPLICABILITY_TEST_CRASH=failpoint,
                   PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable,
            str(ROOT / "tools/rdg-applicability-owner.py"),
            "apply", "--root", str(self.fixture.plans),
            "--graphs-root", str(self.fixture.graphs),
            "--store", str(self.fixture.authpath),
            "--request", str(request_file)],
            env=env, capture_output=True, text=True)

    def test_prepared_recovery_finishes_once(self):
        process = self.crash_at("prepared")
        self.assertEqual(process.returncode, 91, process.stderr)
        witness = OWNER.receipt_path(self.fixture.plans, PLANREL, 2)
        self.assertFalse(witness.exists())
        with self.assertRaisesRegex(ValueError, "RECOVERY_REQUIRED"):
            self.read(self.after(self.bound1))
        self.assertTrue(OWNER.recover(self.fixture.plans)["recovered"])
        self.assertTrue(witness.exists())
        self.assertFalse(OWNER.recover(self.fixture.plans)["recovered"])
        self.assertTrue(self.apply("app-r2", 1, self.second)["idempotent"])

    def test_after_receipt_recovery_preserves_witness(self):
        process = self.crash_at("after-availability-write")
        self.assertEqual(process.returncode, 91, process.stderr)
        witness = OWNER.receipt_path(self.fixture.plans, PLANREL, 2)
        old = witness.read_bytes()
        self.assertTrue(OWNER.recover(self.fixture.plans)["recovered"])
        self.assertEqual(witness.read_bytes(), old)
        self.assertEqual(self.read(self.after(self.receipt(2)["availableBy"]))[
            "selectedAssertionId"], "C2")

    def test_missing_prior_receipt_blocks_next_commit(self):
        OWNER.receipt_path(self.fixture.plans, PLANREL, 1).unlink()
        with self.assertRaisesRegex(ValueError, "PREVIOUS_AVAILABILITY_BOUND_NOT_AVAILABLE"):
            self.apply("app-r2", 1, self.second)
        self.assertFalse(OWNER.journal_path(self.fixture.plans).exists())
        self.assertEqual(json.loads(OWNER.target_path(self.fixture.plans, PLANREL).read_text())[
            "revision"], 1)

    def test_bad_pin_receipt_and_unknown_time_fail_closed(self):
        bad = copy.deepcopy(self.second)
        bad["source"]["plan"]["recordDigest"] = "0"*64
        with self.assertRaisesRegex(ValueError, "PLAN_SNAPSHOT_HASH_MISMATCH"):
            self.apply("bad-pin", 1, bad)
        bad = copy.deepcopy(self.second)
        bad["effectiveAt"] = None
        with self.assertRaisesRegex(ValueError, "EFFECTIVE_AT_REQUIRED"):
            self.apply("bad-time", 1, bad)
        self.apply("app-r2", 1, self.second)
        receipt_path = OWNER.receipt_path(self.fixture.plans, PLANREL, 2)
        receipt = self.receipt(2)
        receipt["recordDigest"] = "0"*64
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "AVAILABILITY_RECEIPT_INVALID"):
            self.read(self.after(self.bound1))


if __name__ == "__main__":
    unittest.main()
