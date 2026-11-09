#!/usr/bin/env python3
"""PR-6: real coordinator persistence and explicit limits on isolated owners."""
import copy
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=SourceFileLoader('pr6_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()

class DecisionIntegration(BASE.PortableApplication):
    # Run only the new scenarios here; the inherited legacy suite has its own entry.
    def work_lens(self):
        existing=next((p for p in self.app().catalog()['packages'] if p.get('lensKey')=='work'),None)
        if existing:return existing
        graph=json.loads((ROOT/'tools/rdg-agent-lenses/work-decision.json').read_text(encoding='utf8'))
        req=self.req('create',path='lenses/test-work',role='lens',lensKey='work',
                     coreModel='rdg-decision-v1',rootReason='Test-only paper definition',graph=graph)
        self.app().request(req)
        return next(p for p in self.app().catalog()['packages'] if p.get('lensKey')=='work')

    def decision(self):
        request=self.req('create',path='working/decision',role='working',title='PR-6 synthetic',
            scope='Synthetic only',coreModel='rdg-decision-v1',rootReason='Verify integration')
        ident=self.app().request(request)['packages'][0]['packageId']
        self.command(ident,'add',entity={'id':'D1','kind':'decision','title':'Potential method','description':'Not selected'},
            initialRelations=[{'id':'RD','type':'DRIVES','from':'R1','to':'D1'}])
        self.command(ident,'add',entity={'id':'A1','kind':'action','title':'Explicit task','description':'Not executed',
            'actionType':'task','lowLevel':False,'targetIds':[],'groupIds':[]},
            initialRelations=[{'id':'DA','type':'REQUIRES_ACTION','from':'D1','to':'A1'}])
        self.command(ident,'work_graph',workGraph={'id':'WG1','title':'Explicit integration area','rootIds':['R1'],'memberIds':['R1','D1','A1']})
        return ident

    def plan(self,ident):
        self.app().request(self.app().schema('plan_create',ident)['request'])

    def test_pr6_work_graph_color_and_change_snapshot_survive_history_readback(self):
        ident=self.decision();before=self.current(ident)
        area=before['graph']['workGraphs'][0]
        self.command(ident,'work_graph',workGraph={**area,'title':'Integration area · updated','colorKey':'violet'})
        current=self.current(ident)
        self.assertEqual(current['graph']['workGraphs'][0]['colorKey'],'violet')
        event=next(e for e in reversed(current['graph']['events']) if e['type']=='work_graph_changed' and
                   e.get('workGraphChange',{}).get('workGraphId')==area['id'])
        change=event['workGraphChange']
        self.assertEqual(change['action'],'updated')
        self.assertEqual(change['before']['title'],area['title'])
        self.assertEqual(change['after']['title'],'Integration area · updated')
        self.assertEqual(change['after']['colorKey'],'violet')
        history=self.app().history(ident)
        record=next(row for row in history['events'] if row['event']['id']==event['id'])
        self.assertEqual(record['event']['workGraphChange'],change)
        self.assertEqual(current['graph']['revision'],before['graph']['revision']+1)

    def test_pr6_order_layout_retry_and_restart(self):
        ident=self.decision();self.plan(ident);graph=copy.deepcopy(self.current(ident)['graph'])
        req=self.app().schema('place',ident,'D1')['request'];req['note']='Potential method before selection'
        before=self.sources();preview=self.app().request(req,preflight=True)
        self.assertEqual(before,self.sources())
        result=self.app().request(req,expected_input_binding=preview['inputBinding'])
        self.assertTrue(result['published']);self.assertTrue(self.app().request(req)['idempotent'])
        placed=self.current(ident);self.assertEqual(placed['plan']['schemaVersion'],3)
        self.assertEqual(len(placed['plan']['mainStepIds']),1);self.assertEqual(placed['plan']['timeConstraints'],[])
        self.assertEqual(placed['planView']['placements'][0]['bucket'],'future')
        for nid in ('R1','A1'):
            req=self.app().schema('place',ident,nid)['request'];req['note']='Ordered existing entity'
            self.app().request(req)
        keys=[self.app().read(ident,True,v)['view']['graphKey'] for v in
            ({'kind':'graph'},{'kind':'workGraph','id':'WG1'},{'kind':'focus','id':'D1'})]
        self.assertEqual(len(set(keys)),1)
        req=self.app().schema('layout_edit',ident)['request']
        req['commands']=[{'type':'set_positions','graphKey':keys[0],'positions':{'D1':{'x':312,'y':-17}}}]
        self.app().request(req);self.assertTrue(self.app().request(req)['idempotent'])
        fresh=self.app().read(ident,True);self.assertEqual(fresh['graph'],graph)
        self.assertEqual(fresh['layouts']['layouts'][keys[0]]['positions']['D1'],{'x':312,'y':-17})
        self.assertEqual([r['step']['ref']['nodeId'] for r in fresh['planView']['placements']],['D1','R1','A1'])
        # Read the actual immutable Plan bytes selected by the published package head.
        row=self.store.read(ident);path=self.store.package_path(row['path'])/row['head']['current']['plan']
        self.assertEqual(json.loads(path.read_bytes()),fresh['plan'])

    def test_pr6_rejects_invalid_lane_refs_profile_and_stale_inputs_without_write(self):
        ident=self.decision();self.plan(ident)
        req=self.app().schema('place',ident,'D1')['request'];req['note']='One first placement';self.app().request(req)
        for mutate in (lambda p:p['mainStepIds'].clear(),lambda p:p['mainStepIds'].append(p['mainStepIds'][0]),
                       lambda p:p['steps'][0]['ref'].update(nodeId='absent'),
                       lambda p:p['steps'][0]['ref'].update(identitySpace='foreign'),
                       lambda p:p.update(forks=[{'id':'not-supported'}])):
            req=self.app().schema('plan_edit',ident)['request'];mutate(req['plan']);before=self.sources()
            with self.assertRaises(ValueError):self.app().request(req)
            self.assertEqual(self.sources(),before)
        req=self.app().schema('layout_edit',ident)['request'];key=self.current(ident)['view']['graphKey']
        req['commands']=[{'type':'set_positions','graphKey':key,'positions':{'absent':{'x':1,'y':2}}}]
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'LAYOUT_SCOPE'):self.app().request(req)
        self.assertEqual(before,self.sources())
        stale=self.app().schema('place',ident,'A1')['request'];stale['note']='Stale placement'
        other=self.app().schema('place',ident,'R1')['request'];other['note']='Concurrent placement';self.app().request(other)
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'CAS_MISMATCH'):self.app().request(stale)
        self.assertEqual(before,self.sources())
        delete=self.command_request(ident,'remove',nodeIds=['D1']);delete['op']='delete'
        delete.pop('command');delete.pop('data');delete['nodeIds']=['D1']
        self.app().request(delete)
        current=self.current(ident);self.assertNotIn('D1',{n['id'] for n in current['graph']['nodes']})
        self.assertFalse(any(s['ref']['nodeId']=='D1' for s in current['plan']['steps']))

    def test_pr6_plan_permission_and_layout_external_action_are_enforced(self):
        ident=self.decision();self.plan(ident)
        grant=self.authority.manage('issue',self.admin,{'permissions':['graph.read','graph.write','plan.read'],
            'scopes':['packages/'+self.namespace+'/']})
        req=self.app(grant['token']).schema('place',ident,'D1')['request'];req['note']='Denied Plan write'
        before=self.sources()
        with self.assertRaises(ValueError):self.app(grant['token']).request(req)
        self.assertEqual(before,self.sources())
        external=self.current(ident)['graph']['externalActions'][0]['id']
        req=self.app().schema('layout_edit',ident)['request'];key=self.current(ident)['view']['graphKey']
        req['commands']=[{'type':'set_positions','graphKey':key,'positions':{external:{'x':1,'y':2}}}]
        with self.assertRaisesRegex(ValueError,'LAYOUT_SCOPE'):self.app().request(req)
        self.assertEqual(before,self.sources())

    def test_pr6_plan_retry_after_staging_and_time_edit_preserves_order(self):
        ident=self.decision();self.plan(ident)
        req=self.app().schema('place',ident,'D1')['request'];req['note']='Interrupted first placement'
        graph=copy.deepcopy(self.current(ident)['graph'])
        def fail(stage):
            if stage=='staged':raise RuntimeError('Synthetic PR-6 interruption')
        with self.assertRaisesRegex(RuntimeError,'PR-6 interruption'):self.app().request(req,failpoint=fail)
        self.assertEqual(self.current(ident)['plan']['mainStepIds'],[])
        self.assertTrue(self.app().request(req)['published'])
        self.assertTrue(self.app().request(req)['idempotent'])
        first=self.current(ident)['plan']['mainStepIds'][0]
        req=self.app().schema('place',ident,'A1')['request'];req['note']='Second task';self.app().request(req)
        order=self.current(ident)['plan']['mainStepIds']
        req=self.app().schema('place',ident,'D1')['request'];req.update(stepId=first,at='2026-11-03',note='Only change time')
        req.pop('afterStepId');self.app().request(req)
        self.assertEqual(self.current(ident)['plan']['mainStepIds'],order)
        req=self.app().schema('place',ident,'D1')['request'];req.update(stepId=first,at='',note='Remove time');req.pop('afterStepId')
        self.app().request(req);self.assertEqual(self.current(ident)['plan']['timeConstraints'],[])
        self.assertEqual(self.current(ident)['plan']['mainStepIds'],order)
        self.assertEqual(self.current(ident)['graph'],graph)

    def test_pr6_fundamental_work_variant_uses_profile_dispatch(self):
        run=subprocess.run(['python3','-B',str(ROOT/'tools/rdg-agent.py'),'lens','--lens','work',
            '--model-profile','rdg-decision-v1'],capture_output=True,text=True,timeout=30)
        self.assertEqual(run.returncode,0,run.stderr);value=json.loads(run.stdout)
        self.assertTrue(value['validated']);self.assertEqual(value['graph']['coreModel'],'rdg-decision-v1')
        self.assertEqual(value['graphWrites'],0);self.assertEqual(value['planWrites'],0)
        ident=self.decision();before=self.current(ident)['graph']
        lens=self.work_lens()['packageId']
        context={k:v for k,v in self.config().items() if k!='authorityStore'}
        context.update(profile='portable',packageId=ident)
        path=self.base/'context.json';path.write_text(json.dumps(context))
        import os
        env={**os.environ,'RDG_AUTH_STORE':str(self.authority.path),'RDG_AUTH_TOKEN':self.token}
        for args in (['lens','--lens','work'],['open','--lens','work','--detail','full']):
            run=subprocess.run(['python3','-B',str(ROOT/'tools/rdg-agent.py'),*args,'--context',str(path)],
                capture_output=True,text=True,timeout=30,env=env)
            self.assertEqual(run.returncode,0,run.stderr);self.assertNotIn(self.token,run.stdout+run.stderr)
            data=json.loads(run.stdout)
            if args[0]=='lens':
                self.assertEqual(data['package']['packageId'],lens)
                self.assertNotEqual(data['graph']['identitySpace'],before['identitySpace'])
            else:
                self.assertEqual(data['package']['packageId'],ident)
                self.assertEqual([r['packageId'] for r in data['lenses']],[lens])
        probe=subprocess.run(['python3','-B',str(ROOT/'tools/rdg-agent.py'),'schema',
            '--action','core','--core-command','add','--entity-kind','question','--node','D1',
            '--context',str(path)],capture_output=True,text=True,timeout=30,env=env)
        self.assertEqual(probe.returncode,0,probe.stderr)
        self.assertEqual(json.loads(probe.stdout)['request']['data']['entity']['kind'],'question')
        self.assertEqual(self.current(ident)['graph'],before)


    def temporal_fixture(self):
        ident=self.decision()
        self.command(ident,'add',entity={'id':'D2','kind':'decision','title':'Alternative method','description':'Paper alternative'},initialRelations=[{'id':'RD2','type':'DRIVES','from':'R1','to':'D2'}])
        self.command(ident,'add',entity={'id':'A2','kind':'action','title':'Alternative task','description':'Paper task','actionType':'task','lowLevel':False,'targetIds':[],'groupIds':[]},initialRelations=[{'id':'D2A2','type':'REQUIRES_ACTION','from':'D2','to':'A2'}])
        self.command(ident,'decision_group',group={'id':'G','title':'Methods','parentId':'R1','selectionRequired':True,'mutuallyExclusive':True,'members':[{'id':'GD1','decisionId':'D1'},{'id':'GD2','decisionId':'D2'}]})
        self.plan(ident);before=self.current(ident);g=before['graph'];ns={n['id']:n for n in g['nodes']};req=self.app().schema('plan_edit',ident)['request'];p=req['plan']
        p['steps']=[{'id':'S-'+i,'title':ns[i]['title'],'kind':ns[i]['kind'],'state':'planned' if i=='R1' else 'possible','ref':BASE.P.reference(ident,g,i)} for i in ('A1','A2','R1')]
        p['mainStepIds']=['S-R1'];p['timeConstraints']=[{'stepId':'S-A1','type':'notBefore','at':'2026-11-06','strength':'soft','basis':'Synthetic date'}]
        p['forks']=[{'id':'F','title':'Method at a point in time','afterStepId':None,'startAt':'2026-11-06T09:00:00+07:00','end':{'title':'Common outcome','at':'2026-11-07T12:00:00+07:00'},'cases':[{'id':'C1','title':'First method','decisionIds':['D1'],'stepIds':['S-A1']},{'id':'C2','title':'Alternative','decisionIds':['D2'],'stepIds':['S-A2']}]}]
        return ident,req,before

    def test_pr6_plan_markers_start_without_action_and_join_shared_continuation_with_client_parity(self):
        ident,req,before=self.temporal_fixture();app=self.app();preview=app.request(req,preflight=True);self.assertEqual(self.current(ident)['plan'],before['plan'])
        result=app.request(req,expected_input_binding=preview['inputBinding']);self.assertTrue(result['published']);self.assertTrue(app.receipt(ident,req['transactionId'])['found']);self.assertTrue(app.request(req)['idempotent'])
        current=self.current(ident);self.assertEqual(current['graph'],before['graph']);self.assertEqual(current['layouts'],before['layouts']);self.assertEqual(current['plan']['mainStepIds'],['S-R1'])
        js="const fs=require('node:fs'),P=require(process.argv[1]);const x=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(P.temporalPlan(x.plan,x.graph,x.completion,x.spec,x.packageId)));"
        for case in ('C1','C2'):
            for window in ({},{'from':'2026-11-08','to':'2026-11-09'}):
                spec={'kind':'graph','shownCases':{'F':case},'planWindow':window};viewed=app.read(ident,True,spec);v=viewed['planView'];self.assertEqual([r['type'] for r in v['road']],['fork','placement','join','placement']);self.assertEqual(v['shownStepIds'].count('S-R1'),1)
                payload={'plan':current['plan'],'graph':current['graph'],'completion':viewed['view']['completion'],'spec':spec,'packageId':ident}
                client=json.loads(subprocess.check_output(['node','-e',js,str(ROOT/'tools/rdg-visual-projection.js')],input=json.dumps(payload).encode()));self.assertEqual(client,v)
                self.assertEqual(viewed['graph'],before['graph']);self.assertTrue(all(n['selectionState']=='discovered' for n in viewed['graph']['nodes'] if n['kind']=='decision'))
        self.assertEqual(self.current(ident)['plan'],current['plan'])

    def test_pr6_plan_markers_reject_invalid_time_end_and_readonly_author_atomically(self):
        ident,req,before=self.temporal_fixture();app=self.app()
        for mutate in (lambda f:f.update(startAt='2026-02-30'),lambda f:f.update(startAt='2026-11-06T09:00:00'),lambda f:f.update(end=True),lambda f:f['end'].update(at='2026-11-05T12:00:00+07:00'),lambda f:f.update(afterStepId='S-A1')):
            bad=copy.deepcopy(req);bad['transactionId']=self.req('plan_edit')['transactionId'];mutate(bad['plan']['forks'][0]);files=self.sources()
            with self.assertRaisesRegex(ValueError,'PLAN_'):app.request(bad,preflight=True)
            self.assertEqual(self.sources(),files)
        grant=self.authority.manage('issue',self.admin,{'permissions':['graph.read','plan.read'],'scopes':['packages/'+self.namespace+'/']})
        files=self.sources()
        with self.assertRaisesRegex(ValueError,'PERMISSION|SCOPE'):self.app(grant['token']).request(req,preflight=True)
        self.assertEqual(self.sources(),files);self.assertEqual(self.current(ident)['graph'],before['graph'])

    def test_pr6_plan_copy_preserves_optional_markers_and_maps_root_decisions(self):
        ident,req,_=self.temporal_fixture();app=self.app();app.request(req);source=self.current(ident)
        copy_request=app.schema('copy',ident)['request'];copy_request['path']='copies/temporal-markers';copy_request['note']='Synthetic copied schedule';copied=app.request(copy_request)['packages'][0]['packageId'];row=app.read(copied,True)
        f=row['plan']['forks'][0];self.assertEqual(f['startAt'],source['plan']['forks'][0]['startAt']);self.assertEqual(f['end'],source['plan']['forks'][0]['end']);self.assertIsNone(f['afterStepId'])
        ids={n['id'] for n in row['graph']['nodes'] if n['kind']=='decision'};self.assertTrue(all(set(c['decisionIds'])<=ids for c in f['cases']));self.assertTrue(all(s['ref']['packageId']==copied for s in row['plan']['steps']));self.assertEqual(self.current(ident)['plan'],source['plan'])


if __name__=='__main__':
    names=[n for n in DecisionIntegration.__dict__ if n.startswith('test_pr6_')]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(DecisionIntegration(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
