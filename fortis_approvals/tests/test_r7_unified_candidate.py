"""R7 source candidate: one Core and owner-WebAuthn-gated Sonar execution.

Offline fake Sonar only; no real token, Docker, Windows or live deployment.
Reuses R6 real-TLS/owner-WebAuthn read and proposal tests through R7 build.
"""
from io import BytesIO
import json
from pathlib import Path
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

from fortis_approvals.core import Denied
from fortis_approvals import r7_unified_server as server
from fortis_approvals.r7_unified_candidate import (
    ACTOR, G4_OPERATION, MARKER, build_r7_unified_candidate,
)
from test_r6_repo_sonar_read_to_approvals_tls_offline import (
    R6CompleteOfflineChainTests, CLIENT_GRANT, HOST, OWNER_HOST,
    ORG, PROJECT, ISSUE, ReadAndProposalFakeSonar, R5VirtualKey,
)
from test_r5_lifecycle_offline import create_test_identity


class R7RealTLSCandidateE2ETests(R6CompleteOfflineChainTests):
    """Every inherited R6 test now routes through R7 source composition."""

    def test_repo_typed_bridge_real_tls_read_ask_status_without_service_token(self):
        # A real HTTPS call from the proposed Repo client to the R7 listener.
        # The socket destination is redirected to the ephemeral TEST listener,
        # but TLS/SNI/hostname verification remains host.docker.internal.
        import socket
        from fortis_approvals import repo_sonar_tools as bridge
        grant_file=self.folder/'repo-grant'
        grant_file.write_text(CLIENT_GRANT+'\n')
        grant_file.chmod(0o600)
        original_socket=socket.create_connection
        def local_test_connect(address,timeout=None,source_address=None):
            if address[0]=='host.docker.internal':
                address=('127.0.0.1',self.machine.server_port)
            return original_socket(address,timeout=timeout,
                                   source_address=source_address)
        with (patch.object(bridge,'ENDPOINT','https://host.docker.internal:'+
                           str(self.machine.server_port)),
              patch('socket.create_connection',side_effect=local_test_connect)):
            gate=bridge.call('sonar.get_quality_gate',target=PROJECT,
                             grant_path=grant_file,
                             certificate_path=self.cert)
            self.assertEqual(gate['data']['status'],'ERROR')
            self.assertEqual(gate['data']['prShaBinding'],'NOT_VERIFIED_D2')
            issue=bridge.call('sonar.get_issue',target=ISSUE,
                              project_key=PROJECT,grant_path=grant_file,
                              certificate_path=self.cert)
            self.assertEqual(issue['data']['issue']['key'],ISSUE)
            req=str(uuid.uuid4())
            proposal=bridge.call(
                'sonar.propose_accept_issue',target=ISSUE,
                project_key=PROJECT,request_id=req,
                reason='Review one Sonar issue via limited Repo tool',
                grant_path=grant_file,certificate_path=self.cert)
            self.assertEqual(proposal,{'requestId':req,'state':'PENDING'})
            status=bridge.call('approvals.request_status',request_id=req,
                               grant_path=grant_file,
                               certificate_path=self.cert)
            self.assertEqual(status,proposal)
        self.assertEqual(self.fake.posts,0)
        self.assertIn(req,[x['requestId'] for x in self.core.owner_list()])
        grant_file.chmod(0o644)
        with self.assertRaisesRegex(Denied,'FORTIS_MACHINE_GRANT_FILE_INSECURE'):
            bridge.call('sonar.get_quality_gate',target=PROJECT,
                        grant_path=grant_file,certificate_path=self.cert)
        with self.assertRaisesRegex(Denied,'FORTIS_TOOL_NOT_SUPPORTED'):
            bridge.payload('sonar.raw_http',target='http://evil.invalid')
        with self.assertRaisesRegex(
                Denied,'FORTIS_PROPOSAL_STABLE_REQUEST_ID_REQUIRED'):
            bridge.payload('sonar.propose_accept_issue',
                           target=ISSUE,project_key=PROJECT)
        print('R7_FORTIS_REPO_TYPED_CLIENT_REAL_TLS_SOURCE_PASS')

    def test_repo_typed_bridge_two_actors_share_one_http_core_and_isolate_status(self):
        from fortis_approvals import repo_sonar_tools as bridge
        second_grant = 'R7-TEST-SECOND-ACTOR-GRANT-000002'
        second_actor = 'trusted-ai-actor-b'
        state = self.folder/'r7-two-actor-private'
        state.mkdir(mode=0o700)
        core,owner,portal,ingress=build_r7_unified_candidate(
            state=state,owner_origin='http://'+OWNER_HOST,
            ingress_host=HOST,ingress_grant=CLIENT_GRANT,
            actor_grants={CLIENT_GRANT: ACTOR, second_grant: second_actor},
            sonar_transport=self.fake,organizations=(ORG,))
        self.machine.set_app(ingress)
        first_file=self.folder/'repo-grant-a'
        second_file=self.folder/'repo-grant-b'
        unknown_file=self.folder/'repo-grant-unknown'
        for path, value in (
                (first_file, CLIENT_GRANT),
                (second_file, second_grant),
                (unknown_file, 'R7-TEST-UNKNOWN-ACTOR-GRANT-000003')):
            path.write_text(value+'\n')
            path.chmod(0o600)
        original_socket=__import__('socket').create_connection
        def local_test_connect(address,timeout=None,source_address=None):
            if address[0]=='host.docker.internal':
                address=('127.0.0.1',self.machine.server_port)
            return original_socket(address,timeout=timeout,
                                   source_address=source_address)
        read_calls = (
            ('sonar.list_projects', {'target': ORG}),
            ('sonar.list_issues', {'target': PROJECT}),
            ('sonar.get_issue', {'target': ISSUE, 'project_key': PROJECT}),
            ('sonar.get_quality_gate', {'target': PROJECT}),
        )
        request_id=str(uuid.uuid4())
        with (patch.object(bridge,'ENDPOINT','https://host.docker.internal:'+
                           str(self.machine.server_port)),
              patch('socket.create_connection',side_effect=local_test_connect)):
            for grant_file in (first_file, second_file):
                for tool, kwargs in read_calls:
                    with self.subTest(actor=grant_file.name, tool=tool):
                        result=bridge.call(
                            tool, grant_path=grant_file,
                            certificate_path=self.cert, **kwargs)
                        self.assertEqual(result['operation'], tool.split('.', 1)[1])
            for grant_file in (first_file, second_file):
                with self.assertRaisesRegex(Denied,'FORTIS_HTTP_403'):
                    bridge.call(
                        'sonar.get_quality_gate',target='foreign_project',
                        grant_path=grant_file,certificate_path=self.cert)
            with self.assertRaisesRegex(Denied,'FORTIS_HTTP_(401|403)'):
                bridge.call(
                    'sonar.get_quality_gate',target=PROJECT,
                    grant_path=unknown_file,certificate_path=self.cert)
            pending=bridge.call(
                'sonar.propose_accept_issue',target=ISSUE,
                project_key=PROJECT,request_id=request_id,
                reason='two actor HTTP boundary check',
                grant_path=first_file,certificate_path=self.cert)
            with self.assertRaisesRegex(Denied,'FORTIS_HTTP_403'):
                bridge.call(
                    'approvals.request_status',request_id=request_id,
                    grant_path=second_file,certificate_path=self.cert)
            status=bridge.call(
                'approvals.request_status',request_id=request_id,
                grant_path=first_file,certificate_path=self.cert)
        self.assertEqual(pending,{'requestId':request_id,'state':'PENDING'})
        self.assertEqual(status,pending)
        self.assertIs(portal.core,core)
        self.assertIs(ingress.broker.core,core)
        self.assertEqual(self.fake.posts,0)
        print('R7_FORTIS_REPO_TWO_ACTOR_HTTP_SOURCE_PASS')

    def test_repo_typed_proposal_reaches_owner_portal_and_rejects(self):
        from fortis_approvals import repo_sonar_tools as bridge
        grant_file=self.folder/'repo-grant-owner-reject'
        grant_file.write_text(CLIENT_GRANT+'\n')
        grant_file.chmod(0o600)
        original_socket=__import__('socket').create_connection
        def local_test_connect(address,timeout=None,source_address=None):
            if address[0]=='host.docker.internal':
                address=('127.0.0.1',self.machine.server_port)
            return original_socket(address,timeout=timeout,
                                   source_address=source_address)
        request_id=str(uuid.uuid4())
        with (patch.object(bridge,'ENDPOINT','https://host.docker.internal:'+
                           str(self.machine.server_port)),
              patch('socket.create_connection',side_effect=local_test_connect)):
            pending=bridge.call(
                'sonar.propose_accept_issue',target=ISSUE,
                project_key=PROJECT,request_id=request_id,
                reason='typed client owner reject acceptance',
                grant_path=grant_file,certificate_path=self.cert)
            self.assertEqual(pending,
                             {'requestId':request_id,'state':'PENDING'})
            self.assertEqual(self.owner_call('/v1/owner/pending')[0],403)
            self.owner_login()
            code,rows,_=self.owner_call('/v1/owner/pending')
            self.assertEqual(code,200)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['requestId'],request_id)
            self.assertEqual(rows[0]['state'],'PENDING')
            self.assertTrue(rows[0]['approvalAllowed'])
            code,begin,_=self.owner_call('/v1/owner/decision/begin',{
                'requestId':request_id,'decision':'reject'})
            self.assertEqual(code,200)
            code,rejected,_=self.owner_call('/v1/owner/decision/finish',{
                'requestId':request_id,'decision':'reject',
                'ceremonyId':begin['ceremonyId'],
                'response':self.key.assert_(begin)})
            self.assertEqual(code,200)
            self.assertEqual(rejected['state'],'REJECTED')
            status=bridge.call(
                'approvals.request_status',request_id=request_id,
                grant_path=grant_file,certificate_path=self.cert)
        self.assertEqual(status,
                         {'requestId':request_id,'state':'REJECTED'})
        self.assertEqual(self.fake.posts,0)
        print('R7_FORTIS_REPO_TYPED_PENDING_OWNER_REJECT_SOURCE_PASS')

    def test_one_tls_client_reads_quality_gate_issues_then_pending_owner_ask(self):
        for operation,target,params in (
            ('list_issues',PROJECT,{'page':1,'pageSize':2}),
            ('get_issue',ISSUE,{'projectKey':PROJECT}),
            ('get_quality_gate',PROJECT,{}),
        ):
            code,response=self.machine_call(
                '/v1/reads',self.intent(operation,target,params))
            self.assertEqual(code,200,response)
            self.assertEqual(response['operation'],operation)
        proposal=self.intent('accept_issue',ISSUE,{'projectKey':PROJECT})
        status,created=self.machine_call('/v1/actions',proposal)
        self.assertEqual((status,created['state']),(202,'PENDING'))
        self.assertEqual(self.fake.posts,0)
        self.owner_login()
        status,rows,_=self.owner_call('/v1/owner/pending')
        self.assertEqual(status,200)
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]['approvalAllowed'])
        self.assertTrue(rows[0]['requiresStrongProof'])
        status,begin,_=self.owner_call('/v1/owner/decision/begin',{
            'requestId':proposal['requestId'],'decision':'approve'})
        self.assertEqual(status,200)
        status,executed,_=self.owner_call('/v1/owner/decision/finish',{
            'requestId':proposal['requestId'],'decision':'approve',
            'ceremonyId':begin['ceremonyId'],
            'response':self.key.assert_(begin)})
        self.assertEqual(status,200,executed)
        self.assertEqual(executed['state'],'EXECUTED')
        self.assertEqual(executed['result']['readback']['status'],'ACCEPTED')
        self.assertEqual(self.fake.posts,1)
        status,public=self.machine_call(
            '/v1/requests/'+proposal['requestId'],method='GET')
        self.assertEqual((status,public['state']),(200,'EXECUTED'))
        print('R7_SINGLE_CORE_TLS13_OWNER_WEBAUTHN_EXECUTE_READBACK_PASS')

    def test_all_owner_approval_routes_disabled_but_strong_reject_works(self):
        proposal=self.intent('accept_issue',ISSUE,{'projectKey':PROJECT})
        status,created=self.machine_call('/v1/actions',proposal)
        self.assertEqual((status,created['state']),(202,'PENDING'))
        self.owner_login()
        pending=self.core._read(proposal['requestId'])
        status,body,_=self.owner_call('/v1/owner/decision/session',{
            'requestId':pending['requestId'],
            'fingerprint':pending['fingerprint'],'decision':'approve'})
        self.assertEqual(status,403)
        self.assertEqual(body['error'],'STRONG_PROOF_REQUIRED')
        self.assertEqual(self.fake.posts,0)
        status,begin,_=self.owner_call('/v1/owner/decision/begin',{
            'requestId':pending['requestId'],'decision':'approve'})
        self.assertEqual(status,200)
        status,executed,_=self.owner_call('/v1/owner/decision/finish',{
            'requestId':pending['requestId'],'decision':'approve',
            'ceremonyId':begin['ceremonyId'],
            'response':self.key.assert_(begin)})
        self.assertEqual(status,200,executed)
        self.assertEqual(executed['state'],'EXECUTED')
        self.assertEqual(self.fake.posts,1)
        print('R7_STRONG_WEBAUTHN_APPROVAL_REQUIRED_AND_EXECUTE_PASS')

    def setUp(self):
        super().setUp()
        self.fake=WritableR7SonarFake()
        state=self.folder/'r7-private'
        state.mkdir(mode=0o700)
        core,owner,portal,ingress=build_r7_unified_candidate(
            state=state,owner_origin='http://'+OWNER_HOST,
            ingress_host=HOST,ingress_grant=CLIENT_GRANT,
            sonar_transport=self.fake,organizations=(ORG,),
            project_keys=(PROJECT,))
        self.core,self.owner,self.portal,self.ingress=core,owner,portal,ingress
        self.machine.set_app(ingress)
        self.web.set_app(portal)
        self.assertEqual((state/MARKER).read_text(),
                         'fortis-r7-unified-v1\n')
        self.assertEqual(core.policies[(ACTOR,*G4_OPERATION)],'ASK')
        self.assertEqual(set(core.adapters),{'sonarcloud'})
        self.assertIs(portal.core,core)
        self.assertIs(ingress.broker.core,core)
        self.assertEqual(ingress.broker.actor_operations[ACTOR],
                         frozenset({G4_OPERATION}))
        self.assertFalse(portal.read_only_banner)
        self.assertNotIn(G4_OPERATION,portal.blocked_approvals)


