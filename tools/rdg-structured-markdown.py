#!/usr/bin/env python3
"""One ordered document for RDG Markdown and the Viewer."""
import base64
from collections import defaultdict
import hashlib
import json
import re
from urllib.parse import quote


PAGE_BYTES = 4 * 1024 * 1024
CORE_KINDS = frozenset(('requirement', 'decision', 'action'))
LABELS = {
    'kind': 'Тип', 'id': 'ID', 'revision': 'Ревизия', 'selectionState': 'Выбор',
    'result': 'Результат', 'review': 'Актуальность', 'resultCondition': 'Условия результата',
    'estimates': 'Оценки исполнения', 'subjectRefs': 'Предметы работы', 'value': 'Содержание',
    'guidance': 'Общее', 'canonItems': 'Каноны по ID', 'canons': 'Каноны', 'knownErrors': 'Известные ошибки',
    'findingType': 'Тип файндинга', 'rationale': 'Обоснование', 'answers': 'Ответы',
    'answerCondition': 'Условие достаточности', 'assessment': 'Оценка достаточности',
    'context': 'Контекст принятия решения', 'canon': 'Теория принятия решения',
    'findings': 'Файндинги', 'questions': 'Вопросы', 'recommendations': 'Рекомендации',
    'dependencyApplications': 'Зависимости и влияния', 'completion': 'Завершённость',
    'subjects': 'Предметные ссылки', 'edges': 'Связи', 'decisionMemberships': 'Участие в группах',
    'decisionGroups': 'Группы решений', 'workGraphs': 'Рабочие области',
    'contextGroups': 'Банк контекстов', 'rootCauses': 'Корневые основания',
    'dependencyPolicies': 'Политики зависимостей', 'dependencyPolicyAliases': 'Ссылки на политики',
    'externalRefs': 'Внешние ссылки', 'plan': 'Plan', 'parents': 'Родители и границы',
}


def schema():
    return {'detail': ['full', 'focus', 'branch'], 'defaultDetail': 'full',
            'fullViewKinds': ['graph', 'workGraph', 'focus'], 'profile': 'rdg-decision-v1',
            'pageBudgetBytes': PAGE_BYTES, 'content': 'markdown',
            'cursor': 'opaque, scope/snapshot/format-bound',
            'blocks': 'line ranges for the Viewer; zero-based, end-exclusive'}


def inline(value):
    text = ' '.join(str(value).splitlines())
    return re.sub(r'([\\*_\[\]<>|#])', r'\\\1', text)


def fields(value, level=0):
    indent = '  ' * level
    if isinstance(value, dict):
        if value.get('kind')=='canon':
            value=dict(value);legacy=value.pop('knownErrors',[])
            if legacy:value['canons']='\n\n'.join(v for v in [value.get('canons','')]+['\n'.join(v for v in (e['title'],e['description']) if v) for e in legacy] if v)
        for key, child in sorted(value.items()):
            label = inline(LABELS.get(key, key))
            if isinstance(child, (dict, list)) and child:
                yield f'{indent}- **{label}**'
                yield from fields(child, level+1)
            elif isinstance(child, str) and '\n' in child:
                yield f'{indent}- **{label}**'
                yield from (indent + '  > ' + line for line in child.split('\n'))
            else:
                yield f'{indent}- **{label}** — {scalar(child)}'
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)) and child:
                yield f'{indent}-'
                yield from fields(child, level+1)
            elif isinstance(child, str) and '\n' in child:
                yield f'{indent}-'
                yield from (indent + '  > ' + line for line in child.split('\n'))
            else:
                yield f'{indent}- {scalar(child)}'


def scalar(value):
    if value is None:
        return 'не задано'
    if type(value) is bool:
        return 'да' if value else 'нет'
    if isinstance(value, (list, dict)):
        return 'пусто'
    return inline(value)


def node_id(ref):
    return (ref or {}).get('nodeId')


