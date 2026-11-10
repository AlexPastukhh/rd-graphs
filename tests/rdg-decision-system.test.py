#!/usr/bin/env python3
"""D3-D9 integration: real immutable artifacts, typed participants and isolated owners."""
import base64
import copy
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
BASE=SourceFileLoader('decision_system_fixture',str(ROOT/'tests/rdg-decision-integration.test.py')).load_module()

class DecisionSystem(BASE.DecisionIntegration):
    def process(self,name):
        return self.app().request(self.req('create',path='working/'+name,role='working',title=name,
            scope='Synthetic D3-D9 process',coreModel='rdg-decision-v1',rootReason='Verify application contracts'))['packages'][0]['packageId']
    def definition(self,ident,scope='all'):
        graph=self.current(ident)['graph'];lens=self.work_lens()
        rule={'id':'RULE','nodeKinds':['requirement','decision','action'],'scope':scope,'state':'any',
            'lensRefs':[{'packageId':lens['packageId'],'identitySpace':lens['identitySpace'],'lensKey':'work'}]}
        if scope!='all':rule['anchor']={'packageId':ident,'identitySpace':graph['identitySpace'],'nodeId':'R1'}
        return {'id':str(uuid.uuid4()),'revision':1,'key':'custom','title':'Synthetic rule','supplied':False,'rules':[rule]}
    def create_definition(self,ident,definition,attach=True):
        reg=self.app().recommendation_catalog();request=self.req('recommendation_edit',expectedRegistryRevision=reg['registryRevision'],
            action='create',definition=definition,note='Create actual recommendation definition')
        if attach:
            row=self.current(ident);request['attachTo']={'packageId':ident,'expectedPackageRevision':row['package']['revision'],'expectedGraphRevision':row['graph']['revision']}
        self.app().request(request);return definition['id']
    def add_evidence(self,ident):
        raw=b'Actual synthetic output read back through the writer'
        row=self.current(ident);req=self.req('attach_evidence',targetPackageId=ident,expectedPackageRevision=row['package']['revision'],contentBase64=base64.b64encode(raw).decode())
        result=self.app().request(req);pin=result['packages'][0]['receipt']['effects']['evidenceRef']
        stored=self.store.read(ident);self.assertEqual((self.store.package_path(stored['path'])/pin['path']).read_bytes(),raw)
        self.command(ident,'add',entity={'id':'EV','kind':'evidence','title':'IO verification','description':'Synthetic observed bytes',
            'claim':'The fixture output was written and read back','scope':'Synthetic IO test','version':'1','source':'The actual temporary package evidence file','artifact':pin})
        return pin
    def place_node(self,ident,nid,**extra):
        req=self.app().schema('place',ident,nid)['request'];req.update(note='Place existing identity',**extra)
        return self.app().request(req)

    def review_all(self,ident):
        graph=self.current(ident)['graph']
        for node in graph['nodes']:
            if self.current(ident)['completion'][node['id']].get('reviewRequired'):
                req=self.app().schema('core',ident,node['id'],command='review')['request'];req['note']='Actually inspected current synthetic pins';self.app().request(req)

    def test_system_facts_template_normalization_lens_versions_and_copy(self):
        ident=self.decision();self.create_definition(ident,self.definition(ident))
        self.plan(ident);self.place_node(ident,'A1');pin=self.add_evidence(ident)
        self.review_all(ident);self.command(ident,'select',nodeId='D1');self.review_all(ident)
        for nid in ('A1','D1','R1'):
            self.review_all(ident);req=self.app().schema('core',ident,nid,command='complete')['request'];req['note']='Wrote and read the actual synthetic output';req['data'].update(basis=req['note'],evidenceIds=['EV']);req['evidenceRefs']=[pin];self.app().request(req)
        source=self.current(ident);self.assertTrue(all(source['completion'][i]['complete'] for i in ('R1','D1','A1')))
        req=self.app().schema('lens_apply',ident)['request'];lens=self.work_lens();req.update(lensPackageId=lens['packageId'],nodeIds=['R1'],evidenceIds=['EV'],recommendationIds=source['graph']['recommendationPackageIds'],note='Actually read the Work instructions and checked the output')
        self.app().request(req);event=next(e for e in self.current(ident)['graph']['events'] if e['type']=='lens_application_recorded');self.assertEqual(event['observedPins'][0]['mode'],'historical')
        old_pin=copy.deepcopy(event['lensPins'][0]);attach=self.app().schema('recommendation_attach',lens['packageId'])['request'];attach.update(packageIds=source['graph']['recommendationPackageIds'],note='Enable explicit nested recommendations without changing supplied structure');self.app().request(attach)
        old=self.app().source_snapshot(lens['packageId'],old_pin);self.assertEqual(old['graph']['revision'],old_pin['graphRevision'])
        req=self.app().schema('copy',ident)['request'];req.update(path='copies/facts',note='Stateful copy with verified provenance');result=self.app().request(req);copied=result['packages'][0]['packageId'];mapping=result['packages'][0]['receipt']['effects']['idMap']['entity'];copyrow=self.current(copied)
        self.assertTrue(all(copyrow['completion'][mapping[i]]['complete'] for i in ('R1','D1','A1')));self.assertEqual(copyrow['graph']['events'],[]);self.assertTrue(copyrow['graph']['inheritedHistory'])
        req=self.app().schema('capture_ready',ident)['request'];req.update(path='ready/without-facts',note='Reusable structure only');ready=self.app().request(req)['packages'][0]['packageId'];paper=self.current(ready)
        self.assertFalse(paper['graph']['events']);self.assertIsNone(paper['plan']);self.assertFalse(paper['graph'].get('inheritedHistory'));self.assertFalse(any(n['kind']=='evidence' for n in paper['graph']['objects']));self.assertFalse(any(n['lowLevel'] for n in paper['graph']['externalActions']));self.assertTrue(all(n['result']['state']=='open' for n in paper['graph']['nodes']));self.assertTrue(all(n['selectionState']=='discovered' for n in paper['graph']['nodes'] if n['kind']=='decision'))

    def test_system_boundary_rebind_delete_coordination_and_replace(self):
        ident=self.decision();self.command(ident,'add',entity={'id':'D2','kind':'decision','title':'Outside fragment','description':'Boundary target'},initialRelations=[{'id':'RD2','type':'DRIVES','from':'R1','to':'D2'}])
        req=self.app().schema('copy',ident)['request'];req.update(path='copies/boundary',focus={'kind':'action','id':'A1'},includeDescendants=False,note='Copy support with qualified boundary');result=self.app().request(req);copied=result['packages'][0]['packageId'];refs=self.current(copied)['graph']['externalRefs'];self.assertTrue(refs)
        ref=next(r for r in refs if r['target']['nodeId']=='D2');self.assertEqual(ref['target']['packageId'],ident)
        row=self.current(ident);req=self.req('delete',targetPackageId=ident,expectedPackageRevision=row['package']['revision'],expectedGraphRevision=row['graph']['revision'],nodeIds=['D2'],note='Coordinate qualified incoming references');self.app().request(req)
        changed=self.current(copied);archived=next(r for r in changed['graph']['externalRefs'] if r['id']==ref['id']);self.assertEqual(archived['target']['mode'],'historical');self.assertEqual(archived['target']['sha256'],ref['target']['sha256']);self.assertTrue(changed['completion'][archived['localId']]['reviewRequired'])
        req=self.app().schema('external_edit',copied)['request'];req.update(referenceId=ref['id'],remove=True,note='Explicitly remove historical boundary');req.pop('target',None);self.app().request(req);self.assertFalse(any(r['id']==ref['id'] for r in self.current(copied)['graph']['externalRefs']))
        req=self.app().schema('capture_ready',ident)['request'];req.update(path='ready/replacement',note='Reusable replacement');ready=self.app().request(req)['packages'][0]['packageId']
        self.command(ident,'add',entity={'id':'OLD','kind':'requirement','title':'Replace this block','description':'Explicit target','scope':'Synthetic'},initialRelations=[{'id':'R-OLD','type':'DERIVES','from':'R1','to':'OLD'}]);self.plan(ident);self.place_node(ident,'OLD')
        req=self.app().schema('apply_ready',ident,source_id=ready)['request'];req.update(mode='REPLACE_R',targetRequirementId='OLD',note='One coordinated replacement');result=self.app().request(req);current=self.current(ident);self.assertNotIn('OLD',{n['id'] for n in current['graph']['nodes']});self.assertFalse(any(s['ref']['nodeId']=='OLD' for s in current['plan']['steps']));self.assertIn('A1',{n['id'] for n in current['graph']['nodes']})

    def test_system_plan_forks_history_pins_and_view_only(self):
        ident=self.decision();self.plan(ident);self.command(ident,'add',entity={'id':'D2','kind':'decision','title':'Alternative','description':'Potential alternative'},initialRelations=[{'id':'RD2','type':'DRIVES','from':'R1','to':'D2'}])
        row=self.current(ident);plan=copy.deepcopy(row['plan']);plan['revision']+=1
        plan['steps']=[{'id':sid,'title':nid,'kind':next(n['kind'] for n in row['graph']['nodes'] if n['id']==nid),'state':'planned',
            'ref':BASE.BASE.P.reference(ident,row['graph'],nid)} for sid,nid in [('S0','R1'),('S1','D1'),('S2','D2')]]
        plan['mainStepIds']=['S0'];plan['forks']=[{'id':'F','title':'Potential continuations','afterStepId':'S0','cases':[
            {'id':'C1','title':'First','decisionIds':['D1'],'stepIds':['S1']},{'id':'C2','title':'Second','decisionIds':['D2'],'stepIds':['S2']}]}]
        req=self.app().schema('plan_edit',ident)['request'];req['plan']=plan;self.app().request(req)
        before=self.sources();graph=self.current(ident)['graph']
        for case,sid in [('C1','S1'),('C2','S2')]:
            view=self.app().read(ident,True,{'kind':'graph','shownCases':{'F':case}})
            self.assertEqual([r['step']['id'] for r in view['planView']['placements']],['S0',sid]);self.assertEqual(view['graph'],graph)
        self.assertEqual(before,self.sources())
        self.command(ident,'add',entity={'id':'TASK','kind':'action','title':'Write and verify a real test output','description':'Performed by this test',
            'actionType':'task','lowLevel':False,'targetIds':['R1'],'groupIds':[]},location='external')
        self.place_node(ident,'TASK');pin=self.add_evidence(ident)
        req=self.command_request(ident,'complete',nodeId='TASK',basis='Wrote and checked the actual output bytes',evidenceIds=['EV']);req['evidenceRefs']=[pin];self.app().request(req)
        event=next(e for e in self.current(ident)['graph']['events'] if e['type']=='action_executed' and 'TASK' in e['nodeIds'])
        self.assertEqual(len(event['placementIds']),1);old=list(event['placementIds']);self.place_node(ident,'TASK')
        history=self.app().history(ident);record=next(r for r in history['events'] if r['event']['id']==event['id'])
        self.assertEqual(record['event']['placementIds'],old);self.assertIsNotNone(record['planPin'])
        version=next(v['plan'] for v in history['planVersions'] if v['sha256']==record['planPin']['sha256'])
        self.assertEqual([s['id'] for s in version['steps'] if s['ref']['nodeId']=='TASK'],old)

    def test_system_registry_atomic_crud_pins_permissions_and_recovery(self):
        ident=self.process('registry');definition=self.definition(ident,'identity');pid=self.create_definition(ident,definition)
        second=self.process('other');req=self.app().schema('recommendation_attach',second)['request'];req.update(packageIds=[pid],note='Use the same shared definition');self.app().request(req)
        def hits(owner):return [m for m in self.current(owner)['recommendations']['matches'] if any(r['packageId']==pid for r in m['reasons'])]
        self.assertTrue(hits(ident));self.assertFalse(hits(second))
        reg=self.app().recommendation_catalog();changed=copy.deepcopy(definition);changed['revision']+=1;changed['rules'][0].pop('anchor');changed['rules'][0]['scope']='all'
        req=self.req('recommendation_edit',expectedRegistryRevision=reg['registryRevision'],action='edit',packageId=pid,definition=changed,note='Shared definition update')
        preview=self.app().request(req,preflight=True);self.assertTrue(any(p['kind']=='recommendationRegistry' for p in preview['inputBinding']['ownerPins']))
        self.app().request(req,expected_input_binding=preview['inputBinding']);self.assertTrue(hits(second))
        reg=self.app().recommendation_catalog();req=self.req('recommendation_edit',expectedRegistryRevision=reg['registryRevision'],action='copy',packageId=pid,note='Independent copy')
        result=self.app().request(req);new_id=result['participants'][0]['receipt']['effects']['definitionId'];self.assertNotEqual(new_id,pid)
        # A caller cannot declare a new definition to be a privileged supplied package.
        supplied_attempt=copy.deepcopy(definition)
        supplied_attempt.update(id=str(uuid.uuid4()),key='forged-supplied',supplied=True)
        bad=self.req('recommendation_edit',expectedRegistryRevision=self.app().recommendation_catalog()['registryRevision'],
                     action='create',definition=supplied_attempt,note='Must reject forged supplied metadata')
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'PACKAGE_IMMUTABLE'):self.app().request(bad)
        self.assertEqual(before,self.sources())
        grant=self.authority.manage('issue',self.admin,{'permissions':['graph.read','graph.write'],'scopes':['packages/'+self.namespace+'/'+ident]})
        with self.assertRaisesRegex(ValueError,'SCOPE_DENIED'):self.app(grant['token']).recommendation_catalog()
        scoped=self.app(grant['token']).read(ident);self.assertEqual(scoped['graph']['id'],self.current(ident)['graph']['id']);self.assertFalse(scoped['recommendations']['available']);self.assertEqual(scoped['recommendations']['packages'],[])
        legacy=self.create('legacy-profile-gate')
        for op in ('recommendation_attach','lens_apply','capture_ready'):
            with self.assertRaisesRegex(ValueError,'UNSUPPORTED_PROFILE_CAPABILITY'):self.app().schema(op,legacy)
        value=self.definition(ident);row=self.current(ident);req=self.req('recommendation_edit',expectedRegistryRevision=self.app().recommendation_catalog()['registryRevision'],action='create',definition=value,note='Coupled Graph registry transaction',attachTo={'packageId':ident,'expectedPackageRevision':row['package']['revision'],'expectedGraphRevision':row['graph']['revision']})
        def fail(stage):
            if stage=='head:1':raise RuntimeError('Synthetic participant interruption')
        with self.assertRaisesRegex(RuntimeError,'participant'):self.app().request(req,failpoint=fail)
        with self.assertRaises(ValueError):self.app().read(ident)
        self.app().recover(req['transactionId']);self.assertTrue(self.app().request(req)['idempotent'])
        self.assertIn(value['id'],self.current(ident)['graph']['recommendationPackageIds'])
        raw=self.store.registry_read();self.assertEqual(raw['head']['kind'],'rdgRecommendationRegistryHead')

    def test_system_template_instances_copy_layout_and_namespace_safety(self):
        source=self.decision();pid=self.create_definition(source,self.definition(source,'identity'));self.plan(source);self.place_node(source,'D1')
        req=self.app().schema('capture_ready',source)['request'];req.update(path='ready/decision-template',recommendationIds=[pid],note='Capture definitions only')
        ready=self.app().request(req)['packages'][0]['packageId'];paper=self.current(ready)
        self.assertEqual(paper['graph']['events'],[]);self.assertIsNone(paper['plan']);self.assertFalse(self.app().history(ready)['events']);self.assertFalse(self.app().history(ready)['planVersions'])
        target=self.process('destination');maps=[]
        for i in range(2):
            req=self.app().schema('apply_ready',target,source_id=ready)['request'];req.update(parentRequirementId='R1',note='Insert independent template instance')
            result=self.app().request(req);maps.append(result['packages'][0]['receipt']['effects']['idMap']['entity'])
        self.assertFalse(set(maps[0].values())&set(maps[1].values()))
        positioned=self.current(target);positions=positioned['layouts']['layouts'][positioned['view']['graphKey']]['positions'];self.assertNotEqual(positions[maps[0][paper['graph']['rootRequirementId']]]['x'],positions[maps[1][paper['graph']['rootRequirementId']]]['x'])
        row=self.current(target);definitions=self.app().recommendation_catalog()['packages'];instances=[p for p in definitions if p.get('instance',{}).get('graphBinding',{}).get('packageId')==target]
        self.assertEqual(len(instances),2);self.assertFalse(set(instances[0]['instance']['memberIds'])&set(instances[1]['instance']['memberIds']))
        for instance in instances:self.assertNotIn('R1',instance['instance']['memberIds'])
        graph=row['graph'];self.assertEqual(graph['nodes'][0]['result']['state'],'open')
        # A new descendant of one inserted root belongs only to its instance.
        root=maps[0][paper['graph']['rootRequirementId']];self.command(target,'add',entity={'id':'NEW','kind':'requirement','title':'New descendant','description':'New real node','scope':'Synthetic'},initialRelations=[{'id':'NEW-EDGE','type':'DERIVES','from':root,'to':'NEW'}])
        # Preserve canonical coordinates on stateful copy through the shared codec.
        row=self.current(target);key=row['view']['graphKey'];req=self.app().schema('layout_edit',target)['request'];req['commands']=[{'type':'set_positions','graphKey':key,'positions':{root:{'x':-82,'y':211}}}];self.app().request(req)
        req=self.app().schema('copy',target)['request'];req.update(path='copies/decision-state',note='Preserve work and layouts');result=self.app().request(req);copied=result['packages'][0]['packageId'];mapping=result['packages'][0]['receipt']['effects']['idMap']['entity'];copyrow=self.current(copied)
        self.assertEqual(copyrow['layouts']['layouts'][copyrow['view']['graphKey']]['positions'][mapping[root]],{'x':-82,'y':211})
        owned=[p for p in self.app().recommendation_catalog()['packages'] if p.get('instance',{}).get('graphBinding',{}).get('packageId')==copied]
        self.assertEqual(len(owned),2);self.assertTrue(all(p['id'] not in {v['id'] for v in instances} for p in owned))
        # A foreign anchor cannot be localized by a repeated short R1.
        foreign=self.process('foreign');baddef=self.definition(foreign,'identity');badid=self.create_definition(source,baddef)
        req=self.app().schema('capture_ready',source)['request'];req.update(path='ready/must-fail',recommendationIds=[badid],note='Foreign anchor must fail')
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'FOREIGN_TEMPLATE_ANCHOR'):self.app().request(req)
        self.assertEqual(before,self.sources())

    def test_system_sessions_shared_projection_and_coordinated_delete(self):
        ident=self.decision();self.plan(ident);self.place_node(ident,'D1');app=self.app()
        sid=str(uuid.uuid4());session=app.call({'method':'view_session','action':'create','sessionId':sid,'packageId':ident})
        before=self.sources();value={k:copy.deepcopy(session[k]) for k in ('screens','activeScreenId','explorer')};second=copy.deepcopy(value['screens'][0]);second['id']=str(uuid.uuid4());second['spec']={'kind':'focus','id':'D1','camera':{'x':12,'y':33,'width':640,'height':420}};value['screens'].append(second)
        updated=app.call({'method':'view_session','action':'update','sessionId':sid,'expectedRevision':session['revision'],'value':value})
        self.assertEqual(len(updated['screens']),2);self.assertEqual(before,self.sources())
        with self.assertRaisesRegex(ValueError,'VIEW_CAS_MISMATCH'):app.call({'method':'view_session','action':'update','sessionId':sid,'expectedRevision':session['revision'],'value':value})
        row=self.current(ident);key=row['view']['graphKey'];req=app.schema('layout_edit',ident)['request'];req['commands']=[{'type':'set_positions','graphKey':key,'positions':{'D1':{'x':90,'y':120}}}];app.request(req)
        row=self.current(ident);req=self.req('delete',targetPackageId=ident,expectedPackageRevision=row['package']['revision'],expectedGraphRevision=row['graph']['revision'],nodeIds=['D1'],note='Coordinated current-ref cleanup');app.request(req)
        row=self.current(ident);self.assertFalse(any(s['ref']['nodeId']=='D1' for s in row['plan']['steps']));self.assertNotIn('D1',row['layouts']['layouts'][key]['positions'])

if __name__=='__main__':
    names=[n for n in DecisionSystem.__dict__ if n.startswith('test_system_')]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(DecisionSystem(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
