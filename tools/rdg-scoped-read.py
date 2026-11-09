"""Addressed, read-only focus/branch packages. No layout, catalog or writer."""
import base64
import copy
import hashlib
import json
from collections import defaultdict

FACETS = ('parents', 'entities', 'edges', 'decisionGroups', 'decisionMemberships',
          'outline', 'context', 'canon', 'findings', 'questions', 'completion',
          'recommendations', 'dependencyApplications', 'subjects', 'plan')
DEFAULTS = FACETS[:-1]
STRUCTURAL = ('DERIVES', 'DRIVES', 'INTRODUCES', 'REQUIRES_ACTION')
VERSION = 1


def schema():
    return {'profile': 'rdg-decision-v1', 'rootKinds': {
        'focus': ['requirement', 'decision', 'action', 'canon', 'context', 'info', 'finding', 'question', 'evidence'],
        'branch': ['requirement', 'decision']},
        'include': list(FACETS), 'defaultInclude': list(DEFAULTS),
        'nodeId': 'required; existing entity ID in this package',
        'entities': {'ref': 'existing qualified entity reference', 'entity': 'complete canonical body; root first'},
        'reference': {'ref': 'qualified reference or null for a missing local endpoint',
                      'nodeId': 'recorded endpoint ID', 'kind': 'kind or null', 'title': 'title or null',
                      'status': 'current|missing', 'bodyState': 'loaded|pendingPage|notRequested|referenceOnly|missing'},
        'outline': {'occurrenceId': 'derived stable row address', 'parentOccurrenceId': 'row address or null',
                    'ref': 'qualified entity ref', 'via': 'edge or membership; null for root',
                    'mode': ['expand', 'reference'], 'reason': ['cycle', 'shared', 'boundary', 'unavailable', None]},
        'sections': {'parents': 'brief root parents + via',
            'edges': 'canonical scoped and boundary edges', 'decisionGroups': 'canonical fields + membersComplete/originalMemberCount',
            'decisionMemberships': 'canonical derived membership rows', 'context': 'subjectRef + shared context row + source',
            'canon': 'subjectRef/source/via and linked Info refs', 'findings': 'shared descriptor with brief subject and source',
            'questions': 'source + relatedTo refs; body/answers in entities, legacy marked explicitly',
            'completion': 'nodeId/ref/state + blockerRefs (entity or group/parent descriptor)', 'recommendations': 'existing match rows; no target graph',
            'dependencyApplications': 'existing application without repeated policy definition (policyRef), or external-reference boundary descriptor without node body',
            'subjects': 'actionId + shared resolution without repeated node body',
            'plan': 'matching Action placements only, explicit include'},
        'reading': {'scopeEnumerated': 'entire structural scope enumerated; not a delivery-complete flag',
                    'requestedSections': 'sections in this request', 'continuations': 'exact next read requests'},
        'cursor': 'per section, scope/version/source/auth-status pinned; continuation requests one section',
        'compatibility': 'summary/item/full and default item unchanged; no automatic Markdown parsing'}


def check(app, ok, code):
    app.check(ok, 'READ_' + code)


def options(app, detail, include, node_id, limit, token):
    check(app, detail in ('focus', 'branch'), 'DETAIL')
    check(app, isinstance(node_id, str) and bool(node_id), 'NODE_ID')
    check(app, isinstance(include, list) and all(isinstance(x, str) and x in FACETS for x in include)
          and len(include) == len(set(include)), 'INCLUDE')
    check(app, type(limit) is int and 1 <= limit <= 100, 'LIMIT')
    selected = include or list(DEFAULTS)
    origin = list(selected)
    if token is not None:
        check(app, isinstance(token, str) and bool(token) and len(selected) == 1, 'CURSOR')
        try:
            decoded = json.loads(base64.urlsafe_b64decode(token.encode('ascii')))
            signature = decoded['pin']['scope']
            origin = signature['sections']
            valid = (set(decoded) == {'pin', 'facet', 'nodeId', 'offset'}
                     and decoded['facet'] == selected[0] and decoded['nodeId'] == node_id
                     and type(decoded['offset']) is int and decoded['offset'] >= 0
                     and signature['detail'] == detail and signature['root'] == node_id
                     and signature['version'] == VERSION and isinstance(origin, list)
                     and len(origin) == len(set(origin))
                     and all(isinstance(f, str) and f in FACETS for f in origin)
                     and selected[0] in origin)
        except (ValueError, TypeError, KeyError, UnicodeError):
            valid = False
        check(app, valid, 'CURSOR_INVALID')
    return selected, origin


