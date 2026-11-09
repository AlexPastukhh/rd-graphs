# STATUS: IN DEVELOPMENT. Change only for module-related tasks; see docs/guides/RDG-MODULES.md.
"""Neutral integration probe. Available only to registered isolated test owners."""
API_VERSION = 1


def validate_entity(node, graph):
    value = node['data']['value']
    if value != value.strip().upper() or len(value) > 32:
        raise ValueError('TEST_MODULE_MARKER_VALUE')


def graph_operation(operation, graph):
    node = operation['node']
    node['data']['value'] = node['data']['value'].strip().upper()
    return {'node': node}


def validate_plan(data, plan):
    if data['score'] != len(data['annotation'].split()):
        raise ValueError('TEST_MODULE_PLAN_SCORE')


def plan_operation(operation, plan):
    data = operation['data']
    data['annotation'] = data['annotation'].strip()
    data['score'] = len(data['annotation'].split())
    return data


def describe_history(event, owner):
    if event['type'] == 'module_plan_changed':
        return 'Тестовый модуль · Plan: ' + event['data']['annotation']
    return 'Тестовый модуль · запись: ' + event['nodeSnapshot']['data']['value']
