#!/usr/bin/env python3
"""Exact historical Plan/RDG resolution on synthetic roots; no live graph reads."""
import copy
import datetime as dt
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HISTORY = SourceFileLoader("test_exact_history", str(ROOT / "tools/rdg-exact-history.py")).load_module()
OWNER = HISTORY.OWNER
REL = "workspaces/temporal-fixture/graph.json"
PLANREL = "plans/demo/plan.json"


class ExactHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rdg-exact-history-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.plans = self.base / "owner"
        self.plans.mkdir()
        self.graphs = self.base / "graphs"
        (self.graphs / "workspaces/.transactions").mkdir(parents=True)
        (self.graphs / "workspaces/.writer.lock").touch()
        self.authpath = self.base / "authority.json"
        self.auth = OWNER.AUTH.Authority(self.authpath)
        self.admin = self.auth.init_local(plan_capable=True,
            applicability_capable=getattr(self, "applicability_capable", False))["token"]
        self.writer = self.grant(["plan.create", "plan.edit", "plan.branch"], [PLANREL])
        self.reader_id, self.reader = self.grant(["plan.read", "graph.read"], [PLANREL, REL], with_id=True)
        self.plan = json.loads((ROOT / "docs/examples/temporal-plan-candidate-v1.json").read_text())
        self.graph = {"schemaVersion": 1, "revision": 1, "id": "synthetic",
            "title": "Temporary", "identitySpace": "temporal-demo",
            "rootRequirementId": "R0", "actionModel": "candidate-v6", "planningScale": "module",
            "nodes": [{"id": "R0", "kind": "requirement", "title": "Root", "status": "active"}] +
            [{"id": aid, "kind": "action", "title": "Candidate " + aid,
              "status": "candidate", "qrpe": []} for aid in ("A1", "A2")],
            "edges": [{"id": "E-" + aid, "type": "DRIVES", "from": "R0", "to": aid}
                      for aid in ("A1", "A2")], "events": []}
        HISTORY.GRAPH.validate(self.graph)
        OWNER.apply_request(self.plans, self.authpath, self.writer, {
            "transactionId": "create", "op": "create", "file": PLANREL,
            "expectedRevision": 0, "plan": self.plan})
        self.provenance = OWNER.read_snapshot(self.plans, PLANREL, 1)["provenance"]
        self.add_journal("graph-create", None, self.graph)
        self.query = {"schemaVersion": 1, "mode": "exact-reference", "lifecycle": "candidate",
            "plan": {"file": PLANREL, "identitySpace": "temporal-demo", "planId": self.plan["id"],
                     "revision": 1, "snapshotSHA256": self.provenance["snapshotSHA256"],
                     "recordDigest": self.provenance["recordDigest"]},
            "graphs": [{"graphFile": REL, "identitySpace": "temporal-demo",
                        "revision": 1, "snapshotSHA256": OWNER.digest(self.graph)}],
            "scenario": {"branchId": "B-RESULT", "outcome": "positive"}}

    def grant(self, permissions, scopes, with_id=False):
        issued = self.auth.manage("issue", self.admin, {"permissions": permissions, "scopes": scopes})
        return (issued["id"], issued["token"]) if with_id else issued["token"]

    def add_journal(self, tx, before, after, state="completed", file=REL, recorded_at=None):
        value = {"schemaVersion": 2 if recorded_at else 1,
                 "transactionId": tx, "requestSHA256": "0"*64,
                 "state": state, "records": [{"file": file, "before": before,
                 "after": after, "changed": before != after}]}
        if recorded_at:
            value["preparedAt"] = (OWNER.instant(recorded_at) - dt.timedelta(seconds=1)).isoformat()
            value["recordedAt"] = recorded_at
        path = self.graphs / "workspaces/.transactions" / (tx + ".json")
        path.write_text(json.dumps(value))
        return path

    def resolve(self, query=None, token=None, callback=None):
        return HISTORY.resolve(self.plans, self.graphs, self.authpath, token or self.reader,
                               query or self.query, before_return=callback)

    def assert_denied(self, code, query=None, token=None):
        with self.assertRaisesRegex(ValueError, code):
            self.resolve(query, token)

    def test_exact_source_is_stable_after_current_graph_changes(self):
        original = self.resolve()
        newer = copy.deepcopy(self.graph)
        newer["revision"] = 2
        newer["nodes"][1]["title"] = "Later change to A1"
        HISTORY.GRAPH.validate(newer)
        self.add_journal("graph-edit", self.graph, newer)
        # The current graph exists but is never used for the historical result.
        path = self.graphs / REL
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(newer))
        again = self.resolve()
        self.assertEqual(original["impact"], again["impact"])
        self.assertEqual(again["graphSnapshots"][0]["graph"], self.graph)
        self.assertEqual(len(again["impact"]["branches"]), 1)
        self.assertEqual(again["impact"]["branches"][0]["outcome"], "positive")
        self.assertEqual(again["impact"]["branches"][0]["actionReviewLeads"][0]["action"]["graphRevision"], 1)
        self.assertFalse(again["provenance"]["twoTimeAsOfResolved"])
        self.assertFalse(again["provenance"]["historicalT1KnowledgeVerified"])
        self.assertFalse(again["provenance"]["eventsAttested"])

    def test_completed_before_image_resolves_without_create_journal(self):
        newer = copy.deepcopy(self.graph)
        newer["revision"] = 2
        newer["nodes"][1]["title"] = "Later candidate"
        self.add_journal("graph-edit", self.graph, newer)
        (self.graphs / "workspaces/.transactions/graph-create.json").unlink()
        resolved = self.resolve()
        self.assertEqual(resolved["graphSnapshots"][0]["graph"], self.graph)
        self.assertEqual([s["side"] for s in resolved["graphSnapshots"][0]["provenance"]["sources"]], ["before"])

    def test_symlinked_journal_is_denied(self):
        outside = self.base / "other-journal.json"
        outside.write_text("{}")
        (self.graphs / "workspaces/.transactions/linked.json").symlink_to(outside)
        self.assert_denied("SYMLINK_DENIED")

    def test_known_at_uses_direct_plan_receipt_and_legacy_successor(self):
        # r1 already existed when the next guarded Plan edit read the store.
        later_plan = copy.deepcopy(self.plan)
        later_plan["revision"] = 2
        editor = self.grant(["plan.edit"], [PLANREL])
        OWNER.apply_request(self.plans, self.authpath, editor, {
            "transactionId": "plan-r2", "op": "edit", "file": PLANREL,
            "expectedRevision": 1, "plan": later_plan})
        plan_bound = OWNER.read_snapshot(self.plans, PLANREL, 2)["provenance"]["recordedAt"]
        graph_time = OWNER.instant(plan_bound) + dt.timedelta(seconds=10)
        self.add_journal("graph-create", None, self.graph, recorded_at=graph_time.isoformat())
        q = copy.deepcopy(self.query)
        q["knownAt"] = (graph_time + dt.timedelta(seconds=1)).isoformat()
        result = self.resolve(q)
        self.assertTrue(result["provenance"]["recordingCutoffVerified"])
        self.assertFalse(result["provenance"]["twoTimeAsOfResolved"])
        direct_bound = OWNER.read_availability(self.plans, PLANREL, 1,
                         self.provenance["recordDigest"])["availableBy"]
        self.assertEqual(result["planAvailableBy"], direct_bound)
        self.assertEqual(result["planAvailabilitySource"], "owner-after-durable-store")
        self.assertEqual(result["graphSnapshots"][0]["provenance"]["recordedAt"], graph_time.isoformat())
        q["knownAt"] = (graph_time - dt.timedelta(microseconds=1)).isoformat()
        self.assert_denied("GRAPH_RECORDED_AFTER_KNOWN_AT", q)
        q["knownAt"] = (OWNER.instant(direct_bound) - dt.timedelta(microseconds=1)).isoformat()
        self.assert_denied("PLAN_NOT_PROVEN_AVAILABLE_BY_KNOWN_AT", q)
        # The current Plan revision also has its own post-write witness.
        q["knownAt"] = result["knownAtCutoff"]
        next_meta = OWNER.read_snapshot(self.plans, PLANREL, 2)["provenance"]
        q["plan"].update(revision=2, snapshotSHA256=next_meta["snapshotSHA256"],
                         recordDigest=next_meta["recordDigest"])
        self.assertEqual(self.resolve(q)["planAvailabilitySource"], "owner-after-durable-store")
        # Simulate a legacy Plan store without receipts: the older version uses
        # the next guarded edit, while the latest fails closed.
        OWNER.availability_path(self.plans, PLANREL, 1).unlink()
        OWNER.availability_path(self.plans, PLANREL, 2).unlink()
        self.assert_denied("PLAN_AVAILABILITY_BOUND_NOT_AVAILABLE", q)
        q = copy.deepcopy(self.query)
        q["knownAt"] = result["knownAtCutoff"]
        self.assertEqual(self.resolve(q)["planAvailabilitySource"], "next-guarded-plan-edit")
        self.add_journal("graph-create", None, self.graph)
        self.assert_denied("GRAPH_RECORDING_TIME_NOT_AVAILABLE", q)

    def test_invalid_v2_clock_and_effective_at_are_rejected(self):
        q = copy.deepcopy(self.query)
        q["effectiveAt"] = "2026-11-01"
        self.assert_denied("TWO_TIME_QUERY_NOT_SUPPORTED", q)
        q = copy.deepcopy(self.query)
        q["knownAt"] = "2026-10-19"
        self.assert_denied("KNOWN_AT_INSTANT_REQUIRED", q)
        q["knownAt"] = "2026-10-19T00:00:00Z"
        self.assert_denied("GRAPH_RECORDING_TIME_NOT_AVAILABLE|PLAN_NOT_PROVEN_AVAILABLE_BY_KNOWN_AT", q)
        self.add_journal("bad-clock", self.graph, {**self.graph, "revision": 2},
                         recorded_at="2026-10-19T08:00:00+07:00")
        self.assert_denied("JOURNAL_RECORDED_AT_NOT_UTC")

    def test_missing_exact_graph_and_no_current_fallback(self):
        (self.graphs / "workspaces/.transactions/graph-create.json").unlink()
        path = self.graphs / REL
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(self.graph))
        self.assert_denied("GRAPH_SNAPSHOT_NOT_FOUND")

    def test_plan_hash_and_graph_hash_are_mandatory(self):
        q = copy.deepcopy(self.query)
        q["plan"]["snapshotSHA256"] = "0"*64
        self.assert_denied("PLAN_SNAPSHOT_HASH_MISMATCH", q)
        q = copy.deepcopy(self.query)
        q["graphs"][0]["snapshotSHA256"] = "0"*64
        self.assert_denied("GRAPH_SNAPSHOT_HASH_MISMATCH", q)

    def test_plan_or_graph_not_authorized_even_with_write_grants(self):
        plan_only = self.grant(["plan.read"], [PLANREL, REL])
        self.assert_denied("MISSING_PERMISSION: graph.read", token=plan_only)
        graph_only = self.grant(["graph.read"], [PLANREL, REL])
        self.assert_denied("MISSING_PERMISSION: plan.read", token=graph_only)
        broad_writer = self.grant(["graph.write", "plan.create"], [PLANREL, REL])
        self.assert_denied("MISSING_PERMISSION: plan.read", token=broad_writer)
        wrong_scope = self.grant(["plan.read", "graph.read"], [PLANREL, "workspaces/other/graph.json"])
        self.assert_denied("SNAPSHOT_READ_SCOPE_DENIED", token=wrong_scope)

    def test_revocation_during_read_blocks_delivery(self):
        def revoke():
            self.auth.manage("revoke", self.admin, {"id": self.reader_id})
        self.assert_denied("AUTH_TOKEN_REQUIRED", token="bad-token")
        with self.assertRaisesRegex(ValueError, "AUTH_.*"):
            self.resolve(callback=revoke)

    def test_prepared_or_corrupt_journal_blocks_resolution(self):
        path = self.add_journal("interrupted", self.graph, {**self.graph, "revision": 2}, "prepared")
        self.assert_denied("GRAPH_RECOVERY_REQUIRED")
        path.write_text("{this is not JSON")
        with self.assertRaises(json.JSONDecodeError):
            self.resolve()

    def test_ambiguous_same_revision_and_wrong_owner_fail_closed(self):
        other = copy.deepcopy(self.graph)
        other["nodes"][1]["title"] = "Conflicting revision 1"
        self.add_journal("conflict", None, other)
        self.assert_denied("AMBIGUOUS_GRAPH_REVISION")
        (self.graphs / "workspaces/.transactions/conflict.json").unlink()
        other["identitySpace"] = "different"
        self.add_journal("wrong-owner", None, other)
        self.assert_denied("GRAPH_IDENTITY_MISMATCH")

    def test_scenario_and_graph_pins_cannot_be_invented(self):
        q = copy.deepcopy(self.query)
        q["scenario"]["outcome"] = "unknown"
        self.assert_denied("SCENARIO_NOT_FOUND", q)
        q = copy.deepcopy(self.query)
        q["graphs"][0]["revision"] = 2
        self.assert_denied("SCENARIO_GRAPH_PINS_MISMATCH", q)
        q = copy.deepcopy(self.query)
        q["graphs"].append(copy.deepcopy(q["graphs"][0]))
        self.assert_denied("DUPLICATE_GRAPH_PIN", q)

    def test_no_two_time_or_lifecycle_claim_is_accepted(self):
        q = copy.deepcopy(self.query)
        q["knownAt"] = (OWNER.instant(self.provenance["recordedAt"]) -
                        dt.timedelta(microseconds=1)).isoformat()
        self.assert_denied("PLAN_NOT_PROVEN_AVAILABLE_BY_KNOWN_AT", q)
        q = copy.deepcopy(self.query)
        q["lifecycle"] = "accepted"
        self.assert_denied("REQUEST_SCHEMA", q)
        later = copy.deepcopy(self.plan)
        later["revision"] = 2
        later["steps"][2]["actionRef"].pop("observedGraphRevision")
        OWNER.apply_request(self.plans, self.authpath, self.writer, {
            "transactionId": "missing-observed", "op": "edit", "file": PLANREL,
            "expectedRevision": 1, "plan": later})
        q = copy.deepcopy(self.query)
        provenance = OWNER.read_snapshot(self.plans, PLANREL, 2)["provenance"]
        q["plan"].update(revision=2, snapshotSHA256=provenance["snapshotSHA256"],
                         recordDigest=provenance["recordDigest"])
        self.assert_denied("EXACT_ACTION_REVISIONS_REQUIRED", q)


if __name__ == "__main__":
    unittest.main()
