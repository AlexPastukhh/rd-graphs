"""Owner portal request-boundary and decision wiring tests without WebAuthn dependencies.

The fake verifier is strictly test-only. These tests do not claim real FIDO2,
human UV, browser ceremony, or production deployment acceptance.
"""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from fortis_approvals.core import Authenticator, Core, Denied
from fortis_approvals.owner_portal import OwnerPortal
from fortis_approvals.synthetic import SyntheticAdapter


class TestOwnerVerifier:
    origin = 'http://localhost:18990'
    owner = 'test-owner'

    def session(self, token, csrf=None):
        if token != 'owner-session' or (csrf is not None and csrf != 'csrf-token'):
            raise Denied('OWNER_SESSION_REQUIRED')
        return {'owner': self.owner, 'csrf': 'csrf-token'}

    def begin_session_decision(self, session, request_id, fingerprint, decision):
        self.session(session)
        return {
            'requestId': request_id,
            'fingerprint': fingerprint,
            'decision': decision,
            'session': session,
        }

    def verify(self, request_id, fingerprint, decision, proof):
        if (not isinstance(proof, dict) or
                proof != {
                    'requestId': request_id,
                    'fingerprint': fingerprint,
                    'decision': decision,
                    'session': 'owner-session',
                }):
            raise Denied('TEST_OWNER_PROOF_INVALID')
        return self.owner


class OwnerPortalInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fortis-owner-input-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.adapter = SyntheticAdapter(root / 'synthetic.sqlite')
        self.adapter.seed('R3', 'before')
        self.owner = TestOwnerVerifier()
        self.auth = Authenticator({'agent-secret': 'agent-1'})
        self.core = Core(
            root / 'approvals.sqlite',
            adapters={'synthetic': self.adapter},
            policies={('synthetic', 'set_ask'): 'ASK'},
            authenticator=self.auth,
            owner_verifier=self.owner,
        )
        self.portal = OwnerPortal(self.core, self.owner)

    def action(self):
        return {
            'requestId': str(uuid.uuid4()),
            'service': 'synthetic',
            'operation': 'set_ask',
            'target': 'R3',
            'params': {'value': 'after'},
            'expectedVersion': 0,
            'reason': 'owner input regression',
        }

    def call(self, path, raw=None, *, cookie='owner-session', csrf='csrf-token',
             origin='http://localhost:18990', host='localhost:18990',
             extra_headers=None):
        method = 'POST' if raw is not None else 'GET'
        body = raw if raw is not None else b''
        env = {
            'HTTP_HOST': host,
            'REQUEST_METHOD': method,
            'PATH_INFO': path,
            'QUERY_STRING': '',
            'wsgi.input': BytesIO(body),
            'CONTENT_LENGTH': str(len(body)),
            'CONTENT_TYPE': 'application/json',
        }
        if method == 'POST':
            env['HTTP_ORIGIN'] = origin
        if cookie:
            env['HTTP_COOKIE'] = 'fortis_owner=' + cookie
        if csrf:
            env['HTTP_X_FORTIS_CSRF'] = csrf
        if extra_headers:
            env.update(extra_headers)
        observed = []
        response = b''.join(
            self.portal(env, lambda status, headers: observed.append((status, dict(headers)))))
        return int(observed[0][0][:3]), json.loads(response), observed[0][1]

    def submit(self):
        return self.core.client('agent-secret', 'submit', self.action())

    def decision_body(self, row):
        return json.dumps({
            'requestId': row['requestId'],
            'fingerprint': row['fingerprint'],
            'decision': 'approve',
        }, separators=(',', ':')).encode()

    def test_duplicate_json_keys_are_denied_before_owner_decision(self):
        row = self.submit()
        raw = self.decision_body(row)
        duplicate = raw.replace(
            b'"requestId":',
            b'"requestId":"00000000-0000-4000-8000-000000000001","requestId":',
            1,
        )
        code, result, _ = self.call('/v1/owner/decision/session', duplicate)
        self.assertEqual(code, 400)
        self.assertEqual(result['error'], 'REQUEST_INVALID')
        self.assertEqual(self.core._read(row['requestId'])['state'], 'PENDING')
        self.assertEqual(self.adapter.get('R3')['version'], 0)

    def test_nonfinite_and_deep_json_are_denied_without_server_exception(self):
        nonfinite = b'{"value":NaN}'
        deeply_nested = b'{"value":' + b'[' * 1200 + b'0' + b']' * 1200 + b'}'
        for body in (nonfinite, deeply_nested):
            with self.subTest(prefix=body[:20]):
                code, result, _ = self.call('/v1/owner/decision/session', body)
                self.assertEqual(code, 400)
                self.assertEqual(result['error'], 'REQUEST_INVALID')

    def test_invalid_content_length_and_short_body_fail_closed(self):
        portal = self.portal
        env = {
            'HTTP_HOST': 'localhost:18990',
            'REQUEST_METHOD': 'POST',
            'PATH_INFO': '/v1/login/begin',
            'QUERY_STRING': '',
            'CONTENT_TYPE': 'application/json',
            'CONTENT_LENGTH': '１２',
            'wsgi.input': BytesIO(b'{}'),
            'HTTP_ORIGIN': 'http://localhost:18990',
        }
        observed = []
        response = b''.join(portal(env, lambda status, headers: observed.append(status)))
        self.assertEqual(int(observed[0][:3]), 403)
        self.assertEqual(json.loads(response)['error'], 'BODY_SIZE')
        env['CONTENT_LENGTH'] = '3'
        env['wsgi.input'] = BytesIO(b'{}')
        observed.clear()
        response = b''.join(portal(env, lambda status, headers: observed.append(status)))
        self.assertEqual(int(observed[0][:3]), 403)
        self.assertEqual(json.loads(response)['error'], 'BODY_SIZE')

    def test_stale_preview_blocks_owner_approval_after_external_change(self):
        row = self.submit()
        with self.adapter._db() as db:
            db.execute(
                'UPDATE objects SET value=?,version=? WHERE id=?',
                ('changed-externally', 1, 'R3'),
            )
        code, result, _ = self.call(
            '/v1/owner/decision/session', self.decision_body(row))
        self.assertEqual(code, 200)
        self.assertEqual(result['state'], 'STALE')
        self.assertEqual(self.adapter.get('R3'), {
            'value': 'changed-externally', 'version': 1})
        self.assertIsNone(self.adapter.receipt(row['requestId']))

    def test_replayed_owner_click_cannot_apply_twice(self):
        row = self.submit()
        body = self.decision_body(row)
        first = self.call('/v1/owner/decision/session', body)
        second = self.call('/v1/owner/decision/session', body)
        self.assertEqual((first[0], first[1]['state']), (200, 'EXECUTED'))
        self.assertEqual(second[0], 403)
        self.assertEqual(self.adapter.get('R3'), {'value': 'after', 'version': 1})
        self.assertEqual(
            [event['state'] for event in self.core.events(row['requestId'])],
            ['PENDING', 'APPROVED', 'DISPATCHED', 'EXECUTED'],
        )

    def test_blocked_and_strong_operations_cannot_use_session_only(self):
        row = self.submit()
        blocked = OwnerPortal(
            self.core, self.owner, blocked_approvals={('synthetic', 'set_ask')})
        self.portal = blocked
        code, result, _ = self.call(
            '/v1/owner/decision/session', self.decision_body(row))
        self.assertEqual(code, 403)
        self.assertEqual(result['error'], 'OWNER_OPERATION_WRITE_NOT_ENABLED')
        self.assertEqual(self.core._read(row['requestId'])['state'], 'PENDING')

        strong = OwnerPortal(
            self.core, self.owner, strong_operations={('synthetic', 'set_ask')})
        self.portal = strong
        code, result, _ = self.call(
            '/v1/owner/decision/session', self.decision_body(row))
        self.assertEqual(code, 403)
        self.assertEqual(result['error'], 'STRONG_PROOF_REQUIRED')
        self.assertEqual(self.adapter.get('R3')['version'], 0)

    def test_host_forwarding_and_bearer_headers_are_rejected(self):
        row = self.submit()
        body = self.decision_body(row)
        for kwargs in (
            {'host': 'evil.test'},
            {'extra_headers': {'HTTP_X_FORWARDED_HOST': 'evil.test'}},
            {'extra_headers': {'HTTP_AUTHORIZATION': 'Bearer agent-secret'}},
        ):
            with self.subTest(kwargs=kwargs):
                code, _, _ = self.call(
                    '/v1/owner/decision/session', body, **kwargs)
                self.assertEqual(code, 403)
        self.assertEqual(self.core._read(row['requestId'])['state'], 'PENDING')
        self.assertEqual(self.adapter.get('R3')['version'], 0)


if __name__ == '__main__':
    unittest.main()
