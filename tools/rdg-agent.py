#!/usr/bin/env python3
"""Task-facing RDG client. AI attribution, scoped credentials, canonical writers."""
import argparse
from contextlib import redirect_stdout, contextmanager
import copy
import datetime as dt
import hashlib
from importlib.machinery import SourceFileLoader
import io
import json
import os
from pathlib import Path
import re
import subprocess
import stat
import sys
import tempfile
import uuid
import urllib.request
import urllib.error
from urllib.parse import urlsplit

TOOLS=Path(__file__).resolve().parent
ROOT=TOOLS.parent
WF=SourceFileLoader('agent_workflow',str(TOOLS/'rdg-workflow.py')).load_module()
AUTH=WF.OWNER.AUTH
COMMANDS=SourceFileLoader('agent_command_builders',str(TOOLS/'rdg-workflow-commands.py')).load_module()
PORTABLE=SourceFileLoader('agent_portable_composition',str(TOOLS/'rdg-portable.py')).load_module()
PKG=SourceFileLoader('agent_graph_package',str(TOOLS/'graph-package.py')).load_module()
DEP=SourceFileLoader('agent_dependencies',str(TOOLS/'rdg-requirement-gendocen.py')).load_module()
ACTIONS={'add_action':'add_action','prepare_requirement':'graph_edit.prepare_action_requirement',
         'edit_title':'graph_edit.edit_node','edit_canon':'graph_edit.edit_node','add_qrpe':'append_qrpe',
         'resolve_qrpe':'transition_qrpe','select':'select_action','complete':'record_action_execution',
         'withdraw':'withdraw_action','place':'plan.edit','unplace':'plan.edit'}
FIELDS={'action','transactionId','nodeId','note','title','recommended','contraindicated',
        'actionType','childRole','dispositions','expectedGraphRevision','expectedPlanRevision',
        'at','afterStepId','stepId','graphFile','issueId','evidenceRefs'}


def require(ok,code):
    if not ok:raise ValueError('AGENT_'+code)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def credentials(c=None,*,verify_active=True):
    c=c or {}
    if 'authStore' in c or 'tokenFile' in c:
        require(isinstance(c.get('authStore'),str) and isinstance(c.get('tokenFile'),str),
                'PRIVATE_AUTH_PATHS_REQUIRED')
        path=Path(c['tokenFile'])
        require(path.is_absolute() and path.is_file()
                and not any(p.is_symlink() for p in [path,*path.parents]),'TOKEN_FILE_UNSAFE')
        require(stat.S_IMODE(path.stat().st_mode)&0o077==0,'TOKEN_FILE_MUST_BE_PRIVATE')
        store,token=c['authStore'],path.read_text(encoding='utf8').strip()
    else:
        store,token=os.environ.get('RDG_AUTH_STORE'),os.environ.get('RDG_AUTH_TOKEN')
    require(store and token,'AUTH_NOT_CONFIGURED: use a privately prepared scoped environment or context file references')
    auth=AUTH.Authority(store)
    if verify_active:auth._actor(auth._read(),token)
    return store,token


@contextmanager
def writer_environment(store,token):
    old={key:os.environ.get(key) for key in ('RDG_AUTH_STORE','RDG_AUTH_TOKEN')}
    os.environ.update(RDG_AUTH_STORE=str(store),RDG_AUTH_TOKEN=token)
    try:yield
    finally:
        for key,value in old.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value


def config(path):
    require(path,'CONTEXT_REQUIRED: pass --context FILE or RDG_AGENT_CONTEXT')
    c=json.loads(Path(path).read_text(encoding='utf8'))
    if isinstance(c,dict) and c.get('profile') in ('remote','gateway'):
        remote=SourceFileLoader('agent_remote_client',str(TOOLS/'rdg-remote-client.py')).load_module()
        return remote.validate_config(c)
    if isinstance(c,dict) and c.get('profile')=='portable':
        require({'profile','packageRoot','namespaceId'}<=set(c)<= {'profile','packageRoot','namespaceId','coordinationRoot','packageId','authStore','tokenFile','migrationConfig','helperUrlFile'},'PORTABLE_CONTEXT_SCHEMA')
        require(Path(c['packageRoot']).is_absolute() and (not c.get('coordinationRoot') or Path(c['coordinationRoot']).is_absolute()),'PORTABLE_ABSOLUTE_PATHS')
        return c
    require(isinstance(c,dict) and {'graphFile','planFile','identitySpace'}<=set(c)
        <= {'graphFile','planFile','identitySpace','graphId','planRoot','sourceGraphRefs','gendocenProject','authStore','tokenFile'},
        'CONTEXT_SCHEMA')
    require(isinstance(c['graphFile'],str) and DEP.GRAPH_PATH.fullmatch(c['graphFile'])
        and isinstance(c['planFile'],str) and WF.OWNER.TARGET.fullmatch(c['planFile'])
        and isinstance(c['identitySpace'],str) and bool(c['identitySpace']),'CONTEXT_OWNER')
    require(isinstance(c.get('sourceGraphRefs',[]),list),'CONTEXT_SOURCES')
    c['planRoot']=str(Path(c.get('planRoot',ROOT)).resolve(strict=True))
    return c


CORE=WF.ACTIVITY.MODEL.core_model()
ACTIONS.update({'core_'+c:'graph_edit.core_'+c for c in CORE.COMMANDS - {'remove'}})
FIELDS.update({'data','evidenceRefs'})

