#!/usr/bin/env python3
"""Disposable manual preview using the real Application, writer and WebAuthn.

This entry point never opens existing projects or real grants. Windows preview
flushes file contents and uses byte-range locks; directory durability and trust
isolation remain unverified. The ordinary POSIX backend is unchanged.
"""
import argparse
from contextlib import contextmanager
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import socket
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'tools'
def load(name):
    return SourceFileLoader('manual_preview_'+name.replace('-','_'),str(TOOLS/(name+'.py'))).load_module()
def require(ok,message):
    if not ok:raise ValueError('RDG_PREVIEW_'+message)

def preview_io():
    io=load('rdg-transaction-io')
    if os.name=='nt':
        locks=load('rdg-windows-lock')
        # Only this explicitly selected disposable adapter omits directory flush.
        io.sync_dir=lambda path:None
        @contextmanager
        def reference_lock(root,exclusive,create=True):
            root=Path(root).absolute()
            io.require(root.is_dir() and not root.is_symlink(),'COORDINATION_ROOT_REQUIRED')
            path=io.safe_path(root,'.rdg-reference.lock',True)
            if not path.exists() and not create:
                yield
                return
            flags=os.O_RDWR | (os.O_CREAT if create else 0)
            try:fd=os.open(path,flags,0o600)
            except FileNotFoundError:
                if not create:
                    yield
                    return
                raise
            with os.fdopen(fd,'a+b') as stream:
                locks.flock(stream,locks.LOCK_EX if exclusive else locks.LOCK_SH)
                try:yield
                finally:locks.flock(stream,locks.LOCK_UN)
        io.reference_lock=reference_lock
    return io

