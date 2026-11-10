#!/usr/bin/env python3
"""Pure recommendation definitions/resolver; persistence is the existing FileStore."""
import copy
import hashlib
import json
import uuid

KINDS={'requirement','decision','action','canon','context','info','evidence','finding','question','process','workGraph'}
STATES={'any','open','selected','unselected','discovered','completed','review_required'}
COMPOSITION={'DRIVES','DECISION_MEMBER','INTRODUCES','DERIVES','REQUIRES_ACTION'}
def require(ok,code):
    if not ok:raise ValueError(code)
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def text(v):return isinstance(v,str) and bool(v.strip())
def uuid_valid(v):
    try:return str(uuid.UUID(v))==v
    except (ValueError,TypeError,AttributeError):return False
def empty(namespace):return {'schemaVersion':1,'kind':'rdgRecommendationRegistry','namespaceId':namespace,'revision':0,'packages':[]}
def validate_definition(p):
    require(isinstance(p,dict) and set(p)<= {'id','revision','key','title','supplied','rules','instance','userManaged','authored'} and
        {'id','revision','key','title','supplied','rules'}<=set(p) and uuid_valid(p['id']) and
        type(p['revision']) is int and p['revision']>=1 and text(p['key']) and text(p['title']) and
        type(p['supplied']) is bool and isinstance(p['rules'],list) and bool(p['rules']) and
        ('userManaged' not in p or (p['userManaged'] is True and p['supplied'] is True)),
        'SCHEMA_INVALID:recommendation-definition')
    require('authored' not in p or type(p['authored']) is bool,'SCHEMA_INVALID:recommendation-authored')
    ids=set()
    for r in p['rules']:
        require(isinstance(r,dict) and set(r)<= {'id','nodeKinds','scope','anchor','state','tag','lensRefs','whenText','usageText'} and
            {'id','nodeKinds','scope','state','lensRefs'}<=set(r) and text(r['id']) and r['id'] not in ids and
            isinstance(r['nodeKinds'],list) and bool(r['nodeKinds']) and set(r['nodeKinds'])<=KINDS and len(r['nodeKinds'])==len(set(r['nodeKinds'])) and
            r['scope'] in ('all','identity','children','descendants') and r['state'] in STATES and
            isinstance(r['lensRefs'],list) and bool(r['lensRefs']) and ('tag' not in r or text(r['tag'])),'SCHEMA_INVALID:recommendation-rule')
        require(all(isinstance(r[k],str) for k in ('whenText','usageText') if k in r),'SCHEMA_INVALID:recommendation-text')
        ids.add(r['id']);require(('anchor' not in r)==(r['scope']=='all'),'SCHEMA_INVALID:recommendation-anchor')
        if 'anchor' in r:
            a=r['anchor'];require(isinstance(a,dict) and {'packageId','identitySpace','nodeId'}<=set(a)<={'packageId','identitySpace','nodeId','kind'} and a.get('kind','entity') in ('entity','process','workGraph') and
                uuid_valid(a['packageId']) and uuid_valid(a['identitySpace']) and text(a['nodeId']),'SCHEMA_INVALID:recommendation-anchor')
        for ref in r['lensRefs']:
            require(isinstance(ref,dict) and {'packageId','identitySpace','lensKey'}<=set(ref)<={'packageId','identitySpace','lensKey','nodeId'} and ('nodeId' not in ref or text(ref['nodeId'])) and
                uuid_valid(ref['packageId']) and uuid_valid(ref['identitySpace']) and text(ref['lensKey']),'SCHEMA_INVALID:lens-ref')
    if 'instance' in p:
        v=p['instance'];require(isinstance(v,dict) and set(v)=={'sourceDefinition','graphBinding','memberIds','rootIds'},'SCHEMA_INVALID:recommendation-instance')
        pin=v['sourceDefinition'];binding=v['graphBinding']
        require(set(pin)=={'packageId','revision','sha256'} and uuid_valid(pin['packageId']) and type(pin['revision']) is int and pin['revision']>=1 and
            isinstance(pin['sha256'],str) and len(pin['sha256'])==64 and all(c in '0123456789abcdef' for c in pin['sha256']),'SCHEMA_INVALID:definition-pin')
        require(set(binding)=={'packageId','identitySpace'} and all(uuid_valid(i) for i in binding.values()),'SCHEMA_INVALID:graph-binding')
        require(all(isinstance(v[k],list) and all(text(i) for i in v[k]) and len(v[k])==len(set(v[k])) for k in ('memberIds','rootIds')) and
            set(v['rootIds'])<=set(v['memberIds']),'SCHEMA_INVALID:instance-members')
    return p

