#!/usr/bin/env python3
"""Shared loopback transport. Domain semantics remain in Application."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.machinery import SourceFileLoader
from pathlib import Path
from html import escape
import hashlib
import json
import secrets

TOOLS=Path(__file__).resolve().parent

def require(ok, message):
    if not ok:raise ValueError(message)

class PortableEditor:
    """Thin manual-session adapter; all semantics and writes belong to Application."""
    def __init__(self,config,token,*,application_factory=None):
        if application_factory is None:
            application_factory=SourceFileLoader('manual_portable_composition',str(TOOLS/'rdg-portable.py')).load_module().application
        self.application=application_factory(config,token,attribution='user')
        self.require_verified_locks=False

    def session_metadata(self):
        return {'profile':'portable','namespaceId':self.application.store.namespace_id}

    def snapshot(self):
        return {**self.application.call({'method':'catalog'}),'profile':'portable'}

    def dispatch(self,request):
        try:
            if self.require_verified_locks and isinstance(request,dict) and request.get('method') in ('apply','preflight'):
                body=request.get('request',{})
                if isinstance(body,dict):
                    protected=(body.get('op') in ('lock_set','lock_remove') or
                        body.get('op') in ('core','paper_edit') and body.get('command') in ('lock_set','lock_remove'))
                    require(not protected,'VERIFIED_APPROVAL_REQUIRED')
            return self.application.call(request)
        except (ValueError,OSError,KeyError,TypeError) as exc:
            tx=request.get('request',{}).get('transactionId') if isinstance(request,dict) else None
            if isinstance(tx,str):
                try:accepted=any(self.application.store.metadata_path(category,tx).is_file() for category in ('accepted','transfers'))
                except ValueError:accepted=False
                if accepted:raise ValueError('WRITER_OUTCOME_UNCONFIRMED: inspect receipt or repeat the exact accepted request') from exc
            raise


def make_server(editor, *, approval_factory=None, listen_port=0, workspace_editor_type=(), banner=None, manual_session_port=False, start_in_explorer=False):
    # Only trusted host code can configure approval. CLI and file sessions do not.
    require(approval_factory is None or isinstance(editor, PortableEditor), 'APPROVAL_PORTABLE_REQUIRED')
    require(type(manual_session_port) is bool and (not manual_session_port or isinstance(editor,PortableEditor)), 'HELPER_MANUAL_PORT')
    require(type(listen_port) is int and 0 <= listen_port <= 65535 and
            (approval_factory is not None or listen_port == 0 or manual_session_port), 'APPROVAL_LISTEN_PORT')
    require(type(start_in_explorer) is bool and (not start_in_explorer or isinstance(editor,PortableEditor)), 'HELPER_EXPLORER_MODE')
    if approval_factory is not None:editor.require_verified_locks=True
    require(banner is None or isinstance(banner,str) and len(banner)<=1000,'HELPER_BANNER')
    notice=escape(banner if banner is not None else 'RDG · локальная ручная сессия · закройте процесс Helper после работы.')
    session=secrets.token_urlsafe(32)
    prefix='/session/'+session+'/'
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup();self.connection.settimeout(10)
        def log_message(self,*args):pass  # no session URLs, bearer or request bodies in logs
        def output(self,status,body,content_type='application/json'):
            if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode()
            self.send_response(status)
            for k,v in {'Content-Type':content_type,'Content-Length':str(len(body)),
                'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
                'Permissions-Policy':'publickey-credentials-get=(self), publickey-credentials-create=(self)',
                'Content-Security-Policy':"default-src 'self'; script-src 'self' 'nonce-"+session+"'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"}.items():
                self.send_header(k,v)
            self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def route(self):
            require(self.headers.get('Host')==self.server.origin.removeprefix('http://'),'HELPER_HOST_DENIED')
            require(self.path.startswith(prefix),'HELPER_SESSION_DENIED')
            return self.path[len(prefix):]
        def do_GET(self):
            try:
                route=self.route()
                if route=='':
                    boot=("globalThis.RDG_LOCAL_PORTABLE=true;" if isinstance(editor,PortableEditor) else "globalThis.RDG_LOCAL_WORKFLOW=true;")+"globalThis.RDG_SESSION="+json.dumps(session)+";"
                    if start_in_explorer:boot+='globalThis.RDG_DECISION_EXPLORER=true;'
                    if self.server.approvals is not None:boot+='globalThis.RDG_APPROVAL_AVAILABLE=true;'
                    body=('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                        '<title>RDG — локальная рабочая сессия</title><body style="background:#101b29;color:#e4edf7;font:16px system-ui">'
                        '<p class="rdg-session-notice">'+notice+'</p>'
                        '<script nonce="'+session+'">'+boot+'</script><script src="viewer.js"></script>'+
                        ('' if isinstance(editor,PortableEditor) else '<script src="ui.js"></script>')+'</body></html>').encode()
                    self.output(200,body,'text/html; charset=utf-8')
                elif route in ('viewer.js','ui.js'):
                    name='rd-graph-viewer.user.js' if route=='viewer.js' else 'rdg-workflow-ui.js'
                    self.output(200,(TOOLS/name).read_bytes(),'text/javascript; charset=utf-8')
                elif route=='state':
                    require(self.headers.get('X-RDG-Session')==session,'HELPER_SESSION_HEADER_REQUIRED')
                    self.output(200,editor.snapshot(self.headers.get('X-RDG-Workspace')) if isinstance(editor,workspace_editor_type) else editor.snapshot())
                else:self.output(404,{'error':'NOT_FOUND'})
            except (ValueError,OSError,KeyError) as exc:self.output(403,{'error':str(exc)})
        def do_POST(self):
            try:
                route=self.route()
                require(route in ('command','admin','dependencies') or
                        route=='approval' and self.server.approvals is not None,'NOT_FOUND')
                require(self.headers.get('Origin')==self.server.origin,'HELPER_ORIGIN_DENIED')
                require(self.headers.get('X-RDG-Session')==session,'HELPER_SESSION_HEADER_REQUIRED')
                require(self.headers.get('Content-Type','').split(';')[0]=='application/json','HELPER_CONTENT_TYPE')
                size=int(self.headers.get('Content-Length','0'))
                require(0<size<=1000000,'HELPER_REQUEST_SIZE')
                req=json.loads(self.rfile.read(size))
                if self.headers.get('X-RDG-Actor') is not None:
                    require(isinstance(editor,PortableEditor) and req.get('method')=='view_session' and self.headers['X-RDG-Actor']==hashlib.sha256(editor.application.token.encode()).hexdigest(),'HELPER_ACTOR_DENIED')
                self.output(200,self.server.approvals.dispatch(req) if route=='approval' else
                    editor.dependencies(req) if route=='dependencies' else
                    editor.admin_dispatch(req) if route=='admin' else editor.dispatch(req))
            except (ValueError,OSError,KeyError,TypeError) as exc:
                self.output(400,{'error':str(exc),'definite':not str(exc).startswith('WRITER_OUTCOME_UNCONFIRMED')})
    host='localhost' if approval_factory is not None else '127.0.0.1'
    server=HTTPServer(('127.0.0.1',listen_port),Handler)
    server.origin='http://'+host+':'+str(server.server_port)
    server.approvals=None
    if approval_factory is not None:
        try:
            server.approvals=approval_factory(server.origin)
            approved=server.approvals.executor
            require(approved.app.store.namespace_id==editor.application.store.namespace_id and
                    approved.app.store.root.resolve()==editor.application.store.root.resolve() and
                    approved.app.authority.path.resolve()==editor.application.authority.path.resolve(),
                    'APPROVAL_OWNER_BINDING')
            require(approved.verifier.origin==server.origin and approved.verifier.rp_id=='localhost',
                    'APPROVAL_ORIGIN_BINDING')
        except BaseException:
            server.server_close();raise
    server.session_url=server.origin+prefix
    return server
