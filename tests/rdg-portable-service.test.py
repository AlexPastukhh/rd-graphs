#!/usr/bin/env python3
"""Isolated public service/CLI acceptance, including incoming-reference races."""
import base64
import copy
from importlib.machinery import SourceFileLoader
import json
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
FIX=SourceFileLoader('portable_service_fixture',str(ROOT/'tests/rdg-portable-store.test.py')).load_module()
CLI=SourceFileLoader('portable_service_cli',str(ROOT/'tools/rdg-portable.py')).load_module()
P,M=FIX.P,FIX.M


def request_worker(config,token,request,queue,ready=None,proceed=None):
    try:
        def pause():
            ready.set()
            if not proceed.wait(15):raise RuntimeError('test barrier timeout')
        app=CLI.application(config,token)
        queue.put(('ok',app.request(request,before_accept=pause if ready else None)))
    except Exception as exc:queue.put(('error',str(exc)))


class PortableApplication(unittest.TestCase):
    setUp=FIX.PortableStore.setUp
    graph=FIX.PortableStore.graph

    def app(self,token=None):return CLI.application(self.config(),token or self.token)
    def config(self):return {'packageRoot':str(self.root),'namespaceId':self.namespace,
        'coordinationRoot':str(self.base),'authorityStore':str(self.authority.path)}
    def req(self,op,**fields):return {'transactionId':str(uuid.uuid4()),'op':op,**fields}
    def create(self,name,role='working',graph=None):
        request=self.req('create',path=role+'/'+name,role=role,title=name)
        if graph is not None:request['graph']=graph
        result=self.app().request(request)
        return result['packages'][0]['packageId']
    def current(self,ident):return self.app().read(ident,True)
    def command_request(self,ident,command,**data):
        current=self.current(ident)
        return self.req('core',targetPackageId=ident,expectedPackageRevision=current['package']['revision'],
            expectedGraphRevision=current['graph']['revision'],command=command,data=data,note='Synthetic command '+command)
    def command(self,ident,command,**data):return self.app().request(self.command_request(ident,command,**data))
    def placement(self,owner,target,nid='R1'):
        current=self.current(owner);graph=self.current(target)['graph'];plan=copy.deepcopy(current['plan']);plan['revision']+=1
        plan['steps'].append({'id':'S-'+str(len(plan['steps'])),'title':'Synthetic placement','kind':M.entities(graph)[nid]['kind'],
            'state':'planned','ref':P.reference(target,graph,nid)})
        plan['timeConstraints'].append({'stepId':plan['steps'][-1]['id'],'type':'notBefore','at':'2026-10-25',
            'strength':'soft','basis':'Synthetic placement'})
        return self.req('plan_edit',targetPackageId=owner,expectedPackageRevision=current['package']['revision'],
            expectedPlanRevision=current['plan']['revision'],plan=plan)
    def replace_request(self,target,source):
        before=self.current(target);paper=self.current(source)
        return self.req('apply_ready',targetPackageId=target,sourcePackageId=source,
            expectedPackageRevision=before['package']['revision'],expectedGraphRevision=before['graph']['revision'],
            sourcePin={'revision':paper['package']['revision'],'sha256':P.digest(paper['graph'])},
            mode='REPLACE_R',targetRequirementId='R1',note='Synthetic full replacement')
    def review(self,ident):
        graph=self.current(ident)['graph'];ns=M.entities(graph);ids=[i for i,n in ns.items() if n.get('review',{}).get('required')]
        if ids:self.command(ident,'review',nodeIds=ids,observed={i:ns[i]['revision'] for j in ids for i in M.pins(graph,j)})
    def sources(self):return {str(p.relative_to(self.base)):p.read_bytes() for p in self.base.rglob('*.json')}

    def finding_package(self):
        ident=self.app().request(self.req('create',path='working/findings-'+uuid.uuid4().hex,role='working',title='Finding acceptance',scope='Synthetic',coreModel='rdg-decision-v1',rootReason='Synthetic finding tests'))['packages'][0]['packageId']
        root=self.current(ident)['graph']['rootRequirementId']
        subject='SUBJECT'
        self.command(ident,'add',entity={'id':subject,'kind':'decision','title':'Subject decision','description':'Synthetic candidate'},initialRelations=[{'id':'SUBJECT-BASIS','type':'DRIVES','from':root,'to':subject}])
        self.command(ident,'add',entity={'id':'FINDING','kind':'finding','title':'Fixture problem','description':'Current violation','subjectId':subject,'findingType':'problem','rationale':'Synthetic observable violation','evidenceIds':[]})
        return ident,subject

    def test_finding_schema_preflight_retry_and_restart_share_writer(self):
        ident,subject=self.finding_package();app=self.app()
        self.command(ident,'add',entity={'id':'CTX','kind':'context','title':'Fact','description':'Fixture','value':'Observed'})
        request=app.schema('core',ident,node_id=subject,command='decision_context')['request']
        request['note']='Explain role';request['data']={'nodeId':subject,'sourceId':'CTX','action':'save','comment':'Supports this choice'}
        before=self.sources();preview=app.request(request,preflight=True)
        self.assertEqual(before,self.sources());self.assertFalse(preview['accepted'])
        result=app.request(request);self.assertTrue(result['published']);app.request(request)
        read=self.current(ident);self.assertEqual(len(read['decisionContexts'][subject]),1)
        self.assertEqual(read['decisionContexts'][subject][0]['comment'],'Supports this choice')
        self.assertTrue(app.receipt(ident,request['transactionId'])['found'])
        self.assertEqual(read['graph'],self.app().read(ident)['graph']);self.assertEqual(read['findings'][0]['subject']['id'],subject)

    def test_finding_invalid_chain_and_cas_leave_no_partial_entities(self):
        ident,subject=self.finding_package();before=self.current(ident)['graph']
        for command in ('finding_response','finding_proposal'):
            with self.assertRaisesRegex(ValueError,'CORE_COMMAND'):self.app().schema('core',ident,node_id='FINDING',command=command)
            bad=self.command_request(ident,command,findingId='FINDING',decisionId='BAD',title='Retired')
            with self.assertRaisesRegex(ValueError,'CORE_COMMAND|OPERATION'):self.app().request(bad)
        self.assertEqual(self.current(ident)['graph'],before)
        request=self.command_request(ident,'finding_transfer',nodeId='FINDING',subjectId=subject)
        self.command(ident,'edit',nodeId=subject,changes={'title':'Cosmetic new title'},cosmetic=True)
        with self.assertRaisesRegex(ValueError,'CAS|REVISION'):self.app().request(request)

    def test_finding_api_has_same_dependencies_and_invalidation(self):
        ident,subject=self.finding_package();self.command(ident,'edit',nodeId=subject,changes={'description':'Changed subject content'},cosmetic=False)
        read=self.current(ident);f=next(n for n in read['graph']['objects'] if n['id']=='FINDING')
        self.assertTrue(f['review']['required'])
        records=read['dependencyCatalog']['invalidationRecords'];self.assertTrue(any(r['targetId']=='FINDING' and r['kind']=='review' for r in records))
        request=self.app().schema('core',ident,node_id='FINDING',command='review')['request'];request['note']='Rechecked current fixture';request['data']['basis']=request['note'];self.app().request(request)
        current=self.current(ident);self.assertEqual(next(n for n in current['graph']['objects'] if n['id']=='FINDING')['disposition']['code'],'unresolved')

    def test_finding_commands_require_existing_write_authority(self):
        ident,_=self.finding_package();grant=self.authority.manage('issue',self.admin,{'permissions':['graph.read'],'scopes':['packages/'+self.namespace+'/'+ident]})
        reader=self.app(grant['token']);read=reader.read(ident);self.assertEqual(read['findings'][0]['findingId'],'FINDING')
        request=self.command_request(ident,'finding_transfer',nodeId='FINDING',subjectId='SUBJECT')
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'DENIED|PERMISSION'):reader.request(request)
        self.assertEqual(before,self.sources())

    def test_finding_copy_remaps_subject_context_provenance_and_evidence(self):
        ident,subject=self.finding_package()
        self.command(ident,'context_group',action='save',id='TOP',title='Timing',parentId=None)
        self.command(ident,'add',entity={'id':'CTX','kind':'context','title':'Fact','description':'Observed','value':'Current','contextGroupId':'TOP'})
        self.command(ident,'link',relation={'id':'CTX-F','type':'DEPENDS_ON','from':'CTX','to':'FINDING','dependencyLevel':'L1'})
        self.command(ident,'decision_context',nodeId=subject,sourceId='CTX',action='note',comment='Relevant finding input')
        self.command(ident,'add',entity={'id':'F-EVIDENCE','kind':'context','title':'Fixture evidence','description':'Verified synthetic outcome','value':'Verified fixture','scope':'Synthetic scope','version':'1','source':'Fixture'})
        self.command(ident,'edit',nodeId='FINDING',changes={'evidenceIds':['F-EVIDENCE']},cosmetic=False)
        row=self.current(ident);request=self.app().schema('copy',ident,source_id=ident)['request'];request.update(path='copy/findings-'+uuid.uuid4().hex,note='Copy finding process')
        result=self.app().request(request);copied_id=result['packages'][0]['packageId'];read=self.current(copied_id);copied=read['graph']
        f=next(n for n in copied['objects'] if n['kind']=='finding');d=next(n for n in copied['nodes'] if n['id']==f['subjectId']);ctx=next(n for n in copied['objects'] if n['kind']=='context')
        self.assertEqual(d['contextNotes'][ctx['id']],'Relevant finding input');self.assertEqual(read['decisionContexts'][d['id']][0]['provenance'][0]['findingId'],f['id'])
        self.assertEqual(ctx['contextGroupId'],copied['contextGroups'][0]['id']);self.assertNotEqual(ctx['contextGroupId'],'TOP')
        self.assertEqual(len(f['evidenceIds']),1);self.assertNotEqual(f['evidenceIds'][0],'F-EVIDENCE');self.assertTrue(any(n['id']==f['evidenceIds'][0] and n['kind']=='context' for n in copied['objects']))
        self.assertNotEqual(f['id'],'FINDING');self.assertEqual(self.current(ident)['graph'],row['graph'])

    def test_structure_mode_is_validated_ephemeral_view_session_not_graph_spec(self):
        ident=self.app().request(self.req('create',path='working/structure-session',role='working',
            title='Session mode',scope='Session-only view',coreModel='rdg-decision-v1',
            rootReason='Explicit synthetic goal'))['packages'][0]['packageId']
        app=self.app();sid=str(uuid.uuid4())
        start=app.call({'method':'view_session','action':'create','sessionId':sid,'packageId':ident})
        original=self.current(ident)
        screen=copy.deepcopy(start['screens'][0])
        screen['presentation']={'mode':'structure','expandedPaths':['root:R1'],
            'collapsedPaths':['materials'],'query':''}
        screen['panels']['roadTab']='dependencies'
        self.assertEqual(screen['panels']['inspectorWidth'],340)
        screen['panels']['inspectorWidth']=615
        payload={'activeScreenId':screen['id'],'screens':[screen],'explorer':start['explorer']}
        changed=app.call({'method':'view_session','action':'update','sessionId':sid,
            'expectedRevision':start['revision'],'value':payload})
        self.assertEqual(changed['screens'][0]['presentation'],screen['presentation'])
        self.assertEqual(changed['screens'][0]['panels']['roadTab'],'dependencies',
                         'right-side dependency view is accepted as ephemeral state')
        self.assertEqual(changed['screens'][0]['panels']['inspectorWidth'],615)
        self.assertFalse(changed['persisted'])
        self.assertEqual(self.current(ident),original,'presentation cannot modify graph/plan/layout')
        self.assertRaisesRegex(ValueError,'VIEW_SCHEMA',P.validate_view_spec,
            {'kind':'graph','presentation':'structure'})
        bad=copy.deepcopy(payload);bad['screens'][0]['presentation']['mode']='unknown'
        with self.assertRaisesRegex(ValueError,'VIEW_PRESENTATION_SCHEMA'):
            app.call({'method':'view_session','action':'update','sessionId':sid,
                'expectedRevision':changed['revision'],'value':bad})
        bad=copy.deepcopy(payload);bad['screens'][0]['presentation']['collapsedPaths']=['root:R1']
        with self.assertRaisesRegex(ValueError,'VIEW_PRESENTATION_PATH_CONFLICT'):
            app.call({'method':'view_session','action':'update','sessionId':sid,
                'expectedRevision':changed['revision'],'value':bad})
        bad=copy.deepcopy(payload);bad['screens'][0]['presentation']['expandedPaths']=['x']*513
        with self.assertRaisesRegex(ValueError,'VIEW_PRESENTATION_PATHS'):
            app.call({'method':'view_session','action':'update','sessionId':sid,
                'expectedRevision':changed['revision'],'value':bad})
        with self.assertRaisesRegex(ValueError,'VIEW_CAS_MISMATCH'):
            app.call({'method':'view_session','action':'update','sessionId':sid,
                'expectedRevision':start['revision'],'value':payload})
        self.assertEqual(app.call({'method':'view_session','sessionId':sid})['screens'][0]['presentation'],
                         screen['presentation'])
        self.assertEqual(self.current(ident),original)
        legacy=copy.deepcopy(payload)
        legacy['screens'][0]['panels'].pop('roadTab')
        legacy['screens'][0]['panels'].pop('inspectorWidth')
        old_session=app.call({'method':'view_session','action':'update','sessionId':sid,
            'expectedRevision':changed['revision'],'value':legacy})
        self.assertNotIn('roadTab',old_session['screens'][0]['panels'],
                         'pre-existing Viewer sessions stay valid with timeline as default')
        self.assertNotIn('inspectorWidth',old_session['screens'][0]['panels'])
        for width in (True, '500', 259, 1001, float('nan'), float('inf')):
            bad=copy.deepcopy(payload);bad['screens'][0]['panels']['inspectorWidth']=width
            with self.assertRaisesRegex(ValueError,'VIEW_PANEL_SCHEMA'):
                app.call({'method':'view_session','action':'update','sessionId':sid,
                    'expectedRevision':old_session['revision'],'value':bad})
        bad=copy.deepcopy(payload)
        bad['screens'][0]['panels']['roadTab']='not-a-view'
        with self.assertRaisesRegex(ValueError,'VIEW_PANEL_SCHEMA'):
            app.call({'method':'view_session','action':'update','sessionId':sid,
                'expectedRevision':old_session['revision'],'value':bad})
        self.assertEqual(self.current(ident),original)

    def test_configurable_dependencies_are_written_read_reviewed_through_public_application(self):
        ident=self.app().request(self.req('create',role='working',path='working/custom-dependency-api',
            title='Dependency rules',scope='Isolated test process',coreModel='rdg-decision-v1',
            rootReason='Verify one canonical rule evaluator'))['packages'][0]['packageId']
        self.command(ident,'add',entity={'id':'CT1','kind':'context','title':'Current load',
            'description':'Actual condition','value':'100'},location='graph')
        self.command(ident,'add',entity={'id':'D1','kind':'decision','title':'PostgreSQL',
            'description':'Storage decision'},location='graph')
        snapshot=self.current(ident)
        req=self.req('dependency_add',targetPackageId=ident,
            expectedPackageRevision=snapshot['package']['revision'],
            expectedGraphRevision=snapshot['graph']['revision'],
            sourceId='CT1',dependentId='D1',
            dependencyRule={'preset':'L1','watch':['definition']},
            dependencyPurpose='decisionContext',contextComment='Current process load influences choice',note='Track current process load')
        saved=self.app().request(req)
        self.assertTrue(saved['published'])
        listed=self.app().call({'method':'dependencies','packageId':ident})
        self.assertEqual(len(listed['edges']),1)
        edge=listed['edges'][0]
        self.assertEqual(edge['dependencyRule'],{'preset':'L1','watch':['definition']})
        self.assertEqual(listed['projections'][edge['id']]['watched']['definition']['value'],'100')
        self.command(ident,'edit',nodeId='CT1',changes={'value':'100000'},cosmetic=False)
        graph=self.current(ident)['graph']
        self.assertTrue(M.entities(graph)['D1']['review']['required'])
        impact=graph['events'][-1]['dependencyImpacts']
        self.assertEqual([(r['edgeId'],r['changedParts']) for r in impact],[(edge['id'],['definition'])])
        self.assertEqual(impact[0]['origin'],'manual')
        self.command(ident,'review',nodeId='D1',observed=CLI.module('rdg-model-profiles').pins(graph,'D1'),
            basis='Verified changed load and retained Decision')
        self.assertFalse(M.entities(self.current(ident)['graph'])['D1']['review']['required'])
        updated={**edge,'dependencyRule':{'preset':'custom','watch':['definition','directScope']}}
        self.command(ident,'dependency_rule',mode='save',relation=updated)
        self.assertEqual(self.app().call({'method':'dependencies','packageId':ident})['edges'][0]['dependencyRule']['preset'],'custom')
        self.command(ident,'dependency_rule',mode='remove',edgeId=edge['id'])
        self.assertEqual(self.app().call({'method':'dependencies','packageId':ident})['edges'],[])
        self.assertEqual(M.entities(self.current(ident)['graph'])['D1'].get('decisionContextIds',[]),[])

    def test_compact_graph_view_spec_is_boolean_and_not_a_domain_write(self):
        spec={'kind':'graph','compactGraph':True,'showAllBlocks':True}
        self.assertEqual(P.validate_view_spec(spec),spec)
        self.assertRaisesRegex(ValueError,'VIEW_SCHEMA',P.validate_view_spec,
            {'kind':'graph','showAllBlocks':'true'})
        self.assertRaisesRegex(ValueError,'VIEW_SCHEMA',P.validate_view_spec,
            {'kind':'graph','compactGraph':'true'})
        focus={'kind':'focus','id':'R1','focusPositions':{'R1':{'x':120.5,'y':80}}}
        self.assertEqual(P.validate_view_spec(focus),focus)
        self.assertRaisesRegex(ValueError,'VIEW_FOCUS_POSITIONS',P.validate_view_spec,
            {'kind':'graph','focusPositions':{'R1':{'x':20,'y':80}}})
        self.assertRaisesRegex(ValueError,'VIEW_FOCUS_POSITIONS',P.validate_view_spec,
            {'kind':'focus','id':'R1','focusPositions':{'R1':{'x':'20','y':80}}})
        self.assertRaisesRegex(ValueError,'VIEW_FOCUS_POSITIONS',P.validate_view_spec,
            {'kind':'focus','id':'R1','focusPositions':{'R1':{'x':float('nan'),'y':80}}})

    def test_fresh_cli_preflight_is_readonly_and_catalog_uses_real_roles(self):
        request=self.req('create',role='ready',path='templates/actual-folder',title='Paper')
        before=self.sources()
        args=[sys.executable,'-B',str(ROOT/'tools/rdg-portable.py'),'preflight','--packages',str(self.root),
              '--namespace',self.namespace,'--coordination-root',str(self.base),'--store',str(self.authority.path)]
        result=subprocess.run(args,input=json.dumps(request),capture_output=True,text=True,
            env={**os.environ,'RDG_AUTH_TOKEN':self.token},timeout=20)
        self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(json.loads(result.stdout)['accepted'])
        self.assertEqual(before,self.sources());self.assertFalse(self.root.exists())
        args[3]='apply'
        result=subprocess.run(args,input=json.dumps(request),capture_output=True,text=True,
            env={**os.environ,'RDG_AUTH_TOKEN':self.token},timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        ident=json.loads(result.stdout)['packages'][0]['packageId']
        row=self.app().catalog()['packages'][0]
        self.assertEqual((row['path'],row['role'],row['packageId']),('templates/actual-folder','ready',ident))
        graph=self.current(ident)['graph'];self.assertFalse(graph['events']);self.assertEqual('potential',graph['nodes'][0]['status'])
        self.assertIsNone(self.current(ident)['plan'])

    def test_ready_authoring_never_saves_choices_history_or_plan(self):
        ident=self.create('editable','ready');current=self.current(ident)
        self.app().request(self.req('paper_edit',targetPackageId=ident,expectedPackageRevision=current['package']['revision'],
            expectedGraphRevision=current['graph']['revision'],command='add',data={'entity':{'id':'A','kind':'action','title':'Alternative'}},note='Paper alternative'))
        graph=self.current(ident)['graph'];self.assertFalse(graph['events']);self.assertEqual('candidate',M.entities(graph)['A']['status'])
        bad=self.command_request(ident,'select',nodeId='A');before=self.sources()
        with self.assertRaisesRegex(ValueError,'DOCUMENT_ROLE_COMMAND'):self.app().request(bad)
        self.assertEqual(before,self.sources())

    def test_replace_preserves_selected_detached_stale_and_cleans_two_plans(self):
        target=self.create('target');other=self.create('other');source=self.create('paper','ready')
        self.command(target,'add',entity={'id':'A','kind':'action','title':'Retained action'})
        self.command(target,'add',entity={'id':'OUT','kind':'requirement','title':'Output','description':'Output','scope':'Synthetic'})
        self.command(target,'link',edge={'id':'driver','type':'DRIVES','from':'R1','to':'A'})
        self.command(target,'link',edge={'id':'output','type':'INTRODUCES','from':'A','to':'OUT','origin':{'role':'method_correctness'}})
        self.review(target);self.command(target,'select',nodeId='A');self.review(target)
        for owner in (target,other):self.app().request(self.placement(owner,target))
        before=self.current(target);selection=M.entities(before['graph'])['A']['selectedEventId'];old_events=copy.deepcopy(before['graph']['events'])
        request=self.replace_request(target,source);preview=self.app().request(request,preflight=True)
        self.assertEqual(set(preview['effects']['removedPlacements']),{target,other})
        result=self.app().request(request);self.assertTrue(result['published'])
        after=self.current(target);nodes=M.entities(after['graph'])
        self.assertNotIn('R1',nodes);self.assertEqual(nodes['A']['selectedEventId'],selection)
        self.assertEqual(nodes['A']['status'],'selected');self.assertTrue(nodes['A']['review']['required'])
        self.assertEqual(after['graph']['events'][:len(old_events)],old_events)
        self.assertTrue(any(set(c['memberIds'])=={'A','OUT'} for c in after['detached']))
        for owner in (target,other):self.assertEqual(self.current(owner)['plan']['steps'],[])
        historical=self.store.historical_graph(target,before['graph']['identitySpace'],before['graph']['revision'],P.digest(before['graph']))
        self.assertEqual(historical,before['graph'])
        self.assertTrue(self.app().request(request)['idempotent'])

    def test_missing_plan_edit_does_not_partially_replace_graph(self):
        target=self.create('target');other=self.create('other');source=self.create('source','ready')
        self.app().request(self.placement(other,target))
        grant=self.authority.manage('issue',self.admin,{'permissions':['graph.read','graph.write','plan.read'],
            'scopes':['packages/'+self.namespace+'/']})
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'MISSING_PERMISSION: plan.edit'):
            self.app(grant['token']).request(self.replace_request(target,source))
        self.assertEqual(before,self.sources())

    def test_new_incoming_owner_after_discovery_fails_final_catalog_cas(self):
        target=self.create('target');source=self.create('source','ready')
        outside=self.base/'outside';outside.mkdir()
        config={**self.config(),'packageRoot':str(outside/'packages'),'coordinationRoot':str(outside)}
        other_app=CLI.application(config,self.token)
        created=other_app.request(self.req('create',path='working/late',role='working',title='Late owner'))
        ident=created['packages'][0]['packageId'];late=other_app.read(ident,True);target_graph=self.current(target)['graph']
        plan=late['plan'];plan['revision']+=1
        plan['steps']=[{'id':'late','kind':'requirement','title':'Late','state':'planned','ref':P.reference(target,target_graph,'R1')}]
        plan['timeConstraints']=[{'stepId':'late','type':'notBefore','at':'2026-10-25','strength':'soft','basis':'Race'}]
        # Storage-level synthetic writer represents a foreign writer bypassing the protocol.
        snap=other_app.store.read(ident)
        with other_app.store.lock(True):
            changes={ident:{'before':snap,'path':snap['path'],'plan':plan,'permissions':['plan.edit']}}
            checks=[{'namespaceId':self.namespace,'packageId':ident,'path':snap['path'],'permissions':['plan.edit']}]
            other_app.store.commit(str(uuid.uuid4()),'0'*64,changes,'1'*64,lambda:None,
                lambda:self.authority.checked_portable_transaction(self.token,checks),{})
        request=self.replace_request(target,source);before=self.current(target)
        def incoming():shutil.copytree(outside/'packages/working/late',self.root/'working/late')
        with self.assertRaisesRegex(ValueError,'INCOMING_CATALOG_CHANGED'):
            self.app().request(request,before_accept=incoming)
        self.assertEqual(before['graph'],self.current(target)['graph'])
        preview=self.app().request(request,preflight=True)
        self.assertIn(ident,preview['effects']['removedPlacements'])

    def test_reference_creating_process_waits_then_rejects_removed_target(self):
        target=self.create('target');other=self.create('other');source=self.create('source','ready')
        replace=self.replace_request(target,source);place=self.placement(other,target)
        ready,proceed,queue=mp.Event(),mp.Event(),mp.Queue()
        first=mp.Process(target=request_worker,args=(self.config(),self.token,replace,queue,ready,proceed))
        second=mp.Process(target=request_worker,args=(self.config(),self.token,place,queue))
        first.start()
        try:
            self.assertTrue(ready.wait(10));second.start();proceed.set()
            for process in (first,second):process.join(20);self.assertFalse(process.is_alive())
            rows=[queue.get(timeout=2) for _ in range(2)]
            self.assertEqual(sum(kind=='ok' for kind,_ in rows),1)
            self.assertTrue(any('PLAN_REFERENCE_MISMATCH' in str(value) for kind,value in rows if kind=='error'),rows)
            self.assertEqual(self.current(other)['plan']['steps'],[])
        finally:
            proceed.set()
            for process in (first,second):
                if process.pid and process.is_alive():process.terminate();process.join()

    def test_evidence_is_actual_bytes_and_cannot_claim_a_human_actor(self):
        target=self.create('evidence');before=self.current(target)
        raw=b'Isolated observation, not a real user achievement.'
        attached=self.app().request(self.req('attach_evidence',targetPackageId=target,
            expectedPackageRevision=before['package']['revision'],contentBase64=base64.b64encode(raw).decode()))
        ref=attached['packages'][0]['receipt']['effects']['evidenceRef']
        self.assertEqual(ref['sha256'],self.store.sha(raw))
        complete=self.command_request(target,'complete',nodeId='R1');complete['evidenceRefs']=[ref]
        self.app().request(complete);self.assertTrue(self.current(target)['completion']['R1']['complete'])
        forged=self.command_request(target,'edit',nodeId='R1',changes={'title':'Forgery'});forged['by']='user'
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'CORE_FIELDS'):self.app().request(forged)
        self.assertEqual(before,self.sources())

    def test_preacceptance_retry_keeps_logical_ids_and_accepts_one_result(self):
        target=self.create('retry-target');source=self.create('retry-source','ready')
        request=self.replace_request(target,source);preview=self.app().request(request,preflight=True)
        old=self.current(target)['graph']
        def fail(name):
            if name=='staged':raise RuntimeError('Synthetic preacceptance interruption')
        with self.assertRaisesRegex(RuntimeError,'Synthetic preacceptance'):
            self.app().request(request,failpoint=fail)
        self.assertEqual(self.current(target)['graph'],old)
        result=self.app().request(request)
        self.assertTrue(result['published'])
        self.assertEqual(result['packages'][0]['receipt']['effects']['idMap'],preview['effects']['idMap'])
        self.assertEqual(sum(e['type']=='ready_graph_applied' for e in self.current(target)['graph']['events']),1)

    def test_unaccepted_intent_cannot_be_reused_for_another_request(self):
        target=self.create('intent-target');source=self.create('intent-source','ready');request=self.replace_request(target,source)
        def fail(name):
            if name=='staged':raise RuntimeError('Synthetic interruption')
        with self.assertRaises(RuntimeError):self.app().request(request,failpoint=fail)
        changed=copy.deepcopy(request);changed['note']='Different logical request'
        with self.assertRaisesRegex(ValueError,'TRANSACTION_ID_CONFLICT'):self.app().request(changed)
        with self.assertRaisesRegex(ValueError,'TRANSACTION_ID_CONFLICT'):self.app().request(changed,preflight=True)
        self.assertIn('R1',M.entities(self.current(target)['graph']))

    def test_new_placement_requires_position_and_existing_identity(self):
        target=self.create('target');other=self.create('other');request=self.placement(other,target)
        request['plan']['timeConstraints']=[]
        with self.assertRaisesRegex(ValueError,'NEW_PLACEMENT_POSITION_REQUIRED'):self.app().request(request)
        request=self.placement(other,target);request['plan']['steps'][0]['ref']['identitySpace']='wrong'
        with self.assertRaisesRegex(ValueError,'PLAN_REFERENCE_MISMATCH'):self.app().request(request)
        self.assertEqual(self.current(other)['plan']['steps'],[])

    def test_native_dependency_api_uses_same_writer_and_readback(self):
        target=self.create('native-api')
        self.command(target,'add',entity={'id':'R2','kind':'requirement','title':'R2',
                                          'description':'R2','scope':'Synthetic'})
        self.command(target,'add',entity={'id':'Y','kind':'requirement','title':'Y',
                                          'description':'Y','scope':'Synthetic'})
        before=self.current(target)
        request=self.req('dependency_add',targetPackageId=target,
            expectedPackageRevision=before['package']['revision'],
            expectedGraphRevision=before['graph']['revision'],
            sourceId='R1',dependentId='Y',dependencyLevel='L2',
            note='Register native L2 dependency')
        preview=self.app().request(request,preflight=True)
        self.assertFalse(preview['accepted'])
        result=self.app().request(request)
        self.assertTrue(result['published'])
        read=self.app().call({'method':'dependencies','packageId':target})
        self.assertEqual(len(read['edges']),1)
        edge=read['edges'][0];self.assertEqual(edge['dependencyLevel'],'L2')
        self.assertEqual(read['projections'][edge['id']]['nodeId'],'R1')
        current=self.current(target)
        remove=self.req('dependency_remove',targetPackageId=target,
            expectedPackageRevision=current['package']['revision'],
            expectedGraphRevision=current['graph']['revision'],
            edgeId=edge['id'],disposition='Dependency no longer applies',
            note='Remove native dependency')
        self.app().request(remove)
        self.assertEqual(self.app().call({'method':'dependencies','packageId':target})['edges'],[])

    def test_native_dependency_api_accepts_shared_info_criterion_source(self):
        target=self.create('native-info-api')
        self.command(target,'add',entity={'id':'C3','kind':'info','title':'Shared criterion'})
        self.command(target,'add',entity={'id':'Y','kind':'requirement','title':'Y',
                                          'description':'Y','scope':'Synthetic'})
        before=self.current(target)
        request=self.req('dependency_add',targetPackageId=target,
            expectedPackageRevision=before['package']['revision'],
            expectedGraphRevision=before['graph']['revision'],
            sourceId='C3',dependentId='Y',dependencyLevel='L1',
            note='Register direct shared criterion dependency')
        result=self.app().request(request)
        self.assertTrue(result['published'])
        edges=self.app().call({'method':'dependencies','packageId':target})['edges']
        self.assertEqual(len(edges),1)
        self.assertEqual((edges[0]['from'],edges[0]['to'],edges[0]['dependencyLevel']),
                         ('C3','Y','L1'))

    def test_decision_profile_uses_existing_application_for_create_select_and_complete(self):
        request=self.req('create',path='working/decision-profile',role='working',title='Decision process',
            scope='Synthetic Decision scope',coreModel='rdg-decision-v1',
            rootReason='The process exists to test the accepted Decision model')
        created=self.app().request(request);ident=created['packages'][0]['packageId']
        current=self.current(ident);graph=current['graph']
        self.assertEqual(graph['coreModel'],'rdg-decision-v1')
        self.assertEqual(graph['workGraphs'],[])
        self.assertEqual(graph['rootCauses'][0]['reason'],request['rootReason'])
        self.assertEqual(graph['events'][0]['type'],'created')
        self.assertEqual(current['completion']['R1']['active'],True)
        self.assertIn('decision_group',self.app().schema('core',ident,'R1',command='decision_group')['coreCommands'])

        def command(name,data,note):
            snapshot=self.current(ident)
            return self.app().request(self.req('core',targetPackageId=ident,
                expectedPackageRevision=snapshot['package']['revision'],
                expectedGraphRevision=snapshot['graph']['revision'],
                command=name,data=data,note=note))

        command('add',{'entity':{'id':'D1','kind':'decision','title':'Choose path',
            'description':'Choose one path','revision':1,'result':{'state':'open','truth':'unknown'},
            'selectionState':'discovered'},'location':'graph'},'Add Decision')
        command('decision_group',{'group':{'id':'G1','parentId':'R1','title':'Path',
            'selectionRequired':True,'mutuallyExclusive':True,
            'members':[{'id':'M1','decisionId':'D1'}]}},'Connect Decision group')
        for nid in ('R1','D1'):
            snapshot=self.current(ident)
            command('review',{'nodeIds':[nid],'observed':CLI.module('rdg-model-profiles').pins(snapshot['graph'],nid),
                'basis':'Review the current Decision inputs'},'Review '+nid)
        command('select',{'nodeId':'D1'},'Select Decision')
        command('add',{'entity':{'id':'EVID1','kind':'context','title':'Observed result',
            'description':'Synthetic evidence','revision':1,'value':'The path was checked',
            'scope':'Synthetic Decision scope','version':'v1','source':'rdg-portable-service.test'},
            'location':'graph'},'Add evidence')
        command('complete',{'nodeId':'D1','basis':'Decision result observed',
            'evidenceIds':['EVID1']},'Complete Decision')
        command('complete',{'nodeId':'R1','basis':'Requirement result observed',
            'evidenceIds':['EVID1']},'Complete Requirement')
        final=self.current(ident)
        self.assertTrue(final['completion']['D1']['complete'])
        self.assertTrue(final['completion']['R1']['complete'])
        self.assertEqual(M.entities(final['graph'])['D1']['selectionState'],'selected')
        self.assertEqual(final['graph']['revision'],9)

    def test_decision_context_links_survive_api_writes_and_full_graph_copy(self):
        source=self.app().request(self.req('create',path='working/context-source',role='working',
            title='Context source',scope='Actual process scope',coreModel='rdg-decision-v1',
            rootReason='Explicit test'))['packages'][0]['packageId']
        for entity in (
            {'id':'CT1','kind':'context','title':'Existing process fact','description':'Actual',
             'value':'Material circumstance'},
            {'id':'D1','kind':'decision','title':'Choose','description':'Evaluate'},
        ):
            self.command(source,'add',entity=entity,location='graph')
        req=self.command_request(source,'edit',nodeId='D1',
            changes={'decisionContextIds':['CT1','R1'],'contextNotes':{'CT1':'Process condition','R1':'Goal'}},cosmetic=False)
        before=self.sources();preview=self.app().request(req,preflight=True)
        self.assertFalse(preview['accepted']);self.assertEqual(self.sources(),before)
        applied=self.app().request(req,expected_input_binding=preview['inputBinding'])
        self.assertTrue(applied['published'])
        self.assertTrue(self.app().receipt(source,req['transactionId'])['found'])
        snapshot=self.current(source)
        self.assertEqual(M.entities(snapshot['graph'])['D1']['decisionContextIds'],['CT1','R1'])
        focus=self.app().read(source,False,{'kind':'focus','id':'D1'})
        self.assertIn('CT1',{n['id'] for n in focus['view']['entities']})
        self.assertEqual(focus['view']['edges'],[], 'factual refs are not graph dependency edges')
        invalid=self.command_request(source,'edit',nodeId='D1',
            changes={'decisionContextIds':['another-owner-id']},cosmetic=False)
        old=self.sources()
        with self.assertRaisesRegex(ValueError,'DECISION_CONTEXT_REFS'):
            self.app().request(invalid,preflight=True)
        self.assertEqual(self.sources(),old)
        # Copy exact source as a fresh owner: link IDs map to the new objects,
        # without references back into the original process.
        request=self.req('copy',sourcePackageId=source,
            sourcePin={'revision':snapshot['package']['revision'],
                       'sha256':P.digest(snapshot['graph'])},
            path='copy/context-clone',focus={'kind':'graph'},
            note='Check local context remap on full graph copy')
        result=self.app().request(request)
        self.assertTrue(result['published'])
        target=result['packages'][0]['packageId'];graph=self.current(target)['graph']
        found=[n for n in graph['nodes'] if n['kind']=='decision']
        self.assertEqual(len(found),1)
        values=found[0]['decisionContextIds']
        self.assertEqual({M.entities(graph)[i]['kind'] for i in values},{'requirement','context'})
        self.assertFalse(set(values)&{'R1','CT1'})
        self.assertTrue(set(values)<=set(M.entities(graph)))
        # A ready graph imports as normal owned blocks; all contextual links
        # refer to newly inserted IDs inside the target process, not to source.
        draft=self.req('capture_ready',sourcePackageId=source,
            sourcePin={'revision':snapshot['package']['revision'],
                       'sha256':P.digest(snapshot['graph'])},
            path='ready/context-template',focus={'kind':'graph'},
            title='Reusable factual context',note='Capture complete graph with context IDs')
        ready_result=self.app().request(draft)
        self.assertTrue(ready_result['published'])
        ready_id=ready_result['packages'][0]['packageId']
        paper=self.current(ready_id)
        self.assertNotIn('decisionContextIds',
                         next(n for n in paper['graph']['nodes'] if n['kind']=='decision'))
        self.assertEqual(M.entities(self.current(source)['graph'])['D1']['decisionContextIds'],['CT1','R1'],
                         'capture must not change the original process context')
        target=self.app().request(self.req('create',path='working/context-destination',
            role='working',title='Destination',scope='Destination scope',
            coreModel='rdg-decision-v1',rootReason='Explicit destination'))['packages'][0]['packageId']
        before_target=self.current(target)
        apply=self.req('apply_ready',targetPackageId=target,sourcePackageId=ready_id,
            sourcePin={'revision':paper['package']['revision'],
                       'sha256':P.digest(paper['graph'])},
            expectedPackageRevision=before_target['package']['revision'],
            expectedGraphRevision=before_target['graph']['revision'],
            mode='ADD_ROOT',note='Materialize entire ready context into process')
        prepared=self.app().request(apply,preflight=True)
        self.assertFalse(prepared['accepted'])
        published=self.app().request(apply,expected_input_binding=prepared['inputBinding'])
        self.assertTrue(published['published'])
        destination=self.current(target)['graph']
        decisions=[n for n in destination['nodes'] if n['kind']=='decision']
        self.assertEqual(len(decisions),1)
        self.assertNotIn('decisionContextIds',decisions[0],
                         'a new process must choose its own factual context')
        self.assertNotEqual(decisions[0]['id'],'D1')

    def test_capture_ready_focused_decision_does_not_pull_process_only_context_facts(self):
        source=self.app().request(self.req('create',path='working/focused-context-source',role='working',
            title='Focused context source',scope='Process facts',coreModel='rdg-decision-v1',
            rootReason='Evaluate process facts'))['packages'][0]['packageId']
        self.command(source,'add',entity={'id':'R2','kind':'requirement','title':'Separate requirement',
            'description':'Only in process context','scope':'Process'},location='graph')
        self.command(source,'add',entity={'id':'C2','kind':'context','title':'Local operational fact',
            'description':'Current server state','value':'Server already provisioned'},location='graph')
        self.command(source,'add',entity={'id':'C3','kind':'context','title':'Additional local condition',
            'description':'Only an explicit configured context subscription','value':'100 users'},location='graph')
        self.command(source,'add',entity={'id':'D2','kind':'decision','title':'Other Decision',
            'description':'A separate process option'},location='graph')
        self.command(source,'add',entity={'id':'D1','kind':'decision','title':'Reusable option',
            'description':'Reusable method'},location='graph',
            initialRelations=[{'id':'E-D1','type':'DRIVES','from':'R1','to':'D1'}])
        self.command(source,'edit',nodeId='D1',changes={
            'decisionContextIds':['R2','D2','C2'],'contextNotes':{i:'Material process fact' for i in ('R2','D2','C2')}},cosmetic=False)
        self.command(source,'decision_context',nodeId='D1',sourceId='C3',action='save',comment='Additional process condition',rule={'preset':'L1','watch':['definition']})
        snapshot=self.current(source)
        source_before=copy.deepcopy(snapshot['graph'])
        request=self.req('capture_ready',sourcePackageId=source,
            sourcePin={'revision':snapshot['package']['revision'],
                       'sha256':P.digest(snapshot['graph'])},
            path='ready/focused-context-clean',focus={'kind':'decision','id':'D1'},
            title='Reusable option without situational facts',note='Capture only reusable method')
        ready=self.app().request(request)
        self.assertTrue(ready['published'])
        graph=self.current(ready['packages'][0]['packageId'])['graph']
        self.assertEqual({n['kind'] for n in graph['nodes']+graph['objects']},
                         {'requirement','decision'},
                         'process-only references cannot pull unrelated facts into ready')
        self.assertEqual(len(graph['nodes'])+len(graph['objects']),2)
        choice=next(n for n in graph['nodes'] if n['kind']=='decision')
        requirement=next(n for n in graph['nodes'] if n['kind']=='requirement')
        self.assertNotIn('decisionContextIds',choice)
        self.assertEqual([(e['type'],e['from'],e['to']) for e in graph['edges']],
                         [('DRIVES',requirement['id'],choice['id'])])
        self.assertNotIn('C3',{n['id'] for n in graph['objects']})
        self.assertFalse(any(e.get('dependencyPurpose')=='decisionContext' for e in graph['edges']),
            'explicit process-only Context subscriptions cannot enter a ready template')
        self.assertNotIn(choice['id'],{'D1','R1'})
        self.assertEqual(self.current(source)['graph'],source_before)
        # The identical focused *process copy* must retain the configured
        # factual dependency and remap its source into the new independent owner.
        clone=self.app().request(self.req('copy',sourcePackageId=source,
            sourcePin={'revision':snapshot['package']['revision'],
                       'sha256':P.digest(snapshot['graph'])},
            path='copy/focused-context-with-rule',focus={'kind':'decision','id':'D1'},
            note='Copy configured process context as local dependent data'))
        self.assertTrue(clone['published'])
        copied=self.current(clone['packages'][0]['packageId'])['graph']
        subscriptions=[e for e in copied['edges'] if e.get('dependencyPurpose')=='decisionContext']
        self.assertEqual(len(subscriptions),1)
        dep=subscriptions[0]
        self.assertNotIn(dep['from'],{'C3','C2'})
        self.assertEqual(M.entities(copied)[dep['from']]['kind'],'context')
        self.assertEqual(M.entities(copied)[dep['from']]['value'],'100 users')
        self.assertEqual(M.entities(copied)[dep['to']]['kind'],'decision')
        self.assertEqual(dep['dependencyRule']['watch'],['definition'])
        self.assertEqual(self.current(source)['graph'],source_before)

    def test_ready_and_lens_reject_process_context_even_if_empty_and_paper_edit_cannot_add_it(self):
        for role in ('ready','lens'):
            created=self.app().request(self.req('create',path=role+'/context-paper-'+str(uuid.uuid4()),
                role=role,title='A reusable Decision definition',scope='Reusable method',
                coreModel='rdg-decision-v1',rootReason='Reusable goal',
                **({'lensKey':'context-role-'+str(uuid.uuid4())} if role=='lens' else {})))
            ident=created['packages'][0]['packageId']
            existing=self.current(ident)
            request=self.req('paper_edit',targetPackageId=ident,
                expectedPackageRevision=existing['package']['revision'],
                expectedGraphRevision=existing['graph']['revision'],command='add',
                data={'entity':{'id':'D1','kind':'decision','title':'General choice',
                'description':'General guidance','decisionContextIds':[]},'location':'graph'},
                note='Do not put process-specific refs in a reusable definition')
            before=self.sources()
            with self.assertRaisesRegex(ValueError,'DECISION_CONTEXT_PROCESS_ONLY'):
                self.app().request(request,preflight=True)
            self.assertEqual(self.sources(),before)
            request['data']['entity'].pop('decisionContextIds')
            self.assertTrue(self.app().request(request)['published'])
            after=self.current(ident)
            request=self.req('paper_edit',targetPackageId=ident,
                expectedPackageRevision=after['package']['revision'],
                expectedGraphRevision=after['graph']['revision'],command='edit',
                data={'nodeId':'D1','changes':{'decisionContextIds':[]},'cosmetic':False},
                note='Process-only refs cannot be set via paper editing')
            before=self.sources()
            with self.assertRaisesRegex(ValueError,'DECISION_CONTEXT_PROCESS_ONLY'):
                self.app().request(request,preflight=True)
            self.assertEqual(self.sources(),before)
            graph=copy.deepcopy(after['graph'])
            next(n for n in graph['nodes'] if n['id']=='D1')['decisionContextIds']=[]
            with self.assertRaisesRegex(ValueError,'DECISION_CONTEXT_PROCESS_ONLY'):
                CLI.module('rdg-model-profiles').validate_role(graph,role)

    def test_decision_profile_preflight_apply_receipt_and_strict_focus_share_application(self):
        request=self.req('create',path='working/decision-api',role='working',title='Decision API',
            scope='Synthetic API scope',coreModel='rdg-decision-v1',
            rootReason='Exercise the shared Application path')
        created=self.app().request(request);ident=created['packages'][0]['packageId']
        app=self.app();schema=app.schema('core',ident,'R1',command='add')
        self.assertEqual(schema['capabilities']['profile'],'rdg-decision-v1')
        self.assertIn('decision_group',schema['coreCommands'])
        self.assertTrue(schema['capabilities']['capabilities']['planOrderOnly'])
        self.assertTrue(schema['capabilities']['capabilities']['planForks'])
        add=self.req('core',targetPackageId=ident,
            expectedPackageRevision=app.read(ident)['package']['revision'],
            expectedGraphRevision=app.read(ident)['graph']['revision'],command='add',
            data={'entity':{'id':'A1','kind':'action','title':'Check','description':'Check the goal',
                'revision':1,'result':{'state':'open','truth':'unknown'},'actionType':'task',
                'lowLevel':False,'targetIds':[],'groupIds':[]},
                'location':'graph',
                'initialRelations':[{'id':'RA1','type':'REQUIRES_ACTION','from':'R1','to':'A1'}]},
            note='Create a real required Action')
        preview=app.request(add,preflight=True)
        self.assertFalse(preview['accepted'])
        self.assertIn('A1',preview['effects']['changedIds'])
        applied=app.request(add,expected_input_binding=preview['inputBinding'])
        self.assertTrue(applied['published'])
        receipt=app.receipt(ident,add['transactionId'])
        self.assertTrue(receipt['found'])
        focused=app.read(ident,False,{'kind':'focus','id':'R1'})
        ids={n['id'] for n in focused['view']['entities']}
        self.assertEqual(ids,{'R1','A1'})
        self.assertEqual([e['id'] for e in focused['view']['edges']],['RA1'])
        self.assertEqual(focused['capabilities']['profile'],'rdg-decision-v1')
        self.assertIsNone(focused['plan'])
        self.assertTrue(focused['completion']['R1']['blockers'])

    def test_decision_profile_cascade_survives_restart_and_exact_retry(self):
        created=self.app().request(self.req('create',path='working/decision-cascade',role='working',
            title='Cascade',scope='Synthetic scope',coreModel='rdg-decision-v1',rootReason='Test cascade'))
        ident=created['packages'][0]['packageId']
        for node_id,kind in (('D1','decision'),('R2','requirement'),('D2','decision')):
            entity={'id':node_id,'kind':kind,'title':node_id,'description':node_id,'revision':1}
            if kind=='decision':entity.update(selectionState='unselected',result={'state':'open','truth':'unknown'})
            else:entity.update(scope='Synthetic scope',result={'state':'open','truth':'unknown'})
            self.command(ident,'add',entity=entity,location='graph')
        self.command(ident,'link',relation={'id':'I1','type':'INTRODUCES','from':'D1','to':'R2'})
        for group_id,parent,decision in (('G1','R1','D1'),('G2','R2','D2')):
            self.command(ident,'decision_group',group={'id':group_id,'parentId':parent,
                'title':group_id,'selectionRequired':True,'mutuallyExclusive':True,
                'members':[{'id':group_id+'-member','decisionId':decision}]})
        profile=CLI.module('rdg-model-profiles')
        for node_id in ('R1','D1','R2','D2'):
            graph=self.current(ident)['graph']
            if profile.entities(graph)[node_id].get('review',{}).get('required'):
                self.command(ident,'review',nodeIds=[node_id],
                    observed=profile.pins(graph,node_id),basis='Review the actual current inputs')
        self.command(ident,'select',nodeId='D1')
        self.command(ident,'select',nodeId='D2')
        before=self.current(ident);self.assertIn('R2',profile.support_state(before['graph'])['activeIds'])
        withdrawal=self.command_request(ident,'withdraw',nodeId='D1')
        preview=self.app().request(withdrawal,preflight=True)
        self.assertEqual(preview['effects']['supportLostIds'],['D1','D2','R2'])
        accepted=self.app().request(withdrawal,expected_input_binding=preview['inputBinding'])
        self.assertTrue(accepted['published'])
        reopened_app=CLI.application(self.config(),self.token)
        after=reopened_app.read(ident)
        self.assertEqual(profile.entities(after['graph'])['D2']['selectionState'],'unselected')
        self.assertNotIn('R2',profile.support_state(after['graph'])['activeIds'])
        self.assertEqual(len([e for e in after['graph']['events'] if e['type']=='branch_cancelled']),1)
        self.assertTrue(reopened_app.request(withdrawal)['idempotent'])
        self.assertEqual(after['graph'],reopened_app.read(ident)['graph'])
        self.assertTrue(reopened_app.receipt(ident,withdrawal['transactionId'])['found'])

    def test_history_modes_and_requirement_activity_do_not_change_plan_or_owner(self):
        made=self.app().request(self.req('create',path='working/history-modes',role='working',title='History modes',scope='Synthetic',coreModel='rdg-decision-v1',rootReason='Synthetic current process'))
        ident=made['packages'][0]['packageId']
        self.command(ident,'add',entity={'id':'CTX','kind':'context','title':'Load','description':'Synthetic','value':'100'},location='graph')
        self.command(ident,'context_group',action='save',id='CG',title='Conditions',parentId=None)
        self.command(ident,'add',entity={'id':'D','kind':'decision','title':'Choice','description':'Synthetic'},location='graph',initialRelations=[{'id':'RD','type':'DRIVES','from':'R1','to':'D'}])
        self.command(ident,'add',entity={'id':'R2','kind':'requirement','title':'Paper child','description':'Synthetic','scope':'Synthetic'},location='graph',initialRelations=[{'id':'DR2','type':'INTRODUCES','from':'D','to':'R2'}])
        self.review(ident);self.command(ident,'select',nodeId='D')
        self.command(ident,'edit',nodeId='CTX',changes={'value':'1000'},cosmetic=False)
        self.command(ident,'edit',nodeId='CTX',changes={'title':'Readable fact name'},cosmetic=True)
        req=self.app().schema('plan_create',ident)['request'];self.app().request(req)
        req=self.app().schema('place',ident,'D')['request'];req['note']='Plan order only';self.app().request(req)
        before=self.current(ident);all_rows=self.app().history(ident,{'kind':'graph','historyMode':'all'})['events']
        self.assertTrue(all_rows);self.assertTrue(all('historyView' in r for r in all_rows))
        for mode in ('important','meaningful','technical','all'):
            result=self.app().history(ident,{'kind':'graph','historyMode':mode});self.assertEqual(result['modes'],['important','meaningful','technical','all'])
            expected=[r['event']['id'] for r in all_rows if CLI.module('rdg-model-profiles').for_graph(before['graph']).HISTORY.accepts(r['historyView']['level'],mode)]
            self.assertEqual([r['event']['id'] for r in result['events']],expected)
        chosen=next(r for r in all_rows if r['event']['type']=='decision_selected');self.assertEqual(chosen['historyView']['activatedRequirementIds'],['R2'])
        context=next(r for r in all_rows if r['historyView']['label']=='Изменены данные контекста');self.assertEqual(context['historyView']['edits'][0]['before'],'100');self.assertEqual(context['historyView']['edits'][0]['after'],'1000')
        with self.assertRaisesRegex(ValueError,'VIEW_HISTORY_MODE'):self.app().history(ident,{'kind':'graph','historyMode':'invalid'})
        after=self.current(ident)
        for key in ('graph','plan','layouts'):self.assertEqual(after[key],before[key])

    def test_context_record_migrates_stored_legacy_id_with_readonly_preflight_and_exact_receipt_retry(self):
        fixture=FIX.PortableStore();fixture.setUp();self.addCleanup(fixture.doCleanups)
        profiles=CLI.module('rdg-model-profiles');graph=profiles.blank('legacy-record-owner','Legacy record',str(uuid.uuid4()),'R1','Goal','Synthetic',core_model='rdg-decision-v1',root_reason='Synthetic compatibility owner')
        graph['objects'].append({'id':'EV','kind':'evidence','title':'Recorded observation','description':'Synthetic','revision':1,'claim':'Observed result','scope':'Synthetic scope','version':'1','source':'Test log'})
        plan={'schemaVersion':3,'kind':'temporalPlan','id':str(uuid.uuid4()),'identitySpace':graph['identitySpace'],'title':'Synthetic','revision':1,'status':'candidate','steps':[],'mainStepIds':[],'forks':[],'timeConstraints':[]}
        ident,_,_=fixture.create('legacy-context-record',graph=graph,plan=plan)
        app=CLI.application({'packageRoot':str(fixture.root),'namespaceId':fixture.namespace,'coordinationRoot':str(fixture.base),'authorityStore':str(fixture.authority.path)},fixture.token)
        before=app.read(ident,True);request={'transactionId':str(uuid.uuid4()),'op':'core','targetPackageId':ident,'expectedPackageRevision':before['package']['revision'],'expectedGraphRevision':before['graph']['revision'],'command':'context_record','data':{'nodeId':'EV'},'note':'Preserve existing confirmation as process context'}
        preview=app.request(request,preflight=True);self.assertEqual(app.read(ident,True)['graph'],before['graph'])
        result=app.request(request,expected_input_binding=preview['inputBinding']);self.assertTrue(result['published']);replay=app.request(request);self.assertTrue(replay['idempotent']);self.assertEqual(replay['participants'],result['participants'])
        after=app.read(ident,True);n=next(n for n in after['graph']['objects'] if n['id']=='EV');self.assertEqual(n['kind'],'context');self.assertEqual(n['value'],'Observed result');self.assertEqual(n['source'],'Test log')
        with self.assertRaisesRegex(ValueError,'EVIDENCE_RETIRED_USE_CONTEXT'):
            app.request({'transactionId':str(uuid.uuid4()),'op':'create','path':'working/forged-old-kind','role':'working','title':'Forbidden new Evidence','graph':graph,'rootReason':'Synthetic rejection'},preflight=True)

    def test_decision_profile_artifact_evidence_requires_verified_existing_bytes(self):
        created=self.app().request(self.req('create',path='working/decision-artifact',role='working',
            title='Artifact',scope='Synthetic scope',coreModel='rdg-decision-v1',rootReason='Verify Evidence'))
        ident=created['packages'][0]['packageId']
        artifact={'path':'evidence/observed.txt','sha256':'a'*64}
        evidence={'id':'EV1','kind':'context','title':'Witness','description':'Witness',
            'value':'Observed goal','scope':'Synthetic scope','version':'1','source':'fixture',
            'revision':1,'artifact':artifact}
        self.command(ident,'add',entity=evidence,location='graph')
        request=self.command_request(ident,'complete',nodeId='R1',basis='Observed result',evidenceIds=['EV1'])
        with self.assertRaisesRegex(ValueError,'EVIDENCE_ARTIFACT_PIN_NOT_VERIFIED'):
            self.app().request(request,preflight=True)
        request['evidenceRefs']=[artifact]
        with self.assertRaisesRegex(ValueError,'EVIDENCE_BYTES_UNAVAILABLE'):
            self.app().request(request,preflight=True)
        self.assertEqual(self.current(ident)['graph']['revision'],2)

    def test_decision_delete_uses_coordinator_and_preserves_history(self):
        create=self.req('create',path='working/decision-delete',role='working',title='Deletion',
            scope='Synthetic scope',coreModel='rdg-decision-v1',rootReason='Delete with strict closure')
        ident=self.app().request(create)['packages'][0]['packageId']
        entity={'id':'R2','kind':'requirement','title':'Child','description':'Child',
            'revision':1,'scope':'Synthetic scope','result':{'state':'open','truth':'unknown'}}
        self.command(ident,'add',entity=entity,location='graph',
            initialRelations=[{'id':'DER1','type':'DERIVES','from':'R1','to':'R2'}])
        snapshot=self.current(ident)
        delete=self.req('delete',targetPackageId=ident,
            expectedPackageRevision=snapshot['package']['revision'],
            expectedGraphRevision=snapshot['graph']['revision'],
            nodeIds=['R2'],note='Explicitly delete child')
        preview=self.app().request(delete,preflight=True)
        self.assertIn('R2',preview['effects']['removedIds'])
        result=self.app().request(delete,expected_input_binding=preview['inputBinding'])
        self.assertTrue(result['published'])
        current=self.app().read(ident)
        self.assertNotIn('R2',CLI.module('rdg-model-profiles').entities(current['graph']))
        self.assertFalse(current['graph']['edges'])
        self.assertTrue(any(e['type']=='removed' and 'R2' in e['nodeIds'] for e in current['graph']['events']))
        self.assertTrue(self.app().request(delete)['idempotent'])
        self.assertEqual(current['graph'],self.app().read(ident)['graph'])
        self.assertTrue(self.app().receipt(ident,delete['transactionId'])['found'])
        self.assertTrue(current['completion']['R1']['reviewRequired'])

    def test_legacy_plan_writer_fails_closed_for_decision_source(self):
        decision=self.app().request(self.req('create',path='working/decision-referenced',
            role='working',title='Referenced',scope='Synthetic scope',coreModel='rdg-decision-v1',
            rootReason='Do not delete placed entity'))['packages'][0]['packageId']
        entity={'id':'R2','kind':'requirement','title':'Placed child','description':'Child',
                'revision':1,'scope':'Synthetic scope','result':{'state':'open','truth':'unknown'}}
        self.command(decision,'add',entity=entity,location='graph')
        other=self.create('decision-incoming-plan-owner')
        before_graph=self.current(decision)['graph']
        before_plan=self.current(other)['plan']
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_PROFILE_CAPABILITY'):
            self.app().request(self.placement(other,decision,'R2'))
        self.assertEqual(self.current(decision)['graph'],before_graph)
        self.assertEqual(self.current(other)['plan'],before_plan)

    def test_decision_external_action_has_details_but_no_graph_membership(self):
        created=self.app().request(self.req('create',path='working/decision-external',role='working',
            title='External tasks',scope='Synthetic scope',coreModel='rdg-decision-v1',
            rootReason='Check exterior Action identity'))
        ident=created['packages'][0]['packageId']
        self.command(ident,'work_graph',workGraph={'id':'EXTERNAL-CONTEXT','title':'Explicit test area','rootIds':['R1'],'memberIds':['R1']})
        task={'id':'EXT1','kind':'action','title':'Research','description':'Independent task',
            'revision':1,'actionType':'task','lowLevel':True,'targetIds':[],
            'groupIds':[],'result':{'state':'open','truth':'unknown'}}
        self.command(ident,'add',entity=task,location='external')
        current=self.app().read(ident)
        self.assertIn('EXT1',current['references'])
        self.assertNotIn('EXT1',{n['id'] for n in current['view']['entities']})
        self.assertFalse(any('EXT1' in w['memberIds'] for w in current['graph']['workGraphs']))
        focused=self.app().read(ident,False,{'kind':'focus','id':'EXT1'})
        self.assertEqual(focused['view']['externalAction']['id'],'EXT1')
        self.assertEqual(focused['view']['entities'],[])
        self.assertEqual(focused['view']['edges'],[])

    def test_decision_ready_authoring_does_not_manufacture_low_level_executions(self):
        created=self.app().request(self.req('create',path='templates/decision-paper',role='ready',
            title='Paper Decision',scope='Synthetic template scope',coreModel='rdg-decision-v1',
            rootReason='A paper process is not performed work'))
        ident=created['packages'][0]['packageId']
        before=self.current(ident)
        entity={'id':'D1','kind':'decision','title':'Unselected choice','description':'Option',
                'revision':1,'selectionState':'discovered',
                'result':{'state':'open','truth':'unknown'}}
        request=self.req('paper_edit',targetPackageId=ident,
            expectedPackageRevision=before['package']['revision'],
            expectedGraphRevision=before['graph']['revision'],
            command='add',data={'entity':entity,'location':'graph'},
            note='Define, but do not execute an option')
        self.assertTrue(self.app().request(request)['published'])
        after=self.app().read(ident)
        self.assertIn('D1',CLI.module('rdg-model-profiles').entities(after['graph']))
        self.assertEqual(after['graph']['events'],[])
        self.assertEqual(after['graph']['externalActions'],[])
        self.assertIsNone(after['plan'])
        self.assertEqual(after['graph']['nodes'][-1]['selectionState'],'discovered')

    def test_decision_profile_native_l1_l2_dependency_api(self):
        ident=self.app().request(self.req('create',path='working/decision-dependencies',role='working',
            title='Dependencies',scope='Synthetic scope',coreModel='rdg-decision-v1',
            rootReason='Validate typed dependencies'))['packages'][0]['packageId']
        entity={'id':'R2','kind':'requirement','title':'Dependent R','description':'Dependent',
            'revision':1,'scope':'Synthetic scope','result':{'state':'open','truth':'unknown'}}
        self.command(ident,'add',entity=entity,location='graph')
        self.command(ident,'link',relation={'id':'DEP1','type':'DEPENDS_ON',
            'from':'R1','to':'R2','dependencyLevel':'L2'})
        result=self.app().call({'method':'dependencies','packageId':ident})
        self.assertEqual([(e['id'],e['dependencyLevel']) for e in result['edges']],[('DEP1','L2')])
        projection=result['projections']['DEP1']
        self.assertEqual(projection['profile'],'rdg-decision-v1')
        self.assertEqual(set(projection['affectedIds']),{'R1','R2'})

    def test_finding_fixes_persist_through_application_retry_and_readback(self):
        ident=self.app().request(self.req('create',role='working',path='working/decision-findings',
            title='Findings verification',scope='Synthetic',coreModel='rdg-decision-v1',
            rootReason='Exercise confirmed contract repairs'))['packages'][0]['packageId']
        profile=CLI.module('rdg-model-profiles')
        fake={'id':'FAKE1','kind':'action','title':'Not discovered','description':'Not performed',
              'actionType':'discover_requirement','lowLevel':True,'targetIds':[],'groupIds':[],
              'revision':1,'result':{'state':'open','truth':'unknown'}}
        invalid=self.command_request(ident,'add',entity=fake,location='external')
        before=self.current(ident)['graph']
        with self.assertRaisesRegex(ValueError,'OPERATION_RECORD_ONLY'):
            self.app().request(invalid,preflight=True)
        self.assertEqual(self.current(ident)['graph'],before)
        req={'id':'R2','kind':'requirement','title':'Child','description':'Child',
             'scope':'Synthetic','revision':1,'result':{'state':'open','truth':'unknown'}}
        connected=self.command_request(ident,'add',entity=req,location='graph',
            initialRelations=[{'id':'DER1','type':'DERIVES','from':'R1','to':'R2'}])
        preview=self.app().request(connected,preflight=True)
        self.assertIn('DER1',preview['effects']['relationIds'])
        accepted=self.app().request(connected,expected_input_binding=preview['inputBinding'])
        self.assertTrue(accepted['published'])
        app=CLI.application(self.config(),self.token)
        graph=app.read(ident)['graph']
        latest=graph['events'][-1]
        linked=next(e for e in graph['events'] if e['type']=='linked')
        self.assertEqual(linked['relationIds'],['DER1'])
        self.assertEqual(latest['type'],'created')
        self.assertEqual(linked['transactionId'],latest['transactionId'])
        self.assertTrue(app.request(connected)['idempotent'])
        self.assertEqual(graph,app.read(ident)['graph'])
        self.assertTrue(app.receipt(ident,connected['transactionId'])['found'])
        observed=profile.pins(graph,'R1')
        historical_sha=CLI.module('rdg-portable-model').digest(graph)
        self.command(ident,'review',nodeIds=['R1'],observed=observed,
                     basis='Verify actual revision pins')
        reviewed=CLI.application(self.config(),self.token).read(ident)['graph']['events'][-1]
        self.assertEqual({r['nodeId']:r['revision'] for r in reviewed['observedPins']},observed)
        self.assertTrue(all(r['sha256']==historical_sha and
            r['graphRevision']==graph['revision'] and
            r['packageId']==ident for r in reviewed['observedPins']))
        protected={'id':'R3','kind':'requirement','title':'Stable','description':'Stable',
                   'scope':'Synthetic','revision':1,'result':{'state':'open','truth':'unknown'},
                   'policy':{'mode':'stable'},
                   'locks':{'edit':{'mode':'warning','principals':[],
                                   'message':'Explain the stable edit'}}}
        self.command(ident,'add',entity=protected,location='graph')
        attempted=self.command_request(ident,'edit',nodeId='R3',
            changes={'description':'Changed'},cosmetic=False)
        previous=self.current(ident)['graph']
        with self.assertRaisesRegex(ValueError,'STABLE_REASON_REQUIRED'):
            self.app().request(attempted,preflight=True)
        self.assertEqual(previous,self.current(ident)['graph'])
        permitted=self.command_request(ident,'edit',nodeId='R3',
            changes={'description':'Changed'},cosmetic=False)
        permitted['reasonForReconsideration']='Changed conditions justify revisiting the goal'
        warning_preview=self.app().request(permitted,preflight=True)
        self.assertEqual(warning_preview['effects']['lockWarnings'],
            [{'nodeId':'R3','operation':'edit','message':'Explain the stable edit'}])
        published=self.app().request(permitted,expected_input_binding=warning_preview['inputBinding'])
        self.assertTrue(published['published'])
        self.assertEqual(published['packages'][0]['receipt']['effects']['lockWarnings'],
                         warning_preview['effects']['lockWarnings'])
        self.assertTrue(self.app().receipt(ident,permitted['transactionId'])['found'])
        readback=CLI.application(self.config(),self.token).read(ident)['graph']
        warnings=readback['events'][-1]['lockWarnings']
        self.assertEqual(warnings,[{'nodeId':'R3','operation':'edit',
            'message':'Explain the stable edit'}])
        self.assertTrue(self.app().request(permitted)['idempotent'])
        self.assertEqual(readback,self.current(ident)['graph'])
        for bad_data,expected_error in (
            ({'nodeId':'R1','basis':'Observed','evidenceIds':[]},'OBLIGATIONS_OPEN:R2'),
            ({'nodeId':'R1','basis':'Observed','evidenceIds':['MISSING'],
              'decisionOutcome':'invalid'},'SCHEMA_INVALID')):
            invalid=self.command_request(ident,'complete',**bad_data)
            before_invalid=self.current(ident)['graph']
            with self.assertRaisesRegex(ValueError,'^'+expected_error+'$'):
                self.app().request(invalid,preflight=True)
            self.assertEqual(before_invalid,self.current(ident)['graph'])

    def test_finding_02_decision_focus_does_not_include_other_group_metadata(self):
        ident=self.app().request(self.req('create',role='working',path='working/decision-focus-boundary',
            title='Focus',scope='Synthetic',coreModel='rdg-decision-v1',
            rootReason='Verify strict scoped group metadata'))['packages'][0]['packageId']
        for name,kind in (('R2','requirement'),('D1','decision'),('D2','decision')):
            node={'id':name,'kind':kind,'title':name,'description':name,'revision':1}
            if kind=='requirement':node.update(scope='Synthetic',result={'state':'open','truth':'unknown'})
            else:node.update(selectionState='unselected',result={'state':'open','truth':'unknown'})
            self.command(ident,'add',entity=node,location='graph')
        for group_id,parent,decision in (('G1','R1','D1'),('G2','R2','D2')):
            self.command(ident,'decision_group',group={'id':group_id,'parentId':parent,
                'title':group_id,'selectionRequired':False,'mutuallyExclusive':True,
                'members':[{'id':'M'+group_id,'decisionId':decision}]})
        focus=self.app().read(ident,False,{'kind':'focus','id':'D1'})['view']
        self.assertEqual([g['id'] for g in focus['decisionGroups']],['G1'])
        self.assertEqual([v['groupId'] for v in focus['groupVisibility']],['G1'])
        self.assertEqual(focus['groupVisibility'][0]['visibleIds'],['D1'])
        self.assertEqual([r['id'] for r in focus['decisionMemberships']],['MG1'])
        self.assertNotIn('D2',str(focus['groupVisibility']))
        full=self.app().read(ident,False,{'kind':'graph'})['view']
        self.assertEqual({v['groupId'] for v in full['groupVisibility']},{'G1','G2'})


    def test_postfix_public_delete_rejects_protected_surviving_action(self):
        ident=self.app().request(self.req('create',role='working',path='working/delete-guard-postfix',
            title='Protected deletion',scope='Synthetic',coreModel='rdg-decision-v1',
            rootReason='Test coordinated cleanup lock'))['packages'][0]['packageId']
        d={'id':'D1','kind':'decision','title':'D1','description':'D1',
           'revision':1,'selectionState':'unselected','result':{'state':'open','truth':'unknown'}}
        e={'id':'EXT1','kind':'action','title':'Task','description':'Protected target',
           'actionType':'task','lowLevel':True,'targetIds':['D1'],'groupIds':[],
           'revision':1,'result':{'state':'open','truth':'unknown'},
           'locks':{'edit':{'mode':'hard','principals':['owner:key'],'message':'Cannot edit targets'}}}
        self.command(ident,'add',entity=d,location='graph')
        self.command(ident,'add',entity=e,location='external')
        before=self.app().read(ident)
        delete=self.req('delete',targetPackageId=ident,
            expectedPackageRevision=before['package']['revision'],
            expectedGraphRevision=before['graph']['revision'],
            nodeIds=['D1'],note='Try protected deletion')
        with self.assertRaisesRegex(ValueError,'OBJECT_OPERATION_LOCK_REQUIRED'):
            self.app().request(delete,preflight=True)
        readback=self.app().read(ident)
        self.assertEqual(before['graph'],readback['graph'])
        self.assertEqual(before['package']['revision'],readback['package']['revision'])
        self.assertEqual(readback['graph']['externalActions'][0]['targetIds'],['D1'])

    def test_postfix_decision_decline_and_typed_binding_work_through_public_api(self):
        create=self.req('create',role='working',path='working/decline-postfix',
            title='Decline',scope='Synthetic',coreModel='rdg-decision-v1',
            rootReason='Verify actual decision outcome')
        preview=self.app().request(create,preflight=True)
        self.assertEqual((preview['inputBinding']['schemaVersion'],preview['inputBinding']['policy']),
            (2,'typed-owner-read-set-v1'))
        self.assertEqual(preview['inputBinding']['ownerPins'],[])
        # Creating a working process must neither install lenses nor mutate the registry.
        self.assertEqual(len(preview['inputBinding']['effectOwners']),1)
        self.assertEqual(sum(o['kind']=='recommendationRegistry' for o in preview['inputBinding']['effectOwners']),0)
        ident=self.app().request(create,expected_input_binding=preview['inputBinding'])['packages'][0]['packageId']
        self.assertEqual([p['packageId'] for p in self.app().catalog()['packages']],[ident])
        self.assertEqual(self.current(ident)['graph']['recommendationPackageIds'],[])
        self.assertEqual(self.app().recommendation_catalog()['packages'],[])
        decision={'id':'D1','kind':'decision','title':'D1','description':'D1',
                  'revision':1,'selectionState':'unselected','result':{'state':'open','truth':'unknown'}}
        evidence={'id':'EV1','kind':'context','title':'Evidence','description':'Evidence',
                  'value':'Examined','scope':'Synthetic','version':'1','source':'fixture','revision':1}
        action={'id':'A1','kind':'action','title':'Decide','description':'Decide',
                'actionType':'decide_acceptance','lowLevel':False,'targetIds':['D1'],
                'groupIds':[],'revision':1,'result':{'state':'open','truth':'unknown'}}
        self.command(ident,'add',entity=decision,location='graph')
        self.command(ident,'add',entity=evidence,location='graph')
        self.command(ident,'add',entity=action,location='graph',
            initialRelations=[{'id':'REQ-A','type':'REQUIRES_ACTION','from':'R1','to':'A1'}])
        req=self.command_request(ident,'complete',nodeId='A1',basis='Rejected on evidence',
            evidenceIds=['EV1'],decisionOutcome='unselected')
        before=self.app().read(ident)
        pending=self.app().request(req,preflight=True)
        binding=pending['inputBinding']
        self.assertEqual((binding['schemaVersion'],binding['policy']),(2,'typed-owner-read-set-v1'))
        self.assertEqual(len(binding['ownerPins']),1)
        self.assertEqual(binding['ownerPins'][0]['packageId'],ident)
        self.assertEqual(binding['ownerPins'][0]['revision'],before['package']['revision'])
        self.assertEqual(binding['requiredPermissions'][0]['owner']['kind'],'package')
        self.assertEqual(binding['effectOwners'][0]['packageId'],ident)
        self.assertEqual(CLI.module('rdg-portable-model').digest(
            {k:v for k,v in binding.items() if k!='sha256'}),binding['sha256'])
        bad=copy.deepcopy(binding);bad['schemaVersion']=1
        with self.assertRaisesRegex(ValueError,'PREVIEW_INPUTS_CHANGED'):
            self.app().request(req,expected_input_binding=bad)
        self.assertEqual(self.app().read(ident)['graph'],before['graph'])
        committed=self.app().request(req,expected_input_binding=binding)
        self.assertTrue(committed['published'])
        after=CLI.application(self.config(),self.token).read(ident)['graph']
        self.assertEqual(CLI.module('rdg-model-profiles').entities(after)['D1']['selectionState'],'unselected')
        self.assertEqual(CLI.module('rdg-model-profiles').entities(after)['A1']['result']['state'],'confirmed')
        self.assertEqual(after['events'][-1]['actionResult'],
            {'decisionId':'D1','decisionOutcome':'unselected'})
        self.assertTrue(self.app().request(req)['idempotent'])
        self.assertTrue(self.app().receipt(ident,req['transactionId'])['found'])

        legacy=self.req('create',role='working',path='working/legacy-postfix',
            title='Legacy unchanged')
        legacy_binding=self.app().request(legacy,preflight=True)['inputBinding']
        self.assertEqual((legacy_binding['schemaVersion'],legacy_binding['policy']),
            (1,'full-read-set-v1'))

    def test_operation_lock_api_requires_user_attribution_and_reads_pairs(self):
        target=self.create('lock-api');self.command(target,'add',entity={'id':'R2','kind':'requirement',
            'title':'R2','description':'R2','scope':'Synthetic'})
        current=self.current(target)
        schema=self.app().schema('lock_set',target,'R1')
        self.assertEqual(schema['request']['op'],'lock_set')
        user_app=CLI.application(self.config(),self.token,'user')
        request=self.req('lock_set',targetPackageId=target,
            expectedPackageRevision=current['package']['revision'],
            expectedGraphRevision=current['graph']['revision'],nodeId='R1',
            operation='edit',mode='hard',principals=['key:k1'],
            message='Protect R1',authorityPrincipal='user:owner',
            note='Set operation lock')
        result=user_app.request(request);self.assertTrue(result['published'])
        locks=user_app.call({'method':'locks','packageId':target})
        self.assertEqual(locks['locks']['R1']['edit']['principals'],['key:k1'])
        current=self.current(target)
        remove=self.req('lock_remove',targetPackageId=target,
            expectedPackageRevision=current['package']['revision'],
            expectedGraphRevision=current['graph']['revision'],nodeId='R1',
            operation='edit',disposition='Owner removal',
            authorityPrincipal='user:owner',note='Remove operation lock')
        user_app.request(remove)
        self.assertEqual(user_app.call({'method':'locks','packageId':target})['locks'],{})


    def test_explicit_management_of_supplied_lens_and_registry_preserves_identity_and_history(self):
        """Synthetic legacy data, explicit takeover, normal edit and pinned history."""
        app=self.app()
        lens_request=self.req('create',path='lenses/fundamental/synthetic',role='lens',
            lensKey='synthetic',title='Supplied old lens',scope='Fixture',
            coreModel='rdg-decision-v1',rootReason='Synthetic supplied fixture')
        lens_id=app.request(lens_request)['packages'][0]['packageId']
        lens_row=self.store.read(lens_id)
        provenance={'supplied':True,'sourceDefinitionSHA256':'a'*64}
        self._seed_source_metadata({lens_id:{'path':lens_row['path'],'before':lens_row,
                                 'lineage':provenance,'permissions':['graph.write']}})
        before=self.store.read(lens_id)
        self.assertTrue(app.read(lens_id)['immutableDefinition'])
        before_graph=copy.deepcopy(before['graph'])
        graph_path=before['head']['current']['graph']
        pin=P.reference(lens_id,before_graph,'R1')
        self.assertEqual(pin['graphRevision'],1)
        source_pin={k:pin[k] for k in ('packageId','identitySpace','graphRevision','sha256')}
        # Ordinary editing cannot turn a supplied definition into a mutable one.
        edit=self.req('paper_edit',targetPackageId=lens_id,
            expectedPackageRevision=before['head']['revision'],
            expectedGraphRevision=before_graph['revision'],command='add',
            data={'entity':{'id':'R2','kind':'requirement','title':'Managed lens requirement',
                            'description':'Explicit owner-managed content','scope':'Synthetic'}} ,note='Guard')
        with self.assertRaisesRegex(ValueError,'PACKAGE_IMMUTABLE'):app.request(edit)
        req=app.schema('lens_manage',lens_id)['request']
        self.assertFalse(req['confirmOwnerManagement'])
        req['note']='Owner explicitly accepts management of this legacy definition'
        with self.assertRaisesRegex(ValueError,'OWNER_MANAGEMENT_CONFIRMATION_REQUIRED'):app.request(req)
        req['confirmOwnerManagement']=True
        before_bytes=self.sources()
        preview=app.request(req,preflight=True)
        self.assertEqual(self.sources(),before_bytes)
        grant=self.authority.manage('issue',self.admin,{'permissions':['graph.read','graph.write'],
            'scopes':['packages/'+self.namespace+'/']})['token']
        with self.assertRaisesRegex(ValueError,'MISSING_PERMISSION: package.move'):
            self.app(grant).request(req)
        # Issuing a scoped token changes the authority fixture, not RDG data.
        # Take the no-write baseline after the grant has been issued.
        before_bytes=self.sources()
        applied=app.request(req,expected_input_binding=preview['inputBinding'])
        self.assertTrue(applied['published'])
        self.assertTrue(app.request(req,expected_input_binding=preview['inputBinding'])['idempotent'])
        new=self.store.read(lens_id)
        self.assertEqual(new['head']['lineage']['sourceDefinitionSHA256'],'a'*64)
        self.assertTrue(new['head']['lineage']['supplied'])
        self.assertTrue(new['head']['lineage']['userManaged'])
        self.assertEqual(new['head']['revision'],before['head']['revision']+1)
        self.assertEqual(new['head']['current']['graph'],graph_path)
        self.assertEqual(new['graph'],before_graph)
        self.assertFalse(app.read(lens_id)['immutableDefinition'])
        self.assertEqual(self.store.historical_graph(lens_id,pin['identitySpace'],pin['graphRevision'],pin['sha256']),before_graph)
        self.assertEqual(app.source_snapshot(lens_id,source_pin)['graph'],before_graph)
        with self.assertRaisesRegex(ValueError,'PACKAGE_CAS_MISMATCH'):
            app.request({**req,'transactionId':str(uuid.uuid4())})
        current=app.read(lens_id)
        edit.update(transactionId=str(uuid.uuid4()),expectedPackageRevision=current['package']['revision'],
                    expectedGraphRevision=current['graph']['revision'],note='Now edit the managed lens')
        app.request(edit)
        self.assertIn('R2',{n['id'] for n in app.read(lens_id)['graph']['nodes']})
        self.assertEqual(app.source_snapshot(lens_id,source_pin)['graph'],before_graph)
        self.assertEqual([r['lensKey'] for r in app.catalog()['packages'] if r.get('role')=='lens'],['synthetic'])

        # Synthetic legacy registry, same stable definition ID and consumers.
        definition={'id':str(uuid.uuid4()),'revision':1,'key':'fundamental','title':'Supplied rules',
                    'supplied':False,'rules':[{'id':'R','nodeKinds':['requirement'],'scope':'all',
                    'state':'any','lensRefs':[{'packageId':lens_id,'identitySpace':before_graph['identitySpace'],
                                             'lensKey':'synthetic'}]}]}
        reg=app.recommendation_catalog()
        app.request(self.req('recommendation_edit',action='create',definition=definition,
                             expectedRegistryRevision=reg['registryRevision'],note='Synthetic legacy registry'))
        registry_row=self.store.registry_read()
        synthetic=copy.deepcopy(registry_row['registry'])
        synthetic['revision']+=1
        synthetic['packages'][0]['supplied']=True
        self._seed_source_metadata({self.store.registry_key():{'path':'.rdg/recommendations',
            'before':registry_row,'registry':synthetic,'permissions':['graph.write']}})
        supplied=app.recommendation_catalog();self.assertTrue(supplied['packages'][0]['supplied'])
        before_bytes=self.sources()
        denied=self.req('recommendation_edit',action='edit',packageId=definition['id'],
            expectedRegistryRevision=supplied['registryRevision'],definition={**synthetic['packages'][0],
            'revision':2},note='Guard supplied')
        with self.assertRaisesRegex(ValueError,'PACKAGE_IMMUTABLE'):app.request(denied)
        manage=self.req('recommendation_edit',action='manage',packageId=definition['id'],
            expectedRegistryRevision=supplied['registryRevision'],confirmOwnerManagement=True,
            note='Owner accepts management of supplied registry definition')
        preview=app.request(manage,preflight=True)
        self.assertEqual(self.sources(),before_bytes)
        with self.assertRaisesRegex(ValueError,'MISSING_PERMISSION: package.move'):
            self.app(grant).request(manage)
        result=app.request(manage,expected_input_binding=preview['inputBinding'])
        self.assertTrue(result['published'])
        self.assertTrue(app.request(manage,expected_input_binding=preview['inputBinding'])['idempotent'])
        after=app.recommendation_catalog();managed=after['packages'][0]
        self.assertEqual(managed['id'],definition['id'])
        self.assertEqual(managed['revision'],2)
        self.assertTrue(managed['supplied'])
        self.assertTrue(managed['userManaged'])
        ordinary={**managed,'revision':3,'title':'Edited via ordinary API'}
        edit_reg=self.req('recommendation_edit',action='edit',packageId=definition['id'],
            expectedRegistryRevision=after['registryRevision'],definition=ordinary,note='Update controlled definition')
        app.request(edit_reg)
        self.assertEqual(app.recommendation_catalog()['packages'][0]['title'],'Edited via ordinary API')
        self.assertEqual(app.recommendation_catalog()['packages'][0]['id'],definition['id'])
        with self.assertRaisesRegex(ValueError,'REGISTRY_CAS_MISMATCH'):
            app.request({**manage,'transactionId':str(uuid.uuid4())})
        reg=app.recommendation_catalog()
        with self.assertRaisesRegex(ValueError,'PACKAGE_IMMUTABLE'):
            app.request(self.req('recommendation_edit',action='remove',packageId=definition['id'],
                expectedRegistryRevision=reg['registryRevision'],note='Supplied origin cannot be deleted'))
        forbidden=dict(ordinary,revision=4,userManaged=False)
        with self.assertRaisesRegex(ValueError,'REGISTRY_CAS_MISMATCH'):
            app.request(self.req('recommendation_edit',action='edit',packageId=definition['id'],
                expectedRegistryRevision=app.recommendation_catalog()['registryRevision'],
                definition=forbidden,note='Cannot forge protected provenance'))

    def _seed_source_metadata(self, changes):
        """Fixture-only FileStore transaction; not a production API bypass."""
        tx=str(uuid.uuid4());checks=[{'namespaceId':self.namespace,'packageId':key if key!=self.store.registry_key() else None,
            'path':value['path'] if key!=self.store.registry_key() else None,'permissions':value['permissions']}
            for key,value in changes.items()]
        def authorize():
            for item in checks:
                self.authority.authorize_portable(self.token,item['permissions'],self.namespace,
                    item['packageId'],item['path'])
        with self.store.lock(True):
            self.store.commit(tx,P.digest({'transactionId':tx,'operation':'seed-fixture'}),changes,
                FIX.AUTH.token_digest(self.token),authorize,
                lambda:self.authority.checked_portable_transaction(self.token,checks),
                {key:value['before']['headSHA256'] for key,value in changes.items()})

if __name__=='__main__':unittest.main()
