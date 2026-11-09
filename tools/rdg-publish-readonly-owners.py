#!/usr/bin/env python3
"""Explicitly publish persisted WORKING Graph/Plan/Gendocen read-only snapshots.

This is a derived transport for disconnected Viewers, never an authoritative
Plan, Graph, completion receipt, or live Gendocen review. It cannot accept writes.
Only exact owner slugs explicitly approved in this script's config are exported.
"""
import json
from pathlib import Path
import hashlib
import os
import sys
import tempfile
from importlib.machinery import SourceFileLoader
ROOT=Path(__file__).resolve().parent.parent
OUTPUT=ROOT/'tools/rdg-published-owners.json'
CONFIG=ROOT/'tools/rdg-published-owners.allowlist.json'
GENDOCEN=SourceFileLoader('rdg_published_gendocen',str(ROOT/'tools/rdg-requirement-gendocen.py')).load_module()

def check(ok,why):
    if not ok:raise ValueError('RDG_PUBLISH_'+why)

def sha(value):return hashlib.sha256(value).hexdigest()

def publish():
    manifest=json.loads(CONFIG.read_text(encoding='utf8'))
    check(manifest.get('schemaVersion')==1 and isinstance(manifest.get('slugs'),list) and
          set(manifest)=={'schemaVersion','slugs'} and
          len(set(manifest['slugs']))==len(manifest['slugs']), 'ALLOWLIST_INVALID')
    index=json.loads((ROOT/'graphs/index.json').read_text(encoding='utf8'))
    published={}
    for slug in manifest['slugs']:
        check(isinstance(slug,str) and slug.isascii() and slug.replace('-','').replace('_','').isalnum(),
              'SLUG_INVALID')
        entry=next((e for e in index['fullGraphs'] if e['slug']==slug),None)
        check(entry and entry['file']==f'workspaces/{slug}/graph.json','OWNER_NOT_IN_INDEX')
        graph_path=ROOT/'graphs'/entry['file'];plan_path=ROOT/'plans'/slug/'plan.json'
        engine_path=ROOT/'.rdg-gendocen-projects'/slug
        check(graph_path.is_file() and plan_path.is_file() and engine_path.is_dir(),'OWNER_OR_ENGINE_MISSING')
        for item in (graph_path,plan_path,engine_path):check(not item.is_symlink(),'OWNER_SYMLINK')
        graph_bytes=graph_path.read_bytes();plan_bytes=plan_path.read_bytes()
        graph=json.loads(graph_bytes);plan=json.loads(plan_bytes)
        check(graph.get('actionModel')=='candidate-v6' and not any(graph.get(k) for k in ('readOnly','exampleOnly','templateOnly')),'OWNER_OLD_MODEL')
        check(graph.get('identitySpace')==entry['identitySpace'] and graph.get('rootRequirementId')==entry['rootRequirementId'],'OWNER_GRAPH_IDENTITY')
        check(plan.get('kind')=='temporalPlanOwner' and plan.get('revision')==len(plan.get('versions',[])) and
              plan.get('owner',{}).get('identitySpace')==graph['identitySpace'] and
              plan.get('owner',{}).get('sourcePath')==f'plans/{slug}/plan.json' and
              plan['versions'][-1]['plan'].get('id')==slug,'OWNER_PLAN_IDENTITY')
        for version in plan['versions']:
            for step in version['plan']['steps']:
                ref=step.get('actionRef') or step.get('requirementRef')
                check(ref and ref.get('graphFile')==entry['file'] and ref.get('identitySpace')==graph['identitySpace'] and
                      any(n['id']==ref.get('nodeId') and n['kind']==step['kind'] for n in graph['nodes']), 'PLAN_GRAPH_REF')
        report=GENDOCEN.report(engine_path)
        check(report.get('engine')=='gendocen' and report.get('sourceGraphs')==[entry['file']] and
              report.get('identitySpace')==graph['identitySpace'] and
              report.get('completionTruthAttested') is False,'GENDOCEN_REPORT_IDENTITY')
        history={}
        for row in report['rows']:
            check(row['graphFile']==entry['file'] and any(n['id']==row['nodeId'] for n in graph['nodes']), 'GENDOCEN_TARGET_MISSING')
            history[row['target']]=GENDOCEN.engine_cli(engine_path,'history',row['target'])
        # Include the actual signed Graph writer history, not a reconstructed
        # teaching storyboard. The same real reader/permissions as the Helper
        # are used to materialize this read-only published projection.
        auth=SourceFileLoader('rdg_pub_auth',str(ROOT/'tools/rdg-authority.py')).load_module()
        reader=SourceFileLoader('rdg_pub_reader',str(ROOT/'tools/rdg-workflow.py')).load_module()
        with tempfile.TemporaryDirectory(prefix='rdg-approved-owner-publication-') as temp:
            grant=Path(temp)/'ephemeral-auth.json'
            issued=auth.Authority(grant).init_local(plan_capable=True,graph_read_capable=True)
            real=reader.read_workflow(ROOT,f'plans/{slug}/plan.json',ROOT/'graphs',
                     str(grant),issued['token'],[entry['file']],include_sources=False)
        check(len(real['history'])>0 and any(x['kind']=='requirement_reformulated'
              for x in real['history']),'GRAPH_HISTORY_MISSING')
        # The engine snapshot has *historical* statuses. It must never be
        # described as an online refresh. The source Graph revision binds it.
        published[slug]={'schemaVersion':1,'mode':'published-owner-snapshot',
            'graphFile':entry['file'],'identitySpace':graph['identitySpace'],
            'rootRequirementId':graph['rootRequirementId'],
            'graphRevision':graph['revision'],'graphSha256':sha(graph_bytes),
            'planRevision':plan['revision'],'planSha256':sha(plan_bytes),
            'recordedAt':plan['versions'][-1]['recordedAt'],
            'planOwner':plan,'history':real['history'],
            'dependencies':report,'dependencyHistory':history}
    OUTPUT.write_text(json.dumps({'schemaVersion':1,'owners':published},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PUBLISHED_READONLY',json.dumps({k:{'planRevision':v['planRevision'],'graphRevision':v['graphRevision'],
       'dependencies':len(v['dependencies']['rows']),'historyTargets':len(v['dependencyHistory'])} for k,v in published.items()},ensure_ascii=False))

if __name__=='__main__':
    try:publish()
    except (ValueError,KeyError,OSError) as exc:print(str(exc),file=sys.stderr);sys.exit(2)
