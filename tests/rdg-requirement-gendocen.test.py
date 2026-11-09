#!/usr/bin/env python3
"""Real Gendocen process+receipts, no assertion of objective R truth."""
from importlib.machinery import SourceFileLoader
import copy
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BRIDGE=SourceFileLoader('rdg_requirement_engine',str(ROOT/'tools/rdg-requirement-gendocen.py')).load_module()
REF='workspaces/example/graph.json'

class GendocenRequirementDependencies(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='rdg-gendocen-req-');self.addCleanup(tmp.cleanup)
        self.home=Path(tmp.name);self.graph_root=self.home/'graphs'
        self.graph_file=self.graph_root/REF;self.graph_file.parent.mkdir(parents=True)
        (self.graph_root/'index.json').write_text(json.dumps({'schemaVersion':1,'graphs':[
            {'file':REF,'identitySpace':'dep-space'}]}))
        self.project=self.home/'gendocen'
        self.graph={'schemaVersion':1,'actionModel':'candidate-v6','id':'example',
            'identitySpace':'dep-space','rootRequirementId':'R0','revision':1,
            'nodes':[{'id':'R0','kind':'requirement','title':'Feature support'},
                {'id':'R1','kind':'requirement','title':'Subgoal'},
                {'id':'A1','kind':'action','title':'Implementation','status':'candidate',
                 'canonBlock':{'recommended':[{'id':'X','text':'Use only if root is still relevant',
                     'evidenceRefs':['graph-node:R0@'+'1'*64]}], 'contraindicated':[]}},
                {'id':'A2','kind':'action','title':'Independent method','status':'candidate'}],
            'edges':[{'id':'E1','type':'DRIVES','from':'R0','to':'A1'},
                     {'id':'E2','type':'DERIVES','from':'R0','to':'R1'}],
            'events':[]}
        self.save()
    def save(self):
        self.graph_file.write_text(json.dumps(self.graph,ensure_ascii=False))
    def refresh(self):return BRIDGE.refresh(self.graph_root,[REF],self.project)
    def test_real_receipt_and_invalidation_without_automatic_acceptance(self):
        initial=self.refresh()
        self.assertEqual(initial['engine'],'gendocen')
        target=next(row for row in initial['rows'] if row['nodeId']=='A1')
        self.assertEqual({u['nodeId'] for u in target['uses']},{'R0'})
        self.assertIn('E1',str(target['uses']))
        self.assertEqual({row['nodeId'] for row in initial['rows']},{'R1','A1'})
        self.assertNotIn('A2',str(initial['rows']))
        pending={row['nodeId']:row['status'] for row in initial['rows']}
        self.assertNotEqual(pending['A1'],'valid')
        # An actual reviewer (not this bridge) must explicitly validate the
        # current dependency baseline with a Gendocen review context.
        packet=BRIDGE.engine_cli(self.project,'explain',target['target'])
        baseline=BRIDGE.engine_cli(self.project,'validate',target['target'],
                                  '--result','still-valid',
                                  '--reason','Synthetic initial review, not objective truth',
                                  '--review-context',packet['review_context_id'])
        self.assertEqual(BRIDGE.report(self.project)['rows'][0]['status'] in
                         ('valid','review_required'), True)
        self.assertEqual(next(row for row in BRIDGE.report(self.project)['rows']
                              if row['nodeId']=='A1')['status'],'valid')
        original_receipt=BRIDGE.engine_cli(self.project,'history',target['target'])
        self.assertTrue(original_receipt['receipt_ids'])
        self.graph['nodes'][0]['title']='Feature support clarified'
        self.graph['revision']+=1;self.save()
        after=self.refresh()
        a1=next(row for row in after['rows'] if row['nodeId']=='A1')
        self.assertEqual(a1['status'],'review_required')
        self.assertIn('nodesById/R0',str(a1['changedDependencies']))
        self.assertNotIn('A2',str(after['rows']))
        self.assertEqual(BRIDGE.engine_cli(self.project,'history',target['target'])['receipt_ids'],
                         original_receipt['receipt_ids'],'not auto-validated by refresh')
        self.assertEqual(self.graph_file.read_text(),json.dumps(self.graph,ensure_ascii=False))
    def test_unavailable_scope_is_not_silently_complete(self):
        other='workspaces/missing/graph.json'
        self.graph_root.joinpath('index.json').write_text(json.dumps({'schemaVersion':1,'graphs':[
            {'file':REF,'identitySpace':'dep-space'},{'file':other,'identitySpace':'dep-space'}]}))
        with self.assertRaisesRegex(ValueError,'SCOPE_INCOMPLETE'):
            self.refresh()
        self.assertFalse(self.project.exists())
    def test_canon_check_requirements_are_engine_subscriptions_not_text_search(self):
        self.graph['nodes'][2]['canonBlock']['recommended'][0]['checkRequirements']=['R0']
        self.graph['nodes'][3]['canonBlock']={'recommended':[
            {'id':'AX','text':'Narrative mentions R0 but has no structured reference'}],
            'contraindicated':[]}
        self.save()
        view=self.refresh()
        a1=next(x for x in view['rows'] if x['nodeId']=='A1')
        self.assertIn('canon:',str(a1['uses']))
        self.assertFalse(any(x['nodeId']=='A2' for x in view['rows']),
                         'narrative alone is not a review registration')

    def test_ambiguous_explicit_target_denied(self):
        self.graph['nodes'][2]['canonBlock']['recommended'][0]['evidenceRefs'] = (
            ['graph-node:R-UNKNOWN@'+'1'*64])
        self.save()
        with self.assertRaisesRegex(ValueError,'EXPLICIT_REF_OWNER_MISSING'):
            self.refresh()


    def test_rejected_owner_change_preserves_existing_engine_project(self):
        self.refresh()
        before={p.relative_to(self.project).as_posix():p.read_bytes()
                for p in self.project.rglob('*') if p.is_file()}
        # A different identity is a different owner, even at the same graph path.
        self.graph['identitySpace']='replacement-space'
        self.graph['nodes'][0]['title']='Different owner definition'
        self.save()
        (self.graph_root/'index.json').write_text(json.dumps({'schemaVersion':1,'graphs':[
            {'file':REF,'identitySpace':'replacement-space'}]}))
        with self.assertRaisesRegex(ValueError,'PROJECT_OWNER_CLOSURE_CHANGED'):
            self.refresh()
        after={p.relative_to(self.project).as_posix():p.read_bytes()
               for p in self.project.rglob('*') if p.is_file()}
        self.assertEqual(after,before,'rejected owner changes must not replace engine inputs')

        # A larger graph closure is another rejected rebind, not a partial refresh.
        self.graph['identitySpace']='dep-space';self.graph['nodes'][0]['title']='Feature support';self.save()
        other='workspaces/second/graph.json';p=self.graph_root/other;p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'schemaVersion':1,'actionModel':'candidate-v6','id':'second',
            'identitySpace':'dep-space','revision':1,'rootRequirementId':'R-SECOND',
            'nodes':[{'id':'R-SECOND','kind':'requirement','title':'Another owner'}],'edges':[],'events':[]}))
        (self.graph_root/'index.json').write_text(json.dumps({'schemaVersion':1,'graphs':[
            {'file':REF,'identitySpace':'dep-space'},{'file':other,'identitySpace':'dep-space'}]}))
        with self.assertRaisesRegex(ValueError,'PROJECT_OWNER_CLOSURE_CHANGED'):
            BRIDGE.refresh(self.graph_root,[REF,other],self.project)
        self.assertEqual({p.relative_to(self.project).as_posix():p.read_bytes()
            for p in self.project.rglob('*') if p.is_file()},before)

    def test_unrelated_changes_and_refresh_preserve_review_but_changed_input_invalidates_alternative(self):
        self.graph['nodes'].append({'id':'UNRELATED','kind':'requirement','title':'Independent'})
        # Put this supported reference in a scanned canon field, without a DRIVES edge.
        self.graph['nodes'][3]['canonBlock']={'recommended':[
            {'id':'ALT','text':'Alternative applies when root is relevant','checkRequirements':['R0']}],
            'contraindicated':[]}
        self.graph['nodes'][2]['status']='selected'
        self.save()
        initial=self.refresh()
        targets={r['nodeId']:r['target'] for r in initial['rows']}
        for nid in ['A1','A2']:
            packet=BRIDGE.engine_cli(self.project,'explain',targets[nid])
            BRIDGE.engine_cli(self.project,'validate',targets[nid],'--result','still-valid',
                '--reason','Isolated test review, not real-world completion',
                '--review-context',packet['review_context_id'])
        receipts={nid:BRIDGE.engine_cli(self.project,'history',targets[nid])['receipt_ids']
                  for nid in ['A1','A2']}
        self.graph['nodes'][-1]['title']='Independent changed'
        self.graph['revision']+=1;self.save()
        for unused in range(2):
            current={r['nodeId']:r for r in self.refresh()['rows']}
            self.assertEqual([current[n]['status'] for n in ['A1','A2']],['valid','valid'])
        self.graph['nodes'][0]['title']='Changed actual input'
        self.graph['revision']+=1;self.save()
        changed={r['nodeId']:r for r in self.refresh()['rows']}
        self.assertEqual([changed[n]['status'] for n in ['A1','A2']],['review_required','review_required'])
        for nid in ['A1','A2']:
            self.assertEqual(BRIDGE.engine_cli(self.project,'history',targets[nid])['receipt_ids'],receipts[nid])
        self.assertEqual(self.graph['nodes'][3]['status'],'candidate')
        self.assertEqual(self.graph.get('events'),[])



