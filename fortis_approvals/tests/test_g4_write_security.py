"""G4 WRITE design gate: test-only Sonar + virtual FIDO2, never real network.

The deployed G4 is still blocked by NoWriteTransport/blocked_approvals.
These tests compose an IN-MEMORY/SYNTHETIC future decision boundary only.
They are not production WRITE implementation or owner authorization.
"""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from fortis_approvals.core import Authenticator, Core, Denied
from fortis_approvals.owner_auth import OwnerWebAuthn
from fortis_approvals.owner_portal import OwnerPortal
from fortis_approvals.sonar import SonarIssueAdapter
from test_owner_portal import VirtualKey
from test_sonar import FakeSonar

ORIGIN='http://localhost:18992'  # test-only, not Windows G2/G4
OPERATION=('sonarcloud','accept_issue')


class G4VirtualKey(VirtualKey):
    """Use isolated test origin; parent test credential defaults to G2 origin."""
    def client_data(self, opts, typ, *, origin=ORIGIN, cross_origin=False):
        return super().client_data(opts,typ,origin=origin,cross_origin=cross_origin)

    def assert_(self, begin, *, origin=ORIGIN, uv=True, cross_origin=False):
        return super().assert_(begin,origin=origin,uv=uv,cross_origin=cross_origin)


