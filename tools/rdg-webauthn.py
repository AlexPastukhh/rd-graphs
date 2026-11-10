#!/usr/bin/env python3
"""WebAuthn ceremony verification, independent of Graph execution.

The caller owns trusted enrollment, credential storage, grant mapping and the
current approval digest. None of those values may come from an untrusted client.
This module does not authorize Graph writes or prove deployment isolation.
"""
import base64
import hashlib
import json
import re
import secrets
import threading
import time
from urllib.parse import urlsplit


def require(ok, code):
    if not ok:
        raise ValueError("RDG_WEBAUTHN_" + code)


class Verifier:
    def __init__(self, rp_id, origin, *, ttl=120, clock=time.monotonic, credential_store=None):
        from fido2.server import Fido2Server
        from fido2.webauthn import PublicKeyCredentialRpEntity
        parsed = urlsplit(origin)
        require(parsed.scheme in ("http", "https") and parsed.hostname == rp_id
                and not parsed.username and not parsed.password and
                not parsed.path and not parsed.query and not parsed.fragment,
                "ORIGIN_CONFIGURATION")
        require(parsed.scheme == "https" or rp_id == "localhost",
                "SECURE_ORIGIN_REQUIRED")
        require(type(ttl) in (int, float) and 0 < ttl <= 300, "TTL")
        self.origin, self.rp_id = origin, rp_id
        self.credential_store = credential_store
        self._clock, self._ttl = clock, ttl
        self._lock = threading.RLock()
        self._pending, self._credentials = {}, {}
        self._server = Fido2Server(
            PublicKeyCredentialRpEntity(id=rp_id, name="RDG"),
            verify_origin=lambda value: value == origin)
        self._server.timeout = 60000

    def _remember(self, purpose, state, **context):
        ceremony = secrets.token_urlsafe(32)
        self._pending[ceremony] = {"purpose": purpose, "state": state,
            "expires": self._clock() + self._ttl, **context}
        return ceremony

    def _take(self, ceremony, purpose):
        require(isinstance(ceremony, str), "CEREMONY_UNAVAILABLE")
        context = self._pending.pop(ceremony, None)
        require(context is not None and self._clock() < context["expires"],
                "CEREMONY_UNAVAILABLE")
        require(context["purpose"] == purpose, "CEREMONY_KIND")
        return context

    @staticmethod
    def _top_level(parsed):
        data = json.loads(parsed.response.client_data)
        require(data.get("crossOrigin", False) is False and "topOrigin" not in data,
                "CROSS_ORIGIN_DENIED")

    @staticmethod
    def _user_id(principal):
        require(isinstance(principal, str) and bool(principal.strip()), "PRINCIPAL")
        return hashlib.sha256(("rdg-user:" + principal).encode()).digest()

    def _digest(self, value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                         allow_nan=False).encode()).hexdigest()

    def _refresh_credentials(self, principal):
        if self.credential_store is None:
            return None
        import base64
        from fido2.webauthn import AttestedCredentialData
        binding, rows = self.credential_store.credentials(principal, self.rp_id, self.origin)
        self._credentials = {ident: {"principal": row["principalId"],
            "user_id": base64.b64decode(row["userId"], validate=True),
            "credential": AttestedCredentialData(base64.b64decode(row["credentialData"], validate=True)),
            "counter": row["counter"], "revision": row["revision"]}
            for ident, row in rows.items()}
        return self._digest(binding)

    def validate_binding(self, principal, namespace_id, grant_id, authority_principal):
        if self.credential_store is not None:
            value = self.credential_store.binding(principal, self.rp_id, self.origin)
            require(value["namespaceId"] == namespace_id and
                    value["executorGrantId"] == grant_id and
                    value["authorityPrincipal"] == authority_principal, "EXECUTOR_BINDING")
            return self._digest(value)
        return None

    def check_ceremony(self, ceremony):
        with self._lock:
            context = self._pending.get(ceremony)
            require(context is not None and self._clock() < context["expires"], "CEREMONY_UNAVAILABLE")
            binding_sha = self._refresh_credentials(context["principal"])
            require(binding_sha == context.get("bindingSHA256"), "BINDING_CHANGED")
            require(any(ident in self._credentials for ident in context["credentialIds"]),
                    "PRINCIPAL_NOT_ENROLLED")

    def begin_registration(self, principal, display_name, *, enrollment_permit=None):
        """Trusted operator call; this is not a public self-enrollment endpoint."""
        from fido2.webauthn import PublicKeyCredentialUserEntity, UserVerificationRequirement
        user_id = self._user_id(principal)
        require(isinstance(display_name, str) and bool(display_name.strip()), "DISPLAY_NAME")
        with self._lock:
            if self.credential_store is not None:
                require(enrollment_permit is not None, 'ENROLLMENT_PERMIT_REQUIRED')
                self._refresh_credentials(principal)
            options, state = self._server.register_begin(
                PublicKeyCredentialUserEntity(id=user_id, name=principal,
                                              display_name=display_name),
                credentials=[row["credential"] for row in self._credentials.values()],
                user_verification=UserVerificationRequirement.REQUIRED)
            ceremony = self._remember("register", state, principal=principal, user_id=user_id,
                                      enrollment_permit=enrollment_permit)
            if self.credential_store is not None:
                try:
                    self.credential_store.reserve_enrollment(enrollment_permit, principal,
                                                             self.rp_id, self.origin, ceremony)
                except (ValueError, OSError, KeyError, TypeError):
                    self._pending.pop(ceremony, None)
                    raise
            return {"ceremonyId": ceremony, "options": dict(options)}

    def complete_registration(self, ceremony, response):
        from fido2.webauthn import RegistrationResponse
        from fido2.utils import websafe_encode
        with self._lock:
            context = self._take(ceremony, "register")
            try:
                parsed = RegistrationResponse.from_dict(response)
                self._top_level(parsed)
                data = self._server.register_complete(context["state"], parsed)
            except (ValueError, TypeError, KeyError) as exc:
                if self.credential_store is not None:
                    self.credential_store.fail_enrollment(context["enrollment_permit"], ceremony)
                raise ValueError("RDG_WEBAUTHN_REGISTRATION_INVALID") from exc
            credential = data.credential_data
            require(credential is not None and parsed.raw_id == credential.credential_id,
                    "REGISTRATION_CREDENTIAL_ID")
            ident = websafe_encode(credential.credential_id)
            require(ident not in self._credentials, "CREDENTIAL_ALREADY_REGISTERED")
            if self.credential_store is not None:
                self.credential_store.register(context["enrollment_permit"], context["principal"],
                    self.rp_id, self.origin, ceremony, ident, bytes(credential), context["user_id"],
                    data.counter, dict(parsed))
            self._credentials[ident] = {"principal": context["principal"],
                "user_id": context["user_id"], "credential": credential,
                "counter": data.counter}
            return {"credentialId": ident, "principalId": context["principal"],
                    "userVerified": data.is_user_verified(),
                    "attestationModelVerified": False}

    def begin_decision(self, principal, approval_digest, decision):
        from fido2.webauthn import UserVerificationRequirement
        require(isinstance(approval_digest, str) and
                re.fullmatch("[0-9a-f]{64}", approval_digest), "APPROVAL_DIGEST")
        require(decision in ("approve", "reject"), "DECISION")
        with self._lock:
            binding_sha = self._refresh_credentials(principal)
            credentials = [row["credential"] for row in self._credentials.values()
                           if row["principal"] == principal]
            require(bool(credentials), "PRINCIPAL_NOT_ENROLLED")
            binding_context = {"principal": principal, "approval": approval_digest, "decision": decision}
            if binding_sha is not None:
                binding_context["credentialBindingSHA256"] = binding_sha
            binding = json.dumps(binding_context, sort_keys=True, separators=(",", ":")).encode()
            challenge_nonce = secrets.token_bytes(32)
            challenge = hashlib.sha256(b"rdg-approval-v1\0" + challenge_nonce + binding).digest()
            options, state = self._server.authenticate_begin(
                credentials, user_verification=UserVerificationRequirement.REQUIRED,
                challenge=challenge)
            ceremony = self._remember("decision", state, principal=principal,
                                      approval=approval_digest, decision=decision,
                                      bindingSHA256=binding_sha,
                                      challengeNonce=base64.urlsafe_b64encode(challenge_nonce).decode(),
                                      credentialIds=[ident for ident, row in self._credentials.items()
                                                     if row["principal"] == principal])
            return {"ceremonyId": ceremony, "options": dict(options)}

    def complete_decision(self, ceremony, response, current_approval_digest):
        """The digest is recomputed by the trusted planner, never echoed by a client."""
        from fido2.webauthn import AuthenticationResponse
        from fido2.utils import websafe_encode
        with self._lock:
            context = self._take(ceremony, "decision")
            require(context["approval"] == current_approval_digest, "PREVIEW_CHANGED")
            binding_sha = self._refresh_credentials(context["principal"])
            require(binding_sha == context.get("bindingSHA256"), "BINDING_CHANGED")
            credentials = [row["credential"] for row in self._credentials.values()
                           if row["principal"] == context["principal"]]
            try:
                parsed = AuthenticationResponse.from_dict(response)
                self._top_level(parsed)
                credential = self._server.authenticate_complete(
                    context["state"], credentials, parsed)
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError("RDG_WEBAUTHN_ASSERTION_INVALID") from exc
            ident = websafe_encode(credential.credential_id)
            row = self._credentials[ident]
            handle = parsed.response.user_handle
            require(handle is None or handle == row["user_id"], "USER_HANDLE_MISMATCH")
            counter = parsed.response.authenticator_data.counter
            require(not (counter or row["counter"]) or counter > row["counter"],
                    "COUNTER_NOT_INCREASING")
            row["counter"] = counter
            encoded = json.dumps(dict(parsed), sort_keys=True,
                                 separators=(",", ":")).encode()
            proof = {"schemaVersion": 1, "credentialId": ident,
                    "principalId": row["principal"], "decision": context["decision"],
                    "approvalSHA256": context["approval"], "origin": self.origin,
                    "rpId": self.rp_id, "userVerified": True,
                    "proofSHA256": hashlib.sha256(encoded).hexdigest(),
                    "graphExecutionAuthorized": False}
            if self.credential_store is not None:
                proof["bindingSHA256"] = binding_sha
                proof["challengeNonce"] = context["challengeNonce"]
                self.credential_store.record_proof(proof, dict(parsed), binding_sha,
                                                    row["revision"], counter)
            return proof
