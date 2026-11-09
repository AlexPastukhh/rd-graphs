#!/usr/bin/env python3
"""Opt-in approval surface contract. Synthetic verifier; no real human proof."""
from importlib.machinery import SourceFileLoader
from contextlib import contextmanager
import errno
import fcntl
from unittest.mock import patch
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = SourceFileLoader("surface_execution_fixture", str(ROOT / "tests/rdg-approval-execution.test.py")).load_module()
MODULE = SourceFileLoader("approval_surface_test", str(ROOT / "tools/rdg-approval-surface.py")).load_module()


class ApprovalSurface(unittest.TestCase):
    def setUp(self):
        self.fx = BASE.ApprovalExecution(
            "test_exact_signed_execution_separates_three_actors_without_granting_ai")
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.clock = [0.]
        self.surface = MODULE.ApprovalSurface(self.fx.executor, clock=lambda: self.clock[0])

    def request(self, locked=True):
        ident = self.fx.locked() if locked else self.fx.create("unlocked")
        body = self.fx.edit(ident)
        self.fx.pending(body)
        return ident, body

    def call(self, method, **body):
        return self.surface.dispatch({"method": method, **body})

    def test_displayed_preview_is_the_one_signed_and_executed(self):
        ident, body = self.request()
        opened = self.call("open", requestId=body["transactionId"])
        self.assertTrue(opened["previewAvailable"])
        self.assertEqual(self.call("list")["requests"][0]["state"], "pending")
        for token in (self.fx.token, self.fx.human_token, self.fx.admin):
            self.assertNotIn(token, json.dumps(opened))
        begin = self.call("choose", viewId=opened["viewId"], decision="approve")
        self.assertNotIn("preview", begin)
        self.assertFalse(self.fx.app().receipt(ident, body["transactionId"])["found"])
        result = self.call("complete", ceremonyId=begin["ceremonyId"],
                           response=self.fx.verifier.response(begin["ceremonyId"]))
        self.assertEqual(result["packages"][0]["receipt"]["authorizationContext"]["previewSHA256"],
                         self.fx.human.model.digest(opened["preview"]))
        self.assertEqual(self.fx.current(ident)["graph"], opened["preview"]["owners"][0]["after"]["graph"])
        self.assertEqual(self.call("status", requestId=body["transactionId"])["state"], "executed-approved")
        with self.assertRaisesRegex(ValueError, "CEREMONY_UNAVAILABLE"):
            self.call("complete", ceremonyId=begin["ceremonyId"], response={})

    def test_open_and_decide_with_serialized_read_locks(self):
        # Windows preview maps shared locks to exclusive byte-range locks.
        # Separate handles must contend, including handles in the same process.
        ident, body = self.request()
        store = self.fx.human.store

        @contextmanager
        def serialized(exclusive=True, create=True):
            with (store.coordination_root / ".rdg-reference.lock").open("a+b") as stream:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise PermissionError(errno.EACCES, "Permission denied") from exc
                try:
                    yield
                finally:
                    fcntl.flock(stream, fcntl.LOCK_UN)

        original = self.fx.executor._preview
        def preview(*args, **kwargs):
            # Removing the duplicate acquisition must retain writer exclusion.
            with self.assertRaises(PermissionError):
                with serialized():
                    pass
            return original(*args, **kwargs)

        with patch.object(store, "lock", serialized), patch.object(self.fx.executor, "_preview", preview):
            opened = self.call("open", requestId=body["transactionId"])
            self.assertTrue(opened["previewAvailable"])
            self.assertFalse(self.fx.app().receipt(ident, body["transactionId"])["found"])
            begin = self.call("choose", viewId=opened["viewId"], decision="approve")
            self.call("complete", ceremonyId=begin["ceremonyId"],
                      response=self.fx.verifier.response(begin["ceremonyId"]))
            self.assertEqual(self.call("status", requestId=body["transactionId"])["state"], "executed-approved")

    def test_trusted_loopback_cannot_remove_a_lock_through_manual_attribution(self):
        helper = SourceFileLoader("surface_manual_boundary_helper",
            str(ROOT / "tools/rdg-workflow-helper.py")).load_module()
        ident, _ = self.request()
        editor = helper.PortableEditor(self.fx.config(), self.fx.token)
        def factory(origin):
            self.fx.verifier.origin, self.fx.verifier.rp_id = origin, "localhost"
            return self.surface
        server = helper.make_server(editor, approval_factory=factory)
        try:
            request = self.fx.app().schema("lock_remove", ident, "R1")["request"]
            request.update(operation="edit", authorityPrincipal="user:unverified",
                           disposition="Synthetic unverified attempt", note="Must require WebAuthn")
            with self.assertRaisesRegex(ValueError, "VERIFIED_APPROVAL_REQUIRED"):
                editor.dispatch({"method": "apply", "request": request})
            self.assertIn("edit", self.fx.current(ident)["graph"]["nodes"][0]["locks"])
        finally:
            server.server_close()

    def test_new_plan_requires_refresh_before_browser_assertion(self):
        target = self.fx.create("target")
        source = self.fx.create("paper", "ready")
        p1 = self.fx.create("P1")
        self.fx.app().request(self.fx.placement(p1, target))
        body = self.fx.replace_request(target, source)
        self.fx.pending(body)
        opened = self.call("open", requestId=body["transactionId"])
        p2 = self.fx.create("P2")
        self.fx.app().request(self.fx.placement(p2, target))
        with self.assertRaisesRegex(ValueError, "PREVIEW_CHANGED"):
            self.call("choose", viewId=opened["viewId"], decision="approve")
        self.assertFalse(self.fx.app().receipt(target, body["transactionId"])["found"])
        fresh = self.call("open", requestId=body["transactionId"])
        self.assertEqual(set(fresh["preview"]["effects"]["removedPlacements"]), {p1, p2})

    def test_missing_write_right_is_visible_and_can_only_reject(self):
        ident, body = self.request()
        grant = self.fx.authority.manage("issue", self.fx.admin, {
            "permissions": ["graph.read"], "scopes": ["packages/" + self.fx.namespace + "/" + ident]})
        self.surface = MODULE.ApprovalSurface(self.fx.bridge(self.fx.app(grant["token"]), grant=grant["id"]))
        opened = self.call("open", requestId=body["transactionId"])
        self.assertFalse(opened["previewAvailable"])
        self.assertTrue(opened["blocker"])
        with self.assertRaisesRegex(ValueError, "PREVIEW_UNAVAILABLE"):
            self.call("choose", viewId=opened["viewId"], decision="approve")
        begin = self.call("choose", viewId=opened["viewId"], decision="reject")
        result = self.call("complete", ceremonyId=begin["ceremonyId"],
                           response=self.fx.verifier.response(begin["ceremonyId"]))
        self.assertEqual(result["state"], "rejected")
        self.assertFalse(self.fx.app().receipt(ident, body["transactionId"])["found"])
        with self.assertRaisesRegex(ValueError, "ACCEPTED_REQUIRED"):
            self.call("recover", requestId=body["transactionId"])

    def test_list_filters_current_scope_and_revocation_does_not_become_empty_success(self):
        ident, body = self.request()
        other = self.fx.create("other")
        other_body = self.fx.edit(other)
        self.fx.pending(other_body)
        grant = self.fx.authority.manage("issue", self.fx.admin, {
            "permissions": ["graph.read"], "scopes": ["packages/" + self.fx.namespace + "/" + ident]})
        self.surface = MODULE.ApprovalSurface(self.fx.bridge(self.fx.app(grant["token"]), grant=grant["id"]))
        self.assertEqual([r["requestId"] for r in self.call("list")["requests"]], [body["transactionId"]])
        with self.assertRaisesRegex(ValueError, "SCOPE_DENIED"):
            self.call("open", requestId=other_body["transactionId"])
        self.fx.authority.manage("revoke", self.fx.admin, {"id": grant["id"]})
        with self.assertRaisesRegex(ValueError, "TOKEN_REVOKED"):
            self.call("list")

    def test_expired_view_and_client_actor_claims_cannot_authorize(self):
        ident, body = self.request()
        opened = self.call("open", requestId=body["transactionId"])
        self.clock[0] = 121
        with self.assertRaisesRegex(ValueError, "VIEW_UNAVAILABLE"):
            self.call("choose", viewId=opened["viewId"], decision="approve")
        for method, fields in [("choose", {"viewId": opened["viewId"], "decision": "approve"}),
                               ("complete", {"ceremonyId": "fake", "response": {}})]:
            with self.assertRaisesRegex(ValueError, "MESSAGE_FIELDS"):
                self.call(method, **fields, principalId="synthetic-operator")
        with self.assertRaisesRegex(ValueError, "MESSAGE_FIELDS"):
            self.fx.app().call({"method": "approval_complete", "response": {"userVerified": True}})
        self.assertFalse(self.fx.app().receipt(ident, body["transactionId"])["found"])

    def test_accepted_recovery_survives_revocation_without_new_consent(self):
        ident, body = self.request()
        opened = self.call("open", requestId=body["transactionId"])
        begin = self.call("choose", viewId=opened["viewId"], decision="approve")
        original = self.fx.executor.complete
        def crash(ceremony, response):
            def fail(stage):
                if stage == "prepared":
                    raise ValueError("SYNTHETIC_AFTER_ACCEPTANCE")
            return original(ceremony, response, failpoint=fail)
        self.fx.executor.complete = crash
        with self.assertRaisesRegex(ValueError, "WRITER_OUTCOME_UNCONFIRMED"):
            self.call("complete", ceremonyId=begin["ceremonyId"],
                      response=self.fx.verifier.response(begin["ceremonyId"]))
        self.fx.authority.manage("revoke", self.fx.admin, {"id": self.fx.human_grant})
        self.assertEqual(self.call("status", requestId=body["transactionId"])["state"], "approved-awaiting-recovery")
        self.assertTrue(self.call("recover", requestId=body["transactionId"])["accepted"])
        self.assertEqual(self.call("status", requestId=body["transactionId"])["state"], "executed-approved")
        self.assertEqual(self.fx.current(ident)["graph"]["nodes"][0]["title"], "Approved title")


if __name__ == "__main__":
    unittest.main()
