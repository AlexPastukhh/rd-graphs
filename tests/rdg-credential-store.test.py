#!/usr/bin/env python3
"""Credential owner/permit/counter/acceptance contracts on synthetic records.

These tests exercise Authority state and role boundaries, not cryptographic
verification or OS isolation. Native registration/restart is tested in Chromium.
"""
import copy
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASE = SourceFileLoader("credential_state_fixture",
    str(ROOT / "tests/rdg-approval-execution.test.py")).load_module()
MODULE = SourceFileLoader("credential_state_test",
    str(ROOT / "tools/rdg-credential-store.py")).load_module()


class CredentialState(unittest.TestCase):
    def setUp(self):
        self.fx = BASE.ApprovalExecution(
            "test_exact_signed_execution_separates_three_actors_without_granting_ai")
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.clock = [1000.]
        self.store = MODULE.CredentialStore(self.fx.authority, clock=lambda: self.clock[0])
        self.spec = {"principalId": "synthetic-operator", "displayName": "Тестовый оператор",
            "namespaceId": self.fx.namespace, "executorGrantId": self.fx.human_grant,
            "authorityPrincipal": "key:synthetic-human", "rpId": "localhost",
            "origin": "http://localhost:17321", "active": True}
        self.grants = copy.deepcopy(self.fx.authority._read()["grants"])
        self.grant_revision = self.fx.authority._read()["revision"]
        self.store.configure_binding(self.fx.admin, self.spec, expected_revision=0)

    def enrolled(self, ident="synthetic-credential"):
        permit = self.store.issue_enrollment(self.fx.admin, self.spec["principalId"])
        self.store.reserve_enrollment(permit, self.spec["principalId"], "localhost",
                                     self.spec["origin"], "synthetic-ceremony")
        self.store.register(permit, self.spec["principalId"], "localhost", self.spec["origin"],
            "synthetic-ceremony", ident, b"synthetic public key", b"synthetic user id", 0,
            {"syntheticRegistration": True})
        return ident, permit

    def proof(self, counter=1, tag="one", ident="synthetic-credential"):
        response = {"syntheticChallenge": tag, "counter": counter}
        binding = self.store.binding(self.spec["principalId"])
        proof = {"schemaVersion": 1, "credentialId": ident,
            "principalId": self.spec["principalId"], "origin": self.spec["origin"], "rpId": "localhost",
            "approvalSHA256": "a" * 64, "decision": "approve", "userVerified": True,
            "proofSHA256": MODULE.digest(response), "graphExecutionAuthorized": False,
            "bindingSHA256": MODULE.digest(binding)}
        self.store.record_proof(proof, response, proof["bindingSHA256"], 1, counter)
        return proof

    def test_existing_owner_required_and_no_grants_are_created(self):
        before = self.fx.authority.path.read_bytes()
        delegated = self.fx.authority.manage("issue", self.fx.admin, {
            "permissions": ["grant.admin", "graph.read"], "scopes": ["packages/" + self.fx.namespace + "/"]})
        before = self.fx.authority.path.read_bytes()
        for token in (self.fx.token, self.fx.human_token, delegated["token"]):
            with self.assertRaisesRegex(ValueError, "OWNER_REQUIRED"):
                self.store.configure_binding(token, self.spec, expected_revision=1)
            with self.assertRaisesRegex(ValueError, "OWNER_REQUIRED"):
                self.store.issue_enrollment(token, self.spec["principalId"])
            with self.assertRaisesRegex(ValueError, "OWNER_REQUIRED"):
                self.store.inspect(token)
        self.assertEqual(before, self.fx.authority.path.read_bytes())

    def test_binding_cas_and_namespace_ceiling_fail_without_state_write(self):
        before = self.fx.authority.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "BINDING_CAS"):
            self.store.configure_binding(self.fx.admin, {**self.spec, "displayName": "Other"},
                                         expected_revision=0)
        with self.assertRaisesRegex(ValueError, "EXECUTOR_NAMESPACE"):
            self.store.configure_binding(self.fx.admin, {**self.spec, "namespaceId": str(uuid.uuid4())},
                                         expected_revision=1)
        self.assertEqual(before, self.fx.authority.path.read_bytes())

    def test_enrollment_is_one_use_and_persists_without_raw_permit(self):
        ident, permit = self.enrolled()
        self.assertNotIn(permit, self.fx.authority.path.read_text())
        fresh = MODULE.CredentialStore(self.fx.authority, clock=lambda: self.clock[0])
        _, rows = fresh.credentials(self.spec["principalId"], "localhost", self.spec["origin"])
        self.assertIn(ident, rows)
        self.assertEqual(rows[ident]["counter"], 0)
        with self.assertRaisesRegex(ValueError, "ENROLLMENT_ALREADY_STARTED"):
            fresh.reserve_enrollment(permit, self.spec["principalId"], "localhost",
                                     self.spec["origin"], "different")
        self.assertEqual(self.fx.authority._read()["grants"], self.grants)

    def test_expired_and_changed_binding_permits_cannot_register(self):
        permit = self.store.issue_enrollment(self.fx.admin, self.spec["principalId"])
        self.clock[0] = 1121
        with self.assertRaisesRegex(ValueError, "ENROLLMENT_UNAVAILABLE"):
            self.store.reserve_enrollment(permit, self.spec["principalId"], "localhost",
                                         self.spec["origin"], "expired")
        permit = self.store.issue_enrollment(self.fx.admin, self.spec["principalId"])
        self.store.configure_binding(self.fx.admin, {**self.spec, "displayName": "Reconfigured"},
                                     expected_revision=1)
        with self.assertRaisesRegex(ValueError, "ENROLLMENT_BINDING_CHANGED"):
            self.store.reserve_enrollment(permit, self.spec["principalId"], "localhost",
                                         self.spec["origin"], "old-binding")

    def test_counter_and_evidence_survive_reopen_without_changing_grant_revision(self):
        self.enrolled()
        proof = self.proof()
        reopened = MODULE.CredentialStore(self.fx.authority)
        _, rows = reopened.credentials(self.spec["principalId"], "localhost", self.spec["origin"])
        self.assertEqual(rows["synthetic-credential"]["counter"], 1)
        evidence = self.fx.authority._read()["webauthn"]["proofs"][proof["proofSHA256"]]
        self.assertEqual(evidence["receipt"], proof)
        self.assertEqual(MODULE.digest(evidence["response"]), proof["proofSHA256"])
        self.assertEqual(self.fx.authority._read()["grants"], self.grants)
        self.assertEqual(self.fx.authority._read()["revision"], self.grant_revision)
        with self.assertRaisesRegex(ValueError, "COUNTER_NOT_INCREASING"):
            self.proof(counter=1, tag="different")
        self.proof(counter=2, tag="new")

    def test_zero_counter_still_requires_a_new_assertion(self):
        self.enrolled()
        self.proof(counter=0)
        with self.assertRaisesRegex(ValueError, "PROOF_REPLAY"):
            self.proof(counter=0)
        self.proof(counter=0, tag="different-challenge")

    def test_revoked_credential_is_checked_under_final_authority_lock(self):
        ident, _ = self.enrolled()
        proof = self.proof()
        with self.fx.authority.checked_portable_transaction(self.fx.human_token, [],
                assertion_check=lambda data: self.store.check_proof(data, proof)):
            pass
        self.store.revoke_credential(self.fx.admin, ident, expected_revision=1)
        with self.assertRaisesRegex(ValueError, "CREDENTIAL_UNAVAILABLE"):
            with self.fx.authority.checked_portable_transaction(self.fx.human_token, [],
                    assertion_check=lambda data: self.store.check_proof(data, proof)):
                self.fail("revoked credential reached acceptance")
        self.assertEqual(self.store.credentials(self.spec["principalId"], "localhost",
                                               self.spec["origin"])[1], {})

    def test_changed_binding_invalidates_verified_proof_before_acceptance(self):
        self.enrolled()
        proof = self.proof()
        self.store.configure_binding(self.fx.admin, {**self.spec, "displayName": "Updated"},
                                     expected_revision=1)
        with self.assertRaisesRegex(ValueError, "BINDING_CHANGED"):
            with self.fx.authority.checked_portable_transaction(self.fx.human_token, [],
                    assertion_check=lambda data: self.store.check_proof(data, proof)):
                self.fail("stale binding reached acceptance")

    def test_operator_cli_denies_agent_and_writes_invite_only_to_private_file(self):
        target = self.fx.base / "owner-enrollment-permit"
        env = {k: v for k, v in os.environ.items() if not k.startswith("RDG_AUTH_")}
        args = [sys.executable, "-B", str(ROOT / "tools/rdg-credentials.py"), "invite",
                "--store", str(self.fx.authority.path), "--principal", self.spec["principalId"],
                "--permit-file", str(target)]
        denied = subprocess.run(args, env={**env, "RDG_AUTH_TOKEN": self.fx.token},
                                capture_output=True, text=True, timeout=30)
        self.assertNotEqual(denied.returncode, 0)
        self.assertFalse(target.exists())
        issued = subprocess.run(args, env={**env, "RDG_AUTH_TOKEN": self.fx.admin},
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(issued.returncode, 0, issued.stderr)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        permit = target.read_text().strip()
        self.assertGreater(len(permit), 32)
        self.assertNotIn(permit, issued.stdout + issued.stderr)
        self.assertFalse(json.loads(issued.stdout)["rawPermitReturned"])
        for token in (self.fx.admin, self.fx.token):
            self.assertNotIn(token, issued.stdout + issued.stderr + denied.stdout + denied.stderr)


if __name__ == "__main__":
    unittest.main()
