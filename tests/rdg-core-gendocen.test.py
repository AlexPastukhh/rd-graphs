#!/usr/bin/env python3
"""Real freshness engine: R/A/Context sources and transitive core coverage."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import json,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
FIX=SourceFileLoader('core_engine_scenario',str(ROOT/'tests/rdg-core-model.test.py')).load_module()
B=SourceFileLoader('core_real_engine',str(ROOT/'tools/rdg-requirement-gendocen.py')).load_module()
REF='workspaces/core-proof/graph.json'

class CoreEngine(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix='rdg-core-engine-');self.addCleanup(t.cleanup)
        self.root=Path(t.name);self.graphs=self.root/'graphs';self.file=self.graphs/REF
        self.file.parent.mkdir(parents=True);self.project=self.root/'engine'
        self.scenario=FIX.Core();self.scenario.setUp();self.scenario.shared()
        (self.graphs/'index.json').write_text(json.dumps({'schemaVersion':1,'graphs':[{'file':REF,'identitySpace':self.scenario.g['identitySpace']}]}))
        self.save()
    def save(self):self.file.write_text(json.dumps(self.scenario.g,ensure_ascii=False))
    def refresh(self):return B.refresh(self.graphs,[REF],self.project)
    def test_a_and_context_semantic_changes_invalidate_real_receipt_without_owner_writes(self):
        result=self.refresh();target=next(r for r in result['rows'] if r['nodeId']=='END')
        self.assertTrue({'R1','R2','A','OUT','NEXT','C'} <= {x['nodeId'] for x in target['uses']})
        packet=B.engine_cli(self.project,'explain',target['target'])
        B.engine_cli(self.project,'validate',target['target'],'--result','still-valid','--reason','Isolated freshness review only',
                     '--review-context',packet['review_context_id'])
        original=B.engine_cli(self.project,'history',target['target'])['receipt_ids']
        self.scenario.do('edit',nodeId='C',changes={'description':'Changed actual environment'})
        self.save();before=self.file.read_bytes();after=self.refresh()
        row=next(r for r in after['rows'] if r['nodeId']=='END')
        self.assertEqual(row['status'],'review_required');self.assertIn('nodesById/C',str(row['changedDependencies']))
        self.assertEqual(self.file.read_bytes(),before)
        self.assertEqual(B.engine_cli(self.project,'history',target['target'])['receipt_ids'],original)
        self.scenario.do('edit',nodeId='A',changes={'description':'Changed actual method'});self.save()
        row=next(r for r in self.refresh()['rows'] if r['nodeId']=='END')
        self.assertEqual(row['status'],'review_required');self.assertIn('nodesById/A',str(row['changedDependencies']))
    def test_review_flags_do_not_create_infinite_engine_invalidation(self):
        first=self.refresh();target=next(r for r in first['rows'] if r['nodeId']=='END')
        packet=B.engine_cli(self.project,'explain',target['target'])
        B.engine_cli(self.project,'validate',target['target'],'--result','still-valid','--reason','Isolated freshness review only',
                     '--review-context',packet['review_context_id'])
        self.scenario.review();self.save()
        row=next(r for r in self.refresh()['rows'] if r['nodeId']=='END')
        self.assertEqual(row['status'],'valid')
    def test_origin_only_change_invalidates_real_dependency_review(self):
        first=self.refresh();target=next(r for r in first['rows'] if r['nodeId']=='END')
        packet=B.engine_cli(self.project,'explain',target['target'])
        B.engine_cli(self.project,'validate',target['target'],'--result','still-valid','--reason','Isolated baseline before origin change',
                     '--review-context',packet['review_context_id'])
        self.scenario.qualify_output();self.save();before=self.file.read_bytes()
        row=next(r for r in self.refresh()['rows'] if r['nodeId']=='END')
        self.assertEqual('review_required',row['status']);self.assertEqual(before,self.file.read_bytes())
if __name__=='__main__':unittest.main()
