#!/usr/bin/env python3
"""Opt-in Viewer transport for an already configured trusted approval executor.

The host supplies enrollment, credentials, grant/key mapping and token isolation.
No client message can choose an actor or create a grant. Optional enrollment is
restricted to an owner-issued, one-use permit injected by trusted host code.
"""
import copy
import hashlib
import json
import secrets
import threading
import time


class ApprovalSurface:
    def __init__(self, executor, *, clock=time.monotonic, enrollment_permit=None):
        self.executor, self.app = executor, executor.app
        self._clock, self._lock = clock, threading.RLock()
        self._views, self._ceremonies = {}, {}
        self._enrollment_permit, self._registration = enrollment_permit, None

    @staticmethod
    def check(ok, code):
        if not ok:
            raise ValueError("RDG_APPROVAL_SURFACE_" + code)

    def _record(self, request_id):
        value = self.app.approval_record(request_id)
        accepted = self.app.store.metadata_path("accepted", request_id)
        own_accepted = False
        if accepted.is_file():
            certificate = json.loads(accepted.read_bytes())
            own_accepted = (certificate.get("schemaVersion") == 2 and
                certificate["authorizationContext"]["approver"]["principalId"] == self.executor.principal_id and
                certificate["authorizationContext"]["executor"]["grantId"] == self.executor.executor_grant_id and
                self.app.store.transaction_actor(certificate, hashlib.sha256(self.app.token.encode()).hexdigest()))
        if not own_accepted:
            self.executor._actor()
            if value["targetPackageId"] is not None:
                self.app.metadata(value["targetPackageId"], ["graph.read"])
            else:
                self.check(value["request"].get("op") in ("create", "copy"), "TARGETLESS_OPERATION")
        return value

    def status(self, request_id):
        with self.app.store.lock(False, create=False):
            return self.app.approval_view(self._record(request_id))

    def list_requests(self):
        self.executor._actor()
        rows = []
        with self.app.store.lock(False, create=False):
            directory = self.app.store.path(".rdg/approval-requests", True)
            for path in sorted(directory.glob("*.json")):
                try:
                    value = self._record(path.stem)
                except ValueError as exc:
                    if str(exc) == "AUTH_PORTABLE_SCOPE_DENIED" or str(exc).startswith("AUTH_MISSING_PERMISSION: "):
                        continue
                    raise
                public = self.app.approval_view(value)
                rows.append({key: copy.deepcopy(public[key]) for key in
                    ("requestId", "state", "targetPackageId", "initiator", "rationale",
                     "createdAt", "request")})
        return {"requests": rows, "namespaceId": self.app.store.namespace_id,
                "enrollment": self.enrollment_info()}

    def enrollment_info(self):
        if self._enrollment_permit is None:
            return None
        credentials = getattr(self.executor.verifier, "credential_store", None)
        self.check(credentials is not None, "ENROLLMENT_PERSISTENCE_REQUIRED")
        info = credentials.enrollment_info(self._enrollment_permit, self.executor.principal_id,
                                           self.executor.verifier.rp_id, self.executor.verifier.origin)
        if info['state'] == 'started' and self._registration is None:
            info['state'] = 'interrupted'
        return info

    def registration_begin(self):
        self.executor._actor()
        info = self.enrollment_info()
        self.check(info is not None and info["state"] in ("issued", "started"), "ENROLLMENT_NOT_ENABLED")
        if self._registration is None:
            self._registration = self.executor.verifier.begin_registration(
                self.executor.principal_id, info["displayName"],
                enrollment_permit=self._enrollment_permit)
        return copy.deepcopy(self._registration)

    def registration_complete(self, ceremony_id, response):
        self.check(self._registration is not None and
                   self._registration["ceremonyId"] == ceremony_id, "ENROLLMENT_NOT_ENABLED")
        self._registration = None
        return self.executor.verifier.complete_registration(ceremony_id, response)

    def open_request(self, request_id):
        with self.app.store.lock(False, create=False):
            value = self._record(request_id)
            state = self.app.approval_view(value)
        # begin() acquires and holds its own reference barrier. Nesting two
        # shared handles self-conflicts with Windows preview exclusive locks.
        result = {"record": state, "previewAvailable": False, "preview": None}
        if state["state"] != "pending":
            return result
        begun, blocker = None, None
        try:
            begun = self.executor.begin(request_id, "approve")
        except ValueError as exc:
            blocker = str(exc)
        view_id = secrets.token_urlsafe(32)
        # Views are temporary capabilities. Eviction never accepts a request.
        if len(self._views) >= 128:
            self._views.pop(next(iter(self._views)))
        self._views[view_id] = {"requestId": request_id,
            "pendingSHA256": self.app.model.digest(value),
            "begun": begun, "expires": self._clock() + 120}
        result.update(viewId=view_id, previewAvailable=begun is not None,
                      preview=copy.deepcopy(begun["preview"]) if begun else None,
                      blocker=blocker)
        return result

    def choose(self, view_id, decision):
        self.check(decision in ("approve", "reject"), "DECISION")
        context = self._views.get(view_id)
        self.check(context is not None and self._clock() < context["expires"], "VIEW_UNAVAILABLE")
        with self.app.store.lock(False, create=False):
            value = self._record(context["requestId"])
            self.check(self.app.model.digest(value) == context["pendingSHA256"], "REQUEST_CHANGED")
        if decision == "approve":
            begun = context["begun"]
            self.check(begun is not None, "PREVIEW_UNAVAILABLE")
            self.executor.recheck(begun["ceremonyId"])
        else:
            begun = self.executor.begin(context["requestId"], "reject")
        self._ceremonies[begun["ceremonyId"]] = {"requestId": context["requestId"], "viewId": view_id}
        return {key: copy.deepcopy(begun[key]) for key in ("ceremonyId", "options")}

    def complete(self, ceremony_id, response):
        context = self._ceremonies.pop(ceremony_id, None)
        self.check(context is not None, "CEREMONY_UNAVAILABLE")
        self._views.pop(context["viewId"], None)
        try:
            return self.executor.complete(ceremony_id, response)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            if self.app.store.metadata_path("accepted", context["requestId"]).is_file():
                raise ValueError("WRITER_OUTCOME_UNCONFIRMED: inspect approval status before recovery") from exc
            raise

    def recover(self, request_id):
        with self.app.store.lock(False, create=False):
            path = self.app.store.metadata_path("accepted", request_id)
            self.check(path.is_file(), "ACCEPTED_REQUIRED")
            certificate = json.loads(path.read_bytes())
            self.check(certificate.get("schemaVersion") == 2 and
                certificate["authorizationContext"]["approver"]["principalId"] == self.executor.principal_id and
                certificate["authorizationContext"]["executor"]["grantId"] == self.executor.executor_grant_id,
                "ACCEPTED_BINDING")
        return self.app.recover(request_id)

    def dispatch(self, message):
        fields = {"list": set(), "open": {"requestId"}, "status": {"requestId"},
                  "choose": {"viewId", "decision"}, "complete": {"ceremonyId", "response"},
                  "recover": {"requestId"}, "registration_begin": set(),
                  "registration_complete": {"ceremonyId", "response"}}
        self.check(isinstance(message, dict) and message.get("method") in fields and
                   set(message) == {"method"} | fields[message["method"]], "MESSAGE_FIELDS")
        with self._lock:
            method = message["method"]
            if method == "list":
                return self.list_requests()
            if method == "registration_begin":
                return self.registration_begin()
            if method == "registration_complete":
                return self.registration_complete(message["ceremonyId"], message["response"])
            if method == "open":
                return self.open_request(message["requestId"])
            if method == "status":
                return self.status(message["requestId"])
            if method == "choose":
                return self.choose(message["viewId"], message["decision"])
            if method == "complete":
                return self.complete(message["ceremonyId"], message["response"])
            return self.recover(message["requestId"])
