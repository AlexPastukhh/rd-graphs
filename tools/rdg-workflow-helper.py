#!/usr/bin/env python3
"""Explicit local editor session over the existing Graph/Plan owners.

Binds loopback only while this command runs. No grants are created or widened.
The session uses its configured bearer plus a process-local MAC for manual
attribution; this is not verified human identity or protected-owner approval.
"""
import argparse
import copy
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
LOOPBACK = SourceFileLoader(__name__+'_loopback',str(TOOLS/'rdg-loopback-helper.py')).load_module()
WF = SourceFileLoader('manual_workflow', str(TOOLS/'rdg-workflow.py')).load_module()
AUTH = WF.OWNER.AUTH
COMMANDS = SourceFileLoader('workflow_command_builders',str(TOOLS/'rdg-workflow-commands.py')).load_module()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode()


class Editor:
    def __init__(self, plan_root, plan_file, graph_root, graph_file, store, token, tools=TOOLS, grant_admin_token=None, root_slug=None, source_graph_refs=()):
        self.plan_root, self.plan_file = Path(plan_root), plan_file
        self.graph_root, self.graph_file = Path(graph_root), graph_file
        self.store, self.token, self.tools = str(store), token, Path(tools)
        self.root_slug = root_slug
        self.source_graph_refs = tuple(source_graph_refs)
        self.key = secrets.token_hex(32)
        self.requests = {}
        self.grant_admin_token = grant_admin_token
        self.grant_requests = {}
        if grant_admin_token is not None:
            data = AUTH.Authority(self.store)._read()
            _, administrator = AUTH.Authority(self.store)._actor(data, grant_admin_token)
            require(administrator.get('owner') is True and
                    'grant.admin' in administrator['permissions'],
                    'HELPER_OWNER_ADMIN_REQUIRED')
        require((self.tools/'graph-apply.py').is_file(), 'WRITER_UNAVAILABLE')
        require(self.graph_root.resolve() == (self.tools.parent/'graphs').resolve(),
                'HELPER_GRAPH_ROOT_MUST_MATCH_WRITER')
        self.snapshot()  # fail before binding a port if sources/rights unavailable

    def snapshot(self):
        view = WF.read_workflow(self.plan_root, self.plan_file, self.graph_root,
            self.store, self.token, [self.graph_file,*self.source_graph_refs], include_sources=True)
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
        view['capabilities'] = ['plan.place.from-read-sources','modules.configure']
        modules=WF.OWNER.PLAN.MODULES
        view['moduleCapabilities']={'graph':modules.capabilities(graph,'graph'),
            'plan':modules.capabilities(view['sources']['plan'],'plan')}
        if graph.get('coreModel'):
            core=WF.ACTIVITY.MODEL.core_model()
            view['coreViews']={self.graph_file:{i:core.focused_view(graph,i) for i in [graph['rootRequirementId']]}}
            view['coreCommands']=sorted('core_'+c for c in core.COMMANDS)
        view['grantAdminAvailable'] = self.grant_admin_token is not None
        if self.root_slug is not None:view['contextId'] = self.root_slug
        return view

    def dependencies(self, request=None):
        """Authorized, opt-in Gendocen freshness. No Graph/Plan mutation.

        No Gendocen state or engine installation = explicit unavailable, never
        an empty 'no dependencies' report. History is read only upon expansion.
        """
        request=request or {}
        require(isinstance(request,dict) and set(request)<= {'scope','historyTarget'} and
                all(isinstance(v,str) and v for v in request.values()),
                'DEPENDENCY_REQUEST_SCHEMA')
        project=getattr(self,'dependency_project',None)
        if project is None:
            return {'available':False,'engine':'gendocen',
                    'reason':'Gendocen не подключён. Запустите Helper с --gendocen-project.'}
        bridge=self.tools/'rdg-requirement-gendocen.py'
        require(bridge.is_file(),'GENDOCEN_BRIDGE_UNAVAILABLE')
        module=SourceFileLoader('manual_gendocen_req',str(bridge)).load_module()
        refs=[self.graph_file,*self.source_graph_refs]
        dest=Path(project)
        # Called only after ordinary bearer-backed snapshot grants, with the
        # exact graph closure of this workspace. Preserve independent project
        # history per rootSlug when multiple workspaces share a session.
        result=module.refresh(self.graph_root,refs,dest,self.token,self.store)
        history=request.get('historyTarget')
        if history:
            allowed={row['target'] for row in result['rows']}
            require(history in allowed,'DEPENDENCY_HISTORY_TARGET_NOT_AUTHORIZED')
            return {'available':True,'history':module.engine_cli(dest,'history',history)}
        return {'available':True,'report':module.report(dest,request.get('scope'))}

    def admin_dispatch(self, request):
        """Opt-in owner-only grant panel. Browser never receives an admin bearer.

        Same grant store, lock and authorization as the CLI. A repeated
        transaction returns its original response without issuing a new token.
        """
        require(self.grant_admin_token is not None, 'HELPER_ADMIN_NOT_ENABLED')
        require(isinstance(request, dict) and
                set(request) <= {'operation', 'transactionId', 'expectedRevision', 'id', 'grant'},
                'HELPER_ADMIN_REQUEST_SCHEMA')
        op = request.get('operation')
        require(op in ('list', 'issue', 'amend', 'revoke'), 'HELPER_ADMIN_OPERATION')
        auth = AUTH.Authority(self.store)
        data = auth._read()
        _, actor = auth._actor(data, self.grant_admin_token)
        require(actor.get('owner') is True and 'grant.admin' in actor['permissions'],
                'HELPER_OWNER_ADMIN_REQUIRED')
        if op == 'list':
            require(set(request) == {'operation'}, 'HELPER_ADMIN_LIST_SCHEMA')
            return auth.manage('list', self.grant_admin_token)
        tid = request.get('transactionId')
        require(isinstance(tid, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,70}',tid),
                'HELPER_ADMIN_TRANSACTION_ID')
        require(type(request.get('expectedRevision')) is int and request['expectedRevision'] >= 1,
                'HELPER_ADMIN_EXPECTED_REVISION')
        if op == 'issue':
            require(set(request) == {'operation','transactionId','expectedRevision','grant'},
                    'HELPER_ADMIN_ISSUE_SCHEMA')
            payload = request['grant']
        else:
            expected = {'operation','transactionId','expectedRevision','id'}
            if op == 'amend':expected.add('grant')
            require(set(request) == expected, 'HELPER_ADMIN_MUTATION_SCHEMA')
            require(isinstance(request['id'], str), 'HELPER_ADMIN_GRANT_ID')
            payload = {'id':request['id']}
            if op == 'amend':payload['grant']=request['grant']
        if op in ('issue', 'amend'):
            validated = AUTH.validate_spec(payload if op == 'issue' else payload['grant'])
            require('grant.admin' not in validated['permissions'],
                    'HELPER_ADMIN_DELEGATION_NOT_SUPPORTED')
        digest = hashlib.sha256(canonical(request)).hexdigest()
        prior = self.grant_requests.get(tid)
        if prior:
            require(prior['digest'] == digest, 'HELPER_ADMIN_TRANSACTION_CONFLICT')
            return {**copy.deepcopy(prior['response']), 'replayed': True}
        result = auth.manage(op, self.grant_admin_token, payload,
                             expected_revision=request['expectedRevision'])
        response = {**result, 'replayed': False}
        self.grant_requests[tid] = {'digest': digest, 'response': response}
        return copy.deepcopy(response)

    def event(self, tid, kind, note, **fields):
        return {'id':'EV-'+tid, 'type':kind, 'by':'user', 'note':note, **fields}

    def operation(self,req,graph):
        return COMMANDS.operation(self,req,graph,WF.ACTIVITY.MODEL.core_model())

    def placement_request(self,req,view):
        return COMMANDS.placement_request(self,req,view)

    def dispatch(self, req):
        require(isinstance(req,dict) and set(req) <= {'action','transactionId','nodeId','title',
            'note','recommended','contraindicated','actionType','childRole','dispositions',
            'expectedGraphRevision','expectedPlanRevision','at','afterStepId','stepId','graphFile',
            'modules','disabledModules','module','version','operation','node','data','evidenceRefs'}, 'HELPER_REQUEST_SCHEMA')
        tid=req.get('transactionId')
        require(isinstance(tid,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,70}',tid),
                'HELPER_TRANSACTION_ID')
        for name in ('action','nodeId','title','note','recommended','contraindicated','actionType','childRole','at','afterStepId','stepId','graphFile'):
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
            if action in ('configure_plan_modules','set_module_data'):
                require(req.get('expectedPlanRevision')==view['sources']['plan']['revision'],'HELPER_PLAN_CAS_MISMATCH')
                require(isinstance(req.get('note'),str) and req['note'].strip(),'RESULT_OR_CHANGE_NOTE_REQUIRED')
                operation=({'op':'configure_modules','modules':req.get('modules'),
                            'disabledModules':req.get('disabledModules',[])}
                    if action=='configure_plan_modules' else
                    {'op':'set_module_data','module':req.get('module'),'version':req.get('version'),'data':req.get('data')})
                request={'transactionId':tid,'op':'edit','file':self.plan_file,
                    'expectedRevision':req['expectedPlanRevision'],'operations':[operation]}
                record={'kind':'plan','request':request,'digest':digest}
            elif action in ('place','unplace'):
                require(req.get('expectedPlanRevision')==view['sources']['plan']['revision'],'HELPER_PLAN_CAS_MISMATCH')
                request=self.placement_request(req,view)
                record={'kind':'plan','request':request,'digest':digest}
            else:
                require('graphFile' not in req or req['graphFile']==self.graph_file,'HELPER_GRAPH_WRITE_FILE_BOUND')
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
                    receipt=WF.OWNER.apply_request(self.plan_root,self.store,self.token,record['request'], graph_root=self.graph_root)
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
        # Graph write is already committed. A failed Gendocen refresh must not
        # misreport accepted Graph writes as failed or trigger a duplicate retry.
        # Rebuild subscriptions on every accepted Graph mutation (including an
        # existing Request replay after an earlier engine outage).
        if record['kind']=='graph' and getattr(self,'dependency_project',None) is not None:
            try:
                dependency=self.dependencies({})
                counts={}
                for row in dependency.get('report',{}).get('rows',[]):
                    counts[row['status']]=counts.get(row['status'],0)+1
                result['dependencyUpdate']={'engine':'gendocen','refreshed':True,
                                            'statuses':counts}
            except (ValueError,OSError,KeyError,subprocess.TimeoutExpired) as exc:
                result['dependencyUpdate']={'engine':'gendocen','refreshed':False,
                                            'warning':'Запись Graph сохранена. Gendocen требует повторной синхронизации: '+str(exc)}
        try:result['view']=self.snapshot()
        except (ValueError,OSError,KeyError) as exc:
            result.update(view=None,refreshError=str(exc))
        return result


