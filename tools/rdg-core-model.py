#!/usr/bin/env python3
"""Closed RDG core profile: actual state, shared identity and reviewable dependencies.

A physical owner contains entities once. workGraphs are work scopes; focused
views are projections, never owners. Legacy candidate-v6 remains a separate
reader/writer branch. This module performs no IO and never migrates a live owner.
"""
import copy
import hashlib
import json
import re
from collections import defaultdict, deque

PROFILE = 'rdg-core-v1'
NODE_KINDS = frozenset(('requirement', 'action'))
OBJECT_KINDS = frozenset(('context', 'canon', 'info', 'evidence'))
PAIRS = {'DRIVES': ({'requirement'}, {'action'}),
         'RELATES_R': ({'requirement'}, {'action'}),
         'DERIVES': ({'requirement'}, {'requirement'}),
         'INTRODUCES': ({'action'}, {'requirement'}),
         'CONTEXT_FOR': ({'context'}, {'action'}),
         'DEPENDS_ON': ({'requirement', 'action', 'context', 'info'}, {'requirement', 'action', 'context'}),
         'CANON_FOR': ({'canon'}, {'action'}),
         'INFO_FOR': ({'info'}, NODE_KINDS | OBJECT_KINDS),
         'EVIDENCE_FOR': ({'evidence'}, {'requirement', 'action', 'context'})}
# Positive semantics: a new relation must choose its own freshness policy.
DEPENDENCY_TYPES = frozenset(('DRIVES', 'RELATES_R', 'DERIVES', 'INTRODUCES',
                              'CONTEXT_FOR', 'DEPENDS_ON', 'CANON_FOR'))
NATIVE_DEPENDENCY_LEVELS = frozenset(('L1', 'L2'))
LOCK_OPERATIONS = frozenset(('edit', 'link', 'unlink', 'select', 'withdraw', 'complete',
                             'falsify', 'reopen', 'review', 'assess', 'remove',
                             'dependency_add', 'dependency_remove', 'lock_set', 'lock_remove'))
LOCK_MODES = frozenset(('warning', 'hard'))
COMMANDS = frozenset(('add', 'edit', 'link', 'unlink', 'dependency_add', 'dependency_remove',
                      'lock_set', 'lock_remove',
                      'select', 'withdraw', 'complete',
                      'falsify', 'reopen', 'review', 'assess', 'work_graph', 'include',
                      'join', 'exclusion_group', 'finding', 'resolve_finding', 'requirement_state',
                      'output_origin', 'lens_recommendations', 'remove'))
EDITABLE = frozenset(('title', 'description', 'scope', 'successCriteria', 'value',
                      'properties', 'arguments', 'claim', 'version', 'source', 'policy',
                      'evaluationMode', 'comment'))
ROLES = frozenset(('affected', 'constraining'))
MATCHES = frozenset(('match', 'partial', 'no-match', 'unknown'))
COMPLETION_TYPES = frozenset(('action_executed', 'requirement_achieved',
                              'requirement_falsified', 'action_reopened'))


def require(ok, code):
    if not ok:
        raise ValueError('CORE_' + code)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')).encode()).hexdigest()


def text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_lock_map(locks):
    require(isinstance(locks, dict), 'LOCKS_OBJECT')
    for operation, spec in locks.items():
        require(operation in LOCK_OPERATIONS and isinstance(spec, dict), 'LOCK_OPERATION')
        require(set(spec) <= {'mode', 'principals', 'message'} and
                spec.get('mode') in LOCK_MODES and isinstance(spec.get('principals'), list) and
                len(spec['principals']) == len(set(spec['principals'])) and
                all(text(p) for p in spec['principals']) and text(spec.get('message')),
                'LOCK_SPEC')
        if spec['mode'] == 'hard':
            require(bool(spec['principals']), 'HARD_LOCK_PRINCIPALS_REQUIRED')
    return locks


def entities(g):
    return {n['id']: n for n in [*g['nodes'], *g.get('objects', [])]}


def active_edges(g):
    return [e for e in g['edges'] if not e.get('archived')]



def external_pin_key(ref):
    return json.dumps(['external',ref['packageId'],ref['identitySpace'],ref['nodeId']], separators=(',',':'))


def fact_record(g, owner_id, event_id, relation=False):
    """Resolve a local fact or its explicitly inherited, unchanged source record."""
    for event in g.get('events', []):
        if event.get('id') != event_id:continue
        if relation and owner_id in event.get('unresolvedOriginIds', []) or not relation and (event.get('targetId') == owner_id or owner_id in event.get('targetIds', []) or owner_id in event.get('before', {}) or owner_id in event.get('after', {}) or owner_id in event.get('affectedIds', [])):
            return event, owner_id, g['events']
    table=g.get('relationLineage' if relation else 'factLineage', {})
    link=table.get(owner_id, {}).get(event_id)
    if link:
        history=g.get('inheritedHistory', {}).get(link['historyKey'], {})
        event=next((e for e in history.get('events', []) if e.get('id') == event_id), {})
        return event, link['sourceId'], history.get('events', [])
    return {}, owner_id, []


def validate_inherited_facts(g, ns, edge_ids):
    histories=g.get('inheritedHistory', {})
    require(isinstance(histories,dict),'INHERITED_HISTORY')
    for key, history in histories.items():
        require(isinstance(key,str) and bool(re.fullmatch('[0-9a-f]{64}',key)) and
                isinstance(history,dict) and set(history)=={'source','events','eventsSHA256'} and
                isinstance(history['events'],list) and digest(history['events'])==history['eventsSHA256'], 'INHERITED_HISTORY_BYTES')
        source=history['source']
        require(isinstance(source,dict) and set(source)=={'packageId','identitySpace','graphRevision','sha256'} and
                all(text(source[k]) for k in ('packageId','identitySpace')) and source['sha256']==key and
                type(source['graphRevision']) is int and source['graphRevision']>=1,'INHERITED_HISTORY_SOURCE')
        seen=set()
        for event in history['events']:
            require(isinstance(event,dict) and text(event.get('id')) and event['id'] not in seen and
                    text(event.get('type')) and event.get('by') in ('assistant','user') and text(event.get('note')),'INHERITED_EVENT')
            seen.add(event['id'])
    for field, owners in (('factLineage',set(ns)),('relationLineage',edge_ids)):
        table=g.get(field,{})
        require(isinstance(table,dict) and set(table)<=owners,'FACT_LINEAGE_OWNER')
        for owner, links in table.items():
            require(isinstance(links,dict),'FACT_LINEAGE_RECORD')
            for event_id, link in links.items():
                require(isinstance(link,dict) and set(link)=={'historyKey','sourceId'} and
                        link['historyKey'] in histories and text(link['sourceId']) and
                        any(e['id']==event_id for e in histories[link['historyKey']]['events']),'FACT_LINEAGE_SOURCE')


def retained_selection(g, action):
    """A recorded choice survives driver loss without inventing a new selection."""
    event, subject, events=fact_record(g,action['id'],action.get('selectedEventId'))
    if event.get('type')!='action_selected' or event.get('targetId')!=subject:return False
    position=next(i for i,e in enumerate(events) if e['id']==event['id'])
    groups=[(events[position+1:],subject)]
    if events is not g.get('events'):groups.append((g.get('events',[]),action['id']))
    for records, ident in groups:
        for record in records:
            relations=([record.get('previousRelation')] if record.get('type')=='core_relation_removed' else
                       record.get('removedEdges',[]) if record.get('type')=='core_entities_removed' else [])
            if any(isinstance(e,dict) and e.get('type')=='DRIVES' and e.get('to')==ident for e in relations):return True
    return False


def detached_components(g, work_graph_id=None):
    """Derived rooted scope, deliberately different from freshness and capture traversal.

    Realization flows from R through its alternatives/children/outputs. Situation,
    canons, info and evidence accompany reachable work but never make unrelated
    work reachable through a shared explanatory object. Membership is never edited.
    """
    validate(g)
    ns = entities(g); edges = active_edges(g); result = []
    realization = frozenset(('DRIVES', 'DERIVES', 'INTRODUCES'))
    companions = frozenset(('RELATES_R', 'CONTEXT_FOR', 'CANON_FOR', 'INFO_FOR', 'EVIDENCE_FOR'))
    for scope in g['workGraphs']:
        if work_graph_id is not None and scope['id'] != work_graph_id:
            continue
        members = set(scope['memberIds']); reached = set(scope['rootIds'])
        focus=g.get('fragmentFocus')
        if not reached and focus and focus['id'] in members:
            reached.add(focus['id'])
            if focus['kind']=='action':
                reached.update(e['from'] for e in edges if e['to']==focus['id'] and e['type']=='DRIVES' and e['from'] in members)
        pending = deque(reached)
        while pending:
            source = pending.popleft()
            for edge in edges:
                if edge['type'] in realization and edge['from'] == source and edge['to'] in members:
                    if edge['to'] not in reached:
                        reached.add(edge['to']); pending.append(edge['to'])
        # Companions are attached to actual reachable work; they are not roots.
        companions_seen = set(reached)
        while True:
            extra = {e['from'] for e in edges if e['type'] in companions and
                     e['to'] in companions_seen and e['from'] in members}
            if extra <= companions_seen:
                break
            companions_seen.update(extra)
        remaining = members - companions_seen
        # Group only leftovers. No second persisted membership or stale owner.
        adjacency = {i: set() for i in remaining}
        for edge in edges:
            if edge['from'] in remaining and edge['to'] in remaining:
                adjacency[edge['from']].add(edge['to']); adjacency[edge['to']].add(edge['from'])
        while remaining:
            first = min(remaining); component = {first}; queue = [first]
            while queue:
                for other in adjacency[queue.pop()] - component:
                    component.add(other); queue.append(other)
            remaining.difference_update(component)
            result.append({'workGraphId': scope['id'], 'memberIds': sorted(component),
                           'reviewIds': sorted(i for i in component if ns[i].get('review', {}).get('required')),
                           'rootIds': list(scope['rootIds']), 'derived': True})
    if work_graph_id is not None:
        require(any(w['id'] == work_graph_id for w in g['workGraphs']), 'WORK_GRAPH_UNKNOWN')
    return result


