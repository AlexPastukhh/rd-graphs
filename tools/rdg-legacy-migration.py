#!/usr/bin/env python3
"""Opt-in legacy-owner adapter. Source bytes stay immutable and scoped.

Only configured, closed core owners are supported. Unsupported Plan constructs
or incoming legacy refs block the switch. No live owner is migrated at startup.
"""
import base64
import copy
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import uuid


class Migration:
    def __init__(self,app,legacy=None,owner_port=None):
        self.app=app;self.store=app.store;self.io=self.store.io;self.config=legacy;self.owner=owner_port
        self.root=self.store.coordination_root.resolve()
        if legacy:
            self.check(set(legacy)<={'graphRoot','planRoot','owners','registryFiles','configFile'},'CONFIG_FIELDS')
            self.graph_root=self.configured_path(legacy['graphRoot']);self.plan_root=self.configured_path(legacy['planRoot'])
            self.check(self.graph_root.parent==self.root,'SHARED_REFERENCE_BARRIER_REQUIRED')
            self.check(isinstance(legacy['owners'],dict) and bool(legacy['owners']),'OWNERS_REQUIRED')

    def check(self,ok,code):
        if not ok:raise ValueError('MIGRATION_'+code)

    def configured_path(self,value):
        path=Path(value);path=(path if path.is_absolute() else self.root/path).absolute()
        self.check(path.is_relative_to(self.root) and not any(p.is_symlink() for p in (path,*path.parents)),'SOURCE_OUTSIDE_CONFIGURED_ROOT')
        return path

    def configured_file(self,value,external=False):
        path=Path(value);path=(path if path.is_absolute() else self.root/path).absolute()
        self.check(external or path.is_relative_to(self.root),'SOURCE_OUTSIDE_CONFIGURED_ROOT')
        self.check(not any(p.is_symlink() for p in (path,*path.parents)),'SYMLINK_SOURCE')
        self.check(path!=self.app.authority.path.resolve(),'AUTHORITY_FILE_FORBIDDEN')
        return path

    def label(self,path):return str(path.relative_to(self.root)) if path.is_relative_to(self.root) else 'configured-file:'+path.name

    def marker(self,path):return path.with_name(path.name+'.rdg-migration.json')
    def journal(self,tx):return self.store.metadata_path('migrations',tx)
    def raw_sha(self,path):return hashlib.sha256(self.configured_file(path,True).read_bytes()).hexdigest()

    def sources(self):
        rows=[]
        if self.config:
            for key,source in self.config['owners'].items():
                try:self.app.authority.authorize_graph_read(self.app.token,[source['graphFile']])
                except ValueError:continue
                route=self.io.legacy_owner_route(self.io.safe_path(self.graph_root,source['graphFile']))
                rows.append({'sourceKey':key,'graphFile':source['graphFile'],'planFile':source.get('planFile'),
                    'role':source.get('role','working'),'route':route})
        return {'configured':self.config is not None,'sources':rows}

    def auth_legacy(self,source,all_graphs,all_plans):
        auth=self.app.authority;token=self.app.token
        auth.authorize_graph_read(token,list(dict.fromkeys([source['graphFile'],*all_graphs])))
        auth.authorize_package(token,{'changes':[{'file':source['graphFile'],'metadata':{'migration':True}}]})
        for relative in dict.fromkeys([*all_plans,*([source['planFile']] if source.get('planFile') else [])]):
            auth.authorize_plan(token,['plan.read']+(['plan.edit'] if relative==source.get('planFile') else []),relative)

    def discover(self):
        return {'graphs':sorted(p.relative_to(self.graph_root).as_posix() for p in (self.graph_root/'workspaces').glob('**/graph.json') if self.io.portable_container(p,self.graph_root) is None),
                'plans':sorted(p.relative_to(self.plan_root).as_posix() for p in (self.plan_root/'plans').glob('**/plan.json') if self.io.portable_container(p,self.plan_root) is None),
                'journals':sorted(p.relative_to(self.graph_root).as_posix() for p in (self.graph_root/'workspaces/.transactions').glob('*.json'))}

    def capture(self,key,tx=None):
        self.check(self.config is not None and self.owner is not None,'LEGACY_SOURCES_NOT_CONFIGURED')
        source=self.config['owners'].get(key);self.check(isinstance(source,dict),'SOURCE_KEY_UNKNOWN')
        self.check(set(source)<={'graphFile','planFile','role','lensKey','layoutFiles'},'SOURCE_FIELDS')
        self.check(re.fullmatch(r'workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json',source['graphFile']) is not None,'GRAPH_PATH')
        if source.get('planFile'):self.check(self.owner.TARGET.fullmatch(source['planFile']) is not None,'PLAN_PATH')
        discovery=self.discover();self.auth_legacy(source,discovery['graphs'],discovery['plans'])
        artifacts={};readset={};gaps=[];blockers=[];snapshots={};accepted_afters=[];projections=[];evidence={}
        def read(path,external=False):
            path=self.configured_file(path,external)
            self.check(path.is_file(),'SOURCE_FILE_MISSING:'+self.label(path))
            raw=path.read_bytes();readset[str(path)]=hashlib.sha256(raw).hexdigest();return raw
        graph_path=self.io.safe_path(self.graph_root,source['graphFile'])
        self.check(self.io.portable_container(graph_path,self.graph_root) is None,'SOURCE_ALREADY_PACKAGED')
        raw_graph=read(graph_path);graph=json.loads(raw_graph)
        route=self.marker(graph_path)
        if route.exists():
            value=json.loads(route.read_bytes());self.check(tx is not None and value.get('transactionId')==tx and value.get('state')=='switching','OWNER_ALREADY_SWITCHED')
        self.check(graph.get('coreModel')==self.app.kernel.PROFILE,'CORE_PROFILE_REQUIRED_NO_LEGACY_CONVERSION')
        original=copy.deepcopy(graph)
        for field in ('templateOnly','readOnly','exampleOnly','rootSlug','category'):graph.pop(field,None)
        self.app.model.validate_graph_payload(graph,self.app.kernel)
        role=source.get('role','working');self.app.kernel.validate_role(graph,role)
        if role=='lens':self.check(isinstance(source.get('lensKey'),str) and bool(source['lensKey'].strip()),'LENS_KEY_REQUIRED')
        self.check(not graph.get('inheritedHistory') and not graph.get('externalRefs'),'LEGACY_PORTABLE_PAYLOAD_NOT_SUPPORTED')
        for row in self.store.scan():
            if row.get('head',{}).get('identitySpace')==graph['identitySpace']:blockers.append('PACKAGE_IDENTITY_SPACE_ALREADY_EXISTS')
            if role=='lens' and row.get('head',{}).get('lensKey')==source['lensKey']:blockers.append('LENS_KEY_ALREADY_EXISTS')
        source_paths=[graph_path];plan_store=None
        if source.get('planFile'):
            plan_path=self.io.safe_path(self.plan_root,source['planFile'])
            self.check(self.io.portable_container(plan_path,self.plan_root) is None,'SOURCE_ALREADY_PACKAGED')
            raw_plan=read(plan_path)
            plan_store=self.owner.validate_store(json.loads(raw_plan),source['planFile']);source_paths.append(plan_path)
            artifacts['legacy/plan-owner.json']=raw_plan
            route=self.marker(plan_path)
            if route.exists():
                value=json.loads(route.read_bytes());self.check(tx is not None and value.get('transactionId')==tx and value.get('state')=='switching','PLAN_ALREADY_SWITCHED')
            self.check(not (self.plan_root/self.owner.JOURNAL).exists(),'PLAN_RECOVERY_REQUIRED')
            self.check(plan_store['owner']['identitySpace']==graph['identitySpace'],'PLAN_IDENTITY_MISMATCH')
            index_path=self.plan_root/self.owner.INDEX
            if index_path.exists():
                index=json.loads(read(index_path));binding={k:v for k,v in index['bindings'].items() if v==plan_store['owner']}
                self.check(bool(binding),'PLAN_BINDING_MISSING')
                projections.append({'kind':'legacyPlanIndexProjection','sourceSHA256':readset[str(index_path)],'bindings':binding})
            for record in plan_store['versions']:
                path=self.owner.availability_path(self.plan_root,source['planFile'],record['revision'])
                if path.exists():
                    raw=read(path);self.owner.availability_receipt(self.plan_root,source['planFile'],record)
                    artifacts['legacy/availability/'+path.name]=raw
                else:gaps.append('PLAN_AVAILABILITY_UNKNOWN:r'+str(record['revision']))
        if role in ('ready','lens') and plan_store is not None:blockers.append('PAPER_HAS_PLAN_OWNER')
        # Refuse to leave another current legacy Plan pointing at an immutable source.
        for relative in discovery['plans']:
            path=self.io.safe_path(self.plan_root,relative);data=json.loads(read(path))
            self.owner.validate_store(data,relative)
            if relative==source.get('planFile'):continue
            if data['owner']['identitySpace']==graph['identitySpace']:
                blockers.append('UNCAPTURED_PLAN_OWNER:'+relative)
            if any((s.get('actionRef') or s.get('requirementRef') or {}).get('graphFile')==source['graphFile'] for s in data['versions'][-1]['plan']['steps']):
                blockers.append('INCOMING_LEGACY_PLAN:'+relative)
        for relative in discovery['graphs']:
            path=self.io.safe_path(self.graph_root,relative);other=json.loads(read(path))
            if relative==source['graphFile']:continue
            if other.get('identitySpace')==graph['identitySpace']:blockers.append('SHARED_LEGACY_IDENTITY_SPACE:'+relative)
            refs=[other.get('expansionOf',{}),*[n.get('projectionOf',{}) for n in other.get('nodes',[])]]
            if any(isinstance(ref,dict) and ref.get('graphFile')==source['graphFile'] for ref in refs):blockers.append('INCOMING_LEGACY_GRAPH:'+relative)
        for relative in discovery['journals']:
            path=self.io.safe_path(self.graph_root,relative,True);raw=read(path);journal=json.loads(raw)
            self.check(journal.get('state')=='completed','GRAPH_RECOVERY_REQUIRED')
            relevant=[copy.deepcopy(r) for r in journal.get('records',[]) if r.get('file')==source['graphFile']]
            if not relevant:continue
            projection={'schemaVersion':1,'kind':'legacyGraphJournalProjection','sourceJournal':relative,
                'originalEnvelopeSHA256':hashlib.sha256(raw).hexdigest(),'transactionId':journal['transactionId'],
                'originalRecordedAt':journal.get('recordedAt'),'records':relevant,
                'recordSHA256':[self.app.model.digest(r) for r in relevant],
                'fullEnvelopeCopied':False,'note':'Owner-specific unchanged record values; original envelope verification is separate.'}
            artifacts['legacy/journals/'+path.name]=self.store.encode(projection)
            for record in relevant:
                if record.get('after'):accepted_afters.append(record['after'])
                for value in (record.get('before'),record.get('after')):
                    if value:snapshots[self.app.model.digest(value)]=value
        snapshots[self.app.model.digest(original)]=original
        self.check(accepted_afters and max(v['revision'] for v in accepted_afters)==original['revision'] and
            any(self.app.model.digest(v)==self.app.model.digest(original) for v in accepted_afters),'CURRENT_GRAPH_NOT_IN_COMPLETED_JOURNAL')
        if role in ('ready','lens'):
            for value in snapshots.values():self.app.kernel.validate_role(value,role)
        self.check(any(p.startswith('legacy/journals/') for p in artifacts),'COMPLETED_OWNER_JOURNAL_REQUIRED')
        for digest,value in snapshots.items():artifacts['legacy/graphs/'+digest+'/graph.json']=self.app.model.encoded(value)
        artifacts['legacy/current-graph.json']=raw_graph
        for value in snapshots.values():
            for event in value.get('events',[]):
                for ref in event.get('evidenceRefs',[]):
                    path=ref.get('path');sha=ref.get('sha256')
                    if not isinstance(path,str) or not isinstance(sha,str):blockers.append('UNSUPPORTED_EVIDENCE_REF');continue
                    try:
                        full=self.io.safe_path(self.root,path);raw=read(full)
                        self.check(hashlib.sha256(raw).hexdigest()==sha,'EVIDENCE_HASH_MISMATCH')
                        artifacts['evidence/'+sha]=raw;evidence[path]={'path':'evidence/'+sha,'sha256':sha}
                    except (ValueError,OSError):gaps.append('EVIDENCE_UNAVAILABLE:'+path)
        registries=list(self.config.get('registryFiles',[]))
        if (self.graph_root/'index.json').is_file():registries.append(str(self.graph_root/'index.json'))
        source_slugs={graph['id']}
        for configured in dict.fromkeys(registries):
            path=self.configured_path(configured);value=json.loads(read(path))
            entries=value.get('graphs',value.get('entries',[]))
            selected=[r for r in entries if isinstance(r,dict) and r.get('file')==source['graphFile']] if isinstance(entries,list) else []
            for row in selected:
                if isinstance(row.get('slug'),str):source_slugs.add(row['slug'])
            projections.append({'kind':'legacyRegistryProjection','sourceFile':str(path.relative_to(self.root)),
                'originalEnvelopeSHA256':readset[str(path)],'entries':selected,'fullEnvelopeCopied':False})
        layouts=None
        configured_layouts=list(source.get('layoutFiles',[]))
        if (self.graph_root/'layouts.json').is_file():configured_layouts.append(str(self.graph_root/'layouts.json'))
        for configured in dict.fromkeys(configured_layouts):
            path=self.configured_file(configured,True);document=json.loads(read(path,True));self.app.layout('validate',document=document)
            owned={key:layout for key,layout in document['layouts'].items() if json.loads(key)[0]==graph['identitySpace']}
            projection={**document,'layouts':owned}
            projections.append({'kind':'legacyLayoutProjection','sourceFile':self.label(path),
                'originalEnvelopeSHA256':readset[str(path)],'document':projection,'fullEnvelopeCopied':False})
            views={slug:graph['id'] for slug in source_slugs};views.update({'full-'+w['id']:'full-'+w['id'] for w in graph['workGraphs']})
            remapped=self.app.layout('remap',document=projection,spec={'sourceSpace':graph['identitySpace'],'targetSpace':graph['identitySpace'],
                'viewMap':views,'entityMap':{i:i for i in self.app.kernel.entities(graph)},'sourceIds':list(self.app.kernel.entities(graph)),'sourceSlugs':sorted(source_slugs)})
            if layouts is None:layouts=remapped['document']
            else:
                self.check(not set(layouts['layouts'])&set(remapped['document']['layouts']),'AMBIGUOUS_LAYOUT_SOURCES')
                layouts['layouts'].update(remapped['document']['layouts'])
        if self.config.get('configFile'):read(self.configured_file(self.config['configFile'],True),True)
        artifacts['legacy/projections.json']=self.store.encode(projections)
        normalized={'sourceKey':key,'graphSHA256':readset[str(graph_path)],'sourceFiles':readset,'discovery':discovery,
            'configSHA256':self.app.model.digest(self.config)}
        return {'source':source,'graph':graph,'role':role,'planStore':plan_store,'layouts':layouts,'sourcePaths':source_paths,
            'readset':readset,'discovery':discovery,'artifacts':artifacts,'evidenceMap':evidence,'sourcePin':self.app.model.digest(normalized),
            'blockers':sorted(set(blockers)),'evidenceGaps':sorted(set(gaps)),
            'allGraphs':discovery['graphs'],'allPlans':discovery['plans'],'snapshots':snapshots}

    def convert_plan(self,owner,package_id,graph):
        if owner is None:return None
        old=owner['versions'][-1]['plan']
        self.check(not any(old.get(k) for k in ('modules','moduleData','disabledModules')),'PLAN_MODULES_UNSUPPORTED')
        self.check(not old['branches'] and all(s['kind'] in ('action','requirement') and s['state']=='planned' for s in old['steps']),'PLAN_ONLY_EVENT_GATE_OR_BRANCH_UNSUPPORTED')
        result={k:copy.deepcopy(old[k]) for k in ('kind','id','title','identitySpace','status','sequence','branches','timeConstraints')}
        result.update(schemaVersion=2,revision=old['revision']+1,steps=[])
        for step in old['steps']:
            ref=step.get('actionRef') or step.get('requirementRef')
            self.check(ref['graphFile']==owner['sourceGraphFile'] and ref['identitySpace']==graph['identitySpace'],'UNMIGRATED_PLAN_TARGET')
            node=self.app.kernel.entities(graph).get(ref['nodeId'])
            self.check(node and node['kind']==step['kind'],'PLAN_CURRENT_ENDPOINT_MISSING')
            result['steps'].append({k:copy.deepcopy(step[k]) for k in ('id','title','kind','state')})
            result['steps'][-1]['ref']=self.app.model.reference(package_id,graph,node['id'])
        self.app.model.validate_plan(result);return result

    def inspect(self,key):
        with self.store.lock(False,create=False):
            value=self.capture(key)
            try:
                owner=copy.deepcopy(value['planStore'])
                if owner:owner['sourceGraphFile']=value['source']['graphFile']
                self.convert_plan(owner,str(uuid.uuid5(uuid.NAMESPACE_URL,'migration-preflight:'+key)),value['graph'])
            except (ValueError,KeyError) as exc:value['blockers'].append(str(exc))
            return {'sourceKey':key,'sourcePin':value['sourcePin'],'ready':not value['blockers'],
                'requiresHistoricalGapAcknowledgement':bool(value['evidenceGaps']),
                'blockers':value['blockers'],'evidenceGaps':value['evidenceGaps'],'files':len(value['artifacts']),
                'sourceGraphRevision':value['graph']['revision'],'sourcePlanRevision':value['planStore']['revision'] if value['planStore'] else None}

    def input_binding(self,request,value,check,ident):
        """Bind the configured legacy source and destination catalog."""
        actor,_=self.app.authority._actor(self.app.authority._read(),self.app.token)
        binding={'schemaVersion':1,'policy':'legacy-source-read-set-v1',
                 'namespaceId':self.store.namespace_id,'actorGrantId':actor,
                 'requestSHA256':self.app.model.digest(request),
                 'sourceKey':request['sourceKey'],'sourcePin':value['sourcePin'],
                 'sourceReadSetSHA256':self.app.model.digest(value['readset']),
                 'discovery':copy.deepcopy(value['discovery']),
                 'catalog':self.store.catalog_signature(ignore_ids={ident}),
                 'requiredPermissions':[copy.deepcopy(check)],
                 'effectPackageIds':[ident]}
        return {**binding,'sha256':self.app.model.digest(binding)}

    def handle(self,request,*,preflight=False,failpoint=None,before_accept=None,
               expected_input_binding=None):
        self.check({'op','transactionId','sourceKey','sourcePin','path','confirmOwnerSwitch','legacyWritersQuiesced','presentationSourcesComplete','presentationWritersPaused'}<=set(request)<=
                   {'op','transactionId','sourceKey','sourcePin','path','confirmOwnerSwitch','legacyWritersQuiesced','presentationSourcesComplete','presentationWritersPaused','acknowledgeHistoricalGaps'},'REQUEST_FIELDS')
        self.check(request['confirmOwnerSwitch'] is True and request['legacyWritersQuiesced'] is True and request['presentationSourcesComplete'] is True and request['presentationWritersPaused'] is True,
                   'EXPLICIT_SWITCH_AND_PRESENTATION_CONFIRMATION_REQUIRED')
        tx=request['transactionId'];request_sha=self.app.model.digest(request);actor_sha=hashlib.sha256(self.app.token.encode()).hexdigest()
        prior=None
        if self.journal(tx).is_file():
            prior=json.loads(self.journal(tx).read_bytes())
            self.check(prior['requestSHA256']==request_sha and prior['actorTokenSHA256']==actor_sha,'EXACT_ACTOR_AND_REQUEST_REQUIRED')
            self.check(prior['state']!='cancelled','TRANSACTION_CANCELLED')
        if not preflight and self.journal(tx).is_file():
            if self.store.metadata_path('accepted',tx).is_file():
                with self.store.lock(True):return self.resume(prior,request_sha,actor_sha)
        self.app.authority._actor(self.app.authority._read(),self.app.token)
        with self.store.lock(not preflight,create=not preflight):
            value=self.capture(request['sourceKey'],tx);self.check(value['sourcePin']==request['sourcePin'],'SOURCE_CAPTURE_CHANGED')
            self.check(not value['blockers'] and (not value['evidenceGaps'] or request.get('acknowledgeHistoricalGaps') is True),
                       'PREFLIGHT_BLOCKED:'+','.join(value['blockers']+value['evidenceGaps']))
            ident=str(uuid.uuid5(uuid.UUID(tx),'package'));graph=value['graph']
            owner=copy.deepcopy(value['planStore'])
            if owner:owner['sourceGraphFile']=value['source']['graphFile']
            plan=self.convert_plan(owner,ident,graph)
            permissions=['package.create','graph.write']+(['plan.create'] if plan is not None else [])
            check={'namespaceId':self.store.namespace_id,'packageId':ident,'permissions':permissions,'path':request['path']}
            self.app.authorize(ident,permissions,request['path']);self.store.validate_destination(request['path'])
            prefix='provenance/legacy-'+value['sourcePin'];artifacts={prefix+'/'+p:raw for p,raw in value['artifacts'].items()}
            for relative,raw in value['artifacts'].items():
                if relative.startswith('evidence/'):artifacts[relative]=raw
            created_at=prior['createdAt'] if prior else datetime.now(timezone.utc).isoformat()
            witness={'schemaVersion':1,'kind':'legacyOwnerMigrationWitness','sourceKey':request['sourceKey'],'sourcePin':value['sourcePin'],
                'packageId':ident,'namespaceId':self.store.namespace_id,'identitySpace':graph['identitySpace'],'graphId':graph['id'],'entityIdsPreserved':True,
                'sourceGraphFile':value['source']['graphFile'],'sourcePlanFile':value['source'].get('planFile'),
                'sourceGraphRevision':graph['revision'],'sourcePlanRevision':owner['revision'] if owner else None,
                'evidenceMap':value['evidenceMap'],'originalFactsRewritten':False,'originalEnvelopeCopied':False,
                'presentationWriterExclusion':'operator-confirmed','graphPlanWriterExclusion':'shared-reference-barrier + operator-confirmed legacy writer quiescence',
                'evidenceGaps':value['evidenceGaps'],'createdAt':created_at}
            artifacts[prefix+'/migration-witness.json']=self.store.encode(witness)
            changes={ident:{'path':request['path'],'role':value['role'],'graph':graph,'permissions':permissions,'artifacts':artifacts,
                'lineage':{'kind':'migration','sourceKey':request['sourceKey'],'snapshotPrefix':prefix,'sourcePin':value['sourcePin']},
                'effects':{'operation':'migrate','createdPackageId':ident,'sourceKey':request['sourceKey'],'sourcePin':value['sourcePin']}}}
            if plan is not None:changes[ident]['plan']=plan
            if value['layouts'] is not None:changes[ident]['layouts']=value['layouts']
            if value['role']=='lens':changes[ident]['lensKey']=value['source']['lensKey']
            effects={'operation':'migrate','createdPackageId':ident,'sourceGraphRevision':graph['revision'],
                'sourcePlanRevision':owner['revision'] if owner else None,'newPlanRevision':plan['revision'] if plan else None,
                'identitySpace':graph['identitySpace'],'retainedFacts':len(graph['events']),'artifacts':len(artifacts),'evidenceGaps':value['evidenceGaps']}
            binding=self.input_binding(request,value,check,ident)
            if expected_input_binding is not None:self.check(expected_input_binding==binding,'PREVIEW_INPUTS_CHANGED')
            if preflight:return {'preflight':True,'accepted':False,'effects':effects,
                                 'requiredPermissions':[check],'inputBinding':binding}
            self.store.initialize();self.store.check_intent(tx,request_sha,actor_sha)
            routes=[{'path':str(self.marker(path)),'ownerPath':str(path)} for path in value['sourcePaths']]
            record={'schemaVersion':1,'kind':'legacyOwnerMigration','transactionId':tx,'requestSHA256':request_sha,'actorTokenSHA256':actor_sha,
                'packageId':ident,'namespaceId':self.store.namespace_id,'routes':routes,'sourcePin':value['sourcePin'],'state':'staged'}
            record['createdAt']=created_at
            self.io.atomic_bytes(self.journal(tx),self.store.encode(record))
            if before_accept:before_accept()
            def authorize():
                self.app.authorize(ident,permissions,request['path']);self.auth_legacy(value['source'],value['allGraphs'],value['allPlans'])
            @contextmanager
            def final():
                with self.app.authority.checked_portable_transaction(self.app.token,[check]) as verified:
                    self.auth_legacy(value['source'],value['allGraphs'],value['allPlans'])
                    self.check(self.discover()==value['discovery'],'SOURCE_INVENTORY_CHANGED')
                    for path,sha in value['readset'].items():self.check(self.raw_sha(Path(path))==sha,'SOURCE_FILE_CHANGED:'+self.label(Path(path)))
                    try:
                        for route in routes:
                            marker={'schemaVersion':1,'kind':'legacyOwnerRoute','transactionId':tx,'requestSHA256':request_sha,
                                'packageId':ident,'namespaceId':self.store.namespace_id,'state':'switching'}
                            self.io.immutable_bytes(Path(route['path']),self.store.encode(marker))
                        yield verified
                    except Exception:
                        if not self.store.metadata_path('accepted',tx).is_file():
                            for route in routes:
                                path=self.configured_path(route['path'])
                                if not path.is_file():continue
                                current=json.loads(path.read_bytes())
                                if current.get('transactionId')==tx:path.unlink();self.io.sync_dir(path.parent)
                        raise
            result=self.store.commit(tx,request_sha,changes,actor_sha,authorize,final,{},failpoint,
                expected_catalog=self.store.catalog_signature(ignore_ids={ident}))
            return self.finish(record,result)

    def finish(self,record,result):
        for route in record['routes']:
            path=self.configured_path(route['path']);self.check(path.parent.is_dir(),'SOURCE_ROUTE_PARENT_MISSING')
            current=json.loads(path.read_bytes());self.check(current['transactionId']==record['transactionId'],'SOURCE_ROUTE_CONFLICT')
            current['state']='committed';self.io.atomic_bytes(path,self.store.encode(current))
        record['state']='completed';record['result']=result;self.io.atomic_bytes(self.journal(record['transactionId']),self.store.encode(record))
        return result

    def resume(self,record,request_sha,actor_sha):
        self.check(record['requestSHA256']==request_sha and record['actorTokenSHA256']==actor_sha,'EXACT_ACTOR_AND_REQUEST_REQUIRED')
        result=self.store.replay(record['transactionId'],request_sha,actor_sha)
        return result if record['state']=='completed' else self.finish(record,result)

    def cancel(self,transaction_id):
        """Release only this actor's unaccepted legacy route; retain every staged byte."""
        self.check(isinstance(transaction_id,str),'TRANSACTION_ID')
        self.check(str(uuid.UUID(transaction_id))==transaction_id,'TRANSACTION_ID')
        actor=hashlib.sha256(self.app.token.encode()).hexdigest()
        with self.store.lock(True,create=False):
            self.check(self.store.initialized(),'NAMESPACE_NOT_INITIALIZED')
            path=self.journal(transaction_id);self.check(path.is_file(),'TRANSACTION_NOT_FOUND')
            record=json.loads(path.read_bytes())
            self.check(record.get('kind')=='legacyOwnerMigration' and record.get('transactionId')==transaction_id
                and record.get('namespaceId')==self.store.namespace_id and record.get('state') in ('staged','cancelled')
                and record.get('packageId')==str(uuid.uuid5(uuid.UUID(transaction_id),'package')),'MIGRATION_JOURNAL_INVALID')
            self.check(record['actorTokenSHA256']==actor,'EXACT_ACTOR_AND_REQUEST_REQUIRED')
            intent=self.store.metadata_path('intents',transaction_id)
            self.check(intent.is_file(),'MIGRATION_INTENT_MISSING')
            self.check(json.loads(intent.read_bytes())=={'transactionId':transaction_id,
                'requestSHA256':record['requestSHA256'],'actorTokenSHA256':actor},'MIGRATION_INTENT_CONFLICT')
            self.check(not self.store.metadata_path('accepted',transaction_id).exists() and
                not self.store.metadata_path('completed',transaction_id).exists(),'ACCEPTED_SWITCH_REQUIRES_FORWARD_RECOVERY')
            staged=self.store.metadata_path('staged',transaction_id)
            payload=json.loads(staged.read_bytes()) if staged.is_file() else None
            if payload is not None:
                self.check(payload.get('transactionId')==transaction_id and payload.get('requestSHA256')==record['requestSHA256']
                    and len(payload.get('entries',[]))==1 and payload['entries'][0]['packageId']==record['packageId'],
                    'MIGRATION_STAGED_CONFLICT')
            found=False
            for row in self.store.scan():
                self.check(row['health'] not in ('invalid','incomplete'),
                    'UNIDENTIFIED_PACKAGE_CANNOT_CANCEL')
                if row.get('packageId')!=record['packageId']:continue
                found=True;directory=self.store.package_path(row['path'])
                self.check(row['health']=='unaccepted-stage' and not row.get('head'),'PUBLISHED_STAGE_CANNOT_CANCEL')
                marker=json.loads(self.io.safe_path(directory,'.rdg/package.json',True).read_bytes())
                self.check(marker=={'schemaVersion':1,'kind':'rdgPackageIdentity',
                    'packageId':record['packageId'],'creationTransactionId':transaction_id},'STAGED_OWNER_CONFLICT')
                if payload is not None:self.check(payload['entries'][0]['path']==row['path'],'MIGRATION_STAGED_CONFLICT')
                self.check(not any(self.io.safe_path(directory,'.rdg/'+kind+'/'+transaction_id+'.json',True).exists()
                    for kind in ('acceptances','commits','completed')),'PUBLISHED_STAGE_CANNOT_CANCEL')
            self.check(found,'MIGRATION_STAGE_MISSING')
            self.check(isinstance(record.get('routes'),list) and bool(record['routes']),'MIGRATION_ROUTES_INVALID')
            markers=[];seen=set()
            for route in record['routes']:
                marker=self.configured_path(route['path'])
                owner=self.configured_path(route['ownerPath'])
                self.check(marker==self.marker(owner) and marker not in seen,'MIGRATION_ROUTES_INVALID')
                seen.add(marker)
                if not marker.exists():continue
                self.check(marker.is_file() and not marker.is_symlink(),'SOURCE_ROUTE_CONFLICT')
                value=json.loads(marker.read_bytes())
                self.check(value=={'schemaVersion':1,'kind':'legacyOwnerRoute','transactionId':transaction_id,
                    'requestSHA256':record['requestSHA256'],'packageId':record['packageId'],
                    'namespaceId':self.store.namespace_id,'state':'switching'} and record['state']=='staged',
                    'SOURCE_ROUTE_CONFLICT')
                markers.append(marker)
            for marker in markers:marker.unlink();self.io.sync_dir(marker.parent)
            if record['state']!='cancelled':
                record['state']='cancelled';self.io.atomic_bytes(path,self.store.encode(record))
            return {'cancelled':True,'accepted':False,'transactionId':transaction_id,
                    'sourceFactsRewritten':False,'stagedBytesRetained':True}

    def historical_records(self,row,records,inventory):
        """Read owned migration evidence after copy/move, without a legacy path."""
        directory=self.store.package_path(row['path']);events={};plans=[];graphs=[];gaps=[];seen=set()
        def read(relative):
            raw=self.io.safe_path(directory,relative,True).read_bytes()
            self.check(inventory.get(relative)==hashlib.sha256(raw).hexdigest(),'HISTORY_ARTIFACT_HASH')
            return json.loads(raw)
        for record in records:
            lineage=record['head'].get('lineage',{})
            if lineage.get('kind')!='migration':continue
            prefix=record['prefix']+lineage['snapshotPrefix']+'/'
            if prefix in seen:continue
            seen.add(prefix);witness=read(prefix+'migration-witness.json');gaps.extend(witness['evidenceGaps'])
            plan_path=prefix+'legacy/plan-owner.json'
            if plan_path in inventory:
                owner=read(plan_path)
                for version in owner['versions']:
                    plans.append({'plan':version['plan'],'sha256':self.app.model.digest(version['plan']),
                        'recordDigest':version['digest'],'acceptedAt':version['recordedAt'],'inherited':record['inherited'],
                        'legacy':True,'sourceArtifact':plan_path,'sourcePackageId':record['head']['packageId'],
                        'current':False,'sourceCodec':'temporalPlanOwner/v1','validatedDuringMigration':True})
            for relative in inventory:
                if relative.startswith(prefix+'legacy/graphs/') and relative.endswith('/graph.json'):
                    graph=read(relative);graphs.append({'graph':graph,'sha256':self.app.model.digest(graph),'sourceArtifact':relative,
                        'sourcePackageId':record['head']['packageId'],'inherited':record['inherited'],'legacy':True})
                if not relative.startswith(prefix+'legacy/journals/'):continue
                projection=read(relative)
                self.check(projection['recordSHA256']==[self.app.model.digest(r) for r in projection['records']],'HISTORY_RECORD_HASH')
                for value in projection['records']:
                    after=value['after'];previous={e['id'] for e in (value.get('before') or {}).get('events',[])}
                    for event in after.get('events',[]):
                        if event['id'] in previous:continue
                        events[(after['identitySpace'],event['id'])]={'source':{'packageId':record['head']['packageId'],
                            'identitySpace':after['identitySpace'],'graphRevision':after['revision'],'sha256':self.app.model.digest(after)},
                            'acceptedAt':projection['originalRecordedAt'],'transactionId':projection['transactionId'],
                            'snapshotKind':'legacy-after-record-projection','fullEnvelopeCopied':False,'sourceArtifact':relative}
        return {'events':events,'planVersions':plans,'graphSnapshots':graphs,'evidenceGaps':sorted(set(gaps))}
