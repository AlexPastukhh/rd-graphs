"""OFFLINE G4 WRITE EXECUTOR LAB. NOT in Docker image or deployment.

No SonarHTTPTransport, token, CLI, web listener or real API access exists here.
All mutation attempts target a *typed in-memory LabSonar* only.
This proves a possible durable ASK-bound executor interface, NOT a secure
production process boundary and NOT an authorization for SonarCloud POST.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from .core import Denied, canonical
from .sonar import SonarIssueAdapter, SonarTransportError

LAB_PROJECT = 'g4-lab-project'
LAB_ISSUE = 'G4-LAB-1'
LAB_OPERATION = ('sonarcloud', 'accept_issue')


class LabSonar:
    """Exactly one simulated issue. No URL, socket, token or HTTP imports."""
    def __init__(self):
        self.issue = dict(key=LAB_ISSUE, project=LAB_PROJECT, issueStatus='OPEN',
                          updateDate='2026-10-31T00:00:00+0000',
                          message='isolated synthetic issue', rule='python:S100',
                          severity='MAJOR', component=LAB_PROJECT+':lab.py',
                          assignee=None, type='CODE_SMELL')
        self.calls = []
        self.posts = 0
        self.fail_after_post = False
        self.fail_before_post = False
        self.race_before_post = False

    def call(self, method, path, params):
        self.calls.append((method, path, deepcopy(params)))
        if method == 'GET' and path == '/api/issues/search':
            if params.get('componentKeys') != LAB_PROJECT or params.get('issues', LAB_ISSUE) != LAB_ISSUE:
                return {'issues': []}
            row = deepcopy(self.issue)
            if 'additionalFields' in params:
                if params['additionalFields'] != 'transitions':
                    raise Denied('LAB_TRANSITIONS_DENIED')
                row['transitions'] = ['accept'] if row['issueStatus'] == 'OPEN' else []
            return {'issues': [row]}
        if method == 'POST' and path == '/api/issues/do_transition':
            if params != {'issue': LAB_ISSUE, 'transition': 'accept'}:
                raise Denied('LAB_POST_NOT_SCOPED')
            self.posts += 1  # counts even failed outbound-attempt simulation
            if self.fail_before_post:
                raise SonarTransportError('LAB_SIMULATED_429')
            if self.race_before_post:
                self.issue['message'] = 'concurrent edit after preflight'
                self.issue['updateDate'] = '2026-10-31T00:00:30+0000'
            self.issue['issueStatus'] = 'ACCEPTED'
            self.issue['updateDate'] = '2026-10-31T00:01:00+0000'
            if self.fail_after_post:
                raise SonarTransportError('LAB_SIMULATED_LOST_RESPONSE')
            return {'issue': deepcopy(self.issue)}
        raise Denied('LAB_ROUTE_DENIED')


class LabPostGate:
    """One exact Core-authorized request -> one durable POST attempt maximum.

    The Core state DB is a trusted input. Out-of-process DB tampering or code
    execution in the same token-bearing process is NOT defeated by this gate.
    The gate reserves before simulating POST, so a crash may yield UNCERTAIN.
    """
    def __init__(self, database, source, *, trusted_policy='ASK', clock=None):
        if type(source) is not LabSonar:
            raise Denied('LAB_IN_MEMORY_SOURCE_ONLY')
        if trusted_policy not in ('ALLOW', 'ASK'):
            raise Denied('LAB_TRUSTED_POLICY_REQUIRED')
        # This is a trusted constructor choice, NEVER a caller/AI request field.
        # Sonar accept_issue is ASK in deployed G4 and in the worker lab.
        self.trusted_policy = trusted_policy
        self.database = Path(database)
        self.source = source
        self.clock = clock or (lambda: int(time.time()))
        self._local = threading.local()
        if not self.database.is_file() or self.database.is_symlink():
            raise Denied('LAB_TRUSTED_CORE_DATABASE_REQUIRED')
        with sqlite3.connect(self.database, timeout=10) as db:
            db.execute('CREATE TABLE IF NOT EXISTS g4_lab_post_attempts '
                       '(request_id TEXT PRIMARY KEY, reserved_at INTEGER NOT NULL)')

    @contextmanager
    def armed_for(self, req):
        if getattr(self._local, 'request', None) is not None:
            raise Denied('LAB_NESTED_DISPATCH_DENIED')
        self._local.request = deepcopy(req)
        try:
            yield
        finally:
            self._local.request = None

    def _reserve(self, params):
        req = getattr(self._local, 'request', None)
        if (type(req) is not dict or req.get('service') != LAB_OPERATION[0] or
            req.get('operation') != LAB_OPERATION[1] or req.get('target') != LAB_ISSUE or
            req.get('params') != {'projectKey': LAB_PROJECT, 'transition': 'accept',
                'expectedIssueSha256':req.get('params', {}).get('expectedIssueSha256')} or
            params != {'issue': LAB_ISSUE, 'transition': 'accept'}):
            raise Denied('LAB_EXACT_ACTION_DENIED')
        try:
            ident = str(uuid.UUID(req['requestId']))
        except (KeyError, TypeError, ValueError):
            raise Denied('LAB_REQUEST_ID_DENIED') from None
        if req['requestId'] != ident:
            raise Denied('LAB_REQUEST_ID_DENIED')
        with sqlite3.connect(self.database, timeout=10) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('''SELECT id,fingerprint,actor,payload,snapshot,
                        state,decision,owner,policy_version,expires_at
                        FROM requests WHERE id=?''', (ident,)).fetchone()
            if (row is None or row['state'] != 'DISPATCHED' or
                row['expires_at'] <= int(self.clock()) or
                row['payload'] != canonical(req) or
                not row['actor'] or not row['policy_version']):
                raise Denied('LAB_APPROVED_DISPATCH_REQUIRED')
            expected = hashlib.sha256(canonical({
                'actor': row['actor'], 'request': json.loads(row['payload']),
                'policyVersion': row['policy_version'],
                'preview': json.loads(row['snapshot'])}).encode()).hexdigest()
            if expected != row['fingerprint']:
                raise Denied('LAB_FINGERPRINT_CHANGED')
            events = db.execute('''SELECT state,detail FROM events
                WHERE request_id=? ORDER BY seq''', (ident,)).fetchall()
            states = [event['state'] for event in events]
            if self.trusted_policy == 'ASK':
                if (states != ['PENDING','APPROVED','DISPATCHED'] or
                    json.loads(events[0]['detail']).get('policy') != 'ASK' or
                    row['decision'] != 'approve' or not row['owner']):
                    raise Denied('LAB_ASK_APPROVAL_REQUIRED')
                detail = json.loads(events[1]['detail'])
                if (detail.get('owner') != row['owner'] or
                    detail.get('requestSHA256') != expected or
                    not isinstance(detail.get('proofSHA256'), str) or
                    len(detail['proofSHA256']) != 64):
                    raise Denied('LAB_WEBAUTHN_PROOF_AUDIT_REQUIRED')
            else:
                # ALLOW has NO owner decision, yet must be explicitly allowed
                # by a trusted policy and lead into the SAME Core.execute and
                # adapter.post_gate path as a completed ASK.
                if (states != ['APPROVED','DISPATCHED'] or
                    json.loads(events[0]['detail']).get('policy') != 'ALLOW' or
                    row['decision'] is not None or row['owner'] is not None):
                    raise Denied('LAB_TRUSTED_ALLOW_REQUIRED')
            try:
                db.execute('INSERT INTO g4_lab_post_attempts VALUES (?,?)',
                           (ident,int(self.clock())))
            except sqlite3.IntegrityError:
                raise Denied('LAB_POST_ATTEMPT_ALREADY_RESERVED') from None
        return True

    def call(self, method, path, params):
        if method == 'GET':
            return self.source.call(method, path, params)
        if method != 'POST' or path != '/api/issues/do_transition':
            raise Denied('LAB_WRITE_METHOD_DENIED')
        self._reserve(params)  # persisted before effects, even if fake upstream fails
        return self.source.call(method,path,params)


class LabGuardedSonarAdapter(SonarIssueAdapter):
    """Synthetic-only Sonar adapter; all POSTs pass LabPostGate._reserve."""
    def __init__(self, database, source, receipt_store, *, trusted_policy='ASK', clock=None):
        self.post_gate = LabPostGate(database, source, trusted_policy=trusted_policy,
                                     clock=clock)
        super().__init__(self.post_gate, project_keys=(LAB_PROJECT,),
                         receipt_store=receipt_store)

    def apply(self, req):
        with self.post_gate.armed_for(req):
            return super().apply(req)


class LabOwnerProposalCoreMixin:
    """Owner-facing Core: record approved ASK without dispatching any effect.

    This mixin is lab-only. Production needs an independently reviewed IPC
    protocol, process identity, token custody and process sandbox.
    """
    def execute(self, request_id):
        # OwnerPortal/Core.owner_decide calls this after saving APPROVED.
        # Write-worker is the only process intended to use Core.execute.
        return self._read(request_id)


def lab_worker_once(db_path, receipts_path, request_id, output_queue):
    """Synthetic worker callable by multiprocessing spawn; exact UUID only.

    Returns non-secret status/counts via an IPC queue. Always creates a fake
    LabSonar source; no real credential/host/HTTP transport can be injected.
    """
    from .core import Authenticator, Core
    try:
        source = LabSonar()
        core = Core(db_path,adapters={},policies={LAB_OPERATION:'ASK'},
                    authenticator=Authenticator({'lab-proposer':'lab-actor'}))
        adapter = LabGuardedSonarAdapter(db_path,source,receipts_path)
        core.adapters['sonarcloud'] = adapter
        outcome = core.execute(request_id)
        output_queue.put({'state':outcome['state'],'fake_posts':source.posts})
    except Exception:
        # No stack, secrets, dynamic file paths or Issue text in IPC output.
        output_queue.put({'state':'LAB_WORKER_FAILED','fake_posts':0})
