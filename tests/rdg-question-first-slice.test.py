#!/usr/bin/env python3
"""First T3 vertical API slice: canonical Question, sourced observation, assessment."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import copy
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('question_first_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()


class QuestionFirstSlice(unittest.TestCase):
    setUp=T.PortableApplication.setUp
    config=T.PortableApplication.config
    app=T.PortableApplication.app
    req=T.PortableApplication.req
    current=T.PortableApplication.current
    sources=T.PortableApplication.sources
    command=T.PortableApplication.command
    command_request=T.PortableApplication.command_request
    finding_package=T.PortableApplication.finding_package

    def setup_question(self):
        ident,decision=self.finding_package()
        self.command(ident,'add',entity={'id':'FACT','kind':'context',
            'title':'Synthetic observations','description':'Fixture',
            'value':'Queue latency sample, not user-supplied'})
        app=self.app()
        graph=app.read(ident)['graph']
        refs=[app.model.reference(ident,graph,ref) for ref in (decision,'FINDING')]
        request=app.call({'method':'schema','op':'core','packageId':ident,
                          'command':'add','nodeId':decision,'entityKind':'question'})['request']
        request['note']='Question about fixture trade-off'
        question=request['data']['entity']
        question.update(title='What is peak queue latency?',description='Unknown load peak',
                        relatedRefs=refs,impact='Changes decision feasibility',
                        answerCondition='An observed p95 for the expected peak')
        before=self.sources()
        preview=app.call({'method':'preflight','request':request})
        self.assertEqual(before,self.sources())
        applied=app.call({'method':'apply','request':request,
                          'expectedInputBinding':preview['inputBinding']})
        self.assertTrue(applied['published'])
        return ident,decision,question['id']

    def test_create_answer_assess_and_read_links_without_false_completion(self):
        ident,decision,qid=self.setup_question()
        app=self.app();graph=app.read(ident)['graph']
        question=next(n for n in graph['objects'] if n['id']==qid)
        self.assertEqual(question['kind'],'question')
        self.assertEqual({ref['nodeId'] for ref in question['relatedRefs']},{decision,'FINDING'})
        self.assertNotIn(qid,{n['id'] for n in graph['nodes']})
        self.assertEqual(app.kernel.entities(graph)['FINDING']['disposition']['code'],'unresolved')
        self.assertEqual(app.kernel.entities(graph)[decision]['selectionState'],'discovered')

        form=app.call({'method':'schema','op':'core','packageId':ident,
                       'nodeId':qid,'command':'question_answer'})
        request=form['request'];request['note']='Synthetic observed fact'
        request['data'].update(kind='observation',text='Measured 7 rps',
            sourceRefs=[app.model.reference(ident,graph,'FACT')])
        snapshot=self.sources()
        preview=app.call({'method':'preflight','request':request})
        self.assertEqual(snapshot,self.sources())
        self.assertTrue(app.call({'method':'apply','request':request,
                   'expectedInputBinding':preview['inputBinding']})['published'])
        self.assertTrue(app.call({'method':'apply','request':request})['idempotent'])
        stored=app.call({'method':'read','packageId':ident,'detail':'item',
                         'nodeId':qid})['item']
        self.assertEqual(len(stored['answers']),1)
        answer=stored['answers'][0]
        self.assertEqual(answer['kind'],'observation')
        self.assertEqual(answer['sourceRefs'][0]['nodeId'],'FACT')
        self.assertEqual(answer['recordedBy'],'assistant')
        self.assertIn('recordedAt',answer)
        self.assertEqual(len(app.call({'method':'read','packageId':ident,'detail':'item',
                          'nodeId':decision,'include':['questions']})['data']['questions']['items']),1)
        self.assertEqual(len(app.call({'method':'read','packageId':ident,'detail':'item',
                          'nodeId':'FINDING','include':['questions']})['data']['questions']['items']),1)

        request=app.call({'method':'schema','op':'core','packageId':ident,
                         'nodeId':qid,'command':'question_assess'})['request']
        request['note']='Insufficient for peak'
        request['data'].update(answerIds=[answer['id']],sufficient=False,
                               basis='Peak traffic not measured')
        self.assertTrue(app.call({'method':'apply','request':request})['published'])
        changed=app.call({'method':'read','packageId':ident,'detail':'item',
                          'nodeId':qid})['item']
        self.assertFalse(changed['assessment']['sufficient'])
        self.assertEqual(changed['assessment']['answerIds'],[answer['id']])
        self.assertFalse(changed['assessmentReviewRequired'])
        request=app.call({'method':'schema','op':'core','packageId':ident,
                         'nodeId':qid,'command':'question_assess'})['request']
        request['note']='Still insufficient'
        request['data'].update(answerIds=[answer['id']],sufficient=False,
                               basis='Still need a peak measurement')
        app.call({'method':'apply','request':request})
        changed=app.read(ident)['graph']
        question=app.kernel.entities(changed)[qid]
        self.assertEqual(len(question['assessmentHistory']),1)
        self.assertEqual(question['assessmentHistory'][0]['basis'],'Peak traffic not measured')
        self.assertEqual(app.kernel.entities(changed)[decision]['selectionState'],'discovered')
        self.assertEqual(app.kernel.entities(changed)['FINDING']['disposition']['code'],'unresolved')
        self.assertEqual(app.call({'method':'receipt','packageId':ident,
                    'transactionId':request['transactionId']})['found'],True)

    def test_fails_closed_for_unproven_user_answer_generic_edit_and_foreign_reference(self):
        ident,decision,qid=self.setup_question()
        app=self.app();base=self.sources()
        original=app.read(ident)['graph']
        bad_inputs=[
            ('question_answer',{'nodeId':qid,'kind':'user_answer','text':'User agreed','sourceRefs':[]},
             'QUESTION_USER_SOURCE_REQUIRED'),
            ('question_answer',{'nodeId':qid,'kind':'observation','text':'No source','sourceRefs':[]},
             'QUESTION_OBSERVATION_SOURCE_REQUIRED'),
            ('question_assess',{'nodeId':qid,'answerIds':['not-real'],'sufficient':True,'basis':'Invented'},
             'QUESTION_ASSESS_FIELDS'),
            ('edit',{'nodeId':qid,'changes':{'answers':[]},'cosmetic':False},'EDIT_FIELDS')
        ]
        for command,data,code in bad_inputs:
            with self.subTest(command=command,data=data):
                request=app.call({'method':'schema','op':'core','packageId':ident,
                                  'nodeId':qid,'command':command})['request']
                request['note']='Should not save';request['data']=data
                with self.assertRaisesRegex(ValueError,code):
                    app.call({'method':'apply','request':request})
                self.assertEqual(self.sources(),base)
        source=app.model.reference(ident,original,'FACT')
        source['packageId']='11111111-1111-4111-8111-111111111111'
        request=app.call({'method':'schema','op':'core','packageId':ident,
                       'nodeId':qid,'command':'question_answer'})['request']
        request['note']='Foreign source must be blocked'
        request['data'].update(kind='observation',text='Untrusted',sourceRefs=[source])
        with self.assertRaisesRegex(ValueError,'QUESTION_FOREIGN_REF_UNSUPPORTED'):
            app.call({'method':'apply','request':request})
        self.assertEqual(self.sources(),base)
        stale=app.model.reference(ident,original,'FACT')
        stale['sha256']='0'*64
        request['data']['sourceRefs']=[stale]
        with self.assertRaisesRegex(ValueError,'QUESTION_SOURCE_PIN_CHANGED'):
            app.call({'method':'apply','request':request})
        self.assertEqual(self.sources(),base)

    def test_change_condition_marks_assessment_stale_and_copy_preserves_it(self):
        ident,decision,qid=self.setup_question()
        app=self.app()
        request=app.call({'method':'schema','op':'core','packageId':ident,
                           'nodeId':qid,'command':'question_assess'})['request']
        request['note']='No evidence available'
        request['data'].update(answerIds=[],sufficient=False,basis='No observations yet')
        app.call({'method':'apply','request':request})
        request=app.call({'method':'schema','op':'core','packageId':ident,
                          'nodeId':qid,'command':'edit'})['request']
        request['note']='Change sufficiency condition'
        request['data']={'nodeId':qid,'changes':{'answerCondition':'Need a measured busy-hour p95'},'cosmetic':False}
        app.call({'method':'apply','request':request})
        q=app.call({'method':'read','packageId':ident,'detail':'item','nodeId':qid})['item']
        self.assertEqual(q['assessment']['basis'],'No observations yet')
        self.assertTrue(q['assessmentReviewRequired'])
        request=app.call({'method':'schema','op':'copy','packageId':ident,
                           'sourcePackageId':ident})['request']
        request.update(note='Copy not yet supported',path='copy/t3-unavailable')
        before=self.sources()
        preview=app.call({'method':'preflight','request':request})
        self.assertEqual(self.sources(),before)
        result=app.call({'method':'apply','request':request,'expectedInputBinding':preview['inputBinding']})
        copied=app.read(result['packages'][0]['packageId'])['graph']
        copied_q=next(n for n in copied['objects'] if n['kind']=='question')
        self.assertNotEqual(copied_q['id'],qid)
        self.assertTrue(copied_q['assessmentReviewRequired'])


    def test_existing_question_without_answer_history_stays_valid(self):
        # Owners persisted by the previous T3 slice had no answerHistory field.
        ident,_,qid=self.setup_question()
        app=self.app()
        add=app.call({'method':'schema','op':'core','packageId':ident,
                      'command':'question_answer','nodeId':qid})['request']
        add['note']='Legacy-format simulated answer'
        add['data'].update(kind='hypothesis',text='Unconfirmed',sourceRefs=[])
        app.call({'method':'apply','request':add})
        answer=next(n for n in app.read(ident)['graph']['objects'] if n['id']==qid)['answers'][0]
        assess=app.call({'method':'schema','op':'core','packageId':ident,
                         'command':'question_assess','nodeId':qid})['request']
        assess['note']='Earlier first-slice assessment'
        assess['data'].update(answerIds=[answer['id']],sufficient=False,basis='Unconfirmed data')
        app.call({'method':'apply','request':assess})
        import json
        schema=json.loads((ROOT/'tools/contracts/rdg-decision-v1.schema.json').read_text())
        self.assertNotIn('answerHistory',schema['$defs']['question']['required'])
        before=self.sources()
        older=copy.deepcopy(app.read(ident)['graph'])
        oldq=next(n for n in older['objects'] if n['id']==qid)
        self.assertEqual(oldq.pop('answerHistory'),[])
        app.kernel.validate(older)
        self.assertEqual(self.sources(),before)

    def test_question_panel_mode_is_session_only_and_validates_selected_id(self):
        ident,_,qid=self.setup_question()
        app=self.app()
        sid=str(uuid.uuid4())
        initial=app.call({'method':'view_session','action':'create',
                          'sessionId':sid,'packageId':ident})
        screen=copy.deepcopy(initial['screens'][0])
        screen['presentation']={'mode':'questions','questionId':qid}
        payload={'activeScreenId':screen['id'],'screens':[screen],
                 'explorer':initial['explorer']}
        before=self.sources()
        owner=app.read(ident)['graph']
        changed=app.call({'method':'view_session','action':'update',
             'sessionId':sid,'expectedRevision':initial['revision'],'value':payload})
        self.assertFalse(changed['persisted'])
        self.assertEqual(changed['screens'][0]['presentation'],screen['presentation'])
        self.assertEqual(self.sources(),before)
        self.assertEqual(app.read(ident)['graph'],owner)
        for invalid in (42,'x'*181):
            payload['screens'][0]['presentation']['questionId']=invalid
            with self.assertRaisesRegex(ValueError,'VIEW_PRESENTATION_SCHEMA'):
                app.call({'method':'view_session','action':'update','sessionId':sid,
                    'expectedRevision':changed['revision'],'value':payload})
        self.assertEqual(self.sources(),before)

    def test_answer_edit_remove_preserves_history_and_invalidates_assessment(self):
        ident,decision,qid=self.setup_question()
        app=self.app()
        def form():
            return app.call({'method':'schema','op':'core','packageId':ident,
                             'command':'question_answer','nodeId':qid})['request']
        add=form()
        self.assertEqual(add['data']['action'],'add')
        add['note']='First unsupported hypothesis'
        add['data'].update(kind='hypothesis',text='Likely under 50 ms',sourceRefs=[])
        self.assertTrue(app.call({'method':'apply','request':add})['published'])
        original=app.call({'method':'read','packageId':ident,'detail':'item','nodeId':qid})['item']['answers'][0]
        aid=original['id']

        assess=app.call({'method':'schema','op':'core','packageId':ident,
                         'command':'question_assess','nodeId':qid})['request']
        assess['note']='Initial optimistic judgment'
        assess['data'].update(answerIds=[aid],sufficient=True,basis='Initial hypothetical threshold')
        app.call({'method':'apply','request':assess})

        edit=form()
        edit['note']='Correct the original estimate'
        edit['data']={'nodeId':qid,'action':'edit','answerId':aid,
            'expectedAnswerEventId':original['eventId'],
            'kind':'hypothesis','text':'Likely under 70 ms','sourceRefs':[]}
        before=self.sources()
        preview=app.call({'method':'preflight','request':edit})
        self.assertEqual(before,self.sources())
        result=app.call({'method':'apply','request':edit,
                         'expectedInputBinding':preview['inputBinding']})
        self.assertTrue(result['published'])
        self.assertTrue(app.call({'method':'apply','request':edit})['idempotent'])
        question=app.call({'method':'read','packageId':ident,'detail':'item','nodeId':qid})['item']
        self.assertEqual(len(question['answers']),1)
        updated=question['answers'][0]
        self.assertEqual(updated['id'],aid,'edit must preserve canonical answer identity')
        self.assertNotEqual(updated['eventId'],original['eventId'])
        self.assertEqual(updated['text'],'Likely under 70 ms')
        self.assertEqual(len(question['answerHistory']),1)
        self.assertEqual(question['answerHistory'][0]['action'],'edit')
        self.assertEqual(question['answerHistory'][0]['previous'],original)
        self.assertTrue(question['assessmentReviewRequired'])
        self.assertTrue(question['assessment']['sufficient'])
        self.assertEqual(question['assessment']['answerIds'],[aid])

        stale=form()
        stale['note']='Editing stale snapshot is forbidden'
        stale['data']={'nodeId':qid,'action':'edit','answerId':aid,
            'expectedAnswerEventId':original['eventId'],'kind':'hypothesis',
            'text':'Made-up third value','sourceRefs':[]}
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'QUESTION_ANSWER_STALE'):
            app.call({'method':'apply','request':stale})
        self.assertEqual(before,self.sources())

        remove=form()
        remove['note']='Withdraw unsupported answer'
        remove['data']={'nodeId':qid,'action':'remove','answerId':aid,
                        'expectedAnswerEventId':updated['eventId']}
        before=self.sources()
        preview=app.call({'method':'preflight','request':remove})
        self.assertEqual(before,self.sources())
        self.assertTrue(app.call({'method':'apply','request':remove,
                         'expectedInputBinding':preview['inputBinding']})['published'])
        self.assertTrue(app.call({'method':'apply','request':remove})['idempotent'])
        question=app.call({'method':'read','packageId':ident,'detail':'item','nodeId':qid})['item']
        self.assertEqual(question['answers'],[])
        self.assertEqual([h['action'] for h in question['answerHistory']],['edit','remove'])
        self.assertEqual(question['answerHistory'][1]['previous'],updated)
        self.assertTrue(question['assessmentReviewRequired'])
        self.assertEqual(question['assessment']['answerIds'],[aid],
                         'historical assessment must not lose removed ID')
        self.assertEqual(self.app().read(ident)['graph'],
                         app.read(ident)['graph'],'restart must preserve edits and removals')

        invalid=form()
        invalid['note']='Already removed'
        invalid['data']=remove['data'].copy()
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'QUESTION_ANSWER_NOT_FOUND'):
            app.call({'method':'apply','request':invalid})
        self.assertEqual(before,self.sources())

        reassess=app.call({'method':'schema','op':'core','packageId':ident,
                         'command':'question_assess','nodeId':qid})['request']
        reassess['note']='No active answers'
        reassess['data'].update(answerIds=[],sufficient=False,basis='Hypothesis was withdrawn')
        self.assertTrue(app.call({'method':'apply','request':reassess})['published'])
        graph=app.read(ident)['graph'];entities=app.kernel.entities(graph);question=entities[qid]
        self.assertEqual(len(question['assessmentHistory']),1)
        self.assertTrue(question['assessmentHistory'][0]['sufficient'])
        self.assertFalse(question['assessment']['sufficient'])
        self.assertFalse(question['assessmentReviewRequired'])
        self.assertEqual(entities[decision]['selectionState'],'discovered')
        self.assertEqual(entities['FINDING']['disposition']['code'],'unresolved')


if __name__=='__main__':unittest.main()
