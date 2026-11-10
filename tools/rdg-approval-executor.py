#!/usr/bin/env python3
"""Exact approval coordinator for a trusted in-process host.

No transport or enrollment endpoint is installed by this module. The host owns
the verifier, principal-to-grant/key binding and protection of its executor token.
Ordinary Application messages cannot supply this context.
"""
import copy
from datetime import datetime, timezone
import hashlib
import threading


class ApprovalExecutor:
    def __init__(self, app, verifier, principal_id, authority_principal, executor_grant_id):
        self.app, self.verifier = app, verifier
        self.principal_id, self.authority_principal = principal_id, authority_principal
        self.executor_grant_id = executor_grant_id
        self._lock, self._ceremonies = threading.RLock(), {}
        credentials = getattr(verifier, "credential_store", None)
        self.check(credentials is None or credentials.path.resolve() == app.authority.path.resolve(),
                   "CREDENTIAL_AUTHORITY_BINDING")
        self._actor()

    def check(self, ok, code):
        if not ok:
            raise ValueError("RDG_APPROVAL_" + code)

    def _actor(self):
        actor, _ = self.app.authority._actor(self.app.authority._read(), self.app.token)
        self.check(actor == self.executor_grant_id, "EXECUTOR_BINDING_CHANGED")
        self.check(all(isinstance(s, str) and s.strip() for s in
                       (self.principal_id, self.authority_principal)), "PRINCIPAL_BINDING")
        if getattr(self.verifier, "credential_store", None) is not None:
            self.verifier.validate_binding(self.principal_id, self.app.store.namespace_id,
                                           self.executor_grant_id, self.authority_principal)
        return actor

    def _pending(self, request_id):
        value = self.app.approval_record(request_id)
        self.check(value["namespaceId"] == self.app.store.namespace_id, "NAMESPACE")
        if value["targetPackageId"] is not None:
            self.app.metadata(value["targetPackageId"], ["graph.read"])
        else:
            self.check(value["request"].get("op") in ("create", "copy"), "TARGETLESS_OPERATION")
        self.check(not self.app.store.metadata_path("accepted", request_id).exists(),
                   "ALREADY_ACCEPTED")
        self.check(not self.app.store.metadata_path("approval-decisions", request_id).exists(),
                   "ALREADY_DECIDED")
        self.check(self.app.store.check_intent(request_id, value["requestSHA256"],
                                              value["actorTokenSHA256"]), "INTENT_REQUIRED")
        return value

    def _actor_context(self):
        value = {"principalId": self.principal_id,
                 "authorityPrincipal": self.authority_principal,
                 "executorGrantId": self.executor_grant_id}
        if getattr(self.verifier, "credential_store", None) is not None:
            value["credentialBindingSHA256"] = self.verifier.validate_binding(
                self.principal_id, self.app.store.namespace_id, self.executor_grant_id,
                self.authority_principal)
        return value

    def _preview(self, value, recorded_at, decision):
        request = value["request"]
        result = {"schemaVersion": 1, "kind": "rdgExactApprovalPreview",
            "namespaceId": self.app.store.namespace_id,
            "requestId": value["requestId"], "request": copy.deepcopy(request),
            "rationale": value["rationale"], "initiator": copy.deepcopy(value["initiator"]),
            "executor": self._actor_context(), "decision": decision,
            "pendingSHA256": self.app.model.digest(value), "recordedAt": recorded_at}
        if decision == "reject":
            # Rejection grants no execution and need not acquire missing write rights.
            result["proposalSnapshot"] = copy.deepcopy(value["preview"])
            return result, None
        prepared = self.app.prepare(request, approval_actor=self._actor_context(),
                                    recorded_at=recorded_at)
        owners = []
        for ident, change in sorted(prepared["changes"].items()):
            before = change.get("before")
            fields = ("graph", "plan", "layouts", "role", "lineage", "lensKey")
            old, new = {}, {}
            for field in fields:
                if field not in change:
                    continue
                new[field] = copy.deepcopy(change[field])
                if before:
                    old[field] = copy.deepcopy(before.get(field) if field in
                        ("graph", "plan", "layouts") else before["head"].get(field))
            owners.append({"packageId": ident, "path": change["path"],
                "before": old if before else None, "after": new,
                "artifacts": [{"path": path, "sha256": hashlib.sha256(raw).hexdigest(),
                               "size": len(raw)}
                              for path, raw in sorted(change.get("artifacts", {}).items())]})
        result.update(inputBinding=self.app.input_binding(request, prepared),
                      effects=copy.deepcopy(prepared["effects"]), owners=owners)
        return result, prepared

    def begin(self, request_id, decision):
        self.check(decision in ("approve", "reject"), "DECISION")
        with self._lock, self.app.store.lock(False, create=False):
            self._actor()
            value = self._pending(request_id)
            recorded_at = datetime.now(timezone.utc).isoformat()
            preview, _ = self._preview(value, recorded_at, decision)
            digest = self.app.model.digest(preview)
            ceremony = self.verifier.begin_decision(self.principal_id, digest, decision)
            self._ceremonies[ceremony["ceremonyId"]] = {
                "requestId": request_id, "decision": decision,
                "recordedAt": recorded_at, "previewSHA256": digest}
            return {**ceremony, "preview": preview, "approvalSHA256": digest}

    def recheck(self, ceremony_id):
        """Check the displayed preview before requesting a browser assertion."""
        with self._lock, self.app.store.lock(False, create=False):
            context = self._ceremonies.get(ceremony_id)
            self.check(context is not None, "CEREMONY_UNAVAILABLE")
            self._actor()
            value = self._pending(context["requestId"])
            preview, _ = self._preview(value, context["recordedAt"], context["decision"])
            self.check(self.app.model.digest(preview) == context["previewSHA256"], "PREVIEW_CHANGED")
            if hasattr(self.verifier, "check_ceremony"):
                self.verifier.check_ceremony(ceremony_id)

    def complete(self, ceremony_id, response, *, failpoint=None, before_accept=None):
        with self._lock:
            context = self._ceremonies.pop(ceremony_id, None)
            self.check(context is not None, "CEREMONY_UNAVAILABLE")
            with self.app.store.lock(True, create=False):
                self._actor()
                value = self._pending(context["requestId"])
                preview, prepared = self._preview(value, context["recordedAt"],
                                                   context["decision"])
                digest = self.app.model.digest(preview)
                self.check(digest == context["previewSHA256"], "PREVIEW_CHANGED")
                # Only this call obtains a proof. A client-supplied proof dict or actor
                # label never substitutes for a verified assertion.
                proof = self.verifier.complete_decision(ceremony_id, response, digest)
                self.check(proof.get("principalId") == self.principal_id and
                    proof.get("decision") == context["decision"] and
                    proof.get("approvalSHA256") == digest and
                    proof.get("userVerified") is True, "VERIFIER_BINDING")
                def final_authorize(checks):
                    credentials = getattr(self.verifier, "credential_store", None)
                    kwargs = ({"assertion_check": lambda data: credentials.check_proof(data, proof)}
                              if credentials is not None else {})
                    return self.app.authority.checked_portable_transaction(self.app.token, checks, **kwargs)
                public_proof = {key: proof[key] for key in
                    ("principalId", "credentialId", "origin", "rpId", "proofSHA256",
                     "userVerified")}
                if context["decision"] == "reject":
                    decision = {"schemaVersion": 1, "kind": "rdgApprovalDecision",
                        "requestId": value["requestId"], "requestSHA256": value["requestSHA256"],
                        "state": "rejected", "previewSHA256": digest,
                        "initiator": value["initiator"], "approver": public_proof,
                        "recordedAt": datetime.now(timezone.utc).isoformat()}
                    # Fresh read authorization is held through durable rejection.
                    checks = []
                    if value["targetPackageId"] is not None:
                        row = self.app.metadata(value["targetPackageId"], ["graph.read"])
                        checks = [{"namespaceId": value["namespaceId"],
                                   "packageId": value["targetPackageId"], "path": row["path"],
                                   "permissions": ["graph.read"]}]
                    with final_authorize(checks):
                        self.app.store.io.immutable_bytes(self.app.store.metadata_path(
                            "approval-decisions", value["requestId"]), self.app.store.encode(decision))
                    return self.app.approval_view(value)
                authorization = {"schemaVersion": 1, "kind": "rdgExactApproval",
                    "namespaceId": value["namespaceId"], "requestId": value["requestId"],
                    "requestSHA256": value["requestSHA256"],
                    "initiator": {**value["initiator"],
                                  "tokenSHA256": value["actorTokenSHA256"]},
                    "approver": public_proof,
                    "executor": {"grantId": self.executor_grant_id,
                        "tokenSHA256": hashlib.sha256(self.app.token.encode()).hexdigest(),
                        "authorityPrincipal": self.authority_principal},
                    "previewSHA256": digest,
                    "inputBindingSHA256": preview["inputBinding"]["sha256"]}
                if before_accept:
                    before_accept()
                def preauthorize():
                    self._actor()
                    for check in prepared["checks"]:
                        self.app.authorize(check["packageId"], check["permissions"], check["path"])
                return self.app.store.commit(value["requestId"], value["requestSHA256"],
                    prepared["changes"], authorization["executor"]["tokenSHA256"],
                    preauthorize,
                    lambda: final_authorize(prepared["checks"]), prepared["readset"], failpoint,
                    expected_catalog=prepared["catalog"], authorization_context=authorization)