def validate_role(g, role, plan=None):
    """One paper policy for ready authoring/import; copy preserves working state."""
    validate(g)
    require(role in ('working', 'ready', 'copy', 'lens'), 'DOCUMENT_ROLE')
    if role in ('ready', 'lens'):
        require(g.get('rootRequirementId') is not None, 'PAPER_ROOT_REQUIRED')
        require(plan is None and not g['events'] and not g.get('inheritedHistory') and
                not g.get('factLineage') and not g.get('relationLineage'), 'PAPER_NO_PLAN_OR_WORK_HISTORY')
        require(not g.get('externalRefs') and not g.get('entityLineage'),'PAPER_SELF_CONTAINED')
        for node in entities(g).values():
            if node['kind'] == 'requirement':
                require(node['status'] == 'potential', 'PAPER_REQUIREMENT_POTENTIAL')
            if node['kind'] == 'action':
                require(node['status'] == 'candidate', 'PAPER_ACTION_CANDIDATE')
            if node['kind'] in NODE_KINDS:
                require(node['result'] == {'state': 'open', 'truth': 'unknown'}, 'PAPER_RESULT_OPEN')
            require(not node.get('assessment') and not node.get('selectedEventId') and
                    not node.get('review', {}).get('required') and not node.get('review', {}).get('pins') and
                    not node.get('qrpe'), 'PAPER_NO_WORK_FACTS')
    return g


def validate_output_origin(origin, ns):
    require(isinstance(origin, dict) and origin.get('role') in ('subgoal', 'method_correctness', 'unresolved'),
            'OUTPUT_ORIGIN_ROLE')
    if origin['role'] == 'unresolved':
        require(set(origin) == {'role', 'lossEventId'} and text(origin.get('lossEventId')),
                'UNRESOLVED_ORIGIN_LOSS_EVENT')
    elif origin['role'] == 'method_correctness':
        require(set(origin) == {'role'}, 'METHOD_CORRECTNESS_ORIGIN_FIELDS')
    else:
        ids = origin.get('requirementIds')
        require(set(origin) <= {'role','requirementIds','externalRequirementRefs'} and isinstance(ids,list) and (bool(ids) or bool(origin.get('externalRequirementRefs')))
                and all(isinstance(i, str) and ns.get(i, {}).get('kind') == 'requirement' for i in ids)
                and len(ids) == len(set(ids)) and isinstance(origin.get('externalRequirementRefs',[]),list), 'OUTPUT_ORIGIN_REQUIREMENTS')


def validate_lens_recommendations(g):
    """Optional textual guidance attached to the whole graph or a real R/A/Canon.

    Advisory only: references existing lens names, but performs no lookup, import,
    selection, scheduling or execution. Graph copy keeps the same local targets.
    """
    rows=g.get('lensRecommendations', [])
    require(isinstance(rows,list),'LENS_RECOMMENDATIONS_LIST')
    work_ids = {w['id'] for w in g.get('workGraphs', [])}
    kinds={n['id']:n['kind'] for n in [*g.get('nodes',[]),*g.get('objects',[])]
           if isinstance(n,dict) and isinstance(n.get('id'),str) and isinstance(n.get('kind'),str)}
    for row in rows:
        require(isinstance(row,dict) and set(row) in ({'lensKey','text'}, {'lensKey','text','targetId'},
                  {'lensKey','text','targetWorkGraphId'}) and
                isinstance(row.get('lensKey'),str) and re.fullmatch('[a-z][a-z0-9-]*',row['lensKey']) and
                text(row.get('text')) and len(row['text'])<=10000 and
                ('targetId' not in row or kinds.get(row['targetId']) in ('requirement','action','canon')) and
                ('targetWorkGraphId' not in row or row['targetWorkGraphId'] in work_ids),
                'LENS_RECOMMENDATION')
    require(len({(r['lensKey'],r.get('targetId'),r.get('targetWorkGraphId'),r['text']) for r in rows})==len(rows),
            'DUPLICATE_LENS_RECOMMENDATION')
    return rows


def output_origin(g, edge, driver_ids=None):
    """Origin through A is not a direct DERIVES relation or a new entity."""
    drivers = sorted(driver_ids if driver_ids is not None else {
        e['from'] for e in active_edges(g) if e['type'] == 'DRIVES' and e['to'] == edge['from']})
    origin = edge.get('origin')
    role = origin['role'] if origin else 'unspecified'
    declared = (origin['requirementIds'] if role == 'subgoal' else
                drivers if role == 'method_correctness' else [])
    external=origin.get('externalRequirementRefs',[]) if origin else []
    actual=[r['target'] for r in g.get('externalRefs',[]) if r['localId']==edge['from'] and r['direction']=='incoming' and r['relation']['type']=='DRIVES' and not r['relation'].get('archived')]
    missing_external=[r for r in external if not any(all(r[k]==a[k] for k in ('packageId','identitySpace','nodeId')) for a in actual)]
    return {'externalRequirementRefs':copy.deepcopy(external),'missingExternalDriverRefs':missing_external,
            'edgeId': edge['id'], 'actionId': edge['from'], 'role': role,
            'requirementIds': sorted(declared),
            'activeRequirementIds': sorted(set(declared) & set(drivers)),
            'missingDriverIds': sorted(set(declared) - set(drivers))}


def output_origin_issues(g, aid):
    return [e['id'] for e in active_edges(g) if e['type'] == 'INTRODUCES' and
            e['from'] == aid and (output_origin(g, e)['missingDriverIds'] or output_origin(g,e)['missingExternalDriverRefs'] or
                                    output_origin(g, e)['role'] == 'unresolved')]


def blank(ident, title, space, root, root_title, scope='Specified working scope'):
    return {'schemaVersion': 1, 'actionModel': 'candidate-v6', 'coreModel': PROFILE,
            'id': ident, 'title': title, 'identitySpace': space, 'revision': 1,
            'rootRequirementId': root, 'planningScale': 'module',
            'nodes': [{'id': root, 'kind': 'requirement', 'title': root_title,
                       'description': root_title, 'scope': scope, 'status': 'active',
                       'revision': 1, 'qrpe': [], 'result': {'state': 'open', 'truth': 'unknown'}}],
            'objects': [], 'edges': [], 'events': [], 'collections': [],
            'workGraphs': [{'id': 'WG-main', 'title': title, 'rootIds': [root], 'memberIds': [root]}],
            'workGraphLinks': [], 'exclusionGroups': []}


def argument_leaves(condition):
    if 'all' in condition or 'any' in condition:
        return [leaf for item in condition.get('all', condition.get('any', []))
                for leaf in argument_leaves(item)]
    return [condition]


def validate_condition(c, ids):
    require(isinstance(c, dict), 'CONDITION_OBJECT')
    if set(c) in ({'all'}, {'any'}):
        items = c.get('all', c.get('any'))
        require(isinstance(items, list) and bool(items), 'CONDITION_EMPTY_GROUP')
        for child in items:
            validate_condition(child, ids)
    else:
        require(set(c) <= {'id', 'kind', 'text', 'properties', 'scope'} and
                text(c.get('id')) and c['id'] not in ids and
                c.get('kind') in ('requirement', 'context') and text(c.get('text')),
                'CONDITION_LOCAL_R_OR_CONTEXT')
        ids.add(c['id'])
        require('properties' not in c or isinstance(c['properties'], dict), 'CONDITION_PROPERTIES')
        # A canon is illustrative. No owner-qualified refs, including hidden in properties.
        def local(v):
            if isinstance(v, dict):
                require(not set(v) & {'graphFile', 'identitySpace', 'nodeId', 'ref',
                                     'requirementId', 'dependsOnRequirements', 'checkRequirements'},
                        'CANON_EXTERNAL_REF_FORBIDDEN')
                for x in v.values(): local(x)
            elif isinstance(v, list):
                for x in v: local(x)
        local(c)


def validate_canon(n):
    mode = n.get('evaluationMode', 'legacy-arguments-v1')
    require(mode in ('legacy-arguments-v1', 'comment-only-v1'), 'CANON_EVALUATION_MODE')
    if mode == 'comment-only-v1':
        require(isinstance(n.get('comment'), str) and n.get('arguments') == [],
                'COMMENT_CANON_FREE_TEXT_WITHOUT_ARGUMENTS')
        return
    args = n.get('arguments')
    require(isinstance(args, list) and bool(args), 'CANON_ARGUMENTS_REQUIRED')
    ids, leaf_ids = set(), set()
    for a in args:
        require(isinstance(a, dict) and set(a) <= {'id', 'text', 'polarity', 'strength', 'condition'}
                and text(a.get('id')) and a['id'] not in ids and text(a.get('text')) and
                a.get('polarity') in ('for', 'against') and a.get('strength') in ('hard', 'soft') and
                (a['polarity'] == 'against' or a['strength'] == 'soft'), 'CANON_ARGUMENT')
        ids.add(a['id'])
        validate_condition(a.get('condition'), leaf_ids)


