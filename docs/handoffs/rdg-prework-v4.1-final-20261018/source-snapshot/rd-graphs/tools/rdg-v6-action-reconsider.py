#!/usr/bin/env python3
"""Bounded candidate-v6 Action reconsideration semantics, not an authority service.

A selected ordinary Action performs the reconsideration. The writer records
snapshots and consequences; no user permission or factual canon proof is
established by user-supplied string fields in an event.
"""
import copy


def ensure(ok, message):
    if not ok:
        raise ValueError(message)


def active(edge):
    return edge.get('archived') is not True


def action_driver(graph, action_id):
    drivers = [e for e in graph['edges'] if e.get('type') == 'DRIVES'
               and e.get('to') == action_id and active(e)]
    ensure(len(drivers) == 1, 'RECONSIDER_DRIVER_UNCERTAIN')
    return drivers[0]['from']


def cases(action):
    block = action.get('canonBlock')
    ensure(isinstance(block, dict), 'RECONSIDER_ACTION_CANON_REQUIRED')
    positive = block.get('recommended')
    negative = block.get('contraindicated')
    ensure(isinstance(positive, list) and positive and isinstance(negative, list),
           'RECONSIDER_ACTION_REQUIRES_RECOMMENDED_CANON')
    return {c['id']: (polarity, c) for polarity, seq in
            [('recommended', positive), ('contraindicated', negative)] for c in seq}


def ensure_assessment(review, event):
    cs = cases(review)
    checks = event.get('canonChecks')
    ensure(isinstance(checks, list) and len(checks) == len(cs),
           'RECONSIDER_CANON_CASES_NOT_REVIEWED')
    seen = set()
    recommended_applies = False
    for check in checks:
        ensure(isinstance(check, dict) and check.get('caseId') in cs and
               check['caseId'] not in seen, 'RECONSIDER_INVALID_CANON_ASSESSMENT')
        seen.add(check['caseId'])
        ensure(check.get('result') in ('applicable', 'inapplicable') and
               isinstance(check.get('reason'), str) and check['reason'].strip() and
               isinstance(check.get('evidenceRefs'), list) and check['evidenceRefs'] and
               all(isinstance(ref, str) and ref.strip() for ref in check['evidenceRefs']),
               'RECONSIDER_CANON_EVIDENCE_REQUIRED')
        polarity = cs[check['caseId']][0]
        ensure(not (polarity == 'contraindicated' and check['result'] == 'applicable'),
               'RECONSIDER_CONTRAINDICATION_APPLIES')
        if polarity == 'recommended' and check['result'] == 'applicable':
            recommended_applies = True
    ensure(recommended_applies, 'RECONSIDER_NO_APPLICABLE_POSITIVE_CANON')
    qrpe = review.get('qrpe')
    ensure(isinstance(qrpe, list) and qrpe, 'RECONSIDER_REVIEW_ACTION_QRPE_REQUIRED')
    ensure(all(q.get('status') in ('resolved', 'accepted-risk', 'invalidated')
               for q in qrpe), 'RECONSIDER_REVIEW_ACTION_QRPE_OPEN')
    for q in qrpe:
        refs = q.get('resolutionEvidenceRefs')
        history = q.get('statusHistory', [])
        ensure((isinstance(refs, list) and refs and
                all(isinstance(ref, str) and ref.strip() for ref in refs))
               or (isinstance(history, list) and history and
                   history[-1].get('status') == q['status'] and
                   isinstance(history[-1].get('note'), str) and history[-1]['note'].strip()),
               'RECONSIDER_QRPE_RESOLUTION_NOT_EVIDENCED')
    # This verifies reference formats only. External evidence is NOT retrieved.


