#!/usr/bin/env python3
"""Safe manual placement edits through actual Plan/Graph owners, isolated sources."""
from importlib.machinery import SourceFileLoader
import copy
import json
import os
from pathlib import Path
import subprocess
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
F=SourceFileLoader('placement_edit_fixture',str(ROOT/'tests/rdg-workflow.acceptance.test.py')).load_module()
H=SourceFileLoader('placement_edit_helper',str(ROOT/'tools/rdg-workflow-helper.py')).load_module()

class PlacementEdit(unittest.TestCase):
    def setUp(self):
        self.f=F.Workflow('test_whole_future_execution_withdrawal_new_variant_and_history')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.w=self.f.w;self.w.apply([self.w.add('A1'),self.w.add('A2'),self.w.add('A3')])
        self.editor=H.Editor(self.f.root,self.f.rel,self.w.home/'graphs',self.w.rel,
            self.w.store,self.w.token,tools=self.w.home/'tools')
        self.seq=0

    def plan(self):
        return self.editor.snapshot()['sources']['plan']

    def command(self,node='A1',**extra):
        self.seq+=1;v=self.editor.snapshot()
        return {'action':'place','transactionId':'safe-place-'+str(self.seq),'nodeId':node,
            'expectedGraphRevision':v['sources']['graphs'][self.w.rel]['revision'],
            'expectedPlanRevision':v['sources']['plan']['revision'],'note':'Synthetic date edit',**extra}

    def place(self,node='A1',**extra):
        return self.editor.dispatch(self.command(node,**extra))

    def seed(self,*,date_b=False,delay=0,hard=False,deadline=False):
        a=self.f.place('S-A1','A1');b=self.f.place('S-A2','A2',
            sequence=[{'before':'S-A1','after':'S-A2','minDelayDays':delay}])
        if hard:a['timeConstraints'][0]['strength']='hard'
        if deadline:a['timeConstraints'].append({'type':'deadline','at':'2026-10-25',
            'strength':'hard','basis':'Synthetic existing candidate deadline'})
        a['step']['actionRef']['observedGraphRevision']=self.w.read()['revision']
        if date_b:b['timeConstraints']=[{'type':'notBefore','at':'2026-10-21',
            'strength':'soft','basis':'Synthetic second date'}]
        self.f.owner(self.f.placement_request([a,b,self.f.place('S-A3','A3')]))

    def test_date_edit_preserves_successor_with_date_or_only_order(self):
        self.seed();before=self.plan()['sequence'];graph=self.w.sources()
        self.place(at='2026-10-22',afterStepId='')
        self.assertEqual(before,self.plan()['sequence']);self.assertEqual(graph,self.w.sources())
        self.place('A2',at='2026-10-23',afterStepId='S-A1')
        self.place(at='2026-10-21',afterStepId='')
        self.assertEqual(before,self.plan()['sequence'])

    def test_date_edit_keeps_deadline_strength_step_reference_and_graph(self):
        self.seed(hard=True,deadline=True);before=copy.deepcopy(self.plan());graph=self.w.sources()
        req=self.command(at='2026-10-21',afterStepId='')
        self.editor.dispatch(req)
        after=self.plan()
        self.assertEqual(next(s for s in before['steps'] if s['id']=='S-A1'),
                         next(s for s in after['steps'] if s['id']=='S-A1'))
        old=[r for r in before['timeConstraints'] if r['stepId']=='S-A1']
        new=[r for r in after['timeConstraints'] if r['stepId']=='S-A1']
        expected=copy.deepcopy(old)
        next(r for r in expected if r['type']=='notBefore')['at']='2026-10-21'
        self.assertEqual(new,expected);self.assertEqual(graph,self.w.sources())
        sources=self.f.plan_sources();result=self.editor.dispatch(req)
        self.assertTrue(result['replayed']);self.assertEqual(sources,self.f.plan_sources())

    def test_change_and_clear_predecessor_preserve_unedited_minimum_delay(self):
        self.seed(delay=3)
        self.place('A2',afterStepId='S-A3')
        self.assertEqual(self.plan()['sequence'],[{'before':'S-A3','after':'S-A2','minDelayDays':3}])
        self.place('A2',afterStepId='',at='2026-10-23')
        self.assertEqual(self.plan()['sequence'],[])
        self.assertTrue(any(r['stepId']=='S-A2' for r in self.plan()['timeConstraints']))

    def test_clear_shown_fields_keeps_deadline_and_successor(self):
        self.seed(hard=True,deadline=True);before=copy.deepcopy(self.plan())
        self.place(at='',afterStepId='')
        after=self.plan()
        self.assertEqual(before['sequence'],after['sequence'])
        self.assertEqual([r for r in after['timeConstraints'] if r['stepId']=='S-A1'],
            [r for r in before['timeConstraints'] if r['stepId']=='S-A1' and r['type']=='deadline'])

    def test_complex_inputs_fail_without_partial_write(self):
        self.seed(date_b=True)
        variants=[
            {'timeConstraints':[{'stepId':'S-A1','type':'notBefore','at':'2026-10-20T12:00:00Z',
                'strength':'hard','basis':'Precise time'}]},
            {'timeConstraints':[{'stepId':'S-A1','type':'notBefore','at':'2026-10-'+day,
                'strength':'hard','basis':'Separate bound'} for day in ['20','21']]},
            {'sequence':[{'before':'S-A1','after':'S-A2'},{'before':'S-A3','after':'S-A2'}]}
        ]
        for changes in variants:
            with self.subTest(changes=changes):
                plan=self.plan()
                for key,value in changes.items():
                    plan[key]=([r for r in plan[key] if r['stepId']!='S-A1']+value
                        if key=='timeConstraints' else value)
                rev=plan['revision'];plan['revision']=rev+1
                self.f.seq+=1
                self.f.owner({'transactionId':'seed-complex-'+str(self.f.seq),'op':'edit',
                    'file':self.f.rel,'expectedRevision':rev,'plan':plan})
                before=self.f.plan_sources(),self.w.sources()
                node='A2' if 'sequence' in changes else 'A1'
                with self.assertRaisesRegex(ValueError,'HELPER_COMPLEX_PLACEMENT_USE_FULL_API'):
                    self.place(node,at='2026-10-22',afterStepId='')
                self.assertEqual(before,(self.f.plan_sources(),self.w.sources()))

    def test_cas_and_permission_denial_do_not_write(self):
        self.seed();stale=self.command(at='2026-10-22',afterStepId='')
        self.place(at='2026-10-21',afterStepId='')
        before=self.f.plan_sources(),self.w.sources()
        with self.assertRaisesRegex(ValueError,'CAS_MISMATCH'):self.editor.dispatch(stale)
        self.assertEqual(before,(self.f.plan_sources(),self.w.sources()))
        token=self.w.grant(['graph.read','plan.read'],['workspaces/','plans/'])['token']
        editor=H.Editor(self.f.root,self.f.rel,self.w.home/'graphs',self.w.rel,
            self.w.store,token,tools=self.w.home/'tools')
        req=self.command(at='2026-10-23',afterStepId='')
        with self.assertRaisesRegex(ValueError,'plan.edit'):editor.dispatch(req)
        self.assertEqual(before,(self.f.plan_sources(),self.w.sources()))

    def test_controller_round_trip_via_live_helper_and_writers(self):
        self.seed(hard=True,deadline=True,delay=2);graph=self.w.sources()
        server=H.make_server(self.editor)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            env={**os.environ,'RDG_PLACEMENT_TEST_URL':server.session_url}
            for key in ['RDG_WORKFLOW_TEST_URL','RDG_WORKFLOW_TEST_DIR','RDG_CROSS_TEST_URL']:env.pop(key,None)
            run=subprocess.run(['node','--test','tests/rdg-workflow-ui.test.cjs'],cwd=ROOT,
                env=env,text=True,capture_output=True,timeout=90)
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
            out=os.environ.get('RDG_PLACEMENT_TEST_LOG')
            if out:Path(out).write_text(run.stdout+run.stderr)
            self.assertEqual(graph,self.w.sources())
        finally:server.shutdown();server.server_close();thread.join(2)

if __name__=='__main__':unittest.main()
