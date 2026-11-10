#!/usr/bin/env python3
"""Behavioral and real-engine regression for scoped dependency coverage."""
import copy
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = SourceFileLoader("rdg_p0_adapter", str(ROOT / "tools/rdg-gendocen-adapter.py")).load_module()
DEP = ADAPTER.DEPENDENCIES
ENGINE = Path(os.environ.get("RDG_GENDOCEN_SOURCE", "/workspace/repos/gendocen"))


class DependencyContractTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdg-p0-dependencies-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.graphfile = self.root / "workspaces/temporal-fixture/graph.json"
        self.graphfile.parent.mkdir(parents=True)
        self.planfile = self.root / "plan.json"
        self.plan = json.loads((ROOT / "docs/examples/temporal-plan-candidate-v1.json").read_text())
        self.graph = {
            "schemaVersion": 1, "id": "synthetic-p0", "revision": 1,
            "identitySpace": "temporal-demo", "rootRequirementId": "R0",
            "actionModel": "candidate-v6", "edges": [], "events": [],
            "nodes": [{"id": "R0", "kind": "requirement", "title": "Synthetic"}] +
                     [{"id": a, "kind": "action", "status": "candidate", "qrpe": [],
                       "canonBlock": {"recommended": [{"id": "C-" + a, "text": "Review"}],
                                      "contraindicated": []}}
                      for a in ("A1", "A2")],
        }

    def projections(self):
        self.graphfile.write_text(json.dumps(self.graph))
        self.planfile.write_text(json.dumps(self.plan))
        return ADAPTER.graph_resource(self.graphfile), ADAPTER.plan_resource(self.planfile)

    def views(self):
        return self.projections()[1]["data"]["reviewInputsByStep"]

    def test_branch_reassignment_changes_both_action_contexts(self):
        before = self.views()
        cases = self.plan["branches"][0]["cases"]
        cases[0]["stepIds"], cases[1]["stepIds"] = cases[1]["stepIds"], cases[0]["stepIds"]
        after = self.views()
        for aid in ("A1", "A2"):
            self.assertNotEqual(before["S-" + aid]["branches"], after["S-" + aid]["branches"])

    def test_cosmetic_reorder_and_revision_keep_contexts(self):
        before = self.views()
        self.plan["steps"].reverse()
        self.plan["sequence"].reverse()
        self.plan["timeConstraints"].reverse()
        self.plan["branches"][0]["cases"].reverse()
        for step in self.plan["steps"]:
            if step["kind"] == "event":
                step["outcomes"].reverse()
        self.plan["revision"] += 1
        self.assertEqual(before, self.views())

    def test_alternative_only_constraint_stays_local(self):
        before = self.views()
        self.plan["timeConstraints"].append({
            "stepId": "S-A2", "type": "notBefore", "at": "2026-11-15",
            "strength": "hypothetical", "basis": "Synthetic alternative"})
        after = self.views()
        self.assertEqual(before["S-A1"], after["S-A1"])
        self.assertNotEqual(before["S-A2"], after["S-A2"])

    def test_indirect_sequence_and_first_prerequisite_constraint_are_covered(self):
        before = self.views()
        self.plan["sequence"][0]["minDelayDays"] += 1
        after = self.views()
        for aid in ("A1", "A2"):
            self.assertNotEqual(before["S-" + aid]["sequence"], after["S-" + aid]["sequence"])
        self.plan["timeConstraints"].append({
            "stepId": "S-RESULT", "type": "notBefore", "at": "2026-11-16",
            "strength": "hard", "basis": "Synthetic prerequisite"})
        latest = self.views()
        for aid in ("A1", "A2"):
            self.assertNotEqual(after["S-" + aid]["timeConstraints"],
                                latest["S-" + aid]["timeConstraints"])

    def test_action_ref_revision_is_local_but_not_historical_truth(self):
        before = self.views()
        self.plan["steps"][2]["actionRef"]["observedGraphRevision"] += 1
        after = self.views()
        self.assertNotEqual(before["S-A1"], after["S-A1"])
        self.assertEqual(before["S-A2"], after["S-A2"])
        g, p = self.projections()
        provenance = DEP.build_contract(g, p, "A1", "S-A1")["provenance"]
        self.assertEqual(provenance["observedGraphRevision"], 2)
        self.assertEqual(provenance["asOfMode"], "current-projection")
        self.assertFalse(provenance["historicalSnapshotAvailable"])

    def test_omitted_indirect_sequence_subscription_fails_closed(self):
        g, p = self.projections()
        contract = DEP.build_contract(g, p, "A1", "S-A1")
        declared = [s for s in contract["subscriptions"] if not s[0].endswith("/sequence")]
        with self.assertRaisesRegex(ValueError, "SUBSCRIPTIONS_INCOMPLETE.*sequence"):
            DEP.assert_coverage(contract, declared)

    def test_stale_or_missing_derived_context_fails_closed(self):
        g, p = self.projections()
        p["data"]["sequenceByPair"]["S-TRIAL->S-RESULT"]["minDelayDays"] += 1
        with self.assertRaisesRegex(ValueError, "PLAN_PROJECTION_INCOMPLETE_OR_STALE"):
            DEP.build_contract(g, p, "A1", "S-A1")
        g, p = self.projections()
        del p["data"]["reviewInputsByStep"]
        with self.assertRaisesRegex(ValueError, "PLAN_PROJECTION_INCOMPLETE_OR_STALE"):
            DEP.build_contract(g, p, "A1", "S-A1")

    def test_unknown_coverage_version_fails_closed(self):
        g, p = self.projections()
        p["data"]["reviewCoverage"]["contract"] = "unknown/v99"
        with self.assertRaisesRegex(ValueError, "PLAN_PROJECTION_INCOMPLETE_OR_STALE"):
            DEP.build_contract(g, p, "A1", "S-A1")

    def test_producer_source_group_omission_fails_closed_before_baseline(self):
        original = copy.deepcopy(DEP.READ_MATRIX)
        try:
            DEP.READ_MATRIX.pop("sequence")
            with self.assertRaisesRegex(ValueError, "SOURCE_GROUPS_INCOMPLETE_OR_UNKNOWN"):
                self.projections()
        finally:
            DEP.READ_MATRIX.clear()
            DEP.READ_MATRIX.update(original)

    def test_unknown_source_group_fails_closed(self):
        original = copy.deepcopy(DEP.READ_MATRIX)
        try:
            DEP.READ_MATRIX["uncovered"] = ["futureInput"]
            with self.assertRaisesRegex(ValueError, "SOURCE_GROUPS_INCOMPLETE_OR_UNKNOWN"):
                self.projections()
        finally:
            DEP.READ_MATRIX.clear()
            DEP.READ_MATRIX.update(original)

    def test_step_meaning_title_requires_review_context_change(self):
        before = self.views()
        self.plan["steps"][1]["title"] = "Receive a different event (synthetic)"
        after = self.views()
        for aid in ("A1", "A2"):
            self.assertNotEqual(before["S-" + aid], after["S-" + aid])

    def test_wrong_action_owner_fails_closed(self):
        self.plan["steps"][2]["actionRef"]["identitySpace"] = "another-owner"
        g, p = self.projections()
        with self.assertRaisesRegex(ValueError, "ACTION_OWNER_MISMATCH"):
            DEP.build_contract(g, p, "A1", "S-A1")

    def test_multiple_branches_are_explicitly_uncovered(self):
        self.plan["steps"] += [
            {"id": "E2", "kind": "event", "title": "Second event", "state": "expected",
             "outcomes": ["yes", "no"]},
            *[{"id": s, "kind": "milestone", "title": s, "state": "possible"}
              for s in ("M1", "M2")]]
        self.plan["sequence"] += [{"before": "E2", "after": s} for s in ("M1", "M2")]
        self.plan["branches"].append({"id": "B2", "eventStepId": "E2", "cases": [
            {"outcome": "yes", "stepIds": ["M1"]}, {"outcome": "no", "stepIds": ["M2"]}]})
        g, p = self.projections()
        self.assertFalse(p["data"]["reviewCoverage"]["complete"])
        with self.assertRaisesRegex(ValueError, "MULTI_BRANCH_NOT_COVERED"):
            DEP.build_contract(g, p, "A1", "S-A1")

    def test_real_engine_change_matrix_and_omission_guard(self):
        self.assertTrue((ENGINE / "src/docengine/cli.py").is_file(), "Real engine required")
        project = self.root / "engine-project"
        docs = project / "docs"
        (docs / "_structured/rdg").mkdir(parents=True)
        (docs / "review").mkdir()
        (project / "docengine_project").mkdir()
        (project / "docengine.toml").write_text(
            '[docengine]\nconfig_version = 1\ndocumentation_root = "docs"\n'
            'structured_dir = "_structured"\ndependency_dir = "_dependency"\n'
            'project_package = "docengine_project"\n')
        config = project / "docengine_project/__init__.py"
        original_config = DEP.project_config("_structured/rdg/graph.json",
            "_structured/rdg/plan.json", [("A1", "S-A1"), ("A2", "S-A2")], "p0-review")
        config.write_text(original_config)
        for aid in ("A1", "A2"):
            (docs / "review" / (aid + ".md")).write_text("Synthetic review; no user approval.\n")
        prose = {f: f.read_bytes() for f in (docs / "review").glob("*.md")}
        env = {**os.environ, "PYTHONPATH": str(ENGINE / "src"), "PYTHONDONTWRITEBYTECODE": "1"}

        def project_sources():
            g, p = self.projections()
            for name, obj in (("graph", g), ("plan", p)):
                (docs / "_structured/rdg" / (name + ".json")).write_text(json.dumps(obj))

        def cli(*args):
            proc = subprocess.run([sys.executable, "-m", "docengine.cli", *args,
                "--project-root", str(project), "--json"], capture_output=True, text=True,
                env=env, timeout=45)
            return proc, json.loads(proc.stdout) if proc.stdout.strip() else {}

        def renew():
            for aid in ("A1", "A2"):
                target = "file://review/" + aid + ".md"
                proc, body = cli("explain", target)
                self.assertTrue(body.get("ok"), proc.stderr + proc.stdout)
                if body["data"]["computed_status"] == "valid":
                    continue
                proc, body = cli("validate", target, "--result", "still-valid",
                    "--reason", "Synthetic baseline only", "--review-context",
                    body["data"]["review_context_id"])
                self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

        results = {}
        def expect(label, a1, a2):
            proc, body = cli("check")
            self.assertTrue(body.get("data", {}).get("results"), proc.stderr + proc.stdout)
            actual = {r["target"].rsplit("/", 1)[-1][:-3]: r["status"]
                      for r in body["data"]["results"]}
            self.assertEqual(actual, {"A1": a1, "A2": a2}, label)
            self.assertEqual({f: f.read_bytes() for f in prose}, prose)
            results[label] = actual

        project_sources()
        cli("sync")
        renew()
        expect("baseline", "valid", "valid")
        self.plan["steps"].reverse()
        self.plan["sequence"].reverse()
        self.plan["branches"][0]["cases"].reverse()
        for step in self.plan["steps"]:
            if step["kind"] == "event": step["outcomes"].reverse()
        self.plan["revision"] += 1
        self.graph["revision"] += 1
        self.graph["nodes"].reverse()
        project_sources()
        expect("cosmetic_reorder", "valid", "valid")
        cases = self.plan["branches"][0]["cases"]
        cases[0]["stepIds"], cases[1]["stepIds"] = cases[1]["stepIds"], cases[0]["stepIds"]
        project_sources()
        expect("branch_swap", "review_required", "review_required")
        renew()
        self.plan["timeConstraints"].append({"stepId": "S-A2", "type": "notBefore",
            "at": "2026-11-17", "strength": "soft", "basis": "Synthetic A2 only"})
        project_sources()
        expect("A2_only", "valid", "review_required")
        renew()
        edge = next(e for e in self.plan["sequence"] if e["before"] == "S-TRIAL")
        edge["minDelayDays"] += 1
        project_sources()
        expect("indirect_sequence", "review_required", "review_required")
        renew()
        self.plan["timeConstraints"].append({"stepId": "S-RESULT", "type": "notBefore",
            "at": "2026-11-18", "strength": "hard", "basis": "Synthetic indirect prerequisite"})
        project_sources()
        expect("first_indirect_constraint", "review_required", "review_required")
        renew()
        self.plan["steps"].append({"id": "S-NEW", "kind": "milestone",
            "title": "New prerequisite", "state": "planned"})
        self.plan["sequence"].append({"before": "S-NEW", "after": "S-TRIAL", "minDelayDays": 4})
        project_sources()
        expect("new_indirect_predecessor", "review_required", "review_required")
        renew()
        next(s for s in self.plan["steps"] if s["id"] == "S-A1")["actionRef"]["observedGraphRevision"] += 1
        project_sources()
        expect("A1_ref_revision", "review_required", "valid")
        renew()
        next(n for n in self.graph["nodes"] if n["id"] == "A2")["status"] = "selected"
        project_sources()
        expect("A2_status", "valid", "review_required")
        renew()
        node = next(n for n in self.graph["nodes"] if n["id"] == "A1")
        node["canonBlock"]["recommended"][0]["text"] = "Synthetic changed canon"
        project_sources()
        expect("A1_canon", "review_required", "valid")
        renew()
        next(r for r in self.plan["timeConstraints"] if r["type"] == "deadline")["at"] = "2026-11-19"
        project_sources()
        expect("shared_deadline", "review_required", "review_required")
        renew()
        node["qrpe"].append({"id": "U1", "status": "open", "text": "Synthetic uncertainty"})
        project_sources()
        expect("A1_qrpe", "review_required", "valid")
        renew()
        receipts = {f: f.read_bytes() for f in (docs / "_dependency/receipts").glob("*.json")}
        state = docs / "_dependency/state/dependency_state.json"
        config.write_text(original_config.replace("sources = contract['subscriptions']",
            "sources = [s for s in contract['subscriptions'] if not s[0].endswith('/sequence')]"))
        for command in ("check", "validate"):
            args = (command,) if command == "check" else (command, "file://review/A1.md",
                "--result", "still-valid", "--reason", "Must reject missing coverage",
                "--review-context", "stale-test-context")
            proc, body = cli(*args)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("SUBSCRIPTIONS_INCOMPLETE", proc.stdout + proc.stderr)
            self.assertFalse(body.get("ok"))
            if command == "check":
                self.assertEqual(body["meta"]["status"], "current_project_code_unavailable")
                after_check_state = state.read_bytes()
            else:
                self.assertEqual(state.read_bytes(), after_check_state)
        self.assertEqual({f: f.read_bytes() for f in
                          (docs / "_dependency/receipts").glob("*.json")}, receipts)
        results["omitted_indirect_subscription"] = "fail-closed; check records unavailable-registry diagnostic; validate/state and receipts unchanged"
        config.write_text(original_config)
        renew()
        expect("restored_complete_contract", "valid", "valid")
        print("P0_REAL_ENGINE_MATRIX=" + json.dumps(results, sort_keys=True), flush=True)


if __name__ == "__main__":
    unittest.main()