def walk(root, links, available):
    """Iterative DFS: one expansion per entity; stack membership distinguishes cycles."""
    outgoing = defaultdict(list)
    for link in links:
        outgoing[link['from']].append(link)
    seen = {root}
    active = {root}
    order = [root]
    rows = [{'occurrenceId': 'o0', 'parentOccurrenceId': None, 'nodeId': root,
             'via': None, 'mode': 'expand', 'reason': None}]
    stack = [(root, 'o0', iter(outgoing[root]))]
    while stack:
        source, parent, iterator = stack[-1]
        link = next(iterator, None)
        if link is None:
            active.remove(source)
            stack.pop()
            continue
        target = link['to']
        reason = ('unavailable' if target not in available else 'cycle' if target in active
                  else 'shared' if target in seen else None)
        occurrence = 'o' + str(len(rows))
        rows.append({'occurrenceId': occurrence, 'parentOccurrenceId': parent,
                     'nodeId': target, 'via': copy.deepcopy(link),
                     'mode': 'reference' if reason else 'expand', 'reason': reason})
        if reason is None:
            seen.add(target)
            active.add(target)
            order.append(target)
            stack.append((target, occurrence, iter(outgoing[target])))
    return order, rows


def project(app, ident, row, detail, include, node_id, limit, token, compact):
    selected, origin = options(app, detail, include, node_id, limit, token)
    graph = row['graph']
    check(app, graph.get('coreModel') == 'rdg-decision-v1', 'PROFILE_UNSUPPORTED')
    K = app.kernel.for_graph(graph)
    ns = K.entities(graph)
    # Only this read-only Application path opts in. Writers never seed this key.
    K.ANALYSIS.active_read_cache(graph)['scopedImmutableEntities'] = ns
    check(app, node_id in ns, 'NODE_NOT_FOUND')
    check(app, detail != 'branch' or ns[node_id]['kind'] in ('requirement', 'decision'), 'ROOT_KIND')
    sha = app.model.digest(graph)
    refs = {}
    def ref(i):
        if i not in ns:
            return None
        if i not in refs:
            refs[i] = app.model.reference(ident, graph, i, graph_sha256=sha, node_revision=ns[i]['revision'])
        return refs[i]
    def brief(i):
        n = ns.get(i)
        return {'ref': ref(i), 'nodeId': i, 'kind': n.get('kind') if n else None,
                'title': n.get('title') if n else None, 'status': 'current' if n else 'missing'}

    edges = sorted(K.active_edges(graph), key=lambda e: e['id'])
    memberships = K.decision_memberships(graph)
    # Keep group/member order (including independent groups), then deterministic edge IDs.
    links = memberships + [e for e in edges if e['type'] in STRUCTURAL]
    unique = []
    seen_links = set()
    for e in links:
        key = (e['type'], e['id'])
        if key not in seen_links:
            seen_links.add(key)
            unique.append(e)
    links = unique
    focus = None
    if detail == 'focus':
        if node_id in {a['id'] for a in graph.get('externalActions', [])}:
            focus = {'entities': [ns[node_id]], 'edges': [], 'decisionMemberships': [],
                     'decisionGroups': []}
        else:
            focus = K.focused_view(graph, node_id, include_completion=False)
        chosen = {n['id'] for n in focus['entities']}
        parents = [e for e in links if e['to'] == node_id]
        parent_ids = {e['from'] for e in parents}
        structural = {node_id} | {i for i in chosen - parent_ids if ns[i]['kind'] in ('requirement', 'decision', 'action')}
        scoped_links = [e for e in links if e['from'] == node_id and e['to'] in structural]
        order, outline = walk(node_id, scoped_links, ns)
        structural.update(order)
        # Auxiliary focus may select a structural neighbor through a non-structural relation.
        order += sorted(structural - set(order))
        subject_ids = {node_id}
        scoped_edges = focus['edges']
        scoped_members = focus['decisionMemberships']
        groups = focus['decisionGroups']
    else:
        order, outline = walk(node_id, links, ns)
        structural = set(order)
        subject_ids = structural
        parents = [e for e in links if e['to'] == node_id]
        scoped_edges = [e for e in edges if e['from'] in structural and e['to'] in structural
                        or e['type'] in STRUCTURAL and e['to'] in structural]
        scoped_members = [e for e in memberships if e['to'] in structural]
        groups = [{**g, 'members': [m for m in g['members'] if m['decisionId'] in structural]}
                  for g in graph['decisionGroups']
                  if g['parentId'] in structural or any(m['decisionId'] in structural for m in g['members'])]
    # A logical membership and legacy DRIVES may describe one step; preserve both links,
    # but subsequent occurrence is a shared reference, never a second body.
    included = set(structural)
    contexts, canons = [], []
    attached = defaultdict(list)
    for e in edges:
        if e['type'] in ('CONTEXT_FOR', 'CANON_FOR', 'INFO_FOR', 'EVIDENCE_FOR'):
            attached[e['to']].append(e)
    for i in sorted(subject_ids):
        if ns[i]['kind'] == 'decision':
            for c in K.decision_context(graph, i):
                contexts.append({'subjectRef': ref(i), **copy.deepcopy(c), 'source': brief(c['sourceId'])})
                if c['present']:
                    included.add(c['sourceId'])
        for e in attached[i]:
            included.add(e['from'])
            entry = {'subjectRef': ref(i), 'source': brief(e['from']), 'via': copy.deepcopy(e)}
            if e['type'] == 'CANON_FOR':
                info = [r for r in attached[e['from']] if r['type'] == 'INFO_FOR']
                included.update(r['from'] for r in info)
                entry['info'] = [{'source': brief(r['from']), 'via': copy.deepcopy(r)} for r in info]
                canons.append(entry)
            else:
                contexts.append({**entry, 'sourceId': e['from'], 'present': e['from'] in ns,
                                 'manual': False, 'provenance': [], 'edgeIds': [e['id']]})
    if focus:
        parent_ids = {e['from'] for e in parents}
        included.update(n['id'] for n in focus['entities'] if n['id'] not in parent_ids
                        or n['kind'] not in ('requirement', 'decision', 'action'))
    finding_ids = {n['id'] for n in graph['objects'] if n['kind'] == 'finding'
                   and (n['subjectId'] in subject_ids or n['id'] in included)}
    finding_ids.update(p['findingId'] for c in contexts for p in c.get('provenance', []))
    included.update(finding_ids)
    finding_rows = []
    descriptors = K.FINDINGS.describe(graph, K, node_id) if finding_ids else []
    for f in descriptors:
        if f['findingId'] in finding_ids:
            f = copy.deepcopy(f)
            sub = f['subject']
            f['subject'] = {**brief(sub['id']), 'present': sub['present']}
            if not sub['present']:
                f['subject'].update(title=sub.get('title'), kind=sub.get('kind'), recorded=True)
            f['source'] = brief(f['findingId'])
            finding_rows.append(f)
    question_rows = []
    related_ids = subject_ids | finding_ids
    for q in graph['objects']:
        if q['kind'] != 'question':
            continue
        targets = [K.QUESTIONS.reference_id(graph, r, K, q) for r in q.get('relatedRefs', [])]
        hits = sorted(set(targets) & related_ids)
        if q['id'] in subject_ids or hits:
            included.add(q['id'])
            question_rows.append({'source': brief(q['id']), 'relatedTo': [ref(i) for i in hits], 'legacy': False})
    for i in sorted(related_ids):
        for q in ns.get(i, {}).get('questions', []):
            question_rows.append({'legacy': True, 'ownerRef': ref(i), 'question': copy.deepcopy(q)})
    # Canon selected as the focus itself also exposes its direct Info.
    if ns[node_id]['kind'] == 'canon' and not canons:
        info = [r for r in attached[node_id] if r['type'] == 'INFO_FOR']
        included.update(r['from'] for r in info)
        canons.append({'subjectRef': ref(node_id), 'source': brief(node_id), 'via': None,
                       'info': [{'source': brief(r['from']), 'via': copy.deepcopy(r)} for r in info]})
    included &= ns.keys()
    snapshot = compact.pin(app, row)
    snapshot['scope'] = {'packageId': ident, 'detail': detail, 'root': node_id, 'version': VERSION, 'sections': origin}
    registered = {ident: row}
    def register(pid):
        if pid not in registered:
            registered[pid] = app.snapshot(pid, layouts=False)
        value = registered[pid]
        return value

    data = {'parents': [{**brief(e['from']), 'via': copy.deepcopy(e)} for e in parents],
            'edges': copy.deepcopy(scoped_edges), 'decisionMemberships': copy.deepcopy(scoped_members),
            'outline': [{**r, **brief(r['nodeId'])} for r in outline],
            'context': contexts, 'canon': canons, 'findings': finding_rows, 'questions': question_rows}
    for name in ('edges','decisionMemberships'):
        for edge in data[name]:
            edge['fromEndpoint'] = brief(edge['from'])
            edge['toEndpoint'] = brief(edge['to'])
    originals = {g['id']: g for g in graph['decisionGroups']}
    data['decisionGroups'] = [{**copy.deepcopy(g),
                              'membersComplete': len(g['members']) == len(originals[g['id']]['members']),
                              'originalMemberCount': len(originals[g['id']]['members']),
                              'parent': brief(g['parentId'])} for g in groups]
    body_order = list(dict.fromkeys([node_id, *order, *sorted(included - set(order))]))
    data['entities'] = [{'ref': ref(i), 'entity': ns[i]} for i in body_order if i in included]
    external = (app.boundaries(row, register) if graph.get('externalRefs') and
                {'completion','dependencyApplications'} & set(origin) else
                {'states': [], 'reviewIds': [], 'conflictIds': [], 'pinsRefreshed': False})
    snapshot['boundaries'] = app.model.digest(external)

    if 'recommendations' in origin:
        rec = app.recommendation_projection(ident, graph, node_ids=subject_ids, register=register)
        data['recommendations'] = rec['matches']
        snapshot['recommendations'] = app.model.digest(rec)
    if 'subjects' in origin:
        data['subjects'] = []
        resolved_cache = {}
        for i in sorted(subject_ids):
            action = ns[i]
            for target in action.get('subjectRefs', []):
                # Inherited bindings belong to the containing Action, not merely its ref.
                key = (json.dumps(target, sort_keys=True), json.dumps(action.get('referenceBindings'), sort_keys=True))
                if key not in resolved_cache:
                    resolved_cache[key] = app.resolve_action_subject(target, action, row, register=register)
                resolved = copy.deepcopy(resolved_cache[key])
                body = resolved.pop('node', None)
                if body is not None:
                    resolved['target'] = {k: body.get(k) for k in ('id', 'kind', 'title', 'revision')}
                data['subjects'].append({'actionId': i, **resolved})
        snapshot['subjects'] = app.model.digest(data['subjects'])
    if 'plan' in origin:
        data['plan'] = [copy.deepcopy(s) for s in (row['plan'] or {}).get('steps', [])
                        if s.get('ref', {}).get('packageId') == ident
                        and s['ref'].get('identitySpace') == graph['identitySpace']
                        and s['ref'].get('nodeId') in structural
                        and ns[s['ref']['nodeId']]['kind'] == 'action']
    snapshot['sources'] = {pid: {'graphRevision': r['graph']['revision'],
                                'graphSHA256': app.model.digest(r['graph'])}
                           for pid, r in sorted(registered.items()) if pid != ident}
    if 'completion' in selected:
        cache_key = app.model.digest({'snapshot': snapshot, 'section': 'completion',
                                      'actor': hashlib.sha256(app.token.encode()).hexdigest()})
        cached = app._scoped_cache.get(cache_key)
        if cached is not None:
            data['completion'] = cached
        else:
            states = app.states(row, external)
            group_index = {g['id']: g for g in graph['decisionGroups']}
            def blocker(i):
                group = group_index.get(i.removeprefix('group:')) if i.startswith('group:') else None
                return ({'groupId': group['id'], 'title': group['title'], 'parent': brief(group['parentId'])}
                        if group else brief(i))
            data['completion'] = [{'nodeId': i, 'ref': ref(i), 'state': states[i],
                                   'blockerRefs': [blocker(b) for b in states[i]['blockers']]}
                                  for i in sorted(subject_ids) if i in states]
            app._scoped_cache.put(cache_key, data['completion'])
    if 'dependencyApplications' in selected:
        cache_key = app.model.digest({'snapshot': snapshot, 'section': 'dependencyApplications',
                                      'actor': hashlib.sha256(app.token.encode()).hexdigest()})
        cached = app._scoped_cache.get(cache_key)
        if cached is not None:
            data['dependencyApplications'] = cached
        else:
            data['dependencyApplications'] = []
            for value in K.POLICIES.describe_applications(graph, K):
                if value['targetId'] not in subject_ids and not (set(value['nodeIds']) & subject_ids):
                    continue
                value = copy.deepcopy(value)
                p = value.pop('policy')
                value['policyRef'] = {'id': p['id'], 'version': p['version'], 'name': p['name']}
                data['dependencyApplications'].append(value)
            for boundary in external['states']:
                affected = set(K.affected(graph, graph, [boundary['localId']]))
                if boundary['localId'] not in subject_ids and not (boundary['reviewRequired'] and affected & subject_ids):
                    continue
                value = copy.deepcopy(boundary)
                body = value['resolved'].pop('node', None)
                if body is not None:
                    value['resolved']['targetSummary'] = {k: body.get(k) for k in ('id','kind','title','revision')}
                data['dependencyApplications'].append({'id': boundary['referenceId'], 'kind': 'external-reference', **value})
            app._scoped_cache.put(cache_key, data['dependencyApplications'])
    result = {'schemaVersion': 1,
              'package': {k: row['head'][k] for k in ('packageId', 'role', 'identitySpace', 'revision')},
              'graph': {k: graph.get(k) for k in ('id', 'title', 'coreModel', 'revision', 'identitySpace', 'rootRequirementId')},
              'snapshot': snapshot, 'detail': detail, 'scope': {'kind': detail, 'rootRef': ref(node_id), 'viewOnly': True},
              'loaded': {f: f in selected for f in FACETS}, 'data': {},
              'reading': {'requestedSections': selected, 'scopeEnumerated': True, 'continuations': []}}
    if 'recommendations' in selected:
        result['recommendationAvailability'] = {'available': rec['available'], 'diagnostics': rec['diagnostics']}
    if 'plan' in selected:
        result['plan'] = ({'available': False} if row['plan'] is None else
                          {'available': True, 'id': row['plan']['id'], 'revision': row['plan']['revision']})
    for facet in selected:
        result['data'][facet] = compact.paginate(app, data.get(facet, []), facet, token, snapshot, node_id, limit)
        nxt = result['data'][facet]['page']['nextCursor']
        if nxt:
            result['reading']['continuations'].append({'method': 'read', 'packageId': ident,
                'detail': detail, 'nodeId': node_id, 'include': [facet], 'limit': limit, 'cursor': nxt})
    delivered = {r['entity']['id'] for r in result['data'].get('entities', {}).get('items', [])}
    def mark(value):
        if isinstance(value, dict):
            if 'ref' in value and 'nodeId' in value and 'status' in value:
                i = value['nodeId']
                value['bodyState'] = ('missing' if i not in ns else 'referenceOnly' if i not in included
                    else 'notRequested' if 'entities' not in selected else 'loaded' if i in delivered else 'pendingPage')
            for v in value.values():
                mark(v)
        elif isinstance(value, list):
            for v in value:
                mark(v)
    # Never annotate the canonical bodies or stored refs themselves.
    for facet, page in result['data'].items():
        if facet != 'entities':
            mark(page['items'])
    return result


