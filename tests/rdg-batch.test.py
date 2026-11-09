#!/usr/bin/env python3
"""Atomic T2 public batches against real isolated package owners."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import copy
import uuid
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('batch_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
CLI=SourceFileLoader('batch_cli',str(ROOT/'tools/rdg-portable.py')).load_module()


class AtomicBatch(unittest.TestCase):
    setUp=T.PortableApplication.setUp
    config=T.PortableApplication.config
    app=T.PortableApplication.app
    req=T.PortableApplication.req
    sources=T.PortableApplication.sources
    current=T.PortableApplication.current
    command_request=T.PortableApplication.command_request
    command=T.PortableApplication.command
    finding_package=T.PortableApplication.finding_package
    review=T.PortableApplication.review

    def start(self):
        ident,subject=self.finding_package()
        request=self.app().call({'method':'schema','op':'batch','packageId':ident})['request']
        request['note']='Batch acceptance, synthetic'
        return ident,subject,request

    def steps(self):
        return [
            {'alias':'d','op':'core','command':'add','data':{
                'entity':{'kind':'decision','title':'Batch decision','description':'A considered option'},
                'initialRelations':[{'id':'B-D','type':'DRIVES','from':'R1','to':{'$alias':'d'}}]}},
            {'alias':'a','op':'core','command':'add','data':{
                'entity':{'kind':'action','title':'Batch action','description':'Only a candidate',
                          'actionType':'task','lowLevel':False},
                'initialRelations':[{'id':'B-A','type':'REQUIRES_ACTION',
                                     'from':{'$alias':'d'},'to':{'$alias':'a'}}]}},
            {'alias':'plan','op':'plan_create','title':'Batch plan'},
            {'alias':'place','op':'place','nodeId':{'$alias':'a'},
             'at':'2026-11-08','afterStepId':None}]

    def test_schema_preflight_atomic_apply_receipt_restart_exact_retry(self):
        ident,subject,request=self.start()
        capabilities=self.app().read(ident)['capabilities']
        self.assertTrue(capabilities['capabilities']['atomicBatch'])
        self.assertIn('complete',capabilities['coreCommands'])
        self.assertNotIn('complete',capabilities['unsupportedCapabilities'])
        schema=self.app().call({'method':'schema','op':'batch','packageId':ident})
        self.assertEqual(schema['batch']['maxSteps'],100)
        self.assertIn('question_answer',schema['batch']['steps']['core']['command'])
        request['steps']=self.steps()
        before=self.sources();preview=self.app().call({'method':'preflight','request':request})
        self.assertEqual(before,self.sources())
        self.assertFalse(preview['accepted'])
        aliases=preview['effects']['aliasIds']
        self.assertEqual(set(aliases),{'d','a','plan','place'})
        result=self.app().call({'method':'apply','request':request,
                                'expectedInputBinding':preview['inputBinding']})
        self.assertTrue(result['published'])
        self.assertEqual(result['packages'][0]['receipt']['effects']['aliasIds'],aliases)
        after=self.app().read(ident,True)
        entities=self.app().kernel.entities(after['graph'])
        self.assertEqual(entities[aliases['d']]['selectionState'],'discovered')
        self.assertEqual(entities[aliases['a']]['result']['state'],'open')
        self.assertEqual(after['plan']['steps'][0]['ref']['nodeId'],aliases['a'])
        self.assertEqual(after['plan']['steps'][0]['id'],aliases['place'])
        event_ids=[event['id'] for event in after['graph']['events']]
        self.assertEqual(len(event_ids),len(set(event_ids)))
        self.assertIn('B-A',[e['id'] for e in after['graph']['edges']])
        recovered=CLI.application(self.config(),self.token)
        self.assertEqual(recovered.read(ident,True)['plan'],after['plan'])
        self.assertTrue(recovered.call({'method':'receipt','packageId':ident,
                       'transactionId':request['transactionId']})['found'])
        self.assertTrue(recovered.call({'method':'apply','request':request})['idempotent'])
        self.assertEqual(after['graph'],recovered.read(ident)['graph'])

    def test_bad_final_step_and_bad_plan_cannot_commit_first_steps(self):
        ident,subject,request=self.start()
        request['steps']=self.steps()
        request['steps'][-1]['nodeId']='not-present'
        before=self.sources()
        for method in ('preflight','apply'):
            with self.assertRaisesRegex(ValueError,'PLACEMENT_NODE_UNKNOWN'):
                self.app().call({'method':method,'request':request})
        self.assertEqual(before,self.sources())
        request['steps']=self.steps()[:2]
        request['steps'][-1]['data']['entity']['actionType']='unsupported'
        for method in ('preflight','apply'):
            with self.assertRaisesRegex(ValueError,'NEW_ACTION_FIELDS'):
                self.app().call({'method':method,'request':request})
        self.assertEqual(before,self.sources())

    def test_stale_revision_and_preview_pin_are_atomic(self):
        ident,subject,request=self.start()
        request['steps']=self.steps()[:2]
        preview=self.app().call({'method':'preflight','request':request})
        self.command(ident,'edit',nodeId=subject,changes={'description':'A changed subject'},cosmetic=False)
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'CAS_MISMATCH'):
            self.app().call({'method':'apply','request':request,'expectedInputBinding':preview['inputBinding']})
        self.assertEqual(before,self.sources())

    def test_alias_references_and_rejection_contract(self):
        ident,subject,request=self.start()
        request['steps']=[
            {'alias':'g','op':'core','command':'context_group',
             'data':{'action':'save','title':'Facts','parentId':None}},
            {'alias':'c','op':'core','command':'add','data':{'entity':{
                'kind':'context','title':'Observed','description':'Observed claim',
                'value':'Present in synthetic owner','contextGroupId':{'$alias':'g'}}}}]
        result=self.app().call({'method':'apply','request':request})
        aliases=result['packages'][0]['receipt']['effects']['aliasIds']
        g=self.app().read(ident)['graph']
        self.assertEqual(next(n for n in g['objects'] if n['id']==aliases['c'])['contextGroupId'],aliases['g'])
        self.assertEqual(next(c for c in g['contextGroups'] if c['id']==aliases['g'])['title'],'Facts')
        bad=self.app().schema('batch',ident)['request'];bad['note']='Reject batch'
        for steps,code in [
            ([{'alias':'d','op':'core','command':'add','data':{'entity':{'kind':'decision','title':'D','description':'D'},
              'initialRelations':[{'id':'R','type':'DRIVES','from':{'$alias':'future'},'to':{'$alias':'d'}}]}}], 'BATCH_ALIAS_UNKNOWN'),
            ([{'alias':'a','op':'core','command':'complete','data':{'nodeId':'R1'}}], 'BATCH_COMMAND_UNSUPPORTED'),
            ([{'alias':'a','op':'core','command':'add','data':{'entity':{'kind':'info','title':'I','value':'V','description':'V'}}}]*101,'BATCH_STEPS'),
            ([{'alias':'x','op':'place','nodeId':'R1'},{'alias':'y','op':'core','command':'edit','data':{'nodeId':'R1'}}], 'BATCH_GRAPH_AFTER_PLAN_UNSUPPORTED')]:
            trial=copy.deepcopy(bad);trial['steps']=steps;before=self.sources()
            with self.subTest(code=code),self.assertRaisesRegex(ValueError,code):
                self.app().call({'method':'preflight','request':trial})
            self.assertEqual(before,self.sources())

    def test_existing_plan_create_and_place_share_one_revision_and_receipt(self):
        ident,subject,request=self.start()
        request['steps']=[{'alias':'plan','op':'plan_create','title':'Existing process plan'}]
        self.app().call({'method':'apply','request':request})
        request=self.app().schema('batch',ident)['request']
        request['note']='Append action and placement atomically'
        request['steps']=[
            {'alias':'a','op':'core','command':'add','data':{'entity':{
                'kind':'action','title':'New action','description':'No completion implied',
                'actionType':'task','lowLevel':False},
                'initialRelations':[{'id':'BN-A','type':'REQUIRES_ACTION',
                                     'from':'R1','to':{'$alias':'a'}}]}},
            {'alias':'p','op':'place','nodeId':{'$alias':'a'},'at':'2026-11-09'}]
        before=self.app().read(ident,True)
        out=self.app().call({'method':'apply','request':request})
        after=self.app().read(ident,True)
        self.assertEqual(after['package']['revision'],before['package']['revision']+1)
        self.assertEqual(after['plan']['revision'],before['plan']['revision']+1)
        self.assertEqual(out['packages'][0]['receipt']['effects']['stepCount'],2)

    def test_explicit_selection_and_rejected_selection_are_distinct(self):
        ident,subject,request=self.start()
        self.review(ident)
        request=self.app().schema('batch',ident)['request']
        request['note']='Explicit approved selection'
        request['steps']=[
            {'alias':'chosen','op':'core','command':'select',
             'data':{'nodeId':subject},'note':'Select reviewed option'}]
        result=self.app().call({'method':'apply','request':request})
        did=subject
        graph=self.app().read(ident)['graph']
        self.assertEqual(self.app().kernel.entities(graph)[did]['selectionState'],'selected')
        self.assertEqual(len([e for e in graph['events'] if e['type']=='decision_selected']),1)

        other,subject,bad=self.start()
        bad['steps']=[
            {'alias':'d','op':'core','command':'add','data':{
                'entity':{'kind':'decision','title':'Orphan choice','description':'No support'}}},
            {'alias':'s','op':'core','command':'select','data':{'nodeId':{'$alias':'d'}}}]
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'NO_ACTIVE_BASIS'):
            self.app().call({'method':'apply','request':bad})
        self.assertEqual(self.sources(),before)

    def test_preacceptance_interruption_retries_original_batch(self):
        ident,subject,request=self.start()
        request['steps']=self.steps()[:2]
        preview=self.app().call({'method':'preflight','request':request})
        initial=self.app().read(ident)['graph']
        def fail(point):
            if point=='staged':raise RuntimeError('Synthetic batch staged interruption')
        with self.assertRaisesRegex(RuntimeError,'Synthetic batch staged'):
            self.app().request(request,failpoint=fail)
        self.assertEqual(self.app().read(ident)['graph'],initial)
        result=self.app().call({'method':'apply','request':request,
                                'expectedInputBinding':preview['inputBinding']})
        self.assertTrue(result['published'])
        self.assertEqual(result['packages'][0]['receipt']['effects']['aliasIds'],
                         preview['effects']['aliasIds'])
        self.assertTrue(self.app().call({'method':'apply','request':request})['idempotent'])

    def test_link_alias_can_target_previous_created_edge_and_edit(self):
        ident,subject,request=self.start()
        request['steps']=[
            {'alias':'ctx','op':'core','command':'add','data':{'entity':{
                'kind':'context','title':'Fact','description':'A fact','value':'Observed'}}},
            {'alias':'link','op':'core','command':'link','data':{'relation':{
                'type':'CONTEXT_FOR','from':{'$alias':'ctx'},'to':subject}}},
            {'alias':'edit','op':'core','command':'edit','data':{
                'nodeId':{'$alias':'ctx'},'changes':{'value':'Observed more precisely'},'cosmetic':False}}]
        preview=self.app().call({'method':'preflight','request':request})
        alias=preview['effects']['aliasIds']
        self.assertIn('link',alias)
        applied=self.app().call({'method':'apply','request':request})
        graph=self.app().read(ident)['graph']
        self.assertEqual(self.app().kernel.entities(graph)[alias['ctx']]['value'],'Observed more precisely')
        self.assertTrue(any(e['id']==alias['link'] for e in graph['edges']))
        self.assertEqual(applied['packages'][0]['receipt']['effects']['stepCount'],3)

    def test_many_steps_use_one_owner_snapshot_per_preflight_apply(self):
        ident,subject,request=self.start()
        request['steps']=[
            {'alias':'ctx'+str(i),'op':'core','command':'add',
             'data':{'entity':{'kind':'context','title':'Data '+str(i),
                                'description':'Batch load',
                                'value':'Observed '+str(i)}}}
            for i in range(20)]
        app=self.app()
        before=self.sources()
        with patch.object(app,'snapshot',wraps=app.snapshot) as snapshots:
            preview=app.call({'method':'preflight','request':request})
            self.assertEqual(snapshots.call_count,1)
            self.assertEqual(self.sources(),before)
            result=app.call({'method':'apply','request':request,
                             'expectedInputBinding':preview['inputBinding']})
            self.assertEqual(snapshots.call_count,2)
        self.assertEqual(len(result['packages']),1)
        self.assertEqual(result['packages'][0]['receipt']['effects']['stepCount'],20)
        self.assertEqual(len(result['packages'][0]['receipt']['effects']['aliasIds']),20)
        self.assertEqual(len([n for n in app.read(ident)['graph']['objects']
                              if n['kind']=='context']),20)

if __name__=='__main__':unittest.main()
