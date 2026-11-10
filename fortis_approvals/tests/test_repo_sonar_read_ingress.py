"""R3 source-only HTTP ingress: authenticated Sonar reads, never a Sonar token."""
from copy import deepcopy
from io import BytesIO
import json
import unittest
import uuid
from wsgiref.simple_server import make_server
from threading import Thread
import http.client

from fortis_approvals.core import Authenticator, Denied
from fortis_approvals.repo_action_contract import RepoIntentBroker, SONAR_READ_OPERATIONS
from fortis_approvals.repo_ingress import RepoIngress
from fortis_approvals.sonar_read import SonarReadAdapter
from fortis_approvals.sonar import SonarTransportError
from test_sonar_read_adapter import FakeRemote


READ_CREDENTIAL = 'synthetic-read-credential-strong'
OTHER_CREDENTIAL = 'synthetic-other-credential-strong'


class ReadCore:
    def __init__(self):
        self.auth = Authenticator({READ_CREDENTIAL: 'allowed-reader',
                                   OTHER_CREDENTIAL: 'other-reader'})
        self.lookups = 0
        self.client_calls = 0
        self.policies = {}

    def _policy(self, actor, query):
        self.lookups += 1
        allowed = actor == 'allowed-reader' and (
            query['target'] == 'trusted_org' or
            query['target'].startswith('trusted_project_'))
        return 'ALLOW' if allowed else 'DENY'

    def client(self, *_args, **_kwargs):
        self.client_calls += 1
        raise AssertionError('READ_MUST_NOT_DISPATCH_CORE')


