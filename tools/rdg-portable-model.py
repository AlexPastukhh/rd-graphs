#!/usr/bin/env python3
"""Pure portable Graph planning. No filesystem, authority, transport, clock or RNG.

The existing core kernel is supplied explicitly. Reference definitions are shared
by capture/remap/planning; capture, freshness and rooted scope retain distinct
policies. EffectPlan keeps canonical immutable bytes and returns defensive copies.
"""
import copy
from datetime import date, datetime
from dataclasses import dataclass
import hashlib
import json
import re
import uuid
from collections import deque

FORMAT_VERSION = 1
ROLES = frozenset(('working', 'ready', 'copy', 'lens'))
CURRENT_GRAPH_FIELDS = frozenset(('schemaVersion', 'actionModel', 'coreModel', 'id', 'title',
    'identitySpace', 'revision', 'rootRequirementId', 'planningScale', 'nodes', 'objects', 'edges',
    'events', 'collections', 'workGraphs', 'workGraphLinks', 'exclusionGroups', 'lensRecommendations',
    'coreDocumentVersion', 'fragmentFocus', 'externalRefs', 'factLineage', 'relationLineage', 'entityLineage', 'inheritedHistory'))
DECISION_GRAPH_FIELDS = frozenset(('schemaVersion', 'actionModel', 'coreModel', 'id', 'title',
    'identitySpace', 'revision', 'rootRequirementId', 'rootCauses', 'nodes', 'objects',
    'externalActions', 'edges', 'decisionGroups', 'workGraphs', 'events', 'recommendationPackageIds',
    'externalRefs','inheritedHistory','factLineage','entityLineage',
    'dependencyPolicies','dependencyBindings','dependencyPresets','dependencyAutomaticStates','dependencyPolicyAliases','contextGroups'))
REALIZATION_TYPES = frozenset(('DERIVES', 'DRIVES', 'INTRODUCES'))
COMPANION_TYPES = frozenset(('CANON_FOR', 'CONTEXT_FOR', 'INFO_FOR', 'EVIDENCE_FOR'))


def require(ok, code):
    if not ok:raise ValueError('PORTABLE_' + code)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


@dataclass(frozen=True)
class EffectPlan:
    payload: bytes

    @property
    def value(self):return json.loads(self.payload)

    @property
    def sha256(self):return hashlib.sha256(self.payload).hexdigest()


def reference(package_id, graph, node_id, mode='current', *, graph_sha256=None, node_revision=None):
    require(mode in ('current', 'historical', 'inherited'), 'REF_MODE')
    return {'schemaVersion': 1, 'packageId': package_id, 'identitySpace': graph['identitySpace'],
            'nodeId': node_id, 'mode': mode,
            'revision': (next(n['revision'] for n in graph['nodes'] + graph['objects'] + graph.get('externalActions', [])
                              if n['id'] == node_id) if node_revision is None else node_revision),
            'graphRevision': graph['revision'], 'sha256': digest(graph) if graph_sha256 is None else graph_sha256}


def valid_graph_pin(pin):
    return (isinstance(pin,dict) and
            all(isinstance(pin.get(k),str) and pin[k].strip() for k in ('packageId','identitySpace')) and
            type(pin.get('graphRevision')) is int and pin['graphRevision']>=1 and
            isinstance(pin.get('sha256'),str) and bool(re.fullmatch('[0-9a-f]{64}',pin['sha256'])))


def validate_graph_pin(pin):
    require(valid_graph_pin(pin) and set(pin)=={'packageId','identitySpace','graphRevision','sha256'},'GRAPH_PIN_SCHEMA')
    return pin


def scope_reference(package_id, graph, kind='process', work_graph_id=None):
    ref={'schemaVersion':1,'kind':kind,'packageId':package_id,
         'identitySpace':graph['identitySpace'],'graphRevision':graph['revision'],'sha256':digest(graph)}
    if work_graph_id is not None:ref['workGraphId']=work_graph_id
    validate_reference(ref,allow_scope=True)
    return ref


def validate_reference(ref, *, allow_scope=False):
    if allow_scope and isinstance(ref,dict) and 'kind' in ref:
        fields={'schemaVersion','kind','packageId','identitySpace','graphRevision','sha256'}
        if ref.get('kind')=='workGraph':fields.add('workGraphId')
        require(set(ref)==fields and ref.get('schemaVersion')==1 and
                ref.get('kind') in ('process','workGraph','lens') and valid_graph_pin(ref) and
                (ref['kind']!='workGraph' or isinstance(ref.get('workGraphId'),str) and ref['workGraphId'].strip()),'REF_SCHEMA')
        return ref
    require(isinstance(ref, dict) and set(ref) == {'schemaVersion', 'packageId', 'identitySpace',
            'nodeId', 'mode', 'revision', 'graphRevision', 'sha256'} and ref['schemaVersion'] == 1 and
            valid_graph_pin(ref) and isinstance(ref.get('nodeId'),str) and ref['nodeId'].strip() and
            ref.get('mode') in ('current', 'historical', 'inherited') and
            type(ref.get('revision')) is int and ref['revision'] >= 1, 'REF_SCHEMA')
    return ref


def resolve_reference(ref, snapshots, historical=None, kernel=None):
    """Resolve only provided, authorized snapshots. Missing is never an empty success."""
    validate_reference(ref,allow_scope=True)
    key = ref['packageId']; snapshot = snapshots.get(key)
    if 'kind' in ref:
        graph=snapshot['graph'] if snapshot else None
        if graph is None:return {'status':'unavailable','changed':None,'packageId':key}
        require(graph['identitySpace']==ref['identitySpace'],'REF_IDENTITY_MISMATCH')
        node=next((w for w in graph['workGraphs'] if w['id']==ref['workGraphId']),None) if ref['kind']=='workGraph' else {'id':graph['id'],'title':graph['title'],'kind':ref['kind']}
        return {'status':'current' if node else 'missing','node':copy.deepcopy(node),
                'changed':digest(graph)!=ref['sha256'],'packageId':key,'revision':graph['revision']}
    if snapshot is not None:
        graph = snapshot['graph']
        require(graph['identitySpace'] == ref['identitySpace'], 'REF_IDENTITY_MISMATCH')
        families = graph['nodes'] + graph['objects'] + graph.get('externalActions', [])
        node = next((n for n in families if n['id'] == ref['nodeId']), None)
        if ref['mode'] == 'current' and node is not None:
            baseline=(historical or {}).get((key,ref['identitySpace'],ref['sha256']))
            if baseline is not None:
                require(digest(baseline)==ref['sha256'] and baseline['revision']==ref['graphRevision'],'HISTORY_PIN_MISMATCH')
                prior=next((n for n in baseline['nodes']+baseline['objects']+baseline.get('externalActions',[]) if n['id']==ref['nodeId']),None)
                require(baseline['identitySpace']==ref['identitySpace'] and prior is not None and prior['revision']==ref['revision'],'HISTORICAL_ENDPOINT_MISMATCH')
                changed=endpoint_state(graph,ref['nodeId'],kernel)!=endpoint_state(baseline,ref['nodeId'],kernel)
            else:changed=True if node['revision']!=ref['revision'] else False if digest(graph)==ref['sha256'] else None
            return {'status': 'current', 'node': copy.deepcopy(node), 'changed':changed,
                    'packageId': key, 'revision': graph['revision']}
    history = (historical or {}).get((key, ref['identitySpace'], ref['sha256']))
    if history is not None:
        require(digest(history) == ref['sha256'] and history['revision'] == ref['graphRevision'], 'HISTORY_PIN_MISMATCH')
        node = next((n for n in history['nodes'] + history['objects'] + history.get('externalActions', []) if n['id'] == ref['nodeId']), None)
        require(node is not None and node['revision'] == ref['revision'], 'HISTORICAL_ENDPOINT_MISSING')
        return {'status': ('historical' if ref['mode'] != 'current' else
                           'deleted' if snapshot is not None else 'historical-current-unavailable'),
                'node': copy.deepcopy(node), 'changed': (ref['mode'] == 'current') if snapshot is not None else None, 'packageId': key,
                'revision': history['revision']}
    return {'status': 'unavailable' if snapshot is None else 'missing', 'changed': None if snapshot is None else True,
            'packageId': key, 'revision': ref['revision']}


def kernel_for_graph(kernel, graph):
    """Select the profile when available; keep direct legacy-kernel callers working."""
    if hasattr(kernel, 'for_graph'):
        return kernel.for_graph(graph)
    require(graph.get('coreModel') == 'rdg-core-v1', 'UNSUPPORTED_PROFILE_CAPABILITY')
    return kernel


def endpoint_state(graph,node_id,kernel=None):
    node=next((n for n in graph['nodes']+graph['objects']+graph.get('externalActions',[]) if n['id']==node_id),None)
    dependency_types=kernel_for_graph(kernel, graph).DEPENDENCY_TYPES if kernel is not None else set()
    edges=sorted((copy.deepcopy(e) for e in graph['edges'] if not e.get('archived') and
                  node_id in (e['from'],e['to']) and e['type'] in dependency_types),key=lambda e:e['id'])
    external=sorted((copy.deepcopy(r) for r in graph.get('externalRefs',[]) if r['localId']==node_id),key=lambda r:r['id'])
    return {'entity':copy.deepcopy(node),'dependencies':edges,'external':external}


