#!/usr/bin/env python3
# STATUS: IN DEVELOPMENT. Change only for module-related tasks; see docs/guides/RDG-MODULES.md.
"""Closed RDG module contracts; trusted registry, owner-local version pins.

Data selects installed declarations, never code paths. Writers retain CAS,
authorization, journals, and the exclusive right to attest base outcomes.
"""
import copy
import json
import importlib.util
import re
from pathlib import Path

REGISTRY = Path(__file__).with_name('rdg-module-registry.json')
NAME = re.compile(r'[a-z][a-z0-9_-]*\Z')
IDENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]*\Z')
GRAPH_REF = re.compile(r'workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json\Z')


def require(ok, code):
    if not ok:
        raise ValueError('MODULE_' + code)


def registry():
    require(REGISTRY.is_file() and not REGISTRY.is_symlink(), 'REGISTRY_UNAVAILABLE')
    value = json.loads(REGISTRY.read_text(encoding='utf8'))
    require(isinstance(value, dict) and set(value) == {'schemaVersion','base','modules'}
            and value['schemaVersion'] == 1 and isinstance(value['base'], dict)
            and isinstance(value['modules'], dict), 'REGISTRY_INVALID')
    return value


def code(mid, version):
    d = definition(mid, version)
    entry = d.get('entry')
    require(isinstance(entry, str) and re.fullmatch(r'rdg-module-[a-z0-9_-]+\.py', entry),
            'CODE_ENTRY_INVALID')
    path = REGISTRY.parent / entry
    require(path.is_file() and not path.is_symlink(), 'CODE_NOT_INSTALLED')
    spec = importlib.util.spec_from_file_location('rdg_plugin_' + mid.replace('-', '_') + '_' + str(version), path)
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    require(getattr(plugin, 'API_VERSION', None) == 1, 'CODE_API_INCOMPATIBLE')
    return plugin


def hook(mid, version, name, *arguments):
    plugin = code(mid, version)
    callback = getattr(plugin, name, None)
    require(callable(callback), 'HOOK_UNAVAILABLE:' + name)
    return callback(*copy.deepcopy(arguments))


def base():
    return registry()['base']


def definition(mid, version):
    require(isinstance(mid, str) and NAME.fullmatch(mid) and type(version) is int,
            'PIN_INVALID')
    definition = registry()['modules'].get(mid, {}).get(str(version))
    require(isinstance(definition, dict), 'UNKNOWN_OR_INCOMPATIBLE_VERSION')
    require(definition.get('requiresBase') == base()['version'], 'BASE_INCOMPATIBLE')
    return definition


def pins(owner):
    configured = owner.get('modules', {})
    require(isinstance(configured, dict), 'PINS_INVALID')
    for mid, version in configured.items():
        definition(mid, version)
    disabled = owner.get('disabledModules', [])
    require(isinstance(disabled, list) and all(isinstance(x,str) for x in disabled)
            and len(disabled)==len(set(disabled)) and set(disabled)<=set(configured),
            'DISABLED_PINS_INVALID')
    return configured


def active(owner, mid, version):
    require(pins(owner).get(mid)==version and mid not in owner.get('disabledModules', []),
            'NOT_ENABLED')


def resolve(owner, scope):
    result = {}
    for mid, version in pins(owner).items():
        d = definition(mid, version)
        identity = {'id':owner.get('id'), 'identitySpace':owner.get('identitySpace')}
        require(identity in d.get('allowedOwners', {}).get(scope, []),
                'OWNER_NOT_GRANTED')
        code(mid, version)
        result[mid] = d
    return result


def schema(value, fields):
    """Small closed field vocabulary. Unsupported shapes fail, never free JSON."""
    require(isinstance(value, dict) and isinstance(fields, dict)
            and set(value) == set(fields), 'DATA_FIELDS')
    for key, spec in fields.items():
        item = value[key]
        if spec == 'text':
            require(isinstance(item, str) and bool(item.strip()), 'DATA_TEXT')
        elif spec == 'integer':
            require(type(item) is int, 'DATA_INTEGER')
        elif spec == 'requirementRefs':
            require(isinstance(item, list), 'DATA_REQUIREMENT_REFS')
            for ref in item:
                require(isinstance(ref, dict) and set(ref) == {'graphFile','identitySpace','nodeId'}
                        and isinstance(ref['graphFile'], str) and GRAPH_REF.fullmatch(ref['graphFile'])
                        and isinstance(ref['identitySpace'], str) and bool(ref['identitySpace'])
                        and isinstance(ref['nodeId'], str) and IDENT.fullmatch(ref['nodeId']),
                        'DATA_REQUIREMENT_REF')
            require(len({json.dumps(r, sort_keys=True) for r in item}) == len(item),
                    'DUPLICATE_REQUIREMENT_REF')
        else:
            raise ValueError('MODULE_UNSUPPORTED_FIELD_SCHEMA')


