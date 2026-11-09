"""G4 isolated candidate: real G2 portal routes, fake Sonar, zero HTTP writes."""
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fortis_approvals.core import Denied
from fortis_approvals.g4_candidate import (
    build_candidate, propose_issue, NoWriteTransport, OPERATOR_CREDENTIAL)
from test_owner_portal import VirtualKey


class FakeScopedSonar:
    def __init__(self):
        self.calls=[]
        self.posts=0
        self.issues={'S1':{'key':'S1','project':'AlexPastukhh_gd-cap','issueStatus':'OPEN',
            'updateDate':'2026-10-31T01:00:00+0000','message':'example private finding',
            'rule':'python:S111','severity':'MAJOR','component':'gd-cap:src.py',
            'assignee':None,'type':'CODE_SMELL'}}
        self.transitions=['accept','falsepositive']

    def call(self,method,path,params):
        self.calls.append((method,path,dict(params)))
        if method=='POST':
            self.posts+=1
            raise AssertionError('POST reached synthetic Sonar')
        if method=='GET' and path=='/api/components/search':
            org=params['organization']
            matches=[{'qualifier':'TRK','organization':org,'key':'AlexPastukhh_gd-cap'}] if org=='alexpastukhh' else []
            if 'q' in params:matches=[m for m in matches if m['key']==params['q']]
            return {'components':matches,'paging':{'pageIndex':1,'total':len(matches)}}
        if method=='GET' and path=='/api/issues/search':
            rows=[dict(row) for row in self.issues.values()
                  if row['project']==params.get('componentKeys') and
                  ('issues' not in params or row['key']==params['issues'])]
            if params.get('additionalFields')=='transitions':
                for row in rows:row['transitions']=list(self.transitions)
            return {'issues':rows}
        raise AssertionError('Unexpected remote call')


