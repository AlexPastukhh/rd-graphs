#!/usr/bin/env python3
"""Shared graph mutations for candidate-v6. No Lens-specific operation.

Called by the existing authorized graph-package writer. The package's verified
signature is necessary but NOT proof of a user's real-world identity.
"""
import copy

OPERATIONS = {'create_requirement', 'create_context', 'edit_node',
              'delete_candidate', 'delete_orphan_requirement', 'deactivate_requirement',
              'detach_requirement', 'archive_edge', 'add_edge', 'set_reconsideration_policy',
              'reparent_requirement'}
PROTECTED_KEYS = {'id', 'kind', 'selectionBasis', 'qrpe', 'history', 'preparedSource',
                  'introducedByActionId', 'projectionOf', 'expansionOf', 'supersededBy',
                  'supersededEventId', 'selectedOptionId', 'authorityPrincipal',
                  'reconsiderationPolicy'}


def ensure(ok, message):
    if not ok:
        raise ValueError('GRAPH_API_' + message)


def guard_policy(node, event):
    """Guard material changes to a Requirement's scoped composition.

    Does not authenticate humans: caller's signed package must be authorized by
    a separately managed issuer. Read-only inspection never invokes this.
    """
    if node is None or node.get('kind') != 'requirement':
        return
    p = node.get('reconsiderationPolicy', {'mode': 'ordinary'})
    ensure(isinstance(p, dict) and p.get('mode', 'ordinary') in
           ('ordinary', 'stable', 'protected'), 'INVALID_POLICY')
    if p.get('mode') == 'stable':
        ensure(isinstance(event.get('reasonForReconsideration'), str) and
               event['reasonForReconsideration'].strip(), 'STABLE_RECONSIDERATION_REASON_REQUIRED')
    if p.get('mode') == 'protected':
        ensure(event.get('by') == 'user' and
               event.get('authorityPrincipal') == p.get('authorityPrincipal'),
               'PROTECTED_OWNER_GRANT_REQUIRED')


