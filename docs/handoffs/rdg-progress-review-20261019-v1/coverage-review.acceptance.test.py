#!/usr/bin/env python3
"""Review fault injection; missing declaration must not silently remain valid.

Only temp synthetic inputs/config are changed. Repository source is not edited.
One expected product/proof failure until source-group coverage is independent.
"""
from importlib.machinery import SourceFileLoader
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = SourceFileLoader("review_dependency_fixture", str(ROOT / "tests/rdg-gendocen-dependencies.test.py")).load_module()
ADAPTER = FIXTURE.ADAPTER
DEP = ADAPTER.DEPENDENCIES
ENGINE = Path(os.environ.get("RDG_GENDOCEN_SOURCE", "/workspace/repos/gendocen"))


def run_probe(mode):
    fixture = FIXTURE.DependencyContractTest()
    fixture.setUp()
    original_matrix = copy.deepcopy(DEP.READ_MATRIX)
    try:
        if mode == "missing-source-group":
            # Simulate an accidentally omitted declaration at the producer,
            # rather than dropping a source after build_contract has returned.
            DEP.READ_MATRIX.pop("sequence")
        project = fixture.root / "review-project"
        docs = project / "docs"
        (docs / "_structured/rdg").mkdir(parents=True)
        (docs / "review").mkdir()
        (project / "docengine_project").mkdir()
        (project / "docengine.toml").write_text(
            '[docengine]\nconfig_version = 1\ndocumentation_root = "docs"\n'
            'structured_dir = "_structured"\ndependency_dir = "_dependency"\n'
            'project_package = "docengine_project"\n')
        config = DEP.project_config("_structured/rdg/graph.json", "_structured/rdg/plan.json",
            [("A1", "S-A1"), ("A2", "S-A2")], "audit-coverage")
        if mode == "missing-source-group":
            config = config.replace("def register_semantic_dependencies(registry):\n",
                "def register_semantic_dependencies(registry):\n    dependency.READ_MATRIX.pop('sequence', None)\n")
        (project / "docengine_project/__init__.py").write_text(config)
        for aid in ("A1", "A2"):
            (docs / "review" / (aid + ".md")).write_text("Synthetic dependency review.\n")
        env = {**os.environ, "PYTHONPATH": str(ENGINE / "src"), "PYTHONDONTWRITEBYTECODE": "1"}

        def cli(*args):
            r = subprocess.run([sys.executable, "-m", "docengine.cli", *args,
                "--project-root", str(project), "--json"], text=True, capture_output=True,
                env=env, timeout=45)
            return r.returncode, json.loads(r.stdout)

        def project_sources():
            graph, plan = fixture.projections()
            for name, obj in (("graph", graph), ("plan", plan)):
                (docs / "_structured/rdg" / (name + ".json")).write_text(json.dumps(obj))
            return graph, plan

        graph, before = project_sources()
        contract = DEP.build_contract(graph, before, "A1", "S-A1")
        DEP.assert_coverage(contract, contract["subscriptions"])
        cli("sync")
        for aid in ("A1", "A2"):
            target = "file://review/" + aid + ".md"
            _, explanation = cli("explain", target)
            code, validated = cli("validate", target, "--result", "still-valid",
                "--reason", "Synthetic review baseline only", "--review-context",
                explanation["data"]["review_context_id"])
            assert code == 0 and validated["ok"], validated
        if mode == "event-title":
            next(s for s in fixture.plan["steps"] if s["id"] == "S-RESULT")["title"] = (
                "Receive deletion authorization instead of experiment outcome (synthetic)")
        else:
            fixture.plan["sequence"][0]["minDelayDays"] += 9
        fixture.plan["revision"] += 1
        _, after = project_sources()
        code, body = cli("check")
        contexts_before, contexts_after = before["data"]["reviewInputsByStep"], after["data"]["reviewInputsByStep"]
        result = {
            "mode": mode, "engine": body["meta"]["engine_version"],
            "coverageComplete": after["data"]["reviewCoverage"]["complete"],
            "declaredGroups": sorted(after["data"]["reviewCoverage"]["sourceReads"]),
            "computedFacets": sorted(contexts_after["S-A1"]),
            "changedFacets": [key for key in contexts_before["S-A1"]
                              if contexts_before["S-A1"][key] != contexts_after["S-A1"][key]],
            "projectionSemanticHashChanged": before["data"]["semanticSHA256"] != after["data"]["semanticSHA256"],
            "registeredSources": [s[0] for s in contract["subscriptions"]],
            "guardAccepted": True, "checkExitCode": code, "checkOk": body["ok"],
            "statuses": {r["target"].rsplit("/", 1)[-1][:-3]: r["status"]
                         for r in body["data"]["results"]}}
        print("REVIEW_PROBE=" + json.dumps(result, sort_keys=True), flush=True)
        return result
    finally:
        DEP.READ_MATRIX.clear()
        DEP.READ_MATRIX.update(original_matrix)
        fixture.doCleanups()


class CoverageReviewAcceptance(unittest.TestCase):
    def test_current_sequence_subscription_detects_change(self):
        result = run_probe("normal-sequence")
        self.assertEqual(result["statuses"], {"A1": "review_required", "A2": "review_required"})

    def test_omitted_source_group_must_not_claim_complete_and_stay_valid(self):
        result = run_probe("missing-source-group")
        self.assertFalse(result["guardAccepted"] and result["coverageComplete"] and
                         result["checkOk"] and all(x == "valid" for x in result["statuses"].values()),
                         "Actual sequence facet changed but omitted source-group declaration was accepted as complete.")


if __name__ == "__main__":
    run_probe("event-title")
    unittest.main()
