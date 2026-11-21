"""Versioned Planning Helper command data. Planning never executes command text."""
import copy
import hashlib
import json
from pathlib import Path
import re


OPERATIONS = ('chat_catalog_initialize', 'chat_catalog_edit')
GROUP_FIELDS = ('title', 'description')
COMMAND_FIELDS = ('kind', 'title', 'description', 'lensRefs', 'insertText')
STEPS = {
    'group_create': (('id', *GROUP_FIELDS), ('beforeId',)),
    'group_edit': (('id', 'changes'), ()),
    'group_move': (('id',), ('beforeId',)),
    'group_delete': (('id',), ()),
    'command_create': (('id', 'groupId', *COMMAND_FIELDS), ('beforeId',)),
    'command_edit': (('id', 'changes'), ()),
    'command_move': (('id', 'groupId'), ('beforeId',)),
    'command_delete': (('id',), ()),
}
KEY = re.compile(r'[a-z][a-z0-9-]{0,79}')
COMMAND_ID = re.compile(r'rdg\.(?:lens|command)\.[a-z][a-z0-9-]{0,79}')
SECRET = re.compile(r'ghp_[A-Za-z0-9]{20}|Bearer\s+[A-Za-z0-9._~+/-]{16}|'
                    r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|rdg_[A-Za-z0-9_-]{40,100}', re.I)
MAX_STEPS = 100
MAX_BYTES = 800_000
SEED = Path(__file__).resolve().parents[1] / 'kit' / 'helper-commands' / 'catalog-v2.json'


def require(ok, code):
    if not ok:
        raise ValueError('PORTABLE_APP_CHAT_CATALOG_' + code)


def empty():
    return {'schemaVersion': 1, 'revision': 0, 'groups': [], 'commands': []}


def fields(value, required, optional=()):
    return (isinstance(value, dict) and set(required) <= value.keys()
            and value.keys() <= set(required) | set(optional))


def key(value, pattern=KEY):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def group_key(value):
    return key(value) and value not in ('all', 'ungrouped')


def text(value, limit, *, multiline=False):
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= limit
            and not SECRET.search(value) and
            all((multiline and c in '\n\r\t') or (ord(c) >= 32 and ord(c) != 127) for c in value))


def validate(value):
    require(fields(value, ('schemaVersion', 'revision', 'groups', 'commands')) and
            value['schemaVersion'] == 1 and type(value['revision']) is int and value['revision'] >= 0,
            'FORMAT')
    groups, commands = value['groups'], value['commands']
    require(isinstance(groups, list) and len(groups) <= 30 and
            isinstance(commands, list) and len(commands) <= 250, 'SIZE')
    group_ids = set()
    for row in groups:
        require(fields(row, ('id', *GROUP_FIELDS)) and group_key(row['id'])
                and row['id'] not in group_ids, 'GROUP')
        require(text(row['title'], 160) and text(row['description'], 500, multiline=True), 'GROUP_TEXT')
        group_ids.add(row['id'])
    command_ids = set()
    for row in commands:
        require(fields(row, ('id', 'groupId', *COMMAND_FIELDS)) and key(row['id'], COMMAND_ID)
                and row['id'] not in command_ids, 'COMMAND')
        require(row['groupId'] is None or group_key(row['groupId']) and row['groupId'] in group_ids, 'GROUP_NOT_FOUND')
        require(text(row['title'], 300) and text(row['description'], 1200, multiline=True)
                and text(row['insertText'], 8000, multiline=True), 'COMMAND_TEXT')
        refs = row['lensRefs']
        require(isinstance(refs, list) and len(refs) <= 12, 'LENS_REFS')
        ref_keys = set()
        for ref in refs:
            require(fields(ref, ('role', 'lensKey', 'modelProfile')) and ref['role'] == 'lens'
                    and ref['modelProfile'] == 'rdg-decision-v1' and key(ref['lensKey'])
                    and ref['lensKey'] not in ref_keys, 'LENS_REF')
            ref_keys.add(ref['lensKey'])
        kind = row['kind']
        if kind == 'lens-launcher':
            require(len(refs) == 1 and row['id'] == 'rdg.lens.' + refs[0]['lensKey'], 'COMMAND_KIND')
        else:
            require(kind in ('workflow', 'instruction') and row['id'].startswith('rdg.command.')
                    and (kind == 'instruction' or bool(refs)), 'COMMAND_KIND')
        command_ids.add(row['id'])
    require(len(json.dumps(value, ensure_ascii=False).encode()) <= MAX_BYTES, 'SIZE')
    return value


