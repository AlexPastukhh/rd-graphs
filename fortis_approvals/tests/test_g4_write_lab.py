"""End-to-end, offline ASK-bound lab executor. Never touches SonarCloud/G2/G4."""
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

from fortis_approvals.core import Authenticator, Core, Denied
from fortis_approvals.owner_auth import OwnerWebAuthn
from fortis_approvals.owner_portal import OwnerPortal
from fortis_approvals.g4_write_lab import (
    LabSonar, LabGuardedSonarAdapter, LAB_ISSUE, LAB_PROJECT, LAB_OPERATION)
from test_g4_write_security import G4VirtualKey, ORIGIN


class GuardedWriteLabTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='g4-write-executor-lab-')
        self.addCleanup(tmp.cleanup)
        folder=Path(tmp.name)
        self.core_db=folder/'request.sqlite'
        self.remote=LabSonar()
        self.owner=OwnerWebAuthn(folder/'owner.sqlite',origin=ORIGIN)
        self.core=Core(self.core_db,adapters={},policies={LAB_OPERATION:'ASK'},
                       authenticator=Authenticator({'lab-proposer':'lab-actor'}),
                       owner_verifier=self.owner)
        self.adapter=LabGuardedSonarAdapter(self.core_db,self.remote,
                         folder/'receipt.sqlite')
        self.core.adapters['sonarcloud']=self.adapter
        self.portal=OwnerPortal(self.core,self.owner,strong_operations={LAB_OPERATION})
        self.key=G4VirtualKey()
        self.cookie=None
        self.csrf=None

    def call(self, route, body=None, *, origin=True, csrf=True, cookie=True):
        raw=json.dumps(body or {}).encode()
        env={'HTTP_HOST':'localhost:18992',
            'REQUEST_METHOD':'POST' if body is not None else 'GET',
            'PATH_INFO':route,'QUERY_STRING':'','wsgi.input':BytesIO(raw),
            'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json'}
        if body is not None and origin:env['HTTP_ORIGIN']=ORIGIN
        if cookie and self.cookie:env['HTTP_COOKIE']='fortis_owner='+self.cookie
        if csrf and self.csrf:env['HTTP_X_FORTIS_CSRF']=self.csrf
        headers=[]
        result=b''.join(self.portal(env,lambda status,head:headers.append((
            int(status[:3]),dict(head)))))
        return headers[0][0],json.loads(result),headers[0][1]

    def login(self):
        code,begin,_=self.call('/v1/enroll/begin',
            {'invitation':self.owner.issue_invitation()})
        self.assertEqual(code,200)
        self.assertEqual(self.call('/v1/enroll/finish',
            {'ceremonyId':begin['ceremonyId'],
             'response':self.key.enroll(begin)})[0],200)
        code,begin,_=self.call('/v1/login/begin',{})
        self.assertEqual(code,200)
        code,login,headers=self.call('/v1/login/finish',
            {'ceremonyId':begin['ceremonyId'],
             'response':self.key.assert_(begin)})
        self.assertEqual(code,200)
        self.cookie=headers['Set-Cookie'].split(';')[0].split('=',1)[1]
        self.csrf=login['csrf']

    def propose(self):
        sha=self.adapter.read_issue(LAB_PROJECT,LAB_ISSUE)['sha256']
        req={'requestId':str(uuid.uuid4()),'service':'sonarcloud',
             'operation':'accept_issue','target':LAB_ISSUE,
             'params':{'projectKey':LAB_PROJECT,'transition':'accept',
                       'expectedIssueSha256':sha},
             'expectedVersion':0,'reason':'isolated fake issue only'}
        return self.core.client('lab-proposer','submit',req)

    def decide(self, row, decision='approve'):
        code,begin,_=self.call('/v1/owner/decision/begin',
            {'requestId':row['requestId'],'decision':decision})
        self.assertEqual(code,200)
        return self.call('/v1/owner/decision/finish',
            {'requestId':row['requestId'],'decision':decision,
             'ceremonyId':begin['ceremonyId'],
             'response':self.key.assert_(begin)})

    def reservations(self):
        with sqlite3.connect(self.core_db) as db:
            return db.execute('SELECT request_id FROM g4_lab_post_attempts').fetchall()

    def test_signed_ask_dispatch_one_fake_post_and_durable_reservation(self):
        row=self.propose()
        self.assertEqual((row['state'],self.remote.posts),('PENDING',0))
        self.login()
        code,result,_=self.decide(row)
        self.assertEqual((code,result['state']),(200,'EXECUTED'))
        self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.reservations(),[(row['requestId'],)])
        self.assertEqual(self.remote.issue['issueStatus'],'ACCEPTED')
        self.assertEqual([x['state'] for x in self.core.events(row['requestId'])],
                        ['PENDING','APPROVED','DISPATCHED','EXECUTED'])
        self.assertEqual(self.core.execute(row['requestId'])['state'],'EXECUTED')
        self.assertEqual(self.remote.posts,1)

    def test_pending_cannot_arm_or_dispatch_even_with_same_issue(self):
        row=self.propose()
        with self.adapter.post_gate.armed_for(row['request']):
            with self.assertRaisesRegex(Denied,'APPROVED_DISPATCH_REQUIRED'):
                self.adapter.post_gate.call('POST','/api/issues/do_transition',
                    {'issue':LAB_ISSUE,'transition':'accept'})
        self.assertEqual(self.core.execute(row['requestId'])['state'],'PENDING')
        self.assertEqual(self.reservations(),[])
        self.assertEqual(self.remote.posts,0)

    def test_trusted_allow_and_approved_ask_use_same_executor_path(self):
        # This is a fake in-memory route demonstrating the shared mechanism.
        # Real Sonar accept_issue in G4 still has trusted ASK policy only.
        self.core.policies[LAB_OPERATION]='ALLOW'
        self.adapter.post_gate.trusted_policy='ALLOW'
        row=self.propose()
        self.assertEqual(row['state'],'EXECUTED')
        self.assertIsNone(row['decision'])
        self.assertIsNone(row['owner'])
        self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.reservations(),[(row['requestId'],)])
        self.assertEqual([e['state'] for e in self.core.events(row['requestId'])],
                         ['APPROVED','DISPATCHED','EXECUTED'])
        self.assertEqual(self.core.execute(row['requestId'])['state'],'EXECUTED')
        self.assertEqual(self.remote.posts,1)

    def test_ask_approved_request_cannot_dispatch_through_mismatched_allow_gate(self):
        row=self.propose();self.login()
        # Hypothetical trusted mismatch must fail closed; no caller can select
        # the branch in the mutation payload.
        self.adapter.post_gate.trusted_policy='ALLOW'
        code,result,_=self.decide(row)
        self.assertEqual((code,result['state']),(200,'UNCERTAIN'))
        self.assertEqual(self.remote.posts,0)
        self.assertEqual(self.reservations(),[])

    def test_core_allow_bypass_is_denied_without_ask_decision(self):
        self.core.policies[LAB_OPERATION]='ALLOW'
        row=self.propose()
        self.assertEqual(row['state'],'UNCERTAIN')
        self.assertEqual(self.remote.posts,0)
        self.assertEqual(self.reservations(),[])
        self.assertEqual([e['state'] for e in self.core.events(row['requestId'])],
                         ['APPROVED','DISPATCHED','UNCERTAIN'])

    def test_rejected_request_has_no_post_or_reservation(self):
        row=self.propose();self.login()
        code,result,_=self.decide(row,'reject')
        self.assertEqual((code,result['state']),(200,'REJECTED'))
        self.assertEqual(self.core.execute(row['requestId'])['state'],'REJECTED')
        self.assertEqual((self.remote.posts,self.reservations()),(0,[]))

    def test_stale_issue_denied_before_post_reservation(self):
        row=self.propose();self.login()
        self.remote.issue['updateDate']='2026-11-01T00:00:00+0000'
        code,result,_=self.decide(row)
        self.assertEqual((code,result['state']),(200,'STALE'))
        self.assertEqual((self.remote.posts,self.reservations()),(0,[]))

    def test_fake_timeout_after_post_is_uncertain_never_repeated(self):
        row=self.propose();self.login();self.remote.fail_after_post=True
        code,result,_=self.decide(row)
        self.assertEqual((code,result['state']),(200,'UNCERTAIN'))
        self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.reservations(),[(row['requestId'],)])
        self.assertEqual(self.core.execute(row['requestId'])['state'],'UNCERTAIN')
        self.assertEqual(self.core.reconcile(row['requestId'])['state'],'UNCERTAIN')
        self.assertEqual(self.remote.posts,1)
        with self.adapter.post_gate.armed_for(row['request']):
            with self.assertRaisesRegex(Denied,'APPROVED_DISPATCH_REQUIRED'):
                self.adapter.post_gate.call('POST','/api/issues/do_transition',
                    {'issue':LAB_ISSUE,'transition':'accept'})
        self.assertEqual(self.remote.posts,1)

    def test_failed_429_reservation_never_retries(self):
        row=self.propose();self.login();self.remote.fail_before_post=True
        code,result,_=self.decide(row)
        self.assertEqual((code,result['state']),(200,'UNCERTAIN'))
        self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.reservations(),[(row['requestId'],)])
        self.assertEqual(self.core.execute(row['requestId'])['state'],'UNCERTAIN')
        self.assertEqual(self.remote.posts,1)

    def test_approve_challenge_wrong_decision_cannot_trigger_post(self):
        row=self.propose();self.login()
        code,begin,_=self.call('/v1/owner/decision/begin',
            {'requestId':row['requestId'],'decision':'approve'})
        self.assertEqual(code,200)
        code,_,_=self.call('/v1/owner/decision/finish',
            {'requestId':row['requestId'],'decision':'reject',
             'ceremonyId':begin['ceremonyId'],'response':self.key.assert_(begin)})
        self.assertEqual(code,403)
        self.assertEqual((self.remote.posts,self.reservations()),(0,[]))

    def test_forged_approved_state_without_event_chain_cannot_write(self):
        row=self.propose()
        with sqlite3.connect(self.core_db) as db:
            db.execute('UPDATE requests SET state=?,decision=?,owner=? WHERE id=?',
                       ('APPROVED','approve','forged-owner',row['requestId']))
        result=self.core.execute(row['requestId'])
        self.assertEqual(result['state'],'UNCERTAIN')
        self.assertEqual((self.remote.posts,self.reservations()),(0,[]))

    def test_competing_post_call_cannot_dispatch_same_request_twice(self):
        from concurrent.futures import ThreadPoolExecutor
        row=self.propose();self.login()
        original=self.remote.call
        def competing(method,path,params):
            if method=='POST':
                def competitor():
                    with self.adapter.post_gate.armed_for(row['request']):
                        try:
                            self.adapter.post_gate.call('POST',path,params)
                        except Denied as error:
                            return str(error)
                    return 'UNEXPECTED_SECOND_POST'
                with ThreadPoolExecutor(max_workers=1) as pool:
                    refused=pool.submit(competitor).result(timeout=5)
                self.assertEqual(refused,'LAB_POST_ATTEMPT_ALREADY_RESERVED')
            return original(method,path,params)
        self.remote.call=competing
        code,result,_=self.decide(row)
        self.assertEqual((code,result['state']),(200,'EXECUTED'))
        self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.reservations(),[(row['requestId'],)])

    def test_persisted_reservation_blocks_retry_after_simulated_crash(self):
        from fortis_approvals.g4_write_lab import LabPostGate
        row=self.propose();self.login()
        code,result,_=self.decide(row)
        self.assertEqual((code,result['state']),(200,'EXECUTED'))
        self.assertEqual(self.remote.posts,1)
        # Simulate crash after remote transition but before Core recorded
        # EXECUTED. Edit only this synthetic temporary SQLite test fixture.
        with sqlite3.connect(self.core_db) as db:
            db.execute('UPDATE requests SET state=?,result=NULL WHERE id=?',
                       ('DISPATCHED',row['requestId']))
            db.execute('DELETE FROM events WHERE request_id=? AND state=?',
                       (row['requestId'],'EXECUTED'))
        restarted=LabPostGate(self.core_db,self.remote)
        with restarted.armed_for(row['request']):
            with self.assertRaisesRegex(Denied,'LAB_POST_ATTEMPT_ALREADY_RESERVED'):
                restarted.call('POST','/api/issues/do_transition',
                               {'issue':LAB_ISSUE,'transition':'accept'})
        self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.reservations(),[(row['requestId'],)])

    def test_post_gate_does_not_accept_unknown_methods_or_routes(self):
        row=self.propose()
        with self.adapter.post_gate.armed_for(row['request']):
            for method,path in [('PUT','/api/issues/do_transition'),
                                ('POST','/api/admin/delete'),
                                ('PATCH','/api/issues/do_transition')]:
                with self.subTest(method=method,path=path):
                    with self.assertRaisesRegex(Denied,'LAB_WRITE_METHOD_DENIED'):
                        self.adapter.post_gate.call(method,path,
                                                 {'issue':LAB_ISSUE,'transition':'accept'})
        self.assertEqual((self.remote.posts,self.reservations()),(0,[]))

    def test_g4_lab_refuses_real_transport_constructor(self):
        with self.assertRaisesRegex(Denied,'LAB_IN_MEMORY_SOURCE_ONLY'):
            LabGuardedSonarAdapter(self.core_db,object(),
                                   Path(self.core_db.parent)/'fake-receipts.sqlite')
        self.assertEqual(self.remote.posts,0)

    def test_fake_get_post_race_is_visible_as_residual_risk(self):
        row=self.propose();self.login();self.remote.race_before_post=True
        code,result,_=self.decide(row)
        self.assertEqual((code,result['state']),(200,'EXECUTED'))
        self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.remote.issue['message'],'concurrent edit after preflight')
        # This exhibits missing upstream Sonar CAS; not a safe concurrent writer.


if __name__=='__main__':unittest.main()