def read_pages(client, message, all_pages=False):
    """Client-side assembly only; a continuation response never proves earlier delivery."""
    if all_pages and message.get('cursor') is not None:
        raise ValueError('READ_ALL_PAGES_REQUIRES_FIRST_PAGE')
    result = client.call(message)
    if message.get('detail') not in ('focus', 'branch'):
        if all_pages:
            raise ValueError('READ_ALL_PAGES_REQUIRES_FOCUS_OR_BRANCH')
        return result
    calls = 1
    if all_pages:
        for facet, section in result['data'].items():
            seen = set()
            cursor = section['page']['nextCursor']
            while cursor is not None:
                if cursor in seen:
                    raise ValueError('READ_CURSOR_REPEATED')
                seen.add(cursor)
                page = client.call({**message, 'include': [facet], 'cursor': cursor})
                calls += 1
                if page['snapshot'] != result['snapshot'] or page['scope'] != result['scope']:
                    raise ValueError('READ_CURSOR_STALE')
                part = page['data'][facet]
                if part['page']['total'] != section['page']['total'] or not part['items']:
                    raise ValueError('READ_PAGE_INCONSISTENT')
                section['items'].extend(part['items'])
                cursor = part['page']['nextCursor']
            if len(section['items']) != section['page']['total']:
                raise ValueError('READ_PAGE_INCOMPLETE')
            section['page'].update(returned=len(section['items']), nextCursor=None, hasMore=False)
        def delivered(value):
            if isinstance(value, dict):
                if value.get('bodyState') == 'pendingPage':
                    value['bodyState'] = 'loaded'
                for v in value.values():
                    delivered(v)
            elif isinstance(value, list):
                for v in value:
                    delivered(v)
        for facet, section in result['data'].items():
            if facet != 'entities':
                delivered(section['items'])
        result['reading']['continuations'] = []
    result['reading']['pagesComplete'] = (message.get('cursor') is None
        and all(not s['page']['hasMore'] for s in result['data'].values()))
    result['reading']['pageRequests'] = calls
    return result
