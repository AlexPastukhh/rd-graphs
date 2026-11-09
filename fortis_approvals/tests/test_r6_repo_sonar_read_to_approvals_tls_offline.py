"""One-Core integration proof: simulated authorized AI -> Repo HTTPS ingress
-> Sonar GET quality-gate/issues -> Sonar ASK proposal -> owner WebAuthn queue.

OFFLINE / TEST-ONLY. Never connect to real Sonar or Windows, never mount a
token/volume, never enable an approve-to-POST path. This does NOT show that
arbitrary AI clients currently have an MCP tool or live access to Fortis.
"""
from io import BytesIO
import http.client
import json
from pathlib import Path
import socket
import ssl
import tempfile
from threading import Thread
import unittest
import uuid

from wsgiref.simple_server import make_server

from fortis_approvals.a3_server import TLSRepoServer
from fortis_approvals.core import Authenticator, Core, Denied
from fortis_approvals.g4_candidate import NoWriteTransport
from fortis_approvals.owner_auth import OwnerWebAuthn
from fortis_approvals.owner_portal import OwnerPortal
from fortis_approvals.repo_action_contract import RepoIntentBroker, SONAR_READ_OPERATIONS
from fortis_approvals.repo_ingress import RepoIngress
from fortis_approvals.server import OwnerHTTPServer, OwnerRequestHandler
from fortis_approvals.sonar import SonarIssueAdapter
from fortis_approvals.sonar_read import SonarReadAdapter
from test_sonar_read_adapter import FakeRemote
from test_r5_lifecycle_offline import create_test_identity, R5VirtualKey


CLIENT_GRANT = 'R6-TEST-ONLY-AUTHORIZED-AI-GRANT-000001'
GUEST_GRANT = 'R6-TEST-ONLY-UNAUTHORIZED-AI-GRANT-002'
ACTOR = 'trusted-ai-actor'
OPERATION = ('sonarcloud', 'accept_issue')
ORG = 'trusted_org'
PROJECT = 'trusted_project_000'
ISSUE = PROJECT + '-I007'
HOST = 'host.docker.internal:19104'
OWNER_HOST = 'localhost:19103'


class ReadAndProposalFakeSonar(FakeRemote):
    def __init__(self):
        super().__init__()
        self.posts = 0

    def call(self, method, path, params):
        if method != 'GET':
            self.posts += 1
            raise AssertionError('OFFLINE_SONAR_POST_FORBIDDEN')
        if params.get('additionalFields') == 'transitions':
            original = dict(params)
            del original['additionalFields']
            response = super().call(method, path, original)
            for issue in response['issues']:
                issue['transitions'] = ['accept']
            return response
        return super().call(method, path, params)