def automatic_working_contexts(graph_root):
    """Discover writable full working roots; do not mistake legacy or examples
    for candidate-v6 owners. Does not write any files or issue capabilities.
    """
    root=Path(graph_root).resolve()
    index=root/'index.json'
    require(index.is_file() and not index.is_symlink(),'WORKSPACE_GRAPH_INDEX_MISSING')
    manifest=json.loads(index.read_text(encoding='utf8'))
    require(isinstance(manifest,dict) and isinstance(manifest.get('fullGraphs'),list)
            and isinstance(manifest.get('graphs'),list),'WORKSPACE_GRAPH_INDEX_INVALID')
    by_file={row.get('file'):row for row in manifest['graphs']}
    contexts=[]
    for entry in manifest['fullGraphs']:
        file=entry.get('file')
        source=by_file.get(file)
        if not source or not isinstance(file,str) or not file.startswith('workspaces/'):
            continue
        require(re.fullmatch(r'workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json',file) is not None,
                'WORKSPACE_GRAPH_PATH_INVALID')
        target=root/file
        require(target.is_file() and not target.is_symlink() and
                target.resolve().is_relative_to(root) and
                not any(parent.is_symlink() for parent in target.parents if parent.is_relative_to(root)),
                'WORKSPACE_GRAPH_SOURCE_UNSAFE')
        if WF.OWNER.IO.legacy_owner_route(target):continue
        graph=json.loads(target.read_text(encoding='utf8'))
        if graph.get('actionModel')!='candidate-v6' or any(graph.get(x) for x in ('readOnly','templateOnly','exampleOnly')):
            continue
        require(all(graph.get(field)==entry.get(field) for field in ('rootRequirementId','identitySpace')),
                'WORKSPACE_CATALOG_ROOT_MISMATCH')
        slug=entry['slug']
        contexts.append({'rootSlug':slug,'graphFile':entry['file'],
             'planFile':'plans/'+slug+'/plan.json','identitySpace':entry['identitySpace'],
             'rootRequirementId':entry['rootRequirementId']})
    return {'schemaVersion':1,'contexts':contexts}