def graph_references(graph):
    """Declared typed reference slots; prose and historical events are not current edges."""
    rows = []
    if graph.get('coreModel') == 'rdg-decision-v1':
        def add_decision(path, namespace='entity', mode='current', key=False):
            value = graph
            for part in path: value = value[part]
            rows.append({'path': list(path), 'namespace': namespace, 'mode': mode,
                         'value': value, 'key': key})
        if graph.get('rootRequirementId') is not None:
            add_decision(('rootRequirementId',))
        for i, cause in enumerate(graph.get('rootCauses', [])):
            add_decision(('rootCauses', i, 'requirementId'))
        for i, edge in enumerate(graph.get('edges', [])):
            add_decision(('edges', i, 'from')); add_decision(('edges', i, 'to'))
        known={n['id'] for n in graph['nodes']+graph['objects']+graph['externalActions']}
        for i, edge in enumerate(graph.get('edges', [])):
            if 'findingId' in edge:add_decision(('edges',i,'findingId'))
        for i,n in enumerate(graph['objects']):
            if n['kind']=='finding':
                if n['subjectId'] in known:add_decision(('objects',i,'subjectId'))
                for j,value in enumerate(n['evidenceIds']):
                    if value in known:add_decision(('objects',i,'evidenceIds',j))
                if n.get('disposition',{}).get('replacementId') in known:add_decision(('objects',i,'disposition','replacementId'))
        for i, work in enumerate(graph.get('workGraphs', [])):
            for field in ('rootIds', 'memberIds'):
                for j, _ in enumerate(work[field]): add_decision(('workGraphs', i, field, j))
        for i, group in enumerate(graph.get('decisionGroups', [])):
            add_decision(('decisionGroups', i, 'parentId'))
            for j, member in enumerate(group['members']):
                add_decision(('decisionGroups', i, 'members', j, 'decisionId'))
        for family in ('nodes', 'externalActions'):
            for i, node in enumerate(graph.get(family, [])):
                if family == 'nodes' and node['kind'] == 'decision':
                    for j,_ in enumerate(node.get('impactTargetIds',[])):add_decision((family,i,'impactTargetIds',j))
                    for j, _ in enumerate(node.get('decisionContextIds', [])):
                        add_decision((family, i, 'decisionContextIds', j))
                for j, _ in enumerate(node.get('targetIds', [])):
                    add_decision((family, i, 'targetIds', j))
                for j, _ in enumerate(node.get('groupIds', [])):
                    add_decision((family, i, 'groupIds', j), 'decisionGroup')
        for i,ref in enumerate(graph.get('externalRefs',[])):
            add_decision(('externalRefs',i,'localId'))
            add_decision(('externalRefs',i,'target'),'entity','observed')
        for field in ('factLineage','entityLineage'):
            for nid in graph.get(field,{}):
                rows.append({'path':[field,nid],'namespace':'entity','mode':'current','value':nid,'key':True})
        for i,_ in enumerate(graph.get('recommendationPackageIds',[])):add_decision(('recommendationPackageIds',i),'recommendationPackage','observed')
        for i,b in enumerate(graph.get('dependencyBindings',[])):
            for field in ('targetId','sourceId','parentId'):
                if b[field] is not None and b[field] in {n['id'] for n in graph['nodes']+graph['objects']+graph['externalActions']}:add_decision(('dependencyBindings',i,field))
            for role,value in b.get('participantBindings',{}).items():
                if value in {n['id'] for n in graph['nodes']+graph['objects']+graph['externalActions']}:add_decision(('dependencyBindings',i,'participantBindings',role))
        return rows
    def add(path, namespace='entity', mode='current', key=False):
        value = graph
        for part in path:value = value[part]
        rows.append({'path': list(path), 'namespace': namespace, 'mode': mode,
                     'value': value, 'key': key})
    if graph.get('rootRequirementId') is not None:add(('rootRequirementId',))
    if graph.get('fragmentFocus'):add(('fragmentFocus', 'id'))
    for i, edge in enumerate(graph['edges']):
        add(('edges', i, 'from'));add(('edges', i, 'to'))
        for j, _ in enumerate(edge.get('origin', {}).get('requirementIds', [])):
            add(('edges', i, 'origin', 'requirementIds', j))
    for i, scope in enumerate(graph['workGraphs']):
        for field in ('rootIds', 'memberIds'):
            for j, _ in enumerate(scope[field]):add(('workGraphs', i, field, j))
    for i, link in enumerate(graph['workGraphLinks']):
        for j, _ in enumerate(link):add(('workGraphLinks', i, j), 'workGraph')
    for i, group in enumerate(graph['exclusionGroups']):
        for j, _ in enumerate(group['actionIds']):add(('exclusionGroups', i, 'actionIds', j))
    for i, advice in enumerate(graph.get('lensRecommendations', [])):
        if 'targetId' in advice:add(('lensRecommendations', i, 'targetId'))
        if 'targetWorkGraphId' in advice:add(('lensRecommendations', i, 'targetWorkGraphId'), 'workGraph')
    for family in ('nodes', 'objects'):
        for i, node in enumerate(graph[family]):
            for field in ('assessment', 'review'):
                for key in node.get(field, {}).get('pins', {}):
                    path = (family, i, field, 'pins', key)
                    rows.append({'path': list(path), 'namespace': 'entity', 'mode': 'observed', 'value': key, 'key': True})
            for cid, matches in node.get('assessment', {}).get('matches', {}).items():
                rows.append({'path': [family, i, 'assessment', 'matches', cid], 'namespace': 'entity',
                             'mode': 'observed', 'value': cid, 'key': True})
                for condition, item in matches.items():
                    for j, _ in enumerate(item.get('sourceIds', [])):
                        add((family, i, 'assessment', 'matches', cid, condition, 'sourceIds', j), mode='observed')
    for i, ref in enumerate(graph.get('externalRefs', [])):
        add(('externalRefs', i, 'localId'))
    return rows


def definitions(graph):
    if graph.get('coreModel') == 'rdg-decision-v1':
        return {'entity': [n['id'] for n in graph['nodes'] + graph['objects'] + graph.get('externalActions', [])],
                'edge': [e['id'] for e in graph['edges']],
                'workGraph': [w['id'] for w in graph['workGraphs']],
                'decisionGroup': [g['id'] for g in graph['decisionGroups']],
                'contextGroup': [g['id'] for g in graph.get('contextGroups',[])],
                'membership': [m['id'] for g in graph['decisionGroups'] for m in g['members']],
                'rootCause': [r['id'] for r in graph['rootCauses']],
                'externalReference':[r['id'] for r in graph.get('externalRefs',[])],
                'event': [e['id'] for e in graph['events']]}
    return {'entity': [n['id'] for n in graph['nodes'] + graph['objects']],
            'edge': [e['id'] for e in graph['edges']],
            'workGraph': [w['id'] for w in graph['workGraphs']],
            'exclusion': [e['id'] for e in graph['exclusionGroups']]}


def remap_graph(graph, mapping, observed_mapping=None):
    """Profile dispatch for the existing typed remapper and Decision owner map."""
    if graph.get('coreModel')=='rdg-decision-v1':return decision_remap(graph,mapping)
    result = copy.deepcopy(graph)
    for namespace, values in definitions(graph).items():
        require(namespace in mapping and set(values) <= set(mapping[namespace]) and
                len(set(mapping[namespace].values())) == len(mapping[namespace]), 'ID_MAP_' + namespace)
    slots = graph_references(graph)
    # Nested values before dictionary key replacement so their original paths still exist.
    for slot in sorted(slots, key=lambda r: (r['key'], -len(r['path']))):
        value = mapping.get(slot['namespace'], {}).get(slot['value'])
        if value is None and slot['mode']=='observed':value=(observed_mapping or {}).get(slot['value'])
        if value is None:
            require(slot['mode'] != 'current', 'UNMAPPED_CURRENT_REF')
            continue
        cursor = result
        for part in slot['path'][:-1]:cursor = cursor[part]
        old = slot['path'][-1]
        if slot['key']:
            if old != value:
                require(value not in cursor, 'MAP_KEY_COLLISION')
                cursor[value] = cursor.pop(old)
        else:cursor[old] = value
    for field, namespace in (('nodes', 'entity'), ('objects', 'entity'), ('edges', 'edge'),
                             ('workGraphs', 'workGraph'), ('exclusionGroups', 'exclusion')):
        for item in result[field]:item['id'] = mapping[namespace][item['id']]
    for field in ('factLineage', 'entityLineage'):
        if field in result:result[field] = {mapping['entity'][k]: v for k, v in result[field].items()}
    if 'relationLineage' in result:result['relationLineage']={mapping['edge'][k]:v for k,v in result['relationLineage'].items()}
    return result


def capture(graph, focus, kernel, include_descendants=True):
    if graph.get('coreModel')=='rdg-decision-v1':return decision_capture(graph,focus,kernel,include_descendants)
    kernel.validate(graph)
    ns = kernel.entities(graph); kind = focus['kind']; ident = focus.get('id')
    require(kind in ('graph', 'requirement', 'action', 'canon'), 'COPY_FOCUS')
    if kind == 'graph':chosen = set(ns)
    else:
        require(ident in ns and ns[ident]['kind'] == kind, 'COPY_FOCUS_TARGET')
        chosen = {ident}
        if kind == 'requirement':
            queue = deque([ident])
            while queue:
                source = queue.popleft()
                for edge in kernel.active_edges(graph):
                    if edge['from'] == source and edge['type'] in REALIZATION_TYPES:
                        if edge['to'] not in chosen:
                            chosen.add(edge['to'])
                            if include_descendants:queue.append(edge['to'])
        elif kind == 'action':
            chosen.update(e['from'] for e in kernel.active_edges(graph) if e['to'] == ident and
                          e['type'] in ('DRIVES', 'RELATES_R', 'CONTEXT_FOR', 'CANON_FOR'))
            chosen.update(e['to'] for e in kernel.active_edges(graph) if e['from'] == ident and e['type'] == 'INTRODUCES')
        while True:
            extra = {e['from'] for e in kernel.active_edges(graph) if e['to'] in chosen and
                     e['type'] in COMPANION_TYPES and (kind != 'canon' or e['type'] in ('INFO_FOR', 'EVIDENCE_FOR'))}
            if extra <= chosen:break
            chosen.update(extra)
    internal, boundary = [], []
    for edge in graph['edges']:
        a, b = edge['from'] in chosen, edge['to'] in chosen
        if a and b:internal.append(copy.deepcopy(edge))
        elif a or b:boundary.append(copy.deepcopy(edge))
    return {'entityIds': sorted(chosen), 'edges': internal, 'boundaryEdges': boundary,
            'workGraphIds': [w['id'] for w in graph['workGraphs'] if set(w['memberIds']) & chosen],
            'exclusionContext': [copy.deepcopy(e) for e in graph['exclusionGroups'] if set(e['actionIds']) & chosen]}


def validate_plan_at(value):
    require(isinstance(value,str) and bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))?',value)), 'PLAN_TIME_CONSTRAINT')
    try:
        if 'T' in value:
            require(datetime.fromisoformat(value.replace('Z','+00:00')).tzinfo is not None,'PLAN_TIMEZONE_REQUIRED')
        else:date.fromisoformat(value)
    except (ValueError,TypeError):raise ValueError('PORTABLE_PLAN_TIME_LITERAL')
    return value


