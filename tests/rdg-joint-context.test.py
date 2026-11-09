#!/usr/bin/env python3
"""Scoped joint context: lifecycle, applicability, exact Plan/RDG and event."""
import copy
import datetime as dt
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
JOINT = SourceFileLoader("test_joint_context", str(ROOT/"tools/rdg-joint-context.py")).load_module()
FIXTURE = SourceFileLoader("joint_exact_fixture", str(ROOT/"tests/rdg-exact-history.test.py")).load_module()
PLANREL = FIXTURE.PLANREL


class JointContextTest(unittest.TestCase):
    def setUp(self):
        self.fixture = FIXTURE.ExactHistoryTest("test_exact_source_is_stable_after_current_graph_changes")
        self.fixture.applicability_capable = True
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        f.add_journal("graph-create",None,f.graph,
                      recorded_at=dt.datetime.now(dt.timezone.utc).isoformat())
        self.appwriter = f.grant(["plan.applicability.write","plan.read","graph.read"],
                                 [PLANREL,FIXTURE.REL])
        self.claimant = f.grant(["plan.edit","plan.read"],[PLANREL])
        self.acceptor = f.grant(["plan.accept","plan.read"],[PLANREL])
        self.source1 = copy.deepcopy(f.query)
        self.app1 = self.app_assertion("A1",self.source1,"2026-10-18T10:00:00+00:00")
        self.apply_app("app-A1",0,self.app1)
        self.event1 = self.event_claim("E1",self.source1["plan"])
        self.apply_event("event-E1",0,self.event1)
        JOINT.BASELINE.apply(f.plans,f.authpath,self.acceptor,{
            "transactionId":"accept-r1","op":"accept","file":PLANREL,
            "expectedStateRevision":0,"planPin":self.source1["plan"],
            "basis":"Synthetic exact baseline"})
        self.early = self.now()
        self.request = {"schemaVersion":1,"mode":"scoped-joint-context",
            "lifecycle":"candidate","planFile":PLANREL,"knownAt":self.early,
            "effectiveAt":"2026-10-18T10:45:00+00:00",
            "scenario":{"branchId":"B-RESULT","outcome":"positive"},
            "occurrenceId":"O1","baselineStateRevision":None}
        time.sleep(0.02)

    @staticmethod
    def now():
        return dt.datetime.now(dt.timezone.utc).isoformat()

    @staticmethod
    def app_assertion(ident,source,when,supersedes=None):
        return {"id":ident,"effectiveAt":when,"supersedes":supersedes,
                "source":copy.deepcopy(source),"eventClaim":None}

    @staticmethod
    def event_claim(ident,pin,supersedes=None,outcome="positive"):
        return {"id":ident,"occurrenceId":"O1","planPin":copy.deepcopy(pin),
            "eventStepId":"S-RESULT","outcome":outcome,
            "occurredAt":"2026-10-18T10:00:00+00:00",
            "evidenceRefs":["EV-"+ident],"supersedes":supersedes}

    def apply_app(self,tx,expected,assertion):
        f = self.fixture
        return JOINT.APP.apply(f.plans,f.graphs,f.authpath,self.appwriter,{
            "transactionId":tx,"file":PLANREL,"expectedRevision":expected,
            "assertion":assertion})

    def apply_event(self,tx,expected,payload):
        f = self.fixture
        return JOINT.EVENT_PROJECTION.EVENT.apply(f.plans,f.authpath,self.claimant,{
            "transactionId":tx,"kind":"claim","file":PLANREL,
            "expectedRevision":expected,"payload":payload})

    def resolve(self,request=None,callback=None):
        f = self.fixture
        return JOINT.resolve(f.plans,f.graphs,f.authpath,f.reader,
                             request or self.request,before_return=callback)

    def source_bytes(self):
        f = self.fixture
        return {str(p.relative_to(f.base)):p.read_bytes()
                for root in (f.plans,f.graphs) for p in root.rglob("*.json")}

    def plan2(self,graph2=False):
        f = self.fixture
        source = copy.deepcopy(self.source1)
        plan = copy.deepcopy(f.plan)
        plan["revision"] = 2
        plan["title"] = "Later candidate"
        if graph2:
            newer = copy.deepcopy(f.graph)
            newer["revision"] = 2
            newer["nodes"][1]["title"] = "Later A1 title"
            f.add_journal("graph-edit",f.graph,newer,recorded_at=self.now())
            for step in plan["steps"]:
                if step["kind"] == "action":
                    step["actionRef"]["observedGraphRevision"] = 2
            source["graphs"][0].update(revision=2,snapshotSHA256=JOINT.OWNER.digest(newer))
        JOINT.OWNER.apply_request(f.plans,f.authpath,f.writer,{
            "transactionId":"plan-r2","op":"edit","file":PLANREL,
            "expectedRevision":1,"plan":plan})
        meta = JOINT.OWNER.read_snapshot(f.plans,PLANREL,2)["provenance"]
        source["plan"].update(revision=2,snapshotSHA256=meta["snapshotSHA256"],
                              recordDigest=meta["recordDigest"])
        return source

    def test_read_only_joint_candidate_has_all_declared_sources(self):
        before = self.source_bytes()
        context = self.resolve()
        self.assertEqual(context["plan"]["pin"],self.source1["plan"])
        self.assertEqual(context["graphs"][0]["snapshot"],self.fixture.graph)
        self.assertEqual(context["applicability"]["selectedAssertionId"],"A1")
        self.assertEqual(context["event"]["data"]["reviewInputs"]["resolution"][
            "unresolvedClaimIds"],["E1"])
        self.assertTrue(context["boundaries"]["scopedExactContextResolved"])
        self.assertFalse(context["boundaries"]["completeApplicableContextVerified"])
        self.assertFalse(context["boundaries"]["factualEventVerified"])
        self.assertEqual(before,self.source_bytes())

    def test_fixed_early_context_survives_late_plan_graph_app_and_event(self):
        before = self.resolve()
        source2 = self.plan2(graph2=True)
        self.apply_app("app-A2",1,self.app_assertion("A2",source2,
            "2026-10-18T10:30:00+00:00","A1"))
        self.apply_event("event-E2",1,self.event_claim("E2",source2["plan"],"E1"))
        self.assertEqual(self.resolve(),before)
        late = copy.deepcopy(self.request);late["knownAt"] = self.now()
        context = self.resolve(late)
        self.assertEqual(context["plan"]["pin"]["revision"],2)
        self.assertEqual(context["graphs"][0]["pin"]["revision"],2)
        self.assertEqual(context["applicability"]["selectedAssertionId"],"A2")
        self.assertEqual(before["graphs"][0]["source"]["side"],"after")

    def test_exact_accepted_baseline_is_not_replaced_by_candidate(self):
        source2 = self.plan2()
        self.apply_app("app-A2",1,self.app_assertion("A2",source2,
            "2026-10-18T10:30:00+00:00","A1"))
        accepted = copy.deepcopy(self.request)
        accepted.update(lifecycle="accepted-future",baselineStateRevision=1,knownAt=self.now())
        context = self.resolve(accepted)
        self.assertEqual(context["plan"]["pin"],self.source1["plan"])
        self.assertEqual([r["assertion"]["id"] for r in
                          context["applicability"]["records"]],["A1"])
        self.assertEqual(context["lifecycle"]["selectionMode"],"exact-baseline-state")
        candidate = copy.deepcopy(self.request);candidate["knownAt"] = self.now()
        with self.assertRaisesRegex(ValueError,"EVENT_PLAN_PIN_MISMATCH"):
            self.resolve(candidate)

    def test_event_conflict_and_scenario_mismatch_fail_closed(self):
        self.apply_event("event-E2",1,self.event_claim("E2",self.source1["plan"],
                                                     outcome="negative"))
        request = copy.deepcopy(self.request);request["knownAt"] = self.now()
        with self.assertRaisesRegex(ValueError,"EVENT_CLAIM_CONFLICT"):
            self.resolve(request)
        request = copy.deepcopy(self.request)
        request["scenario"]["outcome"] = "negative"
        with self.assertRaisesRegex(ValueError,"SCENARIO_APPLICABILITY_MISMATCH"):
            self.resolve(request)

    def test_unlinked_applicability_conflict_is_not_resolved_by_latest_revision(self):
        source2 = self.plan2()
        self.apply_app("app-A2",1,self.app_assertion("A2",source2,
            "2026-10-18T10:30:00+00:00"))
        request = copy.deepcopy(self.request);request["knownAt"] = self.now()
        with self.assertRaisesRegex(ValueError,"UNRESOLVED_APPLICABILITY_CONFLICT"):
            self.resolve(request)

    def test_missing_graph_proof_and_pending_owner_journal_rejected(self):
        journal = self.fixture.graphs/"workspaces/.transactions/graph-create.json"
        value = json.loads(journal.read_text())
        old = {k:v for k,v in value.items() if k not in ("preparedAt","recordedAt")}
        old["schemaVersion"] = 1
        journal.write_text(json.dumps(old))
        with self.assertRaisesRegex(ValueError,"GRAPH_RECORDING_TIME_NOT_AVAILABLE"):
            self.resolve()
        journal.write_text(json.dumps(value))
        JOINT.APP.journal_path(self.fixture.plans).write_text("{}")
        with self.assertRaisesRegex(ValueError,"RECOVERY_REQUIRED"):
            self.resolve()

    def test_exact_baseline_revision_and_no_future_knowledge_required(self):
        bad = copy.deepcopy(self.request);bad["lifecycle"] = "accepted-future"
        with self.assertRaisesRegex(ValueError,"EXACT_BASELINE_STATE_REQUIRED"):
            self.resolve(bad)
        bad = copy.deepcopy(self.request)
        bad["knownAt"] = (dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError,"FUTURE_KNOWN_AT_UNSUPPORTED"):
            self.resolve(bad)

    def test_projection_coverage_and_tampered_bundle_rejected(self):
        context = self.resolve()
        resource = JOINT.project(context)
        contract = JOINT.build_contract(resource)
        self.assertEqual(len(contract["subscriptions"]),9)
        JOINT.assert_coverage(contract,contract["subscriptions"])
        with self.assertRaisesRegex(ValueError,"SUBSCRIPTIONS_INCOMPLETE"):
            JOINT.assert_coverage(contract,contract["subscriptions"][:-1])
        bad = copy.deepcopy(context)
        bad["graphs"][0]["snapshot"]["title"] = "Forged after projection"
        with self.assertRaisesRegex(ValueError,"GRAPH_SNAPSHOT_MISMATCH"):
            JOINT.project(bad)
        bad = copy.deepcopy(context);bad["assessment"] = {}
        with self.assertRaisesRegex(ValueError,"ASSESSMENT_INCOMPLETE_OR_STALE"):
            JOINT.project(bad)
        bad = copy.deepcopy(resource);bad["data"]["reviewInputs"]["event"] = {}
        with self.assertRaisesRegex(ValueError,"PROJECTION_INCOMPLETE_OR_STALE"):
            JOINT.build_contract(bad)

    def test_producer_group_and_factual_flag_cannot_be_hidden(self):
        context = self.resolve()
        original = copy.deepcopy(JOINT.READ_MATRIX)
        try:
            JOINT.READ_MATRIX.pop("event")
            with self.assertRaisesRegex(ValueError,"SOURCE_GROUPS_INCOMPLETE_OR_UNKNOWN"):
                JOINT.project(context)
        finally:
            JOINT.READ_MATRIX.clear();JOINT.READ_MATRIX.update(original)
        context["boundaries"]["factualEventVerified"] = True
        with self.assertRaisesRegex(ValueError,"UNSUPPORTED_TRUST_OR_SCOPE"):
            JOINT.project(context)

    def test_equivalent_time_offsets_have_same_joint_resource(self):
        request = copy.deepcopy(self.request)
        request["knownAt"] = JOINT.MODEL.known(request["knownAt"]).astimezone(
            dt.timezone(dt.timedelta(hours=7))).isoformat()
        request["effectiveAt"] = "2026-10-18T17:45:00+07:00"
        self.assertEqual(JOINT.project(self.resolve(request)),
                         JOINT.project(self.resolve()))

    def test_exact_replacement_baseline_not_applicable_to_earlier_effective_time(self):
        source2 = self.plan2()
        self.apply_app("app-A2",1,self.app_assertion("A2",source2,
            "2026-10-18T10:30:00+00:00","A1"))
        f = self.fixture
        JOINT.BASELINE.apply(f.plans,f.authpath,self.acceptor,{
            "transactionId":"replace-r2","op":"replace","file":PLANREL,
            "expectedStateRevision":1,"planPin":source2["plan"],
            "basis":"Synthetic replacement"})
        request = copy.deepcopy(self.request)
        request.update(lifecycle="accepted-future",baselineStateRevision=2,
                       knownAt=self.now(),effectiveAt="2026-10-18T10:15:00+00:00")
        with self.assertRaisesRegex(ValueError,"BASELINE_NOT_APPLICABLE"):
            self.resolve(request)

    def test_withdrawn_baseline_and_final_reader_revoke_rejected(self):
        f = self.fixture
        JOINT.BASELINE.apply(f.plans,f.authpath,self.acceptor,{
            "transactionId":"withdraw-r1","op":"withdraw","file":PLANREL,
            "expectedStateRevision":1,"planPin":self.source1["plan"],
            "basis":"Synthetic withdrawal"})
        request = copy.deepcopy(self.request)
        request.update(lifecycle="accepted-future",baselineStateRevision=2,knownAt=self.now())
        with self.assertRaisesRegex(ValueError,"BASELINE_WITHDRAWN"):
            self.resolve(request)
        with self.assertRaisesRegex(ValueError,"AUTH_TOKEN_REVOKED"):
            self.resolve(callback=lambda:f.auth.manage("revoke",f.admin,{"id":f.reader_id}))


if __name__=="__main__":
    unittest.main()
