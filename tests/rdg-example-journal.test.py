#!/usr/bin/env python3
"""Incremental operator journal: legacy JSON, crash recovery, and exact retries."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
J=SourceFileLoader('incremental_example_journal',str(ROOT/'tools/rdg-example-journal.py')).load_module()


class IncrementalExampleJournal(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='rdg-journal-test-')
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'operator-example.json'
        self.initial={'operations':{},'path':'examples/test-isolated','day':'2026-11-07'}

    def test_replays_legacy_json_and_wal_without_losing_transaction_id(self):
        original={**self.initial,'operations':{'create':{'request':{'transactionId':'tx-1'},
                                                             'result':{'published':True}}}}
        self.path.write_text(json.dumps(original,ensure_ascii=False))
        journal=J.Journal(self.path,self.initial)
        self.assertEqual(journal.state,original)
        journal.state['operations']['followup']={'request':{'transactionId':'tx-2'}}
        journal.append('followup')
        journal.state['operations']['followup']['applyAttempted']=True
        journal.append('followup')
        # Simulate abrupt termination without exporting a full checkpoint.
        self.assertNotIn('followup',json.loads(self.path.read_text())['operations'])
        recovered=J.Journal(self.path,self.initial)
        self.assertTrue(recovered.state['operations']['followup']['applyAttempted'])
        self.assertEqual(recovered.state['operations']['followup']['request']['transactionId'],'tx-2')
        recovered.state['operations']['followup']['result']={'published':True}
        recovered.append('followup')
        recovered.checkpoint()
        final=json.loads(self.path.read_text())
        self.assertEqual(final['operations']['create'],original['operations']['create'])
        self.assertEqual(final['operations']['followup']['request']['transactionId'],'tx-2')
        self.assertTrue(final['operations']['followup']['result']['published'])
        self.assertFalse(recovered.wal.exists())
        new=J.Journal(self.path,self.initial)
        self.assertEqual(new.state['operations'],recovered.state['operations'])

    def test_truncated_tail_discards_only_incomplete_record(self):
        journal=J.Journal(self.path,self.initial)
        journal.state['operations']['create']={'request':{'transactionId':'tx-1'}}
        journal.append('create')
        with journal.wal.open('ab') as stream:
            stream.write(b'{"seq":2,"meta":')
        recovered=J.Journal(self.path,self.initial)
        self.assertEqual(recovered.state['operations']['create']['request']['transactionId'],'tx-1')
        recovered.state['operations']['create']['applyAttempted']=True
        recovered.append('create')
        reopened=J.Journal(self.path,self.initial)
        self.assertTrue(reopened.state['operations']['create']['applyAttempted'])
        reopened.checkpoint()

    def test_checkpoint_replacement_before_wal_unlink_is_idempotent(self):
        journal=J.Journal(self.path,self.initial)
        journal.state['operations']['create']={'request':{'transactionId':'tx-1'},'applyAttempted':True}
        journal.append('create')
        # Simulate the small crash window after JSON replace but before WAL unlink.
        self.path.write_text(json.dumps({**journal.state,'_journalSeq':journal.sequence}))
        reopened=J.Journal(self.path,self.initial)
        self.assertEqual(reopened.sequence,1)
        self.assertTrue(reopened.state['operations']['create']['applyAttempted'])
        reopened.state['operations']['create']['uncertain']='lost HTTP reply'
        reopened.append('create')
        final=J.Journal(self.path,self.initial)
        self.assertEqual(final.sequence,2)
        self.assertEqual(final.state['operations']['create']['uncertain'],'lost HTTP reply')
        final.checkpoint()

    def test_legacy_windows_codepage_json_is_readable(self):
        old={**self.initial,'operations':{'create':{'request':{'transactionId':'tx-windows','note':'Пример'}}}}
        self.path.write_bytes(json.dumps(old,ensure_ascii=False).encode('cp1251'))
        with patch('locale.getpreferredencoding',return_value='cp1251'):
            journal=J.Journal(self.path,self.initial)
        self.assertEqual(journal.state['operations']['create']['request']['note'],'Пример')
        journal.state['packageId']='owner-1'
        journal.append()
        journal.checkpoint()
        self.assertEqual(J.Journal(self.path,self.initial).state['packageId'],'owner-1')

    def test_metadata_and_unicode_survive_interrupted_resume(self):
        journal=J.Journal(self.path,self.initial)
        journal.state['operations']['create']={'request':{'transactionId':'tx-1','note':'Пример'}}
        journal.append('create')
        journal.state['packageId']='owner-1'
        journal.append()
        journal.state['reviews']={'review-sql':True}
        journal.append()
        recovered=J.Journal(self.path,self.initial)
        self.assertEqual(recovered.state['reviews'],{'review-sql':True})
        self.assertEqual(recovered.state['packageId'],'owner-1')
        self.assertEqual(recovered.state['operations']['create']['request']['note'],'Пример')
        recovered.checkpoint()


if __name__=='__main__':
    unittest.main(verbosity=2)
