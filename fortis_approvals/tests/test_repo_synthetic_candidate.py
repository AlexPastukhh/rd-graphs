"""Candidate assembly tests: synthetic WSGI only; no Windows or Sonar access."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from fortis_approvals.core import Denied
from fortis_approvals.repo_synthetic_candidate import build_synthetic_candidate
from test_g4_write_security import G4VirtualKey

OWNER_ORIGIN = 'http://localhost:18993'
REPO_HOST = 'repo-ingress.test:18443'
GRANT = 'synthetic-isolated-test-grant-000001'


class CandidateVirtualKey(G4VirtualKey):
    def client_data(self, opts, typ, *, origin=OWNER_ORIGIN, cross_origin=False):
        return super().client_data(opts, typ, origin=origin, cross_origin=cross_origin)

    def assert_(self, begin, *, origin=OWNER_ORIGIN, uv=True, cross_origin=False):
        return super().assert_(begin, origin=origin, uv=uv, cross_origin=cross_origin)


class RepoSyntheticCandidateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='fortis-synthetic-candidate-')
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name) / 'candidate'
        self.state.mkdir(mode=0o700)
        self.core, self.owner, self.adapter, self.portal, self.ingress = (
            build_synthetic_candidate(state=self.state, owner_origin=OWNER_ORIGIN,
                ingress_host=REPO_HOST, ingress_grant=GRANT))
        self.key = CandidateVirtualKey()
        self.cookie = None
        self.csrf = None
    @staticmethod
    def intent(operation, target):
        return {'requestId': str(uuid.uuid4()), 'service': 'synthetic',
                'operation': operation, 'target': target,
                'params': {'value': 'changed', 'expectedVersion': 0},
                'reason': 'synthetic candidate wire check'}

    @staticmethod
    def _run(app, env):
        out = []
        payload = b''.join(app(env, lambda status, headers:
            out.append((int(status[:3]), dict(headers)))))
        return out[0][0], json.loads(payload), out[0][1]

    def repo_call(self, request=None, *, path='/v1/actions', method='POST',
                  grant=GRANT, scheme='https'):
        raw = json.dumps(request).encode() if request is not None else b''
        env = {'HTTP_HOST': REPO_HOST, 'wsgi.url_scheme': scheme,
               'REQUEST_METHOD': method, 'PATH_INFO': path,
               'QUERY_STRING': '', 'wsgi.input': BytesIO(raw),
               'CONTENT_TYPE': 'application/json' if method == 'POST' else '',
               'CONTENT_LENGTH': str(len(raw)) if method == 'POST' else '0'}
        if grant is not None:
            env['HTTP_AUTHORIZATION'] = 'Bearer ' + grant
        return self._run(self.ingress, env)
    def owner_call(self, path, request=None):
        raw = json.dumps(request).encode() if request is not None else b''
        env = {'HTTP_HOST': 'localhost:18993',
               'REQUEST_METHOD': 'POST' if request is not None else 'GET',
               'PATH_INFO': path, 'QUERY_STRING': '',
               'wsgi.input': BytesIO(raw), 'CONTENT_TYPE': 'application/json',
               'CONTENT_LENGTH': str(len(raw))}
        if request is not None:
            env['HTTP_ORIGIN'] = OWNER_ORIGIN
        if self.cookie:
            env['HTTP_COOKIE'] = 'fortis_owner=' + self.cookie
            env['HTTP_X_FORTIS_CSRF'] = self.csrf
        return self._run(self.portal, env)

    def login(self):
        invitation = self.owner.issue_invitation()
        begin = self.owner_call('/v1/enroll/begin',
                                {'invitation': invitation})[1]
        self.assertEqual(self.owner_call('/v1/enroll/finish', {
            'ceremonyId': begin['ceremonyId'],
            'response': self.key.enroll(begin)})[0], 200)
        begin = self.owner_call('/v1/login/begin', {})[1]
        code, result, headers = self.owner_call('/v1/login/finish', {
            'ceremonyId': begin['ceremonyId'],
            'response': self.key.assert_(begin)})
        self.assertEqual(code, 200)
        self.cookie = headers['Set-Cookie'].split(';')[0].split('=', 1)[1]
        self.csrf = result['csrf']
    def decide(self, request_id, decision):
        code, begin, _ = self.owner_call('/v1/owner/decision/begin', {
            'requestId': request_id, 'decision': decision})
        self.assertEqual(code, 200)
        return self.owner_call('/v1/owner/decision/finish', {
            'requestId': request_id, 'decision': decision,
            'ceremonyId': begin['ceremonyId'],
            'response': self.key.assert_(begin)})

    def test_allow_and_webauthn_ask_share_core_and_audit(self):
        free = self.intent('set_free', 'SYN-ALLOW')
        code, result, _ = self.repo_call(free)
        self.assertEqual((code, result), (200, {
            'requestId': free['requestId'], 'state': 'EXECUTED'}))
        ask = self.intent('set_ask', 'SYN-ASK')
        code, result, _ = self.repo_call(ask)
        self.assertEqual((code, result['state']), (202, 'PENDING'))
        self.assertEqual(self.adapter.get('SYN-ASK')['version'], 0)
        self.login()
        code, rows, _ = self.owner_call('/v1/owner/pending')
        self.assertEqual(code, 200)
        self.assertEqual([row['requestId'] for row in rows], [ask['requestId']])
        self.assertTrue(rows[0]['requiresStrongProof'])
        code, _, _ = self.owner_call('/v1/owner/decision/session', {
            'requestId': ask['requestId'], 'decision': 'approve',
            'fingerprint': rows[0]['fingerprint']})
        self.assertEqual(code, 403)  # Session alone cannot approve ASK.
        code, done, _ = self.decide(ask['requestId'], 'approve')
        self.assertEqual((code, done['state']), (200, 'EXECUTED'))
        self.assertEqual(self.repo_call(path='/v1/requests/' + ask['requestId'],
                                        method='GET')[1]['state'], 'EXECUTED')
        for request, states in (
                (free, ['APPROVED', 'DISPATCHED', 'EXECUTED']),
                (ask, ['PENDING', 'APPROVED', 'DISPATCHED', 'EXECUTED'])):
            self.assertEqual([x['state'] for x in self.core.events(
                request['requestId'])], states)
        self.assertEqual(self.repo_call(free)[1]['state'], 'EXECUTED')
        self.assertEqual(self.repo_call(ask)[1]['state'], 'EXECUTED')
        self.assertEqual(self.adapter.get('SYN-ALLOW')['version'], 1)
        self.assertEqual(self.adapter.get('SYN-ASK')['version'], 1)
        self.assertEqual(self.core.execute(ask['requestId'])['state'], 'EXECUTED')
        self.assertEqual(self.adapter.get('SYN-ASK')['version'], 1)

    def test_webauthn_reject_and_deny_have_no_effect(self):
        ask = self.intent('set_ask', 'SYN-ASK')
        self.assertEqual(self.repo_call(ask)[1]['state'], 'PENDING')
        self.login()
        self.assertEqual(self.decide(ask['requestId'], 'reject')[1]['state'],
                         'REJECTED')
        self.assertEqual(self.repo_call(path='/v1/requests/' + ask['requestId'],
                                        method='GET')[1]['state'], 'REJECTED')
        deny = self.intent('set_deny', 'SYN-DENY')
        self.assertEqual(self.repo_call(deny)[0], 403)
        self.assertEqual(self.adapter.get('SYN-ASK')['version'], 0)
        self.assertEqual(self.adapter.get('SYN-DENY')['version'], 0)
    def test_route_grant_tls_and_actor_are_not_owner_authority(self):
        self.assertEqual(self.repo_call(self.intent('set_free', 'SYN-ALLOW'),
                                        scheme='http')[0], 403)
        self.assertEqual(self.repo_call(self.intent('set_free', 'SYN-ALLOW'),
                                        grant=None)[0], 401)
        self.assertEqual(self.repo_call(self.intent('set_free', 'SYN-ALLOW'),
                                        grant='wrong-credential')[0], 401)
        for path in ('/v1/owner/pending', '/v1/owner/decision/finish',
                     '/v1/execute', '/api/proxy'):
            with self.subTest(path=path):
                self.assertEqual(self.repo_call(path=path, method='GET')[0], 404)
        self.assertEqual(set(self.core.adapters), {'synthetic'})
        self.assertEqual(self.adapter.get('SYN-ALLOW')['version'], 0)

    def test_isolated_state_required_and_restart_preserves_result(self):
        free = self.intent('set_free', 'SYN-ALLOW')
        self.assertEqual(self.repo_call(free)[1]['state'], 'EXECUTED')
        core, owner, synthetic, portal, ingress = build_synthetic_candidate(
            state=self.state, owner_origin=OWNER_ORIGIN,
            ingress_host=REPO_HOST, ingress_grant=GRANT)
        self.assertEqual(synthetic.get('SYN-ALLOW')['version'], 1)
        self.assertEqual(core._read(free['requestId'])['state'], 'EXECUTED')
        self.assertIs(core.owner_verifier, owner)
        self.assertIs(portal.core, ingress.broker.core)
        for name in ('owner.sqlite', 'approvals.sqlite', '.g4-candidate-v1'):
            with tempfile.TemporaryDirectory(prefix='fortis-foreign-state-') as td:
                other = Path(td)
                other.chmod(0o700)
                (other / name).write_text('existing unrelated state')
                with self.subTest(name=name), self.assertRaisesRegex(
                        Denied, 'FRESH_STATE_REQUIRED'):
                    build_synthetic_candidate(state=other,
                        owner_origin=OWNER_ORIGIN, ingress_host=REPO_HOST,
                        ingress_grant=GRANT)
        with self.assertRaisesRegex(Denied, 'DISTINCT_OWNER_ORIGIN_REQUIRED'):
            build_synthetic_candidate(state=self.state,
                owner_origin='http://localhost:18991',
                ingress_host=REPO_HOST, ingress_grant=GRANT)
        with self.assertRaisesRegex(Denied, 'INGRESS_GRANT_REQUIRED'):
            build_synthetic_candidate(state=self.state,
                owner_origin=OWNER_ORIGIN, ingress_host=REPO_HOST,
                ingress_grant='short')


if __name__ == '__main__':
    unittest.main()