class WorkspaceEditors:
    """Explicit full-graph -> Plan mappings; never guess a plan from a slug.

    Each context uses the unchanged authorized writers. The shared file-session
    capability does not confer rights absent from the configured bearer.
    """
    def __init__(self, config, plan_root, graph_root, store, token, tools=TOOLS, grant_admin_token=None):
        require(isinstance(config,dict) and set(config)=={'schemaVersion','contexts'} and
                config['schemaVersion']==1 and isinstance(config['contexts'],list) and
                bool(config['contexts']), 'WORKSPACE_CONFIG_SCHEMA')
        self.specs={};self.editors={}
        for row in config['contexts']:
            require(isinstance(row,dict) and set(row)=={'rootSlug','graphFile','planFile','identitySpace','rootRequirementId'},
                    'WORKSPACE_ENTRY_SCHEMA')
            slug=row['rootSlug']
            require(isinstance(slug,str) and re.fullmatch(r'[a-z0-9][a-z0-9_-]*',slug) and
                    slug not in self.specs, 'WORKSPACE_ROOT_DUPLICATE_OR_INVALID')
            require(all(isinstance(row[k],str) and row[k] for k in ('graphFile','planFile','identitySpace','rootRequirementId')),
                    'WORKSPACE_ENTRY_VALUE')
            require(re.fullmatch(r'workspaces/(?:[a-zA-Z0-9_-]+/)+graph\.json',row['graphFile']) is not None,
                    'WORKSPACE_GRAPH_PATH_INVALID')
            require(WF.OWNER.TARGET.fullmatch(row['planFile']) is not None,
                    'WORKSPACE_PLAN_PATH_INVALID')
            require(not any(x['graphFile']==row['graphFile'] or x['planFile']==row['planFile'] or
                            x['identitySpace']==row['identitySpace'] for x in self.specs.values()),
                    'WORKSPACE_OWNER_REUSED')
            self.specs[slug]=dict(row)
        self.plan_root=Path(plan_root);self.graph_root=Path(graph_root)
        self.store,self.token,self.tools=str(store),token,Path(tools)
        self.grant_admin_token=grant_admin_token
        require((self.tools/'graph-apply.py').is_file(), 'WRITER_UNAVAILABLE')
        require(self.graph_root.resolve()==(self.tools.parent/'graphs').resolve(),
                'HELPER_GRAPH_ROOT_MUST_MATCH_WRITER')

    @property
    def contexts(self):
        return [dict(row) for row in self.specs.values()]

    def source_graph_refs(self, row):
        """The same published identitySpace closure used by the full-graph Viewer.

        An unreadable owner is NOT silently dropped: the existing bearer reader
        must authorize the entire source set, or the workspace fails closed.
        """
        index=self.graph_root/'index.json'
        require(index.is_file() and not index.is_symlink(),'WORKSPACE_GRAPH_INDEX_MISSING')
        manifest=json.loads(index.read_text())
        require(isinstance(manifest,dict) and isinstance(manifest.get('graphs'),list)
                and isinstance(manifest.get('fullGraphs'),list),
                'WORKSPACE_GRAPH_INDEX_INVALID')
        roots=[root for root in manifest['fullGraphs'] if root.get('slug')==row['rootSlug']]
        require(bool(roots),'WORKSPACE_CATALOG_ROOT_MISMATCH')
        require(len(roots)==1 and all(roots[0].get(key)==row[value] for key,value in (
                    ('file','graphFile'),('identitySpace','identitySpace'),
                    ('rootRequirementId','rootRequirementId'))),
                'WORKSPACE_CATALOG_ROOT_MISMATCH')
        matches=[item['file'] for item in manifest['graphs']
                 if item.get('identitySpace')==row['identitySpace']]
        require(row['graphFile'] in matches and all(isinstance(file,str) and file for file in matches)
                and len(matches)==len(set(matches)), 'WORKSPACE_CATALOG_GRAPH_SET_INVALID')
        return tuple(file for file in matches if file!=row['graphFile'])

    def ensure_plan(self, row, source_refs):
        """Create the first *durable* empty Plan through the existing bearer writer.

        No graph writes; authorized plan.create is mandatory. A missing Plan is
        never simulated as a saved owner, and an existing path is never reset.
        """
        target=WF.OWNER.safe(WF.OWNER.root_path(self.plan_root),row['planFile'])
        if target.exists():return False
        # Check every owner read and exact root identity BEFORE requesting write.
        report=WF.ACTIVITY.read_activity(self.graph_root,
            [row['graphFile'],*source_refs],self.token,self.store,include_sources=True)
        # Avoid creating an owner that this session cannot subsequently read.
        WF.OWNER.AUTH.Authority(self.store).authorize_plan(self.token,
            ['plan.create','plan.read'],row['planFile'])
        graph=report['sourceGraphs'][row['graphFile']]
        require(graph.get('actionModel')=='candidate-v6' and not any(graph.get(k) for k in
                    ('readOnly','templateOnly','exampleOnly')) and
                graph.get('identitySpace')==row['identitySpace'] and
                graph.get('rootRequirementId')==row['rootRequirementId'],
                'WORKSPACE_NEW_ACTION_MODEL_REQUIRED')
        plan={'schemaVersion':1,'kind':'temporalPlan','id':row['rootSlug'],
              'title':'План во времени · '+graph['title'],
              'identitySpace':row['identitySpace'],'revision':1,'status':'candidate',
              'steps':[],'sequence':[],'branches':[],'timeConstraints':[]}
        WF.OWNER.apply_request(self.plan_root,self.store,self.token,
            {'transactionId':'init-workspace-'+row['rootSlug'],
             'op':'create','file':row['planFile'],'expectedRevision':0,'plan':plan}, graph_root=self.graph_root)
        return True

    def initialize_missing_plans(self):
        # Authorised bootstrap at Helper startup, not lazily on first Action.
        # Preflight all missing owners before creating any of them.
        pending=[]
        for row in self.specs.values():
            refs=self.source_graph_refs(row)
            target=WF.OWNER.safe(WF.OWNER.root_path(self.plan_root),row['planFile'])
            if target.exists():
                saved=WF.OWNER.read_snapshot(self.plan_root,row['planFile'])['plan']
                require(saved['id']==row['rootSlug'] and
                        saved['identitySpace']==row['identitySpace'],
                        'WORKSPACE_EXISTING_PLAN_IDENTITY_MISMATCH')
                continue
            if not target.exists():
                report=WF.ACTIVITY.read_activity(self.graph_root,[row['graphFile'],*refs],
                     self.token,self.store,include_sources=True)
                g=report['sourceGraphs'][row['graphFile']]
                require(g.get('actionModel')=='candidate-v6' and
                        g.get('identitySpace')==row['identitySpace'] and
                        g.get('rootRequirementId')==row['rootRequirementId'] and
                        not any(g.get(k) for k in ('readOnly','templateOnly','exampleOnly')),
                        'WORKSPACE_NEW_ACTION_MODEL_REQUIRED')
                WF.OWNER.AUTH.Authority(self.store).authorize_plan(self.token,
                    ['plan.create','plan.read'],row['planFile'])
                pending.append((row,refs))
        for row,refs in pending:self.ensure_plan(row,refs)
        return len(pending)

    def editor(self, context_id):
        require(isinstance(context_id,str) and context_id in self.specs,
                'WORKSPACE_NOT_REGISTERED')
        if context_id not in self.editors:
            row=self.specs[context_id]
            # Validate published root/closure before allocating a Plan owner.
            refs=self.source_graph_refs(row)
            self.ensure_plan(row,refs)
            graph=WF.ACTIVITY.read_activity(self.graph_root,[row['graphFile']],
                self.token,self.store,include_sources=True)['sourceGraphs'][row['graphFile']]
            require(graph.get('actionModel')=='candidate-v6', 'WORKSPACE_NEW_ACTION_MODEL_REQUIRED')
            owner=Editor(self.plan_root,row['planFile'],self.graph_root,row['graphFile'],
                self.store,self.token,tools=self.tools,grant_admin_token=self.grant_admin_token,
                root_slug=context_id,source_graph_refs=refs)
            g=owner.snapshot()['sources']['graphs'][row['graphFile']]
            require(g['identitySpace']==row['identitySpace'] and
                    g['rootRequirementId']==row['rootRequirementId'],
                    'WORKSPACE_GRAPH_IDENTITY_MISMATCH')
            if isinstance(owner,Editor):
                dep_root=getattr(self,'dependency_project',None)
                owner.dependency_project=Path(dep_root)/context_id if dep_root else None
            self.editors[context_id]=owner
        return self.editors[context_id]

    def snapshot(self, context_id=None):
        require(context_id is not None, 'WORKSPACE_SELECTION_REQUIRED')
        editor=self.editor(context_id)
        row=self.specs[context_id]
        # Catalog membership is mutable; reread before every observation so a
        # new child owner cannot be omitted from an apparently successful view.
        refs=self.source_graph_refs(row)
        if isinstance(editor,Editor):editor.source_graph_refs=refs
        view=editor.snapshot()
        if isinstance(editor,Editor):
            g=view['sources']['graphs'][row['graphFile']]
            require(g['identitySpace']==row['identitySpace'] and
                    g['rootRequirementId']==row['rootRequirementId'],
                    'WORKSPACE_GRAPH_IDENTITY_MISMATCH')
        return view

    def dispatch(self, request):
        require(isinstance(request,dict),'HELPER_REQUEST_SCHEMA')
        context=request.get('contextId')
        require(isinstance(context,str) and context in self.specs,'WORKSPACE_NOT_REGISTERED')
        editor=self.editor(context)
        if isinstance(editor,Editor):editor.source_graph_refs=self.source_graph_refs(self.specs[context])
        return editor.dispatch({k:v for k,v in request.items() if k!='contextId'})

    def dependencies(self,request):
        require(isinstance(request,dict) and isinstance(request.get('contextId'),str) and
                request['contextId'] in self.specs and
                set(request)<= {'contextId','scope','historyTarget'},
                'WORKSPACE_DEPENDENCY_CONTEXT_REQUIRED')
        context=request['contextId'];editor=self.editor(context)
        require(isinstance(editor,Editor),'DEPENDENCY_ACTION_MODEL_NOT_AVAILABLE')
        editor.source_graph_refs=self.source_graph_refs(self.specs[context])
        root=getattr(self,'dependency_project',None)
        editor.dependency_project=Path(root)/context if root is not None else None
        return editor.dependencies({k:v for k,v in request.items() if k!='contextId'})

    def admin_dispatch(self, request):
        require(self.grant_admin_token is not None,'HELPER_ADMIN_NOT_ENABLED')
        return self.editor(next(iter(self.specs))).admin_dispatch(request)


