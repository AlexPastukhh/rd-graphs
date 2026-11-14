#!/usr/bin/env python3
"""Portable package CLI. Bearer tokens are read only from RDG_AUTH_TOKEN."""
import argparse
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import sys
import subprocess

TOOLS=Path(__file__).resolve().parent

def module(name):return SourceFileLoader('portable_cli_'+name.replace('-','_'),str(TOOLS/(name+'.py'))).load_module()

def application(config,token,attribution='assistant',*,io_override=None,authority_factory=None):
    model=module('rdg-portable-model');io=module('rdg-transaction-io');backend=module('rdg-portable-store')
    service=module('rdg-portable-service');auth=module('rdg-authority');core=module('rdg-model-profiles')
    if io_override is not None:io=io_override
    authority_factory=authority_factory or auth.Authority
    store=backend.FileStore(config['packageRoot'],config['namespaceId'],io,model,config.get('coordinationRoot'))
    def layout_port(request):
        env={k:v for k,v in os.environ.items() if k not in ('RDG_AUTH_TOKEN','RDG_AUTH_STORE')}
        result=subprocess.run(['node',str(TOOLS/'rdg-layout-cli.cjs'),'--transform-stdin'],input=json.dumps(request),
            text=True,capture_output=True,timeout=15,env=env)
        if result.returncode:raise ValueError('PORTABLE_LAYOUT_CODEC: '+result.stderr.strip()[-500:])
        return json.loads(result.stdout)
    app=service.Application(store,authority_factory(config['authorityStore']),core,model,token,layout_port,module('rdg-workflow-commands').core_request_data,attribution)
    app.recommendations=module('rdg-recommendations')
    app.transfers=module('rdg-package-transfer').Transfers(app)
    legacy=None
    if config.get('migrationConfig'):
        legacy=json.loads(Path(config['migrationConfig']).read_text());legacy['configFile']=str(Path(config['migrationConfig']).absolute())
    app.migration=module('rdg-legacy-migration').Migration(app,legacy,module('rdg-temporal-plan-owner') if legacy else None)
    return app

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('capabilities','read_ref','catalog','read','history','dependencies','locks','resolve','source_snapshot','migration_sources','migration_inspect','preflight','apply','schema','receipt','recover','cancel_migration','approval_request','approval_read'))
    parser.add_argument('--packages',required=True,type=Path)
    parser.add_argument('--namespace',required=True)
    parser.add_argument('--coordination-root',type=Path)
    parser.add_argument('--store',default=os.environ.get('RDG_AUTH_STORE'))
    parser.add_argument('--package-id')
    parser.add_argument('--with-plan',action='store_true')
    parser.add_argument('--show-excluded-alternatives',action='store_true',
                        help='Read-only Decision group visibility override')
    parser.add_argument('--request',type=Path)
    parser.add_argument('--expected-input-binding',type=Path)
    parser.add_argument('--preview',type=Path)
    parser.add_argument('--source-detail',choices=('full','graph'),default='full')
    parser.add_argument('--op')
    parser.add_argument('--node')
    parser.add_argument('--source-package-id')
    parser.add_argument('--core-command')
    parser.add_argument('--core-model',choices=('rdg-core-v1','rdg-decision-v1'))
    parser.add_argument('--role',choices=('working','ready','lens'))
    parser.add_argument('--entity-kind',choices=('requirement','decision','action','canon','context','info','finding'))
    parser.add_argument('--history-mode',choices=('important','meaningful','technical','all'))
    parser.add_argument('--detail',choices=('summary','item','full','compact','focus','branch'))
    parser.add_argument('--all-pages',action='store_true',help='Collect focus/branch pages; abort on snapshot change')
    parser.add_argument('--include',action='append')
    parser.add_argument('--limit',type=int,default=25)
    parser.add_argument('--cursor')
    parser.add_argument('--record-id')
    parser.add_argument('--event-id')
    parser.add_argument('--transaction-id')
    parser.add_argument('--source-folder')
    parser.add_argument('--source-key')
    parser.add_argument('--migration-config',type=Path)
    args=parser.parse_args(argv)
    if (args.core_model is not None or args.role is not None or args.entity_kind is not None) and args.command!='schema':
        raise ValueError('PORTABLE_SCHEMA_SELECTORS_ONLY')
    if args.history_mode is not None and args.command!='history':raise ValueError('PORTABLE_HISTORY_MODE_ONLY')
    if args.command=='history' and args.node is not None:raise ValueError('PORTABLE_HISTORY_FOCUS_FILTER_UNAVAILABLE')
    if args.all_pages and not (args.command=='read' and args.detail in ('focus','branch')):raise ValueError('PORTABLE_ALL_PAGES_ONLY')
    if args.record_id is not None and args.command!='read':raise ValueError('PORTABLE_RECORD_ID_ONLY_FOR_READ')
    if args.event_id is not None and args.command!='history':raise ValueError('PORTABLE_EVENT_ID_ONLY_FOR_HISTORY')
    if (args.detail is not None or args.include is not None or args.limit!=25 or args.cursor is not None) and args.command not in ('read','history'):
        raise ValueError('PORTABLE_READ_OPTIONS_ONLY')
    if args.expected_input_binding and args.command not in ('preflight','apply'):
        raise ValueError('PORTABLE_INPUT_BINDING_ONLY_FOR_PREFLIGHT_APPLY')
    if args.preview and args.command!='preflight':raise ValueError('PORTABLE_PREVIEW_ONLY_FOR_PREFLIGHT')
    if args.source_detail!='full' and args.command!='source_snapshot':raise ValueError('PORTABLE_SOURCE_DETAIL_ONLY_FOR_SOURCE_SNAPSHOT')
    token=os.environ.get('RDG_AUTH_TOKEN')
    if not token or not args.store:raise ValueError('PORTABLE_CREDENTIALS_REQUIRED')
    app=application({'packageRoot':str(args.packages),'namespaceId':args.namespace,
                     'coordinationRoot':str(args.coordination_root) if args.coordination_root else None,
                     'authorityStore':args.store,'migrationConfig':str(args.migration_config) if args.migration_config else None},token)
    if args.command=='schema':result=app.schema(args.op,args.package_id,args.node,args.source_package_id,args.core_command,args.source_folder,args.source_key,
        core_model=(args.core_model or 'rdg-decision-v1') if args.op=='create' else args.core_model,role=args.role,entity_kind=args.entity_kind)
    elif args.command=='receipt':result=app.receipt(args.package_id,args.transaction_id)
    elif args.command=='recover':result=app.recover(args.transaction_id)
    elif args.command=='cancel_migration':result=app.migration.cancel(args.transaction_id)
    elif args.command=='capabilities':result=app.call({'method':'capabilities',**({'packageId':args.package_id} if args.package_id else {})})
    elif args.command=='read_ref':result=app.call({'method':'read_ref','reference':json.load(sys.stdin),**({'packageId':args.package_id} if args.package_id else {})})
    elif args.command=='catalog':result=app.catalog()
    elif args.command in ('dependencies','locks'):result=app.call({'method':args.command,'packageId':args.package_id})
    elif args.command=='approval_request':
        body=json.loads(args.request.read_text() if args.request else sys.stdin.read())
        if not isinstance(body,dict) or set(body)!={'request','rationale'}:raise ValueError('PORTABLE_APPROVAL_MESSAGE_FIELDS')
        result=app.call({'method':'approval_request','request':body['request'],'rationale':body['rationale']})
    elif args.command=='approval_read':result=app.call({'method':'approval_read','requestId':args.transaction_id})
    elif args.command=='migration_sources':result=app.migration.sources()
    elif args.command=='migration_inspect':result=app.migration.inspect(args.source_key)
    elif args.command=='source_snapshot':
        if not args.package_id:raise ValueError('PORTABLE_PACKAGE_ID_REQUIRED')
        result=app.source_snapshot(args.package_id,json.loads(sys.stdin.read()),{'kind':'focus','id':args.node} if args.node else None,detail=args.source_detail)
    elif args.command in ('read','history','resolve'):
        if not args.package_id:raise ValueError('PORTABLE_PACKAGE_ID_REQUIRED')
        if args.command=='history':
            result=app.call({'method':'history','packageId':args.package_id,
                             'view':{'kind':'graph','historyMode':args.history_mode or 'all'},
                             **({'detail':args.detail or 'item'} if args.event_id else {'detail':args.detail} if args.detail else {}),
                             **({'eventId':args.event_id} if args.event_id else {}),
                             **({'include':args.include} if args.include is not None else {}),
                             'limit':args.limit,**({'cursor':args.cursor} if args.cursor else {})})
        elif args.command=='resolve':result=app.resolve(args.package_id,json.loads(sys.stdin.read()))
        else:
            view=({'kind':'focus','id':args.node} if args.node else {'kind':'graph'})
            if args.show_excluded_alternatives:view['showExcludedAlternatives']=True
            detail=args.detail
            if detail in ('summary','item','focus','branch'):
                if args.show_excluded_alternatives or args.with_plan:
                    raise ValueError('PORTABLE_READ_USE_INCLUDE_OR_FULL')
                message={'method':'read','packageId':args.package_id,'detail':detail,
                         **({'nodeId':args.node} if args.node else {}),
                         **({'recordId':args.record_id} if args.record_id else {}),
                         'include':args.include or [],'limit':args.limit,
                         **({'cursor':args.cursor} if args.cursor else {})}
                result=(module('rdg-scoped-read').read_pages(app,message,args.all_pages)
                        if detail in ('focus','branch') else app.call(message))
            else:
                if args.record_id:raise ValueError('PORTABLE_RECORD_ID_REQUIRES_COMPACT')
                result=app.call({'method':'read','packageId':args.package_id,'includePlan':args.with_plan,
                                 'view':view,**({'detail':detail} if detail else {}),
                                 **({'include':args.include} if args.include is not None else {}),
                                 'limit':args.limit,**({'cursor':args.cursor} if args.cursor else {})})
    else:
        request=json.loads(args.request.read_text() if args.request else sys.stdin.read())
        binding=json.loads(args.expected_input_binding.read_text()) if args.expected_input_binding else None
        result=app.request(request,preflight=args.command=='preflight',expected_input_binding=binding,preview=json.loads(args.preview.read_text()) if args.preview else None)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);sys.exit(1)