def validate_plan(plan):
    """Dispatch versioned Plan contracts without reinterpreting legacy v2."""
    if isinstance(plan, dict) and plan.get("schemaVersion") == 3:
        return validate_order_plan(plan)
    require(isinstance(plan, dict) and plan.get('schemaVersion') == 2 and plan.get('kind') == 'temporalPlan', 'PLAN_VERSION')
    require(set(plan) <= {'schemaVersion', 'kind', 'id', 'title', 'identitySpace', 'revision', 'status',
                         'steps', 'sequence', 'branches', 'timeConstraints'}, 'PLAN_FIELDS')
    require(type(plan.get('revision')) is int and plan['revision'] >= 1 and plan.get('status') == 'candidate' and
            all(isinstance(plan.get(k), str) and plan[k].strip() for k in ('id', 'title', 'identitySpace')), 'PLAN_IDENTITY')
    require(all(isinstance(plan.get(k), list) for k in ('steps', 'sequence', 'branches', 'timeConstraints')), 'PLAN_ARRAYS')
    steps = {}
    for step in plan['steps']:
        require(isinstance(step, dict) and set(step) == {'id', 'title', 'kind', 'state', 'ref'} and
                all(isinstance(step.get(k), str) and step[k].strip() for k in ('id', 'title')) and
                step['id'] not in steps and step['kind'] in ('action', 'requirement') and
                step['state'] in ('planned', 'possible'), 'PLAN_STEP')
        validate_reference(step['ref']);require('kind' not in step['ref'],'PLAN_ENTITY_REFERENCE');require(step['ref']['mode'] == 'current', 'PLAN_CURRENT_TARGET_REQUIRED')
        steps[step['id']] = step
    successors = {i: set() for i in steps};pairs = set();placed = set()
    for edge in plan['sequence']:
        require(isinstance(edge, dict) and set(edge) <= {'before', 'after', 'minDelayDays'} and
                edge.get('before') in steps and edge.get('after') in steps and edge['before'] != edge['after'] and
                (edge['before'], edge['after']) not in pairs, 'PLAN_SEQUENCE')
        if 'minDelayDays' in edge:require(type(edge['minDelayDays']) in (int, float) and edge['minDelayDays'] >= 0, 'PLAN_DELAY')
        successors[edge['before']].add(edge['after']);pairs.add((edge['before'], edge['after']))
        placed.update((edge['before'], edge['after']))
    visiting, visited = set(), set()
    def visit(i):
        require(i not in visiting, 'PLAN_SEQUENCE_CYCLE')
        if i in visited:return
        visiting.add(i)
        for j in successors[i]:visit(j)
        visiting.remove(i);visited.add(i)
    for i in steps:visit(i)
    branch_ids, branched = set(), set()
    for branch in plan['branches']:
        require(isinstance(branch, dict) and set(branch) == {'id', 'title', 'cases'} and
                branch.get('id') not in branch_ids and isinstance(branch.get('id'), str) and
                isinstance(branch.get('title'), str) and isinstance(branch.get('cases'), list) and
                len(branch['cases']) >= 2, 'PLAN_BRANCH')
        branch_ids.add(branch['id']);case_ids = set()
        for case in branch['cases']:
            require(isinstance(case, dict) and set(case) <= {'id', 'title', 'condition', 'stepIds', 'emptyOutcome'} and
                    isinstance(case.get('id'), str) and case['id'] not in case_ids and
                    isinstance(case.get('title'), str) and isinstance(case.get('condition'), str) and
                    isinstance(case.get('stepIds'), list) and len(case['stepIds']) == len(set(case['stepIds'])) and
                    set(case['stepIds']) <= set(steps) and not (set(case['stepIds']) & branched), 'PLAN_CASE')
            require((bool(case['stepIds']) and 'emptyOutcome' not in case) or
                    (not case['stepIds'] and case.get('emptyOutcome') == 'no-placed-work'), 'PLAN_EMPTY_OUTCOME')
            require(all(steps[i]['state'] == 'possible' for i in case['stepIds']), 'PLAN_BRANCH_POSSIBLE')
            case_ids.add(case['id']);branched.update(case['stepIds'])
        def reaches(start, goal):
            queue = [start];seen = set()
            while queue:
                current = queue.pop()
                if current == goal:return True
                if current not in seen:seen.add(current);queue.extend(successors[current])
            return False
        for i, left in enumerate(branch['cases']):
            for right in branch['cases'][i + 1:]:
                require(not any(reaches(a, b) or reaches(b, a) for a in left['stepIds'] for b in right['stepIds']),
                        'PLAN_EXCLUSIVE_BRANCH_DEPENDENCY')
    for rule in plan['timeConstraints']:
        require(isinstance(rule, dict) and set(rule) == {'stepId', 'type', 'at', 'strength', 'basis'} and
                rule.get('stepId') in steps and rule.get('type') in ('deadline', 'notBefore') and
                rule.get('strength') in ('hard', 'soft') and isinstance(rule.get('basis'), str) and bool(rule['basis']) and
                isinstance(rule.get('at'), str) and bool(rule['at']),
                'PLAN_TIME_CONSTRAINT')
        validate_plan_at(rule['at'])
        placed.add(rule['stepId'])
    # Retained placements may lose their relative anchor on delete; do not invent
    # dates/order or delete the surviving records. Their missing position is a projection.
    require(all(s['state'] != 'possible' or i in branched for i, s in steps.items()), 'PLAN_POSSIBLE_WITHOUT_BRANCH')
    return plan


def plan_lanes(plan):
    return [plan['mainStepIds']]+[case['stepIds'] for fork in plan['forks'] for case in fork['cases']]


def validate_order_plan(plan):
    """Decision Plan v3: complete lane membership, independent choices and time."""
    require(set(plan)=={'schemaVersion','kind','id','title','identitySpace','revision','status',
        'steps','mainStepIds','forks','timeConstraints'}, 'PLAN_FIELDS')
    require(plan['kind']=='temporalPlan' and plan['status']=='candidate' and
        type(plan['revision']) is int and plan['revision']>=1 and
        all(isinstance(plan[k],str) and plan[k].strip() for k in ('id','title','identitySpace')), 'PLAN_IDENTITY')
    require(all(isinstance(plan[k],list) for k in ('steps','mainStepIds','forks','timeConstraints')), 'PLAN_ARRAYS')
    legacy={k:copy.deepcopy(v) for k,v in plan.items() if k not in ('mainStepIds','forks')}
    legacy.update(schemaVersion=2,sequence=[],branches=[])
    ids=[]
    for step in legacy['steps']:
        require(isinstance(step,dict) and step.get('kind') in ('requirement','decision','action'), 'PLAN_STEP')
        ids.append(step.get('id'));step['state']='planned' if step.get('state')=='possible' else step.get('state')
        if step['kind']=='decision':step['kind']='action'
    validate_plan(legacy)
    forks=set();cases=set()
    for fork in plan['forks']:
        require(isinstance(fork,dict) and {'id','title','afterStepId','cases'}<=set(fork)<={'id','title','afterStepId','cases','startAt','end'} and
            isinstance(fork['id'],str) and fork['id'].strip() and fork['id'] not in forks and
            isinstance(fork['title'],str) and fork['title'].strip() and
            (fork['afterStepId'] is None or fork['afterStepId'] in plan['mainStepIds']) and
            isinstance(fork['cases'],list) and len(fork['cases'])>=2, 'PLAN_FORK')
        forks.add(fork['id'])
        if 'startAt' in fork:validate_plan_at(fork['startAt'])
        if 'end' in fork:
            end=fork['end']
            require(isinstance(end,dict) and {'title'}<=set(end)<={'title','at'} and isinstance(end['title'],str) and end['title'].strip(),'PLAN_FORK_END')
            if 'at' in end:validate_plan_at(end['at'])
            if fork.get('startAt') and end.get('at') and ('T' in fork['startAt'])==('T' in end['at']):
                start,finish=(datetime.fromisoformat(v.replace('Z','+00:00')) if 'T' in v else date.fromisoformat(v) for v in (fork['startAt'],end['at']))
                require(start<=finish,'PLAN_FORK_TIME_ORDER')
        for case in fork['cases']:
            require(isinstance(case,dict) and set(case)=={'id','title','decisionIds','stepIds'} and
                isinstance(case['id'],str) and case['id'].strip() and case['id'] not in cases and
                isinstance(case['title'],str) and case['title'].strip() and
                isinstance(case['decisionIds'],list) and all(isinstance(i,str) and i.strip() for i in case['decisionIds']) and
                len(case['decisionIds'])==len(set(case['decisionIds'])) and isinstance(case['stepIds'],list), 'PLAN_CASE')
            cases.add(case['id'])
    lanes=plan_lanes(plan);flat=[i for lane in lanes for i in lane]
    require(all(isinstance(i,str) for i in flat) and len(flat)==len(set(flat))==len(ids) and set(flat)==set(ids), 'PLAN_LANE_MEMBERSHIP')
    require(all(step['state'] in ('planned','possible') for step in plan['steps']), 'PLAN_STEP')
    return plan


def place_order_plan(plan,request,ref,node):
    result=copy.deepcopy(plan);sid=request.get('stepId');lanes=plan_lanes(result)
    existing=next((s for s in result['steps'] if s['id']==sid),None)
    previous=next((lane for lane in lanes if sid in lane),None)
    index=previous.index(sid) if previous is not None else None
    if request['op']=='unplace':
        require(existing is not None,'PLACEMENT_UNKNOWN')
        result['steps']=[s for s in result['steps'] if s['id']!=sid]
        previous.remove(sid);result['timeConstraints']=[r for r in result['timeConstraints'] if r['stepId']!=sid]
        for fork in result['forks']:
            if fork['afterStepId']==sid:fork['afterStepId']=None
    else:
        require(ref is not None and node and node['kind'] in ('requirement','decision','action'),'PLACEMENT_GRAPH_BLOCK')
        require(sid and (existing is None or all(existing['ref'][k]==ref[k] for k in ('packageId','identitySpace','nodeId'))),'PLACEMENT_TARGET_MISMATCH')
        if existing is None:result['steps'].append({'id':sid,'title':node['title'],'kind':node['kind'],'state':'planned','ref':copy.deepcopy(ref)})
        target=previous if previous is not None else result['mainStepIds']
        if 'caseId' in request:
            target=next((c['stepIds'] for f in result['forks'] for c in f['cases'] if c['id']==request['caseId']),None) if request['caseId'] else result['mainStepIds']
            require(target is not None,'PLAN_CASE_UNKNOWN')
        if previous is not None:previous.remove(sid)
        if 'afterStepId' in request:
            anchor=request['afterStepId'];require(anchor is None or anchor in target,'PLAN_LANE_MEMBERSHIP')
            target.insert(0 if anchor is None else target.index(anchor)+1,sid)
        elif previous is target and index is not None:target.insert(index,sid)
        else:target.append(sid)
        if 'at' in request:
            result['timeConstraints']=[r for r in result['timeConstraints'] if not(r['stepId']==sid and r['type']=='notBefore')]
            if request['at']:result['timeConstraints'].append({'stepId':sid,'type':'notBefore','at':request['at'],'strength':'soft','basis':request['note']})
    if 'deadline' in request:
        result['timeConstraints']=[r for r in result['timeConstraints'] if not(r['stepId']==sid and r['type']=='deadline')]
        if request['deadline']:result['timeConstraints'].append({'stepId':sid,'type':'deadline','at':request['deadline'],'strength':'soft','basis':request['note']})
    result['revision']+=1;validate_plan(result);return result


def window_matches(at,window):
    if not window:return True
    day=at[:10]
    return (not window.get('from') or day>=window['from']) and (not window.get('to') or day<=window['to'])


def validate_view_spec(spec):
    require(isinstance(spec,dict) and set(spec)<= {'kind','id','showExcludedAlternatives','shownCases','historyWindow','planWindow',
        'camera','expandedOccurrenceIds','groupIds','workGraphId','showLowLevel','compactGraph','focusPositions','showAllBlocks','historyMode'},'VIEW_SCHEMA')
    require(type(spec.get('showExcludedAlternatives',False)) is bool and type(spec.get('compactGraph',False)) is bool and
            type(spec.get('showAllBlocks',False)) is bool,'VIEW_SCHEMA')
    require(spec.get('kind') in ('graph','workGraph','focus') and (spec['kind']=='graph' or isinstance(spec.get('id'),str) and bool(spec['id'].strip())),'VIEW_KIND')
    require(type(spec.get('showLowLevel',False)) is bool and (spec.get('workGraphId') is None or isinstance(spec['workGraphId'],str) and bool(spec['workGraphId'].strip())),'VIEW_SCHEMA')
    require(spec.get('historyMode','important') in ('important','meaningful','technical','all'),'VIEW_HISTORY_MODE')
    for name in ('historyWindow','planWindow'):
        w=spec.get(name,{})
        require(isinstance(w,dict) and set(w)<= {'from','to'},'VIEW_WINDOW')
        for value in w.values():
            try:require(isinstance(value,str) and date.fromisoformat(value).isoformat()==value,'VIEW_WINDOW')
            except (ValueError,TypeError):raise ValueError('PORTABLE_VIEW_WINDOW')
        require(not w.get('from') or not w.get('to') or w['from']<=w['to'],'VIEW_WINDOW')
    require(isinstance(spec.get('shownCases',{}),dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in spec.get('shownCases',{}).items()),'VIEW_CASES')
    require(all(isinstance(spec.get(k,[]),list) and len(spec.get(k,[]))==len(set(spec.get(k,[]))) and
        all(isinstance(i,str) for i in spec.get(k,[])) for k in ('expandedOccurrenceIds','groupIds')),'VIEW_IDS')
    if 'focusPositions' in spec:
        overrides=spec['focusPositions']
        require(spec.get('kind')=='focus' and isinstance(overrides,dict) and len(overrides)<=256 and
            all(isinstance(node_id,str) and 0<len(node_id)<=250 and isinstance(pos,dict) and
                set(pos)=={'x','y'} and all(type(value) in (int,float) and
                abs(value)<1e7 and value==value for value in pos.values())
                for node_id,pos in overrides.items()),'VIEW_FOCUS_POSITIONS')
    if 'camera' in spec:
        c=spec['camera'];require(isinstance(c,dict) and set(c)=={'x','y','width','height'} and
            all(type(v) in (int,float) and abs(v)<1e8 for v in c.values()) and c['width']>0 and c['height']>0,'VIEW_CAMERA')
    return spec


