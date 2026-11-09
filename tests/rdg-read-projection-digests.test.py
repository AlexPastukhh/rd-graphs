#!/usr/bin/env python3
"""Read/historical output pins must stay identical after per-snapshot digest reuse."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch
import unittest

ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('read_projection_perf_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()


class ReadProjectionDigests(unittest.TestCase):
    def setUp(self):
        self.fixture=T.PortableApplication('test_finding_schema_preflight_retry_and_restart_share_writer')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.owner,_=self.fixture.finding_package()
        self.app=self.fixture.app()

    def test_full_read_has_exact_references_of_legacy_individual_function(self):
        fast=self.app.read(self.owner,True)
        reference=self.app.model.reference
        # Restore original per-reference SHA calculation without modifying
        # the product source or any owner contents.
        def baseline_reference(*args,**kwargs):
            return reference(*args)
        with patch.object(self.app.model,'reference',side_effect=baseline_reference):
            baseline=self.app.read(self.owner,True)
        self.assertEqual(fast,baseline)
        all_entities=self.app.kernel.entities(fast['graph'])
        self.assertEqual(set(fast['references']),set(all_entities))
        for nid in all_entities:
            self.assertEqual(fast['references'][nid],
                             reference(self.owner,fast['graph'],nid))

    def test_history_reuses_sha_of_exact_current_graph_for_all_events(self):
        old_snapshot=self.app.snapshot
        old_digest=self.app.model.digest
        checked={'currentGraph':None,'currentDigestCalls':0}
        def capture(*args,**kwargs):
            row=old_snapshot(*args,**kwargs)
            checked['currentGraph']=row['graph']
            return row
        def track(value):
            if value is checked['currentGraph']:
                checked['currentDigestCalls']+=1
            return old_digest(value)
        with patch.object(self.app,'snapshot',side_effect=capture):
            with patch.object(self.app.model,'digest',side_effect=track):
                history=self.app.history(self.owner)
        self.assertTrue(history['events'])
        self.assertEqual(checked['currentDigestCalls'],1)
        self.assertEqual(self.app.history(self.owner),history)


if __name__=='__main__':
    unittest.main(verbosity=2)
