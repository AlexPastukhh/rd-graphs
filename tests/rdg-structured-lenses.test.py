#!/usr/bin/env python3
"""Source completeness, ordinary Application views and non-destructive lens upgrade."""
import copy
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import subprocess
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
F=SourceFileLoader('structured_lens_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
P=SourceFileLoader('structured_lens_publisher',str(ROOT/'tools/rdg-lens-publish.py')).load_module()
MD=SourceFileLoader('structured_lens_markdown',str(ROOT/'tools/rdg-structured-markdown.py')).load_module()
C=SourceFileLoader('structured_lens_compiler',str(ROOT/'tools/rdg-lens-content.py')).load_module()

class Sources(unittest.TestCase):
    def test_the_19_sources_are_complete_versioned_and_not_mechanical_requirements(self):
        plan,graphs,_=P.bundle()
        self.assertEqual(len(graphs),19)
        self.assertEqual(sum(p['group']=='bootstrap' for p in plan.values()),7)
        for key,g in graphs.items():
            with self.subTest(lens=key):
                P.PROFILES.validate_role(g,'lens')
                self.assertEqual(P.AGENT.lens_definition(key)[2]['coreModel'],'rdg-decision-v1')
                ns=P.entities(g)
                mapping=json.loads(next(n['value'] for n in g['objects'] if 'rdg:lens-source-map' in n.get('tags',[])))
                path=ROOT/mapping['source']['path'];raw=path.read_bytes()
                self.assertEqual(C.sha(raw),mapping['source']['sha256'])
                self.assertEqual(raw.decode(),ns[mapping['fullTextInfoId']]['value'])
                _,_,sections=C.source_sections(path)
                self.assertEqual([s['anchor'] for s in sections],[r['anchor'] for r in mapping['rows']])
                for section,row in zip(sections,mapping['rows']):
                    self.assertEqual(C.sha(section['text'].encode()),row['sectionSHA256'])
                    self.assertTrue(set(row['entityIds'])<=set(ns))
                    self.assertTrue(set(row['edgeIds'])<={e['id'] for e in g['edges']})
                    preserved=ns[C.source_id(key,section)]
                    self.assertIn(section['text'].strip(),preserved.get('guidance',preserved.get('value','')))
                    self.assertIn(preserved['kind'],('canon','info'))
                self.assertTrue(set(plan[key]['retainedIds'])<=set(ns))
                self.assertEqual(g['events'],[])
                self.assertTrue(all(n.get('result',{}).get('truth')!='true' for n in ns.values()))
        model=graphs['model']
        self.assertTrue({'R-CONTINUITY','R-DECOMPOSITION'}<={c['requirementId'] for c in model['rootCauses']})
        self.assertTrue(all(any(e['type']=='DERIVES' and e['from']==r and e['to']=='R-MODEL' for e in model['edges']) for r in ('R-CONTINUITY','R-DECOMPOSITION')))
        self.assertFalse(C.compile_all())

    def test_unknown_existing_identity_and_changed_kind_are_rejected_before_writes(self):
        graph=P.bundle(['research'])[1]['research']
        rogue=copy.deepcopy(graph);rogue['objects'].append({'id':'foreign','kind':'info','title':'Existing user content','description':'','revision':1,'value':'Keep'})
        with self.assertRaisesRegex(ValueError,'UNMAPPED_EXISTING_ENTITIES'):P.delta_commands(rogue,graph)
        rogue=copy.deepcopy(graph);rogue['nodes'][0]['kind']='decision'
        with self.assertRaisesRegex(ValueError,'ENTITY_KIND_CHANGE'):P.delta_commands(rogue,graph)

class LensApplication(unittest.TestCase):
    setUp=F.PortableApplication.setUp
    app=F.PortableApplication.app
    config=F.PortableApplication.config
    def test_all_definitions_create_and_read_as_the_same_graph_and_markdown(self):
        app=self.app();plan,graphs,_=P.bundle()
        for key,g in graphs.items():
            with self.subTest(lens=key):
                req=app.schema('create',core_model='rdg-decision-v1',role='lens')['request']
                req.update(path='lenses/'+key,lensKey=key,title=g['title'],scope='Synthetic teaching lens',rootReason='Source conversion acceptance',graph=g)
                result=app.call({'method':'apply','request':req,'expectedInputBinding':app.call({'method':'preflight','request':req})['inputBinding']})
                pid=result['packages'][0]['packageId'];row=app.call({'method':'read','packageId':pid,'detail':'full'})
                P.verify_graph(row['graph'],g)
                self.assertIsNone(row['plan'])
                self.assertTrue(any(n['id']==g['rootRequirementId'] for n in row['view']['entities']))
                markdown=MD.read_pages(app,{'method':'read','packageId':pid,'format':'markdown'},True)
                self.assertIn(g['rootRequirementId'],markdown['markdown'])
                self.assertIn('Карта соответствия',markdown['markdown'])
                self.assertTrue(app.call({'method':'receipt','packageId':pid,'transactionId':req['transactionId']})['published'])
        published={p['lensKey']:{'packageId':p['packageId'],'identitySpace':p['identitySpace']} for p in app.catalog()['packages']}
        state={'verified':published}
        def write(key,request):
            return app.call({'method':'apply','request':request,'expectedInputBinding':app.call({'method':'preflight','request':request})['inputBinding']})
        navigation=P.publish_navigation(app,graphs,state,write,lambda:None,lambda _:None)
        self.assertIn('work',navigation)
        self.assertTrue(any(any(ref['lensKey']=='research' for ref in rule['lensRefs']) for d in app.recommendation_catalog()['packages'] for rule in d['rules']))
        catalog=app.catalog();cards=[p['lensCard'] for p in catalog['packages']]
        self.assertEqual(len(cards),19);self.assertTrue(all(c['status']=='available' for c in cards))

    def test_supplied_upgrade_preserves_identity_history_working_data_and_resume(self):
        fixture=F.PortableApplication()
        # Use this case's isolated authority/store, not a second environment.
        fixture.__dict__.update(self.__dict__)
        app=self.app()
        old=json.loads(subprocess.check_output(['git','show','8f0ad5be997afde088f9d6fbb8e3cd27f8220c0d:tools/rdg-agent-lenses/work-decision.json'],cwd=ROOT,text=True))
        request={'op':'create','transactionId':str(uuid.uuid4()),'path':'lenses/fundamental/work','role':'lens','title':old['title'],'scope':'Original fixture','rootReason':'Original fixture','lensKey':'work','coreModel':'rdg-decision-v1','graph':old}
        pid=app.request(request)['packages'][0]['packageId']
        row=self.store.read(pid);fixture._seed_source_metadata({pid:{'path':row['path'],'before':row,'lineage':{'supplied':True,'sourceDefinitionSHA256':'a'*64},'permissions':['graph.write']}})
        before=app.read(pid);ref=before['references'][before['graph']['rootRequirementId']];pin={k:ref[k] for k in ('packageId','identitySpace','graphRevision','sha256')}
        working=app.request({'op':'create','transactionId':str(uuid.uuid4()),'path':'working/unrelated','role':'working','title':'Unrelated','scope':'Keep','rootReason':'Keep','coreModel':'rdg-decision-v1'})['packages'][0]['packageId']
        untouched=app.read(working)
        journal=self.base/'lens-transfer.json'
        with self.assertRaisesRegex(ValueError,'EXPLICIT_SUPPLIED_MANAGEMENT_REQUIRED'):
            P.run(app,journal,apply=True,keys=['work'],progress=lambda _:None)
        self.assertEqual(app.read(pid)['graph'],before['graph'])
        result=P.run(app,journal,apply=True,manage_supplied=True,keys=['work'],progress=lambda _:None)
        after=app.read(pid)
        self.assertEqual(result['verified']['work']['packageId'],pid)
        self.assertEqual(after['package']['identitySpace'],before['package']['identitySpace'])
        self.assertEqual(app.source_snapshot(pid,pin)['graph'],before['graph'])
        self.assertEqual(app.read(working)['graph'],untouched['graph'])
        self.assertEqual(app.read(working)['package'],untouched['package'])
        head=after['package']['revision']
        P.run(app,journal,apply=True,manage_supplied=True,keys=['work'],progress=lambda _:None)
        self.assertEqual(app.read(pid)['package']['revision'],head)

    def test_completed_journal_does_not_hide_changed_navigation(self):
        app=self.app();journal=self.base/'changed-navigation.json'
        P.run(app,journal,apply=True,keys=['model','work'],progress=lambda _:None)
        registry=app.recommendation_catalog()
        definition=copy.deepcopy(next(d for d in registry['packages'] if d['key']=='lens-source-work'))
        definition['revision']+=1
        definition['rules'][0]['usageText']='Changed after the original publication'
        app.request({'op':'recommendation_edit','transactionId':str(uuid.uuid4()),'action':'edit','packageId':definition['id'],
                     'expectedRegistryRevision':registry['registryRevision'],'definition':definition,'note':'Synthetic later revision'})
        with self.assertRaisesRegex(ValueError,'NAVIGATION_DEFINITION_EXISTS_REVIEW_NEW_VERSION'):
            P.run(app,journal,apply=True,keys=['model','work'],progress=lambda _:None)

    def test_lost_apply_response_resumes_from_the_original_receipt(self):
        app=self.app();journal=self.base/'lost-reply.json'
        class LostReply:
            def call(_,message):
                result=app.call(message)
                if message['method']=='apply':raise TimeoutError('Lost after accepted publication')
                return result
        with self.assertRaisesRegex(RuntimeError,'UNCERTAIN_LENS_OPERATION_SAVED'):
            P.run(LostReply(),journal,apply=True,keys=['research'],progress=lambda _:None)
        catalog=app.catalog();self.assertEqual(len(catalog['packages']),1)
        pid=catalog['packages'][0]['packageId'];revision=catalog['packages'][0]['revision']
        state=P.run(app,journal,apply=True,keys=['research'],progress=lambda _:None)
        self.assertEqual(state['verified']['research']['packageId'],pid)
        self.assertEqual(app.catalog()['packages'][0]['revision'],revision)

if __name__=='__main__':unittest.main()
