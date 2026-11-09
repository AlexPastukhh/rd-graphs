"""Standalone owner WebAuthn for G2; does not import RDG or expose admin APIs.

Requires fido2>=2.2. Operator issues a short-lived enrollment invitation OUTSIDE
HTTP. Real browsers perform UV-required FIDO2 registration/login/each decision.
The owner store, origins and policy belong to a trusted deployment, not Repo AI.
"""
import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit

from .core import Denied, canonical


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _user_id(owner):
    return hashlib.sha256(('fortis-owner:' + owner).encode()).digest()


class OwnerWebAuthn:
    def __init__(self, database, *, origin, owner='owner', clock=None, session_seconds=43200):
        from fido2.server import Fido2Server
        from fido2.webauthn import PublicKeyCredentialRpEntity
        parsed = urlsplit(origin)
        if (parsed.scheme not in ('https', 'http') or not parsed.hostname or
            (parsed.scheme == 'http' and parsed.hostname != 'localhost') or
            parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or
            origin != f'{parsed.scheme}://{parsed.netloc}'):
            raise ValueError('OWNER_SECURE_ORIGIN_REQUIRED')
        self.origin, self.owner, self.rp_id = origin, owner, parsed.hostname
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise Denied('OWNER_STORE_SYMLINK')
        if not self.path.exists():
            os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        if self.path.stat().st_mode & 0o077:
            raise Denied('OWNER_STORE_PERMISSIONS')
        if type(session_seconds) is not int or not 600 <= session_seconds <= 86400:
            raise ValueError('SESSION_TTL_INVALID')
        self.session_ttl = session_seconds
        self.clock = clock or time.time
        self.lock = threading.RLock()
        self.pending = {}  # ephemeral challenges: fail closed on restart
        self.sessions = {}  # ephemeral browser sessions: fail closed on restart
        self.session_decisions = {}  # one-use, bound to exact request + session
        self.server = Fido2Server(PublicKeyCredentialRpEntity(id=self.rp_id, name='Fortis Approvals'),
                                  verify_origin=lambda value: value == self.origin)
        self.server.timeout = 60000
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS config (
                    setting TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS invitations (
                    digest TEXT PRIMARY KEY, expiry REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS credentials (
                    id TEXT PRIMARY KEY, data BLOB NOT NULL, counter INTEGER NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1);
            ''')
            for setting, value in [('origin', self.origin), ('rpId', self.rp_id),
                                   ('owner', self.owner)]:
                old = db.execute('SELECT value FROM config WHERE setting=?', (setting,)).fetchone()
                if old is None:
                    db.execute('INSERT INTO config(setting,value) VALUES(?,?)', (setting, value))
                elif old['value'] != value:
                    raise Denied('OWNER_BINDING_CHANGED')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def issue_invitation(self):
        """Operator-local provisioning only. NEVER expose via WSGI/AI API."""
        token = secrets.token_urlsafe(32)
        with self._db() as db:
            db.execute('INSERT INTO invitations(digest,expiry) VALUES(?,?)',
                       (_hash(token), self.clock() + 300))
        return token

    def _credentials(self, db):
        from fido2.webauthn import AttestedCredentialData
        from fido2.utils import websafe_encode
        rows = db.execute('SELECT * FROM credentials WHERE active=1').fetchall()
        return {row['id']: (AttestedCredentialData(row['data']), row['counter']) for row in rows}

    def _remember(self, kind, state, **data):
        # Anonymous login/enrollment starts must not accumulate unbounded state.
        self.pending = {key: row for key, row in self.pending.items()
                        if row[0] > self.clock()}
        if len(self.pending) >= 128:
            raise Denied('CEREMONY_CAPACITY')
        ceremony = secrets.token_urlsafe(32)
        self.pending[ceremony] = (self.clock() + 120, kind, state, data)
        return ceremony

    def _take(self, ceremony, kind):
        if not isinstance(ceremony, str):
            raise Denied('CEREMONY_UNAVAILABLE')
        context = self.pending.pop(ceremony, None)
        if context is None or context[0] <= self.clock() or context[1] != kind:
            raise Denied('CEREMONY_UNAVAILABLE')
        return context[2], context[3]

    @staticmethod
    def _parse(response, kind):
        from fido2.webauthn import AuthenticationResponse, RegistrationResponse
        if not isinstance(response, dict):
            raise Denied('WEBAUTHN_RESPONSE_INVALID')
        try:
            parsed = (RegistrationResponse if kind == 'registration' else
                      AuthenticationResponse).from_dict(response)
            client = json.loads(parsed.response.client_data)
            if client.get('crossOrigin', False) is not False or 'topOrigin' in client:
                raise ValueError('cross-origin')
            return parsed
        except (ValueError, TypeError, KeyError):
            raise Denied('WEBAUTHN_RESPONSE_INVALID') from None

    def begin_enrollment(self, invite):
        from fido2.webauthn import PublicKeyCredentialUserEntity, UserVerificationRequirement
        if not isinstance(invite, str) or len(invite) < 32:
            raise Denied('INVITATION_REQUIRED')
        with self.lock, self._db() as db:
            row = db.execute('SELECT * FROM invitations WHERE digest=?', (_hash(invite),)).fetchone()
            if not row or row['used'] or row['expiry'] <= self.clock():
                raise Denied('INVITATION_UNAVAILABLE')
            options, state = self.server.register_begin(
                PublicKeyCredentialUserEntity(id=_user_id(self.owner), name=self.owner,
                                              display_name='Fortis owner'),
                credentials=[c for c, _ in self._credentials(db).values()],
                user_verification=UserVerificationRequirement.REQUIRED)
            ceremony = self._remember('enroll', state, permit=_hash(invite))
            return {'ceremonyId': ceremony, 'options': dict(options)}

    def finish_enrollment(self, ceremony, response):
        from fido2.utils import websafe_encode
        with self.lock:
            state, data = self._take(ceremony, 'enroll')
            parsed = self._parse(response, 'registration')
            try:
                attestation = self.server.register_complete(state, parsed)
            except (ValueError, TypeError, KeyError):
                raise Denied('WEBAUTHN_REGISTRATION_FAILED') from None
            credential = attestation.credential_data
            if credential is None or not attestation.is_user_verified() or parsed.raw_id != credential.credential_id:
                raise Denied('WEBAUTHN_USER_VERIFICATION_REQUIRED')
            cred_id = websafe_encode(credential.credential_id)
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                invite = db.execute('SELECT * FROM invitations WHERE digest=?', (data['permit'],)).fetchone()
                if not invite or invite['used'] or invite['expiry'] <= self.clock():
                    raise Denied('INVITATION_UNAVAILABLE')
                db.execute('INSERT INTO credentials(id,data,counter) VALUES(?,?,?)',
                           (cred_id, bytes(credential), attestation.counter))
                db.execute('UPDATE invitations SET used=1 WHERE digest=?', (data['permit'],))
            return {'registered': True, 'owner': self.owner}

    def _begin_assertion(self, kind, **data):
        from fido2.webauthn import UserVerificationRequirement
        with self.lock, self._db() as db:
            creds = self._credentials(db)
            if not creds:
                raise Denied('OWNER_NOT_ENROLLED')
            material = canonical({'kind': kind, 'rpId': self.rp_id,
                                  'origin': self.origin, **data}).encode()
            challenge = hashlib.sha256(secrets.token_bytes(32) + material).digest()
            options, state = self.server.authenticate_begin(
                [c for c, _ in creds.values()],
                user_verification=UserVerificationRequirement.REQUIRED, challenge=challenge)
            ceremony = self._remember(kind, state, credential_ids=list(creds), **data)
            return {'ceremonyId': ceremony, 'options': dict(options)}

    def begin_login(self):
        return self._begin_assertion('login')

    def _finish_assertion(self, state, data, response):
        from fido2.utils import websafe_encode
        parsed = self._parse(response, 'assertion')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            creds = self._credentials(db)
            if not creds:
                raise Denied('OWNER_NOT_ENROLLED')
            try:
                credential = self.server.authenticate_complete(
                    state, [c for c, _ in creds.values()], parsed)
            except (ValueError, TypeError, KeyError):
                raise Denied('WEBAUTHN_ASSERTION_FAILED') from None
            ident = websafe_encode(credential.credential_id)
            if ident not in data['credential_ids'] or ident not in creds:
                raise Denied('CREDENTIAL_NOT_ALLOWED')
            if not parsed.response.authenticator_data.is_user_verified():
                raise Denied('WEBAUTHN_USER_VERIFICATION_REQUIRED')
            if parsed.response.user_handle not in (None, _user_id(self.owner)):
                raise Denied('USER_HANDLE_MISMATCH')
            old = creds[ident][1]
            counter = parsed.response.authenticator_data.counter
            if (counter or old) and counter <= old:
                raise Denied('CREDENTIAL_COUNTER_REPLAY')
            db.execute('UPDATE credentials SET counter=? WHERE id=? AND counter=? AND active=1',
                       (counter, ident, old))
            if db.execute('SELECT changes()').fetchone()[0] != 1:
                raise Denied('CREDENTIAL_REVOKED')
        return self.owner

    def finish_login(self, ceremony, response):
        with self.lock:
            state, data = self._take(ceremony, 'login')
            owner = self._finish_assertion(state, data, response)
            session = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(32)
            self.sessions = {key: row for key, row in self.sessions.items()
                             if row['expires'] > self.clock()}
            if len(self.sessions) >= 128:
                raise Denied('SESSION_CAPACITY')
            self.sessions[_hash(session)] = {'owner': owner, 'expires': self.clock() + self.session_ttl,
                                              'csrf': csrf}
            return session, csrf

    def session(self, token, csrf=None):
        if not isinstance(token, str) or len(token) < 32:
            raise Denied('OWNER_SESSION_REQUIRED')
        with self.lock:
            row = self.sessions.get(_hash(token))
            if not row or row['expires'] <= self.clock():
                raise Denied('OWNER_SESSION_REQUIRED')
            if csrf is not None and (not isinstance(csrf, str) or
                                     not secrets.compare_digest(csrf, row['csrf'])):
                raise Denied('CSRF_DENIED')
            return row

    def begin_session_decision(self, session, request_id, fingerprint, decision):
        """Mint a one-use owner-session proof; trusted owner portal only.

        Caller MUST first require Origin, CSRF, exact pending request and a real
        user click. Neither client Gateway nor AI has an endpoint to mint this.
        """
        if decision not in ('approve', 'reject') or not isinstance(request_id, str) or not isinstance(fingerprint, str):
            raise Denied('DECISION_INVALID')
        self.session(session)
        with self.lock:
            self.session_decisions = {k: v for k, v in self.session_decisions.items()
                                      if v['expires'] > self.clock()}
            if len(self.session_decisions) >= 128:
                raise Denied('SESSION_DECISION_CAPACITY')
            permit = secrets.token_urlsafe(32)
            self.session_decisions[_hash(permit)] = {
                'expires': self.clock() + 30, 'session': _hash(session),
                'requestId': request_id, 'fingerprint': fingerprint, 'decision': decision}
            return {'mode': 'session', 'session': session, 'permit': permit}

    def begin_decision(self, session, request_id, fingerprint, decision):
        if decision not in ('approve', 'reject'):
            raise Denied('DECISION_INVALID')
        self.session(session)
        return self._begin_assertion('decision', session_hash=_hash(session),
                                     request_id=request_id, fingerprint=fingerprint, decision=decision)

    def verify(self, request_id, fingerprint, decision, proof):
        """Called ONLY by Core.owner_decide; verifies the actual FIDO2 assertion."""
        if isinstance(proof, dict) and set(proof) == {'mode', 'session', 'permit'} and proof['mode'] == 'session':
            with self.lock:
                self.session(proof['session'])
                permit = proof['permit']
                if not isinstance(permit, str):
                    raise Denied('SESSION_DECISION_UNAVAILABLE')
                row = self.session_decisions.pop(_hash(permit), None)
                if (not row or row['expires'] <= self.clock() or
                    row['session'] != _hash(proof['session']) or row['requestId'] != request_id or
                    row['fingerprint'] != fingerprint or row['decision'] != decision):
                    raise Denied('SESSION_DECISION_UNAVAILABLE')
                return self.owner
        if not isinstance(proof, dict) or set(proof) != {'session', 'ceremonyId', 'response'}:
            raise Denied('OWNER_PROOF_INVALID')
        self.session(proof['session'])
        with self.lock:
            state, data = self._take(proof['ceremonyId'], 'decision')
            if (data['session_hash'] != _hash(proof['session']) or data['request_id'] != request_id or
                data['fingerprint'] != fingerprint or data['decision'] != decision):
                raise Denied('DECISION_BINDING_MISMATCH')
            return self._finish_assertion(state, data, proof['response'])

    def revoke_credentials(self):
        """Operator-local only; NOT exposed through HTTP."""
        with self.lock, self._db() as db:
            db.execute('UPDATE credentials SET active=0')
            self.pending.clear()
            self.sessions.clear()
            self.session_decisions.clear()
