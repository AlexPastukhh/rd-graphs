"""Synthetic Repo ingress WSGI and ephemeral *localhost* HTTP smoke only."""
from io import BytesIO
import http.client
import json
from threading import Thread
import unittest
from wsgiref.simple_server import make_server

from fortis_approvals.repo_ingress import RepoIngress
import test_repo_action_contract as contract_tests
from fortis_approvals.unified_lab import SONAR_CREDENTIAL, SYNTHETIC_CREDENTIAL


class RepoIngressTests(unittest.TestCase):
    portal_call = contract_tests.RepoActionContractTests.portal_call
    login = contract_tests.RepoActionContractTests.login
    synthetic_intent = staticmethod(contract_tests.RepoActionContractTests.synthetic_intent)
    sonar_intent = staticmethod(contract_tests.RepoActionContractTests.sonar_intent)

    def setUp(self):
        contract_tests.RepoActionContractTests.setUp(self)
        self.ingress = RepoIngress(self.broker,host='localhost:18992',
                                   allow_http_local_test=True)

    def call(self, path='/v1/actions', *, method='POST', data=None,
             credential=SYNTHETIC_CREDENTIAL, host='localhost:18992',
             scheme='http', remote='127.0.0.1', extra=None):
        if data is None:
            data = self.synthetic_intent()
        if isinstance(data, dict):
            data = json.dumps(data,ensure_ascii=False).encode('utf-8')
        env={'HTTP_HOST':host,'REQUEST_METHOD':method,'PATH_INFO':path,
             'QUERY_STRING':'','REMOTE_ADDR':remote,'wsgi.url_scheme':scheme,
             'wsgi.input':BytesIO(data),'CONTENT_TYPE':'application/json',
             'CONTENT_LENGTH':str(len(data))}
        if method=='GET':
            env['CONTENT_LENGTH']='0'
            env['CONTENT_TYPE']=''
        if credential is not None:
            env['HTTP_AUTHORIZATION']='Bearer '+credential
        if extra:
            env.update(extra)
        result=[]
        body=b''.join(self.ingress(env,lambda status,headers:
            result.append((int(status[:3]),dict(headers)))))
        self.assertTrue(result)
        return result[0][0],json.loads(body),result[0][1]

    def test_allow_and_ask_same_core_from_typed_http(self):
        free=self.synthetic_intent('set_free','REC-FREE')
        code,done,headers=self.call(data=free)
        self.assertEqual((code,done['state']),(200,'EXECUTED'))
        self.assertEqual(set(done),{'requestId','state'})
        self.assertEqual(headers['Cache-Control'],'no-store')
        ask=self.synthetic_intent()
        code,pending,_=self.call(data=ask)
        self.assertEqual((code,pending['state']),(202,'PENDING'))
        self.assertEqual(self.synthetic.get('REC-ASK')['version'],0)
        self.login()
        row=self.core._read(ask['requestId'])
        code,approved,_=self.portal_call('/v1/owner/decision/session',{
            'requestId':row['requestId'],'fingerprint':row['fingerprint'],
            'decision':'approve'})
        self.assertEqual((code,approved['state']),(200,'EXECUTED'))
        code,status,_=self.call('/v1/requests/'+ask['requestId'],method='GET')
        self.assertEqual((code,status['state']),(200,'EXECUTED'))
        self.assertEqual(self.synthetic.get('REC-ASK')['version'],1)
        self.assertEqual(self.synthetic.get('REC-FREE')['version'],1)

    def test_read_query_cannot_enter_action_route_before_r2(self):
        query=self.sonar_intent()
        query['operation']='list_issues'
        query['target']='trusted_org_project'
        query['params']={'page':1,'pageSize':20}
        code,body,_=self.call(data=query,credential=SONAR_CREDENTIAL)
        self.assertEqual((code,body),(403,{'error':'REPO_DENIED'}))
        self.assertFalse(self.fake.calls)
        self.assertEqual(self.fake.posts,0)

    def test_sonar_ask_is_only_pending_and_rejectable_without_post(self):
        req=self.sonar_intent()
        code,pending,_=self.call(data=req,credential=SONAR_CREDENTIAL)
        self.assertEqual((code,pending['state']),(202,'PENDING'))
        self.assertEqual(set(pending),{'requestId','state'})
        self.assertEqual(self.fake.posts,0)
        self.assertTrue(all(entry[0]=='GET' for entry in self.fake.calls))
        self.login()
        code,error,_=self.portal_call('/v1/owner/decision/begin',{
            'requestId':req['requestId'],'decision':'approve'})
        self.assertEqual(code,403)
        self.assertEqual(self.fake.posts,0)
        code,begin,_=self.portal_call('/v1/owner/decision/begin',{
            'requestId':req['requestId'],'decision':'reject'})
        self.assertEqual(code,200)
        code,denied,_=self.portal_call('/v1/owner/decision/finish',{
            'requestId':req['requestId'],'decision':'reject',
            'ceremonyId':begin['ceremonyId'],'response':self.key.assert_(begin)})
        self.assertEqual((code,denied['state']),(200,'REJECTED'))
        code,status,_=self.call('/v1/requests/'+req['requestId'],method='GET',
                                credential=SONAR_CREDENTIAL)
        self.assertEqual((code,status['state']),(200,'REJECTED'))
        self.assertEqual(self.fake.posts,0)

    def test_authentication_no_cookie_or_owner_routes(self):
        self.assertEqual(self.call(credential=None)[0],401)
        self.assertEqual(self.call(credential='wrong-token')[0],401)
        for route in ('/v1/owner/decision/finish','/v1/owner/pending',
                      '/v1/execute','/api/proxy','/healthz','/admin/token'):
            with self.subTest(route=route):
                self.assertEqual(self.call(path=route)[0],404)
        self.assertEqual(self.call(method='DELETE')[0],404)
        self.assertEqual(self.fake.posts,0)

    def test_one_client_cannot_use_other_client_status(self):
        req=self.sonar_intent()
        code,result,_=self.call(data=req,credential=SONAR_CREDENTIAL)
        self.assertEqual(code,202)
        code,error,_=self.call('/v1/requests/'+result['requestId'],method='GET')
        self.assertEqual((code,error['error']),(403,'REPO_DENIED'))
        code,result,_=self.call('/v1/requests/'+result['requestId'],method='GET',
                            credential=SONAR_CREDENTIAL)
        self.assertEqual((code,result['state']),(200,'PENDING'))

    def test_headers_proxy_origin_cookie_host_query_and_method_override_denied(self):
        injections=[{'HTTP_HOST':'evil.invalid'}, {'QUERY_STRING':'password=abc'},
            {'HTTP_X_FORWARDED_FOR':'127.0.0.1'},
            {'HTTP_X_FORWARDED_PROTO':'https'}, {'HTTP_FORWARDED':'for=localhost'},
            {'HTTP_COOKIE':'fortis_owner=forged'}, {'HTTP_ORIGIN':'http://evil.invalid'},
            {'HTTP_X_FORTIS_CSRF':'forged'}, {'HTTP_PROXY_AUTHORIZATION':'Bearer hi'},
            {'HTTP_X_HTTP_METHOD_OVERRIDE':'POST'},
            {'HTTP_TRANSFER_ENCODING':'chunked'},
            {'HTTP_X_REAL_IP':'127.0.0.1'},
            {'HTTP_X_FORWARDED_PREFIX':'/client'}, {'SCRIPT_NAME':'/fake'},
        ]
        for extra in injections:
            with self.subTest(extra=extra):
                self.assertEqual(self.call(extra=extra)[0],403)
        self.assertEqual(self.fake.posts,0)

    def test_https_required_unless_explicit_local_test(self):
        gateway=RepoIngress(self.broker,host='localhost:18992')
        old=self.ingress
        try:
            self.ingress=gateway
            self.assertEqual(self.call()[0],403)
            self.assertEqual(self.call(scheme='https')[0],202)
        finally:
            self.ingress=old
        self.assertEqual(self.call(remote='10.0.0.2')[0],403)
        self.assertEqual(self.call(scheme='ftp')[0],403)
        with self.assertRaisesRegex(ValueError,'LOCAL_TEST_HOST_REQUIRED'):
            RepoIngress(self.broker,host='fortis-repo.example',
                        allow_http_local_test=True)

    def test_json_duplicate_nan_type_mismatch_and_oversized_blocked(self):
        probes=[
            (b'{"requestId":"x","requestId":"y"}',403),
            (b'{"foo":{"bar":1,"bar":2}}',403),
            (b'{"x":NaN}',403),
            (b'{',403),
            (b'\xff\xfe',403),
            (b'{"actor":"owner","approved":true}',403),
            (b' '*8193,413),
        ]
        for data,expected in probes:
            with self.subTest(data=data[:25]):
                self.assertEqual(self.call(data=data)[0],expected)
        self.assertEqual(self.fake.posts,0)

    def test_length_and_content_type_and_get_body_rejected(self):
        for extra in ({'CONTENT_LENGTH':'-1'}, {'CONTENT_LENGTH':'00'},
                      {'CONTENT_LENGTH':'0'}, {'CONTENT_LENGTH':'oops'},
                      {'CONTENT_TYPE':'text/plain'},
                      {'CONTENT_LENGTH':'5000'}):
            with self.subTest(extra=extra):
                self.assertEqual(self.call(extra=extra)[0],403)
        req=self.synthetic_intent()
        self.broker.submit(SYNTHETIC_CREDENTIAL,req)
        self.assertEqual(self.call('/v1/requests/'+req['requestId'],method='GET',
                              extra={'CONTENT_LENGTH':'3'})[0],403)
        self.assertEqual(self.call(path='/v1/requests/not-a-uuid',method='GET')[0],404)
        self.assertEqual(self.fake.posts,0)

    def test_rate_limited_by_authenticated_actor_not_account_token(self):
        now=[0.0]
        self.ingress=RepoIngress(self.broker,host='localhost:18992',
            max_requests=2,rate_seconds=10,clock=lambda:now[0],
            allow_http_local_test=True)
        for i in range(2):
            self.assertEqual(self.call(method='GET',path='/v1/requests/'+
                self.synthetic_intent()['requestId'])[0],403)
        self.assertEqual(self.call()[0],429)
        # Actor scoped, not global.
        self.assertEqual(self.call(data=self.sonar_intent(),credential=SONAR_CREDENTIAL)[0],202)
        now[0]=11
        self.assertEqual(self.call(data=self.synthetic_intent())[0],202)
        self.assertEqual(self.fake.posts,0)

    def test_idempotency_and_conflict_returns_constant_error(self):
        req=self.synthetic_intent()
        self.assertEqual(self.call(data=req)[0],202)
        self.assertEqual(self.call(data=req)[0],202)
        changed=dict(req,reason='DIFFERENT')
        code,error,_=self.call(data=changed)
        self.assertEqual((code,error['error']),(409,'REPO_REQUEST_ID_CONFLICT'))
        self.assertEqual(self.synthetic.get('REC-ASK')['version'],0)

    def test_loopback_real_http_roundtrip_no_windows_or_service_token(self):
        # Uses a temporary 127.0.0.1 ephemeral port inside Fortis Repo's
        # own Linux test process, not the Windows owner's 18990/18991.
        server=make_server('127.0.0.1',0,lambda e,s:[b'NO_APP'])
        server.set_app(RepoIngress(self.broker,
            host='localhost:'+str(server.server_port),
            allow_http_local_test=True))
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            req=self.synthetic_intent('set_free','REC-FREE')
            payload=json.dumps(req).encode('utf-8')
            conn.request('POST','/v1/actions',payload,headers={
                'Host':'localhost:'+str(server.server_port),
                'Authorization':'Bearer '+SYNTHETIC_CREDENTIAL,
                'Content-Type':'application/json'})
            response=conn.getresponse()
            status=response.status
            body=json.loads(response.read())
            self.assertEqual((status,body['state']),(200,'EXECUTED'))
            self.assertEqual(set(body),{'requestId','state'})
            self.assertEqual(self.synthetic.get('REC-FREE')['version'],1)
            conn.request('GET','/v1/requests/'+req['requestId'],headers={
                'Host':'localhost:'+str(server.server_port),
                'Authorization':'Bearer '+SYNTHETIC_CREDENTIAL})
            resp=conn.getresponse()
            self.assertEqual(resp.status,200)
            self.assertEqual(json.loads(resp.read())['state'],'EXECUTED')
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertEqual(self.fake.posts,0)


if __name__ == '__main__':unittest.main()
