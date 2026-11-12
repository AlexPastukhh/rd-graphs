#!/usr/bin/env python3
"""API forms and Agent discovery against isolated real Application owners."""
from importlib.machinery import SourceFileLoader
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('discovery_service_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
A=SourceFileLoader('discovery_agent',str(ROOT/'tools/rdg-agent.py')).load_module()


class APIDiscovery(unittest.TestCase):
    setUp=T.PortableApplication.setUp
    config=T.PortableApplication.config
    app=T.PortableApplication.app
    req=T.PortableApplication.req
    sources=T.PortableApplication.sources
    current=T.PortableApplication.current
    command_request=T.PortableApplication.command_request
    command=T.PortableApplication.command
    finding_package=T.PortableApplication.finding_package

    def create(self,role='working'):
        app=self.app();form=app.call({'method':'schema','op':'create','coreModel':'rdg-decision-v1','role':role})
        request=form['request'];request.update(path=role+'/discovery',title='API discovery',scope='Synthetic scope',rootReason='Synthetic API acceptance')
        if role=='lens':request['lensKey']='discovery'
        before=self.sources();preview=app.call({'method':'preflight','request':request});self.assertEqual(self.sources(),before)
        result=app.call({'method':'apply','request':request,'expectedInputBinding':preview['inputBinding']})
        return result['packages'][0]['packageId']

    def form(self,ident,command,node='R1',**selectors):
        return self.app().call({'method':'schema','op':'core','packageId':ident,'command':command,'nodeId':node,**selectors})


    def catalog_info(self, ident, purpose='Choose a useful method', triggers='When a fact is unknown', tags=None):
        request=self.app().call({'method':'schema','op':'paper_edit','packageId':ident,
            'command':'add','nodeId':'R1','entityKind':'info'})['request']
        entity=request['data']['entity']
        entity.update(title='Catalog guidance',description=purpose,value=triggers,
                      tags=tags or ['rdg:lens-catalog'])
        request['note']='Author catalog content in the owning definition'
        before=self.sources()
        preview=self.app().call({'method':'preflight','request':request})
        self.assertEqual(before,self.sources())
        self.app().call({'method':'apply','request':request,'expectedInputBinding':preview['inputBinding']})
        return entity['id']

    def test_lens_catalog_returns_owned_card_and_complete_snapshot_without_writes(self):
        ident=self.create('lens');app=self.app()
        node=self.catalog_info(ident)
        self.catalog_info(ident,'Before choosing a method','Research stage of work',['rdg:lens-workflow'])
        before=self.sources();catalog=app.call({'method':'catalog'})
        self.assertTrue(catalog['complete']);self.assertEqual(len(catalog['catalogSHA256']),64)
        row=next(x for x in catalog['packages'] if x['packageId']==ident)
        card=row['lensCard'];self.assertEqual(card['status'],'available')
        self.assertEqual(card['purpose'],'Choose a useful method')
        self.assertEqual(card['appliesWhen'],'When a fact is unknown')
        graph=app.read(ident)['graph']
        self.assertEqual(card['source']['graphSHA256'],T.P.digest(graph))
        self.assertEqual(card['source']['graphRevision'],graph['revision'])
        self.assertEqual(card['sourceRef']['nodeId'],node)
        self.assertEqual(card['workflow']['text'],'Research stage of work')
        with patch.object(A,'portable_application',return_value=app):
            listed=A.portable_command(SimpleNamespace(command='lenses',package_id=None,
                expected_input_binding=None,format='json'),{'profile':'portable'})
        self.assertEqual(listed['lenses'][0]['lensCard'],card)
        self.assertEqual(listed['catalogSHA256'],catalog['catalogSHA256'])
        self.assertEqual(self.sources(),before)

    def test_lens_catalog_missing_and_ambiguous_metadata_never_borrows_drafts(self):
        ident=self.create('lens');app=self.app()
        before=self.sources()
        card=app.call({'method':'catalog'})['packages'][0]['lensCard']
        self.assertEqual(card['status'],'missing');self.assertIsNone(card['purpose'])
        self.assertEqual(self.sources(),before)
        self.catalog_info(ident);self.catalog_info(ident,'Another purpose','Different conditions')
        before=self.sources();card=app.call({'method':'catalog'})['packages'][0]['lensCard']
        self.assertEqual(card['status'],'invalid');self.assertIsNone(card['purpose'])
        self.assertEqual(self.sources(),before)

    def test_lens_catalog_schema_and_changed_revision_are_readable(self):
        ident=self.create('lens');app=self.app()
        form=app.call({'method':'schema','op':'catalog'})
        self.assertFalse(form['pagination'])
        self.assertEqual(form['lensCard']['authoring']['tags'],['rdg:lens-catalog'])
        with self.assertRaisesRegex(ValueError,'CATALOG_SCHEMA_SELECTORS'):
            app.call({'method':'schema','op':'catalog','packageId':ident})
        old=app.call({'method':'catalog'})
        self.catalog_info(ident,'Explain intent','When intent is unclear')
        new=app.call({'method':'catalog'})
        self.assertNotEqual(old['catalogSHA256'],new['catalogSHA256'])
        self.assertGreater(new['packages'][0]['lensCard']['source']['graphRevision'],
                           old['packages'][0]['lensCard']['source']['graphRevision'])


    def test_catalog_authorization_precedes_card_projection_and_working_owners_stay_unchanged(self):
        ident=self.create('lens');app=self.app()
        self.catalog_info(ident,'Private purpose','Private trigger')
        original=app.authorize
        def authorize(package,permissions,path=None):
            if package==ident:raise ValueError('Denied by fixture grant')
            return original(package,permissions,path)
        before=self.sources()
        with patch.object(app,'authorize',side_effect=authorize), patch.object(app,'_lens_catalog_card',wraps=app._lens_catalog_card) as project:
            listed=app.call({'method':'catalog'})
            self.assertEqual(listed['packages'],[])
            project.assert_not_called()
        self.assertEqual(self.sources(),before)
        working=self.create()
        row=next(r for r in app.call({'method':'catalog'})['packages'] if r['packageId']==working)
        self.assertNotIn('lensCard',row)

    def test_legacy_lens_with_a_known_key_reports_missing_without_importing_source_catalog(self):
        app=self.app()
        request=self.req('create',path='lens/legacy-catalog',role='lens',lensKey='work',
            title='Legacy work definition',graph=T.PortableApplication.graph(self,'legacy-catalog',paper=True))
        ident=app.request(request)['packages'][0]['packageId']
        before=self.sources()
        row=next(r for r in app.call({'method':'catalog'})['packages'] if r['packageId']==ident)
        self.assertEqual(row['lensCard']['status'],'missing')
        self.assertIsNone(row['lensCard']['purpose'])
        self.assertEqual(self.sources(),before)

    def test_create_selectors_are_explicit_and_legacy_schema_is_preserved(self):
        app=self.app();before=self.sources()
        legacy=app.call({'method':'schema','op':'create'})
        self.assertEqual((legacy['request']['coreModel'],legacy['request']['role']),('rdg-core-v1','ready'))
        primary=app.call({'method':'schema','op':'create','coreModel':'rdg-decision-v1'})
        self.assertEqual((primary['request']['coreModel'],primary['request']['role']),('rdg-decision-v1','working'))
        self.assertEqual(primary['request']['rootReason'],'');self.assertIn('rootReason',primary['requiredInput'])
        self.assertIn('decision_group',primary['coreCommands']);self.assertNotIn('resolve_finding',primary['coreCommands'])
        lens=app.call({'method':'schema','op':'create','coreModel':'rdg-decision-v1','role':'lens'})
        self.assertIn('lensKey',lens['requiredInput'])
        for selectors in ({'coreModel':'unknown'},{'role':'copy'},{'entityKind':'decision'}):
            with self.assertRaises(ValueError):app.call({'method':'schema','op':'create',**selectors})
        self.assertEqual(self.sources(),before)

    def test_batch_discovery_matches_each_owner_role(self):
        app=self.app()
        owners={role:self.create(role) for role in ('working','ready','lens')}
        request=app.schema('copy',owners['working'])['request']
        request.update(path='copy/discovery',note='Copy for role discovery')
        owners['copy']=app.request(request)['packages'][0]['packageId']
        before=self.sources()
        for role,ident in owners.items():
            with self.subTest(role=role):
                working=role in ('working','copy')
                view=app.read(ident)
                for feature in ('atomicBatch','planningMetaAction','plan','planOrderOnly','planForks',
                                'templateApply','externalReferences','questionApiSlice','questionMigration'):
                    self.assertEqual(view['capabilities']['capabilities'][feature],working,feature)
                self.assertEqual(view['capabilities']['batch']['available'],working)
                self.assertEqual(view['capabilities']['batch']['supportedRoles'],['working','copy'])
                command='core' if working else 'paper_edit'
                form=app.schema(command,ident,node_id=view['graph']['rootRequirementId'],command='edit')
                self.assertEqual(form['capabilities']['capabilities']['atomicBatch'],working)
                if working:
                    batch=app.schema('batch',ident)
                    self.assertTrue(batch['capabilities']['capabilities']['atomicBatch'])
                else:
                    with self.assertRaisesRegex(ValueError,'BATCH_PROFILE'):
                        app.schema('batch',ident)
        self.assertEqual(self.sources(),before)

    def test_every_advertised_decision_command_has_a_readonly_form(self):
        ident,subject=self.finding_package();app=self.app();view=app.read(ident);before=self.sources()
        targets={'finding_transfer':'FINDING','finding_disposition':'FINDING','select':subject,'withdraw':subject,'decision_context':subject}
        for command in view['capabilities']['coreCommands']:
            with self.subTest(command=command):
                form=self.form(ident,command,targets.get(command,'R1'))
                self.assertEqual(form['request']['command'],command)
                self.assertEqual(form['request']['expectedGraphRevision'],view['graph']['revision'])
        self.assertEqual(self.sources(),before)

    def test_typed_add_forms_publish_each_current_kind_with_receipts_and_exact_retry(self):
        ident=self.create();app=self.app();decision=None;created={}
        for kind in ('requirement','decision','action','canon','context','info','finding'):
            with self.subTest(kind=kind):
                form=self.form(ident,'add',decision if kind in ('canon','context','info','finding') else 'R1',entityKind=kind)
                request=form['request'];data=request['data'];entity=data['entity'];request['note']='Create synthetic '+kind
                entity.update(title='Synthetic '+kind,description='API form acceptance')
                if kind in ('context','info'):entity['value']='Observed synthetic data'
                if kind=='canon':entity['guidance']='Check the applicable requirement'
                if kind=='finding':entity.update(findingType='risk',rationale='A specific future failure mechanism')
                if kind=='decision':decision=entity['id']
                created[kind]=entity['id'];before=self.sources()
                preview=app.call({'method':'preflight','request':request});self.assertEqual(before,self.sources())
                result=app.call({'method':'apply','request':request,'expectedInputBinding':preview['inputBinding']})
                self.assertTrue(result['published'])
                self.assertTrue(app.call({'method':'receipt','packageId':ident,'transactionId':request['transactionId']})['found'])
                self.assertTrue(app.call({'method':'apply','request':request})['idempotent'])
        view=app.read(ident);ns=app.kernel.entities(view['graph'])
        self.assertEqual(ns[decision]['selectionState'],'discovered')
        self.assertEqual(ns[created['finding']]['subjectId'],decision)
        self.assertEqual(ns[created['finding']]['disposition']['code'],'unresolved')
        self.assertEqual(view['decisionContexts'][decision],[], 'creating Context alone does not invent a role')
        self.assertEqual(set(created.values()),{n['id'] for n in view['graph']['nodes']+view['graph']['objects']}-{'R1'})

    def test_form_selectors_and_invalid_subject_do_not_bypass_the_writer(self):
        ident=self.create();before=self.sources()
        for command,selectors in [('add',{'entityKind':'evidence'}),('add',{'entityKind':'arbitrary'}),('edit',{'entityKind':'context'}),('add',{'coreModel':'rdg-core-v1'}),('add',{'role':'lens'})]:
            with self.subTest(command=command,selectors=selectors),self.assertRaises(ValueError):self.form(ident,command,**selectors)
        request=self.form(ident,'add',entityKind='finding')['request']
        request['note']='Invalid requirement subject';request['data']['entity'].update(title='Invalid subject',subjectId='R1',findingType='risk',rationale='Synthetic')
        for method in ('preflight','apply'):
            with self.assertRaisesRegex(ValueError,'FINDING_SUBJECT_REQUIRED'):self.app().call({'method':method,'request':request})
        self.assertEqual(before,self.sources())

    def test_paper_capabilities_only_offer_paper_commands_and_current_types(self):
        ident=self.create('lens');app=self.app();view=app.read(ident);before=self.sources()
        self.assertNotIn('select',view['capabilities']['coreCommands']);self.assertNotIn('finding',view['capabilities']['entityKinds'])
        for command in view['capabilities']['coreCommands']:
            form=app.call({'method':'schema','op':'paper_edit','packageId':ident,'command':command,'nodeId':'R1'})
            self.assertEqual(form['request']['op'],'paper_edit')
        for message in ({'op':'core','command':'add'},{'op':'paper_edit','command':'select'},
                        {'op':'paper_edit','command':'add','entityKind':'finding'}):
            with self.assertRaises(ValueError):app.call({'method':'schema','packageId':ident,**message})
        self.assertEqual(before,self.sources())

    def test_graph_title_uses_the_common_writer_and_preserves_entities_in_every_role(self):
        app=self.app();working=None
        for role in ('working','ready','lens','copy'):
            with self.subTest(role=role):
                if role=='copy':
                    req=app.schema('copy',working)['request'];req.update(path='copies/title',note='Copy title fixture')
                    ident=app.request(req)['packages'][0]['packageId']
                else:
                    ident=self.create(role)
                    if role=='working':working=ident
                before=app.read(ident);operation='paper_edit' if role in ('ready','lens') else 'core'
                req=app.schema(operation,ident,command='graph_title')['request']
                req.update(data={'title':'Updated '+role+' title'},note='Rename the owning Graph only')
                files=self.sources();preview=app.call({'method':'preflight','request':req})
                self.assertEqual(self.sources(),files)
                self.assertEqual(preview['effects']['graphTitleChange'],{'before':before['graph']['title'],'after':req['data']['title']})
                result=app.call({'method':'apply','request':req,'expectedInputBinding':preview['inputBinding']})
                self.assertTrue(result['published'])
                after=app.read(ident)
                self.assertEqual(after['graph']['title'],req['data']['title'])
                self.assertEqual(next(p for p in app.catalog()['packages'] if p['packageId']==ident)['title'],req['data']['title'])
                self.assertIn(req['data']['title'],app.call({'method':'read','packageId':ident,'format':'markdown'})['markdown'])
                self.assertEqual(app.kernel.entities(after['graph']),app.kernel.entities(before['graph']))
                self.assertEqual(after['graph']['identitySpace'],before['graph']['identitySpace'])
                self.assertEqual(after['plan'],before['plan'])
                self.assertTrue(app.call({'method':'receipt','packageId':ident,'transactionId':req['transactionId']})['published'])
                self.assertTrue(app.call({'method':'apply','request':req})['idempotent'])
                stale=app.schema(operation,ident,command='graph_title')['request']
                stale.update(data={'title':'Stale overwrite'},note='Stale title intent')
                edit=app.schema(operation,ident,command='edit')['request'];root=after['graph']['rootRequirementId']
                edit.update(data={'nodeId':root,'changes':{'description':'Independent edit '+role},'cosmetic':False},note='Independent edit')
                app.request(edit);files=self.sources()
                with self.assertRaisesRegex(ValueError,'CAS'):app.request(stale)
                self.assertEqual(self.sources(),files)
                history=app.history(ident,{'kind':'graph','historyMode':'all'})
                if role in ('working','copy'):
                    event=next(e for e in history['events'] if e['event'].get('historyDetail',{}).get('command')=='graph_title')
                    self.assertEqual(event['event']['historyDetail']['edits'][0]['after'],req['data']['title'])
                    self.assertEqual(event['historyView']['level'],'technical')

    def test_graph_title_handles_rootless_paper_and_respects_existing_root_locks(self):
        import copy,uuid
        app=self.app();kernel=app.kernel.for_profile('rdg-decision-v1')
        graph=kernel.blank('title-fixture','Original graph title',str(uuid.uuid4()),'R1','Root','Explicit scope','Fixture basis')
        for locked in (False,True):
            candidate=copy.deepcopy(graph)
            if locked:
                candidate['nodes'][0]['locks']={'edit':{'mode':'hard','principals':['owner-fixture'],'message':'Keep the root edit lock'}}
            else:candidate.update(rootRequirementId=None,rootCauses=[])
            req=app.schema('create',core_model='rdg-decision-v1',role='ready')['request']
            req.update(path='ready/title-'+str(locked),title=candidate['title'],scope='Title guards',rootReason='Acceptance',graph=candidate)
            ident=app.request(req)['packages'][0]['packageId']
            change=app.schema('paper_edit',ident,command='graph_title')['request']
            change.update(data={'title':'Updated graph title'},note='Graph title guard acceptance')
            before=self.sources()
            if locked:
                for method in ('preflight','apply'):
                    with self.assertRaisesRegex(ValueError,'OBJECT_OPERATION_LOCK_REQUIRED'):app.call({'method':method,'request':change})
                self.assertEqual(self.sources(),before)
            else:
                app.request(change)
                self.assertEqual(app.read(ident)['graph']['title'],'Updated graph title')
                self.assertIsNone(app.read(ident)['graph']['rootRequirementId'])

    def test_form_request_keeps_cas_and_rejected_changes_are_atomic(self):
        ident=self.create()
        stale=self.form(ident,'edit')['request'];stale['note']='Stale intent'
        self.command(ident,'edit',nodeId='R1',changes={'title':'Later title'},cosmetic=True)
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'CAS'):self.app().call({'method':'apply','request':stale})
        self.assertEqual(before,self.sources())

    def test_agent_read_commands_use_the_application_route_without_a_graph_read(self):
        messages=[]
        class Client:
            def call(self,msg):messages.append(msg);return {'method':msg['method']}
        args=SimpleNamespace(package_id='owner',expected_input_binding=None,node=None,history_mode='technical')
        for command in ('dependencies','locks','history'):
            args.command=command;messages.clear()
            with patch.object(A,'portable_application',return_value=Client()):result=A.portable_command(args,{'profile':'gateway'})
            self.assertEqual(result['method'],command);self.assertEqual(len(messages),1)
            if command=='history':self.assertEqual(messages[0]['view']['historyMode'],'technical')
        args.command='history';args.node='D1';messages.clear()
        with patch.object(A,'portable_application',return_value=Client()),self.assertRaisesRegex(ValueError,'HISTORY_FOCUS_FILTER_UNAVAILABLE'):
            A.portable_command(args,{'profile':'gateway'})
        self.assertEqual(messages,[])

    def test_agent_default_create_selects_primary_profile_and_explicit_legacy_stays_available(self):
        app=self.app();args=SimpleNamespace(command='schema',package_id=None,expected_input_binding=None,action='create',core_command=None,
            model_profile=None,role=None,entity_kind=None,node=None,source_package_id=None,source_folder=None,source_key=None)
        with patch.object(A,'portable_application',return_value=app):
            primary=A.portable_command(args,{'profile':'gateway'})
            self.assertEqual(primary['request']['coreModel'],'rdg-decision-v1');self.assertEqual(primary['request']['role'],'working')
            args.model_profile='rdg-core-v1';legacy=A.portable_command(args,{'profile':'gateway'})
            self.assertEqual(legacy['request']['coreModel'],'rdg-core-v1');self.assertEqual(legacy['request']['role'],'ready')

    def test_portable_cli_create_uses_the_same_explicit_selectors(self):
        args=['schema','--packages',str(self.root),'--namespace',self.namespace,'--coordination-root',str(self.base),'--op','create']
        before=self.sources()
        for extra,profile,role in [([], 'rdg-decision-v1','working'),(['--core-model','rdg-core-v1'],'rdg-core-v1','ready'),(['--role','lens'],'rdg-decision-v1','lens')]:
            output=io.StringIO()
            with patch.dict(os.environ,{'RDG_AUTH_TOKEN':self.token,'RDG_AUTH_STORE':str(self.authority.path)}),redirect_stdout(output):
                T.CLI.main(args+extra)
            form=json.loads(output.getvalue());self.assertEqual(form['request']['coreModel'],profile);self.assertEqual(form['request']['role'],role)
        self.assertEqual(before,self.sources())


if __name__=='__main__':unittest.main()