class Agent:
    def __init__(self,c):
        self.c=c
        self.store,self.token=credentials(c)
        self.graph_root=ROOT/'graphs'
        self.graph_file,self.plan_file=c['graphFile'],c['planFile']
        self.plan_root=Path(c['planRoot'])
        self.auth=AUTH.Authority(self.store)

    def event(self,tid,kind,note,**fields):
        return {'id':'EV-'+tid,'type':kind,'by':'assistant','note':note,**fields}

    def snapshot(self):
        v=WF.read_workflow(self.plan_root,self.plan_file,self.graph_root,self.store,self.token,
                            [self.graph_file,*self.c.get('sourceGraphRefs',[])],include_sources=True)
        graph=v['sources']['graphs'][self.graph_file]
        require(graph['actionModel']=='candidate-v6' and graph['identitySpace']==self.c['identitySpace']
                and v['sources']['plan']['identitySpace']==self.c['identitySpace'],'OWNER_IDENTITY_MISMATCH')
        require(not self.c.get('graphId') or graph['id']==self.c['graphId'],'GRAPH_ID_MISMATCH')
        v['graphFile'],v['planFile']=self.graph_file,self.plan_file
        return v

    def dependencies(self,v,refresh=False):
        project=self.c.get('gendocenProject')
        if not project:return {'available':False,'reason':'GENDOCEN_PROJECT_NOT_CONFIGURED','completionAttested':False}
        if refresh:
            report=DEP.refresh(self.graph_root,list(v['sources']['graphs']),Path(project),
                               token=self.token,store=self.store)
        else:
            manifest=Path(project)/'rdg-dependency-manifest.json'
            if not manifest.is_file():
                return {'available':False,'reason':'GENDOCEN_PROJECT_NOT_INITIALIZED','completionAttested':False}
            saved=json.loads(manifest.read_text())
            require(saved.get('identitySpace')==self.c['identitySpace']
                and set(saved.get('graphFiles',[]))==set(v['sources']['graphs']),'DEPENDENCY_OWNER_MISMATCH')
            # A report command is explicit; ordinary open never refreshes engine state.
            report=DEP.report(Path(project))
        return {'available':True,'report':report,'refreshed':refresh,
                'freshness':'checked-at-refresh' if refresh else 'not-checked-against-current-sources',
                'completionAttested':False}

    def packet(self,lens='work',node_id=None):
        v=self.snapshot();g=v['sources']['graphs'][self.graph_file];plan=v['sources']['plan']
        focus=next((n for n in [*g['nodes'],*g.get('objects',[])] if n['id']==(node_id or g['rootRequirementId'])),None)
        require(focus is not None,'FOCUS_NOT_FOUND')
        if g.get('coreModel'):
            return self.core_packet(v,g,plan,focus,lens)
        relevant={focus['id']}
        if focus['kind']=='action':
            relevant.update(e['from'] for e in g['edges'] if e['type']=='DRIVES' and e['to']==focus['id'] and not e.get('archived'))
        for edge in g['edges']:
            if edge['from']==focus['id'] and not edge.get('archived'):relevant.add(edge['to'])
        for edge in g['edges']:
            if edge['from'] in relevant and edge['type'] in ('INTRODUCES','OUTCOME_OF') and not edge.get('archived'):
                relevant.add(edge['to'])
        nodes=[n for n in g['nodes'] if n['id'] in relevant]
        issues=[{'nodeId':n['id'],'issue':q} for n in nodes for q in n.get('qrpe',[])
                if q.get('status') in ('open','candidate')]
        states=v['sources']['completion'].get(self.graph_file,{})
        summary={key:copy.deepcopy(v[key]) for key in ('future','unresolved','excludedPlacements')}
        summary['history']=v['history'][-12:]
        summary['focus']=copy.deepcopy(focus)
        summary['lensRecommendations']=copy.deepcopy(g.get('lensRecommendations',[]))
        summary['relatedNodes']=[{k:n[k] for k in ('id','kind','title','status','canonBlock','qrpe')
                                 if k in n} for n in nodes]
        summary['completion']={k:{a:b for a,b in states[k].items() if a!='basis'}
                               for k in relevant if k in states}
        summary['openQuestions']=issues
        summary['context']={'graphFile':self.graph_file,'planFile':self.plan_file,
            'graphId':g['id'],'identitySpace':g['identitySpace'],'rootRequirementId':g['rootRequirementId'],
            'graphRevision':g['revision'],'planRevision':plan['revision']}
        summary['dependencyAvailability']={'configured':bool(self.c.get('gendocenProject')),
            'refreshed':False,'instruction':'Run dependencies explicitly; no check is implied by open.'}
        names=[lens] if isinstance(lens,str) else lens
        require(isinstance(names,list) and bool(names) and len(names)==len(set(names)),'LENS_SELECTION')
        sessions=[self.lens_session(name,g,plan,focus) for name in names]
        summary['lens']=sessions[0]  # Compatibility for clients opening one lens.
        summary['lenses']=sessions
        guidance=lens_catalog()
        summary['availableLenses']=guidance['lenses']
        summary['instructionLimitations']=guidance['limitations']
        summary['commandAccess']={k:v for k,v in self.command_access(focus).items() if not k.startswith('core_')}
        summary['availableCommands']=[key for key,value in summary['commandAccess'].items() if value['permitted']]
        summary['rules']=['candidate / selected / placed / executed are separate facts',
            'canon applicability requires actual assessment; no automatic choice',
            'complete and resolve_qrpe require checked file evidence',
            'after uncertainty query receipt with the SAME transactionId',
            'modules are in development: this client does not modify them']
        return summary

    def core_packet(self,v,g,plan,focus,lens):
        names=[lens] if isinstance(lens,str) else lens
        require(isinstance(names,list) and names and len(names)==len(set(names)),'LENS_SELECTION')
        sessions=[self.lens_session(name,g,plan,focus) for name in names]
        return {'context':{'graphFile':self.graph_file,'planFile':self.plan_file,'graphId':g['id'],
                    'identitySpace':g['identitySpace'],'rootRequirementId':g['rootRequirementId'],
                    'graphRevision':g['revision'],'planRevision':plan['revision'],'coreModel':g['coreModel']},
                'focus':copy.deepcopy(focus),'focusedGraph':CORE.focused_view(g,focus['id']),
                'workGraphs':copy.deepcopy(g['workGraphs']),'workGraphLinks':copy.deepcopy(g['workGraphLinks']),
                'lensRecommendations':copy.deepcopy(CORE.validate_lens_recommendations(g)),
                'lens':sessions[0],'lenses':sessions,'availableLenses':lens_catalog()['lenses'],
                'commandAccess':{k:v for k,v in self.command_access(focus).items() if k.startswith('core_') or k in ('place','unplace')},
                'availableCommands':[k for k,v in self.command_access(focus).items() if v['permitted'] and (k.startswith('core_') or k in ('place','unplace'))],
                'future':v['future'],'unresolved':v['unresolved'],'excludedPlacements':v['excludedPlacements'],
                'history':v['history'][-12:], 'dependencyAvailability':{'configured':bool(self.c.get('gendocenProject')),
                    'refreshed':False,'instruction':'Run dependencies explicitly; Graph core review flags are separate.'},
                'rules':['R: required truth in scope; stale is a request for review, not false.',
                         'A: one shared identity; all current outputs of a selected A are mandatory.',
                         'Lens read/select is not apply; Plan placement is a separate owner.',
                         'Use core commands with data and exact expectedGraphRevision; query the same receipt after uncertainty.']}

    def command_access(self,focus):
        result={}
        for action,operation in ACTIONS.items():
            try:
                if operation=='plan.edit':
                    self.auth.authorize_plan(self.token,['plan.edit'],self.plan_file)
                else:
                    name=operation
                    if action=='complete' and focus['kind']=='requirement':name='record_requirement_achievement'
                    if action=='edit_title' and focus['kind']=='requirement':name='graph_edit.reformulate_requirement'
                    parts=name.split('.');op={'op':parts[0]}
                    if len(parts)>1:op['action']=parts[1]
                    self.auth.authorize_package(self.token,{'schemaVersion':1,'transactionId':'access-inspection',
                        'changes':[{'file':self.graph_file,'patch':{'operations':[op]}}]})
                result[action]={'permitted':True}
            except ValueError as e:result[action]={'permitted':False,'reason':str(e)}
        return result

    def lens_session(self,lens,g,plan,focus):
        entry,source,definition=lens_definition(lens)
        bindings={'targetGraphId':g['id'],'targetRequirementId':focus['id'] if focus['kind']=='requirement' else None,
            'targetActionId':focus['id'] if focus['kind']=='action' else None,
            'relevantInputs':{'identitySpace':g['identitySpace'],'graphFile':self.graph_file,
                'graphSHA256':sha(json.dumps(g,sort_keys=True,ensure_ascii=False).encode()),
                'planSHA256':sha(json.dumps(plan,sort_keys=True,ensure_ascii=False).encode()),
                'nodeId':focus['id']}}
        with tempfile.TemporaryDirectory(prefix='rdg-lens-binding-') as t:
            p=Path(t)/'binding.json';p.write_text(json.dumps(bindings))
            run=subprocess.run(['node',str(TOOLS/'rdg-lens-session-cli.cjs'),'--lens',str(source),
                '--bindings',str(p)],text=True,capture_output=True,timeout=30)
        require(run.returncode==0,'LENS_FAILED: '+run.stderr[-700:])
        session=json.loads(run.stdout)['session']
        return {'key':lens,'id':session['lensId'],'title':entry['title'],
                'lensRecommendations':copy.deepcopy(CORE.validate_lens_recommendations(definition))
                    if definition.get('coreModel')=='rdg-core-v1' else copy.deepcopy(definition.get('lensRecommendations',[])),
            'paperOnly':entry['paperOnly'],'definitionDigest':session['definitionDigest'],
            'bindingDigest':session['bindingDigest'],'rootResult':session['rootResult'],
            'persisted':False,'graphWrites':0,'planWrites':0,
            'graph':session['graph'],'unresolvedQrpe':session['unresolvedQrpe'],
            'unassessedOrStaleCanons':session['unassessedOrStaleCanons'],'steps':[
                {'id':n['id'],'task':n['title'],'description':n.get('description'),
                 'canon':n.get('canonBlock'),'qrpe':n.get('qrpe',[])}
                for n in definition['nodes'] if n['kind']=='action'],
            'interpretation':'R/A graph with potential branches; steps are not a schedule or selected Actions.'}

    def evidence(self,req):
        verifier=SourceFileLoader('agent_file_evidence',str(TOOLS/'rdg-evidence.py')).load_module()
        return verifier.verify(ROOT,req.get('evidenceRefs'),protected=[self.store,self.c.get('tokenFile')],prefix='AGENT_')

    def receipt(self,tid):
        require(isinstance(tid,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,70}',tid),'TRANSACTION_ID')
        self.auth.authorize_graph_read(self.token,[self.graph_file])
        self.auth.authorize_plan(self.token,['plan.read'],self.plan_file)
        current=json.loads(DEP.safe_graph(self.graph_root,self.graph_file).read_text())
        require(current.get('identitySpace')==self.c['identitySpace'] and
                (not self.c.get('graphId') or current.get('id')==self.c['graphId']),'OWNER_IDENTITY_MISMATCH')
        directory=self.graph_root/'workspaces/.transactions'
        require(not any(p.is_symlink() for p in [directory,*directory.parents]),'UNSAFE_RECEIPT')
        path=directory/(tid+'.json')
        if path.is_file():
            require(not path.is_symlink(),'UNSAFE_RECEIPT')
            journal=json.loads(path.read_text())
            rows=[r for r in journal['records'] if r['file']==self.graph_file]
            require(len(rows)==1 and len(journal['records'])==1,'RECEIPT_NOT_IN_CONTEXT')
            row=rows[0]
            return {'found':True,'owner':'graph','transactionId':tid,
                'state':journal['state'],'recordedAt':journal.get('recordedAt'),
                'acceptedGraphRevision':row['after']['revision'],
                'currentGraphRevision':current['revision'],
                'newNodes':[{k:n[k] for k in ('id','kind','title','status') if k in n}
                            for n in row['after']['nodes']
                            if n['id'] not in {x['id'] for x in (row.get('before') or {}).get('nodes',[])}],
                'events':[{k:e[k] for k in ('id','type','by','targetId','actionId','note','evidenceRefs') if k in e}
                    for e in row['after']['events']
                    if e['id'] not in {x['id'] for x in (row.get('before') or {}).get('events',[])}],
                'note':'Acceptance receipt, not permission to repeat work or proof of business success.'}
        pending=WF.OWNER.safe(self.plan_root,WF.OWNER.JOURNAL,True)
        if pending.is_file():
            journal=json.loads(pending.read_text())
            found=journal.get('transactionId')==tid and journal.get('target')==self.plan_file
            return {'found':found,'owner':'plan' if found else None,'transactionId':tid,
                    'state':'prepared','recoveryRequired':True}
        snap=WF.OWNER.read_snapshot(self.plan_root,self.plan_file)
        store=json.loads(WF.OWNER.safe(self.plan_root,self.plan_file).read_text())
        item=store['transactions'].get(tid)
        return {'found':bool(item),'owner':'plan' if item else None,'transactionId':tid,
                'acceptedPlanRevision':item['revision'] if item else None,
                'currentPlanRevision':snap['plan']['revision'],
                'recoveryRequired':(self.plan_root/WF.OWNER.JOURNAL).exists()}

    def command(self,req):
        require(isinstance(req,dict) and set(req)<=FIELDS,'REQUEST_SCHEMA')
        action=req.get('action');require(action in ACTIONS,'ACTION_NOT_AVAILABLE')
        tid=req.get('transactionId');require(isinstance(tid,str)
            and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,70}',tid),'TRANSACTION_ID')
        require(isinstance(req.get('note'),str) and bool(req['note'].strip())
            and req['note']!='REPLACE_WITH_ACTUAL_ACTION_OR_CHECK','MEANINGFUL_NOTE_REQUIRED')
        prior=self.receipt(tid)
        if prior['found']:
            return {'saved':None,'transactionExists':True,'receipt':prior,'requestNotReplayed':True,
                'instruction':'Inspect the accepted operation; this input was not replayed or assumed identical.'}
        require(not prior.get('recoveryRequired'),'RECOVERY_REQUIRED: inspect the pending owner journal')
        v=self.snapshot();g=v['sources']['graphs'][self.graph_file]
        if action in ('place','unplace'):
            require(type(req.get('expectedPlanRevision')) is int,'PLAN_REVISION_REQUIRED')
            request=COMMANDS.placement_request(self,req,v)
            try:
                result=WF.OWNER.apply_request(self.plan_root,self.store,self.token,request, graph_root=self.graph_root)
            except (ValueError,OSError,KeyError,TypeError) as exc:
                return self.writer_error(tid,exc)
            owner='plan'
        else:
            require(type(req.get('expectedGraphRevision')) is int,'GRAPH_REVISION_REQUIRED')
            require('graphFile' not in req or req['graphFile']==self.graph_file,'GRAPH_WRITE_BOUND')
            evidence=self.evidence(req) if (action in ('complete','resolve_qrpe','core_complete','core_falsify','core_resolve_finding') or req.get('evidenceRefs')) else None
            if action=='resolve_qrpe':
                op={'op':'transition_qrpe','targetId':req.get('nodeId'),'issueId':req.get('issueId'),
                    'transition':{'id':'QT-'+tid,'status':'resolved',
                        'recordedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
                        'note':req['note'],'evidenceRefs':evidence}}
            else:
                op=COMMANDS.operation(self,req,g,CORE)
                if evidence:op['event']['evidenceRefs']=evidence
            package={'schemaVersion':1,'transactionId':tid,'changes':[{'file':self.graph_file,
                'patch':{'schemaVersion':1,'expectedRevision':req['expectedGraphRevision'],'operations':[op]}}]}
            try:
                with writer_environment(self.store,self.token),redirect_stdout(io.StringIO()):
                    PKG.execute(package)
            except (ValueError,OSError,KeyError,TypeError) as exc:
                return self.writer_error(tid,exc)
            # The writer returned acceptance. A later receipt read failure
            # must not turn that accepted operation into saved=false.
            try:result=self.receipt(tid)
            except (ValueError,OSError,KeyError,TypeError) as exc:
                result={'available':False,'transactionId':tid,'readError':str(exc)}
            owner='graph'
        response={'saved':True,'owner':owner,'transactionId':tid,'receipt':result,
                  'attribution':'assistant','dependencyRefreshPerformed':False}
        try:response['context']=self.packet('work',req.get('nodeId'))['context']
        except (ValueError,OSError,KeyError,subprocess.TimeoutExpired) as exc:
            response['refreshError']=str(exc)
        return response

    def writer_error(self,tid,error):
        try:receipt=self.receipt(tid)
        except (ValueError,OSError,KeyError,TypeError):
            return {'saved':None,'transactionId':tid,'error':str(error),
                    'instruction':'Writer outcome unconfirmed; restore read access and inspect receipt/recovery.'}
        if receipt['found']:
            complete=receipt.get('state')!='prepared'
            return {'saved':True if complete else None,'transactionId':tid,'receipt':receipt,
                    'acceptedBeforeError':True,'error':str(error),
                    'recoveryRequired':not complete}
        return {'saved':None if receipt.get('recoveryRequired') else False,'transactionId':tid,
                'error':str(error),'recoveryRequired':receipt.get('recoveryRequired',False)}



def read_lens_catalog():
    folder=TOOLS/'rdg-agent-lenses'
    source=folder/'catalog.json'
    require(source.is_file() and not folder.is_symlink() and not source.is_symlink(),'UNSAFE_LENS_CATALOG')
    c=json.loads(source.read_text(encoding='utf8'))
    require(isinstance(c,dict) and c.get('schemaVersion')==1
            and isinstance(c.get('entries'),list) and bool(c['entries']),'LENS_CATALOG_SCHEMA')
    keys=set()
    for entry in c['entries']:
        require(isinstance(entry,dict) and isinstance(entry.get('key'),str)
                and re.fullmatch('[a-z][a-z0-9-]*',entry['key'])
                and entry['key'] not in keys,'LENS_CATALOG_KEY')
        keys.add(entry['key'])
        require(all(isinstance(entry.get(k),str) and entry[k].strip()
                    for k in ('title','purpose','appliesWhen'))
                and type(entry.get('paperOnly')) is bool
                and isinstance(entry.get('companions'),list),'LENS_CATALOG_ENTRY')
        variants=entry.get('profileDefinitions',{})
        require(isinstance(variants,dict) and set(variants)<= {'rdg-core-v1','rdg-decision-v1'} and
                ('definition' in entry and isinstance(entry['definition'],str) and bool(entry['definition'].strip()) or
                 'definition' not in entry and set(variants)=={'rdg-decision-v1'}), 'LENS_PROFILE_DEFINITIONS')
        for name in ([entry['definition']] if 'definition' in entry else [])+list(variants.values()):
            require(isinstance(name,str) and re.fullmatch('[a-z][a-z0-9-]*[.]json',name) and name!='catalog.json', 'UNSAFE_LENS_DEFINITION')
            path=folder/name
            require(path.is_file() and not path.is_symlink() and path.resolve().parent==folder.resolve(),'UNSAFE_LENS_DEFINITION')
    require(all(all(isinstance(k,str) and k in keys for k in e['companions'])
                for e in c['entries']),'LENS_COMPANION_UNKNOWN')
    require(isinstance(c.get('instructionCoverage'),list)
            and isinstance(c.get('limitations'),list),'LENS_CATALOG_COVERAGE')
    return c


def lens_catalog():
    c=read_lens_catalog()
    rows=[]
    for entry in c['entries']:
        name=entry.get('definition') or entry['profileDefinitions']['rdg-decision-v1']
        path=TOOLS/'rdg-agent-lenses'/name
        rows.append({**entry,'definitionFile':'tools/rdg-agent-lenses/'+name,
                     'fileSHA256':sha(path.read_bytes())})
    return {'lenses':rows,'instructionCoverage':c['instructionCoverage'],
            'limitations':c['limitations'],'rules':c.get('rules',[]),
            'graphWrites':0,'planWrites':0,'requiresOwnerContext':False}


def lens_definition(key,profile=None):
    require(isinstance(key,str),'LENS_NOT_AVAILABLE')
    entry=next((e for e in read_lens_catalog()['entries'] if e['key']==key),None)
    require(entry is not None,'LENS_NOT_AVAILABLE')
    name=(entry.get('definition') or entry['profileDefinitions']['rdg-decision-v1']) if profile is None else entry.get('profileDefinitions',{}).get(profile)
    if profile=='rdg-core-v1' and name is None:name=entry.get('definition')
    require(name is not None,'UNSUPPORTED_PROFILE_CAPABILITY:lens')
    path=TOOLS/'rdg-agent-lenses'/name
    definition=json.loads(path.read_text(encoding='utf8'))
    require(profile is None or definition.get('coreModel')==profile,'LENS_PROFILE_MISMATCH')
    return entry,path,definition


def inspect_lens(key,profile=None):
    entry,path,definition=lens_definition(key,profile)
    code="const fs=require('node:fs');const m=require(process.argv[1]);"+\
         "m.parsePreparedLens(JSON.parse(fs.readFileSync(process.argv[2],'utf8')));"
    run=subprocess.run(['node','-e',code,str(TOOLS/'rdg-lens-session.cjs'),str(path)],
                       text=True,capture_output=True,timeout=30)
    require(run.returncode==0,'LENS_FAILED: '+run.stderr[-700:])
    return {'key':key,'title':entry['title'],'graph':definition,
            'validated':True,'bound':False,'graphWrites':0,'planWrites':0}

def portable_application(c):
    if c.get('profile') in ('remote','gateway'):
        return SourceFileLoader('agent_remote_application',str(TOOLS/'rdg-remote-client.py')).load_module().Client(c)
    store,token=credentials(c,verify_active=False)
    return PORTABLE.application({**c,'authorityStore':store},token)


def portable_view_session(c,message):
    require(isinstance(message,dict) and message.get('method')=='view_session','VIEW_MESSAGE_REQUIRED')
    store,token=credentials(c)
    path=Path(c.get('helperUrlFile',''))
    require(path.is_absolute() and path.is_file() and not any(p.is_symlink() for p in [path,*path.parents]) and stat.S_IMODE(path.stat().st_mode)&0o077==0,'PRIVATE_HELPER_URL_FILE_REQUIRED')
    url=path.read_text(encoding='utf8').strip();parsed=urlsplit(url)
    require(parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost') and parsed.port and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and re.fullmatch(r'/session/[A-Za-z0-9_-]{40,80}/',parsed.path),'HELPER_URL_INVALID')
    session=parsed.path.split('/')[2];origin='http://'+parsed.netloc
    request=urllib.request.Request(url+'command',data=json.dumps(message).encode(),method='POST',headers={
        'Content-Type':'application/json','Origin':origin,'X-RDG-Session':session,'X-RDG-Actor':sha(token.encode())})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(request,timeout=15) as response:return json.load(response)
    except urllib.error.HTTPError as exc:
        try:error=json.load(exc).get('error','HELPER_REQUEST_FAILED')
        except (ValueError,AttributeError):error='HELPER_REQUEST_FAILED'
        raise ValueError(error) from None
    except urllib.error.URLError:raise ValueError('AGENT_HELPER_UNAVAILABLE') from None


def portable_command(args,c):
    if args.command=='view_session' and c.get('profile') not in ('remote','gateway'):return portable_view_session(c,json.load(sys.stdin))
    app=portable_application(c);ident=args.package_id or c.get('packageId')
    output_format = getattr(args, 'format', 'json')
    if args.command=='view_session':return app.call(json.load(sys.stdin))
    require(not args.expected_input_binding or args.command in ('command','preflight'),
            'INPUT_BINDING_ONLY_FOR_PREFLIGHT_COMMAND')
    if args.command=='doctor':
        catalog=app.catalog()
        return {'ready':True,'profile':c['profile'],'namespaceId':catalog['namespaceId'],'catalog':catalog,'writes':0}
    if args.command=='catalog':return app.call({'method':'catalog'})
    if args.command=='search':
        return app.call({'method':'search','query':args.query,'scope':args.search_scope,
                         **({'packageId':ident} if args.search_scope=='package' else {}),
                         'limit':args.limit,'cursor':args.cursor})
    if args.command=='theory':
        require(ident and args.theory_id,'THEORY_OWNER_AND_ID_REQUIRED')
        message={'method':'theory_read','packageId':ident,'theoryId':args.theory_id,
                 'collection':args.collection,'detail':args.detail or 'content',
                 'expand':args.expand_sources,'limit':args.limit,'format':output_format}
        if args.item_id:message['itemIds']=args.item_id
        if args.cursor:message['cursor']=args.cursor
        return PORTABLE.module('rdg-theory').read_pages(app,message,args.all_pages)
    if args.command=='recommendation_catalog':return app.call({'method':'recommendation_catalog',**json.load(sys.stdin)})
    if args.command=='approval_request':
        body=json.load(sys.stdin)
        require(isinstance(body,dict) and set(body)=={'request','rationale'},'APPROVAL_MESSAGE_FIELDS')
        return app.call({'method':'approval_request','request':body['request'],'rationale':body['rationale']})
    if args.command=='approval_read':return app.call({'method':'approval_read','requestId':args.transaction_id})
    if args.command=='recover':return app.call({'method':'recover','transactionId':args.transaction_id})
    if args.command=='cancel_migration':return app.call({'method':'cancel_migration','transactionId':args.transaction_id})
    if args.command=='migration_sources':return app.call({'method':'migration_sources'})
    if args.command=='migration_inspect':
        require(args.source_key,'SOURCE_KEY_REQUIRED');return app.call({'method':'migration_inspect','sourceKey':args.source_key})
    if args.command=='lenses':
        catalog=app.catalog()
        return {'lenses':[r for r in catalog['packages'] if r.get('role')=='lens'],'writes':0,
                **{k:catalog[k] for k in ('namespaceId','complete','catalogSHA256') if k in catalog}}
    if args.command=='lens':
        require(args.lens and len(args.lens)==1,'ONE_LENS_REQUIRED')
        rows=[r for r in app.catalog()['packages'] if r.get('role')=='lens' and r.get('lensKey')==args.lens[0] and (not args.model_profile or r.get('coreModel')==args.model_profile)]
        require(len(rows)==1,'LENS_KEY_MISSING_OR_AMBIGUOUS')
        message = {'method':'read','packageId':rows[0]['packageId']}
        if output_format == 'markdown':
            message.update(format='markdown',detail='full',cursor=args.cursor)
            return PORTABLE.module('rdg-structured-markdown').read_pages(app,message,args.all_pages)
        return app.call(message)
    if args.command in ('command','preflight'):
        message={'method':'apply' if args.command=='command' else 'preflight','request':json.load(sys.stdin)}
        if args.expected_input_binding:message['expectedInputBinding']=json.loads(Path(args.expected_input_binding).read_text())
        result=app.call(message)
        return {**result,'saved':result.get('published') is True} if args.command=='command' else result
    require(ident or args.command=='schema' and args.action in ('create','folder_create','folder_move','migrate','read','search','history'),'PACKAGE_ID_REQUIRED')
    if args.command=='schema':
        require(args.action,'ACTION_REQUIRED');op=args.action
        command=op[5:] if op.startswith('core_') else args.core_command
        if op.startswith('core_'):
            role=app.call({'method':'read','packageId':ident,'detail':'summary','include':[]})['package']['role'];op='paper_edit' if role in ('ready','lens') else 'core'
        selectors={}
        if op=='create':
            selectors['coreModel']=args.model_profile or 'rdg-decision-v1'
            if args.role is not None:selectors['role']=args.role
        else:require(args.role is None and args.model_profile is None,'CREATE_SELECTORS_ONLY')
        if args.entity_kind is not None:selectors['entityKind']=args.entity_kind
        return app.call({'method':'schema','op':op,'packageId':None if op=='search' else ident,'nodeId':args.node,
                          'sourcePackageId':args.source_package_id,'command':command,'sourcePath':args.source_folder,'sourceKey':args.source_key,**selectors})
    if args.command=='receipt':return app.call({'method':'receipt','packageId':ident,'transactionId':args.transaction_id})
    if args.command=='resolve':return app.call({'method':'resolve','packageId':ident,'reference':json.load(sys.stdin)})
    if args.command=='source_snapshot':return app.call({'method':'source_snapshot','packageId':ident,'pin':json.load(sys.stdin),**({'view':{'kind':'focus','id':args.node}} if args.node else {})})
    if args.command in ('dependencies','locks'):return app.call({'method':args.command,'packageId':ident})
    if args.command=='history':
        require(args.node is None,'HISTORY_FOCUS_FILTER_UNAVAILABLE')
        view={'kind':'graph'}
        if args.history_mode is not None:view['historyMode']=args.history_mode
        return app.call({'method':'history','packageId':ident,'view':view,
                         'detail':getattr(args,'detail',None) or ('item' if getattr(args,'event_id',None) else 'compact'),
                         **({'eventId':args.event_id} if getattr(args,'event_id',None) else {}),
                         **({'include':args.include} if getattr(args,'include',None) is not None else {}),
                         'limit':getattr(args,'limit',25),
                         'cursor':getattr(args,'cursor',None)})
    view_spec=({'kind':'focus','id':args.node} if args.node else {'kind':'graph'})
    if args.show_excluded_alternatives:
        view_spec['showExcludedAlternatives']=True
    require(args.command=='open','PORTABLE_COMMAND')
    if output_format == 'markdown':
        detail = args.detail or ('focus' if args.node else 'full')
        require(not args.record_id and args.limit == 25,'MARKDOWN_OPTIONS')
        message = {'method':'read','packageId':ident,'format':'markdown','detail':detail,
                   'include':args.include,'cursor':args.cursor,'includePlan':args.include_plan}
        if detail == 'full':
            if args.work_graph:
                require(not args.node,'MARKDOWN_SCOPE')
                view_spec.update(kind='workGraph',id=args.work_graph)
            message['view'] = view_spec
        else:
            require(not args.work_graph and not args.show_excluded_alternatives,'MARKDOWN_SCOPE')
            message['nodeId'] = args.node
        return PORTABLE.module('rdg-structured-markdown').read_pages(app,message,args.all_pages)
    detail=getattr(args,'detail',None) or ('item' if args.node else 'summary')
    require(detail in ('summary','item','full','focus','branch'),'READ_DETAIL')
    require(not getattr(args,'all_pages',False) or detail in ('focus','branch'),'READ_ALL_PAGES_REQUIRES_FOCUS_OR_BRANCH')
    if detail!='full':
        require(not args.show_excluded_alternatives,'READ_EXCLUDED_ALTERNATIVES_REQUIRES_FULL')
        message={'method':'read','packageId':ident,'detail':detail,
                 **({'nodeId':args.node} if args.node else {}),
                 **({'recordId':args.record_id} if getattr(args,'record_id',None) else {}),
                 'include':getattr(args,'include',None) or [],
                 'limit':getattr(args,'limit',25),'cursor':getattr(args,'cursor',None)}
        if detail in ('focus','branch'):
            return PORTABLE.module('rdg-scoped-read').read_pages(app,message,getattr(args,'all_pages',False))
        return app.call(message)
    require(not getattr(args,'include',None) and not getattr(args,'record_id',None) and
            not getattr(args,'cursor',None) and getattr(args,'limit',25)==25,'READ_FULL_OPTIONS_UNSUPPORTED')
    view=app.call({'method':'read','packageId':ident,'includePlan':True,'view':view_spec})
    view['lenses']=[r for r in app.catalog()['packages'] if r.get('role')=='lens' and (not args.lens or r.get('lensKey') in args.lens)]
    view['lensApplicationAutomatic']=False
    return view


def doctor(path):
    checks={'contextConfigured':bool(path),'authStoreConfigured':bool(os.environ.get('RDG_AUTH_STORE')),
            'authTokenConfigured':bool(os.environ.get('RDG_AUTH_TOKEN'))}
    if not path:return {'ready':False,'checks':checks,'next':'Provide a private context file; never paste tokens into chat.'}
    try:
        c=config(path)
        if c.get('authStore') and c.get('tokenFile'):
            checks.update(authStoreConfigured=True,authTokenConfigured=True,authSource='context-files')
        else:checks['authSource']='environment'
        a=Agent(c);v=a.snapshot()
        return {'ready':True,'checks':checks,'context':{'graphFile':a.graph_file,'planFile':a.plan_file,
                'identitySpace':v['sources']['graphs'][a.graph_file]['identitySpace']}}
    except (ValueError,OSError,KeyError,TypeError) as e:
        return {'ready':False,'checks':checks,'error':str(e)}


def catalog(c=None):
    store,token=credentials(c);auth=AUTH.Authority(store)
    index=json.loads((ROOT/'graphs/index.json').read_text());rows=[]
    for entry in index['graphs']:
        if not entry.get('file','').startswith('workspaces/'):continue
        try:auth.authorize_graph_read(token,[entry['file']])
        except ValueError:continue
        if WF.OWNER.IO.legacy_owner_route(DEP.safe_graph(ROOT/'graphs',entry['file'])):continue
        g=json.loads(DEP.safe_graph(ROOT/'graphs',entry['file']).read_text())
        if g.get('actionModel')!='candidate-v6' or any(g.get(k) for k in ('readOnly','exampleOnly','templateOnly')):continue
        rows.append({'graphFile':entry['file'],'id':g['id'],'identitySpace':g['identitySpace'],
            'title':g['title'],'revision':g['revision']})
    return {'graphs':rows,'writes':0}


def core_request_data(graph,command,node_id):
    return COMMANDS.core_request_data(graph,command,node_id,CORE)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['doctor','catalog','lenses','lens','open','theory','schema','command','receipt','dependencies','locks','preflight','history','resolve','source_snapshot','migration_sources','migration_inspect','recover','cancel_migration','approval_request','approval_read','view_session','recommendation_catalog','search'])
    p.add_argument('--context',default=os.environ.get('RDG_AGENT_CONTEXT'))
    p.add_argument('--lens',action='append',help='Registered lens key; repeat for several lenses')
    p.add_argument('--node')
    p.add_argument('--theory-id')
    p.add_argument('--collection',choices=['overview','canons','recommendations'],default='overview')
    p.add_argument('--item-id',action='append',help='Owned entry ID; repeat for several entries')
    p.add_argument('--expand-sources',action='store_true',help='Explicitly fetch one level of source content')
    p.add_argument('--format',choices=['json','markdown'],default='json')
    p.add_argument('--query',help='Literal text for search')
    p.add_argument('--search-scope',choices=['package','catalog'],default='package')
    p.add_argument('--work-graph',help='Working Graph ID for a full Markdown read')
    p.add_argument('--include-plan',action='store_true',help='Include Plan in a full Markdown read')
    p.add_argument('--model-profile',choices=['rdg-core-v1','rdg-decision-v1'],help='Lens profile or create-schema profile; new processes default to rdg-decision-v1')
    p.add_argument('--role',choices=['working','ready','lens'],help='Role for schema --action create')
    p.add_argument('--entity-kind',choices=['requirement','decision','action','canon','context','info','finding','question'],help='Entity type for schema core/add')
    p.add_argument('--history-mode',choices=['important','meaningful','technical','all'])
    p.add_argument('--detail',choices=['summary','content','item','full','compact','focus','branch'],
                   help='item: one body (default with --node); focus: existing nearest scope; branch: all structural downstream')
    p.add_argument('--all-pages',action='store_true',help='Collect all focus/branch sections at one pinned snapshot')
    p.add_argument('--include',action='append',help='Read facet from schema --action read/history')
    p.add_argument('--limit',type=int,default=25)
    p.add_argument('--cursor')
    p.add_argument('--record-id')
    p.add_argument('--event-id')
    p.add_argument('--show-excluded-alternatives',action='store_true',
                   help='View excluded Decision alternatives without changing selection')
    p.add_argument('--action')
    p.add_argument('--package-id')
    p.add_argument('--source-package-id')
    p.add_argument('--core-command')
    p.add_argument('--source-folder')
    p.add_argument('--source-key')
    p.add_argument('--transaction-id')
    p.add_argument('--expected-input-binding')
    p.add_argument('--refresh',action='store_true',help='Explicit Gendocen refresh; may write engine state')
    a=p.parse_args()
    require(a.role is None and a.entity_kind is None or a.command=='schema','SCHEMA_SELECTORS_ONLY')
    require(a.history_mode is None or a.command=='history','HISTORY_MODE_ONLY')
    require((a.detail is None and a.include is None and a.limit==25 and a.cursor is None)
            or a.command in ('open','history','search','theory') or a.command=='lens' and a.format=='markdown' and a.detail is None and a.include is None and a.limit==25,'READ_OPTIONS_ONLY')
    require(not a.all_pages or a.command=='open' and a.detail in ('focus','branch') or
            a.command in ('open','lens') and a.format=='markdown' or a.command=='theory','READ_ALL_PAGES_ONLY')
    require(a.format=='json' or a.command in ('open','lens','theory'),'MARKDOWN_COMMAND')
    require(a.command=='theory' or not (a.theory_id or a.item_id or a.expand_sources or a.collection!='overview'),'THEORY_OPTIONS_ONLY')
    require(a.query is None and a.search_scope=='package' or a.command=='search','SEARCH_OPTIONS_ONLY')
    require(a.command!='search' or a.query is not None and a.detail is None and a.include is None,
            'SEARCH_OPTIONS')
    require(not (a.work_graph or a.include_plan) or a.command=='open' and a.format=='markdown',
            'MARKDOWN_OPTIONS_ONLY')
    require(a.record_id is None or a.command=='open','READ_RECORD_ID_ONLY')
    require(a.event_id is None or a.command=='history','READ_EVENT_ID_ONLY')
    selected=config(a.context) if a.context else None
    if selected and selected.get('profile') in ('portable','remote','gateway'):
        out=portable_command(a,selected)
        if a.format=='markdown':
            sys.stdout.write(out['markdown'])
            if out.get('page',{}).get('nextCursor') is not None:
                print('Markdown continuation: '+out['page']['nextCursor'],file=sys.stderr)
        else:
            print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
        if a.command=='command' and out.get('saved') is not True:sys.exit(2)
        return
    require(a.detail not in ('focus','branch') and not a.all_pages and a.format=='json' and a.command!='search','PORTABLE_CONTEXT_REQUIRED')
    require(not a.expected_input_binding,'PORTABLE_CONTEXT_REQUIRED')
    require(a.command not in ('preflight','history','locks','resolve','source_snapshot','migration_sources','migration_inspect','recover','cancel_migration','approval_request','approval_read','theory'),'PORTABLE_CONTEXT_REQUIRED')
    require(a.role is None and a.entity_kind is None,'PORTABLE_CONTEXT_REQUIRED')
    if a.command=='lenses':out=lens_catalog()
    elif a.command=='lens':
        require(a.lens is not None and len(a.lens)==1,'ONE_LENS_REQUIRED')
        out=inspect_lens(a.lens[0],a.model_profile)
    elif a.command=='doctor':out=doctor(a.context)
    elif a.command=='catalog':out=catalog(config(a.context) if a.context else None)
    else:
        client=Agent(config(a.context))
        if a.command=='open':out=client.packet(a.lens or ['work'],a.node)
        elif a.command=='receipt':out=client.receipt(a.transaction_id)
        elif a.command=='dependencies':out=client.dependencies(client.snapshot(),a.refresh)
        elif a.command=='command':out=client.command(json.load(sys.stdin))
        else:
            require(a.action in ACTIONS,'ACTION_NOT_AVAILABLE')
            v=client.snapshot();g=v['sources']['graphs'][client.graph_file]
            req={'action':a.action,'transactionId':'agent-'+uuid.uuid4().hex,'nodeId':a.node or g['rootRequirementId'],
                'note':'REPLACE_WITH_ACTUAL_ACTION_OR_CHECK','expectedGraphRevision':g['revision'],
                'expectedPlanRevision':v['sources']['plan']['revision']}
            if a.action in ('add_action','prepare_requirement','edit_title','add_qrpe'):req['title']=''
            if a.action in ('add_action','edit_canon'):req.update(recommended='',contraindicated='')
            if a.action=='prepare_requirement':req['childRole']='subgoal'
            if a.action=='place':req['at']=''
            if a.action=='unplace':req['stepId']=''
            if a.action=='withdraw':req['dispositions']=[]
            if a.action.startswith('core_'):
                req['data']=core_request_data(g,a.action[5:],req['nodeId'])
            if a.action in ('complete','resolve_qrpe','core_complete','core_falsify','core_review','core_resolve_finding'):req['evidenceRefs']=[]
            if a.action=='resolve_qrpe':req['issueId']=''
            out={'request':req,'instruction':'Fill actual fields; keep the same transactionId for receipt lookup after uncertainty.'}
    print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
    if a.command=='command' and out.get('saved') is not True:sys.exit(2)


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'saved':False,'error':str(exc),
            'instruction':'After an uncertain writer outcome inspect receipt/recovery; never assume rejection.'},
            ensure_ascii=False),file=sys.stderr);sys.exit(2)
