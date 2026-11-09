#!/usr/bin/env python3
"""Read/evaluate one published workspace composition; never writes source graphs.

projectionOf identifies the semantic owner. expansionOf permits an exact local
continuation of that R. The temporary union is a calculation, not another owner.
Callers hold the common writer lock and authorize every loaded graph.
"""
import copy
import hashlib
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import re

TOOLS=Path(__file__).resolve().parent
IO=SourceFileLoader('completion_current_routes',str(TOOLS/'rdg-transaction-io.py')).load_module()
MODEL=SourceFileLoader('cross_completion_model',str(TOOLS/'rdg-v7-model.py')).load_module()
PATH=re.compile(r'workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json\Z')


def require(ok,code):
    if not ok:raise ValueError('COMPLETION_'+code)


def safe(root,relative):
    require(isinstance(relative,str) and PATH.fullmatch(relative),'WORKSPACE_PATH_INVALID')
    path=root/relative
    require(path.resolve().is_relative_to(root) and not any(p.is_symlink()
        for p in [path,*path.parents] if p!=root.parent),'UNSAFE_SOURCE')
    return path


def load(root,seeds,authorize=None,overrides=None):
    root=Path(root).resolve();overrides=overrides or {}
    index=root/'index.json'
    require(not index.is_symlink(),'UNSAFE_CATALOG')
    raw=index.read_bytes() if index.exists() else None
    manifest=json.loads(raw) if raw else {'schemaVersion':1,'graphs':[]}
    require(manifest.get('schemaVersion')==1 and isinstance(manifest.get('graphs'),list),'CATALOG_INVALID')
    metadata={};slugs={}
    for row in manifest['graphs']:
        file=row.get('file');slug=row.get('slug')
        require(isinstance(file,str) and file not in metadata and
                isinstance(slug,str) and slug not in slugs,'AMBIGUOUS_CATALOG')
        metadata[file]={k:row.get(k) for k in ('file','slug','identitySpace','rootRequirementId')}
        slugs[slug]=file
    supplied={**seeds,**overrides}
    for file,g in supplied.items():
        safe(root,file)
        if file not in metadata:
            slug=g.get('catalogSlug') or Path(file).parent.name
            require(slug not in slugs,'AMBIGUOUS_CATALOG')
            metadata[file]={'file':file,'slug':slug,'identitySpace':g.get('identitySpace'),
                            'rootRequirementId':g.get('rootRequirementId')}
            slugs[slug]=file
        else:
            require(all(metadata[file][k]==g.get(k) for k in ('identitySpace','rootRequirementId')),
                    'CATALOG_STALE')
    spaces={g.get('identitySpace') for g in supplied.values() if g.get('actionModel')=='candidate-v6'}
    for relation in manifest.get('relations',[]):
        if relation.get('identitySpace') not in spaces:continue
        for key in ('from','to'):
            file=slugs.get(relation.get(key))
            require(file in metadata and metadata[file]['identitySpace']==relation['identitySpace'],
                    'CATALOG_STALE')
    files=sorted(set(supplied)|{f for f,m in metadata.items()
        if m['identitySpace'] in spaces and isinstance(f,str) and f.startswith('workspaces/')})
    cross=any(sum(metadata[f]['identitySpace']==space for f in files)>1 for space in spaces) or any(
        n.get('projectionOf') for g in supplied.values() for n in g['nodes'])
    if cross:require(raw is not None,'CATALOG_REQUIRED')
    if authorize and cross:authorize(files)
    graphs={};pins={}
    for file in files:
        path=safe(root,file)
        IO.require_current_legacy(path)
        data=path.read_bytes() if path.exists() else None
        require(data is not None or file in supplied,'SOURCE_MISSING')
        pins[file]=hashlib.sha256(data).hexdigest() if data is not None else None
        g=supplied[file] if file in supplied else json.loads(data)
        require(all(metadata[file][k]==g.get(k) for k in ('identitySpace','rootRequirementId')),
                'CATALOG_STALE')
        graphs[file]=g
    require((index.read_bytes() if index.exists() else None)==raw,'CATALOG_CHANGED')
    return Context(graphs,{f:metadata[f]['slug'] for f in files},pins,
                   hashlib.sha256(raw).hexdigest() if raw else None)