def remove_plan_references(plan, package_id, identity_space, node_ids):
    validate_plan(plan)
    removed = {s['id'] for s in plan['steps'] if s['ref']['packageId'] == package_id and
               s['ref']['identitySpace'] == identity_space and s['ref']['nodeId'] in node_ids}
    if not removed:return copy.deepcopy(plan), []
    result = copy.deepcopy(plan)
    result['steps'] = [s for s in result['steps'] if s['id'] not in removed]
    result['timeConstraints'] = [r for r in result['timeConstraints'] if r['stepId'] not in removed]
    if result['schemaVersion']==3:
        for lane in plan_lanes(result):lane[:]=[i for i in lane if i not in removed]
        for fork in result['forks']:
            if fork['afterStepId'] in removed:fork['afterStepId']=None
        result['revision']+=1;validate_plan(result);return result,sorted(removed)
    result['sequence'] = [e for e in result['sequence'] if not {e['before'], e['after']} & removed]
    for branch in result['branches']:
        for case in branch['cases']:
            case['stepIds'] = [i for i in case['stepIds'] if i not in removed]
            if not case['stepIds']:case['emptyOutcome'] = 'no-placed-work'
    # Keep surviving records even when their only relative anchor was removed.
    # Read projections expose an unresolved position; no date/order is invented.
    result['revision'] += 1
    validate_plan(result)
    return result, sorted(removed)


def validate_graph_payload(graph, kernel):
    if isinstance(graph, dict) and graph.get('coreModel') == 'rdg-decision-v1':
        kernel.validate(graph)
        require(not (set(graph) - DECISION_GRAPH_FIELDS),
                'UNSUPPORTED_GRAPH_FIELDS:' + ','.join(sorted(set(graph) - DECISION_GRAPH_FIELDS)))
        return graph
    for ref in graph.get('externalRefs',[]):
        require(isinstance(ref,dict) and set(ref)=={'id','localId','direction','relation','target','observed','reason'} and
                ref['localId'] in kernel.entities(graph) and ref['direction'] in ('incoming','outgoing','peer') and
                isinstance(ref['relation'],dict) and ref['relation'].get('type') in set(kernel.PAIRS)|{'EXCLUDES'},'EXTERNAL_RELATION')
        validate_reference(ref['target'])
        require(ref['observed'].get('id')==ref['target']['nodeId'] and
                ref['observed'].get('revision')==ref['target']['revision'],'EXTERNAL_OBSERVED_PIN')
    for edge in graph['edges']:
        for ref in edge.get('origin',{}).get('externalRequirementRefs',[]):validate_reference(ref)
    for refs in graph.get('entityLineage',{}).values():
        require(isinstance(refs,list),'ENTITY_LINEAGE')
        for ref in refs:validate_reference(ref)
    kernel.validate(graph)
    allowed_fields = DECISION_GRAPH_FIELDS if graph.get('coreModel') == 'rdg-decision-v1' else CURRENT_GRAPH_FIELDS
    require(not (set(graph) - allowed_fields), 'UNSUPPORTED_GRAPH_FIELDS:' + ','.join(sorted(set(graph) - allowed_fields)))
    require(not graph.get('collections'), 'UNSUPPORTED_COLLECTION_CONTENT')
    return graph


def prepare_effects(command, snapshots, policies, allocation):
    kernel = policies['kernel'];op = command['op'];target_id = command['targetPackageId']
    target_graph = snapshots['packages'][target_id]['graph']
    require(target_graph.get('coreModel') != 'rdg-decision-v1', 'UNSUPPORTED_PROFILE_CAPABILITY')
    require(op in ('apply_ready', 'delete', 'unlink'), 'OPERATION_UNSUPPORTED')
    before_snapshot = snapshots['packages'][target_id];before = before_snapshot['graph']
    validate_graph_payload(before, kernel)
    require(before_snapshot['role'] in ('working', 'copy'), 'TARGET_ROLE')
    require(command.get('expectedGraphRevision') == before['revision'], 'GRAPH_REVISION_CONFLICT')
    require(command.get('expectedPackageRevision') == before_snapshot['revision'], 'PACKAGE_REVISION_CONFLICT')
    event = {'id': allocation['eventId'], 'type': 'requested', 'by': policies.get('attribution',command.get('by', 'assistant')),
             'note': command['note'], 'recordedAt': allocation['recordedAt'],
             'verifiedTrustReceipt': {'mode': 'coordinator-planning'}}
    event_context = policies.get('eventContext', {})
    require(isinstance(event_context, dict) and
            set(event_context) <= {'authorityPrincipal', 'verifiedTrustReceipt'}, 'EVENT_CONTEXT')
    event.update(copy.deepcopy(event_context))
    require(event['by'] in ('user', 'assistant') and isinstance(event['note'], str) and bool(event['note'].strip()), 'ATTRIBUTION')
    source = None;mapping = {};removed = set();graph = copy.deepcopy(before);inserted_scope = None
    if op == 'delete':
        require(isinstance(command.get('nodeIds'), list) and bool(command['nodeIds']) and
                len(set(command['nodeIds'])) == len(command['nodeIds']), 'DELETE_TARGETS')
        removed = set(command['nodeIds'])
    if op == 'apply_ready':
        source_id = command['sourcePackageId'];source = snapshots['packages'][source_id]
        require(source['role'] in ('ready', 'lens'), 'SOURCE_ROLE')
        validate_graph_payload(source['graph'], kernel);kernel.validate_role(source['graph'], source['role'], source.get('plan'))
        require(command.get('sourcePin') == {'revision': source['revision'], 'sha256': digest(source['graph'])}, 'SOURCE_REVISION_CONFLICT')
        require(command['mode'] in ('ADD_ROOT', 'REPLACE_R'), 'APPLY_MODE')
        if command['mode'] == 'REPLACE_R':
            nid = command.get('targetRequirementId')
            require(kernel.entities(before).get(nid, {}).get('kind') == 'requirement', 'REPLACE_REQUIREMENT_REQUIRED')
            removed = {nid}
    if removed:
        require(snapshots.get('incomingComplete') is True, 'INCOMING_CLOSURE_UNCONFIRMED')
        removal_event = copy.deepcopy(event)
        if op == 'apply_ready':removal_event['id'] = allocation['removalEventId']
        graph, _ = kernel.apply(before, {'schemaVersion': 1, 'expectedRevision': before['revision'],
            'operations': [{'op': 'graph_edit', 'action': 'core_remove', 'data': {'nodeIds': sorted(removed)},
                            'event': removal_event}]}, True, coordinated=True)
    if op == 'unlink':
        graph, _ = kernel.apply(before, {'schemaVersion': 1, 'expectedRevision': before['revision'],
            'operations': [{'op': 'graph_edit', 'action': 'core_unlink', 'data': command['data'], 'event': event}]}, True)
    if op == 'apply_ready':
        original = source['graph'];mapping = allocation['idMap'];imported = remap_graph(original, mapping)
        existing = definitions(before)
        for namespace in existing:
            require(not (set(existing[namespace]) & set(mapping[namespace].values())), 'DESTINATION_ID_COLLISION')
        new_root = imported['rootRequirementId'];inserted_ids = {n['id'] for n in imported['nodes'] + imported['objects']}
        for n in imported['nodes']:
            if n['id'] == new_root:n['status'] = 'active'
        for field in ('nodes', 'objects', 'edges', 'workGraphs', 'workGraphLinks', 'exclusionGroups'):
            graph[field].extend(imported[field])
        if removed:
            if before['rootRequirementId'] in removed:graph['rootRequirementId'] = new_root
            previous = {w['id']: w for w in before['workGraphs']}
            for scope in graph['workGraphs']:
                old = previous.get(scope['id'])
                if old:
                    scope['rootIds'] = [new_root if i in removed else i for i in old['rootIds']]
                    scope['memberIds'] = [new_root if i in removed else i for i in old['memberIds']]
        candidates = [w for w in imported['workGraphs'] if set(w['memberIds']) == inserted_ids and new_root in w['rootIds']]
        if candidates:inserted_scope = candidates[0]['id']
        else:
            inserted_scope = allocation['scopeId']
            require(inserted_scope not in {w['id'] for w in graph['workGraphs']}, 'SCOPE_ID_COLLISION')
            graph['workGraphs'].append({'id': inserted_scope, 'title': original['title'],
                                       'rootIds': [new_root], 'memberIds': sorted(inserted_ids)})
        destination = command.get('targetWorkGraphId')
        if destination:
            scope = next((w for w in graph['workGraphs'] if w['id'] == destination), None)
            require(scope is not None, 'TARGET_WORK_GRAPH_UNKNOWN')
            scope['memberIds'] = sorted(set(scope['memberIds']) | inserted_ids)
        for rec in imported.get('lensRecommendations', []):
            if 'targetId' not in rec and 'targetWorkGraphId' not in rec:rec['targetWorkGraphId'] = inserted_scope
            graph.setdefault('lensRecommendations', []).append(rec)
        graph['events'].append({**event, 'type': 'ready_graph_applied', 'sourcePackageId': command['sourcePackageId'],
            'sourcePin': copy.deepcopy(command['sourcePin']), 'mode': command['mode'], 'removedIds': sorted(removed),
            'idMap': copy.deepcopy(mapping), 'insertedWorkGraphId': inserted_scope,
            'removalEventId': allocation.get('removalEventId') if removed else None})
    for scope in graph['workGraphs']:
        old = next((w for w in before['workGraphs'] if w['id'] == scope['id']), None)
        if old and old != scope:
            for root_id in old['rootIds']:
                kernel_for_graph(kernel, before).guard(kernel.entities(before)[root_id], event,
                             'remove' if root_id in removed else 'edit')
    graph['revision'] = before['revision'] + 1
    kernel.validate(graph)
    plan_changes, removed_placements = {}, {}
    for owner, current in sorted(snapshots.get('plans', {}).items()):
        plan = current['plan']
        after, step_ids = remove_plan_references(plan, target_id, before['identitySpace'], removed)
        if step_ids:
            plan_changes[owner] = after;removed_placements[owner] = step_ids
    rights = [{'owner': target_id, 'permission': 'graph.write'}]
    if source is not None:rights.append({'owner': command['sourcePackageId'], 'permission': 'graph.read'})
    rights.extend({'owner': owner, 'permission': 'plan.edit'} for owner in sorted(plan_changes))
    report = {'schemaVersion': 1, 'requestSHA256': digest(command), 'operation': op,
              'readSet': {key: {'revision': snap['revision'], 'graphSHA256': digest(snap['graph'])}
                          for key, snap in sorted(snapshots['packages'].items())},
              'planReadSet': {key: {'revision': snap['plan']['revision'], 'sha256': digest(snap['plan'])}
                              for key, snap in sorted(snapshots.get('plans', {}).items())},
              'graphs': {target_id: graph}, 'plans': plan_changes, 'idMap': mapping,
              'removedIds': sorted(removed), 'removedPlacements': removed_placements,
              'insertedWorkGraphId': inserted_scope, 'permissions': rights,
              'detached': kernel.detached_components(graph), 'recordedAt': allocation['recordedAt']}
    return EffectPlan(encoded(report))


