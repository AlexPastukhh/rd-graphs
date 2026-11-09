#!/usr/bin/env python3
"""Explicit local editor session over the existing Graph/Plan owners.

Binds loopback only while this command runs. No grants are created or widened.
The session uses its configured bearer plus a process-local MAC for manual
attribution; this is not verified human identity or protected-owner approval.
"""
import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import stat
import tempfile
import time

TOOLS = Path(__file__).resolve().parent
WF = SourceFileLoader('manual_workflow', str(TOOLS/'rdg-workflow.py')).load_module()
AUTH = WF.OWNER.AUTH


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode()


class Editor:
    def __init__(self, plan_root, plan_file, graph_root, graph_file, store, token, tools=TOOLS):
        self.plan_root, self.plan_file = Path(plan_root), plan_file
        self.graph_root, self.graph_file = Path(graph_root), graph_file
        self.store, self.token, self.tools = str(store), token, Path(tools)
        self.key = secrets.token_hex(32)
        self.requests = {}
        require((self.tools/'graph-apply.py').is_file(), 'WRITER_UNAVAILABLE')
        require(self.graph_root.resolve() == (self.tools.parent/'graphs').resolve(),
                'HELPER_GRAPH_ROOT_MUST_MATCH_WRITER')
        self.snapshot()  # fail before binding a port if sources/rights unavailable

    def snapshot(self):
        view = WF.read_workflow(self.plan_root, self.plan_file, self.graph_root,
            self.store, self.token, [self.graph_file], include_sources=True)
        graph = view['sources']['graphs'][self.graph_file]
        require(graph.get('actionModel') == 'candidate-v6' and not graph.get('readOnly') and
                not graph.get('templateOnly') and not graph.get('exampleOnly'), 'HELPER_WORKSPACE_REQUIRED')
        require(view['sources']['plan']['identitySpace'] == graph['identitySpace'],
                'HELPER_PLAN_GRAPH_IDENTITY_MISMATCH')
        require(not view['sources']['plan'].get('branches') and all(
            s['kind'] in ('action','requirement') for s in view['sources']['plan']['steps']),
            'HELPER_PLAN_BRANCH_OR_EVENT_EDITOR_NOT_IMPLEMENTED')
        # The configured write file stays fixed; dependencies are authorized read snapshots.
        root=next(n for n in graph['nodes'] if n['id']==graph['rootRequirementId'])
        view['continuationRootId']=root['id'] if graph.get('expansionOf') and root.get('projectionOf')==graph['expansionOf'] else None
        data = AUTH.Authority(self.store)._read()
        _, grant = AUTH.Authority(self.store)._actor(data, self.token)
        view['permissions'] = [p for p in grant['permissions'] if p.startswith(('graph.', 'plan.'))]
        view['graphFile'], view['planFile'] = self.graph_file, self.plan_file
        return view

    def event(self, tid, kind, note, **fields):
        return {'id':'EV-'+tid, 'type':kind, 'by':'user', 'note':note, **fields}

    def operation(self, req, graph):
        action, tid = req['action'], req['transactionId']
        nodes = {n['id']:n for n in graph['nodes']}
        nid = req.get('nodeId')
        node = nodes.get(nid)
        note = req.get('note', '').strip()
        require(note, 'RESULT_OR_CHANGE_NOTE_REQUIRED')
        # Local manual attribution does not unlock protected-owner policy.
        require(not any(n.get('reconsiderationPolicy', {}).get('mode') == 'protected'
                        for n in graph['nodes']), 'HELPER_PROTECTED_OWNER_APPROVAL_UNAVAILABLE')
        def target(kind=None):
            require(node and not node.get('projectionOf') and
                    (not kind or node['kind'] == kind), 'HELPER_TARGET_NOT_OWNED')
        if action == 'add_action':
            require(node and node['kind']=='requirement' and (not node.get('projectionOf') or
                nid==graph.get('rootRequirementId') and graph.get('expansionOf')==node['projectionOf']),
                'HELPER_TARGET_NOT_OWNED_OR_CONTINUATION_ROOT')
            title = req.get('title', '').strip()
            cases = req.get('recommended', '').splitlines()
            negative = req.get('contraindicated', '').splitlines()
            require(title and any(x.strip() for x in cases), 'ACTION_TITLE_AND_CANON_REQUIRED')
            aid = 'A-'+tid
            return {'op':'add_action', 'requirementId':nid,
                'action':{'id':aid,'kind':'action','title':title,'status':'candidate',
                    'actionType':req.get('actionType','general'), 'qrpe':[],
                    'canonBlock':{key:[{'id':prefix+tid+'-'+str(i),'text':x.strip()}
                                      for i,x in enumerate(values) if x.strip()]
                        for key,prefix,values in [('recommended','C-',cases),
                                                 ('contraindicated','N-',negative)]}}}
        if action == 'edit_title':
            target()
            require(node['kind'] in ('action','requirement'), 'HELPER_TARGET_KIND')
            title = req.get('title','').strip();require(title, 'TITLE_REQUIRED')
            return {'op':'graph_edit','action':'edit_node','nodeId':nid,'changes':{'title':title},
                    'event':self.event(tid,'graph_changed',note,operation='edit_node')}
        if action == 'prepare_requirement':
            target('action')
            title=req.get('title','').strip();require(title,'TITLE_REQUIRED')
            return {'op':'graph_edit','action':'prepare_action_requirement','actionId':nid,
                    'node':{'id':'R-'+tid,'kind':'requirement','title':title},
                    'edgeId':'PE-'+tid,'childRole':req.get('childRole'),
                    'event':self.event(tid,'graph_changed',note,operation='prepare_action_requirement')}
        if action == 'edit_canon':
            target('action')
            old=node.get('canonBlock',{})
            require(set(old)<={'recommended','contraindicated'} and all(
                set(c)<={'id','text'} for values in old.values() for c in values),
                'HELPER_COMPLEX_CANON_USE_FULL_API')
            plus=[x.strip() for x in req.get('recommended','').splitlines() if x.strip()]
            minus=[x.strip() for x in req.get('contraindicated','').splitlines() if x.strip()]
            require(plus,'CANON_RECOMMENDED_REQUIRED')
            canon={key:[{'id':prefix+tid+'-'+str(i),'text':x} for i,x in enumerate(values)]
                   for key,prefix,values in [('recommended','C-',plus),('contraindicated','N-',minus)]}
            return {'op':'graph_edit','action':'edit_node','nodeId':nid,'changes':{'canonBlock':canon},
                    'event':self.event(tid,'graph_changed',note,operation='edit_node')}
        if action == 'add_qrpe':
            target()
            text=req.get('title','').strip();require(text,'QRPE_TEXT_REQUIRED')
            return {'op':'append_qrpe','targetId':nid,
                    'issue':{'id':'Q-'+tid,'text':text,'status':'open'}}
        if action == 'select':
            target('action')
            drivers=[e['from'] for e in graph['edges'] if e['type']=='DRIVES' and
                     e['to']==nid and not e.get('archived')]
            require(len(drivers)==1,'ACTION_DRIVER_REQUIRED')
            return {'op':'select_action','actionId':nid,
                    'event':self.event(tid,'action_selected',note,actionId=nid,driverRequirementId=drivers[0])}
        if action == 'complete':
            target()
            require(node['kind'] in ('action','requirement'),'HELPER_TARGET_KIND')
            kind='action_executed' if node['kind']=='action' else 'requirement_achieved'
            return {'op':'record_action_execution' if node['kind']=='action' else 'record_requirement_achievement',
                    'targetId':nid,'event':self.event(tid,kind,note,targetId=nid)}
        if action == 'withdraw':
            target('action')
            drivers=[e['from'] for e in graph['edges'] if e['type']=='DRIVES' and
                     e['to']==nid and not e.get('archived')]
            require(len(drivers)==1,'ACTION_DRIVER_REQUIRED')
            return {'op':'withdraw_action','actionId':nid,'dispositions':req.get('dispositions',[]),
                    'event':self.event(tid,'action_withdrawn',note,actionId=nid,driverRequirementId=drivers[0])}
        raise ValueError('HELPER_UNKNOWN_ACTION')

    def dispatch(self, req):
        require(isinstance(req,dict) and set(req) <= {'action','transactionId','nodeId','title',
            'note','recommended','contraindicated','actionType','childRole','dispositions',
            'expectedGraphRevision','expectedPlanRevision','at','afterStepId','stepId'}, 'HELPER_REQUEST_SCHEMA')
        tid=req.get('transactionId')
        require(isinstance(tid,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,70}',tid),
                'HELPER_TRANSACTION_ID')
        for name in ('action','nodeId','title','note','recommended','contraindicated','actionType','childRole','at','afterStepId','stepId'):
            require(name not in req or isinstance(req[name],str), 'HELPER_FIELD_TYPE_'+name)
        digest=hashlib.sha256(canonical(req)).hexdigest()
        view=self.snapshot()
        old=self.requests.get(tid)
        if old:
            require(old['digest']==digest,'HELPER_TRANSACTION_ID_CONFLICT')
            self.authorize(old)
            if old.get('saved'):
                return self.result(old, replay=True)
            record=old
        else:
            graph=view['sources']['graphs'][self.graph_file]
            action=req.get('action')
            if action in ('place','unplace'):
                require(req.get('expectedPlanRevision')==view['sources']['plan']['revision'],'HELPER_PLAN_CAS_MISMATCH')
                plan=view['sources']['plan']
                if action=='unplace':
                    ops=[{'op':'unplace','stepId':req.get('stepId')}]
                else:
                    node=next((n for n in graph['nodes'] if n['id']==req.get('nodeId')),None)
                    require(node and node['kind'] in ('action','requirement'),
                            'HELPER_TARGET_NOT_OWNED')
                    ref={'graphFile':self.graph_file,'identitySpace':graph['identitySpace'],'nodeId':node['id']}
                    field='actionRef' if node['kind']=='action' else 'requirementRef'
                    matches=[s for s in plan['steps'] if all(s.get(field,{}).get(k)==v for k,v in ref.items())]
                    require(len(matches)<=1 or req.get('stepId'), 'CHOOSE_EXISTING_PLACEMENT')
                    existing=next((s for s in matches if s['id']==req.get('stepId')),None) if req.get('stepId') else next(iter(matches),None)
                    require(not req.get('stepId') or existing, 'PLACEMENT_TARGET_MISMATCH')
                    sid=existing['id'] if existing else 'S-'+node['id']
                    step={'id':sid,'title':node['title'],'kind':node['kind'],'state':'planned',
                          'actionRef' if node['kind']=='action' else 'requirementRef':ref}
                    operation={'op':'place','step':step,'timeConstraints':[],'sequence':[]}
                    if req.get('at'):
                        operation['timeConstraints']=[{'type':'notBefore','at':req['at'],
                            'strength':'soft','basis':req.get('note') or 'Manual placement'}]
                    if req.get('afterStepId'):
                        operation['sequence']=[{'before':req['afterStepId'],'after':sid}]
                    require(operation['timeConstraints'] or operation['sequence'],'EXPLICIT_TIME_OR_ORDER_REQUIRED')
                    ops=[operation]
                request={'transactionId':tid,'op':'edit','file':self.plan_file,
                    'expectedRevision':req['expectedPlanRevision'],'operations':ops}
                record={'kind':'plan','request':request,'digest':digest}
            else:
                require(req.get('expectedGraphRevision')==graph['revision'],'HELPER_GRAPH_CAS_MISMATCH')
                require(not any(n.get('reconsiderationPolicy',{}).get('mode')=='protected'
                    for g in view['sources']['graphs'].values() for n in g['nodes']),
                    'HELPER_PROTECTED_OWNER_APPROVAL_UNAVAILABLE')
                op=self.operation(req,graph)
                package={'schemaVersion':1,'transactionId':tid,'changes':[{'file':self.graph_file,
                    'patch':{'schemaVersion':1,'expectedRevision':req['expectedGraphRevision'],'operations':[op]}}]}
                actor=AUTH.Authority(self.store).authorize_package(self.token,package)
                principal='bearer:'+actor['grantId']
                if op.get('event'):op['event']['authorityPrincipal']=principal
                # Exact signed changes, using the established verifier; no browser HMAC key.
                claim={'principal':principal,'expiresAt':int(time.time())+600,'purpose':'rdg-v6-material-action-v1'}
                package['trustedApproval']=claim
                payload={'transactionId':tid,'changes':package['changes'],**{k:claim[k] for k in ('principal','expiresAt','purpose')}}
                claim['signature']=hmac.new(self.key.encode(),canonical(payload),hashlib.sha256).hexdigest()
                # add_action is candidate preparation, not a material event; no fake human fact.
                if op['op'] in ('add_action','append_qrpe'):package.pop('trustedApproval')
                record={'kind':'graph','package':package,'digest':digest}
            self.requests[tid]=record
        self.authorize(record)
        try:
            if record['kind']=='plan':
                try:
                    receipt=WF.OWNER.apply_request(self.plan_root,self.store,self.token,record['request'])
                except (OSError,ValueError,KeyError,TypeError) as exc:
                    # A failed response can follow durable acceptance. Inspect this
                    # exact transaction before describing it as rejected.
                    try:
                        path=WF.OWNER.safe(self.plan_root,self.plan_file)
                        stored=json.loads(path.read_text())
                        accepted=stored.get('transactions',{}).get(tid)
                    except (OSError,ValueError,KeyError,TypeError):
                        raise ValueError('WRITER_OUTCOME_UNCONFIRMED: Plan read-back unavailable') from exc
                    if (self.plan_root/WF.OWNER.JOURNAL).exists():
                        raise ValueError('WRITER_OUTCOME_UNCONFIRMED: inspect/recover Plan journal before retry') from exc
                    if accepted and accepted.get('requestSHA256')==WF.OWNER.digest(record['request']):
                        receipt={'idempotent':True,**accepted}
                    elif isinstance(exc,OSError):
                        raise ValueError('WRITER_OUTCOME_UNCONFIRMED: Plan result needs read-back') from exc
                    else:raise
            else:
                with tempfile.TemporaryDirectory(prefix='rdg-manual-request-') as tmp:
                    path=Path(tmp)/'request.json';path.write_text(json.dumps(record['package'],ensure_ascii=False))
                    run=subprocess.run(['python3','-B',str(self.tools/'graph-apply.py'),'--package','--patch',str(path)],
                        text=True,capture_output=True,timeout=60,env={**os.environ,
                            'RDG_AUTH_STORE':self.store,'RDG_AUTH_TOKEN':self.token,
                            'RDG_V6_TRUST_KEY':self.key,'RDG_LOCAL_MANUAL_SESSION':'1'})
                    if run.returncode:
                        journal=self.graph_root/'workspaces/.transactions'/(tid+'.json')
                        require(not journal.exists(),'WRITER_OUTCOME_UNCONFIRMED: inspect/recover accepted journal before retry')
                        raise ValueError((run.stderr.strip() or 'WRITER_FAILED')[-1500:])
                    receipt={'transactionId':tid,'writer':run.stdout.strip()}
        except subprocess.TimeoutExpired as exc:
            raise ValueError('WRITER_OUTCOME_UNCONFIRMED: timeout; inspect state/journal before retry') from exc
        record.update(saved=True,receipt=receipt)
        return self.result(record)

    def authorize(self, record):
        auth=AUTH.Authority(self.store)
        if record['kind']=='plan':
            auth.authorize_plan(self.token,['plan.edit'],self.plan_file)
        else:
            auth.authorize_package(self.token,record['package'])

    def result(self, record, replay=False):
        result={'saved':True,'replayed':replay,'receipt':record['receipt']}
        try:result['view']=self.snapshot()
        except (ValueError,OSError,KeyError) as exc:
            result.update(view=None,refreshError=str(exc))
        return result


