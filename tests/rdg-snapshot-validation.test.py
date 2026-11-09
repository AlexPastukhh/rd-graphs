#!/usr/bin/env python3
"""Snapshot validation deduplication: full Graph validation remains mandatory."""
import copy
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
FIX=SourceFileLoader('snapshot_validation_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()


class SnapshotValidation(unittest.TestCase):
    def setUp(self):
        self.fixture=FIX.PortableApplication('test_finding_schema_preflight_retry_and_restart_share_writer')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.package_id,_=self.fixture.finding_package()
        self.app=self.fixture.app()
        self.kernel=self.app.kernel.for_profile('rdg-decision-v1')

    def test_snapshot_fully_validates_graph_exactly_once(self):
        with patch.object(self.kernel,'validate',wraps=self.kernel.validate) as validated:
            row=self.app.snapshot(self.package_id)
            self.assertEqual(validated.call_count,1)
        self.assertEqual(row['graph']['coreModel'],'rdg-decision-v1')
        self.assertEqual(self.app.snapshot(self.package_id),row)

    def test_snapshot_scans_metadata_only_once(self):
        with patch.object(self.app.store,'scan',wraps=self.app.store.scan) as scanning:
            self.app.snapshot(self.package_id)
            self.assertEqual(scanning.call_count,1)

    def test_authorization_happens_before_payload_and_pending_io(self):
        with patch.object(self.app,'authorize',side_effect=ValueError('DENIED')) as auth:
            with patch.object(self.app.store,'_pending_check',side_effect=AssertionError('too late')) as pending:
                with self.assertRaisesRegex(ValueError,'DENIED'):
                    self.app.snapshot(self.package_id)
                auth.assert_called_once()
                pending.assert_not_called()

    def test_external_public_role_validation_still_validates_graph(self):
        row=self.app.snapshot(self.package_id)
        with patch.object(self.kernel,'validate',wraps=self.kernel.validate) as validated:
            self.kernel.validate_role(row['graph'], row['head']['role'], row['plan'])
            self.assertEqual(validated.call_count,1)

    def test_malformed_payload_rejected_before_role_constraints(self):
        row=self.app.snapshot(self.package_id)
        bad=copy.deepcopy(row)
        bad['graph']['nodes'][0]['kind']='invalid-kind'
        with patch.object(self.app.store,'read',return_value=bad):
            with self.assertRaises(ValueError):
                self.app.snapshot(self.package_id)
        self.assertNotEqual(bad,self.app.snapshot(self.package_id))

    def test_role_constraints_still_reject_unsupported_paper_graph(self):
        row=self.app.snapshot(self.package_id)
        paper=copy.deepcopy(row)
        paper['head']['role']='ready'
        with self.assertRaises(ValueError) as reference:
            self.kernel.validate_role(paper['graph'],'ready',paper['plan'])
        with patch.object(self.app.store,'read',return_value=paper):
            with self.assertRaises(ValueError) as actual:
                self.app.snapshot(self.package_id)
        self.assertEqual(str(actual.exception),str(reference.exception))


if __name__=='__main__':
    unittest.main(verbosity=2)
