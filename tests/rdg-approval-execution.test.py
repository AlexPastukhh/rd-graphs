#!/usr/bin/env python3
"""Synthetic actor-chain/CAS/recovery tests; fake verifier, no real human proof."""
import copy
import hashlib
import hmac
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import secrets
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = SourceFileLoader("execution_fixture", str(ROOT / "tests/rdg-portable-service.test.py")).load_module()
MODULE = SourceFileLoader("approval_execution", str(ROOT / "tools/rdg-approval-executor.py")).load_module()


class SyntheticVerifier:
    """In-process test double. Native WebAuthn is tested separately in Chromium."""
    def __init__(self):
        self.ceremonies = {}
        self.secret = secrets.token_bytes(32)

    def begin_decision(self, principal, digest, decision):
        ident = secrets.token_hex(32)
        self.ceremonies[ident] = (principal, digest, decision)
        return {"ceremonyId": ident, "options": {"synthetic": True}}

    def response(self, ident):
        return {"syntheticSignature": hmac.new(self.secret, ident.encode(), "sha256").hexdigest()}

    def complete_decision(self, ident, response, digest):
        principal, expected, decision = self.ceremonies.pop(ident)
        if digest != expected or response != self.response(ident):
            raise ValueError("SYNTHETIC_ASSERTION_INVALID")
        return {"schemaVersion": 1, "principalId": principal, "credentialId": "synthetic-credential",
            "origin": "http://localhost:12345", "rpId": "localhost", "decision": decision,
            "approvalSHA256": digest, "userVerified": True,
            "proofSHA256": hashlib.sha256(json.dumps(response, sort_keys=True).encode()).hexdigest(),
            "graphExecutionAuthorized": False}


