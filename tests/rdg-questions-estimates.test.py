#!/usr/bin/env python3
"""T3/T4 acceptance through the common Application on disposable owners."""
import copy
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[1]
Q=SourceFileLoader('questions_estimates_fixture',str(ROOT/'tests/rdg-question-first-slice.test.py')).load_module()

class QuestionsEstimates(unittest.TestCase):
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

    def form(self,pid,command,nid):
        req=self.app().schema('core',pid,node_id=nid,command=command)['request']
        req['note']='Synthetic T3/T4 acceptance'
        return req

    def apply_checked(self,req,app=None):
        app=app or self.app();before=self.sources()
        preview=app.call({'method':'preflight','request':req})
        self.assertEqual(before,self.sources())
        result=app.call({'method':'apply','request':req,'expectedInputBinding':preview['inputBinding']})
        self.assertTrue(result['published'])
        self.assertTrue(app.call({'method':'apply','request':req})['idempotent'])
        return result

    def test_verified_user_entry_and_ai_quote_cannot_be_forged(self):
        pid,_,qid=self.setup_question()
        user=self.app();user.attribution='user'
        req=self.form(pid,'question_answer',qid)
        req['data'].update(kind='user_answer',text='A direct user answer',sourceRefs=[])
        self.apply_checked(req,user)
        q=self.app().read(pid)['graph']['objects'][-1]
        self.assertEqual(q['answers'][0]['userSource']['mode'],'direct-user-entry')
        req=self.form(pid,'add','R1')
        req['data']={'entity':{'id':'USER-TEXT','kind':'context','title':'Actual user entry','description':'Fixture','value':'Keep both alternatives'}}
        self.apply_checked(req,user)
        self.command(pid,'add',entity={'id':'ASSISTANT-INFO','kind':'info','title':'Related note','description':'Does not author Context','value':'A separate note'},initialRelations=[{'id':'INFO-USER-CONTEXT','type':'INFO_FOR','from':'ASSISTANT-INFO','to':'USER-TEXT'}])
        graph=self.app().read(pid)['graph'];ref=self.app().model.reference(pid,graph,'USER-TEXT')
        req=self.form(pid,'question_answer',qid)
        req['data'].update(kind='user_answer',text='Keep both alternatives',sourceRefs=[ref])
        self.apply_checked(req)
        q=self.app().kernel.entities(self.app().read(pid)['graph'])[qid]
        self.assertEqual(q['answers'][-1]['recordedBy'],'assistant')
        self.assertEqual(q['answers'][-1]['userSource']['mode'],'user-context')
        for text,extra in [('Not actually said',{}),('Keep both alternatives',{'recordedBy':'user'})]:
            req=self.form(pid,'question_answer',qid)
            graph=self.app().read(pid)['graph']
            req['data'].update(kind='user_answer',text=text,sourceRefs=[self.app().model.reference(pid,graph,'USER-TEXT')],**extra)
            before=self.sources()
            with self.assertRaisesRegex(ValueError,'QUESTION_'):self.app().request(req)
            self.assertEqual(before,self.sources())

        self.command(pid,'edit',nodeId='USER-TEXT',changes={'value':'An assistant invented answer'},cosmetic=False)
        req=self.form(pid,'add','R1');req['data']={'entity':{'id':'USER-INFO','kind':'info','title':'User linked a note','description':'Does not author the Context value','value':'Unrelated note'},'initialRelations':[{'id':'USER-INFO-REL','type':'INFO_FOR','from':'USER-INFO','to':'USER-TEXT'}]};self.apply_checked(req,user)
        graph=self.app().read(pid)['graph'];req=self.form(pid,'question_answer',qid)
        req['data'].update(kind='user_answer',text='An assistant invented answer',sourceRefs=[self.app().model.reference(pid,graph,'USER-TEXT')])
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'USER_SOURCE_REQUIRED'):self.app().request(req)
        self.assertEqual(before,self.sources())

    def test_batch_questions_answers_assessment_estimates_and_late_failure(self):
        pid,_,_=self.setup_question();app=self.app()
        req=app.schema('batch',pid)['request'];req['note']='One atomic authoring intention'
        req['steps']=[
            {'alias':'q','op':'core','command':'add','data':{'entity':{'kind':'question','title':'What is enough?','description':'','impact':'Changes choice','answerCondition':'A verified observation','relatedRefs':[]}}},
            {'alias':'answer','op':'core','command':'question_answer','data':{'nodeId':{'$alias':'q'},'kind':'hypothesis','text':'Maybe 20','sourceRefs':[]}},
            {'alias':'assessment','op':'core','command':'question_assess','data':{'nodeId':{'$alias':'q'},'answerIds':[{'$alias':'answer'}],'sufficient':False,'basis':'Still a hypothesis'}},
            {'alias':'a','op':'core','command':'add','data':{'entity':{'kind':'action','title':'Measure','description':'','actionType':'task','lowLevel':False,'targetIds':[],'groupIds':[],'estimates':{'time':{'minSeconds':0,'maxSeconds':60}}},'location':'external'}},
            {'alias':'linkq','op':'core','command':'edit','data':{'nodeId':{'$alias':'q'},'changes':{'relatedRefs':[{'$entityRef':'a'}]},'cosmetic':False}}
        ]
        invalid=copy.deepcopy(req);invalid['steps'][-1]['data']['changes']={'answers':[]}
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'EDIT_FIELDS'):app.request(invalid)
        self.assertEqual(before,self.sources())
        result=self.apply_checked(req)
        effects=result['packages'][0]['receipt']['effects'];ids=effects['aliasIds']
        graph=self.app().read(pid)['graph'];q=app.kernel.entities(graph)[ids['q']]
        self.assertEqual(q['answers'][0]['id'],ids['answer'])
        self.assertFalse(q['assessment']['sufficient'])
        self.assertEqual(q['relatedRefs'][0]['nodeId'],ids['a'])
        self.assertNotIn(q['id'],[n['id'] for n in graph['nodes']])
        self.assertEqual(graph,self.app().read(pid)['graph'])

    def test_copy_twice_preserves_history_remaps_ids_and_shared_question_survives_delete(self):
        pid,decision,qid=self.setup_question()
        req=self.form(pid,'question_answer',qid);req['data'].update(text='First hypothesis')
        self.apply_checked(req)
        q=self.app().kernel.entities(self.app().read(pid)['graph'])[qid];a=q['answers'][0]
        req=self.form(pid,'question_assess',qid);req['data'].update(answerIds=[a['id']],sufficient=True,basis='Initial assessment')
        self.apply_checked(req)
        req=self.form(pid,'question_answer',qid);req['data']={'nodeId':qid,'action':'edit','answerId':a['id'],'expectedAnswerEventId':a['eventId'],'kind':'hypothesis','text':'Corrected hypothesis','sourceRefs':[]}
        self.apply_checked(req)
        old_answer=a['id']
        for index in range(2):
            req=self.app().schema('copy',pid,source_id=pid)['request'];req.update(path='copy/questions-'+str(index),note='Preserve canonical evidence')
            result=self.apply_checked(req);pid=result['packages'][0]['packageId']
            graph=self.app().read(pid)['graph'];q=next(n for n in graph['objects'] if n['kind']=='question')
            self.assertNotEqual(q['id'],qid);self.assertNotEqual(q['answers'][0]['id'],old_answer)
            self.assertEqual(q['answerHistory'][0]['previous']['id'],q['answers'][0]['id'])
            self.assertEqual(q['assessment']['answerIds'],[q['answers'][0]['id']])
            self.assertTrue(q['assessmentReviewRequired'])
            self.assertTrue(all(self.app().kernel.for_graph(graph).QUESTIONS.reference_id(graph,r,self.app().kernel.for_graph(graph),q) in self.app().kernel.entities(graph) for r in q['relatedRefs']))
            old_answer=q['answers'][0]['id'];qid=q['id']
        finding=next(n for n in graph['objects'] if n['kind']=='finding')
        req=self.app().schema('delete',pid,node_id=finding['id'])['request'];req['note']='Remove subject, retain shared Question'
        self.apply_checked(req)
        q=self.app().kernel.entities(self.app().read(pid)['graph'])[qid]
        self.assertTrue(any(r['mode']=='historical' for r in q['relatedRefs']))
        self.assertEqual(q['answers'][0]['text'],'Corrected hypothesis')
        req=self.command_request(pid,'edit',nodeId=qid,changes={'title':'Updated without losing recorded sources','relatedRefs':copy.deepcopy(q['relatedRefs']),'sourceRefs':copy.deepcopy(q['sourceRefs'])},cosmetic=False);self.apply_checked(req)
        current=self.app().kernel.entities(self.app().read(pid)['graph'])[qid];self.assertEqual(current['relatedRefs'],q['relatedRefs'])

    def test_explicit_legacy_migration_separates_equal_local_ids_and_is_retryable(self):
        pid,decision=self.finding_package();app=self.app();legacy=app.read(pid)['graph']
        row={'id':'same-local-id','question':'Which scope?','impact':'Changes scope','blocking':'partially-blocking','scope':'Unbuilt part','closeCondition':'Explicit bounds'}
        for nid in (decision,'FINDING'):app.kernel.entities(legacy)[nid]['questions']=[copy.deepcopy(row)]
        for n in app.kernel.entities(legacy).values():n.pop('review',None)
        legacy['externalActions']=[a for a in legacy['externalActions'] if not a['lowLevel']]
        legacy['events']=[e for e in legacy['events'] if e['type']!='action_executed']
        req=self.req('create',rootReason='Import legacy fixture explicitly',path='working/legacy-questions',role='working',coreModel='rdg-decision-v1',title='Legacy import',graph=legacy)
        pid=app.request(req)['packages'][0]['packageId']
        for nid in (decision,'FINDING'):
            req=self.form(pid,'question_migrate',nid);self.apply_checked(req)
        graph=app.read(pid)['graph'];qs=[n for n in graph['objects'] if n['kind']=='question']
        self.assertEqual(len(qs),2);self.assertNotEqual(qs[0]['id'],qs[1]['id'])
        self.assertEqual({q['relatedRefs'][0]['nodeId'] for q in qs},{decision,'FINDING'})
        self.assertFalse(app.kernel.entities(graph)[decision]['questions'])
        self.assertEqual(app.kernel.entities(graph)[decision]['selectionState'],'discovered')
        self.assertEqual(app.kernel.entities(graph)['FINDING']['disposition']['code'],'unresolved')
        req=self.command_request(pid,'edit',nodeId=decision,changes={'questions':[row]},cosmetic=False)
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'LEGACY_MIGRATION_REQUIRED'):app.request(req)
        self.assertEqual(before,self.sources())

    def test_paper_question_capture_and_apply_preserve_local_identity_without_live_answers(self):
        app=self.app();pid=app.request(self.req('create',path='working/paper-question-source',role='working',coreModel='rdg-decision-v1',title='Paper questions',scope='Synthetic',rootReason='Template safety'))['packages'][0]['packageId']
        read=app.read(pid);req=app.schema('core',pid,node_id='R1',command='add',entity_kind='question')['request'];req['note']='Reusable unresolved question'
        req['data']['entity'].update(title='What data is required?',impact='Determines feasibility',answerCondition='A current measurement',relatedRefs=[read['references']['R1']])
        self.apply_checked(req)
        req=app.schema('capture_ready',pid)['request'];req.update(path='ready/paper-questions',note='Only paper questions, no process answers')
        result=self.apply_checked(req);ready=result['packages'][0]['packageId']
        graph=app.read(ready)['graph'];q=next(n for n in graph['objects'] if n['kind']=='question')
        self.assertEqual(q['answers'],[]);self.assertFalse(q['sourceRefs']);self.assertNotIn('inheritedHistory',graph)
        kernel=app.kernel.for_graph(graph);self.assertIn(kernel.QUESTIONS.reference_id(graph,q['relatedRefs'][0],kernel,q),kernel.entities(graph))
        req=app.schema('apply_ready',pid,source_id=ready)['request'];req['note']='Instantiate reusable Question';req['mode']='ADD_ROOT'
        self.apply_checked(req)
        self.assertEqual(len([n for n in app.read(pid)['graph']['objects'] if n['kind']=='question']),2)
        req=app.schema('apply_ready',pid,source_id=ready)['request'];req['note']='Second independent template instance';req['mode']='ADD_ROOT';self.apply_checked(req)
        graph=app.read(pid)['graph'];kernel=app.kernel.for_graph(graph)
        bound=[kernel.QUESTIONS.reference_id(graph,q['relatedRefs'][0],kernel,q) for q in graph['objects'] if q['kind']=='question']
        self.assertEqual(len(set(bound)),3)
        original_q=next(n for n in app.read(pid)['graph']['objects'] if n['kind']=='question')
        req=self.form(pid,'question_answer',original_q['id']);req['data'].update(text='A process-only hypothesis');self.apply_checked(req)
        req=app.schema('capture_ready',pid)['request'];req.update(path='ready/forbidden-live-question',note='Must not promote process answers')
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'QUESTION_TEMPLATE_LIVE_DATA'):app.request(req)
        self.assertEqual(before,self.sources())

    def test_graph_estimates_trigger_definition_review_and_survive_copy(self):
        pid,decision=self.finding_package();app=self.app()
        self.command(pid,'add',entity={'id':'GRAPH-A','kind':'action','title':'Measure','description':'','actionType':'task','lowLevel':False,'targetIds':[],'groupIds':[]},initialRelations=[{'id':'REQUIRED-A','type':'REQUIRES_ACTION','from':decision,'to':'GRAPH-A'}])
        self.command(pid,'link',relation={'id':'EST-WATCH','type':'DEPENDS_ON','from':'GRAPH-A','to':decision,'dependencyLevel':'L1'})
        req=self.form(pid,'review',decision);self.apply_checked(req)
        req=self.command_request(pid,'edit',nodeId='GRAPH-A',changes={'estimates':{'time':{'minSeconds':60,'maxSeconds':180}}},cosmetic=False);self.apply_checked(req)
        graph=app.read(pid)['graph'];self.assertTrue(app.kernel.entities(graph)[decision]['review']['required'])
        hit=[h for e in graph['events'] for h in e.get('dependencyImpacts',[]) if h['sourceId']=='GRAPH-A' and h['dependentId']==decision]
        self.assertTrue(any('definition' in h['changedParts'] for h in hit))
        req=app.schema('copy',pid,source_id=pid)['request'];req.update(path='copy/estimates',note='Preserve estimate')
        result=self.apply_checked(req);copied=app.read(result['packages'][0]['packageId'])['graph']
        action=next(n for n in copied['nodes'] if n['kind']=='action' and n['title']=='Measure')
        self.assertEqual(action['estimates'],{'time':{'minSeconds':60,'maxSeconds':180}})
        self.assertEqual(action['result'],{'state':'open','truth':'unknown'})

    def test_scoped_question_and_area_focus_copies_remap_the_same_scope(self):
        pid,decision,qid=self.setup_question();app=self.app()
        self.command(pid,'work_graph',workGraph={'id':'SCOPE-AREA','title':'Area','rootIds':[],'memberIds':[decision]})
        ref={'schemaVersion':1,'kind':'workGraph','packageId':pid,'identitySpace':app.read(pid)['graph']['identitySpace'],'workGraphId':'SCOPE-AREA'}
        self.command(pid,'edit',nodeId=qid,changes={'relatedRefs':[ref],'sourceRefs':[{'schemaVersion':1,'kind':'document','uri':'https://example.test/theory'}]},cosmetic=False)
        for kind,ident in [('question',qid),('workGraph','SCOPE-AREA')]:
            req=app.schema('copy',pid,source_id=pid)['request'];req.update(path='copy/scope-'+kind,note='Preserve scoped Question',focus={'kind':kind,'id':ident})
            result=self.apply_checked(req);copied_id=result['packages'][0]['packageId'];graph=app.read(copied_id)['graph']
            qs=[n for n in graph['objects'] if n['kind']=='question'];self.assertEqual(len(qs),1)
            scope=qs[0]['relatedRefs'][0];self.assertEqual(scope['packageId'],copied_id);self.assertEqual(scope['identitySpace'],graph['identitySpace'])
            self.assertNotEqual(scope['workGraphId'],'SCOPE-AREA');self.assertTrue(any(w['id']==scope['workGraphId'] and w['memberIds'] for w in graph['workGraphs']))
            self.assertEqual(qs[0]['sourceRefs'][0]['uri'],'https://example.test/theory')

    def test_question_delete_preflight_shows_links_and_preserves_subjects_and_receipt(self):
        pid,decision,qid=self.setup_question();app=self.app()
        req=app.schema('delete',pid,node_id=qid)['request'];req['note']='Remove the Question, preserve subjects'
        before=self.sources();preview=app.call({'method':'preflight','request':req});self.assertEqual(before,self.sources())
        links=preview['effects']['questionLinks'];self.assertEqual(links[0]['questionId'],qid);self.assertTrue(links[0]['removed']);self.assertEqual(len(links[0]['relatedRefs']),2)
        self.apply_checked(req)
        graph=app.read(pid)['graph'];ns=app.kernel.entities(graph);self.assertNotIn(qid,ns)
        self.assertEqual(ns[decision]['selectionState'],'discovered');self.assertEqual(ns['FINDING']['disposition']['code'],'unresolved')
        self.assertTrue(any(e['type']=='removed' and qid in e['nodeIds'] for e in graph['events']))

    def test_estimates_validation_removal_history_and_no_result_side_effect(self):
        pid,_=self.finding_package()
        self.command(pid,'add',entity={'id':'A','kind':'action','title':'Measure','description':'','actionType':'task','lowLevel':False,'targetIds':[],'groupIds':[]},location='external')
        app=self.app()
        for value in [{'complexity':'Hard, requires access'},{'time':{'minSeconds':0,'maxSeconds':0}},{'complexity':'Simple','time':{'minSeconds':60,'maxSeconds':180},'basis':'Prior sample'}]:
            req=self.command_request(pid,'edit',nodeId='A',changes={'estimates':value},cosmetic=False);self.apply_checked(req)
            n=app.call({'method':'read','packageId':pid,'detail':'item','nodeId':'A'})['item']
            self.assertEqual(n['estimates'],value);self.assertEqual(n['result'],{'state':'open','truth':'unknown'})
        for value in [{},{'basis':'No estimate'},{'complexity':''},{'time':{'minSeconds':2,'maxSeconds':1}},{'time':{'minSeconds':False,'maxSeconds':1}},{'time':{'minSeconds':-1,'maxSeconds':1}},{'time':{'minSeconds':1,'maxSeconds':'2'}}]:
            req=self.command_request(pid,'edit',nodeId='A',changes={'estimates':value},cosmetic=False);before=self.sources()
            with self.assertRaisesRegex(ValueError,'ESTIMATES'):app.request(req)
            self.assertEqual(before,self.sources())
        req=self.command_request(pid,'edit',nodeId='A',changes={'estimates':{'complexity':'New'}},cosmetic=True)
        with self.assertRaisesRegex(ValueError,'COSMETIC'):app.request(req)
        req=self.command_request(pid,'edit',nodeId='A',changes={'estimates':None},cosmetic=False);self.apply_checked(req)
        graph=app.read(pid)['graph'];self.assertNotIn('estimates',app.kernel.entities(graph)['A'])
        edits=[e for e in graph['events'] if any(r['field']=='estimates' for r in e.get('historyDetail',{}).get('edits',[]))]
        self.assertEqual(len(edits),4)
        self.assertFalse(edits[-1]['historyDetail']['edits'][0]['afterPresent'])
        self.assertEqual(graph,self.app().read(pid)['graph'])

if __name__=='__main__':unittest.main()
