"""Addressable theory-owned entries and source references; no Graph node kinds.

All authoring uses the normal core writer. These functions only validate, read
and remap owned values. Source expansion is explicit and one level deep.
"""
import base64
import copy
import hashlib
import json
import re
from importlib.machinery import SourceFileLoader
from pathlib import Path

SOURCES = SourceFileLoader('rdg_theory_sources', str(Path(__file__).with_name('rdg-theory-sources.py'))).load_module()
COLLECTIONS = ('canons', 'recommendations')
FIELDS = ('canonItems', 'recommendations')
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z')
LINK = re.compile(r'\[([^\]\n]*)\]\(theory:(canons|recommendations)/([A-Za-z0-9][A-Za-z0-9._-]{0,127})\)')
MAX_PAGE_BYTES = 2 * 1024 * 1024


def require(ok, code):
    if not ok:
        raise ValueError('THEORY_' + code)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def entity_reference(target):
    if target.get('kind') in ('theoryItem', 'lens') and 'reference' in target:
        return target['reference']
    return target if 'packageId' in target and target.get('kind') != 'file' else None


def scope_key(ref):
    return json.dumps(['scope', ref.get('packageId'), ref.get('identitySpace'),
                       ref.get('kind'), ref.get('workGraphId')], separators=(',', ':'))


def validate_target(target, validator):
    require(isinstance(target, dict), 'TARGET')
    kind = target.get('kind')
    if kind in ('document', 'file') and 'uri' in target:
        require({'schemaVersion', 'kind', 'uri'} <= set(target) <=
                {'schemaVersion', 'kind', 'uri', 'sha256', 'version'} and
                target['schemaVersion'] == 1, 'TARGET')
        SOURCES.url_parts(target['uri'])
        require('version' not in target or text(target['version']), 'TARGET_VERSION')
    elif kind == 'file':
        require(set(target) == {'schemaVersion', 'kind', 'packageId', 'path', 'sha256'} and
                target['schemaVersion'] == 1 and text(target['packageId']) and
                isinstance(target['path'], str) and target['path'].startswith('evidence/') and
                '\\' not in target['path'] and
                not any(p in ('', '.', '..') for p in target['path'].split('/')), 'FILE_TARGET')
    elif kind in ('theoryItem', 'lens') and 'reference' in target:
        fields = {'schemaVersion', 'kind', 'reference'}
        if kind == 'theoryItem':
            fields |= {'collection', 'itemId'}
        require(set(target) == fields and target['schemaVersion'] == 1, 'TARGET')
        validator(target['reference'], allow_scope=kind == 'lens')
        if kind == 'theoryItem':
            require(target['collection'] in COLLECTIONS and text(target['itemId']) and
                    ID.fullmatch(target['itemId']), 'TARGET_ITEM')
    else:
        validator(target, allow_scope=True)
    if 'sha256' in target:
        require(isinstance(target['sha256'], str) and
                re.fullmatch('[0-9a-f]{64}', target['sha256']), 'TARGET_SHA256')


def entries(theory, collection):
    rows = copy.deepcopy(theory.get('canonItems' if collection == 'canons' else collection, []))
    if collection == 'canons':
        if text(theory.get('canons')):
            rows.insert(0, {'id': 'legacy-canons', 'title': 'Каноны · прежний текст',
                            'body': theory['canons'], 'legacy': True})
        for old in theory.get('knownErrors', []):
            rows.append({'id': 'legacy-' + digest(old['id'])[:24], 'title': old['title'],
                         'body': '\n'.join(v for v in (old['title'], old['description']) if v),
                         'legacy': True})
    return rows


