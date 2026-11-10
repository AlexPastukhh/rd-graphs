#!/usr/bin/env python3
"""Authorized literal search of current RDG entity text."""
import base64
import json


FIELDS = {
    'requirement': ('resultCondition',),
    'decision': ('resultCondition', 'contextNotes', 'questions', 'reviewLimitations', 'userAssistance'),
    'action': ('resultCondition', 'estimates'),
    'context': ('value',),
    'info': ('value',),
    'canon': ('guidance', 'canons', 'knownErrors'),
    'finding': ('rationale', 'limitation', 'disposition'),
    'question': ('impact', 'answerCondition', 'answers', 'assessment'),
    'evidence': ('claim',),
}
LABELS = {
    'id': 'ID', 'title': 'Название', 'description': 'Описание',
    'resultCondition': 'Условия результата', 'estimates': 'Оценки исполнения',
    'contextNotes': 'Контекст принятия решения', 'value': 'Содержание',
    'guidance': 'Общее', 'canons': 'Каноны', 'knownErrors': 'Известные ошибки',
    'claim': 'Утверждение',
    'rationale': 'Обоснование', 'limitation': 'Ограничение', 'disposition': 'Рассмотрение',
    'impact': 'Влияние', 'answerCondition': 'Условие достаточности', 'answers': 'Ответы',
    'assessment': 'Оценка достаточности', 'questions': 'Вопросы',
    'reviewLimitations': 'Ограничения проверки', 'userAssistance': 'Вопросы и помощь',
}
# Typed refs, provenance keys and version pins do not represent authored text.
TECHNICAL = frozenset({
    'id', 'ref', 'refs', 'source', 'sourceRef', 'sourceRefs', 'reference', 'provenance',
    'author', 'by', 'recordedAt', 'eventId', 'packageId', 'identitySpace', 'sha256',
    'kind', 'type', 'state', 'status', 'mode',
})
SECTIONS = {'canon': 'canon', 'context': 'context', 'finding': 'findings', 'question': 'questions'}


def schema():
    return {'schemaVersion': 1, 'search': {
        'scope': ['package', 'catalog'], 'query': {'maxLength': 180, 'mode': 'literal-casefold'},
        'limit': {'default': 25, 'min': 1, 'max': 100}, 'packageId': 'required for package scope',
        'cursor': 'opaque, query/visibility/snapshot-bound',
        'item': ['ref', 'kind', 'title', 'owner', 'matches', 'target'],
    }}


def texts(value, path, *, arbitrary=False):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            if arbitrary or key not in TECHNICAL:
                yield from texts(child, f'{path}.{key}', arbitrary=arbitrary)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from texts(child, f'{path}[{index}]', arbitrary=arbitrary)


def snippet(text, index, folded_length):
    # Unicode casefold may expand a character, so offsets in the folded string
    # are not necessarily character offsets into the original value.
    length = 0
    start = end = 0
    for i, char in enumerate(text):
        if length <= index:
            start = i
        length += len(char.casefold())
        if length >= index + folded_length:
            end = i + 1
            break
    lo, hi = max(0, start - 46), min(len(text), max(start + 100, end + 46))
    return ('…' if lo else '') + ' '.join(text[lo:hi].split()) + ('…' if hi < len(text) else '')


def matches(entity, query):
    rank = 3
    hits = []
    for field in ('id', 'title', 'description', *FIELDS.get(entity['kind'], ())):
        for path, value in texts(entity.get(field), field, arbitrary=field == 'value'):
            index = value.casefold().find(query)
            if index < 0:
                continue
            rank = min(rank, 0 if field == 'id' and value.casefold() == query else
                       1 if field in ('id', 'title') else 2)
            hits.append({'field': path, 'label': LABELS[field],
                         'snippet': snippet(value, index, len(query))})
    return rank, hits


def search(app, query, scope='package', package_id=None, limit=25, cursor=None):
    app.check(isinstance(query, str) and 0 < len(query.strip()) <= 180, 'SEARCH_QUERY')
    app.check(scope in ('package', 'catalog') and
              (isinstance(package_id, str) and bool(package_id) if scope == 'package'
               else package_id is None), 'SEARCH_SCOPE')
    app.check(type(limit) is int and 1 <= limit <= 100, 'SEARCH_LIMIT')
    app.check(cursor is None or isinstance(cursor, str) and 0 < len(cursor) <= 4096,
              'SEARCH_CURSOR')
    query = query.strip().casefold()
    found, pins = [], []
    with app.store.lock(False, create=False):
        ids = ([package_id] if scope == 'package' else
               sorted({r['packageId'] for r in app.store.scan()
                       if r.get('packageId') and r.get('health') == 'metadata-verified'}))
        for ident in ids:
            try:
                row = app.snapshot(ident, layouts=False, scoped_read=True)
            except ValueError as exc:
                if scope == 'catalog' and str(exc) == 'PORTABLE_SCOPE_DENIED':
                    continue
                raise
            graph = row['graph']
            if graph.get('coreModel') != 'rdg-decision-v1':
                if scope == 'catalog':
                    continue
                app.check(False, 'SEARCH_PROFILE_UNSUPPORTED')
            digest = app.model.digest(graph)
            pins.append((ident, row['head']['revision'], digest, row['path']))
            owner = {'packageId': ident, 'title': graph['title'], 'path': row['path'],
                     'role': row['head']['role']}
            for entity in app.kernel.entities(graph).values():
                rank, hits = matches(entity, query)
                if not hits:
                    continue
                ref = app.model.reference(ident, graph, entity['id'], graph_sha256=digest,
                                          node_revision=entity['revision'])
                section = SECTIONS.get(entity['kind'])
                if entity['kind'] == 'decision' and hits[0]['field'].startswith('contextNotes.'):
                    section = 'context'
                target = {'ref': ref, 'section': section}
                if entity['kind'] == 'finding':
                    target['subjectId'] = entity.get('subjectId')
                found.append(((rank, bool(entity.get('lowLevel')), graph['title'].casefold(), ident, entity['id']),
                              {'ref': ref, 'kind': entity['kind'], 'title': entity['title'],
                               'owner': owner, 'matches': hits, 'target': target}))
        fingerprint = app.model.digest({'query': query, 'scope': scope, 'packageId': package_id,
                                        'namespaceId': app.store.namespace_id, 'pins': pins})
        offset = 0
        if cursor is not None:
            try:
                data = json.loads(base64.urlsafe_b64decode(cursor.encode('ascii')))
            except (ValueError, UnicodeError) as exc:
                raise ValueError('PORTABLE_APP_SEARCH_CURSOR') from exc
            app.check(isinstance(data, list) and len(data) == 2 and type(data[1]) is int
                      and 0 < data[1], 'SEARCH_CURSOR')
            app.check(data[0] == fingerprint, 'SEARCH_CURSOR_STALE')
            app.check(data[1] < len(found), 'SEARCH_CURSOR')
            offset = data[1]
        found.sort(key=lambda row: row[0])
        items = [item for _, item in found[offset:offset + limit]]
        end = offset + len(items)
        nxt = (base64.urlsafe_b64encode(json.dumps([fingerprint, end]).encode()).decode('ascii')
               if end < len(found) else None)
        return {'schemaVersion': 1, 'scope': {'kind': scope, 'packageId': package_id},
                'items': items, 'page': {'hasMore': nxt is not None, 'nextCursor': nxt}}
