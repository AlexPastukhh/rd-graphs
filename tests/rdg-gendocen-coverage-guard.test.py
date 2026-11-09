#!/usr/bin/env python3
"""P0.1 acceptance: declaration-level omission and actual semantic title edits."""
from importlib.machinery import SourceFileLoader
import copy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = SourceFileLoader("p01_review_probe", str(ROOT / "docs/handoffs/rdg-progress-review-20261019-v1/coverage-review.acceptance.test.py")).load_module()
DEP = PROBE.DEP


class CoverageGuardAcceptance(unittest.TestCase):
    def test_omitted_producer_group_is_rejected_before_baseline(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_GROUPS_INCOMPLETE_OR_UNKNOWN"):
            PROBE.run_probe("missing-source-group")

    def test_event_title_is_semantic_until_separate_display_contract(self):
        result = PROBE.run_probe("event-title")
        self.assertTrue(result["checkOk"])
        self.assertIn("steps", result["changedFacets"])
        self.assertEqual(result["statuses"], {"A1": "review_required", "A2": "review_required"})

    def test_duplicate_declared_subscription_is_rejected(self):
        fixture = PROBE.FIXTURE.DependencyContractTest()
        fixture.setUp()
        try:
            graph, plan = fixture.projections()
            contract = DEP.build_contract(graph, plan, "A1", "S-A1")
            declared = contract["subscriptions"] + [contract["subscriptions"][0]]
            with self.assertRaisesRegex(ValueError, "SUBSCRIPTIONS_INCOMPLETE"):
                DEP.assert_coverage(contract, declared)
        finally:
            fixture.doCleanups()

    def test_missing_group_cannot_hide_in_an_empty_action_set(self):
        fixture = PROBE.FIXTURE.DependencyContractTest()
        fixture.setUp()
        original = copy.deepcopy(DEP.READ_MATRIX)
        try:
            fixture.plan["steps"] = [s for s in fixture.plan["steps"] if s["kind"] != "action"]
            ids = {s["id"] for s in fixture.plan["steps"]}
            fixture.plan["branches"] = []
            fixture.plan["sequence"] = [e for e in fixture.plan["sequence"] if e["before"] in ids and e["after"] in ids]
            DEP.READ_MATRIX.pop("sequence")
            with self.assertRaisesRegex(ValueError, "SOURCE_GROUPS_INCOMPLETE_OR_UNKNOWN"):
                fixture.projections()
        finally:
            DEP.READ_MATRIX.clear()
            DEP.READ_MATRIX.update(original)
            fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()