def mentions(theory):
    parts = [('guidance', theory.get('guidance', ''))]
    parts += [('canons/' + x['id'], x['body']) for x in theory.get('canonItems', []) if 'body' in x]
    result = []
    for field, body in parts:
        for match in LINK.finditer(body):
            a = body.rfind('\n\n', 0, match.start())
            b = body.find('\n\n', match.end())
            result.append({'field': field, 'collection': match[2], 'itemId': match[3],
                           'label': match[1], 'start': match.start(), 'end': match.end(),
                           'excerpt': body[0 if a < 0 else a + 2:len(body) if b < 0 else b][:4096],
                           'excerptComplete': (len(body) if b < 0 else b) - (0 if a < 0 else a + 2) <= 4096})
    return result


def validate(theory, validator):
    for field in FIELDS:
        require(field not in theory or isinstance(theory[field], list) and len(theory[field]) <= 10000,
                'COLLECTION')
        seen = set()
        for item in theory.get(field, []):
            required = {'id', 'title'} | ({'targetRef'} if field == 'recommendations' else set())
            allowed = required | ({'body', 'targetRef'} if field == 'canonItems' else set())
            require(isinstance(item, dict) and required <= set(item) <= allowed and
                    isinstance(item['id'], str) and ID.fullmatch(item['id']) and
                    not item['id'].startswith('legacy-') and text(item['title']), 'ITEM')
            require(item['id'] not in seen, 'ITEM_ID_DUPLICATE')
            seen.add(item['id'])
            if field == 'canonItems':
                require(('body' in item) != ('targetRef' in item), 'CANON_CONTENT')
                if 'body' in item:
                    require(text(item['body']), 'CANON_CONTENT')
            if 'targetRef' in item:
                validate_target(item['targetRef'], validator)
    valid = {c: {r['id'] for r in entries(theory, c)} for c in COLLECTIONS}
    for body in [theory.get('guidance', ''), *(x.get('body', '') for x in theory.get('canonItems', []))]:
        for link in re.finditer(r'\[[^\]\n]*\]\(theory:[^)]*\)', body):
            require(LINK.fullmatch(link[0]) is not None, 'REFERENCE_SYNTAX')
    for item in mentions(theory):
        require(item['itemId'] in valid[item['collection']], 'REFERENCE_MISSING:' + item['itemId'])
    bindings = theory.get('referenceBindings', {})
    require(isinstance(bindings, dict) and all(text(k) and text(v) for k, v in bindings.items()), 'REF_BINDINGS')


def targets(theory):
    return [x['targetRef'] for field in FIELDS for x in theory.get(field, []) if 'targetRef' in x]


def source_kind(target):
    return {'lens': 'lens', 'file': 'file', 'document': 'document'}.get(target.get('kind'), 'rdg')


def item_ref(app, row, theory, collection, ident, theory_ref=None):
    return {'theoryRef': theory_ref or app.model.reference(row['head']['packageId'], row['graph'], theory['id']),
            'collection': collection, 'itemId': ident}


def schema():
    return {'method': 'theory_read', 'schemaVersion': 1,
            'selectors': {'packageId': 'owner', 'theoryId': 'existing canon entity ID',
                          'collection': ['overview', *COLLECTIONS],
                          'itemIds': 'optional unique IDs; omit for the complete collection'},
            'detail': ['summary', 'content'], 'expand': 'explicit one-level source content',
            'limit': {'default': 25, 'min': 1, 'max': 100},
            'cursor': 'opaque, owner/source-snapshot and query bound',
            'format': ['json', 'markdown'], 'expectedTheoryRevision': 'optional exact theory revision',
            'link': '[label](theory:canons/ID) or [label](theory:recommendations/ID)',
            'fields': {'canonItems': '{id,title,body} or {id,title,targetRef}',
                       'recommendations': '{id,title,targetRef}'},
            'targets': ['qualified entity/scope ref', 'lens wrapper + qualified ref',
                        'theoryItem + qualified theory ref/collection/itemId',
                        'HTTPS document/file URI', 'authorized package evidence file + SHA256'],
            'completeness': 'page.complete covers the complete requested list; contentComplete additionally covers all material contents (false when source expansion was not requested)',
            'legacy': 'Unchanged text is exposed as read-only legacy entries; reads never migrate.'}