class RepoReadIngressTests(unittest.TestCase):
    def setUp(self):
        self.remote = FakeRemote()
        self.reader = SonarReadAdapter(
            self.remote, organization_keys={'trusted_org'})
        self.core = ReadCore()
        self.broker = RepoIntentBroker(
            self.core, actor_operations={},
            actor_read_operations={'allowed-reader': SONAR_READ_OPERATIONS},
            read_adapter=self.reader)
        self.ingress = RepoIngress(self.broker, host='localhost:19433',
                                   allow_http_local_test=True,
                                   max_read_response_bytes=8192)

    @staticmethod
    def query(operation, target=None, params=None):
        catalog = {
            'list_projects': ('trusted_org', {'page': 1, 'pageSize': 3}),
            'list_issues': ('trusted_project_000',
                            {'page': 1, 'pageSize': 2}),
            'get_issue': ('trusted_project_000-I001',
                          {'projectKey': 'trusted_project_000'}),
            'get_quality_gate': ('trusted_project_000', {}),
        }
        default_target, default_params = catalog[operation]
        return {'requestId': str(uuid.uuid4()), 'service': 'sonarcloud',
                'operation': operation, 'target': target or default_target,
                'params': deepcopy(default_params if params is None else params),
                'reason': 'read issues, no external write requested'}

    def call(self, query=None, *, path='/v1/reads', method='POST',
             credential=READ_CREDENTIAL, extra=None, raw=None):
        if query is None:
            query = self.query('list_issues')
        if raw is None:
            raw = json.dumps(query, ensure_ascii=False).encode()
        env = {'HTTP_HOST': 'localhost:19433',
               'PATH_INFO': path, 'REQUEST_METHOD': method,
               'QUERY_STRING': '', 'wsgi.url_scheme': 'http',
               'REMOTE_ADDR': '127.0.0.1', 'wsgi.input': BytesIO(raw),
               'CONTENT_TYPE': 'application/json',
               'CONTENT_LENGTH': str(len(raw))}
        if credential is not None:
            env['HTTP_AUTHORIZATION'] = 'Bearer ' + credential
        if extra:
            env.update(extra)
        events = []
        answer = b''.join(self.ingress(env,lambda status, headers:
                           events.append((int(status[:3]),dict(headers)))))
        code, headers = events[0]
        return code, json.loads(answer), headers

    def test_all_four_reads_return_only_typed_projection_not_raw_upstream(self):
        for operation in ('list_projects', 'list_issues',
                          'get_issue', 'get_quality_gate'):
            with self.subTest(operation=operation):
                query = self.query(operation)
                code, result, headers = self.call(query)
                self.assertEqual(code, 200)
                self.assertEqual(set(result),
                                 {'requestId','service','operation','data'})
                self.assertEqual(result['requestId'], query['requestId'])
                self.assertEqual(result['operation'],operation)
                self.assertEqual(result['data']['operation'],operation)
                self.assertEqual(headers['Cache-Control'], 'no-store')
                self.assertEqual(headers['Vary'], 'Authorization')
                self.assertNotIn('MUST_NOT_LEAK',json.dumps(result))
                self.assertNotIn(READ_CREDENTIAL,json.dumps(result))
                self.assertNotIn('owner',json.dumps(result))
        self.assertEqual(self.core.client_calls, 0)
        self.assertTrue(all(m=='GET' for m,_,_ in self.remote.calls))

    def test_next_page_and_r2_project_scope_from_http(self):
        code, data,_ = self.call(self.query('list_issues',params={
                                          'page': 2,'pageSize': 10}))
        self.assertEqual(code,200)
        self.assertEqual((data['data']['total'],data['data']['nextPage'],
                          len(data['data']['issues'])),(123,3,10))
        code,denied,_ = self.call(self.query('list_projects',target='other_org'))
        self.assertEqual((code,denied),(403,{'error':'REPO_DENIED'}))
        before=len(self.remote.calls)
        code,denied,_ = self.call(self.query('list_issues',target='foreign_project'))
        self.assertEqual((code,denied),(403,{'error':'REPO_DENIED'}))
        self.assertEqual(len(self.remote.calls),before)

    def test_wrong_token_or_wrong_actor_never_calls_upstream(self):
        for credential in (None,'invalid-strong-credential',OTHER_CREDENTIAL):
            with self.subTest(credential=credential):
                code,report,_=self.call(credential=credential)
                self.assertIn(code,(401,403))
                self.assertNotIn(READ_CREDENTIAL,json.dumps(report))
        self.assertFalse(self.remote.calls)
        self.assertEqual(self.core.client_calls,0)

    def test_policy_change_ask_or_deny_fails_closed_without_remote(self):
        self.core._policy = lambda *_: 'ASK'
        self.assertEqual(self.call()[0],403)
        self.core._policy = lambda *_: 'DENY'
        self.assertEqual(self.call()[0],403)
        self.assertFalse(self.remote.calls)

    def test_default_reader_disabled_even_with_registered_grant(self):
        broker = RepoIntentBroker(
            self.core,actor_operations={},
            actor_read_operations={'allowed-reader': SONAR_READ_OPERATIONS})
        disabled=RepoIngress(broker,host='localhost:19433',
                             allow_http_local_test=True)
        before=self.ingress
        self.ingress=disabled
        try:
            self.assertEqual(self.call()[0],403)
        finally:
            self.ingress=before
        self.assertFalse(self.remote.calls)

    def test_wrong_adapter_type_cannot_be_installed(self):
        with self.assertRaisesRegex(ValueError,'REPO_TRUSTED_READ_ADAPTER_INVALID'):
            RepoIntentBroker(self.core,actor_operations={},
                             actor_read_operations={'allowed-reader':
                                                    SONAR_READ_OPERATIONS},
                             read_adapter=object())

    def test_action_route_rejects_read_and_read_route_rejects_mutation(self):
        self.assertEqual(self.call(path='/v1/actions')[0],403)
        mut=dict(self.query('get_issue'),operation='accept_issue',
                 params={'projectKey':'trusted_project_000'})
        self.assertEqual(self.call(mut)[0],403)
        self.assertEqual(self.call(method='GET')[0],404)
        self.assertEqual(self.call(path='/v1/owner/pending')[0],404)
        self.assertEqual(self.call(path='/api/proxy')[0],404)
        self.assertEqual(self.core.client_calls,0)
        self.assertFalse(self.remote.calls)

    def test_unknown_headers_json_shape_and_body_guards_fail_before_get(self):
        query=self.query('get_issue')
        for extra in ({'HTTP_COOKIE':'fortis_owner=other'},
                      {'HTTP_ORIGIN':'http://localhost:19433'},
                      {'QUERY_STRING':'url=https://invalid'},
                      {'HTTP_X_HTTP_METHOD_OVERRIDE':'GET'},
                      {'wsgi.url_scheme':'http','REMOTE_ADDR':'8.8.8.8'},
                      {'CONTENT_LENGTH':'99999'},
                      {'CONTENT_TYPE':'text/plain'}):
            with self.subTest(extra=extra):
                self.assertIn(self.call(query,extra=extra)[0],(403,413))
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'not json'):
            self.assertEqual(self.call(query,raw=raw)[0],403)
        poisoned=self.query('get_issue')
        poisoned['params']['token']='private'
        self.assertEqual(self.call(poisoned)[0],403)
        poisoned=self.query('get_issue')
        poisoned['url']='https://invalid'
        self.assertEqual(self.call(poisoned)[0],403)
        self.assertFalse(self.remote.calls)

    def test_rejects_oversized_page_without_streaming_partial_secrets(self):
        code,out,_=self.call(self.query('list_issues',params={
                              'page':1,'pageSize':100}))
        self.assertEqual((code,out),(413,{'error':'REPO_READ_RESPONSE_TOO_LARGE'}))
        self.assertNotIn('MUST_NOT_LEAK',json.dumps(out))
        self.assertEqual(self.core.client_calls,0)

    def test_rate_limit_is_shared_with_existing_ingress_actions(self):
        self.ingress = RepoIngress(
            self.broker,host='localhost:19433',
            allow_http_local_test=True,max_requests=1)
        self.assertEqual(self.call()[0],200)
        before=len(self.remote.calls)
        self.assertEqual(self.call()[0],429)
        self.assertEqual(len(self.remote.calls),before)

    def test_broker_denies_extraneous_fields_from_compromised_read_adapter(self):
        # The type is an actual trusted adapter. A coding mistake must not
        # turn a raw upstream object into the public result.
        self.reader.read = lambda _q: {
            'operation':'get_quality_gate','token':'DO_NOT_EMIT'}
        code,error,_=self.call(self.query('get_quality_gate'))
        self.assertEqual((code,error),(403,{'error':'REPO_DENIED'}))

    def test_broker_denies_nested_raw_issue_and_gate_fields(self):
        source = self.reader.read
        for operation in ('list_issues', 'get_issue',
                          'get_quality_gate', 'list_projects'):
            def contaminated(req, operation=operation):
                result = source(req)
                if operation == 'list_issues':
                    result['issues'][0]['token'] = 'SENSITIVE'
                elif operation == 'get_issue':
                    result['issue']['headers'] = {'Authorization': 'SENSITIVE'}
                elif operation == 'get_quality_gate':
                    result['conditions'][0]['rawToken'] = 'SENSITIVE'
                else:
                    result['projects'][0]['url'] = 'https://invalid.test'
                return result
            self.reader.read = contaminated
            with self.subTest(operation=operation):
                code,error,_=self.call(self.query(operation))
                self.assertEqual((code,error),(403,{'error':'REPO_DENIED'}))
                self.assertNotIn('SENSITIVE',json.dumps(error))
        self.reader.read = source

    def test_upstream_failure_returns_redacted_error(self):
        self.reader.read=lambda _q: (_ for _ in ()).throw(
            SonarTransportError('SONAR_HTTP_401'))
        code,error,_=self.call(self.query('get_quality_gate'))
        self.assertEqual((code,error),
                         (500,{'error':'REPO_OUTCOME_UNCONFIRMED'}))
        self.assertNotIn(READ_CREDENTIAL,json.dumps(error))

    def test_http_wire_loopback_is_source_only(self):
        server = make_server('127.0.0.1',0,self.ingress)
        port=server.server_port
        # Host is part of strict ingress validation. Isolated per-test binding.
        self.ingress.host='127.0.0.1:'+str(port)
        thread=Thread(target=server.handle_request,daemon=True)
        thread.start()
        conn=http.client.HTTPConnection('127.0.0.1',port,timeout=4)
        try:
            body=json.dumps(self.query('get_quality_gate')).encode()
            conn.request('POST','/v1/reads',body,
                         {'Host':'127.0.0.1:'+str(port),
                          'Content-Type':'application/json',
                          'Authorization':'Bearer '+READ_CREDENTIAL})
            response=conn.getresponse()
            self.assertEqual(response.status,200)
            out=json.loads(response.read())
            self.assertEqual(out['data']['status'],'ERROR')
            self.assertEqual(response.getheader('Cache-Control'),'no-store')
        finally:
            conn.close()
            server.server_close()
            thread.join(timeout=4)
        self.assertEqual(self.core.client_calls,0)


if __name__ == '__main__':
    unittest.main()
