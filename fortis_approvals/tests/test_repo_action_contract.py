"""Fortis Repo -> Approvals typed intent stage-1, entirely in memory/offline."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from fortis_approvals.core import Denied, Conflict
from fortis_approvals.repo_action_contract import RepoIntentBroker, validate_intent
from fortis_approvals.unified_lab import (build_unified_offline_lab, LAB_PROJECT,
    LAB_ISSUE, LAB_ORIGIN, SYNTHETIC_CREDENTIAL, SONAR_CREDENTIAL)
from test_g4_write_security import G4VirtualKey


class RepoActionContractTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='fortis-repo-action-contract-')
        self.addCleanup(temp.cleanup)
        state = Path(temp.name) / 'state'
        state.mkdir(mode=0o700)
        state.chmod(0o700)
        self.core,self.owner,self.synthetic,self.sonar,self.portal,self.fake=(
            build_unified_offline_lab(state))
        self.synthetic.seed('REC-FREE','before')
        self.synthetic.seed('REC-ASK','before')
        self.synthetic.seed('REC-DENY','before')
        self.broker=RepoIntentBroker(self.core,actor_operations={
            'lab-synthetic-actor':{('synthetic','set_free'),
                                   ('synthetic','set_ask'),('synthetic','set_deny')},
            'lab-sonar-actor':{('sonarcloud','accept_issue')},
        })
        self.key=G4VirtualKey()
        self.cookie=None
        self.csrf=None

    @staticmethod
    def synthetic_intent(operation='set_ask', target='REC-ASK'):
        return {'requestId':str(uuid.uuid4()),'service':'synthetic',
                'operation':operation,'target':target,
                'params':{'value':'after','expectedVersion':0},
                'reason':'Repo action request: synthetic offline test'}

    @staticmethod
    def sonar_intent():
        return {'requestId':str(uuid.uuid4()),'service':'sonarcloud',
                'operation':'accept_issue','target':LAB_ISSUE,
                'params':{'projectKey':LAB_PROJECT},
                'reason':'Repo asks owner to review a fake Sonar Issue'}

    def portal_call(self,route,body):
        raw=json.dumps(body).encode()
        env={'HTTP_HOST':'localhost:18992','HTTP_ORIGIN':LAB_ORIGIN,
             'REQUEST_METHOD':'POST','PATH_INFO':route,'QUERY_STRING':'',
             'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(raw)),
             'wsgi.input':BytesIO(raw)}
        if self.cookie:
            env['HTTP_COOKIE']='fortis_owner='+self.cookie
            env['HTTP_X_FORTIS_CSRF']=self.csrf
        result=[]
        out=b''.join(self.portal(env,lambda status,headers:result.append(
            (int(status[:3]),dict(headers)))))
        return result[0][0],json.loads(out),result[0][1]

    def login(self):
        begin=self.portal_call('/v1/enroll/begin',
                  {'invitation':self.owner.issue_invitation()})[1]
        self.assertEqual(self.portal_call('/v1/enroll/finish',{
            'ceremonyId':begin['ceremonyId'],
            'response':self.key.enroll(begin)})[0],200)
        begin=self.portal_call('/v1/login/begin',{})[1]
        code,login,headers=self.portal_call('/v1/login/finish',{
            'ceremonyId':begin['ceremonyId'],
            'response':self.key.assert_(begin)})
        self.assertEqual(code,200)
        self.cookie=headers['Set-Cookie'].split(';')[0].split('=',1)[1]
        self.csrf=login['csrf']

    def test_allow_executes_immediately_through_existing_core(self):
        intent=self.synthetic_intent('set_free','REC-FREE')
        result=self.broker.submit(SYNTHETIC_CREDENTIAL,intent)
        self.assertEqual(result,{'requestId':intent['requestId'],'state':'EXECUTED'})
        self.assertEqual(self.broker.status(SYNTHETIC_CREDENTIAL,intent['requestId']),result)
        self.assertEqual([r['state'] for r in self.core.events(intent['requestId'])],
                         ['APPROVED','DISPATCHED','EXECUTED'])
        self.assertEqual(self.synthetic.get('REC-FREE')['version'],1)
        self.assertEqual(self.broker.submit(SYNTHETIC_CREDENTIAL,intent),result)
        self.assertEqual(self.synthetic.get('REC-FREE')['version'],1)

    def test_ask_waits_and_after_owner_approve_uses_same_core_execute(self):
        intent=self.synthetic_intent()
        result=self.broker.submit(SYNTHETIC_CREDENTIAL,intent)
        self.assertEqual(result['state'],'PENDING')
        self.assertEqual(self.synthetic.get('REC-ASK')['version'],0)
        self.login()
        row=self.core._read(intent['requestId'])
        code,approved,_=self.portal_call('/v1/owner/decision/session',{
            'requestId':row['requestId'],'fingerprint':row['fingerprint'],
            'decision':'approve'})
        self.assertEqual((code,approved['state']),(200,'EXECUTED'))
        self.assertEqual(self.broker.status(SYNTHETIC_CREDENTIAL,intent['requestId'])['state'],
                         'EXECUTED')
        self.assertEqual([r['state'] for r in self.core.events(intent['requestId'])],
                         ['PENDING','APPROVED','DISPATCHED','EXECUTED'])
        self.assertEqual(self.synthetic.get('REC-ASK')['version'],1)

    def test_sonar_uses_trusted_digest_and_stays_pending_write_disabled(self):
        intent=self.sonar_intent()
        self.assertNotIn('expectedIssueSha256',intent['params'])
        out=self.broker.submit(SONAR_CREDENTIAL,intent)
        self.assertEqual(out['state'],'PENDING')
        self.assertEqual(set(out),{'requestId','state'})
        stored=self.core._read(intent['requestId'])
        self.assertEqual(stored['request']['params']['transition'],'accept')
        self.assertRegex(stored['request']['params']['expectedIssueSha256'],
                         r'^[0-9a-f]{64}$')
        self.assertEqual(stored['request']['expectedVersion'],0)
        self.assertEqual(self.fake.posts,0)
        self.assertTrue(self.fake.calls)
        self.assertTrue(all(x[0]=='GET' for x in self.fake.calls))
        self.login()
        code,denied,_=self.portal_call('/v1/owner/decision/begin',{
            'requestId':out['requestId'],'decision':'approve'})
        self.assertEqual((code,denied['error']),
                         (403,'OWNER_OPERATION_WRITE_NOT_ENABLED'))
        code,begin,_=self.portal_call('/v1/owner/decision/begin',{
            'requestId':out['requestId'],'decision':'reject'})
        self.assertEqual(code,200)
        code,rejected,_=self.portal_call('/v1/owner/decision/finish',{
            'requestId':out['requestId'],'decision':'reject',
            'ceremonyId':begin['ceremonyId'],
            'response':self.key.assert_(begin)})
        self.assertEqual((code,rejected['state']),(200,'REJECTED'))
        self.assertEqual(self.broker.status(SONAR_CREDENTIAL,intent['requestId'])['state'],
                         'REJECTED')
        self.assertEqual(self.fake.posts,0)

    def test_deny_and_unknown_operations_cannot_dispatch(self):
        with self.assertRaisesRegex(Denied,'OPERATION_DENIED'):
            self.broker.submit(SYNTHETIC_CREDENTIAL,
                 self.synthetic_intent('set_deny','REC-DENY'))
        bad=self.synthetic_intent()
        bad['operation']='run_shell'
        with self.assertRaisesRegex(Denied,'REPO_OPERATION_NOT_SUPPORTED'):
            self.broker.submit(SYNTHETIC_CREDENTIAL,bad)
        self.assertEqual(self.synthetic.get('REC-DENY')['version'],0)
        self.assertEqual(self.fake.posts,0)

    def test_untrusted_extra_field_including_token_owner_approve_and_http_denied(self):
        for field,value in (
                ('approved',True),('actor','owner'),('policy','ALLOW'),
                ('sonarToken','do-not-send'),('bearerToken','do-not-send'),
                ('headers',{'Authorization':'Bearer fake'}),
                ('url','https://evil.invalid'),('method','POST'),
                ('approval',{'decision':'approve'}),('expectedIssueSha256','f'*64),
                ('expectedVersion',0),('transition','accept')):
            intent=self.sonar_intent()
            intent[field]=value
            with self.subTest(field=field),self.assertRaisesRegex(Denied,'SCHEMA_DENIED'):
                self.broker.submit(SONAR_CREDENTIAL,intent)
        self.assertFalse(self.fake.calls)
        self.assertEqual(self.fake.posts,0)

    def test_nested_params_cannot_request_custom_method_transition_or_secret(self):
        for extra in ({'transition':'falsepositive'},
                      {'token':'leak'}, {'method':'POST'},
                      {'url':'https://evil.invalid'},
                      {'expectedIssueSha256':'f'*64}, {'expectedVersion':0}):
            intent=self.sonar_intent()
            intent['params'].update(extra)
            with self.subTest(extra=extra),self.assertRaisesRegex(
                     Denied,'REPO_SONAR_PARAMS_DENIED'):
                self.broker.submit(SONAR_CREDENTIAL,intent)
        self.assertFalse(self.fake.calls)
        self.assertEqual(self.fake.posts,0)

    def test_actor_credentials_are_distinct_from_sonar_token_and_scoped(self):
        with self.assertRaisesRegex(Denied,'CLIENT_UNAUTHORIZED'):
            self.broker.submit('unknown-ingress-grant',self.sonar_intent())
        with self.assertRaisesRegex(Denied,'REPO_GRANT_DENIED'):
            self.broker.submit(SYNTHETIC_CREDENTIAL,self.sonar_intent())
        with self.assertRaisesRegex(Denied,'REPO_GRANT_DENIED'):
            self.broker.submit(SONAR_CREDENTIAL,self.synthetic_intent())
        self.assertFalse(self.fake.calls)
        self.assertEqual(self.fake.posts,0)

    def test_status_is_actor_scoped_and_without_sonar_issue_text(self):
        intent=self.sonar_intent()
        out=self.broker.submit(SONAR_CREDENTIAL,intent)
        self.assertEqual(out['state'],'PENDING')
        text=json.dumps(out)
        self.assertNotIn('synthetic unified preview',text)
        self.assertNotIn('beforeSha256',text)
        with self.assertRaisesRegex(Denied,'REQUEST_NOT_AVAILABLE'):
            self.broker.status(SYNTHETIC_CREDENTIAL,intent['requestId'])
        self.assertEqual(self.broker.status(SONAR_CREDENTIAL,intent['requestId']),out)

    def test_sonar_policy_must_be_ask_and_never_downgrade_to_allow(self):
        intent=self.sonar_intent()
        self.core.policies[('lab-sonar-actor','sonarcloud','accept_issue')]='ALLOW'
        with self.assertRaisesRegex(Denied,'REPO_SONAR_ASK_REQUIRED'):
            self.broker.submit(SONAR_CREDENTIAL,intent)
        self.assertEqual(self.core.owner_list(pending=False),[])
        self.assertEqual(self.fake.posts,0)
        self.assertFalse(self.fake.calls)

    def test_malformed_intent_types_and_uuid_fail_before_lookup(self):
        invalid=[None,[],{'requestId':None},
            dict(self.sonar_intent(),requestId=str(uuid.uuid4()).upper()),
            dict(self.sonar_intent(),target='https://evil.invalid/a'),
            dict(self.sonar_intent(),reason=''),
            dict(self.sonar_intent(),params={'projectKey':42}),
            dict(self.sonar_intent(),params={'projectKey':LAB_PROJECT,'foo':1}),
            dict(self.synthetic_intent(),params={'value':'ok','expectedVersion':True}),
            dict(self.synthetic_intent(),params={'value':'ok','expectedVersion':-1}),
            dict(self.synthetic_intent(),params={'value':'ok','expectedVersion':0,'cmd':'rm'}),
            dict(self.sonar_intent(),service=['sonarcloud']),
            dict(self.sonar_intent(),operation={'accept_issue':True}),
            dict(self.sonar_intent(),reason='bad-\ud800'),
            dict(self.synthetic_intent(),params={
                'value':'bad-\ud800','expectedVersion':0}),
        ]
        for item in invalid:
            with self.subTest(item=repr(item)[:70]),self.assertRaises(Denied):
                validate_intent(item)
        self.assertEqual(self.fake.posts,0)
        self.assertFalse(self.fake.calls)

    def test_duplicate_id_cannot_override_other_request_payload(self):
        intent=self.synthetic_intent()
        result=self.broker.submit(SYNTHETIC_CREDENTIAL,intent)
        altered=dict(intent,reason='different requested reason')
        with self.assertRaisesRegex(Conflict,'REQUEST_ID_CONFLICT'):
            self.broker.submit(SYNTHETIC_CREDENTIAL,altered)
        self.assertEqual(self.broker.status(SYNTHETIC_CREDENTIAL,intent['requestId']),result)

    def test_contract_does_not_install_runtime_listener(self):
        source=(Path(__file__).resolve().parents[1]/'repo_action_contract.py').read_text()
        for unsafe in ('SonarHTTPTransport(', 'bearer_token=', 'socket.socket(',
                       'serve_forever(', 'docker run', 'docker compose'):
            self.assertNotIn(unsafe,source)
        image=(Path(__file__).resolve().parents[1]/'deploy'/'Dockerfile-G4-Candidate').read_text()
        self.assertNotIn('repo_action_contract.py',image)


if __name__=='__main__':
    unittest.main()
