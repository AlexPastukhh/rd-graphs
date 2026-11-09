#!/usr/bin/env python3
"""Disposable manual Decision launcher: real HTTP, writer, persistence and scope."""
from importlib.machinery import SourceFileLoader
import hashlib
import os
from unittest.mock import patch
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]
PREVIEW=SourceFileLoader('decision_preview_host',str(ROOT/'tools/rdg-preview.py')).load_module()

class DecisionPreview(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='rdg-decision-preview-test-',dir='/workspace/repo/Workfiles');self.addCleanup(self.temp.cleanup)
        self.data=Path(self.temp.name)/'data';self.server=None;self.thread=None;self.addCleanup(self.stop)
    def start(self):
        self.server=PREVIEW.build_host(self.data,0,'rdg-decision-v1')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        return self.server
    def stop(self):
        if self.server:
            self.server.shutdown();self.server.server_close();self.thread.join(5);self.server=None
    def call(self,message):
        base=self.server.session_url;cap=base.rstrip('/').rsplit('/',1)[1]
        req=urllib.request.Request(base+'command',data=json.dumps(message).encode(),headers={'Content-Type':'application/json','Origin':self.server.origin,'X-RDG-Session':cap})
        try:
            with urllib.request.urlopen(req,timeout=15) as response:return json.load(response)
        except urllib.error.HTTPError as exc:raise ValueError(json.load(exc).get('error','HTTP_REQUEST_FAILED')) from None
    def schema(self,op,ident,**fields):return self.call({'method':'schema','op':op,'packageId':ident,**fields})['request']
    def files(self):return {str(p.relative_to(self.data)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.data.rglob('*') if p.is_file()}
    def execute(self,request):
        before=self.files();preview=self.call({'method':'preflight','request':request});self.assertEqual(self.files(),before)
        return self.call({'method':'apply','request':request,'expectedInputBinding':preview['inputBinding']})
    def test_real_manual_host_writes_and_restarts_with_same_owners(self):
        self.start();catalog=self.call({'method':'catalog'});rows=catalog['packages']
        self.assertEqual(len(rows),1)
        ident=rows[0]['packageId'];self.assertEqual(rows[0]['role'],'working')
        self.assertEqual(self.call({'method':'recommendation_catalog'})['packages'],[])
        self.assertEqual(rows[0]['recommendationPackageIds'],[])
        self.assertEqual(self.call({'method':'read','packageId':ident})['graph']['workGraphs'],[])
        req=self.schema('core',ident,nodeId='R1',command='add');req['data']={'entity':{'id':'D-MANUAL','kind':'decision','title':'Ручная альтернатива','description':'Проверка сохранения'},'initialRelations':[{'id':'R-D-MANUAL','type':'DRIVES','from':'R1','to':'D-MANUAL'}]};req['note']='Actual manual host authoring';self.execute(req)
        self.execute(self.schema('plan_create',ident));req=self.schema('place',ident,nodeId='D-MANUAL');req['note']='Order without selection or date';self.execute(req)
        row=self.call({'method':'read','packageId':ident,'includePlan':True});req=self.schema('layout_edit',ident);req['commands']=[{'type':'set_positions','graphKey':row['view']['graphKey'],'positions':{'D-MANUAL':{'x':327,'y':-44}}}];self.execute(req)
        saved=self.call({'method':'read','packageId':ident,'includePlan':True});origin=self.server.origin;old_url=self.server.session_url;self.stop();self.start()
        self.assertEqual(self.server.origin,origin);self.assertNotEqual(self.server.session_url,old_url)
        restored=self.call({'method':'read','packageId':ident,'includePlan':True})
        for key in ('graph','plan','layouts','recommendations'):self.assertEqual(restored[key],saved[key])
        self.assertEqual(len(self.call({'method':'catalog'})['packages']),1);self.assertEqual(restored['plan']['timeConstraints'],[])
        self.assertEqual(next(n for n in restored['graph']['nodes'] if n['id']=='D-MANUAL')['selectionState'],'discovered')
    def test_explicit_lenses_and_nested_recommendations_via_application(self):
        self.start()
        before=self.call({'method':'catalog'})
        self.assertEqual(len(before['packages']),1)
        created={}
        for key in ('model','decision-logic'):
            req={'op':'create','transactionId':str(uuid.uuid4()),'path':'lenses/manual/'+key,
                 'role':'lens','lensKey':key,'coreModel':'rdg-decision-v1',
                 'rootReason':'Explicit API-driven paper definition','title':'Manual '+key,
                 'scope':'Isolated lens test'}
            created[key]=self.execute(req)['packages'][0]['packageId']
        src=self.call({'method':'read','packageId':created['model']})
        dst=self.call({'method':'read','packageId':created['decision-logic']})
        self.assertEqual(src['graph']['coreModel'],'rdg-decision-v1')
        refs=[{'packageId':created[key],
               'identitySpace':data['graph']['identitySpace'],'lensKey':key}
              for key,data in (('decision-logic',dst),('model',src))]
        definition={'id':str(uuid.uuid4()),'revision':1,'key':'manual-nested',
                    'title':'Manually attached nested recommendation','supplied':False,
                    'rules':[{'id':'manual-root','nodeKinds':['requirement'],
                              'scope':'identity','anchor':{'packageId':created['model'],
                              'identitySpace':src['graph']['identitySpace'],'nodeId':'R1'},
                              'state':'any','lensRefs':refs}]}
        before_files=self.files()
        registry=self.call({'method':'recommendation_catalog'})
        req={'op':'recommendation_edit','transactionId':str(uuid.uuid4()),
             'expectedRegistryRevision':registry['registryRevision'],'action':'create',
             'definition':definition,'note':'Explicit nested lens graph data',
             'attachTo':{'packageId':created['model'],
                         'expectedPackageRevision':src['package']['revision'],
                         'expectedGraphRevision':src['graph']['revision']}}
        self.execute(req)
        refreshed=self.call({'method':'read','packageId':created['model']})
        self.assertEqual(refreshed['graph']['recommendationPackageIds'],[definition['id']])
        hits=refreshed['recommendations']['matches']
        self.assertEqual({m['lensRef']['lensKey'] for m in hits},{'decision-logic','model'})
        self.assertEqual(sum(p['role']=='working' for p in self.call({'method':'catalog'})['packages']),1)
        read_only=self.files()
        self.call({'method':'read','packageId':created['decision-logic']})
        self.call({'method':'read','packageId':created['model']})
        self.assertEqual(self.files(),read_only)
        self.assertNotEqual(before_files,read_only)

    @unittest.skipUnless(os.name=='posix','POSIX handles simulate Windows preview serialization')
    def test_serialized_reads_open_catalog_process_and_write_without_nested_lock(self):
        locks=SourceFileLoader('decision_serialized_handles',str(ROOT/'tests/rdg-preview-serialized-io.py')).load_module()
        io=locks.serialized_io(PREVIEW.preview_io())
        with patch.object(PREVIEW,'preview_io',return_value=io):
            self.start();catalog=self.call({'method':'catalog'})
            ident=next(p['packageId'] for p in catalog['packages'] if p['role']=='working')
            registry=self.call({'method':'recommendation_catalog'})
            self.assertEqual(registry['packages'],[])
            self.assertEqual(registry['participation'],{})
            row=self.call({'method':'read','packageId':ident,'includePlan':True})
            self.assertEqual(row['graph']['coreModel'],'rdg-decision-v1')
            before=self.files()
            with io.reference_lock(self.data,False):
                with self.assertRaises(PermissionError):
                    with io.reference_lock(self.data,False):pass
            self.assertEqual(self.files(),before)
            req=self.schema('core',ident,nodeId='R1',command='add')
            req['data']={'entity':{'id':'D-SERIAL','kind':'decision','title':'Serialized read check','description':'Same real writer'},'initialRelations':[{'id':'R-D-SERIAL','type':'DRIVES','from':'R1','to':'D-SERIAL'}]}
            req['note']='Verify Windows-style handle exclusion';self.execute(req)
            self.execute(self.schema('plan_create',ident));req=self.schema('place',ident,nodeId='D-SERIAL');req['note']='Same owner Plan';self.execute(req)
            saved=self.call({'method':'read','packageId':ident,'includePlan':True});self.stop();self.start()
            restored=self.call({'method':'read','packageId':ident,'includePlan':True})
            self.assertEqual(restored['graph'],saved['graph']);self.assertEqual(restored['plan'],saved['plan'])
            self.assertEqual(self.call({'method':'recommendation_catalog'})['packages'],registry['packages'])

    def test_explorer_session_has_no_implicit_graph_and_keeps_view_cas(self):
        self.start();before=self.files();sid=str(uuid.uuid4())
        empty=self.call({'method':'view_session','action':'create','sessionId':sid})
        self.assertEqual(empty['screens'],[]);self.assertIsNone(empty['activeScreenId'])
        self.assertTrue(empty['explorer']['open']);self.assertEqual(self.files(),before)
        value={k:empty[k] for k in ('activeScreenId','screens','explorer')}
        value['activeScreenId']=str(uuid.uuid4())
        with self.assertRaisesRegex(ValueError,'VIEW_ACTIVE_SCREEN'):
            self.call({'method':'view_session','action':'update','sessionId':sid,'expectedRevision':1,'value':value})
        ident=next(p['packageId'] for p in self.call({'method':'catalog'})['packages'] if p['role']=='working')
        opened=self.call({'method':'view_session','action':'create','sessionId':str(uuid.uuid4()),'packageId':ident})
        value={k:opened[k] for k in ('activeScreenId','screens','explorer')}
        selected=self.call({'method':'view_session','action':'update','sessionId':sid,'expectedRevision':1,'value':value})
        self.assertEqual(selected['screens'][0]['packageId'],ident)
        value.update(activeScreenId=None,screens=[]);value['explorer']['open']=True
        closed=self.call({'method':'view_session','action':'update','sessionId':sid,'expectedRevision':2,'value':value})
        self.assertEqual(closed['screens'],[]);self.assertIsNone(closed['activeScreenId'])
        with self.assertRaisesRegex(ValueError,'VIEW_CAS_MISMATCH'):
            self.call({'method':'view_session','action':'update','sessionId':sid,'expectedRevision':2,'value':value})
        self.assertEqual(self.files(),before)
        document=urllib.request.urlopen(self.server.session_url,timeout=10).read().decode()
        self.assertIn('globalThis.RDG_DECISION_EXPLORER=true;',document)

    def test_unknown_folder_and_other_preview_profile_are_refused_without_changes(self):
        self.data.mkdir();(self.data/'unrelated.txt').write_text('Keep this file')
        before=self.files()
        with self.assertRaisesRegex(ValueError,'EXISTING_DATA_REFUSED'):self.start()
        self.assertEqual(self.files(),before)
        (self.data/'preview.json').write_text(json.dumps({'schemaVersion':1,'kind':'rdg-disposable-manual-preview'}));before=self.files()
        with self.assertRaisesRegex(ValueError,'DECISION_MARKER'):self.start()
        self.assertEqual(self.files(),before)
    def test_http_origin_and_ordinary_port_guards_stay_closed(self):
        self.start();cap=self.server.session_url.rstrip('/').rsplit('/',1)[1]
        req=urllib.request.Request(self.server.session_url+'command',data=b'{"method":"catalog"}',headers={'Content-Type':'application/json','Origin':'http://unrelated.invalid','X-RDG-Session':cap})
        with self.assertRaises(urllib.error.HTTPError) as raised:urllib.request.urlopen(req,timeout=10)
        self.assertIn('HELPER_ORIGIN_DENIED',raised.exception.read().decode())
        loopback=PREVIEW.load('rdg-loopback-helper')
        with self.assertRaisesRegex(ValueError,'APPROVAL_LISTEN_PORT'):loopback.make_server(object(),listen_port=8795)
        with self.assertRaisesRegex(ValueError,'HELPER_MANUAL_PORT'):loopback.make_server(object(),listen_port=8795,manual_session_port=True)
        self.assertTrue((self.data/'session-url.txt').is_file())
        self.assertNotIn('initiatorToken',urllib.request.urlopen(self.server.session_url,timeout=10).read().decode())

if __name__=='__main__':unittest.main()