def validate(g):
    require(isinstance(g, dict) and g.get('schemaVersion') == 1 and g.get('coreModel') == PROFILE
            and g.get('actionModel') == 'candidate-v6', 'PROFILE')
    require(type(g.get('revision')) is int and g['revision'] >= 1 and
            all(text(g.get(k)) for k in ('id', 'identitySpace', 'title')), 'OWNER')
    require(not any(g.get(k) for k in ('modules', 'nodeKindExtensions', 'expansionOf')),
            'NO_IMPLICIT_MODULE_OR_LEGACY_EXPANSION')
    require(all(isinstance(g.get(k), list) for k in ('nodes', 'objects', 'edges', 'events',
                                                  'workGraphs', 'workGraphLinks', 'exclusionGroups')), 'ARRAYS')
    ns = {}
    for field, allowed in (('nodes', NODE_KINDS), ('objects', OBJECT_KINDS)):
        for n in g[field]:
            require(isinstance(n, dict) and text(n.get('id')) and n['id'] not in ns and
                    n.get('kind') in allowed and text(n.get('title')) and
                    type(n.get('revision')) is int and n['revision'] >= 1, 'ENTITY')
            require(not any(k in n for k in ('projectionOf', 'module', 'selectionBasis', 'canonBlock')),
                    'LEGACY_FIELDS_REQUIRE_EXPLICIT_CONVERSION')
            if n['kind'] == 'requirement':
                require(n.get('status') in ('active', 'potential', 'inactive') and text(n.get('scope'))
                        and text(n.get('description')), 'REQUIREMENT_MEANING_SCOPE')
            elif n['kind'] == 'action':
                require(n.get('status') in ('candidate', 'selected', 'rejected', 'superseded'), 'ACTION_STATUS')
            elif n['kind'] == 'canon':
                validate_canon(n)
            elif n['kind'] == 'evidence':
                require(all(text(n.get(k)) for k in ('claim', 'scope', 'version', 'source')),
                        'EVIDENCE_CLAIM_SCOPE_VERSION_SOURCE')
            if n['kind'] in NODE_KINDS:
                require(isinstance(n.get('result'), dict) and n['result'].get('state') in
                        ('open', 'confirmed'), 'RESULT')
                require(n['result'].get('truth') in ('true','false','unknown') and
                        (n['result']['state']=='confirmed')==(n['result']['truth']=='true') and
                        (n['kind']!='action' or n['result']['truth']!='false'),'RESULT_TRUTH')
            if 'review' in n:
                require(isinstance(n['review'], dict) and isinstance(n['review'].get('causes'), list)
                        and isinstance(n['review'].get('required'), bool), 'REVIEW')
            policy = n.get('policy', {'mode': 'ordinary'})
            require(isinstance(policy, dict) and policy.get('mode') in ('ordinary', 'stable', 'protected')
                    and (policy['mode'] != 'protected' or text(policy.get('authorityPrincipal'))), 'POLICY')
            if 'locks' in n: validate_lock_map(n['locks'])
            ns[n['id']] = n
    validate_lens_recommendations(g)
    document_version = g.get('coreDocumentVersion', 1)
    require(type(document_version) is int and document_version in (1, 2), 'DOCUMENT_VERSION')
    require((g.get('rootRequirementId') in ns and
             ns[g['rootRequirementId']]['kind'] == 'requirement') or
            (document_version == 2 and g.get('rootRequirementId') is None), 'ROOT')
    work_ids, members = set(), set()
    for w in g['workGraphs']:
        require(isinstance(w, dict) and set(w) == {'id', 'title', 'rootIds', 'memberIds'} and
                text(w['id']) and w['id'] not in work_ids and text(w['title']) and
                isinstance(w['memberIds'], list) and len(w['memberIds']) == len(set(w['memberIds'])) and
                set(w['memberIds']) <= set(ns) and isinstance(w['rootIds'], list) and
                set(w['rootIds']) <= set(w['memberIds']) and (bool(w['rootIds']) or document_version == 2) and
                all(ns[i]['kind'] == 'requirement' for i in w['rootIds']), 'WORK_GRAPH')
        work_ids.add(w['id']); members.update(w['memberIds'])
    require(members == set(ns), 'ENTITY_WORK_SCOPE_REQUIRED')
    seen_links = set()
    for link in g['workGraphLinks']:
        require(isinstance(link, list) and len(link) == 2 and len(set(link)) == 2 and
                set(link) <= work_ids and tuple(sorted(link)) not in seen_links, 'WORK_GRAPH_LINK')
        seen_links.add(tuple(sorted(link)))
    edge_ids, edge_keys = set(), set()
    for e in g['edges']:
        require(isinstance(e, dict) and text(e.get('id')) and e['id'] not in edge_ids and
                e.get('type') in PAIRS and e.get('from') in ns and e.get('to') in ns and
                e['from'] != e['to'], 'EDGE')
        edge_ids.add(e['id'])
        a, b = PAIRS[e['type']]
        require(ns[e['from']]['kind'] in a and ns[e['to']]['kind'] in b, 'EDGE_KINDS')
        require(e['type'] != 'RELATES_R' or e.get('role') in ROLES, 'SITUATION_ROLE')
        if e['type'] == 'DEPENDS_ON':
            if ns[e['from']]['kind'] == 'info':
                require('dependencyLevel' in e, 'INFO_DEPENDENCY_LEVEL_REQUIRED')
            if 'dependencyLevel' in e:
                require(e['dependencyLevel'] in NATIVE_DEPENDENCY_LEVELS, 'DEPENDENCY_LEVEL')
                require(e.get('from') != e.get('to'), 'DEPENDENCY_SELF_REFERENCE')
        if 'origin' in e:
            require(e['type'] == 'INTRODUCES', 'OUTPUT_ORIGIN_RELATION')
            validate_output_origin(e['origin'], ns)
        if not e.get('archived'):
            key = (e['type'], e['from'], e['to'], e.get('role'), e.get('dependencyLevel'))
            require(key not in edge_keys, 'DUPLICATE_RELATION'); edge_keys.add(key)
    events = {}
    for ev in g['events']:
        require(isinstance(ev, dict) and text(ev.get('id')) and ev['id'] not in events and
                text(ev.get('type')) and ev.get('by') in ('assistant', 'user') and text(ev.get('note')),
                'EVENT')
        events[ev['id']] = ev
    validate_inherited_facts(g,ns,edge_ids)
    for n in ns.values():
        if n['kind'] in NODE_KINDS and n['result']['state'] == 'confirmed':
            ev, subject, _ = fact_record(g,n['id'],n['result'].get('eventId'))
            require(ev.get('type') == ('requirement_achieved' if n['kind'] == 'requirement' else 'action_executed')
                    and ev.get('targetId') == subject and bool(ev.get('evidenceRefs')), 'CONFIRMATION_EVENT_REQUIRED')
        if n.get('assessment') is not None:
            assessment_event, subject, _=fact_record(g,n['id'],n['assessment'].get('eventId'))
            require(n['kind']=='action' and assessment_event.get('type')=='core_canon_assessed' and
                    assessment_event.get('targetId')==subject,'ASSESSMENT_EVENT_REQUIRED')
        if n['kind']=='requirement' and n['result'].get('truth')=='false':
            loss, subject, _=fact_record(g,n['id'],n['result'].get('eventId'))
            require(loss.get('type')=='requirement_falsified' and loss.get('targetId')==subject and
                    bool(loss.get('evidenceRefs')),'FALSIFICATION_EVENT_REQUIRED')
        if n['kind'] == 'action' and n['status'] == 'selected':
            ev, subject, _ = fact_record(g,n['id'],n.get('selectedEventId'))
            require(ev.get('type') == 'action_selected' and ev.get('targetId') == subject, 'SELECTION_EVENT_REQUIRED')
            require(any(e['type']=='DRIVES' and e['to']==n['id'] for e in active_edges(g)) or
                    retained_selection(g, n), 'SELECTED_ACTION_DRIVER_REQUIRED')
    for edge in active_edges(g):
        if edge.get('origin', {}).get('role') == 'unresolved':
            loss, subject, _ = fact_record(g,edge['id'],edge['origin']['lossEventId'],True)
            require(loss.get('type') == 'core_entities_removed' and
                    subject in loss.get('unresolvedOriginIds', []), 'UNRESOLVED_ORIGIN_PROVENANCE')
    if document_version == 2 and g.get('rootRequirementId') is None:
        focus = g.get('fragmentFocus')
        require((isinstance(focus, dict) and set(focus) == {'kind', 'id'} and
                 ns.get(focus.get('id'), {}).get('kind') == focus.get('kind')) or
                any(e.get('type') == 'core_entities_removed' and (e.get('removedRootIds') or e.get('removedFragmentFocus'))
                    for e in [*events.values(),*(e for h in g.get('inheritedHistory',{}).values() for e in h['events'])]), 'ROOTLESS_PROVENANCE_REQUIRED')
    for n in ns.values():
        qids=set()
        for q in n.get('qrpe',[]):
            require(isinstance(q,dict) and text(q.get('id')) and q['id'] not in qids and text(q.get('text')) and
                    q.get('type') in ('problem','risk','decision-uncertainty','opportunity') and q.get('status') in ('open','resolved'), 'FINDING_RECORD')
            qids.add(q['id'])
            require(fact_record(g,n['id'],q.get('eventId'))[0].get('type')=='core_finding_added','FINDING_EVENT_REQUIRED')
            if q['status']=='resolved':require(fact_record(g,n['id'],q.get('resolutionEventId'))[0].get('type')=='core_finding_resolved','FINDING_RESOLUTION_EVENT_REQUIRED')
    gids = set()
    for group in g['exclusionGroups']:
        require(isinstance(group, dict) and set(group) == {'id', 'actionIds', 'reason'} and
                text(group['id']) and group['id'] not in gids and text(group['reason']) and
                isinstance(group['actionIds'], list) and len(set(group['actionIds'])) == len(group['actionIds'])
                and len(group['actionIds']) >= 2 and all(ns.get(i, {}).get('kind') == 'action'
                                                       for i in group['actionIds']), 'EXCLUSION_GROUP')
        gids.add(group['id'])
        require(sum(ns[i]['status'] == 'selected' for i in group['actionIds']) <= 1, 'EXCLUDED_ACTIONS_SELECTED')
    return g


def dependencies(g):
    """source -> dependent; explanatory and historical links are not dependencies."""
    out = defaultdict(set)
    for e in active_edges(g):
        if e['type'] in DEPENDENCY_TYPES and not (
                e['type'] == 'DEPENDS_ON' and e.get('dependencyLevel') in NATIVE_DEPENDENCY_LEVELS):
            out[e['from']].add(e['to'])
    return dict(out)


def _definition_projection(g, nid):
    node = entities(g).get(nid)
    if node is None:
        return None
    return {key: copy.deepcopy(node[key]) for key in sorted(EDITABLE) if key in node}


