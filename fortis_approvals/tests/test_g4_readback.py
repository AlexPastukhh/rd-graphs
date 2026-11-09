"""G4 rejected-request readback: readonly history + Sonar GET synthetic proof."""
from contextlib import redirect_stderr,redirect_stdout
from io import StringIO
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fortis_approvals.sonar import SonarIssueAdapter
from test_g4_candidate import FakeScopedSonar

SOURCE=Path(__file__).resolve().parents[1]/'deploy'/'G4-Readback-Probe.py'
spec=importlib.util.spec_from_file_location('g4_probe',SOURCE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class G4ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='g4-readback-test-')
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'approvals.sqlite'
        self.remote=FakeScopedSonar()
        self.project='AlexPastukhh_gd-cap'
        self.issue='S1'
        self.request_id='a145e369-a980-4a42-9d93-b7ea7ceaa003'
        digest=SonarIssueAdapter._digest(SonarIssueAdapter._normalize(
            self.remote.issues[self.issue],project=self.project))
        self.expected_digest=digest
        self.payload={'requestId':self.request_id,'service':'sonarcloud',
                      'operation':'accept_issue','target':self.issue,
                      'params':{'projectKey':self.project,'transition':'accept',
                                'expectedIssueSha256':digest},
                      'reason':'synthetic-only','expectedVersion':0}
        self.snapshot={'projectKey':self.project,'issueKey':self.issue,
                       'before':{'sha256':digest,'status':'OPEN'},
                       'after':{'status':'ACCEPTED'}}
        with sqlite3.connect(self.db) as conn:
            conn.executescript('''CREATE TABLE requests (id TEXT, payload TEXT,
               snapshot TEXT, state TEXT, decision TEXT, owner TEXT,
               created_at INTEGER); CREATE TABLE events (request_id TEXT,
               state TEXT);''')
            conn.execute('INSERT INTO requests VALUES (?,?,?,?,?,?,?)',
                         (self.request_id,json.dumps(self.payload),json.dumps(self.snapshot),
                          'REJECTED','reject','owner',1))
            conn.execute('INSERT INTO events VALUES (?,?)',(self.request_id,'REJECTED'))

    def test_exact_rejected_request_and_same_remote_projection_pass(self):
        self.assertEqual(mod.audit(self.project,self.issue,self.request_id,database=self.db,
                                   transport=self.remote),('REJECTED','OPEN',True))
        self.assertEqual(self.remote.posts,0)
        self.assertTrue(self.remote.calls)
        self.assertTrue(all(m=='GET' for m,_,_ in self.remote.calls))

    def test_remote_open_but_changed_fields_does_not_pass(self):
        self.remote.issues['S1']['updateDate']='2026-11-01T12:00:00+0000'
        state,status,match=mod.audit(self.project,self.issue,self.request_id,
                                    database=self.db,transport=self.remote)
        self.assertEqual((state,status,match),('REJECTED','OPEN',False))
        self.assertEqual(self.remote.posts,0)

    def test_remote_accepted_does_not_pass(self):
        self.remote.issues['S1']['issueStatus']='ACCEPTED'
        state,status,match=mod.audit(self.project,self.issue,self.request_id,
                                    database=self.db,transport=self.remote)
        self.assertEqual((state,status,match),('REJECTED','ACCEPTED',False))
        self.assertEqual(self.remote.posts,0)

    def test_reject_must_match_exact_local_state_and_event(self):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE requests SET state='PENDING'")
        with self.assertRaisesRegex(mod.ReadbackDenied,'LOCAL_REJECTED'):
            mod.audit(self.project,self.issue,self.request_id,database=self.db,transport=self.remote)
        self.assertFalse(self.remote.calls)

    def test_tampered_digest_denied_before_remote_read(self):
        with sqlite3.connect(self.db) as db:
            self.snapshot['before']['sha256']='0'*64
            db.execute('UPDATE requests SET snapshot=?',(json.dumps(self.snapshot),))
        with self.assertRaisesRegex(mod.ReadbackDenied,'LOCAL_REJECTED'):
            mod.audit(self.project,self.issue,self.request_id,database=self.db,transport=self.remote)
        self.assertFalse(self.remote.calls)

    def test_missing_event_denied_before_remote_read(self):
        with sqlite3.connect(self.db) as db:db.execute('DELETE FROM events')
        with self.assertRaisesRegex(mod.ReadbackDenied,'LOCAL_REJECT_EVENT'):
            mod.audit(self.project,self.issue,self.request_id,database=self.db,transport=self.remote)
        self.assertFalse(self.remote.calls)

    def test_unknown_target_denied_without_remote_get(self):
        with self.assertRaisesRegex(mod.ReadbackDenied,'EXACT_REQUEST_TARGET_MISMATCH'):
            mod.audit(self.project,'S2',self.request_id,database=self.db,transport=self.remote)
        self.assertFalse(self.remote.calls)

    def test_newer_pending_same_issue_cannot_be_mistaken_for_rejected(self):
        later='69898cab-809d-468a-aaeb-be64dde1295e'
        with sqlite3.connect(self.db) as db:
            duplicate=dict(self.payload,requestId=later)
            db.execute('INSERT INTO requests VALUES (?,?,?,?,?,?,?)',
                       (later,json.dumps(duplicate),json.dumps(self.snapshot),
                        'PENDING',None,None,2))
            db.execute('INSERT INTO events VALUES (?,?)',(later,'PENDING'))
        # Earlier request remains independently verifiable by exact UUID.
        self.assertEqual(mod.audit(self.project,self.issue,self.request_id,
                         database=self.db,transport=self.remote),('REJECTED','OPEN',True))
        self.remote.calls.clear()
        # The new PENDING UUID must FAIL before Sonar GET.
        with self.assertRaisesRegex(mod.ReadbackDenied,'LOCAL_REJECTED'):
            mod.audit(self.project,self.issue,later,database=self.db,transport=self.remote)
        self.assertFalse(self.remote.calls)

    def test_request_uuid_is_mandatory_and_exact(self):
        for invalid in ('','69898CAB-809D-468A-AAEB-BE64DDE1295E',
                        '69898cab-809d-468a-aaeb-be64dde1295',
                        'exploit; rm -rf /'):
            with self.subTest(invalid=invalid),self.assertRaises((ValueError,mod.ReadbackDenied)):
                mod.audit(self.project,self.issue,invalid,database=self.db,transport=self.remote)
        self.assertFalse(self.remote.calls)
        with self.assertRaisesRegex(mod.ReadbackDenied,'EXACT_G4_REQUEST_NOT_FOUND'):
            mod.audit(self.project,self.issue,'69898cab-809d-468a-aaeb-be64dde1295e',
                      database=self.db,transport=self.remote)
        self.assertFalse(self.remote.calls)

    def test_no_token_issue_or_exception_body_in_denial(self):
        o=StringIO()
        with redirect_stderr(o):
            self.assertEqual(mod.main(['bad target!','S1',self.request_id]),3)
        self.assertEqual(o.getvalue().strip(),'G4_READBACK_CHECK_FAILED_NO_POST')

    def test_security_of_windows_probe_contract(self):
        base=SOURCE.parent
        ps=(base/'Verify-G4-Rejected-Readback.ps1').read_text()
        for required in ('Get-Content -Raw -Encoding UTF8',
                         '--read-only', '--cap-drop ALL', '--network bridge',
                         'fortis-approvals-g4_state,target=/state,readonly',
                         'fortis-approvals-g4_token,target=/run/g4-token,readonly',
                         '--entrypoint python $image - $ProjectKey $IssueKey $RequestId'):
            self.assertIn(required,ps)
        self.assertIn('G4_READBACK_EXACT_REQUEST_ID_REQUIRED',ps)
        self.assertIn('[string]$RequestId',ps)
        self.assertNotIn('docker compose up',ps)
        self.assertNotIn('docker exec',ps)
        self.assertNotIn('--user 0',ps)
        self.assertNotIn('g2_state',ps)
        code=SOURCE.read_text()
        self.assertIn('?mode=ro',code)
        self.assertIn("'PRAGMA query_only = ON'",code)
        self.assertIn("transport.call('GET'",code)
        self.assertNotIn("transport.call('POST'",code)
        self.assertNotIn('print(digest)',code)
        self.assertIn('FROM requests WHERE id=? LIMIT 1',code)
        self.assertNotIn('ORDER BY created_at DESC,id DESC',code)


if __name__=='__main__':
    unittest.main()
