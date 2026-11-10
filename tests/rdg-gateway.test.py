#!/usr/bin/env python3
"""Real HTTP gateway, secret separation, common writer and uncertain outcomes."""
from importlib.machinery import SourceFileLoader
import io
import json
import os
from pathlib import Path
import subprocess
import threading
import unittest
from unittest import mock
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from wsgiref.simple_server import make_server

ROOT = Path(__file__).resolve().parents[1]
BASE = SourceFileLoader('gateway_test_server', str(ROOT / 'tests/rdg-server.test.py')).load_module()
G = SourceFileLoader('gateway_test_gateway', str(ROOT / 'tools/rdg-gateway.py')).load_module()
SETUP = SourceFileLoader('gateway_test_setup', str(ROOT / 'tools/rdg-server-setup.py')).load_module()


class GatewayTests(BASE.Server):
    def setUp(self):
        super().setUp()
        self.private = self.base / 'gateway-private'
        SETUP.prepare_gateway(self.secrets, self.private)
        self.gateway = G.Gateway(self.private / 'credentials.json', self.origin, upstream=self.origin)
        self.gateway_server = make_server('127.0.0.1', 0, self.gateway, handler_class=BASE.Quiet)
        self.gateway_thread = threading.Thread(target=self.gateway_server.serve_forever, daemon=True)
        self.gateway_thread.start(); self.addCleanup(self.stop_gateway)
        self.gateway_url = 'http://127.0.0.1:' + str(self.gateway_server.server_port)

    def stop_gateway(self):
        self.gateway_server.shutdown(); self.gateway_server.server_close(); self.gateway_thread.join(5)

    def private_call(self, message=None, *, path='/api/command', headers=None, method=None):
        h = {'Host': 'rdg-api-gateway:8081', 'X-RDG-Namespace': self.namespace}
        h.update(headers or {})
        if message is not None: h['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.gateway_url + path, headers=h, method=method,
            data=json.dumps(message).encode() if message is not None else None)
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(); self.assertNotIn(self.agent.encode(), raw)
            return json.loads(raw)

    def gateway_create(self):
        request = self.private_call({'method': 'schema', 'op': 'create'})['request']
        request.update(path='api-tests/gateway', role='working', title='Gateway process',
            coreModel='rdg-decision-v1', scope='Private API test', rootReason='Actual API readback')
        before = self.files(); preview = self.private_call({'method': 'preflight', 'request': request})
        self.assertEqual(before, self.files())
        result = self.private_call({'method': 'apply', 'request': request,
            'expectedInputBinding': preview['inputBinding']})
        return result['packages'][0]['packageId'], request, preview


    def test_gateway_markdown_and_literal_search_are_read_only(self):
        pid,_,_=self.gateway_create()
        before=self.files()
        schema=self.private_call({'method':'schema','op':'read'})
        self.assertIn('markdown',schema['read']['format'])
        md=self.private_call({'method':'read','format':'markdown','packageId':pid,
                              'detail':'focus','nodeId':'R1'})
        self.assertTrue(md['reading']['pagesComplete'])
        self.assertTrue(md['markdown'].startswith('# Gateway process'))
        hits=self.private_call({'method':'search','packageId':pid,'query':'R1'})['items']
        self.assertEqual(hits[0]['target']['ref']['nodeId'],'R1')
        self.assertEqual(before,self.files())

    def test_gateway_scoped_focus_branch_http_pages_and_stale_retry(self):
        pid,_,_=self.gateway_create()
        request=self.private_call({'method':'schema','op':'batch','packageId':pid})['request']
        request.update(note='Read-only branch acceptance fixture',steps=[
            {'alias':'child','op':'core','command':'add','data':{
                'entity':{'id':'R-CHILD','kind':'requirement','title':'Child','description':'','scope':'Synthetic'},
                'initialRelations':[{'id':'DERIVE','type':'DERIVES','from':'R1','to':'R-CHILD'}]}},
            {'alias':'action','op':'core','command':'add','data':{
                'entity':{'id':'ACTION','kind':'action','title':'Act','description':'Free text','actionType':'task','lowLevel':False},
                'initialRelations':[{'id':'ACT','type':'REQUIRES_ACTION','from':'R-CHILD','to':'ACTION'}]}}])
        self.private_call({'method':'apply','request':request})
        before=self.files()
        msg={'method':'read','packageId':pid,'detail':'branch','nodeId':'R1','include':['entities','outline'],'limit':1}
        first=self.private_call(msg)
        self.assertEqual(first['data']['entities']['items'][0]['entity']['id'],'R1')
        token=first['data']['entities']['page']['nextCursor']
        more=self.private_call({**msg,'include':['entities'],'cursor':token})
        self.assertEqual(more['snapshot'],first['snapshot'])
        self.assertEqual(more['data']['entities']['items'][0]['entity']['id'],'R-CHILD')
        focus=self.private_call({'method':'read','packageId':pid,'detail':'focus','nodeId':'R-CHILD'})
        self.assertTrue(focus['data']['parents']['items'][0]['title']);self.assertEqual(focus['data']['parents']['items'][0]['nodeId'],'R1')
        self.assertNotIn('R1',{x['entity']['id'] for x in focus['data']['entities']['items']})
        self.assertEqual(before,self.files())
        edit=self.private_call({'method':'schema','op':'core','packageId':pid,'nodeId':'R1','command':'edit'})['request']
        edit.update(note='Concurrent definition change',data={'nodeId':'R1','changes':{'description':'Changed'},'cosmetic':False})
        self.private_call({'method':'apply','request':edit})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.private_call({**msg,'include':['entities'],'cursor':token})
        self.assertIn('CURSOR_STALE',caught.exception.read().decode())

    def test_gateway_decision_theory_schema_edit_readback_and_retry(self):
        pid,_,_=self.gateway_create()
        schema=self.private_call({'method':'schema','op':'core','packageId':pid,'nodeId':'R1','command':'add','entityKind':'canon'})
        self.assertIn('decisionTheory',schema['inputChoices'])
        request=schema['request'];request['note']='B02A through actual HTTP'
        entity=request['data']['entity'];entity.update(title='HTTP theory',guidance='',canons='Bounded use; risky without measurements',knownErrors=[{'id':'e','title':'Assuming the result','description':''}])
        nid=entity['id'];before=self.files();preview=self.private_call({'method':'preflight','request':request});self.assertEqual(self.files(),before)
        result=self.private_call({'method':'apply','request':request,'expectedInputBinding':preview['inputBinding']});self.assertTrue(result['published'])
        self.assertTrue(self.private_call({'method':'apply','request':request})['idempotent'])
        request=self.private_call({'method':'schema','op':'core','packageId':pid,'nodeId':nid,'command':'edit'})['request'];request['note']='Partial legacy-compatible edit';request['data']={'nodeId':nid,'changes':{'guidance':'General from HTTP'},'cosmetic':False}
        self.private_call({'method':'apply','request':request})
        item=self.private_call({'method':'read','packageId':pid,'nodeId':nid,'detail':'item'})['item']
        self.assertEqual(item['guidance'],'General from HTTP');self.assertEqual(item['knownErrors'],entity['knownErrors']);self.assertEqual(item['canons'],entity['canons'])
        self.assertTrue(self.private_call({'method':'receipt','packageId':pid,'transactionId':request['transactionId']})['found'])

    def test_gateway_planning_meta_action_atomic_refs_receipt_retry(self):
        pid,_,_=self.gateway_create();row=self.private_call({'method':'read','packageId':pid})
        req=self.private_call({'method':'schema','op':'plan_action','packageId':pid})['request'];req.update(note='Explicit HTTP meta Action');req['entity'].update(title='Review process definition',description='Ordinary work',subjectRefs=[row['references']['R1']])
        before=self.files();pre=self.private_call({'method':'preflight','request':req});self.assertEqual(before,self.files())
        result=self.private_call({'method':'apply','request':req,'expectedInputBinding':pre['inputBinding']});self.assertTrue(result['published']);self.assertTrue(self.private_call({'method':'apply','request':req})['idempotent'])
        aid=pre['effects']['actionId'];row=self.private_call({'method':'read','packageId':pid,'includePlan':True});self.assertEqual(row['plan']['steps'][0]['ref']['nodeId'],aid);self.assertNotIn(aid,{n['id'] for n in row['graph']['nodes']})
        compact=self.private_call({'method':'read','packageId':pid,'detail':'item','nodeId':aid,'include':['subjects']});self.assertEqual(compact['data']['subjects']['items'][0]['node']['id'],'R1')

    def test_gateway_authored_recommendation_full_compact_and_exact_retry(self):
        pid,_,_=self.gateway_create()
        req=self.private_call({'method':'schema','op':'create','coreModel':'rdg-decision-v1','role':'lens'})['request'];req.update(path='lenses/http-work',role='lens',lensKey='work',rootReason='Isolated HTTP fixture',graph=json.loads((ROOT/'tools/rdg-agent-lenses/work-decision.json').read_text()))
        lensid=self.private_call({'method':'apply','request':req})['packages'][0]['packageId'];lens=self.private_call({'method':'read','packageId':lensid});row=self.private_call({'method':'read','packageId':pid});reg=self.private_call({'method':'recommendation_catalog'})
        definition={'id':str(uuid.uuid4()),'revision':1,'key':'http-advice','title':'An explicit method recommendation','supplied':False,'authored':True,'rules':[{'id':'advice','nodeKinds':['requirement'],'scope':'identity','anchor':{'packageId':pid,'identitySpace':row['graph']['identitySpace'],'nodeId':'R1','kind':'entity'},'state':'any','whenText':'When considering options','usageText':'Consult the principle as needed','lensRefs':[{'packageId':lensid,'identitySpace':lens['graph']['identitySpace'],'lensKey':'work'}]}]}
        req={'op':'recommendation_edit','transactionId':str(uuid.uuid4()),'expectedRegistryRevision':reg['registryRevision'],'action':'create','definition':definition,'note':'Explicit HTTP authoring','attachTo':{'packageId':pid,'expectedPackageRevision':row['package']['revision'],'expectedGraphRevision':row['graph']['revision']}}
        before=self.files();pre=self.private_call({'method':'preflight','request':req});self.assertEqual(before,self.files());self.private_call({'method':'apply','request':req,'expectedInputBinding':pre['inputBinding']});self.assertTrue(self.private_call({'method':'apply','request':req})['idempotent'])
        compact=self.private_call({'method':'read','packageId':pid,'detail':'item','nodeId':'R1','include':['recommendations']});record=compact['data']['recommendations']['items'][0];self.assertEqual(record['usageText'],'Consult the principle as needed');self.assertTrue(record['target']['available'])
        self.assertEqual(record,self.private_call({'method':'read','packageId':pid})['recommendations']['matches'][0])

    def test_gateway_prepare_is_private_idempotent_and_refuses_foreign_data(self):
        before = self.files(); secret = (self.private / 'credentials.json').read_bytes()
        result = SETUP.prepare_gateway(self.secrets, self.private)
        self.assertNotIn(self.agent, json.dumps(result)); self.assertEqual(before, self.files())
        self.assertEqual((self.private / 'credentials.json').read_bytes(), secret)
        self.assertEqual(self.private.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.private / 'credentials.json').stat().st_mode & 0o777, 0o600)
        foreign = self.base / 'foreign'; foreign.mkdir(); (foreign / 'keep').write_text('unchanged')
        with self.assertRaisesRegex(ValueError, 'EXISTING_GATEWAY_DATA_REFUSED'):
            SETUP.prepare_gateway(self.secrets, foreign)
        with self.assertRaisesRegex(ValueError, 'SEPARATE_CREDENTIALS_REQUIRED'):
            SETUP.prepare_gateway(self.secrets, self.secrets)
        with self.assertRaisesRegex(ValueError, 'GATEWAY_NAMESPACE_MISMATCH'):
            SETUP.prepare_gateway(self.secrets, self.base / 'wrong-namespace', expected_namespace=str(uuid.uuid4()))
        self.assertFalse((self.base / 'wrong-namespace').exists())
        value = json.loads(secret); value['token'] = 'rdg_' + 'z' * 50
        (self.private / 'credentials.json').write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'GATEWAY_CREDENTIAL_MISMATCH'):
            SETUP.prepare_gateway(self.secrets, self.private)

    def test_gateway_closed_routes_headers_namespace_and_browser_origin(self):
        before = self.files()
        health = self.private_call(path='/healthz')
        self.assertEqual(health['credentialLocation'], 'gateway-only')
        caps = self.private_call(path='/api/capabilities')
        self.assertEqual(caps['namespaceId'], self.namespace)
        self.assertFalse(caps['humanApprovalAvailable'])
        for headers in ({'Host': 'wrong.invalid'}, {'Origin': self.origin},
            {'Authorization': 'Bearer ignored'}, {'Cookie': 'ignored'},
            {'X-RDG-Namespace': str(uuid.uuid4())}, {'X-Forwarded-Host': 'wrong.invalid'}):
            with self.subTest(headers=list(headers)):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    self.private_call({'method': 'catalog'}, headers=headers)
                self.assertEqual(error.exception.code, 403)
        for path in ('/read_file', '/api/command?url=http://example.invalid', '/session/fake/command'):
            with self.assertRaises(urllib.error.HTTPError):
                self.private_call({'method': 'catalog'}, path=path)
        for message in ({'method': 'start_process', 'command': 'outside'},
                        {'method': 'read_file', 'path': '/run/rdg-gateway/credentials.json'},
                        {'method': 'catalog', 'attribution': 'user'}):
            with self.assertRaises(urllib.error.HTTPError):
                self.private_call(message)
        self.assertEqual(before, self.files())

    def test_gateway_setup_upgrade_preserves_existing_process_and_credentials(self):
        ident, _, _ = self.gateway_create()
        before = self.files(); secret = (self.private / 'credentials.json').read_bytes()
        for _ in range(2):
            run = subprocess.run(['python3', '-B', str(ROOT / 'tools/rdg-server-setup.py'),
                '--data-dir', str(self.data), '--credentials-dir', str(self.secrets),
                '--gateway-dir', str(self.private)], capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            value = json.loads(run.stdout)
            self.assertTrue(value['alreadyInitialized']); self.assertTrue(value['gatewayCredentialPrepared'])
            self.assertEqual(value['namespaceId'], self.namespace)
            self.assertNotIn(self.agent, run.stdout + run.stderr)
            self.assertEqual(before, self.files())
            self.assertEqual((self.private / 'credentials.json').read_bytes(), secret)
        self.assertEqual(self.private_call({'method': 'read', 'packageId': ident})['graph']['title'], 'Gateway process')

    def test_gateway_real_create_retry_receipt_and_same_browser_graph(self):
        ident, request, preview = self.gateway_create()
        retry = self.private_call({'method': 'apply', 'request': request,
                                  'expectedInputBinding': preview['inputBinding']})
        self.assertTrue(retry['idempotent'])
        self.assertTrue(self.private_call({'method': 'receipt', 'packageId': ident,
                                          'transactionId': request['transactionId']})['found'])
        row = self.private_call({'method': 'read', 'packageId': ident, 'includePlan': True})
        self.assertTrue(any(e['by'] == 'assistant' for e in row['graph']['events']))
        _, _, _ = self.raw('/', browser=True)
        cap = self.host.caps[self.host.config['browserGrantId']]
        _, raw, _ = self.raw('/session/' + cap + '/command', browser=True,
            headers={'Origin': self.origin, 'X-RDG-Session': cap},
            message={'method': 'read', 'packageId': ident, 'includePlan': True})
        self.assertEqual(json.loads(raw)['graph'], row['graph'])

    def test_gateway_does_not_cache_revoked_authority(self):
        self.private_call({'method': 'catalog'})
        owner = (self.secrets / 'owner-token.txt').read_text().strip()
        self.host.authority.manage('revoke', owner, {'id': self.host.config['agentGrantId']})
        before = self.files()
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.private_call({'method': 'catalog'})
        self.assertEqual(error.exception.code, 401); self.assertEqual(before, self.files())

    def test_gateway_redirect_and_secret_echo_are_closed(self):
        calls = []; mode = ['redirect']
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(inner):
                calls.append(inner.path)
                if inner.path == '/trap':
                    inner.send_response(200); inner.end_headers(); return
                if mode[0] == 'redirect':
                    inner.send_response(302); inner.send_header('Location', '/trap'); raw = b'{}'
                else:
                    inner.send_response(200); raw = json.dumps({'echo': self.agent}).encode()
                inner.send_header('Content-Length', str(len(raw))); inner.end_headers(); inner.wfile.write(raw)
        upstream = HTTPServer(('127.0.0.1', 0), Upstream)
        worker = threading.Thread(target=upstream.serve_forever, daemon=True); worker.start()
        try:
            self.gateway.upstream = 'http://127.0.0.1:' + str(upstream.server_port)
            for value in ('redirect', 'echo'):
                mode[0] = value
                with self.assertRaises(urllib.error.HTTPError) as error:
                    self.private_call(path='/api/capabilities')
                raw = error.exception.read(); self.assertNotIn(self.agent.encode(), raw)
                self.assertFalse(json.loads(raw)['definite'])
            self.assertNotIn('/trap', calls)
        finally:
            upstream.shutdown(); upstream.server_close(); worker.join(5)

    def test_gateway_loss_after_acceptance_retains_exact_transaction(self):
        ident, _, _ = self.gateway_create()
        request = self.private_call({'method': 'schema', 'op': 'core', 'packageId': ident,
                                     'nodeId': 'R1', 'command': 'edit'})['request']
        request['data']['changes'] = {'title': 'Accepted through private gateway'}
        request['note'] = 'Actual accepted write before simulated HTTP response loss'
        def loss(env, start):
            raw = env['wsgi.input'].read(int(env.get('CONTENT_LENGTH', '0')))
            env['wsgi.input'] = io.BytesIO(raw); captured = []
            result = self.host(env, lambda status, headers: captured.append((status, headers)))
            if json.loads(raw).get('method') == 'apply' and captured[0][0] == '200 OK':
                self.assertTrue(json.loads(b''.join(result))['published'])
                start('200 OK', [('Content-Length', '100')]); return [b'{']
            start(*captured[0]); return result
        self.server.set_app(loss)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.private_call({'method': 'apply', 'request': request})
        self.assertFalse(json.loads(error.exception.read())['definite'])
        self.server.set_app(self.host)
        receipt = self.private_call({'method': 'receipt', 'packageId': ident,
                                     'transactionId': request['transactionId']})
        self.assertTrue(receipt['found'])
        self.assertTrue(self.private_call({'method': 'apply', 'request': request})['idempotent'])

    def test_gateway_tokenless_agent_cli_and_strict_context(self):
        context = {'profile': 'gateway', 'origin': G.ORIGIN, 'namespaceId': self.namespace}
        client = BASE.REMOTE.Client(context); self.assertIsNone(client.token)
        for changes in ({'tokenFile': str(self.secrets / 'agent-token.txt')},
                        {'origin': 'http://host.docker.internal:18880'}, {'upstream': 'http://outside'}):
            with self.assertRaises(ValueError): BASE.REMOTE.Client({**context, **changes})
        path = self.base / 'client-context.json'; path.write_text(json.dumps(context))
        # Route only this test subprocess's DNS to its isolated HTTP fixture.
        routing = """import socket,sys,runpy
original=socket.getaddrinfo
def local(host,port,*args,**kwargs):
 if host=='rdg-api-gateway' and int(port)==8081:return original('127.0.0.1',int(sys.argv[1]),*args,**kwargs)
 return original(host,port,*args,**kwargs)
socket.getaddrinfo=local
port=sys.argv.pop(1);sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')
""".replace("int(sys.argv[1])", str(self.gateway_server.server_port))
        def cli(command, *arguments, body=None):
            run = subprocess.run(['python3', '-B', '-c', routing, str(self.gateway_server.server_port),
                str(ROOT / 'tools/rdg-agent.py'), command, '--context', str(path), *arguments], capture_output=True,
                input=json.dumps(body) if body is not None else None, text=True, timeout=30,
                env={k:v for k,v in os.environ.items() if k not in ('RDG_AUTH_TOKEN','RDG_AUTH_STORE')})
            self.assertNotIn(self.agent, run.stdout + run.stderr); self.assertEqual(run.returncode, 0, run.stderr)
            return json.loads(run.stdout)
        self.assertEqual(cli('doctor')['profile'], 'gateway'); cli('catalog')
        create_form=cli('schema','--action','create')
        self.assertEqual(create_form['request']['coreModel'],'rdg-decision-v1')
        self.assertEqual(create_form['request']['role'],'working')
        self.assertEqual(cli('schema','--action','create','--model-profile','rdg-core-v1')['request']['coreModel'],'rdg-core-v1')
        primary_request=create_form['request'];primary_request.update(path='working/agent-discovery',title='Agent primary profile',scope='Synthetic',rootReason='Agent form acceptance')
        primary_id=cli('command',body=primary_request)['packages'][0]['packageId']
        typed=cli('schema','--package-id',primary_id,'--action','core','--core-command','add','--entity-kind','context')
        self.assertEqual(typed['request']['data']['entity']['kind'],'context')
        ident, _, _ = self.gateway_create()
        request = cli('schema', '--package-id', ident, '--action', 'core_edit', '--node', 'R1')['request']
        request['data']['changes'] = {'title': 'Edited by tokenless Agent'}
        request['note'] = 'Actual private gateway command'
        before = self.files(); cli('preflight', body=request); self.assertEqual(before, self.files())
        self.assertTrue(cli('command', body=request)['saved'])
        self.assertTrue(cli('command', body=request)['idempotent'])
        self.assertTrue(cli('receipt', '--package-id', ident, '--transaction-id', request['transactionId'])['found'])
        self.assertIn('edges',cli('dependencies','--package-id',ident))
        self.assertIn('locks',cli('locks','--package-id',ident))
        compact_history=cli('history','--package-id',ident,'--history-mode','technical')
        self.assertTrue(compact_history['loaded']['events'])
        self.assertIn('items',compact_history['data']['events'])
        self.assertIn('events',cli('history','--package-id',ident,'--history-mode','technical','--detail','full'))

    def test_gateway_decision_typed_form_preflight_receipt_and_retry(self):
        request=self.private_call({'method':'schema','op':'create','coreModel':'rdg-decision-v1'})['request']
        request.update(path='working/discovery',title='Discovery over gateway',scope='Synthetic',rootReason='Gateway acceptance')
        preview=self.private_call({'method':'preflight','request':request})
        result=self.private_call({'method':'apply','request':request,'expectedInputBinding':preview['inputBinding']})
        ident=result['packages'][0]['packageId']
        request=self.private_call({'method':'schema','op':'core','packageId':ident,'nodeId':'R1','command':'add','entityKind':'decision'})['request']
        request['note']='Create a paper option';request['data']['entity']['title']='Paper option'
        before=self.files();preview=self.private_call({'method':'preflight','request':request});self.assertEqual(before,self.files())
        self.assertTrue(self.private_call({'method':'apply','request':request,'expectedInputBinding':preview['inputBinding']})['published'])
        self.assertTrue(self.private_call({'method':'receipt','packageId':ident,'transactionId':request['transactionId']})['found'])
        self.assertTrue(self.private_call({'method':'apply','request':request})['idempotent'])
        view=self.private_call({'method':'read','packageId':ident})
        self.assertEqual(next(n for n in view['graph']['nodes'] if n['kind']=='decision')['selectionState'],'discovered')

    def test_gateway_question_create_answer_assess_readback(self):
        """T3 uses the same wire contract, coordinator and readback as other clients."""
        ident, _, _ = self.gateway_create()

        def command(name, *, node='R1', kind=None):
            form = {'method': 'schema', 'op': 'core', 'packageId': ident,
                    'command': name, 'nodeId': node}
            if kind is not None: form['entityKind'] = kind
            return self.private_call(form)['request']

        def publish(request, *, check_preflight=False):
            before = self.files() if check_preflight else None
            preview = self.private_call({'method': 'preflight', 'request': request})
            if check_preflight: self.assertEqual(before, self.files())
            result = self.private_call({'method': 'apply', 'request': request,
                                        'expectedInputBinding': preview['inputBinding']})
            self.assertTrue(result['published'])
            self.assertTrue(self.private_call({'method': 'receipt', 'packageId': ident,
                              'transactionId': request['transactionId']})['found'])
            return result

        decision = command('add', kind='decision')
        decision_id = decision['data']['entity']['id']
        decision['note'] = 'Synthetic unresolved choice'
        decision['data']['entity'].update(title='Evaluate queueing',
                                           description='Candidate, not selected')
        decision['data']['initialRelations'] = [
            {'id': 'T3-GATEWAY-BASIS', 'type': 'DRIVES',
             'from': 'R1', 'to': decision_id}]
        publish(decision)

        finding = command('add', node=decision_id, kind='finding')
        finding_id = finding['data']['entity']['id']
        finding['note'] = 'Synthetic risk'
        finding['data']['entity'].update(
            title='Unknown peak latency', description='Possible degradation at peak',
            subjectId=decision_id, findingType='risk',
            rationale='No measured busy-hour latency', evidenceIds=[])
        publish(finding)

        context = command('add', node=decision_id, kind='context')
        context_id = context['data']['entity']['id']
        context['note'] = 'Synthetic observed data'
        context['data']['entity'].update(title='Observed normal load',
            description='Only non-peak sample', value='7 requests per second')
        publish(context)

        graph_read = self.private_call({'method': 'read', 'packageId': ident})
        question = command('add', node=decision_id, kind='question')
        qid = question['data']['entity']['id']
        question['note'] = 'What is the busy-hour latency?'
        question['data']['entity'].update(
            title='What is the busy-hour queue latency?',
            description='Normal load does not establish the peak',
            impact='May change the queueing decision',
            answerCondition='Observed p95 during the expected peak',
            relatedRefs=[graph_read['references'][decision_id],
                         graph_read['references'][finding_id]])
        publish(question, check_preflight=True)
        self.assertTrue(self.private_call({'method': 'apply', 'request': question})['idempotent'])

        current = self.private_call({'method': 'read', 'packageId': ident})
        answer = command('question_answer', node=qid)
        answer['note'] = 'Record synthetic observed context'
        answer['data'].update(kind='observation', text='Normal load: 7 rps',
                              sourceRefs=[current['references'][context_id]])
        publish(answer, check_preflight=True)
        self.assertTrue(self.private_call({'method': 'apply', 'request': answer})['idempotent'])

        item = self.private_call({'method': 'read', 'packageId': ident,
                                  'detail': 'item', 'nodeId': qid})['item']
        self.assertEqual(item['kind'], 'question')
        self.assertEqual(len(item['answers']), 1)
        self.assertEqual(item['answers'][0]['kind'], 'observation')
        self.assertEqual(item['answers'][0]['sourceRefs'][0]['nodeId'], context_id)
        self.assertEqual(item['answers'][0]['recordedBy'], 'assistant')
        answer_id = item['answers'][0]['id']

        assess = command('question_assess', node=qid)
        assess['note'] = 'The sample is insufficient'
        assess['data'].update(answerIds=[answer_id], sufficient=False,
                              basis='Peak traffic is not measured')
        publish(assess, check_preflight=True)
        self.assertTrue(self.private_call({'method': 'apply', 'request': assess})['idempotent'])

        item = self.private_call({'method': 'read', 'packageId': ident,
                                  'detail': 'item', 'nodeId': qid})['item']
        self.assertFalse(item['assessment']['sufficient'])
        self.assertEqual(item['assessment']['answerIds'], [answer_id])
        self.assertEqual(item['assessment']['basis'], 'Peak traffic is not measured')
        for related_id in (decision_id, finding_id):
            linked = self.private_call({'method': 'read', 'packageId': ident,
                         'detail': 'item', 'nodeId': related_id,
                         'include': ['questions']})
            self.assertEqual([n['id'] for n in linked['data']['questions']['items']], [qid])

        final = self.private_call({'method': 'read', 'packageId': ident})
        selected = next(n for n in final['graph']['nodes'] if n['id'] == decision_id)
        linked_finding = next(n for n in final['graph']['objects'] if n['id'] == finding_id)
        self.assertEqual(selected['selectionState'], 'discovered')
        self.assertEqual(linked_finding['disposition']['code'], 'unresolved')
        self.assertNotIn(qid, {n['id'] for n in final['graph']['nodes']})

        edited = command('question_answer', node=qid)
        edited['note'] = 'Correct synthetic observation'
        edited['data'] = {
            'nodeId': qid, 'action': 'edit', 'answerId': answer_id,
            'expectedAnswerEventId': item['answers'][0]['eventId'],
            'kind': 'observation', 'text': 'Corrected normal load: 8 rps',
            'sourceRefs': [final['references'][context_id]]}
        publish(edited, check_preflight=True)
        self.assertTrue(self.private_call({'method': 'apply', 'request': edited})['idempotent'])
        changed = self.private_call({'method': 'read', 'packageId': ident,
                                    'detail': 'item', 'nodeId': qid})['item']
        self.assertEqual(changed['answers'][0]['id'], answer_id)
        self.assertEqual(changed['answers'][0]['text'], 'Corrected normal load: 8 rps')
        self.assertTrue(changed['assessmentReviewRequired'])
        self.assertEqual(changed['answerHistory'][0]['action'], 'edit')
        self.assertEqual(changed['answerHistory'][0]['previous']['text'], 'Normal load: 7 rps')

        stale = command('question_answer', node=qid)
        stale['note'] = 'Stale answer version'
        stale['data'] = dict(edited['data'], text='Unapproved later edit')
        before = self.files()
        with self.assertRaises(urllib.error.HTTPError) as stale_error:
            self.private_call({'method': 'apply', 'request': stale})
        self.assertEqual(stale_error.exception.code, 400)
        self.assertEqual(before, self.files())

        remove = command('question_answer', node=qid)
        remove['note'] = 'Remove synthetic observation but keep its history'
        remove['data'] = {'nodeId': qid, 'action': 'remove', 'answerId': answer_id,
                          'expectedAnswerEventId': changed['answers'][0]['eventId']}
        publish(remove, check_preflight=True)
        self.assertTrue(self.private_call({'method': 'apply', 'request': remove})['idempotent'])
        removed = self.private_call({'method': 'read', 'packageId': ident,
                                    'detail': 'item', 'nodeId': qid})['item']
        self.assertEqual(removed['answers'], [])
        self.assertEqual([row['action'] for row in removed['answerHistory']], ['edit', 'remove'])
        self.assertEqual(removed['answerHistory'][1]['previous']['text'], 'Corrected normal load: 8 rps')
        self.assertTrue(removed['assessmentReviewRequired'])
        self.assertEqual(removed['assessment']['answerIds'], [answer_id],
                         'historical assessment keeps the now-removed reference')

        action = command('add', node=decision_id, kind='action')
        action_id = action['data']['entity']['id']
        action['note'] = 'Estimate through public HTTP route'
        action['data']['entity'].update(title='Measure peak',description='Synthetic',estimates={'complexity':'Needs access','time':{'minSeconds':60,'maxSeconds':180}})
        publish(action,check_preflight=True)
        estimate_item=self.private_call({'method':'read','packageId':ident,'detail':'item','nodeId':action_id})['item']
        self.assertEqual(estimate_item['estimates']['time'],{'minSeconds':60,'maxSeconds':180})
        self.assertEqual(estimate_item['result'],{'state':'open','truth':'unknown'})
        invalid=command('edit',node=action_id);invalid['note']='Bad time bounds';invalid['data']={'nodeId':action_id,'changes':{'estimates':{'time':{'minSeconds':3,'maxSeconds':1}}},'cosmetic':False}
        before=self.files()
        with self.assertRaises(urllib.error.HTTPError):self.private_call({'method':'preflight','request':invalid})
        self.assertEqual(before,self.files())

        bad_assessment = command('question_assess', node=qid)
        bad_assessment['note'] = 'Removed answer cannot be accepted as active'
        bad_assessment['data'].update(answerIds=[answer_id], sufficient=True,
                                      basis='Historical record cannot be current evidence')
        before = self.files()
        with self.assertRaises(urllib.error.HTTPError) as invalid_assessment:
            self.private_call({'method': 'apply', 'request': bad_assessment})
        self.assertEqual(invalid_assessment.exception.code, 400)
        self.assertEqual(before, self.files())

        final_assessment = command('question_assess', node=qid)
        final_assessment['note'] = 'Reassess after removing observation'
        final_assessment['data'].update(answerIds=[], sufficient=False,
                                        basis='No active observation remains')
        publish(final_assessment)
        last = self.private_call({'method': 'read', 'packageId': ident,
                                  'detail': 'item', 'nodeId': qid})['item']
        self.assertFalse(last['assessmentReviewRequired'])
        self.assertEqual(len(last['assessmentHistory']), 1)
        self.assertFalse(last['assessment']['sufficient'])

        bad = command('question_answer', node=qid)
        bad['note'] = 'Must not impersonate a user'
        bad['data'].update(kind='user_answer', text='User agreed', sourceRefs=[])
        before = self.files()
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.private_call({'method': 'apply', 'request': bad})
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(before, self.files())

    def test_gateway_atomic_batch_aliases_preflight_and_retry(self):
        ident,_,_=self.gateway_create()
        form=self.private_call({'method':'schema','op':'batch','packageId':ident})
        self.assertEqual(form['batch']['maxSteps'],100)
        request=form['request'];request['note']='Gateway batch acceptance'
        request['steps']=[
            {'alias':'decision','op':'core','command':'add','data':{
                'entity':{'kind':'decision','title':'Gateway option','description':'Pending evaluation'},
                'initialRelations':[{'id':'GW-BATCH-D','type':'DRIVES','from':'R1',
                                     'to':{'$alias':'decision'}}]}},
            {'alias':'action','op':'core','command':'add','data':{
                'entity':{'kind':'action','title':'Gateway task','description':'Not executed',
                          'actionType':'task','lowLevel':False},
                'initialRelations':[{'id':'GW-BATCH-A','type':'REQUIRES_ACTION',
                                     'from':{'$alias':'decision'},'to':{'$alias':'action'}}]}},
            {'alias':'plan','op':'plan_create','title':'Gateway plan'},
            {'alias':'placement','op':'place','nodeId':{'$alias':'action'},
             'at':'2026-11-09'}]
        before=self.files()
        preview=self.private_call({'method':'preflight','request':request})
        self.assertEqual(self.files(),before)
        result=self.private_call({'method':'apply','request':request,
                                  'expectedInputBinding':preview['inputBinding']})
        self.assertTrue(result['published'])
        self.assertEqual(result['packages'][0]['receipt']['effects']['aliasIds'],
                         preview['effects']['aliasIds'])
        self.assertTrue(self.private_call({'method':'apply','request':request})['idempotent'])
        self.assertTrue(self.private_call({'method':'receipt','packageId':ident,
                                          'transactionId':request['transactionId']})['found'])
        read=self.private_call({'method':'read','packageId':ident,'detail':'summary',
                                'include':['plan'],'limit':20})
        self.assertEqual(read['data']['plan']['items'][0]['ref']['nodeId'],
                         preview['effects']['aliasIds']['action'])
        self.assertEqual(read['data']['plan']['items'][0]['state'],'planned')


if __name__ == '__main__':
    names = [name for name in GatewayTests.__dict__ if name.startswith('test_gateway_')]
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(GatewayTests(name) for name in names))
    raise SystemExit(not result.wasSuccessful())