def fragment(source_package, source, focus, kernel, include_descendants=True):
    """Capture state plus qualified boundary meaning. No fictitious local endpoints."""
    if source.get('coreModel')=='rdg-decision-v1':return decision_fragment(source,focus,kernel,include_descendants)
    validate_graph_payload(source,kernel)
    inventory=capture(source,focus,kernel,include_descendants);chosen=set(inventory['entityIds'])
    result=copy.deepcopy(source);ns=kernel.entities(source)
    for family in ('nodes','objects'):result[family]=[n for n in result[family] if n['id'] in chosen]
    result['edges']=inventory['edges']
    result['workGraphs']=[{**w,'rootIds':[i for i in w['rootIds'] if i in chosen],
        'memberIds':[i for i in w['memberIds'] if i in chosen]} for w in result['workGraphs'] if set(w['memberIds']) & chosen]
    scopes={w['id'] for w in result['workGraphs']}
    result['workGraphLinks']=[w for w in result['workGraphLinks'] if set(w)<=scopes]
    result['coreDocumentVersion']=2
    if focus['kind']!='graph':
        result['rootRequirementId']=focus['id'] if focus['kind']=='requirement' else None
        result['fragmentFocus']=copy.deepcopy(focus)
    result['lensRecommendations']=[r for r in result.get('lensRecommendations',[]) if
        ('targetId' not in r or r['targetId'] in chosen) and ('targetWorkGraphId' not in r or r['targetWorkGraphId'] in scopes)]
    for field in ('factLineage','entityLineage'):
        result[field]={i:v for i,v in result.get(field,{}).items() if i in chosen}
    edge_ids={e['id'] for e in result['edges']}
    result['relationLineage']={i:v for i,v in result.get('relationLineage',{}).items() if i in edge_ids}
    result['externalRefs']=[r for r in result.get('externalRefs',[]) if r['localId'] in chosen]
    def outside(local,external,relation,direction,suffix):
        result['externalRefs'].append({'id':source_package+':'+suffix,'localId':local,'direction':direction,
            'relation':copy.deepcopy(relation),'target':reference(source_package,source,external,'historical' if relation.get('archived') else 'current'),
            'observed':copy.deepcopy(ns[external]),'reason':'outside-captured-fragment'})
    for edge in inventory['boundaryEdges']:
        local=edge['to'] if edge['to'] in chosen else edge['from']
        external=edge['from'] if edge['to'] in chosen else edge['to']
        outside(local,external,edge,'incoming' if edge['to'] in chosen else 'outgoing',edge['id'])
    for edge in result['edges']:
        origin=edge.get('origin',{})
        if origin.get('role')=='subgoal':
            external=[i for i in origin['requirementIds'] if i not in chosen]
            origin['requirementIds']=[i for i in origin['requirementIds'] if i in chosen]
            if external:origin.setdefault('externalRequirementRefs',[]).extend(reference(source_package,source,i) for i in external)
    groups=[]
    for group in source['exclusionGroups']:
        included=[i for i in group['actionIds'] if i in chosen]
        omitted=[i for i in group['actionIds'] if i not in chosen]
        if len(included)>=2:groups.append({**copy.deepcopy(group),'actionIds':included})
        for local in included:
            for external in omitted:outside(local,external,{'id':group['id'],'type':'EXCLUDES','reason':group['reason']},'peer',group['id']+':'+local+':'+external)
    result['exclusionGroups']=groups
    return result,inventory


def copy_graph(source_package, source, focus, mapping, identity_space, graph_id, kernel, include_descendants=True):
    if source.get('coreModel')=='rdg-decision-v1':return decision_copy(source_package,source,focus,mapping,identity_space,graph_id,kernel,include_descendants)
    captured,inventory=fragment(source_package,source,focus,kernel,include_descendants)
    observed={r['target']['nodeId']:kernel.external_pin_key(r['target']) for r in captured.get('externalRefs',[])
              if r['target']['packageId']==source_package and r['target']['identitySpace']==source['identitySpace']}
    graph=remap_graph(captured,mapping,observed);key=digest(source)
    graph.update(identitySpace=identity_space,id=graph_id,revision=1,events=[])
    for ref in graph.get('externalRefs',[]):ref['id']=digest([identity_space,ref['localId'],ref['id']])
    graph.setdefault('inheritedHistory',{})[key]={'source':{'packageId':source_package,'identitySpace':source['identitySpace'],
        'graphRevision':source['revision'],'sha256':key},'events':copy.deepcopy(source['events']),
        'eventsSHA256':digest(source['events'])}
    graph['factLineage']={};graph['relationLineage']={};graph['entityLineage']={}
    def inherited(owner,event_id,relation=False):
        event,subject,events=kernel.fact_record(source,owner,event_id,relation)
        require(bool(event),'COPY_FACT_SOURCE_MISSING')
        history_key=key if events is source['events'] else source['relationLineage' if relation else 'factLineage'][owner][event_id]['historyKey']
        return {'historyKey':history_key,'sourceId':subject}
    for old in inventory['entityIds']:
        new=mapping['entity'][old];node=kernel.entities(source)[old]
        lineage=[reference(source_package,source,old,'inherited'),*copy.deepcopy(source.get('entityLineage',{}).get(old,[]))]
        graph['entityLineage'][new]=lineage
        event_ids={node.get('selectedEventId'),node.get('result',{}).get('eventId'),node.get('assessment',{}).get('eventId'),node.get('review',{}).get('eventId')}
        for finding in node.get('qrpe',[]):event_ids.update((finding.get('eventId'),finding.get('resolutionEventId')))
        event_ids.update(c.get('eventId') for c in node.get('review',{}).get('causes',[]))
        links={eid:inherited(old,eid) for eid in event_ids if eid}
        if links:graph['factLineage'][new]=links
    for edge in captured['edges']:
        if edge.get('origin',{}).get('role')=='unresolved':
            eid=edge['origin']['lossEventId'];graph['relationLineage'][mapping['edge'][edge['id']]]={eid:inherited(edge['id'],eid,True)}
    validate_graph_payload(graph,kernel)
    return graph,inventory


def copy_plan(plan,source_package,target_package,graph,mapping):
    """Keep full temporal context. Only captured local targets become new instances."""
    validate_plan(plan);result=copy.deepcopy(plan);result['revision']=1
    result['id']=graph['id']+'-plan';result['identitySpace']=graph['identitySpace']
    if plan['schemaVersion']==3:
        def new(kind,old):return str(uuid.uuid5(uuid.UUID(graph['identitySpace']),kind+':'+old))
        step_map={s['id']:new('placement',s['id']) for s in plan['steps']}
        result['mainStepIds']=[step_map[i] for i in plan['mainStepIds']]
        for step in result['steps']:step['id']=step_map[step['id']]
        for rule in result['timeConstraints']:rule['stepId']=step_map[rule['stepId']]
        for fork in result['forks']:
            fork['id']=new('fork',fork['id']);fork['afterStepId']=step_map.get(fork['afterStepId'])
            for case in fork['cases']:
                case['id']=new('case',case['id']);case['stepIds']=[step_map[i] for i in case['stepIds']]
                case['decisionIds']=[mapping['entity'][i] for i in case['decisionIds'] if i in mapping['entity']]
    mapped,external=[],[]
    for step in result['steps']:
        ref=step['ref']
        if (ref['packageId']==source_package and ref['nodeId'] in mapping['entity'] and
                ref['identitySpace']==graph['entityLineage'][mapping['entity'][ref['nodeId']]][0]['identitySpace']):
            step['ref']=reference(target_package,graph,mapping['entity'][ref['nodeId']]);mapped.append(step['id'])
        else:external.append(step['id'])
    validate_plan(result)
    return result,{'mappedStepIds':mapped,'externalContextStepIds':external}


def insert_graph(target, imported, event, scope_id, kernel):
    """Append independent instances and their lineage; preserved external refs stay qualified."""
    validate_graph_payload(target,kernel);validate_graph_payload(imported,kernel)
    for namespace,ids in definitions(target).items():
        require(not set(ids)&set(definitions(imported)[namespace]),'INSERT_ID_COLLISION')
    if target.get('coreModel')=='rdg-decision-v1':return decision_insert(target,imported,event,scope_id,kernel)
    graph=copy.deepcopy(target);graph['coreDocumentVersion']=2
    for field in ('nodes','objects','edges','workGraphs','workGraphLinks','exclusionGroups'):
        graph[field].extend(copy.deepcopy(imported[field]))
    for field in ('inheritedHistory','factLineage','relationLineage','entityLineage'):
        for key,value in imported.get(field,{}).items():
            previous=graph.setdefault(field,{}).get(key)
            require(previous is None or previous==value,'INSERT_LINEAGE_CONFLICT')
            graph[field][key]=copy.deepcopy(value)
    graph.setdefault('externalRefs',[]).extend(copy.deepcopy(imported.get('externalRefs',[])))
    members=sorted(kernel.entities(imported))
    scope=next((w['id'] for w in imported['workGraphs'] if set(w['memberIds'])==set(members)),None)
    if scope is None:
        scope=scope_id
        graph['workGraphs'].append({'id':scope,'title':imported['title'],'memberIds':members,
                                   'rootIds':[imported['rootRequirementId']] if imported.get('rootRequirementId') else []})
    for row in copy.deepcopy(imported.get('lensRecommendations',[])):
        if 'targetId' not in row and 'targetWorkGraphId' not in row:row['targetWorkGraphId']=scope
        graph.setdefault('lensRecommendations',[]).append(row)
    graph['events'].append(copy.deepcopy(event));graph['revision']=target['revision']+1
    validate_graph_payload(graph,kernel)
    return graph,scope


def append_plan(target, incoming, step_mapping, branch_mapping, case_mapping):
    validate_plan(target);validate_plan(incoming)
    result=copy.deepcopy(target);part=copy.deepcopy(incoming)
    require(not {s['id'] for s in target['steps']}&set(step_mapping.values()),'PLAN_INSERT_ID_COLLISION')
    for step in part['steps']:step['id']=step_mapping[step['id']]
    if part['schemaVersion']==3:
        require(target['schemaVersion']==3,'PLAN_VERSION')
        for rule in part['timeConstraints']:rule['stepId']=step_mapping[rule['stepId']]
        part['mainStepIds']=[step_mapping[i] for i in part['mainStepIds']]
        for fork in part['forks']:
            old=fork['id'];fork['id']=branch_mapping[old];fork['afterStepId']=step_mapping.get(fork['afterStepId'])
            for case in fork['cases']:
                case['id']=case_mapping[(old,case['id'])];case['stepIds']=[step_mapping[i] for i in case['stepIds']]
        for field in ('steps','mainStepIds','forks','timeConstraints'):result[field].extend(part[field])
        result['revision']+=1;validate_plan(result);return result
    for edge in part['sequence']:
        edge['before']=step_mapping[edge['before']];edge['after']=step_mapping[edge['after']]
    for rule in part['timeConstraints']:rule['stepId']=step_mapping[rule['stepId']]
    for branch in part['branches']:
        old=branch['id'];branch['id']=branch_mapping[old]
        for case in branch['cases']:
            case['id']=case_mapping[(old,case['id'])]
            case['stepIds']=[step_mapping[i] for i in case['stepIds']]
    for field in ('steps','sequence','branches','timeConstraints'):result[field].extend(part[field])
    result['revision']+=1;validate_plan(result)
    return result


