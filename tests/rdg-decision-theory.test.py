#!/usr/bin/env python3
"""B02A: common writer, legacy read, semantic observations and independent copies."""
import copy
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('theory_fixture',str(ROOT/'tests/rdg-questions-estimates.test.py')).load_module()

class DecisionTheory(unittest.TestCase):
    setUp=T.QuestionsEstimates.setUp
    config=T.QuestionsEstimates.config
    app=T.QuestionsEstimates.app
    req=T.QuestionsEstimates.req
    current=T.QuestionsEstimates.current
    sources=T.QuestionsEstimates.sources
    command=T.QuestionsEstimates.command
    command_request=T.QuestionsEstimates.command_request
    finding_package=T.QuestionsEstimates.finding_package
    form=T.QuestionsEstimates.form
    apply_checked=T.QuestionsEstimates.apply_checked

    def seed(self,**fields):
        pid,d=self.finding_package()
        self.command(pid,'add',entity={'id':'THEORY','kind':'canon','title':'Theory','description':'Legacy description','guidance':'Legacy unrestricted text',**fields},initialRelations=[{'id':'THEORY-LINK','type':'CANON_FOR','from':'THEORY','to':d}])
        return pid,d

    def node(self,pid,nid='THEORY'):
        app=self.app();return app.kernel.entities(app.read(pid)['graph'])[nid]

    def test_legacy_read_is_byte_preserving_and_schema_discovers_all_sections(self):
        pid,d=self.seed();before=self.sources();original=self.node(pid)
        app=self.app()
        for detail in ('full','item'):
            app.call({'method':'read','packageId':pid,'detail':detail,**({'nodeId':'THEORY'} if detail=='item' else {})})
        self.assertEqual(self.sources(),before)
        self.assertNotIn('canons',original);self.assertNotIn('knownErrors',original)
        schema=app.call({'method':'schema','op':'core','packageId':pid,'command':'add','nodeId':d,'entityKind':'canon'})
        self.assertEqual(set(schema['request']['data']['entity'])&{'guidance','canons','knownErrors'},{'guidance','canons','knownErrors'})
        self.assertNotIn('data.entity.guidance',schema['requiredInput'])
        self.assertIn('decisionTheory',schema['inputChoices'])
        req=self.command_request(pid,'edit',nodeId='THEORY',changes={'canons':'Useful at low load; risky at high load; borderline at bursts','knownErrors':[{'id':'one','title':'Assuming capacity','description':''}]},cosmetic=False)
        self.apply_checked(req)
        node=self.node(pid);self.assertEqual(node['guidance'],original['guidance']);self.assertEqual(node['description'],original['description'])
        # An old client updates only guidance; optional fields are never lost.
        self.command(pid,'edit',nodeId='THEORY',changes={'guidance':'Updated by a legacy client'},cosmetic=False)
        self.assertEqual(self.node(pid)['knownErrors'],node['knownErrors']);self.assertEqual(self.node(pid)['canons'],node['canons'])
        result=app.call({'method':'read','packageId':pid,'nodeId':d,'detail':'item','include':['canon']})
        self.assertEqual(result['data']['canon']['items'][0],self.node(pid))

    def test_partial_sections_validation_and_explicit_clear(self):
        pid,d=self.seed()
        for i,content in enumerate([{'guidance':'','canons':'Use with a bound'}, {'guidance':'','knownErrors':[{'id':'e','title':'Overconfidence','description':''}]}]):
            req=self.app().schema('core',pid,node_id=d,command='add',entity_kind='canon')['request'];req['note']='Single section allowed';req['data']['entity'].update(title='Partial',**content);self.apply_checked(req)
        for bad in [ {'guidance':''}, {'guidance':None}, {'canons':None}, {'canons':2}, {'knownErrors':{}}, {'knownErrors':None}, {'knownErrors':[{'id':'a','title':' ','description':''}]}, {'knownErrors':[{'id':'a','title':'Error','description':None}]}, {'knownErrors':[{'id':'a','title':'Error','description':'','extra':True}]}, {'knownErrors':[{'id':'a','title':'A','description':''},{'id':'a','title':'B','description':''}]} ]:
            with self.subTest(bad=bad):
                req=self.command_request(pid,'edit',nodeId='THEORY',changes=bad,cosmetic=False);before=self.sources()
                with self.assertRaisesRegex(ValueError,'CANON_|THEORY_'):self.app().request(req)
                self.assertEqual(self.sources(),before)
        self.command(pid,'edit',nodeId='THEORY',changes={'canons':'Some scope','knownErrors':[{'id':'e','title':'Mistake','description':'Comment'}]},cosmetic=False)
        self.command(pid,'edit',nodeId='THEORY',changes={'canons':'','knownErrors':[]},cosmetic=False)
        self.assertEqual(self.node(pid)['knownErrors'],[])
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'COSMETIC'):self.command(pid,'edit',nodeId='THEORY',changes={'canons':'Changed'},cosmetic=True)
        self.assertEqual(self.sources(),before)

    def test_each_section_and_error_order_trigger_review_and_record_before_after(self):
        pid,d=self.seed();app=self.app()
        rows=[{'id':'a','title':'A','description':''},{'id':'b','title':'B','description':'Explanation'}]
        for changes in [{'canons':'Bounded use'}, {'guidance':'New general'}, {'knownErrors':rows}, {'knownErrors':list(reversed(rows))}, {'knownErrors':[dict(rows[0],description='More detail')]}, {'knownErrors':[]}]:
            req=self.form(pid,'review',d);self.apply_checked(req)
            previous=self.node(pid)
            req=self.command_request(pid,'edit',nodeId='THEORY',changes=changes,cosmetic=False);self.apply_checked(req)
            graph=app.read(pid)['graph'];self.assertTrue(app.kernel.entities(graph)[d]['review']['required'])
            event=next(e for e in reversed(graph['events']) if e.get('historyDetail',{}).get('command')=='edit')
            for edit in event['historyDetail']['edits']:
                self.assertEqual(edit['before'],previous.get(edit['field']));self.assertEqual(edit['after'],changes[edit['field']])
            history=app.history(pid)['events'];view=next(r['historyView'] for r in history if r['event']['id']==event['id'])
            self.assertEqual(view['level'],'semantic')
            self.assertEqual(app.kernel.entities(graph)[d]['selectionState'],'discovered')
            self.assertEqual(app.kernel.entities(graph)['FINDING']['disposition']['code'],'unresolved')

    def test_batch_late_error_cas_retry_and_restart(self):
        pid,d=self.seed();app=self.app();req=app.schema('batch',pid)['request'];req['note']='Theory batch'
        req['steps']=[{'alias':'theory','op':'core','command':'add','data':{'entity':{'kind':'canon','title':'Batch theory','description':'','guidance':'','canons':'Mixed suitability','knownErrors':[]},'initialRelations':[]}}, {'alias':'edit','op':'core','command':'edit','data':{'nodeId':{'$alias':'theory'},'changes':{'knownErrors':[{'id':'one','title':'Do not assume','description':''}]},'cosmetic':False}}]
        invalid=copy.deepcopy(req);invalid['steps'][1]['data']['changes']['knownErrors'][0]['title']='';before=self.sources()
        with self.assertRaisesRegex(ValueError,'THEORY_'):app.request(invalid)
        self.assertEqual(self.sources(),before)
        result=self.apply_checked(req);nid=result['packages'][0]['receipt']['effects']['aliasIds']['theory'];self.assertEqual(self.node(pid,nid)['knownErrors'][0]['id'],'one')
        stale=self.command_request(pid,'edit',nodeId=nid,changes={'canons':'Stale value'},cosmetic=False)
        self.command(pid,'edit',nodeId=nid,changes={'canons':'Actual new value'},cosmetic=False);before=self.sources()
        with self.assertRaisesRegex(ValueError,'CAS|REVISION'):app.request(stale)
        self.assertEqual(self.sources(),before);self.assertEqual(self.node(pid,nid)['canons'],'Actual new value')

    def test_copy_import_capture_apply_and_delete_preserve_independent_data(self):
        app=self.app();pid=app.request(self.req('create',path='working/theory-only',role='working',coreModel='rdg-decision-v1',title='Theory copy',scope='Synthetic',rootReason='No live owners'))['packages'][0]['packageId']
        rows=[{'id':'local','title':'Repeated assumption','description':'A free comment https://example.test/source'}]
        self.command(pid,'add',entity={'id':'THEORY','kind':'canon','title':'Reusable theory','description':'Keep description','guidance':'General','canons':'Mixed conditions','knownErrors':rows},initialRelations=[{'id':'THEORY-R','type':'CANON_FOR','from':'THEORY','to':'R1'}])
        original=copy.deepcopy(app.read(pid)['graph']);copies=[]
        for i in range(2):
            req=app.schema('copy',pid)['request'];req.update(path='copy/theory-'+str(i),focus={'kind':'canon','id':'THEORY'},note='Independent copy');result=self.apply_checked(req);copies.append(result['packages'][0]['packageId'])
        for cid in copies:
            theory=next(n for n in app.read(cid)['graph']['objects'] if n['kind']=='canon');self.assertNotEqual(theory['id'],'THEORY');self.assertEqual(theory['knownErrors'],rows)
        copied=next(n for n in app.read(copies[0])['graph']['objects'] if n['kind']=='canon')
        self.command(copies[0],'edit',nodeId=copied['id'],changes={'knownErrors':[]},cosmetic=False)
        self.assertEqual(app.read(pid)['graph'],original);self.assertEqual(next(n for n in app.read(copies[1])['graph']['objects'] if n['kind']=='canon')['knownErrors'],rows)
        req=app.schema('capture_ready',pid)['request'];req.update(path='ready/theory',note='Capture only paper theory');ready=self.apply_checked(req)['packages'][0]['packageId']
        req=app.schema('apply_ready',pid,source_id=ready)['request'];req.update(mode='ADD_ROOT',note='Create separate theory instance');self.apply_checked(req)
        theories=[n for n in app.read(pid)['graph']['objects'] if n['kind']=='canon'];self.assertEqual(len(theories),2);self.assertTrue(all(n['knownErrors']==rows for n in theories))
        imported=app.request(self.req('create',path='working/theory-import',role='working',coreModel='rdg-decision-v1',title='Imported',rootReason='Explicit isolated import',graph=app.read(ready)['graph']))['packages'][0]['packageId'];self.assertEqual(next(n for n in app.read(imported)['graph']['objects'] if n['kind']=='canon')['knownErrors'],rows)
        req=app.schema('delete',pid,node_id='THEORY')['request'];req['note']='Delete theory only';self.apply_checked(req);self.assertNotIn('THEORY',app.kernel.entities(app.read(pid)['graph']));self.assertTrue(app.history(pid)['events'])

if __name__=='__main__':unittest.main()
