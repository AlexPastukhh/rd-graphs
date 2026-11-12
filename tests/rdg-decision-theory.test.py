#!/usr/bin/env python3
"""Two-section theory, Decision/Action targets, atomic authoring and legacy reads."""
import copy
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
F=SourceFileLoader('theory_service_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
M=SourceFileLoader('theory_decision_model',str(ROOT/'tools/rdg-decision-model.py')).load_module()
MD=SourceFileLoader('theory_markdown',str(ROOT/'tools/rdg-structured-markdown.py')).load_module()

class Theory(unittest.TestCase):
    setUp=F.PortableApplication.setUp
    app=F.PortableApplication.app
    config=F.PortableApplication.config
    current=F.PortableApplication.current
    req=F.PortableApplication.req
    command_request=F.PortableApplication.command_request
    command=F.PortableApplication.command
    sources=F.PortableApplication.sources
    review=F.PortableApplication.review

    def fixture(self):
        app=self.app();req=app.schema('create',core_model='rdg-decision-v1',role='working')['request']
        req.update(path='working/theory-test',title='Theory test',scope='Synthetic',rootReason='Synthetic authoring acceptance')
        pid=app.request(req)['packages'][0]['packageId']
        self.command(pid,'add',entity={'id':'D','kind':'decision','title':'Candidate','description':'Concrete mechanism'},initialRelations=[{'id':'RD','type':'DRIVES','from':'R1','to':'D'}])
        self.command(pid,'add',entity={'id':'A','kind':'action','title':'Whole task','description':'Inputs, method, output and acceptance in one task','actionType':'task','lowLevel':False,'targetIds':[],'groupIds':[]},initialRelations=[{'id':'RA','type':'REQUIRES_ACTION','from':'R1','to':'A'}])
        return pid

    def add_theory(self,pid,target='D',ident='K',**fields):
        self.command(pid,'add',entity={'id':ident,'kind':'canon','title':'Theory','description':'Source','guidance':'General',**fields},initialRelations=[{'id':ident+'-LINK','type':'CANON_FOR','from':ident,'to':target}])
        return next(n for n in self.current(pid)['graph']['objects'] if n['id']==ident)

    def test_schema_and_theory_for_decision_and_action(self):
        pid=self.fixture();app=self.app()
        for target in ('D','A'):
            req=app.schema('core',pid,node_id=target,command='add',entity_kind='canon')['request']
            self.assertEqual(set(req['data']['entity'])&{'guidance','canons','knownErrors'},{'guidance','canons'})
            row=self.add_theory(pid,target,'K-'+target,canons='Good at bounded load; bad without a bound; known mistake: assuming capacity')
            self.assertNotIn('knownErrors',row)
            self.assertIn('known mistake',row['canons'])
        root=app.schema('core',pid,node_id='R1',command='add',entity_kind='canon')['request']
        self.assertEqual(root['data']['initialRelations'],[])

    def test_requirement_initial_link_and_later_link_are_rejected_atomically(self):
        pid=self.fixture();before=self.current(pid)['graph']
        with self.assertRaisesRegex(ValueError,'THEORY_TARGET_DECISION_OR_ACTION'):
            self.add_theory(pid,'R1')
        self.assertEqual(self.current(pid)['graph'],before)
        self.add_theory(pid);before=self.current(pid)['graph']
        req=self.command_request(pid,'link',relation={'id':'BAD','type':'CANON_FOR','from':'K','to':'R1'})
        for preflight in (True,False):
            with self.assertRaisesRegex(ValueError,'THEORY_TARGET_DECISION_OR_ACTION'):self.app().request(req,preflight=preflight)
        self.assertEqual(self.current(pid)['graph'],before)

    def test_new_error_cases_use_canons_and_separate_list_is_rejected(self):
        pid=self.fixture();before=self.current(pid)['graph']
        errors=[{'id':'e','title':'Assuming capacity','description':'Measure actual load'}]
        with self.assertRaisesRegex(ValueError,'KNOWN_ERRORS_USE_CANONS'):self.add_theory(pid,knownErrors=errors)
        self.assertEqual(self.current(pid)['graph'],before)
        self.add_theory(pid,canons='Known mistake: assuming capacity. Measure actual load.')
        before=self.current(pid)['graph']
        with self.assertRaisesRegex(ValueError,'KNOWN_ERRORS_USE_CANONS'):self.command(pid,'edit',nodeId='K',changes={'knownErrors':errors},cosmetic=False)
        self.assertEqual(self.current(pid)['graph'],before)

    def test_late_invalid_batch_does_not_keep_prefix_edit(self):
        pid=self.fixture();self.add_theory(pid);app=self.app();before=self.current(pid)['graph']
        req=app.schema('batch',pid)['request'];req['note']='Synthetic late failure'
        req['steps']=[{'alias':'rename','op':'core','command':'edit','data':{'nodeId':'K','changes':{'title':'Renamed'},'cosmetic':True}}, {'alias':'bad','op':'core','command':'link','data':{'relation':{'id':'BAD','type':'CANON_FOR','from':'K','to':'R1'}}}]
        with self.assertRaisesRegex(ValueError,'THEORY_TARGET_DECISION_OR_ACTION'):app.request(req,preflight=True)
        with self.assertRaisesRegex(ValueError,'THEORY_TARGET_DECISION_OR_ACTION'):app.request(req)
        self.assertEqual(self.current(pid)['graph'],before)

    def test_import_cannot_reintroduce_forbidden_theory_shape(self):
        pid=self.fixture();app=self.app();g=copy.deepcopy(self.current(pid)['graph'])
        g['events']=[];g['externalActions']=[]
        for n in g['nodes']+g['objects']:
            n.pop('review',None)
            if n['kind'] in ('requirement','decision','action'):n['result']={'state':'open','truth':'unknown'}
        g['objects'].append({'id':'K','kind':'canon','title':'Imported theory','description':'','revision':1,'guidance':'General'})
        for target,errors,code in [('R1',None,'THEORY_TARGET_DECISION_OR_ACTION'),('D',[{'id':'e','title':'Legacy error','description':''}],'KNOWN_ERRORS_USE_CANONS')]:
            bad=copy.deepcopy(g);bad['edges'].append({'id':'KL','type':'CANON_FOR','from':'K','to':target})
            if errors:bad['objects'][-1]['knownErrors']=errors
            req=app.schema('create',core_model='rdg-decision-v1',role='working')['request'];req.update(path='working/bad-import',title='Bad import',scope='Synthetic',rootReason='Test invalid import',graph=bad)
            with self.assertRaisesRegex(ValueError,code):app.request(req,preflight=True)

    def test_canons_change_invalidates_the_decision_and_keeps_history(self):
        pid=self.fixture();self.add_theory(pid,canons='Original conditions');before=self.current(pid)['graph']
        self.command(pid,'edit',nodeId='K',changes={'canons':'Good under bounded load; bad under bursts. Known mistake: ignoring recovery.'},cosmetic=False)
        g=self.current(pid)['graph'];self.assertTrue(M.entities(g)['D']['review']['required']);self.assertNotEqual(g['events'],before['events'])
        self.assertEqual(M.entities(before)['K']['canons'],'Original conditions')
        self.assertIn('Known mistake',M.entities(g)['K']['canons'])

    def test_copy_uses_independent_theory_identity_and_source_is_unchanged(self):
        pid=self.fixture();self.add_theory(pid,canons='Good, borderline and bad cases, including known mistakes');app=self.app();before=self.current(pid)['graph']
        req=app.schema('copy',pid)['request'];req['path']='copies/theory';req['note']='Copy valid theory'
        result=app.request(req);cid=result['packages'][0]['packageId'];g=self.current(cid)['graph'];theory=next(n for n in g['objects'] if n['kind']=='canon')
        self.assertNotEqual(theory['id'],'K');self.assertEqual(theory['canons'],M.entities(before)['K']['canons'])
        self.command(cid,'edit',nodeId=theory['id'],changes={'canons':'Changed only in copy'},cosmetic=False)
        self.assertEqual(self.current(pid)['graph'],before)

    def test_legacy_is_readable_without_automatic_rewrite(self):
        pid=self.fixture();self.add_theory(pid);g=copy.deepcopy(self.current(pid)['graph']);n=M.entities(g)['K'];n['knownErrors']=[{'id':'old','title':'Old known mistake','description':'Retain this explanation'}]
        g['edges'].append({'id':'OLD-R','type':'CANON_FOR','from':'K','to':'R1'})
        before=copy.deepcopy(g);M.validate(g);M.validate_authored_theory(g,g)
        markdown='\n'.join(MD.fields(n))
        self.assertIn('Каноны',markdown);self.assertIn('Old known mistake',markdown);self.assertIn('Retain this explanation',markdown);self.assertNotIn('**Известные ошибки**',markdown)
        self.assertEqual(g,before)
        with self.assertRaisesRegex(ValueError,'THEORY_TARGET_DECISION_OR_ACTION'):M.validate_authored_theory(g)

if __name__=='__main__':unittest.main()
