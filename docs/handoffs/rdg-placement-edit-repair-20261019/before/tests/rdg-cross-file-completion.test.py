#!/usr/bin/env python3
"""Cross-owner calculation and publication through actual guarded writers."""
import copy
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
FIX=SourceFileLoader('cross_fixture',str(ROOT/'tests/rdg-workflow.acceptance.test.py')).load_module()
ENGINE=SourceFileLoader('cross_engine_test',str(ROOT/'tools/rdg-completion-context.py')).load_module()
HELPER=SourceFileLoader('cross_helper_test',str(ROOT/'tools/rdg-workflow-helper.py')).load_module()


class CrossFile(unittest.TestCase):
    def setUp(self):
        self.f=FIX.Workflow('test_whole_future_execution_withdrawal_new_variant_and_history')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.w=self.f.w;self.parent=self.w.rel;self.child='workspaces/child/graph.json'
        self.seq=0

    def graph(self,file):
        return json.loads((self.w.home/'graphs'/file).read_text())

    def package(self,file,operations,tid=None):
        self.seq+=1
        return {'schemaVersion':1,'transactionId':tid or 'cross-'+str(self.seq),
            'changes':[{'file':file,'patch':{'schemaVersion':1,
                'expectedRevision':self.graph(file)['revision'],'operations':operations}}]}

    def apply(self,file,ops,token=None):
        package=self.package(file,ops);self.w.assert_ok(self.w.write(package,token or self.w.token));return package

    def setup_child(self,role='subgoal',selected=True,done=True,alias='Local display of R1'):
        self.w.apply([self.w.add('D',action_type='decomposition' if role=='subgoal' else 'general'),
                      self.w.prepare('D','R1',role)])
        if selected:self.w.apply([self.w.choose('D')])
        if selected and done and role=='subgoal':self.w.apply([self.w.result('D',action=True)])
        graph={'schemaVersion':1,'revision':1,'id':'child','title':'Child continuation',
            'planningScale':'module','actionModel':'candidate-v6','identitySpace':'demo',
            'rootRequirementId':'R1','expansionOf':{'graphSlug':'demo','nodeId':'R1'},
            'nodes':[{'id':'R1','kind':'requirement','title':alias,'status':'potential',
                      'projectionOf':{'graphSlug':'demo','nodeId':'R1'}}],'edges':[],'events':[]}
        self.w.assert_ok(self.w.write({'schemaVersion':1,'transactionId':'create-child',
            'changes':[{'file':self.child,'create':graph}]},self.w.token))

    def add_child_action(self,selected=True):
        self.apply(self.child,[self.w.add('C','R1')])
        if selected:self.apply(self.child,[self.w.choose('C','R1')])

    def view(self,token=None):
        return FIX.WF.read_workflow(self.f.root,self.f.rel,self.w.home/'graphs',self.w.store,
            token or self.w.token,[self.parent],include_sources=True)

    def context(self):
        return ENGINE.load(self.w.home/'graphs',{self.parent:self.graph(self.parent)})

    def place(self):
        self.f.owner(self.f.placement_request([self.f.place('ROOT','R0','requirement')]))

    def test_subgoal_continuation_execution_writes_parent_history_and_future_once(self):
        self.setup_child();self.add_child_action();self.place()
        self.assertEqual([r['nodeId'] for r in self.view()['future']],['R0'])
        old_d=copy.deepcopy(next(e for e in self.graph(self.parent)['events'] if e['type']=='action_executed'))
        plan=self.f.plan_sources()
        request=self.apply(self.child,[self.w.result('C',action=True)])
        view=self.view();self.assertEqual(view['future'],[]);self.assertEqual(plan,self.f.plan_sources())
        self.assertIn(old_d,self.graph(self.parent)['events'])
        self.assertEqual(len([e for e in self.graph(self.parent)['events'] if e['type']=='action_executed']),1)
        rows=[r for r in view['history'] if r.get('transactionId')==request['transactionId'] and r['kind']!='graph_saved']
        self.assertEqual([(r['kind'],r['targetId']) for r in rows],
            [('action_executed','C'),('requirement_achieved','R1'),('requirement_achieved','R0')])
        self.assertTrue(all(r['graphFile']==self.parent for r in rows[1:]))
        source=self.w.sources();self.view();self.assertEqual(source,self.w.sources())
        self.w.assert_ok(self.w.write(request,self.w.token));self.assertEqual(source,self.w.sources())

    def test_method_correctness_automatically_executes_composite_action_and_goal(self):
        self.setup_child(role='method_correctness');self.add_child_action()
        before=self.w.sources()
        self.w.assert_denied(self.w.write(self.package(self.parent,[self.w.result('D',action=True)]),self.w.token),'required work')
        self.assertEqual(before,self.w.sources())
        request=self.apply(self.child,[self.w.result('C',action=True)])
        rows=[r for r in self.view()['history'] if r.get('transactionId')==request['transactionId'] and r['kind']!='graph_saved']
        self.assertEqual([(r['kind'],r['targetId']) for r in rows],[
            ('action_executed','C'),('requirement_achieved','R1'),('action_executed','D'),('requirement_achieved','R0')])
        state=self.context().evaluate()
        self.assertTrue(state[self.parent]['D']['complete'])
        self.assertTrue(state[self.parent]['R0']['complete'])

    def test_deep_choice_does_not_activate_unselected_ancestor(self):
        self.setup_child(selected=False,done=False);self.add_child_action()
        before=self.w.sources();request=self.package(self.child,[self.w.result('C',action=True)])
        self.w.assert_denied(self.w.write(request,self.w.token),'actual selected scope')
        self.assertEqual(before,self.w.sources())
        self.w.apply([self.w.choose('D')])
        self.apply(self.child,[self.w.result('C',action=True)])
        state=self.context().evaluate();self.assertTrue(state[self.parent]['R1']['complete'])
        self.assertFalse(state[self.parent]['R0']['complete'])
        self.w.apply([self.w.result('D',action=True)])
        self.assertTrue(self.context().evaluate()[self.parent]['R0']['complete'])

    def test_driver_alias_preserves_local_display_and_pins_canonical_definition(self):
        self.setup_child(alias='Different local display');self.add_child_action()
        action=next(n for n in self.graph(self.child)['nodes'] if n['id']=='C')
        self.assertEqual(action['selectionBasis']['driverSnapshot']['title'],'Different local display')
        self.assertEqual(action['selectionBasis']['driverOwnerSnapshot']['node']['title'],'R1')
        self.assertEqual(action['selectionBasis']['driverOwnerSnapshot']['ownerRef']['graphFile'],self.parent)
        self.apply(self.child,[self.w.result('C',action=True)])
        self.assertTrue(self.context().evaluate()[self.parent]['R0']['complete'])

    def test_denied_dependency_read_fails_before_any_write_or_success(self):
        self.setup_child();self.add_child_action()
        token=self.w.grant(['graph.read','graph.record_action_execution'],[self.child])['token']
        before=self.w.sources()
        self.w.assert_denied(self.w.write(self.package(self.child,[self.w.result('C',action=True)]),token),'GRAPH_READ_SCOPE_DENIED')
        self.assertEqual(before,self.w.sources())
        token=self.w.grant(['graph.read','plan.read'],[self.parent,'plans/'])['token']
        with self.assertRaisesRegex(ValueError,'GRAPH_READ_SCOPE_DENIED'):self.view(token)
        self.assertEqual(before,self.w.sources())

    def test_missing_parent_result_permission_rejects_entire_child_execution(self):
        self.setup_child();self.add_child_action()
        token=self.w.grant(['graph.read','graph.record_action_execution'],[self.parent,self.child])['token']
        before=self.w.sources();req=self.package(self.child,[self.w.result('C',action=True)])
        self.w.assert_denied(self.w.write(req,token),'graph.record_requirement_achievement')
        self.assertEqual(before,self.w.sources())
        token=self.w.grant(['graph.read','graph.record_action_execution','graph.record_requirement_achievement'],
                           [self.parent,self.child])['token']
        self.w.assert_ok(self.w.write(req,token))
        self.assertTrue(self.context().evaluate()[self.parent]['R0']['complete'])

    def test_requested_parent_edit_does_not_bypass_derived_result_permission(self):
        self.setup_child();self.add_child_action()
        token=self.w.grant(['graph.read','graph.record_action_execution','graph.graph_edit.edit_node'],
                           [self.parent,self.child])['token']
        req=self.package(self.child,[self.w.result('C',action=True)])
        req['changes'].extend(self.package(self.parent,[
            self.w.edit('edit_node',nodeId='R1',changes={'title':'R1'})])['changes'])
        before=self.w.sources()
        self.w.assert_denied(self.w.write(req,token),'graph.record_requirement_achievement')
        self.assertEqual(before,self.w.sources())
        allowed=self.w.grant(['graph.read','graph.record_action_execution',
            'graph.record_requirement_achievement','graph.graph_edit.edit_node'],
            [self.parent,self.child])['token']
        self.w.assert_ok(self.w.write(req,allowed))
        self.assertTrue(self.context().evaluate()[self.parent]['R0']['complete'])
        snapshot=self.w.sources()
        self.w.assert_denied(self.w.write(req,token),'graph.record_requirement_achievement')
        self.assertEqual(snapshot,self.w.sources())
        self.w.assert_ok(self.w.write(req,allowed))
        self.assertEqual(snapshot,self.w.sources())

    def test_result_must_be_recorded_at_its_owner_not_projection(self):
        self.setup_child();self.add_child_action()
        before=self.w.sources()
        self.w.assert_denied(self.w.write(self.package(self.child,[self.w.result('R1')]),self.w.token),'owning graph')
        self.assertEqual(before,self.w.sources())

    def test_missing_source_ambiguity_projection_cycle_scope_and_dependency_cycle(self):
        self.setup_child();self.add_child_action()
        context=self.context();original=self.w.sources()
        child=copy.deepcopy(context.graphs[self.child]);child['nodes'][0].pop('projectionOf');child.pop('expansionOf')
        with self.assertRaisesRegex(ValueError,'AMBIGUOUS_IDENTITY_OWNER'):context.updated({self.child:child}).evaluate()
        parent=copy.deepcopy(context.graphs[self.parent])
        next(n for n in parent['nodes'] if n['id']=='R1')['projectionOf']={'graphSlug':'child','nodeId':'R1'}
        with self.assertRaisesRegex(ValueError,'PROJECTION_CYCLE'):context.updated({self.parent:parent}).evaluate()
        child=copy.deepcopy(context.graphs[self.child]);child['nodes'][0]['scope']='other'
        with self.assertRaisesRegex(ValueError,'SCOPE_MISMATCH'):context.updated({self.child:child}).evaluate()
        child=copy.deepcopy(context.graphs[self.child]);child['nodes'].append({'id':'R0','kind':'requirement','title':'Root alias',
            'projectionOf':{'graphSlug':'demo','nodeId':'R0'}})
        child['edges'].append({'id':'cycle','type':'INTRODUCES','from':'C','to':'R0','parent':'R1','childRole':'method_correctness'})
        with self.assertRaisesRegex(ValueError,'completion dependency cycle'):context.updated({self.child:child}).evaluate()
        self.assertEqual(original,self.w.sources())
        path=self.w.home/'graphs'/self.child;raw=path.read_bytes();path.unlink()
        try:
            with self.assertRaisesRegex(ValueError,'SOURCE_MISSING'):self.view()
        finally:path.write_bytes(raw)

    def test_catalog_metadata_and_exact_expansion_binding_are_checked(self):
        self.setup_child();self.add_child_action()
        context=self.context();child=copy.deepcopy(context.graphs[self.child]);child['expansionOf']['nodeId']='other'
        with self.assertRaisesRegex(ValueError,'EXPANSION_BINDING_INVALID'):context.updated({self.child:child}).evaluate()
        child=copy.deepcopy(context.graphs[self.child]);child.pop('expansionOf')
        with self.assertRaisesRegex(ValueError,'EXPANSION_BINDING_REQUIRED'):context.updated({self.child:child}).evaluate()
        child=copy.deepcopy(context.graphs[self.child]);child['actionModel']='legacy'
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_OWNER_MODEL'):context.updated({self.child:child}).evaluate()
        path=self.w.home/'graphs/index.json';saved=path.read_bytes();data=json.loads(saved)
        next(x for x in data['graphs'] if x['file']==self.child)['identitySpace']='different'
        path.write_text(json.dumps(data))
        try:
            with self.assertRaisesRegex(ValueError,'OWNER_MISSING|CATALOG_STALE'):self.view()
        finally:path.write_bytes(saved)

    def test_executed_instance_never_reexecutes_or_returns_to_future_after_owner_edit(self):
        self.setup_child();self.add_child_action()
        self.f.owner(self.f.placement_request([{'op':'place','step':{'id':'C','kind':'action','state':'planned','title':'C',
            'actionRef':{'graphFile':self.child,'identitySpace':'demo','nodeId':'C'}},
            'timeConstraints':[{'type':'notBefore','at':'2026-10-21','strength':'soft','basis':'Synthetic'}]}]))
        self.apply(self.child,[self.w.result('C',action=True)])
        original=next(e for e in self.graph(self.child)['events'] if e['type']=='action_executed')
        self.apply(self.child,[self.w.edit('edit_node',nodeId='C',changes={'title':'Changed after execution'})])
        states=self.context().evaluate();self.assertTrue(states[self.child]['C']['complete'])
        self.assertFalse(states[self.child]['C']['currentScopeComplete'])
        self.assertFalse(states[self.parent]['R0']['complete'])
        self.assertNotIn('C',[r['nodeId'] for r in self.view()['future']])
        self.assertIn(original,self.graph(self.child)['events'])
        before=self.w.sources()
        self.w.assert_denied(self.w.write(self.package(self.child,[self.w.result('C',action=True)]),self.w.token),'already executed')
        self.assertEqual(before,self.w.sources())

    def test_partial_multifile_publication_blocks_read_and_recovers_once(self):
        self.setup_child();self.add_child_action();self.place()
        req=self.package(self.child,[self.w.result('C',action=True)],'cross-crash')
        (self.w.home/'cross-request.json').write_text(json.dumps(req))
        script=self.w.home/'cross-crash.py'
        script.write_text("""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import json,os
m=SourceFileLoader('cross_crash_package',str(Path(__file__).parent/'tools/graph-package.py')).load_module()
def crash(path,journal):
 first=journal['records'][0]
 m.write_json(m.target_path(first['file']),first['after'])
 os._exit(77)
m.finish=crash
m.execute(json.loads((Path(__file__).parent/'cross-request.json').read_text()))
""")
        run=subprocess.run(['python3','-B',str(script)],capture_output=True,text=True,
                           env={**self.w.env,'RDG_AUTH_TOKEN':self.w.token})
        self.assertEqual(run.returncode,77,run.stderr)
        with self.assertRaisesRegex(ValueError,'RECOVERY_REQUIRED'):self.view()
        self.w.assert_ok(self.w.write(req,self.w.token));self.assertEqual(self.view()['future'],[])
        self.assertEqual(len([e for e in self.graph(self.parent)['events']
            if e['type']=='requirement_achieved' and e['targetId']=='R0']),1)
        snapshot=self.w.sources();self.w.assert_ok(self.w.write(req,self.w.token));self.assertEqual(snapshot,self.w.sources())

    def test_changed_dependency_between_read_and_acceptance_is_not_published(self):
        self.setup_child();self.add_child_action()
        req=self.package(self.child,[self.w.result('C',action=True)],'cross-race')
        (self.w.home/'cross-request.json').write_text(json.dumps(req))
        script=self.w.home/'cross-race.py'
        script.write_text("""
from importlib.machinery import SourceFileLoader
from contextlib import contextmanager
from pathlib import Path
import json
m=SourceFileLoader('cross_race_package',str(Path(__file__).parent/'tools/graph-package.py')).load_module()
real=m.checked_package_authority
@contextmanager
def race(package):
 with real(package) as actor:
  path=m.target_path('workspaces/demo/graph.json')
  graph=json.loads(path.read_text());graph['revision']+=100
  path.write_text(json.dumps(graph))
  yield actor
m.checked_package_authority=race
try:m.execute(json.loads((Path(__file__).parent/'cross-request.json').read_text()))
except ValueError as exc:print(str(exc));raise SystemExit(2)
""")
        child=(self.w.home/'graphs'/self.child).read_bytes()
        run=subprocess.run(['python3','-B',str(script)],text=True,capture_output=True,
                           env={**self.w.env,'RDG_AUTH_TOKEN':self.w.token})
        self.assertNotEqual(run.returncode,0);self.assertIn('COMPLETION_DEPENDENCY_CHANGED',run.stdout+run.stderr)
        self.assertEqual(child,(self.w.home/'graphs'/self.child).read_bytes())
        self.assertFalse((self.w.home/'graphs/workspaces/.transactions/cross-race.json').exists())

    def test_repeated_projections_do_not_duplicate_action_work_or_its_history(self):
        self.setup_child();self.add_child_action()
        action=copy.deepcopy(next(n for n in self.graph(self.child)['nodes'] if n['id']=='C'))
        action.update(status='candidate',projectionOf={'graphSlug':'child','nodeId':'C'})
        action.pop('selectionBasis',None)
        third='workspaces/display/graph.json'
        graph={'schemaVersion':1,'revision':1,'id':'display','title':'Repeated display',
            'planningScale':'module','actionModel':'candidate-v6','identitySpace':'demo','rootRequirementId':'R-OTHER',
            'nodes':[{'id':'R-OTHER','kind':'requirement','title':'Independent display root','status':'active'},
                {'id':'R1','kind':'requirement','title':'Display alias','status':'active',
                 'projectionOf':{'graphSlug':'demo','nodeId':'R1'}},action],
            'edges':[{'id':'repeated-drive','type':'DRIVES','from':'R1','to':'C'}],'events':[]}
        self.w.assert_ok(self.w.write({'schemaVersion':1,'transactionId':'display-create',
            'changes':[{'file':third,'create':graph}]},self.w.token))
        before=self.w.sources()
        self.w.assert_denied(self.w.write(self.package(third,[self.w.choose('C','R1')]),self.w.token),'owning graph')
        self.assertEqual(before,self.w.sources())
        self.apply(self.child,[self.w.result('C',action=True)])
        states=self.context().evaluate()
        self.assertEqual(states[self.parent]['R1']['dependencyIds'],['C'])
        self.assertEqual(states[third]['C']['ownerRef']['graphFile'],self.child)
        rows=[r for r in self.view()['history'] if r['kind']=='action_executed' and r['targetId']=='C']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['graphFile'],self.child)
        place=self.f.place('ALIAS','R1','requirement');place['step']['requirementRef']['graphFile']=third
        self.f.owner(self.f.placement_request([place]))
        row=next(r for r in self.view()['excludedPlacements'] if r['stepId']=='ALIAS')
        self.assertEqual(row['reason'],'completed');self.assertEqual(row['ownerRef']['graphFile'],self.parent)

    def test_cross_owner_withdrawal_and_new_variant_preserve_both_executions(self):
        self.setup_child();self.add_child_action();self.apply(self.child,[self.w.result('C',action=True)])
        first=copy.deepcopy(next(e for e in self.graph(self.child)['events'] if e['type']=='action_executed'))
        withdrawal={'op':'withdraw_action','actionId':'C','dispositions':[],
            'event':self.w.event('action_withdrawn',actionId='C',driverRequirementId='R1')}
        self.apply(self.child,[withdrawal])
        self.assertFalse(self.context().evaluate()[self.parent]['R0']['complete'])
        self.apply(self.child,[self.w.add('C2','R1'),self.w.choose('C2','R1')])
        self.assertFalse(self.context().evaluate()[self.parent]['R0']['complete'])
        self.apply(self.child,[self.w.result('C2',action=True)])
        self.assertTrue(self.context().evaluate()[self.parent]['R0']['complete'])
        self.assertIn(first,self.graph(self.child)['events'])
        facts=[(r['kind'],r['targetId']) for r in self.view()['history']
               if r['kind'] in ('action_executed','action_withdrawn') and r['targetId'] in ('C','C2')]
        self.assertEqual(facts,[('action_executed','C'),('action_withdrawn','C'),('action_executed','C2')])

    def test_projection_cannot_bypass_canonical_requirement_policy(self):
        self.setup_child();self.add_child_action();self.apply(self.child,[self.w.result('C',action=True)])
        # Isolated fixture injection sets the canonical policy; projection has no local copy.
        path=self.w.home/'graphs'/self.parent;graph=self.graph(self.parent)
        next(n for n in graph['nodes'] if n['id']=='R1')['reconsiderationPolicy']={
            'mode':'protected','authorityPrincipal':'protected-owner'}
        path.write_text(json.dumps(graph))
        before=self.w.sources()
        operation={'op':'withdraw_action','actionId':'C','dispositions':[],
            'event':self.w.event('action_withdrawn',actionId='C',driverRequirementId='R1')}
        self.w.assert_denied(self.w.write(self.package(self.child,[operation]),self.w.token),'PROTECTED_OWNER_GRANT_REQUIRED')
        self.assertEqual(before,self.w.sources())
        graph=self.graph(self.parent)
        next(n for n in graph['nodes'] if n['id']=='R1')['reconsiderationPolicy']={'mode':'stable'}
        path.write_text(json.dumps(graph))
        before=self.w.sources()
        self.w.assert_denied(self.w.write(self.package(self.child,[operation]),self.w.token),'STABLE_RECONSIDERATION_REASON_REQUIRED')
        self.assertEqual(before,self.w.sources())

    def test_durable_cross_owner_acceptance_recovers_after_grant_revocation(self):
        self.setup_child();self.add_child_action();self.place()
        request=self.package(self.child,[self.w.result('C',action=True)],'revoked-cross-crash')
        (self.w.home/'cross-request.json').write_text(json.dumps(request))
        script=self.w.home/'revoke-crash.py'
        script.write_text("""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import json,os
m=SourceFileLoader('cross_revoke',str(Path(__file__).parent/'tools/graph-package.py')).load_module()
m.finish=lambda path,journal:os._exit(77)
m.execute(json.loads((Path(__file__).parent/'cross-request.json').read_text()))
""")
        run=subprocess.run(['python3','-B',str(script)],capture_output=True,text=True,
                           env={**self.w.env,'RDG_AUTH_TOKEN':self.w.token})
        self.assertEqual(run.returncode,77,run.stderr)
        auth=HELPER.AUTH.Authority(self.w.store);ident=auth._actor(auth._read(),self.w.token)[0]
        self.w.admin('revoke',{'id':ident},self.w.owner)
        observer=self.w.grant(['graph.read','plan.read'],['workspaces/','plans/'])['token']
        with self.assertRaisesRegex(ValueError,'RECOVERY_REQUIRED'):self.view(observer)
        self.w.assert_denied(self.w.write(request,self.w.token),'TOKEN_REVOKED')
        self.assertEqual(self.view(observer)['future'],[])
        self.assertEqual(len([e for e in self.graph(self.parent)['events']
            if e['type']=='requirement_achieved' and e['targetId']=='R0']),1)

    def test_reader_waits_for_whole_publication_instead_of_mixing_owner_revisions(self):
        import time
        self.setup_child();self.add_child_action()
        req=self.package(self.child,[self.w.result('C',action=True)],'locked-cross-publication')
        (self.w.home/'cross-request.json').write_text(json.dumps(req))
        script=self.w.home/'slow-cross.py'
        script.write_text("""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import json,time
m=SourceFileLoader('slow_cross_package',str(Path(__file__).parent/'tools/graph-package.py')).load_module()
real=m.finish
def slow(path,journal):
 first=journal['records'][0]
 m.write_json(m.target_path(first['file']),first['after'])
 print('HALF',flush=True)
 gate=Path(__file__).parent/'release-cross'
 for _ in range(1000):
  if gate.exists():break
  time.sleep(.01)
 else:raise ValueError('TEST_GATE_TIMEOUT')
 real(path,journal)
m.finish=slow
m.execute(json.loads((Path(__file__).parent/'cross-request.json').read_text()))
""")
        reader_script=self.w.home/'cross-reader.py'
        reader_script.write_text("""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import json,os
home=Path(__file__).parent
m=SourceFileLoader('waiting_cross_reader',str(home/'tools/rdg-activity.py')).load_module()
print('ATTEMPT',flush=True)
view=m.read_activity(home/'graphs',['workspaces/demo/graph.json'],os.environ['RDG_AUTH_TOKEN'],home/'grants.json')
print(json.dumps(view),flush=True)
""")
        env={**self.w.env,'RDG_AUTH_TOKEN':self.w.token}
        writer=subprocess.Popen(['python3','-B',str(script)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        reader=None
        try:
            self.assertEqual(writer.stdout.readline().strip(),'HALF')
            reader=subprocess.Popen(['python3','-B',str(reader_script)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
            self.assertEqual(reader.stdout.readline().strip(),'ATTEMPT')
            time.sleep(.15);self.assertIsNone(reader.poll(),'reader must not publish a mixed revision')
            (self.w.home/'release-cross').write_text('go')
            out,err=reader.communicate(timeout=20);self.assertEqual(reader.returncode,0,err)
            report=json.loads(out)
            self.assertTrue(report['currentCompletion'][self.parent]['R0']['complete'])
            self.assertTrue(report['currentCompletion'][self.child]['C']['complete'])
            self.assertEqual(report['graphOwners'][self.parent]['revision'],self.graph(self.parent)['revision'])
            self.assertEqual(report['graphOwners'][self.child]['revision'],self.graph(self.child)['revision'])
        finally:
            (self.w.home/'release-cross').write_text('go')
            out,err=writer.communicate(timeout=20)
            if reader and reader.poll() is None:reader.terminate();reader.communicate(timeout=5)
        self.assertEqual(writer.returncode,0,err)

    def test_cross_owner_gui_uses_same_writers_and_can_build_on_projection_root(self):
        self.setup_child()
        editor=HELPER.Editor(self.f.root,self.f.rel,self.w.home/'graphs',self.child,self.w.store,self.w.token,tools=self.w.home/'tools')
        server=HELPER.make_server(editor);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            run=subprocess.run(['node','--test','tests/rdg-workflow-ui.test.cjs'],cwd=ROOT,text=True,capture_output=True,
                timeout=90,env={**os.environ,'RDG_CROSS_TEST_URL':server.session_url})
            (ROOT/'docs/handoffs/rdg-cross-file-completion-20261019/gui-cross.log').write_text(run.stdout+run.stderr)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertTrue(self.context().evaluate()[self.parent]['R0']['complete'])
        finally:server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
