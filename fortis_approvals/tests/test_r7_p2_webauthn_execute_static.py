"""R7 P2 static source guardrails; no dependencies, network or deployment."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class R7P2WebAuthnExecuteStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = (ROOT/'fortis_approvals/core.py').read_text()
        cls.portal = (ROOT/'fortis_approvals/owner_portal.py').read_text()
        cls.candidate = (ROOT/'fortis_approvals/r7_unified_candidate.py').read_text()
        cls.server = (ROOT/'fortis_approvals/r7_unified_server.py').read_text()
        cls.dockerfile = (ROOT/'fortis_approvals/deploy/Dockerfile-R7-Unified-Read-Ask-Candidate').read_text()
        cls.tests = (ROOT/'fortis_approvals/tests/test_r7_unified_candidate.py').read_text()

    def test_r7_removes_only_the_candidate_write_stops(self):
        self.assertNotIn('NoWriteTransport', self.candidate)
        self.assertNotIn('blocked_approvals={G4_OPERATION}', self.candidate)
        self.assertNotIn('read_only_banner=True', self.candidate)
        self.assertIn('writer = SonarIssueAdapter(\n        sonar_transport,', self.candidate)
        self.assertIn("policy_version='r7-p1-sonar-accept-issue-write-v1'", self.candidate)
        self.assertIn('strong_operations={G4_OPERATION}', self.candidate)

    def test_core_and_portal_revalidate_exact_current_ask_policy(self):
        self.assertGreaterEqual(self.core.count("row['policy_version'] != self.policy_version"), 2)
        self.assertEqual(self.core.count("self._policy(row['actor'], loads_strict(row['payload'])) != 'ASK'"), 2)
        self.assertIn('row.get(\'policyVersion\') == self.core.policy_version', self.portal)
        self.assertIn("self.core._policy(row['actor'], row['request']) == 'ASK'", self.portal)
        self.assertIn('OWNER_OPERATION_POLICY_CHANGED', self.portal)

    def test_machine_ingress_still_has_no_owner_decision_or_execute_route(self):
        self.assertIn('OWNER_WEBAUTHN_APPROVAL_REQUIRED', self.server)
        self.assertNotIn('NoWriteTransport', self.server)
        self.assertIn('machine ingress has no decision or execute route', self.server)
        self.assertIn('Sonar POST requires the exact owner', self.server)

    def test_offline_integration_covers_web_authn_post_and_readback(self):
        for required in (
            'test_owner_webauthn_approval_executes_one_issue_and_confirms_readback',
            'test_pending_created_under_old_policy_cannot_be_approved',
            "self.assertEqual(self.sonar.posts,1)",
            "self.assertEqual(result['result']['readback']['status'],'ACCEPTED')",
            'OWNER_POLICY_CHANGED',
        ):
            self.assertIn(required, self.tests)
        self.assertIn('POST only after exact owner WebAuthn Approve', self.dockerfile)


if __name__ == '__main__':
    unittest.main()
