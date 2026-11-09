#!/usr/bin/env python3
"""Resumable filesystem moves under the existing reference/grant barriers.

No Graph/Plan mutation or new identity. A cross-filesystem destination is fully
staged and verified before acceptance. Source removal follows destination proof.
"""
import copy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import uuid


class Transfers:
    OPERATIONS=('move','folder_create','folder_move')

    def __init__(self,application):
        self.app=application;self.store=application.store;self.io=self.store.io

    def check(self,ok,code):
        if not ok:raise ValueError('TRANSFER_'+code)

    def path(self,relative,metadata=False):return self.store.path(relative,metadata)
    def journal(self,tx):return self.store.metadata_path('transfers',tx)

    def tree(self,directory):
        self.check(directory.is_dir() and not directory.is_symlink(),'SOURCE_DIRECTORY')
        files={};directories=[];total=0
        for parent,dirs,names in os.walk(directory,followlinks=False):
            parent=Path(parent)
            for name in dirs:
                path=parent/name;self.check(not path.is_symlink(),'SYMLINK_TREE')
                directories.append(path.relative_to(directory).as_posix())
            for name in names:
                path=parent/name;self.check(not path.is_symlink() and stat.S_ISREG(path.stat().st_mode),'REGULAR_FILES_REQUIRED')
                digest=hashlib.sha256()
                with path.open('rb') as stream:
                    while chunk:=stream.read(262144):digest.update(chunk)
                files[path.relative_to(directory).as_posix()]=digest.hexdigest();total+=path.stat().st_size
        return {'files':files,'directories':sorted(directories),'bytes':total}

    def digest_tree(self,value):return self.store.codec.digest({'files':value['files'],'directories':value['directories']})

    def reject_legacy_owners(self,directory,tree,packages):
        # The folder API cannot silently relocate an unmigrated Graph/Plan owner.
        for relative in tree['files']:
            if Path(relative).name not in ('graph.json','plan.json'):continue
            path=self.io.safe_path(directory,relative,True)
            if any(path.is_relative_to(self.path(p['sourcePath'])) for p in packages):continue
            try:value=json.loads(path.read_bytes())
            except (ValueError,UnicodeError):continue
            owner=isinstance(value,dict) and (value.get('actionModel')=='candidate-v6' or
                value.get('coreModel')=='rdg-core-v1' or value.get('kind') in ('temporalPlan','temporalPlanStore') or
                isinstance(value.get('owner'),dict) and isinstance(value.get('versions'),list))
            self.check(not owner,'LEGACY_OWNER_REQUIRES_EXPLICIT_MIGRATION')

    def own_paths(self,record):
        result=set()
        for package in record['packages']:
            suffix=package['sourcePath'][len(record['sourcePath']):].lstrip('/')
            prefix=suffix+'/' if suffix else ''
            for category in ('moves','move-pending'):result.add(prefix+'.rdg/'+category+'/'+record['transactionId']+'.json')
        return result

    def normalized_tree(self,directory,record):
        actual=self.tree(directory);own=self.own_paths(record)
        actual['files']={p:sha for p,sha in actual['files'].items() if p not in own}
        own_dirs={str(Path(p).parent) for p in own}-set(record['tree']['directories'])
        actual['directories']=[d for d in actual['directories'] if d not in own_dirs]
        return actual

    def mark_pending(self,record):
        if record['mode']=='mkdir':return
        for location in (record['sourcePath'],record.get('stagePath'),record['destinationPath']):
            if not location:continue
            directory=self.path(location,location==record.get('stagePath'))
            if not directory.is_dir():continue
            for package in record['packages']:
                suffix=package['sourcePath'][len(record['sourcePath']):].lstrip('/')
                owner=self.io.safe_path(directory,suffix,True) if suffix else directory
                if not (owner/'package.json').is_file():continue
                marker={'transactionId':record['transactionId'],'requestSHA256':record['requestSHA256'],'packageId':package['packageId']}
                self.io.immutable_bytes(self.io.safe_path(owner,'.rdg/move-pending/'+record['transactionId']+'.json',True),self.store.encode(marker))

    def parent_device(self,directory):
        while not directory.exists():directory=directory.parent
        self.check(directory.is_dir() and not directory.is_symlink(),'DESTINATION_PARENT')
        return directory.stat().st_dev

    def same_filesystem(self,source,destination):return source.stat().st_dev==self.parent_device(destination.parent)

    def authorize(self,checks):
        for check in checks:self.app.authorize(check['packageId'],check['permissions'],check['path'])

    def input_binding(self,request,state):
        """Bind filesystem inputs for a later preflight/apply pair."""
        actor,_=self.app.authority._actor(self.app.authority._read(),self.app.token)
        merged={}
        for check in state['checks']:
            key=(check['namespaceId'],check.get('packageId'),check.get('path'))
            merged.setdefault(key,set()).update(check['permissions'])
        permissions=[{'namespaceId':key[0],'packageId':key[1],'path':key[2],
                      'permissions':sorted(value)}
                     for key,value in sorted(merged.items(),
                         key=lambda item:tuple(str(part) for part in item[0]))]
        heads=sorted([[p['packageId'],p['headSHA256']] for p in state['packages']])
        value={'schemaVersion':1,'policy':'filesystem-tree-v1',
               'namespaceId':self.store.namespace_id,'actorGrantId':actor,
               'requestSHA256':self.store.codec.digest(request),
               'sourcePath':state['sourcePath'],'destinationPath':state['destinationPath'],
               'mode':state['mode'],'sourceTreeSHA256':self.digest_tree(state['tree']),
               'packageHeads':heads,'catalog':self.store.catalog_signature(),
               'requiredPermissions':permissions,
               'effectPackageIds':sorted(p['packageId'] for p in state['packages'])}
        return {**value,'sha256':self.store.codec.digest(value)}

    def prepare(self,request):
        op=request['op'];self.check(op in self.OPERATIONS,'OPERATION')
        allowed={'op','transactionId','path','note'}
        if op=='move':allowed|={'targetPackageId','sourcePath','expectedPackageRevision','expectedGraphRevision'}
        elif op=='folder_move':allowed|={'sourcePath','sourcePin'}
        self.check(set(request)<=allowed,'REQUEST_FIELDS')
        destination=request['path'];dest=self.store.validate_destination(destination)
        self.check(not dest.exists(),'DESTINATION_EXISTS')
        checks=[];packages=[];source_path=None;tree={'files':{},'directories':[],'bytes':0}
        def permission(ident,perms,path):
            check={'namespaceId':self.store.namespace_id,'packageId':ident,'permissions':perms,'path':path}
            self.authorize([check]);checks.append(check)
        permission(None,['folder.write'],destination)
        if op!='folder_create':
            if op=='move':
                row=self.app.snapshot(request['targetPackageId'],True)
                self.check(row['head']['revision']==request['expectedPackageRevision'],'PACKAGE_CAS_MISMATCH')
                if 'expectedGraphRevision' in request:self.check(row['graph']['revision']==request['expectedGraphRevision'],'GRAPH_CAS_MISMATCH')
                source_path=row['path'];self.check(request.get('sourcePath',source_path)==source_path,'SOURCE_PATH_CHANGED')
                rows=[row]
            else:
                source_path=request['sourcePath'];self.path(source_path)
                permission(None,['folder.write'],source_path)
                found=[r for r in self.store.scan() if r['path']==source_path or r['path'].startswith(source_path+'/')]
                self.check(all(r['health']=='metadata-verified' for r in found),'SOURCE_CATALOG_UNHEALTHY')
                rows=[self.app.snapshot(r['packageId'],True) for r in found]
            source=self.path(source_path);permission(None,['folder.write'],source_path)
            self.check(source!=dest and not source.is_relative_to(dest) and not dest.is_relative_to(source),'OVERLAPPING_PATHS')
            # A source folder may not be an interior directory of an existing package.
            for row in self.store.scan():
                self.check(not source_path.startswith(row['path']+'/'),'SOURCE_INSIDE_PACKAGE')
            for row in rows:
                self.store.inventory(row)
                suffix=row['path'][len(source_path):].lstrip('/')
                target=destination+('/'+suffix if suffix else '')
                permission(row['packageId'],['package.move'],row['path']);permission(row['packageId'],['package.move'],target)
                packages.append({'packageId':row['packageId'],'sourcePath':row['path'],'destinationPath':target,'headSHA256':row['headSHA256']})
            tree=self.tree(source)
            if op=='folder_move':self.reject_legacy_owners(source,tree,packages)
            if op=='folder_move':self.check(request['sourcePin']==self.digest_tree(tree),'SOURCE_TREE_CHANGED')
        return {'sourcePath':source_path,'destinationPath':destination,'tree':tree,'checks':checks,'packages':packages,
                'mode':'mkdir' if op=='folder_create' else 'rename' if self.same_filesystem(self.path(source_path),dest) else 'copy'}

    def inspect_folder(self,relative):
        self.app.authorize(None,['folder.write'],relative)
        source=self.path(relative)
        for row in self.store.scan():
            self.check(not relative.startswith(row['path']+'/'),'SOURCE_INSIDE_PACKAGE')
            if row['path']==relative or row['path'].startswith(relative+'/'):self.app.snapshot(row['packageId'],True)
        tree=self.tree(source)
        packages=[{'sourcePath':r['path']} for r in self.store.scan() if r['path']==relative or r['path'].startswith(relative+'/')]
        self.reject_legacy_owners(source,tree,packages)
        return {'sourcePath':relative,'sourcePin':self.digest_tree(tree),'files':len(tree['files']),'bytes':tree['bytes']}

    def copy_verified(self,source,destination,tree):
        self.io.mkdirs(destination)
        for relative in tree['directories']:self.io.mkdirs(self.io.safe_path(destination,relative,True))
        for relative,expected in tree['files'].items():
            original=self.io.safe_path(source,relative,True);target=self.io.safe_path(destination,relative,True)
            self.io.mkdirs(target.parent);digest=hashlib.sha256();fd,temporary=tempfile.mkstemp(prefix='.rdg-move-',dir=target.parent)
            try:
                with original.open('rb') as inp,os.fdopen(fd,'wb') as out:
                    while chunk:=inp.read(262144):out.write(chunk);digest.update(chunk)
                    out.flush();os.fsync(out.fileno())
                self.check(digest.hexdigest()==expected,'SOURCE_BYTES_CHANGED')
                os.replace(temporary,target);self.io.sync_dir(target.parent)
            finally:
                if os.path.exists(temporary):os.unlink(temporary)
        self.check(self.digest_tree(self.tree(destination))==self.digest_tree(tree),'STAGE_VERIFICATION_FAILED')

    def handle(self,request,*,preflight=False,failpoint=None,before_accept=None,
               expected_input_binding=None):
        tx=request['transactionId'];self.check(str(uuid.UUID(tx))==tx,'TRANSACTION_ID')
        request_sha=self.store.codec.digest(request);actor_sha=hashlib.sha256(self.app.token.encode()).hexdigest()
        accepted=self.journal(tx)
        if not preflight and accepted.is_file():
            with self.store.lock(True):return self.resume(tx,request_sha,actor_sha,failpoint)
        self.app.authority._actor(self.app.authority._read(),self.app.token)
        with self.store.lock(not preflight,create=not preflight):
            self.store.check_intent(tx,request_sha,actor_sha)
            state=self.prepare(request)
            binding=self.input_binding(request,state)
            effects={'operation':request['op'],'sourcePath':state['sourcePath'],'destinationPath':state['destinationPath'],
                     'packages':copy.deepcopy(state['packages']),'files':len(state['tree']['files']),'bytes':state['tree']['bytes'],'mode':state['mode']}
            if expected_input_binding is not None:self.check(expected_input_binding==binding,'PREVIEW_INPUTS_CHANGED')
            if preflight:return {'preflight':True,'accepted':False,'effects':effects,
                                 'requiredPermissions':state['checks'],'inputBinding':binding}
            self.store.initialize()
            self.io.immutable_bytes(self.store.metadata_path('intents',tx),self.store.encode({'transactionId':tx,'requestSHA256':request_sha,'actorTokenSHA256':actor_sha}))
            stage=None
            if state['mode']=='copy':
                parent=Path(state['destinationPath']).parent.as_posix();name='.rdg-transfer-'+str(uuid.uuid5(uuid.UUID(tx),self.digest_tree(state['tree'])))
                stage=name if parent=='.' else parent+'/'+name
                self.copy_verified(self.path(state['sourcePath']),self.path(stage,True),state['tree'])
            if failpoint:failpoint('move-staged')
            if before_accept:before_accept()
            with self.app.authority.checked_portable_transaction(self.app.token,state['checks']) as verified:
                self.check(not self.path(state['destinationPath']).exists(),'DESTINATION_RACE')
                if state['sourcePath']:
                    self.check(self.digest_tree(self.tree(self.path(state['sourcePath'])))==self.digest_tree(state['tree']),'SOURCE_TREE_CHANGED')
                    for package in state['packages']:
                        self.check(self.store.locate(package['packageId'])['headSHA256']==package['headSHA256'],'SOURCE_HEAD_CHANGED')
                record={'schemaVersion':1,'kind':'rdgFilesystemTransfer','transactionId':tx,'requestSHA256':request_sha,
                    'actorTokenSHA256':actor_sha,'acceptedAt':datetime.now(timezone.utc).isoformat(),'state':'prepared',
                    **state,'stagePath':stage,'authorization':verified,'effects':effects}
                self.io.atomic_bytes(accepted,self.store.encode(record))
                self.mark_pending(record)
                if failpoint:failpoint('move-prepared')
                return self.resume(tx,request_sha,actor_sha,failpoint)

    def resume(self,tx,request_sha,actor_sha,failpoint=None):
        record=json.loads(self.journal(tx).read_bytes())
        self.check(record['requestSHA256']==request_sha,'TRANSACTION_ID_CONFLICT')
        self.check(record['actorTokenSHA256']==actor_sha,'TRANSACTION_ACTOR_MISMATCH')
        if record['state']=='completed':return {**record['result'],'idempotent':True}
        self.mark_pending(record)
        destination=self.path(record['destinationPath']);source=self.path(record['sourcePath']) if record['sourcePath'] else None
        tree=record['tree'];expected=self.digest_tree(tree)
        if record['mode']=='mkdir':
            self.check(not destination.exists() or destination.is_dir(),'DESTINATION_RACE')
            self.io.mkdirs(destination)
        elif not destination.exists():
            if record['mode']=='rename':
                self.check(source.exists() and self.digest_tree(self.normalized_tree(source,record))==expected,'SOURCE_TREE_CHANGED')
                self.io.mkdirs(destination.parent);os.rename(source,destination);self.io.sync_dir(source.parent);self.io.sync_dir(destination.parent)
            else:
                stage=self.path(record['stagePath'],True)
                self.check(stage.is_dir() and self.digest_tree(self.normalized_tree(stage,record))==expected,'STAGE_BYTES_MISSING')
                self.io.mkdirs(destination.parent);os.rename(stage,destination);self.io.sync_dir(destination.parent)
        if failpoint:failpoint('move-published')
        if record['mode']!='mkdir':
            # Exclude only this transfer's own completion receipts on exact recovery.
            actual=self.normalized_tree(destination,record)
            self.check(actual['files']==tree['files'] and set(tree['directories'])==set(actual['directories']),'DESTINATION_BYTES_CHANGED')
            record['state']='published';self.io.atomic_bytes(self.journal(tx),self.store.encode(record))
            if source and source.exists():
                remaining=self.normalized_tree(source,record)
                self.check(record['mode']=='copy' and set(remaining['files'])<=set(tree['files']) and
                    all(tree['files'][p]==sha for p,sha in remaining['files'].items()) and
                    set(remaining['directories'])<=set(tree['directories']),'SOURCE_TREE_CHANGED')
                for relative,sha in tree['files'].items():
                    file=self.io.safe_path(source,relative,True)
                    if not file.exists():continue
                    self.check(self.io.file_sha(file)==sha,'SOURCE_BYTES_CHANGED');file.unlink()
                    if failpoint:failpoint('move-cleanup-file')
                for relative in self.own_paths(record):
                    own=self.io.safe_path(source,relative,True)
                    if own.is_file():own.unlink()
                for directory in sorted({str(Path(p).parent) for p in self.own_paths(record)}-set(tree['directories']),reverse=True):
                    path=self.io.safe_path(source,directory,True)
                    if path.exists():path.rmdir()
                for relative in sorted(tree['directories'],key=lambda s:len(s.split('/')),reverse=True):
                    directory=self.io.safe_path(source,relative,True)
                    if directory.exists():directory.rmdir()
                source.rmdir();self.io.sync_dir(source.parent)
        if failpoint:failpoint('move-source-removed')
        receipt={'schemaVersion':1,'transactionId':tx,'requestSHA256':request_sha,'acceptedAt':record['acceptedAt'],
                 'operation':record['effects']['operation'],'effects':record['effects'],'published':True}
        for package in record['packages']:
            proof=self.io.safe_path(self.path(package['destinationPath']),'.rdg/moves/'+tx+'.json',True)
            self.io.immutable_bytes(proof,self.store.encode({**receipt,'packageId':package['packageId'],'headSHA256':package['headSHA256']}))
        result={'accepted':True,'published':True,'transactionId':tx,'effects':record['effects'],
                'packages':[{'packageId':p['packageId'],'path':p['destinationPath'],'receipt':{**receipt,'packageId':p['packageId']}} for p in record['packages']]}
        record.update(state='completed',result=result);self.io.atomic_bytes(self.journal(tx),self.store.encode(record))
        return result