PortableEditor = LOOPBACK.PortableEditor


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
        if isinstance(editor,WorkspaceEditors):editor.initialize_missing_plans()
        self.directory.mkdir(mode=0o700)
        self.session=secrets.token_urlsafe(32)
        self.seen=set()
        context_info=(editor.session_metadata() if isinstance(editor,PortableEditor) else
            {'contexts':editor.contexts} if isinstance(editor,WorkspaceEditors) else
            {'graphFile':editor.graph_file,'planFile':editor.plan_file})
        self.write('session.json',{'schemaVersion':1,'kind':'rdg-local-manual-session',
            'active':True,'session':self.session,**context_info})

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
                    if isinstance(self.editor,WorkspaceEditors):
                        require(isinstance(req['body'],dict) and set(req['body'])=={'contextId'},
                                'WORKSPACE_SELECTION_REQUIRED')
                        result=self.editor.snapshot(req['body']['contextId'])
                    else:
                        require(req['body'] is None,'STATE_REQUEST_BODY')
                        result=self.editor.snapshot()
                elif req['kind']=='dependencies':
                    result=self.editor.dependencies(req['body'])
                elif req['kind']=='admin':
                    result=self.editor.admin_dispatch(req['body'])
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


def make_server(editor, *, approval_factory=None, listen_port=0):
    return LOOPBACK.make_server(editor, approval_factory=approval_factory, listen_port=listen_port, workspace_editor_type=WorkspaceEditors)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manual-session',action='store_true',required=True,
                        help='Explicitly opt in local manual attribution; does not prove human identity')
    parser.add_argument('--root')
    parser.add_argument('--portable-packages',type=Path)
    parser.add_argument('--namespace')
    parser.add_argument('--migration-config',type=Path)
    parser.add_argument('--coordination-root',type=Path)
    parser.add_argument('--file',help='Single-graph Plan file')
    parser.add_argument('--graph',help='Single-graph session; use --contexts-file for multiple full graphs')
    parser.add_argument('--contexts-file',help='Owner-controlled JSON mapping of full graph roots to Plan files')
    parser.add_argument('--auto-workspaces',action='store_true',help='Discover local working graphs and initialize missing Plan owners at session startup with authorized writer')
    parser.add_argument('--initialize-plans-only',action='store_true',help='Create missing real Plan owners with authorized writer; no browser session')
    parser.add_argument('--store',default=os.environ.get('RDG_AUTH_STORE'))
    parser.add_argument('--transport',choices=('files','loopback'),default='files')
    parser.add_argument('--grant-admin',action='store_true',help='Explicit opt-in owner grant management using RDG_AUTH_ADMIN_TOKEN')
    parser.add_argument('--session-dir',help='New session folder on an existing authorized mount; no new sharing')
    parser.add_argument('--gendocen-project',help='Explicit persistent Gendocen state directory, separate from Graph/Plan owners')
    args=parser.parse_args()
    require(args.initialize_plans_only or args.transport!='files' or args.session_dir,'SESSION_DIRECTORY_REQUIRED')
    require(not args.initialize_plans_only or args.auto_workspaces or args.contexts_file,
            'INITIALIZE_PLANS_NEEDS_WORKSPACE_MAPPING')
    require(args.store and os.environ.get('RDG_AUTH_TOKEN'),'CONFIGURED_STORE_AND_TOKEN_REQUIRED')
    require(not args.grant_admin or os.environ.get('RDG_AUTH_ADMIN_TOKEN'), 'HELPER_ADMIN_TOKEN_REQUIRED')
    require(not (args.contexts_file or args.auto_workspaces) or args.transport=='files', 'MULTI_CONTEXT_FILES_ONLY')
    require(sum(map(bool,(args.contexts_file,args.auto_workspaces,args.graph,args.portable_packages)))==1,
            'CHOOSE_SINGLE_GRAPH_OR_CONTEXTS_FILE_OR_AUTO_WORKSPACES')
    require(bool(args.file)==bool(args.graph), 'SINGLE_GRAPH_REQUIRES_PLAN_FILE')
    if args.portable_packages:
        require(args.namespace and not (args.file or args.root or args.initialize_plans_only or args.grant_admin or args.gendocen_project),'PORTABLE_SESSION_ARGUMENTS')
        editor=PortableEditor({'packageRoot':str(args.portable_packages),'namespaceId':args.namespace,
            'coordinationRoot':str(args.coordination_root) if args.coordination_root else None,'authorityStore':args.store,
            'migrationConfig':str(args.migration_config) if args.migration_config else None},os.environ['RDG_AUTH_TOKEN'])
    elif args.contexts_file or args.auto_workspaces:
        require(args.root,'PLAN_ROOT_REQUIRED')
        config=(json.loads(Path(args.contexts_file).read_text()) if args.contexts_file else
                automatic_working_contexts(TOOLS.parent/'graphs'))
        editor=WorkspaceEditors(config,args.root,
            TOOLS.parent/'graphs',args.store,os.environ['RDG_AUTH_TOKEN'],
            grant_admin_token=os.environ['RDG_AUTH_ADMIN_TOKEN'] if args.grant_admin else None)
    else:
        require(args.root,'PLAN_ROOT_REQUIRED')
        editor=Editor(args.root,args.file,TOOLS.parent/'graphs',args.graph,args.store,os.environ['RDG_AUTH_TOKEN'],
                      grant_admin_token=os.environ['RDG_AUTH_ADMIN_TOKEN'] if args.grant_admin else None)
    editor.dependency_project=Path(args.gendocen_project).resolve() if args.gendocen_project else None
    if args.initialize_plans_only:
        count=editor.initialize_missing_plans()
        print('Plan owners initialized: '+str(count)+'; existing plans preserved.',flush=True)
        return
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
