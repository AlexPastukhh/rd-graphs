"""Unified logical Approvals: one Core/UI/WebAuthn for ALLOW/ASK and Sonar.

Only temporary state and fixed in-memory FakeSonar; no real Docker/network.
"""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from fortis_approvals.core import Denied
from fortis_approvals.g4_candidate import NoWriteTransport
from fortis_approvals.unified_lab import (build_unified_offline_lab,
    UnifiedFakeSonar, LAB_ORIGIN, LAB_ISSUE, LAB_PROJECT,
    SONAR_CREDENTIAL, SYNTHETIC_CREDENTIAL)
from test_g4_write_security import G4VirtualKey


class UnifiedApprovalsLabTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='fortis-unified-offline-')
        self.addCleanup(tmp.cleanup)
        self.state=Path(tmp.name)/'state'
        self.state.mkdir(mode=0o700)
        self.state.chmod(0o700)
        self.core,self.owner,self.synthetic,self.sonar_adapter,self.portal,self.fake=(
            build_unified_offline_lab(self.state))
        self.synthetic.seed('R-ALLOW','original')
        self.synthetic.seed('R-ASK','original')
        self.synthetic.seed('R-DENY','original')
        self.key=G4VirtualKey()
        self.cookie=None
        self.csrf=None

    def call(self,path,body=None, *, cookie=True, csrf=True, origin=True):
        raw=json.dumps(body or {}).encode()
        env={'HTTP_HOST':'localhost:18992',
             'REQUEST_METHOD':'POST' if body is not None else 'GET',
             'PATH_INFO':path,'QUERY_STRING':'','wsgi.input':BytesIO(raw),
             'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json'}
        if origin and body is not None:env['HTTP_ORIGIN']=LAB_ORIGIN
        if cookie and self.cookie:env['HTTP_COOKIE']='fortis_owner='+self.cookie
        if csrf and self.csrf:env['HTTP_X_FORTIS_CSRF']=self.csrf
        ret=[]
        data=b''.join(self.portal(env,lambda status,headers:
            ret.append((int(status[:3]),dict(headers)))))
        self.assertTrue(ret)
        return ret[0][0],json.loads(data),ret[0][1]

    def login(self):
        code,begin,_=self.call('/v1/enroll/begin',
                               {'invitation':self.owner.issue_invitation()})
        self.assertEqual(code,200)
        code,_,_=self.call('/v1/enroll/finish',
            {'ceremonyId':begin['ceremonyId'],'response':self.key.enroll(begin)})
        self.assertEqual(code,200)
        code,begin,_=self.call('/v1/login/begin',{})
        self.assertEqual(code,200)
        code,session,headers=self.call('/v1/login/finish',
            {'ceremonyId':begin['ceremonyId'],'response':self.key.assert_(begin)})
        self.assertEqual(code,200)
        self.cookie=headers['Set-Cookie'].split(';')[0].split('=',1)[1]
        self.csrf=session['csrf']

    def synthetic_request(self, operation='set_ask', target='R-ASK'):
        return {'requestId':str(uuid.uuid4()),'service':'synthetic',
                'operation':operation,'target':target,
                'params':{'value':'changed'},'expectedVersion':0,
                'reason':'unified offline owner review'}

    def propose_sonar(self):
        read=self.sonar_adapter.read_issue(LAB_PROJECT,LAB_ISSUE)
        payload={'requestId':str(uuid.uuid4()),'service':'sonarcloud',
                 'operation':'accept_issue','target':LAB_ISSUE,
                 'params':{'projectKey':LAB_PROJECT,'transition':'accept',
                           'expectedIssueSha256':read['sha256']},
                 'expectedVersion':0,'reason':'unified fake Sonar owner review'}
        return self.core.client(SONAR_CREDENTIAL,'submit',payload)

    def test_one_owner_queue_and_history_for_both_services(self):
        auto=self.core.client(SYNTHETIC_CREDENTIAL,'submit',
            self.synthetic_request('set_free','R-ALLOW'))
        self.assertEqual(auto['state'],'EXECUTED')
        self.assertEqual(self.synthetic.get('R-ALLOW'),
                         {'value':'changed','version':1})
        local=self.core.client(SYNTHETIC_CREDENTIAL,'submit',
            self.synthetic_request())
        sonar=self.propose_sonar()
        self.assertEqual(local['state'],sonar['state'])
        self.assertEqual(local['state'],'PENDING')
        self.assertEqual(self.call('/v1/owner/pending')[0],403)
        self.login()
        code,rows,_=self.call('/v1/owner/pending')
        self.assertEqual(code,200)
        self.assertEqual({r['requestId'] for r in rows},
                         {local['requestId'],sonar['requestId']})
        services={r['request']['service']:r for r in rows}
        self.assertTrue(services['synthetic']['approvalAllowed'])
        self.assertFalse(services['synthetic']['requiresStrongProof'])
        self.assertFalse(services['sonarcloud']['approvalAllowed'])
        self.assertTrue(services['sonarcloud']['requiresStrongProof'])
        code,s_done,_=self.call('/v1/owner/decision/session',
            {'requestId':local['requestId'],'fingerprint':local['fingerprint'],
             'decision':'approve'})
        self.assertEqual((code,s_done['state']),(200,'EXECUTED'))
        self.assertEqual(self.synthetic.get('R-ASK')['version'],1)
        code,s_begin,_=self.call('/v1/owner/decision/begin',
            {'requestId':sonar['requestId'],'decision':'reject'})
        self.assertEqual(code,200)
        code,s_done,_=self.call('/v1/owner/decision/finish',
            {'requestId':sonar['requestId'],'decision':'reject',
             'ceremonyId':s_begin['ceremonyId'],
             'response':self.key.assert_(s_begin)})
        self.assertEqual((code,s_done['state']),(200,'REJECTED'))
        code,history,_=self.call('/v1/owner/history')
        self.assertEqual(code,200)
        self.assertEqual({h['requestId'] for h in history},
                         {auto['requestId'],local['requestId'],sonar['requestId']})
        self.assertEqual(self.fake.posts,0)
        self.assertEqual(self.fake.issue['issueStatus'],'OPEN')

    def test_sonar_approve_disabled_at_all_owner_routes(self):
        row=self.propose_sonar();self.login()
        for route,body in [
            ('/v1/owner/decision/session',
             {'requestId':row['requestId'],'fingerprint':row['fingerprint'],
              'decision':'approve'}),
            ('/v1/owner/decision/begin',
             {'requestId':row['requestId'],'decision':'approve'}),
            ('/v1/owner/decision/finish',
             {'requestId':row['requestId'],'decision':'approve',
              'ceremonyId':'bogus','response':{}})]:
            with self.subTest(route=route):
                code,_,_=self.call(route,body)
                self.assertEqual(code,403)
        self.assertEqual(self.fake.posts,0)
        self.assertEqual(self.core._read(row['requestId'])['state'],'PENDING')

    def test_single_executor_allow_and_ask_synthetic_and_deny(self):
        free=self.core.client(SYNTHETIC_CREDENTIAL,'submit',
             self.synthetic_request('set_free','R-ALLOW'))
        ask=self.core.client(SYNTHETIC_CREDENTIAL,'submit',self.synthetic_request())
        self.assertEqual([e['state'] for e in self.core.events(free['requestId'])],
                         ['APPROVED','DISPATCHED','EXECUTED'])
        self.assertEqual([e['state'] for e in self.core.events(ask['requestId'])],
                         ['PENDING'])
        with self.assertRaisesRegex(Denied,'OPERATION_DENIED'):
            self.core.client(SYNTHETIC_CREDENTIAL,'submit',
                             self.synthetic_request('set_deny','R-DENY'))
        self.login()
        self.assertEqual(self.call('/v1/owner/decision/session',
                         {'requestId':ask['requestId'],'fingerprint':ask['fingerprint'],
                          'decision':'approve'})[1]['state'],'EXECUTED')
        self.assertEqual([e['state'] for e in self.core.events(ask['requestId'])],
                         ['PENDING','APPROVED','DISPATCHED','EXECUTED'])
        self.assertEqual(self.core.execute(free['requestId'])['state'],'EXECUTED')
        self.assertEqual(self.core.execute(ask['requestId'])['state'],'EXECUTED')
        self.assertEqual(self.synthetic.get('R-ALLOW')['version'],1)
        self.assertEqual(self.synthetic.get('R-ASK')['version'],1)
        self.assertEqual(self.synthetic.get('R-DENY'),{'value':'original','version':0})
        self.assertEqual(self.fake.posts,0)

    def test_trusted_service_grants_are_independent(self):
        sonar=self.propose_sonar()
        wrong=dict(sonar['request'],requestId=str(uuid.uuid4()))
        with self.assertRaisesRegex(Denied,'OPERATION_DENIED'):
            self.core.client(SYNTHETIC_CREDENTIAL,'submit',wrong)
        with self.assertRaisesRegex(Denied,'OPERATION_DENIED'):
            self.core.client(SONAR_CREDENTIAL,'submit',self.synthetic_request())
        self.assertEqual(self.fake.posts,0)

    def test_unified_sonar_transport_cannot_post_even_directly(self):
        with self.assertRaisesRegex(Denied,'WRITE_DISABLED'):
            self.sonar_adapter.transport.call('POST','/api/issues/do_transition',
                 {'issue':LAB_ISSUE,'transition':'accept'})
        self.assertEqual(self.fake.posts,0)

    def test_restart_uses_one_existing_history_and_enrollment(self):
        before=self.propose_sonar()
        core2,owner2,syn2,sonar2,portal2,source2=build_unified_offline_lab(self.state)
        self.assertEqual(core2._read(before['requestId'])['state'],'PENDING')
        self.assertEqual(core2.owner_list()[0]['requestId'],before['requestId'])
        self.assertEqual(owner2.origin,LAB_ORIGIN)
        self.assertEqual(set(core2.adapters),{'synthetic','sonarcloud'})
        self.assertEqual(source2.posts,0)

    def test_state_migration_from_g2_or_g4_is_not_implicit(self):
        for filename in ('owner.sqlite','approvals.sqlite','.g4-candidate-v1'):
            with tempfile.TemporaryDirectory(prefix='fortis-existing-state-') as folder:
                state=Path(folder)
                state.chmod(0o700)
                (state/filename).write_text('not lab state')
                with self.subTest(filename=filename),self.assertRaisesRegex(
                    Denied,'EXISTING_STATE_DENIED'):
                    build_unified_offline_lab(state)
        with self.assertRaisesRegex(Denied,'TEST_ORIGIN_ONLY'):
            build_unified_offline_lab(self.state,origin='http://localhost:18990')
        with self.assertRaisesRegex(Denied,'SYNTHETIC_TRANSPORT_ONLY'):
            build_unified_offline_lab(self.state,sonar=object())

    def test_no_network_or_token_in_unified_lab_source(self):
        source=(Path(__file__).resolve().parents[1]/'unified_lab.py').read_text()
        for forbidden in ('SonarHTTPTransport(', 'bearer_token=',
                          'docker run','docker compose','import requests',
                          'urllib.request', 'socket.socket('):
            self.assertNotIn(forbidden,source)
        self.assertNotIn('unified_lab.py',
            (Path(__file__).resolve().parents[1]/'deploy'/'Dockerfile-G4-Candidate').read_text())


if __name__=='__main__':unittest.main()
