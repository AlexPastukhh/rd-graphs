#!/usr/bin/env python3
"""Isolated negative/positive-local-only checks for uncommittable F-P evidence."""
import copy
import datetime as dt
import importlib.machinery
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
P = importlib.machinery.SourceFileLoader(
    "problem_evidence_preflight", str(ROOT / "tools/rdg-problem-evidence-preflight.py")).load_module()
today = dt.datetime.now(dt.timezone.utc).date()


class ProblemEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdg-problem-gate-")
        self.base = Path(self.temp.name)
        self.file = self.base / "workspaces/pilot/graph.json"
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.graph = {
            "schemaVersion": 1, "identitySpace": "pilot", "revision": 2,
            "nodes": [
                {"id": "R0", "kind": "requirement", "title": "Target"},
                {"id": "CX", "kind": "context", "title": "Observed",
                 "scope": "module-a", "evidenceStatus": "checked-present",
                 "recordedAt": today.isoformat(),
                 "effectiveAt": (today - dt.timedelta(days=1)).isoformat(),
                 "contextValue": {"incidentDetected": True}},
            ], "edges": [], "events": []}
        self.request = {
            "graphFile": "workspaces/pilot/graph.json",
            "identitySpace": "pilot", "observedRevision": 2,
            "targetId": "R0", "findingId": "F-P-1",
            "statement": "Potential observed incident requiring independent verification",
            "targetScope": "module-a", "asOf": today.isoformat(),
            "evidenceRefs": [], "reviewQuestions": [
                "Is the recorded condition independently verified as present?"]}
        self.request["evidenceRefs"] = [self.ref()]

    def tearDown(self):
        self.temp.cleanup()

    def ref(self):
        return "graph-node:CX@" + P.REVIEW.sha(self.graph["nodes"][1])

    def test_matching_local_evidence_still_never_issues_f_p(self):
        result = P.assess(self.graph, self.request)
        self.assertTrue(result["localEvidenceReadyForReview"])
        self.assertFalse(result["mayAppendFP"])
        self.assertFalse(result["humanIdentityVerified"])
        self.assertFalse(result["trustProofValidated"])
        self.assertFalse(result["confirmedProblem"])
        self.assertIn("trusted-independent-factual-attestation-not-implemented",
                      result["missingGates"])

    def test_changed_observation_hash_fail_closed(self):
        altered = copy.deepcopy(self.graph)
        altered["nodes"][1]["contextValue"]["incidentDetected"] = False
        result = P.assess(altered, self.request)
        self.assertFalse(result["localEvidenceReadyForReview"])
        self.assertEqual(result["localEvidenceChecks"][0]["status"], "changed-node")

    def test_recorded_later_than_as_of_cannot_prove_t1(self):
        altered = copy.deepcopy(self.graph)
        altered["nodes"][1]["recordedAt"] = (
            today + dt.timedelta(days=1)).isoformat()
        packet = copy.deepcopy(self.request)
        packet["evidenceRefs"] = [
            "graph-node:CX@" + P.REVIEW.sha(altered["nodes"][1])]
        result = P.assess(altered, packet)
        self.assertEqual(result["localEvidenceChecks"][0]["status"], "not-recorded-as-of")
        self.assertFalse(result["localEvidenceReadyForReview"])

    def test_unchecked_context_and_other_scope_do_not_count(self):
        altered = copy.deepcopy(self.graph)
        altered["nodes"][1]["evidenceStatus"] = "unknown"
        packet = copy.deepcopy(self.request)
        packet["evidenceRefs"] = [
            "graph-node:CX@" + P.REVIEW.sha(altered["nodes"][1])]
        result = P.assess(altered, packet)
        self.assertEqual(result["localEvidenceChecks"][0]["status"],
                         "not-confirmed-in-record")
        packet = copy.deepcopy(self.request)
        packet["targetScope"] = "module-b"
        result = P.assess(self.graph, packet)
        self.assertEqual(result["localEvidenceChecks"][0]["status"], "scope-not-proven")

    def test_candidate_plan_claim_and_future_as_of_not_allowed_to_attest(self):
        packet = copy.deepcopy(self.request)
        packet["asOf"] = (today + dt.timedelta(days=1)).isoformat()
        result = P.assess(self.graph, packet)
        self.assertFalse(result["localEvidenceReadyForReview"])
        self.assertIn("as-of-not-current-utc-date", result["missingGates"])
        packet = copy.deepcopy(self.request)
        packet["temporalPlanAssumption"] = {"hard": True}
        with self.assertRaisesRegex(ValueError, "PROBLEM_PREFLIGHT_SCHEMA"):
            P.assess(self.graph, packet)

    def test_stale_graph_revision_and_invalid_source_ref(self):
        packet = copy.deepcopy(self.request)
        packet["observedRevision"] = 1
        self.assertFalse(P.assess(self.graph, packet)["pinMatches"])
        packet = copy.deepcopy(self.request)
        packet["evidenceRefs"] = ["unqualified-id"]
        self.assertEqual(P.assess(self.graph, packet)["localEvidenceChecks"][0]["status"],
                         "invalid-reference")

    def test_cli_has_no_write_and_rejects_other_graph_path(self):
        self.file.write_text(json.dumps(self.graph), encoding="utf8")
        request_file = self.base / "request.json"
        request_file.write_text(json.dumps(self.request), encoding="utf8")
        before = self.file.read_bytes(), request_file.read_bytes()
        cmd = ["python3", str(ROOT / "tools/rdg-problem-evidence-preflight.py"),
               "--graph", str(self.file), "--request", str(request_file)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["mayAppendFP"])
        self.assertEqual((self.file.read_bytes(), request_file.read_bytes()), before)
        request = copy.deepcopy(self.request)
        request["graphFile"] = "workspaces/other/graph.json"
        request_file.write_text(json.dumps(request), encoding="utf8")
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GRAPH_PATH_REF_MISMATCH", result.stderr)


if __name__ == "__main__":
    unittest.main()