def graph_kinds(graph):
    result = set()
    for mid, d in resolve(graph, 'graph').items():
        for kind in d.get('graph', {}).get('entities', {}):
            require(kind.startswith(mid + '.'), 'KIND_NAMESPACE')
            require(kind not in result and kind not in base()['nodeKinds'], 'KIND_COLLISION')
            result.add(kind)
    return result


def entity_spec(owner, node):
    module = node.get('module')
    require(isinstance(module, dict) and set(module) == {'id','version'}, 'ENTITY_PIN')
    mid, version = module['id'], module['version']
    require(pins(owner).get(mid) == version, 'ENTITY_MODULE_NOT_ENABLED')
    d = resolve(owner, 'graph').get(mid)
    require(d is not None, 'ENTITY_MODULE_NOT_ENABLED')
    spec = d.get('graph', {}).get('entities', {}).get(node.get('kind'))
    require(isinstance(spec, dict), 'ENTITY_KIND_NOT_DECLARED')
    require(set(node) == {'id','kind','title','module','data'}
            and isinstance(node['id'], str) and IDENT.fullmatch(node['id'])
            and isinstance(node['title'], str) and bool(node['title'].strip()), 'ENTITY_SCHEMA')
    schema(node['data'], spec['fields'])
    hook(mid, version, 'validate_entity', node, owner)
    return spec


def validate_graph(graph):
    resolve(graph, 'graph')
    for node in graph['nodes']:
        if node['kind'] in base()['nodeKinds']:
            require('module' not in node, 'BASE_KIND_CANNOT_BE_OVERRIDDEN')
        if node['kind'] not in base()['nodeKinds'] and node['kind'] != 'context':
            entity_spec(graph, node)
    for event in graph['events']:
        if event.get('type') in ('module_event','modules_configured'):
            validate_event(graph, event)


def validate_event(graph, event):
    require(isinstance(event.get('authorityPrincipal'), str) and bool(event['authorityPrincipal']),
            'EVENT_AUTHORITY')
    if event['type'] == 'modules_configured':
        require(isinstance(event.get('previousModules'), dict)
                and isinstance(event.get('newModules'), dict), 'CONFIG_EVENT')
        for configured, disabled in ((event['previousModules'],event.get('previousDisabled',[])),
                                     (event['newModules'],event.get('newDisabled',[]))):
            resolve({**graph, 'modules':configured,'disabledModules':disabled}, 'graph')
        return
    module = event.get('module', {})
    mid, version = module.get('id'), module.get('version')
    require(pins(graph).get(mid) == version, 'HISTORY_MODULE_NOT_ENABLED')
    d = resolve(graph, 'graph')[mid]
    operation = d.get('graph', {}).get('operations', {}).get(event.get('operation'))
    require(operation is not None, 'HISTORY_OPERATION_UNKNOWN')
    snapshot = event.get('nodeSnapshot')
    require(isinstance(snapshot, dict) and snapshot.get('id') == event.get('targetId')
            and snapshot.get('kind') == operation['kind']
            and snapshot.get('module') == module, 'HISTORY_SNAPSHOT')
    entity_spec(graph, snapshot)
    require(isinstance(event.get('label'),str) and bool(event['label'].strip()),'HISTORY_LABEL')