def presentation(graph, kernel, spec=None):
    """A view has no state of its own; layout keys use the existing shared codec."""
    spec=spec or {'kind':'graph'}
    validate_view_spec(spec)
    kind=spec.get('kind');slug=graph['id'];focus=None
    if kind=='focus':
        focus=spec['id']
        external = next((a for a in graph.get('externalActions',[]) if a['id']==focus),None)
        if graph.get('coreModel') == 'rdg-decision-v1' and external is not None:
            view={'entities':[],'edges':[],'terminalIds':[],'externalAction':copy.deepcopy(external),'viewOnly':True}
        else:
            view=kernel.focused_view(graph,focus)
    else:
        require(kind in ('graph','workGraph'),'VIEW_KIND')
        members=({n['id'] for n in graph['nodes']+graph['objects']}
                 if graph.get('coreModel') == 'rdg-decision-v1' else set(kernel.entities(graph)))
        if kind=='workGraph':
            work=next((w for w in graph['workGraphs'] if w['id']==spec.get('id')),None)
            require(work is not None,'VIEW_WORK_GRAPH_UNKNOWN')
            members=set(work['memberIds']);slug='full-'+work['id']
        view={'entities':[copy.deepcopy(n) for i,n in kernel.entities(graph).items() if i in members],
              'edges':[copy.deepcopy(e) for e in kernel.active_edges(graph) if e['from'] in members and e['to'] in members],
              'terminalIds':[],'viewOnly':True}
    if graph.get('coreModel') == 'rdg-decision-v1':
        if spec.get('groupIds'):
            groups=[g for g in graph['decisionGroups'] if g['id'] in spec['groupIds']]
            require(len(groups)==len(spec['groupIds']),'REFERENCE_MISSING:group')
            selected={i for g in groups for i in [g['parentId'],*(m['decisionId'] for m in g['members'])]}
            view['entities']=[n for n in view['entities'] if n['id'] in selected]
            view['edges']=[e for e in view['edges'] if e['from'] in selected and e['to'] in selected]
        decision=kernel.for_graph(graph)
        visible_ids={n['id'] for n in view['entities']}
        memberships=[r for r in decision.decision_memberships(graph)
                     if r['from'] in visible_ids and r['to'] in visible_ids]
        groups=[{**copy.deepcopy(g), 'members':[copy.deepcopy(m) for m in g['members']
                 if m['decisionId'] in visible_ids]} for g in graph['decisionGroups']
                if g['parentId'] in visible_ids and any(m['decisionId'] in visible_ids for m in g['members'])]
        group_ids={g['id'] for g in groups}
        visibility=[{**entry, 'visibleIds':[i for i in entry['visibleIds'] if i in visible_ids],
                          'hiddenIds':[i for i in entry['hiddenIds'] if i in visible_ids]}
                    for entry in kernel.group_visibility(graph,spec.get('showExcludedAlternatives',False))
                    if entry['groupId'] in group_ids]
        view.update(decisionMemberships=memberships, decisionGroups=groups,
                    groupVisibility=visibility,
                    support=kernel.support_state(graph),
                    showExcludedAlternatives=spec.get('showExcludedAlternatives',False))
    key_parts=([graph['identitySpace'],graph['id']] if graph.get('coreModel')=='rdg-decision-v1'
        else [graph['identitySpace'],slug]+([focus] if focus else []))
    key=json.dumps(key_parts,ensure_ascii=False,separators=(',',':'))
    return {**view,'spec':copy.deepcopy(spec),'graphKey':key}


def project_plan(plan,snapshots,kernel,spec=None):
    """Current placement projection, never a second task or fact database."""
    if plan is None:return None
    validate_plan(plan);rows=[]
    if plan['schemaVersion']==3:
        by_id={s['id']:s for s in plan['steps']}
        spec=spec or {};shown=spec.get('shownCases',{});order=[];markers=[];road=[]
        require(set(shown)<= {f['id'] for f in plan['forks']},'VIEW_CASES')
        def forks_after(anchor):
            for fork in plan['forks']:
                if fork['afterStepId']!=anchor:continue
                case_id=shown.get(fork['id'],fork['cases'][0]['id'])
                case=next((c for c in fork['cases'] if c['id']==case_id),None);require(case is not None,'VIEW_CASES')
                markers.append({**copy.deepcopy(fork),'shownCaseId':case_id});road.append({'type':'fork','forkId':fork['id']});order.extend(case['stepIds']);road.extend({'type':'placement','stepId':sid} for sid in case['stepIds'])
                if 'end' in fork:road.append({'type':'join','forkId':fork['id']})
        forks_after(None)
        for sid in plan['mainStepIds']:
            order.append(sid);road.append({'type':'placement','stepId':sid});forks_after(sid)
        for sid in order:
            step=by_id[sid];source=snapshots.get(step['ref']['packageId'],{});graph=source.get('graph')
            node=kernel.entities(graph).get(step['ref']['nodeId']) if graph else None
            reason=('source-unavailable' if graph is None else 'identity-mismatch' if graph['identitySpace']!=step['ref']['identitySpace']
                else 'missing-current-block' if node is None else 'kind-mismatch' if node['kind']!=step['kind'] else None)
            times=[r['at'][:10] for r in plan['timeConstraints'] if r['stepId']==sid]
            window=spec.get('planWindow',{})
            if times and ((window.get('from') and max(times)<window['from']) or (window.get('to') and min(times)>window['to'])):continue
            rows.append({'step':copy.deepcopy(step),'node':copy.deepcopy(node),'positioned':True,
                'bucket':'unresolved' if reason else 'future','reason':reason,
                'completion':copy.deepcopy(source.get('completion',{}).get(step['ref']['nodeId'],{})),
                'timeConstraints':[copy.deepcopy(r) for r in plan['timeConstraints'] if r['stepId']==sid]})
        return {'revision':plan['revision'],'placements':rows,'mainStepIds':copy.deepcopy(plan['mainStepIds']),
            'forks':markers,'shownStepIds':order,'road':road, 'currentGraphOnly':True,'factsCreated':False}
    positioned={r['stepId'] for r in plan['timeConstraints']}
    for edge in plan['sequence']:positioned.update((edge['before'],edge['after']))
    for step in plan['steps']:
        ref=step['ref'];source=snapshots.get(ref['packageId'],{});graph=source.get('graph')
        node=kernel.entities(graph).get(ref['nodeId']) if graph else None
        state=source.get('completion',{}).get(ref['nodeId'],{})
        reason=None;bucket='future'
        if graph is None:bucket='unresolved';reason='source-unavailable'
        elif graph['identitySpace']!=ref['identitySpace']:bucket='unresolved';reason='identity-mismatch'
        elif node is None:bucket='unresolved';reason='missing-current-block'
        elif node['kind']!=step['kind']:bucket='unresolved';reason='kind-mismatch'
        elif state.get('reviewRequired'):bucket='unresolved';reason='review-required'
        elif state.get('complete'):bucket='excluded';reason='already-confirmed'
        elif node.get('status') in ('inactive','superseded','rejected'):bucket='excluded';reason='inactive'
        elif node['kind']=='action' and node.get('status')!='selected':bucket='unresolved';reason='action-not-selected'
        elif node['kind']=='requirement' and node.get('status')!='active':bucket='unresolved';reason='requirement-not-active'
        if step['id'] not in positioned and bucket=='future':bucket='unresolved';reason='position-required'
        if step['state']=='possible' and bucket=='future':bucket='possible'
        rows.append({'step':copy.deepcopy(step),'node':copy.deepcopy(node),'completion':copy.deepcopy(state),
                     'bucket':bucket,'reason':reason,'positioned':step['id'] in positioned,
                     'timeConstraints':[copy.deepcopy(r) for r in plan['timeConstraints'] if r['stepId']==step['id']],
                     'sourceError':source.get('error')})
    return {'revision':plan['revision'],'placements':rows,'sequence':copy.deepcopy(plan['sequence']),
            'branches':copy.deepcopy(plan['branches']),'currentGraphOnly':True,'factsCreated':False}


def place(plan,request,ref=None,node=None):
    """Place/unplace one existing block, retaining unrelated anchors and branches."""
    validate_plan(plan)
    if plan['schemaVersion']==3:return place_order_plan(plan,request,ref,node)
    result=copy.deepcopy(plan);sid=request.get('stepId')
    existing=next((s for s in result['steps'] if s['id']==sid),None)
    if request['op']=='unplace':
        require(existing is not None,'PLACEMENT_UNKNOWN')
        result['steps']=[s for s in result['steps'] if s['id']!=sid]
        result['timeConstraints']=[r for r in result['timeConstraints'] if r['stepId']!=sid]
        result['sequence']=[e for e in result['sequence'] if sid not in (e['before'],e['after'])]
        for branch in result['branches']:
            for case in branch['cases']:
                case['stepIds']=[i for i in case['stepIds'] if i!=sid]
                if not case['stepIds']:case['emptyOutcome']='no-placed-work'
    else:
        require(ref is not None and node and node['kind'] in ('action','requirement'),'PLACEMENT_GRAPH_BLOCK')
        require(sid and (existing is None or existing['ref']['packageId']==ref['packageId'] and
                existing['ref']['identitySpace']==ref['identitySpace'] and existing['ref']['nodeId']==ref['nodeId']),
                'PLACEMENT_TARGET_MISMATCH')
        if existing is None:
            result['steps'].append({'id':sid,'title':node['title'],'kind':node['kind'],'state':'planned','ref':copy.deepcopy(ref)})
        if 'at' in request:
            result['timeConstraints']=[r for r in result['timeConstraints'] if not (r['stepId']==sid and r['type']=='notBefore')]
            if request['at']:result['timeConstraints'].append({'stepId':sid,'type':'notBefore','at':request['at'],
                'strength':'soft','basis':request['note']})
        if 'afterStepId' in request:
            result['sequence']=[e for e in result['sequence'] if e['after']!=sid]
            if request['afterStepId']:result['sequence'].append({'before':request['afterStepId'],'after':sid})
        require(any(r['stepId']==sid for r in result['timeConstraints']) or any(sid in (e['before'],e['after']) for e in result['sequence']),
                'PLACEMENT_POSITION_REQUIRED')
    result['revision']+=1;validate_plan(result);return result


