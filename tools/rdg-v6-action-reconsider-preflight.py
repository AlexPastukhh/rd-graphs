#!/usr/bin/env python3
"""Read-only Action reconsideration preflight; never revokes or deactivates R.

Candidate v6 only. A report is an analysis, not authority, canon evaluation,
proof of no outside effects, or a durable LensRun.
"""
import argparse
import json
from pathlib import Path
from importlib.machinery import SourceFileLoader

APPLY = SourceFileLoader('rdg_v6_action_validation', str(Path(__file__).with_name('graph-apply.py'))).load_module()


def preview(graph, action_id):
    APPLY.validate(graph)
    if graph.get('actionModel') != APPLY.ACTION_MODEL:
        raise ValueError('Action reconsideration preflight requires opt-in candidate-v6 graph')
    nodes = {n['id']: n for n in graph['nodes']}
    action = nodes.get(action_id)
    if not action or action['kind'] != 'action':
        raise ValueError('Action not found')
    driving = [e for e in graph['edges'] if e['type'] == 'DRIVES'
               and e['to'] == action_id and not e.get('archived')]
    selected = action.get('status') == 'selected'
    children = [e for e in graph['edges'] if e['type'] == 'INTRODUCES'
                and e['from'] == action_id and not e.get('archived')]
    issues = [q['id'] for q in action.get('qrpe', [])
              if q.get('status') not in ('resolved', 'invalidated', 'accepted-risk')]
    impact = []
    for edge in children:
        rid = edge['to']
        supports = [e for e in graph['edges'] if e['type'] == 'INTRODUCES' and
                    e['from'] != action_id and e['to'] == rid and not e.get('archived') and
                    nodes.get(e['from'], {}).get('kind') == 'action' and
                    nodes[e['from']].get('status') == 'selected']
        dependents = [e for e in graph['edges'] if e['from'] == rid and not e.get('archived')]
        impact.append({'requirementId': rid, 'introducedByEdgeId': edge['id'],
                       'independentSelectedActionIds': sorted(e['from'] for e in supports),
                       'dependentEdgeIds': sorted(e['id'] for e in dependents),
                       'disposition': 'separately-justified' if supports else 'unresolved'})
    unresolved = [r['requirementId'] for r in impact if r['disposition'] == 'unresolved']
    return {
        'mode': 'read-only-candidate-preflight', 'actionId': action_id,
        'driverRequirementId': driving[0]['from'] if len(driving) == 1 else None,
        'actionStatus': action.get('status'), 'selectionEventIds': [e['id'] for e in graph['events']
            if e.get('type') == 'action_selected' and e.get('actionId') == action_id],
        'openQrpeIds': issues, 'introducedRequirements': impact,
        'unresolvedRequirementIds': unresolved,
        'externalEffectsVerifiedAbsent': False,
        'authorityVerified': False,
        'canExecuteRevocation': False,
        'structuralObstacles': (['Action is not selected'] if not selected else []) +
            (['Introduced Requirements need explicit disposition'] if unresolved else []) +
            (['Open QRPE need assessment'] if issues else []),
        'nextAction': 'Investigate canons/QRPE, independent reasons for child R, actual effects and authority before an event-bearing change.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph', required=True)
    parser.add_argument('--action-id', required=True)
    args = parser.parse_args()
    graph = json.loads(Path(args.graph).read_text(encoding='utf-8'))
    print(json.dumps(preview(graph, args.action_id), ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
