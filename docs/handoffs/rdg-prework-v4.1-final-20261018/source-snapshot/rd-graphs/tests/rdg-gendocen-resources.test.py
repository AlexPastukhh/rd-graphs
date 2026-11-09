#!/usr/bin/env python3
"""Stable, read-only Gendocen projection tests without docengine dependency."""
import copy
import importlib.machinery
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = importlib.machinery.SourceFileLoader(
    "rdg_gendocen_resources", str(ROOT / "tools/rdg-gendocen-adapter.py")).load_module()


class ResourceAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rdg-gendocen-")
        self.base = Path(self.tmp.name)
        self.first = self.base / "workspaces/a/graph.json"
        self.second = self.base / "workspaces/b/graph.json"
        for path in (self.first, self.second):
            path.parent.mkdir(parents=True)
        self.graph = {"schemaVersion": 1, "id": "same-graph-id",
                      "identitySpace": "same-space", "rootRequirementId": "R0",
                      "revision": 1, "actionModel": "candidate-v6",
                      "nodes": [
                          {"id": "R0", "kind": "requirement", "title": "Root"},
                          {"id": "A1", "kind": "action", "title": "A",
                           "status": "candidate"},
                          {"id": "A2", "kind": "action", "title": "B",
                           "status": "candidate"}],
                      "edges": [{"id": "E1", "type": "DRIVES", "from": "R0", "to": "A1"}],
                      "events": []}
        self.first.write_text(json.dumps(self.graph))
        self.second.write_text(json.dumps(self.graph))
        self.plan = json.loads(
            (ROOT / "docs/examples/temporal-plan-candidate-v1.json")
            .read_text(encoding="utf8"))
        self.planfile = self.base / "plan.json"
        self.planfile.write_text(json.dumps(self.plan))

    def tearDown(self):
        self.tmp.cleanup()

    def test_different_graphs_with_same_graph_id_have_distinct_resources(self):
        a = ADAPTER.graph_resource(self.first)
        b = ADAPTER.graph_resource(self.second)
        self.assertNotEqual(a["$docengine"]["resource_id"],
                            b["$docengine"]["resource_id"])
        self.assertEqual(a["data"]["graphFile"], "workspaces/a/graph.json")
        self.assertEqual(b["data"]["graphFile"], "workspaces/b/graph.json")

    def test_reordering_nodes_json_and_revision_only_does_not_touch_semantic_digest(self):
        before = ADAPTER.graph_resource(self.first)
        reordered = copy.deepcopy(self.graph)
        reordered["nodes"].reverse()
        reordered["revision"] = 9
        self.first.write_text(json.dumps(reordered, indent=3, ensure_ascii=False))
        after = ADAPTER.graph_resource(self.first)
        self.assertEqual(before["$docengine"]["resource_id"],
                         after["$docengine"]["resource_id"])
        self.assertEqual(before["data"]["semanticSHA256"],
                         after["data"]["semanticSHA256"])
        self.assertEqual(before["data"]["nodesById"], after["data"]["nodesById"])
        self.assertNotIn("sourceSHA256", after["data"])
        self.assertEqual(after["data"]["sourceRevision"], 9)

    def test_semantic_node_changes_are_localized_by_id(self):
        old = ADAPTER.graph_resource(self.first)
        updated = copy.deepcopy(self.graph)
        updated["nodes"][2]["title"] = "Changed B"
        self.first.write_text(json.dumps(updated))
        new = ADAPTER.graph_resource(self.first)
        self.assertEqual(old["data"]["nodesById"]["A1"],
                         new["data"]["nodesById"]["A1"])
        self.assertNotEqual(old["data"]["nodesById"]["A2"],
                            new["data"]["nodesById"]["A2"])
        self.assertNotEqual(old["data"]["semanticSHA256"],
                            new["data"]["semanticSHA256"])

    def test_stable_plan_resource_has_branch_and_action_ref_paths(self):
        data = ADAPTER.plan_resource(self.planfile)
        self.assertTrue(data["$docengine"]["resource_id"].startswith("rdg.plan."))
        self.assertEqual(data["data"]["planStatus"], "candidate")
        self.assertEqual(set(data["data"]["actionRefsByStep"]), {"S-A1", "S-A2"})
        self.assertEqual(
            {case["outcome"] for case in
             data["data"]["branchesById"]["B-RESULT"]["cases"]},
            {"positive", "negative"})
        self.assertNotIn("selectedAction", data["data"])
        self.assertNotIn("sourceSHA256", data["data"])

    def test_plan_steps_reordering_and_revision_are_not_semantic(self):
        first = ADAPTER.plan_resource(self.planfile)
        altered = copy.deepcopy(self.plan)
        altered["steps"].reverse()
        altered["revision"] += 1
        self.planfile.write_text(json.dumps(altered, indent=2))
        second = ADAPTER.plan_resource(self.planfile)
        self.assertEqual(first["$docengine"]["resource_id"],
                         second["$docengine"]["resource_id"])
        self.assertEqual(first["data"]["semanticSHA256"], second["data"]["semanticSHA256"])

    def test_reordering_conditional_outcomes_and_cases_does_not_change_semantics(self):
        first = ADAPTER.plan_resource(self.planfile)
        altered = copy.deepcopy(self.plan)
        altered["steps"][1]["outcomes"].reverse()
        altered["branches"][0]["cases"].reverse()
        altered["revision"] += 1
        self.planfile.write_text(json.dumps(altered))
        second = ADAPTER.plan_resource(self.planfile)
        self.assertEqual(first["data"]["semanticSHA256"],
                         second["data"]["semanticSHA256"])
        self.assertEqual(first["data"]["branchesById"], second["data"]["branchesById"])
        self.assertEqual(first["data"]["stepsById"], second["data"]["stepsById"])

    def test_declared_graph_reference_must_match_known_workspace_path(self):
        with self.assertRaisesRegex(ValueError, "RDG_GENDOCEN_GRAPH_REF_PATH_MISMATCH"):
            ADAPTER.graph_resource(self.first, "workspaces/b/graph.json")

    def test_branch_specific_constraint_does_not_change_other_refs(self):
        old = ADAPTER.plan_resource(self.planfile)
        changed = copy.deepcopy(self.plan)
        changed["timeConstraints"].append({
            "stepId": "S-A2", "type": "notBefore", "at": "2026-11-15",
            "strength": "hypothetical", "basis": "Only negative branch"})
        self.planfile.write_text(json.dumps(changed))
        new = ADAPTER.plan_resource(self.planfile)
        self.assertEqual(old["data"]["actionRefsByStep"]["S-A1"],
                         new["data"]["actionRefsByStep"]["S-A1"])
        self.assertEqual(old["data"]["stepsById"]["S-A1"],
                         new["data"]["stepsById"]["S-A1"])
        self.assertEqual(old["data"]["timeConstraintsByStep"]["S-A2"], [])
        self.assertEqual(len(new["data"]["timeConstraintsByStep"]["S-A2"]), 1)

    def test_invalid_graph_or_plan_fails(self):
        graph = copy.deepcopy(self.graph)
        graph["nodes"].append(copy.deepcopy(graph["nodes"][0]))
        self.first.write_text(json.dumps(graph))
        with self.assertRaisesRegex(ValueError, "RDG_GENDOCEN_DUPLICATE_ID"):
            ADAPTER.graph_resource(self.first)
        plan = copy.deepcopy(self.plan)
        plan["steps"][2]["state"] = "selected"
        self.planfile.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, "TEMPORAL_PLAN_INVALID_STEP"):
            ADAPTER.plan_resource(self.planfile)

    def test_cli_uses_explicit_path_and_leaves_inputs_unchanged(self):
        before = self.first.read_bytes(), self.planfile.read_bytes()
        cmd = ["python3", str(ROOT / "tools/rdg-gendocen-adapter.py"),
               "--graph", str(self.first), "--graph-ref", "workspaces/a/graph.json"]
        first = subprocess.run(cmd, text=True, capture_output=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["data"]["graphFile"],
                         "workspaces/a/graph.json")
        cmd = ["python3", str(ROOT / "tools/rdg-gendocen-adapter.py"),
               "--plan", str(self.planfile)]
        second = subprocess.run(cmd, text=True, capture_output=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((self.first.read_bytes(), self.planfile.read_bytes()), before)

if __name__ == "__main__":
    unittest.main()
