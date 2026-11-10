"""G4 SonarCloud READ + one ASK transition, synthetic transport ONLY.

No real SonarCloud endpoints, tokens or network calls are used in this file.
"""
from copy import deepcopy
from pathlib import Path
from io import BytesIO
import json
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
import hashlib
import hmac
import tempfile
import unittest
import uuid

from fortis_approvals.core import Authenticator, Core, Denied, Stale
from fortis_approvals.sonar import SonarHTTPTransport, SonarIssueAdapter, SonarTransportError


class FakeSonar:
    def __init__(self):
        self.issues={'S1':dict(key='S1',project='gd-cap',issueStatus='OPEN',
                               updateDate='2026-10-31T00:00:00+0000',message='Investigate warning',
                               severity='MAJOR',rule='python:S100',component='gd-cap:src.py',
                               assignee=None,type='CODE_SMELL')}
        self.calls=[]
        self.posts=0
        self.fail_after_post=False
        self.fail_readback=False
        self.transition_keys=['accept','falsepositive']
        self.omit_transitions=False
        self.wrong_projection_on_transition_read=False

    def call(self,method,path,params):
        self.calls.append((method,path,deepcopy(params)))
        if method=='GET' and path=='/api/issues/search':
            if self.fail_readback and self.posts:
                raise SonarTransportError('SONAR_TRANSPORT_UNAVAILABLE')
            arr=[deepcopy(v) for v in self.issues.values() if v['project']==params['componentKeys']]
            if 'issues' in params: arr=[x for x in arr if x['key']==params['issues']]
            if 'additionalFields' in params:
                assert params['additionalFields']=='transitions'
                if self.wrong_projection_on_transition_read:
                    for row in arr:row['updateDate']='2026-11-01T11:11:11+0000'
                if not self.omit_transitions:
                    for row in arr:row['transitions']=deepcopy(self.transition_keys)
            return {'issues':arr[:int(params.get('ps','20'))]}
        if method=='POST' and path=='/api/issues/do_transition':
            assert set(params)=={'issue','transition'} and params['transition']=='accept'
            row=self.issues[params['issue']]
            self.posts+=1
            row['issueStatus']='ACCEPTED'
            row['updateDate']='2026-10-31T00:01:00+0000'
            if self.fail_after_post:
                raise TimeoutError('upstream timed out after commit')
            return {'issue':deepcopy(row)}
        raise AssertionError('unexpected outbound route: '+str((method,path,params)))


class TestOnlyVerifier:
    def __init__(self): self.key=b'REPO-TEST-ONLY-NOT-A-REAL-OWNER-CREDENTIAL'
    def proof(self,ident,fp,decision):
        return {'sig':hmac.new(self.key,f'{ident}/{fp}/{decision}'.encode(),hashlib.sha256).hexdigest()}
    def verify(self,ident,fp,decision,proof):
        if (not isinstance(proof,dict) or set(proof)!={'sig'} or
            not isinstance(proof['sig'],str) or
            not hmac.compare_digest(self.proof(ident,fp,decision)['sig'],proof['sig'])):
            raise Denied('TEST_OWNER_DENIED')
        return 'virtual-test-owner'


