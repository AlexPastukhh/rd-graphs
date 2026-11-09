#!/usr/bin/env python3
"""Real HTTP boundary, distinct grants, common writer, remote Agent and restart."""
import base64
import copy
import hashlib
import io
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from wsgiref.simple_server import make_server, WSGIRequestHandler

ROOT = Path(__file__).resolve().parents[1]
HOST = SourceFileLoader('server_test_host', str(ROOT / 'tools/rdg-server.py')).load_module()
REMOTE = SourceFileLoader('server_test_client', str(ROOT / 'tools/rdg-remote-client.py')).load_module()


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


class Server(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rdg-server-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.data = self.base / 'data'; self.secrets = self.base / 'secrets'
        HOST.initialize(self.data, self.secrets)
        self.browser = (self.secrets / 'browser-token.txt').read_text().strip()
        self.agent = (self.secrets / 'agent-token.txt').read_text().strip()
        self.namespace = (self.secrets / 'namespace-id.txt').read_text().strip()
        self.server = None; self.thread = None; self.addCleanup(self.stop)
        self.start()

    def start(self):
        self.server = make_server('127.0.0.1', 0, lambda e, s: [], handler_class=Quiet)
        self.origin = 'http://127.0.0.1:' + str(self.server.server_port)
        self.host = HOST.Host(self.data, self.origin); self.server.set_app(self.host)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.context = {'profile': 'remote', 'origin': self.origin, 'namespaceId': self.namespace,
                        'tokenFile': str(self.secrets / 'agent-token.txt')}
        self.client = REMOTE.Client(self.context)

    def stop(self):
        if self.server:
            self.server.shutdown(); self.server.server_close(); self.thread.join(5); self.server = None

    def files(self):
        return {str(p.relative_to(self.data)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.data.rglob('*') if p.is_file()}

    def raw(self, path, *, message=None, browser=False, token=None, headers=None, method=None):
        credential = token if token is not None else self.browser if browser else self.agent
        auth = ('Basic ' + base64.b64encode(('rdg:' + credential).encode()).decode()
                if browser else 'Bearer ' + credential)
        h = {'Authorization': auth, 'X-RDG-Namespace': self.namespace}
        if message is not None:
            h['Content-Type'] = 'application/json'
        h.update(headers or {})
        request = urllib.request.Request(self.origin + path,
            data=json.dumps(message).encode() if message is not None else None, headers=h, method=method)
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read(), response.headers

    def create(self):
        request = self.client.call({'method': 'schema', 'op': 'create'})['request']
        request.update(path='processes/http-test', role='working', title='Server test',
                       scope='Real isolated server API', coreModel='rdg-decision-v1',
                       rootReason='Verify same owners for browser and AI')
        before = self.files(); preview = self.client.call({'method': 'preflight', 'request': request})
        self.assertEqual(self.files(), before)
        result = self.client.call({'method': 'apply', 'request': request,
                                   'expectedInputBinding': preview['inputBinding']})
        self.assertTrue(result['published'])
        return result['packages'][0]['packageId'], request

    def test_bootstrap_is_empty_idempotent_and_never_exports_secrets(self):
        self.assertNotEqual(self.browser, self.agent)
        self.assertEqual(self.client.catalog()['packages'], [])
        before = self.files(); HOST.initialize(self.data, self.secrets)
        self.assertEqual(self.files(), before)
        for path in self.secrets.iterdir():
            self.assertEqual(path.stat().st_mode & 0o077, 0)
        status, raw, _ = self.raw('/api/capabilities')
        self.assertEqual(status, 200); self.assertIn(b'rdg-application-v1', raw)
        owner = (self.secrets / 'owner-token.txt').read_text().strip()
        for token in (self.browser, self.agent, owner):
            self.assertNotIn(token.encode(), raw)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.raw('/api/capabilities', token=owner)
        self.assertEqual(error.exception.code, 401)
        other = self.base / 'other'; other.mkdir(); (other / 'keep').write_text('unchanged')
        with self.assertRaisesRegex(ValueError, 'EXISTING_DATA_REFUSED'):
            HOST.initialize(other, self.base / 'other-secrets')
        self.assertEqual((other / 'keep').read_text(), 'unchanged')

    def test_auth_host_namespace_origin_and_closed_dispatch(self):
        before = self.files()
        for options, status in [({'token': 'invalid'}, 401),
            ({'token': self.browser}, 401),
            ({'headers': {'Host': 'wrong.invalid'}}, 403),
            ({'headers': {'X-RDG-Namespace': str(uuid.uuid4())}}, 403),
            ({'headers': {'Origin': 'https://wrong.invalid'}}, 403)]:
            with self.subTest(options=list(options)):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    self.raw('/api/command', message={'method': 'catalog'}, **options)
                self.assertEqual(error.exception.code, status)
        for message in [{'method': 'start_process', 'command': 'touch outside'},
                        {'method': 'read_file', 'path': '/etc/passwd'},
                        {'method': 'catalog', 'attribution': 'user'}]:
            with self.assertRaisesRegex(ValueError, 'MESSAGE_FIELDS'):
                self.client.call(message)
        self.assertEqual(self.files(), before)
        with self.assertRaisesRegex(ValueError, 'HTTPS_REQUIRED'):
            HOST.origin_value('http://public.example.com')
        with self.assertRaisesRegex(ValueError, 'HTTPS_REQUIRED'):
            REMOTE.validate_config({**self.context, 'origin': 'http://public.example.com'})

    def test_browser_uses_same_snapshot_and_actor_owned_sessions(self):
        ident, request = self.create()
        _, page, _ = self.raw('/', browser=True)
        self.assertIn(b'RDG_AUTHENTICATED_SERVER=true', page)
        self.assertNotIn(self.browser.encode(), page)
        cap = self.host.caps[self.host.config['browserGrantId']]
        headers = {'Origin': self.origin, 'X-RDG-Session': cap}
        _, raw, _ = self.raw('/session/' + cap + '/command', browser=True,
            headers=headers, message={'method': 'read', 'packageId': ident, 'includePlan': True})
        self.assertEqual(json.loads(raw)['graph'], self.client.call({'method': 'read', 'packageId': ident})['graph'])
        for missing in ('Origin', 'X-RDG-Session'):
            bad = {k: v for k, v in headers.items() if k != missing}
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.raw('/session/' + cap + '/command', browser=True, headers=bad,
                         message={'method': 'catalog'})
            self.assertEqual(error.exception.code, 403)
        session = self.client.call({'method': 'view_session', 'action': 'create',
                                   'sessionId': str(uuid.uuid4()), 'packageId': ident})
        with self.assertRaises(urllib.error.HTTPError):
            self.raw('/session/' + cap + '/command', browser=True, headers=headers,
                message={'method': 'view_session', 'sessionId': session['id']})

    def test_f5_from_previous_browser_session_after_restart_is_safe(self):
        ident, _ = self.create()
        _, old_page, _ = self.raw('/', browser=True)
        self.assertIn(b'RDG_AUTHENTICATED_SERVER=true', old_page)
        old_cap = self.host.caps[self.host.config['browserGrantId']]
        old_path = '/session/' + old_cap + '/'
        before = self.files()
        self.stop(); self.start()
        self.assertNotIn(old_cap, self.host.caps.values())
        new_origin = self.origin
        # The browser follows the same-origin 303 and renders a fresh document.
        status, new_page, headers = self.raw(old_path, browser=True)
        self.assertEqual(status, 200)
        self.assertIn(b'RDG_AUTHENTICATED_SERVER=true', new_page)
        self.assertIn(self.host.caps[self.host.config['browserGrantId']].encode(), new_page)
        self.assertNotIn(old_cap.encode(), new_page)
        self.assertEqual(self.origin, new_origin)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        # Confirm the exact same-origin redirect, not just the final HTML.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs): return None
        authorization = 'Basic ' + base64.b64encode(('rdg:'+self.browser).encode()).decode()
        request = urllib.request.Request(self.origin+old_path,
                                         headers={'Authorization':authorization})
        opener = urllib.request.build_opener(NoRedirect())
        with self.assertRaises(urllib.error.HTTPError) as redirected:
            opener.open(request,timeout=15)
        self.assertEqual(redirected.exception.code,303)
        new_cap = self.host.caps[self.host.config['browserGrantId']]
        self.assertEqual(redirected.exception.headers['Location'],'/session/'+new_cap+'/')
        self.assertEqual(redirected.exception.headers['Cache-Control'],'no-store')
        js_status,js,js_headers=self.raw('/session/'+new_cap+'/viewer.js',browser=True)
        self.assertEqual(js_status,200)
        self.assertTrue(len(js)>1000)
        self.assertEqual(js_headers['Cache-Control'],'no-store')
        self.assertEqual(self.files(), before)
        self.assertEqual(self.client.call({'method':'read','packageId':ident})['graph']['revision'],1)
        # Only authenticated document GETs recover.  Not arbitrary stale files,
        # POST, foreign credentials, wrong host, Origin, or unqualified paths.
        rejected = [
            (old_path+'viewer.js', {}, None, 403),
            ('/session/'+old_cap+'/command', {'Origin':self.origin, 'X-RDG-Session':old_cap}, {'method':'catalog'},403),
            ('/session/bad/', {}, None,403),
            ('/unknown/', {}, None,403),
        ]
        for path,header,body,expected in rejected:
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as failure:
                    self.raw(path,browser=True,headers=header,message=body)
                self.assertEqual(failure.exception.code,expected)
                self.assertNotIn('Location',failure.exception.headers)
        for opts,expected in [({'token':'invalid'},401),
                              ({'headers':{'Host':'wrong.invalid'}},403),
                              ({'headers':{'Origin':'https://wrong.invalid'}},403)]:
            with self.subTest(opts=list(opts)):
                with self.assertRaises(urllib.error.HTTPError) as failure:
                    self.raw(old_path,browser=True,**opts)
                self.assertEqual(failure.exception.code,expected)
                self.assertNotIn('Location',failure.exception.headers)
        # An old command with even a valid new X-RDG-Session is rejected: the
        # server never treats a stale document capability as an API endpoint.
        new_cap = self.host.caps[self.host.config['browserGrantId']]
        with self.assertRaises(urllib.error.HTTPError) as failure:
            self.raw('/session/'+old_cap+'/command',browser=True,
                     headers={'Origin':self.origin,'X-RDG-Session':new_cap},message={'method':'catalog'})
        self.assertEqual(failure.exception.code,403)
        self.assertEqual(self.files(),before)

    def test_real_remote_agent_schema_preflight_apply_receipt_and_restart(self):
        ident, initial = self.create()
        context = self.base / 'remote-context.json'; context.write_text(json.dumps(self.context))
        def cli(command, *args, body=None):
            run = subprocess.run(['python3', '-B', str(ROOT / 'tools/rdg-agent.py'), command,
                '--context', str(context), *args], input=json.dumps(body) if body is not None else None,
                text=True, capture_output=True, timeout=30, env={**os.environ, 'RDG_AUTH_TOKEN': 'ignored'})
            self.assertNotIn(self.agent, run.stdout + run.stderr)
            self.assertEqual(run.returncode, 0, run.stderr)
            return json.loads(run.stdout)
        self.assertTrue(cli('doctor')['ready'])
        req = cli('schema', '--package-id', ident, '--action', 'core_edit', '--node', 'R1')['request']
        req['data']['changes'] = {'title': 'Remote Agent changed this'}
        req['note'] = 'Actual remote Agent request'
        before = self.files(); preview = cli('preflight', body=req); self.assertEqual(self.files(), before)
        self.assertIn('inputBinding', preview)
        result = cli('command', body=req); self.assertTrue(result['saved'])
        again = cli('command', body=req); self.assertTrue(again['idempotent'])
        receipt = cli('receipt', '--package-id', ident, '--transaction-id', req['transactionId'])
        self.assertTrue(receipt['found'])
        row = cli('open', '--package-id', ident, '--detail', 'full')
        self.assertEqual(row['graph']['nodes'][0]['title'], 'Remote Agent changed this')
        self.assertTrue(any(e.get('by') == 'assistant' for e in row['graph']['events']))
        self.stop(); self.start()
        restored = self.client.call({'method': 'read', 'packageId': ident, 'includePlan': True})
        for key in ('graph', 'plan', 'layouts', 'recommendations'):
            self.assertEqual(restored[key], row[key])

    def test_permission_revocation_and_path_escape_do_not_write(self):
        before = self.files()
        request = self.client.call({'method': 'schema', 'op': 'create'})['request']
        request.update(path='../escape', role='working', title='Denied', scope='Denied',
                       coreModel='rdg-decision-v1', rootReason='Denied')
        with self.assertRaises(ValueError):
            self.client.call({'method': 'preflight', 'request': request})
        self.assertEqual(self.files(), before)
        owner = (self.secrets / 'owner-token.txt').read_text().strip()
        self.host.authority.manage('amend', owner, {'id': self.host.config['agentGrantId'], 'grant': {
            'permissions': ['graph.read', 'plan.read'], 'scopes': ['packages/' + self.namespace + '/']}})
        before = self.files()
        request['path'] = 'processes/no-write-permission'
        with self.assertRaises(ValueError):
            self.client.call({'method': 'preflight', 'request': request})
        self.assertEqual(self.files(), before)
        self.host.authority.manage('revoke', owner, {'id': self.host.config['agentGrantId']})
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'AUTH_REQUIRED'):
            self.client.catalog()
        self.assertEqual(self.files(), before)

    def test_redirect_does_not_forward_credentials(self):
        seen = []
        class Target(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                seen.append(self.headers.get('Authorization'));self.send_response(200);self.end_headers()
            do_POST = do_GET
        target = HTTPServer(('127.0.0.1', 0), Target)
        class Redirect(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length', '0')))
                self.send_response(302)
                self.send_header('Location', 'http://127.0.0.1:' + str(target.server_port) + '/trap')
                self.end_headers()
        redirect = HTTPServer(('127.0.0.1', 0), Redirect)
        workers = []
        try:
            for server in (target, redirect):
                thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start();workers.append(thread)
            client = REMOTE.Client({**self.context, 'origin': 'http://127.0.0.1:' + str(redirect.server_port)})
            with self.assertRaisesRegex(ValueError, 'REDIRECT_DENIED'):
                client.catalog()
            self.assertEqual(seen, [])
        finally:
            for server in (target, redirect):server.shutdown();server.server_close()
            for thread in workers:thread.join(5)

    def test_lost_response_after_acceptance_uses_receipt_and_exact_retry(self):
        ident, _ = self.create()
        request = self.client.call({'method': 'schema', 'op': 'core', 'command': 'edit',
                                    'packageId': ident, 'nodeId': 'R1'})['request']
        request['data']['changes'] = {'title': 'Accepted before response loss'}
        request['note'] = 'Real HTTP response loss'
        def drop_response(env, start):
            raw = env['wsgi.input'].read(int(env.get('CONTENT_LENGTH', '0')))
            env['wsgi.input'] = io.BytesIO(raw)
            is_apply = json.loads(raw).get('method') == 'apply'
            captured = []
            result = self.host(env, lambda status, headers: captured.append((status, headers)))
            if is_apply and captured[0][0] == '200 OK':
                self.assertTrue(json.loads(b''.join(result))['published'])
                start('200 OK', [('Content-Type', 'application/json'), ('Content-Length', '100')])
                return [b'{']
            start(*captured[0]);return result
        self.server.set_app(drop_response)
        with self.assertRaises(ValueError) as raised:
            self.client.call({'method': 'apply', 'request': request})
        self.assertFalse(raised.exception.definite)
        self.server.set_app(self.host)
        receipt = self.client.call({'method': 'receipt', 'packageId': ident,
                                    'transactionId': request['transactionId']})
        self.assertTrue(receipt['found'])
        retry = self.client.call({'method': 'apply', 'request': request})
        self.assertTrue(retry['idempotent'])
        graph = self.client.call({'method': 'read', 'packageId': ident})['graph']
        self.assertEqual(graph['nodes'][0]['title'], 'Accepted before response loss')


if __name__ == '__main__':
    unittest.main()
