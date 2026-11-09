#!/usr/bin/env python3
"""P2-AC-04: one Action, two Plan occurrences, real writer and Gendocen."""
import copy
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = SourceFileLoader("shared_plan_fixture",
    str(ROOT/"tests/rdg-temporal-plan-owner.test.py")).load_module()
ADAPTER = FIXTURE.ADAPTER
DEP = ADAPTER.DEPENDENCIES
ENGINE = Path(os.environ.get("RDG_GENDOCEN_SOURCE", "/workspace/repos/gendocen"))
REL = FIXTURE.REL
GRAPH = "workspaces/temporal-fixture/graph.json"


class SharedActionAcceptance(unittest.TestCase):
    def setUp(self):
        self.owner = FIXTURE.PlanOwnerTest(
            "test_create_edit_history_exact_snapshot_and_idempotency")
        self.owner.setUp()
        self.addCleanup(self.owner.doCleanups)
        self.graphs = self.owner.base/"graphs"
        self.graphfile = self.graphs/GRAPH
        self.graphfile.parent.mkdir(parents=True)
        self.graph = {"schemaVersion":1,"id":"shared-action","revision":1,
            "identitySpace":"temporal-demo","rootRequirementId":"R0",
            "actionModel":"candidate-v6","edges":[],"events":[],
            "nodes":[{"id":"R0","kind":"requirement","title":"Root"}]+[
                {"id":aid,"kind":"action","title":aid,"status":"candidate",
                 "qrpe":[],"canonBlock":{"recommended":[],"contraindicated":[]}}
                for aid in ("A1","A2")]}
        self.graphfile.write_text(json.dumps(self.graph))
        self.graph_bytes = self.graphfile.read_bytes()
        for step in self.owner.plan["steps"]:
            if step["id"] == "S-A2":
                step["actionRef"]["nodeId"] = "A1"
                step["title"] = "Possible reconsideration of A1 after negative result"
        self.owner.plan["steps"].append({"id":"S-CONTROL","kind":"action",
            "title":"Unrelated A2 occurrence","state":"planned",
            "actionRef":{"graphFile":GRAPH,"identitySpace":"temporal-demo",
                         "nodeId":"A2","observedGraphRevision":1}})
        self.owner.plan["sequence"].append({"before":"S-RESULT","after":"S-CONTROL"})
        self.owner.apply(self.owner.request())
        self.original = FIXTURE.OWNER.read_snapshot(self.owner.root,REL,1)

    def saved(self):
        return FIXTURE.OWNER.read_snapshot(self.owner.root,REL)["plan"]

    def edit(self, mutate, op="edit"):
        plan = self.saved()
        expected = plan["revision"]
        plan["revision"] += 1
        mutate(plan)
        self.owner.apply(self.owner.request(op,expected,plan))

    def projections(self):
        return (ADAPTER.graph_resource(self.graphfile,graph_ref=GRAPH),
                ADAPTER.plan_resource(self.owner.root/REL,plan_root=self.owner.root))

    def assert_graph_unchanged(self):
        self.assertEqual(self.graphfile.read_bytes(),self.graph_bytes)
        graph = json.loads(self.graphfile.read_text())
        self.assertEqual(sum(n["id"]=="A1" for n in graph["nodes"]),1)
        self.assertEqual([n["status"] for n in graph["nodes"]
                          if n["kind"]=="action"],["candidate","candidate"])
        self.assertEqual(graph["events"],[])

    def test_writer_reader_keep_one_action_and_distinct_case_membership(self):
        plan = self.saved()
        report = FIXTURE.OWNER.PLAN.inspect(plan,self.graphs)
        shared = [r for r in report["actionReferences"] if r["nodeId"]=="A1"]
        self.assertEqual({r["stepId"] for r in shared},{"S-A1","S-A2"})
        self.assertEqual({r["verification"] for r in shared},{"resolved"})
        self.assertFalse(report["decisionCommitted"])
        self.assertFalse(report["eventsAttested"])
        graph, resource = self.projections()
        before = resource["data"]["reviewInputsByStep"]
        self.assertEqual(set(before["S-A1"]["branches"]),{"positive"})
        self.assertEqual(set(before["S-A2"]["branches"]),{"negative"})
        for sid in ("S-A1","S-A2"):
            DEP.build_contract(graph,resource,"A1",sid)
        self.edit(lambda p:p["branches"][0]["cases"].reverse())
        self.assertEqual(before,self.projections()[1]["data"]["reviewInputsByStep"])
        def swap(p):
            cases = p["branches"][0]["cases"]
            cases[0]["stepIds"],cases[1]["stepIds"] = cases[1]["stepIds"],cases[0]["stepIds"]
        self.edit(swap,"branch")
        after = self.projections()[1]["data"]["reviewInputsByStep"]
        self.assertNotEqual(before["S-A1"]["branches"],after["S-A1"]["branches"])
        self.assertNotEqual(before["S-A2"]["branches"],after["S-A2"]["branches"])
        self.assertEqual(before["S-CONTROL"],after["S-CONTROL"])
        unchanged = self.owner.source_bytes()
        def reuse(p):
            p["branches"][0]["cases"][1]["stepIds"] = list(
                p["branches"][0]["cases"][0]["stepIds"])
        with self.assertRaisesRegex(ValueError,"BRANCH_STEP_NOT_POSSIBLE_OR_REUSED"):
            self.edit(reuse,"branch")
        self.assertEqual(unchanged,self.owner.source_bytes())
        self.assertEqual(FIXTURE.OWNER.read_snapshot(self.owner.root,REL,1),self.original)
        self.assert_graph_unchanged()

    def test_real_engine_reviews_action_once_and_covers_both_occurrences(self):
        self.assertTrue((ENGINE/"src/docengine/cli.py").is_file())
        project = self.owner.base/"consumer"
        docs = project/"docs"
        for rel in ("_structured","review"):
            (docs/rel).mkdir(parents=True)
        (project/"docengine_project").mkdir()
        (project/"docengine.toml").write_text(
            '[docengine]\nconfig_version = 1\ndocumentation_root = "docs"\n'
            'structured_dir = "_structured"\ndependency_dir = "_dependency"\n'
            'project_package = "docengine_project"\n')
        config = project/"docengine_project/__init__.py"
        targets = [("A1","S-A1"),("A1","S-A2"),("A2","S-CONTROL")]
        complete = DEP.project_config("_structured/graph.json",
            "_structured/plan.json",targets,"shared-review")
        config.write_text(complete)
        for aid in ("A1","A2"):
            (docs/"review"/(aid+".md")).write_text("Synthetic review "+aid+"\n")
        prose = {p:p.read_bytes() for p in (docs/"review").iterdir()}
        calls = 0
        def cli(*args):
            nonlocal calls
            calls += 1
            run = subprocess.run([sys.executable,"-m","docengine.cli",*args,
                "--project-root",str(project),"--json"],capture_output=True,
                text=True,timeout=45,env={**os.environ,
                "PYTHONPATH":str(ENGINE/"src"),"PYTHONDONTWRITEBYTECODE":"1"})
            return run,json.loads(run.stdout) if run.stdout.strip() else {}
        def project_sources():
            for name,obj in zip(("graph","plan"),self.projections()):
                (docs/"_structured"/(name+".json")).write_text(json.dumps(obj))
        def renew():
            for aid in ("A1","A2"):
                target = "file://review/"+aid+".md"
                run,body = cli("explain",target)
                self.assertTrue(body.get("ok"),run.stdout+run.stderr)
                if body["data"]["computed_status"] != "valid":
                    run,body = cli("validate",target,"--result","still-valid",
                        "--reason","Synthetic shared Action only","--review-context",
                        body["data"]["review_context_id"])
                    self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        results = {}
        def expect(label,a1,a2):
            run,body = cli("check")
            self.assertTrue(body.get("data",{}).get("results"),run.stdout+run.stderr)
            actual = {r["target"].rsplit("/",1)[-1][:-3]:r["status"]
                      for r in body["data"]["results"]}
            self.assertEqual(actual,{"A1":a1,"A2":a2},label)
            results[label] = actual
            self.assertEqual({p:p.read_bytes() for p in prose},prose)
            self.assert_graph_unchanged()
        project_sources()
        run,body = cli("sync")
        self.assertTrue(body.get("ok"),run.stdout+run.stderr)
        renew()
        expect("baseline","valid","valid")
        self.edit(lambda p:p["branches"][0]["cases"].reverse())
        project_sources()
        expect("cosmetic","valid","valid")
        for sid in ("S-A1","S-A2"):
            self.edit(lambda p:p["timeConstraints"].append({"stepId":sid,
                "type":"notBefore","at":"2026-11-15","strength":"hypothetical",
                "basis":"Synthetic occurrence constraint"}))
            project_sources()
            expect(sid+"_constraint","review_required","valid")
            renew()
        def swap(p):
            cases = p["branches"][0]["cases"]
            cases[0]["stepIds"],cases[1]["stepIds"] = cases[1]["stepIds"],cases[0]["stepIds"]
        self.edit(swap,"branch")
        project_sources()
        expect("membership_swap","review_required","valid")
        renew()
        receipts = {p:p.read_bytes() for p in (docs/"_dependency/receipts").glob("*.json")}
        config.write_text(DEP.project_config("_structured/graph.json",
            "_structured/plan.json",[targets[0],targets[2]],"shared-review"))
        run,body = cli("check")
        self.assertNotEqual(run.returncode,0)
        self.assertIn("ACTION_OCCURRENCES_INCOMPLETE",run.stdout+run.stderr)
        self.assertFalse(body.get("ok"))
        self.assertEqual({p:p.read_bytes() for p in
                          (docs/"_dependency/receipts").glob("*.json")},receipts)
        config.write_text(complete)
        expect("restored","valid","valid")
        print("SHARED_ACTION_REAL_ENGINE="+json.dumps(
            {"cliProcesses":calls,"results":results,"omittedOccurrence":"rejected",
             "actionSelected":False,"sourceBytesUnchanged":True},sort_keys=True),flush=True)


if __name__=="__main__":
    unittest.main()
