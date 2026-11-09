#!/usr/bin/env python3
"""Deep candidate planning and real result history through the bearer writer."""
import copy
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIX = SourceFileLoader("deep_bearer_fixture", str(ROOT/"tests/rdg-bearer-package.integration.test.py")).load_module()
MODEL = SourceFileLoader("deep_action_model", str(ROOT/"tools/rdg-v7-model.py")).load_module()


class DeepAction(unittest.TestCase):
    def setUp(self):
        FIX.BearerPackage.setUp(self)
        self.seq = 0
        self.token = self.grant(["graph.write", "graph.read"])["token"]
        self.assert_ok(self.write(self.create(), self.token))
        for name in ("rdg-activity.py", "rdg-root-projection.js"):
            shutil.copy2(ROOT/"tools"/name, self.home/"tools"/name)

    def read(self):
        return json.loads(self.path.read_text())

    def event(self, kind, **rest):
        self.seq += 1
        return {"id": "EV-"+str(self.seq), "type": kind, "by": "assistant",
                "note": "Synthetic result or graph change", **rest}

    def add(self, aid, rid="R0", action_type="general"):
        return {"op": "add_action", "requirementId": rid,
                "action": {"id": aid, "kind": "action", "title": aid,
                           "status": "candidate", "actionType": action_type,
                           "canonBlock": {"recommended": [{"id": "C-"+aid, "text": "Applicable case"}],
                                          "contraindicated": []},
                           "qrpe": [{"id": "Q-"+aid, "text": "Check the case", "status": "open"}]}}

    def edit(self, kind, **rest):
        return {"op": "graph_edit", "action": kind, **rest,
                "event": self.event("graph_changed", operation=kind)}

    def prepare(self, aid, rid, role="subgoal", existing=False):
        args = {"requirementId": rid} if existing else {
            "node": {"id": rid, "kind": "requirement", "title": rid}}
        return self.edit("prepare_action_requirement", actionId=aid,
                         edgeId="potential-"+aid+"-"+rid, childRole=role, **args)

    def choose(self, aid, rid="R0"):
        return {"op": "select_action", "actionId": aid,
                "event": self.event("action_selected", actionId=aid, driverRequirementId=rid)}

    def result(self, nid, action=False):
        return {"op": "record_action_execution" if action else "record_requirement_achievement",
                "targetId": nid, "event": self.event(
                    "action_executed" if action else "requirement_achieved", targetId=nid)}

    def apply(self, operations, tid=None, token=None):
        revision = self.read()["revision"]
        package = self.patch(operations, revision, tid or "tx-"+str(revision))
        self.assert_ok(self.write(package, token or self.token))
        return package

    def states(self):
        return MODEL.completion_state(self.read())

    def sources(self):
        return {str(p.relative_to(self.home)): p.read_bytes()
                for p in (self.home/"graphs").rglob("*") if p.is_file()}

    def projection(self, include=True):
        script = "const p=require(process.argv[1]); let g=JSON.parse(require('fs').readFileSync(0,'utf8')); console.log(JSON.stringify(p.project({graphs:[{slug:'demo',graph:g}],relations:[]},'demo',{includePotential:"+str(include).lower()+"})));"
        r = subprocess.run(["node", "-e", script, str(self.home/"tools/rdg-root-projection.js")],
                           input=json.dumps(self.read()), text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def activity(self, token=None):
        r = subprocess.run(["python3", "-B", str(self.home/"tools/rdg-activity.py"),
                            "--graph-root", str(self.home/"graphs"), "--graph", self.rel],
                           text=True, capture_output=True,
                           env={**self.env, "RDG_AUTH_TOKEN": token or self.token})
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_deep_unselected_branch_retains_canons_qrpe_and_distinct_roles(self):
        self.apply([self.add("A0", action_type="decomposition"), self.prepare("A0", "R1"),
                    self.prepare("A0", "RC0", "method_correctness"), self.add("A1", "R1"),
                    self.prepare("A1", "R2", "method_correctness"),
                    self.add("A2", "R2", "decomposition"), self.prepare("A2", "R3"),
                    self.add("A3", "R3"), self.prepare("A3", "RC3", "method_correctness")])
        self.apply([self.edit("edit_node", nodeId="A3", changes={"canonBlock": {
            "recommended": [{"id": "C-DEEP", "text": "Deep candidate canon"}], "contraindicated": []}}),
            {"op": "append_qrpe", "targetId": "A3", "issue": {
                "id": "Q-DEEP", "text": "Deep branch challenge", "status": "open"}}])
        g = self.read()
        self.assertTrue(all(n["status"] == "candidate" for n in g["nodes"] if n["kind"] == "action"))
        self.assertFalse(any(e["type"] == "INTRODUCES" for e in g["edges"]))
        self.assertFalse(any(e["type"] in MODEL.COMPLETION_EVENTS or e["type"] == "action_selected" for e in g["events"]))
        deep = next(n for n in g["nodes"] if n["id"] == "A3")
        self.assertEqual(deep["canonBlock"]["recommended"][0]["id"], "C-DEEP")
        self.assertEqual(deep["qrpe"][-1]["id"], "Q-DEEP")
        self.assertEqual({n["id"] for n in self.projection()["nodes"]}, {"R0", "R1", "RC0", "R2", "R3", "RC3"})
        self.assertEqual([n["id"] for n in self.projection(False)["nodes"]], ["R0"])
        self.assertTrue(all(n["branchState"] == "potential" for n in self.projection()["nodes"] if n["id"] != "R0"))
        self.assertFalse(any(row["complete"] for row in self.states().values()))

    def test_select_promotes_same_ids_without_accepting_descendants_or_other_group(self):
        self.apply([self.add("D1", action_type="decomposition"), self.prepare("D1", "R1"),
                    self.prepare("D1", "R2"), self.add("D2", action_type="decomposition"),
                    self.prepare("D2", "R1", existing=True), self.prepare("D2", "R-ALT"),
                    self.add("DEEP", "R1"), self.prepare("DEEP", "R-DEEP", "method_correctness")])
        before = self.read()
        self.apply([self.choose("D1")])
        g = self.read(); ns = {n["id"]: n for n in g["nodes"]}
        self.assertEqual(ns["D1"]["status"], "selected")
        self.assertEqual(ns["D2"]["status"], "candidate")
        self.assertEqual(ns["DEEP"]["status"], "candidate")
        self.assertEqual(ns["R1"]["status"], "active")
        self.assertEqual(ns["R-DEEP"]["status"], "potential")
        self.assertEqual(len(g["nodes"]), len(before["nodes"]))
        self.assertEqual(ns["D1"]["canonBlock"], before["nodes"][1]["canonBlock"])
        self.assertEqual({e["to"] for e in g["edges"] if e["type"] == "INTRODUCES"}, {"R1", "R2"})
        self.assertEqual({n["id"] for n in self.projection(False)["nodes"]}, {"R0", "R1", "R2"})

    def test_potential_cycle_unknown_type_and_empty_decomposition_fail_atomically(self):
        self.apply([self.add("D", action_type="decomposition")])
        for ops, reason in [([self.prepare("D", "R0", existing=True)], "cycle"),
                            ([self.choose("D")], "at least one subgoal"),
                            ([self.add("BAD", action_type="made-up")], "invalid Action type")]:
            before = self.sources()
            self.assert_denied(self.write(self.patch(ops, self.read()["revision"], "bad-"+str(self.seq)), self.token), reason)
            self.assertEqual(self.sources(), before)

    def test_decomposition_execution_does_not_mean_its_subgoals_are_achieved(self):
        self.apply([self.add("D", action_type="decomposition"), self.prepare("D", "R1"),
                    self.prepare("D", "R2"), self.choose("D")])
        self.assertFalse(self.states()["D"]["complete"])
        self.apply([self.result("D", action=True)])
        self.assertTrue(self.states()["D"]["complete"])
        self.assertFalse(self.states()["R0"]["complete"])
        self.apply([self.result("R1")])
        self.assertFalse(self.states()["R0"]["complete"])
        self.apply([self.result("R2")])
        self.assertTrue(self.states()["R0"]["complete"])
        events = [e for e in self.read()["events"] if e["type"] in MODEL.COMPLETION_EVENTS]
        self.assertEqual([(e["type"], e["targetId"]) for e in events], [
            ("action_executed", "D"), ("requirement_achieved", "R1"),
            ("requirement_achieved", "R2"), ("requirement_achieved", "R0")])
        self.assertEqual(events[-1]["completionMode"], "derived")

    def test_mixed_action_uses_correctness_for_itself_and_subgoals_for_parent(self):
        self.apply([self.add("A"), self.prepare("A", "RS"),
                    self.prepare("A", "RC", "method_correctness"), self.add("ALT"),
                    self.prepare("ALT", "RX", "method_correctness"), self.choose("A")])
        before = self.sources()
        self.assert_denied(self.write(self.patch([self.result("A", action=True)],
                           self.read()["revision"], "premature"), self.token), "required work")
        self.assertEqual(self.sources(), before)
        self.apply([self.result("RC")])
        self.assertTrue(self.states()["A"]["complete"])
        self.assertFalse(self.states()["R0"]["complete"])
        self.assertFalse(self.states()["RX"]["complete"])
        self.apply([self.result("RS")])
        self.assertTrue(self.states()["R0"]["complete"])
        self.assertTrue(any(e.get("targetId") == "A" and e.get("completionMode") == "derived" for e in self.read()["events"]))

    def test_leaf_no_extra_result_goal_and_later_definition_edit_preserves_history(self):
        self.apply([self.add("LEAF"), self.choose("LEAF")])
        self.assertFalse(self.states()["LEAF"]["complete"])
        self.apply([self.result("LEAF", action=True)])
        self.assertTrue(self.states()["R0"]["complete"])
        old = [e for e in self.read()["events"] if e["type"] in MODEL.COMPLETION_EVENTS]
        self.assertEqual(len(self.read()["nodes"]), 2)
        self.apply([self.edit("edit_node", nodeId="LEAF", changes={"title": "Changed definition"})])
        self.assertFalse(self.states()["LEAF"]["complete"])
        self.assertFalse(self.states()["R0"]["complete"])
        self.assertEqual([e for e in self.read()["events"] if e["type"] in MODEL.COMPLETION_EVENTS], old)
        self.apply([self.result("LEAF", action=True)])
        self.assertTrue(self.states()["R0"]["complete"])
        self.assertEqual(len([e for e in self.read()["events"] if e["type"] in MODEL.COMPLETION_EVENTS]), 4)

    def test_denied_result_candidate_and_separate_grants_cannot_forge_completion(self):
        self.apply([self.add("A")])
        before = self.sources()
        self.assert_denied(self.write(self.patch([self.result("A", action=True)], 2, "candidate-result"), self.token), "actual selected scope")
        self.assertEqual(self.sources(), before)
        self.apply([self.choose("A")])
        author = self.grant(["graph.add_action", "graph.append_qrpe"])["token"]
        before = self.sources()
        self.assert_denied(self.write(self.patch([self.result("A", action=True)], 3, "author-result"), author), "MISSING_PERMISSION")
        self.assertEqual(self.sources(), before)
        fake = {"op": "append_event", "event": self.event("action_executed", targetId="A")}
        generic = self.grant(["graph.append_event"])["token"]
        self.assert_denied(self.write(self.patch([fake], 3, "fake-event"), generic), "DEDICATED_OPERATION")
        self.assertEqual(self.sources(), before)
        forged = self.result("A", action=True); forged["event"]["by"] = "user"
        self.assert_denied(self.write(self.patch([forged], 3, "fake-user"), self.token), "CANNOT_CLAIM_USER")
        self.assertEqual(self.sources(), before)

    def test_activity_shows_edits_results_actor_and_idempotency_without_schedule(self):
        self.apply([self.add("A")]); self.apply([self.choose("A")])
        request = self.apply([self.result("A", action=True)])
        before = self.sources()
        self.assert_ok(self.write(request, self.token))
        self.assertEqual(self.sources(), before)
        report = self.activity()
        self.assertEqual(self.sources(), before)
        rows = report["activities"]
        self.assertEqual(len([r for r in rows if r["kind"] == "graph_saved"]), 4)
        self.assertEqual({(r["kind"], r["targetId"]) for r in rows if r["kind"] != "graph_saved"},
                         {("action_executed", "A"), ("requirement_achieved", "R0")})
        self.assertEqual(len(rows), len({r["id"] for r in rows}))
        self.assertTrue(all(r["recordedAt"] for r in rows))
        self.assertTrue(all(r.get("authorityPrincipals") for r in rows if r["kind"] == "graph_saved"))
        self.assertTrue(report["currentCompletion"][self.rel]["R0"]["complete"])
        self.assertFalse((self.home/"plans").exists())
        denied = self.grant(["graph.read"], ["workspaces/another/graph.json"])["token"]
        r = subprocess.run(["python3", "-B", str(self.home/"tools/rdg-activity.py"),
                            "--graph-root", str(self.home/"graphs"), "--graph", self.rel],
                           text=True, capture_output=True, env={**self.env, "RDG_AUTH_TOKEN": denied})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("GRAPH_READ_SCOPE_DENIED", r.stderr)

    def test_unavailable_projection_blocks_composite_without_erasing_result_history(self):
        self.apply([self.add("A"), self.prepare("A", "RC", "method_correctness"), self.choose("A")])
        graph = self.read()
        next(n for n in graph["nodes"] if n["id"] == "RC")["projectionOf"] = {"graphSlug": "missing", "nodeId": "RC"}
        states = MODEL.completion_state(graph)
        self.assertFalse(states["RC"]["complete"])
        self.assertFalse(states["A"]["complete"])
        self.assertFalse(states["R0"]["complete"])


    def test_composite_definition_change_needs_result_review_instead_of_auto_success(self):
        self.apply([self.add("A"), self.prepare("A", "RC", "method_correctness"), self.choose("A")])
        self.apply([self.result("RC")])
        self.assertTrue(self.states()["A"]["complete"])
        old = [e for e in self.read()["events"] if e["type"] in MODEL.COMPLETION_EVENTS]
        self.apply([self.edit("edit_node", nodeId="A", changes={"definition": "New execution definition"})])
        self.assertFalse(self.states()["A"]["complete"])
        self.assertEqual(self.states()["A"]["reason"], "definition-changed-result-review")
        self.assertEqual([e for e in self.read()["events"] if e["type"] in MODEL.COMPLETION_EVENTS], old)
        self.apply([self.result("A", action=True)])
        self.assertTrue(self.states()["A"]["complete"])
        self.assertTrue(self.states()["R0"]["complete"])

    def test_unknown_child_role_is_incomplete_and_annotation_does_not_erase_results(self):
        self.apply([self.add("A"), self.prepare("A", "RC", "method_correctness"), self.choose("A")])
        self.apply([self.result("RC")])
        self.assertTrue(self.states()["A"]["complete"])
        self.apply([{"op": "append_qrpe", "targetId": "A", "issue": {
            "id": "Q-POST", "text": "Post-result discussion", "status": "open"}}])
        self.assertTrue(self.states()["A"]["complete"])
        g = self.read()
        next(e for e in g["edges"] if e["type"] == "INTRODUCES").pop("childRole")
        self.assertFalse(MODEL.completion_state(g)["A"]["complete"])
        self.assertFalse(MODEL.completion_state(g)["R0"]["complete"])
        with self.assertRaisesRegex(ValueError, "unknown roles"):
            MODEL.record_completion(g, self.result("A", action=True))

    def test_potential_composition_can_be_revised_without_accepting_it(self):
        self.apply([self.add("D", action_type="decomposition"), self.prepare("D", "R1"),
                    self.prepare("D", "R2")])
        self.apply([self.edit("archive_edge", edgeId="potential-D-R2"),
                    self.prepare("D", "R3")])
        self.assertEqual({n["id"] for n in self.projection()["nodes"]}, {"R0", "R1", "R3"})
        self.assertEqual(next(n for n in self.read()["nodes"] if n["id"] == "D")["status"], "candidate")
        self.assertFalse(any(e["type"] == "action_selected" for e in self.read()["events"]))
        self.apply([self.choose("D")])
        self.assertEqual({e["to"] for e in self.read()["edges"] if e["type"] == "INTRODUCES"}, {"R1", "R3"})

    def test_dry_run_and_recovered_result_have_no_duplicate_success_in_activity(self):
        self.apply([self.add("A"), self.choose("A")])
        request = self.patch([self.result("A", action=True)], self.read()["revision"], "recover-result")
        inp = self.home/"result-request.json"; inp.write_text(json.dumps(request))
        env = {**self.env, "RDG_AUTH_TOKEN": self.token}
        before = self.sources()
        dry = subprocess.run(["python3", "-B", str(self.home/"tools/graph-apply.py"),
                              "--package", "--patch", str(inp), "--dry-run"],
                             text=True, capture_output=True, env=env)
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertEqual(self.sources(), before)
        script = "from importlib.machinery import SourceFileLoader\nimport json,os,sys\nw=SourceFileLoader('crash_writer',sys.argv[1]).load_module()\nreal_write=w.write_json\ndef crash_after_graph(path,obj):\n real_write(path,obj)\n if path.name=='graph.json':os._exit(91)\nw.write_json=crash_after_graph\nw.execute(json.load(open(sys.argv[2])))"
        crashed = subprocess.run(["python3", "-B", "-c", script,
                                  str(self.home/"tools/graph-package.py"), str(inp)],
                                 text=True, capture_output=True, env=env)
        self.assertEqual(crashed.returncode, 91, crashed.stderr)
        # The image already contains results, but the journal has not completed.
        self.assertTrue(self.states()["A"]["complete"])
        pending = subprocess.run(["python3", "-B", str(self.home/"tools/rdg-activity.py"),
                                  "--graph-root", str(self.home/"graphs"), "--graph", self.rel],
                                 text=True, capture_output=True, env=env)
        self.assertNotEqual(pending.returncode, 0)
        self.assertIn("ACTIVITY_RECOVERY_REQUIRED", pending.stderr)
        self.assert_ok(self.write(request, self.token))
        recovered = self.activity()
        results = [r for r in recovered["activities"] if r["kind"] in MODEL.COMPLETION_EVENTS]
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["recordedAt"] for r in results))
        self.assert_ok(self.write(request, self.token))
        self.assertEqual(self.activity(), recovered)

    def test_create_select_execute_in_one_transaction_needs_no_temporal_step(self):
        self.apply([self.add("IMMEDIATE"), self.choose("IMMEDIATE"),
                    self.result("IMMEDIATE", action=True)])
        self.assertTrue(self.states()["IMMEDIATE"]["complete"])
        self.assertTrue(self.states()["R0"]["complete"])
        self.assertEqual(len(self.read()["nodes"]), 2)
        self.assertFalse((self.home/"plans").exists())

    def test_unchanged_graph_in_multifile_transaction_is_not_a_saved_edit(self):
        token = self.grant(["graph.write", "graph.read"], ["workspaces/"])["token"]
        other = copy.deepcopy(self.graph)
        other["id"] = "other"; other["identitySpace"] = "other"
        other.pop("actionModel")  # Existing legacy metadata can be a genuine no-op.
        rel = "workspaces/other/graph.json"
        self.assert_ok(self.write({"schemaVersion": 1, "transactionId": "other-create",
                                   "changes": [{"file": rel, "create": other}]}, token))
        self.assert_ok(self.write({"schemaVersion": 1, "transactionId": "multi-one-change", "changes": [
            {"file": rel, "metadata": {"planningScale": "module"},
             "patch": {"schemaVersion": 1, "expectedRevision": 1, "operations": []}},
            {"file": self.rel, "patch": {"schemaVersion": 1, "expectedRevision": 1, "operations": [self.add("OTHER")]}}
        ]}, token))
        run = subprocess.run(["python3", "-B", str(self.home/"tools/rdg-activity.py"),
                              "--graph-root", str(self.home/"graphs"), "--graph", self.rel, "--graph", rel],
                             text=True, capture_output=True, env={**self.env, "RDG_AUTH_TOKEN": token})
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(run.stdout)
        other_rows = [r for r in report["activities"] if r["graphFile"] == rel]
        self.assertEqual(len(other_rows), 1)
        self.assertEqual(other_rows[0]["transactionId"], "other-create")
        self.assertEqual(len(report["activities"]), 3)

    def link(self, aid, rid, role="subgoal"):
        edge_id = "linked-"+aid+"-"+rid
        return {"op": "link_action_requirement", "actionId": aid,
                "requirementId": rid, "edgeId": edge_id, "childRole": role,
                "event": self.event("action_requirement_linked", actionId=aid,
                    requirementId=rid, edgeId=edge_id, driverRequirementId="R0")}

    def actual_requirement(self, rid):
        return self.edit("create_requirement", node={"id": rid, "kind": "requirement", "title": rid},
                         parentRequirementId="R0", edgeId="refinement-"+rid)

    def test_output_set_changes_result_scope_without_requiring_subgoal_achievement(self):
        self.apply([self.add("D", action_type="decomposition"), self.prepare("D", "R1"), self.choose("D")])
        self.apply([self.result("D", action=True), self.result("R1")])
        old = self.states()["D"]
        history = [e for e in self.read()["events"] if e["type"] in MODEL.COMPLETION_EVENTS]
        self.apply([self.actual_requirement("R2"), self.link("D", "R2")])
        now = self.states()["D"]
        self.assertNotEqual(old["basisSHA256"], now["basisSHA256"])
        self.assertFalse(now["complete"])
        self.assertEqual([e for e in self.read()["events"] if e["type"] in MODEL.COMPLETION_EVENTS], history)
        # Recording creation/selection of the new group does not achieve its goals.
        self.apply([self.result("D", action=True)])
        self.assertTrue(self.states()["D"]["complete"])
        self.assertFalse(self.states()["R2"]["complete"])
        self.assertFalse(self.states()["R0"]["complete"])
        event = next(e for e in reversed(self.read()["events"]) if e.get("targetId") == "D")
        self.assertEqual({o["node"]["id"] for o in event["basis"]["outputs"]}, {"R1", "R2"})
        self.apply([self.result("R2")])
        self.assertTrue(self.states()["R0"]["complete"])

    def test_mixed_general_action_gets_new_output_scope_from_completed_correctness(self):
        self.apply([self.add("A"), self.prepare("A", "R1"),
                    self.prepare("A", "RC", "method_correctness"), self.choose("A")])
        self.apply([self.result("RC")])
        old = self.states()["A"]
        self.apply([self.actual_requirement("R2"), self.link("A", "R2")])
        now = self.states()["A"]
        self.assertTrue(now["complete"])
        self.assertNotEqual(old["basisSHA256"], now["basisSHA256"])
        self.assertNotEqual(old["eventId"], now["eventId"])
        self.assertFalse(self.states()["R2"]["complete"])
        self.assertFalse(self.states()["R0"]["complete"])
        old_event = next(e for e in self.read()["events"] if e["id"] == old["eventId"])
        self.assertEqual([o["node"]["id"] for o in old_event["basis"]["outputs"]], ["R1"])

    def test_selected_decomposition_cannot_lose_its_last_active_output(self):
        self.apply([self.add("D", action_type="decomposition"), self.prepare("D", "RS"),
                    self.prepare("D", "RC", "method_correctness"), self.choose("D")])
        for operation in (self.edit("detach_requirement", edgeId="potential-D-RS"),
                          self.edit("edit_node", nodeId="RS", changes={"active": False})):
            before = self.sources()
            request = self.patch([operation], self.read()["revision"], "invalid-empty-"+operation["action"])
            self.assert_denied(self.write(request, self.token), "selected decomposition requires")
            self.assertEqual(self.sources(), before)
        self.apply([self.result("RC")])
        self.assertTrue(self.states()["D"]["complete"])
        self.assertFalse(self.states()["RS"]["complete"])
        # A historical empty snapshot remains readable but cannot claim success.
        old = self.read()
        next(e for e in old["edges"] if e["id"] == "potential-D-RS")["archived"] = True
        MODEL.validate_v7(old)
        self.assertFalse(MODEL.completion_state(old)["D"]["complete"])
        self.assertFalse(MODEL.completion_state(old)["R0"]["complete"])

    def test_atomic_output_replacement_and_incomplete_candidate_are_allowed(self):
        self.apply([self.add("D", action_type="decomposition"), self.prepare("D", "OLD"), self.choose("D")])
        self.apply([self.result("D", action=True)])
        self.apply([self.actual_requirement("NEW"),
                    self.edit("detach_requirement", edgeId="potential-D-OLD"), self.link("D", "NEW"),
                    self.add("DRAFT", action_type="decomposition")])
        self.assertEqual([e["to"] for e in self.read()["edges"] if e["type"] == "INTRODUCES" and not e.get("archived")], ["NEW"])
        self.assertFalse(self.states()["D"]["complete"])
        self.assertFalse(self.states()["DRAFT"]["complete"])
        self.apply([self.result("D", action=True)])
        self.assertTrue(self.states()["D"]["complete"])
        self.assertFalse(self.states()["NEW"]["complete"])

    def test_no_phantom_results_while_replacing_incomplete_correctness(self):
        self.apply([self.add("A"), self.prepare("A", "DONE", "method_correctness"),
                    self.prepare("A", "OLD", "method_correctness"), self.choose("A")])
        self.apply([self.result("DONE"), self.actual_requirement("NEW")])
        before = self.activity()
        self.apply([self.edit("detach_requirement", edgeId="potential-A-OLD"),
                    self.link("A", "NEW", "method_correctness")])
        self.assertFalse(self.states()["A"]["complete"])
        self.assertFalse(self.states()["R0"]["complete"])
        self.assertEqual([r for r in self.activity()["activities"] if r["kind"] in MODEL.COMPLETION_EVENTS],
                         [r for r in before["activities"] if r["kind"] in MODEL.COMPLETION_EVENTS])
        request = self.apply([self.result("NEW")])
        self.assertTrue(self.states()["R0"]["complete"])
        stable = self.activity()
        self.assert_ok(self.write(request, self.token))
        self.assertEqual(self.activity(), stable)

    def test_explicit_result_does_not_derive_from_intermediate_composition(self):
        self.apply([self.add("A"), self.prepare("A", "DONE", "method_correctness"), self.choose("A")])
        self.apply([self.actual_requirement("NEW")])
        self.apply([self.result("DONE"), self.link("A", "NEW", "method_correctness")])
        results = [e for e in self.read()["events"] if e["type"] in MODEL.COMPLETION_EVENTS]
        self.assertEqual([(e["targetId"], e["completionMode"]) for e in results], [("DONE", "explicit")])
        self.assertFalse(self.states()["A"]["complete"])
        self.assertFalse(self.states()["R0"]["complete"])

    def test_explicit_result_keeps_its_scope_when_definition_changes_later_in_package(self):
        self.apply([self.add("A"), self.choose("A")])
        self.apply([self.result("A", action=True), self.edit("edit_node", nodeId="A", changes={"title": "Later definition"})])
        results = [e for e in self.read()["events"] if e["type"] in MODEL.COMPLETION_EVENTS]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["basis"]["node"]["title"], "A")
        self.assertEqual(results[0]["completionMode"], "explicit")
        self.assertFalse(self.states()["A"]["complete"])
        self.assertFalse(self.states()["R0"]["complete"])

    def test_prospective_action_continuation_across_explicit_identity_owner(self):
        token = self.grant(["graph.write", "graph.read"], ["workspaces/"])["token"]
        self.apply([self.add("A"), self.prepare("A", "R1")])
        child = {"schemaVersion": 1, "revision": 1, "id": "child", "title": "Child",
                 "planningScale": "module", "actionModel": "candidate-v6", "identitySpace": "demo",
                 "rootRequirementId": "R1", "expansionOf": {"graphSlug": "demo", "nodeId": "R1"},
                 "nodes": [{"id": "R1", "kind": "requirement", "title": "R1", "status": "potential",
                            "projectionOf": {"graphSlug": "demo", "nodeId": "R1"}}],
                 "edges": [], "events": []}
        rel = "workspaces/child/graph.json"
        self.assert_ok(self.write({"schemaVersion": 1, "transactionId": "child-create",
                                   "changes": [{"file": rel, "create": child}]}, token))
        patch = {"schemaVersion": 1, "transactionId": "child-plan", "changes": [{"file": rel,
                 "patch": {"schemaVersion": 1, "expectedRevision": 1,
                           "operations": [self.add("A-DEEP", "R1"), self.prepare("A-DEEP", "R2")]}}]}
        self.assert_ok(self.write(patch, token))
        index = json.loads((self.home/"graphs/index.json").read_text())
        link = next(r for r in index["relations"] if r["to"] == "child")
        self.assertEqual(link["relationKind"], "potential")
        self.assertEqual(link["originatingActionId"], "A")
        self.assertEqual(link["originatingRequirementId"], "R0")


for name in ("tearDown", "admin", "grant", "create", "patch", "write", "assert_ok", "assert_denied"):
    setattr(DeepAction, name, getattr(FIX.BearerPackage, name))

if __name__ == "__main__":
    unittest.main()
