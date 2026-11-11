#!/usr/bin/env python3
"""Common application service. Transports supply intents, never their own writers."""
import base64
import copy
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path
import uuid
from zoneinfo import ZoneInfo


COMPACT = SourceFileLoader('rdg_compact_read', str(Path(__file__).with_name('rdg-compact-read.py'))).load_module()
SCOPED = COMPACT.SCOPED
MARKDOWN = SourceFileLoader('rdg_structured_markdown', str(Path(__file__).with_name('rdg-structured-markdown.py'))).load_module()
SEARCH = SourceFileLoader('rdg_text_search', str(Path(__file__).with_name('rdg-text-search.py'))).load_module()
BATCH = SourceFileLoader('rdg_batch', str(Path(__file__).with_name('rdg-batch.py'))).load_module()
CACHE = SourceFileLoader('rdg_projection_cache', str(Path(__file__).with_name('rdg-projection-cache.py'))).load_module()


class Application:
    def __init__(self, store, authority, kernel, model, token, layout_port=None, command_port=None, attribution='assistant'):
        self.store, self.authority, self.kernel, self.model, self.token = store, authority, kernel, model, token
        self.layout_port=layout_port;self.command_port=command_port;self.view_sessions={}
        # Volatile, bounded per-Application projections; never authority or file facts.
        self._visual_cache=CACHE.ProjectionCache(max_bytes=8*1024*1024)
        self._history_cache=CACHE.ProjectionCache(max_bytes=12*1024*1024)
        self._scoped_cache=CACHE.ProjectionCache(max_entries=4,max_bytes=48*1024*1024)
        self.check(attribution in ('assistant','user'),'ATTRIBUTION');self.attribution=attribution
        self.check(not authority.path.resolve().is_relative_to(store.root.resolve()), 'AUTHORITY_OUTSIDE_PACKAGES_REQUIRED')

    @staticmethod
    def check(ok, code):
        if not ok:raise ValueError('PORTABLE_APP_' + code)

    def authorize(self, ident, permissions, path=None):
        return self.authority.authorize_portable(self.token, permissions, self.store.namespace_id, ident, path)

    def metadata(self, ident, permissions):
        row = self.store.locate(ident)
        self.authorize(ident, permissions, row['path'])
        return row

    def decision_effects(self, before, after):
        before_entities = self.kernel.entities(before); after_entities = self.kernel.entities(after)
        before_ids, after_ids = set(before_entities), set(after_entities)
        added = after_ids - before_ids; removed = before_ids - after_ids
        changed = {i for i in before_ids & after_ids if before_entities[i] != after_entities[i]}
        before_edges = {e['id']: e for e in before.get('edges', [])}
        after_edges = {e['id']: e for e in after.get('edges', [])}
        relation_ids = {i for i in set(before_edges) | set(after_edges)
                        if before_edges.get(i) != after_edges.get(i)}
        before_groups = {g['id']: g for g in before.get('decisionGroups', [])}
        after_groups = {g['id']: g for g in after.get('decisionGroups', [])}
        group_ids = {i for i in set(before_groups) | set(after_groups)
                     if before_groups.get(i) != after_groups.get(i)}
        before_causes = {c['id']: c for c in before.get('rootCauses', [])}
        after_causes = {c['id']: c for c in after.get('rootCauses', [])}
        cause_ids = {i for i in set(before_causes) | set(after_causes)
                     if before_causes.get(i) != after_causes.get(i)}
        before_active = set(self.kernel.support_state(before)['activeIds'])
        after_active = set(self.kernel.support_state(after)['activeIds'])
        selection_changes = []
        for ident in sorted(before_ids & after_ids):
            old, new = before_entities[ident], after_entities[ident]
            if old.get('kind') == 'decision' and old.get('selectionState') != new.get('selectionState'):
                selection_changes.append({'decisionId': ident, 'before': old.get('selectionState'),
                                          'after': new.get('selectionState')})
        review_reasons = {ident: copy.deepcopy(node.get('review', {}).get('causeEventIds', []))
                          for ident, node in after_entities.items()
                          if node.get('review', {}).get('required')}
        old_events = {e['id'] for e in before.get('events', [])}
        new_events = [e for e in after.get('events', []) if e['id'] not in old_events]
        basis_before=self.kernel.support_state(before)['basisById']
        basis_after=self.kernel.support_state(after)['basisById']
        basis_changed=[{'nodeId':i,'before':basis_before.get(i,[]),'after':basis_after.get(i,[])}
                       for i in sorted(set(basis_before)|set(basis_after))
                       if basis_before.get(i,[])!=basis_after.get(i,[])]
        dependency_hits=[copy.deepcopy(hit) for ev in new_events for hit in ev.get('dependencyImpacts',[])]
        return {'profile': 'rdg-decision-v1',
            'basisChanges':basis_changed,'dependencyImpacts':dependency_hits,
            'questionLinks':[{'questionId':i,'removed':i in removed,'relatedRefs':copy.deepcopy((after_entities.get(i) or before_entities[i])['relatedRefs'])} for i in sorted(added|removed|changed) if (after_entities.get(i) or before_entities.get(i,{})).get('kind')=='question'],
            'changedIds': sorted(added | removed | changed), 'addedIds': sorted(added),
            'removedIds': sorted(removed), 'relationIds': sorted(relation_ids),
            'decisionGroupIds': sorted(group_ids), 'rootCauseIds': sorted(cause_ids),
            'supportLostIds': sorted(before_active - after_active),
            'supportGainedIds': sorted(after_active - before_active),
            'selectionChanges': selection_changes, 'reviewRequiredIds': sorted(review_reasons),
            'reviewReasons': review_reasons, 'eventIds': [e['id'] for e in new_events],
            'eventTypes': [e['type'] for e in new_events],
            'lockWarnings': [copy.deepcopy(w) for e in new_events for w in e.get('lockWarnings', [])],
            'actionResults': [copy.deepcopy(e['actionResult']) for e in new_events if 'actionResult' in e]}

    def authoring_commands(self,graph,role=None):
        commands=self.kernel.commands_for(graph)-{'remove','recommendation_packages','lens_application'}
        if role in ('ready','lens'):
            commands=commands & ({'add','edit','link','unlink','decision_group','root_cause','work_graph'}
                if graph['coreModel']=='rdg-decision-v1' else
                {'add','edit','link','unlink','work_graph','include','join','exclusion_group','lens_recommendations','output_origin'})
        return commands

    def profile_capabilities(self, graph, role=None):
        profile = graph.get('coreModel')
        commands = sorted(self.authoring_commands(graph,role))
        if profile == 'rdg-decision-v1':
            return {'profile': profile, 'coreCommands': commands,'entityKinds':['requirement','decision','action','canon','context','info','question']+([] if role in ('ready','lens') else ['finding']),'historyModes':list(self.kernel.for_graph(graph).HISTORY.MODES),
                    'planFeatures':['order','fork-start','fork-end','marker-date-time'],
                'capabilities': {'create': True, 'read': True, 'schema': True,
                    'preflight': True, 'apply': True, 'receipt': True, 'focus': True,
                    'groups': True, 'rootCauses': True, 'externalActions': True,
                    'copy': True, 'templateApply': True, 'plan': True,
                    'planOrderOnly': True, 'planForks': True, 'layoutWrite': True, 'layoutOccurrences': True,
                    'recommendations': True, 'externalReferences': True, 'viewSessions': True, 'compactRead': True, 'atomicBatch': True, 'questionApiSlice': True, 'questionEditing':True, 'questionMigration':True, 'questionCopy':True, 'actionEstimates':True, 'decisionTheory':True, 'recommendationAuthoring':True, 'planningMetaAction':role in ('working','copy'), 'crossOwnerRefs': False},
                'batch': BATCH.schema(),
                'unsupportedCapabilities': ['crossOwnerRefs']}
        return {'profile': profile, 'coreCommands': commands,
                'capabilities': {'read': True, 'schema': True, 'preflight': True, 'apply': True, 'receipt': True}}

    def snapshot(self, ident, plan=False, layouts=True, *, scoped_read=False):
        def authorize_loaded_head(metadata):
            self.authorize(ident,['graph.read'],metadata['path'])
            if plan and 'plan' in metadata['head']['current']:
                self.authorize(ident,['plan.read'],metadata['path'])
        value = self.store.read(ident, include_plan=plan, include_layouts=layouts,
                                on_located=authorize_loaded_head)
        graph = value['graph']
        if scoped_read and graph.get('coreModel') == 'rdg-decision-v1':
            # Validate every rule. Only repeated entity indexing is memoized.
            K = self.kernel.for_graph(graph)
            with K.ANALYSIS.read_scope(graph) as cache:
                cache['scopedImmutableEntityMode'] = True
                return self._checked_snapshot(value)
        return self._checked_snapshot(value)

    def _checked_snapshot(self, value):
        self.model.validate_graph_payload(value['graph'],self.kernel)
        if value['graph'].get('coreModel') == 'rdg-decision-v1':
            # This exact Graph was fully validated one line above. Check the
            # role constraints without validating the same payload twice.
            self.kernel.for_graph(value['graph'])._validate_role_on_validated_graph(
                value['graph'], value['head']['role'], value['plan'])
        else:
            self.kernel.validate_role(value['graph'], value['head']['role'], value['plan'])
        if value['plan'] is not None:
            self.model.validate_plan(value['plan'])
            self.check(value['plan']['schemaVersion']==(3 if value['graph']['coreModel']=='rdg-decision-v1' else 2), 'PLAN_PROFILE_VERSION')
        return value

    def catalog(self):
        with self.store.lock(False,create=False):return self._catalog_locked()

    def _lens_catalog_card(self, value):
        """Project owned Info from this exact visible definition; never a key lookup."""
        graph, head = value['graph'], value['head']
        source = {'packageId':head['packageId'], 'identitySpace':graph['identitySpace'],
                  'packageRevision':head['revision'], 'graphRevision':graph['revision'],
                  'graphSHA256':self.model.digest(graph)}
        infos = [n for n in self.kernel.entities(graph).values() if n['kind']=='info']
        cards = [n for n in infos if 'rdg:lens-catalog' in n.get('tags',[])]
        contexts = [n for n in infos if 'rdg:lens-workflow' in n.get('tags',[])]
        result = {'status':'missing', 'purpose':None, 'appliesWhen':None,
                  'workflow':None, 'source':source}
        if not cards:return result
        if len(cards)!=1 or len(contexts)>1 or not cards[0]['description'].strip() or (contexts and (contexts[0]['id']==cards[0]['id'] or not contexts[0]['description'].strip())):
            result['status']='invalid'
            return result
        card=cards[0]
        result.update(status='available',purpose=card['description'],appliesWhen=card['value'],
                      sourceRef=self.model.reference(head['packageId'],graph,card['id']))
        if contexts:
            context=contexts[0]
            result['workflow']={'text':context['value'],'explanation':context['description'],
                'sourceRef':self.model.reference(head['packageId'],graph,context['id'])}
        return result

    def _catalog_locked(self):
        """Read the catalog while the caller holds the namespace barrier."""
        rows=[]
        for row in self.store.scan():
            try:self.authorize(row.get('packageId'), ['graph.read'], row['path'])
            except ValueError:continue
            result={k:row[k] for k in ('path','packageId','health')}
            if row.get('head'):result.update({k:row['head'].get(k) for k in ('role','identitySpace','revision','lensKey')})
            if row.get('head',{}).get('role')=='lens':
                result['lensCard']={'status':'unavailable','purpose':None,'appliesWhen':None,'workflow':None,'source':None}
            try:
                if row['health']=='metadata-verified':
                    value=self.store.read(row['packageId'],include_plan=False,include_layouts=False)
                    self.kernel.validate_role(value['graph'],value['head']['role'])
                    if value['head']['role']=='lens':result['lensCard']=self._lens_catalog_card(value)
                    result.update(title=value['graph']['title'],coreModel=value['graph']['coreModel'],recommendationPackageIds=value['graph'].get('recommendationPackageIds',[]),workGraphs=value['graph'].get('workGraphs',[]),detached=self.kernel.detached_components(value['graph']))
            except (ValueError,OSError) as exc:result.update(health='unhealthy',error=str(exc))
            rows.append(result)
        visible={str(Path(r['path']).parent) for r in rows}
        folders=[]
        for relative in self.store.folders():
            try:self.authorize(None,['folder.write'],relative);manageable=True
            except ValueError:manageable=False
            if manageable or any(p==relative or p.startswith(relative+'/') for p in visible):folders.append({'path':relative,'manageable':manageable})
        result={'schemaVersion':1,'namespaceId':self.store.namespace_id,'packages':rows,'folders':folders,'locationSource':'filesystem','complete':True}
        result['catalogSHA256']=self.model.digest(result)
        return result

    def dependencies(self, ident):
        row = self.snapshot(ident, layouts=False)
        edges = self.kernel.native_dependency_edges(row['graph'])
        sources = sorted({e['from'] for e in edges})
        return {'schemaVersion': 1, 'packageId': ident,
                'graphRevision': row['graph']['revision'],
                'graphSHA256': self.model.digest(row['graph']),
                'edges': copy.deepcopy(edges),
                'projections': {edge['id']: self.kernel.semantic_projection(
                                  row['graph'], edge['from'],
                                  edge.get('dependencyRule', edge.get('dependencyLevel','L1')))
                                for edge in edges}}

    def locks(self, ident):
        row = self.snapshot(ident, layouts=False)
        return {'schemaVersion': 1, 'packageId': ident,
                'graphRevision': row['graph']['revision'],
                'graphSHA256': self.model.digest(row['graph']),
                'locks': {node['id']: copy.deepcopy(node.get('locks', {}))
                          for node in self.kernel.entities(row['graph']).values()
                          if node.get('locks')}}

    OPERATIONS=('create','apply_ready','copy','insert_copy','delete','unlink','core','paper_edit','batch','plan_action',
                'dependency_add','dependency_remove','lock_set','lock_remove',
                'place','unplace','plan_create','plan_edit','external_edit','layout_edit','attach_evidence','move','folder_create','folder_move','migrate','recommendation_edit','recommendation_attach','lens_apply','capture_ready','lens_manage')

    def view_session(self,message):
        actor,_=self.authority._actor(self.authority._read(),self.token)
        action=message.get('action','read');sid=message.get('sessionId')
        self.check(action in ('read','create','update','close'),'VIEW_SESSION_ACTION')
        if sid is None:
            self.check(action=='read','VIEW_SESSION_ID')
            return {'sessions':[{'id':s['id'],'revision':s['revision'],'activeScreenId':s['activeScreenId']} for s in self.view_sessions.values() if s['actor']==actor]}
        self.check(isinstance(sid,str) and str(uuid.UUID(sid))==sid,'VIEW_SESSION_ID')
        old=self.view_sessions.get(sid)
        if action=='create':
            self.check(old is None,'VIEW_SESSION_EXISTS');ident=message.get('packageId');screen=None
            if ident is not None:
                self.metadata(ident,['graph.read'])
                screen={'id':str(uuid.uuid5(uuid.UUID(sid),'first-screen')),'packageId':ident,'spec':message.get('view',{'kind':'graph'}),
                    'panels':{'roadVisible':True,'roadTab':'timeline','roadWidth':420,'inspectorWidth':340,'historyScroll':0,'planScroll':0},'draft':None,'trail':[],'inspector':None}
                self.model.validate_view_spec(screen['spec'])
            else:self.check('view' not in message,'VIEW_SESSION_PACKAGE_REQUIRED')
            old={'id':sid,'actor':actor,'revision':1,'activeScreenId':screen['id'] if screen else None,'screens':[screen] if screen else [],'explorer':{'open':screen is None,'tab':'graphs','query':'','scroll':0,'selectedPackageId':None,'drafts':{},'expandedIds':['processes','ready','category:fundamental']+(['process:'+ident] if ident else [])}};self.view_sessions[sid]=old
        else:self.check(old is not None and old['actor']==actor,'VIEW_SESSION_NOT_FOUND')
        if action in ('update','close'):
            self.check(message.get('expectedRevision')==old['revision'],'VIEW_CAS_MISMATCH')
        if action=='close':del self.view_sessions[sid];return {'closed':True,'persisted':False}
        if action=='update':
            value=copy.deepcopy(message['value']);self.check({'activeScreenId','screens'}<=set(value) and set(value)<= {'activeScreenId','screens','explorer'} and isinstance(value['screens'],list) and 0<=len(value['screens'])<=32,'VIEW_SESSION_SCHEMA')
            if 'explorer' in value:
                e=value['explorer'];self.check(isinstance(e,dict) and {'open','tab','query','scroll','selectedPackageId','drafts'}<=set(e) and set(e)<={'open','tab','query','scroll','selectedPackageId','drafts','expandedIds'} and isinstance(e['drafts'],dict) and (e['selectedPackageId'] is None or isinstance(e['selectedPackageId'],str)) and type(e['open']) is bool and e['tab'] in ('graphs','packages') and isinstance(e['query'],str) and type(e['scroll']) in (int,float) and e['scroll']>=0,'VIEW_EXPLORER_SCHEMA')
                self.check(isinstance(e.get('expandedIds',[]),list) and len(e.get('expandedIds',[]))<=512 and all(isinstance(i,str) and 0<len(i)<=250 for i in e.get('expandedIds',[])),'VIEW_EXPLORER_SCHEMA')
            ids=set();previous={s['id']:s for s in old['screens']}
            for screen in value['screens']:
                self.check(isinstance(screen,dict) and {'id','packageId','spec','panels','draft','trail','inspector'}<=set(screen) and set(screen)<={'id','packageId','spec','panels','draft','trail','inspector','viewTrail','focusLayouts','presentation'} and
                    isinstance(screen['id'],str) and str(uuid.UUID(screen['id']))==screen['id'] and screen['id'] not in ids,'VIEW_SCREEN_SCHEMA')
                ids.add(screen['id']);self.model.validate_view_spec(screen['spec'])
                # Controller presentation state is UI-only; no changes to the
                # public Graph/View specification or any persisted owner data.
                presentation=screen.get('presentation',{})
                self.check(isinstance(presentation,dict) and set(presentation)<=
                    {'mode','expandedPaths','collapsedPaths','query','dependencyTab','selectedPolicyId','selectedPolicyVersion','selectedPolicyRuleId','questionId'} and
                    presentation.get('mode','graph') in ('graph','structure','markdown','dependencies','questions') and
                    (presentation.get('questionId') is None or
                     isinstance(presentation['questionId'],str) and 0<len(presentation['questionId'])<=180) and
                    presentation.get('dependencyTab','stale') in ('stale','policies') and
                    isinstance(presentation.get('selectedPolicyId',''),str) and
                    len(presentation.get('selectedPolicyId',''))<=180 and
                    (presentation.get('selectedPolicyVersion') is None or
                     type(presentation.get('selectedPolicyVersion')) is int and
                     1<=presentation['selectedPolicyVersion']<=1000000) and
                    (presentation.get('selectedPolicyRuleId') is None or
                     isinstance(presentation.get('selectedPolicyRuleId'),str) and
                     len(presentation['selectedPolicyRuleId'])<=180) and
                    isinstance(presentation.get('query',''),str) and
                    len(presentation.get('query',''))<=180,'VIEW_PRESENTATION_SCHEMA')
                for name in ('expandedPaths','collapsedPaths'):
                    paths=presentation.get(name,[])
                    self.check(isinstance(paths,list) and len(paths)<=512 and
                        len(paths)==len(set(paths)) and all(isinstance(key,str) and
                        0<len(key)<=350 for key in paths),'VIEW_PRESENTATION_PATHS')
                self.check(not set(presentation.get('expandedPaths',[])) &
                    set(presentation.get('collapsedPaths',[])),'VIEW_PRESENTATION_PATH_CONFLICT')
                self.metadata(screen['packageId'],['graph.read'])
                panel=screen['panels'];self.check({'roadVisible','roadWidth','historyScroll','planScroll'} <= set(panel) <=
                    {'roadVisible','roadTab','roadWidth','inspectorWidth','historyScroll','planScroll'} and
                    type(panel.get('inspectorWidth',340)) in (int,float) and 260<=panel.get('inspectorWidth',340)<=1000 and
                    panel.get('roadTab','timeline') in ('timeline','dependencies') and
                    type(panel['roadVisible']) is bool and
                    type(panel['roadWidth']) in (int,float) and 260<=panel['roadWidth']<=1200 and all(type(panel[k]) in (int,float) and panel[k]>=0 for k in ('historyScroll','planScroll')),'VIEW_PANEL_SCHEMA')
                self.check(screen['draft'] is None or isinstance(screen['draft'],dict),'VIEW_DRAFT_SCHEMA')
                focus_layouts=screen.get('focusLayouts',{})
                self.check(isinstance(focus_layouts,dict) and len(focus_layouts)<=256 and
                    all(isinstance(k,str) and 0<len(k)<=250 and isinstance(v,dict)
                        for k,v in focus_layouts.items()),'VIEW_FOCUS_LAYOUTS')
                for focus_id,placements in focus_layouts.items():
                    self.model.validate_view_spec({'kind':'focus','id':focus_id,'focusPositions':placements})
                self.check(isinstance(screen.get('viewTrail',[]),list) and len(screen.get('viewTrail',[]))<=32,'VIEW_NAV_TRAIL_SCHEMA')
                for item in screen.get('viewTrail',[]):
                    self.check(isinstance(item,dict) and set(item)=={'spec','inspector'} and
                        (item['inspector'] is None or isinstance(item['inspector'],dict)),'VIEW_NAV_TRAIL_SCHEMA')
                    self.model.validate_view_spec(item['spec'])
                self.check(isinstance(screen['trail'],list) and len(screen['trail'])<=32,'VIEW_TRAIL_SCHEMA')
                for trail in screen['trail']:
                    self.check({'packageId','spec','inspector'}<=set(trail) and set(trail)<= {'packageId','spec','inspector','draft','mode','inspectorTab'} and trail.get('mode','graph') in ('graph','structure','markdown','dependencies','questions') and isinstance(trail.get('inspectorTab',''),str),'VIEW_TRAIL_SCHEMA');self.metadata(trail['packageId'],['graph.read']);self.model.validate_view_spec(trail['spec'])
            self.check(value['activeScreenId'] in ids if ids else value['activeScreenId'] is None,'VIEW_ACTIVE_SCREEN')
            old={**old,**value,'revision':old['revision']+1};self.view_sessions[sid]=old
        for screen in old['screens']:
            self.metadata(screen['packageId'],['graph.read'])
            for trail in screen['trail']:self.metadata(trail['packageId'],['graph.read'])
        return {k:copy.deepcopy(v) for k,v in old.items() if k!='actor'}|{'persisted':False}

    def registry(self,revision=None):
        self.authorize(None,['graph.read'])
        row=self.store.registry_read();value=row['registry'] or self.recommendations.empty(self.store.namespace_id)
        if revision is not None and revision!=value['revision']:
            directory=self.store.path('.rdg/recommendations/versions',True)
            found=[json.loads(p.read_bytes()) for p in directory.glob('*.json') if json.loads(p.read_bytes()).get('revision')==revision]
            self.check(len(found)==1,'REGISTRY_VERSION_UNAVAILABLE');value=found[0]
        self.recommendations.validate(value)
        self.kernel.for_graph({'coreModel':'rdg-decision-v1'}).validate_policy_definitions(value.get('dependencyPolicies',[]))
        return {**row,'registry':value}

    def recommendation_catalog(self,query='',offset=0,limit=50,revision=None,package_id=None):
        with self.store.lock(False,create=False):
            row=self.registry(revision);value=row['registry'];rows=[]
            self.check(isinstance(query,str) and type(offset) is int and offset>=0 and type(limit) is int and 1<=limit<=100,'CATALOG_QUERY')
            for p in value['packages']:
                if (package_id is None or p['id']==package_id) and query.casefold() in (p['title']+' '+p['key']).casefold():rows.append(copy.deepcopy(p))
            participation={p['id']:[] for p in value['packages']}
            for meta in self._catalog_locked()['packages']:
                if meta['health']!='metadata-verified':continue
                # Catalog payloads were already validated under this same namespace barrier.
                for pid in meta.get('recommendationPackageIds',[]):
                    participation.setdefault(pid,[]).append({'packageId':meta['packageId'],'title':meta['title'],'role':meta['role']})
            return {'registryRevision':value['revision'],'registrySHA256':self.model.digest(value),'packages':rows[offset:offset+limit],
                'total':len(rows),'offset':offset,'participation':participation,'versionsAvailable':True}

    def input_binding(self, request, prepared):
        """Conservative input pin for this planner; never a human consent proof."""
        actor, _ = self.authority._actor(self.authority._read(), self.token)
        checks = {}
        for check in prepared['checks']:
            key = (check['namespaceId'], check.get('packageId'), check.get('path'))
            checks.setdefault(key, set()).update(check['permissions'])
        permissions = [{'namespaceId': key[0], 'packageId': key[1], 'path': key[2],
                        'permissions': sorted(value)}
                       for key, value in sorted(checks.items(),
                           key=lambda item: tuple(str(part) for part in item[0]))]
        if prepared['decisionProfile']:
            def owner(ident):
                return ({'kind':'recommendationRegistry','namespaceId':self.store.namespace_id} if ident in (None,self.store.registry_key()) else
                        {'kind':'package', 'namespaceId':self.store.namespace_id,'packageId':ident})
            typed_permissions = [{'owner':owner(key[1]), 'permissions':sorted(value)}
                for key, value in sorted(checks.items(),
                    key=lambda item:tuple(str(part) for part in item[0]))]
            effect_owners = [owner(ident) for ident in sorted(prepared['changes'])]
            typed = {'schemaVersion':2, 'policy':'typed-owner-read-set-v1',
                     'namespaceId':self.store.namespace_id, 'actorGrantId':actor,
                     'requestSHA256':self.model.digest(request),
                     'ownerPins':copy.deepcopy(prepared['ownerPins']),
                     'requiredPermissions':typed_permissions,
                     'catalog':copy.deepcopy(prepared['catalog']),
                     'effectOwners':effect_owners}
            return {**typed, 'sha256':self.model.digest(typed)}
        value = {'schemaVersion': 1, 'policy': 'full-read-set-v1',
                 'namespaceId': self.store.namespace_id, 'actorGrantId': actor,
                 'requestSHA256': self.model.digest(request),
                 'readSet': copy.deepcopy(prepared['readset']),
                 'catalog': copy.deepcopy(prepared['catalog']),
                 'requiredPermissions': permissions,
                 'effectPackageIds': sorted(prepared['changes'])}
        return {**value, 'sha256': self.model.digest(value)}

    def preflight_result(self, request, prepared):
        return {'preflight': True, 'accepted': False, 'effects': prepared['effects'],
                'requiredPermissions': prepared['checks'], 'readSet': prepared['readset'],
                'allocation': prepared.get('allocation'),
                'inputBinding': self.input_binding(request, prepared)}

    def approval_record(self, request_id):
        path = self.store.metadata_path('approval-requests', request_id)
        self.check(path.is_file(), 'APPROVAL_REQUEST_NOT_FOUND')
        value = json.loads(path.read_bytes())
        self.check(value.get('schemaVersion') == 1 and
                   value.get('kind') == 'rdgPendingApprovalRequest' and
                   value.get('requestId') == request_id and value.get('state') == 'pending' and
                   isinstance(value.get('request'), dict) and
                   value['request'].get('transactionId') == request_id and
                   value.get('namespaceId') == self.store.namespace_id and
                   value.get('targetPackageId') == value['request'].get('targetPackageId') and
                   self.model.digest(value['request']) == value.get('requestSHA256'),
                   'APPROVAL_REQUEST_CORRUPT')
        return value

    def check_approval_intent(self, request, token_sha):
        if not self.store.metadata_path('approval-requests', request['transactionId']).is_file():
            return
        value = self.approval_record(request['transactionId'])
        self.check(value['actorTokenSHA256'] == token_sha, 'APPROVAL_REQUEST_ACTOR_MISMATCH')
        self.check(value['requestSHA256'] == self.model.digest(request),
                   'APPROVAL_REQUEST_ID_CONFLICT')

    def approval_view(self, value):
        result = {k: copy.deepcopy(v) for k, v in value.items() if k != 'actorTokenSHA256'}
        result.update(executionAvailable=False, humanApprovalVerified=False,
                      previewIsSnapshot=True, limitation='TRUSTED_HUMAN_PATH_UNAVAILABLE')
        decision = self.store.metadata_path('approval-decisions', value['requestId'])
        if decision.is_file():
            record = json.loads(decision.read_bytes())
            self.check(record.get('kind') == 'rdgApprovalDecision' and
                       record.get('requestId') == value['requestId'] and
                       record.get('requestSHA256') == value['requestSHA256'] and
                       record.get('state') == 'rejected', 'APPROVAL_DECISION_CORRUPT')
            result.update(state='rejected', decisionVerified=True, decision=record,
                          limitation='TRUSTED_DEPLOYMENT_NOT_VERIFIED')
        accepted = self.store.metadata_path('accepted', value['requestId'])
        if accepted.is_file():
            certificate = json.loads(accepted.read_bytes())
            self.check(certificate['actorTokenSHA256'] == value['actorTokenSHA256'] and
                       certificate['requestSHA256'] == value['requestSHA256'],
                       'APPROVAL_TRANSACTION_CONFLICT')
            self.check(not decision.exists(), 'APPROVAL_TRANSACTION_CONFLICT')
            result['state'] = 'executed-independently'
            if certificate.get('schemaVersion') == 2:
                self.store.transaction_actor(certificate, value['actorTokenSHA256'])
                result.update(state='executed-approved', decisionVerified=True,
                    authorizationContext=self.store.public_authorization_context(certificate['authorizationContext']),
                    limitation='TRUSTED_DEPLOYMENT_NOT_VERIFIED')
            result['transactionState'] = ('completed' if
                self.store.metadata_path('completed', value['requestId']).is_file() else 'prepared')
            if certificate.get('schemaVersion') == 2 and result['transactionState'] == 'prepared':
                result['state'] = 'approved-awaiting-recovery'
        return result

    def approval_request(self, request, rationale):
        """Create a pending exact request for an existing target or a new package.

        Targetless pending is intentionally closed to create/copy: their prepared
        checks pin the destination path, source read set and catalog before any
        executor decision. No new grant is issued by this method.
        """
        self.check(isinstance(request, dict) and isinstance(request.get('transactionId'), str),
                   'APPROVAL_REQUEST')
        request = copy.deepcopy(request)
        self.check(str(uuid.UUID(request['transactionId'])) == request['transactionId'],
                   'TRANSACTION_ID')
        self.check(isinstance(rationale, str) and bool(rationale.strip()) and len(rationale) <= 4000,
                   'APPROVAL_RATIONALE_REQUIRED')
        operation = request.get('op')
        self.check(operation in self.OPERATIONS, 'UNKNOWN_OPERATION')
        self.check(operation not in ('move', 'folder_create', 'folder_move', 'migrate'),
                   'APPROVAL_ADAPTER_NOT_IMPLEMENTED')
        targetless = operation in ('create', 'copy') and 'targetPackageId' not in request
        ident = request.get('targetPackageId')
        self.check((isinstance(ident, str) and not targetless) or
                   (targetless and ident is None), 'APPROVAL_EXISTING_TARGET_REQUIRED')
        actor, _ = self.authority._actor(self.authority._read(), self.token)
        token_sha = hashlib.sha256(self.token.encode()).hexdigest()
        with self.store.lock(True):
            row = self.metadata(ident, ['graph.read', 'graph.write']) if ident is not None else None
            path = self.store.metadata_path('approval-requests', request['transactionId'])
            if path.is_file():
                value = self.approval_record(request['transactionId'])
                self.check_approval_intent(request, token_sha)
                self.check(value['rationale'] == rationale, 'APPROVAL_REQUEST_ID_CONFLICT')
                return self.approval_view(value)
            self.check(not self.store.metadata_path('accepted', request['transactionId']).exists(),
                       'APPROVAL_TRANSACTION_ALREADY_ACCEPTED')
            self.store.check_intent(request['transactionId'], self.model.digest(request), token_sha)
            prepared = None
            try:
                prepared = self.prepare(request)
                preview = {'available': True, **self.preflight_result(request, prepared)}
            except ValueError as exc:
                blocker = str(exc)
                self.check(blocker in ('CORE_OBJECT_OPERATION_LOCK_REQUIRED',
                    'CORE_PROTECTED_OWNER_GRANT_REQUIRED', 'CORE_LOCK_USER_PATH_REQUIRED',
                    'PORTABLE_APP_LOCK_USER_PATH_REQUIRED', 'AUTH_PORTABLE_SCOPE_DENIED') or
                    blocker.startswith('AUTH_MISSING_PERMISSION: ') or
                    blocker == 'PORTABLE_APP_LOCK_PRINCIPAL_REQUIRED' and
                    operation in ('lock_set','lock_remove') and
                    request.get('authorityPrincipal') in (None,''),
                    'APPROVAL_INVALID_REQUEST: ' + blocker)
                preview = {'available': False, 'blocker': blocker, 'inputBinding': None}
            value = {'schemaVersion': 1, 'kind': 'rdgPendingApprovalRequest',
                     'requestId': request['transactionId'], 'state': 'pending',
                     'namespaceId': self.store.namespace_id, 'targetPackageId': ident,
                     'initiator': {'grantId': actor, 'attribution': self.attribution},
                     'actorTokenSHA256': token_sha, 'requestSHA256': self.model.digest(request),
                     'request': request, 'rationale': rationale,
                     'createdAt': datetime.now(timezone.utc).isoformat(),
                     'targetHeadSHA256': row['headSHA256'] if row is not None else None,
                     'preview': preview}
            checks = prepared['checks'] if prepared is not None else []
            if row is not None:
                checks = [{'namespaceId': self.store.namespace_id, 'packageId': ident,
                           'path': row['path'], 'permissions': ['graph.read', 'graph.write']}]
            with self.authority.checked_portable_transaction(self.token, checks):
                self.store.reserve_intent(request['transactionId'], value['requestSHA256'], token_sha)
                self.store.io.immutable_bytes(path, self.store.encode(value))
            return self.approval_view(value)

    def approval_read(self, request_id):
        _, _grant = self.authority._actor(self.authority._read(), self.token)
        token_sha = hashlib.sha256(self.token.encode()).hexdigest()
        with self.store.lock(False, create=False):
            value = self.approval_record(request_id)
            self.check(value['actorTokenSHA256'] == token_sha, 'APPROVAL_REQUEST_ACTOR_MISMATCH')
            if value['targetPackageId'] is not None:
                self.metadata(value['targetPackageId'], ['graph.read'])
            return self.approval_view(value)

    def dependency_applications(self,current):
        """Authorized, derived namespace usage; never a manually edited count."""
        decision=self.kernel.for_graph({'coreModel':'rdg-decision-v1'});result=[]
        for meta in self.store.scan():
            pid=meta.get('packageId')
            if not pid or meta.get('health')!='metadata-verified':continue
            try:self.authorize(pid,['graph.read'],meta['path'])
            except ValueError as exc:
                if 'PORTABLE_SCOPE_DENIED' not in str(exc):raise
                continue
            graph=(current['graph'] if pid==current['packageId'] else
                   self.store.read(pid,include_plan=False,include_layouts=False)['graph'])
            if graph.get('coreModel')!='rdg-decision-v1':continue
            for binding in graph.get('dependencyBindings',[]):
                if binding.get('status')=='deleted':continue
                result.append({'packageId':pid,'graphTitle':graph['title'],'automatic':False,
                    'policyId':binding['policyId'],'policyVersion':binding['policyVersion'],
                    'binding':copy.deepcopy(binding)})
            effective=decision.POLICIES.automatic_matches(graph,decision)
            for key,state in graph.get('dependencyAutomaticStates',{}).items():
                if key not in effective:
                    result.append({'packageId':pid,'graphTitle':graph['title'],'automatic':True,
                        'policyId':decision.POLICIES.automatic_policy_id(state['origin']),
                        'policyVersion':1,'binding':copy.deepcopy(state)})
            for key,match in effective.items():
                state=graph.get('dependencyAutomaticStates',{}).get(key,{})
                result.append({'packageId':pid,'graphTitle':graph['title'],'automatic':True,
                    'policyId':decision.POLICIES.automatic_policy_id(match['origin']),
                    'policyVersion':1,'binding':{'id':key,'sourceId':match['sourceId'],'targetId':match['dependentId'],
                        'enabled':state.get('status','active')=='active','status':state.get('status','active'),
                        'reasonCode':state.get('reasonCode')}})
            for edge in graph['edges']:
                if edge['type']!='DEPENDS_ON':continue
                preset=edge.get('dependencyRule',{}).get('preset',edge.get('dependencyLevel','L1'))
                result.append({'packageId':pid,'graphTitle':graph['title'],'automatic':False,'legacy':True,
                    'policyId':'builtin:'+preset,'policyVersion':1,'binding':{'id':edge['id'],
                        'sourceId':edge['from'],'targetId':edge['to'],'enabled':True,'status':'active'}})
        return result

    def read(self, ident, include_plan=False, view=None, *, detail=None, include=None, node_id=None, record_id=None, limit=25, cursor=None, output_format=None):
        self.check(output_format in (None, 'json', 'markdown'), 'READ_FORMAT')
        if output_format == 'markdown':
            self.check(record_id is None and limit == 25, 'MARKDOWN_OPTIONS')
            return MARKDOWN.read(self, ident, detail=detail, view=view, node_id=node_id,
                                 include=include, include_plan=include_plan, cursor=cursor,
                                 compact=COMPACT, scoped=SCOPED)
        self.check(detail in (None,'full','summary','item','focus','branch'), 'READ_DETAIL')
        if detail in ('focus','branch'):
            self.check(view is None and not include_plan, 'READ_VIEW_FILTER_UNAVAILABLE')
            self.check(record_id is None, 'READ_RECORD_ID_UNAVAILABLE')
            selected, origin = SCOPED.options(self,detail,[] if include is None else include,node_id,limit,cursor)
            with self.store.lock(False,create=False):
                row=self.snapshot(ident,'plan' in origin,layouts=False,scoped_read=True)
                self.check(row['graph']['coreModel']=='rdg-decision-v1','READ_PROFILE_UNSUPPORTED')
                with self.kernel.for_graph(row['graph']).ANALYSIS.read_scope(row['graph']):
                    return SCOPED.project(self,ident,row,detail,[] if include is None else include,node_id,limit,cursor,COMPACT)
        if detail in ('summary','item'):
            facets=include or (['entities'] if detail=='summary' else [])
            self.check(view is None and not include_plan, 'READ_VIEW_FILTER_UNAVAILABLE')
            with self.store.lock(False,create=False):
                row=self.snapshot(ident,any(f in facets for f in ('plan','planForks','planTimeConstraints')),layouts=False)
                scope=(self.kernel.for_graph(row['graph']).ANALYSIS.read_scope(row['graph'])
                       if row['graph']['coreModel']=='rdg-decision-v1' and
                       ('context' in facets or 'dependencyApplications' in facets) else nullcontext())
                with scope:return COMPACT.project(self,ident,row,detail,include or [],node_id,limit,cursor,record_id)
        self.check(include is None and node_id is None and record_id is None and cursor is None and limit==25, 'READ_DETAIL_REQUIRED')
        with self.store.lock(False, create=False):
            row=self.snapshot(ident,include_plan)
            scope=(self.kernel.for_graph(row['graph']).ANALYSIS.read_scope(row['graph'])
                   if row['graph']['coreModel']=='rdg-decision-v1' else nullcontext())
            # One immutable snapshot, one read calculation; never cache across writes.
            with scope:return self._read_projection(ident,row,view)

    def recommendation_projection(self,ident,graph,*,node_ids=None,register=None):
        try:self.authorize(None,['graph.read'])
        except ValueError as exc:
            if 'PORTABLE_SCOPE_DENIED' not in str(exc):raise
            return {'available':False,'matches':[],'packages':[],'diagnostics':[{'reason':'registry-scope-unavailable'}],'automaticExecution':False}
        reg=self.registry()['registry'];result=self.recommendations.matches(reg,graph,ident,self.kernel,**({'node_ids':node_ids} if node_ids is not None else {}))
        if node_ids is not None:result['matches']=[m for m in result['matches'] if m['nodeId'] in node_ids]
        result.update(available=True,packages=[p for p in reg['packages'] if p['id'] in graph['recommendationPackageIds']])
        cache={}
        for match in result['matches']:
            ref=match['lensRef'];key=(ref['packageId'],ref['identitySpace'],ref['lensKey'],ref.get('nodeId'))
            if key not in cache:
                try:
                    target=register(ref['packageId']) if register else self.snapshot(ref['packageId'],layouts=False)
                    self.check(target['head']['role']=='lens' and target['graph']['coreModel']==graph['coreModel'] and target['graph']['identitySpace']==ref['identitySpace'] and target['head']['lensKey']==ref['lensKey'],'RECOMMENDATION_TARGET_INCOMPATIBLE')
                    self.check('nodeId' not in ref or ref['nodeId'] in self.kernel.entities(target['graph']),'RECOMMENDATION_STEP_MISSING')
                    cache[key]={'available':True,'graphRevision':target['graph']['revision']}
                except (ValueError,OSError):cache[key]={'available':False,'reason':'target-unavailable-or-incompatible'}
            match['target']=copy.deepcopy(cache[key])
        return result

    def _read_projection(self,ident,row,view):
        external=self.boundaries(row);completion=self.states(row,external)
        sources={ident:{'graph':row['graph'],'completion':completion}}
        if row['plan'] is not None:
            for ref_id in {s['ref']['packageId'] for s in row['plan']['steps']}-{ident}:
                try:
                    source=self.snapshot(ref_id,layouts=False)
                    sources[ref_id]={'graph':source['graph'],'completion':self.states(source,self.boundaries(source))}
                except (ValueError,OSError) as exc:sources[ref_id]={'error':str(exc)}
        projection=self.model.presentation(row['graph'],self.kernel,view)
        projection['completion']=completion
        if row['graph']['coreModel']=='rdg-decision-v1':projection['visual']=self.layout('project',graph=row['graph'],view=projection,document=row['layouts'])
        recommendations=self.recommendation_projection(ident,row['graph']) if row['graph']['coreModel']=='rdg-decision-v1' else None
        dependency_catalog=None
        if row['graph']['coreModel']=='rdg-decision-v1':
            decision=self.kernel.for_graph(row['graph'])
            shared={};catalog_revision=None;available=False
            try:
                reg=self.registry()['registry'];catalog_revision=reg['revision'];available=True
                shared={(p['id'],p['version']):copy.deepcopy(p) for p in reg.get('dependencyPolicies',[])}
            except ValueError as exc:
                if 'PORTABLE_SCOPE_DENIED' not in str(exc):raise
            for p in row['graph'].get('dependencyPolicies',[]):shared.setdefault((p['id'],p['version']),copy.deepcopy(p))
            local_applications=decision.POLICIES.describe_applications(row['graph'],decision)
            dependency_catalog={'available':available,'revision':catalog_revision,
                'policyAliases':row['graph'].get('dependencyPolicyAliases',{}),
                'policies':list(shared.values()),'systemPolicies':decision.POLICIES.builtins(decision),
                'capabilities':decision.dependency_capabilities(),
                'localApplications':local_applications,
                'invalidationRecords':decision.POLICIES.describe_invalidation(row['graph'],decision,local_applications),
                'migrationRequired':bool(row['graph'].get('dependencyPresets')) or any(not any(p['id']==q['id'] and p['version']==q['version'] and {k:v for k,v in p.items() if k!='status'}=={k:v for k,v in q.items() if k!='status'} for q in reg.get('dependencyPolicies',[])) for p in row['graph'].get('dependencyPolicies',[])) if available else False,
                'localPolicyCount':len(row['graph'].get('dependencyPolicies',[])),
                'localPresetCount':len(row['graph'].get('dependencyPresets',[])),
                'applications':self.dependency_applications(row)}
        reference_nodes=self.kernel.entities(row['graph'])
        reference_sha=self.model.digest(row['graph'])
        references={nid:self.model.reference(ident,row['graph'],nid,graph_sha256=reference_sha,node_revision=node['revision'])
                    for nid,node in reference_nodes.items()}
        return {'decisionContexts':({n['id']:decision.decision_context(row['graph'],n['id']) for n in row['graph']['nodes'] if n['kind']=='decision'} if row['graph']['coreModel']=='rdg-decision-v1' else {}),'findings':(decision.FINDINGS.describe(row['graph'],decision,(view or {}).get('id') if (view or {}).get('kind')=='focus' else row['graph'].get('rootRequirementId')) if row['graph']['coreModel']=='rdg-decision-v1' else []),'dependencyCatalog':dependency_catalog,'package':{k:row['head'][k] for k in ('packageId','role','identitySpace','revision')},
                'capabilities':self.profile_capabilities(row['graph'],row['head']['role']),
                'immutableDefinition':bool(row['head'].get('lineage',{}).get('supplied') and not row['head'].get('lineage',{}).get('userManaged')),'path':row['path'],'graph':row['graph'],'plan':row['plan'],'layouts':row['layouts'],
                'references':references,
                'scopeReferences':{'process':self.model.scope_reference(ident,row['graph']),
                    'workGraphs':{w['id']:self.model.scope_reference(ident,row['graph'],'workGraph',w['id']) for w in row['graph']['workGraphs']}},
                'actionSubjects':{a['id']:[self.resolve_action_subject(ref,a,row) for ref in a.get('subjectRefs',[])] for a in row['graph'].get('externalActions',[]) if 'subjectRefs' in a},
                'view':projection,'planView':self.model.project_plan(row['plan'],sources,self.kernel,view),
                'detached':[{**c,'reviewIds':sorted(set(c['reviewIds']) | (set(c['memberIds']) & set(external['reviewIds'])))} for c in self.kernel.detached_components(row['graph'])],
                'recommendations':recommendations,'completion':completion,'external':external,'receipt':row['receiptValue']}

    def states(self,row,external):
        completion=self.kernel.completion_state(row['graph'])
        for nid in external['reviewIds']:
            if nid in completion:completion[nid].update(complete=False,currentScopeComplete=False,reviewRequired=True,truth='unknown')
        return completion

    def schema(self,op,ident=None,node_id=None,source_id=None,command=None,source_path=None,source_key=None,*,core_model=None,role=None,entity_kind=None):
        with self.store.lock(False,create=False):return self._schema(op,ident,node_id,source_id,command,source_path,source_key,core_model=core_model,role=role,entity_kind=entity_kind)

    def _schema(self,op,ident=None,node_id=None,source_id=None,command=None,source_path=None,source_key=None,*,core_model=None,role=None,entity_kind=None):
        if op == 'catalog':
            self.check(all(v is None for v in (ident,node_id,source_id,command,source_path,source_key,core_model,role,entity_kind)), 'CATALOG_SCHEMA_SELECTORS')
            return {'method':'catalog','schemaVersion':1,'pagination':False,'complete':True,
                'snapshot':'catalogSHA256 binds the complete visible response under the namespace read barrier',
                'lensCard':{'status':['available','missing','invalid','unavailable'],
                    'source':'exact package and graph revisions/SHA256; sourceRef identifies the owning Info',
                    'authoring':{'kind':'info','tags':['rdg:lens-catalog'],
                        'description':'purpose','value':'free-text applicability triggers'},
                    'workflowAuthoring':{'kind':'info','tags':['rdg:lens-workflow'],
                        'description':'when/how explanation','value':'workflow context text'},
                    'rules':'At most one Info per role. Use existing add/edit operations. No automatic execution or draft-key fallback.'}}
        if op == 'search':
            self.check(all(v is None for v in (ident,node_id,source_id,command,source_path,source_key,core_model,role,entity_kind)), 'SEARCH_SCHEMA_SELECTORS')
            return SEARCH.schema()
        if op in ('read','history'):
            self.check(core_model is None and role is None and entity_kind is None and command is None and source_id is None and source_path is None and source_key is None, 'READ_SCHEMA_SELECTORS')
            if ident:self.snapshot(ident,layouts=False)
            result = COMPACT.schema()
            if op == 'read':
                result['read']['format'] = ['json','markdown']
                result['markdown'] = MARKDOWN.schema()
            return result
        self.check(op in self.OPERATIONS,'UNKNOWN_OPERATION')
        self.check((core_model is None and role is None) or op=='create','CREATE_SELECTOR_ONLY')
        self.check(entity_kind is None or op in ('core','paper_edit') and command=='add','ENTITY_KIND_ONLY_FOR_ADD')
        req={'op':op,'transactionId':str(uuid.uuid4())}
        required=[]
        if op=='create':
            profile='rdg-core-v1' if core_model is None else core_model;self.kernel.for_profile(profile)
            selected_role=role if role is not None else ('working' if core_model=='rdg-decision-v1' else 'ready')
            self.check(selected_role in ('working','ready','lens'),'CREATE_ROLE')
            req.update(path='', role=selected_role, title='', scope='', coreModel=profile,
                        rootReason='' if core_model=='rdg-decision-v1' else 'Explicit reason for this process')
            required=['path','role','title','scope','coreModel']
            if profile=='rdg-decision-v1':required.append('rootReason')
            if selected_role=='lens':req['lensKey']='';required.append('lensKey')
        elif op in ('batch','plan_action'):
            self.check(ident is not None,'BATCH_OWNER')
            row=self.snapshot(ident,True)
            self.check(row['graph']['coreModel']=='rdg-decision-v1' and
                       row['head']['role'] in ('working','copy'), 'BATCH_PROFILE')
            req.update(targetPackageId=ident,expectedPackageRevision=row['head']['revision'],
                       expectedGraphRevision=row['graph']['revision'],
                       expectedPlanRevision=row['plan']['revision'] if row['plan'] else None,
                       steps=[],note='')
            required=['steps','note']
            if op=='plan_action':
                req.pop('steps');req.update(entity={'kind':'action','actionType':'task','lowLevel':False,'title':'','description':'','subjectRefs':[]},placement={})
                required=['entity.title','note']
        elif op=='recommendation_edit':
            reg=self.registry()['registry'];req.update(expectedRegistryRevision=reg['revision'],action='create',definition={},note='')
        elif op=='migrate':
            self.check(source_key is not None,'SOURCE_KEY_REQUIRED')
            inspection=self.migration.inspect(source_key)
            req.update(sourceKey=source_key,sourcePin=inspection['sourcePin'],path='',confirmOwnerSwitch=False,legacyWritersQuiesced=False,
                       presentationSourcesComplete=False,presentationWritersPaused=False,acknowledgeHistoricalGaps=False)
        elif op in ('folder_create','folder_move'):
            req['path']=''
            if op=='folder_move':
                self.check(source_path is not None,'SOURCE_FOLDER_REQUIRED')
                req.update({k:v for k,v in self.transfers.inspect_folder(source_path).items() if k in ('sourcePath','sourcePin')})
        else:
            row=self.snapshot(ident,op in ('plan_edit','place','unplace')) if ident else None
            self.check(row is not None or op=='copy','PACKAGE_ID_REQUIRED')
            if row:
                graph=row['graph'];nid=node_id or graph.get('rootRequirementId') or graph.get('fragmentFocus',{}).get('id')
                req.update(targetPackageId=ident,expectedPackageRevision=row['head']['revision'])
                if op not in ('plan_create','plan_edit','place','unplace','layout_edit','attach_evidence'):req['expectedGraphRevision']=graph['revision']
            if op in ('dependency_add','dependency_remove','lock_set','lock_remove'):
                self.check(row is not None, 'PACKAGE_ID_REQUIRED')
                if op == 'dependency_add':
                    req.update(sourceId='', dependentId=ident, dependencyLevel='L1', note='')
                elif op == 'dependency_remove':
                    req.update(edgeId='', disposition='', note='')
                elif op == 'lock_set':
                    req.update(nodeId=nid, operation='edit', mode='hard',
                               principals=[], message='', authorityPrincipal='', note='')
                else:
                    req.update(nodeId=nid, operation='edit', disposition='',
                               authorityPrincipal='', note='')
            elif op in ('core','paper_edit'):
                owner_role=row['head']['role']
                self.check((op=='paper_edit')==(owner_role in ('ready','lens')),'DOCUMENT_ROLE_COMMAND')
                self.check(command in self.authoring_commands(graph,owner_role),'CORE_COMMAND')
                self.check(self.command_port is not None,'COMMAND_BUILDER_UNAVAILABLE')
                if entity_kind is not None:
                    self.check(graph['coreModel']=='rdg-decision-v1','ENTITY_KIND_REQUIRES_DECISION_PROFILE')
                    self.check(entity_kind in self.profile_capabilities(graph,owner_role)['entityKinds'],'ENTITY_KIND_UNSUPPORTED')
                data=(self.command_port(graph,command,nid,self.kernel,entity_kind) if entity_kind is not None
                      else self.command_port(graph,command,nid,self.kernel))
                req.update(command=command,data=data,note='')
                required=['note']
                if command=='add' and graph['coreModel']=='rdg-decision-v1':
                    required=['note']+['data.entity.'+f for f in ('title',)+{
                        'requirement':('scope',),'decision':(),'action':(),
                        'canon':(),'context':('value',),'info':('value',),
                        'finding':('subjectId','findingType','rationale'),'question':('relatedRefs','impact','answerCondition')}[data['entity']['kind']]]
                if command=='question_migrate':data['sourceRef']=self.model.reference(ident,graph,nid)
                if command=='question_answer':required=['note','data.action','data.kind','data.text']
                if command=='question_assess':required=['note','data.sufficient','data.basis']
                if command in ('complete','falsify','resolve_finding','finding_disposition'):req['evidenceRefs']=[]
            elif op in ('copy','insert_copy','apply_ready','capture_ready'):
                source_id=source_id or (ident if op in ('copy','capture_ready') else None)
                self.check(source_id is not None,'SOURCE_PACKAGE_ID_REQUIRED');source=self.snapshot(source_id)
                req.update(sourcePackageId=source_id,sourcePin={'revision':source['head']['revision'],'sha256':self.model.digest(source['graph'])})
                if op in ('copy','capture_ready'):
                    req.pop('targetPackageId',None);req.pop('expectedPackageRevision',None);req.pop('expectedGraphRevision',None)
                    day=datetime.now(ZoneInfo('Asia/Bangkok')).date().isoformat()
                    req['path']='copies/'+day+'/'+req['transactionId']
                if op=='capture_ready':
                    self.check(source['graph']['coreModel']=='rdg-decision-v1','UNSUPPORTED_PROFILE_CAPABILITY');req.update(role='ready',recommendationIds=[],focus={'kind':'graph'},note='')
                elif op=='apply_ready':req.update(mode='ADD_ROOT',note='')
                else:req.update(focus={'kind':'graph'},note='')
            elif op=='delete':req.update(nodeIds=[nid] if nid else [],note='')
            elif op=='unlink':req.update(data={'edgeId':''},note='')
            elif op in ('place','unplace'):
                self.check(row['plan'] is not None,'PLAN_OWNER_REQUIRED')
                req.update(expectedPlanRevision=row['plan']['revision'],note='')
                if op=='place':
                    req.update(nodePackageId=ident,nodeId=nid,at='')
                    if graph['coreModel']=='rdg-decision-v1':
                        req['afterStepId']=row['plan']['mainStepIds'][-1] if row['plan']['mainStepIds'] else None
                else:req['stepId']=''
            elif op=='plan_edit':
                self.check(row['plan'] is not None,'PLAN_OWNER_REQUIRED');plan=copy.deepcopy(row['plan']);plan['revision']+=1
                req.update(expectedPlanRevision=row['plan']['revision'],plan=plan)
            elif op=='plan_create':req['title']=graph['title']
            elif op=='external_edit':req.update(referenceId='',target=None,note='')
            elif op=='layout_edit':req.update(expectedLayoutRevision=row['layouts']['revision'] if row['layouts'] else 0,commands=[])
            elif op=='lens_manage':
                req.update(confirmOwnerManagement=False,note='')
            elif op=='recommendation_attach':
                self.check(graph['coreModel']=='rdg-decision-v1','UNSUPPORTED_PROFILE_CAPABILITY');req.update(packageIds=graph['recommendationPackageIds'],note='')
            elif op=='lens_apply':
                self.check(graph['coreModel']=='rdg-decision-v1','UNSUPPORTED_PROFILE_CAPABILITY');req.update(lensPackageId='',nodeIds=[nid] if nid else [],evidenceIds=[],recommendationIds=[],note='')
            elif op=='attach_evidence':req['contentBase64']=''
            elif op=='move':req.update(path='',sourcePath=row['path'],note='')
        core_commands = (self.authoring_commands(graph,row['head']['role']) if 'graph' in locals() else
                         self.authoring_commands({'coreModel':req['coreModel']},req['role']) if op=='create' else self.kernel.COMMANDS)
        return {'request':req,'requiredInput':required,'operations':list(self.OPERATIONS),
                'profileSelector':{'default':'rdg-core-v1','preferred':'rdg-decision-v1','supported':['rdg-core-v1','rdg-decision-v1'],
                    'rootReasonRequiredFor':['rdg-decision-v1']},
                'conditionalRequired':{'rootReason':{'when':{'coreModel':'rdg-decision-v1'}}},
                'batch':BATCH.schema(),
                'capabilities':self.profile_capabilities(graph,row['head']['role']) if 'graph' in locals() else
                    {'profiles':['rdg-core-v1','rdg-decision-v1'],'selectionRequired':True},
                'inputChoices':({'entityKind':self.profile_capabilities(graph,row['head']['role']).get('entityKinds',[]),
                    'findingType':list(self.kernel.for_graph(graph).FINDINGS.TYPES),
                    'recommendations':{'authored':'boolean; independent advice identities','textFields':['whenText','usageText'],'anchorKinds':['entity','process','workGraph'],'lensStep':'optional lensRefs[].nodeId','compactFacet':'recommendations'},
                     'questionAnswerKinds':['hypothesis','observation','user_answer'],
                    'questionUserSource':'Direct trusted user entry, or exact quote of a current user-authored Context.',
                    'decisionTheory':{'kind':'canon','fields':{'guidance':'General text (legacy field), may be empty','canons':'Optional free text','knownErrors':'Optional ordered array of {id,title,description}; id unique locally, title nonempty, description may be empty'},'contentRequired':'At least one nonblank guidance/canons or one knownErrors entry','clear':{'guidance':'','canons':'','knownErrors':[]},'edit':'core edit changes, cosmetic=false; omitted fields are preserved'},
                    'planningMetaAction':{'operation':'plan_action','subjectRefs':'optional qualified entity or scope references; work subjects, no dependencies','atomic':'Action + placement via batch coordinator'},
                    'actionEstimates':{'optional':['complexity','time','basis'],'time':{'minSeconds':'finite >= 0','maxSeconds':'>= minSeconds'},'remove':'core edit changes.estimates=null'},
                    'questionAnswerActions':['add','edit','remove']} if 'graph' in locals() and graph['coreModel']=='rdg-decision-v1' else {}),
                'coreCommands':sorted(core_commands-{'remove','recommendation_packages','lens_application'}),'status':'unsubmitted',
                'instruction':'Supply actual data; preflight and apply the same request. Keep transactionId for exact retry.'}

    def receipt(self,ident,transaction_id):
        with self.store.lock(False,create=False):
            fallback=None
            accepted=self.store.metadata_path('accepted',transaction_id)
            if accepted.is_file():
                certificate=json.loads(accepted.read_bytes())
                if self.store.transaction_actor(certificate, hashlib.sha256(self.token.encode()).hexdigest()):
                    completed=self.store.metadata_path('completed',transaction_id).is_file()
                    fallback={'found':True,'accepted':True,'publicationCertificatePresent':completed,
                        'state':'completed-certificate' if completed else 'prepared','transactionId':transaction_id,
                        'requestSHA256':certificate['requestSHA256'],'currentStateVerified':False,
                        'instruction':'This is the accepted transaction certificate. Use the exact request to finish recovery; read the current package separately.'}
            transfer=self.store.metadata_path('transfers',transaction_id)
            if transfer.is_file():
                value=json.loads(transfer.read_bytes())
                if ident is None or any(p['packageId']==ident for p in value['packages']):
                    for check in value['checks']:self.authorize(check['packageId'],check['permissions'],check['path'])
                    return {'found':True,'state':value['state'],'published':value['state']=='completed','effects':value['effects'],
                            'transactionId':transaction_id}
            if ident is None:return fallback or {'found':False,'transactionId':transaction_id}
            try:row=self.snapshot(ident,layouts=False)
            except (ValueError,OSError):
                if fallback:return fallback
                raise
            directory=self.store.package_path(row['path'])
            for head in self.store.head_chain(row):
                if head['lastTransactionId']!=transaction_id:continue
                raw=self.store.io.safe_path(directory,head['receipt']['path'],True).read_bytes()
                self.check(self.store.sha(raw)==head['receipt']['sha256'],'RECEIPT_HASH_MISMATCH')
                return {'found':True,'receipt':json.loads(raw),'currentPackageRevision':row['head']['revision'],'published':True}
            return fallback or {'found':False,'transactionId':transaction_id,'instruction':'A missing receipt does not prove an uncertain write failed; use the exact request to recover.'}

    def call(self,message):
        """Closed shared transport contract for CLI, Agent and manual sessions."""
        self.check(isinstance(message,dict),'MESSAGE')
        method=message.get('method')
        fields={'catalog':set(),'search':{'query','scope','packageId','limit','cursor'},'read':{'packageId','includePlan','view','detail','include','nodeId','recordId','limit','cursor','format'},'history':{'packageId','view','detail','include','eventId','limit','cursor'},
                'resolve':{'packageId','reference'},'source_snapshot':{'packageId','pin','view'},
                'schema':{'op','packageId','nodeId','sourcePackageId','command','sourcePath','sourceKey','coreModel','role','entityKind'},
                'migration_sources':set(),'migration_inspect':{'sourceKey'},
                'receipt':{'packageId','transactionId'},'recover':{'transactionId'},'cancel_migration':{'transactionId'},
                'dependencies':{'packageId'},'locks':{'packageId'},
                'view_session':{'action','sessionId','packageId','view','expectedRevision','value'},
                'recommendation_catalog':{'query','offset','limit','revision','packageId'},
                'approval_request':{'request','rationale'},'approval_read':{'requestId'},
                'preflight':{'request','expectedInputBinding'},'apply':{'request','expectedInputBinding'}}
        self.check(method in fields and set(message)<={'method'}|fields[method],'MESSAGE_FIELDS')
        if method=='view_session':return self.view_session(message)
        if method=='catalog':return self.catalog()
        if method=='search':
            return SEARCH.search(self,message.get('query'),message.get('scope','package'),
                                 message.get('packageId'),message.get('limit',25),message.get('cursor'))
        if method=='recommendation_catalog':return self.recommendation_catalog(message.get('query',''),message.get('offset',0),message.get('limit',50),message.get('revision'),message.get('packageId'))
        if method=='approval_request':return self.approval_request(message['request'],message['rationale'])
        if method=='approval_read':return self.approval_read(message['requestId'])
        if method=='migration_sources':return self.migration.sources()
        if method=='migration_inspect':return self.migration.inspect(message['sourceKey'])
        if method=='read':return self.read(message['packageId'],message.get('includePlan',False),message.get('view'),detail=message.get('detail'),include=message.get('include'),node_id=message.get('nodeId'),record_id=message.get('recordId'),limit=message.get('limit',25),cursor=message.get('cursor'),output_format=message.get('format'))
        if method=='history':return self.history(message['packageId'],message.get('view'),detail=message.get('detail'),include=message.get('include'),event_id=message.get('eventId'),limit=message.get('limit',25),cursor=message.get('cursor'))
        if method=='resolve':return self.resolve(message['packageId'],message['reference'])
        if method=='source_snapshot':return self.source_snapshot(message['packageId'],message['pin'],message.get('view'))
        if method=='dependencies':return self.dependencies(message['packageId'])
        if method=='locks':return self.locks(message['packageId'])
        if method=='schema':return self.schema(message['op'],message.get('packageId'),message.get('nodeId'),
            message.get('sourcePackageId'),message.get('command'),message.get('sourcePath'),message.get('sourceKey'),
            core_model=message.get('coreModel'),role=message.get('role'),entity_kind=message.get('entityKind'))
        if method=='receipt':return self.receipt(message['packageId'],message['transactionId'])
        if method=='recover':return self.recover(message['transactionId'])
        if method=='cancel_migration':return self.migration.cancel(message['transactionId'])
        return self.request(message['request'],preflight=method=='preflight',
                            expected_input_binding=message.get('expectedInputBinding'))

    def recover(self,transaction_id):
        """Finish only a durable accepted intent, for its original bearer actor."""
        self.check(isinstance(transaction_id,str) and str(uuid.UUID(transaction_id))==transaction_id,'TRANSACTION_ID')
        actor=hashlib.sha256(self.token.encode()).hexdigest()
        with self.store.lock(True,create=False):
            transfer=self.store.metadata_path('transfers',transaction_id)
            if transfer.is_file():
                record=json.loads(transfer.read_bytes())
                return self.transfers.resume(transaction_id,record['requestSHA256'],actor)
            accepted=self.store.metadata_path('accepted',transaction_id)
            self.check(accepted.is_file(),'ACCEPTED_TRANSACTION_NOT_FOUND')
            certificate=json.loads(accepted.read_bytes());migration=self.store.metadata_path('migrations',transaction_id)
            if migration.is_file():return self.migration.resume(json.loads(migration.read_bytes()),certificate['requestSHA256'],actor)
            return self.store.replay(transaction_id,certificate['requestSHA256'],actor)

    def request(self, request, *, preflight=False, failpoint=None, before_accept=None,
                expected_input_binding=None):
        self.check(isinstance(request,dict) and isinstance(request.get('transactionId'),str),'REQUEST')
        tx=request['transactionId'];self.check(str(uuid.UUID(tx))==tx,'TRANSACTION_ID')
        if request.get('op')=='migrate':
            return self.migration.handle(request,preflight=preflight,failpoint=failpoint,
                                         before_accept=before_accept,
                                         expected_input_binding=expected_input_binding)
        if request.get('op') in ('move','folder_create','folder_move'):
            return self.transfers.handle(request,preflight=preflight,failpoint=failpoint,
                                         before_accept=before_accept,
                                         expected_input_binding=expected_input_binding)
        intent_sha=self.model.digest(request);token_sha=hashlib.sha256(self.token.encode()).hexdigest()
        if not preflight and self.store.metadata_path('accepted',tx).is_file():
            with self.store.lock(True):return self.store.replay(tx,intent_sha,token_sha)
        # Authenticate before a write lock can create a metadata file.
        self.authority._actor(self.authority._read(),self.token)
        with self.store.lock(not preflight,create=not preflight):
            if not preflight:
                prior=self.store.replay(tx,intent_sha,token_sha)
                if prior:return prior
            self.store.check_intent(tx,intent_sha,token_sha)
            self.check_approval_intent(request,token_sha)
            prepared=self.prepare(request)
            if expected_input_binding is not None:
                self.check(expected_input_binding == self.input_binding(request,prepared),
                           'PREVIEW_INPUTS_CHANGED')
            if preflight:return self.preflight_result(request,prepared)
            if before_accept:before_accept()
            def authorize_all():
                for check in prepared['checks']:self.authorize(check['packageId'],check['permissions'],check['path'])
            return self.store.commit(tx,intent_sha,prepared['changes'],token_sha,authorize_all,
                lambda:self.authority.checked_portable_transaction(self.token,prepared['checks']),prepared['readset'],
                failpoint,expected_catalog=prepared['catalog'])

    def prepare(self, request, *, approval_actor=None, recorded_at=None):
        # Internal host inputs only; the closed message contract never accepts them.
        attribution = 'user' if approval_actor is not None else self.attribution
        trust = ({'mode':'webauthn-approval-v1', 'transactionId':request['transactionId'],
                  'principalId':approval_actor['principalId'],
                  'executorGrantId':approval_actor['executorGrantId']} if approval_actor else None)
        def now():return recorded_at if recorded_at is not None else datetime.now(timezone.utc).isoformat()
        if request.get('op')=='batch':
            return BATCH.plan(self,request,attribution=attribution,trust=trust,recorded_at=recorded_at)
        op=request.get('op');tx=uuid.UUID(request['transactionId']);checks=[];rows={};changes={}
        effects={};allocation=None;registry_row=None;registry_value=None
        def add_check(ident,permissions,path):
            permissions=list(dict.fromkeys(permissions));self.authorize(ident,permissions,path)
            checks.append({'namespaceId':self.store.namespace_id,'packageId':ident,'path':path,'permissions':permissions})
        def read(ident,plan=False):
            row=self.snapshot(ident,plan)
            if row['graph'].get('coreModel') == 'rdg-decision-v1':
                unsupported = {'delete','unlink',
                    'dependency_add','dependency_remove'}
                self.check(op not in unsupported, 'UNSUPPORTED_PROFILE_CAPABILITY')
            lineage=row['head'].get('lineage',{})
            if lineage.get('supplied') and (op in ('core','delete','unlink') or
                                           op=='paper_edit' and not lineage.get('userManaged')):
                self.check(False,'PACKAGE_IMMUTABLE')
            rows[ident]=row
            add_check(ident,['graph.read']+(['plan.read'] if plan and row['plan'] is not None else []),row['path']);return row
        def change(ident,row,permissions,**values):
            add_check(ident,permissions,row['path'])
            changes[ident]={'path':row['path'],'before':row,'permissions':permissions,**values}
        def expected(row):
            self.check(request.get('expectedPackageRevision')==row['head']['revision'],'PACKAGE_CAS_MISMATCH')
            self.check(request.get('expectedGraphRevision')==row['graph']['revision'],'GRAPH_CAS_MISMATCH')
        def event(label):
            self.check(isinstance(request.get('note'),str) and request['note'].strip(),'NOTE_REQUIRED')
            value={'id':str(uuid.uuid5(tx,label)),'type':'requested','by':attribution,'note':request['note'],
                   'recordedAt':now(),
                   'verifiedTrustReceipt':copy.deepcopy(trust) if trust else {'mode':'local-manual-session' if self.attribution=='user' else 'portable-planning','transactionId':str(tx)}}
            if approval_actor:value['authorityPrincipal']=approval_actor['authorityPrincipal']
            for field in ('reasonForReconsideration','evidenceRefs'):
                if field in request:value[field]=copy.deepcopy(request[field])
            return value
        def registry_read():
            nonlocal registry_row,registry_value
            if registry_row is None:
                registry_row=self.registry();registry_value=copy.deepcopy(registry_row['registry'])
                add_check(None,['graph.read'],None)
                rows[self.store.registry_key()]={**registry_row,'head':{'revision':registry_value['revision']},'graph':None}
            return registry_value
        def registry_write():
            value=registry_read();self.recommendations.validate(value);add_check(None,['graph.write'],None)
            changes[self.store.registry_key()]={'path':'.rdg/recommendations','before':registry_row,
                'registry':copy.deepcopy(value),'permissions':['graph.write']}
        def remap_recommendations(graph,source,target_id,mapping,template=False):
            if not graph['recommendationPackageIds']:return
            reg=registry_read();definitions={p['id']:p for p in reg['packages']};result=[];changed=False
            for pid in graph['recommendationPackageIds']:
                self.check(pid in definitions,'REFERENCE_MISSING:recommendation');old=definitions[pid]
                owned=old.get('instance',{}).get('graphBinding')=={'packageId':source['packageId'],'identitySpace':source['graph']['identitySpace']}
                anchored=any(a.get('packageId')==source['packageId'] and a.get('identitySpace')==source['graph']['identitySpace'] for rule in old['rules'] if (a:=rule.get('anchor')))
                if not template and not owned and not (old.get('authored') and anchored):result.append(pid);continue
                value=copy.deepcopy(old);new_id=str(uuid.uuid5(tx,'recommendation-instance:'+pid))
                value.update(id=new_id,revision=1,supplied=False)
                for rule in value['rules']:
                    if 'anchor' not in rule:continue
                    anchor=rule['anchor']
                    scope_map={**mapping['entity'],**mapping.get('workGraph',{}),source['graph']['id']:graph['id']}
                    local=anchor['packageId']==source['packageId'] and anchor['identitySpace']==source['graph']['identitySpace'] and anchor['nodeId'] in scope_map
                    self.check(local or not template,'FOREIGN_TEMPLATE_ANCHOR')
                    if local:rule['anchor']={'packageId':target_id,'identitySpace':graph['identitySpace'],'nodeId':scope_map[anchor['nodeId']],**({'kind':anchor['kind']} if 'kind' in anchor else {})}
                members=[n['id'] for n in graph['nodes']+graph['objects']+graph['externalActions']]
                roots=[c['requirementId'] for c in graph['rootCauses']]
                value['instance']={'sourceDefinition':{'packageId':pid,'revision':old['revision'],'sha256':self.recommendations.digest(old)},
                    'graphBinding':{'packageId':target_id,'identitySpace':graph['identitySpace']},'memberIds':members,'rootIds':roots}
                self.recommendations.validate_definition(value);reg['packages'].append(value);result.append(new_id);changed=True
            graph['recommendationPackageIds']=result
            if changed:reg['revision']+=1;registry_write()
        if op=='create':
            self.check(set(request)<={'op','transactionId','path','role','graph','title','scope','lensKey','coreModel','rootReason'},'CREATE_FIELDS')
            role=request['role'];self.check(role in ('working','ready','lens'),'CREATE_ROLE')
            ident=str(uuid.uuid5(tx,'package'));space=str(uuid.uuid5(tx,'identity-space'))
            graph=copy.deepcopy(request.get('graph'))
            core_model=request.get('coreModel', graph.get('coreModel') if graph else self.kernel.PROFILE)
            self.check(core_model in (self.kernel.PROFILE, 'rdg-decision-v1'), 'CORE_MODEL')
            add_check(ident,['package.create','graph.write']+
                      (['plan.create'] if role=='working' and core_model != 'rdg-decision-v1' else []),request['path'])
            if core_model == 'rdg-decision-v1':
                self.check(isinstance(request.get('rootReason'),str) and request['rootReason'].strip(), 'ROOT_REASON_REQUIRED')
            if graph is None:
                graph=self.kernel.blank('graph-'+ident,request['title'],space,'R1',request['title'],
                    request.get('scope','Explicit working scope'),core_model=core_model,
                    root_reason=request.get('rootReason'))
            else:
                self.check(graph.get('coreModel')==core_model, 'CORE_MODEL_MISMATCH')
                self.kernel.validate_role(graph,'ready')
                if core_model=='rdg-decision-v1':self.check(not any(n['kind']=='evidence' for n in graph['objects']),'EVIDENCE_RETIRED_USE_CONTEXT')
            graph['id']='graph-'+ident;graph['identitySpace']=space;graph['revision']=1
            if graph.get('coreModel') != 'rdg-decision-v1':
                for node in graph['nodes']:
                    if node['kind']=='requirement':node['status']='potential'
                if role=='working':self.kernel.entities(graph)[graph['rootRequirementId']]['status']='active'
            else:
                root_id=graph.get('rootRequirementId')
                graph['events'].append({'id':str(uuid.uuid5(tx,'create')), 'type':'created',
                    'transactionId':str(tx), 'recordedAt':now(), 'by':attribution,
                    'nodeIds':[root_id] if root_id else [], 'basis':request.get('rootReason') or request['title']})
            if graph.get('coreModel')=='rdg-decision-v1':
                decision=self.kernel.for_graph(graph);e=graph['events'][-1];d=decision.HISTORY.detail(None,graph,'create',{'nodeId':root_id},decision,process=role=='working')
                if role=='working':
                    ids=sorted(i for i in decision.support_state(graph)['activeIds'] if decision.entities(graph)[i]['kind']=='requirement');d['activatedRequirementIds']=ids;d['subjects'].update({i:decision.HISTORY.snapshot(decision.entities(graph)[i]) for i in ids})
                e['historyDetail']=d
            self.kernel.validate_role(graph,role)
            values={'graph':graph,'role':role,'path':request['path'],'permissions':checks[-1]['permissions']}
            if role=='working' and graph.get('coreModel') != 'rdg-decision-v1':
                values['plan']=self.empty_plan(str(uuid.uuid5(tx,'plan')),space,graph['title'])
            if role=='lens':
                self.check(isinstance(request.get('lensKey'),str) and bool(request['lensKey'].strip()),'LENS_KEY_REQUIRED')
                self.check(not any(r.get('head',{}).get('lensKey')==request['lensKey'] for r in self.store.scan()),'DUPLICATE_LENS_KEY')
                values['lensKey']=request['lensKey']
            # Fundamental lenses and recommendation packages are namespace data,
            # not implicit side effects of creating a working process.
            # Validate explicitly provided package references without installing any.
            if graph['coreModel']=='rdg-decision-v1' and graph['recommendationPackageIds']:
                self.check(set(graph['recommendationPackageIds'])<=
                           {p['id'] for p in registry_read()['packages']},'REFERENCE_MISSING:recommendation')
            changes[ident]=values;effects={'createdPackageId':ident,'role':role}
        elif op=='lens_manage':
            self.check(set(request)=={'op','transactionId','targetPackageId','expectedPackageRevision',
                'expectedGraphRevision','confirmOwnerManagement','note'},'LENS_MANAGE_FIELDS')
            self.check(request['confirmOwnerManagement'] is True,'OWNER_MANAGEMENT_CONFIRMATION_REQUIRED')
            row=read(request['targetPackageId']);expected(row)
            lineage=row['head'].get('lineage',{})
            self.check(row['head']['role']=='lens' and row['graph']['coreModel']=='rdg-decision-v1' and
                lineage.get('supplied') is True and not lineage.get('userManaged'),'LENS_MANAGE_NOT_APPLICABLE')
            self.check(isinstance(request['note'],str) and bool(request['note'].strip()),'NOTE_REQUIRED')
            # Preserve supplied provenance and graph bytes. Only the owner-control
            # bit changes; prior heads and historical graph pins remain intact.
            new_lineage={**lineage,'userManaged':True,'managementTransactionId':str(tx)}
            change(row['packageId'],row,['graph.write','package.move'],lineage=new_lineage)
            effects={'adoptedLens':row['packageId'],'graphRevision':row['graph']['revision'],
                     'sourceSupplied':True,'userManaged':True}
        elif op in ('copy','insert_copy','capture_ready') or op=='apply_ready' and self.snapshot(request['sourcePackageId'],layouts=False)['graph']['coreModel']=='rdg-decision-v1':
            template=op in ('capture_ready','apply_ready')
            self.check(set(request)<={'op','transactionId','sourcePackageId','sourcePin','focus','includeDescendants','path',
                'targetPackageId','expectedPackageRevision','expectedGraphRevision','mode','targetRequirementId','parentRequirementId','targetWorkGraphId','role','lensKey','title','recommendationIds','note'},'COPY_FIELDS')
            source_id=request['sourcePackageId'];meta=self.metadata(source_id,['graph.read','package.copy'])
            source=read(source_id,'plan' in meta['head']['current']);add_check(source_id,['package.copy'],source['path'])
            self.check(request['sourcePin']=={'revision':source['head']['revision'],'sha256':self.model.digest(source['graph'])},'SOURCE_CAS_MISMATCH')
            if template:
                self.check(source['graph']['coreModel']=='rdg-decision-v1','UNSUPPORTED_PROFILE_CAPABILITY')
                if op=='apply_ready':self.check(source['head']['role']=='ready','READY_SOURCE_REQUIRED')
            focus=request.get('focus',{'kind':'graph'})
            self.check(isinstance(focus,dict) and set(focus)==({'kind'} if focus.get('kind')=='graph' else {'kind','id'}) and type(request.get('includeDescendants',True)) is bool,'COPY_FOCUS_SCHEMA')
            transferable=source['graph']
            if op=='capture_ready' and transferable['coreModel']=='rdg-decision-v1':
                transferable=copy.deepcopy(transferable)
                for node in transferable['nodes']:
                    if node['kind']=='decision':
                        node.pop('decisionContextIds',None);node.pop('contextNotes',None);node.pop('analysisSources',None)
                transferable['edges']=[edge for edge in transferable['edges']
                    if edge.get('dependencyPurpose')!='decisionContext']
            captured,inventory=self.model.fragment(source_id,transferable,focus,self.kernel,request.get('includeDescendants',True))
            mapping={kind:{old:str(uuid.uuid5(tx,kind+':'+old)) for old in ids} for kind,ids in self.model.definitions(captured).items()}
            target=None
            if op in ('copy','capture_ready'):
                ident=str(uuid.uuid5(tx,'package'));space=str(uuid.uuid5(tx,'identity-space'));graph_id='graph-'+ident
                destination=request['path'];permissions=['package.create','graph.write']+(['plan.create'] if source['plan'] and not template else [])
                add_check(ident,permissions,destination)
            else:
                ident=request['targetPackageId'];target=read(ident,True);expected(target)
                self.check(target['head']['role'] in ('working','copy'),'WORKING_TARGET_REQUIRED')
                self.check(target['graph']['coreModel']==source['graph']['coreModel'],'UNSUPPORTED_PROFILE_CAPABILITY')
                destination=target['path'];space=target['graph']['identitySpace'];graph_id=target['graph']['id'];permissions=['graph.write']
                add_check(ident,permissions,destination)
                if op=='apply_ready':
                    self.check(request.get('mode') in ('ADD_ROOT','REPLACE_R'),'APPLY_MODE')
                    if request['mode']=='REPLACE_R':
                        old_id=request.get('targetRequirementId');original_target=target
                        self.check(self.kernel.entities(target['graph']).get(old_id,{}).get('kind')=='requirement','REPLACE_REQUIREMENT_REQUIRED')
                        self.check(not request.get('parentRequirementId') or request['parentRequirementId']!=old_id,'REPLACE_PARENT_REMOVED')
                        removal=self.prepare({'op':'delete','transactionId':request['transactionId'],'targetPackageId':ident,
                            'expectedPackageRevision':target['head']['revision'],'expectedGraphRevision':target['graph']['revision'],
                            'nodeIds':[old_id],'note':request['note']},approval_actor=approval_actor,recorded_at=recorded_at)
                        checks.extend(removal['checks']);changes.update(removal['changes'])
                        for owner in removal['readset']:
                            if owner not in rows:rows[owner]=self.snapshot(owner,True)
                        target={**target,**{k:v for k,v in changes[ident].items() if k in ('graph','plan','layouts')}}

            graph,inventory=self.model.copy_graph(source_id,transferable,focus,mapping,space,graph_id,self.kernel,request.get('includeDescendants',True))
            for action in graph.get('externalActions',[]):
                for ref in action.get('subjectRefs',[]):
                    if ref.get('kind') in ('process','workGraph') and ref['packageId']==source_id:
                        ref.update(packageId=ident,identitySpace=space,graphRevision=graph['revision'],sha256=self.model.digest(graph))
            for question in graph['objects']:
                if question['kind']=='question':
                    for refs in [question['relatedRefs'],question['sourceRefs'],*(a['sourceRefs'] for a in question['answers']),*(h['previous']['sourceRefs'] for h in question.get('answerHistory',[]))]:
                        for ref in refs:
                            if ref.get('kind') in ('process','workGraph','lens'):ref['packageId']=ident
            imported_root=graph.get('rootRequirementId')
            if template:
                graph=self.model.decision_template(graph)
                if request.get('title'):graph['title']=request['title']
                if op=='capture_ready':graph['recommendationPackageIds']=request.get('recommendationIds',[])
            if graph['coreModel']=='rdg-decision-v1':
                remap_recommendations(graph,source,ident,mapping,template)
            if target and template and request.get('parentRequirementId'):
                parent=request['parentRequirementId'];self.check(self.kernel.entities(target['graph']).get(parent,{}).get('kind')=='requirement','REFERENCE_MISSING:parent')
                self.kernel.for_graph(target['graph']).guard(self.kernel.entities(target['graph'])[parent],event('insert-parent'),'link')
                graph['rootCauses']=[]
            scope=None
            if target:
                ev=event('insert-copy');ev.update(type='copy_inserted',sourcePackageId=source_id,sourcePin=copy.deepcopy(request['sourcePin']),idMap=mapping)
                graph,scope=self.model.insert_graph(target['graph'],graph,ev,str(uuid.uuid5(tx,'scope')),self.kernel)
                if template and request.get('parentRequirementId'):
                    graph['edges'].append({'id':str(uuid.uuid5(tx,'template-parent')),'type':'DERIVES','from':request['parentRequirementId'],'to':imported_root})
                    self.kernel.validate(graph)
                if op=='apply_ready' and request['mode']=='REPLACE_R':
                    old_graph=original_target['graph'];old_id=request['targetRequirementId']
                    if old_graph['rootRequirementId']==old_id:graph['rootRequirementId']=imported_root
                    old_scopes={w['id']:w for w in old_graph['workGraphs']}
                    for w in graph['workGraphs']:
                        if w['id'] in old_scopes:
                            previous=old_scopes[w['id']]
                            w['rootIds']=[imported_root if i==old_id else i for i in previous['rootIds']]
                            w['memberIds']=[imported_root if i==old_id else i for i in previous['memberIds']]
                    self.kernel.validate(graph)
                destination_scope=request.get('targetWorkGraphId')
                if destination_scope:
                    wg=next((w for w in graph['workGraphs'] if w['id']==destination_scope),None);self.check(wg is not None,'TARGET_WORK_GRAPH_UNKNOWN')
                    wg['memberIds']=sorted(set(wg['memberIds'])|{i for i in mapping['entity'].values() if i in self.kernel.entities(graph) and i not in {a['id'] for a in graph['externalActions']}})
                    self.kernel.validate(graph)

            plan=None;plan_context={}
            if source['plan'] is not None and not template:
                plan,plan_context=self.model.copy_plan(source['plan'],source_id,ident,graph,mapping)
                if target:
                    permission='plan.create' if target['plan'] is None else 'plan.edit'
                    if target['plan'] is not None:
                        step_map={step['id']:str(uuid.uuid5(tx,'step:'+step['id'])) for step in plan['steps']}
                        branch_field='forks' if plan['schemaVersion']==3 else 'branches'
                        branch_map={b['id']:str(uuid.uuid5(tx,'branch:'+b['id'])) for b in plan[branch_field]}
                        case_map={(b['id'],c['id']):str(uuid.uuid5(tx,'case:'+b['id']+':'+c['id'])) for b in plan[branch_field] for c in b['cases']}
                        plan=self.model.append_plan(target['plan'],plan,step_map,branch_map,case_map)
                    permissions.append(permission);add_check(ident,[permission]+(['plan.branch'] if source['plan'].get('forks',source['plan'].get('branches')) else []),destination)
                for step in plan['steps']:
                    ref=step['ref'];resolved=graph if ref['packageId']==ident else read(ref['packageId'])['graph']
                    node=self.kernel.entities(resolved).get(ref['nodeId'])
                    self.check(resolved['identitySpace']==ref['identitySpace'] and node and node['kind']==step['kind'],'COPY_PLAN_REFERENCE')
            prefix='provenance/'+source['headSHA256'];artifacts={prefix+'/package.json':source['headBytes']}
            directory=self.store.package_path(source['path']);source_inventory=self.store.inventory(source)
            if template:
                artifacts={prefix+'/definition.json':self.model.encoded(self.model.decision_template(source['graph']))}
            else:
                for relative in source_inventory:
                    raw=self.store.io.safe_path(directory,relative,True).read_bytes()
                    self.check(self.store.sha(raw)==source_inventory[relative],'COPY_SOURCE_BYTES_CHANGED')
                    artifacts[prefix+'/'+relative]=raw
                    if relative.startswith('evidence/'):artifacts[relative]=raw
            layout_report=None;layouts=None
            input_layouts=source['layouts'];translation=None
            if target and graph['coreModel']=='rdg-decision-v1':
                source_view=self.model.presentation(source['graph'],self.kernel)
                source_picture=self.layout('project',graph=source['graph'],view=source_view,document=source['layouts'])
                target_view=self.model.presentation(target['graph'],self.kernel)
                target_picture=self.layout('project',graph=target['graph'],view=target_view,document=target['layouts'])
                input_layouts=copy.deepcopy(source['layouts']) if source['layouts'] else self.layout('empty')
                input_layouts['layouts'][source_view['graphKey']]={'positions':source_picture['positions'],'occurrences':source_picture['occurrences']}
                source_points=[*source_picture['positions'].values(),*source_picture['occurrences'].values()]
                target_points=[*target_picture['positions'].values(),*target_picture['occurrences'].values()]
                translation={'x':max((p['x'] for p in target_points),default=0)-min((p['x'] for p in source_points),default=0)+300,'y':0}
            if input_layouts is not None:
                view_map={source['graph']['id']:(graph_id if graph['coreModel']=='rdg-decision-v1' else 'full-'+scope if target else graph_id)}
                for w in source['graph']['workGraphs']:view_map['full-'+w['id']]='full-'+mapping['workGraph'][w['id']] if w['id'] in mapping['workGraph'] else None
                remapped=self.layout('remap',document=input_layouts,spec={'sourceSpace':source['graph']['identitySpace'],**({'translation':translation} if translation else {}),
                    'targetSpace':space,'viewMap':view_map,'entityMap':{old:new for old,new in mapping['entity'].items() if new in self.kernel.entities(graph)},'profile':graph['coreModel'],
                    'sourceIds':list(self.kernel.entities(source['graph'])),'sourceSlugs':[source['graph']['id']],
                    'edgeMap':{old:new for old,new in {**mapping['edge'],**mapping.get('membership',{})}.items() if new in {e['id'] for e in self.visual_edges(graph)}},
                    'edgeEndpoints':{e['id']:{'from':e['from'],'to':e['to']} for e in self.visual_edges(source['graph'])}})
                layouts=remapped['document'];layout_report=remapped['report']
                if target and target['layouts'] is not None:
                    combined=copy.deepcopy(target['layouts'])
                    if graph['coreModel']=='rdg-decision-v1':
                        for key,value in layouts['layouts'].items():
                            original=combined['layouts'].setdefault(key,{'positions':{},'occurrences':{}})
                            original['positions'].update(value['positions']);original.setdefault('occurrences',{}).update(value.get('occurrences',{}))
                    else:
                        self.check(not set(combined['layouts'])&set(layouts['layouts']),'INSERT_LAYOUT_COLLISION');combined['layouts'].update(layouts['layouts'])
                    combined['revision']+=1;layouts=self.layout('validate',document=combined)
            values={'graph':graph,'artifacts':artifacts}
            if target and ident in changes:
                for k in ('plan','layouts'):
                    if k in changes[ident]:values[k]=changes[ident][k]
                permissions=list(dict.fromkeys(permissions+changes[ident]['permissions']))
            if plan is not None:values['plan']=plan
            if layouts is not None:values['layouts']=layouts
            lineage={'kind':op,'source':{'packageId':source_id,'identitySpace':source['graph']['identitySpace'],
                'packageRevision':source['head']['revision'],'headSHA256':source['headSHA256'],'graphSHA256':self.model.digest(source['graph'])},
                'snapshotPrefix':prefix,'focus':focus,'idMap':mapping}
            if target:change(ident,target,permissions,**values)
            else:
                role=request.get('role','ready') if op=='capture_ready' else 'copy'
                self.check(role in ('ready','lens','copy'),'COPY_ROLE')
                if role in ('ready','lens'):self.kernel.validate_role(graph,role)
                changes[ident]={'path':destination,'role':role,'permissions':permissions,'lineage':lineage,**values}
                if role=='lens':
                    self.check(isinstance(request.get('lensKey'),str) and request['lensKey'].strip(),'LENS_KEY_REQUIRED')
                    changes[ident]['lensKey']=request['lensKey']
            effects={'operation':op,'createdPackageId':ident if not target else None,'idMap':mapping,'capture':inventory,
                'boundaryReferences':graph.get('externalRefs',[]),'planContext':plan_context,'layouts':layout_report,'insertedWorkGraphId':scope}
        elif op=='external_edit':
            self.check(set(request)<={'op','transactionId','targetPackageId','expectedPackageRevision','expectedGraphRevision',
                'referenceId','target','remove','note'},'EXTERNAL_EDIT_FIELDS')
            row=read(request['targetPackageId']);expected(row);ident=row['packageId']
            self.check(row['head']['role'] in ('working','copy'),'WORKING_TARGET_REQUIRED')
            graph=copy.deepcopy(row['graph']);record=next((r for r in graph.get('externalRefs',[]) if r['id']==request['referenceId']),None)
            self.check(record is not None,'EXTERNAL_REFERENCE_NOT_FOUND');before=copy.deepcopy(record)
            if request.get('remove') is True:
                self.check('target' not in request,'EXTERNAL_EDIT_CHOICE')
                graph['externalRefs'].remove(record)
            else:
                self.check('remove' not in request,'EXTERNAL_EDIT_CHOICE')
                ref=request['target'];self.model.validate_reference(ref);target=read(ref['packageId'])
                self.check(ref==self.model.reference(ref['packageId'],target['graph'],ref['nodeId']),'EXTERNAL_OBSERVED_SOURCE_CHANGED')
                node=self.kernel.entities(target['graph'])[ref['nodeId']]
                self.check(node['kind']==record['observed']['kind'],'EXTERNAL_REBIND_KIND')
                record.update(target=copy.deepcopy(ref),observed=copy.deepcopy(node))
            ev=event('external-edit');ev.update(type='external_reference_edited',previousReference=before,
                newReference=None if request.get('remove') else copy.deepcopy(record))
            if graph['coreModel']=='rdg-decision-v1':
                graph,affected=self.kernel.for_graph(graph).edit_external_reference(row['graph'],request['referenceId'],None if request.get('remove') else record,ev)
            else:
                affected={before['localId']}|self.kernel.affected(graph,graph,{before['localId']})
                for nid in affected:
                    node=self.kernel.entities(graph)[nid];review=node.setdefault('review',{'required':True,'causes':[]})
                    review['required']=True;review['causes'].append({'eventId':ev['id'],'sourceRef':before['target'],'reason':'external-reference-edited'})
                ev['affectedIds']=sorted(affected)
                graph['events'].append(ev);graph['revision']+=1
            self.model.validate_graph_payload(graph,self.kernel)
            change(ident,row,['graph.write'],graph=graph);effects={'reviewIds':sorted(affected)}
        elif op=='layout_edit':
            self.check(set(request)=={'op','transactionId','targetPackageId','expectedPackageRevision','expectedLayoutRevision','commands'},'LAYOUT_FIELDS')
            row=read(request['targetPackageId']);ident=row['packageId']
            self.check(row['head']['revision']==request['expectedPackageRevision'],'PACKAGE_CAS_MISMATCH')
            original=row['layouts'] if row['layouts'] is not None else self.layout('empty')
            layouts=self.layout('apply',document=original,commands=request['commands'],expectedRevision=request['expectedLayoutRevision'])
            graph=row['graph'];decision=graph['coreModel']=='rdg-decision-v1'
            layout_ids={n['id'] for n in graph['nodes']+graph['objects']}
            if decision:
                key=self.model.presentation(graph,self.kernel)['graphKey']
                self.check(all(k==key for k in layouts['layouts']), 'LAYOUT_SCOPE')
                self.check(all(all(o.get('entityId') in layout_ids for o in v.get('occurrences',{}).values()) for v in layouts['layouts'].values()), 'LAYOUT_SCOPE')
                self.check(all(set(v.get('positions',{}))<=layout_ids for v in layouts['layouts'].values()), 'LAYOUT_SCOPE')
            views={graph['id']:graph['id'],**({} if decision else {'full-'+w['id']:'full-'+w['id'] for w in graph['workGraphs']})}
            check=self.layout('remap',document=layouts,spec={'sourceSpace':graph['identitySpace'],'targetSpace':graph['identitySpace'],
                'viewMap':views,'entityMap':{i:i for i in self.kernel.entities(graph)},'sourceIds':list(self.kernel.entities(graph)),'sourceSlugs':[graph['id']],
                'edgeMap':{e['id']:e['id'] for e in self.visual_edges(graph)},
                'edgeEndpoints':{e['id']:{'from':e['from'],'to':e['to']} for e in self.visual_edges(graph)}})
            self.check(not check['report']['skippedKeys'] and not check['report']['skippedPositionIds'],'LAYOUT_SCOPE')
            change(ident,row,['graph.write'],layouts=layouts);effects={'layoutRevision':layouts['revision']}
        elif op == 'delete' and self.snapshot(request['targetPackageId'],layouts=False)['graph'].get('coreModel') == 'rdg-decision-v1':
            self.check(set(request) == {'op','transactionId','targetPackageId',
                'expectedPackageRevision','expectedGraphRevision','nodeIds','note'}, 'DELETE_FIELDS')
            target=self.snapshot(request['targetPackageId'],True)
            ident=target['packageId'];rows[ident]=target
            add_check(ident,['graph.read'],target['path'])
            expected(target)
            self.check(target['head']['role'] in ('working','copy'), 'WORKING_TARGET_REQUIRED')
            removed=request['nodeIds']
            self.check(isinstance(removed,list) and bool(removed) and
                all(isinstance(i,str) and i.strip() for i in removed) and
                len(removed)==len(set(removed)), 'DELETE_TARGETS')
            # All current placement/layout participants are inventoried under this barrier.
            # Conservative incoming closure before invoking the pure reducer.
            # Prepare Plan/layout and qualified boundary changes as one transaction.
            all_rows=self.store.scan()
            self.check(self.store.initialized() and all(r['health'] in
                ('metadata-verified','unaccepted-stage') for r in all_rows), 'INCOMING_INVENTORY_UNHEALTHY')
            for meta in all_rows:
                if meta['health']=='unaccepted-stage':continue
                other=meta['packageId']
                if other == ident:continue
                add_check(other,['graph.read'],meta['path'])
                foreign=self.snapshot(other,layouts=False);rows[other]=foreign
                for ref in foreign['graph'].get('externalRefs',[]):
                    pin=ref.get('target',{})
                    if pin.get('mode')=='current' and pin.get('packageId')==ident and pin.get('identitySpace')==target['graph']['identitySpace'] and pin.get('nodeId') in removed:
                        self.check(foreign['graph']['coreModel']=='rdg-decision-v1','INCOMING_CURRENT_REFERENCE_REQUIRES_COORDINATION')
                        replacement=copy.deepcopy(ref);replacement['target']['mode']='historical';replacement['reason']='source-entity-deleted'
                        base=changes.get(other,{}).get('graph',foreign['graph'])
                        altered,_=self.kernel.for_graph(base).edit_external_reference(base,ref['id'],replacement,event('incoming:'+other+':'+ref['id']))
                        change(other,foreign,['graph.write'],graph=altered)
                if 'plan' in foreign['head']['current']:
                    add_check(other,['plan.read'],meta['path'])
                    plan_row=self.store.read(other,include_graph=False,include_layouts=False)
                    self.model.validate_plan(plan_row['plan'])
                    cleaned,step_ids=self.model.remove_plan_references(plan_row['plan'],ident,target['graph']['identitySpace'],removed)
                    if step_ids:
                        previous=changes.get(other)
                        if previous:
                            add_check(other,['plan.edit'],plan_row['path']);previous['permissions']=list(dict.fromkeys(previous['permissions']+['plan.edit']));previous['plan']=cleaned
                        else:change(other,plan_row,['plan.edit'],plan=cleaned)
            ev=event('delete')
            before_graph=copy.deepcopy(target['graph'])
            graph,_=self.kernel.apply(before_graph, {'schemaVersion':1,
                'expectedRevision':before_graph['revision'],
                'operations':[{'op':'graph_edit','action':'core_remove',
                    'data':{'nodeIds':removed},'event':ev}]}, True, coordinated=True)
            self.model.validate_graph_payload(graph,self.kernel)
            self.kernel.validate_role(graph,target['head']['role'])
            values={'graph':graph}
            if target['plan'] is not None:
                cleaned,step_ids=self.model.remove_plan_references(target['plan'],ident,before_graph['identitySpace'],removed)
                if cleaned['schemaVersion']==3:
                    for fork in cleaned['forks']:
                        for case in fork['cases']:case['decisionIds']=[i for i in case['decisionIds'] if i not in removed]
                if step_ids or cleaned!=target['plan']:
                    if cleaned['revision']==target['plan']['revision']:cleaned['revision']+=1
                    add_check(ident,['plan.read','plan.edit'],target['path']);values['plan']=cleaned
            if target['layouts'] is not None:
                old_ids=set(self.kernel.entities(before_graph));new_ids=set(self.kernel.entities(graph));old_edges=self.visual_edges(before_graph)
                cleaned=self.layout('remap',document=target['layouts'],spec={'sourceSpace':before_graph['identitySpace'],'targetSpace':graph['identitySpace'],
                    'viewMap':{graph['id']:graph['id']},'entityMap':{i:i for i in new_ids},'sourceIds':sorted(old_ids),'sourceSlugs':[graph['id']],
                    'edgeMap':{e['id']:e['id'] for e in self.visual_edges(graph)},'edgeEndpoints':{e['id']:{'from':e['from'],'to':e['to']} for e in old_edges}})['document']
                cleaned['revision']=target['layouts']['revision']+1;values['layouts']=cleaned
            change(ident,target,['graph.write'],**values)
            effects=self.decision_effects(before_graph,graph)
        elif op=='unlink' and self.snapshot(request['targetPackageId'],layouts=False)['graph']['coreModel']=='rdg-decision-v1':
            self.check(set(request)=={'op','transactionId','targetPackageId','expectedPackageRevision','expectedGraphRevision','data','note'},'UNLINK_FIELDS')
            reduced={**request,'op':'core','command':'unlink'}
            return self.prepare(reduced,approval_actor=approval_actor,recorded_at=recorded_at)
        elif op in ('apply_ready','delete','unlink'):
            allowed={'op','transactionId','targetPackageId','expectedPackageRevision','expectedGraphRevision','note',
                'sourcePackageId','sourcePin','mode','targetRequirementId','targetWorkGraphId','nodeIds','data'}
            self.check(set(request)<=allowed,'PORTABLE_COMMAND_FIELDS')
            target=read(request['targetPackageId']);expected(target)
            self.check(target['head']['role'] in ('working','copy'),'WORKING_TARGET_REQUIRED')
            if op=='apply_ready':
                source=read(request['sourcePackageId'])
                allocation={'idMap':{kind:{old:str(uuid.uuid5(tx,kind+':'+old)) for old in ids}
                            for kind,ids in self.model.definitions(source['graph']).items()},
                    'eventId':str(uuid.uuid5(tx,'apply')),'removalEventId':str(uuid.uuid5(tx,'remove')),
                    'scopeId':str(uuid.uuid5(tx,'scope')),'recordedAt':now()}
            else:allocation={'eventId':str(uuid.uuid5(tx,op)),'recordedAt':now()}
            plans={};all_rows=self.store.scan()
            self.check(all(r['health'] in ('metadata-verified','unaccepted-stage') for r in all_rows),'INCOMING_INVENTORY_UNHEALTHY')
            needs_closure=op=='delete' or op=='apply_ready' and request.get('mode')=='REPLACE_R'
            if needs_closure:
                self.check(self.store.initialized(),'NAMESPACE_NOT_REGISTERED')
                for row in all_rows:
                    if row['health']=='unaccepted-stage':continue
                    if 'plan' not in row['head']['current']:continue
                    ident=row['packageId'];add_check(ident,['plan.read'],row['path'])
                    plan_row=self.store.read(ident,include_graph=False,include_layouts=False)
                    self.model.validate_plan(plan_row['plan']);rows.setdefault(ident,plan_row)
                    plans[ident]={'plan':plan_row['plan']}
            snapshots={'packages':{i:{'graph':r['graph'],'role':r['head']['role'],'revision':r['head']['revision']}
                       for i,r in rows.items() if r['graph'] is not None},'plans':plans,'incomingComplete':needs_closure}
            effects=self.model.prepare_effects(request,snapshots,{'kernel':self.kernel,'attribution':attribution,
                'eventContext':({'authorityPrincipal':approval_actor['authorityPrincipal'],
                                 'verifiedTrustReceipt':trust} if approval_actor else {})},allocation).value
            for ident,graph in effects['graphs'].items():change(ident,rows[ident],['graph.write'],graph=graph)
            for ident,plan in effects['plans'].items():
                if ident in changes:
                    changes[ident]['plan']=plan;changes[ident]['permissions'].append('plan.edit');add_check(ident,['plan.edit'],rows[ident]['path'])
                else:change(ident,rows[ident],['plan.edit'],plan=plan)
        elif op in ('dependency_add','dependency_remove') and self.snapshot(request['targetPackageId'],layouts=False)['graph']['coreModel']=='rdg-decision-v1':
            allowed={'op','transactionId','targetPackageId','expectedPackageRevision','expectedGraphRevision',
                     'sourceId','dependentId','dependencyLevel','dependencyRule','dependencyPurpose','contextComment','edgeId','disposition','note'}
            self.check(set(request)<=allowed,'DEPENDENCY_FIELDS')
            if op=='dependency_add':
                relation={'id':str(uuid.uuid5(tx,'dependency')),'type':'DEPENDS_ON',
                          'from':request['sourceId'],'to':request['dependentId']}
                if 'dependencyRule' in request:
                    relation['dependencyRule']=copy.deepcopy(request['dependencyRule'])
                else:relation['dependencyLevel']=request['dependencyLevel']
                if 'dependencyPurpose' in request:relation['dependencyPurpose']=request['dependencyPurpose']
                data={'relation':relation};command='link'
                if relation.get('dependencyPurpose')=='decisionContext':
                    command='decision_context';data={'nodeId':request['dependentId'],'sourceId':request['sourceId'],'action':'save','comment':request.get('contextComment',''),'rule':relation.get('dependencyRule',{'preset':relation.get('dependencyLevel','L1'),'watch':['definition']+(['directScope'] if relation.get('dependencyLevel')=='L2' else [])})}
            else:data={'edgeId':request['edgeId']};command='unlink'
            reduced={k:request[k] for k in ('transactionId','targetPackageId','expectedPackageRevision','expectedGraphRevision','note')};reduced.update(op='core',command=command,data=data)
            return self.prepare(reduced,approval_actor=approval_actor,recorded_at=recorded_at)
        elif op in ('dependency_add','dependency_remove'):
            allowed = {'op','transactionId','targetPackageId','expectedPackageRevision',
                       'expectedGraphRevision','sourceId','dependentId','dependencyLevel',
                       'edgeId','disposition','note'}
            self.check(set(request) <= allowed, 'DEPENDENCY_FIELDS')
            row=read(request['targetPackageId']);expected(row);ident=row['packageId']
            self.check(row['head']['role'] in ('working','copy'), 'WORKING_DEPENDENCY_REQUIRED')
            if op == 'dependency_add':
                self.check(all(isinstance(request.get(k), str) and request[k].strip()
                               for k in ('sourceId','dependentId')), 'DEPENDENCY_ENDPOINTS')
                data={'edge': {'id': str(uuid.uuid5(tx, 'dependency')),
                               'type': 'DEPENDS_ON', 'from': request['sourceId'],
                               'to': request['dependentId'],
                               'dependencyLevel': request['dependencyLevel']}}
            else:
                self.check(isinstance(request.get('edgeId'), str) and request['edgeId'].strip()
                           and isinstance(request.get('disposition'), str)
                           and request['disposition'].strip(), 'DEPENDENCY_REMOVE')
                data={'edgeId': request['edgeId'], 'disposition': request['disposition']}
            ev=event('dependency')
            graph,_=self.kernel.apply(row['graph'], {'schemaVersion':1,
                'expectedRevision':row['graph']['revision'],
                'operations':[{'op':'graph_edit','action':'core_'+op,
                               'data':data,'event':ev}]}, True)
            self.model.validate_graph_payload(graph,self.kernel)
            self.kernel.validate_role(graph,row['head']['role'])
            change(ident,row,['graph.write'],graph=graph)
            effects={'dependencyOperation':op,'edgeId':data.get('edge',{}).get('id',data.get('edgeId'))}
        elif op in ('lock_set','lock_remove'):
            allowed = {'op','transactionId','targetPackageId','expectedPackageRevision',
                       'expectedGraphRevision','nodeId','operation','mode','principals',
                       'message','disposition','authorityPrincipal','note'}
            self.check(set(request) <= allowed, 'LOCK_FIELDS')
            self.check(attribution == 'user', 'LOCK_USER_PATH_REQUIRED')
            principal = approval_actor['authorityPrincipal'] if approval_actor else request.get('authorityPrincipal')
            self.check(not approval_actor or request.get('authorityPrincipal') in (None, '', principal),
                       'APPROVAL_PRINCIPAL_MISMATCH')
            self.check(isinstance(principal, str) and principal.strip(), 'LOCK_PRINCIPAL_REQUIRED')
            row=read(request['targetPackageId']);expected(row);ident=row['packageId']
            self.check(row['head']['role'] in ('working','copy'), 'WORKING_LOCK_REQUIRED')
            ev=event('lock');ev['authorityPrincipal']=principal
            if op == 'lock_set':
                data={'nodeId':request['nodeId'],'operation':request['operation'],
                      'mode':request['mode'],'principals':request['principals'],
                      'message':request['message']}
            else:
                data={'nodeId':request['nodeId'],'operation':request['operation'],
                      'disposition':request['disposition']}
            graph,_=self.kernel.apply(row['graph'], {'schemaVersion':1,
                'expectedRevision':row['graph']['revision'],
                'operations':[{'op':'graph_edit','action':'core_'+op,
                               'data':data,'event':ev}]}, True)
            self.model.validate_graph_payload(graph,self.kernel)
            self.kernel.validate_role(graph,row['head']['role'])
            change(ident,row,['graph.write'],graph=graph)
            effects={'lockOperation':op,'nodeId':request['nodeId'],
                     'operation':request['operation']}
        elif op=='plan_action':
            self.check(set(request)<={'op','transactionId','targetPackageId','expectedPackageRevision','expectedGraphRevision','expectedPlanRevision','entity','placement','note'},'PLAN_ACTION_FIELDS')
            row=read(request['targetPackageId'],True)
            reduced={k:copy.deepcopy(v) for k,v in request.items() if k not in ('entity','placement')}
            reduced['op']='batch';reduced['steps']=[]
            if row['plan'] is None:reduced['steps'].append({'alias':'plan','op':'plan_create','title':row['graph']['title']})
            reduced['steps'].append({'alias':'action','op':'plan_action','entity':request['entity'],'placement':request.get('placement',{})})
            prepared=self.prepare(reduced,approval_actor=approval_actor,recorded_at=recorded_at)
            effects=prepared['effects'];effects.update(operation='plan_action',actionId=effects['aliasIds']['action'],placementId=effects['aliasIds']['actionPlacement'])
            for change_ in prepared['changes'].values():change_['effects'].update(effects)
            return prepared
        elif op in ('core','paper_edit'):
            self.check(set(request)<={'op','transactionId','targetPackageId','expectedPackageRevision','expectedGraphRevision',
                'command','data','note','reasonForReconsideration','evidenceRefs','expectedDependencyCatalogRevision'},'CORE_FIELDS')
            row=read(request['targetPackageId']);expected(row);ident=row['packageId'];command=request['command']
            self.check(command in self.kernel.commands_for(row['graph']) and command not in ('remove','recommendation_packages','lens_application'),'CORE_COMMAND')
            paper=row['head']['role'] in ('ready','lens');self.check((op=='paper_edit')==paper,'DOCUMENT_ROLE_COMMAND')
            if paper:
                self.check(command in self.authoring_commands(row['graph'],row['head']['role']),'PAPER_COMMAND')
            if command in ('select','complete','review','assess'):
                boundary=self.boundaries(row,read)
                targets=set(request['data'].get('nodeIds',[])) | {request['data'].get('nodeId')}
                self.check(not targets & set(boundary['reviewIds']),'EXTERNAL_DEPENDENCY_REVIEW_REQUIRED')
                if command=='select':self.check(not targets & set(boundary['conflictIds']),'EXTERNAL_EXCLUSION_CONFLICT')
            if row['graph'].get('coreModel')=='rdg-decision-v1':
                self.kernel.for_graph(row['graph']).QUESTIONS.require_owner_inputs(command,request['data'],ident,row['graph'],self.kernel.for_graph(row['graph']),self.model)
                self.validate_action_subjects(command,request['data'],ident,row['graph'],read)
            ev=event('core');self.verify_evidence(row,ev.get('evidenceRefs',[]))
            if row['graph'].get('coreModel') == 'rdg-decision-v1' and command == 'review':
                ev['reviewPinContext']={'packageId':ident,
                    'graphRevision':row['graph']['revision'],
                    'sha256':self.model.digest(row['graph'])}
            if row['graph'].get('coreModel') == 'rdg-decision-v1' and command in ('complete','finding_disposition'):
                if 'plan' in row['head']['current']:
                    plan_row=read(ident,True)
                    ev['placementIds']=[s['id'] for s in plan_row['plan']['steps'] if s['ref']['packageId']==ident and s['ref']['nodeId']==request['data'].get('nodeId')]
                else:ev['placementIds']=[]
                defined=self.kernel.entities(row['graph'])
                pins=[defined[i]['artifact'] for i in (request['data'].get('disposition',{}).get('evidenceIds',[]) if command=='finding_disposition' else request['data'].get('evidenceIds',[]))
                      if i in defined and defined[i]['kind'] in ('context','evidence') and 'artifact' in defined[i]]
                self.check(all(pin in ev.get('evidenceRefs',[]) for pin in pins),
                           'EVIDENCE_ARTIFACT_PIN_NOT_VERIFIED')
                self.verify_evidence(row,pins)
            policy_data=copy.deepcopy(request['data'])
            policy_catalog_changed=False
            if 'expectedDependencyCatalogRevision' in request:
                self.check(type(request['expectedDependencyCatalogRevision']) is int and request['expectedDependencyCatalogRevision']>=0,'DEPENDENCY_CATALOG_CAS')
                self.check(request['expectedDependencyCatalogRevision']==registry_read()['revision'],'DEPENDENCY_CATALOG_CAS')
            if row['graph'].get('coreModel')=='rdg-decision-v1' and command=='policy_change' and policy_data.get('action') not in ('binding_activate','binding_disable','binding_remove','automatic_activate','automatic_disable','automatic_remove') and not (policy_data.get('action')=='binding_save' and str(policy_data.get('value',{}).get('policyId','')).startswith('builtin:')):
                decision=self.kernel.for_graph(row['graph']);reg=registry_read()
                if 'expectedDependencyCatalogRevision' in request:
                    self.check(request['expectedDependencyCatalogRevision']==reg['revision'],'DEPENDENCY_CATALOG_CAS')
                definitions=reg.setdefault('dependencyPolicies',[]);action=policy_data.get('action');value=policy_data.get('value',{})
                if action=='catalog_migrate':
                    local=copy.deepcopy(row['graph'].get('dependencyPolicies',[]));remap={}
                    for pid in sorted({p['id'] for p in local}):
                        group=[p for p in local if p['id']==pid]
                        collisions=[p for p in definitions if p['id']==pid and any(q['version']==p['version'] and q!=p for q in group)]
                        if collisions:remap[pid]=str(uuid.uuid5(uuid.UUID(ident),'dependency-policy:'+pid+':'+self.model.digest(group)))
                        for definition in group:
                            definition['id']=remap.get(pid,pid)
                            if not any(p['id']==definition['id'] and p['version']==definition['version'] for p in definitions):definitions.append(definition)
                    for pre in row['graph'].get('dependencyPresets',[]):
                        pid=str(uuid.uuid5(uuid.UUID(ident),'dependency-preset:'+pre['id']))
                        if any(p['id']==pid for p in definitions):continue
                        rules=[{'id':'watch-'+w,'name':decision.POLICIES.WATCHES[w][0],'watch':w,
                            'operations':[op for op in pre['operations'] if op in decision.POLICIES.WATCHES[w][2]],'enabled':True} for w in pre['watch']]
                        rules=[r for r in rules if r['operations']]
                        definitions.append({'id':pid,'version':1,'name':pre['name'],'description':'Перенесённая пользовательская политика',
                            'status':'active','pattern':'direct','sourceKinds':pre['sourceKinds'],
                            'targetKinds':sorted(decision.NODE_KINDS),'rules':rules})
                    row=copy.deepcopy(row)
                    row['graph'].setdefault('dependencyPolicyAliases',{}).update(remap)
                    for binding in row['graph'].get('dependencyBindings',[]):binding['policyId']=remap.get(binding['policyId'],binding['policyId'])
                    row['graph']['dependencyPolicies']=[{**p,'id':remap.get(p['id'],p['id'])} for p in local]
                    policy_catalog_changed=True
                elif action=='policy_save':
                    self.check(not value.get('id','').startswith('builtin:'),'POLICY_SYSTEM_IMMUTABLE')
                    # Saving a new version also preserves its existing local version chain.
                    for old in row['graph'].get('dependencyPolicies',[]):
                        if old['id']==value.get('id') and not any(p['id']==old['id'] and p['version']==old['version'] for p in definitions):definitions.append(copy.deepcopy(old))
                    versions=[p['version'] for p in definitions if p['id']==value.get('id')]
                    self.check(value.get('version')==max(versions,default=0)+1,'POLICY_VERSION_CONFLICT')
                    decision.POLICIES.validate_definition(value,decision);definitions.append(copy.deepcopy(value));policy_catalog_changed=True
                elif action=='policy_status':
                    definition=next((p for p in definitions if p['id']==value.get('id') and p['version']==value.get('version')),None)
                    self.check(definition is not None and not definition['id'].startswith('builtin:') and value.get('status') in ('active','disabled','archived'),'POLICY_STATUS')
                    definition['status']=value['status'];policy_catalog_changed=True
                    # All affected Graphs join the same existing multi-head transaction.
                    for metadata in self.store.scan():
                        other_id=metadata.get('packageId')
                        if not other_id or other_id==ident:continue
                        other=self.snapshot(other_id,False,layouts=False)
                        if other['head']['role'] not in ('working','copy'):continue
                        if not any(b['policyId']==value['id'] and b['policyVersion']==value['version'] and b.get('status')!='deleted' for b in other['graph'].get('dependencyBindings',[])):continue
                        other=read(other_id)
                        changed_graph,_=self.kernel.apply(other['graph'],{'schemaVersion':1,'expectedRevision':other['graph']['revision'],
                            'operations':[{'op':'graph_edit','action':'core_policy_change','data':policy_data,'event':event('policy-status:'+other_id)}]},True)
                        change(other_id,other,['graph.write'],graph=changed_graph)
                if policy_catalog_changed:
                    decision.validate_policy_definitions(definitions);reg['revision']+=1;registry_write()
                # Import immutable versions to the Graph only as execution/history pins.
                row=copy.deepcopy(row);local={(p['id'],p['version']):p for p in row['graph'].get('dependencyPolicies',[])}
                needed=set(local)
                if action=='binding_save':needed.add((value.get('policyId'),value.get('policyVersion')))
                if action=='policy_save':needed.update((p['id'],p['version']) for p in definitions if p['id']==value['id'] and p['version']<value['version'])
                needed.update((p['id'],p['version']) for p in definitions if any(p['id']==pid and p['version']<=version for pid,version in list(needed)))
                for definition in definitions:
                    key=(definition['id'],definition['version'])
                    if key in needed:
                        prior=local.get(key)
                        self.check(prior is None or {k:v for k,v in prior.items() if k!='status'}=={k:v for k,v in definition.items() if k!='status'},'POLICY_IDENTITY_CONFLICT_USE_MIGRATION')
                        local[key]=copy.deepcopy(definition)
                row['graph']['dependencyPolicies']=list(local.values())
                self.check(action!='binding_save' or any(p['id']==value.get('policyId') and p['version']==value.get('policyVersion') for p in definitions+decision.POLICIES.builtins(decision)), 'POLICY_NOT_IN_SHARED_CATALOG')
            before_graph=copy.deepcopy(row['graph'])
            graph,_=self.kernel.apply(row['graph'],{'schemaVersion':1,'expectedRevision':row['graph']['revision'],
                'operations':[{'op':'graph_edit','action':'core_'+command,'data':policy_data,'event':ev}]},
                True, coordinated=(command == 'remove'), paper=paper)
            if paper:
                graph['events']=[]
                for node in self.kernel.entities(graph).values():
                    node.pop('review',None)
                    if graph.get('coreModel') == 'rdg-decision-v1':
                        if node['kind'] in ('requirement','decision','action'):
                            node['result']={'state':'open','truth':'unknown'}
                        if node['kind']=='decision' and node['selectionState']=='selected':
                            node['selectionState']='unselected'
                    elif node['kind']=='requirement':
                        node['status']='potential'
            self.model.validate_graph_payload(graph,self.kernel)
            self.kernel.validate_role(graph,row['head']['role'])
            change(ident,row,['graph.write'],graph=graph)
            effects=(self.decision_effects(before_graph,graph) if graph.get('coreModel') == 'rdg-decision-v1'
                     else {'detached':self.kernel.detached_components(graph)})
        elif op in ('place','unplace'):
            self.check(set(request)<={'op','transactionId','targetPackageId','expectedPackageRevision','expectedPlanRevision',
                'nodePackageId','nodeId','stepId','at','deadline','afterStepId','caseId','note'},'PLACEMENT_FIELDS')
            owner=read(request['targetPackageId'],True)
            self.check(owner['plan'] is not None,'PLAN_OWNER_REQUIRED')
            self.check(owner['head']['revision']==request['expectedPackageRevision'] and owner['plan']['revision']==request['expectedPlanRevision'],'PLAN_CAS_MISMATCH')
            ref=node=None;spec=copy.deepcopy(request)
            if op=='place':
                source=read(request.get('nodePackageId',request['targetPackageId']))
                self.check(source['head']['role'] in ('working','copy'),'WORKING_PLAN_REQUIRED')
                node=self.kernel.entities(source['graph']).get(request['nodeId']);self.check(node is not None,'PLACEMENT_NODE_UNKNOWN')
                if owner['plan']['schemaVersion']==3:
                    self.check(source['packageId']==owner['packageId'], 'UNSUPPORTED_PROFILE_CAPABILITY:cross-owner-plan')
                ref=self.model.reference(source['packageId'],source['graph'],node['id'])
                spec.setdefault('stepId',str(uuid.uuid5(tx,'placement')))
            plan=self.model.place(owner['plan'],spec,ref,node)
            reduced={'op':'plan_edit','transactionId':request['transactionId'],'targetPackageId':request['targetPackageId'],
                'expectedPackageRevision':request['expectedPackageRevision'],'expectedPlanRevision':request['expectedPlanRevision'],'plan':plan}
            prepared=self.prepare(reduced, approval_actor=approval_actor, recorded_at=recorded_at)
            # The user's original logical request owns the receipt/idempotency key.
            prepared['effects']['placementId']=spec.get('stepId')
            for changed in prepared['changes'].values():changed['effects']['placementId']=spec.get('stepId')
            return prepared
        elif op=='plan_create':
            self.check(set(request)=={'op','transactionId','targetPackageId','expectedPackageRevision','title'},'PLAN_CREATE_FIELDS')
            row=read(request['targetPackageId'],True);ident=row['packageId']
            self.check(row['head']['role'] in ('working','copy') and row['plan'] is None,'PLAN_ALREADY_EXISTS_OR_PAPER')
            self.check(row['head']['revision']==request['expectedPackageRevision'],'PACKAGE_CAS_MISMATCH')
            self.check(isinstance(request['title'],str) and bool(request['title'].strip()),'PLAN_TITLE_REQUIRED')
            plan=self.empty_plan(str(uuid.uuid5(tx,'plan')),row['graph']['identitySpace'],request['title'],
                decision=row['graph']['coreModel']=='rdg-decision-v1')
            change(ident,row,['plan.create'],plan=plan);effects={'planRevision':1,'createdPlanId':plan['id']}
        elif op=='plan_edit':
            self.check(set(request)=={'op','transactionId','targetPackageId','expectedPackageRevision','expectedPlanRevision','plan'},'PLAN_FIELDS')
            ident=request['targetPackageId']
            profile_row=self.snapshot(ident,layouts=False)
            decision=profile_row['graph']['coreModel']=='rdg-decision-v1'
            meta=self.metadata(ident,['plan.read','plan.edit'])
            self.check(meta['head']['role'] in ('working','copy'),'WORKING_PLAN_REQUIRED')
            add_check(ident,['plan.read'],meta['path'])
            row=self.store.read(ident,include_graph=False,include_layouts=False);rows[ident]=row
            self.check(row['head']['revision']==request['expectedPackageRevision'] and row['plan']['revision']==request['expectedPlanRevision'],'PLAN_CAS_MISMATCH')
            plan=copy.deepcopy(request['plan']);self.model.validate_plan(plan)
            self.check(plan['schemaVersion']==(3 if decision else 2), 'PLAN_PROFILE_VERSION')
            self.check(all(plan[k]==row['plan'][k] for k in ('id','identitySpace')) and plan['revision']==row['plan']['revision']+1,'PLAN_OWNER_IMMUTABLE')
            for step in plan['steps']:
                ref=step['ref']
                if decision:self.check(ref['packageId']==ident, 'UNSUPPORTED_PROFILE_CAPABILITY:cross-owner-plan')
                target=read(ref['packageId']);node=self.kernel.entities(target['graph']).get(ref['nodeId'])
                self.check((target['graph']['coreModel']=='rdg-decision-v1')==decision, 'UNSUPPORTED_PROFILE_CAPABILITY:plan-source-profile')
                self.check(target['head']['role'] in ('working','copy') and target['graph']['identitySpace']==ref['identitySpace'] and node and node['kind']==step['kind'],'PLAN_REFERENCE_MISMATCH')
                prior=next((s for s in row['plan']['steps'] if s['id']==step['id']),None)
                if prior is None or prior['ref']!=ref:self.check(ref==self.model.reference(ref['packageId'],target['graph'],ref['nodeId']),'PLAN_REFERENCE_PIN_CHANGED')
            self.validate_new_placements(row['plan'],plan)
            if decision:
                for fork in plan['forks']:
                    for case in fork['cases']:
                        self.check(all(self.kernel.entities(profile_row['graph']).get(i,{}).get('kind')=='decision' for i in case['decisionIds']),'PLAN_CASE_DECISION')
            perms=['plan.edit']+(['plan.branch'] if (plan['forks']!=row['plan']['forks'] if decision else plan['branches']!=row['plan']['branches']) else [])
            change(ident,row,perms,plan=plan);effects={'planRevision':plan['revision']}
        elif op=='recommendation_edit':
            self.check(set(request)<= {'op','transactionId','expectedRegistryRevision','action','definition','packageId','attachTo','note',
                'confirmOwnerManagement'},'RECOMMENDATION_FIELDS')
            reg=registry_read();self.check(reg['revision']==request['expectedRegistryRevision'],'REGISTRY_CAS_MISMATCH')
            self.check(isinstance(request.get('note'),str) and request['note'].strip(),'NOTE_REQUIRED')
            action=request['action'];old=next((p for p in reg['packages'] if p['id']==request.get('packageId')),None)
            self.check(action in ('create','edit','copy','remove','manage'),'RECOMMENDATION_ACTION')
            if action=='manage':
                self.check(set(request)=={'op','transactionId','expectedRegistryRevision','action',
                    'packageId','confirmOwnerManagement','note'},'RECOMMENDATION_FIELDS')
                self.check(request['confirmOwnerManagement'] is True,'OWNER_MANAGEMENT_CONFIRMATION_REQUIRED')
                self.check(old is not None and old['supplied'] is True and not old.get('userManaged'),
                           'RECOMMENDATION_MANAGE_NOT_APPLICABLE')
                add_check(None,['graph.write','package.move'],None)
            if action=='edit':
                self.check(old is not None and (not old['supplied'] or old.get('userManaged')),'PACKAGE_IMMUTABLE')
            if action=='remove':
                self.check(old is not None and not old['supplied'],'PACKAGE_IMMUTABLE')
            if action=='remove':reg['packages'].remove(old)
            else:
                definition=copy.deepcopy(old if action=='manage' else request.get('definition',old if action=='copy' else {}))
                if action=='manage':
                    definition.update(revision=old['revision']+1,userManaged=True)
                if action=='copy':
                    self.check(old is not None,'REFERENCE_MISSING');definition=copy.deepcopy(old)
                    definition.pop('userManaged',None)
                    definition.update(id=str(uuid.uuid5(tx,'recommendation-copy')),revision=1,supplied=False,key=old['key']+'-copy',title=old['title']+' — копия')
                if action=='create':
                    self.check(definition.get('supplied') is False and definition.get('revision')==1 and
                               'userManaged' not in definition,'PACKAGE_IMMUTABLE')
                if action=='edit':
                    self.check(definition.get('id')==old['id'] and definition.get('supplied') is old['supplied'] and
                        definition.get('userManaged',False) == old.get('userManaged',False) and
                        definition.get('revision')==old['revision']+1,'REGISTRY_CAS_MISMATCH')
                self.recommendations.validate_definition(definition)
                self.check(action in ('edit','manage') or not any(p['id']==definition['id'] for p in reg['packages']),'ENTITY_ID_CONFLICT')
                for rule in definition['rules']:
                    if definition.get('authored') and 'anchor' in rule:
                        anchor=rule['anchor'];source=read(anchor['packageId']);g=source['graph'];kind=anchor.get('kind','entity')
                        self.check(g['coreModel']=='rdg-decision-v1' and g['identitySpace']==anchor['identitySpace'],'RECOMMENDATION_ANCHOR_IDENTITY')
                        target=(g if kind=='process' and anchor['nodeId']==g['id'] else next((w for w in g['workGraphs'] if w['id']==anchor['nodeId']),None) if kind=='workGraph' else self.kernel.entities(g).get(anchor['nodeId']) if kind=='entity' else None)
                        self.check(target is not None,'RECOMMENDATION_ANCHOR_KIND')
                    for ref in rule['lensRefs']:
                        lens=read(ref['packageId']);self.check(lens['head']['role']=='lens' and lens['graph']['identitySpace']==ref['identitySpace'] and lens['head']['lensKey']==ref['lensKey'] and lens['graph']['coreModel']=='rdg-decision-v1' and ('nodeId' not in ref or ref['nodeId'] in self.kernel.entities(lens['graph'])),'REFERENCE_MISSING:lens')
                if action in ('edit','manage'):reg['packages'].remove(old)
                reg['packages'].append(definition)
            reg['revision']+=1;registry_write();effects={'registryRevision':reg['revision'],'definitionId':definition['id'] if action!='remove' else old['id']}
            effects['affectedOwners']=[{'packageId':p['packageId'],'title':p.get('title','')} for p in self._catalog_locked()['packages'] if (old and old['id'] in p.get('recommendationPackageIds',[])) or p['packageId']==request.get('attachTo',{}).get('packageId')]
            if request.get('attachTo'):
                self.check(action!='remove','RECOMMENDATION_ACTION');attach=request['attachTo'];row=read(attach['packageId'])
                self.check(row['head']['revision']==attach['expectedPackageRevision'] and row['graph']['revision']==attach['expectedGraphRevision'],'PACKAGE_CAS_MISMATCH')
                self.check(row['graph']['coreModel']=='rdg-decision-v1','UNSUPPORTED_PROFILE_CAPABILITY')
                package_ids=list(dict.fromkeys(row['graph']['recommendationPackageIds']+[definition['id']]))
                graph,_=self.kernel.apply(row['graph'],{'schemaVersion':1,'expectedRevision':row['graph']['revision'],'operations':[{'op':'graph_edit','action':'core_recommendation_packages','data':{'packageIds':package_ids},'event':event('recommendation-attach')}]},True,paper=row['head']['role'] in ('ready','lens'))
                if row['head']['role'] in ('ready','lens'):graph['events']=[]
                change(row['packageId'],row,['graph.write'],graph=graph)
        elif op=='recommendation_attach':
            self.check(set(request)=={'op','transactionId','targetPackageId','expectedPackageRevision','expectedGraphRevision','packageIds','note'},'RECOMMENDATION_FIELDS')
            row=read(request['targetPackageId']);expected(row);ident=row['packageId'];reg=registry_read()
            self.check(row['graph']['coreModel']=='rdg-decision-v1','UNSUPPORTED_PROFILE_CAPABILITY')
            self.check(set(request['packageIds'])<= {p['id'] for p in reg['packages']},'REFERENCE_MISSING:recommendation')
            graph,_=self.kernel.apply(row['graph'],{'schemaVersion':1,'expectedRevision':row['graph']['revision'],'operations':[
                {'op':'graph_edit','action':'core_recommendation_packages','data':{'packageIds':request['packageIds']},'event':event('recommendation-attach')}]},True,paper=row['head']['role'] in ('ready','lens'))
            if row['head']['role'] in ('ready','lens'):graph['events']=[]
            change(ident,row,['graph.write'],graph=graph);effects={'attachedIds':request['packageIds']}
        elif op=='lens_apply':
            self.check(set(request)=={'op','transactionId','targetPackageId','expectedPackageRevision','expectedGraphRevision','lensPackageId','nodeIds','evidenceIds','recommendationIds','note'},'LENS_APPLICATION_FIELDS')
            row=read(request['targetPackageId']);expected(row);ident=row['packageId'];reg=registry_read()
            self.check(row['graph']['coreModel']=='rdg-decision-v1','UNSUPPORTED_PROFILE_CAPABILITY');lens=read(request['lensPackageId'])
            self.check(lens['head']['role']=='lens' and lens['graph']['coreModel']==row['graph']['coreModel'] and row['head']['role'] in ('working','copy'),'LENS_APPLICATION_ROLE')
            definitions={p['id']:p for p in reg['packages']};self.check(set(request['recommendationIds'])<=set(definitions),'REFERENCE_MISSING:recommendation')
            data={k:request[k] for k in ('nodeIds','evidenceIds')};data['observedPins']=[self.model.reference(ident,row['graph'],i,'historical') for i in request['nodeIds']]
            data['recommendationPins']=[{'packageId':i,'revision':definitions[i]['revision'],'sha256':self.recommendations.digest(definitions[i])} for i in request['recommendationIds']]
            data['lensPins']=[{'packageId':lens['packageId'],'identitySpace':lens['graph']['identitySpace'],'graphRevision':lens['graph']['revision'],'sha256':self.model.digest(lens['graph'])}]
            graph,_=self.kernel.apply(row['graph'],{'schemaVersion':1,'expectedRevision':row['graph']['revision'],'operations':[
                {'op':'graph_edit','action':'core_lens_application','data':data,'event':event('lens-application')}]},True)
            change(ident,row,['graph.write'],graph=graph);effects={'lensPins':data['lensPins'],'recommendationPins':data['recommendationPins']}
        elif op=='attach_evidence':
            self.check(set(request)=={'op','transactionId','targetPackageId','expectedPackageRevision','contentBase64'},'EVIDENCE_FIELDS')
            row=read(request['targetPackageId']);ident=row['packageId']
            self.check(row['head']['role'] in ('working','copy') and row['head']['revision']==request['expectedPackageRevision'],'EVIDENCE_TARGET')
            raw=base64.b64decode(request['contentBase64'],validate=True);sha=self.store.sha(raw);path='evidence/'+sha
            change(ident,row,['graph.write'],artifacts={path:raw});effects={'evidenceRef':{'path':path,'sha256':sha}}
        else:raise ValueError('PORTABLE_APP_UNKNOWN_OPERATION')
        # A template carries execution pins, but cannot revive a globally disabled version.
        for changed in list(changes.values()):
            candidate=changed.get('graph')
            if not candidate or candidate.get('coreModel')!='rdg-decision-v1':continue
            if (not changed.get('before') or op in ('copy','apply_ready','insert_copy')) and changed.get('role',(changed.get('before') or {}).get('head',{}).get('role')) in ('working','copy'):
                enabled=[b for b in candidate.get('dependencyBindings',[]) if b['enabled']]
                if enabled:
                    definitions=registry_read().get('dependencyPolicies',[])
                    self.check(not any(p['status']=='disabled' and any(b['policyId']==p['id'] and b['policyVersion']==p['version'] for b in enabled) for p in definitions),'POLICY_VERSION_DISABLED')
        compact={k:v for k,v in effects.items() if k not in ('graphs','plans','readSet','planReadSet','recordedAt')}
        for value in changes.values():value['effects']=copy.deepcopy(compact)
        catalog=self.store.catalog_signature(ignore_ids={i for i,c in changes.items() if not c.get('before')})
        decision_profile = (registry_row is not None or request.get('coreModel') == 'rdg-decision-v1' or
            any((value.get('graph') or {}).get('coreModel') == 'rdg-decision-v1'
                for value in changes.values()) or
            any((row.get('graph') or {}).get('coreModel') == 'rdg-decision-v1'
                for row in rows.values()))
        owner_pins = [{'kind':'package','namespaceId':self.store.namespace_id,
                       'packageId':ident,'revision':row['head']['revision'],
                       'sha256':row['headSHA256']} for ident,row in sorted(rows.items()) if ident!=self.store.registry_key()]
        if registry_row and registry_row['headSHA256']:
            owner_pins.append({'kind':'recommendationRegistry','namespaceId':self.store.namespace_id,'revision':registry_row['registry']['revision'],'sha256':registry_row['headSHA256']})
        return {'changes':changes,'checks':checks,'readset':{i:r['headSHA256'] for i,r in rows.items()},
                'ownerPins':owner_pins,'decisionProfile':decision_profile,
                'catalog':catalog,'effects':effects,'allocation':allocation}

    def visual_edges(self,graph):
        edges=list(self.kernel.active_edges(graph))
        if graph['coreModel']=='rdg-decision-v1':edges+=self.kernel.for_graph(graph).decision_memberships(graph)
        return edges

    def verify_evidence(self,row,refs):
        if not refs:return
        inventory=self.store.inventory(row);directory=self.store.package_path(row['path'])
        for ref in refs:
            self.check(isinstance(ref,dict) and set(ref)=={'path','sha256'} and ref['path'].startswith('evidence/'), 'EVIDENCE_REF')
            path=self.store.io.safe_path(directory,ref['path'],True)
            self.check(inventory.get(ref['path'])==ref['sha256'] and self.store.io.file_sha(path)==ref['sha256'],'EVIDENCE_BYTES_UNAVAILABLE')

    @staticmethod
    def empty_plan(ident,space,title,decision=False):
        if decision:
            return {'schemaVersion':3,'kind':'temporalPlan','id':ident,'identitySpace':space,'title':title,
                'revision':1,'status':'candidate','steps':[],'mainStepIds':[],'forks':[],'timeConstraints':[]}
        return {'schemaVersion':2,'kind':'temporalPlan','id':ident,'identitySpace':space,'title':title,
                'revision':1,'status':'candidate','steps':[],'sequence':[],'branches':[],'timeConstraints':[]}

    def validate_new_placements(self,before,after):
        if after['schemaVersion']==3:return  # full main-lane membership is validated by the model
        old={s['id']:s for s in before['steps']};placed={r['stepId'] for r in after['timeConstraints']}
        for edge in after['sequence']:placed.update((edge['before'],edge['after']))
        self.check(all(step['id'] in placed or old.get(step['id'])==step for step in after['steps']), 'NEW_PLACEMENT_POSITION_REQUIRED')

    def layout(self,operation,**request):
        self.check(self.layout_port is not None,'LAYOUT_CODEC_UNAVAILABLE')
        payload={'op':operation,**request}
        if operation!='project':
            return self.layout_port(payload)
        # The exact pure JS projection is keyed by its complete inputs. The
        # snapshot and its permission checks happen before this call in read().
        key=hashlib.sha256(CACHE.ProjectionCache.encode(payload)).digest()
        cached=self._visual_cache.get(key)
        if cached is not None:return cached
        result=self.layout_port(payload)
        self._visual_cache.put(key,result)
        return result

    def resolve_action_subject(self,ref,action,row,register=None):
        try:
            if 'kind' not in ref:
                local=self.kernel.for_graph(row['graph']).QUESTIONS.reference_id(row['graph'],ref,self.kernel.for_graph(row['graph']),action) if row['graph']['coreModel']=='rdg-decision-v1' else None
                if local and ref.get('mode')=='inherited':
                    node=self.kernel.entities(row['graph']).get(local)
                    return {'reference':copy.deepcopy(ref),'status':'current' if node else 'missing','node':copy.deepcopy(node),'packageId':row['packageId'],'localBinding':True}
            return {'reference':copy.deepcopy(ref),**self.resolve_for(ref,row,register)}
        except (ValueError,OSError):return {'reference':copy.deepcopy(ref),'status':'unavailable','changed':None}

    def validate_action_subjects(self,command,data,ident,graph,read):
        if command=='add':value=data.get('entity',{});prior=[]
        elif command=='edit':
            old=self.kernel.entities(graph).get(data.get('nodeId'),{})
            value={**old,**data.get('changes',{})};prior=old.get('subjectRefs',[])
        else:return
        if value.get('kind')!='action' or 'subjectRefs' not in value:return
        refs=value['subjectRefs'];self.check(isinstance(refs,list),'ACTION_SUBJECTS')
        for ref in refs:
            self.model.validate_reference(ref,allow_scope=True)
            if ref in prior:continue
            source=read(ref['packageId']);target=source['graph']
            if ref['packageId']==ident and ref.get('sha256')==self.model.digest(graph):target=graph
            self.check(ref['packageId']==ident or source['head']['role']=='lens','ACTION_SUBJECT_FOREIGN_PROCESS')
            self.check(target['coreModel']==graph['coreModel'] and target['identitySpace']==ref['identitySpace'],'ACTION_SUBJECT_IDENTITY')
            if 'kind' in ref:
                self.check(ref['kind']!='lens' or source['head']['role']=='lens','ACTION_SUBJECT_LENS')
                self.check(ref['kind']!='process' or ref['packageId']==ident,'ACTION_SUBJECT_PROCESS')
                self.check(ref['kind']!='workGraph' or any(w['id']==ref['workGraphId'] for w in target['workGraphs']),'ACTION_SUBJECT_SCOPE')
                self.check(ref['graphRevision']==target['revision'] and ref['sha256']==self.model.digest(target),'ACTION_SUBJECT_PIN_CHANGED')
            else:
                self.check(ref.get('mode')=='current' and ref.get('nodeId') in self.kernel.entities(target),'ACTION_SUBJECT_MISSING')
                self.check(ref==self.model.reference(ref['packageId'],target,ref['nodeId']),'ACTION_SUBJECT_PIN_CHANGED')

    def reference_snapshots(self,ref,consumer,register=None):
        current={};history={}
        try:
            source=register(ref['packageId']) if register else self.snapshot(ref['packageId'],layouts=False)
            current[ref['packageId']]={'graph':source['graph']}
        except (ValueError,OSError):source=None
        if source is not None:
            try:
                graph=self.store.historical_graph(ref['packageId'],ref['identitySpace'],ref['graphRevision'],ref['sha256'])
                history[(ref['packageId'],ref['identitySpace'],ref['sha256'])]=graph
            except (ValueError,OSError):pass
        if not history:
            found=self.store.find_artifact(consumer,ref['sha256'],suffix='/graph.json',prefix='provenance/')
            if found:
                graph=json.loads(found[1])
                if graph.get('identitySpace')==ref['identitySpace'] and self.model.digest(graph)==ref['sha256']:
                    history[(ref['packageId'],ref['identitySpace'],ref['sha256'])]=graph
        return current,history

    def resolve_for(self,ref,consumer,register=None):
        self.model.validate_reference(ref,allow_scope=True)
        current,history=self.reference_snapshots(ref,consumer,register)
        return self.model.resolve_reference(ref,current,history,self.kernel)

    def source_snapshot(self,ident,pin,spec=None):
        self.check(isinstance(pin,dict) and set(pin)=={'packageId','identitySpace','graphRevision','sha256'},'SOURCE_PIN_FIELDS')
        self.model.validate_graph_pin(pin)
        with self.store.lock(False,create=False):
            consumer=self.snapshot(ident,layouts=False)
            current,history=self.reference_snapshots(pin,consumer)
            graph=history.get((pin['packageId'],pin['identitySpace'],pin['sha256']))
            if graph is None:
                candidate=current.get(pin['packageId'],{}).get('graph')
                if candidate and self.model.digest(candidate)==pin['sha256']:graph=candidate
            self.check(graph is not None and graph['identitySpace']==pin['identitySpace'] and
                graph['revision']==pin['graphRevision'] and self.model.digest(graph)==pin['sha256'],'HISTORICAL_GRAPH_UNAVAILABLE')
            self.model.validate_graph_payload(graph,self.kernel)
            return {'readOnly':True,'pin':copy.deepcopy(pin),'graph':graph,'view':self.model.presentation(graph,self.kernel,spec),
                'completion':self.kernel.completion_state(graph),'layouts':None,'currentOwnerAvailable':pin['packageId'] in current,
                'instruction':'Preserved source version. Current changes require reopening the current package.'}

    def boundaries(self,row,register=None):
        states=[];review=set();conflicts=set();graph=row['graph']
        for ref in graph.get('externalRefs',[]):
            result=self.resolve_for(ref['target'],row,register)
            active=not ref['relation'].get('archived')
            dependency_types = self.kernel.dependency_types_for(graph)
            dependency=active and (ref['direction']=='incoming' and ref['relation']['type'] in dependency_types or
                                   ref['relation']['type']=='EXCLUDES')
            changed=dependency and (result['status']!='current' or result.get('changed') is not False or
                                   result.get('node',{}).get('review',{}).get('required'))
            conflict=active and ref['relation']['type']=='EXCLUDES' and result.get('node',{}).get('status')=='selected'
            if changed:review.add(ref['localId'])
            if conflict:conflicts.add(ref['localId'])
            states.append({'referenceId':ref['id'],'localId':ref['localId'],'direction':ref['direction'],
                'relation':copy.deepcopy(ref['relation']),'target':copy.deepcopy(ref['target']),
                'resolved':result,'dependency':dependency,'reviewRequired':bool(changed),'exclusionConflict':bool(conflict)})
        review |= self.kernel.affected(graph,graph,review)
        return {'states':states,'reviewIds':sorted(review),'conflictIds':sorted(conflicts),'pinsRefreshed':False}

    def resolve(self,ident,reference):
        with self.store.lock(False,create=False):return self.resolve_for(reference,self.snapshot(ident,layouts=False))

    def history(self,ident,view=None,*,detail=None,include=None,event_id=None,limit=25,cursor=None):
        self.check(detail in (None,'full','compact','item'), 'READ_HISTORY_DETAIL')
        self.check((detail=='item')==(isinstance(event_id,str) and bool(event_id)), 'READ_HISTORY_EVENT_ID')
        if detail in (None,'full','item'):
            self.check(include is None and cursor is None and limit==25, 'READ_DETAIL_REQUIRED')
        if view:
            self.model.validate_view_spec(view)
            self.check(view.get('kind')=='graph' and set(view)<={'kind','historyMode','historyWindow'}, 'READ_HISTORY_VIEW_UNSUPPORTED')
        with self.store.lock(False,create=False):
            row=self.snapshot(ident,True,False);directory=self.store.package_path(row['path'])
            inventory=self.store.inventory(row)
            # Full History only: compact/item must still run their own input
            # validation and projection. Auth, snapshot, every inventory byte,
            # and the shared writer barrier are checked even on a cache hit.
            history_key=None
            if detail in (None,'full'):
                evidence={'version':'history-full-v1','owner':ident,
                          'head':row['headSHA256'],'inventory':inventory,
                          'view':view,'detail':detail}
                history_key=hashlib.sha256(CACHE.ProjectionCache.encode(evidence)).digest()
                cached=self._history_cache.get(history_key)
                if cached is not None:return cached
            records=[];seen_heads=set()
            def artifact(relative,sha):
                raw=self.store.io.safe_path(directory,relative,True).read_bytes()
                self.check(self.store.sha(raw)==sha,'HISTORY_ARTIFACT_BYTES');return raw
            def record(head,prefix='',inherited=False):
                key=(prefix,self.model.digest(head))
                if key in seen_heads:return
                seen_heads.add(key)
                graph_path=prefix+head['current']['graph']
                graph=json.loads(artifact(graph_path,head['files'][head['current']['graph']]))
                accepted=None;proof=prefix+'.rdg/acceptances/'+head['lastTransactionId']+'.json'
                if proof in inventory:
                    value=json.loads(artifact(proof,inventory[proof]))
                    self.check(value.get('packageId')==head['packageId'] and value.get('headSHA256')==self.model.digest(head),'HISTORY_ACCEPTANCE_WITNESS')
                    accepted=value['acceptedAt']
                records.append({'head':head,'graph':graph,'prefix':prefix,'inherited':inherited,'acceptedAt':accepted})
            for head in self.store.head_chain(row):record(head)
            # Source packages and their historical heads were copied as exact bytes.
            # Read those owned artifacts; no old source path or source permission is needed.
            for relative,sha in inventory.items():
                if not relative.startswith('provenance/') or not (relative.endswith('/package.json') or '/history/heads/' in relative):continue
                head=json.loads(artifact(relative,sha))
                if head.get('kind')!='rdgGraphPackage':continue
                prefix=(relative.rsplit('/history/heads/',1)[0]+'/' if '/history/heads/' in relative else relative[:-len('package.json')])
                record(head,prefix,True)
            first_facts={};plan_versions={};history_details={};previous_graphs={}
            for value in sorted(records,key=lambda r:(r['head']['identitySpace'],r['head']['revision'])):
                head,graph=value['head'],value['graph'];source={'packageId':head['packageId'],'identitySpace':graph['identitySpace'],
                    'graphRevision':graph['revision'],'sha256':self.model.digest(graph)}
                if graph.get('coreModel')=='rdg-decision-v1':
                    key=(value['prefix'],graph['identitySpace']);before=previous_graphs.get(key);old_events={e['id'] for e in before['events']} if before else set()
                    fresh=[e for e in graph['events'] if e['id'] not in old_events]
                    decision=self.kernel.for_graph(graph)
                    details=decision.HISTORY.legacy_details(before,graph,fresh,decision,process=head['role'] in ('working','copy'))
                    for historical_event_id,d in details.items():history_details.setdefault((graph['identitySpace'],historical_event_id),d)
                    previous_graphs[key]=graph
                plan_pin=None
                if 'plan' in head['current']:
                    plan_bytes=artifact(value['prefix']+head['current']['plan'],head['files'][head['current']['plan']])
                    plan_at_event=json.loads(plan_bytes);plan_pin={'packageId':head['packageId'],'revision':plan_at_event['revision'],'sha256':self.store.sha(plan_bytes)}
                for event in graph.get('events',[]):
                    first_facts.setdefault((graph['identitySpace'],event['id']),{'source':source,'acceptedAt':value['acceptedAt'],
                        'transactionId':head['lastTransactionId'],'snapshotKind':'after-transaction','packageRevision':head['revision'],'planPin':plan_pin})
                if 'plan' in head['current']:
                    relative=value['prefix']+head['current']['plan'];sha=head['files'][head['current']['plan']]
                    plan=json.loads(artifact(relative,sha))
                    plan_versions.setdefault(sha,{'plan':plan,'sha256':sha,'inherited':value['inherited'],
                        'sourceArtifact':relative,'current':not value['inherited'] and relative==row['head']['current'].get('plan'),
                        'acceptedAt':value['acceptedAt'],'sourcePackageId':head['packageId'],'packageRevision':head['revision']})
            legacy=self.migration.historical_records(row,records,inventory)
            first_facts.update(legacy['events'])
            for version in legacy['planVersions']:plan_versions.setdefault(version['sha256'],version)
            events=[];seen=set();graph=row['graph'];lineage={}
            for nid,links in graph.get('factLineage',{}).items():
                for lineage_event_id,link in links.items():
                    source=graph['inheritedHistory'][link['historyKey']]['source']
                    lineage.setdefault((source['identitySpace'],lineage_event_id),[]).append(nid)
            def add(event,source,inherited):
                key=(source['identitySpace'],event['id'])
                if key in seen:return
                seen.add(key);exact=first_facts.get(key,{})
                local=list(dict.fromkeys(event.get('nodeIds',[])+([event['targetId']] if event.get('targetId') else event.get('targetIds',[]))+event.get('affectedIds',[])))
                display=lineage.get(key,[]) if inherited else local
                events.append({'event':copy.deepcopy(event),'inherited':inherited,'source':exact.get('source',source),
                    'snapshotKind':exact.get('snapshotKind','captured-source'),'acceptedAt':exact.get('acceptedAt'),
                    'transactionId':exact.get('transactionId'),'packageRevision':exact.get('packageRevision'),'planPin':exact.get('planPin'),'displayTargetIds':display,'inheritedIntoIds':display if inherited else []})
                if 'fullEnvelopeCopied' in exact:events[-1].update(fullEnvelopeCopied=exact['fullEnvelopeCopied'],sourceArtifact=exact['sourceArtifact'])
                if graph.get('coreModel')=='rdg-decision-v1':
                    decision=self.kernel.for_graph(graph);d=history_details.get(key)
                    if d is None:d=decision.HISTORY.legacy_details(None,graph,[event],decision)[event['id']]
                    events[-1]['historyView']=decision.HISTORY.classify(event,d)
            current_source={'packageId':ident,'identitySpace':graph['identitySpace'],
                            'graphRevision':graph['revision'],'sha256':self.model.digest(graph)}
            for event in graph['events']:
                add(event,current_source,False)
            for value in graph.get('inheritedHistory',{}).values():
                for event in value['events']:add(event,value['source'],True)
            if view:
                self.model.validate_view_spec(view);events=[r for r in events if self.model.window_matches(r['event'].get('recordedAt',''),view.get('historyWindow'))]
                if 'historyMode' in view and graph.get('coreModel')=='rdg-decision-v1':events=[r for r in events if self.kernel.for_graph(graph).HISTORY.accepts(r['historyView']['level'],view['historyMode'])]
            result={'packageId':ident,'events':events,'modes':list(self.kernel.for_graph(graph).HISTORY.MODES) if graph.get('coreModel')=='rdg-decision-v1' else [],'planVersions':list(plan_versions.values()),'legacyGraphSnapshots':legacy['graphSnapshots'],
                    'migrationEvidenceGaps':legacy['evidenceGaps'],'reconstructedExecution':False,
                    'snapshotExplanation':'after-transaction is a preserved accepted version; captured-source is only capture context. legacy-after-record-projection preserves the owned record and original envelope hash; it does not copy or independently verify the full original envelope.'}
            if detail=='item':
                match=next((r for r in events if r['event']['id']==event_id),None)
                self.check(match is not None, 'READ_HISTORY_EVENT_NOT_FOUND')
                return {'schemaVersion':1,'packageId':ident,'snapshot':COMPACT.pin(self,row),
                        'detail':'item','loaded':{'event':True},'item':copy.deepcopy(match)}
            output=COMPACT.project_history(self,row,result,include or [],limit,cursor,view) if detail=='compact' else result
            if history_key is not None:self._history_cache.put(history_key,output)
            return output
