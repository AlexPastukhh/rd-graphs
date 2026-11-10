"""WSGI is a typed client boundary only, never a backdoor to owner decisions."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from fortis_approvals.core import Core, Authenticator
from fortis_approvals.gateway import ClientGateway
from fortis_approvals.synthetic import SyntheticAdapter


class ClientGatewayTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.adapter = SyntheticAdapter(root / 'dummy.sqlite')
        self.adapter.seed('R3', 'old')
        self.core = Core(root / 'approvals.sqlite',
                         adapters={'synthetic': self.adapter},
                         policies={('synthetic', 'set_ask'): 'ASK',
                                   ('synthetic', 'set_free'): 'ALLOW'},
                         authenticator=Authenticator({'synthetic-token': 'agent-1'}))
        self.gateway = ClientGateway(self.core, host='fortis-approvals.test')
        self.action = dict(requestId=str(uuid.uuid4()), service='synthetic', operation='set_ask',
                           target='R3', params={'value': 'new'}, expectedVersion=0,
                           reason='Synthetic test')

    def invoke(self, path='/v1/actions', method='POST', body=None, token='synthetic-token', **headers):
        if body is None:
            body = json.dumps(self.action).encode()
        if isinstance(body, dict):
            body = json.dumps(body).encode()
        env = {'HTTP_HOST': 'fortis-approvals.test', 'PATH_INFO': path, 'REQUEST_METHOD': method,
               'QUERY_STRING': '', 'CONTENT_TYPE': 'application/json',
               'CONTENT_LENGTH': str(len(body)), 'wsgi.input': BytesIO(body)}
        if token is not None:
            env['HTTP_AUTHORIZATION'] = 'Bearer ' + token
        env.update(headers)
        observed = []
        response = self.gateway(env, lambda status, head: observed.append((status, head)))
        return int(observed[0][0][:3]), json.loads(b''.join(response)), dict(observed[0][1])

    def test_post_ask_pending_and_authenticated_status(self):
        code, output, h = self.invoke()
        self.assertEqual(code, 202)
        self.assertEqual(output['state'], 'PENDING')
        self.assertEqual(h['Cache-Control'], 'no-store')
        self.assertEqual(self.adapter.get('R3')['value'], 'old')
        code, status, _ = self.invoke('/v1/requests/' + output['requestId'], method='GET')
        self.assertEqual((code, status['state']), (200, 'PENDING'))

    def test_http_free_runs_same_executor(self):
        self.action['operation'] = 'set_free'
        code, output, _ = self.invoke()
        self.assertEqual((code, output['state']), (200, 'EXECUTED'))
        self.assertEqual(self.adapter.get('R3')['value'], 'new')

    def test_anonymous_and_spoofed_request_rejected(self):
        self.assertEqual(self.invoke(token=None)[0], 401)
        self.assertEqual(self.invoke(token='wrong')[0], 403)
        self.action['actor'] = 'owner'
        self.assertEqual(self.invoke()[0], 403)
        self.assertEqual(self.adapter.get('R3')['version'], 0)

    def test_no_owner_route_or_arbitrary_forwarding(self):
        self.assertEqual(self.invoke('/v1/approve')[0], 404)
        self.assertEqual(self.invoke('/api/proxy')[0], 404)
        self.assertEqual(self.invoke('/v1/actions', method='DELETE')[0], 404)
        self.assertEqual(self.invoke('/v1/actions', HTTP_ORIGIN='https://evil.test')[0], 403)
        self.assertEqual(self.invoke('/v1/actions', HTTP_HOST='evil.test')[0], 403)
        self.assertEqual(self.invoke('/v1/actions', HTTP_X_FORWARDED_HOST='evil.test')[0], 403)

    def test_size_and_invalid_json_fail_closed(self):
        self.assertEqual(self.invoke(body=b'{' )[0], 400)
        self.assertEqual(self.invoke(body=b'a'*32769)[0], 413)
        self.assertEqual(self.invoke(CONTENT_TYPE='text/plain')[0], 400)

    def test_duplicate_nonfinite_and_deep_json_are_denied_before_core(self):
        raw = json.dumps(self.action).encode()
        duplicate = raw.replace(
            b'"requestId":', b'"requestId":"00000000-0000-4000-8000-000000000001","requestId":', 1)
        nonfinite = raw.replace(b'"value": "new"', b'"value": NaN', 1)
        deeply_nested = b'{"nested":' + b'[' * 1200 + b'0' + b']' * 1200 + b'}'
        for body in (duplicate, nonfinite, deeply_nested):
            with self.subTest(body=body[:32]):
                self.assertEqual(self.invoke(body=body)[0], 400)
        with self.core._db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