class G4CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='fortis-isolated-g4-')
        self.addCleanup(self.tmp.cleanup)
        self.state=Path(self.tmp.name)/'state';self.state.mkdir(mode=0o700)
        self.state.chmod(0o700)
        self.env=patch.dict(os.environ,{
            'FORTIS_STATE_DIR':str(self.state),
            'FORTIS_OWNER_ORIGIN':'http://localhost:18990',
            'FORTIS_OWNER_ID':'owner',
            'FORTIS_PORT':'18990'})
        self.env.start();self.addCleanup(self.env.stop)
        self.remote=FakeScopedSonar()

    def build(self):
        return build_candidate(token_file='/missing/token',
                               organizations=['alexpastukhh'],transport=self.remote)

    @staticmethod
    def call(portal,path,body=None,cookie=None,csrf=None):
        raw=json.dumps(body or {}).encode()
        env={'HTTP_HOST':'localhost:18990',
             'REQUEST_METHOD':'POST' if body is not None else 'GET',
             'PATH_INFO':path,'QUERY_STRING':'','wsgi.input':BytesIO(raw),
             'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json'}
        if body is not None:env['HTTP_ORIGIN']='http://localhost:18990'
        if cookie:env['HTTP_COOKIE']='fortis_owner='+cookie
        if csrf:env['HTTP_X_FORTIS_CSRF']=csrf
        output=[]
        data=b''.join(portal(env,lambda status,headers:output.append((status,dict(headers)))))
        return int(output[0][0][:3]),json.loads(data),output[0][1]

    def login(self,portal,owner):
        key=VirtualKey()
        code,begin,_=self.call(portal,'/v1/enroll/begin',{'invitation':owner.issue_invitation()})
        self.assertEqual(code,200)
        code,_,_=self.call(portal,'/v1/enroll/finish',
                 {'ceremonyId':begin['ceremonyId'],'response':key.enroll(begin)})
        self.assertEqual(code,200)
        code,begin,_=self.call(portal,'/v1/login/begin',{})
        self.assertEqual(code,200)
        code,session,headers=self.call(portal,'/v1/login/finish',
            {'ceremonyId':begin['ceremonyId'],'response':key.assert_(begin)})
        self.assertEqual(code,200)
        cookie=headers['Set-Cookie'].split(';')[0].split('=',1)[1]
        return key,cookie,session['csrf']

    def test_pending_in_g2_owner_ui_approve_blocked_reject_works(self):
        core,owner,adapter,portal,port=self.build()
        row=propose_issue(core,adapter,project_key='AlexPastukhh_gd-cap',
                          issue_key='S1',reason='Owner must review issue')
        self.assertEqual((row['state'],port),('PENDING',18990))
        self.assertEqual(row['preview']['before']['status'],'OPEN')
        self.assertEqual(row['preview']['after']['status'],'ACCEPTED')
        self.assertEqual(self.call(portal,'/v1/owner/pending')[0],403)
        key,cookie,csrf=self.login(portal,owner)
        code,rows,_=self.call(portal,'/v1/owner/pending',cookie=cookie)
        self.assertEqual(code,200)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['requestId'],row['requestId'])
        self.assertEqual(rows[0]['request']['service'],'sonarcloud')
        self.assertTrue(rows[0]['requiresStrongProof'])
        self.assertFalse(rows[0]['approvalAllowed'])
        code,error,_=self.call(portal,'/v1/owner/decision/session',
            {'requestId':row['requestId'],'decision':'approve','fingerprint':row['fingerprint']},
            cookie=cookie,csrf=csrf)
        self.assertEqual((code,error['error']),(403,'OWNER_OPERATION_WRITE_NOT_ENABLED'))
        code,error,_=self.call(portal,'/v1/owner/decision/begin',
            {'requestId':row['requestId'],'decision':'approve'},cookie=cookie,csrf=csrf)
        self.assertEqual((code,error['error']),(403,'OWNER_OPERATION_WRITE_NOT_ENABLED'))
        code,error,_=self.call(portal,'/v1/owner/decision/finish',
            {'requestId':row['requestId'],'decision':'approve','ceremonyId':'bogus','response':{}},
            cookie=cookie,csrf=csrf)
        self.assertEqual((code,error['error']),(403,'OWNER_OPERATION_WRITE_NOT_ENABLED'))
        self.assertEqual(core._read(row['requestId'])['state'],'PENDING')
        code,begin,_=self.call(portal,'/v1/owner/decision/begin',
            {'requestId':row['requestId'],'decision':'reject'},cookie=cookie,csrf=csrf)
        self.assertEqual(code,200)
        code,rejected,_=self.call(portal,'/v1/owner/decision/finish',
            {'requestId':row['requestId'],'decision':'reject',
             'ceremonyId':begin['ceremonyId'],'response':key.assert_(begin)},
            cookie=cookie,csrf=csrf)
        self.assertEqual((code,rejected['state']),(200,'REJECTED'))
        self.assertEqual(self.call(portal,'/v1/owner/history',cookie=cookie)[1][0]['state'],'REJECTED')
        self.assertEqual(self.remote.posts,0)
        self.assertTrue(all(method=='GET' for method,_,_ in self.remote.calls))

    def test_candidate_state_survives_restart_but_refuses_existing_g2(self):
        core,owner,adapter,portal,_=self.build()
        row=propose_issue(core,adapter,project_key='AlexPastukhh_gd-cap',
                          issue_key='S1',reason='Persistent proposal')
        after,owner2,adapter2,portal2,_=self.build()
        self.assertEqual(after._read(row['requestId'])['state'],'PENDING')
        self.assertEqual(after.owner_list()[0]['requestId'],row['requestId'])
        self.assertFalse(portal2._owner_view(after._read(row['requestId']))['approvalAllowed'])
        self.assertEqual(self.remote.posts,0)
        # A real G2 with DB/credential state has no candidate marker.
        (self.state/'.g4-candidate-v1').unlink()
        with self.assertRaisesRegex(Denied,'G4_REFUSE_EXISTING_G2_STATE'):
            self.build()

    def test_default_g2_composition_never_receives_sonar(self):
        from fortis_approvals.runtime import build_runtime
        core,owner,adapter,port=build_runtime()
        self.assertEqual(set(core.adapters),{'synthetic'})
        self.assertNotIn(('sonarcloud','accept_issue'),core.policies)
        self.assertEqual(port,18990)
        with self.assertRaisesRegex(Denied,'G4_REFUSE_EXISTING_G2_STATE'):
            self.build()

    def test_no_write_transport_always_denies_post_even_if_direct(self):
        guard=NoWriteTransport(self.remote)
        with self.assertRaisesRegex(Denied,'WRITE_DISABLED'):
            guard.call('POST','/api/issues/do_transition',
                       {'issue':'S1','transition':'accept'})
        self.assertEqual(self.remote.posts,0)

    def test_even_trusted_direct_core_decision_cannot_send_sonar_post(self):
        from unittest.mock import Mock
        core,owner,adapter,portal,_=self.build()
        row=propose_issue(core,adapter,project_key='AlexPastukhh_gd-cap',
                          issue_key='S1',reason='Attempt to bypass UI')
        # Synthetic privileged verifier bypasses the UI inside this test only.
        # The transport must still refuse any outbound Sonar POST.
        core.owner_verifier=Mock()
        core.owner_verifier.verify.return_value='synthetic-privileged-test-owner'
        end=core.owner_decide(row['requestId'],'approve',{'synthetic':True})
        self.assertEqual(end['state'],'UNCERTAIN')
        self.assertEqual(self.remote.posts,0)
        self.assertTrue(all(method=='GET' for method,_,_ in self.remote.calls))

    def test_project_scope_and_stale_issue_fail_closed(self):
        core,owner,adapter,portal,_=self.build()
        with self.assertRaises(Denied):
            propose_issue(core,adapter,project_key='foreign',issue_key='S1',reason='test')
        self.remote.transitions=[]
        with self.assertRaises(Denied):
            propose_issue(core,adapter,project_key='AlexPastukhh_gd-cap',issue_key='S1',reason='test')
        self.assertEqual(core.owner_list(),[])
        self.assertEqual(self.remote.posts,0)

    def test_real_token_candidate_refuses_default_g2_listener(self):
        with self.assertRaisesRegex(Denied,'G4_DISTINCT_OWNER_PORT_REQUIRED'):
            build_candidate(token_file='/missing/token',organizations=['alexpastukhh'])
        self.assertFalse((self.state/'.g4-candidate-v1').exists())

    def test_token_file_rejects_untrusted_path_and_accepts_private_test_file(self):
        from fortis_approvals.g4_candidate import _owner_token_file
        file=Path(self.tmp.name)/'token'
        file.write_text('synthetic-local-token-not-real\n')
        file.chmod(0o644)
        with self.assertRaisesRegex(Denied,'NOT_TRUSTED'):_owner_token_file(file)
        file.chmod(0o600)
        self.assertEqual(_owner_token_file(file),'synthetic-local-token-not-real')
        symlink=Path(self.tmp.name)/'alias';symlink.symlink_to(file)
        with self.assertRaisesRegex(Denied,'NOT_TRUSTED'):_owner_token_file(symlink)
        with self.assertRaisesRegex(Denied,'NOT_TRUSTED'):
            _owner_token_file('/workspace/repo/secrets/sonar_token')


if __name__=='__main__':
    unittest.main()