class WriteOnlySyntheticWebAuthnTests(unittest.TestCase):
    """Exercises future hypothetical WRITE behavior without a live executor."""

    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='g4-write-negative-test-')
        self.addCleanup(temp.cleanup)
        path=Path(temp.name)
        self.remote=FakeSonar()
        self.adapter=SonarIssueAdapter(self.remote,project_keys={'gd-cap'},
                                       receipt_store=path/'receipts.sqlite')
        self.owner=OwnerWebAuthn(path/'owner.sqlite',origin=ORIGIN)
        self.core=Core(path/'approvals.sqlite',adapters={'sonarcloud':self.adapter},
                       policies={OPERATION:'ASK'},
                       authenticator=Authenticator({'synthetic-test-only':'test-agent'}),
                       owner_verifier=self.owner)
        self.portal=OwnerPortal(self.core,self.owner,strong_operations={OPERATION})
        self.key=G4VirtualKey()
        self.cookie=None
        self.csrf=None

    def call(self, route, body=None, *, authenticated=True, csrf=True,
             origin=True, cookie_override=None):
        raw=json.dumps(body or {}).encode()
        env={'HTTP_HOST':'localhost:18992',
             'REQUEST_METHOD':'POST' if body is not None else 'GET',
             'PATH_INFO':route,'QUERY_STRING':'','wsgi.input':BytesIO(raw),
             'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json'}
        if body is not None and origin:env['HTTP_ORIGIN']=ORIGIN
        if authenticated and (self.cookie or cookie_override):
            env['HTTP_COOKIE']='fortis_owner='+(cookie_override or self.cookie)
        if csrf and self.csrf:env['HTTP_X_FORTIS_CSRF']=self.csrf
        headers=[]
        response=b''.join(self.portal(env,lambda status,info:headers.append(
            (int(status[:3]),dict(info)))))
        return headers[0][0],json.loads(response),headers[0][1]

    def enroll_and_login(self):
        code,begin,_=self.call('/v1/enroll/begin',
                 {'invitation':self.owner.issue_invitation()})
        self.assertEqual(code,200)
        self.assertEqual(self.call('/v1/enroll/finish',
            {'ceremonyId':begin['ceremonyId'],
             'response':self.key.enroll(begin)})[0],200)
        code,begin,_=self.call('/v1/login/begin',{})
        self.assertEqual(code,200)
        code,login,headers=self.call('/v1/login/finish',
            {'ceremonyId':begin['ceremonyId'],'response':self.key.assert_(begin)})
        self.assertEqual(code,200)
        self.cookie=headers['Set-Cookie'].split(';')[0].split('=',1)[1]
        self.csrf=login['csrf']

    def submit(self):
        issue=self.adapter.read_issue('gd-cap','S1')
        payload={'requestId':str(uuid.uuid4()),'service':'sonarcloud',
                 'operation':'accept_issue','target':'S1',
                 'params':{'projectKey':'gd-cap','transition':'accept',
                           'expectedIssueSha256':issue['sha256']},
                 'expectedVersion':0,'reason':'synthetic security verification'}
        return self.core.client('synthetic-test-only','submit',payload)

    def begin(self, row, decision='approve'):
        return self.call('/v1/owner/decision/begin',
                         {'requestId':row['requestId'],'decision':decision})

    def finish(self, row, begin, decision='approve', *, request_id=None):
        return self.call('/v1/owner/decision/finish',
                         {'requestId':request_id or row['requestId'],
                          'decision':decision,'ceremonyId':begin['ceremonyId'],
                          'response':self.key.assert_(begin)})

    def test_web_authn_approve_only_after_strong_proof_exact_request_and_once(self):
        row=self.submit()
        self.enroll_and_login()
        self.assertEqual(self.call('/v1/owner/decision/session',{
            'requestId':row['requestId'],'fingerprint':row['fingerprint'],
            'decision':'approve'})[1]['error'],'STRONG_PROOF_REQUIRED')
        self.assertEqual(self.remote.posts,0)
        code,begin,_=self.begin(row)
        self.assertEqual(code,200)
        code,out,_=self.finish(row,begin)
        self.assertEqual((code,out['state']),(200,'EXECUTED'))
        self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.core.owner_list(pending=True),[])
        self.assertEqual(self.call('/v1/owner/history')[1][0]['requestId'],row['requestId'])
        self.assertEqual(self.call('/v1/owner/history')[1][0]['state'],'EXECUTED')
        self.assertEqual(self.call('/v1/owner/decision/finish',{
            'requestId':row['requestId'],'decision':'approve',
            'ceremonyId':begin['ceremonyId'],'response':self.key.assert_(begin)})[0],403)
        self.assertEqual(self.core.execute(row['requestId'])['state'],'EXECUTED')
        self.assertEqual(self.remote.posts,1)

    def test_anonymous_csrf_origin_and_session_shortcuts_cannot_approve(self):
        row=self.submit()
        self.assertEqual(self.begin(row)[0],403)
        self.enroll_and_login()
        for kwargs in ({'authenticated':False},{'csrf':False},
                       {'origin':False},{'cookie_override':'not-a-real-session'}):
            with self.subTest(kwargs=kwargs):
                code,_,_=self.call('/v1/owner/decision/begin',
                        {'requestId':row['requestId'],'decision':'approve'},**kwargs)
                self.assertEqual(code,403)
        self.assertEqual(self.remote.posts,0)
        self.assertEqual(self.core._read(row['requestId'])['state'],'PENDING')

    def test_cross_request_id_and_decision_binding_prevents_post(self):
        first=self.submit();second=self.submit()
        self.enroll_and_login()
        code,begin,_=self.begin(first)
        self.assertEqual(code,200)
        code,_,_=self.finish(first,begin,request_id=second['requestId'])
        self.assertEqual(code,403)
        self.assertEqual(self.remote.posts,0)
        self.assertEqual(self.core._read(first['requestId'])['state'],'PENDING')
        self.assertEqual(self.core._read(second['requestId'])['state'],'PENDING')
        code,begin,_=self.begin(first)
        self.assertEqual(code,200)
        code,_,_=self.finish(first,begin,decision='reject')
        self.assertEqual(code,403)
        self.assertEqual(self.remote.posts,0)

    def test_reject_then_approve_stays_rejected_and_zero_post(self):
        row=self.submit();self.enroll_and_login()
        code,begin,_=self.begin(row,'reject');self.assertEqual(code,200)
        code,rejected,_=self.finish(row,begin,'reject')
        self.assertEqual((code,rejected['state']),(200,'REJECTED'))
        self.assertEqual(self.begin(row)[0],403)
        self.assertEqual(self.remote.posts,0)

    def test_remote_stale_before_dispatch_never_post(self):
        row=self.submit();self.enroll_and_login()
        self.remote.issues['S1']['updateDate']='2026-11-01T00:00:00+0000'
        code,begin,_=self.begin(row)
        self.assertEqual(code,200)
        code,result,_=self.finish(row,begin)
        self.assertEqual((code,result['state']),(200,'STALE'))
        self.assertEqual(self.remote.posts,0)

    def test_post_commit_timeout_is_uncertain_and_never_retried(self):
        row=self.submit();self.enroll_and_login()
        self.remote.fail_after_post=True
        code,begin,_=self.begin(row)
        self.assertEqual(code,200)
        code,out,_=self.finish(row,begin)
        self.assertEqual((code,out['state']),(200,'UNCERTAIN'))
        self.assertEqual(self.remote.posts,1)
        self.assertIsNone(self.adapter.receipt(row['requestId']))
        self.assertEqual(self.core.reconcile(row['requestId'])['state'],'UNCERTAIN')
        self.assertEqual(self.core.execute(row['requestId'])['state'],'UNCERTAIN')
        self.assertEqual(self.remote.posts,1)

    def test_web_authn_without_user_verification_cannot_approve(self):
        row=self.submit();self.enroll_and_login()
        code,begin,_=self.begin(row)
        self.assertEqual(code,200)
        no_uv=self.key.assert_(begin,uv=False)
        code,denied,_=self.call('/v1/owner/decision/finish',{
            'requestId':row['requestId'],'decision':'approve',
            'ceremonyId':begin['ceremonyId'],'response':no_uv})
        self.assertEqual(code,403)
        self.assertIn(denied['error'],('WEBAUTHN_ASSERTION_FAILED',
                                       'WEBAUTHN_USER_VERIFICATION_REQUIRED'))
        self.assertEqual(self.core._read(row['requestId'])['state'],'PENDING')
        self.assertEqual(self.remote.posts,0)

    def test_transport_error_after_dispatch_is_uncertain_no_retry(self):
        row=self.submit();self.enroll_and_login()
        original=self.remote.call
        def outage(method,path,params):
            if method=='POST':
                self.remote.posts+=1
                from fortis_approvals.sonar import SonarTransportError
                raise SonarTransportError('SONAR_HTTP_429')
            return original(method,path,params)
        self.remote.call=outage
        code,begin,_=self.begin(row)
        self.assertEqual(code,200)
        code,result,_=self.finish(row,begin)
        self.assertEqual((code,result['state']),(200,'UNCERTAIN'))
        self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.core.execute(row['requestId'])['state'],'UNCERTAIN')
        self.assertEqual(self.core.reconcile(row['requestId'])['state'],'UNCERTAIN')
        self.assertEqual(self.remote.posts,1)

    def test_wrong_scope_action_and_forged_client_owner_fields_never_post(self):
        issue=self.adapter.read_issue('gd-cap','S1')
        skeleton={'requestId':str(uuid.uuid4()),'service':'sonarcloud',
                  'operation':'accept_issue','target':'S1',
                  'params':{'projectKey':'gd-cap','transition':'accept',
                            'expectedIssueSha256':issue['sha256']},
                  'expectedVersion':0,'reason':'synthetic only'}
        variants=[
            {'target':'other-issue'}, {'service':'admin'},
            {'operation':'delete_project'}, {'approved':True},
            {'actor':'owner'}, {'owner':'trusted'},
            {'params':dict(skeleton['params'],projectKey='other-project')},
            {'params':dict(skeleton['params'],transition='falsepositive')},
            {'params':dict(skeleton['params'],httpMethod='POST')},
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                payload=dict(skeleton,requestId=str(uuid.uuid4()),**variant)
                with self.assertRaises(Denied):
                    self.core.client('synthetic-test-only','submit',payload)
        self.assertEqual(self.remote.posts,0)

    def test_get_post_race_residual_risk_is_reproduced_with_fake_sonar(self):
        row=self.submit();self.enroll_and_login()
        real_call=self.remote.call
        def racing_call(method,path,params):
            if method=='POST':
                # Simulate an independent editor after Fortis last GET but
                # before Sonar's nonconditional transition POST.
                self.remote.issues['S1']['message']='concurrent edit after GET'
                self.remote.issues['S1']['updateDate']='2026-10-31T00:00:30+0000'
            return real_call(method,path,params)
        self.remote.call=racing_call
        code,begin,_=self.begin(row)
        self.assertEqual(code,200)
        code,out,_=self.finish(row,begin)
        # This is EXPECTED TO SUCCEED in today's general adapter, proving
        # an absent upstream CAS, NOT claiming concurrency protection.
        self.assertEqual((code,out['state']),(200,'EXECUTED'))
        self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.remote.issues['S1']['message'],'concurrent edit after GET')


if __name__=='__main__':
    unittest.main()
