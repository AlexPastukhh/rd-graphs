#!/usr/bin/env python3
"""Public API ergonomics on disposable Graph/Registry owners; no live data."""
import copy
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('ergonomics_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()


class ApiErgonomics(unittest.TestCase):
    setUp=T.PortableApplication.setUp
    config=T.PortableApplication.config
    app=T.PortableApplication.app
    req=T.PortableApplication.req
    sources=T.PortableApplication.sources

    def create(self,role='lens'):
        app=self.app();request=app.schema('create',core_model='rdg-decision-v1',role=role)['request']
        name=uuid.uuid4().hex
        request.update(path=role+'/'+name,title='Synthetic API owner',scope='Synthetic',rootReason='API integration acceptance')
        if role=='lens':request['lensKey']='api-'+name
        return app.request(request)['packages'][0]['packageId']

    def paper(self,pid,command,data):
        app=self.app();request=app.schema('paper_edit',pid,command=command)['request']
        request.update(data=data,note='Explicit synthetic paper authoring')
        return app.request(request)

    def batch(self,pid,steps):
        request=self.app().schema('batch',pid)['request']
        request.update(steps=steps,note='Synthetic atomic batch')
        return request

    def decision(self,pid):
        self.paper(pid,'add',{'entity':{'id':'D','kind':'decision','title':'Candidate','description':'Basis'},
            'initialRelations':[{'id':'RD','type':'DRIVES','from':'R1','to':'D'}]})

    def theory(self,pid,op='paper_edit',**fields):
        request=self.app().schema(op,pid,command='add',entity_kind='canon')['request']
        request.update(data={'entity':{'id':'K','kind':'canon','title':'Theory','description':'Synthetic',
            'guidance':'Read [one](theory:canons/one).','canonItems':[{'id':'one','title':'One','body':'Exact body'}],**fields}},
            note='Synthetic owned theory')
        return self.app().request(request)

    def test_paper_batch_same_cas_replay_and_no_process_history(self):
        for role in ('lens','ready'):
            with self.subTest(role=role):
                pid=self.create(role);app=self.app()
                request=self.batch(pid,[
                    {'alias':'d','op':'paper_edit','command':'add','data':{
                        'entity':{'kind':'decision','title':'New option','description':'Candidate'},
                        'initialRelations':[{'id':'RD','type':'DRIVES','from':'R1','to':{'$alias':'d'}}]}},
                    {'alias':'t','op':'paper_edit','command':'graph_title','data':{'title':'Edited title'}}])
                before=self.sources();pre=app.call({'method':'preflight','request':request})
                self.assertEqual(before,self.sources())
                result=app.call({'method':'apply','request':request,'expectedInputBinding':pre['inputBinding']})
                self.assertTrue(result['published'])
                self.assertTrue(app.call({'method':'apply','request':request})['idempotent'])
                row=app.read(pid);self.assertEqual(row['graph']['events'],[])
                self.assertIsNone(row['plan'])
                self.assertEqual(row['graph']['title'],'Edited title')
                option=app.kernel.entities(row['graph'])[pre['effects']['aliasIds']['d']]
                self.assertNotEqual(option['selectionState'],'selected')
                self.assertEqual(option['result'],{'state':'open','truth':'unknown'})

    def test_paper_batch_rejects_process_and_plan_and_invalid_intermediate_steps(self):
        pid=self.create();app=self.app()
        for step in (
            {'alias':'s','op':'paper_edit','command':'select','data':{'nodeId':'R1'}},
            {'alias':'s','op':'core','command':'edit','data':{}},
            {'alias':'s','op':'plan_create','title':'Forbidden'}):
            before=self.sources()
            with self.assertRaises(ValueError):app.request(self.batch(pid,[step]))
            self.assertEqual(before,self.sources())
        request=self.batch(pid,[
            {'alias':'add','op':'paper_edit','command':'add','data':{'entity':{'id':'X','kind':'info','title':'Transient','description':'','value':'Value'}}},
            {'alias':'bad','op':'paper_edit','command':'link','data':{'edge':{'id':'bad','type':'DRIVES','from':'missing','to':'X'}}}])
        before=self.sources()
        with self.assertRaises(ValueError):app.request(request)
        self.assertEqual(before,self.sources())

    def test_remove_is_distinct_from_unlink_and_preserves_old_pin(self):
        pid=self.create();self.decision(pid);app=self.app();before=app.read(pid)
        ref=before['references']['D'];pin={k:ref[k] for k in ('packageId','identitySpace','graphRevision','sha256')}
        request=app.schema('paper_edit',pid,node_id='D',command='remove')['request']
        request.update(data={'nodeIds':['D']},note='Explicit synthetic removal')
        pre=app.call({'method':'preflight','request':request})
        self.assertEqual(pre['effects']['removedNodeIds'],['D'])
        self.assertEqual(pre['effects']['removedEdgeIds'],['RD'])
        self.assertFalse(pre['effects']['dependentOwnersChanged'])
        app.call({'method':'apply','request':request,'expectedInputBinding':pre['inputBinding']})
        self.assertNotIn('D',app.kernel.entities(app.read(pid)['graph']))
        self.assertEqual(app.source_snapshot(pid,pin,detail='graph')['graph'],before['graph'])
        self.assertEqual(app.read(pid)['graph']['events'],[])

    def test_current_incoming_theory_ref_blocks_without_other_owner_edits(self):
        pid=self.create();self.decision(pid);app=self.app();working=self.create('working')
        target={'schemaVersion':1,'kind':'lens','reference':app.read(pid)['references']['D']}
        self.theory(working,'core',recommendations=[{'id':'source','title':'Method','targetRef':target}])
        request=app.schema('delete',pid,node_id='D')['request'];request['note']='Explicit removal'
        before=self.sources()
        for preflight in (True,False):
            with self.assertRaisesRegex(ValueError,'PAPER_REMOVE_CURRENT_REFERENCES'):
                app.request(request,preflight=preflight)
            self.assertEqual(before,self.sources())

    def test_batch_remove_uses_same_guard_and_effects(self):
        pid=self.create();self.decision(pid);app=self.app()
        request=self.batch(pid,[{'alias':'drop','op':'paper_edit','command':'remove','data':{'nodeIds':['D']}}])
        pre=app.request(request,preflight=True)
        self.assertEqual(pre['effects']['removedNodeIds'],['D'])
        app.request(request,expected_input_binding=pre['inputBinding'])
        self.assertNotIn('D',app.kernel.entities(app.read(pid)['graph']))

    def test_preflight_focus_and_markdown_use_proposed_graph_without_persistence(self):
        pid=self.create();app=self.app()
        request=self.batch(pid,[{'alias':'d','op':'paper_edit','command':'add','data':{
            'entity':{'id':'D','kind':'decision','title':'Proposed option','description':'Proposed body'},
            'initialRelations':[{'id':'RD','type':'DRIVES','from':'R1','to':'D'}]}}])
        before=self.sources()
        pre=app.call({'method':'preflight','request':request,
            'preview':{'packageId':pid,'detail':'focus','nodeId':'D','format':'markdown'}})
        self.assertFalse(pre['preview']['persisted'])
        self.assertIn('Proposed option',pre['preview']['projection']['markdown'])
        self.assertEqual(before,self.sources())
        app.call({'method':'apply','request':request,'expectedInputBinding':pre['inputBinding']})
        self.assertIn('D',app.kernel.entities(app.read(pid)['graph']))

    def test_owned_ref_current_historical_stale_and_source_route(self):
        pid=self.create();self.theory(pid,recommendations=[{'id':'source','title':'External',
            'targetRef':{'schemaVersion':1,'kind':'document','uri':'https://example.org/source','version':'v1'}}])
        app=self.app();message={'method':'theory_read','packageId':pid,'theoryId':'K','collection':'canons'}
        item=app.call(message)['data']['canons']['items'][0]
        direct=app.call(item['nextRead'])
        self.assertEqual(direct['data']['canons']['items'][0]['body'],'Exact body')
        original=copy.deepcopy(item['ref'])
        self.paper(pid,'edit',{'nodeId':'K','changes':{'canonItems':[{'id':'one','title':'One','body':'Changed body'}]},'cosmetic':False})
        with self.assertRaisesRegex(ValueError,'OWNED_REF_CHANGED'):app.call(item['nextRead'])
        original['theoryRef']['mode']='historical'
        old=app.call({'method':'read_ref','reference':original})
        self.assertTrue(old['historical']);self.assertIsNone(old['snapshot']['packageRevision'])
        self.assertEqual(old['data']['canons']['items'][0]['body'],'Exact body')
        self.assertEqual(app.call(old['data']['canons']['items'][0]['nextRead'])['data']['canons']['items'][0]['body'],'Exact body')
        source=app.call({**message,'collection':'recommendations'})['data']['recommendations']['items'][0]
        self.assertFalse(source['contentLoaded'])
        self.assertEqual(source['sourceAccess']['route'],'external-reader')
        self.assertEqual(source['sourceAccess']['request']['version'],'v1')

    def test_receipt_envelope_package_registry_and_prepared_state(self):
        pid=self.create();app=self.app()
        request=self.batch(pid,[{'alias':'t','op':'paper_edit','command':'graph_title','data':{'title':'Receipt title'}}])
        result=app.request(request);receipt=app.call({'method':'receipt','transactionId':request['transactionId']})
        self.assertTrue(receipt['published']);self.assertFalse(receipt['currentStateVerified'])
        self.assertEqual(receipt['requestSHA256'],result['requestSHA256'])
        self.assertEqual(receipt['participants'][0]['receipt'],result['packages'][0]['receipt'])
        graph=app.read(pid)['graph']
        definition={'id':str(uuid.uuid4()),'revision':1,'key':'api-test','title':'Advice','supplied':False,'authored':True,
            'rules':[{'id':'rule','nodeKinds':['decision'],'scope':'all','state':'any','whenText':'When useful','usageText':'Read',
                'lensRefs':[{'packageId':pid,'identitySpace':graph['identitySpace'],'lensKey':app.snapshot(pid)['head']['lensKey']}]}]}
        request=self.req('recommendation_edit',expectedRegistryRevision=app.recommendation_catalog()['registryRevision'],
            action='create',definition=definition,note='Registry-only synthetic operation')
        result=app.request(request)
        receipt=app.call({'method':'receipt','transactionId':request['transactionId']})
        self.assertTrue(receipt['published'])
        self.assertEqual(receipt['participants'][0]['owner']['kind'],'recommendationRegistry')
        self.assertEqual(receipt['participants'][0]['receipt'],result['participants'][0]['receipt'])

    def test_capabilities_identity_reasons_and_graph_only_snapshot(self):
        pid=self.create();app=self.app();caps=app.call({'method':'capabilities','packageId':pid})
        self.assertFalse(caps['runtime']['identityAvailable'])
        self.assertTrue(caps['features']['paperRemoval']['available'])
        app.runtime_build_id='test-host-build'
        self.assertEqual(app.call({'method':'capabilities'})['runtime']['buildId'],'test-host-build')
        working=self.create('working')
        self.assertEqual(app.call({'method':'capabilities','packageId':working})['features']['paperBatch']['reason'],'paper-owner-required')
        row=app.read(pid);ref=row['references']['R1'];pin={k:ref[k] for k in ('packageId','identitySpace','graphRevision','sha256')}
        with patch.object(app.model,'presentation',side_effect=AssertionError('unnecessary visual projection')):
            compact=app.call({'method':'source_snapshot','packageId':pid,'pin':pin,'detail':'graph'})
        self.assertEqual(compact['graph'],row['graph'])
        self.assertNotIn('view',compact)


    def test_graph_only_batch_keeps_the_advertised_existing_plan_cas(self):
        pid=self.create('working');app=self.app()
        request=app.schema('plan_create',pid)['request'];request.update(title='Existing Plan')
        app.request(request)
        before=app.read(pid,True)['plan']
        request=self.batch(pid,[{'alias':'info','op':'core','command':'add',
            'data':{'entity':{'id':'I','kind':'info','title':'Read me','description':'','value':'Body'}}}])
        self.assertEqual(request['expectedPlanRevision'],before['revision'])
        pre=app.request(request,preflight=True)
        app.request(request,expected_input_binding=pre['inputBinding'])
        self.assertEqual(app.read(pid,True)['plan'],before)

    def test_prepared_certificate_is_readonly_and_not_a_published_receipt(self):
        pid=self.create();app=self.app()
        request=self.batch(pid,[{'alias':'t','op':'paper_edit','command':'graph_title','data':{'title':'Prepared title'}}])
        def stop(phase):
            if phase=='prepared':raise RuntimeError('Synthetic interruption')
        with self.assertRaisesRegex(RuntimeError,'Synthetic interruption'):app.request(request,failpoint=stop)
        before=self.sources()
        receipt=app.call({'method':'receipt','transactionId':request['transactionId']})
        self.assertTrue(receipt['accepted']);self.assertFalse(receipt['published'])
        self.assertNotIn('receipt',receipt['participants'][0])
        self.assertEqual(before,self.sources())
        result=app.request(request)
        self.assertTrue(result['idempotent'])
        self.assertTrue(app.receipt(None,request['transactionId'])['published'])

    def test_registry_anchor_and_lens_step_block_paper_removal(self):
        pid=self.create();self.decision(pid);app=self.app();graph=app.read(pid)['graph']
        definition={'id':str(uuid.uuid4()),'revision':1,'key':'guard-test','title':'Advice','supplied':False,'authored':True,
            'rules':[{'id':'rule','nodeKinds':['decision'],'scope':'identity','state':'any',
                'anchor':{'packageId':pid,'identitySpace':graph['identitySpace'],'nodeId':'D','kind':'entity'},
                'whenText':'When useful','usageText':'Read',
                'lensRefs':[{'packageId':pid,'identitySpace':graph['identitySpace'],'lensKey':app.snapshot(pid)['head']['lensKey'],'nodeId':'D'}]}]}
        request=self.req('recommendation_edit',expectedRegistryRevision=app.recommendation_catalog()['registryRevision'],
            action='create',definition=definition,note='Synthetic anchored advice')
        app.request(request)
        other=self.authority.manage('issue',self.admin,{'permissions':['graph.read'],
            'scopes':['packages/'+self.namespace+'/']})['token']
        self.assertFalse(self.app(other).receipt(None,request['transactionId'])['found'])
        remove=self.batch(pid,[{'alias':'drop','op':'paper_edit','command':'remove','data':{'nodeIds':['D']}}])
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'PAPER_REMOVE_CURRENT_REFERENCES.*recommendationRegistry'):
            app.request(remove,preflight=True)
        self.assertEqual(before,self.sources())
        edited=copy.deepcopy(definition);edited['revision']=2
        edited['rules'][0].pop('anchor');edited['rules'][0]['scope']='all'
        edited['rules'][0]['lensRefs'][0].pop('nodeId')
        request=self.req('recommendation_edit',expectedRegistryRevision=app.recommendation_catalog()['registryRevision'],
            action='edit',packageId=definition['id'],definition=edited,note='Explicit removal of current references')
        app.request(request)
        # Original Graph CAS is still current; changing Registry did not silently alter the lens.
        app.request(remove)
        self.assertNotIn('D',app.kernel.entities(app.read(pid)['graph']))

    def test_paper_remove_respects_immutable_owner_and_scoped_inventory(self):
        pid=self.create();self.decision(pid);app=self.app();row=app.snapshot(pid)
        fixture=T.PortableApplication();fixture.__dict__.update(self.__dict__)
        fixture._seed_source_metadata({pid:{'path':row['path'],'before':row,
            'lineage':{'supplied':True,'sourceDefinitionSHA256':'a'*64},'permissions':['graph.write']}})
        request=self.batch(pid,[{'alias':'drop','op':'paper_edit','command':'remove','data':{'nodeIds':['D']}}])
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'PACKAGE_IMMUTABLE'):app.request(request)
        self.assertEqual(before,self.sources())
        self.assertFalse(app.call({'method':'capabilities','packageId':pid})['features']['paperRemoval']['available'])
        manage=app.schema('lens_manage',pid)['request'];manage.update(confirmOwnerManagement=True,note='Explicit synthetic management')
        app.request(manage)
        self.create('working')
        scoped=self.authority.manage('issue',self.admin,{'permissions':['graph.read','graph.write'],
            'scopes':['packages/'+self.namespace+'/'+pid]})['token']
        request=self.batch(pid,[{'alias':'drop','op':'paper_edit','command':'remove','data':{'nodeIds':['D']}}])
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'SCOPE_DENIED'):self.app(scoped).request(request)
        self.assertEqual(before,self.sources())


if __name__=='__main__':unittest.main()