class SonarG4Test(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='fortis-g4-synthetic-')
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)
        self.remote=FakeSonar()
        self.adapter=SonarIssueAdapter(self.remote,project_keys={'gd-cap','obs-planning-docs'},
                                        receipt_store=self.path/'sonar-receipts.sqlite')
        self.auth=Authenticator({'client-G4-test':'agent-G4'})
        self.verifier=TestOnlyVerifier()
        self.core=Core(self.path/'core.sqlite',adapters={'sonarcloud':self.adapter},
                       policies={('sonarcloud','accept_issue'):'ASK'},
                       authenticator=self.auth,owner_verifier=self.verifier)

    def action(self, *,project='gd-cap', issue='S1', digest=None, **overrides):
        if digest is None:
            digest=self.adapter.read_issue(project,issue)['sha256']
        payload={'requestId':str(uuid.uuid4()),'service':'sonarcloud',
                 'operation':'accept_issue','target':issue,
                 'params':{'projectKey':project,'transition':'accept',
                           'expectedIssueSha256':digest},
                 'expectedVersion':0,'reason':'Review issue and accept for later'}
        payload.update(overrides)
        return payload

    def submit(self,**kwargs):return self.core.client('client-G4-test','submit',self.action(**kwargs))

    def decide(self,row, decision='approve'):
        return self.core.owner_decide(row['requestId'],decision,
            self.verifier.proof(row['requestId'],row['fingerprint'],decision))

    def test_read_issue_project_allowlist_pagination_and_no_write(self):
        row=self.adapter.read_issue('gd-cap','S1')
        self.assertEqual((row['status'],row['project'],row['key']),('OPEN','gd-cap','S1'))
        self.assertRegex(row['sha256'],r'^[0-9a-f]{64}$')
        self.assertEqual(len(self.adapter.list_issues('gd-cap',page=1,page_size=5)),1)
        self.assertEqual(self.adapter.list_issues('obs-planning-docs'),[])
        self.assertEqual(self.remote.posts,0)
        for x in self.remote.calls:
            self.assertEqual(x[0],'GET')
        with self.assertRaises(Denied):self.adapter.read_issue('other-project','S1')
        with self.assertRaises(Denied):self.adapter.list_issues('other-project')
        with self.assertRaises(Denied):self.adapter.list_issues('gd-cap',page_size=1000)

    def test_pending_shows_frozen_snapshot_before_owner_decision(self):
        row=self.submit()
        self.assertEqual(row['state'],'PENDING')
        self.assertEqual(row['preview']['before']['status'],'OPEN')
        self.assertEqual(row['preview']['after']['status'],'ACCEPTED')
        self.assertEqual(row['request']['params']['transition'],'accept')
        self.assertEqual(row['actor'],'agent-G4')
        self.assertEqual(self.remote.posts,0)
        self.assertEqual(self.core.client('client-G4-test','status',row['requestId'])['state'],'PENDING')

    def test_approve_one_dispatch_post_and_server_readback(self):
        row=self.submit()
        end=self.decide(row)
        self.assertEqual(end['state'],'EXECUTED')
        self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.remote.issues['S1']['issueStatus'],'ACCEPTED')
        self.assertEqual(end['result']['readback']['status'],'ACCEPTED')
        self.assertEqual(end['result']['requestId'],row['requestId'])
        self.assertEqual(self.adapter.receipt(row['requestId']),end['result'])
        self.assertTrue(self.adapter.confirm(row['requestId'],end['result']))
        self.assertEqual([v['state'] for v in self.core.events(row['requestId'])],
                         ['PENDING','APPROVED','DISPATCHED','EXECUTED'])
        self.assertEqual(self.core.execute(row['requestId'])['state'],'EXECUTED')
        self.assertEqual(self.remote.posts,1)

    def test_reject_and_direct_client_bypass_are_blocked(self):
        row=self.submit()
        self.assertEqual(self.decide(row,'reject')['state'],'REJECTED')
        self.assertEqual(self.remote.posts,0)
        with self.assertRaises(Denied):self.core.client('client-G4-test','approve',row['requestId'])
        with self.assertRaises(Denied):self.core.owner_decide(row['requestId'],'approve',{'approved':True})
        self.assertEqual(self.remote.posts,0)

    def test_spoofed_proof_cannot_dispatch(self):
        row=self.submit()
        with self.assertRaises(Denied):
            self.core.owner_decide(row['requestId'],'approve',{'sig':'incorrect'})
        self.assertEqual(self.remote.posts,0)
        self.assertEqual(self.core._read(row['requestId'])['state'],'PENDING')

    def test_nonallowlisted_project_and_custom_payloads_denied(self):
        for mutate in [lambda r:r['params'].update({'url':'https://attacker.test'}),
                       lambda r:r.update({'operation':'do_anything'}),
                       lambda r:r.update({'expectedVersion':4}),
                       lambda r:r['params'].update({'transition':'falsepositive'}),
                       lambda r:r.update({'service':'admin'}),
                       lambda r:r['params'].update({'httpMethod':'DELETE'})]:
            req=self.action();mutate(req)
            with self.subTest(req=req),self.assertRaises(Denied):
                self.core.client('client-G4-test','submit',req)
        req=self.action()
        req['params']['projectKey']='unknown-project'
        with self.assertRaises(Denied):self.core.client('client-G4-test','submit',req)
        self.assertEqual(self.remote.posts,0)

    def test_wrong_digest_or_changed_issue_is_stale(self):
        with self.assertRaises(Stale): self.submit(digest='0'*64)
        row=self.submit()
        self.remote.issues['S1']['updateDate']='2026-11-01T00:00:00+0000'
        out=self.decide(row)
        self.assertEqual(out['state'],'STALE')
        self.assertEqual(self.remote.posts,0)
        self.assertIsNone(self.adapter.receipt(row['requestId']))

    def test_transition_unavailable_blocks_mutation(self):
        self.remote.transition_keys=['falsepositive']
        with self.assertRaises(Denied):self.submit()
        self.assertEqual(self.remote.posts,0)

    def test_live_transition_format_is_exact_issue_search_not_legacy_route(self):
        row=self.submit()
        self.assertEqual(row['state'],'PENDING')
        searches=[(m,p,x) for m,p,x in self.remote.calls if 'additionalFields' in x]
        self.assertEqual(len(searches),1)
        self.assertEqual(searches[0],('GET','/api/issues/search',
            {'componentKeys':'gd-cap','issues':'S1','p':'1','ps':'2',
             'additionalFields':'transitions'}))
        self.assertTrue(all(p!='/api/issues/transitions' for _,p,_ in self.remote.calls))
        self.assertEqual(self.remote.posts,0)

    def test_missing_malformed_or_duplicate_transitions_fail_closed(self):
        variants=(None, 'accept', {}, ['accept','accept'], ['../accept'],
                  ['accept', None], [{'name':'accept'}],
                  ['accept']+['longkey'+str(n) for n in range(32)])
        for value in variants:
            with self.subTest(value=value):
                self.remote.transition_keys=value
                self.remote.omit_transitions=value is None
                with self.assertRaises(Denied):
                    self.submit()
                self.assertEqual(self.remote.posts,0)
        self.remote.omit_transitions=False
        self.remote.transition_keys=[{'key':'accept','name':'Accept'}]
        self.assertEqual(self.submit()['state'],'PENDING',
                         'bounded keyed-object legacy representation is still supported')

    def test_transition_read_stale_projection_cannot_create_ask_or_post(self):
        self.remote.wrong_projection_on_transition_read=True
        with self.assertRaises(Stale):
            self.submit()
        self.assertEqual(self.remote.posts,0)

    def test_changed_transition_at_decision_fails_closed_without_post(self):
        row=self.submit()
        self.remote.transition_keys=['falsepositive']
        decision=self.decide(row)
        self.assertEqual(decision['state'],'STALE')
        self.assertEqual(self.remote.posts,0)

    def test_issue_project_mismatch_duplicate_or_missing_denied(self):
        original=self.remote.call
        def poison(method,path,params):
            if path=='/api/issues/search':
                issue=deepcopy(self.remote.issues['S1']);issue['project']='evil'
                return {'issues':[issue]}
            return original(method,path,params)
        self.remote.call=poison
        with self.assertRaises(Denied):self.adapter.read_issue('gd-cap','S1')
        self.remote.call=lambda m,p,x: {'issues':[deepcopy(self.remote.issues['S1'])]*2}
        with self.assertRaises(Denied):self.adapter.read_issue('gd-cap','S1')
        self.remote.call=lambda m,p,x:{'issues':[]}
        with self.assertRaises(Denied):self.adapter.read_issue('gd-cap','S1')

    def test_unconfirmed_response_never_retries_and_reconcile_read_only(self):
        row=self.submit()
        self.remote.fail_after_post=True
        out=self.decide(row)
        self.assertEqual(out['state'],'UNCERTAIN')
        self.assertEqual(self.remote.posts,1)
        self.assertIsNone(self.adapter.receipt(row['requestId']))
        self.assertEqual(self.core.reconcile(row['requestId'])['state'],'UNCERTAIN')
        self.assertEqual(self.core.execute(row['requestId'])['state'],'UNCERTAIN')
        self.assertEqual(self.remote.posts,1)

    def test_post_success_but_readback_failure_is_uncertain_not_retried(self):
        row=self.submit();self.remote.fail_readback=True
        out=self.decide(row)
        self.assertEqual(out['state'],'UNCERTAIN')
        self.assertEqual(self.remote.posts,1)
        self.assertIsNone(self.adapter.receipt(row['requestId']))

    def test_confirmed_receipt_can_reconcile_lost_local_response(self):
        row=self.submit()
        apply=self.adapter.apply
        def crash_after_receipt(req):
            apply(req)
            raise TimeoutError('local process failed after committed receipt')
        self.adapter.apply=crash_after_receipt
        out=self.decide(row)
        self.assertEqual(out['state'],'UNCERTAIN')
        self.assertEqual(self.remote.posts,1)
        recovered=self.core.reconcile(row['requestId'])
        self.assertEqual(recovered['state'],'EXECUTED')
        self.assertEqual(self.remote.posts,1)

    def test_readback_must_match_issue_status(self):
        row=self.submit()
        original=self.remote.call
        def fake_post(m,p,v):
            if m=='POST':
                self.remote.posts+=1
                res=deepcopy(self.remote.issues['S1'])
                res['issueStatus']='ACCEPTED'
                return {'issue':res} # upstream lies about commit
            return original(m,p,v)
        self.remote.call=fake_post
        out=self.decide(row)
        self.assertEqual(out['state'],'UNCERTAIN')
        self.assertIsNone(self.adapter.receipt(row['requestId']))

    def test_policy_always_ask_even_if_client_requests_allow(self):
        row=self.submit()
        self.assertEqual(row['state'],'PENDING')
        req=self.action()
        req['approved']=True
        with self.assertRaises(Denied): self.core.client('client-G4-test','submit',req)
        self.assertEqual(self.remote.posts,0)

    def test_transport_pinned_https_bearer_and_form_encoding_without_network(self):
        class Response:
            status=200
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self,limit):return b'{"issue":{"key":"S1"}}'
        class Opener:
            def __init__(self):self.requests=[]
            def open(self,req,timeout):
                self.requests.append((req,timeout))
                return Response()
        for region,host in [('eu','sonarcloud.io'),('us','sonarqube.us')]:
            transport=SonarHTTPTransport(region=region,bearer_token='synthetic-token')
            fake=Opener();transport._opener=fake
            self.assertEqual(transport.call('GET','/api/issues/search',
                {'componentKeys':'gd-cap','issues':'S1','p':'1','ps':'2',
                 'additionalFields':'transitions'})['issue']['key'],'S1')
            self.assertEqual(transport.call('POST','/api/issues/do_transition',
                {'issue':'S1','transition':'accept'})['issue']['key'],'S1')
            get=fake.requests[0][0];post=fake.requests[1][0]
            self.assertEqual(urlsplit(get.full_url).hostname,host)
            self.assertEqual(urlsplit(post.full_url).hostname,host)
            self.assertEqual(get.get_header('Authorization'),'Bearer synthetic-token')
            self.assertEqual(parse_qs(urlsplit(get.full_url).query),
                             {'componentKeys':['gd-cap'],'issues':['S1'],
                              'p':['1'],'ps':['2'],'additionalFields':['transitions']})
            self.assertEqual(post.get_header('Authorization'),'Bearer synthetic-token')
            self.assertEqual(post.get_header('Content-type'),'application/x-www-form-urlencoded')
            self.assertEqual(parse_qs(post.data.decode()),{'issue':['S1'],'transition':['accept']})
            self.assertEqual(urlsplit(post.full_url).query,'')

    def test_transport_4xx_never_leaks_bearer_or_response_body(self):
        class BadOpener:
            def open(self,req,timeout):
                raise HTTPError(req.full_url,401,'invalid token private-secret',{},None)
        transport=SonarHTTPTransport(region='eu',bearer_token='private-secret')
        transport._opener=BadOpener()
        with self.assertRaises(SonarTransportError) as failure:
            transport.call('GET','/api/issues/search',{'componentKeys':'gd-cap'})
        self.assertEqual(str(failure.exception),'SONAR_HTTP_401')
        self.assertNotIn('private-secret',str(failure.exception))

    def test_transport_denies_custom_paths_regions_and_query_fields_without_network(self):
        with self.assertRaises(ValueError):SonarHTTPTransport(region='custom',bearer_token='fake-token')
        with self.assertRaises(ValueError):SonarHTTPTransport(region='eu',bearer_token='')
        transport=SonarHTTPTransport(region='eu',bearer_token='fake-token')
        for method,path,fields in [('DELETE','/api/issues/do_transition',{}),
                                    ('GET','/api/users/search',{}),
                                    ('GET','/api/issues/search',{'evil':'1'}),
                                    ('GET','/api/issues/search',{'additionalFields':'_all'}),
                                    ('GET','/api/issues/transitions',{'issue':'S1'}),
                                    ('POST','/api/issues/do_transition',{'issue':'S1','evil':'x'})]:
            with self.subTest(method=method,path=path),self.assertRaises(Denied):
                transport.call(method,path,fields)
        with self.assertRaises(ValueError):
            SonarIssueAdapter(transport,project_keys={'gd-cap'},receipt_store=self.path/'bad-region.sqlite',region='us')


