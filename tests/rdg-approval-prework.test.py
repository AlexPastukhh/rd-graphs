#!/usr/bin/env python3
"""Pilot pending/input-closure proofs. These are not trusted human approval."""
import copy
import hashlib
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = SourceFileLoader("approval_fixture", str(ROOT / "tests/rdg-portable-service.test.py")).load_module()
H = SourceFileLoader("approval_helper", str(ROOT / "tools/rdg-workflow-helper.py")).load_module()


class ApprovalPrework(unittest.TestCase):
    setUp = BASE.PortableApplication.setUp
    config = BASE.PortableApplication.config
    app = BASE.PortableApplication.app
    req = BASE.PortableApplication.req
    create = BASE.PortableApplication.create
    current = BASE.PortableApplication.current
    command_request = BASE.PortableApplication.command_request
    command = BASE.PortableApplication.command
    placement = BASE.PortableApplication.placement
    replace_request = BASE.PortableApplication.replace_request

    def files(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*") if p.is_file()}

    def public(self, command, body=None, agent=False, extra=(), ok=True):
        env = {k: v for k, v in os.environ.items() if not k.startswith("RDG_AUTH_")}
        env.update(RDG_AUTH_STORE=str(self.authority.path), RDG_AUTH_TOKEN=self.token,
                   PYTHONDONTWRITEBYTECODE="1")
        if agent:
            context = self.base / "approval-agent.json"
            context.write_text(json.dumps({"profile": "portable",
                **{k: v for k, v in self.config().items() if k != "authorityStore"}}))
            args = [sys.executable, "-B", str(ROOT / "tools/rdg-agent.py"),
                    command, "--context", str(context), *extra]
        else:
            args = [sys.executable, "-B", str(ROOT / "tools/rdg-portable.py"), command,
                    "--packages", str(self.root), "--namespace", self.namespace,
                    "--coordination-root", str(self.base), "--store", str(self.authority.path),
                    *extra]
        run = subprocess.run(args, input=json.dumps(body) if body is not None else None,
                             text=True, capture_output=True, timeout=45, env=env)
        self.assertNotIn(self.token, run.stdout + run.stderr)
        self.assertNotIn(self.admin, run.stdout + run.stderr)
        if ok:
            self.assertEqual(run.returncode, 0, run.stderr)
            return json.loads(run.stdout)
        self.assertNotEqual(run.returncode, 0)
        return run.stderr

    def pending(self, request, app=None):
        return (app or self.app()).call({"method": "approval_request", "request": request,
                                       "rationale": "Synthetic proposal; not human consent"})

    def test_pending_reserves_unaccepted_intent_without_graph_write_and_survives_new_processes(self):
        ident = self.create("pending")
        request = self.command_request(ident, "edit", nodeId="R1", changes={"title": "Proposed"})
        before = self.files()
        first = self.pending(request)
        after = self.files()
        path = ".rdg/approval-requests/" + request["transactionId"] + ".json"
        intent = ".rdg/intents/" + request["transactionId"] + ".json"
        self.assertEqual(set(after) - set(before), {path, intent})
        self.assertTrue(all(after[p] == digest for p, digest in before.items()))
        self.assertFalse(first["executionAvailable"] or first["humanApprovalVerified"])
        self.assertEqual(first["state"], "pending")
        self.assertTrue(first["previewIsSnapshot"])
        self.assertTrue(first["preview"]["available"])
        self.assertNotIn("actorTokenSHA256", first)
        self.assertFalse(self.app().receipt(ident, request["transactionId"])["found"])
        for token in (self.token, self.admin):
            self.assertNotIn(token, (self.root / path).read_text())
        message = {"request": request, "rationale": first["rationale"]}
        self.assertEqual(self.public("approval_request", message), first)
        self.assertEqual(self.public("approval_request", message, agent=True), first)
        self.assertEqual(self.public("approval_read", extra=("--transaction-id", request["transactionId"])), first)
        self.assertEqual(self.public("approval_read", agent=True,
                         extra=("--transaction-id", request["transactionId"])), first)
        editor = H.PortableEditor(self.config(), self.token)
        self.assertEqual(editor.dispatch({"method": "approval_read", "requestId": request["transactionId"]}), first)
        self.assertEqual(self.files(), after)

    def test_manual_lock_proposal_needs_no_unverified_principal_claim(self):
        ident = self.create("manual-lock-proposal")
        request = self.app().schema("lock_set", ident, "R1")["request"]
        request.update(operation="edit", mode="hard", principals=["key:synthetic-human"],
                       authorityPrincipal="", message="Synthetic lock", note="Propose key management")
        manual = BASE.CLI.application(self.config(), self.token, attribution="user")
        before = self.current(ident)
        result = self.pending(request, manual)
        self.assertFalse(result["preview"]["available"])
        self.assertEqual(result["preview"]["blocker"], "PORTABLE_APP_LOCK_PRINCIPAL_REQUIRED")
        self.assertFalse(result["humanApprovalVerified"])
        self.assertEqual(self.current(ident), before)
        self.assertFalse(self.app().receipt(ident, request["transactionId"])["found"])

    def test_hard_locked_proposal_does_not_enable_execution_or_trust_user_text(self):
        ident = self.create("locked")
        lock = self.app().schema("lock_set", ident)["request"]
        lock.update(principals=["key:synthetic-human"], authorityPrincipal="user:synthetic",
                    message="Synthetic protected edit", note="Fixture lock")
        BASE.CLI.application(self.config(), self.token, attribution="user").request(lock)
        request = self.command_request(ident, "edit", nodeId="R1", changes={"title": "Denied"})
        before = self.current(ident)
        pending = self.pending(request)
        self.assertFalse(pending["preview"]["available"])
        self.assertEqual(pending["preview"]["blocker"], "CORE_OBJECT_OPERATION_LOCK_REQUIRED")
        self.assertEqual(self.current(ident), before)
        for app in (self.app(), BASE.CLI.application(self.config(), self.token, attribution="user")):
            with self.assertRaisesRegex(ValueError, "OBJECT_OPERATION_LOCK_REQUIRED"):
                app.request(request)
            with self.assertRaisesRegex(ValueError, "MESSAGE_FIELDS"):
                app.call({"method": "approval_approve", "requestId": request["transactionId"],
                          "by": "user", "authorityPrincipal": "key:synthetic-human"})
        forged = {**request, "authorityPrincipal": "key:synthetic-human", "by": "user"}
        with self.assertRaisesRegex(ValueError, "CORE_FIELDS"):
            self.app().prepare(forged)
        self.assertEqual(self.current(ident), before)
        self.assertFalse(self.app().receipt(ident, request["transactionId"])["found"])

    def test_pending_id_is_bound_to_request_actor_and_rationale(self):
        ident = self.create("immutable")
        request = self.command_request(ident, "edit", nodeId="R1", changes={"title": "One"})
        pending = self.pending(request)
        files = self.files()
        changed = copy.deepcopy(request)
        changed["data"]["changes"]["title"] = "Two"
        with self.assertRaisesRegex(ValueError, "APPROVAL_REQUEST_ID_CONFLICT"):
            self.pending(changed)
        with self.assertRaisesRegex(ValueError, "APPROVAL_REQUEST_ID_CONFLICT"):
            self.app().call({"method": "approval_request", "request": request, "rationale": "Different"})
        with self.assertRaisesRegex(ValueError, "TRANSACTION_ID_CONFLICT"):
            self.app().request(changed)
        grant = self.authority.manage("issue", self.admin, {"permissions": BASE.FIX.PERMISSIONS,
                                      "scopes": ["packages/" + self.namespace + "/"]})
        with self.assertRaisesRegex(ValueError, "APPROVAL_REQUEST_ACTOR_MISMATCH"):
            self.app(grant["token"]).approval_read(pending["requestId"])
        with self.assertRaisesRegex(ValueError, "APPROVAL_REQUEST_ACTOR_MISMATCH"):
            self.pending(request, self.app(grant["token"]))
        self.assertEqual(self.files(), files)

    def test_current_grant_and_scope_are_required_for_pending_access(self):
        ident = self.create("scope")
        request = self.command_request(ident, "edit", nodeId="R1", changes={"title": "Change"})
        pending = self.pending(request)
        self.authority.manage("revoke", self.admin, {"id": self.grant_id})
        files = self.files()
        with self.assertRaisesRegex(ValueError, "TOKEN_REVOKED"):
            self.app().approval_read(pending["requestId"])
        with self.assertRaisesRegex(ValueError, "TOKEN_REVOKED"):
            self.pending(request)
        self.assertEqual(self.files(), files)

    def test_missing_plan_edit_can_be_proposed_but_never_granted_by_pending(self):
        target = self.create("target")
        source = self.create("source", "ready")
        owner = self.create("plan-owner")
        self.app().request(self.placement(owner, target))
        request = self.replace_request(target, source)
        grant = self.authority.manage("issue", self.admin, {
            "permissions": ["graph.read", "graph.write", "plan.read"],
            "scopes": ["packages/" + self.namespace + "/"]})
        limited = self.app(grant["token"])
        before = {p: self.current(p) for p in (target, owner)}
        pending = self.pending(request, limited)
        self.assertFalse(pending["preview"]["available"])
        self.assertIn("plan.edit", pending["preview"]["blocker"])
        with self.assertRaisesRegex(ValueError, "MISSING_PERMISSION"):
            limited.request(request)
        self.assertEqual(before, {p: self.current(p) for p in (target, owner)})
        self.assertFalse(limited.receipt(target, request["transactionId"])["found"])

    def test_new_p2_with_same_target_and_request_invalidates_full_input_binding(self):
        target = self.create("closure-target")
        source = self.create("closure-source", "ready")
        p1 = self.create("P1")
        self.app().request(self.placement(p1, target))
        request = self.replace_request(target, source)
        graph_before = self.current(target)
        first = self.app().request(request, preflight=True)
        pending = self.pending(request)
        self.assertEqual(first["inputBinding"], pending["preview"]["inputBinding"])
        p2 = self.create("P2")
        self.app().request(self.placement(p2, target))
        self.assertEqual(self.current(target), graph_before)
        second = self.app().request(request, preflight=True)
        self.assertEqual(first["inputBinding"]["requestSHA256"], second["inputBinding"]["requestSHA256"])
        self.assertNotEqual(first["inputBinding"], second["inputBinding"])
        self.assertEqual(self.public("preflight", request)["inputBinding"], second["inputBinding"])
        self.assertNotIn(p2, first["effects"]["removedPlacements"])
        self.assertIn(p2, second["effects"]["removedPlacements"])
        before = self.files()
        with self.assertRaisesRegex(ValueError, "PREVIEW_INPUTS_CHANGED"):
            self.app().call({"method": "apply", "request": request,
                             "expectedInputBinding": first["inputBinding"]})
        self.assertEqual(self.files(), before)
        self.assertEqual(self.current(target), graph_before)
        message = {"method": "apply", "request": request,
                   "expectedInputBinding": second["inputBinding"]}
        accepted = self.app().call(message)
        self.assertTrue(accepted["accepted"])
        self.assertTrue(self.app().call(message)["idempotent"])
        for owner in (p1, p2):
            self.assertEqual(self.current(owner)["plan"]["steps"], [])
        state = self.app().approval_read(request["transactionId"])
        self.assertEqual(state["state"], "executed-independently")
        self.assertFalse(state["humanApprovalVerified"])

    def test_modified_request_and_binding_are_rejected_before_staging(self):
        ident = self.create("modified")
        request = self.command_request(ident, "edit", nodeId="R1", changes={"title": "First"})
        before = self.files()
        first = self.app().request(request, preflight=True)
        second = self.app().request(request, preflight=True)
        self.assertEqual(first["inputBinding"], second["inputBinding"])
        self.assertEqual(self.files(), before)
        changed = copy.deepcopy(request)
        changed["data"]["changes"]["title"] = "Another"
        for intent, binding in ((changed, first["inputBinding"]),
                                (request, {**first["inputBinding"], "sha256": "0" * 64})):
            with self.assertRaisesRegex(ValueError, "PREVIEW_INPUTS_CHANGED"):
                self.app().request(intent, expected_input_binding=binding)
        self.assertEqual(self.files(), before)

    def test_cli_and_agent_check_binding_and_cannot_override_pending_method(self):
        ident = self.create("public")
        request = self.command_request(ident, "edit", nodeId="R1", changes={"title": "Pending"})
        malicious = {"request": request, "rationale": "Synthetic", "method": "apply"}
        before = self.files()
        for agent in (False, True):
            self.assertIn("APPROVAL_MESSAGE_FIELDS", self.public("approval_request", malicious,
                                                               agent=agent, ok=False))
        self.assertEqual(self.files(), before)
        binding = self.app().request(request, preflight=True)["inputBinding"]
        path = self.base / "binding.json"
        path.write_text(json.dumps(binding))
        wrong = copy.deepcopy(request)
        wrong["note"] = "Changed request"
        for command, agent in (("apply", False), ("command", True)):
            self.assertIn("PREVIEW_INPUTS_CHANGED", self.public(command, wrong, agent=agent,
                          extra=("--expected-input-binding", str(path)), ok=False))
        self.assertEqual(self.files(), before)
        result = self.public("apply", request, extra=("--expected-input-binding", str(path)))
        self.assertTrue(result["accepted"])

    def test_revocation_at_acceptance_still_blocks_a_bound_request(self):
        ident = self.create("revoked-at-accept")
        request = self.command_request(ident, "edit", nodeId="R1", changes={"title": "Denied"})
        binding = self.app().request(request, preflight=True)["inputBinding"]
        before = self.files()
        def revoke():
            self.authority.manage("revoke", self.admin, {"id": self.grant_id})
        with self.assertRaisesRegex(ValueError, "TOKEN_REVOKED"):
            self.app().request(request, expected_input_binding=binding, before_accept=revoke)
        self.assertEqual(self.files(), before)

    def test_adapter_binding_and_pending_claims_are_not_silently_accepted(self):
        ident = self.create("adapter")
        move = self.app().schema("move", ident)["request"]
        move.update(path="moved/place", note="Synthetic move")
        before = self.files()
        with self.assertRaisesRegex(ValueError, "TRANSFER_PREVIEW_INPUTS_CHANGED"):
            self.app().request(move, expected_input_binding={})
        first = self.app().request(move, preflight=True)
        self.assertEqual(first["inputBinding"]["policy"], "filesystem-tree-v1")
        self.assertEqual(first["inputBinding"]["requestSHA256"],
                         self.app().model.digest(move))
        self.assertEqual(self.files(), before)

        # A catalog change invalidates the old move preview even though the target
        # package and request body are unchanged.
        self.create("catalog-change")
        with self.assertRaisesRegex(ValueError, "TRANSFER_PREVIEW_INPUTS_CHANGED"):
            self.app().request(move, expected_input_binding=first["inputBinding"])
        second = self.app().request(move, preflight=True)
        self.assertNotEqual(first["inputBinding"], second["inputBinding"])
        result = self.app().request(move, expected_input_binding=second["inputBinding"])
        self.assertTrue(result["accepted"])
        self.assertEqual(self.app().snapshot(ident)["path"], "moved/place")

        folder_create=self.app().schema("folder_create")["request"]
        folder_create["path"]="empty-folder"
        folder_preview=self.app().request(folder_create,preflight=True)
        self.assertEqual(folder_preview["inputBinding"]["policy"],"filesystem-tree-v1")
        self.app().request(folder_create,expected_input_binding=folder_preview["inputBinding"])
        folder_move=self.app().schema("folder_move",source_path="empty-folder")["request"]
        folder_move["path"]="renamed-folder"
        folder_preview=self.app().request(folder_move,preflight=True)
        self.app().request(folder_move,expected_input_binding=folder_preview["inputBinding"])
        self.assertTrue((self.root/"renamed-folder").is_dir())

        cli_ident=self.create("adapter-cli")
        cli_move=self.app().schema("move",cli_ident)["request"]
        cli_move.update(path="moved/cli",note="CLI move binding")
        cli_preview=self.public("preflight",cli_move)
        self.assertEqual(self.app().request(cli_move,preflight=True)["inputBinding"],
                         cli_preview["inputBinding"])
        binding_path=self.base/"adapter-cli-binding.json"
        binding_path.write_text(json.dumps(cli_preview["inputBinding"]))
        cli_result=self.public("apply",cli_move,
                              extra=("--expected-input-binding",str(binding_path)))
        self.assertTrue(cli_result["accepted"])
        self.assertEqual(self.app().snapshot(cli_ident)["path"],"moved/cli")

        with self.assertRaisesRegex(ValueError, "APPROVAL_ADAPTER_NOT_IMPLEMENTED"):
            self.pending(move)
        with self.assertRaisesRegex(ValueError, "MESSAGE_FIELDS"):
            self.app().call({"method": "approval_request", "request": move,
                             "rationale": "Synthetic", "humanBearer": "not-a-real-token"})


    def test_pending_delete_respects_remove_lock_and_edit_lock_stays_pair_scoped(self):
        protected = self.create("remove-protected")
        editable = self.create("edit-only")
        user = BASE.CLI.application(self.config(), self.token, attribution="user")
        for ident, operation in ((protected, "remove"), (editable, "edit")):
            lock = user.schema("lock_set", ident)["request"]
            lock.update(operation=operation, principals=["key:fixture"],
                        authorityPrincipal="user:fixture", message="Synthetic pair", note="Fixture")
            user.request(lock)
        current = self.current(protected)
        request = self.req("delete", targetPackageId=protected,
                           expectedPackageRevision=current["package"]["revision"],
                           expectedGraphRevision=current["graph"]["revision"],
                           nodeIds=["R1"], note="Synthetic delete")
        pending = self.pending(request)
        self.assertFalse(pending["preview"]["available"])
        self.assertIn("OBJECT_OPERATION_LOCK_REQUIRED", pending["preview"]["blocker"])
        with self.assertRaisesRegex(ValueError, "OBJECT_OPERATION_LOCK_REQUIRED"):
            self.app().request(request)
        self.assertEqual(self.current(protected), current)
        current = self.current(editable)
        allowed = self.req("delete", targetPackageId=editable,
                           expectedPackageRevision=current["package"]["revision"],
                           expectedGraphRevision=current["graph"]["revision"],
                           nodeIds=["R1"], note="Different operation from edit")
        self.assertTrue(self.app().request(allowed)["accepted"])
        self.assertNotIn("R1", BASE.M.entities(self.app().store.read(editable)["graph"]))

    def test_readonly_and_wrong_scope_cannot_create_pending_metadata(self):
        import uuid
        ident = self.create("read-scope")
        request = self.command_request(ident, "edit", nodeId="R1", changes={"title": "Denied"})
        readonly = self.authority.manage("issue", self.admin, {"permissions": ["graph.read"],
                                        "scopes": ["packages/" + self.namespace + "/"]})
        wrong = self.authority.manage("issue", self.admin, {"permissions": ["graph.read", "graph.write"],
                                     "scopes": ["packages/" + self.namespace + "/" + str(uuid.uuid4())]})
        before = self.files()
        for token, error in ((readonly["token"], "MISSING_PERMISSION"), (wrong["token"], "SCOPE_DENIED")):
            with self.assertRaisesRegex(ValueError, error):
                self.pending(request, self.app(token))
        self.assertEqual(self.files(), before)


    def test_other_plan_scope_can_block_preview_without_blocking_the_proposal(self):
        target = self.create("scope-target")
        source = self.create("scope-source", "ready")
        owner = self.create("outside-plan-scope")
        self.app().request(self.placement(owner, target))
        request = self.replace_request(target, source)
        grant = self.authority.manage("issue", self.admin, {
            "permissions": ["graph.read", "graph.write", "plan.read", "plan.edit"],
            "scopes": ["packages/" + self.namespace + "/" + ident for ident in (target, source)]})
        limited = self.app(grant["token"])
        before = {p: self.current(p) for p in (target, owner)}
        proposal = self.pending(request, limited)
        self.assertFalse(proposal["preview"]["available"])
        self.assertEqual(proposal["preview"]["blocker"], "AUTH_PORTABLE_SCOPE_DENIED")
        with self.assertRaisesRegex(ValueError, "SCOPE_DENIED"):
            limited.request(request)
        self.assertEqual(before, {p: self.current(p) for p in (target, owner)})


    def test_pending_id_cannot_be_reused_by_the_filesystem_writer(self):
        ident = self.create("shared-intent")
        request = self.command_request(ident, "edit", nodeId="R1", changes={"title": "One intent"})
        self.pending(request)
        move = self.app().schema("move", ident)["request"]
        move.update(transactionId=request["transactionId"], path="moved/collision",
                    note="A different operation must not reuse pending ID")
        before = self.files()
        with self.assertRaisesRegex(ValueError, "TRANSACTION_ID_CONFLICT"):
            self.app().request(move)
        self.assertEqual(self.files(), before)
        self.assertEqual(self.app().approval_read(request["transactionId"])["state"], "pending")


if __name__ == "__main__":
    unittest.main()
