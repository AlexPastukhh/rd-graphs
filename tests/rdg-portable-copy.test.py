#!/usr/bin/env python3
"""Real copy/insert/history/layout/reference paths on disposable packages."""
import copy
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
BASE=SourceFileLoader('copy_application_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
P,M=BASE.P,BASE.M


class CopyApplication(BASE.PortableApplication):
    def make_selected(self,shared=False):
        ident=self.create('source')
        self.command(ident,'add',entity={'id':'A','kind':'action','title':'Source action'})
        self.command(ident,'add',entity={'id':'OUT','kind':'requirement','title':'Output','description':'Output','scope':'Synthetic'})
        self.command(ident,'link',edge={'id':'driver','type':'DRIVES','from':'R1','to':'A'})
        if shared:
            self.command(ident,'add',entity={'id':'R2','kind':'requirement','title':'Shared','description':'Shared','scope':'Synthetic'})
            self.command(ident,'link',edge={'id':'second-driver','type':'DRIVES','from':'R2','to':'A'})
        self.command(ident,'link',edge={'id':'output','type':'INTRODUCES','from':'A','to':'OUT','origin':
            {'role':'subgoal','requirementIds':['R2']} if shared else {'role':'method_correctness'}})
        self.review(ident);self.command(ident,'select',nodeId='A');self.review(ident)
        return ident

    def copy_request(self,ident,focus=None,**fields):
        source=self.current(ident)
        return self.req('copy',sourcePackageId=ident,sourcePin={'revision':source['package']['revision'],
            'sha256':P.digest(source['graph'])},focus=focus or {'kind':'graph'},path='copies/'+str(uuid.uuid4()),**fields)

    def copied(self,request):
        result=self.app().request(request);return result['packages'][0]['packageId'],result['packages'][0]['receipt']['effects']['idMap']

    def actual_review(self,ident):
        graph=self.current(ident)['graph'];ids=[i for i,n in M.entities(graph).items() if n.get('review',{}).get('required')]
        if ids:self.command(ident,'review',nodeIds=ids,observed={i:r for j in ids for i,r in M.pins(graph,j).items()})

    def test_full_copy_preserves_completed_facts_all_plan_versions_evidence_and_layouts(self):
        source=self.make_selected()
        self.app().request(self.placement(source,source,'A'))
        # Real proof bytes, without asserting a real-world user achievement.
        import base64
        current=self.current(source)
        attached=self.app().request(self.req('attach_evidence',targetPackageId=source,
            expectedPackageRevision=current['package']['revision'],contentBase64=base64.b64encode(b'Synthetic full-copy proof').decode()))
        evidence=attached['packages'][0]['receipt']['effects']['evidenceRef']
        for node in ('OUT','A'):
            request=self.command_request(source,'complete',nodeId=node);request['evidenceRefs']=[evidence];self.app().request(request)
        current=self.current(source);graph=current['graph'];key=json.dumps([graph['identitySpace'],graph['id'],'R1'],separators=(',',':'))
        self.app().request(self.req('layout_edit',targetPackageId=source,expectedPackageRevision=current['package']['revision'],
            expectedLayoutRevision=0,commands=[{'type':'set_positions','graphKey':key,'positions':{'R1':{'x':12,'y':23},'A':{'x':34,'y':45},'__canon__A':{'x':56,'y':67}}}]))
        before=self.current(source);request=self.copy_request(source);preview=self.app().request(request,preflight=True)
        self.assertEqual(preview['effects']['capture']['entityIds'],sorted(M.entities(before['graph'])))
        ident,mapping=self.copied(request);copied=self.current(ident);aid=mapping['entity']['A']
        self.assertEqual(copied['package']['role'],'copy');self.assertTrue(copied['completion'][aid]['complete'])
        self.assertEqual(copied['graph']['events'],[]);self.assertEqual(before,self.current(source))
        self.assertEqual(M.entities(copied['graph'])[aid]['result'],M.entities(before['graph'])['A']['result'])
        self.assertEqual(copied['plan']['steps'][0]['ref']['nodeId'],aid)
        self.assertEqual(copied['plan']['steps'][0]['ref']['packageId'],ident)
        positions=next(iter(copied['layouts']['layouts'].values()))['positions']
        self.assertEqual(positions[aid],{'x':34,'y':45});self.assertEqual(positions['__canon__'+aid],{'x':56,'y':67})
        history=self.app().history(ident)
        self.assertEqual(sum(e['event']['type']=='action_executed' for e in history['events']),1)
        self.assertTrue(all(e['inherited'] for e in history['events']))
        self.assertTrue(any(e['displayTargetIds']==[aid] for e in history['events'] if e['event']['type']=='action_executed'))
        self.assertTrue({1,2}<={v['plan']['revision'] for v in history['planVersions'] if v['inherited']})
        row=self.store.read(ident);inventory=self.store.inventory(row)
        self.assertEqual(inventory[evidence['path']],evidence['sha256'])
        self.assertTrue(self.app().request(request)['idempotent'])

    def test_partial_r_external_source_change_stays_reviewable_until_explicit_refresh(self):
        source=self.make_selected(True);request=self.copy_request(source,{'kind':'requirement','id':'R1'})
        ident,mapping=self.copied(request);copy_before=self.current(ident);aid=mapping['entity']['A']
        self.assertNotIn('R2',M.entities(copy_before['graph']))
        record=next(r for r in copy_before['graph']['externalRefs'] if r['target']['nodeId']=='R2')
        self.assertEqual(self.app().resolve(ident,record['target'])['status'],'current')
        self.command(source,'edit',nodeId='R2',changes={'description':'Changed shared source meaning'})
        changed=self.current(ident);self.assertIn(aid,changed['external']['reviewIds'])
        self.assertEqual(changed['graph']['externalRefs'],copy_before['graph']['externalRefs'])
        bad=self.command_request(ident,'review',nodeIds=[aid],observed={i:r for i,r in M.pins(changed['graph'],aid).items()})
        with self.assertRaisesRegex(ValueError,'EXTERNAL_DEPENDENCY_REVIEW_REQUIRED'):self.app().request(bad)
        self.review(source);current_source=self.current(source)
        self.app().request(self.req('external_edit',targetPackageId=ident,expectedPackageRevision=changed['package']['revision'],
            expectedGraphRevision=changed['graph']['revision'],referenceId=record['id'],
            target=P.reference(source,current_source['graph'],'R2'),note='Explicit review of the changed external requirement'))
        self.actual_review(ident);self.assertEqual(self.current(ident)['external']['reviewIds'],[])

    def test_deleted_external_endpoint_is_historical_and_unavailable_is_not_empty(self):
        source=self.make_selected(True);ident,mapping=self.copied(self.copy_request(source,{'kind':'requirement','id':'R1'}))
        record=next(r for r in self.current(ident)['graph']['externalRefs'] if r['target']['nodeId']=='R2')
        before=self.current(source)
        self.app().request(self.req('delete',targetPackageId=source,expectedPackageRevision=before['package']['revision'],
            expectedGraphRevision=before['graph']['revision'],nodeIds=['R2'],note='Synthetic source deletion'))
        result=self.app().resolve(ident,record['target']);self.assertEqual(result['status'],'deleted')
        self.assertEqual(result['node']['id'],'R2')
        limited=self.authority.manage('issue',self.admin,{'permissions':['graph.read','plan.read'],
            'scopes':['packages/'+self.namespace+'/'+ident]})['token']
        result=self.app(limited).resolve(ident,record['target'])
        self.assertEqual(result['status'],'historical-current-unavailable');self.assertIsNone(result['changed'])
        self.assertIn(mapping['entity']['A'],self.app(limited).read(ident,True)['external']['reviewIds'])

    def test_insert_back_keeps_precise_original_boundary_ids_and_never_reexecutes(self):
        source=self.make_selected(True);ident,mapping=self.copied(self.copy_request(source,{'kind':'requirement','id':'R1'}))
        copied=self.current(ident);before=self.current(source)
        request=self.req('insert_copy',sourcePackageId=ident,sourcePin={'revision':copied['package']['revision'],
            'sha256':P.digest(copied['graph'])},targetPackageId=source,expectedPackageRevision=before['package']['revision'],
            expectedGraphRevision=before['graph']['revision'],note='Insert independent instances preserving source references')
        preview=self.app().request(request,preflight=True);new_map=preview['effects']['idMap']
        self.app().request(request);after=self.current(source)
        self.assertEqual(after['graph']['events'][:-1],before['graph']['events'])
        self.assertEqual(after['graph']['events'][-1]['type'],'copy_inserted')
        imported_a=new_map['entity'][mapping['entity']['A']]
        self.assertEqual(M.entities(after['graph'])[imported_a]['status'],'selected')
        refs=[r for r in after['graph']['externalRefs'] if r['localId']==imported_a]
        self.assertTrue(any(r['target']['packageId']==source and r['target']['nodeId']=='R2' for r in refs))
        self.assertEqual(self.app().resolve(source,refs[0]['target'])['status'],'current')
        self.assertEqual(sum(e['type']=='action_executed' for e in after['graph']['events']),0)

    def test_source_bytes_changed_after_inventory_cannot_enter_a_copy(self):
        source=self.create('source-integrity');request=self.copy_request(source);app=self.app();original=app.store.inventory
        def changed(row):
            result=original(row);relative=row['head']['current']['graph']
            path=app.store.package_path(row['path'])/relative;path.write_bytes(path.read_bytes()+b' ')
            return result
        app.store.inventory=changed
        with self.assertRaisesRegex(ValueError,'COPY_SOURCE_BYTES_CHANGED'):app.request(request)
        self.assertFalse((self.root/request['path']/'package.json').exists())

    def test_canon_copy_has_no_fake_root_and_plan_cannot_place_a_ready_template(self):
        source=self.create('canon-source')
        self.command(source,'add',entity={'id':'C','kind':'canon','title':'Canon','arguments':[{'id':'a','text':'Pattern','polarity':'for',
            'strength':'soft','condition':{'id':'c','kind':'context','text':'Illustrative context'}}]})
        ident,_=self.copied(self.copy_request(source,{'kind':'canon','id':'C'}))
        graph=self.current(ident)['graph'];self.assertIsNone(graph['rootRequirementId']);self.assertEqual(graph['nodes'],[])
        self.assertEqual(self.current(ident)['detached'],[])
        before=self.current(ident)
        self.app().request(self.req('delete',targetPackageId=ident,expectedPackageRevision=before['package']['revision'],
            expectedGraphRevision=graph['revision'],nodeIds=[graph['fragmentFocus']['id']],note='Explicit removal of the last Canon focus'))
        empty=self.current(ident)['graph'];self.assertEqual(empty['nodes']+empty['objects'],[])
        self.assertEqual(empty['events'][-1]['removedFragmentFocus'],graph['fragmentFocus'])
        ready=self.create('paper','ready');request=self.placement(source,ready)
        with self.assertRaisesRegex(ValueError,'PLAN_REFERENCE_MISMATCH'):self.app().request(request)

if __name__=='__main__':unittest.main()
