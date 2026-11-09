#!/usr/bin/env python3
"""Event projection coverage and stable historical cutoff on synthetic owners."""
import copy
import datetime as dt
from importlib.machinery import SourceFileLoader
from pathlib import Path
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECTION = SourceFileLoader("test_event_projection",
    str(ROOT / "tools/rdg-event-gendocen.py")).load_module()
FIXTURE = SourceFileLoader("event_projection_fixture",
    str(ROOT / "tests/rdg-event-owner.test.py")).load_module()


class EventProjectionTest(unittest.TestCase):
    def setUp(self):
        self.fixture = FIXTURE.EventOwnerTest("test_three_stages_are_durable_but_never_factual")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.apply("claim", self.fixture.claim, 0)

    def projection(self, known=None):
        f = self.fixture
        return PROJECTION.from_owner(f.root, f.store, f.reader, FIXTURE.PLANREL, "O1", known)

    def sources(self):
        return {str(p.relative_to(self.fixture.root)):p.read_bytes()
                for p in self.fixture.root.rglob("*.json")}

    def test_read_only_resource_has_complete_event_scope_and_false_factual_flags(self):
        before = self.sources()
        resource = self.projection()
        contract = PROJECTION.build_contract(resource)
        self.assertEqual(len(contract["subscriptions"]), 8)
        PROJECTION.assert_coverage(contract, contract["subscriptions"])
        self.assertFalse(resource["data"]["reviewInputs"]["boundaries"]["factualEventVerified"])
        self.assertFalse(resource["data"]["reviewInputs"]["boundaries"]["actionSelected"])
        self.assertFalse(resource["data"]["reviewCoverage"]["completePlanRdgContext"])
        self.assertEqual(self.sources(), before)

    def test_late_attestation_changes_current_only_and_preserves_fixed_cutoff(self):
        f = self.fixture
        early = f.after(f.receipt(1)["availableBy"])
        time.sleep(0.02)
        current = self.projection()
        historical = self.projection(early)
        f.apply("attest", f.attest(), 1)
        later_current, later_historical = self.projection(), self.projection(early)
        self.assertEqual(historical, later_historical)
        self.assertEqual(current["$docengine"], later_current["$docengine"])
        a, b = current["data"]["reviewInputs"], later_current["data"]["reviewInputs"]
        changed = {key for key in a if a[key] != b[key]}
        self.assertEqual(changed, {"attestations"})
        self.assertNotEqual(current["$docengine"], historical["$docengine"])

    def test_review_correction_and_conflict_are_semantic(self):
        f = self.fixture
        f.apply("attest", f.attest(), 1)
        before = self.projection()["data"]["reviewInputs"]
        f.apply("verify", f.verify(), 2)
        after = self.projection()["data"]["reviewInputs"]
        self.assertEqual({key for key in before if before[key] != after[key]}, {"reviews"})
        correction = f.make_claim("C2", "negative", supersedes="C1",
                                   when="2026-10-18T10:30:00+00:00")
        f.apply("claim", correction, 3)
        corrected = self.projection()
        self.assertEqual(corrected["data"]["reviewInputs"]["resolution"],
                         {"unresolvedClaimIds":["C2"], "claimConflict":False})
        f.apply("claim", f.make_claim("C3", "positive"), 4)
        conflict = self.projection()
        self.assertTrue(conflict["data"]["reviewInputs"]["resolution"]["claimConflict"])
        self.assertFalse(conflict["data"]["reviewInputs"]["boundaries"]["factualBranchResolved"])

    def test_missing_subscription_and_mutable_declaration_cannot_hide_group(self):
        resource = self.projection()
        contract = PROJECTION.build_contract(resource)
        with self.assertRaisesRegex(ValueError, "SUBSCRIPTIONS_INCOMPLETE"):
            PROJECTION.assert_coverage(contract, contract["subscriptions"][:-1])
        original = copy.deepcopy(PROJECTION.READ_MATRIX)
        try:
            PROJECTION.READ_MATRIX.pop("reviews")
            with self.assertRaisesRegex(ValueError, "SOURCE_GROUPS_INCOMPLETE_OR_UNKNOWN"):
                PROJECTION.build_contract(resource)
        finally:
            PROJECTION.READ_MATRIX.clear()
            PROJECTION.READ_MATRIX.update(original)

    def test_stale_projection_unknown_fields_and_factual_flag_rejected(self):
        resource = self.projection()
        wrong = copy.deepcopy(resource)
        wrong["data"]["reviewInputs"]["claims"] = {}
        with self.assertRaisesRegex(ValueError, "PROJECTION_INCOMPLETE_OR_STALE"):
            PROJECTION.build_contract(wrong)
        wrong = copy.deepcopy(resource["data"]["sourceHistory"])
        wrong["provenance"]["factualEventVerified"] = True
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_TRUST_OR_SCOPE"):
            PROJECTION.project(wrong)
        wrong = copy.deepcopy(resource["data"]["sourceHistory"])
        wrong["provenance"]["newUnsubscribedField"] = False
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_TRUST_OR_SCOPE"):
            PROJECTION.project(wrong)
        wrong = copy.deepcopy(resource["data"]["sourceHistory"])
        wrong["claimConflict"] = True
        with self.assertRaisesRegex(ValueError, "RESOLUTION_MISMATCH"):
            PROJECTION.project(wrong)

    def test_equivalent_cutoff_offsets_share_resource_identity(self):
        value = self.fixture.after(self.fixture.receipt(1)["availableBy"])
        cutoff = PROJECTION.EVENT.MODEL.known(value)
        local = cutoff.astimezone(dt.timezone(dt.timedelta(hours=7))).isoformat()
        self.assertEqual(self.projection(value), self.projection(local))
        with self.assertRaisesRegex(ValueError, "KNOWN_AT_INSTANT_REQUIRED"):
            self.projection("2026-10-18")


if __name__ == "__main__":
    unittest.main()