def apply(graph, operation):
    ensure(graph.get('actionModel') == 'candidate-v6',
           'RECONSIDER_REQUIRES_CANDIDATE_V6')
    nodes = {n['id']: n for n in graph['nodes']}
    old = nodes.get(operation.get('actionId'))
    review = nodes.get(operation.get('reviewActionId'))
    ensure(old and old.get('kind') == 'action' and old.get('status') == 'selected',
           'RECONSIDER_CURRENT_SELECTED_ACTION_REQUIRED')
    ensure(review and review.get('kind') == 'action' and review.get('status') == 'selected'
           and review is not old, 'RECONSIDER_SELECTED_REVIEW_ACTION_REQUIRED')
    driver = action_driver(graph, old['id'])
    ensure(action_driver(graph, review['id']) == driver,
           'RECONSIDER_REVIEW_ACTION_WRONG_DRIVER')
    ensure(review.get('selectionBasis', {}).get('actionSnapshot', {}).get('id') == review['id'],
           'RECONSIDER_REVIEW_T1_REQUIRED')
    ensure(not any(e['type'] == 'INTRODUCES' and e.get('from') == review['id'] and active(e)
                   for e in graph['edges']), 'RECONSIDER_REVIEW_ACTION_MUST_NOT_INTRODUCE_R')
    event = copy.deepcopy(operation.get('event'))
    ensure(isinstance(event, dict) and event.get('type') == 'action_reconsidered' and
           event.get('actionId') == old['id'] and
           event.get('reviewActionId') == review['id'] and
           event.get('driverRequirementId') == driver and
           event.get('by') == 'user' and isinstance(event.get('id'), str) and
           event['id'].strip() and isinstance(event.get('note'), str) and event['note'].strip() and
           isinstance(event.get('approvalRef'), str) and event['approvalRef'].strip() and
           isinstance(event.get('contextVersion'), str) and event['contextVersion'].strip() and
           event['id'] not in {e['id'] for e in graph['events']},
           'RECONSIDER_REQUIRES_EXPLICIT_USER_ATTRIBUTION_AND_APPROVAL_REF')
    ensure_assessment(review, event)
    if 'lensApplication' in event:
        binding = event['lensApplication']
        effect = binding.get('effectQrpe', {}) if isinstance(binding, dict) else {}
        ensure(isinstance(binding, dict) and binding.get('lensId') == 'L-MAINT' and
               binding.get('lensActionId') == 'A-L-MAINT-REVOKE' and
               binding.get('conditionalRequirementId') == 'R-L-MAINT-CHANGE' and
               binding.get('lensRootRequirementId') == 'R-L-MAINT' and
               binding.get('targetGraphId') == graph['id'] and
               binding.get('targetRevision') == graph['revision'] and
               isinstance(binding.get('definitionDigest'), str) and
               len(binding['definitionDigest']) == 64 and
               isinstance(effect, dict) and effect.get('questionId') == 'Q-MAINT-EFFECTS' and
               effect.get('status') in ('resolved', 'accepted-risk') and
               isinstance(effect.get('reason'), str) and effect['reason'].strip() and
               isinstance(effect.get('evidenceRefs'), list) and effect['evidenceRefs'],
               'RECONSIDER_LENS_EFFECT_QRPE_NOT_RESOLVED')
    introduced = [e for e in graph['edges'] if e.get('type') == 'INTRODUCES' and
                  e.get('from') == old['id'] and active(e)]
    dispositions = operation.get('dispositions')
    ensure(isinstance(dispositions, list) and len(dispositions) == len(introduced),
           'RECONSIDER_EXACT_CHILD_DISPOSITIONS_REQUIRED')
    child_map = {e['to']: e for e in introduced}
    ensure(len(child_map) == len(introduced), 'RECONSIDER_DUPLICATE_CHILD_INTRODUCTION')
    seen = set()
    for d in dispositions:
        ensure(isinstance(d, dict) and d.get('requirementId') in child_map and
               d['requirementId'] not in seen and
               d.get('effect') in ('retain_supported', 'deactivate') and
               isinstance(d.get('reason'), str) and d['reason'].strip(),
               'RECONSIDER_DISPOSITION_INVALID')
        seen.add(d['requirementId'])
        rid = d['requirementId']
        child = nodes[rid]
        ensure(child.get('kind') == 'requirement' and
               child.get('status', 'active') == 'active' and
               child.get('active') is not False and
               not child.get('projectionOf') and rid != graph['rootRequirementId'],
               'RECONSIDER_CHILD_SCOPE_NOT_OWNED_ACTIVE_R')
        supporters = [e['from'] for e in graph['edges'] if e.get('type') == 'INTRODUCES'
                      and e.get('to') == rid and e.get('from') != old['id'] and active(e)
                      and nodes[e['from']].get('kind') == 'action' and
                      nodes[e['from']].get('status') == 'selected']
        if d['effect'] == 'retain_supported':
            ensure(supporters, 'RECONSIDER_CHILD_HAS_NO_INDEPENDENT_SUPPORT')
            ensure(set(d.get('supportingActionIds', [])) == set(supporters),
                   'RECONSIDER_SUPPORTER_MISMATCH')
        else:
            ensure(not supporters, 'RECONSIDER_CANNOT_DEACTIVATE_SHARED_R')
            dependencies = [e for e in graph['edges'] if active(e) and
                            (e.get('from') == rid or (e.get('to') == rid and
                             e.get('type') != 'INTRODUCES'))]
            ensure(not dependencies, 'RECONSIDER_CHILD_HAS_DEPENDENCIES')
            ensure(d.get('downstreamScope') == 'single_graph_verified',
                   'RECONSIDER_DOWNSTREAM_SCOPE_UNVERIFIED')
    # Everything validated before graph mutations. Package/index validation later
    # detects cross-file references; cross-file deactivation requires a separate gate.
    event['priorActionSnapshot'] = copy.deepcopy(old)
    event['reviewActionSnapshot'] = copy.deepcopy(review)
    event['priorIntroductionEdges'] = copy.deepcopy(introduced)
    event['childDispositions'] = copy.deepcopy(dispositions)
    old['status'] = 'superseded'
    old['reconsideredByActionId'] = review['id']
    old['reconsiderationEventId'] = event['id']
    for edge in introduced:
        edge['archived'] = True
        edge['archivedByEventId'] = event['id']
    for d in dispositions:
        if d['effect'] == 'deactivate':
            child = nodes[d['requirementId']]
            child['status'] = 'inactive'
            child['deactivatedByActionId'] = review['id']
            child['deactivatedByEventId'] = event['id']
    graph['events'].append(event)
    return event