def _membership_projection(g, nid):
    return sorted(w['id'] for w in g.get('workGraphs', []) if nid in w.get('memberIds', []))


def _relation_projection(g, edge, endpoint):
    target = edge['to'] if endpoint == 'to' else edge['from']
    return {'id': edge['id'], 'type': edge['type'], 'from': edge['from'], 'to': edge['to'],
            **({'role': edge['role']} if 'role' in edge else {}),
            **({'origin': copy.deepcopy(edge['origin'])} if 'origin' in edge else {}),
            'endpoint': target, 'endpointDefinition': _definition_projection(g, target),
            'endpointMembership': _membership_projection(g, target)}


def semantic_projection(g, nid, level='L1'):
    """One semantic impact contract for native L1/L2.

    Revision, result, review, event history and presentation are excluded.
    L2 includes only the direct scope required by the core contract; nested
    outgoing graphs are deliberately absent.
    """
    require(level in NATIVE_DEPENDENCY_LEVELS, 'DEPENDENCY_LEVEL')
    node = entities(g).get(nid)
    if node is None:
        return None
    result = {'level': level, 'nodeId': nid, 'kind': node['kind'],
              'definition': _definition_projection(g, nid),
              'membership': _membership_projection(g, nid)}
    if level == 'L1':
        return result
    relations = []
    for edge in active_edges(g):
        if node['kind'] == 'requirement':
            include = ((edge['from'] == nid and edge['type'] in ('DERIVES', 'DRIVES')) or
                       (edge['to'] == nid and edge['type'] in ('INTRODUCES', 'DERIVES')))
        elif node['kind'] == 'action':
            include = ((edge['from'] == nid and edge['type'] == 'INTRODUCES') or
                       (edge['to'] == nid and edge['type'] in ('DRIVES', 'CONTEXT_FOR', 'CANON_FOR')))
        else:
            include = False
        if include:
            relations.append(_relation_projection(g, edge, 'to' if edge['from'] == nid else 'from'))
    result['directScope'] = sorted(relations, key=lambda row: (row['type'], row['id']))
    return result


def native_dependency_edges(g):
    return [e for e in active_edges(g)
            if e['type'] == 'DEPENDS_ON' and e.get('dependencyLevel') in NATIVE_DEPENDENCY_LEVELS]


def _impact_projection(g, nid, level, cosmetic_ids):
    projection = semantic_projection(g, nid, level)
    if projection is not None:
        if nid in cosmetic_ids:
            projection.pop('definition', None)
        for relation in projection.get('directScope', []):
            if relation['endpoint'] in cosmetic_ids:
                relation.pop('endpointDefinition', None)
    return projection


def dependency_impacts(before, after, changed=None, *, cosmetic_ids=()):
    """Compare native scopes, with an explicit per-operation literal exception.

    Cosmetic edits omit only those definitions, including their direct L2
    occurrences. Membership and relation changes retain their normal impact.
    The public semantic projection always returns the actual unmasked content.
    """
    old_edges = {e['id']: e for e in native_dependency_edges(before)}
    new_edges = {e['id']: e for e in native_dependency_edges(after)}
    rows = []
    for edge_id in sorted(set(old_edges) | set(new_edges)):
        old_edge, new_edge = old_edges.get(edge_id), new_edges.get(edge_id)
        edge = new_edge or old_edge
        source, dependent = edge['from'], edge['to']
        level = edge.get('dependencyLevel')
        before_projection = _impact_projection(before, source, level, cosmetic_ids)
        after_projection = _impact_projection(after, source, level, cosmetic_ids)
        if before_projection == after_projection:
            continue
        before_parts = set()
        after_parts = set()
        if before_projection is not None and after_projection is not None:
            if before_projection.get('definition') != after_projection.get('definition'):
                before_parts.add('definition'); after_parts.add('definition')
            if before_projection.get('membership') != after_projection.get('membership'):
                before_parts.add('membership'); after_parts.add('membership')
            if before_projection.get('directScope') != after_projection.get('directScope'):
                before_parts.add('direct-relations')
                after_parts.add('direct-relations')
        else:
            before_parts.add('definition' if before_projection is not None else 'removed')
            after_parts.add('definition' if after_projection is not None else 'removed')
        rows.append({'edgeId': edge_id, 'sourceId': source, 'dependentId': dependent,
                     'level': level, 'changedParts': sorted(before_parts | after_parts),
                     'reason': 'native-semantic-impact'})
    return rows


def affected(before, after, changed, *, cosmetic_ids=()):
    old, new = dependencies(before), dependencies(after)
    queue, seen = deque(changed), set(changed)
    hits = set()
    while queue:
        source = queue.popleft()
        for target in old.get(source, set()) | new.get(source, set()):
            hits.add(target)
            if target not in seen:
                seen.add(target); queue.append(target)
    for row in dependency_impacts(before, after, changed, cosmetic_ids=cosmetic_ids):
        hits.add(row['dependentId'])
    return hits


def pins(g, nid):
    ns = entities(g)
    ids = {nid}
    ids.update(e['from'] for e in active_edges(g) if e['to'] == nid and e['type'] in DEPENDENCY_TYPES)
    result={i:ns[i]['revision'] for i in sorted(ids)}
    for ref in g.get('externalRefs',[]):
        if ref.get('direction')=='incoming' and ref.get('localId')==nid and not ref.get('relation',{}).get('archived') and ref.get('relation',{}).get('type') in DEPENDENCY_TYPES:
            result[external_pin_key(ref['target'])]=ref['target']['revision']
    return result


def evaluate_condition(c, matches):
    if 'all' in c or 'any' in c:
        values = [evaluate_condition(x, matches) for x in c.get('all', c.get('any'))]
        if 'all' in c:
            if 'no-match' in values: return 'no-match'
            if all(v == 'match' for v in values): return 'match'
        else:
            if 'match' in values: return 'match'
            if all(v == 'no-match' for v in values): return 'no-match'
        return 'unknown' if 'unknown' in values else 'partial'
    return matches.get(c['id'], {}).get('result', 'unknown')


def canon_verdict(g, nid):
    ns = entities(g); action = ns[nid]
    links = [e for e in active_edges(g) if e['type'] == 'CANON_FOR' and e['to'] == nid]
    assessment = action.get('assessment')
    if not links:
        return {'verdict': 'no-canons', 'arguments': [], 'assessmentCurrent': True}
    comments = {e['from']: ns[e['from']]['comment'] for e in links
                if ns[e['from']].get('evaluationMode') == 'comment-only-v1'}
    if len(comments) == len(links):
        return {'verdict': 'comment-only', 'arguments': [], 'assessmentCurrent': True,
                'comments': comments}
    current = bool(assessment and assessment.get('pins') == pins(g, nid))
    records = assessment.get('matches', {}) if current else {}
    rows = []
    for edge in links:
        canon = ns[edge['from']]
        for arg in canon['arguments']:
            row = {k: arg[k] for k in ('id', 'text', 'strength', 'polarity')}
            row.update(canonId=canon['id'], result=evaluate_condition(arg['condition'], records.get(canon['id'], {})))
            rows.append(row)
    hard = [r for r in rows if r['strength'] == 'hard' and r['polarity'] == 'against']
    verdict = ('incompatible' if any(r['result'] == 'match' for r in hard) else
               'undetermined' if not current or any(r['result'] in ('partial', 'unknown') for r in hard) else
               'assessed')
    return {'verdict': verdict, 'arguments': rows, 'assessmentCurrent': current,
            'comments': comments}


def completion_state(g, actual_roots=None):
    ns = entities(g); out = {}; required_children={};edges=active_edges(g)
    drivers=defaultdict(set)
    for e in edges:
        if e['type']=='DRIVES':drivers[e['to']].add(e['from'])
    origins={e['id']:output_origin(g,e,drivers[e['from']]) for e in edges if e['type']=='INTRODUCES'}
    origin_issues=defaultdict(list)
    for origin in origins.values():
        if origin['missingDriverIds'] or origin['missingExternalDriverRefs'] or origin['role'] == 'unresolved':
            origin_issues[origin['actionId']].append(origin['edgeId'])
    for nid,n in ns.items():
        if n['kind'] not in NODE_KINDS:continue
        required_children[nid]=[e['to'] for e in edges if e['from']==nid and
            ((e['type']=='DERIVES' and ns[e['to']].get('status')=='active') or
             (e['type']=='INTRODUCES' and n.get('status')=='selected' and ns[e['to']].get('status')=='active'))]
        if n['kind'] == 'requirement':
            required_children[nid] = sorted(set(required_children[nid]) | {
                e['to'] for e in edges if e['type'] == 'INTRODUCES' and
                ns[e['from']].get('status') == 'selected' and ns[e['to']].get('status') == 'active'
                and nid in origins[e['id']]['activeRequirementIds']})
    eligible={i for i in required_children if ns[i]['result']['state']=='confirmed' and
        not ns[i].get('review',{}).get('required') and
        ns[i]['status']==('selected' if ns[i]['kind']=='action' else 'active') and
        (ns[i]['kind'] != 'action' or not origin_issues[i])}
    # Eliminate invalidated confirmations. Children can block an existing claim,
    # but neither a leaf nor completed children create a new parent confirmation.
    while True:
        removed={i for i in eligible if any(child not in eligible for child in required_children[i])}
        if not removed:break
        eligible.difference_update(removed)
    for nid,children in required_children.items():
        n=ns[nid];result=n['result'];blockers=[i for i in children if i not in eligible]
        review=bool(n.get('review',{}).get('required') or result['state']=='confirmed' and blockers)
        out[nid]={'complete':nid in eligible,'previouslyConfirmed':result['state']=='confirmed',
            'reviewRequired':review,'truth':'unknown' if review else result.get('truth','unknown'),
            'currentScopeComplete':nid in eligible,'eventId':result.get('eventId'),'basis':copy.deepcopy(result),
            'historyPending':False,'blockers':blockers,'autoDerived':False,
            'originIssues':origin_issues[nid] if n['kind']=='action' else []}
    return out


