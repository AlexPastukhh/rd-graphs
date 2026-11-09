"""G1: durable, fail-closed approval checkpoint for typed service adapters.

Not a deployment/authentication server. Owner verification is injected by the
trusted G2 boundary; no dummy verifier or owner HTTP endpoint exists here.
"""
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _reject_json_constant(_value):
    raise ValueError('JSON_NONFINITE')


def _finite_json_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('JSON_NONFINITE')
    return number


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('JSON_DUPLICATE_FIELD')
        result[key] = value
    return result


def loads_strict(raw):
    """Decode UTF-8 JSON without duplicate names, non-finite numbers or ambiguity."""
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    if not isinstance(raw, str):
        raise TypeError('JSON_TEXT_REQUIRED')
    return json.loads(raw, parse_constant=_reject_json_constant,
                      parse_float=_finite_json_float,
                      object_pairs_hook=_unique_json_object)


class ApprovalError(ValueError):
    pass


class Denied(ApprovalError):
    pass


class Conflict(ApprovalError):
    pass


class Stale(ApprovalError):
    pass


class Authenticator:
    """Synthetic credential boundary. Provision/revoke ONLY from trusted host code.

    No actor/role field from request payload is trusted. Production G2 replaces
    token management and adds a separately authenticated owner session.
    """
    def __init__(self, credentials):
        self._credentials = dict(credentials)
        # Store grant IDs, not display names; one grant per credential means
        # revoke() cannot accidentally leave an alternate active key behind.
        if len(set(self._credentials.values())) != len(self._credentials):
            raise ValueError('CLIENT_GRANT_IDS_MUST_BE_UNIQUE')

    def authenticate(self, credential):
        principal = self._credentials.get(credential)
        if not isinstance(principal, str) or not principal:
            raise Denied('CLIENT_UNAUTHORIZED')
        return principal

    def revoke(self, credential):
        self._credentials.pop(credential, None)

    def active(self, principal):
        return principal in self._credentials.values()


