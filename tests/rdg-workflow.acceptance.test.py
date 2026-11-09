#!/usr/bin/env python3
"""Whole workflow through real graph/plan writers, isolated owners and grants."""
import copy
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEEP = SourceFileLoader('workflow_deep_fixture', str(ROOT/'tests/rdg-deep-action.acceptance.test.py')).load_module()
WF = SourceFileLoader('workflow_test_api', str(ROOT/'tools/rdg-workflow.py')).load_module()
DEP = SourceFileLoader('workflow_dependency_api', str(ROOT/'tools/rdg-gendocen-dependencies.py')).load_module()


class Workflow(unittest.TestCase):
    def setUp(self):
        self.w = w = DEEP.DeepAction('test_leaf_no_extra_result_goal_and_later_definition_edit_preserves_history')
        original_admin = w.admin
        def admin(command, payload=None, token=None):
            if command == 'init':
                return subprocess.run(['python3','-B',str(w.home/'tools/rdg-authority.py'),'init',
                    '--store',str(w.store),'--plan-capable'],text=True,capture_output=True,env=w.env)
            return original_admin(command,payload,token)
        w.admin = admin
        w.setUp()
        self.addCleanup(w.tearDown)
        self.permissions = ['graph.write','graph.read','plan.create','plan.edit','plan.read','plan.branch']
        w.token = w.grant(self.permissions,['workspaces/','plans/'])['token']
        self.root = w.home/'plan-owner';self.root.mkdir()
        self.rel = 'plans/demo/plan.json'
        for n in ['rdg-temporal-plan-owner.py','rdg-temporal-plan.py','rdg-workflow.py','rdg-reference-io.py']:
            shutil.copy2(ROOT/'tools'/n,w.home/'tools'/n)
        self.seq = 0
        plan = {'schemaVersion':1,'kind':'temporalPlan','id':'demo','title':'План во времени',
                'identitySpace':'demo','revision':1,'status':'candidate',
                'steps':[],'sequence':[],'branches':[],'timeConstraints':[]}
        request = {'transactionId':'create-plan','op':'create','file':self.rel,'expectedRevision':0,'plan':plan}
        self.owner(request)

    def owner(self, request, token=None, ok=True, crash=None):
        path=self.w.home/'plan-request.json';path.write_text(json.dumps(request))
        r=subprocess.run(['python3','-B',str(self.w.home/'tools/rdg-temporal-plan-owner.py'),
            'apply','--root',str(self.root),'--graph-root',str(self.w.home/'graphs'),'--store',str(self.w.store),'--request',str(path)],
            text=True,capture_output=True,env={**self.w.env,'RDG_AUTH_TOKEN':token or self.w.token, **({'RDG_PLAN_TEST_CRASH':crash} if crash else {})})
        if ok:self.assertEqual(r.returncode,0,r.stderr)
        else:self.assertNotEqual(r.returncode,0,r.stdout)
        return r

    def placement_request(self, operations):
        self.seq+=1
        rev=WF.OWNER.read_snapshot(self.root,self.rel)['plan']['revision']
        return {'transactionId':'placement-'+str(self.seq),'op':'edit','file':self.rel,
                'expectedRevision':rev,'operations':operations}

    def place(self, sid, nid, kind='action', sequence=None):
        step={'id':sid,'kind':kind,'title':'Разместить '+nid,'state':'planned',
              'actionRef' if kind=='action' else 'requirementRef':{
                  'graphFile':self.w.rel,'identitySpace':'demo','nodeId':nid}}
        op={'op':'place','step':step}
        if sequence is None:
            op['timeConstraints']=[{'type':'notBefore','at':'2026-10-20','strength':'soft','basis':'Synthetic placement'}]
        else:op['sequence']=sequence
        return op

    def withdraw(self, aid, dispositions=None):
        return {'op':'withdraw_action','actionId':aid,'dispositions':dispositions or [],
                'event':self.w.event('action_withdrawn',actionId=aid,driverRequirementId='R0')}

    def view(self, token=None):
        return WF.read_workflow(self.root,self.rel,self.w.home/'graphs',self.w.store,
                               token or self.w.token,[self.w.rel])

    def plan_sources(self):
        return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*.json')}

    def test_whole_future_execution_withdrawal_new_variant_and_history(self):
        w=self.w
        w.apply([w.add('A1'),w.add('A2')])
        graph_before=w.sources()
        self.owner(self.placement_request([self.place('S1','A1'),self.place('S2','A2'),self.place('SG','R0','requirement')]))
        self.assertEqual(w.sources(),graph_before)
        before=self.view();self.assertEqual({r['nodeId'] for r in before['future']},{'A1','A2','R0'})
        self.assertTrue(all(n['status']=='candidate' for n in w.read()['nodes'] if n['kind']=='action'))
        w.apply([w.choose('A1')]);execution=w.apply([w.result('A1',action=True)])
        immediate=w.sources();w.assert_ok(w.write(execution,w.token));self.assertEqual(w.sources(),immediate)
        first=next(e for e in w.read()['events'] if e['type']=='action_executed')
        plan_bytes=self.plan_sources()
        middle=self.view();self.assertEqual([r['nodeId'] for r in middle['future']],['A2'])
        w.apply([self.withdraw('A1')])
        self.assertTrue(w.states()['A1']['complete'])
        self.assertFalse(w.states()['R0']['complete'])
        w.apply([w.choose('A2')])
        self.assertFalse(w.states()['A2']['complete'])
        w.apply([w.result('A2',action=True)])
        after=self.view();self.assertEqual(after['future'],[])
        self.assertEqual(self.plan_sources(),plan_bytes)
        self.assertIn(first,w.read()['events'])
        facts=[(r['kind'],r['targetId']) for r in after['history'] if r['kind'] not in ('graph_saved','plan_placement_saved','plan_placement_removed') and r.get('targetId') in ('A1','A2')]
        self.assertEqual(facts,[('action_selected','A1'),('action_executed','A1'),
                                ('action_withdrawn','A1'),('action_selected','A2'),
                                ('action_executed','A2')])
        self.assertEqual(len([e for e in w.read()['events'] if e['type']=='action_executed' and e['targetId']=='A1']),1)
        stable=w.sources();w.assert_denied(w.write(execution,w.token),'REPLAY_STATE_CHANGED');self.assertEqual(w.sources(),stable)
        destination=os.environ.get('RDG_WORKFLOW_DEMO_DIR')
        if destination:
            out=Path(destination);out.mkdir(parents=True,exist_ok=True)
            for name,value in [('before',before),('after',after)]:
                (out/('workflow-'+name+'.html')).write_text(WF.html(value))
                (out/('workflow-'+name+'.md')).write_text(WF.markdown(value))
                (out/('workflow-'+name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

    def test_one_package_records_only_final_goal_and_keeps_fact_order(self):
        w=self.w;w.seq=7
        w.apply([w.add('A1'),w.choose('A1'),w.result('A1',action=True),
                 self.withdraw('A1'),w.add('A2'),w.choose('A2'),w.result('A2',action=True)])
        rows=[r for r in self.view()['history'] if r['kind'] in ('action_executed','action_withdrawn')]
        self.assertEqual([(r['kind'],r['targetId']) for r in rows],
            [('action_executed','A1'),('action_withdrawn','A1'),('action_executed','A2')])
        goals=[e for e in w.read()['events'] if e['type']=='requirement_achieved' and e['targetId']=='R0']
        self.assertEqual(len(goals),1)
        self.assertEqual([d['edge']['to'] for d in goals[0]['basis']['dependencies']],['A2'])
        self.assertTrue(w.states()['A1']['complete']);self.assertTrue(w.states()['R0']['complete'])

    def test_unscheduled_action_stays_in_history_after_edit_and_no_second_execution(self):
        w=self.w;w.apply([w.add('A'),w.choose('A'),w.result('A',action=True)])
        original=next(e for e in w.read()['events'] if e['type']=='action_executed')
        w.apply([w.edit('edit_node',nodeId='A',changes={'title':'<script>changed</script>'})])
        self.assertTrue(w.states()['A']['complete']);self.assertFalse(w.states()['A']['currentScopeComplete'])
        self.assertFalse(w.states()['R0']['complete'])
        before=w.sources();r=w.write(w.patch([w.result('A',action=True)],w.read()['revision'],'forbidden-second'),w.token)
        w.assert_denied(r,'already executed');self.assertEqual(w.sources(),before)
        view=self.view();self.assertEqual(view['future'],[])
        self.assertEqual([r['title'] for r in view['history'] if r['kind']=='action_executed'],[original['basis']['node']['title']])
        self.assertNotIn('<script>',WF.html(view))
        self.assertFalse((self.root/'plans/demo/plan.json').read_text().find('actionRef')>=0)

    def test_placement_edit_unplace_cas_replay_and_no_graph_writes(self):
        w=self.w;w.apply([w.add('A')]);graph=w.sources()
        request=self.placement_request([self.place('S','A')]);self.owner(request)
        saved=self.plan_sources();self.assertTrue(json.loads(self.owner(request).stdout)['idempotent'])
        self.assertEqual(saved,self.plan_sources());self.assertEqual(w.sources(),graph)
        stale=copy.deepcopy(request);stale['transactionId']='stale'
        self.assertIn('CAS_MISMATCH',self.owner(stale,ok=False).stderr)
        self.owner(self.placement_request([{'op':'unplace','stepId':'S'}]))
        plan=WF.OWNER.read_snapshot(self.root,self.rel)['plan']
        self.assertEqual(plan['steps'],[]);self.assertEqual(plan['timeConstraints'],[]);self.assertEqual(plan['sequence'],[])
        self.assertEqual(w.sources(),graph)

    def test_sequence_only_r_and_action_and_unsupported_dependency_context(self):
        self.w.apply([self.w.add('A'),self.w.prepare('A','R1')])
        self.owner(self.placement_request([self.place('SA','A',sequence=[]),self.place('SR','R1','requirement',sequence=[{'before':'SA','after':'SR'}])]))
        self.assertEqual([r['nodeId'] for r in self.view()['future']],['A','R1'])
        self.assertEqual(next(n for n in self.w.read()['nodes'] if n['id']=='R1')['status'],'potential')
        plan=WF.OWNER.read_snapshot(self.root,self.rel)['plan']
        inspected=WF.OWNER.PLAN.inspect(plan,self.w.home/'graphs')
        self.assertEqual(inspected['requirementReferences'][0]['verification'],'resolved')
        coverage=DEP.plan_views({'branchesById':{},'stepsById':{s['id']:s for s in plan['steps']}})['reviewCoverage']
        self.assertFalse(coverage['complete']);self.assertEqual(coverage['diagnostic'],'REQUIREMENT_STEPS_NOT_COVERED')

    def test_withdrawal_is_separately_authorized_and_denial_does_not_write(self):
        w=self.w;w.apply([w.add('A'),w.choose('A'),w.result('A',action=True)])
        only_results=w.grant(['graph.record_action_execution'])['token']
        before=w.sources();request=w.patch([self.withdraw('A')],w.read()['revision'],'denied-withdrawal')
        w.assert_denied(w.write(request,only_results),'MISSING_PERMISSION: graph.withdraw_action')
        self.assertEqual(w.sources(),before)
        withdrawal=w.grant(['graph.withdraw_action'])['token'];w.assert_ok(w.write(request,withdrawal))
        self.assertTrue(w.states()['A']['complete'])
        self.assertIn(('action_withdrawn','A'),[(r['kind'],r.get('targetId')) for r in self.view()['history']])

    def test_withdrawal_keeps_protected_policy_guard(self):
        w=self.w;w.apply([w.add('A'),w.choose('A')])
        before=w.sources()
        w.assert_denied(w.write(w.patch([self.withdraw('A')],w.read()['revision'],'not-executed-withdraw'),w.token),'EXECUTED_INSTANCE_REQUIRED')
        self.assertEqual(w.sources(),before)
        graph=w.read();graph['nodes'][0]['reconsiderationPolicy']={'mode':'protected','authorityPrincipal':'synthetic-owner'}
        w.path.write_text(json.dumps(graph))
        before=w.sources();r=w.write(w.patch([self.withdraw('A')],graph['revision'],'protected-withdraw'),w.token)
        w.assert_denied(r,'PROTECTED_OWNER_GRANT_REQUIRED');self.assertEqual(w.sources(),before)

    def test_child_dispositions_are_required_and_shared_goal_remains_supported(self):
        w=self.w
        w.apply([w.add('D1',action_type='decomposition'),w.prepare('D1','RS'),w.prepare('D1','RC','method_correctness'),w.choose('D1'),w.result('RC')])
        before=w.sources();r=w.write(w.patch([self.withdraw('D1')],w.read()['revision'],'missing-dispositions'),w.token)
        w.assert_denied(r,'EXACT_CHILD_DISPOSITIONS_REQUIRED');self.assertEqual(w.sources(),before)
        w.apply([w.add('D2'),w.prepare('D2','RS',existing=True),w.choose('D2')])
        dispositions=[{'requirementId':'RS','effect':'retain_supported','supportingActionIds':['D2'],'reason':'New variant keeps the same subgoal'},
                      {'requirementId':'RC','effect':'deactivate','reason':'Old correctness is not required','downstreamScope':'single_graph_verified'}]
        w.apply([self.withdraw('D1',dispositions),w.result('D2',action=True),w.result('RS')])
        self.assertTrue(w.states()['R0']['complete']);self.assertTrue(w.states()['D1']['complete'])
        self.assertEqual(next(n for n in w.read()['nodes'] if n['id']=='RS')['status'],'active')

    def test_plan_read_and_graph_read_remain_separate(self):
        token=self.w.grant(['plan.read'],['plans/'])['token']
        with self.assertRaisesRegex(ValueError,'GRAPH_READ_SCOPE_DENIED|MISSING_PERMISSION: graph.read'):
            self.view(token)
        token=self.w.grant(['graph.read'],['workspaces/'])['token']
        with self.assertRaisesRegex(ValueError,'PLAN_SCOPE_DENIED|MISSING_PERMISSION: plan.read'):
            self.view(token)

    def test_withdrawal_recovery_has_one_event_and_never_loses_execution(self):
        w=self.w;w.apply([w.add('A'),w.choose('A'),w.result('A',action=True)])
        request=w.patch([self.withdraw('A')],w.read()['revision'],'recover-withdraw')
        path=w.home/'crash-withdraw.json';path.write_text(json.dumps(request))
        script="from importlib.machinery import SourceFileLoader\nimport json,os,sys\nw=SourceFileLoader('crash',sys.argv[1]).load_module()\nreal=w.write_json\ndef crash(p,o):\n real(p,o)\n if p.name=='graph.json':os._exit(91)\nw.write_json=crash\nw.execute(json.load(open(sys.argv[2])))"
        result=subprocess.run(['python3','-B','-c',script,str(w.home/'tools/graph-package.py'),str(path)],
            text=True,capture_output=True,env={**w.env,'RDG_AUTH_TOKEN':w.token})
        self.assertEqual(result.returncode,91,result.stderr)
        with self.assertRaisesRegex(ValueError,'ACTIVITY_RECOVERY_REQUIRED'):self.view()
        w.assert_ok(w.write(request,w.token))
        history=self.view()['history']
        self.assertEqual(len([r for r in history if r['kind']=='action_withdrawn']),1)
        self.assertEqual(len([r for r in history if r['kind']=='action_executed']),1)
        w.assert_ok(w.write(request,w.token));self.assertEqual(self.view()['history'],history)

    def test_placement_recovery_and_read_permission_do_not_change_graph(self):
        w=self.w;w.apply([w.add('A')]);before=w.sources()
        request=self.placement_request([self.place('S','A')])
        result=self.owner(request,ok=False,crash='prepared');self.assertEqual(result.returncode,91)
        with self.assertRaisesRegex(ValueError,'RECOVERY_REQUIRED'):self.view()
        self.assertTrue(WF.OWNER.recover(self.root)['recovered'])
        self.assertTrue(json.loads(self.owner(request).stdout)['idempotent'])
        self.assertEqual([r['nodeId'] for r in self.view()['future']],['A'])
        self.assertEqual(w.sources(),before)

    def test_wrong_owner_ref_fails_instead_of_hiding_future(self):
        self.w.apply([self.w.add('A')]);op=self.place('S','A')
        op['step']['actionRef']['identitySpace']='another-owner'
        before=self.plan_sources()
        result=self.owner(self.placement_request([op]),ok=False)
        self.assertIn('PLAN_REFERENCE_IDENTITY_OR_NODE_MISMATCH',result.stderr)
        self.assertEqual(before,self.plan_sources())
        self.assertEqual(self.view()['future'],[])

    def test_cli_renders_the_same_future_and_history(self):
        w=self.w;w.apply([w.add('A')]);self.owner(self.placement_request([self.place('S','A')]))
        r=subprocess.run(['python3','-B',str(w.home/'tools/rdg-workflow.py'),'--root',str(self.root),
            '--file',self.rel,'--graph-root',str(w.home/'graphs'),'--graph',w.rel,'--store',str(w.store)],
            text=True,capture_output=True,env={**w.env,'RDG_AUTH_TOKEN':w.token})
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout),self.view())

    def test_result_material_snapshot_survives_annotation_edit_and_legacy_has_no_fabricated_material(self):
        w=self.w
        w.apply([w.add('A'),w.choose('A'),w.result('A',action=True)])
        first=next(e for e in w.read()['events'] if e['type']=='action_executed')
        snapshot=copy.deepcopy(first['viewSnapshot'])
        w.apply([w.edit('edit_node',nodeId='A',changes={'canonBlock':{
            'recommended':[{'id':'NEW','text':'Current canon after execution'}],'contraindicated':[]}}),
            {'op':'append_qrpe','targetId':'A','issue':{'id':'NEW-Q','text':'Current issue','status':'open'}}])
        history=next(r for r in self.view()['history'] if r['kind']=='action_executed')
        self.assertEqual(history['nodeSnapshot'],snapshot)
        self.assertTrue(history['materialSnapshotAvailable'])
        self.assertEqual(history['snapshotProvenance'],'event-view-snapshot')
        self.assertNotIn('Current canon',json.dumps(history))
        self.assertEqual(first,next(e for e in w.read()['events'] if e['type']=='action_executed'))
        # Simulate an old owner whose result predates view snapshots, without journals.
        old=w.read()
        for e in old['events']:
            e.pop('viewSnapshot',None);e.pop('viewSnapshotSHA256',None)
        old_root=w.home/'legacy-source';path=old_root/w.rel;path.parent.mkdir(parents=True)
        path.write_text(json.dumps(old))
        report=WF.ACTIVITY.read_activity(old_root,[w.rel])
        legacy=next(r for r in report['activities'] if r['kind']=='action_executed')
        self.assertFalse(legacy['materialSnapshotAvailable'])
        self.assertEqual(legacy['snapshotProvenance'],'completion-basis')
        self.assertNotIn('canonBlock',legacy['nodeSnapshot'])


if __name__=='__main__':unittest.main()
