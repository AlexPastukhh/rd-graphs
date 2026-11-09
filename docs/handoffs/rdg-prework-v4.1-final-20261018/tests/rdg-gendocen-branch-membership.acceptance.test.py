#!/usr/bin/env python3
"""FAIL-FIRST Stage 4 acceptance gate (separate from established 405 Node tests).

Run:
  RDG_GENDOCEN_SOURCE=/workspace/repos/gendocen python3 -m unittest \
    docs/handoffs/rdg-prework-v4.1-final-20261018/tests/rdg-gendocen-branch-membership.acceptance.test.py -v

Before P0 fix: 1 PASS + 1 FAIL is EXPECTED: the failing case is the product
defect, NOT a successful test. After P0 fix: both tests must PASS. This only
touches synthetic temporary project resources.
"""
import copy
import importlib.machinery
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
HANDOFF = HERE.parents[1]
GENDOCEN = Path(os.environ.get("RDG_GENDOCEN_SOURCE", "/workspace/repos/gendocen"))


class BranchDependencyAcceptance(unittest.TestCase):
    def test_meaningful_branch_reassignment_must_invalidate_affected_reviews(self):
        """Currently FAILS: engine incorrectly returns valid/valid."""
        if not (GENDOCEN / "src/docengine/cli.py").exists():
            self.fail("Gendocen source missing: set RDG_GENDOCEN_SOURCE or connect repo")
        script = HANDOFF / "repro-branch-membership-gap.py"
        result = subprocess.run(
            [sys.executable, str(script), "--engine-source", str(GENDOCEN)],
            cwd=REPO, capture_output=True, text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            timeout=120,
        )
        record = next(
            (s.split("=", 1)[1] for s in result.stdout.splitlines()
             if s.startswith("OBSERVED_AFTER_BRANCH_SWAP=")), None
        )
        self.assertIsNotNone(record, result.stderr + "\n" + result.stdout)
        actual = json.loads(record)
        self.assertEqual(
            actual, {"A1": "review_required", "A2": "review_required"},
            "OPEN PRODUCT DEFECT: semantic branch membership changed, "
            "but A1/A2 assessments are not marked review_required. "
            "The diagnostic's exit 0 means BUG REPRODUCED, not PASS.",
        )

    def test_cosmetic_case_and_outcome_reordering_keeps_plan_semantic_hash(self):
        """Projection-level invariant; additionally retest real engine after fix."""
        adapter = importlib.machinery.SourceFileLoader(
            "v41_branch_acceptance_adapter",
            str(REPO / "tools/rdg-gendocen-adapter.py")
        ).load_module()
        fixture = REPO / "docs/examples/temporal-plan-candidate-v1.json"
        plan = json.loads(fixture.read_text(encoding="utf8"))
        with tempfile.TemporaryDirectory(prefix="rdg-branch-acceptance-") as directory:
            target = Path(directory) / "plan.json"
            target.write_text(json.dumps(plan), encoding="utf8")
            before = adapter.plan_resource(target)
            modified = copy.deepcopy(plan)
            modified["revision"] += 1
            for branch in modified["branches"]:
                branch["cases"].reverse()
                for case in branch["cases"]:
                    case["stepIds"].reverse()
            for step in modified["steps"]:
                if step["kind"] == "event":
                    step["outcomes"].reverse()
            target.write_text(json.dumps(modified), encoding="utf8")
            after = adapter.plan_resource(target)
            self.assertEqual(before["data"]["semanticSHA256"],
                             after["data"]["semanticSHA256"])


if __name__ == "__main__":
    unittest.main()