class ApprovalExecution(unittest.TestCase):
    config = BASE.PortableApplication.config
    app = BASE.PortableApplication.app
    req = BASE.PortableApplication.req
    create = BASE.PortableApplication.create
    current = BASE.PortableApplication.current
    command_request = BASE.PortableApplication.command_request
    command = BASE.PortableApplication.command
    placement = BASE.PortableApplication.placement
    replace_request = BASE.PortableApplication.replace_request

    def setUp(self):
        BASE.PortableApplication.setUp(self)
        human = self.authority.manage("issue", self.admin, {"permissions": BASE.FIX.PERMISSIONS,
            "scopes": ["packages/" + self.namespace + "/"]})
        self.human_token, self.human_grant = human["token"], human["id"]
        self.human = self.app(self.human_token)
        self.verifier = SyntheticVerifier()
        self.executor = self.bridge(self.human)

    def bridge(self, app, verifier=None, principal="key:synthetic-human", grant=None):
        return MODULE.ApprovalExecutor(app, verifier or self.verifier, "synthetic-operator",
                                       principal, grant or self.human_grant)

    def locked(self, operation="edit"):
        ident = self.create("locked-" + operation)
        request = self.app().schema("lock_set", ident)["request"]
        request.update(operation=operation, principals=["key:synthetic-human"],
            authorityPrincipal="user:fixture-setup", message="Synthetic hard lock",
            note="Synthetic setup; no real enrollment")
        BASE.CLI.application(self.config(), self.token, attribution="user").request(request)
        return ident

    def pending(self, request):
        return self.app().approval_request(request, "Synthetic AI proposal")

    def begin(self, request, decision="approve", executor=None):
        self.pending(request)
        bridge = executor or self.executor
        ceremony = bridge.begin(request["transactionId"], decision)
        return ceremony, self.verifier.response(ceremony["ceremonyId"])

    def complete(self, begin, response, **kwargs):
        return self.executor.complete(begin["ceremonyId"], response, **kwargs)

    def files(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*") if p.is_file()}

    def edit(self, ident, title="Approved title"):
        return self.command_request(ident, "edit", nodeId="R1", changes={"title": title})

    def test_exact_signed_execution_separates_three_actors_without_granting_ai(self):
        ident = self.locked()
        request = self.edit(ident)
        before = self.current(ident)
        begin, response = self.begin(request)
        self.assertEqual(self.current(ident), before)
        owner = begin["preview"]["owners"][0]
        self.assertEqual(owner["before"]["graph"]["nodes"][0]["title"],
                         before["graph"]["nodes"][0]["title"])
        self.assertEqual(owner["after"]["graph"]["nodes"][0]["title"], "Approved title")
        with self.assertRaisesRegex(ValueError, "TRANSACTION_ACTOR_MISMATCH"):
            self.human.request(request)
        result = self.complete(begin, response)
        self.assertTrue(result["accepted"])
        receipt = result["packages"][0]["receipt"]
        self.assertEqual(receipt["schemaVersion"], 2)
        context = receipt["authorizationContext"]
        self.assertEqual(context["initiator"]["grantId"], self.grant_id)
        self.assertEqual(context["approver"]["principalId"], "synthetic-operator")
        self.assertEqual(context["executor"]["grantId"], self.human_grant)
        self.assertNotEqual(context["initiator"]["grantId"], context["executor"]["grantId"])
        self.assertEqual(context["previewSHA256"], begin["approvalSHA256"])
        for token in (self.token, self.admin, self.human_token):
            self.assertNotIn(token, json.dumps(result) + json.dumps(begin))
        self.assertNotIn("tokenSHA256", json.dumps(result))
        after = self.current(ident)
        self.assertEqual(after["graph"], owner["after"]["graph"])
        event = after["graph"]["events"][-1]
        self.assertEqual(event["by"], "user")
        self.assertEqual(event["authorityPrincipal"], "key:synthetic-human")
        self.assertEqual(event["verifiedTrustReceipt"]["executorGrantId"], self.human_grant)
        self.assertEqual(self.app().approval_read(request["transactionId"])["state"], "executed-approved")
        self.assertEqual(self.app().approval_read(request["transactionId"])["humanApprovalVerified"], False)
        with self.assertRaisesRegex(ValueError, "OBJECT_OPERATION_LOCK_REQUIRED"):
            self.app().request(self.edit(ident, "AI still cannot edit"))

    def test_reject_changes_no_graph_and_prevents_same_id_execution(self):
        ident = self.create("reject-unlocked")
        request = self.edit(ident)
        begin, response = self.begin(request, "reject")
        before = self.current(ident)
        state = self.complete(begin, response)
        self.assertEqual(state["state"], "rejected")
        self.assertEqual(self.current(ident), before)
        self.assertFalse(self.app().receipt(ident, request["transactionId"])["found"])
        self.assertEqual(self.app().approval_read(request["transactionId"])["state"], "rejected")
        with self.assertRaisesRegex(ValueError, "TRANSACTION_REJECTED"):
            self.app().request(request)
        with self.assertRaisesRegex(ValueError, "ALREADY_DECIDED"):
            self.executor.begin(request["transactionId"], "approve")
        # An ordinary new authorized operation remains available.
        self.assertTrue(self.app().request(self.edit(ident, "Independent new action"))["accepted"])

    def test_rejection_still_blocks_execution_if_the_unaccepted_intent_is_missing(self):
        ident = self.create("rejected-without-intent")
        request = self.edit(ident)
        begin, response = self.begin(request, "reject")
        self.complete(begin, response)
        self.store.metadata_path("intents", request["transactionId"]).unlink()
        before = self.current(ident)
        with self.assertRaisesRegex(ValueError, "TRANSACTION_REJECTED"):
            self.app().request(request)
        self.assertEqual(self.current(ident), before)
        self.assertFalse(self.store.metadata_path("accepted", request["transactionId"]).exists())

    def test_reject_does_not_require_missing_write_permissions(self):
        ident = self.create("read-only-reject")
        request = self.edit(ident)
        self.pending(request)
        grant = self.authority.manage("issue", self.admin, {"permissions": ["graph.read"],
            "scopes": ["packages/" + self.namespace + "/"]})
        bridge = self.bridge(self.app(grant["token"]), grant=grant["id"])
        with self.assertRaisesRegex(ValueError, "MISSING_PERMISSION"):
            bridge.begin(request["transactionId"], "approve")
        begin = bridge.begin(request["transactionId"], "reject")
        result = bridge.complete(begin["ceremonyId"], self.verifier.response(begin["ceremonyId"]))
        self.assertEqual(result["state"], "rejected")

    def test_client_proof_dict_and_actor_fields_do_not_authorize(self):
        ident = self.locked()
        request = self.edit(ident)
        begin, _ = self.begin(request)
        before = self.files()
        with self.assertRaisesRegex(ValueError, "SYNTHETIC_ASSERTION_INVALID"):
            self.complete(begin, {"principalId": "synthetic-operator", "userVerified": True})
        self.assertEqual(self.files(), before)
        for field in ("authorizationContext", "approval_actor", "recorded_at"):
            with self.assertRaisesRegex(ValueError, "MESSAGE_FIELDS"):
                self.app().call({"method": "apply", "request": request, field: {}})
        with self.assertRaisesRegex(ValueError, "CEREMONY_UNAVAILABLE"):
            self.complete(begin, {})

    def test_wrong_server_grant_or_object_key_is_denied(self):
        with self.assertRaisesRegex(ValueError, "EXECUTOR_BINDING_CHANGED"):
            self.bridge(self.human, grant=self.grant_id)
        ident = self.locked()
        request = self.edit(ident)
        self.pending(request)
        wrong_key = self.bridge(self.human, principal="key:wrong")
        with self.assertRaisesRegex(ValueError, "OBJECT_OPERATION_LOCK_REQUIRED"):
            wrong_key.begin(request["transactionId"], "approve")
        self.assertFalse(self.app().receipt(ident, request["transactionId"])["found"])

    def test_stale_target_invalidates_assertion_and_requires_new_request(self):
        ident = self.create("stale")
        request = self.edit(ident)
        begin, response = self.begin(request)
        self.command(ident, "edit", nodeId="R1", changes={"description": "Changed"})
        before = self.files()
        with self.assertRaisesRegex(ValueError, "CAS_MISMATCH"):
            self.complete(begin, response)
        self.assertEqual(self.files(), before)
        self.assertFalse(self.app().receipt(ident, request["transactionId"])["found"])

    def test_new_coupled_plan_requires_new_preview_even_with_same_target_and_body(self):
        target = self.create("coupled-target")
        source = self.create("coupled-source", "ready")
        p1 = self.create("P1")
        self.app().request(self.placement(p1, target))
        request = self.replace_request(target, source)
        begin, response = self.begin(request)
        self.assertEqual(set(begin["preview"]["effects"]["removedPlacements"]), {p1})
        target_before = self.current(target)
        p2 = self.create("P2")
        self.app().request(self.placement(p2, target))
        self.assertEqual(self.current(target), target_before)
        before = self.files()
        with self.assertRaisesRegex(ValueError, "PREVIEW_CHANGED"):
            self.complete(begin, response)
        self.assertEqual(self.files(), before)
        updated = self.executor.begin(request["transactionId"], "approve")
        self.assertEqual(set(updated["preview"]["effects"]["removedPlacements"]), {p1, p2})
        result = self.complete(updated, self.verifier.response(updated["ceremonyId"]))
        self.assertEqual(len(result["packages"]), 3)
        for plan in (p1, p2):
            self.assertEqual(self.current(plan)["plan"]["steps"], [])

    def test_revoked_executor_before_acceptance_cannot_stage_or_execute(self):
        ident = self.locked()
        request = self.edit(ident)
        begin, response = self.begin(request)
        before = self.files()
        def revoke():
            self.authority.manage("revoke", self.admin, {"id": self.human_grant})
        with self.assertRaisesRegex(ValueError, "TOKEN_REVOKED"):
            self.complete(begin, response, before_accept=revoke)
        self.assertEqual(self.files(), before)
        self.assertFalse(self.app().receipt(ident, request["transactionId"])["found"])

    def test_revocation_at_final_gate_prevents_durable_acceptance(self):
        ident = self.locked()
        request = self.edit(ident)
        begin, response = self.begin(request)
        before = self.current(ident)
        def failpoint(stage):
            if stage == "staged":
                self.authority.manage("revoke", self.admin, {"id": self.human_grant})
        with self.assertRaisesRegex(ValueError, "TOKEN_REVOKED"):
            self.complete(begin, response, failpoint=failpoint)
        self.assertEqual(self.current(ident), before)
        self.assertFalse(self.store.metadata_path("accepted", request["transactionId"]).exists())

    def test_accepted_payload_recovers_for_initiator_after_executor_revocation_once(self):
        ident = self.locked()
        request = self.edit(ident)
        begin, response = self.begin(request)
        def crash(stage):
            if stage == "prepared":
                raise RuntimeError("synthetic crash after durable acceptance")
        with self.assertRaisesRegex(RuntimeError, "synthetic crash"):
            self.complete(begin, response, failpoint=crash)
        accepted = json.loads(self.store.metadata_path("accepted", request["transactionId"]).read_bytes())
        self.assertEqual(accepted["schemaVersion"], 2)
        self.assertEqual(self.app().approval_read(request["transactionId"])["state"],
                         "approved-awaiting-recovery")
        self.assertEqual(accepted["actorTokenSHA256"], hashlib.sha256(self.token.encode()).hexdigest())
        self.authority.manage("revoke", self.admin, {"id": self.human_grant})
        recovered = self.app().recover(request["transactionId"])
        self.assertTrue(recovered["accepted"] and recovered["idempotent"])
        graph = self.current(ident)["graph"]
        repeated = self.app().request(request)
        self.assertTrue(repeated["idempotent"])
        self.assertEqual(self.current(ident)["graph"], graph)
        other = self.authority.manage("issue", self.admin, {"permissions": BASE.FIX.PERMISSIONS,
            "scopes": ["packages/" + self.namespace + "/"]})
        with self.assertRaisesRegex(ValueError, "TRANSACTION_ACTOR_MISMATCH"):
            self.app(other["token"]).recover(request["transactionId"])
        changed = copy.deepcopy(request)
        changed["data"]["changes"]["title"] = "Different"
        with self.assertRaisesRegex(ValueError, "TRANSACTION_ID_CONFLICT"):
            self.app().request(changed)
        with self.assertRaisesRegex(ValueError, "CEREMONY_UNAVAILABLE"):
            self.complete(begin, response)

    def test_second_signed_decision_cannot_execute_after_first_acceptance(self):
        ident = self.locked()
        request = self.edit(ident)
        first, response = self.begin(request)
        second = self.executor.begin(request["transactionId"], "reject")
        self.complete(first, response)
        before = self.files()
        with self.assertRaisesRegex(ValueError, "ALREADY_ACCEPTED"):
            self.complete(second, self.verifier.response(second["ceremonyId"]))
        self.assertEqual(self.files(), before)
        self.assertTrue(self.human.request(request)["idempotent"])
        self.assertTrue(self.human.receipt(None, request["transactionId"])["accepted"])

    def test_accepted_recovery_is_self_contained_without_pending_or_intent(self):
        ident = self.locked()
        request = self.edit(ident)
        begin, response = self.begin(request)
        def crash(stage):
            if stage == "prepared":
                raise RuntimeError("synthetic crash")
        with self.assertRaisesRegex(RuntimeError, "synthetic crash"):
            self.complete(begin, response, failpoint=crash)
        # Remove only synthetic unaccepted metadata to prove accepted recovery
        # does not acquire a new dependency on the pending store.
        for category in ("approval-requests", "intents"):
            self.store.metadata_path(category, request["transactionId"]).unlink()
        self.assertTrue(self.app().recover(request["transactionId"])["accepted"])
        self.assertEqual(self.current(ident)["graph"]["nodes"][0]["title"], "Approved title")

    def test_changed_effect_with_unchanged_inputs_is_not_the_signed_preview(self):
        ident = self.locked()
        request = self.edit(ident)
        begin, response = self.begin(request)
        original = self.human.prepare
        def changed(*args, **kwargs):
            prepared = original(*args, **kwargs)
            prepared["changes"][ident]["graph"]["nodes"][0]["title"] = "Unshown effect"
            return prepared
        self.human.prepare = changed
        before = self.files()
        with self.assertRaisesRegex(ValueError, "PREVIEW_CHANGED"):
            self.complete(begin, response)
        self.assertEqual(self.files(), before)

    def test_final_catalog_race_cannot_accept_the_old_effect_set(self):
        ident = self.locked()
        request = self.edit(ident)
        begin, response = self.begin(request)
        before = self.current(ident)
        # A foreign non-cooperating synthetic writer changes the namespace marker
        # while the coordinator holds its normal global reference lock.
        def race():
            directory = self.root / "foreign-race"
            directory.mkdir()
            (directory / "package.json").write_text("synthetic invalid concurrent owner")
        with self.assertRaisesRegex(ValueError, "INCOMING_CATALOG_CHANGED"):
            self.complete(begin, response, before_accept=race)
        self.assertEqual(self.current(ident), before)
        self.assertFalse(self.store.metadata_path("accepted", request["transactionId"]).exists())

    def test_retry_of_old_approval_preserves_a_later_approved_revision(self):
        ident = self.locked()
        first = self.edit(ident, "First approved")
        begin, response = self.begin(first)
        self.complete(begin, response)
        second = self.edit(ident, "Later approved")
        begin, response = self.begin(second)
        self.complete(begin, response)
        later = self.current(ident)
        self.assertTrue(self.app().request(first)["idempotent"])
        self.assertTrue(self.app().recover(first["transactionId"])["idempotent"])
        self.assertEqual(self.current(ident), later)

    def test_targetless_create_approval_pins_new_package_and_executes(self):
        request = self.req("create", path="working/approved-create", role="working",
                           title="Approved create", scope="Synthetic approval target")
        pending = self.pending(request)
        self.assertIsNone(pending["targetPackageId"])
        self.assertTrue(pending["preview"]["available"])
        self.assertEqual(pending["preview"]["effects"]["role"], "working")
        begin, response = self.begin(request)
        self.assertIsNone(begin["preview"]["owners"][0]["before"])
        result = self.complete(begin, response)
        self.assertTrue(result["accepted"])
        ident = result["packages"][0]["packageId"]
        current = self.current(ident)
        self.assertEqual(current["package"]["role"], "working")
        self.assertEqual(current["graph"]["title"], "Approved create")
        self.assertEqual(self.app().approval_read(request["transactionId"])["state"],
                         "executed-approved")

    def test_targetless_copy_approval_pins_source_and_executes_new_package(self):
        source = self.create("approval-copy-source")
        source_current = self.current(source)
        request = self.req("copy", sourcePackageId=source,
            sourcePin={"revision": source_current["package"]["revision"],
                       "sha256": BASE.P.digest(source_current["graph"])},
            focus={"kind": "graph"}, includeDescendants=True,
            path="copies/approved-copy", note="Synthetic approved copy")
        pending = self.pending(request)
        self.assertIsNone(pending["targetPackageId"])
        self.assertTrue(pending["preview"]["available"])
        self.assertEqual(pending["preview"]["effects"]["operation"], "copy")
        begin, response = self.begin(request)
        self.assertEqual(begin["preview"]["owners"][0]["before"], None)
        result = self.complete(begin, response)
        self.assertTrue(result["accepted"])
        ident = result["packages"][0]["packageId"]
        copied = self.current(ident)
        self.assertEqual(copied["package"]["role"], "copy")
        self.assertEqual(copied["graph"]["title"], source_current["graph"]["title"])
        self.assertEqual(result["packages"][0]["receipt"]["effects"]["operation"], "copy")

    def test_targetless_reject_records_decision_without_creating_package(self):
        request = self.req("create", path="working/rejected-create", role="working",
                           title="Rejected create", scope="Synthetic rejection target")
        before = self.app().catalog()
        begin, response = self.begin(request, "reject")
        result = self.complete(begin, response)
        self.assertEqual(result["state"], "rejected")
        self.assertEqual(self.app().catalog(), before)
        self.assertEqual(self.app().approval_read(request["transactionId"])["state"], "rejected")

    def test_ordinary_v1_receipt_and_single_actor_boundary_remain(self):
        ident = self.create("ordinary")
        request = self.edit(ident)
        result = self.app().request(request)
        self.assertEqual(result["packages"][0]["receipt"]["schemaVersion"], 1)
        self.assertNotIn("authorizationContext", result["packages"][0]["receipt"])
        with self.assertRaisesRegex(ValueError, "TRANSACTION_ACTOR_MISMATCH"):
            self.human.request(request)


if __name__ == "__main__":
    unittest.main()