def check_transition(before, after, scope):
    previous, current = pins(before), pins(after)
    resolve(after, scope)
    changed = {mid for mid, version in previous.items() if current.get(mid) != version}
    for mid in changed:
        # Upgrades require an explicit migration implementation, not a new pin.
        require(mid not in current, 'MIGRATION_REQUIRED')
        if scope == 'graph':
            used = any(n.get('module', {}).get('id') == mid for n in before.get('nodes', []))
            used = used or any(e.get('module', {}).get('id') == mid
                               for e in before.get('events', []))
        else:
            used = mid in before.get('moduleData', {})
        require(not used, 'DISABLE_HAS_DEPENDENT_DATA_OR_HISTORY')
    if scope == 'plan':
        for mid in after.get('disabledModules',[]):
            require(before.get('moduleData',{}).get(mid)==after.get('moduleData',{}).get(mid),
                    'DISABLED_DATA_IMMUTABLE')
        require(set(before.get('moduleData', {})) <= set(after.get('moduleData', {})),
                'PLAN_DATA_REMOVAL_REQUIRES_MIGRATION')


def attributed_event(graph, operation, kind):
    event = copy.deepcopy(operation.get('event'))
    require(isinstance(event, dict) and event.get('type') == kind
            and isinstance(event.get('id'), str) and bool(event['id'])
            and all(e['id'] != event['id'] for e in graph['events'])
            and event.get('by') in ('assistant','user')
            and isinstance(event.get('note'), str) and bool(event['note'].strip())
            and isinstance(event.get('authorityPrincipal'), str) and bool(event['authorityPrincipal']),
            'ATTRIBUTED_EVENT_REQUIRED')
    # Writer verification supplies provenance. Caller cannot supply semantic payload.
    allowed = {'id','type','by','note','authorityPrincipal','verifiedTrustReceipt'}
    require(set(event) <= allowed, 'EVENT_FIELDS')
    return event


def apply_graph(graph, op, policy_guard):
    before = copy.deepcopy(graph)
    policy_guard(next(n for n in graph['nodes'] if n['id'] == graph['rootRequirementId']),
                 op.get('event') or {})
    if op['op'] == 'configure_modules':
        require({'op','modules','event'} <= set(op) <= {'op','modules','disabledModules','event'},
                'CONFIG_OPERATION_SCHEMA')
        event = attributed_event(graph, op, 'modules_configured')
        graph['modules'] = copy.deepcopy(op['modules'])
        graph['disabledModules'] = copy.deepcopy(op.get('disabledModules', []))
        check_transition(before, graph, 'graph')
        event.update(previousModules=copy.deepcopy(pins(before)), newModules=copy.deepcopy(pins(graph)),
                     previousDisabled=copy.deepcopy(before.get('disabledModules',[])),
                     newDisabled=copy.deepcopy(graph.get('disabledModules',[])))
    else:
        require(set(op) == {'op','module','version','operation','node','event'}, 'GRAPH_OPERATION_SCHEMA')
        mid, version = op['module'], op['version']
        active(graph, mid, version)
        d = resolve(graph, 'graph')[mid]
        operation = d.get('graph', {}).get('operations', {}).get(op['operation'])
        require(operation is not None, 'OPERATION_NOT_DECLARED')
        event = attributed_event(graph, op, 'module_event')
        raw_node=op.get('node')
        require(isinstance(raw_node,dict) and raw_node.get('kind')==operation['kind'],
                'OPERATION_ENTITY')
        schema(raw_node.get('data'), d['graph']['entities'][operation['kind']]['fields'])
        effect = hook(mid, version, 'graph_operation', op, graph)
        require(isinstance(effect, dict) and set(effect) == {'node'}, 'GRAPH_EFFECT_SCHEMA')
        node = effect['node']
        require(isinstance(node, dict) and node.get('kind') == operation['kind']
                and node.get('module') == {'id':mid,'version':version}, 'OPERATION_ENTITY')
        entity_spec(graph, node)
        old = next((n for n in graph['nodes'] if n['id'] == node['id']), None)
        if operation['handler'] == 'create_entity':
            require(old is None, 'ENTITY_ALREADY_EXISTS')
        elif operation['handler'] == 'update_entity':
            require(old is not None and old['kind'] == node['kind'] and old.get('module') == node['module'],
                    'UPDATE_IDENTITY')
            require(old != node, 'NO_CHANGE')
            graph['nodes'].remove(old)
        else:
            raise ValueError('MODULE_HANDLER_UNSUPPORTED')
        graph['nodes'].append(node)
        event.update(module={'id':mid,'version':version}, operation=op['operation'],
                     targetId=node['id'], priorNodeSnapshot=copy.deepcopy(old),
                     nodeSnapshot=copy.deepcopy(node))
        event['label'] = history_label(event, graph)
    graph['events'].append(event)
    validate_graph(graph)