def validate_history(graph):
    if graph.get('actionModel') != 'candidate-v6':
        return
    nodes = {n['id']: n for n in graph['nodes']}
    for action in (n for n in nodes.values() if n['kind'] == 'action'):
        selected = [e for e in graph['events'] if e.get('type') == 'action_selected' and
                    e.get('actionId') == action['id']]
        if action.get('status') in ('selected', 'superseded'):
            ensure(len(selected) == 1, 'ACTION_SELECTION_HISTORY_MISSING_OR_DUPLICATE')
            driver = action_driver(graph, action['id'])
            ensure(selected[0].get('driverRequirementId') == driver,
                   'ACTION_SELECTION_HISTORY_WRONG_DRIVER')
            basis = action.get('selectionBasis')
            ensure(isinstance(basis, dict) and basis.get('actionSnapshot', {}).get('id') == action['id']
                   and basis['actionSnapshot'].get('status') == 'candidate' and
                   basis.get('driverSnapshot', {}).get('id') == driver,
                   'ACTION_SELECTION_T1_LOST')
        else:
            ensure(not selected, 'ACTION_CANDIDATE_HAS_SELECTION_EVENT')
        reconsidered = [e for e in graph['events'] if e.get('type') == 'action_reconsidered' and
                        e.get('actionId') == action['id']]
        if action.get('status') == 'superseded':
            ensure(len(reconsidered) == 1 and
                   action.get('reconsiderationEventId') == reconsidered[0]['id'] and
                   action.get('reconsideredByActionId') == reconsidered[0].get('reviewActionId'),
                   'ACTION_RECONSIDERATION_HISTORY_MISSING')
            event = reconsidered[0]
            expected = copy.deepcopy(action)
            expected['status'] = 'selected'
            for key in ('reconsideredByActionId', 'reconsiderationEventId', 'qrpe'):
                expected.pop(key, None)
            historical = copy.deepcopy(event.get('priorActionSnapshot'))
            ensure(isinstance(historical, dict), 'ACTION_RECONSIDERATION_PRIOR_SNAPSHOT_MISSING')
            historical.pop('qrpe', None)  # Later append-only QRPE changes are allowed.
            ensure(historical == expected,
                   'ACTION_RECONSIDERATION_PRIOR_SNAPSHOT_CHANGED')
            reviewer = nodes.get(event.get('reviewActionId'))
            ensure(reviewer and reviewer['kind'] == 'action' and
                   reviewer['status'] in ('selected', 'superseded') and
                   event.get('reviewActionSnapshot', {}).get('id') == reviewer['id'] and
                   event['reviewActionSnapshot'].get('status') == 'selected',
                   'ACTION_RECONSIDERATION_REVIEWER_HISTORY_MISSING')
            for snapshot in event.get('priorIntroductionEdges', []):
                matches = [edge for edge in graph['edges'] if edge.get('id') == snapshot.get('id')]
                ensure(len(matches) == 1, 'ACTION_RECONSIDERATION_EDGE_LOST')
                final = copy.deepcopy(matches[0])
                ensure(final.pop('archivedByEventId', None) == event['id'] and
                       final.pop('archived', None) is True and final == snapshot,
                       'ACTION_RECONSIDERATION_EDGE_HISTORY_CHANGED')
            ensure(all(e.get('archived') is True for e in graph['edges'] if
                       e.get('type') == 'INTRODUCES' and e.get('from') == action['id']),
                   'ACTION_RECONSIDERATION_ACTIVE_CHILD_LEFT_BEHIND')
        else:
            ensure(not reconsidered, 'ACTION_RECONSIDERATION_EVENT_STATUS_MISMATCH')