def seed():
    raw = SEED.read_bytes()
    manifest = json.loads(raw)
    require(manifest['schemaVersion'] == 2 and manifest['kind'] == 'rdg-chat-commands'
            and manifest['complete'] is True, 'SEED_FORMAT')
    value = validate({**empty(), 'revision': 1,
                      'groups': manifest['groups'], 'commands': manifest['commands']})
    return value, manifest['catalogRevision'], hashlib.sha256(raw).hexdigest()


def schema(op, revision, transaction_id):
    request = {'op': op, 'transactionId': transaction_id,
               'expectedCatalogRevision': revision, 'note': ''}
    response = {'schemaVersion': 1, 'request': request, 'requiredInput': ['note'],
                'preflightBindingRequired': True}
    if op == 'chat_catalog_initialize':
        response['initializationAvailable'] = revision == 0
    else:
        request['steps'] = []
        response['requiredInput'].append('steps')
        response.update(maxSteps=MAX_STEPS, stepFields={
            op: {'required': list(required), 'optional': list(optional)}
            for op, (required, optional) in STEPS.items()},
            editableFields={'group': list(GROUP_FIELDS), 'command': list(COMMAND_FIELDS)},
            order='beforeId identifies a peer in the destination group or group list. '
                  'Omit it or pass null to append. groupId=null means ungrouped.')
    return response


def place(rows, item, before_id, peers):
    if before_id is None:
        rows.append(item)
        return
    require(key(before_id, COMMAND_ID if 'groupId' in item else KEY), 'BEFORE_ID')
    before = next((i for i, row in enumerate(rows) if row['id'] == before_id and peers(row)), None)
    require(before is not None, 'BEFORE_NOT_FOUND')
    rows.insert(before, item)


def edit(before, steps):
    require(isinstance(steps, list) and 1 <= len(steps) <= MAX_STEPS, 'STEPS')
    candidate = copy.deepcopy(before)
    report = []
    for step in steps:
        op = step.get('op') if isinstance(step, dict) else None
        require(isinstance(op, str) and op in STEPS, 'STEP_OP')
        required, optional = STEPS[op]
        require(fields(step, ('op', *required), optional), 'STEP_FIELDS')
        kind, action = op.split('_', 1)
        ident = step['id']
        group = kind == 'group'
        require(group_key(ident) if group else key(ident, COMMAND_ID), 'ITEM_ID')
        rows = candidate['groups' if group else 'commands']
        index = next((i for i, row in enumerate(rows) if row['id'] == ident), None)
        require((index is None) == (action == 'create'), 'ITEM_EXISTS' if action == 'create' else 'ITEM_NOT_FOUND')
        if action == 'edit':
            changes = step['changes']
            allowed = GROUP_FIELDS if group else COMMAND_FIELDS
            require(isinstance(changes, dict) and changes and changes.keys() <= set(allowed), 'EDIT_FIELDS')
            rows[index].update(copy.deepcopy(changes))
        elif action == 'delete':
            rows.pop(index)
            if group:
                for command in candidate['commands']:
                    if command['groupId'] == ident:
                        command['groupId'] = None
        else:
            if action == 'create':
                item = {name: copy.deepcopy(step[name]) for name in required}
            else:
                item = rows.pop(index)
                if not group:
                    item['groupId'] = step['groupId']
            if not group:
                group_id = item['groupId']
                require(group_id is None or group_key(group_id)
                        and any(g['id'] == group_id for g in candidate['groups']), 'GROUP_NOT_FOUND')
            place(rows, item, step.get('beforeId'),
                  lambda row: group or row['groupId'] == item['groupId'])
        report.append({'op': op, 'id': ident})
    require(candidate != before, 'NO_CHANGE')
    candidate['revision'] += 1
    return validate(candidate), report


def plan(before, request):
    op = request['op']
    required = ('op', 'transactionId', 'expectedCatalogRevision', 'note')
    if op == 'chat_catalog_edit':
        required += ('steps',)
    require(fields(request, required), 'REQUEST_FIELDS')
    require(type(request['expectedCatalogRevision']) is int and
            request['expectedCatalogRevision'] == before['revision'], 'REVISION_CHANGED')
    require(text(request['note'], 2000, multiline=True), 'NOTE')
    if op == 'chat_catalog_initialize':
        require(before['revision'] == 0, 'ALREADY_INITIALIZED')
        value, source_revision, source_sha = seed()
        return value, {'seedRevision': source_revision, 'seedSHA256': source_sha,
                       'groupCount': len(value['groups']), 'commandCount': len(value['commands'])}
    require(before['revision'] > 0, 'INITIALIZATION_REQUIRED')
    value, report = edit(before, request['steps'])
    return value, {'steps': report}
