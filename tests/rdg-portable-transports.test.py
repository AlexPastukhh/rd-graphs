#!/usr/bin/env python3
"""Fresh Agent, existing manual transports and application-owned UI projections."""
import copy
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
BASE=SourceFileLoader('portable_transport_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
H=SourceFileLoader('portable_transport_helper',str(ROOT/'tools/rdg-workflow-helper.py')).load_module()


class Transports(unittest.TestCase):
    setUp=BASE.PortableApplication.setUp
    config=BASE.PortableApplication.config
    app=BASE.PortableApplication.app
    create=BASE.PortableApplication.create
    current=BASE.PortableApplication.current
    req=BASE.PortableApplication.req
    command_request=BASE.PortableApplication.command_request
    command=BASE.PortableApplication.command
    sources=BASE.PortableApplication.sources
    review=BASE.PortableApplication.review

    def editor(self):return H.PortableEditor(self.config(),self.token)

    def cli(self,command,*args,body=None):
        context=self.base/'agent-context.json'
        context.write_text(json.dumps({'profile':'portable',**{k:v for k,v in self.config().items() if k!='authorityStore'}}))
        run=subprocess.run(['python3','-B',str(ROOT/'tools/rdg-agent.py'),command,'--context',str(context),*args],
            input=json.dumps(body) if body is not None else None,text=True,capture_output=True,timeout=45,
            env={**os.environ,'RDG_AUTH_STORE':str(self.authority.path),'RDG_AUTH_TOKEN':self.token})
        self.assertNotIn(self.token,run.stdout+run.stderr)
        self.assertEqual(run.returncode,0,run.stderr);return json.loads(run.stdout)

    def test_decision_profile_agent_helper_and_application_share_strict_focus(self):
        request=self.req('create',path='working/decision-transport',role='working',title='Decision transport',
            scope='Synthetic Decision process',coreModel='rdg-decision-v1',rootReason='Validate shared read contracts')
        ident=self.app().request(request)['packages'][0]['packageId']
        graph=self.current(ident)['graph']
        self.assertEqual(self.cli('open','--package-id',ident)['graph'],graph)
        for decision_id in ('D1','D2'):
            entity={'id':decision_id,'kind':'decision','title':decision_id,
                'description':decision_id,'revision':1,'selectionState':'discovered',
                'result':{'state':'open','truth':'unknown'}}
            self.command(ident,'add',entity=entity,location='graph')
        group={'id':'G1','parentId':'R1','title':'Alternatives',
            'selectionRequired':True,'mutuallyExclusive':True,
            'members':[{'id':'M1','decisionId':'D1'},{'id':'M2','decisionId':'D2'}]}
        self.command(ident,'decision_group',group=group)
        spec={'kind':'focus','id':'D1'}
        app=self.app()
        direct=app.call({'method':'read','packageId':ident,'view':spec})
        agent=self.cli('open','--package-id',ident,'--node','D1')
        helper=self.editor().dispatch({'method':'read','packageId':ident,'view':spec})
        for result in (direct,agent,helper):
            self.assertEqual({n['id'] for n in result['view']['entities']},{'R1','D1'})
            self.assertEqual([m['id'] for m in result['view']['decisionMemberships']],['M1'])
            self.assertEqual(result['view']['groupVisibility'][0]['hiddenIds'],[])
            self.assertEqual(result['view']['support']['activeIds'],['R1'])
        self.assertEqual(direct['view']['entities'],agent['view']['entities'])
        self.assertEqual(direct['view']['entities'],helper['view']['entities'])
        for node_id in ('R1','D1','D2'):
            snapshot=self.current(ident)
            from_model=BASE.CLI.module('rdg-model-profiles')
            self.command(ident,'review',nodeIds=[node_id],
                observed=from_model.pins(snapshot['graph'],node_id),basis='Current view checked')
        self.command(ident,'select',nodeId='D1')
        selected=app.read(ident,False,{'kind':'graph'})
        expanded=app.read(ident,False,{'kind':'graph','showExcludedAlternatives':True})
        self.assertEqual(selected['view']['groupVisibility'][0]['hiddenIds'],['D2'])
        self.assertEqual(expanded['view']['groupVisibility'][0]['hiddenIds'],[])
        self.assertTrue(expanded['view']['showExcludedAlternatives'])
        self.assertEqual(selected['graph'],expanded['graph'])
        self.assertEqual(self.cli('open','--package-id',ident,'--show-excluded-alternatives')['view']['groupVisibility'],
                         expanded['view']['groupVisibility'])

    def test_agent_helper_and_cli_use_same_preflight_and_receipt(self):
        ident=self.create('source');before=self.current(ident)
        schema=self.cli('schema','--action','copy','--package-id',ident)
        self.assertRegex(schema['request']['path'],r'^copies/\d{4}-\d{2}-\d{2}/[0-9a-f-]{36}$')
        request=schema['request'];request['path']='copies/from-agent';request['note']='Synthetic exact shared request'
        direct=self.app().call({'method':'preflight','request':request})
        self.assertEqual(self.cli('preflight',body=request),direct)
        self.assertEqual(self.editor().dispatch({'method':'preflight','request':request}),direct)
        result=self.cli('command',body=request);self.assertTrue(result['saved'])
        copied=result['packages'][0]['packageId']
        self.assertEqual(self.current(ident),before)
        receipt=self.cli('receipt','--package-id',copied,'--transaction-id',request['transactionId'])
        self.assertTrue(receipt['found']);self.assertTrue(self.app().request(request)['idempotent'])
        catalog=self.cli('catalog');self.assertEqual({r['role'] for r in catalog['packages']},{'working','copy'})
        self.assertEqual(self.cli('migration_sources'),{'configured':False,'sources':[]})

    def test_high_level_place_unplace_and_server_focus_projection(self):
        ident=self.create('placed');app=self.app()
        request=app.schema('place',ident,'R1')['request'];request.update(at='2026-10-30',note='Synthetic date')
        preview=app.request(request,preflight=True);result=app.request(request)
        sid=result['packages'][0]['receipt']['effects']['placementId'];self.assertTrue(sid)
        current=app.read(ident,True,{'kind':'focus','id':'R1'})
        self.assertEqual(current['planView']['placements'][0]['bucket'],'future')
        self.assertEqual(json.loads(current['view']['graphKey']),[current['graph']['identitySpace'],current['graph']['id'],'R1'])
        self.assertEqual(current['references']['R1'],BASE.P.reference(ident,current['graph'],'R1'))
        request=app.schema('unplace',ident)['request'];request.update(stepId=sid,note='Synthetic unplace')
        app.request(request);self.assertEqual(app.read(ident,True)['plan']['steps'],[])
        bad=app.schema('place',ident,'missing')['request'];bad.update(at='2026-10-30',note='Missing target')
        with self.assertRaisesRegex(ValueError,'PLACEMENT_NODE_UNKNOWN'):app.request(bad)

    def test_paper_copy_retains_absent_plan_then_creates_it_explicitly(self):
        ready=self.create('paper-without-plan','ready');app=self.app()
        request=app.schema('copy',ready)['request'];request.update(path='copies/paper',note='Copy paper as work')
        copied=app.request(request)['packages'][0]['packageId'];self.assertIsNone(app.read(copied,True)['plan'])
        create=self.editor().dispatch({'method':'schema','op':'plan_create','packageId':copied})['request']
        before=app.read(copied,True)['graph'];self.assertFalse(app.request(create,preflight=True)['accepted'])
        restricted=self.authority.manage('issue',self.admin,{'permissions':['graph.read','graph.write'],
            'scopes':['packages/'+self.namespace+'/'+copied]})['token']
        with self.assertRaisesRegex(ValueError,'AUTH_MISSING_PERMISSION: plan.create'):self.app(restricted).request(create)
        self.editor().dispatch({'method':'apply','request':create})
        self.assertEqual(app.read(copied,True)['graph'],before);self.assertEqual(app.read(copied,True)['plan']['steps'],[])
        self.assertTrue(app.request(create)['idempotent'])
        place=app.schema('place',copied,app.read(copied)['graph']['nodes'][0]['id'])['request']
        place.update(at='2026-10-30',note='Explicit plan placement');app.request(place)
        self.assertEqual(len(app.read(copied,True)['plan']['steps']),1)
        with self.assertRaisesRegex(ValueError,'PLAN_ALREADY_EXISTS_OR_PAPER'):
            app.request(app.schema('plan_create',ready)['request'])

    def test_insert_copy_preserves_source_plan_when_destination_has_no_plan(self):
        app=self.app();ready=self.create('paper-target','ready');source=self.create('source-with-plan')
        place=app.schema('place',source,'R1')['request'];place.update(at='2026-10-30',note='Source date');app.request(place)
        source_before=app.read(source,True)
        request=app.schema('copy',ready)['request'];request.update(path='copies/no-plan-target',note='Keep absent Plan')
        target=app.request(request)['packages'][0]['packageId'];self.assertIsNone(app.read(target,True)['plan'])
        request=app.schema('insert_copy',target,source_id=source)['request'];request['note']='Insert work with temporal context'
        app.request(request);after=app.read(target,True)
        self.assertEqual(len(after['plan']['steps']),1);step=after['plan']['steps'][0]
        self.assertEqual(step['ref']['packageId'],target);self.assertIn(step['ref']['nodeId'],after['references'])
        self.assertEqual(after['plan']['timeConstraints'][0]['at'],'2026-10-30')
        self.assertEqual(app.read(source,True),source_before)

    def test_unaccepted_creation_never_becomes_an_incoming_current_owner(self):
        target=self.create('target');app=self.app()
        abandoned=app.schema('create')['request'];abandoned.update(path='working/unaccepted',role='working',title='Unaccepted',
            scope='Synthetic scope')
        def fail(phase):
            if phase=='staged':raise RuntimeError('Before acceptance')
        with self.assertRaisesRegex(RuntimeError,'Before acceptance'):app.request(abandoned,failpoint=fail)
        self.assertTrue(any(r['health']=='unaccepted-stage' for r in self.store.scan()))
        delete=app.schema('delete',target,'R1')['request'];delete['note']='Remove existing current root'
        app.request(delete);self.assertFalse(any(n['id']=='R1' for n in app.read(target)['graph']['nodes']))
        self.assertTrue(app.request(abandoned)['published'])

    def test_decision_profile_recovers_accepted_create_and_preserves_one_event(self):
        request=self.req('create',role='working',path='working/decision-recovery',
            title='Recovered Decision',scope='Synthetic scope',coreModel='rdg-decision-v1',
            rootReason='Recovery of accepted Decision profile')
        def fail(phase):
            if phase=='prepared':raise RuntimeError('Decision response lost')
        with self.assertRaisesRegex(RuntimeError,'Decision response lost'):
            self.app().request(request,failpoint=fail)
        recovered=self.cli('recover','--transaction-id',request['transactionId'])
        self.assertTrue(recovered['published'])
        ident=recovered['packages'][0]['packageId']
        reopened=self.app().read(ident)
        self.assertEqual(reopened['graph']['coreModel'],'rdg-decision-v1')
        self.assertEqual(len(reopened['graph']['events']),1)
        self.assertEqual(reopened['graph']['events'][0]['type'],'created')
        self.assertTrue(self.app().recover(request['transactionId'])['idempotent'])
        self.assertEqual(reopened['graph'],self.app().read(ident)['graph'])

    def test_recover_finishes_only_accepted_intent_without_original_request_body(self):
        request=self.app().schema('create')['request'];request.update(path='working/recover',role='working',title='Recovered',scope='Synthetic scope')
        def fail(phase):
            if phase=='prepared':raise RuntimeError('Lost client')
        with self.assertRaisesRegex(RuntimeError,'Lost client'):self.app().request(request,failpoint=fail)
        other=self.authority.manage('issue',self.admin,{'permissions':BASE.FIX.PERMISSIONS,
            'scopes':['packages/'+self.namespace+'/']})['token']
        with self.assertRaisesRegex(ValueError,'ACTOR_MISMATCH'):self.app(other).recover(request['transactionId'])
        self.authority.manage('revoke',self.admin,{'id':self.grant_id})
        recovered=self.cli('recover','--transaction-id',request['transactionId'])
        self.assertTrue(recovered['published']);ident=recovered['packages'][0]['packageId']
        self.assertEqual(self.store.read(ident)['graph']['title'],'Recovered')
        self.assertTrue(self.app().recover(request['transactionId'])['idempotent'])
        with self.assertRaisesRegex(ValueError,'ACCEPTED_TRANSACTION_NOT_FOUND'):
            self.app(other).recover(str(BASE.uuid.uuid4()))

    def test_history_uses_accepted_version_instead_of_latest_containing_event(self):
        ident=self.create('history');self.command(ident,'edit',nodeId='R1',changes={'title':'First edit'})
        first=self.current(ident);self.command(ident,'edit',nodeId='R1',changes={'title':'Later edit'})
        events=self.app().history(ident)['events']
        original=next(e for e in events if e['event']['after']['R1']['title']=='First edit')
        self.assertEqual(original['source']['sha256'],BASE.P.digest(first['graph']))
        self.assertTrue(original['acceptedAt']);self.assertEqual(original['snapshotKind'],'after-transaction')

    def test_historical_graph_navigation_uses_owned_cache_after_source_is_unavailable(self):
        import shutil
        ident=self.create('historical-source');self.command(ident,'edit',nodeId='R1',changes={'title':'Preserved title'})
        app=self.app();event=app.history(ident)['events'][-1];pin=event['source']
        request=app.schema('copy',ident)['request'];request.update(path='copies/historical',note='Preserve facts')
        copied=app.request(request)['packages'][0]['packageId'];self.command(ident,'edit',nodeId='R1',changes={'title':'Current title'})
        source=self.store.read(ident);shutil.rmtree(self.root/source['path'])
        snapshot=self.editor().dispatch({'method':'source_snapshot','packageId':copied,'pin':pin})
        self.assertTrue(snapshot['readOnly']);self.assertFalse(snapshot['currentOwnerAvailable'])
        self.assertEqual(snapshot['graph']['nodes'][0]['title'],'Preserved title')
        self.assertEqual(BASE.P.digest(snapshot['graph']),pin['sha256']);self.assertEqual(snapshot['pin'],pin)
        self.assertEqual(self.cli('source_snapshot','--package-id',copied,body=pin),snapshot)
        with self.assertRaisesRegex(ValueError,'HISTORICAL_GRAPH_UNAVAILABLE'):
            app.source_snapshot(copied,{**pin,'graphRevision':pin['graphRevision']+100})
        restricted=self.authority.manage('issue',self.admin,{'permissions':['graph.read'],
            'scopes':['packages/'+self.namespace+'/'+ident]})['token']
        with self.assertRaisesRegex(ValueError,'PORTABLE_SCOPE_DENIED'):self.app(restricted).source_snapshot(copied,pin)

    def test_file_and_http_sessions_route_common_contract_without_exposing_bearer(self):
        ident=self.create('manual');editor=self.editor();session=H.FileSession(editor,self.base/'new-session')
        self.addCleanup(session.close)
        descriptor=json.loads((session.directory/'session.json').read_bytes());self.assertEqual(descriptor['profile'],'portable')
        self.assertNotIn(self.token,json.dumps(descriptor))
        message={'method':'schema','op':'core','packageId':ident,'nodeId':'R1','command':'edit'}
        raw={'session':session.session,'kind':'command','body':message}
        (session.directory/'request-one.json').write_text(json.dumps(raw));(session.directory/'request-one.ready').write_text('1')
        session.process_once();response=json.loads((session.directory/'response-one.json').read_bytes())
        self.assertTrue(response['ok']);request=response['result']['request'];request['data']['changes']={'title':'Manual change'};request['note']='Synthetic manual session'
        server=H.make_server(editor);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def close():server.shutdown();server.server_close();thread.join(2)
        self.addCleanup(close);cap=server.session_url.rstrip('/').split('/')[-1]
        headers={'X-RDG-Session':cap,'Content-Type':'application/json','Origin':server.origin}
        with urlopen(Request(server.session_url+'command',data=json.dumps({'method':'apply','request':request}).encode(),headers=headers),timeout=30) as result:
            self.assertTrue(json.load(result)['published'])
        self.assertEqual(self.current(ident)['graph']['events'][-1]['by'],'user')
        with urlopen(server.session_url,timeout=10) as result:html=result.read().decode()
        self.assertIn('RDG_LOCAL_PORTABLE=true',html);self.assertNotIn(self.token,html)
        denied={**headers,'Origin':'https://untrusted.invalid'}
        with self.assertRaises(HTTPError):urlopen(Request(server.session_url+'command',data=b'{}',headers=denied),timeout=10)

    def test_paper_read_needs_no_plan_permission_and_never_shows_plan_facts(self):
        ident=self.create('paper','ready')
        token=self.authority.manage('issue',self.admin,{'permissions':['graph.read'],'scopes':['packages/'+self.namespace+'/'+ident]})['token']
        row=self.app(token).read(ident,True);self.assertIsNone(row['planView']);self.assertFalse(row['graph']['events'])

    def test_actual_ui_controller_uses_manual_helper_and_shared_service(self):
        ident=self.create('working');self.create('ready','ready')
        self.command(ident,'add',entity={'id':'A','kind':'action','title':'Retained action'})
        self.command(ident,'link',edge={'id':'driver','type':'DRIVES','from':'R1','to':'A'})
        self.review(ident);self.command(ident,'select',nodeId='A');self.review(ident)
        request=self.app().schema('place',ident,'R1')['request'];request.update(at='2026-10-30',note='Synthetic placement')
        self.app().request(request)
        server=H.make_server(self.editor());thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            run=subprocess.run(['node','--test',str(ROOT/'tests/rdg-portable-ui.test.cjs')],text=True,capture_output=True,
                timeout=120,env={**os.environ,'RDG_PORTABLE_TEST_URL':server.session_url})
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
            self.assertEqual(self.current(ident)['graph']['events'][-1]['by'],'user')
        finally:server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