class Document:
    def __init__(self, graph, data, occurrences, package_id, recommendations_available):
        self.graph = graph
        self.data = data
        self.occurrences = occurrences
        self.package_id = package_id
        self.recommendations_available = recommendations_available
        self.records = {r['entity']['id']: r for r in data.get('entities', [])}
        self.nodes = {n['id']: n for n in graph['nodes'] + graph['objects'] + graph.get('externalActions', [])}
        self.primary = {r['entityId'] for r in occurrences if not r.get('parentRef')}
        self.emitted = set()
        self.emitted_relations = set()
        self.blocks = []
        self.by_subject = defaultdict(lambda: defaultdict(list))
        self.materials = defaultdict(list)
        self.completion = {r['nodeId']: r['state'] for r in data.get('completion', [])}
        for facet in ('context', 'canon', 'findings', 'questions', 'recommendations',
                      'dependencyApplications', 'completion', 'subjects', 'edges',
                      'decisionMemberships', 'decisionGroups'):
            for record in data.get(facet, []):
                ids, sources = self.participants(facet, record)
                for ident in dict.fromkeys(ids):
                    if ident is None:
                        continue
                    self.by_subject[ident][facet].append(record)
                    self.materials[ident].extend(i for i in sources if i and i != ident)

    @staticmethod
    def participants(facet, row):
        sources = []
        if facet in ('context', 'canon'):
            ids = [node_id(row.get('subjectRef'))]
            sources = [(row.get('source') or {}).get('nodeId')]
            sources.extend(i['source']['nodeId'] for i in row.get('info', []))
        elif facet == 'findings':
            ids, sources = [row['subject']['nodeId']], [row['findingId']]
        elif facet == 'questions':
            ids = ([node_id(row.get('ownerRef'))] if row.get('legacy') else
                   [node_id(ref) for ref in row.get('relatedTo', [])])
            sources = [(row.get('source') or {}).get('nodeId')]
        elif facet == 'dependencyApplications':
            ids = [row.get('targetId'), row.get('localId'), *row.get('nodeIds', [])]
        elif facet in ('edges', 'decisionMemberships'):
            ids = [row['from'], row['to']]
        elif facet == 'decisionGroups':
            ids = [row['parentId'], *(m['decisionId'] for m in row['members'])]
        else:
            ids = [row.get('nodeId') or row.get('actionId')]
        return ids, sources

    def anchor(self, ident):
        key = self.graph['identitySpace'] + ':' + ident
        return 'rdg-' + hashlib.sha256(key.encode()).hexdigest()[:24]

    def link(self, ident):
        title = inline(self.nodes.get(ident, {}).get('title', ident))
        if ident in self.nodes:
            address = f'rdg:{self.package_id}/{quote(ident, safe="")}'
            if ident in self.records:
                return f'[{title}](#{self.anchor(ident)} "{address}")'
            return f'[{title}]({address})'
        return title

    def append(self, lead, details=(), **meta):
        self.blocks.append((list(lead), list(details), meta))

    def entity_fields(self, entity):
        return list(fields({k: v for k, v in entity.items() if k not in ('title', 'description')}))

    def related(self, ident):
        for facet, rows in self.by_subject[ident].items():
            yield ''
            yield f'**{LABELS[facet]}**'
            for row in rows:
                if facet in ('edges', 'decisionMemberships'):
                    yield f"- {inline(row['type'])} · {self.link(row['from'])} → {self.link(row['to'])}"
                if facet in ('context', 'canon', 'findings', 'questions'):
                    src = (row.get('source') or {}).get('nodeId')
                    if src in self.records:
                        yield '- ' + self.link(src)
                # Material records may participate on both sides of several
                # nodes. Keep their full values at the first occurrence.
                key = (facet, hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest())
                anchor = self.anchor('relation:' + ':'.join(key))
                if key in self.emitted_relations:
                    yield f'- [Сведения об отношении](#{anchor})'
                    continue
                self.emitted_relations.add(key)
                yield f'<a id="{anchor}"></a>'
                yield from fields([row])

    def attach_materials(self, ident):
        pending = list(reversed(self.materials[ident]))
        while pending:
            target = pending.pop()
            if target in self.emitted or target in self.primary or target not in self.records:
                continue
            self.emitted.add(target)
            n = self.records[target]['entity']
            yield ''
            yield f'<a id="{self.anchor(target)}"></a>'
            yield f'###### {inline(n["title"])}'
            yield from self.description(n)
            yield from self.entity_fields(n)
            yield from self.related(target)
            pending.extend(reversed(self.materials[target]))

    @staticmethod
    def description(entity):
        value = entity.get('description')
        if value:
            yield ''
            yield from ('> ' + line for line in value.split('\n'))

    def entity(self, ident, depth=0, occurrence=None):
        occurrence = occurrence or {}
        if ident not in self.records or ident in self.emitted:
            reasons = 'цикл' if occurrence.get('cycle') else 'общее вхождение' if ident in self.emitted else 'тело вне выдачи'
            relation = occurrence.get('relation')
            prefix = f'{inline(relation)} · ' if relation and relation != 'root' else ''
            parent = occurrence.get('parentId')
            context = f' · родитель {self.link(parent)}' if parent else ''
            self.append([f'↳ {prefix}{self.link(ident)} · {reasons}{context}', ''], depth=depth)
            return
        self.emitted.add(ident)
        n = self.records[ident]['entity']
        anchor = self.anchor(ident)
        lead = [f'<a id="{anchor}"></a>', f'{"#" * min(depth+2, 4)} {inline(n["title"])}', '']
        state = []
        if n.get('selectionState'):
            state.append('выбор — ' + inline(n['selectionState']))
        if n.get('result', {}).get('state'):
            state.append('результат — ' + inline(n['result']['state']))
        if n.get('review', {}).get('required') or self.completion.get(ident, {}).get('reviewRequired'):
            causes = [r for r in self.by_subject[ident].get('dependencyApplications', [])
                      if r.get('targetId', r.get('localId')) == ident]
            reason = next((r.get('reasonCode') for r in causes if r.get('reasonCode')), None)
            state.append('требуется пересмотр' + (' — ' + inline(reason) if reason else ''))
        if state:
            lead.extend((' · '.join(state), ''))
        relation, parent = occurrence.get('relation'), occurrence.get('parentId')
        if relation and relation != 'root' and parent:
            lead.extend((f'{inline(relation)} · родитель {self.link(parent)}', ''))
        for g in occurrence.get('groupMemberships', []):
            required = 'выбор обязателен' if g['selectionRequired'] else 'выбор необязателен'
            exclusive = 'взаимоисключение' if g['mutuallyExclusive'] else 'совместный выбор'
            lead.append(f'Группа {inline(g["title"])} · {required} · {exclusive}')
        for parent_id in occurrence.get('outsideParentIds', []):
            lead.append('Внешний родитель · ' + self.link(parent_id))
        lead.extend(self.description(n))
        details = [*self.entity_fields(n), *self.related(ident), *self.attach_materials(ident)]
        self.append(lead, details, depth=depth, entityId=ident, anchor=anchor,
                    title=n['title'], kind=n['kind'], ref=self.records[ident]['ref'])

    def build(self, scope, snapshot, extras, requested):
        name = {'graph':'весь граф', 'focus':'фокус', 'workGraph':'рабочая область', 'branch':'ветвь'}[scope['kind']]
        self.append(['# ' + inline(self.graph['title']), '',
                     f'Область — {name} · ревизия Graph — {snapshot["graphRevision"]}', ''])
        if scope.get('nodeId') in self.records and scope['nodeId'] not in self.primary:
            self.primary.add(scope['nodeId'])
        parents = self.data.get('parents', [])
        if parents:
            lead = ['## Родители', '']
            lead.extend('- ' + self.link(p['nodeId']) + ' · ' + inline(p['via']['type']) for p in parents)
            self.append(lead, list(fields(parents)))
        for row in self.occurrences:
            ident = row['entityId']
            if row.get('parentRef'):
                if not parents:
                    self.append(['Родитель · ' + self.link(ident), ''], list(fields(row.get('parentRelations', []))))
                continue
            self.entity(ident, row['entityDepth'], row)
        service_actions = []
        for ident, record in self.records.items():
            if ident not in self.emitted:
                if record['entity'].get('lowLevel'):
                    service_actions.append(record['entity'])
                    self.emitted.add(ident)
                else:
                    self.entity(ident)
        if service_actions:
            for action in service_actions:
                self.append(['Служебное действие · ' + inline(action['title'])],
                            [f'<a id="{self.anchor(action["id"])}"></a>', *self.description(action),
                             *self.entity_fields(action), *self.related(action['id'])])
        for name, rows in extras.items():
            if rows:
                self.append(['## ' + LABELS[name], ''], list(fields(rows)))
        # Explicitly requested records without a participating body remain
        # readable, including projections requested without the entities facet.
        for facet, rows in self.data.items():
            if facet in ('entities', 'outline', 'parents'):
                continue
            detached = [row for row in rows if facet == 'plan' or
                        not (set(self.participants(facet, row)[0]) & self.emitted)]
            if detached:
                self.append(['## ' + LABELS[facet], ''], list(fields(detached)))
        if self.recommendations_available is False:
            self.append(['Рекомендации · недоступны в текущей области доступа.', ''])
        self.append(['## Область выдачи', ''], list(fields({
            'Секции': requested,
            'Пустые секции': [LABELS.get(f, f) for f, rows in self.data.items() if not rows
                              and (f != 'recommendations' or self.recommendations_available is not False)],
            'History': 'доступна отдельным чтением',
            'Plan': 'вне запроса' if 'plan' not in self.data else 'включён в область',
        })))
        return self.blocks


