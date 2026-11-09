#!/usr/bin/env python3
"""Old current-only Plan adapter refuses new owner lifecycle sidecars."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = SourceFileLoader("event_guard_adapter", str(ROOT / "tools/rdg-gendocen-adapter.py")).load_module()
EVENT = SourceFileLoader("event_guard_owner", str(ROOT / "tools/rdg-event-owner.py")).load_module()
FIXTURE = SourceFileLoader("event_guard_fixture", str(ROOT / "tests/rdg-temporal-plan-owner.test.py")).load_module()
PLANREL = FIXTURE.REL


class EventConsumerGuardTest(unittest.TestCase):
    def setUp(self):
        self.fixture = FIXTURE.PlanOwnerTest("test_create_edit_history_exact_snapshot_and_idempotency")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.apply(self.fixture.request())
        self.root, self.target = self.fixture.root, self.fixture.root / PLANREL
        self.original = self.target.read_bytes()
        self.assertEqual(ADAPTER.plan_resource(self.target, self.root)["data"]["planStatus"],
                         "candidate")

    def test_real_event_owner_record_blocks_current_only_adapter(self):
        meta = EVENT.OWNER.read_snapshot(self.root, PLANREL, 1)["provenance"]
        pin = {"file": PLANREL, "identitySpace": meta["identitySpace"],
               "planId": meta["planId"], "revision": 1,
               "snapshotSHA256": meta["snapshotSHA256"],
               "recordDigest": meta["recordDigest"]}
        claim = {"id": "C1", "occurrenceId": "O1", "planPin": pin,
                 "eventStepId": "S-RESULT", "outcome": "positive",
                 "occurredAt": "2026-10-18", "evidenceRefs": ["EV-C1"],
                 "supersedes": None}
        EVENT.apply(self.root, self.fixture.store, self.fixture.author,
                    {"transactionId": "event-claim", "kind": "claim",
                     "file": PLANREL, "expectedRevision": 0, "payload": claim})
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_OWNER_LIFECYCLE"):
            ADAPTER.plan_resource(self.target, self.root)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_baseline_and_applicability_sidecars_are_unsupported(self):
        for name in (".rdg-future-baseline.json", ".rdg-applicability.json"):
            with self.subTest(name=name):
                sidecar = self.target.with_name(name)
                sidecar.write_text("{}")
                with self.assertRaisesRegex(ValueError, "UNSUPPORTED_OWNER_LIFECYCLE"):
                    ADAPTER.plan_resource(self.target, self.root)
                sidecar.unlink()
        self.assertEqual(ADAPTER.plan_resource(self.target, self.root)["data"]["planStatus"],
                         "candidate")

    def test_prepared_sidecar_journal_and_symlink_fail_closed(self):
        journal = self.root / "_rdg-event-journal.json"
        journal.write_text("{}")
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_OWNER_LIFECYCLE"):
            ADAPTER.plan_resource(self.target, self.root)
        journal.unlink()
        outside = self.fixture.base / "outside.json"
        outside.write_text("{}")
        sidecar = self.target.with_name(".rdg-event-history.json")
        sidecar.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_OWNER_LIFECYCLE"):
            ADAPTER.plan_resource(self.target, self.root)
        self.assertEqual(self.target.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
