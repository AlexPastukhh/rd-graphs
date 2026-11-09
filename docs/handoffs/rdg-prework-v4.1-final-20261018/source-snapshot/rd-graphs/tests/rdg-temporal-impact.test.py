#!/usr/bin/env python3
"""Stage 3P read-only Plan/RDG temporal influence tests (synthetic files only)."""
import copy
import importlib.machinery
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODEL = importlib.machinery.SourceFileLoader(
    "impact_stage3p", str(ROOT / "tools/rdg-temporal-impact.py")).load_module()
SOURCE = ROOT / "docs/examples/temporal-plan-candidate-v1.json"
DRAFTS = importlib.machinery.SourceFileLoader(
    "typed_finding_drafts", str(ROOT / "tools/rdg-finding-drafts.py")).load_module()


class ImpactTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rdg-impact-stage3p-")
        self.root = Path(self.tmp.name)
        self.graph_file = self.root / "workspaces/temporal-fixture/graph.json"
        self.graph_file.parent.mkdir(parents=True, exist_ok=True)
        self.plan = json.loads(SOURCE.read_text(encoding="utf8"))
        self.plan["sequence"] += [
            {"before": "S-A1", "after": "S-DELIVERY"},
            {"before": "S-A2", "after": "S-DELIVERY"}]
        self.plan["timeConstraints"] += [
            {"stepId": "S-TRIAL", "type": "notBefore",
             "at": "2026-11-10", "strength": "hard",
             "basis": "Hypothetical assumed constraint only"}]
        self.plan["timeConstraints"][0].update(
            strength="hard", at="2026-11-20", basis="Assumed candidate deadline")
        self.graph = {
            "schemaVersion": 1, "id": "synthetic-rdg", "revision": 1,
            "identitySpace": "temporal-demo", "rootRequirementId": "R0",
            "actionModel": "candidate-v6",
            "nodes": [
                {"id": "R0", "kind": "requirement", "title": "Goal"},
                {"id": "A1", "kind": "action", "title": "Possible A1",
                 "status": "candidate", "canonBlock": {
                    "recommended": [{"id": "PLUS1", "text": "Useful if timely"}],
                    "contraindicated": [{"id": "MINUS1", "text": "Long lead time"}]}},
                {"id": "A2", "kind": "action", "title": "Possible A2",
                 "status": "candidate", "canonBlock": {
                    "recommended": [{"id": "PLUS2", "text": "Useful alternative"}],
                    "contraindicated": []}}],
            "edges": [], "events": []}
        self.save_graph()

    def tearDown(self):
        self.tmp.cleanup()

    def save_graph(self):
        self.graph_file.write_text(json.dumps(self.graph, ensure_ascii=False), encoding="utf8")

    def evaluate(self, plan=None):
        return MODEL.assess(plan or self.plan, self.root)

    def leads(self, report):
        return {case["outcome"]: case["actionReviewLeads"][0]
                for case in report["branches"]}

    def checks(self, report):
        return {case["outcome"]: case["deadlineChecks"][0]
                for case in report["branches"]}

    def test_source_files_unchanged_and_two_conditioned_actions(self):
        before = self.graph_file.read_bytes()
        report = self.evaluate()
        self.assertEqual(report["planStatus"], "candidate")
        self.assertFalse(report["executionPerformed"])
        self.assertEqual(report["committedFindings"], [])
        self.assertEqual(report["selectedActions"], [])
        leads = self.leads(report)
        self.assertEqual(set(leads), {"positive", "negative"})
        self.assertEqual(leads["positive"]["action"]["actionId"], "A1")
        self.assertEqual(leads["negative"]["action"]["actionId"], "A2")
        self.assertEqual(len(leads["positive"]["canonReview"]["cases"]), 2)
        self.assertEqual(leads["positive"]["canonReview"]["applicability"], "not-evaluated")
        self.assertFalse(leads["positive"]["timeConflictReview"])
        self.assertEqual(before, self.graph_file.read_bytes())

    def test_tight_deadline_yields_assumption_only_signal_not_confirmed_finding(self):
        short = copy.deepcopy(self.plan)
        short["timeConstraints"][0]["at"] = "2026-11-11"
        report = self.evaluate(short)
        self.assertTrue(all(a["timeConflictReview"]
                        for a in self.leads(report).values()))
        self.assertTrue(all(x["comparison"] == "candidate-plan-hard-constraint-conflict"
                        for x in self.checks(report).values()))
        self.assertTrue(all(x["assumptionOnly"] and x["findingType"] is None
                        for x in self.checks(report).values()))
        self.assertEqual(report["committedFindings"], [])
        self.assertEqual(self.graph["nodes"][1]["status"], "candidate")

    def test_soft_and_hypothetical_deadlines_do_not_claim_hard_conflict(self):
        for strength in ("soft", "hypothetical"):
            altered = copy.deepcopy(self.plan)
            altered["timeConstraints"][0].update(at="2026-11-01",
                                                   strength=strength)
            checks = self.checks(self.evaluate(altered))
            self.assertTrue(all(x["comparison"] == "nonbinding-deadline"
                                for x in checks.values()))

    def test_branch_only_delay_causes_branch_only_review(self):
        scenario = copy.deepcopy(self.plan)
        scenario["timeConstraints"][0]["at"] = "2026-11-17"
        scenario["timeConstraints"].append({
            "stepId": "S-A2", "type": "notBefore", "at": "2026-11-18",
            "strength": "hard", "basis": "Conditional alternative only"})
        checks = self.checks(self.evaluate(scenario))
        self.assertEqual(checks["positive"]["comparison"], "no-conflict-proven")
        self.assertEqual(checks["negative"]["comparison"],
                         "candidate-plan-hard-constraint-conflict")
        self.assertEqual(checks["negative"]["earliestHardBound"], "2026-11-18")
        self.assertEqual(checks["positive"]["earliestHardBound"], "2026-11-12")

    def test_irrelevant_branch_change_does_not_invalidate_other_action(self):
        before = self.evaluate()
        altered = copy.deepcopy(self.plan)
        altered["revision"] = 2
        altered["timeConstraints"].append({
            "stepId": "S-A2", "type": "notBefore", "at": "2026-11-19",
            "strength": "hard", "basis": "Negative branch conditional only"})
        after = self.evaluate(altered)
        changes = {x["actionId"]: x["change"]
                   for x in MODEL.changed_actions(before, after)}
        self.assertEqual(changes, {"A1": "unchanged", "A2": "review-required"})
        self.assertEqual(self.graph_file.read_bytes(),
                         json.dumps(self.graph, ensure_ascii=False).encode("utf8"))

    def test_deadline_change_in_ancestor_output_affects_both(self):
        old = self.evaluate()
        revised = copy.deepcopy(self.plan)
        revised["revision"] = 2
        revised["timeConstraints"][0]["at"] = "2026-11-14"
        change = MODEL.changed_actions(old, self.evaluate(revised))
        self.assertEqual([x["change"] for x in change],
                         ["review-required", "review-required"])

    def test_reorder_titles_and_revision_do_not_fake_semantic_change(self):
        old = self.evaluate()
        updated = copy.deepcopy(self.plan)
        updated["revision"] = 2
        updated["title"] = "Different display only"
        updated["steps"][2]["title"] = "Different label only"
        self.assertTrue(all(x["change"] == "unchanged"
                            for x in MODEL.changed_actions(old, self.evaluate(updated))))

    def test_graph_canon_change_targeted_without_modifying_action(self):
        before = self.evaluate()
        previous = self.graph_file.read_bytes()
        self.graph["nodes"][1]["canonBlock"]["contraindicated"][0]["text"] = (
            "Revised canon requires contextual review")
        self.save_graph()
        new = self.evaluate()
        delta = {d["actionId"]: d["change"]
                 for d in MODEL.changed_actions(before, new)}
        self.assertEqual(delta, {"A1": "review-required", "A2": "unchanged"})
        self.assertNotEqual(previous, self.graph_file.read_bytes())
        self.assertEqual(self.graph["nodes"][1]["status"], "candidate")

    def test_graph_revision_only_is_not_canon_change_and_is_reported(self):
        self.graph["revision"] = 5
        self.save_graph()
        report = self.evaluate()
        positive = self.leads(report)["positive"]
        self.assertTrue(positive["action"]["revisionChanged"])
        self.assertEqual(positive["canonReview"]["applicability"], "not-evaluated")

    def test_explicitly_qualified_cross_identity_reference_read_only(self):
        scoped = copy.deepcopy(self.plan)
        scoped["identitySpace"] = "planning-office"
        # The referenced Action remains owned by its named RDG identitySpace.
        before = self.graph_file.read_bytes()
        report = self.evaluate(scoped)
        self.assertEqual(report["planId"], scoped["id"])
        self.assertEqual(self.leads(report)["positive"]["action"]["identitySpace"],
                         "temporal-demo")
        self.assertEqual(before, self.graph_file.read_bytes())

    def test_missing_graph_and_wrong_identity_fail_closed(self):
        self.graph_file.unlink()
        with self.assertRaisesRegex(ValueError, "PLAN_IMPACT_ACTION_GRAPH_NOT_AVAILABLE"):
            self.evaluate()
        self.graph["identitySpace"] = "other"
        self.save_graph()
        with self.assertRaisesRegex(ValueError, "PLAN_IMPACT_IDENTITY_SPACE_MISMATCH"):
            self.evaluate()

    def test_mixed_instant_calendar_dates_remain_incomparable(self):
        altered = copy.deepcopy(self.plan)
        altered["timeConstraints"] = [
            r for r in altered["timeConstraints"]
            if not (r["type"] == "notBefore" and r["strength"] == "hard")]
        report = self.evaluate(altered)
        self.assertTrue(all(x["comparison"] == "no-hard-lower-bound"
                            or x["comparison"] == "precision-not-comparable"
                            for x in self.checks(report).values()))
        self.assertFalse(any(a["timeConflictReview"]
                             for a in self.leads(report).values()))

    def test_explicit_mixed_precision_never_proves_a_conflict(self):
        altered = copy.deepcopy(self.plan)
        altered["timeConstraints"] = [
            rule for rule in altered["timeConstraints"]
            if not (rule["type"] == "notBefore" and rule["strength"] == "hard")]
        altered["timeConstraints"][1]["strength"] = "hard"
        checks = self.checks(self.evaluate(altered))
        self.assertEqual({x["comparison"] for x in checks.values()},
                         {"precision-not-comparable"})

    def test_timezone_aware_instants_compare_only_with_instants(self):
        # This is an isolated instant-precision scenario, not a conversion
        # of the plan's calendar date to an invented time of day.
        adjusted = copy.deepcopy(self.plan)
        adjusted["timeConstraints"] = [
            {"stepId": "S-TRIAL", "type": "notBefore",
             "at": "2026-11-10T09:00:00+02:00", "strength": "hard",
             "basis": "Assumed exact earliest time"},
            {"stepId": "S-DELIVERY", "type": "deadline",
             "at": "2026-11-11T06:00:00Z", "strength": "hard",
             "basis": "Assumed exact latest time"}]
        checks = self.checks(self.evaluate(adjusted))
        self.assertEqual({x["comparison"] for x in checks.values()},
                         {"candidate-plan-hard-constraint-conflict"})
        self.assertEqual({x["earliestHardBound"] for x in checks.values()},
                         {"2026-11-12T07:00:00+00:00"})

    def test_multiple_branch_events_are_explicitly_unsupported(self):
        extra = copy.deepcopy(self.plan)
        extra["steps"].extend([
            {"id": "S-E2", "title": "Second future event", "kind": "event",
             "state": "expected", "outcomes": ["x", "y"]},
            {"id": "S-X", "title": "Option X", "kind": "milestone", "state": "possible"},
            {"id": "S-Y", "title": "Option Y", "kind": "milestone", "state": "possible"}])
        extra["sequence"].extend([{"before": "S-E2", "after": "S-X"},
                                  {"before": "S-E2", "after": "S-Y"}])
        extra["branches"].append(
            {"id": "B-OTHER", "eventStepId": "S-E2",
             "cases": [{"outcome": "x", "stepIds": ["S-X"]},
                       {"outcome": "y", "stepIds": ["S-Y"]}]})
        with self.assertRaisesRegex(ValueError, "PLAN_IMPACT_MULTI_BRANCH_NOT_YET_SUPPORTED"):
            self.evaluate(extra)

    def test_temporary_conflict_produces_only_reviewable_F_R_drafts(self):
        altered = copy.deepcopy(self.plan)
        altered["timeConstraints"][0]["at"] = "2026-11-11"
        before = self.graph_file.read_bytes()
        draft = DRAFTS.build(self.evaluate(altered))
        self.assertEqual(draft["draftCount"], 2)
        self.assertEqual(draft["committedFindings"], [])
        self.assertEqual(draft["acceptedProposals"], [])
        self.assertTrue(all(x["reviewStatus"] == "draft-only-not-verified" and
                            x["suggestedFinding"]["findingType"] == "F-R" and
                            x["suggestedFinding"]["findingScope"] == "UPSTREAM" and
                            x["suggestedFinding"]["evidenceRefs"] == [] and
                            not x["commitAllowedAutomatically"]
                            for x in draft["reviewDrafts"]))
        self.assertEqual(before, self.graph_file.read_bytes())

    def test_nonconflicting_plan_creates_no_finding_drafts(self):
        result = DRAFTS.build(self.evaluate())
        self.assertEqual(result["draftCount"], 0)
        self.assertEqual(result["reviewDrafts"], [])

    def test_draft_source_rejects_claimed_committed_findings(self):
        report = self.evaluate()
        report["committedFindings"] = ["F-P-FAKE"]
        with self.assertRaisesRegex(ValueError, "FINDING_DRAFT_REQUIRES_READ_ONLY"):
            DRAFTS.build(report)
        report["committedFindings"] = []
        report["readOnly"] = False
        with self.assertRaisesRegex(ValueError, "FINDING_DRAFT_REQUIRES_READ_ONLY"):
            DRAFTS.build(report)

    def test_finding_draft_cli_round_trip(self):
        updated = copy.deepcopy(self.plan)
        updated["timeConstraints"][0]["at"] = "2026-11-11"
        report = self.evaluate(updated)
        input_file = self.root / "impact.json"
        input_file.write_text(json.dumps(report))
        result = subprocess.run(["python3", str(ROOT / "tools/rdg-finding-drafts.py"),
                                 "--impact-report", str(input_file)], capture_output=True,
                                text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["draftCount"], 2)

    def test_cli_before_after_output_and_no_file_changes(self):
        old = self.root / "before.json"
        new = self.root / "after.json"
        old.write_text(json.dumps(self.plan))
        alt = copy.deepcopy(self.plan)
        alt["revision"] = 2
        alt["timeConstraints"][0]["at"] = "2026-11-01"
        new.write_text(json.dumps(alt))
        before = (old.read_bytes(), new.read_bytes(), self.graph_file.read_bytes())
        proc = subprocess.run([
            "python3", str(ROOT / "tools/rdg-temporal-impact.py"),
            "--plan", str(new), "--before-plan", str(old),
            "--graphs-root", str(self.root)],
            text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        response = json.loads(proc.stdout)
        self.assertEqual(response["planRevision"], 2)
        self.assertEqual(len(response["deltaFromBefore"]), 2)
        self.assertEqual(before, (old.read_bytes(), new.read_bytes(),
                                  self.graph_file.read_bytes()))


if __name__ == "__main__":
    unittest.main()