def page(app, blocks, scope, snapshot, cursor):
    pin = app.model.digest({'scope': scope, 'snapshot': snapshot, 'blocks': blocks})
    offset = 0
    if cursor is not None:
        app.check(isinstance(cursor, str) and len(cursor) <= 4096, 'MARKDOWN_CURSOR')
        try:
            value = json.loads(base64.urlsafe_b64decode(cursor.encode('ascii')))
        except (ValueError, UnicodeError) as exc:
            raise ValueError('PORTABLE_APP_MARKDOWN_CURSOR') from exc
        app.check(isinstance(value, list) and len(value) == 2 and type(value[1]) is int and value[1] > 0,
                  'MARKDOWN_CURSOR')
        app.check(value[0] == pin, 'MARKDOWN_CURSOR_STALE')
        offset = value[1]
        app.check(offset < len(blocks), 'MARKDOWN_CURSOR')
    lines, index = [], []
    budget = len(json.dumps(snapshot, ensure_ascii=False).encode()) + 2048
    for lead, details, meta in blocks[offset:]:
        text = lead + (['', '### Сведения', '', *details] if details else []) + ['']
        cost = len(json.dumps([text, meta], ensure_ascii=False).encode()) + 160
        if budget + cost > PAGE_BYTES:
            app.check(bool(index), 'MARKDOWN_BLOCK_TOO_LARGE:' + str(meta.get('entityId', 'document'))
                      + ':' + str(cost))
            break
        index.append({**meta, 'start': len(lines), 'leadEnd': len(lines) + len(lead),
                      'detailsStart': len(lines) + len(lead) + (3 if details else 0),
                      'end': len(lines) + len(text), 'hasDetails': bool(details)})
        lines.extend(text)
        budget += cost
    end = offset + len(index)
    nxt = (base64.urlsafe_b64encode(json.dumps([pin, end]).encode()).decode('ascii')
           if end < len(blocks) else None)
    complete = offset == 0 and nxt is None
    notice = [] if complete else ['> Частичная выдача Markdown. Область и версия закреплены в snapshot.', '']
    for block in index:
        for key in ('start', 'leadEnd', 'detailsStart', 'end'):
            block[key] += len(notice)
    return {'schemaVersion': 1, 'format': 'markdown', 'scope': scope, 'snapshot': snapshot,
            'markdown': '\n'.join(notice + lines) + '\n', 'blocks': index,
            'reading': {'pagesComplete': complete, 'contentStartLine': len(notice)},
            'page': {'hasMore': nxt is not None, 'nextCursor': nxt}}