class DependencyInventoryContract(unittest.TestCase):
    def base(self):
        return {'schemaVersion':1,'actionModel':'candidate-v6','id':'example',
            'identitySpace':'dep-space','rootRequirementId':'R0','revision':1,
            'nodes':[{'id':'R0','kind':'requirement','title':'Shared title'},
                     {'id':'R1','kind':'requirement','title':'Shared title'},
                     {'id':'A1','kind':'action','title':'First method','status':'selected'},
                     {'id':'A2','kind':'action','title':'Alternative','status':'candidate'}],
            'edges':[],'events':[]}

    def test_action_introduction_propagates_requirement_changes_to_downstream_actions(self):
        g=self.base()
        g['edges']=[{'id':'driver','type':'DRIVES','from':'R0','to':'A1'},
                    {'id':'child','type':'INTRODUCES','from':'A1','to':'R1'},
                    {'id':'next','type':'DRIVES','from':'R1','to':'A2'}]
        nodes,deps=BRIDGE.inventory({REF:g})
        self.assertEqual(set(deps[REF,'A1']),{(REF,'R0')})
        self.assertEqual(set(deps[REF,'R1']),{(REF,'R0')})
        self.assertEqual(set(deps[REF,'A2']),{(REF,'R0'),(REF,'R1')})

    def test_archived_driver_and_equal_titles_do_not_create_dependencies(self):
        g=self.base()
        g['edges']=[{'id':'old','type':'DRIVES','from':'R0','to':'A1','archived':True},
                    {'id':'child','type':'INTRODUCES','from':'A1','to':'R1'}]
        g['nodes'][3]['canonBlock']={'recommended':[{'id':'text','text':'R0 has Shared title'}],
                                   'contraindicated':[]}
        self.assertEqual(BRIDGE.inventory({REF:g})[1],{})

    def test_alternative_requires_review_only_when_it_has_a_declared_reference(self):
        g=self.base()
        g['nodes'][3]['canonBlock']={'recommended':[{'id':'canon','text':'Use R1',
            'checkRequirements':['R1']}],'contraindicated':[]}
        deps=BRIDGE.inventory({REF:g})[1]
        self.assertEqual(set(deps),{(REF,'A2')})
        self.assertEqual(set(deps[REF,'A2']),{(REF,'R1')})

    def test_projection_and_qualified_reference_keep_canonical_owner(self):
        g=self.base();source='workspaces/source/graph.json'
        g['nodes'][0]['projectionOf']={'graphSlug':'source','nodeId':'R0'}
        g['nodes'][2]['canonBlock']={'recommended':[{'id':'canon','text':'Input',
          'source':{'graphFile':source,'identitySpace':'dep-space','nodeId':'R0'}}],
          'contraindicated':[]}
        g['edges']=[{'id':'driver','type':'DRIVES','from':'R0','to':'A1'}]
        owner={**self.base(),'id':'source','nodes':[{'id':'R0','kind':'requirement','title':'Canonical'}]}
        deps=BRIDGE.inventory({REF:g,source:owner})[1]
        self.assertEqual(set(deps[REF,'R0']),{(source,'R0')})
        self.assertEqual(set(deps[REF,'A1']),{(REF,'R0'),(source,'R0')})

    def test_cycles_terminate_without_self_dependencies(self):
        g=self.base()
        g['edges']=[{'id':'forward','type':'DERIVES','from':'R0','to':'R1'},
                    {'id':'back','type':'DERIVES','from':'R1','to':'R0'},
                    {'id':'use','type':'DRIVES','from':'R1','to':'A1'}]
        deps=BRIDGE.inventory({REF:g})[1]
        self.assertEqual(set(deps[REF,'A1']),{(REF,'R0'),(REF,'R1')})
        for target,uses in deps.items():self.assertNotIn(target,uses)

    def test_missing_canon_requirement_and_duplicate_owner_are_rejected(self):
        g=self.base()
        g['nodes'][2]['canonBlock']={'recommended':[{'id':'canon','text':'Missing',
            'checkRequirements':['UNKNOWN']}],'contraindicated':[]}
        with self.assertRaisesRegex(ValueError,'CANON_REQUIREMENT_UNRESOLVED'):
            BRIDGE.inventory({REF:g})
        g=self.base();duplicate={**self.base(),'id':'second','nodes':[g['nodes'][0]]}
        with self.assertRaisesRegex(ValueError,'AMBIGUOUS_OWNER_ID'):
            BRIDGE.inventory({REF:g,'workspaces/second/graph.json':duplicate})