class FileSession:
    """No network: an explicit session folder on an already authorized mount.

    Files are transient request/response views, not graph/plan owners. Possession
    of this local session folder is a capability within the configured grant.
    """
    def __init__(self, editor, directory):
        self.editor, self.directory = editor, Path(directory)
        require(self.directory.is_absolute(), 'SESSION_DIRECTORY_MUST_BE_ABSOLUTE')
        require(not any(p.is_symlink() for p in [self.directory,*self.directory.parents]),
                'SESSION_DIRECTORY_SYMLINK_DENIED')
        require(self.directory.parent.is_dir() and not self.directory.exists(),
                'CHOOSE_NEW_SESSION_DIRECTORY')
        self.directory.mkdir()
        self.session=secrets.token_urlsafe(32)
        self.seen=set()
        self.write('session.json',{'schemaVersion':1,'kind':'rdg-local-manual-session',
            'active':True,'session':self.session,'graphFile':editor.graph_file,'planFile':editor.plan_file})

    def write(self,name,value):
        # Never follow response symlinks or overwrite any file outside this session folder.
        fd,temp=tempfile.mkstemp(prefix='.response-',dir=self.directory)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as out:
                json.dump(value,out,ensure_ascii=False,allow_nan=False)
                out.flush();os.fsync(out.fileno())
            os.replace(temp,self.directory/name)
        finally:
            if os.path.exists(temp):os.unlink(temp)

    def process_once(self):
        count=0
        for ready in sorted(self.directory.glob('request-*.ready')):
            match=re.fullmatch(r'request-([A-Za-z0-9_-]{1,90})\.ready',ready.name)
            if not match or ready.name in self.seen:continue
            self.seen.add(ready.name);qid=match[1];count+=1
            try:
                require(not ready.is_symlink(),'SESSION_REQUEST_SYMLINK_DENIED')
                path=self.directory/('request-'+qid+'.json')
                with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as source:
                    require(stat.S_ISREG(os.fstat(source.fileno()).st_mode),'SESSION_REGULAR_REQUEST_REQUIRED')
                    raw=source.read(1000001)
                require(len(raw)<=1000000,'HELPER_REQUEST_SIZE')
                req=json.loads(raw)
                require(isinstance(req,dict) and set(req)=={'session','kind','body'} and
                        hmac.compare_digest(str(req['session']),self.session),'HELPER_SESSION_DENIED')
                if req['kind']=='state':
                    require(req['body'] is None,'STATE_REQUEST_BODY')
                    result=self.editor.snapshot()
                else:
                    require(req['kind']=='command','SESSION_UNKNOWN_REQUEST')
                    result=self.editor.dispatch(req['body'])
                response={'ok':True,'result':result}
            except (ValueError,OSError,KeyError,TypeError) as exc:
                response={'ok':False,'error':str(exc),'definite':not str(exc).startswith('WRITER_OUTCOME_UNCONFIRMED')}
            self.write('response-'+qid+'.json',response)
        return count

    def close(self):
        self.write('session.json',{'schemaVersion':1,'kind':'rdg-local-manual-session','active':False})