def build_host(data_dir,port,model_profile='rdg-core-v1'):
    require(model_profile in ('rdg-core-v1','rdg-decision-v1'),'MODEL_PROFILE')
    require(type(port) is int and 0<=port<=65535,'PORT')
    data_dir=Path(data_dir)
    require(data_dir.is_absolute() and not data_dir.resolve().is_relative_to(ROOT),'DATA_OUTSIDE_CODE_REQUIRED')
    require(not any(p.is_symlink() for p in (data_dir,*data_dir.parents)),'DATA_SYMLINK')
    marker=data_dir/'preview.json'
    if data_dir.exists():
        require(marker.is_file() or not any(data_dir.iterdir()),'EXISTING_DATA_REFUSED')
    else:data_dir.mkdir(parents=True)
    io=preview_io()
    authority_module=load('rdg-authority')
    class PreviewAuthority(authority_module.Authority):
        def _save(self,data):
            io.atomic_bytes(self.path,(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
    cli=load('rdg-portable')
    loopback=load('rdg-loopback-helper')

    def application(config,token,attribution='assistant'):
        return cli.application(config,token,attribution,
            io_override=io,authority_factory=PreviewAuthority)

    if model_profile=='rdg-decision-v1':
        return build_decision_host(data_dir,port,marker,application,PreviewAuthority,io,loopback)
    core=load('rdg-core-model')
    credential_module=load('rdg-credential-store')
    authn=load('rdg-webauthn')
    executor_module=load('rdg-approval-executor')
    surface_module=load('rdg-approval-surface')

    if marker.exists():
        settings=json.loads(marker.read_text(encoding='utf-8'))
        require(settings.get('kind')=='rdg-disposable-manual-preview' and settings.get('schemaVersion')==1,'MARKER')
        require(settings['packageRoot']==str(data_dir/'packages') and
                settings['authorityStore']==str(data_dir/'preview-authority.json') and
                settings['coordinationRoot']==str(data_dir),'CONFIG_SCOPE')
        require(port in (0,settings['port']),'ORIGIN_PORT_CHANGED')
        port=settings['port']
    else:
        if port==0:
            with socket.socket() as selected:
                selected.bind(('127.0.0.1',0));port=selected.getsockname()[1]
        namespace=str(uuid.uuid4())
        authority=PreviewAuthority(data_dir/'preview-authority.json')
        admin=authority.init_local(plan_capable=True,graph_read_capable=True,portable_roots=[namespace])['token']
        permissions=['graph.read','graph.write','plan.read','plan.create','plan.edit','plan.branch',
                     'package.create','package.copy','package.move','folder.write']
        actors=[authority.manage('issue',admin,{'permissions':permissions,'scopes':['packages/'+namespace+'/']}) for _ in range(2)]
        settings={'schemaVersion':1,'kind':'rdg-disposable-manual-preview',
            'packageRoot':str(data_dir/'packages'),'namespaceId':namespace,'coordinationRoot':str(data_dir),
            'authorityStore':str(authority.path),'port':port,'ownerToken':admin,
            'initiatorToken':actors[0]['token'],'executorToken':actors[1]['token'],
            'executorGrantId':actors[1]['id'],'principalId':'preview-user',
            'authorityPrincipal':'key:preview-user'}
        config={k:settings[k] for k in ('packageRoot','namespaceId','coordinationRoot','authorityStore')}
        ai=application(config,settings['initiatorToken'])
        manual=application(config,settings['initiatorToken'],'user')
        scenarios=[
            ('01-approve','Согласовать план работ','Согласовать план после проверки пользователем',
             'Проверка подтверждения: предлагаю уточнить название R1. Сравните «Было / Станет» и подтвердите.'),
            ('02-reject','Сохранить исходный вариант','Заменить исходный вариант',
             'Проверка отказа: отклоните этот запрос. Исходное название R1 должно сохраниться.'),
            ('03-free','Свободная правка',None,None)]
        for slug,title,after,rationale in scenarios:
            request={'op':'create','transactionId':str(uuid.uuid4()),'path':'working/'+slug,
                     'role':'working','title':title,'scope':'Учебный пример для ручной проверки RDG'}
            ident=ai.request(request)['packages'][0]['packageId']
            if after is None:continue
            lock=manual.schema('lock_set',ident)['request']
            lock.update(operation='edit',principals=['key:preview-user'],
                        authorityPrincipal='user:preview-setup',message='Правка требует подтверждения.',
                        note='Подготовка отдельного тестового примера')
            manual.request(lock)
            current=ai.read(ident)
            command={'op':'core','transactionId':str(uuid.uuid4()),'targetPackageId':ident,
                'expectedPackageRevision':current['package']['revision'],
                'expectedGraphRevision':current['graph']['revision'],'command':'edit',
                'data':{'nodeId':'R1','changes':{'title':after}},'note':rationale}
            ai.approval_request(command,rationale)

        shared_request={'op':'create','transactionId':str(uuid.uuid4()),'path':'working/04-shared-info',
                        'role':'working','title':'Общий критерий и зависимость',
                        'scope':'Учебная проверка shared info dependency'}
        shared_id=ai.request(shared_request)['packages'][0]['packageId']
        shared_entities=[
            {'id':'C3','kind':'info','title':'Общий критерий C3',
             'description':'Shared criterion used by several Canon views'},
            {'id':'Y','kind':'requirement','title':'Зависимая R Y',
             'description':'Requirement with an explicit shared criterion dependency',
             'scope':'Synthetic preview','status':'potential'},
        ]
        for entity in shared_entities:
            add=manual.schema('core',shared_id,command='add')['request']
            add['data']['entity']=entity
            add['note']='Seed shared criterion dependency preview data'
            manual.request(add)
        io.atomic_bytes(marker,(json.dumps(settings,ensure_ascii=False,indent=2)+'\n').encode())

    config={k:settings[k] for k in ('packageRoot','namespaceId','coordinationRoot','authorityStore')}
    authority=PreviewAuthority(settings['authorityStore'])
    credentials=credential_module.CredentialStore(authority)
    origin='http://localhost:'+str(port)
    spec={'principalId':settings['principalId'],'displayName':'Пользователь · ручная проверка',
          'namespaceId':settings['namespaceId'],'executorGrantId':settings['executorGrantId'],
          'authorityPrincipal':settings['authorityPrincipal'],'rpId':'localhost','origin':origin,'active':True}
    old=next((r for r in credentials.inspect(settings['ownerToken']).get('bindings',[])
              if r['principalId']==settings['principalId']),None)
    credentials.configure_binding(settings['ownerToken'],spec,expected_revision=old['revision'] if old else 0)

    class PreviewSurface(surface_module.ApprovalSurface):
        def list_requests(self):
            result=super().list_requests()
            result['requests'].sort(key=lambda row:row['createdAt'])
            return result
        def enrollment_info(self):
            if self._enrollment_permit is None:
                _,active=credentials.credentials(settings['principalId'],'localhost',origin)
                if active:return None
                self._enrollment_permit=credentials.issue_enrollment(settings['ownerToken'],settings['principalId'],ttl=300)
            info=super().enrollment_info()
            if info['state'] in ('expired','failed','interrupted','invalidated'):
                self._registration=None
                self._enrollment_permit=credentials.issue_enrollment(settings['ownerToken'],settings['principalId'],ttl=300)
                info=super().enrollment_info()
            return info

    def factory(actual_origin):
        require(actual_origin==origin,'ORIGIN')
        app=application(config,settings['executorToken'])
        verifier=authn.Verifier('localhost',origin,credential_store=credentials)
        executor=executor_module.ApprovalExecutor(app,verifier,settings['principalId'],
            settings['authorityPrincipal'],settings['executorGrantId'])
        return PreviewSurface(executor)

    editor=loopback.PortableEditor(config,settings['initiatorToken'],application_factory=application)
    server=loopback.make_server(editor,approval_factory=factory,listen_port=port,
        banner='RDG · Тестовый пример. Зарегистрируйте ключ, затем подтвердите первый запрос и отклоните второй. Изменения сохраняются только в учебных данных.')
    return server

def build_decision_host(data_dir,port,marker,application,authority_factory,io,loopback):
    """Separate disposable Decision namespace; the same Application owns all writes."""
    if marker.exists():
        settings=json.loads(marker.read_text(encoding='utf8'))
        require(settings.get('kind')=='rdg-disposable-decision-preview' and settings.get('schemaVersion')==1 and
            settings.get('modelProfile')=='rdg-decision-v1','DECISION_MARKER')
        require(settings['packageRoot']==str(data_dir/'packages') and settings['authorityStore']==str(data_dir/'preview-authority.json') and
            settings['coordinationRoot']==str(data_dir),'CONFIG_SCOPE')
        require(port in (0,settings['port']),'ORIGIN_PORT_CHANGED');port=settings['port']
    else:
        if port==0:
            with socket.socket() as selected:selected.bind(('127.0.0.1',0));port=selected.getsockname()[1]
        namespace=str(uuid.uuid4());authority=authority_factory(data_dir/'preview-authority.json')
        admin=authority.init_local(plan_capable=True,graph_read_capable=True,portable_roots=[namespace])['token']
        grant=authority.manage('issue',admin,{'permissions':['graph.read','graph.write','plan.read','plan.create','plan.edit','plan.branch','package.create','package.copy'],
            'scopes':['packages/'+namespace+'/']})
        settings={'schemaVersion':1,'kind':'rdg-disposable-decision-preview','modelProfile':'rdg-decision-v1',
            'packageRoot':str(data_dir/'packages'),'namespaceId':namespace,'coordinationRoot':str(data_dir),
            'authorityStore':str(authority.path),'initiatorToken':grant['token'],'port':port,
            'seedRequest':{'op':'create','transactionId':str(uuid.uuid4()),'coreModel':'rdg-decision-v1','role':'working',
                'path':'working/manual-decision','title':'Ручная проверка Decision','scope':'Отдельная песочница для проверки интерфейса RDG',
                'rootReason':'Проверить создание блоков, планирование, линзы и сохранение через настоящий Application'}}
        io.atomic_bytes(marker,(json.dumps(settings,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
    config={k:settings[k] for k in ('packageRoot','namespaceId','coordinationRoot','authorityStore')}
    app=application(config,settings['initiatorToken'],'user')
    if not settings.get('packageId'):
        result=app.request(settings['seedRequest']);settings['packageId']=result['packages'][0]['packageId']
        io.atomic_bytes(marker,(json.dumps(settings,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
    else:
        saved=app.snapshot(settings['packageId'])
        require(saved['graph']['coreModel']=='rdg-decision-v1','DECISION_PROFILE')
    editor=loopback.PortableEditor(config,settings['initiatorToken'],application_factory=application)
    server=loopback.make_server(editor,listen_port=port,manual_session_port=True,start_in_explorer=True,
        banner='RDG Decision · Ручная проверка. Изменения сохраняются в отдельной песочнице. Оставьте консоль открытой; для остановки нажмите Ctrl+C.')
    server.preview_data_dir=str(data_dir);server.preview_model_profile='rdg-decision-v1'
    io.atomic_bytes(data_dir/'session-url.txt',(server.session_url+'\n').encode())
    return server


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test-preview',action='store_true',required=True)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--model-profile',choices=('rdg-core-v1','rdg-decision-v1'),default='rdg-core-v1')
    parser.add_argument('--open-browser',action='store_true')
    args=parser.parse_args()
    require(0<=args.port<=65535,'PORT')
    server=build_host(args.data_dir,args.port,args.model_profile)
    print(json.dumps({'url':server.session_url,'previewOnly':True,'modelProfile':args.model_profile,'dataDirectory':str(args.data_dir),
        'osIsolationVerified':False,'windowsDirectoryDurabilityVerified':False},ensure_ascii=False),flush=True)
    if args.open_browser:
        import webbrowser
        webbrowser.open(server.session_url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);sys.exit(1)
