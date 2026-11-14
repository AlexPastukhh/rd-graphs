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
    def test_source_commit_is_claimed_only_for_the_exact_source_bytes(self):
        from unittest.mock import patch
        path=ROOT/'docs/lenses/methods/research.md';raw=path.read_bytes();commit='a'*40
        for head,committed,expected in ((commit,raw,commit),(commit,raw+b'\n',None),('',None,None)):
            with self.subTest(head=head,committed=expected is not None):
                replies=[head+'\n']+([committed] if head else [])
                with patch.object(C.subprocess,'check_output',side_effect=replies):
                    _,source,_=C.source_sections(path)
                self.assertEqual(source['sha256'],C.sha(raw))
                self.assertEqual(source['gitCommit'],expected)
                self.assertEqual(source.get('baseGitCommit'),head or None if expected is None else None)

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

    def test_preserve_choices_are_optional_but_cannot_both_be_selected(self):
        plan,graphs,_=P.bundle(['preserve']);g=graphs['preserve']
        group=g['decisionGroups'][0]
        self.assertEqual(len(g['decisionGroups']),1)
        self.assertEqual({m['decisionId'] for m in group['members']},{'A-PRESERVE-DRAW','A-PRESERVE-SKIP'})
        self.assertFalse(group['selectionRequired'])
        self.assertNotIn('group:'+group['id'],P.PROFILES.completion_state(g)[g['rootRequirementId']]['blockers'])
        self.assertEqual(C.compile_one('preserve',plan['preserve'],g)[0],g)
        retained_plan=copy.deepcopy(plan['preserve']);retained_plan.pop('decisionGroups')
        self.assertEqual(C.compile_one('preserve',retained_plan,g)[0]['decisionGroups'],g['decisionGroups'])
        def choose(graph,ident):
            tx=str(uuid.uuid5(uuid.NAMESPACE_URL,'preserve-choice-'+ident))
            event={'id':str(uuid.uuid5(uuid.UUID(tx),'select')),'type':'requested','by':'assistant',
                   'note':'Synthetic preserve scope','recordedAt':'2026-11-12T12:00:00Z',
                   'verifiedTrustReceipt':{'mode':'test-only','transactionId':tx}}
            return P.PROFILES.apply(graph,{'schemaVersion':1,'expectedRevision':graph['revision'],
                'operations':[{'op':'graph_edit','action':'core_select','data':{'nodeId':ident},'event':event}]},True)[0]
        for first,second in (('A-PRESERVE-DRAW','A-PRESERVE-SKIP'),('A-PRESERVE-SKIP','A-PRESERVE-DRAW')):
            chosen=choose(g,first);before=copy.deepcopy(chosen)
            self.assertEqual(P.entities(chosen)[first]['selectionState'],'selected')
            with self.assertRaisesRegex(ValueError,'DECISION_GROUP_CONFLICT'):choose(chosen,second)
            self.assertEqual(chosen,before)
        missing=copy.deepcopy(g);missing['decisionGroups']=[]
        with self.assertRaisesRegex(ValueError,'PUBLISHED_GROUPS_MISMATCH'):P.verify_graph(missing,g)

    def test_model_methods_are_native_compatible_choices_with_guarded_skip(self):
        plan,graphs,_=P.bundle(['model']);g=graphs['model'];ns=P.entities(g)
        methods={suffix:'LS-METHOD-MODEL-'+suffix for suffix,_,_ in plan['model']['extraMethods']}
        self.assertEqual(set(methods),{'R','D','A','K','C','I','F','Q','REUSE','ORGANIZE','SKIP'})
        group=next(gr for gr in g['decisionGroups'] if gr['id']=='G-MODEL-FORMS')
        self.assertTrue(group['selectionRequired']);self.assertFalse(group['mutuallyExclusive'])
        self.assertEqual({m['decisionId'] for m in group['members']},set(methods.values()))
        self.assertIn('group:'+group['id'],P.PROFILES.completion_state(g)['R-MODEL']['blockers'])
        self.assertFalse(any(e['type']=='DRIVES' and e['from']=='R-MODEL' and e['to'] in methods.values() for e in g['edges']))
        value=next(n['id'] for n in g['objects'] if n['title']=='Оценить ценность фрагмента')
        def choose(graph,ident):
            tx=str(uuid.uuid5(uuid.NAMESPACE_URL,'model-choice-'+ident))
            event={'id':str(uuid.uuid5(uuid.UUID(tx),'select')),'type':'requested','by':'assistant',
                   'note':'One synthetic fragment; do not write live data','recordedAt':'2026-11-13T12:00:00Z',
                   'verifiedTrustReceipt':{'mode':'test-only','transactionId':tx}}
            return P.PROFILES.apply(graph,{'schemaVersion':1,'expectedRevision':graph['revision'],
                'operations':[{'op':'graph_edit','action':'core_select','data':{'nodeId':ident},'event':event}]},True)[0]
        combined=g
        for suffix,ident in methods.items():
            self.assertEqual(ns[ident]['kind'],'decision')
            self.assertEqual(ns[ident]['selectionState'],'discovered')
            action='LS-STEP-MODEL-'+suffix
            self.assertTrue(any(e['type']=='REQUIRES_ACTION' and e['from']==ident and e['to']==action for e in g['edges']))
            focus=P.PROFILES.focused_view(g,ident)
            self.assertIn(ns[ident]['title'],'\n'.join(n.get('guidance','') for n in focus['entities']))
            canon_ids={e['from'] for e in g['edges'] if e['type']=='CANON_FOR' and e['to']==ident}
            self.assertGreaterEqual(len(canon_ids),4)
            self.assertEqual(value in canon_ids,suffix!='SKIP')
            if suffix=='SKIP':continue
            combined=choose(combined,ident)
            for first,second in ((ident,methods['SKIP']),(methods['SKIP'],ident)):
                selected=choose(g,first);before=copy.deepcopy(selected)
                with self.assertRaisesRegex(ValueError,'DECISION_GROUP_CONFLICT'):choose(selected,second)
                self.assertEqual(selected,before)
        self.assertTrue(all(P.entities(combined)[ident]['selectionState']=='selected' for suffix,ident in methods.items() if suffix!='SKIP'))
        self.assertNotIn('group:'+group['id'],P.PROFILES.completion_state(combined)['R-MODEL']['blockers'])
        skipped=choose(g,methods['SKIP'])
        self.assertNotIn('group:'+group['id'],P.PROFILES.completion_state(skipped)['R-MODEL']['blockers'])
        self.assertEqual(skipped['rootCauses'],g['rootCauses'])
        self.assertTrue(all(n.get('result',{}).get('truth')!='true' for n in P.entities(skipped).values()))

    def test_shared_theory_rejects_wrong_roles_and_keeps_one_canon_identity(self):
        plan,graphs,_=P.bundle(['model']);g=graphs['model'];p=copy.deepcopy(plan['model'])
        prefix,targets=p['sharedTheory'][0];p['sharedTheory'].append([prefix,targets])
        self.assertEqual(C.compile_one('model',p,g)[0],g)
        p['sharedTheory']=[[prefix,['R-MODEL']]]
        with self.assertRaisesRegex(ValueError,'SHARED_THEORY_TARGET_INVALID'):C.compile_one('model',p,g)
        p['sharedTheory']=[['Введение',['LS-METHOD-MODEL-R']]]
        with self.assertRaisesRegex(ValueError,'SHARED_THEORY_NOT_CANON'):C.compile_one('model',p,g)

    def test_retained_mappings_are_explicit_and_quality_focus_contains_the_method(self):
        plan,graphs,_=P.bundle()
        g=graphs['work'];ns=P.entities(g)
        self.assertIn('#определить-необходимость-plan',ns['A-WORK-PLAN']['description'])
        self.assertIn('Placement не выбирает Decision',ns['CANON-WORK-DECISION']['guidance'])
        plan_focus=P.PROFILES.focused_view(g,'A-WORK-PLAN')
        self.assertIn('Plan нужен', '\n'.join(n.get('guidance','') for n in plan_focus['entities']))
        for key,graph in graphs.items():
            for node in graph['objects']:
                if node['id'].startswith('INFO-DECISION-API-'):
                    self.assertEqual(node['title'],'Введение и границы · '+key)
        broken=copy.deepcopy(plan['work'])
        for _,ids in broken['assign']:
            if 'A-WORK-PLAN' in ids:ids.remove('A-WORK-PLAN')
        with self.assertRaisesRegex(ValueError,'RETAINED_SECTION_UNASSIGNED:work:A-WORK-PLAN'):
            C.compile_one('work',broken,g)
        focus=P.PROFILES.focused_view(graphs['lens-system'],'LS-STEP-LENS-SYSTEM-QUALITY')
        theory='\n'.join(n.get('guidance','') for n in focus['entities'])
        self.assertIn('Установить проверяемую редакцию',theory)
        self.assertIn('общие критерии качества',theory)
        self.assertIn('контрпример',theory)
        self.assertIn('аудита',theory)

    def test_an_editorial_intro_change_does_not_reauthor_unrelated_sections(self):
        from unittest.mock import patch
        key='research';plan,graphs,_=P.bundle([key]);path=ROOT/'docs/lenses/methods/research.md'
        text,source,sections=C.source_sections(path)
        before=C.compile_one(key,plan[key],graphs[key])[0]
        changed=text.replace('Редакция 2026-11-12.','Редакция 2026-11-13.',1)
        revised=copy.deepcopy(sections)
        revised[0]['text']=revised[0]['text'].replace('Редакция 2026-11-12.','Редакция 2026-11-13.',1)
        next_source={**source,'sha256':C.sha(changed.encode()),'gitCommit':None}
        with patch.object(C,'source_sections',return_value=(changed,next_source,revised)):
            after=C.compile_one(key,plan[key],before)[0]
        commands=P.delta_commands(before,after)
        changed_ids={data['nodeId'] for _,command,data in commands if command=='edit'}
        self.assertEqual(changed_ids,{'LS-TEXT-RESEARCH-e3b0c44298','LS-SOURCE-RESEARCH','LS-MAP-RESEARCH'})
        self.assertEqual(P.entities(after)['LS-SOURCE-RESEARCH']['value'],changed)
        mapping=json.loads(P.entities(after)['LS-MAP-RESEARCH']['value'])
        self.assertEqual(mapping['source']['sha256'],C.sha(changed.encode()))
        self.assertEqual([n for n in before['nodes']],[n for n in after['nodes']])

    def test_publication_includes_the_graph_title_and_root_pointer(self):
        desired=P.bundle(['research'])[1]['research'];old=copy.deepcopy(desired)
        old['title']='Stale lens title'
        self.assertEqual(P.delta_commands(old,desired),[('graph-title','graph_title',{'title':desired['title']})])
        with self.assertRaisesRegex(ValueError,'PUBLISHED_TITLE_MISMATCH'):P.verify_graph(old,desired)
        wrong_root=copy.deepcopy(desired);wrong_root['rootRequirementId']='Wrong root pointer'
        with self.assertRaisesRegex(ValueError,'PUBLISHED_ROOT_MISMATCH'):P.verify_graph(wrong_root,desired)

    def test_root_bases_are_part_of_the_publication_delta_and_readback(self):
        desired=P.bundle(['research'])[1]['research']
        for change in ('missing','reason','enabled'):
            with self.subTest(change=change):
                old=copy.deepcopy(desired)
                if change=='missing':old['rootCauses']=[]
                elif change=='reason':old['rootCauses'][0]['reason']='Previous basis'
                else:old['rootCauses'][0]['enabled']=False
                commands=P.delta_commands(old,desired)
                self.assertEqual([c[1] for c in commands],['root_cause'])
                self.assertEqual(commands[0][2],{'cause':desired['rootCauses'][0]})
                with self.assertRaisesRegex(ValueError,'PUBLISHED_ROOT_CAUSES_MISMATCH'):
                    P.verify_graph(old,desired)

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
    sources=F.PortableApplication.sources
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
                for ident in P.entities(row['graph']):
                    anchor='rdg-'+C.sha((row['graph']['identitySpace']+':'+ident).encode())[:24]
                    self.assertEqual(markdown['markdown'].count('<a id="'+anchor+'"></a>'),1,
                                     key+': one complete body for '+ident)
                self.assertTrue(app.call({'method':'receipt','packageId':pid,'transactionId':req['transactionId']})['published'])
        published={p['lensKey']:{'packageId':p['packageId'],'identitySpace':p['identitySpace'],
            'packageRevision':p['revision'],'graphRevision':p['lensCard']['source']['graphRevision']} for p in app.catalog()['packages']}
        state={'verified':published}
        def write(key,request):
            return app.call({'method':'apply','request':request,'expectedInputBinding':app.call({'method':'preflight','request':request})['inputBinding']})
        navigation=P.publish_navigation(app,graphs,state,write,lambda:None,lambda _:None)
        self.assertIn('work',navigation)
        review_pid=published['review']['packageId']
        tips=app.call({'method':'read','packageId':review_pid,'detail':'item','nodeId':'A-REVIEW-BUILD','include':['recommendations']})['data']['recommendations']['items']
        self.assertTrue(any('Применить KISS к способу проверки' in t['usageText'] and t['target']['available'] for t in tips))
        self.assertTrue(any('Явно запрошенный review' in t['usageText'] and t['target']['available'] for t in tips))
        self.assertTrue(any(any(ref['lensKey']=='research' for ref in rule['lensRefs']) for d in app.recommendation_catalog()['packages'] for rule in d['rules']))
        catalog=app.catalog();cards=[p['lensCard'] for p in catalog['packages']]
        self.assertEqual(len(cards),19);self.assertTrue(all(c['status']=='available' for c in cards))
        registry_revision=app.recommendation_catalog()['registryRevision']
        P.run(app,self.base/'partial-owner-upgrade.json',apply=True,keys=['model','work'],progress=lambda _:None)
        self.assertEqual(app.recommendation_catalog()['registryRevision'],registry_revision,
                         'updating two owners must not remove advice to other available lenses')

    def test_model_native_choices_upgrade_the_existing_owner_and_resume(self):
        app=self.app()
        old=json.loads(subprocess.check_output(['git','show','a360551841c993c9db528ac1eab49c0fd3053bb8:tools/rdg-agent-lenses/model-decision.json'],cwd=ROOT,text=True))
        req=app.schema('create',core_model='rdg-decision-v1',role='lens')['request']
        req.update(path='lenses/model',lensKey='model',title=old['title'],scope='Original model',rootReason='Source fixture',graph=old)
        pid=app.request(req)['packages'][0]['packageId'];before=app.read(pid)
        ref=before['references']['R-MODEL'];pin={k:ref[k] for k in ('packageId','identitySpace','graphRevision','sha256')}
        journal=self.base/'native-model-upgrade.json'
        result=P.run(app,journal,apply=True,keys=['model'],progress=lambda _:None)
        after=app.read(pid);desired=P.bundle(['model'])[1]['model']
        P.verify_graph(after['graph'],desired)
        self.assertEqual(result['verified']['model']['packageId'],pid)
        self.assertEqual(before['package']['identitySpace'],after['package']['identitySpace'])
        self.assertTrue(set(P.entities(before['graph']))<=set(P.entities(after['graph'])))
        self.assertEqual(app.source_snapshot(pid,pin)['graph'],before['graph'])
        self.assertIsNone(after['plan'])
        self.assertEqual(len(after['graph']['decisionGroups']),11)
        head=after['package']['revision']
        P.run(app,journal,apply=True,keys=['model'],progress=lambda _:None)
        self.assertEqual(app.read(pid)['package']['revision'],head)

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

    def test_reviewed_inventory_rejects_an_independent_edit_before_first_write(self):
        app=self.app();desired=P.bundle(['research'])[1]['research']
        old=copy.deepcopy(desired)
        next(n for n in old['objects'] if n['id']=='I-LENS-RESEARCH')['title']='Before reviewed update'
        req=app.schema('create',core_model='rdg-decision-v1',role='lens')['request']
        req.update(path='lenses/research',lensKey='research',title=old['title'],scope='Concurrent authors',rootReason='Acceptance',graph=old)
        pid=app.request(req)['packages'][0]['packageId']
        journal=self.base/'concurrent-author.json'
        P.run(app,journal,keys=['research'],progress=lambda _:None)
        edit=app.schema('paper_edit',pid,node_id='I-LENS-RESEARCH',command='edit')['request']
        edit.update(data={'nodeId':'I-LENS-RESEARCH','changes':{'title':'Independent author'},'cosmetic':False},note='Independent edit after reviewed inventory')
        app.request(edit);before=self.sources()
        with self.assertRaisesRegex(ValueError,'LENS_CHANGED_SINCE_REVIEW'):
            P.run(app,journal,apply=True,keys=['research'],progress=lambda _:None)
        self.assertEqual(self.sources(),before)
        self.assertEqual(P.entities(app.read(pid)['graph'])['I-LENS-RESEARCH']['title'],'Independent author')

    def rejected_preview_update(self):
        app=self.app();desired=P.bundle(['research'])[1]['research'];old=copy.deepcopy(desired)
        P.entities(old)['I-LENS-RESEARCH']['title']='Previous title'
        req=app.schema('create',core_model='rdg-decision-v1',role='lens')['request']
        req.update(path='lenses/research',lensKey='research',title=old['title'],scope='Rejected preview',rootReason='Acceptance',graph=old)
        pid=app.request(req)['packages'][0]['packageId'];journal=self.base/'rejected-preview.json'
        class RejectedPreview:
            def call(_,message):
                if message['method']=='apply':
                    error=ValueError('RDG_REMOTE_PORTABLE_APP_PREVIEW_INPUTS_CHANGED')
                    error.definite=True
                    raise error
                return app.call(message)
        before=app.read(pid)['graph']
        with self.assertRaisesRegex(RuntimeError,'LENS_PREVIEW_CHANGED_RETRY_SAME_REQUEST'):
            P.run(RejectedPreview(),journal,apply=True,keys=['research'],progress=lambda _:None)
        self.assertEqual(app.read(pid)['graph'],before)
        saved=P.JOURNAL.Journal(journal,{})
        operation=next(v for k,v in saved.state['operations'].items() if k.startswith(('research/edit-','research/batch/')))
        request=copy.deepcopy(operation['request']);saved.checkpoint()
        return app,pid,journal,desired,request

    def test_definite_preview_rejection_reuses_the_exact_request_after_new_preflight(self):
        app,pid,journal,desired,request=self.rejected_preview_update()
        state=P.run(app,journal,apply=True,keys=['research'],progress=lambda _:None)
        P.verify_graph(app.read(pid)['graph'],desired)
        operation=next(v for k,v in state['operations'].items() if k.startswith(('research/edit-','research/batch/')))
        self.assertEqual(operation['request'],request)
        self.assertEqual(len(operation['rejections']),1)
        self.assertTrue(operation['receipt']['published'])
        revision=app.read(pid)['package']['revision']
        self.assertTrue(app.request(request)['idempotent'])
        self.assertEqual(app.read(pid)['package']['revision'],revision)

    def test_definite_preview_retry_keeps_cas_against_a_later_independent_edit(self):
        app,pid,journal,_,_=self.rejected_preview_update()
        req=app.schema('paper_edit',pid,node_id='I-LENS-RESEARCH',command='edit')['request']
        req.update(data={'nodeId':'I-LENS-RESEARCH','changes':{'title':'Independent title'},'cosmetic':False},note='Independent edit before exact retry')
        app.request(req);before={k:v for k,v in self.sources().items() if k!=journal.name}
        with self.assertRaisesRegex(ValueError,'PACKAGE_CAS_MISMATCH'):
            P.run(app,journal,apply=True,keys=['research'],progress=lambda _:None)
        self.assertEqual({k:v for k,v in self.sources().items() if k!=journal.name},before)

    def interrupted_update(self,legacy=False):
        app=self.app();desired=P.bundle(['research'])[1]['research'];old=copy.deepcopy(desired)
        for ident in ('I-LENS-RESEARCH','LS-STEP-RESEARCH-QUESTION'):
            P.entities(old)[ident]['title']='Previous '+ident
        req=app.schema('create',core_model='rdg-decision-v1',role='lens')['request']
        req.update(path='lenses/research',lensKey='research',title=old['title'],scope='Interrupted update',rootReason='Acceptance',graph=old)
        pid=app.request(req)['packages'][0]['packageId'];journal=self.base/'interrupted-update.json'
        class LostReply:
            def call(_,message):
                if legacy and message['method']=='capabilities':raise ValueError('PORTABLE_APP_MESSAGE_FIELDS')
                result=app.call(message)
                if message['method']=='apply':raise TimeoutError('Lost accepted authoring reply')
                return result
        with self.assertRaisesRegex(RuntimeError,'UNCERTAIN_LENS_OPERATION_SAVED'):
            P.run(LostReply(),journal,apply=True,keys=['research'],progress=lambda _:None)
        return app,pid,journal,desired

    def test_interrupted_update_advances_only_through_its_own_receipts(self):
        app,pid,journal,desired=self.interrupted_update()
        state=P.run(app,journal,apply=True,keys=['research'],progress=lambda _:None)
        P.verify_graph(app.read(pid)['graph'],desired)
        first=next(op for key,op in state['operations'].items() if key.startswith(('research/edit-','research/batch/')))
        self.assertTrue(first['receipt']['published'])
        self.assertTrue(first['result']['reconciledFromReceipt'])
        revision=app.read(pid)['package']['revision']
        self.assertTrue(app.request(first['request'])['idempotent'])
        self.assertEqual(app.read(pid)['package']['revision'],revision)

    def test_legacy_journal_continues_original_individual_requests(self):
        app,pid,journal,desired=self.interrupted_update(legacy=True)
        saved=P.JOURNAL.Journal(journal,{})
        original=next(op['request'] for key,op in saved.state['operations'].items() if key.startswith('research/edit-'))
        original=copy.deepcopy(original);saved.checkpoint()
        state=P.run(app,journal,apply=True,keys=['research'],progress=lambda _:None)
        self.assertFalse(any('/batch/' in key for key in state['operations']))
        self.assertTrue(any(op.get('request')==original and op.get('result',{}).get('reconciledFromReceipt')
                            for op in state['operations'].values()))
        P.verify_graph(app.read(pid)['graph'],desired)

    def test_uncertain_batch_receipt_is_checked_before_legacy_protocol_fallback(self):
        app,pid,journal,desired=self.interrupted_update()
        calls=[]
        class OldContract:
            def call(_,message):
                calls.append(copy.deepcopy(message))
                if message['method']=='capabilities':raise ValueError('PORTABLE_APP_MESSAGE_FIELDS')
                if message['method']=='apply' and message['request']['op'] in ('paper_edit','batch'):raise AssertionError('Accepted batch must recover through its original receipt')
                return app.call(message)
        state=P.run(OldContract(),journal,apply=True,keys=['research'],progress=lambda _:None)
        P.verify_graph(app.read(pid)['graph'],desired)
        self.assertTrue(any(m['method']=='receipt' for m in calls))
        self.assertFalse(any(k.startswith('research/edit-') for k in state['operations']))
        self.assertTrue(any(k.startswith('research/batch/') and v['result'].get('reconciledFromReceipt')
                            for k,v in state['operations'].items()))

    def test_interrupted_update_preserves_a_later_independent_edit(self):
        app,pid,journal,_=self.interrupted_update()
        req=app.schema('paper_edit',pid,node_id='I-LENS-RESEARCH',command='edit')['request']
        req.update(data={'nodeId':'I-LENS-RESEARCH','changes':{'title':'Later independent author'},'cosmetic':False},note='Independent edit during interrupted authoring')
        app.request(req);before={k:v for k,v in self.sources().items() if k!=journal.name}
        with self.assertRaisesRegex(ValueError,'LENS_CHANGED_SINCE_REVIEW'):
            P.run(app,journal,apply=True,keys=['research'],progress=lambda _:None)
        self.assertEqual({k:v for k,v in self.sources().items() if k!=journal.name},before)

    def test_graph_title_upgrade_preserves_owner_entities_and_historical_pin(self):
        app=self.app();desired=P.bundle(['research'])[1]['research'];old=copy.deepcopy(desired)
        old['title']='Previous published title'
        req=app.schema('create',core_model='rdg-decision-v1',role='lens')['request']
        req.update(path='lenses/research',lensKey='research',title=old['title'],scope='Title upgrade',rootReason='Acceptance',graph=old)
        pid=app.request(req)['packages'][0]['packageId'];before=app.read(pid)
        calls=[]
        class CountingClient:
            def call(_,message):
                calls.append(copy.deepcopy(message));return app.call(message)
        state=P.run(CountingClient(),self.base/'title-upgrade.json',apply=True,keys=['research'],progress=lambda _:None)
        self.assertFalse(any(m.get('method')=='read' and m.get('detail')=='full' for m in calls))
        self.assertEqual(sum(m.get('method')=='apply' and m.get('request',{}).get('op')=='batch' for m in calls),1)
        after=app.read(pid);P.verify_graph(after['graph'],desired)
        self.assertEqual(after['graph']['title'],desired['title'])
        self.assertEqual(after['package']['identitySpace'],before['package']['identitySpace'])
        self.assertEqual(P.entities(after['graph']),P.entities(before['graph']))
        self.assertEqual(state['verified']['research']['packageId'],pid)
        ref=before['references'][old['rootRequirementId']]
        self.assertEqual(app.source_snapshot(pid,{k:ref[k] for k in ('packageId','identitySpace','graphRevision','sha256')})['graph'],before['graph'])

    def test_root_basis_upgrade_uses_the_existing_writer(self):
        app=self.app();desired=P.bundle(['research'])[1]['research'];old=copy.deepcopy(desired)
        old['rootCauses']=[]
        req=app.schema('create',core_model='rdg-decision-v1',role='lens')['request']
        req.update(path='lenses/research',lensKey='research',title=old['title'],scope='Root basis upgrade',rootReason='Acceptance',graph=old)
        pid=app.request(req)['packages'][0]['packageId']
        state=P.run(app,self.base/'root-upgrade.json',apply=True,keys=['research'],progress=lambda _:None)
        self.assertEqual(state['verified']['research']['packageId'],pid)
        self.assertEqual(app.read(pid)['graph']['rootCauses'],desired['rootCauses'])

    def test_group_upgrade_uses_the_existing_atomic_membership_command(self):
        app=self.app();desired=P.bundle(['preserve'])[1]['preserve'];old=copy.deepcopy(desired)
        old['decisionGroups']=[]
        for ident in ('A-PRESERVE-DRAW','A-PRESERVE-SKIP'):
            old['edges'].append({'id':'D-'+ident,'type':'DRIVES','from':old['rootRequirementId'],'to':ident})
        req=app.schema('create',core_model='rdg-decision-v1',role='lens')['request']
        req.update(path='lenses/preserve',lensKey='preserve',title=old['title'],scope='Synthetic preserve upgrade',rootReason='Acceptance',graph=old)
        result=app.request(req);pid=result['packages'][0]['packageId'];before=app.read(pid)
        commands=P.delta_commands(old,desired)
        self.assertEqual([c[1] for c in commands],['decision_group'])
        state=P.run(app,self.base/'group-upgrade.json',apply=True,keys=['preserve'],progress=lambda _:None)
        after=app.read(pid)
        P.verify_graph(after['graph'],desired)
        self.assertEqual(state['verified']['preserve']['packageId'],pid)
        self.assertEqual(after['package']['identitySpace'],before['package']['identitySpace'])
        self.assertEqual(after['graph']['decisionGroups'],desired['decisionGroups'])
        self.assertFalse(any(e['type']=='DRIVES' and e['to'] in ('A-PRESERVE-DRAW','A-PRESERVE-SKIP') for e in after['graph']['edges']))
        ref=before['references'][old['rootRequirementId']]
        historical=app.source_snapshot(pid,{k:ref[k] for k in ('packageId','identitySpace','graphRevision','sha256')})
        self.assertEqual(historical['graph'],before['graph'])

    def test_reviewed_inventory_preserves_an_independent_navigation_edit(self):
        app=self.app();P.run(app,self.base/'nav-initial.json',apply=True,keys=['model','work'],progress=lambda _:None)
        journal=self.base/'nav-reviewed.json';P.run(app,journal,keys=['work'],progress=lambda _:None)
        registry=app.recommendation_catalog(query='lens-source-work')
        definition=copy.deepcopy(registry['packages'][0]);definition['revision']+=1
        definition['rules'][0]['usageText']='Independent author after reviewed inventory'
        app.request({'op':'recommendation_edit','transactionId':str(uuid.uuid4()),'action':'edit','packageId':definition['id'],
                     'expectedRegistryRevision':registry['registryRevision'],'definition':definition,'note':'Independent author'})
        before={k:v for k,v in self.sources().items() if k!=journal.name}
        with self.assertRaisesRegex(ValueError,'NAVIGATION_CHANGED_SINCE_REVIEW'):
            P.run(app,journal,apply=True,keys=['work'],revise_navigation=True,progress=lambda _:None)
        self.assertEqual({k:v for k,v in self.sources().items() if k!=journal.name},before)

    def test_navigation_attachment_keeps_the_verified_graph_base(self):
        from unittest.mock import patch
        app=self.app();original=P.publish_navigation;observed={}
        def independent_edit(client,graphs,state,write,save,progress,**options):
            pid=state['verified']['model']['packageId'];root=graphs['model']['rootRequirementId']
            request=app.schema('paper_edit',pid,node_id=root,command='edit')['request']
            request.update(data={'nodeId':root,'changes':{'description':'Independent edit before attachment'},'cosmetic':False},note='Independent author')
            app.request(request);observed.update(packageId=pid,registryRevision=app.recommendation_catalog()['registryRevision'])
            return original(client,graphs,state,write,save,progress,**options)
        with patch.object(P,'publish_navigation',side_effect=independent_edit):
            with self.assertRaisesRegex(ValueError,'LENS_CHANGED_SINCE_REVIEW'):
                P.run(app,self.base/'attach-race.json',apply=True,keys=['model','work'],progress=lambda _:None)
        self.assertEqual(app.recommendation_catalog()['registryRevision'],observed['registryRevision'])
        graph=app.read(observed['packageId'])['graph']
        self.assertEqual(P.entities(graph)[graph['rootRequirementId']]['description'],'Independent edit before attachment')
        self.assertEqual(graph['recommendationPackageIds'],[])

    def test_lost_navigation_create_reply_resumes_from_its_original_receipt(self):
        app=self.app();journal=self.base/'nav-create-lost.json'
        class LostNavigationCreate:
            def call(_,message):
                result=app.call(message)
                if message['method']=='apply' and message['request'].get('op')=='recommendation_edit':
                    raise TimeoutError('Lost accepted navigation create reply')
                return result
        with self.assertRaisesRegex(RuntimeError,'UNCERTAIN_LENS_OPERATION_SAVED'):
            P.run(LostNavigationCreate(),journal,apply=True,keys=['model','work'],progress=lambda _:None)
        registry=app.recommendation_catalog()
        later=copy.deepcopy(registry['packages'][0]);later['revision']+=1
        app.request({'op':'recommendation_edit','transactionId':str(uuid.uuid4()),'action':'edit','packageId':later['id'],
                     'expectedRegistryRevision':registry['registryRevision'],'definition':later,'note':'Independent same-content version'})
        registry_revision=app.recommendation_catalog()['registryRevision']
        state=P.run(app,journal,apply=True,keys=['model','work'],progress=lambda _:None)
        op=next(v for k,v in state['operations'].items() if k.endswith('/navigation'))
        self.assertTrue(op['receipt']['published'])
        self.assertTrue(op['result']['reconciledFromReceipt'])
        self.assertTrue(app.request(op['request'])['idempotent'])
        self.assertEqual(app.recommendation_catalog()['registryRevision'],registry_revision+1)

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

    def test_reviewed_navigation_upgrade_keeps_identity_and_requires_next_revision(self):
        from unittest.mock import patch
        app=self.app();journal=self.base/'navigation-upgrade.json'
        state=P.run(app,journal,apply=True,keys=['model','work'],progress=lambda _:None)
        definitions=P.navigation_definitions(P.bundle(['model','work'])[1],state['verified'])
        definition=copy.deepcopy(definitions['work']);definition['revision']+=1
        definition['rules'][0]['usageText']='Reviewed context for the current lens'
        def write(key,req):return app.request(req)
        with patch.object(P,'navigation_definitions',return_value={'work':definition}):
            with self.assertRaisesRegex(ValueError,'NAVIGATION_DEFINITION_EXISTS_REVIEW_NEW_VERSION'):
                P.publish_navigation(app,P.bundle(['model','work'])[1],state,write,lambda:None,lambda _:None)
            P.publish_navigation(app,P.bundle(['model','work'])[1],state,write,lambda:None,lambda _:None,revise_navigation=True)
        actual=next(d for d in app.recommendation_catalog()['packages'] if d['id']==definition['id'])
        self.assertEqual(actual,definition)
        self.assertEqual(state['reviewedNavigationBefore']['work'],definitions['work'])
        self.assertEqual(len([d for d in app.recommendation_catalog()['packages'] if d['key']==definition['key']]),1)

    def test_lost_registry_reply_resumes_without_reapplying_the_accepted_edit(self):
        from unittest.mock import patch
        app=self.app()
        state=P.run(app,self.base/'nav-first.json',apply=True,keys=['model','work'],progress=lambda _:None)
        definition=copy.deepcopy(P.navigation_definitions(P.bundle(['model','work'])[1],state['verified'])['work'])
        definition['revision']+=1;definition['rules'][0]['usageText']='Reviewed change with a lost reply'
        journal=self.base/'nav-lost-reply.json'
        class LostRegistryReply:
            def call(_,message):
                result=app.call(message)
                if message['method']=='apply' and message['request'].get('op')=='recommendation_edit':
                    raise TimeoutError('Lost accepted registry reply')
                return result
        with patch.object(P,'navigation_definitions',return_value={'work':definition}):
            with self.assertRaisesRegex(RuntimeError,'UNCERTAIN_LENS_OPERATION_SAVED'):
                P.run(LostRegistryReply(),journal,apply=True,keys=['model','work'],revise_navigation=True,progress=lambda _:None)
            revision=app.recommendation_catalog()['registryRevision']
            result=P.run(app,journal,apply=True,keys=['model','work'],revise_navigation=True,progress=lambda _:None)
        self.assertEqual(app.recommendation_catalog()['registryRevision'],revision)
        operation=result['operations']['work/navigation-v'+str(definition['revision'])]
        self.assertTrue(operation['receipt']['publicationCertificatePresent'])
        self.assertTrue(operation['result']['reconciledFromReceipt'])
        self.assertEqual(operation['receipt']['requestSHA256'],P.MODEL.digest(operation['request']))
        self.assertEqual(next(d for d in app.recommendation_catalog()['packages'] if d['id']==definition['id']),definition)
        later=copy.deepcopy(definition);later['revision']+=1;later['rules'][0]['usageText']='Later independent edit'
        app.request({'op':'recommendation_edit','transactionId':str(uuid.uuid4()),'action':'edit','packageId':later['id'],
                     'expectedRegistryRevision':revision,'definition':later,'note':'Synthetic independent author'})
        revision=app.recommendation_catalog()['registryRevision']
        with patch.object(P,'navigation_definitions',return_value={'work':definition}):
            with self.assertRaisesRegex(ValueError,'NAVIGATION_CHANGED_SINCE_REVIEW'):
                P.run(app,journal,apply=True,keys=['model','work'],revise_navigation=True,progress=lambda _:None)
        self.assertEqual(app.recommendation_catalog()['registryRevision'],revision)
        self.assertEqual(next(d for d in app.recommendation_catalog()['packages'] if d['id']==definition['id']),later)

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