def make_server(editor):
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
                    boot="globalThis.RDG_LOCAL_WORKFLOW=true;globalThis.RDG_SESSION="+json.dumps(session)+";"
                    body=('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                        '<title>RDG — локальная рабочая сессия</title><body style="background:#101b29;color:#e4edf7;font:16px system-ui">'
                        '<p>RDG · локальная ручная сессия · закройте процесс Helper после работы.</p>'
                        '<script nonce="'+session+'">'+boot+'</script><script src="viewer.js"></script><script src="ui.js"></script></body></html>').encode()
                    self.output(200,body,'text/html; charset=utf-8')
                elif route in ('viewer.js','ui.js'):
                    name='rd-graph-viewer.user.js' if route=='viewer.js' else 'rdg-workflow-ui.js'
                    self.output(200,(TOOLS/name).read_bytes(),'text/javascript; charset=utf-8')
                elif route=='state':
                    require(self.headers.get('X-RDG-Session')==session,'HELPER_SESSION_HEADER_REQUIRED')
                    self.output(200,editor.snapshot())
                else:self.output(404,{'error':'NOT_FOUND'})
            except (ValueError,OSError,KeyError) as exc:self.output(403,{'error':str(exc)})
        def do_POST(self):
            try:
                require(self.route()=='command','NOT_FOUND')
                require(self.headers.get('Origin')==self.server.origin,'HELPER_ORIGIN_DENIED')
                require(self.headers.get('X-RDG-Session')==session,'HELPER_SESSION_HEADER_REQUIRED')
                require(self.headers.get('Content-Type','').split(';')[0]=='application/json','HELPER_CONTENT_TYPE')
                size=int(self.headers.get('Content-Length','0'))
                require(0<size<=1000000,'HELPER_REQUEST_SIZE')
                req=json.loads(self.rfile.read(size))
                self.output(200,editor.dispatch(req))
            except (ValueError,OSError,KeyError,TypeError) as exc:
                self.output(400,{'error':str(exc),'definite':not str(exc).startswith('WRITER_OUTCOME_UNCONFIRMED')})
    server=HTTPServer(('127.0.0.1',0),Handler)
    server.origin='http://127.0.0.1:'+str(server.server_port)
    server.session_url=server.origin+prefix
    return server


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manual-session',action='store_true',required=True,
                        help='Explicitly opt in local manual attribution; does not prove human identity')
    parser.add_argument('--root',required=True)
    parser.add_argument('--file',required=True)
    parser.add_argument('--graph',required=True)
    parser.add_argument('--store',default=os.environ.get('RDG_AUTH_STORE'))
    parser.add_argument('--transport',choices=('files','loopback'),default='files')
    parser.add_argument('--session-dir',help='New session folder on an existing authorized mount; no new sharing')
    args=parser.parse_args()
    require(args.transport!='files' or args.session_dir,'SESSION_DIRECTORY_REQUIRED')
    require(args.store and os.environ.get('RDG_AUTH_TOKEN'),'CONFIGURED_STORE_AND_TOKEN_REQUIRED')
    editor=Editor(args.root,args.file,TOOLS.parent/'graphs',args.graph,args.store,os.environ['RDG_AUTH_TOKEN'])
    if args.transport=='files':
        session=FileSession(editor,args.session_dir)
        print('В Viewer нажмите «План и история» и выберите папку этой сессии: '+str(session.directory),flush=True)
        try:
            while True:
                session.process_once();time.sleep(0.15)
        except KeyboardInterrupt:pass
        finally:session.close()
        return
    server=make_server(editor)
    print('Откройте локальную сессию: '+server.session_url,flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError) as exc:raise SystemExit('ERROR: '+str(exc))
