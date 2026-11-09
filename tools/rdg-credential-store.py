#!/usr/bin/env python3
"""Opt-in WebAuthn state in the existing Authority owner.

Administrative methods require the existing owner bearer. Runtime methods use
one-use enrollment permits or a cryptographically verified assertion. This is an
API boundary, not an OS sandbox: Authority and active code still need protection
from the ordinary Agent. No grants, private authenticator keys or new scopes are
created here.
"""
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import time
import uuid
from urllib.parse import urlsplit


def require(ok, code):
    if not ok:
        raise ValueError("RDG_CREDENTIAL_" + code)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class CredentialStore:
    def __init__(self, authority, *, clock=time.time):
        self.authority, self.path, self._clock = authority, authority.path, clock
        require(self.path.is_absolute() and
                not self.path.resolve().is_relative_to(Path(__file__).resolve().parents[1]) and
                not any(path.is_symlink() for path in (self.path, *self.path.parents)),
                'AUTHORITY_OUTSIDE_CODE_REQUIRED')

    def _state(self, data, create=False):
        if "webauthn" not in data:
            require(create, "STORE_NOT_CONFIGURED")
            data["webauthn"] = {"schemaVersion": 1, "revision": 0, "bindings": {},
                               "credentials": {}, "enrollments": {}, "proofs": {}}
        state = data["webauthn"]
        require(isinstance(state, dict) and set(state) == {
            "schemaVersion", "revision", "bindings", "credentials", "enrollments", "proofs"} and
            state["schemaVersion"] == 1 and type(state["revision"]) is int and
            all(isinstance(state[key], dict) for key in
                ("bindings", "credentials", "enrollments", "proofs")), "STORE_INVALID")
        return state

    def _owner(self, data, token):
        ident, actor = self.authority._actor(data, token)
        require(actor.get("owner") is True and "grant.admin" in actor["permissions"],
                "OWNER_REQUIRED")
        return ident

    def _save(self, data):
        self._state(data)["revision"] += 1
        # Grant revision belongs to grants. Credential counters do not amend grants.
        self.authority._save(data)

    def _binding(self, data, principal, rp_id=None, origin=None):
        state = self._state(data)
        value = state["bindings"].get(principal)
        require(value is not None and value["active"], "BINDING_UNAVAILABLE")
        require(rp_id is None or value["rpId"] == rp_id, "RP_BINDING")
        require(origin is None or value["origin"] == origin, "ORIGIN_BINDING")
        grant = data["grants"].get(value["executorGrantId"])
        require(grant is not None and grant["active"], "EXECUTOR_GRANT_UNAVAILABLE")
        return value

    def binding(self, principal, rp_id=None, origin=None):
        return copy.deepcopy(self._binding(self.authority._read(), principal, rp_id, origin))

    def configure_binding(self, operator_token, spec, *, expected_revision):
        names = {"principalId", "displayName", "namespaceId", "executorGrantId",
                 "authorityPrincipal", "rpId", "origin", "active"}
        require(isinstance(spec, dict) and set(spec) == names and type(spec["active"]) is bool
                and all(isinstance(spec[k], str) and spec[k].strip() for k in names - {"active"}),
                "BINDING_SPEC")
        require(str(uuid.UUID(spec["namespaceId"])) == spec["namespaceId"], "NAMESPACE")
        parsed = urlsplit(spec["origin"])
        require(parsed.hostname == spec["rpId"] and not parsed.username and not parsed.password and
                not parsed.path and not parsed.query and not parsed.fragment and
                (parsed.scheme == "https" or parsed.scheme == "http" and spec["rpId"] == "localhost"),
                "ORIGIN")
        with self.authority.locked_store() as data:
            operator = self._owner(data, operator_token)
            state = self._state(data, True)
            grant = data["grants"].get(spec["executorGrantId"])
            require(grant is not None and (not spec["active"] or grant["active"]), "EXECUTOR_GRANT_UNAVAILABLE")
            require(not spec["active"] or any(scope.startswith(("packages/" + spec["namespaceId"] + "/",
                                          "package-paths/" + spec["namespaceId"] + "/"))
                        for scope in grant["scopes"]), "EXECUTOR_NAMESPACE")
            old = state["bindings"].get(spec["principalId"])
            require(expected_revision == (old["revision"] if old else 0), "BINDING_CAS")
            if old and all(old[k] == spec[k] for k in names):
                return copy.deepcopy(old)
            value = {**copy.deepcopy(spec), "revision": expected_revision + 1,
                     "configuredBy": operator, "configuredAt": now_iso()}
            state["bindings"][spec["principalId"]] = value
            self._save(data)
            return copy.deepcopy(value)

    def issue_enrollment(self, operator_token, principal, *, ttl=120):
        require(type(ttl) in (int, float) and 0 < ttl <= 300, "TTL")
        with self.authority.locked_store() as data:
            operator = self._owner(data, operator_token)
            binding = self._binding(data, principal)
            permit = secrets.token_urlsafe(32)
            self._state(data)["enrollments"][digest(permit)] = {
                "state": "issued", "principalId": principal,
                "bindingSHA256": digest(binding), "issuedBy": operator,
                "issuedAt": now_iso(), "expires": self._clock() + ttl}
            self._save(data)
            return permit

    def _permit(self, data, permit, principal, rp_id, origin):
        require(isinstance(permit, str) and len(permit) >= 32, "ENROLLMENT_PERMIT_REQUIRED")
        row = self._state(data)["enrollments"].get(digest(permit))
        require(row is not None and self._clock() < row["expires"] and
                row["principalId"] == principal, "ENROLLMENT_UNAVAILABLE")
        binding = self._binding(data, principal, rp_id, origin)
        require(row["bindingSHA256"] == digest(binding), "ENROLLMENT_BINDING_CHANGED")
        return row

    def reserve_enrollment(self, permit, principal, rp_id, origin, ceremony):
        with self.authority.locked_store() as data:
            row = self._permit(data, permit, principal, rp_id, origin)
            require(row["state"] == "issued", "ENROLLMENT_ALREADY_STARTED")
            row.update(state="started", ceremonyId=ceremony)
            self._save(data)

    def fail_enrollment(self, permit, ceremony):
        with self.authority.locked_store() as data:
            row = self._state(data)["enrollments"].get(digest(permit))
            if row and row["state"] == "started" and row["ceremonyId"] == ceremony:
                row.update(state="failed", failedAt=now_iso())
                self._save(data)

    def register(self, permit, principal, rp_id, origin, ceremony, credential_id,
                 credential_data, user_id, counter, response):
        with self.authority.locked_store() as data:
            row = self._permit(data, permit, principal, rp_id, origin)
            require(row["state"] == "started" and row["ceremonyId"] == ceremony,
                    "ENROLLMENT_UNAVAILABLE")
            state = self._state(data)
            require(credential_id not in state["credentials"], "CREDENTIAL_EXISTS")
            require(type(counter) is int and 0 <= counter <= 0xffffffff, "COUNTER")
            state["credentials"][credential_id] = {
                "principalId": principal, "credentialData": base64.b64encode(credential_data).decode(),
                "userId": base64.b64encode(user_id).decode(), "counter": counter,
                "active": True, "revision": 1, "registeredAt": now_iso(),
                "registrationBindingSHA256": row["bindingSHA256"],
                "registrationEvidence": copy.deepcopy(response)}
            row.update(state="completed", credentialId=credential_id, completedAt=now_iso())
            self._save(data)

    def credentials(self, principal, rp_id, origin):
        data = self.authority._read()
        binding = self._binding(data, principal, rp_id, origin)
        rows = {key: copy.deepcopy(value) for key, value in self._state(data)["credentials"].items()
                if value["principalId"] == principal and value["active"]}
        return copy.deepcopy(binding), rows

    def revoke_credential(self, operator_token, credential_id, *, expected_revision):
        with self.authority.locked_store() as data:
            self._owner(data, operator_token)
            row = self._state(data)["credentials"].get(credential_id)
            require(row is not None, "CREDENTIAL_UNKNOWN")
            require(row["revision"] == expected_revision, "CREDENTIAL_CAS")
            if row["active"]:
                row.update(active=False, revision=row["revision"] + 1, revokedAt=now_iso())
                self._save(data)
            return {"credentialId": credential_id, "active": row["active"],
                    "revision": row["revision"]}

    def enrollment_info(self, permit, principal, rp_id, origin):
        data = self.authority._read()
        state = self._state(data)
        row = state["enrollments"].get(digest(permit))
        require(row is not None and row["principalId"] == principal, "ENROLLMENT_UNAVAILABLE")
        binding = self._binding(data, principal, rp_id, origin)
        status = row["state"]
        if status == "completed":
            credential = state["credentials"].get(row["credentialId"])
            if credential is None or not credential["active"]:
                status = "revoked"
        elif row["bindingSHA256"] != digest(binding):
            status = "invalidated"
        elif self._clock() >= row["expires"]:
            status = "expired"
        return {"state": status, "principalId": principal,
                "displayName": binding["displayName"], "executorGrantId": binding["executorGrantId"],
                "rpId": rp_id, "origin": origin}

    def inspect(self, operator_token):
        data = self.authority._read()
        self._owner(data, operator_token)
        if "webauthn" not in data:
            return {"configured": False, "grantRevision": data["revision"]}
        state = self._state(data)
        return {"configured": True, "grantRevision": data["revision"],
                "credentialRevision": state["revision"],
                "bindings": copy.deepcopy(list(state["bindings"].values())),
                "credentials": [{"credentialId": ident, **{k: row[k] for k in
                    ("principalId", "active", "revision", "counter")}}
                    for ident, row in state["credentials"].items()],
                "enrollmentStates": [row["state"] for row in state["enrollments"].values()],
                "proofCount": len(state["proofs"])}

    def audit_proof(self, operator_token, proof_sha):
        """Recheck saved public evidence; this does not authorize a new action."""
        from fido2.webauthn import AttestedCredentialData, AuthenticationResponse
        from fido2.utils import websafe_encode
        data = self.authority._read()
        self._owner(data, operator_token)
        evidence = self._state(data)["proofs"].get(proof_sha)
        require(evidence is not None, "PROOF_UNAVAILABLE")
        receipt = evidence["receipt"]
        parsed = AuthenticationResponse.from_dict(evidence["response"])
        key = AttestedCredentialData(base64.b64decode(evidence["credentialData"], validate=True))
        binding = evidence["binding"]
        nonce = base64.urlsafe_b64decode(receipt["challengeNonce"])
        context = {"principal": receipt["principalId"], "approval": receipt["approvalSHA256"],
                   "decision": receipt["decision"],
                   "credentialBindingSHA256": receipt["bindingSHA256"]}
        challenge = hashlib.sha256(b"rdg-approval-v1\0" + nonce + encoded(context)).digest()
        client = json.loads(parsed.response.client_data)
        auth = parsed.response.authenticator_data
        require(len(nonce) == 32 and receipt["rpId"] == binding["rpId"] and
                receipt["userVerified"] is True and auth.counter == evidence["counter"] and
                (parsed.response.user_handle is None or parsed.response.user_handle ==
                 hashlib.sha256(("rdg-user:" + receipt["principalId"]).encode()).digest()) and
                digest(evidence["response"]) == proof_sha and
                websafe_encode(key.credential_id) == receipt["credentialId"] and
                parsed.raw_id == key.credential_id and
                client["type"] == "webauthn.get" and
                client["challenge"] == websafe_encode(challenge) and
                client["origin"] == receipt["origin"] == binding["origin"] and
                client.get("crossOrigin", False) is False and "topOrigin" not in client and
                auth.rp_id_hash == hashlib.sha256(binding["rpId"].encode()).digest() and
                auth.is_user_present() and auth.is_user_verified() and
                digest(binding) == receipt["bindingSHA256"], "AUDIT_CONTEXT")
        key.public_key.verify(bytes(auth) + parsed.response.client_data.hash,
                              parsed.response.signature)
        current = self._state(data)["credentials"].get(receipt["credentialId"])
        return {"signatureVerified": True, "proofSHA256": proof_sha,
                "approvalSHA256": receipt["approvalSHA256"], "decision": receipt["decision"],
                "principalId": receipt["principalId"], "origin": receipt["origin"],
                "bindingRevision": binding["revision"],
                "credentialCurrentlyActive": bool(current and current["active"]),
                "authorizesNewExecution": False}

    def record_proof(self, proof, response, binding_sha, credential_revision, counter):
        with self.authority.locked_store() as data:
            state = self._state(data)
            binding = self._binding(data, proof["principalId"], proof["rpId"], proof["origin"])
            require(digest(binding) == binding_sha, "BINDING_CHANGED")
            row = state["credentials"].get(proof["credentialId"])
            require(row is not None and row["active"] and row["principalId"] == proof["principalId"] and
                    row["revision"] == credential_revision, "CREDENTIAL_UNAVAILABLE")
            require(not (counter or row["counter"]) or counter > row["counter"],
                    "COUNTER_NOT_INCREASING")
            require(digest(response) == proof["proofSHA256"], "PROOF_DIGEST")
            require(proof["proofSHA256"] not in state["proofs"], "PROOF_REPLAY")
            row["counter"] = counter
            state["proofs"][proof["proofSHA256"]] = {
                "receipt": copy.deepcopy(proof), "response": copy.deepcopy(response),
                "binding": copy.deepcopy(binding), "credentialData": row["credentialData"],
                "credentialRevision": row["revision"], "counter": counter, "verifiedAt": now_iso()}
            self._save(data)

    def check_proof(self, data, proof):
        """Called under the same Authority lock as final writer authorization."""
        state = self._state(data)
        evidence = state["proofs"].get(proof["proofSHA256"])
        require(evidence is not None and evidence["receipt"] == proof, "PROOF_UNAVAILABLE")
        binding = self._binding(data, proof["principalId"], proof["rpId"], proof["origin"])
        require(digest(binding) == digest(evidence["binding"]), "BINDING_CHANGED")
        row = state["credentials"].get(proof["credentialId"])
        require(row is not None and row["active"] and
                row["revision"] == evidence["credentialRevision"] and
                row["credentialData"] == evidence["credentialData"], "CREDENTIAL_UNAVAILABLE")
        require(row["counter"] >= evidence["counter"], "COUNTER_ROLLBACK")
