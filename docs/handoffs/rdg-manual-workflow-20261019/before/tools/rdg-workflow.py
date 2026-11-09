#!/usr/bin/env python3
"""Current future/history view over the existing Plan and Graph owners.

Read-only: same graph entities, explicit placement, no duplicated execution
owner, no recurrence engine. Plan and graph locks protect one coherent read.
"""
import argparse
from html import escape
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
OWNER = SourceFileLoader('workflow_plan_owner', str(TOOLS/'rdg-temporal-plan-owner.py')).load_module()
ACTIVITY = SourceFileLoader('workflow_activity', str(TOOLS/'rdg-activity.py')).load_module()


def read_workflow(plan_root, plan_file, graph_root, authority_store, token, graph_refs=()):
    if not authority_store:
        raise ValueError('WORKFLOW_AUTHORITY_STORE_REQUIRED')
    OWNER.AUTH.Authority(authority_store).authorize_plan(token, ['plan.read'], plan_file)
    root = OWNER.root_path(plan_root)
    with OWNER.root_lock(root, False):
        snapshot = OWNER.read_snapshot(root, plan_file)
        plan = snapshot['plan']
        refs = list(graph_refs)
        for step in plan['steps']:
            if step['kind'] in ('action', 'requirement'):
                ref = step['actionRef' if step['kind'] == 'action' else 'requirementRef']
                refs.append(ref['graphFile'])
        report = ACTIVITY.read_activity(graph_root, refs, token, authority_store)
    rules = plan.get('timeConstraints', [])
    links = plan.get('sequence', [])
    placed = {r['stepId'] for r in rules}
    for e in links:
        placed.update((e['before'], e['after']))
    # Topological order of the original schedule, including completed predecessors.
    remaining = {s['id'] for s in plan['steps']}
    order = []
    while remaining:
        ready = [s['id'] for s in plan['steps'] if s['id'] in remaining and not any(
            e['after'] == s['id'] and e['before'] in remaining for e in links)]
        if not ready:
            raise ValueError('WORKFLOW_SEQUENCE_CYCLE')
        order.extend(ready)
        remaining.difference_update(ready)
    future, unresolved, excluded = [], [], []
    for step in sorted(plan['steps'], key=lambda s: order.index(s['id'])):
        if step['kind'] not in ('action', 'requirement'):
            continue
        ref = step['actionRef' if step['kind'] == 'action' else 'requirementRef']
        owner = report['graphOwners'][ref['graphFile']]
        node = owner['nodes'].get(ref['nodeId'])
        if owner['identitySpace'] != ref['identitySpace'] or not node or node['kind'] != step['kind']:
            raise ValueError('WORKFLOW_GRAPH_REFERENCE_MISMATCH')
        state = report['currentCompletion'].get(ref['graphFile'], {}).get(ref['nodeId'])
        row = {'stepId': step['id'], 'kind': step['kind'], 'graphRef': dict(ref),
               'nodeId': ref['nodeId'], 'title': node['title'], 'plannedTitle': step['title'],
               'state': step['state'], 'graphRevision': owner['revision'],
               'timeConstraints': [r for r in rules if r['stepId'] == step['id']],
               'sequence': [e for e in links if step['id'] in (e['before'], e['after'])]}
        if step['id'] not in placed:
            excluded.append({**row, 'reason': 'not-placed'})
        elif state and state['complete']:
            excluded.append({**row, 'reason': 'completed', 'eventId': state['eventId']})
        elif node.get('active') is False or node.get('status') in ('superseded', 'rejected', 'inactive'):
            excluded.append({**row, 'reason': 'withdrawn-or-inactive'})
        elif node.get('projectionOf') or not state:
            unresolved.append({**row, 'reason': 'unresolved-owner-or-unsupported-model'})
        else:
            future.append(row)
    return {'schemaVersion': 1, 'planId': plan['id'], 'title': plan['title'],
            'planProvenance': snapshot['provenance'], 'graphOwners': {
                k: {f:v[f] for f in ('identitySpace', 'revision')} for k,v in report['graphOwners'].items()},
            'future': future, 'history': report['activities'], 'unresolved': unresolved,
            'excludedPlacements': excluded, 'sourcesChanged': False,
            'coverage': 'current explicit Plan and requested graph owners; external completion unresolved'}