class Context:
    def __init__(self,graphs,slugs,pins=None,index_hash=None):
        self.graphs=graphs;self.slugs=slugs;self.pins=pins or {};self.index_hash=index_hash
        self.cross=any(sum(g.get('identitySpace')==s for g in graphs.values())>1
            for s in {g.get('identitySpace') for g in graphs.values()}) or any(
                n.get('projectionOf') for g in graphs.values() for n in g['nodes'])

    def updated(self,overrides):
        require(set(overrides)<=set(self.graphs),'UNDECLARED_SOURCE')
        return Context({**self.graphs,**overrides},self.slugs,self.pins,self.index_hash)

    def evaluate(self):
        result={f:{} for f in self.graphs};self.owner_refs={};self.evaluation_order=[]
        for space in sorted({g.get('identitySpace') for g in self.graphs.values()
                      if g.get('actionModel')=='candidate-v6'},key=str):
            files=[f for f,g in self.graphs.items() if g.get('identitySpace')==space]
            require(space and all(self.graphs[f].get('actionModel')=='candidate-v6' and
                not any(self.graphs[f].get(k) for k in ('readOnly','exampleOnly','templateOnly'))
                for f in files),'UNSUPPORTED_OWNER_MODEL')
            by_slug={self.slugs[f]:f for f in files}
            records={(f,n['id']):n for f in files for n in self.graphs[f]['nodes']}
            owners={}
            for (file,nid),node in records.items():
                if not node.get('projectionOf'):
                    require(nid not in owners,'AMBIGUOUS_IDENTITY_OWNER')
                    owners[nid]=file
            resolved={}
            def resolve(file,nid,trail=()):
                key=(file,nid)
                if key in resolved:return resolved[key]
                require(key not in trail,'PROJECTION_CYCLE')
                node=records.get(key);require(node is not None,'OWNER_NODE_MISSING')
                ref=node.get('projectionOf')
                if ref:
                    require(isinstance(ref,dict) and set(ref)=={'graphSlug','nodeId'} and
                            ref['nodeId']==nid,'OWNER_REFERENCE_INVALID')
                    target=by_slug.get(ref['graphSlug'])
                    require(target is not None,'OWNER_MISSING_OR_CROSS_PROJECT')
                    owner=resolve(target,nid,(*trail,key))
                    canonical=records[(owner,nid)]
                    require(node['kind']==canonical['kind'] and all(
                        k not in node or node[k]==canonical.get(k) for k in ('requirementText','scope')),
                        'OWNER_KIND_OR_SCOPE_MISMATCH')
                else:owner=file
                require(owners.get(nid)==owner,'AMBIGUOUS_IDENTITY_OWNER')
                resolved[key]=owner;return owner
            for file,nid in records:resolve(file,nid)
            roots=set()
            for file in files:
                graph=self.graphs[file];rid=graph['rootRequirementId'];root=records[(file,rid)]
                expansion=graph.get('expansionOf')
                if expansion:
                    require(root.get('projectionOf')==expansion and isinstance(expansion,dict) and
                            expansion.get('nodeId')==rid,'EXPANSION_BINDING_INVALID')
                    resolve(file,rid)
                elif not root.get('projectionOf'):
                    roots.add(rid)
            nodes=[copy.deepcopy(records[(owners[nid],nid)]) for nid in sorted(owners)]
            edges=[];events=[]
            for file in sorted(files):
                graph=self.graphs[file]
                for event in graph['events']:
                    nid=event.get('targetId') if event.get('type') in MODEL.COMPLETION_EVENTS else event.get('actionId')
                    if nid is None:continue
                    if event.get('type') in MODEL.COMPLETION_EVENTS:
                        require(owners.get(nid)==file,'HISTORY_MUST_BELONG_TO_OWNER')
                    if owners.get(nid)==file:events.append(copy.deepcopy(event))
                for edge in graph['edges']:
                    if edge.get('archived') is True:continue
                    source,target=edge['from'],edge['to']
                    require((file,source) in records and (file,target) in records,'EDGE_TARGET_MISSING')
                    # Repeated display edges never contribute a second causal action.
                    cause=target if edge['type']=='DRIVES' else source
                    if edge['type'] in ('DRIVES','INTRODUCES','OUTCOME_OF') and owners[cause]!=file:
                        continue
                    if edge['type']=='DRIVES' and owners[source]!=file:
                        require(graph.get('rootRequirementId')==source and
                            graph.get('expansionOf')==records[(file,source)].get('projectionOf') and
                            graph.get('expansionOf') is not None,'EXPANSION_BINDING_REQUIRED')
                    if edge['type']=='DERIVES' and owners[target]!=file:continue
                    material=copy.deepcopy(edge)
                    if owners[source]!=file:material['compositionGraphFile']=file
                    if owners[target]!=file:material['targetOwnerGraphFile']=owners[target]
                    edges.append(material)
            virtual={'actionModel':'candidate-v6','rootRequirementId':next(iter(roots),None),
                     'nodes':nodes,'edges':edges,'events':events}
            states=MODEL.completion_state(virtual,actual_roots=roots)
            self.evaluation_order.extend((owners[nid],nid) for nid in states)
            for nid in states:
                for file in files:
                    node=records.get((file,nid))
                    if not node or node['kind'] not in ('requirement','action'):continue
                    owner=owners[nid];ref={'graphFile':owner,'identitySpace':space,'nodeId':nid}
                    row=copy.deepcopy(states[nid])
                    row.update(ownerRef=ref,projection=owner!=file,
                               dependencyIds=list(dict.fromkeys(row['dependencyIds'])))
                    row['dependencyRefs']=[{'graphFile':owners[d],'identitySpace':space,'nodeId':d}
                                           for d in row['dependencyIds']]
                    row['historyPending']=row['complete'] and not row['eventId']
                    result[file][nid]=row
                    self.owner_refs[(file,nid)]=ref

        return result

    def pins_for_journal(self):
        return [{'file':file,'sha256':digest} for file,digest in sorted(self.pins.items())]
