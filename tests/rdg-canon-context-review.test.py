#!/usr/bin/env python3
"""Synthetic tests of evidence-bound canon review without automatic acceptance."""
import copy
import hashlib
import importlib.machinery
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = importlib.machinery.SourceFileLoader(
    "rdg_canon_context_review", str(ROOT / "tools/rdg-canon-context-review.py")).load_module()
TEMP = importlib.machinery.SourceFileLoader(
    "rdg_temporal_impact_canon", str(ROOT / "tools/rdg-temporal-impact.py")).load_module()
PLAN_FIXTURE = ROOT / "docs/examples/temporal-plan-candidate-v1.json"


class CanonReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rdg-canon-context-")
        self.root = Path(self.tmp.name)
        self.graph_file = self.root / "workspaces/temporal-fixture/graph.json"
        self.graph_file.parent.mkdir(parents=True, exist_ok=True)
        self.graph = {
            "schemaVersion": 1, "id": "canon-review", "revision": 1,
            "actionModel": "candidate-v6", "identitySpace": "temporal-demo",
            "rootRequirementId": "R0", "edges": [], "events": [],
            "nodes": [
                {"kind": "requirement", "id": "R0", "title": "Root"},
                {"kind": "action", "id": "A1", "title": "Choose integration", "status": "candidate",
                 "canonBlock": {
                    "recommended": [{"id": "C-POS", "text": "Useful with stable dependency",
                                     "checkRequirements": ["R0"]}],
                    "contraindicated": [{"id": "C-NEG", "text": "Not useful when dependency slow",
                                        "checkCategories": ["latency"]}]}},
                {"kind": "context", "id": "CTX-POS", "title": "Observed context",
                 "evidenceStatus": "checked-present", "scope": "project",
                 "effectiveAt": "2026-10-01", "recordedAt": "2026-10-02",
                 "contextValue": {"latencyMs": 10}},
                {"kind": "context", "id": "CTX-NEG", "title": "Performance observation",
                 "evidenceStatus": "checked-present", "scope": "subsystem-alpha",
                 "effectiveAt": "2026-10-05", "recordedAt": "2026-10-06",
                 "validUntil": "2026-10-25",
                 "contextValue": {"latencyMs": 90}}
            ]}
        self.packet = {
            "identitySpace": "temporal-demo", "graphFile": "workspaces/temporal-fixture/graph.json",
            "targetId": "A1",
            "targetScope": "subsystem-alpha", "asOf": "2026-10-18",
            "observedRevision": 1,
            "observedCanonSHA256": REVIEW.sha(self.graph["nodes"][1]["canonBlock"]),
            "assessments": [
                {"caseId": "C-POS", "result": "applicable", "reason": "Reviewer hypothesis",
                 "evidenceRefs": [self.ref("CTX-POS")]},
                {"caseId": "C-NEG", "result": "applicable", "reason": "Counter-indication to inspect",
                 "evidenceRefs": [self.ref("CTX-NEG")]},
            ]}
        self.graph_file.write_text(json.dumps(self.graph), encoding="utf8")

    def tearDown(self):
        self.tmp.cleanup()

    def ref(self, id):
        value = next(n for n in self.graph["nodes"] if n["id"] == id)
        return "graph-node:" + id + "@" + REVIEW.sha(value)

    def test_positive_and_negative_are_both_reported_not_collapsed(self):
        before = self.graph_file.read_bytes()
        res = REVIEW.evaluate(self.graph, self.packet)
        self.assertEqual(res["positiveClaimsWithLocallyCurrentRefs"], ["C-POS"])
        self.assertEqual(res["contraindicationClaimsWithLocallyCurrentRefs"], ["C-NEG"])
        self.assertEqual(res["canonVerdict"], "needs-semantic-assessment")
        self.assertFalse(res["actionSelected"])
        self.assertEqual(res["committedFindings"], [])
        self.assertTrue(all(not c["semanticApplicabilityProven"] for c in res["canonCases"]))
        self.assertTrue(all(c["verification"] ==
                            "record-backed-claim-needs-semantic-review"
                            for c in res["canonCases"]))
        self.assertEqual(before, self.graph_file.read_bytes())

    def test_forged_and_changed_context_hashes_fail_to_support_claim(self):
        packet = copy.deepcopy(self.packet)
        packet["assessments"][0]["evidenceRefs"] = ["graph-node:CTX-POS@"+"0"*64]
        result = REVIEW.evaluate(self.graph, packet)
        self.assertEqual(result["positiveClaimsWithLocallyCurrentRefs"], [])
        self.assertEqual(result["canonCases"][0]["evidence"][0]["result"], "stale-source")
        self.graph["nodes"][2]["contextValue"] = {"latencyMs": 1000}
        result = REVIEW.evaluate(self.graph, self.packet)
        self.assertEqual(result["positiveClaimsWithLocallyCurrentRefs"], [])

    def test_out_of_date_or_scopeless_records_do_not_support_claims(self):
        graph = copy.deepcopy(self.graph)
        graph["nodes"][2]["effectiveAt"] = "2026-11-10"
        result = REVIEW.evaluate(graph, self.packet)
        self.assertEqual(result["canonCases"][0]["verification"], "evidence-needs-review")
        graph = copy.deepcopy(self.graph)
        graph["nodes"][3]["scope"] = "unrelated"
        result = REVIEW.evaluate(graph, self.packet)
        self.assertEqual(result["contraindicationClaimsWithLocallyCurrentRefs"], [])
        packet = copy.deepcopy(self.packet)
        packet["asOf"] = "2026-10-30"
        result = REVIEW.evaluate(self.graph, packet)
        self.assertEqual(result["contraindicationClaimsWithLocallyCurrentRefs"], [])

    def test_t2_later_discovery_is_not_t1_recorded_knowledge(self):
        packet = copy.deepcopy(self.packet)
        packet["asOf"] = "2026-10-18"
        graph = copy.deepcopy(self.graph)
        # The objective effective date is earlier, but the record was created
        # after the as-of moment. It must not become T1 evidence.
        graph["nodes"][2]["recordedAt"] = "2026-10-19"
        stale = REVIEW.evaluate(graph, packet)
        self.assertEqual(stale["positiveClaimsWithLocallyCurrentRefs"], [])
        self.assertEqual(stale["canonCases"][0]["evidence"][0]["result"], "stale-source")
        packet["assessments"][0]["evidenceRefs"] = [
            "graph-node:CTX-POS@" + REVIEW.sha(graph["nodes"][2])]
        reread = REVIEW.evaluate(graph, packet)
        self.assertEqual(reread["canonCases"][0]["evidence"][0]["result"],
                         "not-recorded-as-of")
        self.assertEqual(reread["positiveClaimsWithLocallyCurrentRefs"], [])

    def test_recording_date_is_mandatory_for_local_current_check(self):
        graph = copy.deepcopy(self.graph)
        graph["nodes"][2].pop("recordedAt")
        packet = copy.deepcopy(self.packet)
        packet["assessments"][0]["evidenceRefs"] = [
            "graph-node:CTX-POS@" + REVIEW.sha(graph["nodes"][2])]
        result = REVIEW.evaluate(graph, packet)
        self.assertEqual(result["canonCases"][0]["evidence"][0]["result"],
                         "record-time-not-proven")
        self.assertEqual(result["positiveClaimsWithLocallyCurrentRefs"], [])

    def test_unchecked_context_or_normative_requirement_not_real_observation(self):
        graph = copy.deepcopy(self.graph)
        graph["nodes"][2]["evidenceStatus"] = "unknown"
        result = REVIEW.evaluate(graph, self.packet)
        self.assertEqual(result["positiveClaimsWithLocallyCurrentRefs"], [])
        packet = copy.deepcopy(self.packet)
        packet["assessments"][0]["evidenceRefs"] = [self.ref("R0")]
        result = REVIEW.evaluate(self.graph, packet)
        self.assertEqual(result["positiveClaimsWithLocallyCurrentRefs"], [])
        self.assertEqual(result["canonCases"][0]["evidence"][0]["result"], "not-a-context")

    def test_stale_pins_block_both_positive_and_negative_claims(self):
        packet = copy.deepcopy(self.packet)
        packet["observedRevision"] = 2
        result = REVIEW.evaluate(self.graph, packet)
        self.assertFalse(result["pinMatches"])
        self.assertEqual(result["positiveClaimsWithLocallyCurrentRefs"], [])
        self.assertEqual(result["contraindicationClaimsWithLocallyCurrentRefs"], [])
        packet = copy.deepcopy(self.packet)
        packet["observedCanonSHA256"] = "0"*64
        result = REVIEW.evaluate(self.graph, packet)
        self.assertFalse(result["pinMatches"])

    def test_unknown_canon_case_and_missing_assessment_are_explicit(self):
        packet = copy.deepcopy(self.packet)
        packet["assessments"] = packet["assessments"][:1]
        result = REVIEW.evaluate(self.graph, packet)
        self.assertEqual(result["canonCases"][1]["verification"], "not-assessed")
        packet = copy.deepcopy(self.packet)
        packet["assessments"][0]["caseId"] = "C-FAKE"
        with self.assertRaisesRegex(ValueError, "CANON_REVIEW_CLAIM_CASE_UNKNOWN_OR_DUPLICATE"):
            REVIEW.evaluate(self.graph, packet)

    def test_malformed_claim_without_evidence_denied(self):
        packet = copy.deepcopy(self.packet)
        packet["assessments"][0]["evidenceRefs"] = []
        with self.assertRaisesRegex(ValueError, "CANON_REVIEW_EVIDENCE_REQUIRED_FOR_CLAIM"):
            REVIEW.evaluate(self.graph, packet)
        packet = copy.deepcopy(self.packet)
        packet["assessments"][0]["result"] = "selected"
        with self.assertRaisesRegex(ValueError, "CANON_REVIEW_CLAIM_MALFORMED"):
            REVIEW.evaluate(self.graph, packet)

    def test_rdg_plan_impact_keeps_candidate_hypothetical_only(self):
        plan = json.loads(PLAN_FIXTURE.read_text(encoding="utf8"))
        self.graph_file.write_text(json.dumps(self.graph), encoding="utf8")
        # A2 is not in this synthetic graph; the plan cannot be interpreted
        # unless both Action refs resolve to real nodes.
        with self.assertRaisesRegex(ValueError, "PLAN_IMPACT_ACTION_NOT_FOUND"):
            TEMP.assess(plan, self.root)
        self.graph["nodes"].append({
            "kind": "action", "id": "A2", "title": "Other candidate", "status": "candidate",
            "canonBlock": {"recommended": [], "contraindicated": []}})
        self.graph_file.write_text(json.dumps(self.graph), encoding="utf8")
        impact = TEMP.assess(plan, self.root)
        result = REVIEW.evaluate(self.graph, self.packet, impact)
        self.assertFalse(result["temporalReview"]["authoritative"])
        self.assertEqual(result["temporalReview"]["status"], "candidate-context-only")
        self.assertEqual(result["canonVerdict"], "needs-semantic-assessment")
        self.assertEqual(result["actionSelected"], False)
        self.assertEqual(len(result["temporalReview"]["matchingActionLeads"]), 1)

    def test_plan_owner_ref_is_exact_not_merely_matching_node_id(self):
        plan = json.loads(PLAN_FIXTURE.read_text(encoding="utf8"))
        self.graph["nodes"].append({
            "kind": "action", "id": "A2", "title": "Other candidate", "status": "candidate",
            "canonBlock": {"recommended": [], "contraindicated": []}})
        self.graph_file.write_text(json.dumps(self.graph), encoding="utf8")
        impact = TEMP.assess(plan, self.root)
        packet = copy.deepcopy(self.packet)
        packet["graphFile"] = "workspaces/different-owner/graph.json"
        report = REVIEW.evaluate(self.graph, packet, impact)
        self.assertEqual(report["temporalReview"]["matchingActionLeads"], [])

    def test_cli_rejects_mismatched_source_graph_path(self):
        packet = copy.deepcopy(self.packet)
        packet["graphFile"] = "workspaces/different-owner/graph.json"
        packetfile = self.root/"mismatch.json"
        packetfile.write_text(json.dumps(packet))
        proc = subprocess.run(["python3", str(ROOT/"tools/rdg-canon-context-review.py"),
                               "--graph", str(self.graph_file),
                               "--assessment", str(packetfile)],
                              text=True, capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("GRAPH_PATH_REF_MISMATCH", proc.stderr)

    def test_cli_does_not_change_either_input(self):
        packetfile = self.root/"assessment.json"
        packetfile.write_text(json.dumps(self.packet))
        before = self.graph_file.read_bytes(), packetfile.read_bytes()
        proc = subprocess.run(
            ["python3", str(ROOT/"tools/rdg-canon-context-review.py"),
             "--graph", str(self.graph_file),
             "--assessment", str(packetfile)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["targetId"], "A1")
        self.assertEqual(before, (self.graph_file.read_bytes(), packetfile.read_bytes()))


if __name__ == "__main__":
    unittest.main()
