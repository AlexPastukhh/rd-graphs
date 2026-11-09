#!/usr/bin/env python3
"""Independent Stage 2P Temporal Plan tests. No project graphs are edited."""
import copy
import importlib.machinery
import json
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = importlib.machinery.SourceFileLoader(
    "temporal_plan", str(ROOT / "tools/rdg-temporal-plan.py")).load_module()
EXAMPLE = ROOT / "docs/examples/temporal-plan-candidate-v1.json"


class TemporalPlanTest(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.temp = tempfile.TemporaryDirectory(prefix="rdg-temporal-plan-")
        self.root = pathlib.Path(self.temp.name)
        self.graph_path = self.root / "workspaces/temporal-fixture/graph.json"
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = {
            "schemaVersion": 1, "revision": 1, "id": "rdg-temp",
            "identitySpace": "temporal-demo", "rootRequirementId": "R0",
            "actionModel": "candidate-v6",
            "nodes": [{"id": "R0", "kind": "requirement", "title": "Root"},
                      {"id": "A1", "kind": "action", "title": "Option one", "status": "candidate"},
                      {"id": "A2", "kind": "action", "title": "Option two", "status": "candidate"}],
            "edges": [], "events": []
        }
        self.graph_path.write_text(json.dumps(self.graph), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def should_fail(self, plan, code):
        with self.assertRaisesRegex(ValueError, "TEMPORAL_PLAN_" + code):
            MODULE.inspect(plan, self.root)

    def test_two_branches_keep_candidate_actions_and_graph_file_unchanged(self):
        before = self.graph_path.read_bytes()
        report = MODULE.inspect(self.fixture, self.root)
        self.assertEqual(report["planStatus"], "candidate")
        self.assertFalse(report["executionPerformed"])
        self.assertFalse(report["decisionCommitted"])
        self.assertFalse(report["eventsAttested"])
        self.assertEqual({x["actionStatus"] for x in report["actionReferences"]},
                         {"candidate"})
        self.assertEqual([x["verification"] for x in report["actionReferences"]],
                         ["resolved", "resolved"])
        self.assertEqual([c["outcome"] for c in report["branches"][0]["cases"]],
                         ["positive", "negative"])
        self.assertEqual(before, self.graph_path.read_bytes())
        self.assertNotIn("preselected", json.dumps(self.fixture))

    def test_relative_time_and_deadline_do_not_create_dates_or_requirements(self):
        result = MODULE.inspect(self.fixture, self.root)
        link = result["sequence"][0]
        self.assertEqual(link, {"before": "S-TRIAL", "after": "S-RESULT",
                                "minDelayDays": 2})
        deadline = result["timeConstraints"][0]
        self.assertEqual(deadline["precision"], "date")
        self.assertFalse(deadline["effectiveAsCommitment"])
        self.assertIsNone(result["reviewLeads"][0]["findingType"])
        self.assertTrue(result["reviewLeads"][0]["requiresAssessment"])
        self.assertEqual(result["timeConstraints"][1]["precision"], "instant")

    def test_no_invented_accepted_action_or_observed_event(self):
        for status in ("selected", "preselected", "occurred"):
            broken = copy.deepcopy(self.fixture)
            broken["steps"][2]["state"] = status
            self.should_fail(broken, "INVALID_STEP")
        broken = copy.deepcopy(self.fixture)
        broken["steps"][1]["state"] = "planned"
        self.should_fail(broken, "EVENT_NOT_ATTESTED")
        broken = copy.deepcopy(self.fixture)
        broken["selectedCase"] = "positive"
        self.should_fail(broken, "NO_HIDDEN_COMMIT_OR_EXECUTION")
        broken = copy.deepcopy(self.fixture)
        broken["steps"][1]["observedAt"] = "2026-11-06T12:00:00Z"
        self.should_fail(broken, "STEP_CANNOT_COMMIT_OR_ATTEST")

    def test_missing_or_wrong_graph_reference_is_explicit(self):
        missing = MODULE.inspect(self.fixture)
        self.assertEqual(missing["actionReferences"][0]["verification"], "not-checked")
        self.graph_path.unlink()
        missing = MODULE.inspect(self.fixture, self.root)
        self.assertEqual(missing["actionReferences"][0]["verification"], "missing-graph")
        self.graph["identitySpace"] = "unrelated"
        self.graph_path.write_text(json.dumps(self.graph))
        self.should_fail(self.fixture, "REF_IDENTITY_SPACE_MISMATCH")

    def test_selected_action_can_be_referenced_without_new_selection(self):
        self.graph["nodes"][1]["status"] = "selected"
        self.graph_path.write_text(json.dumps(self.graph))
        before = self.graph_path.read_bytes()
        report = MODULE.inspect(self.fixture, self.root)
        self.assertEqual(report["actionReferences"][0]["actionStatus"], "selected")
        self.assertEqual(report["steps"][2]["state"], "possible")
        self.assertFalse(report["decisionCommitted"])
        self.assertEqual(self.graph_path.read_bytes(), before)

    def test_wrong_node_kind_and_changed_revision(self):
        self.graph["revision"] = 2
        self.graph_path.write_text(json.dumps(self.graph))
        result = MODULE.inspect(self.fixture, self.root)
        self.assertTrue(all(r["revisionChanged"] for r in result["actionReferences"]))
        self.graph["nodes"][1]["kind"] = "context"
        self.graph_path.write_text(json.dumps(self.graph))
        self.should_fail(self.fixture, "REF_ACTION_NOT_FOUND")

    def test_cycles_unknown_dependency_and_negative_delay_are_rejected(self):
        cycle = copy.deepcopy(self.fixture)
        cycle["sequence"].append({"before": "S-DELIVERY", "after": "S-TRIAL"})
        self.should_fail(cycle, "TEMPORAL_CYCLE")
        unknown = copy.deepcopy(self.fixture)
        unknown["sequence"].append({"before": "S-UNKNOWN", "after": "S-RESULT"})
        self.should_fail(unknown, "SEQUENCE_REFERENCE")
        negative = copy.deepcopy(self.fixture)
        negative["sequence"][0]["minDelayDays"] = -1
        self.should_fail(negative, "NEGATIVE_DELAY")

    def test_branch_coverage_overlap_and_possible_step_gate(self):
        missing = copy.deepcopy(self.fixture)
        missing["branches"][0]["cases"].pop()
        self.should_fail(missing, "BRANCH_CASES")
        duplicate = copy.deepcopy(self.fixture)
        duplicate["branches"][0]["cases"][1]["stepIds"] = ["S-A1"]
        self.should_fail(duplicate, "BRANCH_STEP_NOT_POSSIBLE_OR_REUSED")
        orphan = copy.deepcopy(self.fixture)
        orphan["steps"][0]["state"] = "possible"
        self.should_fail(orphan, "POSSIBLE_STEP_WITHOUT_BRANCH")

    def test_conditional_paths_require_event_order_and_do_not_force_both_cases(self):
        bad = copy.deepcopy(self.fixture)
        bad["sequence"] = [edge for edge in bad["sequence"]
                           if not (edge["before"] == "S-RESULT" and
                                   edge["after"] == "S-A1")]
        self.should_fail(bad, "BRANCH_WITHOUT_EVENT_ORDER")
        bad = copy.deepcopy(self.fixture)
        bad["sequence"].append({"before": "S-A1", "after": "S-A2"})
        self.should_fail(bad, "EXCLUSIVE_BRANCH_DEPENDENCY")

    def test_unrecognized_fields_cannot_smuggle_execution_claims(self):
        bad = copy.deepcopy(self.fixture)
        bad["steps"][1]["outcomeObserved"] = "positive"
        self.should_fail(bad, "INVALID_STEP")
        bad = copy.deepcopy(self.fixture)
        bad["actualEvents"] = [{"eventStepId": "S-RESULT", "outcome": "positive"}]
        self.should_fail(bad, "SCHEMA")
        bad = copy.deepcopy(self.fixture)
        bad["status"] = "accepted"
        self.should_fail(bad, "CANDIDATE_ONLY")

    def test_time_zone_date_validation_and_basis(self):
        bad = copy.deepcopy(self.fixture)
        bad["timeConstraints"][1]["at"] = "2026-11-01T09:00:00"
        self.should_fail(bad, "TIMEZONE_REQUIRED")
        bad = copy.deepcopy(self.fixture)
        bad["timeConstraints"][0]["at"] = "2026-02-30"
        with self.assertRaises(ValueError):
            MODULE.inspect(bad)
        bad = copy.deepcopy(self.fixture)
        bad["timeConstraints"][0]["basis"] = ""
        self.should_fail(bad, "TIME_CONSTRAINT")

    def test_cli_read_only_and_explicit_derived_json(self):
        input_file = self.root / "temporal.json"
        input_file.write_text(json.dumps(self.fixture))
        before = (input_file.read_bytes(), self.graph_path.read_bytes())
        run = subprocess.run(["python3", str(ROOT / "tools/rdg-temporal-plan.py"),
                              "--plan", str(input_file), "--graphs-root", str(self.root)],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["planId"], "P-DEMO")
        self.assertEqual(before, (input_file.read_bytes(), self.graph_path.read_bytes()))


if __name__ == "__main__":
    unittest.main()