def read(app, ident, *, detail, view, node_id, include, include_plan, cursor, compact, scoped):
    detail = 'full' if detail is None else detail
    app.check(detail in ('full', 'focus', 'branch') and type(include_plan) is bool, 'MARKDOWN_DETAIL')
    app.check((node_id is None if detail == 'full' else isinstance(node_id, str) and bool(node_id))
              and (detail == 'full' or view is None and not include_plan), 'MARKDOWN_SCOPE')
    app.check(include is None or isinstance(include, list) and
              all(isinstance(f, str) and f in scoped.FACETS for f in include) and
              len(include) == len(set(include)), 'MARKDOWN_INCLUDE')
    requested = list(include or scoped.DEFAULTS)
    if include_plan and 'plan' not in requested:
        requested.append('plan')
    with app.store.lock(False, create=False):
        row = app.snapshot(ident, 'plan' in requested, layouts=False, scoped_read=True)
        graph = row['graph']
        app.check(graph.get('coreModel') == 'rdg-decision-v1', 'MARKDOWN_PROFILE_UNSUPPORTED')
        kernel = app.kernel.for_graph(graph)
        if view is None:
            view = {'kind': 'focus', 'id': node_id} if detail == 'focus' else {'kind': 'graph'}
        kind = view.get('kind') if isinstance(view, dict) else None
        app.check(kind in ('graph', 'workGraph', 'focus'), 'MARKDOWN_SCOPE')
        effective = 'focus' if kind == 'focus' else detail
        root = view.get('id') if kind == 'focus' else node_id
        with kernel.ANALYSIS.read_scope(graph):
            presentation = app.model.presentation(graph, app.kernel, view) if detail != 'branch' else None
            projected = scoped.project(app, ident, row, effective, requested, root, 25, None,
                                       compact, document=True, document_view=presentation)
            data = projected['data']
            if detail == 'branch':
                ids = {r['nodeId'] for r in data.get('outline', [])}
                presentation = {'spec': {'kind': 'graph'},
                                'entities': [n for n in kernel.entities(graph).values() if n['id'] in ids],
                                'edges': [e for e in kernel.active_edges(graph)
                                          if e['from'] in ids and e['to'] in ids],
                                'decisionGroups': [{**g, 'members': [m for m in g['members'] if m['decisionId'] in ids]}
                                                   for g in graph['decisionGroups'] if g['parentId'] in ids]}
            outline = (app.layout('outline', graph=graph, view=presentation,
                                  options={'hideProcessContexts': row['head']['role'] in ('working','copy'),
                                           'documentRootId': root})['rows']
                       if 'outline' in requested else [])
            scope = {'kind': effective if detail != 'full' or kind == 'focus' else kind,
                     'packageId': ident, 'nodeId': root, 'view': view, 'sections': requested, 'role': row['head']['role']}
            extras = ({k: graph[k] for k in ('workGraphs','contextGroups','rootCauses','dependencyPolicies',
                                            'dependencyPolicyAliases','externalRefs') if graph.get(k)}
                      if detail == 'full' and kind == 'graph' and not view.get('groupIds') and not include else {})
            if kind == 'workGraph':
                extras['workGraphs'] = [w for w in graph['workGraphs'] if w['id'] == view['id']]
            document = Document(graph, data, outline, ident, projected['recommendationAvailable'])
            blocks = document.build(scope, projected['snapshot'], extras, requested)
            return page(app, blocks, scope, projected['snapshot'], cursor)


def read_pages(client, message, all_pages=False):
    result = client.call(message)
    if not all_pages:
        return result
    if message.get('cursor') is not None:
        raise ValueError('MARKDOWN_ALL_PAGES_REQUIRES_FIRST_PAGE')
    cursor = result['page']['nextCursor']
    if cursor is None:
        return result
    pieces, seen = [], set()
    part = result
    while True:
        pieces.append(''.join(part['markdown'].splitlines(keepends=True)[part['reading']['contentStartLine']:]))
        cursor = part['page']['nextCursor']
        if cursor is None:
            break
        if cursor in seen:
            raise ValueError('MARKDOWN_CURSOR_REPEATED')
        seen.add(cursor)
        part = client.call({**message, 'cursor': cursor})
        if part['snapshot'] != result['snapshot'] or part['scope'] != result['scope']:
            raise ValueError('MARKDOWN_CURSOR_STALE')
    return {**result, 'markdown': ''.join(pieces), 'blocks': [],
            'reading': {'pagesComplete': True, 'contentStartLine': 0, 'pageRequests': len(seen)+1},
            'page': {'hasMore': False, 'nextCursor': None}}
