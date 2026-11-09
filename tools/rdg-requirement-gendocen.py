#!/usr/bin/env python3
"""Gendocen-owned freshness for explicitly linked candidate-v6 Requirements.

RDG owns facts and provenance; this bridge only projects authorized snapshots,
registers exact Gendocen subscriptions, and reads engine receipts/events.
No automatic approval, no inference of real-world truth, no Graph/Plan writes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from importlib.machinery import SourceFileLoader

TOOLS=Path(__file__).resolve().parent
ADAPTER=SourceFileLoader('rdg_req_review_adapter',str(TOOLS/'rdg-gendocen-adapter.py')).load_module()
ENGINE=Path(os.getenv('RDG_GENDOCEN_SOURCE','/workspace/repos/gendocen'))
GRAPH_PATH=re.compile(r'workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json\Z')
EVIDENCE=re.compile(r'^graph-node:([^@]+)@([a-f0-9]{64})$')


def require(ok,code):
    if not ok:raise ValueError('RDG_REQ_DEP_'+code)


def pointer(ident):
    return ident.replace('~','~0').replace('/','~1')


def safe_graph(root,ref):
    require(isinstance(ref,str) and bool(GRAPH_PATH.fullmatch(ref)),'GRAPH_REF_INVALID')
    root=Path(root).resolve();path=root/ref
    require(path.resolve().is_relative_to(root) and path.is_file() and
            not any(p.is_symlink() for p in [path,*path.parents] if p!=root.parent),
            'GRAPH_SOURCE_UNSAFE_OR_MISSING')
    return path


def read_scope(root,refs,token=None,store=None):
    refs=list(dict.fromkeys(refs));require(refs,'EMPTY_SCOPE')
    graphs={ref:json.loads(safe_graph(root,ref).read_text(encoding='utf8')) for ref in refs}
    spaces={g.get('identitySpace') for g in graphs.values()}
    require(len(spaces)==1 and None not in spaces,'MIXED_IDENTITY_SPACE')
    # A partial authorized scope is never treated as proof of no other links.
    index=Path(root)/'index.json'
    require(index.is_file(),'GRAPH_CATALOG_REQUIRED_FOR_COMPLETE_SCOPE')
    if index.exists():
        require(not index.is_symlink(),'UNSAFE_CATALOG')
        manifest=json.loads(index.read_text(encoding='utf8'))
        required={g['file'] for g in manifest.get('graphs',[]) if g.get('identitySpace') in spaces
                  and g.get('file','').startswith('workspaces/')}
        require(required<=set(refs),'SCOPE_INCOMPLETE missing='+repr(sorted(required-set(refs))))
    if store:
        auth=SourceFileLoader('rdg_req_dep_auth',str(TOOLS/'rdg-authority.py')).load_module()
        auth.Authority(store).authorize_graph_read(token,refs)
    require(all(g.get('actionModel')=='candidate-v6' and
                not any(g.get(k) for k in ('readOnly','exampleOnly','templateOnly'))
                for g in graphs.values()),'ACTION_MODEL_UNSUPPORTED')
    return graphs


def inventory(graphs):
    """Discover only typed graph edges / structured refs, never search prose.

    Every target has the exact responsible input Requirement reference. A new
    relation target needs a new review; it is NOT silently accepted by Gendocen.
    """
    core_graphs={f:g for f,g in graphs.items() if g.get('coreModel')}
    if core_graphs:
        core=SourceFileLoader('dependencies_closed_core',str(TOOLS/'rdg-core-model.py')).load_module()
        legacy={f:g for f,g in graphs.items() if not g.get('coreModel')}
        nodes,deps=inventory(legacy) if legacy else ({},{})
        for file,g in core_graphs.items():
            core.validate(g)
            local=core.entities(g); nodes.update({(file,i):n for i,n in local.items()})
            incoming={i:{} for i in local}
            for e in core.active_edges(g):
                if e['type'] in core.DEPENDENCY_TYPES:
                    incoming[e['to']].setdefault(e['from'],set()).add('edge:'+e['id'])
            for target in incoming:
                queue=list(incoming[target]); seen=set(queue)
                for source in queue:
                    for ancestor,reasons in incoming[source].items():
                        if ancestor==target:continue
                        incoming[target].setdefault(ancestor,set()).update('inherited:'+r for r in reasons)
                        if ancestor not in seen:seen.add(ancestor);queue.append(ancestor)
                if incoming[target]:deps[file,target]={(file,i):r for i,r in incoming[target].items()}
        return nodes,deps
    modules=SourceFileLoader('rdg_modules_dependencies',str(TOOLS/'rdg-modules.py')).load_module()
    for graph in graphs.values():modules.validate_graph(graph)
    nodes={(f,n['id']):n for f,g in graphs.items() for n in g['nodes']}
    owners={}
    for (file,nid),node in nodes.items():
        if not node.get('projectionOf'):
            require((graphs[file]['identitySpace'],nid) not in owners,'AMBIGUOUS_OWNER_ID')
            owners[graphs[file]['identitySpace'],nid]=file
    slug={g.get('catalogSlug') or Path(f).parent.name:f for f,g in graphs.items()}
    deps={key:{} for key,node in nodes.items() if node['kind'] in ('action','requirement')}
    def add(target,source,reason):
        if target==source:return
        s=nodes.get(source)
        require(s is not None and s.get('kind')=='requirement','REFERENCE_REQUIREMENT_MISSING')
        deps.setdefault(target,{}).setdefault(source,set()).add(reason)
    # Projection references a canonical owner. This detects a changed R in a
    # nested owner without silently modifying the projection duplicate.
    for (file,nid),node in nodes.items():
        projected=node.get('projectionOf')
        if projected:
            require(isinstance(projected,dict) and set(projected)=={'graphSlug','nodeId'} and
                    projected['nodeId']==nid and projected['graphSlug'] in slug,
                    'PROJECTION_OWNER_UNAVAILABLE')
            source=(slug[projected['graphSlug']],nid)
            add((file,nid),source,'projectionOf')
    for file,graph in graphs.items():
        local={n['id']:n for n in graph['nodes']}
        for edge in graph.get('edges',[]):
            if edge.get('archived') is True:continue
            src,dst=edge.get('from'),edge.get('to')
            if edge.get('type') in ('DRIVES','DERIVES','APPLIES_TO') and src in local:
                if local[src]['kind']=='requirement' and dst in local and local[dst]['kind'] in ('requirement','action'):
                    add((file,dst),(file,src),'edge:'+edge['id'])
            if edge.get('type') in ('INTRODUCES','OUTCOME_OF') and src in local and dst in local:
                if local[src]['kind']=='action' and local[dst]['kind']=='requirement':
                    # A child R relies on the Action's currently declared driver.
                    for link in graph['edges']:
                        if link.get('type')=='DRIVES' and link.get('to')==src and link.get('archived') is not True:
                            add((file,dst),(file,link['from']),'action-child:'+edge['id'])
        for nid,node in local.items():
            target=(file,nid)
            if node.get('module'):
                spec=modules.entity_spec(graph,node)
                for field, kind in spec['fields'].items():
                    if kind!='requirementRefs':continue
                    for ref in node['data'][field]:
                        require(ref['identitySpace']==graph['identitySpace'] and
                                (ref['graphFile'],ref['nodeId']) in nodes,
                                'MODULE_REQUIREMENT_REF_UNRESOLVED')
                        add(target,(ref['graphFile'],ref['nodeId']),'module:'+node['module']['id']+'/'+field)
            if node['kind'] not in ('action','requirement'):continue
            # Only explicitly typed, versioned evidence references. Text merely
            # mentioning a Requirement is not a dependency declaration.
            def scan(item,location):
                if isinstance(item,dict):
                    # Typed owner-qualified references and canon requirement
                    # checks are actual Graph inputs; text mentions are not.
                    if set(('graphFile','identitySpace','nodeId'))<=set(item):
                        ref=(item['graphFile'],item['nodeId'])
                        require(item['identitySpace']==graph['identitySpace'] and ref in nodes,
                                'QUALIFIED_REQUIREMENT_REF_UNRESOLVED')
                        add(target,ref,'qualified:'+location)
                    for key,val in item.items():
                        if key in ('previousRequirementSnapshot','newRequirementSnapshot'):continue
                        if key in ('checkRequirements','dependsOnRequirements') and isinstance(val,list):
                            for rid in val:
                                require(isinstance(rid,str),'CANON_REQUIREMENT_ID_INVALID')
                                owner=owners.get((graph['identitySpace'],rid))
                                require(owner is not None,'CANON_REQUIREMENT_UNRESOLVED')
                                add(target,(owner,rid),'canon:'+location+'/'+key)
                        elif key=='requirementId' and isinstance(val,str):
                            owner=owners.get((graph['identitySpace'],val))
                            require(owner is not None,'CONTEXT_REQUIREMENT_UNRESOLVED')
                            add(target,(owner,val),'context:'+location+'/'+key)
                        else:scan(val,location+'/'+key)
                elif isinstance(item,list):
                    for i,val in enumerate(item):scan(val,location+'/'+str(i))
                elif isinstance(item,str):
                    match=EVIDENCE.fullmatch(item)
                    if match:
                        req_id=match.group(1);owner=owners.get((graph['identitySpace'],req_id))
                        require(owner is not None,'EXPLICIT_REF_OWNER_MISSING:'+req_id)
                        add(target,(owner,req_id),'explicit:'+location)
            for field in ('canonBlock','contextChecks','selectionBasis','qrpe','contextUses'):
                if field in node:scan(node[field],field)
    # Reach all downstream uses, not just immediate Actions, but never treat
    # reachability as proven execution or an objectively invalid decision.
    for target in list(deps):
        agenda=list(deps[target]);visited=set(agenda)
        while agenda:
            upstream=agenda.pop()
            for source,reasons in deps.get(upstream,{}).items():
                if source==target:continue
                deps[target].setdefault(source,set()).update('inherited:'+x for x in reasons)
                if source not in visited:visited.add(source);agenda.append(source)
    return nodes,{t:d for t,d in deps.items() if d}


def engine_cli(project,*parts):
    require((ENGINE/'src/docengine/cli.py').is_file(),'GENDOCEN_ENGINE_UNAVAILABLE')
    env={**os.environ,'PYTHONPATH':str(ENGINE/'src'),
         'PYTHONDONTWRITEBYTECODE':'1'}
    result=subprocess.run([sys.executable,'-m','docengine.cli',*parts,'--project-root',str(project),'--json'],
                          capture_output=True,text=True,env=env,timeout=60)
    require(bool(result.stdout.strip()),'GENDOCEN_RESPONSE_MISSING '+result.stderr)
    data=json.loads(result.stdout)
    require(data.get('ok') is True,'GENDOCEN_'+str(data.get('status'))+' '+repr(data.get('issues')))
    return data['data']


def target_name(file,ident):
    return hashlib.sha256((file+'\0'+ident).encode('utf8')).hexdigest()[:24]


def refresh(root,refs,project,token=None,store=None):
    graphs=read_scope(root,refs,token=token,store=store)
    nodes,deps=inventory(graphs)
    declared_project=Path(project)
    require(not declared_project.is_symlink() and not any(p.is_symlink() for p in declared_project.parents),
            'PROJECT_ROOT_UNSAFE')
    project=declared_project.resolve()
    graph_owner_root=Path(root).resolve()
    # The derived engine state is a distinct owner; never let its projections,
    # receipts or generated Python config land in a canonical Graph/Plan tree.
    canonical_plan_root=graph_owner_root.parent/'plans'
    require(not project.is_relative_to(graph_owner_root) and
            not project.is_relative_to(canonical_plan_root) and
            project != graph_owner_root.parent,
            'PROJECT_MUST_BE_OUTSIDE_GRAPH_AND_PLAN_OWNERS')
    # Never overwrite somebody else's docengine_project/__init__.py.
    existing=project/'docengine.toml'
    manifest=project/'rdg-dependency-manifest.json'
    require(not existing.exists() or manifest.is_file(),'PROJECT_NOT_MANAGED_BY_RDG')
    for reserved in ('docengine.toml','rdg-dependency-manifest.json',
                     'docengine_project/__init__.py','docs','docs/review',
                     'docs/_structured','docengine_project'):
        f=project/reserved
        require(not f.is_symlink(),'PROJECT_PATH_UNSAFE')
    # Reject a different owner/closure before touching existing engine inputs.
    # A failed bind must leave the prior project byte-for-byte unchanged.
    if manifest.is_file():
        old=json.loads(manifest.read_text(encoding='utf8'))
        require(old.get('identitySpace')==next(iter(graphs.values()))['identitySpace'] and
                set(old.get('graphFiles',[]))==set(graphs), 'PROJECT_OWNER_CLOSURE_CHANGED')
    (project/'docs/_structured').mkdir(parents=True,exist_ok=True)
    (project/'docs/review').mkdir(parents=True,exist_ok=True)
    (project/'docengine_project').mkdir(parents=True,exist_ok=True)
    config=project/'docengine.toml'
    if not config.exists():
        config.write_text('[docengine]\nconfig_version = 1\ndocumentation_root = "docs"\n'
            'structured_dir = "_structured"\ndependency_dir = "_dependency"\n'
            'project_package = "docengine_project"\n',encoding='utf8')
    else:
        require('project_package = "docengine_project"' in config.read_text(),
                'PROJECT_CONFIG_FOREIGN')
    projected={}
    for file in sorted(graphs):
        resource=ADAPTER.graph_resource(safe_graph(root,file),file,workflow_context=True)
        name=target_name(file,'source')
        (project/'docs/_structured'/(name+'.json')).write_text(json.dumps(resource,ensure_ascii=False),encoding='utf8')
        projected[file]=ADAPTER.DEPENDENCIES.resource_ref(resource)
    declared=[];entries=[]
    for (file,nid),upstream in sorted(deps.items()):
        target='file://review/'+target_name(file,nid)+'.md'
        sources=sorted((projected[srcfile]+'#/nodesById/'+pointer(srcid),'exact')
                       for srcfile,srcid in upstream)
        # Stable target file is a review marker, not an RDG Graph owner.
        note=project/'docs/review'/(target_name(file,nid)+'.md')
        if not note.exists():note.write_text('Dependency review of '+file+' / '+nid+'\n',encoding='utf8')
        declared.append((target,sources))
        entries.append({'target':target,'graphFile':file,'nodeId':nid,
                         'kind':nodes[file,nid]['kind'],'title':nodes[file,nid].get('title',nid),
                         'uses':[{'graphFile':a,'nodeId':b,'reasons':sorted(reasons)}
                                 for (a,b),reasons in sorted(upstream.items())]})
    config_script='def register_builders(registry):\n    pass\n\n'
    config_script+='def register_semantic_dependencies(registry):\n'
    for target,sources in declared:
        config_script+=f'    registry.register({target!r}, {sources!r}, rule_id={"rdg-requirement."+target_name(target,"rule")!r}, dependency_type="semantic_review")\n'
    if not declared:config_script+='    pass\n'
    (project/'docengine_project/__init__.py').write_text(config_script,encoding='utf8')
    (project/'rdg-dependency-manifest.json').write_text(json.dumps({
        'schemaVersion':1,'coverage':'declared edges and explicit references, authorized single identitySpace',
        'identitySpace':next(iter(graphs.values()))['identitySpace'],
        'graphFiles':sorted(graphs),'entries':entries,
        'externalEvidenceCoverage':'not-attested',
        'completionTruthAttested':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    engine_cli(project,'sync')
    return report(project)


def report(project,scope=None):
    project=Path(project).resolve();manifest_path=project/'rdg-dependency-manifest.json'
    require(manifest_path.is_file(),'MANIFEST_MISSING')
    manifest=json.loads(manifest_path.read_text(encoding='utf8'))
    snapshot=engine_cli(project,'check')
    status={row['target']:row for row in snapshot['results']}
    rows=[]
    for entry in manifest['entries']:
        if scope and entry['nodeId']!=scope and not any(u['nodeId']==scope for u in entry['uses']):continue
        computed=status.get(entry['target'],{})
        changed=computed.get('changed_dependencies')
        if changed is None and computed.get('status') in ('review_required','stale','invalid'):
            explanation=engine_cli(project,'explain',entry['target'])
            changed=explanation.get('changed_dependencies') or []
        rows.append({**entry,'status':computed.get('status','unknown'),
                     'changedDependencies':changed or [],
                     'engineTarget':entry['target']})
    return {'schemaVersion':1,'engine':'gendocen','coverage':manifest['coverage'],
            'sourceGraphs':manifest['graphFiles'],'identitySpace':manifest['identitySpace'],
            'externalEvidenceCoverage':manifest['externalEvidenceCoverage'],
            'completionTruthAttested':False,'rows':rows,'total':len(manifest['entries'])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('refresh','report','history','accept'))
    parser.add_argument('--graph-root')
    parser.add_argument('--graph',action='append',default=[])
    parser.add_argument('--project-root',required=True)
    parser.add_argument('--scope')
    parser.add_argument('--target')
    parser.add_argument('--review-context')
    parser.add_argument('--reason')
    parser.add_argument('--token',default=os.environ.get('RDG_AUTH_TOKEN'))
    parser.add_argument('--store',default=os.environ.get('RDG_AUTH_STORE'))
    a=parser.parse_args()
    if a.command=='refresh':
        require(a.graph_root and a.graph,'GRAPH_SCOPE_REQUIRED')
        answer=refresh(a.graph_root,a.graph,a.project_root,a.token,a.store)
    elif a.command=='report':answer=report(a.project_root,a.scope)
    elif a.command=='history':
        require(a.target and re.fullmatch(r'file://review/[a-f0-9]{24}\.md',a.target),'TARGET_INVALID')
        answer=engine_cli(a.project_root,'history',a.target)
    else:
        require(a.target and re.fullmatch(r'file://review/[a-f0-9]{24}\.md',a.target) and
                a.review_context and isinstance(a.reason,str) and a.reason.strip(),'REVIEW_APPROVAL_REQUIRED')
        answer=engine_cli(a.project_root,'validate',a.target,'--result','still-valid',
                          '--reason',a.reason,'--review-context',a.review_context)
    print(json.dumps(answer,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,FileNotFoundError,subprocess.TimeoutExpired) as e:
        print(str(e),file=sys.stderr);sys.exit(2)
