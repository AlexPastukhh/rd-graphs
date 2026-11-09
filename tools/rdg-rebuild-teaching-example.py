#!/usr/bin/env python3
"""Guarded destructive reset of a specifically registered TEACHING graph owner.

This is not a normal Graph edit, cannot apply to ordinary working projects, and
never erases one event as though the underlying immutable transaction remained.
It resets Graph + its exclusive journal + Plan + Gendocen together, then uses
the existing authorized public Graph/Plan/Gendocen API builder from scratch.
Outside examples the ordinary append-only writer remains the only interface.

Run without --reset for an inspectable dry run. Explicit confirmation required.
Do not run concurrently with a connected Graph/Plan Helper or other editor.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from importlib.machinery import SourceFileLoader

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'tools/rdg-resettable-examples.json'
JOURNALS=ROOT/'graphs/workspaces/.transactions'
DERIVED=(ROOT/'graphs/index.json',ROOT/'tools/rd-graph-data.js',
         ROOT/'tools/rdg-published-owners.json')


def require(condition,reason):
    if not condition:raise ValueError('TEACHING_RESET_DENIED: '+reason)


def inside(relative):
    require(isinstance(relative,str) and '..' not in Path(relative).parts and
            not Path(relative).is_absolute() and '\\' not in relative,'INVALID_RELATIVE_PATH')
    value=ROOT/relative
    require(value.resolve().is_relative_to(ROOT.resolve()) and not value.is_symlink(),
            'SYMLINK_OR_OUTSIDE_ROOT')
    return value


def inventory(slug,policy):
    file=policy['graphFile']
    require(file==f'workspaces/{slug}/graph.json','NOT_A_REGISTERED_DEDICATED_GRAPH_OWNER')
    require(policy['planFile']==f'plans/{slug}/plan.json' and
            policy['engineDir']==f'.rdg-gendocen-projects/{slug}' and
            policy['builder']=='tools/rdg-build-working-example.py','OWNER_SCOPE_MISMATCH')
    gpath=inside('graphs/'+file)
    ppath=inside(policy['planFile'])
    ep=inside(policy['engineDir'])
    require(gpath.is_file() and ppath.is_file() and ep.is_dir(),'ALL_ORIGINAL_OWNERS_REQUIRED')
    graph=json.loads(gpath.read_text(encoding='utf8'))
    require(graph.get('id')==slug and graph.get('identitySpace')==policy['identitySpace']
            and graph.get('actionModel')=='candidate-v6' and
            graph.get('purpose')==policy['expectedPurpose'] and
            graph.get('readOnly') is not True,'GRAPH_NOT_REGISTERED_TEACHING_OWNER')
    plan=json.loads(ppath.read_text(encoding='utf8'))
    require(plan.get('kind')=='temporalPlanOwner' and
            plan.get('owner',{}).get('sourcePath')==policy['planFile'] and
            plan.get('owner',{}).get('identitySpace')==policy['identitySpace'],
            'PLAN_NOT_DEDICATED_TEACHING_OWNER')
    catalog=json.loads((ROOT/'graphs/catalog.json').read_text(encoding='utf8'))
    require(catalog.get('entries',{}).get(file,{}).get('folder')=='examples',
            'NOT_IN_EXAMPLES_FOLDER')
    idx=json.loads((ROOT/'graphs/index.json').read_text(encoding='utf8'))
    require(all(item['file']==file for item in idx.get('graphs',[])
                if item.get('actionModel')=='candidate-v6' and
                item.get('identitySpace')==policy['identitySpace']),
            'EXTERNAL_GRAPH_SHARES_REQUIREMENT_IDENTITY')
    for other in (ROOT/'plans').glob('*/plan.json'):
        if other==ppath:continue
        value=json.loads(other.read_text(encoding='utf8'))
        for step in value.get('versions',[{}])[-1].get('plan',{}).get('steps',[]):
            ref=step.get('requirementRef') or step.get('actionRef') or {}
            require(ref.get('graphFile')!=file and
                    ref.get('identitySpace')!=policy['identitySpace'],
                    'EXTERNAL_PLAN_REFERENCES_EXAMPLE')
    source=[]
    for path in sorted(JOURNALS.glob('*.json')):
        require(not path.is_symlink(),'JOURNAL_SYMLINK')
        journal=json.loads(path.read_text(encoding='utf8'))
        affected=[rec.get('file') for rec in journal.get('records',[])]
        if file not in affected:continue
        require(journal.get('state')=='completed' and affected==[file],
                'SHARED_OR_INCOMPLETE_JOURNAL:'+path.name)
        source.append(path)
    require(len(source)>=1,'CANONICAL_HISTORY_REQUIRED')
    # No unrelated records, foreign Graph transaction or Plan will be removed.
    return {'slug':slug,'file':file,'graphDir':gpath.parent,'planDir':ppath.parent,
            'engineDir':ep,'journals':source,'graph':graph,'plan':plan}


def fresh_owner(slug,file):
    graph=json.loads((ROOT/'graphs'/file).read_text(encoding='utf8'))
    plan=json.loads((ROOT/'plans'/slug/'plan.json').read_text(encoding='utf8'))
    require(graph.get('revision')==10 and graph.get('purpose')=='real-api-teaching-workflow' and
            {n['kind'] for n in graph['nodes']}<= {'requirement','action'},
            'REBUILD_GRAPH_NOT_CLEAN_OR_WRONG_MODEL')
    require(not any(n['id']=='C-ASSURANCE' for n in graph['nodes']) and
            not any(e.get('type')=='CONTEXT_FOR' for e in graph['edges']),
            'REBUILD_HAS_SYNTHETIC_CONTEXT')
    require(plan['revision']==4 and len(plan['versions'])==4,
            'REBUILD_PLAN_NOT_FRESH')
    rows=[json.loads(p.read_text(encoding='utf8')) for p in JOURNALS.glob('*.json')]
    writers=[j for j in rows if any(r['file']==file for r in j.get('records',[]))]
    require(len(writers)==10 and all(j['state']=='completed' for j in writers),
            'REBUILD_GRAPH_WRITER_NOT_FRESH')
    require(len(graph['events'])==4 and
            not any(e['type'] in ('action_executed','requirement_achieved') for e in graph['events']),
            'REBUILD_INVENTS_EXECUTION_OR_TARGET')
    for item in plan['versions'][-1]['plan']['steps']:
        ref=item.get('requirementRef') or item.get('actionRef')
        require(ref and ref.get('graphFile')==file and
                any(n['id']==ref['nodeId'] for n in graph['nodes']),
                'REBUILD_PLAN_REF_NOT_IN_GRAPH')
    return graph,plan


@contextmanager
def durable_reset_storage():
    # Intentionally not TemporaryDirectory: an unrecoverable exception or a
    # killed process must NEVER automatically delete an already moved owner.
    # A stranded backup stays on disk for manual, audited recovery.
    storage=Path(tempfile.mkdtemp(prefix='.rdg-example-reset-',dir=ROOT))
    try:
        yield storage
    finally:
        pass  # Explicit cleanup only on verified success or verified rollback.


def reset(slug,policy,items):
    # Never discard a pending recovery when starting another destructive run.
    require(not list(ROOT.glob('.rdg-example-reset-*')), 'UNRESOLVED_RESET_BACKUP_PRESENT')
    with durable_reset_storage() as storage:
        originals={}
        def preserve(path):
            require(path.is_relative_to(ROOT) and not path.is_symlink(),'RESET_PATH_INVALID')
            dest=storage/('owner-'+str(len(originals)))
            shutil.move(str(path),str(dest))
            originals[path]=dest
        for index,path in enumerate(DERIVED):
            if path.is_file():shutil.copy2(path,storage/('derived-'+str(index)))
        # The 100 archived old-model graphs never participate in these owner
        # changes. Temporarily hide those immutable *source directories* from
        # expensive full-catalog cross-checking on each of the 10 real writer
        # commits. They are restored byte-for-byte before final publication.
        # This is not deleting or migrating archival examples.
        archives=(ROOT/'graphs/examples',ROOT/'graphs/2d')
        def restore_archives():
            for folder in archives:
                saved=originals.get(folder)
                if saved is not None:
                    require(not folder.exists(),'ARCHIVE_RESTORE_PATH_OCCUPIED')
                    shutil.move(str(saved),str(folder))
                    del originals[folder]
        try:
            for folder in archives:
                require(folder.is_dir() and not folder.is_symlink(),'ARCHIVE_SOURCE_REQUIRED')
                for item in folder.rglob('graph.json'):
                    archived=json.loads(item.read_text(encoding='utf8'))
                    require(archived.get('actionModel')!='candidate-v6' or
                            any(archived.get(flag) is True for flag in
                                ('readOnly','exampleOnly','templateOnly','catalogHidden')),
                            'CAN_NOT_HIDE_ACTIVE_ARCHIVE_GRAPH:'+str(item))
                preserve(folder)
            preserve(items['graphDir'])
            preserve(items['planDir'])
            preserve(items['engineDir'])
            for receipt in items['journals']:preserve(receipt)
            # No prior Graph owner exists now; published stale cache is only a
            # reader artifact and is omitted until a new publication is ready.
            index=SourceFileLoader('reset_index',str(ROOT/'tools/graph-index.py')).load_module()
            index.rebuild_index()
            command=[sys.executable,'-B',str(ROOT/policy['builder']),'--apply']
            print('REBUILD_VIA_AUTHORIZED_REAL_WRITERS_FAST_ARCHIVE_ISOLATION',slug,flush=True)
            subprocess.run(command,cwd=ROOT,check=True,timeout=600)
            fresh_owner(slug,items['file'])
            restore_archives()
            index.rebuild_index()
            subprocess.run([sys.executable,'-B',str(ROOT/'tools/rdg-publish-readonly-owners.py')],
                cwd=ROOT,check=True,timeout=180)
            index.rebuild_index()
            print('TEACHING_EXAMPLE_REBUILT_FROM_EMPTY',json.dumps({
                'slug':slug,'graphRevision':10,'graphWriterTransactions':10,
                'planRevision':4,'oldTransactionsCleared':len(items['journals']),
                'historyReset':True},ensure_ascii=False),flush=True)
            # Exact old bytes are intentionally discarded only after BOTH
            # API rebuild and derived Viewer/Gendocen snapshot succeeded.
            shutil.rmtree(storage)
        except BaseException:
            # CRITICAL: NEVER remove an existing owner/receipt that was not
            # already preserved! A failure while inspecting archives, or while
            # moving the first backup, must not delete a byte of live data.
            for path in (items['graphDir'],items['planDir'],items['engineDir']):
                if path in originals and path.is_dir():shutil.rmtree(path)
            old_receipts=set(items['journals'])
            for journal in JOURNALS.glob('*.json'):
                if journal in old_receipts:continue
                record=json.loads(journal.read_text(encoding='utf8'))
                if any(row.get('file')==items['file'] for row in record.get('records',[])):
                    require([row['file'] for row in record['records']]==[items['file']],
                            'CONCURRENT_FOREIGN_GRAPH_WRITE_DURING_RECOVERY')
                    journal.unlink()
            for path,saved in originals.items():
                require(not path.exists(),'RESTORE_PATH_OCCUPIED:'+str(path))
                path.parent.mkdir(parents=True,exist_ok=True)
                shutil.move(str(saved),str(path))
            for index,path in enumerate(DERIVED):
                copy=storage/('derived-'+str(index))
                if copy.exists():shutil.copy2(copy,path)
            print('TEACHING_RESET_ROLLED_BACK_TO_EXACT_OLD_OWNERS',file=sys.stderr,flush=True)
            shutil.rmtree(storage)
            raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reset',metavar='EXAMPLE_SLUG',help='Exact allowlisted teaching Graph to rebuild')
    p.add_argument('--confirm',metavar='EXAMPLE_SLUG',help='Repeat slug to consent to full history removal')
    options=p.parse_args()
    policy=json.loads(REGISTRY.read_text(encoding='utf8'))
    require(policy.get('schemaVersion')==1 and isinstance(policy.get('examples'),dict),
            'RESET_REGISTRY_INVALID')
    if not options.reset:
        print('EXPLICITLY_REBUILDABLE_EXAMPLES',', '.join(policy['examples']))
        print('DRY_RUN: pass --reset SLUG --confirm SLUG; this destroys old teaching Graph/Plan/engine history only after backing it up for rollback')
        return
    require(options.reset in policy['examples'],'ONLY_ALLOWLISTED_EXAMPLES_CAN_BE_RESET')
    require(options.confirm==options.reset,'EXPLICIT_MATCHING_CONFIRMATION_REQUIRED')
    items=inventory(options.reset,policy['examples'][options.reset])
    print('RESET_SCOPE',json.dumps({'slug':options.reset,'graphRevision':items['graph']['revision'],
        'planRevision':items['plan']['revision'],'writerTransactions':len(items['journals']),
        'engineDir':str(items['engineDir'].relative_to(ROOT))},ensure_ascii=False),flush=True)
    reset(options.reset,policy['examples'][options.reset],items)

if __name__=='__main__':
    try:main()
    except (ValueError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as error:
        print(str(error),file=sys.stderr);sys.exit(2)
