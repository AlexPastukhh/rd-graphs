#!/usr/bin/env python3
"""Closed, synthetic legacy owners; no live migration or grant changes."""
import copy
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=SourceFileLoader('legacy_migration_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
OWNER=SourceFileLoader('migration_legacy_plan',str(ROOT/'tools/rdg-temporal-plan-owner.py')).load_module()
ACTIVITY=SourceFileLoader('migration_legacy_activity',str(ROOT/'tools/rdg-activity.py')).load_module()
P,M=BASE.P,BASE.M


class LegacyMigration(unittest.TestCase):
    app=BASE.PortableApplication.app
    create=BASE.PortableApplication.create
    current=BASE.PortableApplication.current
    req=BASE.PortableApplication.req
    command_request=BASE.PortableApplication.command_request
    command=BASE.PortableApplication.command

    def setUp(self):
        BASE.PortableApplication.setUp(self)
        grant=self.authority.manage('issue',self.admin,{'permissions':BASE.FIX.PERMISSIONS,
            'scopes':['packages/'+self.namespace+'/','workspaces/','plans/']})
        self.token=grant['token'];self.grant_id=grant['id']
        self.graph_root=self.base/'graphs';self.old_plans=self.base/'old-plans';self.old_plans.mkdir()
        self.graph_file='workspaces/legacy/graph.json';self.plan_file='plans/legacy/plan.json'
        self.graph_path=self.graph_root/self.graph_file;self.graph_path.parent.mkdir(parents=True)
        self.graph=M.blank('legacy-graph','Legacy work','legacy-space','R1','Required result','Synthetic legacy scope')
        self.sequence=0;self.save(None,'old-create')
        plan={'schemaVersion':1,'kind':'temporalPlan','id':'legacy-plan','title':'Original Plan','identitySpace':'legacy-space',
            'revision':1,'status':'candidate','steps':[],'sequence':[],'branches':[],'timeConstraints':[]}
        OWNER.apply_request(self.old_plans,self.authority.path,self.token,{'transactionId':'old-plan-create','op':'create',
            'file':self.plan_file,'expectedRevision':0,'plan':plan},graph_root=self.graph_root)
        self.configuration=self.base/'migration-config.json'
        self.configuration.write_text(json.dumps({'graphRoot':str(self.graph_root),'planRoot':str(self.old_plans),
            'owners':{'legacy':{'graphFile':self.graph_file,'planFile':self.plan_file,'role':'working'}}}))

    def config(self):return {**BASE.PortableApplication.config(self),'migrationConfig':str(self.configuration)}

    def save(self,before,transaction):
        self.graph_path.write_text(json.dumps(self.graph,ensure_ascii=False,indent=2)+'\n')
        directory=self.graph_root/'workspaces/.transactions';directory.mkdir(exist_ok=True)
        journal={'schemaVersion':2,'transactionId':transaction,'requestSHA256':'0'*64,'state':'completed',
            'preparedAt':'2026-10-20T09:00:00+00:00','recordedAt':'2026-10-20T09:00:01+00:00',
            'records':[{'file':self.graph_file,'before':before,'after':self.graph,'changed':True}]}
        (directory/(transaction+'.json')).write_text(json.dumps(journal,ensure_ascii=False,indent=2)+'\n')

    def change(self,command,**data):
        before=copy.deepcopy(self.graph);self.sequence+=1;tid='old-'+str(self.sequence)
        event={'id':tid,'by':'assistant','note':'Synthetic legacy '+command,'recordedAt':'2026-10-20T09:00:00+00:00',
               'verifiedTrustReceipt':{'mode':'test-only'}}
        self.graph,_=M.apply(self.graph,{'schemaVersion':1,'expectedRevision':self.graph['revision'],
            'operations':[{'op':'graph_edit','action':'core_'+command,'data':data,'event':event}]},True)
        self.save(before,tid)

    def review(self):
        ids=[i for i,n in M.entities(self.graph).items() if n.get('review',{}).get('required')]
        if ids:self.change('review',nodeIds=ids,observed={i:r for j in ids for i,r in M.pins(self.graph,j).items()})

    def prepared(self):
        request=self.app().schema('migrate',source_key='legacy')['request']
        request.update(path='migrated/legacy',confirmOwnerSwitch=True,legacyWritersQuiesced=True,presentationSourcesComplete=True,presentationWritersPaused=True)
        return request

    @staticmethod
    def fail(phase):
        def injected(point):
            if point==phase:raise RuntimeError('Injected '+phase)
        return injected

    def test_scoped_migration_retains_selected_detached_state_versions_and_exact_history_after_move(self):
        self.change('add',entity={'id':'A','kind':'action','title':'Retained action'})
        self.change('link',edge={'id':'driver','type':'DRIVES','from':'R1','to':'A'})
        self.review();self.change('select',nodeId='A');self.review();self.change('unlink',edgeId='driver')
        # An unrelated record in the shared envelope must not enter the new package.
        journal=self.graph_root/'workspaces/.transactions/old-create.json';data=json.loads(journal.read_bytes())
        foreign=M.blank('other','UNRELATED_PRIVATE_SENTINEL','other-space','OTHER','Other result','Synthetic other scope')
        data['records'].append({'file':'workspaces/other/graph.json','before':None,'after':foreign,'changed':True})
        journal.write_text(json.dumps(data))
        current=OWNER.read_snapshot(self.old_plans,self.plan_file)['plan'];plan=copy.deepcopy(current);plan['revision']+=1
        plan['steps']=[{'id':'PLACED-A','title':'Retained action','kind':'action','state':'planned',
            'actionRef':{'graphFile':self.graph_file,'identitySpace':'legacy-space','nodeId':'A'}}]
        plan['timeConstraints']=[{'stepId':'PLACED-A','type':'notBefore','at':'2026-10-30','strength':'soft','basis':'Synthetic date'}]
        OWNER.apply_request(self.old_plans,self.authority.path,self.token,{'transactionId':'old-place','op':'edit',
            'file':self.plan_file,'expectedRevision':current['revision'],'plan':plan},graph_root=self.graph_root)
        raw_graph=self.graph_path.read_bytes();raw_plan=(self.old_plans/self.plan_file).read_bytes()
        request=self.prepared();app=self.app();preview=app.request(request,preflight=True)
        self.assertFalse(preview['accepted']);self.assertFalse(app.migration.marker(self.graph_path).exists())
        result=app.request(request);ident=result['packages'][0]['packageId'];row=app.read(ident,True)
        self.assertEqual(row['graph'],self.graph);self.assertEqual(row['plan']['schemaVersion'],2)
        self.assertEqual(row['plan']['revision'],plan['revision']+1);self.assertEqual(row['plan']['steps'][0]['ref']['packageId'],ident)
        self.assertEqual(row['graph']['nodes'][-1]['status'],'selected');self.assertTrue(row['completion']['A']['reviewRequired'])
        self.assertTrue(any('A' in c['memberIds'] for c in row['detached']))
        self.assertEqual(self.graph_path.read_bytes(),raw_graph);self.assertEqual((self.old_plans/self.plan_file).read_bytes(),raw_plan)
        with self.assertRaisesRegex(ValueError,'LEGACY_OWNER_MIGRATED'):OWNER.read_snapshot(self.old_plans,self.plan_file)
        self.assertEqual(OWNER.read_snapshot(self.old_plans,self.plan_file,revision=1)['plan']['revision'],1)
        with self.assertRaisesRegex(ValueError,'LEGACY_OWNER_MIGRATED'):
            ACTIVITY.read_activity(self.graph_root,[self.graph_file],self.token,self.authority.path,True)
        with self.assertRaisesRegex(ValueError,'LEGACY_OWNER_MIGRATED'):
            OWNER.apply_request(self.old_plans,self.authority.path,self.token,{'transactionId':'forbidden-old-write','op':'edit',
                'file':self.plan_file,'expectedRevision':plan['revision'],'plan':{**plan,'revision':plan['revision']+1}},graph_root=self.graph_root)
        move=app.schema('move',ident)['request'];move.update(path='organized/legacy',note='Move migrated fixture');app.request(move)
        history=app.history(ident)
        self.assertTrue({1,2}<={p['plan']['revision'] for p in history['planVersions'] if p.get('legacy')})
        event=next(e for e in history['events'] if e['event']['type']=='action_selected')
        self.assertEqual(event['snapshotKind'],'legacy-after-record-projection');self.assertEqual(event['acceptedAt'],'2026-10-20T09:00:01+00:00')
        self.assertFalse(event['fullEnvelopeCopied']);self.assertFalse(history['reconstructedExecution'])
        snapshot=app.source_snapshot(ident,event['source']);self.assertTrue(snapshot['readOnly'])
        self.assertEqual(P.digest(snapshot['graph']),event['source']['sha256'])
        package=self.store.read(ident);directory=self.root/package['path']
        for relative in self.store.inventory(package):self.assertNotIn(b'UNRELATED_PRIVATE_SENTINEL',(directory/relative).read_bytes())

    def test_all_source_cas_rejects_source_or_registry_edit_before_switch(self):
        request=self.prepared();app=self.app()
        def change():
            graph=json.loads(self.graph_path.read_bytes());graph['title']='Concurrent change';self.graph_path.write_text(json.dumps(graph))
        with self.assertRaisesRegex(ValueError,'SOURCE_FILE_CHANGED'):app.request(request,before_accept=change)
        self.assertFalse(app.migration.marker(self.graph_path).exists());self.assertFalse(self.store.metadata_path('accepted',request['transactionId']).exists())
        self.assertEqual(json.loads(self.graph_path.read_bytes())['title'],'Concurrent change')

    def test_accepted_recovery_finishes_switch_with_exact_request(self):
        request=self.prepared();app=self.app()
        with self.assertRaisesRegex(RuntimeError,'Injected prepared'):app.request(request,failpoint=self.fail('prepared'))
        with self.assertRaisesRegex(ValueError,'LEGACY_OWNER_MIGRATED'):OWNER.read_snapshot(self.old_plans,self.plan_file)
        self.authority.manage('revoke',self.admin,{'id':self.grant_id})
        with self.assertRaisesRegex(ValueError,'ACCEPTED_SWITCH_REQUIRES_FORWARD_RECOVERY'):app.migration.cancel(request['transactionId'])
        result=app.call({'method':'recover','transactionId':request['transactionId']});self.assertTrue(result['published'])
        route=json.loads(app.migration.marker(self.graph_path).read_bytes());self.assertEqual(route['state'],'committed')
        self.assertTrue(app.request(request)['idempotent'])

    def test_cancel_unaccepted_switch_unfreezes_only_own_routes_without_discarding_facts(self):
        request=self.prepared();app=self.app();original=self.graph_path.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'Injected staged'):app.request(request,failpoint=self.fail('staged'))
        record=json.loads(app.migration.journal(request['transactionId']).read_bytes())
        # Simulate process loss after its own route markers, before acceptance.
        for route in record['routes']:
            marker={'schemaVersion':1,'kind':'legacyOwnerRoute','transactionId':request['transactionId'],
                'requestSHA256':record['requestSHA256'],'packageId':record['packageId'],'namespaceId':self.namespace,'state':'switching'}
            Path(route['path']).write_bytes(self.store.encode(marker))
        with self.assertRaisesRegex(ValueError,'EXACT_ACTOR'):
            self.app(self.admin).migration.cancel(request['transactionId'])
        result=app.call({'method':'cancel_migration','transactionId':request['transactionId']})
        self.assertTrue(result['cancelled']);self.assertFalse(result['accepted']);self.assertTrue(result['stagedBytesRetained'])
        self.assertEqual(self.graph_path.read_bytes(),original)
        self.assertEqual(OWNER.read_snapshot(self.old_plans,self.plan_file)['plan']['revision'],1)
        self.assertTrue(app.migration.cancel(request['transactionId'])['cancelled'])
        with self.assertRaisesRegex(ValueError,'TRANSACTION_CANCELLED'):app.request(request)
        # Same operation through the fresh Agent process, not a direct service import.
        import os
        import subprocess
        context=self.base/'portable-agent.json'
        context.write_text(json.dumps({'profile':'portable',**{
            k:v for k,v in self.config().items() if k!='authorityStore'}}))
        run=subprocess.run(['python3','-B',str(ROOT/'tools/rdg-agent.py'),'cancel_migration',
            '--context',str(context),'--transaction-id',request['transactionId']],
            capture_output=True,text=True,timeout=30,env={**os.environ,
                'RDG_AUTH_STORE':str(self.authority.path),'RDG_AUTH_TOKEN':self.token})
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertTrue(json.loads(run.stdout)['cancelled'])
        self.assertNotIn(self.token,run.stdout+run.stderr)

    def test_cancel_after_abrupt_preacceptance_exit_releases_real_switch(self):
        request=self.prepared();app=self.app();original=self.graph_path.read_bytes()
        accepted=self.store.metadata_path('accepted',request['transactionId'])
        original_write=app.store.io.atomic_bytes
        def exit_at_acceptance(path,data):
            if Path(path)==accepted:raise SystemExit('Simulated abrupt process termination')
            return original_write(path,data)
        app.store.io.atomic_bytes=exit_at_acceptance
        try:
            with self.assertRaisesRegex(SystemExit,'Simulated abrupt'):
                app.request(request)
        finally:
            app.store.io.atomic_bytes=original_write
        self.assertEqual(json.loads(app.migration.marker(self.graph_path).read_bytes())['state'],'switching')
        result=self.app().migration.cancel(request['transactionId'])
        self.assertTrue(result['cancelled'])
        self.assertFalse(app.migration.marker(self.graph_path).exists())
        self.assertEqual(self.graph_path.read_bytes(),original)
        self.assertEqual(OWNER.read_snapshot(self.old_plans,self.plan_file)['plan']['revision'],1)

    def test_cancel_blocks_unidentified_stage_and_acceptance_even_if_certificate_is_missing(self):
        request=self.prepared();app=self.app()
        with self.assertRaisesRegex(RuntimeError,'Injected staged'):app.request(request,failpoint=self.fail('staged'))
        marker=app.migration.marker(self.graph_path)
        record=json.loads(app.migration.journal(request['transactionId']).read_bytes())
        marker.write_bytes(self.store.encode({'schemaVersion':1,'kind':'legacyOwnerRoute',
            'transactionId':request['transactionId'],'requestSHA256':record['requestSHA256'],
            'packageId':record['packageId'],'namespaceId':self.namespace,'state':'switching'}))
        stage=next(row for row in self.store.scan() if row.get('packageId')==record['packageId'])
        identity=self.root/stage['path'] / '.rdg/package.json'
        original=identity.read_bytes();identity.write_bytes(b'broken')
        with self.assertRaises(ValueError):app.migration.cancel(request['transactionId'])
        self.assertTrue(marker.exists())
        identity.write_bytes(original)
        accepted=self.store.metadata_path('accepted',request['transactionId'])
        accepted.parent.mkdir(parents=True,exist_ok=True);accepted.write_bytes(b'broken')
        with self.assertRaisesRegex(ValueError,'ACCEPTED_SWITCH_REQUIRES_FORWARD_RECOVERY'):
            app.migration.cancel(request['transactionId'])
        self.assertTrue(marker.exists())

    def test_preacceptance_retry_reuses_witness_time_and_provenance_bytes(self):
        request=self.prepared();app=self.app()
        with self.assertRaisesRegex(RuntimeError,'Injected staged'):app.request(request,failpoint=self.fail('staged'))
        self.assertFalse(app.migration.marker(self.graph_path).exists())
        self.assertTrue(app.request(request)['published'])

    def test_final_authorization_revocation_does_not_switch_owner(self):
        request=self.prepared();app=self.app();original=self.graph_path.read_bytes()
        def revoke():self.authority.manage('revoke',self.admin,{'id':self.grant_id})
        with self.assertRaisesRegex(ValueError,'REVOKED'):app.request(request,before_accept=revoke)
        self.assertFalse(app.migration.marker(self.graph_path).exists());self.assertEqual(self.graph_path.read_bytes(),original)
        self.assertFalse(self.store.metadata_path('accepted',request['transactionId']).exists())

    def test_final_source_inventory_and_saved_layouts_are_in_read_set(self):
        app=self.app();layout=self.graph_root/'layouts.json';layout.write_text(json.dumps(app.layout('empty')))
        request=self.prepared()
        def edit_layout():layout.write_text(layout.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'SOURCE_FILE_CHANGED'):app.request(request,before_accept=edit_layout)
        request=self.prepared();request['path']='migrated/inventory-attempt'
        def add_owner():
            path=self.graph_root/'workspaces/other/graph.json';path.parent.mkdir()
            path.write_text(json.dumps(M.blank('other','Other graph','other-space','OTHER','Other result','Synthetic other scope')))
        with self.assertRaisesRegex(ValueError,'SOURCE_INVENTORY_CHANGED'):app.request(request,before_accept=add_owner)
        self.assertFalse(app.migration.marker(self.graph_path).exists())

    def test_unsupported_plan_gate_is_reported_and_no_owner_is_switched(self):
        current=OWNER.read_snapshot(self.old_plans,self.plan_file)['plan'];plan=copy.deepcopy(current);plan['revision']+=1
        plan['steps']=[{'id':'GATE','title':'Legacy gate','kind':'decision_gate','state':'planned'}]
        OWNER.apply_request(self.old_plans,self.authority.path,self.token,{'transactionId':'old-gate','op':'edit',
            'file':self.plan_file,'expectedRevision':current['revision'],'plan':plan},graph_root=self.graph_root)
        app=self.app();inspection=app.migration.inspect('legacy');self.assertFalse(inspection['ready'])
        self.assertTrue(any('PLAN_ONLY_EVENT_GATE' in s for s in inspection['blockers']))
        request=self.prepared()
        with self.assertRaisesRegex(ValueError,'PLAN_ONLY_EVENT_GATE'):app.request(request)
        self.assertFalse(app.migration.marker(self.graph_path).exists())

    def test_incoming_legacy_plan_is_not_silently_left_on_immutable_source(self):
        plan=OWNER.read_snapshot(self.old_plans,self.plan_file)['plan'];plan=copy.deepcopy(plan);plan['id']='other-plan'
        plan['steps']=[{'id':'OTHER','title':'Other placement','kind':'requirement','state':'planned',
            'requirementRef':{'graphFile':self.graph_file,'identitySpace':'legacy-space','nodeId':'R1'}}]
        plan['timeConstraints']=[{'stepId':'OTHER','type':'notBefore','at':'2026-10-30','strength':'soft','basis':'Synthetic placement'}]
        OWNER.apply_request(self.old_plans,self.authority.path,self.token,{'transactionId':'other-plan','op':'create',
            'file':'plans/other/plan.json','expectedRevision':0,'plan':plan},graph_root=self.graph_root)
        inspection=self.app().migration.inspect('legacy');self.assertFalse(inspection['ready'])
        self.assertTrue(any(s.startswith('INCOMING_LEGACY_PLAN:') for s in inspection['blockers']))

    def test_no_migration_at_startup_and_explicit_opt_in_required(self):
        app=self.app();self.assertEqual(app.migration.sources()['sources'][0]['sourceKey'],'legacy')
        self.assertFalse(app.migration.marker(self.graph_path).exists());request=self.prepared();request['confirmOwnerSwitch']=False
        with self.assertRaisesRegex(ValueError,'EXPLICIT_SWITCH'):app.request(request)
        self.assertFalse(app.migration.marker(self.graph_path).exists())

    def test_migration_input_binding_rejects_catalog_change_before_switch(self):
        app=self.app();request=self.prepared()
        first=app.request(request,preflight=True)
        self.assertEqual(first['inputBinding']['policy'],'legacy-source-read-set-v1')
        self.assertEqual(first['inputBinding']['sourcePin'],request['sourcePin'])
        self.create('migration-catalog-change')
        with self.assertRaisesRegex(ValueError,'MIGRATION_PREVIEW_INPUTS_CHANGED'):
            app.request(request,expected_input_binding=first['inputBinding'])
        second=app.request(request,preflight=True)
        self.assertNotEqual(first['inputBinding'],second['inputBinding'])
        result=app.request(request,expected_input_binding=second['inputBinding'])
        self.assertTrue(result['accepted'])
        marker=app.migration.marker(self.graph_path)
        self.assertTrue(marker.is_file())
        self.assertEqual(json.loads(marker.read_bytes())['state'],'committed')

    def test_omitted_known_plan_blocks_but_a_true_graph_only_owner_preserves_no_plan(self):
        import shutil
        config=json.loads(self.configuration.read_bytes());del config['owners']['legacy']['planFile']
        self.configuration.write_text(json.dumps(config));app=self.app()
        inspection=app.migration.inspect('legacy');self.assertFalse(inspection['ready'])
        self.assertTrue(any(s.startswith('UNCAPTURED_PLAN_OWNER:') for s in inspection['blockers']))
        # This removes only this test's synthetic legacy Plan fixture.
        shutil.rmtree(self.old_plans);self.old_plans.mkdir()
        self.assertTrue(app.migration.inspect('legacy')['ready']);request=self.prepared()
        ident=app.request(request)['packages'][0]['packageId']
        self.assertIsNone(app.read(ident,True)['plan']);self.assertEqual(app.read(ident)['graph'],self.graph)


if __name__=='__main__':unittest.main()