def guard(n, ev, operation='edit'):
    p = n.get('policy', {'mode': 'ordinary'})
    if n.get('kind') == 'requirement':
        if p['mode'] == 'stable':
            require(text(ev.get('reasonForReconsideration')), 'STABLE_REASON_REQUIRED')
        if p['mode'] == 'protected':
            require(ev.get('by') == 'user' and ev.get('authorityPrincipal') == p['authorityPrincipal'],
                    'PROTECTED_OWNER_GRANT_REQUIRED')
    lock = n.get('locks', {}).get(operation)
    if lock:
        if lock['mode'] == 'warning':
            ev.setdefault('lockWarnings', []).append({
                'nodeId': n['id'], 'operation': operation, 'message': lock['message']})
        else:
            require(ev.get('authorityPrincipal') in lock['principals'],
                    'OBJECT_OPERATION_LOCK_REQUIRED')


def evidence(ev):
    refs = ev.get('evidenceRefs')
    require(isinstance(refs, list) and bool(refs), 'EVIDENCE_REQUIRED')
    for ref in refs:
        require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'} and text(ref['path']) and
                not ref['path'].startswith(('/', '.')) and '..' not in ref['path'].split('/') and
                re.fullmatch('[0-9a-f]{64}', ref['sha256'] or ''), 'EVIDENCE_REF')


