#!/usr/bin/env python3
"""Opt-in full current graph/Plan dependency baseline with real Gendocen.

Synthetic data only; no writes to shared Gendocen installation or RDG owners.
"""
import copy
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = SourceFileLoader('rdg_workflow_review_adapter', str(ROOT/'tools/rdg-gendocen-adapter.py')).load_module()
DEP = ADAPTER.DEPENDENCIES
ENGINE = Path(os.environ.get('RDG_GENDOCEN_SOURCE','/workspace/repos/gendocen'))
GRAPH = 'workspaces/temporal-fixture/graph.json'

class WorkflowGendocen(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='rdg-workflow-gendocen-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.graphfile = self.root/GRAPH
        self.graphfile.parent.mkdir(parents=True)
        self.planfile = self.root/'plan.json'
        self.graph = {'schemaVersion':1,'id':'review-synthetic','revision':1,
            'identitySpace':'review-demo','rootRequirementId':'R0',
            'actionModel':'candidate-v6','nodes':[
                {'id':'R0','kind':'requirement','title':'Root','status':'active'},
                {'id':'A1','kind':'action','title':'Action','status':'selected','actionType':'decomposition',
                 'canonBlock':{'recommended':[],'contraindicated':[]},'qrpe':[]},
                {'id':'R1','kind':'requirement','title':'Subgoal','status':'active'},
                {'id':'R2','kind':'requirement','title':'Correct method','status':'active'}],
            'edges':[{'id':'E1','type':'DRIVES','from':'R0','to':'A1'},
                     {'id':'E2','type':'INTRODUCES','from':'A1','to':'R1','childRole':'subgoal'},
                     {'id':'E3','type':'INTRODUCES','from':'A1','to':'R2','childRole':'method_correctness'}],
            'events':[]}
        def step(ident, kind, node):
            field='actionRef' if kind=='action' else 'requirementRef'
            return {'id':ident,'kind':kind,'title':node+' in Plan','state':'planned',
                    field:{'graphFile':GRAPH,'identitySpace':'review-demo','nodeId':node}}
        self.plan={'schemaVersion':1,'kind':'temporalPlan','id':'P-TEST','revision':1,
            'title':'Review time','identitySpace':'review-demo','status':'candidate',
            'steps':[step('S-A1','action','A1'),step('S-R1','requirement','R1'),step('S-R2','requirement','R2')],
            'sequence':[{'before':'S-R1','after':'S-A1'}], 'timeConstraints':[], 'branches':[]}

    def projections(self):
        self.graphfile.write_text(json.dumps(self.graph))
        self.planfile.write_text(json.dumps(self.plan))
        return ADAPTER.graph_resource(self.graphfile,workflow_context=True), ADAPTER.plan_resource(self.planfile)

    def contract(self,kind='action',ident='A1',steps=None):
        g,p=self.projections()
        return DEP.build_workflow_contract(g,p,kind,ident,steps or ['S-'+ident])

    def test_scoped_contract_covers_both_R_roles_requirements_and_new_declarations(self):
        first=self.contract()
        self.assertTrue(first['complete'])
        self.assertFalse(first['provenance']['completionTruthAttested'])
        self.assertIn('whole-graph-and-plan',first['granularity'])
        r=self.contract('requirement','R1')
        self.assertTrue(r['complete'])
        self.assertEqual(r['provenance']['targetKind'],'requirement')
        self.assertEqual(len(first['subscriptions']),len(DEP.WORKFLOW_GRAPH_FIELDS)+len(DEP.WORKFLOW_PLAN_FIELDS))
        self.assertEqual(len(first['subscriptions']),len(set(map(tuple,first['subscriptions']))))
        self.assertEqual(self.contract()['subscriptions'],first['subscriptions'])
        # New edges and previously unseen events are watched via whole-resource groups.
        self.assertIn('edgesById',str(first['subscriptions']))
        self.assertIn('events',str(first['subscriptions']))
        self.assertIn('stepsById',str(first['subscriptions']))
        with self.assertRaisesRegex(ValueError,'WORKFLOW_SUBSCRIPTIONS_INCOMPLETE'):
            DEP.assert_workflow_coverage(first,first['subscriptions'][:-1])
        with self.assertRaisesRegex(ValueError,'WORKFLOW_SUBSCRIPTIONS_INCOMPLETE'):
            DEP.assert_workflow_coverage(first,first['subscriptions']+[first['subscriptions'][0]])
        with self.assertRaisesRegex(ValueError,'WORKFLOW_OCCURRENCES_INCOMPLETE'):
            self.contract('action','A1',['S-R1'])
        self.plan['steps'].append(copy.deepcopy(self.plan['steps'][0]))
        self.plan['steps'][-1]['id']='S-A1-NEW'
        with self.assertRaisesRegex(ValueError,'WORKFLOW_OCCURRENCES_INCOMPLETE'):
            self.contract()

    def test_fail_closed_unsupported_roles_and_stale_projections(self):
        self.graph['edges'][1]['childRole']='unrecognized'
        with self.assertRaisesRegex(ValueError,'WORKFLOW_CHILD_ROLE_UNKNOWN'):
            self.contract()
        self.graph['edges'][1]['childRole']='subgoal'
        g,p=self.projections()
        g['data']['nodesById']['R1']['title']='Unreflected change'
        # Entire current contract subscribes to raw fields, but stale derived
        # v2 projections still must be rejected rather than accepted as fresh.
        g['data']['nodesById']['A1']['title']='Changed title only in raw map'
        with self.assertRaisesRegex(ValueError,'WORKFLOW_GRAPH_PROJECTION_STALE'):
            DEP.build_workflow_contract(g,p,'action','A1',['S-A1'])
        g,p=self.projections()
        p['data']['stepsById']['S-R1']['title']='No regenerated projection'
        # Earlier Plan v2 marks Requirement steps explicitly uncovered, so its
        # expected coverage remains "incomplete" even in a new v1 contract.
        self.assertFalse(p['data']['reviewCoverage']['complete'])
        self.assertTrue(DEP.build_workflow_contract(g,p,'action','A1',['S-A1'])['complete'],
                        'new contract watches raw steps even when legacy v2 projection is incomplete')

    def test_owner_lineage_changes_are_observed_or_rejected(self):
        base_graph, plan = self.projections()
        base_hash=base_graph['data']['semanticSHA256']
        self.assertTrue(DEP.build_workflow_contract(base_graph,plan,'action','A1',['S-A1'])['complete'])
        self.graph['readOnly']=True
        readonly_graph, plan=self.projections()
        self.assertNotEqual(base_hash,readonly_graph['data']['semanticSHA256'])
        self.assertIn('readOnly',DEP.WORKFLOW_GRAPH_FIELDS)
        self.assertIn('readOnly',str(DEP.build_workflow_contract(
            readonly_graph,plan,'action','A1',['S-A1'])['subscriptions']))
        self.graph['expansionOf']={'graphSlug':'owner','nodeId':'R0'}
        child_graph, plan=self.projections()
        self.assertNotEqual(readonly_graph['data']['semanticSHA256'],child_graph['data']['semanticSHA256'])
        with self.assertRaisesRegex(ValueError,'WORKFLOW_CROSS_OWNER_CONTEXT_NOT_COVERED'):
            DEP.build_workflow_contract(child_graph,plan,'action','A1',['S-A1'])
        self.graph.pop('expansionOf');self.graph['nodes'][2]['projectionOf']={'graphSlug':'owner','nodeId':'R1'}
        projected_graph, plan=self.projections()
        with self.assertRaisesRegex(ValueError,'WORKFLOW_CROSS_OWNER_CONTEXT_NOT_COVERED'):
            DEP.build_workflow_contract(projected_graph,plan,'action','A1',['S-A1'])
        # The legacy adapter must not silently change meaning or hashes.
        prior=ADAPTER.graph_resource(self.graphfile)['data']['semanticSHA256']
        self.graph['readOnly']=False;self.graph.pop('expansionOf',None)
        self.projections()
        self.assertEqual(prior,ADAPTER.graph_resource(self.graphfile)['data']['semanticSHA256'],
                         'legacy v2 resources do not start tracking new readOnly flags')

    def test_real_engine_legacy_and_workflow_resources_coexist(self):
        """A new workflow projection must not steal the old resource ID/receipt."""
        self.assertTrue((ENGINE/'src/docengine/cli.py').is_file())
        project=self.root/'mixed-engine';docs=project/'docs'
        (docs/'_structured').mkdir(parents=True)
        (docs/'review').mkdir()
        (project/'docengine_project').mkdir()
        (project/'docengine.toml').write_text(
            '[docengine]\nconfig_version = 1\ndocumentation_root = "docs"\n'
            'structured_dir = "_structured"\ndependency_dir = "_dependency"\n'
            'project_package = "docengine_project"\n')
        config=project/'docengine_project/__init__.py'
        legacy,workflow=self.old_and_new_graph_projections()
        legacy_ref=DEP.resource_ref(legacy)
        workflow_ref=DEP.resource_ref(workflow)
        self.assertNotEqual(legacy_ref,workflow_ref)
        config.write_text(DEP.workflow_project_config(
            '_structured/workflow.json','_structured/plan.json',
            [('action','A1',['S-A1'])],'workflow-mixed') +
            "    registry.register('file://review/legacy.md', " +
            repr([(legacy_ref+'#/nodesById/A1','exact')]) +
            ", rule_id='legacy-mixed', dependency_type='semantic_review')\n")
        for name in ('A1','legacy'):
            (docs/'review'/(name+'.md')).write_text('Synthetic only\n')
        original_docs={p:p.read_bytes() for p in (docs/'review').glob('*.md')}
        env={**os.environ,'PYTHONPATH':str(ENGINE/'src'),'PYTHONDONTWRITEBYTECODE':'1'}
        def sources():
            legacy,workflow=self.old_and_new_graph_projections()
            plan=ADAPTER.plan_resource(self.planfile)
            for name,obj in (('legacy',legacy),('workflow',workflow),('plan',plan)):
                (docs/'_structured'/(name+'.json')).write_text(json.dumps(obj))
        def cli(*args):
            proc=subprocess.run([sys.executable,'-m','docengine.cli',*args,
                '--project-root',str(project),'--json'],capture_output=True,text=True,
                env=env,timeout=45)
            return proc,json.loads(proc.stdout) if proc.stdout.strip() else {}
        def status():
            run,body=cli('check');self.assertTrue(body.get('ok'),run.stderr+run.stdout)
            self.assertEqual({p:p.read_bytes() for p in original_docs},original_docs)
            return {row['target'].rsplit('/',1)[-1][:-3]:row['status']
                    for row in body['data']['results']}
        sources()
        run,body=cli('sync');self.assertTrue(body.get('ok'),run.stderr+run.stdout)
        for name in ('A1','legacy'):
            target='file://review/'+name+'.md'
            proc,body=cli('explain',target)
            self.assertTrue(body.get('ok'),proc.stderr+proc.stdout)
            if body['data']['computed_status']=='valid':continue
            proc,body=cli('validate',target,'--result','still-valid',
                '--reason','Synthetic baseline only',
                '--review-context',body['data']['review_context_id'])
            self.assertEqual(proc.returncode,0,proc.stderr+proc.stdout)
        self.assertEqual(status(),{'A1':'valid','legacy':'valid'})
        old_digest=ADAPTER.graph_resource(self.graphfile)['data']['semanticSHA256']
        self.graph['readOnly']=True
        sources()
        self.assertEqual(old_digest,ADAPTER.graph_resource(self.graphfile)['data']['semanticSHA256'])
        self.assertEqual(status(),{'A1':'review_required','legacy':'valid'})

    def old_and_new_graph_projections(self):
        self.graphfile.write_text(json.dumps(self.graph))
        self.planfile.write_text(json.dumps(self.plan))
        return (ADAPTER.graph_resource(self.graphfile),
                ADAPTER.graph_resource(self.graphfile,workflow_context=True))

    def test_real_engine_context_mutation_matrix(self):
        self.assertTrue((ENGINE/'src/docengine/cli.py').is_file())
        project=self.root/'engine-project';docs=project/'docs'
        (docs/'_structured').mkdir(parents=True)
        (docs/'review').mkdir()
        (project/'docengine_project').mkdir()
        (project/'docengine.toml').write_text('[docengine]\nconfig_version = 1\ndocumentation_root = "docs"\nstructured_dir = "_structured"\ndependency_dir = "_dependency"\nproject_package = "docengine_project"\n')
        config=project/'docengine_project/__init__.py'
        targets=[('action','A1',['S-A1']),('requirement','R1',['S-R1']),('requirement','R2',['S-R2'])]
        original=DEP.workflow_project_config('_structured/graph.json','_structured/plan.json',targets,'workflow-review')
        config.write_text(original)
        for _,node,_ in targets:
            (docs/'review'/(node+'.md')).write_text('Synthetic review target '+node+'\n')
        original_prose={p:p.read_bytes() for p in (docs/'review').glob('*.md')}
        env={**os.environ,'PYTHONPATH':str(ENGINE/'src'),'PYTHONDONTWRITEBYTECODE':'1'}
        def sources():
            g,p=self.projections()
            for name,obj in (('graph',g),('plan',p)):
                (docs/'_structured'/(name+'.json')).write_text(json.dumps(obj))
        def cli(*args):
            proc=subprocess.run([sys.executable,'-m','docengine.cli',*args,'--project-root',str(project),'--json'],
                                capture_output=True,text=True,env=env,timeout=45)
            return proc,json.loads(proc.stdout) if proc.stdout.strip() else {}
        def statuses():
            run,body=cli('check')
            self.assertTrue(body.get('ok'),run.stderr+run.stdout)
            self.assertEqual({p:p.read_bytes() for p in original_prose},original_prose)
            return {row['target'].rsplit('/',1)[-1][:-3]:row['status'] for row in body['data']['results']}
        def renew():
            for _,node,_ in targets:
                target='file://review/'+node+'.md'
                proc,body=cli('explain',target)
                self.assertTrue(body.get('ok'),proc.stderr+proc.stdout)
                if body['data']['computed_status'] == 'valid':continue
                proc,body=cli('validate',target,'--result','still-valid',
                    '--reason','Synthetic only','--review-context',body['data']['review_context_id'])
                self.assertEqual(proc.returncode,0,proc.stderr+proc.stdout)
        sources();run,body=cli('sync');self.assertTrue(body.get('ok'),run.stdout+run.stderr)
        renew();self.assertEqual(statuses(),{'A1':'valid','R1':'valid','R2':'valid'})
        outcomes=[]
        def change(name,edit):
            edit();sources();found=statuses();self.assertEqual(found,
                {'A1':'review_required','R1':'review_required','R2':'review_required'},name)
            outcomes.append(name);renew()
        change('childRole',lambda:self.graph['edges'][1].update(childRole='method_correctness'))
        change('execution',lambda:self.graph['events'].append({'id':'EX1','type':'action_executed','targetId':'A1'}))
        change('withdrawal',lambda:self.graph['events'].append({'id':'WITH1','type':'action_withdrawn','actionId':'A1'}))
        change('R achieved',lambda:self.graph['events'].append({'id':'DONE1','type':'requirement_achieved','targetId':'R1'}))
        change('Requirement step',lambda:self.plan['steps'][1].update(title='Renamed Requirement placement'))
        change('R status',lambda:self.graph['nodes'][2].update(status='potential'))
        change('Graph read-only flag',lambda:self.graph.update(readOnly=True))
        self.graph['expansionOf']={'graphSlug':'external-owner','nodeId':'R0'}
        sources()
        run,body=cli('check')
        self.assertNotEqual(run.returncode,0,'unsupported cross-owner context must never return valid')
        self.assertIn('WORKFLOW_CROSS_OWNER_CONTEXT_NOT_COVERED',run.stdout+run.stderr)
        self.graph.pop('expansionOf')
        sources()
        outcomes.append('cross-owner-fail-closed')
        run,body=cli('check');self.assertTrue(body.get('ok'),run.stderr+run.stdout)
        self.assertEqual(statuses(),{'A1':'valid','R1':'valid','R2':'valid'})
        receipts={p:p.read_bytes() for p in (docs/'_dependency/receipts').glob('*.json')}
        config.write_text(original.replace("dependency.assert_workflow_coverage(contract, contract['subscriptions'])",
            "dependency.assert_workflow_coverage(contract, contract['subscriptions'][:-1])"))
        run,body=cli('check')
        self.assertNotEqual(run.returncode,0)
        self.assertIn('WORKFLOW_SUBSCRIPTIONS_INCOMPLETE',run.stdout+run.stderr)
        self.assertEqual({p:p.read_bytes() for p in (docs/'_dependency/receipts').glob('*.json')},receipts)
        config.write_text(original)
        self.assertEqual(statuses(),{'A1':'valid','R1':'valid','R2':'valid'})
        print('WORKFLOW_REAL_GENDOCEN='+json.dumps(outcomes+['omitted-source-fail-closed']),flush=True)

if __name__=='__main__': unittest.main()
