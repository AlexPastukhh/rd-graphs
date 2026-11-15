"""Bounded, snapshot-pinned read projections for RDG; no writes or hidden owner state."""
import base64
import copy
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCOPED = SourceFileLoader("rdg_scoped_read", str(Path(__file__).with_name("rdg-scoped-read.py"))).load_module()

DETAILS = ('summary', 'item', 'full', 'focus', 'branch')
FACETS = ('entities', 'edges', 'context', 'canon', 'findings', 'questions', 'dependencyApplications', 'plan', 'planForks', 'planTimeConstraints', 'completion', 'recommendations', 'subjects')
HISTORY_FACETS = ('events', 'planVersions')
DEFAULT_LIMIT = 25
MAX_LIMIT = 100


def schema():
    return {'schemaVersion': 1, 'read': {'detail': list(DETAILS),
            'include': list(FACETS), 'nodeId': 'required for detail=item|focus|branch',
            'recordId': 'optional exact record ID for one requested facet',
            'limit': {'default': DEFAULT_LIMIT, 'min': 1, 'max': MAX_LIMIT},
            'cursor': 'opaque, snapshot-bound, per facet'},
            'history': {'detail': ['compact', 'item', 'full'], 'include': list(HISTORY_FACETS),
                        'limit': {'default': DEFAULT_LIMIT, 'min': 1, 'max': MAX_LIMIT},
                        'cursor': 'opaque, snapshot-bound, per facet',
            'eventId': 'required for detail=item'},
            'scoped': SCOPED.schema(),
            'compatibility': 'Missing detail preserves the original full response.'}


def check(app, ok, code):
    app.check(ok, 'READ_' + code)


def validate(app, detail, include, node_id, limit, cursor):
    check(app, detail in DETAILS[:2], 'DETAIL')
    check(app, isinstance(include, list) and len(include) == len(set(include)) and
          all(isinstance(x, str) and x in FACETS for x in include), 'INCLUDE')
    check(app, type(limit) is int and 1 <= limit <= MAX_LIMIT, 'LIMIT')
    check(app, (detail == 'item') == (isinstance(node_id, str) and bool(node_id)), 'NODE_ID')
    facets = include or (['entities'] if detail == 'summary' else [])
    check(app, cursor is None or isinstance(cursor, str) and bool(cursor) and len(facets) == 1, 'CURSOR')
    return facets


def pin(app, row):
    graph = row['graph']
    return {'packageRevision': row['head']['revision'],
            'graphRevision': graph['revision'], 'graphSHA256': app.model.digest(graph),
            'planRevision': row['plan']['revision'] if row['plan'] is not None else None}


def paginate(app, rows, facet, token, snapshot, node_id, limit):
    offset = 0
    if token is not None:
        try:
            decoded = base64.urlsafe_b64decode(token.encode('ascii'))
            payload = json.loads(decoded)
        except (ValueError, UnicodeError, TypeError) as exc:
            raise ValueError('PORTABLE_APP_READ_CURSOR_INVALID') from exc
        check(app, isinstance(payload, dict) and set(payload) == {'pin', 'facet', 'nodeId', 'offset'}, 'CURSOR_INVALID')
        check(app, payload['pin'] == snapshot, 'CURSOR_STALE')
        check(app, payload['facet'] == facet and payload['nodeId'] == node_id and
              type(payload['offset']) is int and payload['offset'] >= 0, 'CURSOR_INVALID')
        offset = payload['offset']
    take = rows[offset:offset+limit]
    end = offset + len(take)
    nxt = None
    if end < len(rows):
        value = {'pin': snapshot, 'facet': facet, 'nodeId': node_id, 'offset': end}
        nxt = base64.urlsafe_b64encode(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).decode('ascii')
    return {'items': copy.deepcopy(take), 'page': {'total': len(rows), 'limit': limit,
            'returned': len(take), 'nextCursor': nxt, 'hasMore': nxt is not None}}