def apply(original, patch, trusted_verified=False, *, coordinated=False):
    validate(original)
    require(trusted_verified, 'TRUST_RECEIPT_REQUIRED')
    require(isinstance(patch, dict) and patch.get('schemaVersion') == 1 and
            patch.get('expectedRevision') == original['revision'], 'REVISION_CONFLICT')
    require(isinstance(patch.get('operations'), list) and bool(patch['operations']), 'OPERATIONS')
    g = copy.deepcopy(original)
    for op in patch['operations']:
        require(isinstance(op, dict) and op.get('op') == 'graph_edit' and
                op.get('action', '').startswith('core_') and op['action'][5:] in COMMANDS, 'OPERATION_REQUIRED')
        before = copy.deepcopy(g); ns = entities(g)
        cmd, data, ev = op['action'][5:], op.get('data', {}), copy.deepcopy(op.get('event'))
        require(isinstance(data, dict) and isinstance(ev, dict) and text(ev.get('id')) and
                not any(e['id'] == ev['id'] for e in g['events']) and text(ev.get('note')) and
                ev.get('by') in ('assistant', 'user') and isinstance(ev.get('verifiedTrustReceipt'), dict), 'EVENT_RECEIPT')
        require(not {'before', 'after', 'affectedIds', 'cosmetic'} & set(ev), 'WRITER_EVENT_FIELDS')
        nid = data.get('nodeId'); n = ns.get(nid)
        changed, self_review, cosmetic_ids = set(), set(), set()
        def node(kind=None, operation='edit'):
            require(n is not None and (not kind or n['kind'] == kind), 'TARGET_KIND')
            guard(n, ev, operation); return n
        def guard_method(aid):
            for relation in active_edges(g):
                if relation['to']==aid and relation['type'] in ('DRIVES','RELATES_R'):
                    guard(ns[relation['from']],ev)
        def touch(i, review=False):
            ns[i]['revision'] += 1; changed.add(i)
            if review: self_review.add(i)
        def review_parents(child):
            pending=[child];seen={child}
            while pending:
                current=pending.pop()
                for relation in active_edges(g):
                    if relation['to']!=current or relation['type'] not in ('DERIVES','INTRODUCES'):continue
                    parent=relation['from']
                    self_review.add(parent)
                    if parent not in seen:seen.add(parent);pending.append(parent)
                    if relation['type'] == 'INTRODUCES':
                        for rid in output_origin(g, relation)['activeRequirementIds']:
                            self_review.add(rid)
                            if rid not in seen:seen.add(rid);pending.append(rid)
        def membership(i, wid):
            w = next((w for w in g['workGraphs'] if w['id'] == wid), None)
            require(w is not None, 'WORK_GRAPH_UNKNOWN')
            if i not in w['memberIds']: w['memberIds'].append(i)
        if cmd == 'add':
            require(set(data) <= {'entity', 'workGraphId'}, 'ADD_FIELDS')
            value = copy.deepcopy(data.get('entity'))
            require(isinstance(value, dict) and text(value.get('id')) and value['id'] not in ns and
                    value.get('kind') in NODE_KINDS | OBJECT_KINDS and
                    set(value) <= EDITABLE | {'id', 'kind', 'status', 'qrpe'}, 'NEW_ENTITY')
            if value['kind'] == 'requirement':
                require(value.get('status', 'active') in ('active', 'potential'), 'NEW_REQUIREMENT_STATUS')
                value.setdefault('status', 'active'); value.setdefault('description', value.get('title'))
                require(text(value.get('scope')), 'REQUIREMENT_SCOPE_REQUIRED')
            elif value['kind'] == 'action':
                require(value.get('status', 'candidate') == 'candidate', 'NEW_ACTION_CANDIDATE')
                value['status'] = 'candidate'
            require(not value.get('qrpe'),'NEW_FINDINGS_REQUIRE_DEDICATED_OPERATION')
            if value['kind'] in NODE_KINDS:
                value['result'] = {'state': 'open', 'truth': 'unknown'}; value.setdefault('qrpe', [])
            value['revision'] = 1
            g['nodes' if value['kind'] in NODE_KINDS else 'objects'].append(value)
            membership(value['id'], data.get('workGraphId', g['workGraphs'][0]['id']))
            ev['targetId'] = value['id']; ev['type'] = 'core_entity_added'
        elif cmd == 'edit':
            node(); changes = data.get('changes')
            if n['kind']=='action':guard_method(nid)
            if n['kind']=='canon':
                for relation in active_edges(g):
                    if relation['from']==nid and relation['type']=='CANON_FOR':guard_method(relation['to'])
            require(set(data) <= {'nodeId', 'changes', 'legacyCanonMigrationAcknowledged', 'cosmetic'} and
                    isinstance(changes, dict) and bool(changes) and set(changes) <= EDITABLE, 'EDIT_FIELDS')
            if 'cosmetic' in data:
                require(isinstance(data['cosmetic'], bool), 'COSMETIC_BOOLEAN_REQUIRED')
                ev['cosmetic'] = data['cosmetic']
                if data['cosmetic']:
                    cosmetic_ids.add(nid)
            if 'legacyCanonMigrationAcknowledged' in data:
                require(n['kind'] == 'canon' and data['legacyCanonMigrationAcknowledged'] is True,
                        'CANON_MIGRATION_ACKNOWLEDGEMENT')
            if n['kind'] == 'canon' and n.get('evaluationMode', 'legacy-arguments-v1') != changes.get('evaluationMode', n.get('evaluationMode', 'legacy-arguments-v1')):
                require(data.get('legacyCanonMigrationAcknowledged') is True,
                        'CANON_MIGRATION_ACKNOWLEDGEMENT_REQUIRED')
            require('policy' not in changes or changes['policy'] == n.get('policy', {'mode': 'ordinary'}),
                    'POLICY_REPLACEMENT_REQUIRES_SEPARATE_AUTHORITY')
            require(any(n.get(k) != v for k, v in changes.items()),'EDIT_NO_MEANINGFUL_CHANGE')
            if any(n.get(k) != v for k, v in changes.items()):
                n.update(copy.deepcopy(changes)); touch(nid, review=n['kind'] in NODE_KINDS)
            ev['type'] = 'core_entity_changed'; ev['targetId'] = nid
        elif cmd == 'lock_set':
            require(set(data) == {'nodeId', 'operation', 'mode', 'principals', 'message'},
                    'LOCK_SET_FIELDS')
            node_for_lock = node(operation='lock_set')
            require(ev.get('by') == 'user' and text(ev.get('authorityPrincipal')),
                    'LOCK_USER_PATH_REQUIRED')
            spec = {'mode': data['mode'], 'principals': copy.deepcopy(data['principals']),
                    'message': data['message']}
            validate_lock_map({data['operation']: spec})
            node_for_lock.setdefault('locks', {})[data['operation']] = spec
            touch(nid)
            ev.update(type='core_lock_set', targetId=nid, operation=data['operation'])
        elif cmd == 'lock_remove':
            require(set(data) == {'nodeId', 'operation', 'disposition'},
                    'LOCK_REMOVE_FIELDS')
            node_for_lock = node(operation='lock_remove')
            require(ev.get('by') == 'user' and text(ev.get('authorityPrincipal')),
                    'LOCK_USER_PATH_REQUIRED')
            require(data['operation'] in node_for_lock.get('locks', {}),
                    'LOCK_NOT_FOUND')
            del node_for_lock['locks'][data['operation']]
            if not node_for_lock['locks']: node_for_lock.pop('locks')
            touch(nid)
            ev.update(type='core_lock_removed', targetId=nid,
                      operation=data['operation'], disposition=data['disposition'])
        elif cmd == 'dependency_add':
            require(set(data) == {'edge'}, 'DEPENDENCY_ADD_FIELDS')
            edge = copy.deepcopy(data['edge'])
            require(isinstance(edge, dict) and set(edge) <=
                    {'id', 'type', 'from', 'to', 'dependencyLevel'} and
                    edge.get('type') == 'DEPENDS_ON' and
                    edge.get('dependencyLevel') in NATIVE_DEPENDENCY_LEVELS and
                    edge.get('from') in ns and edge.get('to') in ns and
                    edge['from'] != edge['to'] and
                    not any(e['id'] == edge.get('id') for e in g['edges']), 'DEPENDENCY_EDGE')
            require(not any(e['type'] == 'DEPENDS_ON' and not e.get('archived') and
                            e['from'] == edge['from'] and e['to'] == edge['to'] and
                            e.get('dependencyLevel') == edge['dependencyLevel']
                            for e in g['edges']), 'DEPENDENCY_EXISTS')
            guard(ns[edge['from']], ev, 'dependency_add'); guard(ns[edge['to']], ev, 'dependency_add')
            g['edges'].append(edge); touch(edge['to'], review=ns[edge['to']]['kind'] in NODE_KINDS)
            ev.update(type='core_dependency_added', edgeId=edge['id'],
                      dependencyLevel=edge['dependencyLevel'])
        elif cmd == 'dependency_remove':
            require(set(data) == {'edgeId', 'disposition'} and text(data.get('edgeId')),
                    'DEPENDENCY_REMOVE_FIELDS')
            edge = next((e for e in active_edges(g)
                         if e['id'] == data['edgeId'] and e['type'] == 'DEPENDS_ON'), None)
            require(edge is not None, 'DEPENDENCY_EDGE_REQUIRED')
            guard(ns[edge['from']], ev, 'dependency_remove'); guard(ns[edge['to']], ev, 'dependency_remove')
            edge['archived'] = True; edge['archivedEventId'] = ev['id']
            touch(edge['to'], review=ns[edge['to']]['kind'] in NODE_KINDS)
            ev.update(type='core_dependency_removed', edgeId=edge['id'],
                      dependencyLevel=edge.get('dependencyLevel'),
                      disposition=data['disposition'])
        elif cmd == 'link':
            require(set(data) == {'edge'}, 'LINK_FIELDS')
            edge = copy.deepcopy(data.get('edge'))
            require(isinstance(edge, dict) and set(edge) <=
                    {'id', 'type', 'from', 'to', 'role', 'origin', 'dependencyLevel'} and
                    edge.get('from') in ns and edge.get('to') in ns and
                    not any(e['id'] == edge.get('id') for e in g['edges']), 'NEW_EDGE')
            # A DEPENDS_ON edge without dependencyLevel is a legacy generic relation.
            # Native L1/L2 edges use dependency_add and always carry an explicit level.
            guard(ns[edge['from']], ev, 'link'); guard(ns[edge['to']], ev, 'link')
            for endpoint in (edge['from'],edge['to']):
                if ns[endpoint]['kind']=='action':guard_method(endpoint)
            g['edges'].append(edge)
            if edge['type'] in DEPENDENCY_TYPES: touch(edge['to'], review=ns[edge['to']]['kind'] in NODE_KINDS)
            if edge['type'] == 'DERIVES':touch(edge['from'],review=True)
            if edge['type'] == 'INTRODUCES':
                # Candidate drawings may remain unqualified. An already chosen method
                # cannot acquire a new mandatory output with ambiguous provenance.
                require(ns[edge['from']]['status'] != 'selected' or 'origin' in edge,
                        'SELECTED_OUTPUT_ORIGIN_REQUIRED')
                touch(edge['from'], review=True)
                if 'origin' in edge:
                    validate_output_origin(edge['origin'], ns)
                    for rid in output_origin(g, edge)['requirementIds']:
                        guard(ns[rid], ev);touch(rid, review=True)
                if ns[edge['from']]['status']=='selected' and ns[edge['to']]['status']=='potential':
                    ns[edge['to']]['status']='active'
            ev.update(type='core_relation_added', edgeId=edge['id'])
        elif cmd == 'output_origin':
            require(set(data) == {'edgeId', 'origin'}, 'OUTPUT_ORIGIN_FIELDS')
            edge = next((e for e in active_edges(g) if e['id'] == data['edgeId'] and
                         e['type'] == 'INTRODUCES'), None)
            require(edge is not None, 'INTRODUCES_RELATION_REQUIRED')
            validate_output_origin(data['origin'], ns)
            require(edge.get('origin') != data['origin'], 'OUTPUT_ORIGIN_NO_CHANGE')
            old = output_origin(g, edge)
            guard_method(edge['from']);guard(ns[edge['to']], ev)
            edge['origin'] = copy.deepcopy(data['origin'])
            new = output_origin(g, edge)
            for rid in set(old['requirementIds']) | set(new['requirementIds']):
                guard(ns[rid], ev);touch(rid, review=True)
            touch(edge['from'], review=True);touch(edge['to'], review=True)
            ev.update(type='core_output_origin_changed', edgeId=edge['id'],
                      previousOrigin=old, origin=new)
        elif cmd == 'unlink':
            require(set(data) <= {'edgeId', 'disposition'} and text(data.get('edgeId')), 'UNLINK_FIELDS')
            edge = next((e for e in active_edges(g) if e['id'] == data['edgeId']), None)
            require(edge is not None, 'ACTIVE_EDGE_REQUIRED')
            guard(ns[edge['from']], ev, 'unlink'); guard(ns[edge['to']], ev, 'unlink')
            for endpoint in (edge['from'],edge['to']):
                if ns[endpoint]['kind']=='action':guard_method(endpoint)
            if edge['type'] == 'INTRODUCES' and ns[edge['from']]['status'] == 'selected':
                require(text(data.get('disposition')), 'OUTPUT_DISPOSITION_REQUIRED')
            if edge['type'] == 'INTRODUCES' and 'origin' in edge:
                for rid in output_origin(g, edge)['requirementIds']:
                    guard(ns[rid], ev);touch(rid, review=True)
            edge['archived'] = True; edge['archivedEventId'] = ev['id']
            if edge['type'] in DEPENDENCY_TYPES: touch(edge['to'], review=ns[edge['to']]['kind'] in NODE_KINDS)
            if edge['type'] in ('INTRODUCES','DERIVES'):touch(edge['from'],review=True)
            ev.update(type='core_relation_removed', edgeId=edge['id'], disposition=data.get('disposition'))
        elif cmd == 'remove':
            require(coordinated, 'REMOVAL_REQUIRES_COORDINATOR')
            require(set(data) == {'nodeIds'} and isinstance(data['nodeIds'], list) and
                    bool(data['nodeIds']) and len(set(data['nodeIds'])) == len(data['nodeIds']) and
                    set(data['nodeIds']) <= set(ns), 'REMOVE_FIELDS')
            removed = set(data['nodeIds'])
            for i in removed:
                guard(ns[i], ev, 'remove')
                if ns[i]['kind'] == 'action':guard_method(i)
            removed_edges = [copy.deepcopy(e) for e in g['edges'] if {e['from'], e['to']} & removed]
            ev.update(type='core_entities_removed', removedIds=sorted(removed),
                      removedEdges=removed_edges, removedEntities={i: copy.deepcopy(ns[i]) for i in sorted(removed)},
                      removedRootIds=sorted({r for w in g['workGraphs'] for r in w['rootIds']} & removed),
                      unresolvedOriginIds=[])
            g['nodes'] = [n for n in g['nodes'] if n['id'] not in removed]
            g['objects'] = [n for n in g['objects'] if n['id'] not in removed]
            g['edges'] = [e for e in g['edges'] if not {e['from'], e['to']} & removed]
            g['lensRecommendations'] = [r for r in g.get('lensRecommendations', []) if r.get('targetId') not in removed]
            for scope in g['workGraphs']:
                scope['rootIds'] = [i for i in scope['rootIds'] if i not in removed]
                scope['memberIds'] = [i for i in scope['memberIds'] if i not in removed]
            if g.get('rootRequirementId') in removed:
                g['rootRequirementId'] = None
            g['coreDocumentVersion'] = 2
            for edge in g['edges']:
                origin = edge.get('origin', {})
                if origin.get('role') == 'subgoal' and set(origin['requirementIds']) & removed:
                    ids = [i for i in origin['requirementIds'] if i not in removed]
                    edge['origin'] = ({'role': 'subgoal', 'requirementIds': ids} if ids else
                                      {'role': 'unresolved', 'lossEventId': ev['id']})
                    if not ids:ev['unresolvedOriginIds'].append(edge['id'])
                    self_review.update((edge['from'], edge['to']))
            groups = []
            for group in g['exclusionGroups']:
                group['actionIds'] = [i for i in group['actionIds'] if i not in removed]
                if len(group['actionIds']) >= 2:groups.append(group)
            g['exclusionGroups'] = groups
            for field in ('factLineage', 'entityLineage'):
                if field in g:g[field] = {i: v for i, v in g[field].items() if i not in removed}
            if 'relationLineage' in g:g['relationLineage']={i:v for i,v in g['relationLineage'].items() if any(e['id']==i for e in g['edges'])}
            if 'externalRefs' in g:
                g['externalRefs'] = [r for r in g['externalRefs'] if r.get('localId') not in removed]
            if g.get('fragmentFocus', {}).get('id') in removed:
                ev['removedFragmentFocus']=copy.deepcopy(g['fragmentFocus'])
                g.pop('fragmentFocus')
            changed.update(removed)
            for i in affected(before, g, removed):
                if i in ns:guard(ns[i], ev, 'remove')
        elif cmd == 'assess':
            node('action', 'assess'); require(set(data) == {'nodeId', 'matches'}, 'ASSESS_FIELDS')
            matches = data['matches']; require(isinstance(matches, dict), 'MATCHES')
            canons = {e['from']: ns[e['from']] for e in active_edges(g) if e['type'] == 'CANON_FOR' and e['to'] == nid}
            require(set(matches) == set(canons), 'ASSESS_ALL_APPLICABLE_CANONS')
            situation = {e['from'] for e in active_edges(g) if e['to'] == nid and
                         e['type'] in ('DRIVES', 'RELATES_R', 'CONTEXT_FOR')}
            situation.update(external_pin_key(r['target']) for r in g.get('externalRefs',[]) if r['localId']==nid and r['direction']=='incoming' and not r['relation'].get('archived') and r['relation']['type'] in ('DRIVES','RELATES_R','CONTEXT_FOR'))
            for cid, canon in canons.items():
                leaves = {c['id'] for a in canon['arguments'] for c in argument_leaves(a['condition'])}
                require(isinstance(matches[cid], dict) and set(matches[cid]) == leaves, 'ASSESS_ALL_CONDITIONS')
                for item in matches[cid].values():
                    require(isinstance(item, dict) and set(item) == {'result', 'reason', 'sourceIds'} and
                            item['result'] in MATCHES and text(item['reason']) and isinstance(item['sourceIds'], list)
                            and set(item['sourceIds']) <= situation and
                            (item['result'] == 'unknown' or bool(item['sourceIds'])), 'MATCH_BASIS')
            n['assessment'] = {'pins': pins(g, nid), 'matches': copy.deepcopy(matches), 'eventId': ev['id']}
            verdict=canon_verdict(g,nid)
            if n['status']=='selected' and verdict['verdict'] in ('incompatible','undetermined'):
                touch(nid,review=True);n['assessment']['pins']=pins(g,nid)
            ev.update(type='core_canon_assessed', targetId=nid, verdict=verdict)
        elif cmd == 'review':
            require(set(data) == {'nodeIds', 'observed'} and isinstance(data['nodeIds'], list) and
                    bool(data['nodeIds']) and len(set(data['nodeIds'])) == len(data['nodeIds']), 'REVIEW_FIELDS')
            ids = set(data['nodeIds']); require(ids <= set(ns), 'REVIEW_TARGETS')
            observed = {i:revision for j in ids for i,revision in pins(g,j).items()}
            require(data['observed'] == observed, 'REVIEW_VERSION_CHANGED')
            trial=copy.deepcopy(g)
            for j in ids:entities(trial)[j]['review']={'required':False,'causes':[]}
            reviewed_states=completion_state(trial)
            for j in ids:
                guard(ns[j], ev, 'review')
                # A parent Action may be stale *because this child failed*. Do not
                # deadlock child recovery by requiring its blocked, confirmed parent
                # to be reviewed first. Independent upstream staleness still blocks.
                require(not any(ns[src].get('review', {}).get('required') and src not in ids and
                                not (ns[j]['kind']=='requirement' and ns[j]['result']['truth']=='false' and
                                     ns[src]['review'].get('causes') and
                                     all(c.get('eventId')==ns[j]['result'].get('eventId')
                                         for c in ns[src]['review']['causes']))
                                for src in pins(g, j) if src != j and src in ns), 'REVIEW_UPSTREAM_FIRST_OR_TOGETHER')
                if ns[j]['kind'] == 'action' and ns[j]['status'] == 'selected':
                    require(not output_origin_issues(g,j), 'OUTPUT_ORIGIN_DRIVER_REQUIRED')
                    require(canon_verdict(g, j)['verdict'] not in ('incompatible', 'undetermined'),
                            'REVIEW_SELECTED_CANON_UNRESOLVED')
                if ns[j].get('result', {}).get('state') == 'confirmed':
                    require(not reviewed_states[j]['blockers'],'REVIEW_OPEN_OBLIGATIONS')
                    evidence(ev)
                ns[j]['review'] = {'required': False, 'causes': [], 'eventId': ev['id'], 'pins': pins(g, j)}
            ev.update(type='core_review_confirmed', targetIds=sorted(ids), observed=observed)
        elif cmd == 'select':
            node('action', 'select'); require(set(data) <= {'nodeId', 'unresolvedAcknowledged'}, 'SELECT_FIELDS')
            require(n['status'] == 'candidate', 'ACTION_NOT_SELECTABLE')
            drivers = [e['from'] for e in active_edges(g) if e['type'] == 'DRIVES' and e['to'] == nid]
            require(bool(drivers), 'REALIZED_REQUIREMENT_REQUIRED')
            require(not output_origin_issues(g,nid), 'OUTPUT_ORIGIN_DRIVER_REQUIRED')
            # Old selected owners with unspecified output provenance stay readable;
            # new selections must define which parent R is actually blocked.
            require(all('origin' in e for e in active_edges(g)
                        if e['type']=='INTRODUCES' and e['from']==nid),
                    'SELECT_OUTPUT_ORIGIN_REQUIRED')
            for i in drivers: guard(ns[i], ev)
            verdict = canon_verdict(g, nid)
            require(verdict['verdict'] != 'incompatible', 'HARD_INCOMPATIBLE')
            require(verdict['verdict'] != 'undetermined' or data.get('unresolvedAcknowledged') is True,
                    'CANON_UNRESOLVED_ACKNOWLEDGEMENT_REQUIRED')
            require(not any(ns[i]['status'] == 'selected' for group in g['exclusionGroups'] if nid in group['actionIds']
                            for i in group['actionIds'] if i != nid), 'EXCLUSION_CONFLICT')
            for e in active_edges(g):
                if e['from']==nid and e['type']=='INTRODUCES':
                    guard(ns[e['to']],ev)
                    if ns[e['to']]['status']=='potential':
                        ns[e['to']]['status']='active';touch(e['to'],review=True)
            n['status'] = 'selected'; n['selectedEventId'] = ev['id']
            touch(nid); n['review'] = {'required': False, 'causes': [], 'eventId': ev['id']}
            # The assessment describes the same situation; selection is an administrative revision.
            if n.get('assessment'): n['assessment']['pins'] = pins(g, nid)
            ev.update(type='action_selected', targetId=nid, driverRequirementIds=drivers,
                      outputIds=[e['to'] for e in active_edges(g) if e['from'] == nid and e['type'] == 'INTRODUCES'],
                      verdict=verdict)
        elif cmd == 'withdraw':
            node('action', 'withdraw'); require(set(data) == {'nodeId', 'dispositions'} and
                    isinstance(data['dispositions'], dict), 'WITHDRAW_FIELDS')
            outputs = {e['to'] for e in active_edges(g) if e['from'] == nid and e['type'] == 'INTRODUCES'}
            require(set(data['dispositions']) == outputs and all(text(v) for v in data['dispositions'].values()),
                    'EVERY_OUTPUT_DISPOSITION_REQUIRED')
            for e in active_edges(g):
                if e['to'] == nid and e['type'] == 'DRIVES': guard(ns[e['from']], ev)
            n['status'] = 'superseded'; touch(nid)
            ev.update(type='action_withdrawn', targetId=nid, dispositions=copy.deepcopy(data['dispositions']))
        elif cmd == 'complete':
            node(operation='complete'); require(set(data) == {'nodeId'} and n['kind'] in NODE_KINDS, 'COMPLETE_FIELDS')
            require(not n.get('review', {}).get('required'), 'REVIEW_REQUIRED_BEFORE_CONFIRMATION')
            if n['kind'] == 'action':
                require(n['status'] == 'selected', 'SELECTED_ACTION_REQUIRED')
                require(any(e['type'] == 'DRIVES' and e['to'] == nid for e in active_edges(g)),
                        'REALIZED_REQUIREMENT_REQUIRED')
                require(not output_origin_issues(g,nid), 'OUTPUT_ORIGIN_DRIVER_REQUIRED')
                require(canon_verdict(g, nid)['verdict'] not in ('incompatible', 'undetermined'), 'CANON_NOT_ESTABLISHED')
            else: require(n['status'] == 'active', 'ACTIVE_REQUIREMENT_REQUIRED')
            state = completion_state(g)[nid]
            require(not state['blockers'], 'OPEN_OBLIGATIONS:' + ','.join(state['blockers']))
            evidence(ev)
            # A retry of an already-attested result with identical evidence must not
            # invent a new execution or achievement. New real evidence may attest again.
            require(n['result']['state']!='confirmed' or
                    n['result'].get('evidenceRefs')!=ev['evidenceRefs'],
                    'RECONFIRMATION_WITH_SAME_EVIDENCE')
            # Confirmation is an observation of the declared result, not a new method definition.
            n['result'] = {'state': 'confirmed', 'truth': 'true', 'eventId': ev['id'], 'claim': n.get('description', n['title']),
                           'scope': n.get('scope', g['identitySpace']), 'entityRevision': n['revision'],
                           'evidenceRefs': copy.deepcopy(ev['evidenceRefs'])}
            if n.get('assessment'): n['assessment']['pins'] = pins(g, nid)
            ev.update(type='requirement_achieved' if n['kind'] == 'requirement' else 'action_executed', targetId=nid)
        elif cmd == 'falsify':
            node('requirement', 'falsify'); require(set(data) == {'nodeId'}, 'FALSIFY_FIELDS'); evidence(ev)
            n['result'] = {'state': 'open', 'truth': 'false', 'eventId': ev['id'],
                           'evidenceRefs': copy.deepcopy(ev['evidenceRefs'])}
            touch(nid); n['review'] = {'required': False, 'causes': [], 'eventId': ev['id']}
            review_parents(nid)
            # Reuse the existing selected method. Loss of a result is not a new identity.
            for e in active_edges(g):
                if e['type'] == 'INTRODUCES' and e['to'] == nid:
                    a = ns[e['from']]
                    if a['result']['state'] == 'confirmed':
                        a['result'] = {'state': 'open', 'truth': 'unknown', 'eventId': ev['id']}; touch(a['id'], review=True)
            ev.update(type='requirement_falsified', targetId=nid)
        elif cmd == 'reopen':
            node('action', 'reopen'); guard_method(nid); require(set(data) == {'nodeId'}, 'REOPEN_FIELDS')
            require(n['status'] in ('selected','superseded','rejected'), 'EXISTING_ACTION_REQUIRED')
            if n['status']!='selected':n['status']='candidate'
            n['result'] = {'state': 'open', 'truth': 'unknown', 'eventId': ev['id']}; touch(nid, review=True)
            ev.update(type='action_reopened', targetId=nid)
        elif cmd == 'requirement_state':
            node('requirement', 'requirement_state'); require(set(data)<= {'nodeId','state','disposition','acceptSharedConsequences','decisionActionId'} and
                data.get('state') in ('active','inactive') and text(data.get('disposition')), 'REQUIREMENT_STATE_FIELDS')
            require(n['status'] != data['state'], 'REQUIREMENT_STATE_UNCHANGED')
            incoming=[e for e in active_edges(g) if e['to']==nid and e['type'] in ('INTRODUCES','DERIVES')]
            if data['state']=='inactive':
                require(n['status']=='active','ACTIVE_REQUIREMENT_REQUIRED')
                require(not incoming or data.get('acceptSharedConsequences') is True,'SHARED_REQUIREMENT_CONSEQUENCES_REQUIRED')
                aid=data.get('decisionActionId')
                method=ns.get(aid)
                require(method is not None and method['kind']=='action' and
                        any(e['type']=='DRIVES' and e['from']==nid and e['to']==aid for e in active_edges(g)),
                        'NECESSITY_DECISION_ACTION_REQUIRED')
                guard_method(aid)
                require(method['status']=='selected' and completion_state(g)[aid]['complete'],
                        'NECESSITY_DECISION_ACTION_NOT_CONFIRMED')
            else:
                require('decisionActionId' not in data, 'DECISION_ACTION_ONLY_FOR_INACTIVE')
            n['status']=data['state'];touch(nid,review=True);review_parents(nid)
            ev.update(type='core_requirement_necessity_changed',targetId=nid,disposition=data['disposition'],
                      decisionActionId=data.get('decisionActionId'))
        elif cmd == 'lens_recommendations':
            require(set(data)=={'recommendations'},'LENS_RECOMMENDATIONS_FIELDS')
            desired=copy.deepcopy(data['recommendations'])
            validate_lens_recommendations({**g,'lensRecommendations':desired})
            require(desired!=g.get('lensRecommendations',[]),'LENS_RECOMMENDATIONS_UNCHANGED')
            # Replacing the full list also removes old advice; both directions
            # require the ordinary guard for protected R targets.
            for rec in [*g.get('lensRecommendations',[]),*desired]:
                if 'targetId' in rec and ns[rec['targetId']]['kind']=='requirement':guard(ns[rec['targetId']],ev)
                if 'targetWorkGraphId' in rec:
                    scope = next(w for w in g['workGraphs'] if w['id'] == rec['targetWorkGraphId'])
                    for i in scope['memberIds']:
                        if ns[i]['kind'] == 'requirement':guard(ns[i], ev)
            previous=copy.deepcopy(g.get('lensRecommendations',[]))
            g['lensRecommendations']=desired
            ev.update(type='core_lens_recommendations_changed',previousRecommendations=previous,
                      recommendations=copy.deepcopy(desired))
        elif cmd == 'work_graph':
            require(set(data) == {'id', 'title', 'rootIds', 'memberIds'}, 'WORK_GRAPH_FIELDS')
            require(not any(w['id'] == data['id'] for w in g['workGraphs']), 'WORK_GRAPH_EXISTS')
            g['workGraphs'].append(copy.deepcopy(data)); ev.update(type='core_work_graph_added', workGraphId=data['id'])
        elif cmd == 'include':
            node(); require(set(data) == {'nodeId', 'workGraphId'}, 'INCLUDE_FIELDS')
            membership(nid, data['workGraphId']); ev.update(type='core_scope_member_added', targetId=nid)
        elif cmd == 'join':
            require(set(data) == {'workGraphIds'} and isinstance(data['workGraphIds'], list) and
                    len(data['workGraphIds']) == 2 and len(set(data['workGraphIds'])) == 2 and
                    set(data['workGraphIds']) <= {w['id'] for w in g['workGraphs']}, 'JOIN_FIELDS')
            link = sorted(data['workGraphIds'])
            require(link not in g['workGraphLinks'], 'WORK_GRAPHS_ALREADY_CONNECTED')
            g['workGraphLinks'].append(link); ev.update(type='core_work_graphs_connected', workGraphIds=link)
        elif cmd == 'exclusion_group':
            require(set(data) == {'id', 'actionIds', 'reason'}, 'EXCLUSION_FIELDS')
            g['exclusionGroups'].append(copy.deepcopy(data)); ev['type'] = 'core_exclusion_declared'
        elif cmd == 'finding':
            node(); require(set(data) == {'nodeId', 'finding'} and n['kind'] in NODE_KINDS, 'FINDING_FIELDS')
            q = copy.deepcopy(data['finding'])
            require(isinstance(q, dict) and set(q) == {'id', 'type', 'text'} and text(q['id']) and text(q['text']) and
                    q['type'] in ('problem', 'risk', 'decision-uncertainty', 'opportunity') and
                    not any(x['id'] == q['id'] for x in n.get('qrpe', [])), 'FINDING')
            n.setdefault('qrpe', []).append({**q, 'status': 'open', 'eventId': ev['id']})
            ev.update(type='core_finding_added', targetId=nid, findingId=q['id'])
        elif cmd == 'resolve_finding':
            node(); require(set(data) == {'nodeId', 'findingId'}, 'FINDING_RESOLVE_FIELDS'); evidence(ev)
            q = next((q for q in n.get('qrpe', []) if q['id'] == data['findingId']), None)
            require(q is not None and q['status'] == 'open', 'OPEN_FINDING_REQUIRED')
            q.update(status='resolved', resolutionEventId=ev['id']); ev.update(type='core_finding_resolved', targetId=nid)
        ns = entities(g)
        native_impacts = dependency_impacts(before, g, changed, cosmetic_ids=cosmetic_ids)
        hits = affected(before, g, changed, cosmetic_ids=cosmetic_ids) | self_review
        for target in sorted(hits):
            if target in ns:
                review = ns[target].setdefault('review', {'required': True, 'causes': []})
                review['required'] = True
                for src in sorted(changed):
                    source = ns.get(src, entities(before).get(src))
                    cause = {'sourceId': src, 'sourceRevision': source['revision'], 'eventId': ev['id']}
                    native_causes = [row for row in native_impacts
                                     if row['dependentId'] == target]
                    if native_causes:
                        cause['nativeImpact'] = copy.deepcopy(native_causes)
                    if src not in ns:
                        cause['sourceRef'] = {'mode': 'historical', 'identitySpace': before['identitySpace'],
                                              'nodeId': src, 'graphRevision': before['revision'],
                                              'graphSHA256': digest(before)}
                    if cause not in review['causes']: review['causes'].append(cause)
        ev['affectedIds'] = sorted(hits)
        subjects=changed | set(ev.get('targetIds',[])) | ({ev['targetId']} if ev.get('targetId') in ns else set())
        ev['before'] = {i: copy.deepcopy(entities(before)[i]) for i in subjects if i in entities(before)}
        ev['after'] = {i: copy.deepcopy(ns[i]) for i in subjects if i in ns}
        if ev.get('edgeId'):
            ev['previousRelation']=copy.deepcopy(next((e for e in before['edges'] if e['id']==ev['edgeId']),None))
            ev['newRelation']=copy.deepcopy(next(e for e in g['edges'] if e['id']==ev['edgeId']))
        g['events'].append(ev)
        validate(g)
    g['revision'] = original['revision'] + 1
    validate(g)
    return g, True