def apply(graph, op):
    """Mutate only in-memory, under graph-apply's complete validation/atomicity."""
    kind = op.get('action')
    ensure(kind in OPERATIONS, 'UNKNOWN_ACTION')
    event = copy.deepcopy(op.get('event'))
    ensure(isinstance(event, dict) and event.get('type') == 'graph_changed' and
           isinstance(event.get('id'), str) and event['id'] and
           event['id'] not in {e['id'] for e in graph['events']} and
           event.get('by') in ('user', 'assistant') and
           isinstance(event.get('note'), str) and event['note'].strip() and
           isinstance(event.get('authorityPrincipal'), str) and event['authorityPrincipal'].strip(),
           'ATTRIBUTED_EVENT_REQUIRED')
    ensure(event.get('operation') == kind, 'OPERATION_EVENT_MISMATCH')
    nodes = {n['id']: n for n in graph['nodes']}
    nid = op.get('nodeId')
    before = nodes.get(nid)
    old_node = copy.deepcopy(before) if before else None
    old_edges = []
    affected = []
    new_node = copy.deepcopy(op.get('node'))

    def policy(node):
        guard_policy(node, event)

    if kind in ('create_requirement', 'create_context'):
        wanted = 'requirement' if kind == 'create_requirement' else 'context'
        ensure(isinstance(new_node, dict) and new_node.get('kind') == wanted and
               isinstance(new_node.get('id'), str) and new_node['id'] not in nodes and
               isinstance(new_node.get('title'), str) and new_node['title'].strip() and
               'reconsiderationPolicy' not in new_node and
               'projectionOf' not in new_node, 'CREATE_INVALID_NODE')
        if wanted == 'requirement':
            new_node.setdefault('status', 'active')
            ensure(new_node['status'] == 'active', 'NEW_REQUIREMENT_MUST_BE_ACTIVE')
            parent = op.get('parentRequirementId')
            ensure(isinstance(parent, str) and parent in nodes and
                   nodes[parent]['kind'] == 'requirement' and
                   nodes[parent].get('status', 'active') == 'active', 'PARENT_REQUIRED')
            # Parent decomposition is part of a protected Requirement's scope;
            # signing the package as some issuer is not the owner's approval.
            policy(nodes[parent])
            eid = op.get('edgeId')
            ensure(isinstance(eid, str) and eid and
                   eid not in {e['id'] for e in graph['edges']}, 'EDGE_ID_REQUIRED')
            graph['edges'].append({'id': eid, 'type': 'DERIVES', 'from': parent, 'to': new_node['id']})
            affected.append(eid)
        graph['nodes'].append(new_node)
        nid = new_node['id']
    elif kind == 'edit_node':
        ensure(before is not None and before['kind'] in ('requirement', 'context', 'action'),
               'EDIT_TARGET_NOT_FOUND')
        policy(before)
        changes = op.get('changes')
        ensure(isinstance(changes, dict) and changes and
               not PROTECTED_KEYS.intersection(changes) and 'status' not in changes and
               (before['kind'] != 'action' or
                ('driverRequirementId' not in changes and 'status' not in changes)),
               'EDIT_PROTECTED_FIELDS')
        if before['kind'] == 'requirement' and before['id'] == graph['rootRequirementId']:
            ensure(event['by'] == 'user', 'ROOT_REQUIREMENT_REQUIRES_OWNER')
        before.update(copy.deepcopy(changes))
    elif kind == 'set_reconsideration_policy':
        ensure(before is not None and before['kind'] == 'requirement', 'POLICY_R_REQUIRED')
        policy(before)
        p = copy.deepcopy(op.get('policy'))
        ensure(isinstance(p, dict) and p.get('mode') in ('ordinary', 'stable', 'protected') and
               set(p) <= {'mode', 'authorityPrincipal'}, 'INVALID_NEW_POLICY')
        ensure(event['by'] == 'user', 'POLICY_OWNER_REQUIRED')
        if p['mode'] == 'protected':
            ensure(p.get('authorityPrincipal') == event['authorityPrincipal'],
                   'POLICY_PRINCIPAL_MUST_MATCH_ISSUER')
        else:
            ensure('authorityPrincipal' not in p, 'POLICY_PRINCIPAL_UNEXPECTED')
        before['reconsiderationPolicy'] = p
    elif kind in ('delete_candidate', 'delete_orphan_requirement'):
        expected = 'action' if kind == 'delete_candidate' else 'requirement'
        ensure(before is not None and before['kind'] == expected, 'DELETE_TARGET_MISSING')
        policy(before)
        if expected == 'action':
            ensure(before['status'] == 'candidate', 'ONLY_UNSELECTED_ACTION_DELETABLE')
            connected = [e for e in graph['edges'] if e['from'] == nid or e['to'] == nid]
            ensure(all(e['type'] == 'DRIVES' and e['to'] == nid for e in connected),
                   'ACTION_HAS_DEPENDENTS')
            old_edges = copy.deepcopy(connected)
            affected.extend(e['id'] for e in connected)
            graph['edges'] = [e for e in graph['edges'] if e not in connected]
        else:
            ensure(nid != graph['rootRequirementId'] and
                   not any((e['from'] == nid or e['to'] == nid) and
                           e.get('archived') is not True for e in graph['edges']),
                   'REQUIREMENT_HAS_DEPENDENTS')
            old_edges = [copy.deepcopy(e) for e in graph['edges']
                         if e['from'] == nid or e['to'] == nid]
            affected.extend(e['id'] for e in old_edges)
            graph['edges'] = [e for e in graph['edges']
                              if e['from'] != nid and e['to'] != nid]
        ensure(not any(e.get('actionId') == nid or e.get('requirementId') == nid or
                       e.get('driverRequirementId') == nid for e in graph['events']),
               'NODE_HAS_HISTORICAL_EVENTS')
        graph['nodes'] = [n for n in graph['nodes'] if n['id'] != nid]
    elif kind == 'reparent_requirement':
        ensure(before is not None and before['kind'] == 'requirement' and
               nid != graph['rootRequirementId'], 'REPARENT_NONROOT_R_REQUIRED')
        policy(before)
        parent = op.get('newParentRequirementId')
        ensure(isinstance(parent, str) and parent in nodes and
               nodes[parent]['kind'] == 'requirement' and
               nodes[parent].get('status', 'active') == 'active' and
               parent != nid, 'REPARENT_PARENT_REQUIRED')
        policy(nodes[parent])
        existing = [e for e in graph['edges'] if e['type'] == 'DERIVES' and
                    e['to'] == nid and e.get('archived') is not True]
        ensure(len(existing) == 1 and not any(
               e['type'] == 'INTRODUCES' and e['to'] == nid and
               e.get('archived') is not True for e in graph['edges']),
               'REPARENT_REQUIRES_ONE_DERIVES_AND_NO_ACTION_OWNER')
        policy(nodes[existing[0]['from']])
        eid = op.get('newEdgeId')
        ensure(isinstance(eid,str) and eid and
               eid not in {e['id'] for e in graph['edges']}, 'REPARENT_NEW_EDGE_ID_REQUIRED')
        old_edges = [copy.deepcopy(existing[0])]
        existing[0]['archived'] = True
        graph['edges'].append({'id':eid,'type':'DERIVES','from':parent,'to':nid})
        affected = [existing[0]['id'],eid]
    elif kind == 'deactivate_requirement':
        ensure(before is not None and before['kind'] == 'requirement' and
               nid != graph['rootRequirementId'], 'DEACTIVATE_NONROOT_R_REQUIRED')
        policy(before)
        ensure(not any(e.get('archived') is not True and
                       (e['from'] == nid or e['to'] == nid) and
                       e['type'] in ('DRIVES', 'INTRODUCES', 'DERIVES', 'APPLIES_TO')
                       for e in graph['edges']), 'REQUIREMENT_HAS_ACTIVE_DEPENDENTS')
        ensure(before.get('status', 'active') == 'active', 'REQUIREMENT_NOT_ACTIVE')
        before['status'] = 'inactive'
    elif kind in ('detach_requirement', 'archive_edge'):
        eid = op.get('edgeId')
        e = next((x for x in graph['edges'] if x['id'] == eid), None)
        ensure(e is not None and e.get('archived') is not True, 'ACTIVE_EDGE_REQUIRED')
        ensure((kind == 'detach_requirement' and e['type'] == 'INTRODUCES') or
               (kind == 'archive_edge' and e['type'] in ('DERIVES', 'APPLIES_TO', 'CONTEXT_FOR')),
               'CANNOT_ARCHIVE_HISTORIC_DRIVER')
        policy(nodes.get(e['to']))
        # An edge from a protected R is also a material change to its scope.
        policy(nodes.get(e['from']))
        if e.get('parent') in nodes:
            policy(nodes[e['parent']])
        old_edges = [copy.deepcopy(e)]
        affected = [eid]
        e['archived'] = True
        nid = e['to']
    elif kind == 'add_edge':
        e = copy.deepcopy(op.get('edge'))
        ensure(isinstance(e, dict) and e.get('type') in ('DERIVES', 'APPLIES_TO', 'CONTEXT_FOR') and
               isinstance(e.get('id'), str) and e['id'] and
               e['id'] not in {x['id'] for x in graph['edges']}, 'EDGE_TYPE_OR_ID_INVALID')
        ensure(e.get('from') in nodes and e.get('to') in nodes and
               e.get('from') != e.get('to'), 'EDGE_ENDPOINT_INVALID')
        policy(nodes[e['to']])
        policy(nodes[e['from']])
        graph['edges'].append(e)
        nid = e['to']
        affected = [e['id']]
    else:
        ensure(False, 'UNKNOWN_ACTION')

    event['targetId'] = nid
    event['priorNodeSnapshot'] = old_node
    event['priorEdges'] = old_edges
    event['edgeIds'] = affected
    # For hard deletion, provenance lives in this event; no dangling live nodes.
    event['targetDeleted'] = kind in ('delete_candidate', 'delete_orphan_requirement')
    graph['events'].append(event)