def markdown(view):
    lines = ['# '+view['title'], '', '## Предстоит', '']
    for row in view['future']:
        when = ', '.join(r['type']+': '+r['at'] for r in row['timeConstraints'])
        after = ', '.join(e['before'] for e in row['sequence'] if e['after'] == row['stepId'])
        lines.append('- '+row['nodeId']+' · '+row['title']+(' · '+when if when else '')+(' · после '+after if after else ''))
    if not view['future']:
        lines.append('Нет предстоящих действий или целей.')
    if view['unresolved']:
        lines += ['', '## Не разрешены ссылки', '']
        lines += ['- '+r['nodeId']+' · '+r['reason'] for r in view['unresolved']]
    lines += ['', '## История', '', ACTIVITY.markdown({'activities':view['history']})]
    return '\n'.join(lines)+'\n'


def html(view):
    def e(value):
        return escape(str(value), quote=True)
    labels = {'graph_saved':'Сохранение графа', 'action_executed':'Выполнен Action',
              'requirement_achieved':'Достигнута цель', 'action_withdrawn':'Отозван Action'}
    future = ''.join('<tr><td>'+e(r['nodeId'])+'</td><td>'+e(r['title'])+'</td><td>'+e(', '.join(
        x['type']+': '+x['at'] for x in r['timeConstraints']))+'</td><td>'+e(', '.join(
        x['before']+' → '+x['after'] for x in r['sequence']))+'</td></tr>' for r in view['future'])
    history = ''.join('<tr><td>'+e(r.get('recordedAt') or 'Время неизвестно')+'</td><td>'+e(labels[r['kind']])+
        '</td><td>'+e(r.get('targetId') or '')+'</td><td>'+e(r.get('title') or r.get('summary') or r.get('note') or '')+
        '</td></tr>' for r in view['history'])
    unresolved = ''.join('<li>'+e(r['nodeId'])+': '+e(r['reason'])+'</li>' for r in view['unresolved'])
    return '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+ \
        '<title>'+e(view['title'])+'</title><style>body{font:16px system-ui;max-width:1150px;margin:40px auto;padding:0 20px;color:#182436;background:#f5f7fa}h1{font-size:28px}section{background:white;padding:24px;margin:20px 0;border-radius:12px}table{border-collapse:collapse;width:100%}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #e1e6ed}th{color:#496078}small{color:#526579}</style><h1>'+e(view['title'])+'</h1><small>Снимок для чтения · версия плана '+e(view['planProvenance']['revision'])+' · те же ID сущностей графа</small>'+ \
        '<section><h2>Предстоит</h2>'+('<table><tr><th>ID</th><th>Цель / Action</th><th>Время</th><th>Порядок</th></tr>'+future+'</table>' if future else '<p>Нет предстоящих действий или целей.</p>')+'</section>'+ \
        ('<section><h2>Не разрешены ссылки</h2><ul>'+unresolved+'</ul></section>' if unresolved else '')+ \
        '<section><h2>История</h2><table><tr><th>Записано</th><th>Событие</th><th>ID</th><th>Содержание</th></tr>'+history+'</table></section></html>\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--file', required=True)
    parser.add_argument('--graph-root', required=True)
    parser.add_argument('--graph', action='append', default=[])
    parser.add_argument('--store', default=os.environ.get('RDG_AUTH_STORE'))
    parser.add_argument('--format', choices=('json','markdown','html'), default='json')
    args = parser.parse_args()
    result = read_workflow(args.root, args.file, args.graph_root, args.store,
                           os.environ.get('RDG_AUTH_TOKEN'), args.graph)
    print(markdown(result) if args.format == 'markdown' else html(result) if args.format == 'html' else
          json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise SystemExit('ERROR: '+str(exc))