class G4OwnerPortalTest(unittest.TestCase):
    """Actual owner WSGI + cryptographic test-only FIDO2 signing over Sonar ASK."""
    def test_sonar_pending_approved_by_logged_in_owner_not_client(self):
        from fido2.utils import websafe_encode
        from fortis_approvals.owner_auth import OwnerWebAuthn
        from fortis_approvals.owner_portal import OwnerPortal
        from test_owner_portal import VirtualKey  # TEST-ONLY P256 credential, not a human
        with tempfile.TemporaryDirectory(prefix='fortis-g4-portal-') as folder:
            path=Path(folder)
            remote=FakeSonar()
            adapter=SonarIssueAdapter(remote,project_keys={'gd-cap'},receipt_store=path/'receipts.sqlite')
            owner=OwnerWebAuthn(path/'credential.sqlite',origin='http://localhost:18990')
            core=Core(path/'requests.sqlite',adapters={'sonarcloud':adapter},
                      policies={('sonarcloud','accept_issue'):'ASK'},
                      authenticator=Authenticator({'test-client':'test-agent'}),owner_verifier=owner)
            portal=OwnerPortal(core,owner)
            key=VirtualKey()
            issue=adapter.read_issue('gd-cap','S1')
            req=dict(requestId=str(uuid.uuid4()),service='sonarcloud',operation='accept_issue',
                     target='S1',params={'projectKey':'gd-cap','transition':'accept',
                              'expectedIssueSha256':issue['sha256']},expectedVersion=0,
                     reason='Reviewed in synthetic test')
            row=core.client('test-client','submit',req)
            self.assertEqual(row['state'],'PENDING')
            def call(route, body=None, cookie=None, csrf=None):
                raw=json.dumps(body or {}).encode()
                env={'HTTP_HOST':'localhost:18990','REQUEST_METHOD':'POST' if body is not None else 'GET',
                     'PATH_INFO':route,'QUERY_STRING':'','wsgi.input':BytesIO(raw),
                     'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json'}
                if body is not None:env['HTTP_ORIGIN']='http://localhost:18990'
                if cookie:env['HTTP_COOKIE']='fortis_owner='+cookie
                if csrf:env['HTTP_X_FORTIS_CSRF']=csrf
                headers=[]
                answer=b''.join(portal(env,lambda status,h:headers.append((status,dict(h)))))
                return int(headers[0][0][:3]),json.loads(answer),headers[0][1]
            self.assertEqual(call('/v1/owner/pending')[0],403)
            code,begin,_=call('/v1/enroll/begin',{'invitation':owner.issue_invitation()})
            self.assertEqual(code,200)
            self.assertEqual(call('/v1/enroll/finish',{'ceremonyId':begin['ceremonyId'],
                'response':key.enroll(begin)})[0],200)
            code,begin,_=call('/v1/login/begin',{})
            self.assertEqual(code,200)
            code,login,headers=call('/v1/login/finish',{'ceremonyId':begin['ceremonyId'],
                'response':key.assert_(begin)})
            self.assertEqual(code,200)
            cookie=headers['Set-Cookie'].split(';')[0].split('=',1)[1]
            rows=call('/v1/owner/pending',cookie=cookie)[1]
            self.assertEqual(rows[0]['preview']['after']['status'],'ACCEPTED')
            self.assertEqual(call('/v1/owner/decision/session',{'requestId':row['requestId'],
              'fingerprint':row['fingerprint'],'decision':'approve'},cookie=cookie)[0],403)
            code,accepted,_=call('/v1/owner/decision/session',{'requestId':row['requestId'],
              'fingerprint':row['fingerprint'],'decision':'approve'},cookie=cookie,csrf=login['csrf'])
            self.assertEqual((code,accepted['state']),(200,'EXECUTED'))
            self.assertEqual(remote.posts,1)
            self.assertEqual(call('/v1/owner/history',cookie=cookie)[1][0]['state'],'EXECUTED')


if __name__=='__main__':unittest.main()