def _body(node, graph=None):
    if graph is not None and node.get('kind') == 'lens':
        mapping = next((n for n in graph['objects'] if 'rdg:lens-source-map' in n.get('tags', [])), None)
        if mapping:
            source_id = json.loads(mapping['value'])['fullTextInfoId']
            source = next((n for n in graph['objects'] if n['id'] == source_id), None)
            if source:
                return source['value']
        return json.dumps(graph, ensure_ascii=False, indent=2)
    if graph is not None and node.get('kind') == 'process':
        return json.dumps(graph, ensure_ascii=False, indent=2)
    if graph is not None and 'memberIds' in node:
        members = set(node['memberIds']) | set(node.get('rootIds', []))
        return json.dumps({'scope': node, 'entities': [n for n in
            graph['nodes'] + graph['objects'] + graph.get('externalActions', []) if n['id'] in members],
            'edges': [e for e in graph['edges'] if e['from'] in members and e['to'] in members]},
            ensure_ascii=False, indent=2)
    if 'body' in node:
        return node['body']
    if node.get('kind') in ('info', 'context'):
        return node.get('value', '')
    return json.dumps(node, ensure_ascii=False, indent=2)


def resolve_target(app, row, theory, target, expand, cache, budget):
    kind = target.get('kind')
    if kind in ('document', 'file') and 'uri' in target:
        if not expand:
            return {'status': 'external', 'contentLoaded': False, 'uri': target['uri']}
        if budget['network'] <= 0 or budget['bytes'] <= 0:
            return {'status': 'budget-exceeded', 'contentLoaded': False}
        key = 'https:' + digest(target)
        if key not in cache:
            budget['network'] -= 1
            cache[key] = SOURCES.fetch_https(target, max_bytes=min(SOURCES.MAX_BYTES, budget['bytes']))
        return copy.deepcopy(cache[key])
    if kind == 'file':
        try:
            with app.store.lock(False, create=False):
                source = cache.get('package:' + target['packageId'])
                require(source is not None, 'SOURCE_UNAVAILABLE')
                app.verify_evidence(source, [{'path': target['path'], 'sha256': target['sha256']}])
                path = app.store.io.safe_path(app.store.package_path(source['path']), target['path'], True)
                result = {'status': 'available', 'sha256': target['sha256'], 'contentLoaded': False}
                if expand:
                    with path.open('rb') as f:
                        raw = f.read(min(SOURCES.MAX_BYTES, budget['bytes']) + 1)
                    if len(raw) > min(SOURCES.MAX_BYTES, budget['bytes']):
                        return {'status': 'budget-exceeded', 'contentLoaded': False}
                    result = SOURCES.text_source(raw, 'text/plain', target['sha256'])
                return result
        except (ValueError, OSError):
            return {'status': 'unavailable', 'contentLoaded': False}
    ref = entity_reference(target)
    try:
        with app.store.lock(False, create=False):
            def register(ident):
                key = 'package:' + ident
                if key not in cache:
                    cache[key] = app.snapshot(ident, layouts=False)
                require(cache[key] is not None, 'SOURCE_UNAVAILABLE')
                return cache[key]
            K = app.kernel.for_graph(row['graph'])
            local = K.QUESTIONS.reference_id(row['graph'], ref, K, theory) if 'kind' not in ref else None
            scope = theory.get('referenceBindings', {}).get(scope_key(ref)) if 'kind' in ref else None
            if scope:
                node = ({'id': row['graph']['id'], 'title': row['graph']['title'], 'kind': 'process'}
                        if scope == '@process' else next((w for w in row['graph']['workGraphs'] if w['id'] == scope), None))
                resolved = {'status': 'current' if node else 'missing', 'node': node,
                            'changed': None, 'localBinding': True}
                source = row
            elif local and (ref.get('mode') == 'inherited' or ref['packageId'] == row['head']['packageId']):
                node = K.entities(row['graph']).get(local)
                resolved = {'status': 'current' if node else 'missing', 'node': node,
                            'changed': None if node is None else node['revision'] != ref['revision'],
                            'localBinding': True}
                source = row
            else:
                resolved = app.resolve_for(ref, row, register)
                source = cache.get('package:' + ref['packageId'])
            result = {k: copy.deepcopy(v) for k, v in resolved.items() if k != 'node'}
            result['contentLoaded'] = False
            if source:
                source_graph = source['graph']
                if resolved['status'] in ('historical', 'deleted', 'historical-current-unavailable'):
                    _, history = app.reference_snapshots(ref, row, register)
                    source_graph = history[(ref['packageId'], ref['identitySpace'], ref['sha256'])]
                result['sourcePin'] = {'packageId': ref['packageId'],
                    'identitySpace': source_graph['identitySpace'], 'graphRevision': source_graph['revision'],
                    'sha256': app.model.digest(source_graph)}
                result['sourcePin']['packageId'] = source['head']['packageId']
            node = resolved.get('node')
            if kind == 'lens' and source and source['head']['role'] != 'lens':
                return {'status': 'unavailable', 'contentLoaded': False}
            if not node:
                return result
            if kind == 'theoryItem':
                if node.get('kind') != 'canon':
                    return {'status': 'missing', 'contentLoaded': False}
                node = next((x for x in entries(node, target['collection']) if x['id'] == target['itemId']), None)
                if not node:
                    return {'status': 'missing', 'contentLoaded': False}
                result['nextRead'] = {'method': 'theory_read', 'packageId': ref['packageId'],
                    'theoryId': ref['nodeId'], 'collection': target['collection'], 'itemIds': [target['itemId']]}
                if 'targetRef' in node:
                    result['targetRef'] = copy.deepcopy(node['targetRef'])
                    return result  # one level; no recursive source crawl
            result['title'] = node.get('title', '')
            if expand:
                content = _body(node, source_graph if source else None)
                size = len(content.encode())
                if size > budget['bytes']:
                    result.update(status='budget-exceeded', bytes=size)
                else:
                    result.update(content=content, contentLoaded=True, bytes=size,
                                  contentSHA256=hashlib.sha256(content.encode()).hexdigest())
            return result
    except (ValueError, OSError, KeyError):
        return {'status': 'unavailable', 'contentLoaded': False}