def validate_plan(plan):
    definitions = resolve(plan, 'plan')
    data = plan.get('moduleData', {})
    require(isinstance(data, dict) and set(data) <= set(definitions), 'PLAN_MODULE_NOT_ENABLED')
    for mid, value in data.items():
        spec = definitions[mid].get('plan')
        require(isinstance(spec, dict), 'PLAN_EXTENSION_NOT_DECLARED')
        schema(value, spec['fields'])
        hook(mid, pins(plan)[mid], 'validate_plan', value, plan)


def apply_plan(plan, operation):
    before = copy.deepcopy(plan)
    if operation.get('op') == 'configure_modules':
        require({'op','modules'}<=set(operation)<={'op','modules','disabledModules'}, 'PLAN_CONFIG_SCHEMA')
        plan['modules'] = copy.deepcopy(operation['modules'])
        plan['disabledModules'] = copy.deepcopy(operation.get('disabledModules', []))
    else:
        require(set(operation) == {'op','module','version','data'}
                and operation.get('op') == 'set_module_data', 'PLAN_OPERATION_SCHEMA')
        mid = operation['module']
        active(plan, mid, operation['version'])
        d=resolve(plan,'plan')[mid]
        require(isinstance(d.get('plan'),dict),'PLAN_EXTENSION_NOT_DECLARED')
        schema(operation['data'],d['plan']['fields'])
        data = hook(mid, operation['version'], 'plan_operation', operation, plan)
        plan.setdefault('moduleData', {})[mid] = data
    check_transition(before, plan, 'plan')
    validate_plan(plan)


def plan_history(before, after):
    result = []
    if pins(before) != pins(after) or before.get('disabledModules',[]) != after.get('disabledModules',[]):
        result.append({'kind':'modules_configured', 'summary':'Изменены подключённые модули Plan',
                       'previousModules':copy.deepcopy(pins(before)), 'newModules':copy.deepcopy(pins(after)), 'previousDisabled':copy.deepcopy(before.get('disabledModules',[])),
                       'newDisabled':copy.deepcopy(after.get('disabledModules',[]))})
    for mid, data in after.get('moduleData', {}).items():
        old = before.get('moduleData', {}).get(mid)
        if old != data:
            d = definition(mid, pins(after)[mid])
            result.append({'kind':'module_plan_changed', 'module':{'id':mid,'version':pins(after)[mid]},
                           'summary':history_label({'type':'module_plan_changed','module':{'id':mid,'version':pins(after)[mid]},'data':data}, after), 'previousModuleData':copy.deepcopy(old),
                           'newModuleData':copy.deepcopy(data)})
    return result


def capabilities(owner, scope):
    enabled = resolve(owner, scope)
    available = {}
    for mid, versions in registry()['modules'].items():
        for version, d in versions.items():
            if {'id':owner.get('id'),'identitySpace':owner.get('identitySpace')} in d.get('allowedOwners', {}).get(scope, []):
                available.setdefault(mid, []).append(int(version))
    return {'base':{'id':'rdg-base','version':base()['version']},
            'enabled':{k:v for k,v in pins(owner).items() if k not in owner.get('disabledModules',[])},
            'pinned':copy.deepcopy(pins(owner)), 'disabled':copy.deepcopy(owner.get('disabledModules',[])), 'available':available,
            'contributions':copy.deepcopy(enabled)}

def history_label(event, owner):
    module = event['module']
    label = hook(module['id'], module['version'], 'describe_history', event, owner)
    require(isinstance(label, str) and bool(label.strip()) and len(label) <= 500, 'HISTORY_LABEL')
    return label


def requirement_references(graph):
    refs=[]
    for node in graph['nodes']:
        if not node.get('module'):continue
        spec=entity_spec(graph,node)
        for field, shape in spec['fields'].items():
            if shape=='requirementRefs':refs.extend(copy.deepcopy(node['data'][field]))
    return refs


def validate_references(graph, graphs):
    for ref in requirement_references(graph):
        source=graphs.get(ref['graphFile'])
        require(source is not None and ref['identitySpace']==graph['identitySpace']==source.get('identitySpace')
                and any(n.get('id')==ref['nodeId'] and n.get('kind')=='requirement'
                        and not n.get('projectionOf') for n in source.get('nodes',[])),
                'REQUIREMENT_OWNER_UNRESOLVED')