class R6CompleteOfflineChainTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='fortis-r6-single-core-')
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        private = self.folder/'private'
        private.mkdir(mode=0o700)
        self.fake = ReadAndProposalFakeSonar()
        self.reader = SonarReadAdapter(
            self.fake, organization_keys={ORG}, region='eu')
        self.writer = SonarIssueAdapter(
            NoWriteTransport(self.fake), organization_keys={ORG},
            receipt_store=private/'sonar-receipts.sqlite',region='eu')
        self.owner = OwnerWebAuthn(
            private/'owner.sqlite',origin='http://'+OWNER_HOST)
        policies = {(ACTOR, *action): 'ALLOW'
                    for action in SONAR_READ_OPERATIONS}
        policies[(ACTOR,*OPERATION)] = 'ASK'
        self.core = Core(private/'approvals.sqlite',
                         adapters={'sonarcloud':self.writer},
                         policies=policies,
                         authenticator=Authenticator({
                             CLIENT_GRANT:ACTOR,GUEST_GRANT:'unauthorized-ai'}),
                         owner_verifier=self.owner)
        self.portal = OwnerPortal(
            self.core,self.owner,strong_operations={OPERATION},
            blocked_approvals={OPERATION},read_only_banner=True)
        self.broker = RepoIntentBroker(
            self.core, actor_operations={ACTOR:{OPERATION}},
            actor_read_operations={ACTOR: SONAR_READ_OPERATIONS},
            read_adapter=self.reader)
        self.ingress = RepoIngress(self.broker,host=HOST)
        self.cert = self.folder/'tls.crt'
        key = self.folder/'tls.key'
        create_test_identity(self.cert,key)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.load_cert_chain(str(self.cert),str(key))
        self.web = make_server(
            '127.0.0.1',0,self.portal,server_class=OwnerHTTPServer,
            handler_class=OwnerRequestHandler)
        self.machine = make_server(
            '127.0.0.1',0,self.ingress,server_class=TLSRepoServer,
            handler_class=OwnerRequestHandler)
        self.machine.tls_context = context
        threads=[]
        for item in (self.web,self.machine):
            thread=Thread(target=item.serve_forever,daemon=True)
            thread.start()
            threads.append(thread)
        self.addCleanup(self.cleanup_services,self.web,self.machine,threads)
        self.key=R5VirtualKey()
        self.cookie=None
        self.csrf=None

    @staticmethod
    def cleanup_services(web,machine,threads):
        for item in (machine,web):
            item.shutdown()
        for thread in threads:
            thread.join(timeout=3)
            assert not thread.is_alive(), 'OFFLINE_SERVER_NOT_STOPPED'
        for item in (machine,web):
            item.server_close()

    @staticmethod
    def intent(operation, target, params):
        return {
            'requestId':str(uuid.uuid4()),'service':'sonarcloud',
            'operation':operation,'target':target,'params':params,
            'reason':'Offline AI checks Sonar and asks owner to review',
        }

    def machine_call(self,path,body=None,grant=CLIENT_GRANT,method='POST',
                     hostname='host.docker.internal',host=HOST):
        raw=json.dumps(body).encode('utf-8') if body is not None else None
        context=ssl.create_default_context(cafile=str(self.cert))
        context.minimum_version=ssl.TLSVersion.TLSv1_3
        with socket.create_connection(
                ('127.0.0.1',self.machine.server_port),timeout=4) as raw_sock:
            raw_sock.settimeout(4)
            with context.wrap_socket(
                    raw_sock,server_hostname=hostname) as tls:
                self.assertEqual(tls.version(),'TLSv1.3')
                conn=http.client.HTTPConnection('127.0.0.1')
                conn.sock=tls
                headers={'Host':host}
                if grant is not None:
                    headers['Authorization']='Bearer '+grant
                if body is not None:
                    headers['Content-Type']='application/json'
                conn.request(method,path,body=raw,headers=headers)
                response=conn.getresponse()
                return response.status,json.loads(response.read())

    def owner_call(self,path,body=None,*,cookie=True,csrf=True):
        raw=json.dumps(body or {}).encode('utf-8')
        headers={'Host':OWNER_HOST}
        if cookie and self.cookie:
            headers['Cookie']='fortis_owner='+self.cookie
        if body is not None:
            headers['Origin']='http://'+OWNER_HOST
            headers['Content-Type']='application/json'
            headers['Content-Length']=str(len(raw))
            if csrf and self.csrf:
                headers['X-Fortis-Csrf']=self.csrf
        conn=http.client.HTTPConnection('127.0.0.1',self.web.server_port,timeout=3)
        try:
            conn.request('POST' if body is not None else 'GET',path,
                         body=raw if body is not None else None,headers=headers)
            response=conn.getresponse()
            return response.status,json.loads(response.read()),dict(response.getheaders())
        finally:
            conn.close()

    def owner_login(self):
        code,begin,_=self.owner_call(
            '/v1/enroll/begin',{'invitation':self.owner.issue_invitation()})
        self.assertEqual(code,200)
        code,_,_=self.owner_call('/v1/enroll/finish',{
            'ceremonyId':begin['ceremonyId'],
            'response':self.key.enroll(begin)})
        self.assertEqual(code,200)
        code,begin,_=self.owner_call('/v1/login/begin',{})
        self.assertEqual(code,200)
        code,data,headers=self.owner_call('/v1/login/finish',{
            'ceremonyId':begin['ceremonyId'],
            'response':self.key.assert_(begin)})
        self.assertEqual(code,200)
        self.cookie=headers['Set-Cookie'].split(';',1)[0].split('=',1)[1]
        self.csrf=data['csrf']

    def test_one_tls_client_reads_quality_gate_issues_then_pending_owner_ask(self):
        for operation,target,params in (
            ('list_projects',ORG,{'page':1,'pageSize':2}),
            ('list_issues',PROJECT,{'page':1,'pageSize':2}),
            ('get_issue',ISSUE,{'projectKey':PROJECT}),
            ('get_quality_gate',PROJECT,{}),
        ):
            with self.subTest(operation=operation):
                req=self.intent(operation,target,params)
                status,response=self.machine_call('/v1/reads',req)
                self.assertEqual(status,200,response)
                self.assertEqual(set(response),
                                 {'requestId','service','operation','data'})
                self.assertEqual(response['operation'],operation)
                serialized=json.dumps(response)
                for forbidden in ('MUST_NOT_LEAK',CLIENT_GRANT,GUEST_GRANT,
                                  'owner.sqlite','approvals.sqlite',
                                  'expectedIssueSha256','Authorization'):
                    self.assertNotIn(forbidden,serialized)
                if operation=='get_quality_gate':
                    self.assertEqual(response['data']['status'],'ERROR')
                    self.assertEqual(
                        response['data']['prShaBinding'],'NOT_VERIFIED_D2')
                    self.assertEqual(
                        response['data']['scope'],'CURRENT_DEFAULT_BRANCH')
        self.assertEqual(self.core.owner_list(),[])
        intent=self.intent('accept_issue',ISSUE,{'projectKey':PROJECT})
        status,response=self.machine_call('/v1/actions',intent)
        self.assertEqual((status,response['state']),(202,'PENDING'))
        self.assertEqual(set(response),{'requestId','state'})
        self.assertEqual(self.fake.posts,0)
        self.assertEqual(self.core._read(intent['requestId'])['state'],'PENDING')
        pending=self.core.owner_list()
        self.assertEqual(len(pending),1)
        self.assertEqual(pending[0]['request']['service'],'sonarcloud')
        self.assertEqual(pending[0]['request']['params']['transition'],'accept')
        self.assertRegex(pending[0]['request']['params']['expectedIssueSha256'],
                         '^[0-9a-f]{64}$')
        self.assertEqual(self.owner_call('/v1/owner/pending')[0],403)
        self.owner_login()
        status,rows,_=self.owner_call('/v1/owner/pending')
        self.assertEqual(status,200)
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]['requiresStrongProof'])
        self.assertFalse(rows[0]['approvalAllowed'])
        self.assertEqual(rows[0]['requestId'],intent['requestId'])
        # All approve paths blocked. The owner may still reject.
        status,resp,_=self.owner_call('/v1/owner/decision/begin',{
            'requestId':intent['requestId'],'decision':'approve'})
        self.assertEqual(status,403)
        self.assertEqual(resp['error'],'OWNER_OPERATION_WRITE_NOT_ENABLED')
        self.assertEqual(self.machine_call(
            '/v1/requests/'+intent['requestId'],method='GET')[1]['state'],'PENDING')
        status,begin,_=self.owner_call('/v1/owner/decision/begin',{
            'requestId':intent['requestId'],'decision':'reject'})
        self.assertEqual(status,200)
        status,rejected,_=self.owner_call('/v1/owner/decision/finish',{
            'requestId':intent['requestId'],'decision':'reject',
            'ceremonyId':begin['ceremonyId'],
            'response':self.key.assert_(begin)})
        self.assertEqual((status,rejected['state']),(200,'REJECTED'))
        self.assertEqual(self.machine_call(
            '/v1/requests/'+intent['requestId'],method='GET')[1]['state'],
            'REJECTED')
        self.assertEqual(self.owner_call('/v1/owner/history')[1][0]['state'],
                         'REJECTED')
        self.assertEqual(self.fake.posts,0)
        self.assertTrue(all(call[0]=='GET' for call in self.fake.calls))
        print('R6_SINGLE_CORE_TLS13_READ_ASK_OWNER_REJECT_PASS')
        print('R6_NO_SONAR_WRITE_OR_REAL_TOKEN_PASS')

    def test_any_ai_means_granted_client_not_anonymous_and_no_bypass(self):
        read=self.intent('get_quality_gate',PROJECT,{})
        proposal=self.intent('accept_issue',ISSUE,{'projectKey':PROJECT})
        for grant in (None,'unknown-test-grant',GUEST_GRANT):
            with self.subTest(grant=grant):
                code,_=self.machine_call('/v1/reads',read,grant=grant)
                self.assertIn(code,(401,403))
                code,_=self.machine_call('/v1/actions',proposal,grant=grant)
                self.assertIn(code,(401,403))
        self.assertEqual(self.fake.calls,[])
        poisoned=dict(proposal,approved=True)
        self.assertEqual(self.machine_call('/v1/actions',poisoned)[0],403)
        poisoned=dict(proposal,params={'projectKey':PROJECT,'method':'POST'})
        self.assertEqual(self.machine_call('/v1/actions',poisoned)[0],403)
        poisoned=dict(proposal,params={'projectKey':PROJECT,'transition':'accept'})
        self.assertEqual(self.machine_call('/v1/actions',poisoned)[0],403)
        self.assertEqual(self.machine_call('/v1/reads',proposal)[0],403)
        self.assertEqual(self.machine_call('/v1/actions',read)[0],403)
        self.assertEqual(self.machine_call('/v1/owner/pending',
                                           method='GET')[0],404)
        self.assertEqual(self.machine_call('/v1/execute',proposal)[0],404)
        foreign=self.intent('get_quality_gate','foreign_project',{})
        self.assertEqual(self.machine_call('/v1/reads',foreign)[0],403)
        self.assertEqual(self.core.owner_list(),[])
        self.assertEqual(self.fake.posts,0)
        print('R6_NO_UNAUTHORIZED_AI_OR_OWNER_API_BYPASS_PASS')

    def test_all_owner_approval_routes_disabled_but_strong_reject_works(self):
        proposal=self.intent('accept_issue',ISSUE,{'projectKey':PROJECT})
        status,created=self.machine_call('/v1/actions',proposal)
        self.assertEqual((status,created['state']),(202,'PENDING'))
        self.owner_login()
        with self.assertRaises(Denied):
            self.writer.transport.call(
                'POST','/api/issues/do_transition',
                {'issue':ISSUE,'transition':'accept'})
        pending=self.core._read(proposal['requestId'])
        for path,body in (
            ('/v1/owner/decision/session',{
                'requestId':pending['requestId'],
                'fingerprint':pending['fingerprint'],
                'decision':'approve'}),
            ('/v1/owner/decision/begin',{
                'requestId':pending['requestId'],'decision':'approve'}),
            ('/v1/owner/decision/finish',{
                'requestId':pending['requestId'],'decision':'approve',
                'ceremonyId':'fake','response':{}}),
        ):
            with self.subTest(path=path):
                code,body,_=self.owner_call(path,body)
                self.assertEqual(code,403)
                self.assertEqual(body['error'],'OWNER_OPERATION_WRITE_NOT_ENABLED')
        self.assertEqual(self.core._read(proposal['requestId'])['state'],'PENDING')
        self.assertEqual(self.fake.posts,0)
        print('R6_OWNER_APPROVAL_ALL_ROUTES_WRITE_DISABLED_PASS')

    def test_ask_is_idempotent_and_status_actor_bound(self):
        proposal=self.intent('accept_issue',ISSUE,{'projectKey':PROJECT})
        code,first=self.machine_call('/v1/actions',proposal)
        self.assertEqual((code,first['state']),(202,'PENDING'))
        code,again=self.machine_call('/v1/actions',proposal)
        self.assertEqual((code,again),(202,first))
        self.assertEqual(len(self.core.owner_list()),1)
        other=dict(proposal,reason='a changed untrusted reason')
        self.assertEqual(self.machine_call('/v1/actions',other)[0],409)
        self.assertIn(self.machine_call(
            '/v1/requests/'+proposal['requestId'],grant=GUEST_GRANT,
            method='GET')[0],(401,403))
        self.assertEqual(self.fake.posts,0)
        print('R6_REQUEST_DEDUPE_ACTOR_STATUS_ISOLATION_PASS')


if __name__=='__main__':
    unittest.main()