def decision_capture(graph,focus,kernel,include_descendants=True):
    kernel=kernel.for_graph(graph) if hasattr(kernel,'for_graph') else kernel
    kernel.validate(graph);ns=kernel.entities(graph);kind=focus['kind'];ident=focus.get('id')
    require(kind in ('graph','requirement','decision','action','canon','finding','question','workGraph'),'COPY_FOCUS')
    edges=kernel.active_edges(graph);structural={'DRIVES','DECISION_MEMBER','DERIVES','INTRODUCES','REQUIRES_ACTION','FINDING_RESPONSE','FINDING_PROPOSAL'}
    if kind=='graph':chosen=set(ns)
    elif kind=='workGraph':
        work=next((w for w in graph['workGraphs'] if w['id']==ident),None);require(work is not None,'COPY_FOCUS_TARGET');chosen=set(work['memberIds'])
    else:
        require(ident in ns and ns[ident]['kind']==kind,'COPY_FOCUS_TARGET');chosen={ident}
    if include_descendants:
        while True:
            extra={e['to'] for e in edges if e['from'] in chosen and e['type'] in structural}
            if extra<=chosen:break
            chosen|=extra
    # Carry real provenance/support ancestors, rather than inventing primary R.
    while True:
        extra={e['from'] for e in edges if e['to'] in chosen and e['type'] in structural|COMPANION_TYPES}
        for g in graph['decisionGroups']:
            if g['parentId'] in chosen or any(m['decisionId'] in chosen for m in g['members']):extra|={g['parentId'],*(m['decisionId'] for m in g['members'])}
        for action in graph['externalActions']:
            if action['id'] in chosen:extra|=set(action['targetIds'])
        # A captured Decision must retain its local factual context. Pull the
        # same referenced instances into the fragment; remap them once later.
        for decision in graph['nodes']:
            if decision['kind']=='decision' and decision['id'] in chosen:
                extra.update(r['sourceId'] for r in kernel.decision_context(graph,decision['id']) if r['present']);extra.update(decision.get('impactTargetIds',[]))
                extra.update(p['sourceId'] for p in decision.get('analysisSources',[]) if p['sourceId'] in ns)
                # Process-to-process focused copies preserve configured factual
                # context subscriptions and their real source identities.
                # capture_ready strips these process-only edges before capture.
                extra.update(e['from'] for e in edges if e['type']=='DEPENDS_ON' and
                    e.get('dependencyPurpose')=='decisionContext' and e['to']==decision['id'])
        for f in graph['objects']:
            if f['kind']=='finding' and (f['subjectId'] in chosen or f['id'] in chosen):
                extra.add(f['id']);extra.update(i for i in [f['subjectId'],*f.get('evidenceIds',[]),*f.get('disposition',{}).get('evidenceIds',[]),f.get('disposition',{}).get('replacementId')] if i in ns)
                extra.update(e['from'] for e in edges if e['to']==f['id'] and e['type']=='DEPENDS_ON')
                extra.update(p['sourceId'] for p in f.get('analysisSources',[]) if p['sourceId'] in ns)
                for app in kernel.POLICIES.describe_applications(graph,kernel):
                    if app['targetId']==f['id']:extra.update(i for i in app['nodeIds'] if i in ns)
        for q in graph['objects']:
            if q['kind']!='question':continue
            scoped=[w for r in q['relatedRefs'] if r.get('kind')=='workGraph' for w in graph['workGraphs'] if w['id']==r['workGraphId']]
            if q['id'] in chosen or any(set(w['memberIds'])&chosen for w in scoped) or any(kernel.QUESTIONS.reference_id(graph,r,kernel,q) in chosen for r in q['relatedRefs']):
                extra.add(q['id'])
                rows=[*q['relatedRefs'],*q['sourceRefs'],
                      *(r for a in q['answers'] for r in a['sourceRefs']),
                      *(r for h in q.get('answerHistory',[]) for r in h['previous']['sourceRefs'])]
                extra.update(ident for r in rows if (ident:=kernel.QUESTIONS.reference_id(graph,r,kernel,q)) in ns)
                for ref in rows:
                    if ref.get('kind')=='workGraph':
                        area=next(w for w in graph['workGraphs'] if w['id']==ref['workGraphId'])
                        extra.update(area['memberIds'])
        extra.update(e['findingId'] for e in edges if e['type'] in ('FINDING_RESPONSE','FINDING_PROPOSAL') and (e['from'] in chosen or e['to'] in chosen))
        if extra<=chosen:break
        chosen|=extra
    internal=[copy.deepcopy(e) for e in graph['edges'] if e['from'] in chosen and e['to'] in chosen]
    boundary=[copy.deepcopy(e) for e in graph['edges'] if (e['from'] in chosen)!=(e['to'] in chosen)]
    return {'entityIds':sorted(chosen),'edges':internal,'boundaryEdges':boundary,
        'workGraphIds':[w['id'] for w in graph['workGraphs'] if set(w['memberIds'])&chosen]}


def decision_fragment(source,focus,kernel,include_descendants=True):
    inventory=decision_capture(source,focus,kernel,include_descendants);chosen=set(inventory['entityIds']);g=copy.deepcopy(source)
    for family in ('nodes','objects','externalActions'):g[family]=[n for n in g[family] if n['id'] in chosen]
    if 'contextGroups' in g and focus.get('kind')!='graph':
        needed={n['contextGroupId'] for n in g['objects'] if 'contextGroupId' in n};parents={r['id']:r['parentId'] for r in g['contextGroups']}
        while True:
            more={parents[i] for i in needed if parents.get(i) is not None}
            if more<=needed:break
            needed|=more
        g['contextGroups']=[r for r in g['contextGroups'] if r['id'] in needed]
    g['edges']=inventory['edges'];g['rootCauses']=[c for c in g['rootCauses'] if c['requirementId'] in chosen]
    if g['rootRequirementId'] not in chosen:g['rootRequirementId']=next((c['requirementId'] for c in g['rootCauses']),None)
    g['decisionGroups']=[v for v in g['decisionGroups'] if v['parentId'] in chosen and all(m['decisionId'] in chosen for m in v['members'])]
    g['workGraphs']=[{**w,'rootIds':[i for i in w['rootIds'] if i in chosen],'memberIds':[i for i in w['memberIds'] if i in chosen]} for w in g['workGraphs'] if set(w['memberIds'])&chosen]
    for field in ('factLineage','entityLineage'):g[field]={i:v for i,v in g.get(field,{}).items() if i in chosen}
    g['externalRefs']=[r for r in g.get('externalRefs',[]) if r['localId'] in chosen]
    # Policy definitions are reusable and contain no Process-specific entity IDs.
    # Only applications whose concrete endpoints survive the fragment may follow.
    existing={n['id'] for n in source['nodes']+source['objects']+source['externalActions']}
    g['dependencyBindings']=[b for b in g.get('dependencyBindings',[]) if
        (({b['targetId'],b['sourceId'],b['parentId']}|set(b.get('participantBindings',{}).values()))&existing)<=chosen
        and (b['targetId'] in chosen or focus is None)]
    return g,inventory


def decision_remap(graph,mapping):
    g=copy.deepcopy(graph);entity=mapping['entity']
    for family in ('nodes','objects','externalActions'):
        for n in g[family]:
            old=n['id'];n['id']=entity[old]
            if n['kind']=='question':
                answers=[*n['answers'],*(h['previous'] for h in n.get('answerHistory',[]))]
                ids={a['id']:str(uuid.uuid5(uuid.NAMESPACE_URL,n['id']+':answer:'+a['id'])) for a in answers}
                for answer in answers:
                    answer['id']=ids[answer['id']]
                for assessment in [*n['assessmentHistory'],*([n['assessment']] if 'assessment' in n else [])]:
                    assessment['id']=str(uuid.uuid5(uuid.NAMESPACE_URL,n['id']+':assessment:'+assessment['id']))
                    assessment['answerIds']=[ids[i] for i in assessment['answerIds']]
            if n['kind']=='question' or 'subjectRefs' in n or n['kind']=='canon':
                bindings={}
                theory_refs=[r.get('reference',r) for f in ('canonItems','recommendations') for item in n.get(f,[]) for r in [item.get('targetRef',{})] if r and r.get('kind') not in ('document','file')]
                for refs in ([n['relatedRefs'],n['sourceRefs'],*(a['sourceRefs'] for a in answers)] if n['kind']=='question' else [theory_refs] if n['kind']=='canon' else [n['subjectRefs']]):
                    for ref in refs:
                        if n['kind']=='canon' and ref.get('kind') in ('process','workGraph'):
                            key=json.dumps(['scope',ref['packageId'],ref['identitySpace'],ref['kind'],ref.get('workGraphId')],separators=(',',':'))
                            local=n.get('referenceBindings',{}).get(key)
                            if local is None and ref['identitySpace']==graph['identitySpace']:local='@process' if ref['kind']=='process' else ref['workGraphId']
                            if local=='@process':bindings[key]=local
                            elif local in mapping['workGraph']:bindings[key]=mapping['workGraph'][local]
                        if 'nodeId' in ref and ref.get('mode')!='historical':
                            key=json.dumps([ref.get(k) for k in ('packageId','identitySpace','nodeId')],separators=(',',':'))
                            local=n.get('referenceBindings',{}).get(key)
                            if local is None and ref.get('identitySpace')==graph['identitySpace']:local=ref['nodeId']
                            if local is None:
                                matches=[i for i,origins in graph.get('entityLineage',{}).items() if any(all(o.get(k)==ref.get(k) for k in ('packageId','identitySpace','nodeId')) for o in origins)]
                                require(len(matches)<=1,'QUESTION_REF_BINDING_AMBIGUOUS');local=matches[0] if matches else None
                            if local in entity:bindings[key]=entity[local]
                            if ref['mode']=='current' and (n['kind']=='question' or local in entity):ref['mode']='inherited'
                        if n['kind']!='canon' and ref.get('workGraphId') in mapping['workGraph']:ref['workGraphId']=mapping['workGraph'][ref['workGraphId']]
                n['referenceBindings']=bindings
            if n['kind']=='finding':
                n['subjectId']=entity.get(n['subjectId'],n['subjectId']);n['subjectSnapshot']['id']=n['subjectId']
                n['evidenceIds']=[entity.get(i,i) for i in n['evidenceIds']]
                for d in [n['disposition'],*n['dispositionHistory']]:
                    d['evidenceIds']=[entity.get(i,i) for i in d['evidenceIds']]
                    if 'replacementId' in d:d['replacementId']=entity.get(d['replacementId'],d['replacementId'])
            if 'findingOrigin' in n:
                for key in ('findingId','subjectId'):n['findingOrigin'][key]=entity.get(n['findingOrigin'][key],n['findingOrigin'][key])
            for field in ('questions','reviewLimitations'):
                for question in n.get(field,[]):question['id']=str(uuid.uuid5(uuid.NAMESPACE_URL,n['id']+':'+question['id']))
            if 'targetIds' in n:n['targetIds']=[entity[i] for i in n['targetIds']]
            if 'impactTargetIds' in n:n['impactTargetIds']=[entity[i] for i in n['impactTargetIds']]
            if 'decisionContextIds' in n:n['decisionContextIds']=[entity[i] for i in n['decisionContextIds']]
            if 'contextNotes' in n:n['contextNotes']={entity[i]:v for i,v in n['contextNotes'].items()}
            if 'contextGroupId' in n:n['contextGroupId']=mapping['contextGroup'][n['contextGroupId']]
            for p in n.get('analysisSources',[]):p['sourceId']=entity.get(p['sourceId'],p['sourceId'])
            if 'groupIds' in n:n['groupIds']=[mapping['decisionGroup'][i] for i in n['groupIds']]
            # Review causes/observations address historical versions, not current refs.
    for r in g.get('contextGroups',[]):r.update(id=mapping['contextGroup'][r['id']],parentId=mapping['contextGroup'].get(r['parentId']))
    g['rootRequirementId']=entity.get(g['rootRequirementId'])
    for c in g['rootCauses']:c.update(id=mapping['rootCause'][c['id']],requirementId=entity[c['requirementId']])
    for e in g['edges']:e.update(id=mapping['edge'][e['id']],**{'from':entity[e['from']],'to':entity[e['to']]})
    for e in g['edges']:
        if 'findingId' in e:e['findingId']=entity[e['findingId']]
    for group in g['decisionGroups']:
        group.update(id=mapping['decisionGroup'][group['id']],parentId=entity[group['parentId']])
        for m in group['members']:m.update(id=mapping['membership'][m['id']],decisionId=entity[m['decisionId']])
    for w in g['workGraphs']:
        w.update(id=mapping['workGraph'][w['id']],rootIds=[entity[i] for i in w['rootIds']],memberIds=[entity[i] for i in w['memberIds']])
    for ref in g.get('externalRefs',[]):ref.update(id=mapping['externalReference'][ref['id']],localId=entity[ref['localId']])
    for binding in g.get('dependencyBindings',[]):
        for rows in binding.get('observedSources',{}).values():
            for item in rows:item['id']=entity.get(item['id'],item['id'])
        for field in ('targetId','sourceId','parentId'):
            if binding[field] is not None:binding[field]=entity.get(binding[field],binding[field])
        if 'participantBindings' in binding:binding['participantBindings']={r:entity.get(i,i) for r,i in binding['participantBindings'].items()}
    # Automatic exceptions refer to source Graph identities; re-key their anchors in the copy.
    decision=__import__('sys').modules.get('rdg_dependency_policies_v2')
    automatic={}
    for state in g.get('dependencyAutomaticStates',{}).values():
        if state['sourceId'] not in entity or state['targetId'] not in entity:continue
        state=copy.deepcopy(state);state['sourceId']=entity[state['sourceId']];state['targetId']=entity[state['targetId']]
        key=decision.automatic_key({'origin':state['origin'],'sourceId':state['sourceId'],'dependentId':state['targetId']})
        state['id']=key;automatic[key]=state
    if 'dependencyAutomaticStates' in g:g['dependencyAutomaticStates']=automatic
    for field in ('factLineage','entityLineage'):g[field]={entity[i]:v for i,v in g.get(field,{}).items()}
    return g