def validate(reg):
    require(isinstance(reg,dict) and {'schemaVersion','kind','namespaceId','revision','packages'}<=set(reg)<= {'schemaVersion','kind','namespaceId','revision','packages','dependencyPolicies'} and
        reg['schemaVersion']==1 and reg['kind']=='rdgRecommendationRegistry' and uuid_valid(reg['namespaceId']) and
        type(reg['revision']) is int and reg['revision']>=0 and isinstance(reg['packages'],list),'SCHEMA_INVALID:registry')
    require(isinstance(reg.get('dependencyPolicies',[]),list),'SCHEMA_INVALID:dependency-catalog')
    ids=set()
    for p in reg['packages']:
        validate_definition(p);require(p['id'] not in ids,'ENTITY_ID_CONFLICT:recommendation');ids.add(p['id'])
    return reg

def descendants(graph,kernel,roots,depth=None):
    edges=[e for e in kernel.active_edges(graph) if e['type'] in COMPOSITION]
    if graph['coreModel']=='rdg-decision-v1':edges+=kernel.for_graph(graph).decision_memberships(graph)
    seen=set(roots);front=set(roots);level=0
    while front and (depth is None or level<depth):
        front={e['to'] for e in edges if e['from'] in front}-seen;seen|=front;level+=1
    return seen

def matches(reg,graph,package_id,kernel,*,node_ids=None):
    validate(reg);ns=kernel.entities(graph);completion=None;by_id={p['id']:p for p in reg['packages']}
    ns=dict(ns);ns.setdefault(graph['id'],{'id':graph['id'],'kind':'process'})
    
    for w in graph.get('workGraphs',[]):ns.setdefault(w['id'],{'id':w['id'],'kind':'workGraph'})
    rows={};diagnostics=[]
    for pid in graph['recommendationPackageIds']:
        p=by_id.get(pid)
        if p is None:diagnostics.append({'packageId':pid,'reason':'definition-missing'});continue
        scope=set(ns)
        if 'instance' in p:
            instance=p['instance'];binding=instance['graphBinding']
            if binding!={'packageId':package_id,'identitySpace':graph['identitySpace']}:
                diagnostics.append({'packageId':pid,'reason':'foreign-instance'});continue
            if not set(instance['rootIds'])<=set(ns):
                diagnostics.append({'packageId':pid,'reason':'instance-anchor-missing'});continue
            scope=(set(instance['memberIds'])&set(ns))|descendants(graph,kernel,instance['rootIds'])
            if p.get('authored'):
                scope|={w['id'] for w in graph.get('workGraphs',[]) if set(w.get('memberIds',[]))<=scope}
                if graph.get('rootRequirementId') in instance['rootIds']:scope.add(graph['id'])
                elif any(r.get('anchor',{}).get('kind')=='process' for r in p['rules']):diagnostics.append({'packageId':pid,'reason':'instance-process-scope-not-transferable'})
        for rule in p['rules']:
            candidates=scope.copy()
            if rule['scope']!='all':
                a=rule['anchor']
                if a['packageId']!=package_id or a['identitySpace']!=graph['identitySpace'] or a['nodeId'] not in ns or (a.get('kind','entity') in ('process','workGraph')) != (ns.get(a['nodeId'],{}).get('kind') in ('process','workGraph')) or (a.get('kind') in ('process','workGraph') and ns.get(a['nodeId'],{}).get('kind')!=a['kind']):
                    diagnostics.append({'packageId':pid,'ruleId':rule['id'],'reason':'anchor-missing-or-foreign'});continue
                found={a['nodeId']} if rule['scope']=='identity' else descendants(graph,kernel,[a['nodeId']],1 if rule['scope']=='children' else None)-{a['nodeId']}
                candidates&=found
            if node_ids is not None:candidates &= set(node_ids)
            for nid in sorted(candidates):
                node=ns[nid];wanted=rule['state']
                if node['kind'] not in rule['nodeKinds']:continue
                # Application validates Graph before projecting. Most advice does
                # not depend on completion; compute it only for stateful rules.
                if wanted in ('completed','review_required') and completion is None:
                    completion=kernel.completion_state(graph)
                matches_state=(wanted=='any' or wanted=='open' and node.get('result',{}).get('state','open')=='open' or
                    wanted in ('selected','unselected','discovered') and node.get('selectionState')==wanted or
                    wanted=='completed' and completion.get(nid,{}).get('complete') or
                    wanted=='review_required' and completion.get(nid,{}).get('reviewRequired'))
                if node['kind'] not in rule['nodeKinds'] or not matches_state:continue
                if 'tag' in rule and rule['tag'] not in node.get('tags',[]):continue
                for lens in rule['lensRefs']:
                    key=(nid,lens['packageId'],lens['identitySpace'],lens['lensKey'],lens.get('nodeId'),*((pid,rule['id']) if p.get('authored') else ()))
                    row=rows.setdefault(key,{'nodeId':nid,'lensRef':copy.deepcopy(lens),'reasons':[],**({'recommendationId':pid+':'+rule['id'],'whenText':rule.get('whenText',''),'usageText':rule.get('usageText','')} if p.get('authored') else {})})
                    row['reasons'].append({'packageId':pid,'revision':p['revision'],'ruleId':rule['id'],'definitionSHA256':digest(p)})
    return {'matches':list(rows.values()),'diagnostics':diagnostics,'registryRevision':reg['revision'],'automaticExecution':False}
