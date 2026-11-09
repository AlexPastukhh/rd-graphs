#!/usr/bin/env python3
"""Explicit temporal placement and an empty future through the real Plan writer."""
import copy
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = SourceFileLoader("placement_owner_fixture",
    str(ROOT/"tests/rdg-temporal-plan-owner.test.py")).load_module()
OWNER, ADAPTER = FIXTURE.OWNER, FIXTURE.ADAPTER
REL = FIXTURE.REL
GRAPH = "workspaces/temporal-fixture/graph.json"


class TemporalPlacementAcceptance(unittest.TestCase):
    def setUp(self):
        self.owner = FIXTURE.PlanOwnerTest(
            "test_create_edit_history_exact_snapshot_and_idempotency")
        self.owner.setUp()
        self.addCleanup(self.owner.doCleanups)
        self.graphs = self.owner.base/"graphs"
        self.graphfile = self.graphs/GRAPH
        self.graphfile.parent.mkdir(parents=True)
        self.graphfile.write_text(json.dumps({"schemaVersion":1,"revision":1,
            "id":"placement","identitySpace":"temporal-demo","rootRequirementId":"R0",
            "actionModel":"candidate-v6","edges":[],"events":[],
            "nodes":[{"id":"R0","kind":"requirement","title":"Root"}]+[
                {"id":aid,"kind":"action","title":aid,"status":"candidate"}
                for aid in ("A1","A2")]}))
        self.graph_before = self.graphfile.read_bytes()

    def plan(self, step_ids=(), sequence=(), constraints=()):
        result = copy.deepcopy(self.owner.plan)
        steps = {s["id"]:s for s in result["steps"]}
        result["steps"] = [copy.deepcopy(steps[sid]) for sid in step_ids]
        for step in result["steps"]:
            step["state"] = "planned"
        result["branches"] = []
        result["sequence"] = list(copy.deepcopy(sequence))
        result["timeConstraints"] = list(copy.deepcopy(constraints))
        return result

    def create(self, plan):
        return self.owner.apply(self.owner.request(plan=plan))

    def report(self, revision=None):
        saved = OWNER.read_snapshot(self.owner.root,REL,revision)
        return OWNER.PLAN.inspect(saved["plan"],self.graphs)

    def assert_graph_unchanged(self):
        self.assertEqual(self.graphfile.read_bytes(),self.graph_before)

    def test_empty_future_can_be_saved_placed_and_cleared_without_fake_steps(self):
        empty = self.plan()
        self.create(empty)
        original = OWNER.read_snapshot(self.owner.root,REL,1)
        report = self.report()
        self.assertEqual(report["steps"],[])
        self.assertEqual(report["actionReferences"],[])
        self.assertFalse(report["executionPerformed"])
        resource = ADAPTER.plan_resource(self.owner.root/REL,plan_root=self.owner.root)
        self.assertEqual(resource["data"]["actionRefsByStep"],{})
        self.assertEqual(resource["data"]["reviewInputsByStep"],{})
        ordered = self.plan(("S-A1","S-A2"),({"before":"S-A1","after":"S-A2"},))
        ordered["revision"] = 2
        self.owner.apply(self.owner.request("edit",1,ordered))
        self.assertEqual(len(self.report()["actionReferences"]),2)
        cleared = self.plan()
        cleared["revision"] = 3
        self.owner.apply(self.owner.request("edit",2,cleared))
        self.assertEqual(self.report()["steps"],[])
        self.assertEqual(OWNER.read_snapshot(self.owner.root,REL,1),original)
        self.assertEqual(self.report(2)["sequence"],ordered["sequence"])
        self.assert_graph_unchanged()

    def test_order_only_places_candidate_actions_without_inventing_dates(self):
        plan = self.plan(("S-A1","S-A2"),({"before":"S-A1","after":"S-A2"},))
        self.create(plan)
        report = self.report()
        self.assertEqual(report["timeConstraints"],[])
        self.assertEqual(report["sequence"],[{"before":"S-A1","after":"S-A2"}])
        self.assertEqual({r["actionStatus"] for r in report["actionReferences"]},
                         {"candidate"})
        graph = ADAPTER.graph_resource(self.graphfile,graph_ref=GRAPH)
        resource = ADAPTER.plan_resource(self.owner.root/REL,plan_root=self.owner.root)
        for aid in ("A1","A2"):
            contract = ADAPTER.DEPENDENCIES.build_action_contract(
                graph,resource,aid,["S-"+aid])
            self.assertTrue(contract["complete"])
        self.assert_graph_unchanged()

    def test_date_only_places_action_and_cannot_be_removed_leaving_it_unplaced(self):
        rule = {"stepId":"S-A1","type":"notBefore","at":"2026-11-15",
                "strength":"hypothetical","basis":"Explicit candidate placement"}
        self.create(self.plan(("S-A1",),constraints=(rule,)))
        report = self.report()
        self.assertEqual(report["sequence"],[])
        self.assertEqual(report["timeConstraints"][0]["precision"],"date")
        before = self.owner.source_bytes()
        invalid = self.plan(("S-A1",))
        invalid["revision"] = 2
        with self.assertRaisesRegex(ValueError,"ACTION_STEP_NOT_PLACED"):
            self.owner.apply(self.owner.request("edit",1,invalid))
        self.assertEqual(self.owner.source_bytes(),before)
        self.assertEqual(self.report()["planRevision"],1)
        self.assert_graph_unchanged()

    def test_legacy_snapshot_and_accepted_retry_remain_readable_after_new_rule(self):
        legacy = self.plan(("S-A1",))
        request = self.owner.request(plan=legacy,tx="legacy-accepted-create")
        new_rule = OWNER.PLAN.validate_future_write
        try:
            # Simulate the former writer accepting a structurally valid v1 Plan.
            OWNER.PLAN.validate_future_write = OWNER.PLAN.validate
            self.owner.apply(request)
        finally:
            OWNER.PLAN.validate_future_write = new_rule
        original = OWNER.read_snapshot(self.owner.root,REL,1)
        before = self.owner.source_bytes()
        self.assertTrue(self.owner.apply(request)["idempotent"])
        self.assertEqual(self.owner.source_bytes(),before)
        self.assertEqual(self.report()["actionReferences"][0]["nodeId"],"A1")
        invalid = copy.deepcopy(legacy)
        invalid["revision"] = 2
        with self.assertRaisesRegex(ValueError,"ACTION_STEP_NOT_PLACED"):
            self.owner.apply(self.owner.request("edit",1,invalid,tx="new-unplaced"))
        self.assertEqual(self.owner.source_bytes(),before)
        placed = copy.deepcopy(invalid)
        placed["timeConstraints"] = [{"stepId":"S-A1","type":"notBefore",
            "at":"2026-11-15","strength":"hypothetical","basis":"Explicit placement"}]
        self.owner.apply(self.owner.request("edit",1,placed,tx="new-placed"))
        self.assertEqual(OWNER.read_snapshot(self.owner.root,REL,1),original)
        self.assert_graph_unchanged()

    def test_unplaced_action_rejected_atomically_on_create_and_edit(self):
        before = self.owner.source_bytes()
        with self.assertRaisesRegex(ValueError,"ACTION_STEP_NOT_PLACED"):
            self.create(self.plan(("S-A1",)))
        self.assertEqual(self.owner.source_bytes(),before)
        rule = {"stepId":"S-A1","type":"deadline","at":"2026-11-15",
                "strength":"hypothetical","basis":"Explicit candidate deadline"}
        self.create(self.plan(("S-A1",),constraints=(rule,)))
        before = self.owner.source_bytes()
        invalid = self.plan(("S-A1","S-A2"),constraints=(rule,))
        invalid["revision"] = 2
        with self.assertRaisesRegex(ValueError,"ACTION_STEP_NOT_PLACED"):
            self.owner.apply(self.owner.request("edit",1,invalid))
        self.assertEqual(self.owner.source_bytes(),before)
        self.assert_graph_unchanged()


if __name__=="__main__":
    unittest.main()