def focused_view(g, nid):
    validate(g); ns = entities(g); require(nid in ns, 'FOCUS_UNKNOWN')
    focus = ns[nid]; edges = active_edges(g); chosen = {nid}; boundary = set(); origins = []; origin_details = []
    kind = focus['kind']
    if kind == 'requirement':
        for e in edges:
            if e['from'] == nid and e['type'] in ('DRIVES', 'DERIVES'):
                chosen.add(e['to']); boundary.add(e['to'])
            if e['to'] == nid and e['type'] in ('INTRODUCES', 'DERIVES'):
                chosen.add(e['from']); origins.append(e)
                if e['type'] == 'INTRODUCES':
                    detail = output_origin(g,e);origin_details.append(detail)
                    for driver in edges:
                        if driver['to'] == e['from'] and driver['type'] == 'DRIVES':
                            if detail['role'] == 'unspecified' or driver['from'] in detail['activeRequirementIds']:
                                chosen.add(driver['from']); origins.append(driver)
    elif kind == 'action':
        for e in edges:
            if e['to'] == nid and e['type'] in ('DRIVES', 'RELATES_R', 'CONTEXT_FOR', 'CANON_FOR'):
                chosen.add(e['from'])
            if e['from'] == nid and e['type'] == 'INTRODUCES': chosen.add(e['to']); boundary.add(e['to'])
    elif kind == 'canon':
        # Illustrative conditions remain local; the actual A is a view overlay.
        for e in edges:
            if e['from'] == nid and e['type'] == 'CANON_FOR': chosen.add(e['to']); boundary.add(e['to'])
    for e in edges:
        if e['to'] in chosen and e['type'] in ('INFO_FOR', 'EVIDENCE_FOR'): chosen.add(e['from'])
    visible = [copy.deepcopy(e) for e in edges if e['from'] in chosen and e['to'] in chosen and
               not (kind == 'requirement' and e['from'] in boundary and e['type'] == 'INTRODUCES')]
    # No expansion beyond terminal R or A. Unrelated edges between visible nodes are excluded.
    allowed = ({'DRIVES', 'DERIVES', 'INTRODUCES', 'INFO_FOR', 'EVIDENCE_FOR'} if kind == 'requirement' else
               {'DRIVES', 'RELATES_R', 'CONTEXT_FOR', 'CANON_FOR', 'INTRODUCES', 'INFO_FOR', 'EVIDENCE_FOR'})
    visible = [e for e in visible if e['type'] in allowed]
    return {'profile': PROFILE, 'identitySpace': g['identitySpace'], 'ownerId': g['id'],
            'revision': g['revision'], 'focusId': nid, 'focusKind': kind,
            'entities': [copy.deepcopy(ns[i]) for i in sorted(chosen)], 'edges': visible,
            'terminalIds': sorted(boundary), 'origins': copy.deepcopy(origins),
            'originDetails': copy.deepcopy(origin_details),
            'workGraphIds': [w['id'] for w in g['workGraphs'] if nid in w['memberIds']],
            'situation': ([{'id': e['from'], 'kind': ns[e['from']]['kind'],
                            'role': 'realized' if e['type'] == 'DRIVES' else e.get('role', 'context')}
                           for e in edges if e['to'] == nid and e['type'] in ('DRIVES', 'RELATES_R', 'CONTEXT_FOR')]
                          if kind == 'action' else []),
            'canonAssessment': canon_verdict(g, nid) if kind == 'action' else None,
            'completion': completion_state(g), 'viewOnly': True}