class AcceptedWriterGendocenStatus(unittest.TestCase):
    def test_post_commit_dependency_failure_is_a_warning_not_a_duplicate_write(self):
        mod=SourceFileLoader('req_dep_helper',str(ROOT/'tools/rdg-workflow-helper.py')).load_module()
        editor=object.__new__(mod.Editor)
        editor.dependency_project=Path('/tmp/this-path-is-not-accessed-in-synthetic-unit')
        editor.dependencies=lambda request: (_ for _ in ()).throw(ValueError('Engine temporarily unavailable'))
        editor.snapshot=lambda: {'graphFile':'workspaces/synthetic/graph.json','sources':{}}
        record={'kind':'graph','receipt':{'transactionId':'accepted-real-writer-request'}}
        response=editor.result(record)
        self.assertTrue(response['saved'])
        self.assertIn('Gendocen требует повторной синхронизации',response['dependencyUpdate']['warning'])
        self.assertFalse(response['dependencyUpdate']['refreshed'])
        self.assertEqual(response['view']['graphFile'],'workspaces/synthetic/graph.json')
    def test_dependency_free_session_reports_unavailable_not_no_warnings(self):
        mod=SourceFileLoader('req_dep_helper2',str(ROOT/'tools/rdg-workflow-helper.py')).load_module()
        editor=object.__new__(mod.Editor)
        editor.dependency_project=None
        message=editor.dependencies({})
        self.assertEqual(message['available'],False)
        self.assertNotIn('rows',message)

if __name__=="__main__":unittest.main()
