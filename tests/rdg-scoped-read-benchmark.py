#!/usr/bin/env python3
"""Opt-in B03A synthetic backend benchmark; only disposable owners, no live context."""
import argparse
import copy
from importlib.machinery import SourceFileLoader
import json
import hashlib
import math
from pathlib import Path
import statistics
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('read_benchmark_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
S=SourceFileLoader('read_benchmark_scoped',str(ROOT/'tools/rdg-scoped-read.py')).load_module()

def run(sizes,samples,case_names=None,collection_samples=None):
    rows=[]
    sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ("tools/rdg-scoped-read.py","tools/rdg-decision-model.py","tools/rdg-portable-service.py","tools/rdg-compact-read.py","tools/rdg-recommendations.py")}
    for size in sizes:
        fixture=T.FIX.PortableStore();fixture.setUp()
        try:
            config={'packageRoot':str(fixture.root),'namespaceId':fixture.namespace,'coordinationRoot':str(fixture.base),'authorityStore':str(fixture.authority.path)}
            app=T.CLI.application(config,fixture.token);K=app.kernel.for_profile('rdg-decision-v1')
            graph=K.blank(str(uuid.uuid4()),'Synthetic balanced read tree',str(uuid.uuid4()),'R1','Root','Read benchmark','Disposable measurement')
            root=graph['nodes'][0]
            for i in range(2,size+1):
                graph['nodes'].append({**copy.deepcopy(root),'id':'R'+str(i),'title':'Requirement '+str(i)})
                graph['edges'].append({'id':'E'+str(i),'type':'DERIVES','from':'R'+str(i//2),'to':'R'+str(i)})
            K.validate(graph)
            print(json.dumps({'progress':'fixture','nodes':size}),flush=True)
            pid,_,_=fixture.create('benchmark',role='working',graph=graph)
            leaf='R'+str(size)
            cases={
              'full_focus':lambda:app.read(pid,view={'kind':'focus','id':leaf}),
              'focus_default':lambda:app.read(pid,detail='focus',node_id=leaf,limit=100),
              'branch_default_first_page':lambda:app.read(pid,detail='branch',node_id='R1',limit=100),
              'branch_structure_all_pages':lambda:S.read_pages(app,{'method':'read','packageId':pid,'detail':'branch','nodeId':'R1','include':['entities','edges','outline'],'limit':100},True)}
            for name,call in cases.items():
                if case_names and name not in case_names:continue
                durations=[];result=None
                count=collection_samples if collection_samples is not None and name=="branch_structure_all_pages" else samples
                for sample in range(count):
                    start=time.perf_counter();result=call();durations.append((time.perf_counter()-start)*1000)
                    print(json.dumps({'progress':'sample','nodes':size,'case':name,'sample':sample+1,'ms':round(durations[-1],2)}),flush=True)
                raw=json.dumps(result,ensure_ascii=False,separators=(',',':')).encode()
                row={'nodes':size,'case':name,'samples':count,'p50_ms':round(statistics.median(durations),2) if count>1 else None,
                     'p95_ms':round(sorted(durations)[math.ceil(.95*count)-1],2) if count>1 else None,
                     'first_ms':round(durations[0],2),'warm_p50_ms':round(statistics.median(durations[1:]),2) if count>1 else None,
                     'utf8_bytes':len(raw),'rpc':result.get('reading',{}).get('pageRequests',1),
                     'entities_returned':len(result.get('data',{}).get('entities',{}).get('items',[])),
                     'scope_enumerated':result.get('reading',{}).get('scopeEnumerated'),
                     'backend_only':True}
                rows.append(row);print(json.dumps(row),flush=True)
        finally:
            fixture.doCleanups()
    return {'runtimeModulesSHA256':sources,'fixture':'balanced R tree; no Findings/Questions/Registry recommendations',
            'limits':'synthetic in-process backend; no HTTP/model/tool latency or production SLA; small sample p95 is descriptive; first/cold and warm timings are separate; shared host; single collection run has no p50/p95 estimate',
            'measurements':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sizes',type=int,nargs='+',default=[50,500,5000]);p.add_argument('--samples',type=int,default=5);p.add_argument('--output',type=Path,required=True);p.add_argument('--cases',nargs='+',choices=['full_focus','focus_default','branch_default_first_page','branch_structure_all_pages']);p.add_argument('--collection-samples',type=int)
    args=p.parse_args()
    if args.samples<1 or args.collection_samples is not None and args.collection_samples<1 or any(n<2 for n in args.sizes):p.error('positive samples and sizes>=2 required')
    if args.output.exists():p.error('choose a new output; do not overwrite evidence')
    result=run(args.sizes,args.samples,args.cases,args.collection_samples);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