class Core:
    STATES = {'PENDING', 'APPROVED', 'DISPATCHED', 'EXECUTED', 'REJECTED',
              'EXPIRED', 'STALE', 'UNCERTAIN', 'REVOKED'}

    def __init__(self, database, *, adapters, policies, authenticator, owner_verifier=None,
                 clock=None, expiry_seconds=3600, policy_version="v1"):

        self.path = Path(database)
        self.adapters = dict(adapters)
        self.policies = dict(policies)
        self.auth = authenticator
        self.owner_verifier = owner_verifier  # independent, trusted G2 authority
        self.clock = clock or (lambda: int(time.time()))
        self.expiry_seconds = expiry_seconds
        self.policy_version = policy_version
        if not isinstance(policy_version, str) or not policy_version:
            raise ValueError("POLICY_VERSION_INVALID")
        if not isinstance(expiry_seconds, int) or expiry_seconds <= 0:
            raise ValueError('EXPIRY_INVALID')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise Denied('STORE_SYMLINK_DENIED')
        if not self.path.exists():
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        if self.path.stat().st_mode & 0o077:
            raise Denied('STORE_PERMISSIONS_INVALID')
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, actor TEXT NOT NULL,
                    payload TEXT NOT NULL, snapshot TEXT NOT NULL, state TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
                    decision TEXT, owner TEXT, result TEXT, failure TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL,
                    at INTEGER NOT NULL, state TEXT NOT NULL, detail TEXT NOT NULL
                );
            ''')

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

    def _event(self, db, request_id, state, detail=None):
        db.execute('INSERT INTO events(request_id, at, state, detail) VALUES(?,?,?,?)',
                   (request_id, int(self.clock()), state, canonical(detail or {})))

    @staticmethod
    def _payload(value):
        fields = {'requestId', 'service', 'operation', 'target', 'params',
                  'expectedVersion', 'reason'}
        if not isinstance(value, dict) or set(value) != fields:
            raise Denied('REQUEST_SCHEMA')
        try:
            ident = str(uuid.UUID(value['requestId']))
        except (TypeError, ValueError, KeyError, AttributeError):
            raise Denied('REQUEST_ID') from None
        if ident != value['requestId']:
            raise Denied('REQUEST_ID')
        for field in ('service', 'operation', 'target'):
            v = value[field]
            if not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', v):
                raise Denied('REQUEST_' + field.upper())
        if (type(value['expectedVersion']) is not int or value['expectedVersion'] < 0 or
            not isinstance(value['params'], dict) or not isinstance(value['reason'], str) or
            not 0 < len(value['reason'].strip()) <= 1500):
            raise Denied('REQUEST_FIELDS')
        try:
            serialized = canonical(value)
            encoded = serialized.encode('utf-8')
        except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
            raise Denied('REQUEST_JSON') from None
        if len(encoded) > 32768:
            raise Denied('REQUEST_SIZE')
        return serialized

    def _view(self, row):
        return {'requestId': row['id'], 'state': row['state'], 'fingerprint': row['fingerprint'],
                'request': json.loads(row['payload']), 'actor': row['actor'],
                'policyVersion': row['policy_version'],
                'preview': json.loads(row['snapshot']),
                'createdAt': row['created_at'], 'expiresAt': row['expires_at'],
                'decision': row['decision'], 'owner': row['owner'],
                'result': json.loads(row['result']) if row['result'] else None,
                'failure': row['failure']}

    def _policy(self, actor, payload):
        key = (payload['service'], payload['operation'])
        rule = self.policies.get((actor, *key, payload['target']),
            self.policies.get((actor, *key), self.policies.get(key, 'DENY')))
        # Optional trusted policy predicate for target/params, never AI-supplied code.
        return rule(actor, payload) if callable(rule) else rule

    def client(self, credential, action, data):
        actor = self.auth.authenticate(credential)
        if action == 'submit':
            return self.submit(actor, data)
        if action == 'status' and isinstance(data, str):
            with self._db() as db:
                row = db.execute('SELECT * FROM requests WHERE id=?', (data,)).fetchone()
                if not row or row['actor'] != actor:
                    raise Denied('REQUEST_NOT_AVAILABLE')
                return self._view(row)
        raise Denied('CLIENT_ACTION_DENIED')

    def submit(self, actor, payload):
        body = self._payload(payload)
        request_id = payload['requestId']
        def fingerprint(snapshot):
            # Owner signature MUST bind the immutable before/after preview too.
            return hashlib.sha256(canonical({'actor': actor, 'request': json.loads(body),
                    'policyVersion': self.policy_version, 'preview': snapshot}).encode()).hexdigest()
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
            if prior:
                if (prior['fingerprint'] != fingerprint(json.loads(prior['snapshot'])) or
                    prior['actor'] != actor):
                    raise Conflict('REQUEST_ID_CONFLICT')
                return self._view(prior)
            key = (payload['service'], payload['operation'])
            policy = self._policy(actor, payload)
            if policy == 'DENY' or policy not in ('ALLOW', 'ASK') or key[0] not in self.adapters:
                raise Denied('OPERATION_DENIED')
            snapshot = self.adapters[key[0]].prepare(payload)  # read-only, domain validates
            digest = fingerprint(snapshot)
            now = int(self.clock())
            state = 'PENDING' if policy == 'ASK' else 'APPROVED'
            db.execute('''INSERT INTO requests (id, fingerprint, actor, payload, snapshot,
                           state, policy_version, created_at, expires_at) VALUES (?,?,?,?,?,?,?,?,?)''',
                       (request_id, digest, actor, body, canonical(snapshot), state,
                        self.policy_version, now, now + self.expiry_seconds))
            self._event(db, request_id, state, {'policy': policy})
        if policy == 'ALLOW':
            return self.execute(request_id)
        return self._read(request_id)

    def _read(self, request_id):
        with self._db() as db:
            row = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
            if not row:
                raise Denied('REQUEST_NOT_AVAILABLE')
            return self._view(row)

    def owner_list(self, *, pending=True, limit=100):
        """Trusted G2 caller only; never expose on the AI client gateway."""
        if type(pending) is not bool or type(limit) is not int or not 0 < limit <= 100:
            raise Denied('LIST_INVALID')
        with self._db() as db:
            rows = db.execute('SELECT * FROM requests WHERE state ' +
                ('= ?' if pending else '<> ?') + ' ORDER BY created_at DESC,id DESC LIMIT ?',
                ('PENDING', limit)).fetchall()
            return [self._view(row) for row in rows]

    def owner_decide(self, request_id, decision, proof):
        """Trusted entry point; no owner decision without external verifier."""
        if decision not in ('approve', 'reject') or self.owner_verifier is None:
            raise Denied('OWNER_VERIFICATION_REQUIRED')
        with self._db() as db:
            row = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
            if not row or row['state'] != 'PENDING':
                raise Denied('REQUEST_NOT_PENDING')
            if decision == 'approve' and (
                    row['policy_version'] != self.policy_version or
                    self._policy(row['actor'], loads_strict(row['payload'])) != 'ASK'):
                raise Denied('OWNER_POLICY_CHANGED')
            if int(self.clock()) >= row['expires_at']:
                db.execute('UPDATE requests SET state=? WHERE id=? AND state=?',
                           ('EXPIRED', request_id, 'PENDING'))
                self._event(db, request_id, 'EXPIRED')
                return self._view(db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone())
            fingerprint = row['fingerprint']
        # verifier must authenticate owner AND bind the exact fingerprint/decision.
        # No test/default implementation is shipped in the production package.
        owner = self.owner_verifier.verify(request_id, fingerprint, decision, proof)
        if not isinstance(owner, str) or not owner:
            raise Denied('OWNER_VERIFICATION_REQUIRED')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
            if not row or row['state'] != 'PENDING':
                raise Denied('REQUEST_NOT_PENDING')
            if decision == 'approve' and (
                    row['policy_version'] != self.policy_version or
                    self._policy(row['actor'], loads_strict(row['payload'])) != 'ASK'):
                raise Denied('OWNER_POLICY_CHANGED')
            if int(self.clock()) >= row['expires_at']:
                db.execute('UPDATE requests SET state=? WHERE id=?', ('EXPIRED', request_id))
                self._event(db, request_id, 'EXPIRED')
                return self._view(db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone())
            state = 'APPROVED' if decision == 'approve' else 'REJECTED'
            db.execute('UPDATE requests SET state=?, decision=?, owner=? WHERE id=?',
                       (state, decision, owner, request_id))
            self._event(db, request_id, state, {'owner': owner,
                'proofSHA256': hashlib.sha256(canonical(proof).encode()).hexdigest(),
                'requestSHA256': fingerprint})
        return self.execute(request_id) if decision == 'approve' else self._read(request_id)

    def execute(self, request_id):
        """Same executor for ALLOW and approved ASK. Never retries dispatched work."""
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
            if not row:
                raise Denied('REQUEST_NOT_AVAILABLE')
            if row['state'] != 'APPROVED':
                return self._view(row)
            payload = json.loads(row['payload'])
            adapter = self.adapters[payload['service']]
            if int(self.clock()) >= row['expires_at']:
                db.execute('UPDATE requests SET state=?, failure=? WHERE id=?',
                           ('EXPIRED', 'REQUEST_EXPIRED_BEFORE_EXECUTION', request_id))
                self._event(db, request_id, 'EXPIRED')
                return self._view(db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone())
            if not self.auth.active(row['actor']):
                db.execute('UPDATE requests SET state=?, failure=? WHERE id=?',
                           ('REVOKED', 'INITIATOR_REVOKED', request_id))
                self._event(db, request_id, 'REVOKED')
                return self._view(db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone())
            if (row['policy_version'] != self.policy_version or
                self._policy(row['actor'], payload) !=
                    ('ALLOW' if row['decision'] is None else 'ASK')):
                db.execute('UPDATE requests SET state=?, failure=? WHERE id=?',
                           ('STALE', 'POLICY_CHANGED', request_id))
                self._event(db, request_id, 'STALE')
                return self._view(db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone())
            try:
                latest = adapter.prepare(payload)
                if canonical(latest) != row['snapshot']:
                    raise Stale('PREVIEW_INPUTS_CHANGED')
            except Denied as exc:
                db.execute('UPDATE requests SET state=?, failure=? WHERE id=?',
                           ('STALE', 'DOMAIN_CHECK_FAILED', request_id))
                self._event(db, request_id, 'STALE')
                return self._view(db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone())
            except Stale as exc:
                db.execute('UPDATE requests SET state=?, failure=? WHERE id=?',
                           ('STALE', str(exc), request_id))
                self._event(db, request_id, 'STALE')
                return self._view(db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone())
            # Durable marker BEFORE the external effect. Re-entry cannot repeat it.
            db.execute('UPDATE requests SET state=? WHERE id=?', ('DISPATCHED', request_id))
            self._event(db, request_id, 'DISPATCHED')
        try:
            result = adapter.apply(payload)
            if not adapter.confirm(request_id, result):
                raise RuntimeError('RECEIPT_NOT_CONFIRMED')
        except Stale as exc:
            state, failure, result = 'STALE', str(exc), None
        except Exception:
            # No blind retry after unknown remote outcome, even on timeout/restart.
            state, failure, result = 'UNCERTAIN', 'REMOTE_OUTCOME_UNCONFIRMED', None
        else:
            state, failure = 'EXECUTED', None
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
            if row['state'] == 'DISPATCHED':
                db.execute('UPDATE requests SET state=?, result=?, failure=? WHERE id=?',
                           (state, canonical(result) if result is not None else None, failure, request_id))
                self._event(db, request_id, state)
            return self._view(db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone())

    def reconcile(self, request_id):
        """Read-only upstream receipt lookup. No second mutation is attempted."""
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
            if not row or row['state'] not in ('UNCERTAIN', 'DISPATCHED'):
                raise Denied('RECONCILIATION_NOT_AVAILABLE')
            payload = json.loads(row['payload'])
            adapter = self.adapters[payload['service']]
            result = adapter.receipt(request_id)
            if result is None or not adapter.confirm(request_id, result):
                return self._view(row)
            db.execute('UPDATE requests SET state=?, result=?, failure=NULL WHERE id=?',
                       ('EXECUTED', canonical(result), request_id))
            self._event(db, request_id, 'EXECUTED', {'recovered': True})
            return self._view(db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone())

    def events(self, request_id):
        """Trusted local audit inspection; not exposed to AI as a public endpoint."""
        with self._db() as db:
            return [dict(row) for row in db.execute(
                'SELECT seq,request_id,at,state,detail FROM events WHERE request_id=? ORDER BY seq',
                (request_id,))]
