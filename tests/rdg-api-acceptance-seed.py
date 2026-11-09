#!/usr/bin/env python3
"""Opt-in API acceptance fixture. Creates one new test process through the gateway.

No owner files or credentials are read. The state journal retains exact requests
before submission so an interrupted run resumes without allocating new intents.
This seeds the test plan; it does not execute or complete its acceptance tasks.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TITLE = 'RDG — сквозная проверка API'
PROCESS_PATH = 'api-tests/rdg-acceptance-20261029'
AREAS = [
    ('WG1', 'R2', 'API и модель', -1080),
    ('WG2', 'R3', 'Viewer и Plan', -360),
    ('WG3', 'R4', 'Пакеты и линзы', 360),
    ('WG4', 'R5', 'Надёжность', 1080),
]
# Stage ID, title, owning Requirements. Repeated IDs are intentional overlap.
TASKS = [
    ('A0', 'Доступ через private gateway', ['R5'],
     'Проверить доступ из Repo Docker, отказ постороннему контейнеру и machine API через browser ingress. Клиент не содержит bearer. Сверить реальный вывод launcher и API doctor.'),
    ('A1', 'Общий writer: preflight, apply, receipt, retry', ['R2'],
     'Сравнить наблюдаемые Graph/Plan/catalog до и после preflight. Apply публикует один результат, exact retry не меняет его; receipt и actor assistant читаются обратно.'),
    ('A2', 'Модель R / Decision / Action и objects', ['R2'],
     'Проверить add/edit/link/unlink, canon/context/info/evidence, Graph и external Actions. Проверить отказ неверным kinds и связям. Создание процесса не создаёт неявную рабочую область.'),
    ('A3', 'Группы, выбор, отказ и причины актуальности', ['R2'],
     'Проверить exclusive и пересекающиеся Decision Groups, select/withdraw и root_cause. Общее основание сохраняет актуальность; снятие последнего основания сохраняет историю.'),
    ('A4', 'Evidence, complete / reopen / review, History', ['R2'],
     'Прикрепить реальные bytes evidence, проверить pins, blockers, complete/reopen и stale/review. История должна ссылаться на прежние версии. Нельзя завершать проверку лишь по факту создания графа.'),
    ('A5', 'Пересекающиеся рабочие области', ['R2', 'R3'],
     'Рабочие области содержат ссылки на одни и те же IDs. Добавление в полный Process не включает блок в первую WG. Изменение общего блока видно в обеих областях.'),
    ('A6', 'Фокус, camera, view session и CAS', ['R3'],
     'Создать собственную view session, проверить focus/camera/shown cases и отказ устаревшей revision. Graph/Plan не меняются. Чужая browser session остаётся actor-owned.'),
    ('A7', 'Plan без дат: порядок и placements', ['R3'],
     'Проверить plan_create, place/unplace, несколько placements одного блока и порядок. Пустая дата означает порядок без выдуманного срока.'),
    ('A8', 'Plan: время, ветви и historical pins', ['R3'],
     'Проверить timeConstraints, forks/cases, shownCases и source_snapshot. Изменение вида не меняет факты, события сохраняют исходный Plan/placement pin.'),
    ('A9', 'Layout: позиции, projector и readback', ['R3'],
     'Записать позиции через layout_edit с CAS; прочитать из новой сессии. Отдельно вручную проверить изображения, клики, routes, reload и restart.'),
    ('A10', 'Собственные пакеты рекомендаций', ['R4'],
     'Проверить recommendation_catalog/edit/attach, revision и instance pins. CRUD только собственных definitions; supplied definitions не менять.'),
    ('A11', 'Фундаментальная линза и pins применения', ['R4'],
     'Прочитать совместимую линзу, выполнить её инструкцию для выбранной цели и записать lens_apply с действительными evidence/version pins. Открытие линзы не является применением.'),
    ('A12', 'Copy, готовые графы и независимые instances', ['R4'],
     'Сравнить stateful copy и capture_ready/apply_ready; проверить ADD_ROOT/REPLACE_R, remap IDs/refs, provenance, Plan/layout. Использовать только тестовые owners.'),
    ('A13', 'External refs и coordinated cleanup', ['R2', 'R4'],
     'Проверить qualified refs, resolve/external_edit, unlink/delete и согласованное удаление текущих Plan/layout refs. Исторические ссылки сохраняются.'),
    ('A14', 'Каталог: папки и перенос', ['R4'],
     'Проверить folder_create/folder_move/move с сохранением identity и Plan. Миграция — только специально подготовленных synthetic legacy owners и отдельный opt-in.'),
    ('A15', 'Зависимости, guards и права', ['R5'],
     'Проверить L1/L2 dependencies, scope и запрет actor spoofing. Native human approval сейчас не настроен: VERIFIED_APPROVAL_REQUIRED — ожидаемый отказ. Не расширять реальные grants.'),
    ('A16', 'CAS, recovery, неопределённый ответ, restart', ['R5'],
     'Проверить receipt/exact retry прежней transactionId и readback. Crash injection и отзыв credentials — только в изолированной test server копии; живой сервер агент не прерывает.'),
    ('A17', 'Ручной Viewer и restart на Fortis_M', ['R3', 'R5'],
     'Пользователь проверяет тот же Process, WG, Graph, Plan, drag/layout, reload. После перезапуска сервером прочитать те же owners. Backend PASS не подтверждает UX или Stage 4.'),
]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


class Seed:
    def __init__(self, context_path, state_path):
        context = json.loads(context_path.read_text(encoding='utf8'))
        require(context.get('profile') == 'gateway', 'Gateway context required')
        spec = importlib.util.spec_from_file_location('rdg_remote_fixture', ROOT / 'tools/rdg-remote-client.py')
        remote = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(remote)
        self.client = remote.Client(context)
        require(self.client.token is None, 'Fixture must not load a credential')
        self.path = state_path
        require(self.path.is_absolute() and self.path.parent.is_dir(), 'Existing absolute state directory required')
        require(not any(p.is_symlink() for p in (self.path, *self.path.parents)), 'Symlink state path denied')
        self.lock = open(str(self.path) + '.lock', 'a')
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {
            'kind': 'rdg-api-acceptance-seed-v1', 'namespaceId': context['namespaceId'],
            'path': PROCESS_PATH, 'operations': {}, 'checks': {},
        }
        require(self.state['kind'] == 'rdg-api-acceptance-seed-v1' and
                self.state['namespaceId'] == context['namespaceId'] and self.state['path'] == PROCESS_PATH,
                'Foreign state journal denied')
        self.pid = self.state.get('packageId')

    def save(self):
        fd, temp = tempfile.mkstemp(prefix='.rdg-api-seed-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf8') as out:
                json.dump(self.state, out, ensure_ascii=False, indent=2)
                out.write('\n'); out.flush(); os.fsync(out.fileno())
            os.replace(temp, self.path)
            parent = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def call(self, **message):
        return self.client.call(message)

    def read(self, view=None):
        message = {'method': 'read', 'packageId': self.pid, 'includePlan': True}
        if view is not None:
            message['view'] = view
        return self.client.call(message)

    def observed(self):
        value = {'catalog': self.client.catalog()}
        if self.pid:
            row = self.read()
            value['owners'] = {k: row.get(k) for k in ('package', 'graph', 'plan', 'layouts')}
        return digest(value)

    def operation(self, label, op, *, node=None, command=None, values=None, data=None):
        intent = {'op': op, 'node': node, 'command': command, 'values': values, 'data': data}
        record = self.state['operations'].get(label)
        if record is None:
            schema = {'method': 'schema', 'op': op}
            if self.pid:
                schema['packageId'] = self.pid
            if node:
                schema['nodeId'] = node
            if command:
                schema['command'] = command
            request = self.client.call(schema)['request']
            request.update(values or {})
            if data is not None:
                # Explicit fixture data: never inherit a schema's suggested WG or relation.
                request['data'] = data
            elif command == 'review':
                request['data']['basis'] = 'Сверены IDs, состав и связи созданного сценария A0–A17; это проверка структуры, не выполнение тестов.'
            if op != 'create':
                if 'note' in request:
                    request['note'] = 'API acceptance fixture: ' + label
                require(request.get('targetPackageId') == self.pid, 'Only this new test owner may be written')
            record = {'intent': intent, 'request': request}
            self.state['operations'][label] = record; self.save()
        require(record['intent'] == intent, 'Changed intent: use the original fixture version')
        if 'result' not in record:
            if 'inputBinding' not in record:
                before = self.observed()
                preview = self.call(method='preflight', request=record['request'])
                after = self.observed()
                require(before == after, 'Preflight changed observed owners or catalog')
                record.update(inputBinding=preview['inputBinding'], preflightObservedSHA256=before)
                self.save()
            result = self.call(method='apply', request=record['request'],
                               expectedInputBinding=record['inputBinding'])
            require(result.get('published'), 'Apply did not publish')
            record['result'] = result; self.save()
        result = record['result']
        if not self.pid:
            self.pid = result['packages'][0]['packageId']
            self.state['packageId'] = self.pid; self.save()
        if 'receipt' not in record:
            receipt = self.call(method='receipt', packageId=self.pid,
                                transactionId=record['request']['transactionId'])
            require(receipt.get('found') and receipt.get('published'), 'Published receipt required')
            record['receipt'] = receipt; self.save()
        print(json.dumps({'operation': label, 'transactionId': record['request']['transactionId'],
                          'published': True, 'receiptFound': True}, ensure_ascii=False), flush=True)
        return result

    def core(self, label, command, data=None, node=None):
        return self.operation(label, 'core', command=command, data=data, node=node)

    def run(self):
        self.operation('create-process', 'create', values={
            'path': PROCESS_PATH, 'role': 'working', 'title': TITLE,
            'scope': 'Отдельные тестовые owners. План приёмки A0–A17; существующие процессы, supplied packages и grants не изменять.',
            'coreModel': 'rdg-decision-v1',
            'rootReason': 'Проверить реализованные функции RDG общим API и вручную в Viewer, сохраняя реальные доказательства и ограничения.',
        })
        if 'emptyProcess' not in self.state['checks']:
            row = self.read()
            require(row['graph']['workGraphs'] == [] and row['plan'] is None, 'New process must not create an implicit WG or Plan')
            self.state['checks']['emptyProcess'] = True; self.save()
        for ident, title, description in [
            ('D1', 'Вести проверку в отдельном тестовом процессе', 'План A0–A17 хранится в Graph/Plan; результаты подтверждаются API/evidence и ручной проверкой.'),
            ('D2', 'Проверять одноразовыми сценариями без общего графа', 'Альтернатива для демонстрации exclusive group. Сейчас не выбрана; отображение альтернатив включается фильтром вида.'),
        ]:
            self.core('add-' + ident, 'add', {'entity': {'id': ident, 'kind': 'decision',
                      'title': title, 'description': description}, 'location': 'graph', 'initialRelations': []})
        self.core('decision-group', 'decision_group', {'group': {
            'id': 'G1', 'parentId': 'R1', 'title': 'Как организовать проверку RDG?',
            'selectionRequired': True, 'mutuallyExclusive': True,
            'members': [{'id': 'GM1', 'decisionId': 'D1'}, {'id': 'GM2', 'decisionId': 'D2'}],
        }})
        for _, rid, title, _ in AREAS:
            self.core('add-' + rid, 'add', {
                'entity': {'id': rid, 'kind': 'requirement', 'title': 'Проверено: ' + title,
                           'description': 'Критерии соответствующих Action должны быть проверены и подтверждены evidence.',
                           'scope': 'Только отдельный API acceptance process'},
                'location': 'graph', 'initialRelations': [{'id': 'E-D1-' + rid,
                    'type': 'INTRODUCES', 'from': 'D1', 'to': rid}],
            })
        for aid, title, parents, description in TASKS:
            self.core('add-' + aid, 'add', {
                'entity': {'id': aid, 'kind': 'action', 'title': aid + ' · ' + title,
                           'description': description, 'actionType': 'task', 'lowLevel': False,
                           'targetIds': [], 'groupIds': []},
                'location': 'graph', 'initialRelations': [{'id': 'E-' + parent + '-' + aid,
                    'type': 'REQUIRES_ACTION', 'from': parent, 'to': aid} for parent in parents],
            })
        for wid, rid, title, _ in AREAS:
            members = ['R1', 'D1', rid] + [aid for aid, _, parents, _ in TASKS if rid in parents]
            self.core('work-area-' + wid, 'work_graph', {'workGraph': {
                'id': wid, 'title': title, 'rootIds': [rid], 'memberIds': members}})
        # Review only our known, read-back fixture entities; this records inspection,
        # never completion of acceptance tasks. Schema supplies the actual current pins.
        row = self.read()
        require({n['id'] for n in row['graph']['nodes']} ==
                {'R1', 'D1', 'D2', 'R2', 'R3', 'R4', 'R5'} | {t[0] for t in TASKS},
                'Unexpected graph content: stop instead of changing it')
        for nid in ('R1', 'D1'):
            if self.read()['completion'][nid].get('reviewRequired'):
                self.core('review-before-selection-' + nid, 'review', node=nid)
        self.core('select-isolated-process', 'select', {'nodeId': 'D1'}, node='D1')
        self.operation('create-plan', 'plan_create', values={'title': 'План проверки A0–A17 — порядок без дат'})
        for aid, *_ in TASKS:
            self.operation('place-' + aid, 'place', node=aid)
        row = self.read()
        positions = {'R1': {'x': 0, 'y': 0}, 'D1': {'x': 0, 'y': 200}, 'D2': {'x': 720, 'y': 200}}
        for _, rid, _, x in AREAS:
            positions[rid] = {'x': x, 'y': 430}
            actions = [aid for aid, _, parents, _ in TASKS if parents[0] == rid]
            for i, aid in enumerate(actions):
                positions[aid] = {'x': x, 'y': 660 + i * 170}
        self.operation('save-layout', 'layout_edit', values={'commands': [{
            'type': 'set_positions', 'graphKey': row['view']['graphKey'], 'positions': positions}]})
        self.verify()

    def verify(self):
        require(self.pid is not None, 'Run seed before verify')
        row = self.read()
        require(row['graph']['coreModel'] == 'rdg-decision-v1', 'Wrong profile')
        require(len(row['graph']['nodes']) == 25 and len(row['graph']['workGraphs']) == 4, 'Incomplete fixture')
        require(len(row['plan']['steps']) == 18 and row['plan']['timeConstraints'] == [], 'Expected 18 order-only placements')
        by_step = {s['id']: s for s in row['plan']['steps']}
        require([by_step[s]['ref']['nodeId'] for s in row['plan']['mainStepIds']] == [t[0] for t in TASKS], 'Plan order differs')
        require(all(not row['completion'][t[0]]['complete'] for t in TASKS), 'Fixture must not claim test execution')
        require(all(e['by'] == 'assistant' for e in row['graph']['events']), 'Unexpected event attribution')
        canonical = row['view']['graphKey']
        graph_before = digest(row['graph']); plan_before = digest(row['plan'])
        for wid, *_ in AREAS:
            area = self.read({'kind': 'workGraph', 'id': wid})
            require(area['view']['graphKey'] == canonical and digest(area['graph']) == graph_before
                    and digest(area['plan']) == plan_before, 'WG must share Process/Plan owners')
        layout = row['layouts']['layouts'][canonical]['positions']
        require(set(layout) == {n['id'] for n in row['graph']['nodes']}, 'Missing saved node positions')
        before = self.observed()
        retried = ['create-process', 'work-area-WG1', 'select-isolated-process', 'create-plan', 'place-A0', 'save-layout']
        for label in retried:
            record = self.state['operations'][label]
            retry = self.call(method='apply', request=record['request'], expectedInputBinding=record['inputBinding'])
            require(retry.get('idempotent'), 'Exact retry must return the existing receipt: ' + label)
        require(before == self.observed(), 'Exact retries must not change owners')
        report = {'packageId': self.pid, 'path': PROCESS_PATH, 'title': TITLE,
                  'graphNodes': 25, 'workingGraphs': 4, 'plannedActions': 18,
                  'scheduledDates': 0, 'savedPositions': len(layout), 'completedAcceptanceTasks': 0,
                  'credentialRequiredByClient': False, 'preflightsObservedReadOnly': len(self.state['operations']),
                  'receiptsVerified': len(self.state['operations']), 'exactRetryVerified': True,
                  'exactRetryOperations': retried,
                  'sameOwnersAcrossWorkingGraphs': True, 'manualViewerVerified': False,
                  'liveServerRestartVerified': False, 'graphRevision': row['graph']['revision'],
                  'planRevision': row['plan']['revision'], 'layoutRevision': row['layouts']['revision'],
                  'snapshotSHA256': digest({k: row[k] for k in ('graph', 'plan', 'layouts')})}
        self.state['report'] = report; self.save()
        print(json.dumps({'report': report}, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('seed', 'verify'))
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    fixture = Seed(args.context, args.state)
    if args.action == 'seed':
        fixture.run()
    else:
        fixture.verify()
