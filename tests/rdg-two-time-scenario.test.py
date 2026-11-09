#!/usr/bin/env python3
"""Two-time candidate rule probe against exact synthetic Plan/RDG sources."""
import copy
import datetime as dt
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODEL = SourceFileLoader("test_two_time_scenario", str(ROOT / "tools/rdg-two-time-scenario.py")).load_module()
FIXTURE = SourceFileLoader("two_time_exact_fixture", str(ROOT / "tests/rdg-exact-history.test.py")).load_module()
OWNER = MODEL.OWNER
PLANREL = FIXTURE.PLANREL


class TwoTimeScenarioTest(unittest.TestCase):
    def setUp(self):
        self.fixture = FIXTURE.ExactHistoryTest(
            "test_exact_source_is_stable_after_current_graph_changes")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.base = self.fixture.base
        self.graph_time = dt.datetime.now(dt.timezone.utc)
        self.fixture.add_journal("graph-create", None, self.fixture.graph,
                                 recorded_at=self.graph_time.isoformat())
        time.sleep(0.02)  # Leave a reliable cutoff between r1 and r2 writes.
        later = copy.deepcopy(self.fixture.plan)
        later["revision"] = 2
        later["title"] = "Later candidate correction"
        OWNER.apply_request(self.fixture.plans, self.fixture.authpath,
                            self.fixture.writer, {"transactionId": "model-r2",
                            "op": "edit", "file": PLANREL,
                            "expectedRevision": 1, "plan": later})
        self.plan2 = later
        self.meta2 = OWNER.read_snapshot(self.fixture.plans, PLANREL, 2)["provenance"]
        self.bound2 = OWNER.read_availability(self.fixture.plans, PLANREL, 2,
                                             self.meta2["recordDigest"])["availableBy"]
        self.assertLess(self.graph_time, OWNER.instant(self.bound2))
        self.source1 = copy.deepcopy(self.fixture.query)
        self.source2 = copy.deepcopy(self.source1)
        self.source2["plan"].update(revision=2,
            snapshotSHA256=self.meta2["snapshotSHA256"],
            recordDigest=self.meta2["recordDigest"])
        self.claim1 = self.claim("C1", "2026-10-18T10:00:00+00:00", None,
                                 self.source1, "positive")
        self.claim2 = self.claim("C2", "2026-10-18T10:30:00+00:00", "C1",
                                 self.source2, "positive")
        self.request = {"schemaVersion": 1, "mode": "candidate-two-time-scenario",
                        "knownAt": (self.graph_time + dt.timedelta(milliseconds=1)).isoformat(),
                        "effectiveAt": "2026-10-18T10:45:00+00:00",
                        "assertions": [self.claim1, self.claim2]}

    @staticmethod
    def claim(ident, when, supersedes, source, outcome):
        source = copy.deepcopy(source)
        source["scenario"]["outcome"] = outcome
        return {"id": ident, "effectiveAt": when, "supersedes": supersedes,
                "source": source, "eventClaim": {"eventStepId": "S-RESULT",
                "outcome": outcome, "verification": "unverified"}}

    def resolve(self, request=None, token=None, callback=None):
        return MODEL.resolve(self.fixture.plans, self.fixture.graphs,
                             self.fixture.authpath, token or self.fixture.reader,
                             request or self.request, before_return=callback)

    def denied(self, code, request=None):
        with self.assertRaisesRegex(ValueError, code):
            self.resolve(request)

    def test_late_correction_excluded_before_knowledge_then_reconstructs(self):
        plan_bytes = (self.fixture.plans / PLANREL).read_bytes()
        graph_journal = self.fixture.graphs / "workspaces/.transactions/graph-create.json"
        graph_bytes = graph_journal.read_bytes()
        before = self.resolve()
        self.assertEqual(before["selectedAssertionId"], "C1")
        self.assertEqual(before["exactSource"]["plan"]["revision"], 1)
        self.assertIn({"id": "C2", "reason": "not-proven-known"}, before["excluded"])
        self.assertFalse(before["provenance"]["twoTimeAsOfResolved"])
        self.assertFalse(before["provenance"]["eventClaimVerified"])
        self.assertFalse(before["provenance"]["historicalT1KnowledgeVerified"])
        self.request["assertions"].reverse()
        self.assertEqual(self.resolve()["selectedAssertionId"], "C1")
        self.request["knownAt"] = (OWNER.instant(self.bound2) +
                                  dt.timedelta(seconds=1)).isoformat()
        after = self.resolve()
        self.assertEqual(after["selectedAssertionId"], "C2")
        self.assertEqual(after["exactSource"]["plan"]["revision"], 2)
        self.assertEqual(before["exactSource"]["plan"]["revision"], 1)
        self.assertEqual(after["eventClaim"]["verification"], "unverified")
        self.assertTrue(after["exactSource"]["provenance"]["recordingCutoffVerified"])
        self.assertEqual((self.fixture.plans / PLANREL).read_bytes(), plan_bytes)
        self.assertEqual(graph_journal.read_bytes(), graph_bytes)

    def test_effective_time_does_not_invent_future_applicability(self):
        self.request["knownAt"] = (OWNER.instant(self.bound2) +
                                  dt.timedelta(seconds=1)).isoformat()
        self.request["effectiveAt"] = "2026-10-18T10:15:00+00:00"
        result = self.resolve()
        self.assertEqual(result["selectedAssertionId"], "C1")
        self.assertIn({"id": "C2", "reason": "effective-after-query"}, result["excluded"])
        self.request["effectiveAt"] = "2026-10-18T09:00:00+00:00"
        self.denied("NO_KNOWN_APPLICABLE_ASSERTION")

    def test_conflicting_outcomes_fail_without_correction_link(self):
        later = copy.deepcopy(self.plan2)
        later["revision"] = 3
        later["title"] = "Independent conflicting claim"
        OWNER.apply_request(self.fixture.plans, self.fixture.authpath,
                            self.fixture.writer, {"transactionId": "model-r3",
                            "op": "edit", "file": PLANREL,
                            "expectedRevision": 2, "plan": later})
        meta3 = OWNER.read_snapshot(self.fixture.plans, PLANREL, 3)["provenance"]
        source3 = copy.deepcopy(self.source2)
        source3["plan"].update(revision=3, snapshotSHA256=meta3["snapshotSHA256"],
                               recordDigest=meta3["recordDigest"])
        self.request["assertions"].append(self.claim(
            "C3", "2026-10-18T10:30:00+00:00", None, source3, "negative"))
        self.request["knownAt"] = (OWNER.instant(OWNER.read_availability(
            self.fixture.plans, PLANREL, 3, meta3["recordDigest"])["availableBy"]) +
            dt.timedelta(seconds=1)).isoformat()
        self.denied("UNRESOLVED_APPLICABILITY_CONFLICT")

    def test_date_precision_is_preserved_and_mixed_precision_denied(self):
        self.claim1["effectiveAt"] = "2026-10-18"
        self.claim2["effectiveAt"] = "2026-10-19"
        self.request["effectiveAt"] = "2026-10-18"
        self.assertEqual(self.resolve()["selectedAssertionId"], "C1")
        self.claim2["effectiveAt"] = "2026-10-19T00:00:00+00:00"
        self.denied("EFFECTIVE_AT_PRECISION_MISMATCH")
        self.claim2["effectiveAt"] = None
        self.denied("EFFECTIVE_AT_REQUIRED")
        self.request["effectiveAt"] = "2026-10-18T00:00:00"
        self.denied("EFFECTIVE_AT_PRECISION_REQUIRED")

    def test_broken_chain_or_claim_and_bad_future_pin_fail_closed(self):
        self.claim2["supersedes"] = "C9"
        self.denied("CORRECTION_CHAIN_INVALID")
        self.claim2["supersedes"] = "C1"
        self.claim2["eventClaim"]["outcome"] = "negative"
        self.denied("EVENT_CLAIM_INVALID")
        self.claim2["eventClaim"]["outcome"] = "positive"
        self.claim2["source"]["plan"]["snapshotSHA256"] = "0"*64
        self.denied("PLAN_SNAPSHOT_HASH_MISMATCH")

    def test_old_graph_time_missing_and_revocation_prevent_delivery(self):
        journal = self.fixture.graphs / "workspaces/.transactions/graph-create.json"
        old = json.loads(journal.read_text())
        journal.write_text(json.dumps({k:v for k,v in old.items()
                                       if k not in ("preparedAt", "recordedAt")}
                                      | {"schemaVersion": 1}))
        self.denied("GRAPH_RECORDING_TIME_NOT_AVAILABLE")
        journal.write_text(json.dumps(old))
        with self.assertRaisesRegex(ValueError, "AUTH_.*"):
            self.resolve(callback=lambda: self.fixture.auth.manage(
                "revoke", self.fixture.admin, {"id": self.fixture.reader_id}))


if __name__ == "__main__":
    unittest.main()