class WritableR7SonarFake(ReadAndProposalFakeSonar):
    """Offline-only Sonar fake that permits one typed accept transition."""
    def call(self, method, path, params):
        if method == 'POST':
            self.posts += 1
            self.calls.append((method, path, dict(params)))
            if path != '/api/issues/do_transition' or set(params) != {'issue','transition'}:
                raise AssertionError('UNEXPECTED_TEST_WRITE_ROUTE')
            if params['transition'] != 'accept':
                raise AssertionError('UNEXPECTED_TEST_TRANSITION')
            matches = [row for row in self.issues[PROJECT]
                       if row['key'] == params['issue']]
            if len(matches) != 1 or matches[0]['issueStatus'] not in ('OPEN','CONFIRMED'):
                raise AssertionError('TEST_ISSUE_NOT_ACCEPTABLE')
            matches[0]['issueStatus'] = 'ACCEPTED'
            matches[0]['updateDate'] = '2026-11-02T12:00:00+0000'
            return {'issue': dict(matches[0])}
        return super().call(method, path, params)


class R7StandaloneSecurityTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='r7-acceptance-')
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.state=self.root/'private'
        self.state.mkdir(mode=0o700)
        self.sonar=WritableR7SonarFake()

    def build(self,*,state=None,orgs=(ORG,),grant=CLIENT_GRANT,
              actor_grants=None):
        return build_r7_unified_candidate(
            state=state or self.state,owner_origin='http://'+OWNER_HOST,
            ingress_host=HOST,ingress_grant=grant,organizations=orgs,
            actor_grants=actor_grants,sonar_transport=self.sonar,
            project_keys=(PROJECT,))

    @staticmethod
    def owner_call(portal,path,body=None,*,cookie=None,csrf=None):
        raw=json.dumps(body or {}).encode('utf-8')
        env={'HTTP_HOST':OWNER_HOST,
             'REQUEST_METHOD':'POST' if body is not None else 'GET',
             'PATH_INFO':path,'QUERY_STRING':'','wsgi.input':BytesIO(raw),
             'CONTENT_LENGTH':str(len(raw)),
             'CONTENT_TYPE':'application/json'}
        if body is not None:
            env['HTTP_ORIGIN']='http://'+OWNER_HOST
        if cookie:
            env['HTTP_COOKIE']='fortis_owner='+cookie
        if csrf:
            env['HTTP_X_FORTIS_CSRF']=csrf
        output=[]
        data=b''.join(portal(env,lambda status,headers:
                             output.append((status,dict(headers)))))
        return int(output[0][0][:3]),json.loads(data),output[0][1]

    def owner_login(self,portal,owner):
        key=R5VirtualKey()
        code,begin,_=self.owner_call(
            portal,'/v1/enroll/begin',{'invitation':owner.issue_invitation()})
        self.assertEqual(code,200)
        code,_,_=self.owner_call(portal,'/v1/enroll/finish',{
            'ceremonyId':begin['ceremonyId'],'response':key.enroll(begin)})
        self.assertEqual(code,200)
        code,begin,_=self.owner_call(portal,'/v1/login/begin',{})
        self.assertEqual(code,200)
        code,data,headers=self.owner_call(portal,'/v1/login/finish',{
            'ceremonyId':begin['ceremonyId'],'response':key.assert_(begin)})
        self.assertEqual(code,200)
        cookie=headers['Set-Cookie'].split(';',1)[0].split('=',1)[1]
        return key,cookie,data['csrf']

    def test_r7_two_actor_grants_share_one_core_and_isolate_status(self):
        second_grant = 'R7-TEST-SECOND-ACTOR-GRANT-000002'
        second_actor = 'trusted-ai-actor-b'
        core,_,_,ingress = self.build(actor_grants={
            CLIENT_GRANT: ACTOR, second_grant: second_actor})
        read = {
            'requestId': str(uuid.uuid4()), 'service': 'sonarcloud',
            'operation': 'get_quality_gate', 'target': PROJECT,
            'params': {}, 'reason': 'second actor read check'}
        first = ingress.broker.read(CLIENT_GRANT, read)
        second = ingress.broker.read(second_grant, dict(read,
            requestId=str(uuid.uuid4())))
        self.assertEqual(first['operation'], 'get_quality_gate')
        self.assertEqual(second['operation'], 'get_quality_gate')
        proposal_id = str(uuid.uuid4())
        proposal = {
            'requestId': proposal_id, 'service': 'sonarcloud',
            'operation': 'accept_issue', 'target': ISSUE,
            'params': {'projectKey': PROJECT},
            'reason': 'second actor proposal check'}
        pending = ingress.broker.submit(CLIENT_GRANT, proposal)
        self.assertEqual(pending['state'], 'PENDING')
        with self.assertRaisesRegex(Denied, 'REQUEST_NOT_AVAILABLE'):
            ingress.broker.status(second_grant, proposal_id)
        self.assertEqual(
            ingress.broker.status(CLIENT_GRANT, proposal_id)['state'], 'PENDING')
        self.assertEqual(self.sonar.posts, 0)

    def test_r7_writer_is_reachable_only_via_owner_approval_path(self):
        core,_,portal,ingress=self.build()
        writer=core.adapters['sonarcloud']
        self.assertIs(writer.transport,self.sonar)
        self.assertFalse(portal.read_only_banner)
        self.assertNotIn(G4_OPERATION,portal.blocked_approvals)
        pending=ingress.broker.submit(CLIENT_GRANT,{
            'requestId':str(uuid.uuid4()),'service':'sonarcloud',
            'operation':'accept_issue','target':ISSUE,
            'params':{'projectKey':PROJECT},
            'reason':'typed ASK must remain pending until owner proof'})
        self.assertEqual(pending['state'],'PENDING')
        self.assertEqual(self.sonar.posts,0)
        self.assertTrue(all(method=='GET' for method,_,_ in self.sonar.calls))

    def test_owner_webauthn_approval_executes_one_issue_and_confirms_readback(self):
        core,owner,portal,ingress=self.build()
        request_id=str(uuid.uuid4())
        pending=ingress.broker.submit(CLIENT_GRANT,{
            'requestId':request_id,'service':'sonarcloud',
            'operation':'accept_issue','target':ISSUE,
            'params':{'projectKey':PROJECT},
            'reason':'owner approves one exact Sonar issue transition'})
        self.assertEqual(pending,{'requestId':request_id,'state':'PENDING'})
        self.assertEqual(self.sonar.posts,0)
        key,cookie,csrf=self.owner_login(portal,owner)
        code,rows,_=self.owner_call(
            portal,'/v1/owner/pending',cookie=cookie)
        self.assertEqual(code,200)
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]['approvalAllowed'])
        self.assertTrue(rows[0]['requiresStrongProof'])
        self.assertEqual(rows[0]['policyVersion'],
                         'r7-p1-sonar-accept-issue-write-v1')
        code,begin,_=self.owner_call(portal,'/v1/owner/decision/begin',{
            'requestId':request_id,'decision':'approve'},
            cookie=cookie,csrf=csrf)
        self.assertEqual(code,200)
        code,result,_=self.owner_call(portal,'/v1/owner/decision/finish',{
            'requestId':request_id,'decision':'approve',
            'ceremonyId':begin['ceremonyId'],
            'response':key.assert_(begin)},cookie=cookie,csrf=csrf)
        self.assertEqual(code,200,result)
        self.assertEqual(result['state'],'EXECUTED')
        self.assertEqual(result['decision'],'approve')
        self.assertEqual(result['result']['status'],'ACCEPTED')
        self.assertEqual(result['result']['readback']['status'],'ACCEPTED')
        self.assertEqual(self.sonar.posts,1)
        self.assertEqual(sum(1 for method,path,_ in self.sonar.calls
                             if method=='POST' and path=='/api/issues/do_transition'),1)
        self.assertEqual(core.events(request_id)[-1]['state'],'EXECUTED')

    def test_pending_created_under_old_policy_cannot_be_approved(self):
        core,owner,portal,_=self.build()
        writer=core.adapters['sonarcloud']
        issue=writer.read_issue(PROJECT,ISSUE)
        request_id=str(uuid.uuid4())
        legacy=type(core)(core.path,adapters=core.adapters,
            policies=core.policies,authenticator=core.auth,
            owner_verifier=owner,policy_version='r7-p1-read-ask-v0')
        body={'requestId':request_id,'service':'sonarcloud',
              'operation':'accept_issue','target':ISSUE,
              'params':{'projectKey':PROJECT,'transition':'accept',
                        'expectedIssueSha256':issue['sha256']},
              'expectedVersion':0,'reason':'legacy pending must not gain write rights'}
        created=legacy.client(CLIENT_GRANT,'submit',body)
        self.assertEqual(created['state'],'PENDING')
        row=core._read(request_id)
        self.assertEqual(row['policyVersion'],'r7-p1-read-ask-v0')
        self.assertFalse(portal._owner_view(row)['approvalAllowed'])
        with self.assertRaisesRegex(Denied,'OWNER_OPERATION_POLICY_CHANGED'):
            portal._approval_allowed(row,'approve')
        with self.assertRaisesRegex(Denied,'OWNER_POLICY_CHANGED'):
            core.owner_decide(request_id,'approve',{'not':'a WebAuthn proof'})
        self.assertEqual(core._read(request_id)['state'],'PENDING')
        self.assertEqual(self.sonar.posts,0)

    def test_r7_refuses_existing_a3_r5_g4_or_random_state(self):
        self.build()
        self.assertEqual((self.state/MARKER).read_bytes(),
                         b'fortis-r7-unified-v1\n')
        self.build()  # Only same trusted R7 private root is resumable.
        for legacy in ('.fortis-r5-sonar-read-v1','.g4-candidate-v1',
                       'owner.sqlite','approvals.sqlite'):
            folder=self.root/('foreign-'+legacy.strip('.'))
            folder.mkdir(mode=0o700)
            (folder/legacy).write_text('EXISTING_OWNER_STATE')
            with self.subTest(legacy=legacy),self.assertRaisesRegex(
                    Denied,'R7_FRESH_STATE_ONLY_NO_ADOPTION'):
                self.build(state=folder)
        self.state.chmod(0o755)
        with self.assertRaisesRegex(Denied,'R7_NEW_PRIVATE_STATE_REQUIRED'):
            self.build()

    def test_invalid_orgs_grant_and_state_before_bootstrap(self):
        for orgs in ([],(ORG,ORG),('evil/org',),('x',)*21):
            with self.subTest(orgs=orgs),self.assertRaises(ValueError):
                self.build(orgs=orgs)
        self.assertEqual(list(self.state.iterdir()),[])
        for grant in ('x','invalid token','https://bad.invalid'):
            with self.subTest(grant=grant),self.assertRaises(Denied):
                self.build(grant=grant)
        self.assertEqual(list(self.state.iterdir()),[])

    def test_r7_private_source_only_server_creates_isolated_listeners(self):
        grant=self.root/'grant';grant.write_text(CLIENT_GRANT+'\n');grant.chmod(0o600)
        token=self.root/'token'
        token.write_text('R7_TEST_REAL_SONAR_TOKEN_NOT_ALLOWED\n')
        token.chmod(0o600)
        cert=self.root/'cert.pem';key=self.root/'key.pem'
        create_test_identity(cert,key)
        with (patch.object(server,'OWNER_PORT',0),
              patch.object(server,'MACHINE_PORT',0),
              patch.object(server,'SonarHTTPTransport',return_value=self.sonar)):
            owner,machine=server.create_servers(
                state=self.state,grant_path=grant,sonar_token_path=token,
                cert_path=cert,key_path=key,region='eu',
                organizations=(ORG,),project_key=PROJECT,bind_host='127.0.0.1')
        try:
            self.assertGreater(owner.server_port,0)
            self.assertGreater(machine.server_port,0)
            self.assertIs(owner.get_app().core,machine.get_app().broker.core)
            self.assertEqual(
                owner.get_app().core.adapters.keys(),{'sonarcloud'})
            self.assertFalse(owner.get_app().read_only_banner)
        finally:
            owner.server_close();machine.server_close()

    def test_p1_server_requires_exact_project_before_secrets(self):
        for project in ('', 'https://evil.invalid', 'a/b', None):
            with self.subTest(project=project), self.assertRaisesRegex(
                    RuntimeError, 'R7_P1_EXACT_PROJECT_KEY_REQUIRED'):
                server.create_servers(
                    state=self.state, grant_path=self.root/'no-grant',
                    sonar_token_path=self.root/'no-token',
                    cert_path=self.root/'no-cert', key_path=self.root/'no-key',
                    region='eu', organizations=(ORG,), project_key=project)
        self.assertEqual(list(self.state.iterdir()), [])

    def test_p1_one_project_read_and_ask_deny_other_project(self):
        other_project = 'other_in_same_org'
        core, _, _, ingress = build_r7_unified_candidate(
            state=self.state, owner_origin='http://'+OWNER_HOST,
            ingress_host=HOST, ingress_grant=CLIENT_GRANT,
            sonar_transport=self.sonar, organizations=(ORG,),
            project_keys=(PROJECT,))
        read = lambda project: {
            'requestId': str(uuid.uuid4()), 'service': 'sonarcloud',
            'operation': 'get_quality_gate', 'target': project,
            'params': {}, 'reason': 'Owner-pinned project scope test'}
        self.assertEqual(ingress.broker.read(CLIENT_GRANT, read(PROJECT))
                         ['data']['projectKey'], PROJECT)
        with self.assertRaisesRegex(Denied, 'SONAR_READ_PROJECT_DENIED'):
            ingress.broker.read(CLIENT_GRANT, read(other_project))
        assert len(core.adapters['sonarcloud'].projects) == 1
        with self.assertRaisesRegex(Denied, 'SONAR_PROJECT_DENIED'):
            core.adapters['sonarcloud'].read_issue(other_project, ISSUE)
        proposal = {
            'requestId': str(uuid.uuid4()), 'service': 'sonarcloud',
            'operation': 'accept_issue', 'target': ISSUE,
            'params': {'projectKey': other_project},
            'reason': 'Foreign project must not create a pending request'}
        with self.assertRaisesRegex(Denied, 'SONAR_PROJECT_DENIED'):
            ingress.broker.submit(CLIENT_GRANT, proposal)
        self.assertEqual(core.owner_list(), [])
        self.assertEqual(self.sonar.posts, 0)

    def test_r7_docker_context_is_explicit_and_no_live_install(self):
        src=(Path(__file__).resolve().parents[1]/'deploy'/
             'Dockerfile-R7-Unified-Read-Ask-Candidate').read_text()
        for required in (
            'USER 10001:10001','EXPOSE 19103 19104',
            'fortis_approvals/r7_unified_candidate.py',
            'fortis_approvals/r7_unified_server.py',
            'fortis_approvals/requirements-owner.txt',
        ):
            self.assertIn(required,src)
        for forbidden in ('COPY . ', 'docker.sock','ARG SONAR',
                          'ENV SONAR_TOKEN','fortis_approvals/synthetic.py'):
            self.assertNotIn(forbidden,src)


if __name__=='__main__':
    unittest.main()