def decision_copy(source_package,source,focus,mapping,space,ident,kernel,include_descendants=True):
    captured,inventory=decision_fragment(source,focus,kernel,include_descendants);g=decision_remap(captured,mapping);key=digest(source)
    g.update(identitySpace=space,id=ident,revision=1,events=[])
    for binding in g.get('dependencyBindings',[]):
        binding['id']=str(uuid.uuid5(uuid.UUID(space),'dependency-binding:'+binding['id']))
    g.setdefault('inheritedHistory',{})[key]={'source':{'packageId':source_package,'identitySpace':source['identitySpace'],
        'graphRevision':source['revision'],'sha256':key},'events':copy.deepcopy(source['events']),'eventsSHA256':digest(source['events'])}
    g['factLineage']={};g['entityLineage']={}
    for question in g['objects']:
        if question['kind']=='question':
            for refs in [question['relatedRefs'],question['sourceRefs'],*(a['sourceRefs'] for a in question['answers']),*(h['previous']['sourceRefs'] for h in question.get('answerHistory',[]))]:
                for ref in refs:
                    if ref.get('kind') in ('process','workGraph','lens'):ref['identitySpace']=space
    for old,new in mapping['entity'].items():
        node=kernel.entities(source)[old];g['entityLineage'][new]=[reference(source_package,source,old,'inherited'),*copy.deepcopy(source.get('entityLineage',{}).get(old,[]))]
        event_id=node.get('result',{}).get('eventId')
        if event_id:
            event,subject,events=kernel.fact_record(source,old,event_id,False);require(event is not None,'COPY_FACT_SOURCE_MISSING')
            history_key=key if events is source['events'] else source['factLineage'][old][event_id]['historyKey']
            g['factLineage'][new]={event_id:{'historyKey':history_key,'sourceId':subject}}
    for edge in inventory['boundaryEdges']:
        local=edge['from'] if edge['from'] in mapping['entity'] else edge['to'];other=edge['to'] if edge['from']==local else edge['from']
        g['externalRefs'].append({'id':digest([space,edge['id']]),'localId':mapping['entity'][local],
            'direction':'outgoing' if edge['from']==local else 'incoming','relation':copy.deepcopy(edge),
            'target':reference(source_package,source,other),'observed':copy.deepcopy(kernel.entities(source)[other]),'reason':'outside-captured-fragment'})
    kernel.validate(g);return g,inventory


def decision_insert(target,imported,event,scope_id,kernel):
    require(target['coreModel']==imported['coreModel'],'UNSUPPORTED_PROFILE_CAPABILITY')
    for ns,ids in definitions(target).items():
        if ns!='event':require(not set(ids)&set(definitions(imported)[ns]),'INSERT_ID_COLLISION')
    g=copy.deepcopy(target)
    for family in ('nodes','objects','externalActions','edges','workGraphs','rootCauses','decisionGroups'):g[family].extend(copy.deepcopy(imported[family]))
    if imported.get('contextGroups'):g.setdefault('contextGroups',[]).extend(copy.deepcopy(imported['contextGroups']))
    # Defined policies are portable and immutable per version. Preserve equal
    # definitions, isolate colliding foreign IDs, then rewrite imported bindings.
    policy_ids={};used={(p['id'],p['version']):p for p in g.get('dependencyPolicies',[])}
    for pid in sorted({p['id'] for p in imported.get('dependencyPolicies',[])}):
        group=[copy.deepcopy(p) for p in imported['dependencyPolicies'] if p['id']==pid]
        incompatible=any((pid,p['version']) in used and used[(pid,p['version'])]!=p for p in group)
        mapped=(str(uuid.uuid5(uuid.UUID(g['identitySpace']),'import-policy:'+scope_id+':'+pid)) if incompatible else pid)
        policy_ids[pid]=mapped
        for p in group:
            p['id']=mapped;key=(mapped,p['version'])
            if key not in used:g.setdefault('dependencyPolicies',[]).append(p);used[key]=p
    presets={p['id']:p for p in g.get('dependencyPresets',[])}
    for pre in imported.get('dependencyPresets',[]):
        p=copy.deepcopy(pre)
        if p['id'] in presets and presets[p['id']]!=p:
            p['id']=str(uuid.uuid5(uuid.UUID(g['identitySpace']),'import-preset:'+scope_id+':'+p['id']))
        if p['id'] not in presets:
            g.setdefault('dependencyPresets',[]).append(p);presets[p['id']]=p
    used_bindings={b['id'] for b in g.get('dependencyBindings',[])}
    for pre in imported.get('dependencyBindings',[]):
        b=copy.deepcopy(pre);b['policyId']=policy_ids.get(b['policyId'],b['policyId'])
        if b['id'] in used_bindings:
            b['id']=str(uuid.uuid5(uuid.UUID(g['identitySpace']),'import-binding:'+scope_id+':'+b['id']))
        require(b['id'] not in used_bindings,'POLICY_BINDING_COLLISION')
        g.setdefault('dependencyBindings',[]).append(b);used_bindings.add(b['id'])
    for field in ('inheritedHistory','factLineage','entityLineage'):g.setdefault(field,{}).update(copy.deepcopy(imported.get(field,{})))
    g.setdefault('externalRefs',[]).extend(copy.deepcopy(imported.get('externalRefs',[])))
    g['recommendationPackageIds']=list(dict.fromkeys(g['recommendationPackageIds']+imported['recommendationPackageIds']))
    members=[n['id'] for n in imported['nodes']+imported['objects']]
    g['workGraphs'].append({'id':scope_id,'title':imported['title'],'memberIds':members,'rootIds':[imported['rootRequirementId']] if imported['rootRequirementId'] else []})
    g['revision']+=1
    g['events'].append({'id':event['id'],'type':'created','transactionId':event['verifiedTrustReceipt']['transactionId'],
        'recordedAt':event['recordedAt'],'by':event['by'],'basis':event['note'],'nodeIds':members})
    kernel.validate(g);return g,scope_id


def decision_template(graph):
    require(not any(n['kind']=='question' and (n['answers'] or n.get('answerHistory') or n.get('assessment') or n['assessmentHistory'] or n['sourceRefs'] or any(r.get('kind') or r.get('mode')=='historical' for r in n['relatedRefs'])) for n in graph['objects']),'QUESTION_TEMPLATE_LIVE_DATA')
    require(not any(n['kind']=='finding' for n in graph['objects']),'FINDING_PROCESS_ONLY:choose-fragment-without-process-findings')
    g=copy.deepcopy(graph)
    g.pop('contextGroups',None)
    for n in g['objects']:n.pop('contextGroupId',None)
    removed={a['id'] for a in g['externalActions'] if a['lowLevel']}|{n['id'] for n in g['objects'] if n['kind']=='evidence' or n['kind']=='context' and 'artifact' in n}
    g['externalActions']=[a for a in g['externalActions'] if a['id'] not in removed];g['objects']=[n for n in g['objects'] if n['id'] not in removed]
    for family in ('nodes','externalActions'):
        for node in g[family]:
            node['result']={'state':'open','truth':'unknown'};node.pop('review',None);node['revision']=1
            if node['kind']=='decision':
                node['selectionState']='discovered'
                node.pop('decisionContextIds', None);node.pop('contextNotes',None);node.pop('analysisSources',None)
    for family in ('objects',):
        for node in g[family]:node.pop('review',None);node['revision']=1
    g['edges']=[e for e in g['edges'] if not {e['from'],e['to']}&removed and
                e.get('dependencyPurpose')!='decisionContext']
    # Concrete process context is not an inherited template fact. Definition
    # and preset schema survive; context subscriptions and applications do not.
    by_id={n['id']:n for n in g['nodes']+g['objects']+g['externalActions']}
    g.pop('dependencyAutomaticStates',None)
    definitions={(p['id'],p['version']):p for p in g.get('dependencyPolicies',[])}
    def template_binding(b):
        if b.get('status')=='deleted':return False
        refs=({b['targetId'],b['sourceId'],b['parentId']}|set(b.get('participantBindings',{}).values()))-{None}
        if refs & removed or not refs<=set(by_id):return False
        if any(by_id[i]['kind']=='context' for i in refs):return False
        policy=definitions.get((b['policyId'],b['policyVersion']),{})
        if policy.get('pattern')=='parentDecisionContext':return False
        if any(set(r.get('selector',{}).get('relation') if isinstance(r.get('selector',{}).get('relation'),list) else [r.get('selector',{}).get('relation')]) & {'DECISION_CONTEXT','CONTEXT_FOR'} for r in policy.get('roles',[])):return False
        if any(r.get('watch') in ('context','membership') for r in policy.get('rules',[])):return False
        return True
    g['dependencyBindings']=[b for b in g.get('dependencyBindings',[]) if template_binding(b)]
    for w in g['workGraphs']:w['memberIds']=[i for i in w['memberIds'] if i not in removed]
    g['events']=[]
    for key in ('externalRefs','inheritedHistory','factLineage'):g.pop(key,None)
    if not any(n['kind']=='question' and n['relatedRefs'] for n in g['objects']):g.pop('entityLineage',None)
    return g