def project(app, ident, row, detail, include, node_id, limit, cursor, record_id=None):
    facets = validate(app, detail, include, node_id, limit, cursor)
    check(app, record_id is None or isinstance(record_id,str) and bool(record_id) and
          len(facets)==1 and facets[0] in ('edges','canon','findings','dependencyApplications','plan','planForks'), 'RECORD_ID')
    check(app, record_id is None or cursor is None, 'RECORD_CURSOR_UNAVAILABLE')
    graph = row['graph']
    entities = dict(app.kernel.entities(graph))
    if facets==['recommendations']:
        entities[graph['id']]={'id':graph['id'],'kind':'process','title':graph['title']}
        entities.update({w['id']:{**w,'kind':'workGraph'} for w in graph.get('workGraphs',[])})
    if detail == 'item':
        check(app, node_id in entities, 'NODE_NOT_FOUND')
    snapshot = pin(app, row)
    result = {'schemaVersion': 1, 'package': {k: row['head'][k] for k in
              ('packageId', 'role', 'identitySpace', 'revision')},
              'graph': {k: graph.get(k) for k in ('id', 'title', 'coreModel', 'revision', 'identitySpace', 'rootRequirementId')},
              'path':row['path'], 'immutableDefinition':bool(row['head'].get('lineage',{}).get('supplied') and not row['head'].get('lineage',{}).get('userManaged')),
              'snapshot': snapshot, 'detail': detail,
              'loaded': {key: key in facets for key in FACETS}, 'data': {}}
    if detail == 'item':
        result['item'] = copy.deepcopy(entities[node_id])
    decision = app.kernel.for_graph(graph) if graph['coreModel'] == 'rdg-decision-v1' else None
    for facet in facets:
        if facet == 'entities':
            rows = [{'id': n['id'], 'kind': n['kind'], 'title': n.get('title'),
                     'revision': n.get('revision'), 'status': n.get('status'),
                     'selectionState': n.get('selectionState'),**({'estimates':copy.deepcopy(n['estimates'])} if 'estimates' in n else {})} for n in entities.values()]
        elif facet == 'edges':
            rows = [e for e in graph['edges'] if node_id is None or
                    node_id in (e.get('from'), e.get('to'))]
        elif facet == 'context':
            rows = (decision.decision_context(graph, node_id) if decision and detail == 'item'
                    and entities[node_id]['kind'] == 'decision' else
                    [n for n in graph.get('objects', []) if n['kind'] == 'context'] if detail == 'summary' else [])
        elif facet == 'canon':
            ids = {e['from'] for e in graph['edges'] if e['type'] == 'CANON_FOR' and e['to'] == node_id} if node_id else None
            rows = [n for n in graph.get('objects', []) if n['kind'] == 'canon' and (ids is None or n['id'] in ids)]
        elif facet == 'findings':
            rows = [n for n in graph.get('objects', []) if n['kind'] == 'finding' and
                    (node_id is None or n.get('subjectId') == node_id)]
        elif facet == 'questions':
            rows=[n for n in graph.get('objects',[]) if n['kind']=='question' and
                  (node_id is None or node_id==n['id'] or any(decision.QUESTIONS.reference_id(graph,ref,decision,n)==node_id for ref in n.get('relatedRefs',[])))]
        elif facet == 'dependencyApplications':
            rows = (decision.POLICIES.describe_applications(graph, decision) if decision else [])
            if node_id is not None:
                rows = [x for x in rows if node_id == x.get('targetId') or node_id in x.get('nodeIds', [])]
        elif facet == 'plan':
            rows = row['plan']['steps'] if row['plan'] is not None else []
            if node_id is not None:
                rows = [x for x in rows if x.get('ref', {}).get('nodeId') == node_id]
            result['plan'] = ({'available': False} if row['plan'] is None else
                              {'available': True, 'id': row['plan']['id'],
                               'revision': row['plan']['revision'],
                               'stepCount': len(row['plan']['steps']),
                               'forkCount': len(row['plan'].get('forks', [])),
                               'timeConstraintCount': len(row['plan']['timeConstraints'])})
        elif facet == 'planForks':
            check(app, node_id is None, 'PLAN_FORK_NODE_FILTER_UNAVAILABLE')
            rows = row['plan'].get('forks', []) if row['plan'] else []
        elif facet == 'planTimeConstraints':
            rows = row['plan']['timeConstraints'] if row['plan'] else []
            if node_id is not None:
                step_ids = {s['id'] for s in row['plan']['steps'] if s.get('ref', {}).get('nodeId') == node_id}
                rows = [r for r in rows if r['stepId'] in step_ids]
        elif facet == 'subjects':
            rows=[{'actionId':a['id'],**app.resolve_action_subject(ref,a,row)} for a in graph.get('externalActions',[]) if node_id is None or a['id']==node_id for ref in a.get('subjectRefs',[])]
            snapshot['subjectProjectionSHA256']=app.model.digest(rows)
        elif facet == 'recommendations':
            rec=app.recommendation_projection(ident,graph)
            snapshot['recommendationRegistryRevision']=rec.get('registryRevision')
            snapshot['recommendationProjectionSHA256']=app.model.digest(rec)
            result['recommendationAvailability']={'available':rec['available'],'diagnostics':rec['diagnostics']}
            rows=[m for m in rec['matches'] if node_id is None or m['nodeId']==node_id]
        elif facet == 'completion':
            states = app.kernel.completion_state(graph)
            rows = [{'nodeId': i, 'state': value} for i, value in states.items()
                    if node_id is None or i == node_id]
        if record_id is not None:
            rows = [r for r in rows if r.get('id', r.get('findingId')) == record_id]
        result['data'][facet] = paginate(app, rows, facet, cursor, snapshot, node_id, limit)
    return result


def project_history(app, row, full, include, limit, cursor, view=None):
    check(app, isinstance(include, list) and len(include) == len(set(include)) and
          all(isinstance(x, str) and x in HISTORY_FACETS for x in include), 'HISTORY_INCLUDE')
    check(app, type(limit) is int and 1 <= limit <= MAX_LIMIT, 'LIMIT')
    facets = include or ['events']
    check(app, cursor is None or isinstance(cursor, str) and bool(cursor) and len(facets) == 1, 'CURSOR')
    snapshot = {**pin(app, row), 'historyFilter': copy.deepcopy(view or {})}
    result = {'schemaVersion': 1, 'packageId': row['head']['packageId'],
              'snapshot': snapshot, 'modes': full['modes'],
              'loaded': {f: f in facets for f in HISTORY_FACETS}, 'data': {}}
    for facet in facets:
        rows = full[facet]
        if facet == 'events':
            rows = [{'id': r['event']['id'], 'type': r['event']['type'],
                     'recordedAt': r['event'].get('recordedAt'),
                     'displayTargetIds': r['displayTargetIds'],
                     'inherited': r['inherited'],
                     'level': (r.get('historyView') or {}).get('level'),
                     'label': (r.get('historyView') or {}).get('label'),
                     'hasDetails': bool(r.get('historyView'))} for r in rows]
        else:
            rows = [{'sha256': r['sha256'], 'revision': r['plan']['revision'],
                     'sourcePackageId': r['sourcePackageId'], 'current': r['current']} for r in rows]
        result['data'][facet] = paginate(app, rows, facet, cursor, snapshot, None, limit)
    return result
