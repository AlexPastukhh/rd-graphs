#!/usr/bin/env python3
"""T5: ordinary Action + atomic Plan placement on disposable owners."""
import copy,json,unittest,uuid
from pathlib import Path
from importlib.machinery import SourceFileLoader
ROOT=Path(__file__).resolve().parents[1]
Q=SourceFileLoader('meta_action_fixture',str(ROOT/'tests/rdg-question-first-slice.test.py')).load_module()
class PlanningMetaActions(unittest.TestCase):
    setUp=Q.QuestionFirstSlice.setUp
    config=Q.QuestionFirstSlice.config
    app=Q.QuestionFirstSlice.app
    req=Q.QuestionFirstSlice.req
    current=Q.QuestionFirstSlice.current
    sources=Q.QuestionFirstSlice.sources
    command=Q.QuestionFirstSlice.command
    command_request=Q.QuestionFirstSlice.command_request
    finding_package=Q.QuestionFirstSlice.finding_package
    setup_question=Q.QuestionFirstSlice.setup_question
    def form(self,pid,refs=None):
        r=self.app().schema('plan_action',pid)['request'];r['note']='Synthetic explicit planning work'
        r['entity'].update(title='Investigate the process',description='Read and analyse',resultCondition='Record useful conclusions',subjectRefs=refs or [],estimates={'time':{'minSeconds':0,'maxSeconds':120}})
        return r
    def write(self,r):
        app=self.app();before=self.sources();pre=app.call({'method':'preflight','request':r});self.assertEqual(before,self.sources())
        result=app.call({'method':'apply','request':r,'expectedInputBinding':pre['inputBinding']});self.assertTrue(result['published'])
        self.assertTrue(self.app().call({'method':'apply','request':r})['idempotent']);return result['packages'][0]['receipt']['effects']
    def test_atomic_create_receipt_restart_properties_and_no_subject_effects(self):
        pid,d,q=self.setup_question();app=self.app();before=app.read(pid);refs=[app.model.reference(pid,before['graph'],i) for i in (d,q,'FINDING','FACT')]+[app.model.scope_reference(pid,before['graph'])]
        r=self.form(pid,refs);effects=self.write(r);a=effects['actionId'];step=effects['placementId'];row=self.app().read(pid,True)
        self.assertEqual(row['plan']['steps'][0]['id'],step);self.assertEqual(row['plan']['steps'][0]['ref']['nodeId'],a)
        action=next(n for n in row['graph']['externalActions'] if n['id']==a);self.assertEqual(action['resultCondition'],'Record useful conclusions');self.assertEqual(action['result']['state'],'open')
        self.assertFalse(any(n['id']==a for n in row['graph']['nodes']));self.assertEqual(len(row['actionSubjects'][a]),5)
        for i in (d,q,'FINDING','FACT'):self.assertEqual(app.kernel.entities(before['graph'])[i],app.kernel.entities(row['graph'])[i])
        self.assertNotIn(a,{n['id'] for n in row['view']['entities']});self.assertNotIn(a,{n['entityId'] for n in row['view']['visual']['nodes']})
        compact=self.app().call({'method':'read','packageId':pid,'detail':'item','nodeId':a,'include':['subjects']});self.assertEqual(len(compact['data']['subjects']['items']),5)
        self.assertEqual(effects['graphRevision'],row['graph']['revision']);self.assertEqual(effects['planRevision'],row['plan']['revision'])
    def test_bad_refs_bad_placement_cas_and_late_batch_error_write_nothing(self):
        pid,d,q=self.setup_question();app=self.app();g=app.read(pid)['graph'];ref=app.model.reference(pid,g,q)
        for change in ('missing','identity','version','placement'):
            r=self.form(pid,[copy.deepcopy(ref)])
            if change=='missing':r['entity']['subjectRefs'][0]['nodeId']='MISSING'
            if change=='identity':r['entity']['subjectRefs'][0]['identitySpace']=str(uuid.uuid4())
            if change=='version':r['entity']['subjectRefs'][0]['revision']+=1
            if change=='placement':r['placement']={'afterStepId':'MISSING'}
            before=self.sources()
            with self.assertRaises(ValueError):app.request(r)
            self.assertEqual(before,self.sources())
        r=self.form(pid);pre=app.call({'method':'preflight','request':r});self.command(pid,'edit',nodeId=d,changes={'description':'Changed concurrently'},cosmetic=False)
        before=self.sources()
        with self.assertRaises(ValueError):app.call({'method':'apply','request':r,'expectedInputBinding':pre['inputBinding']})
        self.assertEqual(before,self.sources())
        b=app.schema('batch',pid)['request'];b['note']='Late placement failure';b['steps']=[{'alias':'p','op':'plan_create','title':'Plan'},{'alias':'meta','op':'plan_action','entity':{'title':'Never half-created','description':''},'placement':{'afterStepId':'BAD'}}]
        with self.assertRaises(ValueError):app.request(b)
        self.assertEqual(before,self.sources())
    def test_batch_alias_subjects_and_preacceptance_recovery(self):
        pid,d,q=self.setup_question();app=self.app();r=app.schema('batch',pid)['request'];r['note']='Shared batch coordinator'
        r['steps']=[{'alias':'note','op':'core','command':'add','data':{'entity':{'kind':'info','title':'New subject','description':'','value':'An observation'}}},{'alias':'p','op':'plan_create','title':'Plan'},{'alias':'meta','op':'plan_action','entity':{'title':'Read the new subject','description':'','subjectRefs':[{'$entityRef':'note'}]}}]
        pre=app.call({'method':'preflight','request':r});before=app.read(pid)['graph']
        def fail(point):
            if point=='staged':raise RuntimeError('T5 staged interruption')
        with self.assertRaisesRegex(RuntimeError,'T5 staged'):app.request(r,failpoint=fail)
        self.assertEqual(app.read(pid)['graph'],before)
        self.write(r);row=self.app().read(pid,True);aid=pre['effects']['aliasIds']['meta'];self.assertEqual(row['plan']['steps'][0]['ref']['nodeId'],aid)
        self.assertEqual(row['actionSubjects'][aid][0]['status'],'current')
    def test_edit_delete_subject_unplace_and_ordinary_completion(self):
        pid,d,q=self.setup_question();app=self.app();r=self.form(pid,[app.model.reference(pid,app.read(pid)['graph'],q)]);e=self.write(r);aid=e['actionId']
        self.command(pid,'edit',nodeId=aid,changes={'description':'Investigate more','resultCondition':'A useful answer'},cosmetic=False)
        # A preserved reference survives a deleted subject and ordinary edits.
        delete=app.schema('delete',pid,node_id=q)['request'];delete['note']='Delete only question';self.write(delete)
        row=app.read(pid,True);self.assertNotEqual(row['actionSubjects'][aid][0]['status'],'current');self.command(pid,'edit',nodeId=aid,changes={'description':'Keep recorded subject'},cosmetic=False)
        # Ordinary review and result evidence; no special executor or status.
        review=app.schema('core',pid,node_id=aid,command='review')['request'];review['note']='Review changed task';review['data'].update(nodeId=aid,basis='Confirmed task definition');app.request(review)
        complete=app.schema('core',pid,node_id=aid,command='complete')['request'];complete['note']='Actual work done';complete['data'].update(nodeId=aid,basis='Investigation complete',evidenceIds=['FACT']);app.request(complete)
        row=app.read(pid,True);self.assertEqual(app.kernel.entities(row['graph'])[aid]['result']['state'],'confirmed');self.assertEqual(app.kernel.entities(row['graph'])[d]['selectionState'],'discovered');self.assertEqual(app.kernel.entities(row['graph'])['FINDING']['disposition']['code'],'unresolved')
        unplace=app.schema('unplace',pid)['request'];unplace.update(stepId=e['placementId'],note='Remove placement only');self.write(unplace);self.assertIn(aid,app.kernel.entities(app.read(pid)['graph']))
    def test_lens_and_step_refs_profile_guards_and_local_copy_binding(self):
        pid,d,q=self.setup_question();app=self.app();create=app.schema('create',core_model='rdg-decision-v1',role='lens')['request'];create.update(path='lenses/t5-synthetic',role='lens',lensKey='work',graph=json.loads((ROOT/'tools/rdg-agent-lenses/work-decision.json').read_text()),rootReason='Synthetic lens')
        lens=app.request(create)['packages'][0]['packageId'];lg=app.read(lens)['graph'];refs=[app.model.scope_reference(lens,lg,'lens'),app.model.reference(lens,lg,lg['rootRequirementId']),app.model.reference(pid,app.read(pid)['graph'],q)]
        e=self.write(self.form(pid,refs));row=app.read(pid,True);self.assertEqual([x['status'] for x in row['actionSubjects'][e['actionId']]],['current']*3)
        req=app.schema('copy',pid)['request'];req.update(path='copies/t5',note='Independent local subject binding');copied=app.request(req)['packages'][0]['packageId'];c=app.read(copied,True);a=next(n for n in c['graph']['externalActions'] if n.get('subjectRefs'));self.assertEqual([x['status'] for x in c['actionSubjects'][a['id']][:2]],['current','current']);self.assertEqual(a['subjectRefs'][1],refs[1]);local=c['actionSubjects'][a['id']][-1];self.assertEqual(local['packageId'],copied);self.assertNotEqual(local['node']['id'],q)
        delete=app.schema('delete',copied,node_id=local['node']['id'])['request'];delete['note']='Delete copied local subject only';self.write(delete);self.assertNotEqual(app.read(copied)['actionSubjects'][a['id']][-1]['status'],'current')
        other,_,_=self.setup_question();r=self.form(pid,[app.model.reference(other,app.read(other)['graph'],'R1')]);before=self.sources()
        with self.assertRaisesRegex(ValueError,'FOREIGN_PROCESS'):app.request(r)
        self.assertEqual(before,self.sources())
    def test_every_local_subject_scope_and_legacy_task_remain_compatible(self):
        pid,d,q=self.setup_question();app=self.app()
        for kind,ident,extra in [('action','OLD-TASK',{'actionType':'task','lowLevel':False,'targetIds':[],'groupIds':[]}),('canon','THEORY',{'guidance':'Consult as needed'}),('info','NOTE',{'value':'An existing note'})]:
            self.command(pid,'add',entity={'id':ident,'kind':kind,'title':ident,'description':'',**extra},**({'location':'external'} if kind=='action' else {}))
        self.command(pid,'work_graph',workGraph={'id':'AREA','title':'Test area','rootIds':['R1'],'memberIds':['R1',d]})
        g=app.read(pid)['graph'];old=copy.deepcopy(app.kernel.entities(g)['OLD-TASK']);refs=[app.model.reference(pid,g,i) for i in ('R1',d,q,'FINDING','FACT','OLD-TASK','THEORY','NOTE')]+[app.model.scope_reference(pid,g),app.model.scope_reference(pid,g,'workGraph','AREA')]
        e=self.write(self.form(pid,refs));row=app.read(pid,True);self.assertEqual(len(row['actionSubjects'][e['actionId']]),10);self.assertTrue(all(r['status']=='current' for r in row['actionSubjects'][e['actionId']]));self.assertEqual(app.kernel.entities(row['graph'])['OLD-TASK'],old)
        delete=app.schema('delete',pid,node_id=e['actionId'])['request'];delete['note']='Explicitly delete Action';self.write(delete);row=app.read(pid,True);self.assertNotIn(e['actionId'],app.kernel.entities(row['graph']));self.assertFalse(any(s['id']==e['placementId'] for s in row['plan']['steps']))
    def test_accepted_interruption_recovery_publishes_action_and_placement_once(self):
        pid,d,q=self.setup_question();app=self.app();r=self.form(pid);pre=app.call({'method':'preflight','request':r})
        def fail(point):
            if point=='head:1':raise RuntimeError('T5 accepted head interruption')
        with self.assertRaisesRegex(RuntimeError,'T5 accepted'):app.request(r,failpoint=fail)
        self.assertTrue(self.app().recover(r['transactionId'])['published']);row=self.app().read(pid,True);aid=pre['effects']['actionId'];self.assertEqual(sum(n['id']==aid for n in row['graph']['externalActions']),1);self.assertEqual(sum(s['ref']['nodeId']==aid for s in row['plan']['steps']),1);self.assertTrue(self.app().request(r)['idempotent'])
if __name__=='__main__':unittest.main()