def _markdown(result):
    lines = ['# ' + result['theory']['title'], '', 'Общее', result.get('guidance', ''), '']
    for name, section in result['data'].items():
        lines += ['## ' + ('Каноны' if name == 'canons' else 'Рекомендации'), '']
        for item in section['items']:
            lines += ['### ' + item['title'] + ' [' + item['id'] + ']',
                      'Адрес: ' + json.dumps(item['ref'], ensure_ascii=False)]
            if 'body' in item:
                lines += [item['body']]
            if 'targetRef' in item:
                lines += ['Источник: ' + json.dumps(item['targetRef'], ensure_ascii=False)]
            resolved = item.get('resolved', {})
            if resolved.get('contentLoaded'):
                lines += [resolved['content']]
            elif resolved:
                lines += ['Состояние источника: ' + resolved['status']]
            for mention in item['mentions']:
                lines += ['Контекст (' + mention['field'] + '): ' + mention['excerpt']]
            lines += ['']
        lines += ['Полнота коллекции: ' + ('полная' if section['page']['complete'] else 'есть продолжение')]
    return '\n'.join(lines)


def read(app, row, theory_id, collection='overview', item_ids=None, detail='content',
         expand=False, limit=25, cursor=None, output_format='json', expected_revision=None):
    require(row['graph']['coreModel'] == 'rdg-decision-v1', 'PROFILE')
    require(text(theory_id), 'NOT_FOUND')
    require(cursor is None or isinstance(cursor, str) and 0 < len(cursor) <= 2 * MAX_PAGE_BYTES, 'CURSOR_INVALID')
    theory = app.kernel.entities(row['graph']).get(theory_id)
    require(theory is not None and theory['kind'] == 'canon', 'NOT_FOUND')
    require(collection in ('overview', *COLLECTIONS) and detail in ('summary', 'content'), 'READ_OPTIONS')
    require(type(expand) is bool and type(limit) is int and 1 <= limit <= 100 and
            output_format in ('json', 'markdown'), 'READ_OPTIONS')
    require(expected_revision is None or type(expected_revision) is int and expected_revision == theory['revision'], 'REVISION_CHANGED')
    require(item_ids is None or isinstance(item_ids, list) and bool(item_ids) and
            all(isinstance(x, str) and ID.fullmatch(x) for x in item_ids) and
            len(set(item_ids)) == len(item_ids), 'ITEM_IDS')
    require(collection != 'overview' or item_ids is None and cursor is None and not expand, 'OVERVIEW_OPTIONS')
    require(not expand or detail == 'content', 'EXPAND_REQUIRES_CONTENT')
    snapshot = {'packageRevision': row['head']['revision'], 'graphRevision': row['graph']['revision'],
                'graphSHA256': app.model.digest(row['graph']), 'theoryRevision': theory['revision']}
    cache = {'package:' + row['head']['packageId']: row}
    # Capture every internal source under one read lock. The cursor also binds
    # source changes, not just edits to the owner of the theory.
    pins = {}
    if collection != 'overview':
        with app.store.lock(False, create=False):
            for entry in entries(theory, collection):
                if item_ids is not None and entry['id'] not in item_ids:
                    continue
                target = entry.get('targetRef', {})
                ref = entity_reference(target)
                pid = (ref or target).get('packageId')
                if not pid or pid in pins:
                    continue
                try:
                    source = cache.get('package:' + pid) or app.snapshot(pid, layouts=False)
                    cache['package:' + pid] = source
                    pins[pid] = app.model.digest(source['graph'])
                except (ValueError, OSError):
                    cache['package:' + pid] = None
                    pins[pid] = 'unavailable'
    source_snapshot = digest(pins)
    query = {'theoryId': theory_id, 'collection': collection, 'itemIds': item_ids,
             'detail': detail, 'expand': expand, 'format': output_format}
    offset = 0
    if cursor is not None:
        try:
            token = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        except (ValueError, TypeError, UnicodeError):
            raise ValueError('THEORY_CURSOR_INVALID') from None
        require(isinstance(token, dict) and set(token) == {'snapshot', 'sources', 'query', 'offset'}, 'CURSOR_INVALID')
        require(token['snapshot'] == snapshot and token['sources'] == source_snapshot, 'CURSOR_STALE')
        require(token['query'] == query and type(token['offset']) is int and token['offset'] >= 0, 'CURSOR_INVALID')
        offset = token['offset']
    result = {'schemaVersion': 1, 'readOnly': True, 'snapshot': snapshot, 'sourceSnapshot': source_snapshot,
              'theory': {'id': theory_id, 'title': theory['title'], 'revision': theory['revision'],
                         'ref': app.model.reference(row['head']['packageId'], row['graph'], theory_id)},
              'collection': collection, 'detail': 'summary' if collection == 'overview' else detail,
              'loaded': {'guidance': collection == 'overview', 'sourceContents': expand},
              'data': {}}
    if collection == 'overview':
        if len(theory['guidance'].encode()) <= MAX_PAGE_BYTES // 2:
            result['guidance'] = theory['guidance']
        else:
            result['loaded']['guidance'] = False
            result['guidanceStatus'] = 'budget-exceeded'
    all_mentions = mentions(theory)
    budget = {'bytes': MAX_PAGE_BYTES - len(json.dumps(result, ensure_ascii=False).encode()) - 4096, 'network': 8}
    for name in COLLECTIONS if collection == 'overview' else (collection,):
        rows = entries(theory, name)
        if item_ids is not None:
            require(set(item_ids) <= {x['id'] for x in rows}, 'ITEM_NOT_FOUND')
            rows = [x for x in rows if x['id'] in item_ids]
        selected, used = [], 0
        for entry in rows[offset:offset + limit]:
            if (expand and selected and budget['network'] <= 0 and
                    entry.get('targetRef', {}).get('uri') and
                    'https:' + digest(entry['targetRef']) not in cache):
                break
            value = {k: copy.deepcopy(v) for k, v in entry.items() if k != 'body'}
            value['ref'] = item_ref(app, row, theory, name, entry['id'], result['theory']['ref'])
            value['mentions'] = [x for x in all_mentions if x['collection'] == name and x['itemId'] == entry['id']]
            if collection == 'overview' or detail == 'summary':
                value['mentions'] = [{k: v for k, v in x.items() if k not in ('excerpt', 'excerptComplete')}
                                     for x in value['mentions']]
            value['contentLoaded'] = False
            if collection != 'overview' and detail == 'content' and 'body' in entry:
                value.update(body=entry['body'], contentLoaded=True)
            if 'targetRef' in entry:
                value['sourceKind'] = source_kind(entry['targetRef'])
                if collection != 'overview':
                    value['resolved'] = resolve_target(app, row, theory, entry['targetRef'], expand, cache, budget)
                    value['contentLoaded'] = value['resolved']['contentLoaded']
            size = len(json.dumps(value, ensure_ascii=False).encode())
            if size > budget['bytes']:
                if selected:
                    break
                # Keep its exact address; an oversized body is never silently truncated.
                value.pop('body', None)
                value.pop('resolved', None)
                value.update(contentLoaded=False, contentStatus='budget-exceeded', contentBytes=size)
                size = len(json.dumps(value, ensure_ascii=False).encode())
            require(size <= budget['bytes'], 'PAGE_BUDGET')
            selected.append(value)
            budget['bytes'] -= size
            used += 1
        end = offset + used
        more = end < len(rows)
        next_cursor = None
        if more and collection != 'overview':
            payload = {'snapshot': snapshot, 'sources': source_snapshot, 'query': query, 'offset': end}
            next_cursor = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).decode()
        result['data'][name] = {'items': selected, 'page': {'total': len(rows), 'returned': used,
                    'limit': limit, 'complete': not more, 'hasMore': more, 'nextCursor': next_cursor},
                    'contentComplete': collection != 'overview' and detail == 'content' and
                        not more and all(x['contentLoaded'] for x in selected)}
    if output_format == 'markdown':
        result['markdown'] = _markdown(result)
    return result


def read_pages(client, message, all_pages=False):
    """Agent/UI helper: collect one immutable collection, preserving source states."""
    result = client.call(message)
    if not all_pages or message.get('collection', 'overview') == 'overview':
        return result
    name = message['collection']
    pages = 1
    section = result['data'][name]
    while section['page']['nextCursor']:
        part = client.call({**message, 'cursor': section['page']['nextCursor']})
        require(part['snapshot'] == result['snapshot'], 'CURSOR_STALE')
        require(part['sourceSnapshot'] == result['sourceSnapshot'], 'CURSOR_STALE')
        next_section = part['data'][name]
        section['items'].extend(next_section['items'])
        section['page'] = next_section['page']
        pages += 1
        require(pages <= 10000, 'PAGE_LIMIT')
    section['page']['returned'] = len(section['items'])
    section['contentComplete'] = result['detail'] == 'content' and all(x['contentLoaded'] for x in section['items'])
    result['reading'] = {'complete': section['page']['complete'], 'pages': pages, 'snapshot': result['snapshot']}
    if message.get('format') == 'markdown':
        result['markdown'] = _markdown(result)
    return result
