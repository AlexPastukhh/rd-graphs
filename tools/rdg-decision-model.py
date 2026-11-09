#!/usr/bin/env python3
"""Pure kernel for the versioned RDG Decision profile.

This module deliberately does not import or mutate the legacy rdg-core-v1
kernel. The existing Application can dispatch by coreModel while preserving
legacy owners and their state machine.
"""
import copy
import hashlib
import json
import re
import uuid
from collections import defaultdict, deque
from pathlib import Path
from importlib.machinery import SourceFileLoader
import sys

POLICIES = SourceFileLoader("rdg_dependency_policies_v2", str(Path(__file__).with_name("rdg-dependency-policies.py"))).load_module()

FINDINGS = SourceFileLoader('rdg_findings', str(Path(__file__).with_name('rdg-findings.py'))).load_module()

ANALYSIS = SourceFileLoader('rdg_analysis', str(Path(__file__).with_name('rdg-analysis.py'))).load_module()

HISTORY = SourceFileLoader('rdg_history_view', str(Path(__file__).with_name('rdg-history-view.py'))).load_module()
QUESTIONS = SourceFileLoader('rdg_questions', str(Path(__file__).with_name('rdg-questions.py'))).load_module()

REFERENCES = SourceFileLoader('rdg_action_references', str(Path(__file__).with_name('rdg-portable-model.py'))).load_module()

PROFILE = 'rdg-decision-v1'
NODE_KINDS = frozenset(('requirement', 'decision', 'action'))
OBJECT_KINDS = frozenset(('canon', 'context', 'info', 'evidence', 'finding', 'question'))
ENTITY_KINDS = NODE_KINDS | OBJECT_KINDS
REVIEW_KINDS = NODE_KINDS | {'finding','question'}
RELATION_TYPES = frozenset(('DERIVES', 'INTRODUCES', 'DRIVES', 'REQUIRES_ACTION',
                             'CANON_FOR', 'CONTEXT_FOR', 'INFO_FOR', 'EVIDENCE_FOR', 'DEPENDS_ON', 'FINDING_RESPONSE', 'FINDING_PROPOSAL'))
DEPENDENCY_TYPES = frozenset(('DERIVES', 'INTRODUCES', 'DRIVES', 'REQUIRES_ACTION', 'DEPENDS_ON', 'FINDING_RESPONSE', 'FINDING_PROPOSAL'))
LOCK_OPERATIONS = frozenset(('edit', 'link', 'unlink', 'select', 'withdraw', 'complete',
                             'falsify', 'reopen', 'review', 'assess', 'remove',
                             'dependency_add', 'dependency_remove', 'lock_set', 'lock_remove'))
COMMANDS = frozenset(('add', 'edit', 'link', 'unlink', 'select', 'withdraw', 'complete',
                      'reopen', 'decision_group', 'root_cause', 'work_graph', 'review',
                      'lock_set', 'lock_remove', 'recommendation_packages', 'lens_application', 'remove', 'dependency_rule', 'policy_change', 'finding_disposition', 'finding_transfer', 'decision_context', 'context_group', 'requirement_decision', 'context_record', 'question_answer', 'question_assess', 'question_migrate'))
GRAPH_FIELDS = frozenset(('schemaVersion', 'actionModel', 'coreModel', 'id', 'title',
    'identitySpace', 'revision', 'rootRequirementId', 'rootCauses', 'nodes', 'objects',
    'externalActions', 'edges', 'decisionGroups', 'workGraphs', 'events', 'recommendationPackageIds'))
ENTITY_BASE_FIELDS = frozenset(('id', 'kind', 'title', 'description', 'revision', 'tags',
                                'policy', 'locks', 'review'))
RESULT_TYPES = {'requirement': 'requirement_achieved', 'decision': 'decision_completed',
                'action': 'action_executed'}
WORK_GRAPH_COLOR_KEYS = frozenset(('blue', 'teal', 'amber', 'violet', 'rose', 'lime', 'cyan', 'slate'))
EVENT_TYPES = frozenset(('created', 'edited', 'linked', 'unlinked', 'group_changed',
    'work_graph_changed', 'root_cause_changed', 'decision_selected', 'decision_unselected',
    'branch_cancelled', 'action_executed', 'requirement_achieved', 'decision_completed',
    'reopened', 'removed', 'lock_set', 'lock_removed', 'lens_application_recorded', 'policy_changed', 'binding_changed'))
RELATION_PAIRS = {
    'DERIVES': ({'requirement'}, {'requirement'}),
    'INTRODUCES': ({'decision'}, {'requirement'}),
    'DRIVES': ({'requirement'}, {'decision'}),
    'REQUIRES_ACTION': ({'requirement', 'decision'}, {'action'}),
    'CANON_FOR': ({'canon'}, {'requirement', 'decision', 'action'}),
    'CONTEXT_FOR': ({'context'}, {'requirement', 'decision', 'action'}),
    'INFO_FOR': ({'info'}, ENTITY_KINDS | OBJECT_KINDS),
    'EVIDENCE_FOR': ({'context','evidence'}, {'requirement', 'decision', 'action', 'context', 'finding'}),
    'FINDING_RESPONSE': (NODE_KINDS, {'decision'}),
    'FINDING_PROPOSAL': ({'decision'}, {'decision'}),
    'DEPENDS_ON': (ENTITY_KINDS, REVIEW_KINDS | {'context'}),
}


# Dependencies are typed subscriptions. Presets expand to immutable watch sets;
# legacy dependencyLevel L1/L2 is accepted unchanged and has identical effects.
DEPENDENCY_PRESETS = {
    'L1': ('definition',),
    'L2': ('definition', 'directScope'),
    'decision_state': ('selection', 'result'),
    'decision_context': ('definition', 'context'),
    'decision_canon': ('definition', 'canon'),
    'canon_criteria': ('definition',),
}
DEPENDENCY_WATCH = frozenset(('definition', 'directScope', 'selection', 'result', 'context', 'canon', 'info'))
DEPENDENCY_WATCH_PARTS = {'definition':'definition', 'directScope':'direct-scope',
    'selection':'selection', 'result':'result', 'context':'context', 'canon':'canon', 'info':'info','canonInfo':'info'}
STRUCTURAL_KINDS = frozenset(('DERIVES','DRIVES','INTRODUCES','REQUIRES_ACTION','DECISION_MEMBER','FINDING_RESPONSE','FINDING_PROPOSAL'))


def dependency_rule(relation):
    """Resolve saved custom rules and legacy L1/L2 edges without migration."""
    rule = relation.get('dependencyRule')
    if rule is not None:
        return rule
    level = relation.get('dependencyLevel', 'L1')
    return {'preset':level, 'watch':list(DEPENDENCY_PRESETS[level])}


def validate_dependency_rule(rule, kind):
    require(isinstance(rule,dict) and set(rule)=={'preset','watch'} and
            rule.get('preset') in (*DEPENDENCY_PRESETS,'custom') and
            unique_strings(rule.get('watch')) and bool(rule.get('watch')) and
            set(rule['watch']) <= DEPENDENCY_WATCH, 'DEPENDENCY_RULE_SCHEMA')
    if rule['preset'] != 'custom':
        # A modified preset is represented by the original name plus an exact
        # frozen selection of watch features; its meaning never drifts later.
        require(len(rule['watch']) <= len(DEPENDENCY_WATCH), 'DEPENDENCY_RULE_SCHEMA')
    if any(w in rule['watch'] for w in ('selection','result','context','canon')):
        require(kind=='decision', 'DEPENDENCY_RULE_SOURCE_KIND')
    if 'info' in rule['watch']:
        require(kind in ('canon','decision'), 'DEPENDENCY_RULE_SOURCE_KIND')
    if rule['preset'].startswith('decision_'):
        require(kind=='decision', 'DEPENDENCY_RULE_SOURCE_KIND')
    if rule['preset']=='canon_criteria':
        require(kind=='canon', 'DEPENDENCY_RULE_SOURCE_KIND')



# Graph-local, immutable-version policy catalog. Legacy DEPENDS_ON and structural
# subscriptions are kept as-is. New bindings add conditions to the SAME evaluator.
POLICY_PATTERNS = frozenset(('direct', 'parentDecisionContext', 'roles'))
POLICY_OPERATIONS = frozenset(('changed', 'added', 'removed'))
POLICY_STATUSES = frozenset(('active', 'disabled', 'archived'))
POLICY_SOURCE_KINDS = frozenset(('requirement', 'decision', 'action', 'context', 'canon', 'info'))


def _policy_versions(g, policy_id):
    return sorted([p for p in g.get('dependencyPolicies',[]) if p['id']==policy_id],
                  key=lambda p:p['version'])


def _policy_at(g, policy_id, version):
    return next((p for p in g.get('dependencyPolicies',[]) + POLICIES.builtins(sys.modules[__name__]) if
                 p['id']==policy_id and p['version']==version),None)


def _structural_decision_parent(g, parent_id, target_id):
    return any(e['from']==parent_id and e['to']==target_id and
        e['type'] in ('INTRODUCES','REQUIRES_ACTION') for e in g['edges'])


def dependency_capabilities():
    return POLICIES.capabilities(sys.modules[__name__])


def validate_policy_definitions(definitions):
    return POLICIES.validate_catalog(definitions, sys.modules[__name__])


def validate_policy_catalog(g):
    K=sys.modules[__name__]
    validate_policy_definitions(g.get('dependencyPolicies',[]))
    preset_ids=set()
    for pre in g.get('dependencyPresets',[]):
        require(isinstance(pre,dict) and set(pre)=={'id','name','sourceKinds','watch','operations'} and
            text(pre.get('id')) and text(pre.get('name')) and pre['id'] not in preset_ids and
            unique_strings(pre.get('sourceKinds')) and bool(pre['sourceKinds']) and
            set(pre['sourceKinds'])<=POLICY_SOURCE_KINDS and unique_strings(pre.get('watch')) and
            bool(pre['watch']) and set(pre['watch'])<=DEPENDENCY_WATCH and
            unique_strings(pre.get('operations')) and bool(pre['operations']) and
            set(pre['operations'])<=POLICY_OPERATIONS,'POLICY_PRESET_SCHEMA')
        preset_ids.add(pre['id'])
        for kind in pre['sourceKinds']:validate_dependency_rule({'preset':'custom','watch':pre['watch']},kind)
        if not any(w in ('directScope','context','canon','info') for w in pre['watch']):
            require(pre['operations']==['changed'],'POLICY_PRESET_OPERATION_WATCH')
    ids=set();keys=set()
    for b in g.get('dependencyBindings',[]):
        require(isinstance(b,dict),'POLICY_BINDING_SCHEMA')
        p=_policy_at(g,b.get('policyId'),b.get('policyVersion'))
        require(p is not None,'POLICY_BINDING_POLICY')
        POLICIES.binding_valid(b,p,K)
        require(b['id'] not in ids,'POLICY_BINDING_DUPLICATE');ids.add(b['id'])
        key=(b['policyId'],b['policyVersion'],b['targetId'],b['sourceId'],b['parentId'],
             json.dumps(b.get('participantBindings',{}),sort_keys=True))
        if b.get('status')!='deleted':
            require(key not in keys,'POLICY_BINDING_DUPLICATE');keys.add(key)
        # Disabled applications may reference removed historical participants.
        if b['enabled']:
            _,_,problems=POLICIES.resolve(g,p,b,K)
            require(not problems,'POLICY_BINDING_INAPPLICABLE:'+','.join(problems))


def _projection_item_index(value, part):
    if part=='directScope':
        return {str(x['id']):x for x in value or []}
    if part=='context':return {str(x['sourceId']):x for x in value or []}
    if part=='canon':return {str(x['canonId']):x for x in value or []}
    if part=='info':return {str(x['infoId']):x for x in value or []}
    return {}


def _policy_part_differences(before,after,src,part,cosmetic_ids):
    rule={'preset':'custom','watch':[part]}
    prior=_effective_observable(before,src,rule,cosmetic_ids) if src in entities(before) else None
    current=_effective_observable(after,src,rule,cosmetic_ids) if src in entities(after) else None
    b=prior.get(part) if prior else None;a=current.get(part) if current else None
    if b==a:return []
    if part in ('directScope','context','canon','info'):
        bi=_projection_item_index(b,part);ai=_projection_item_index(a,part)
        differences=([('added',i) for i in sorted(set(ai)-set(bi))]+
                     [('removed',i) for i in sorted(set(bi)-set(ai))]+
                     [('changed',i) for i in sorted(set(ai)&set(bi)) if ai[i]!=bi[i]])
        result=[]
        for operation,key in differences:
            record=ai.get(key) or bi.get(key)
            # The projection is indexed by relation ID to preserve distinct
            # edges. Its endpoint is the actual semantic participant and must
            # not be confused with the relation ID in trigger evidence.
            participant=(record.get('endpoint') or record.get('sourceId') or
                         record.get('canonId') or record.get('infoId') or
                         record.get('id') or src)
            relation=record.get('edgeId') or (record.get('id') if part=='directScope' else None)
            result.append((operation,participant,relation))
        return result
    return [('changed',src,None)]


def policy_binding_impacts(before,after,cosmetic_ids=(),event=None):
    rows=[];bs={b['id']:b for b in before.get('dependencyBindings',[])}
    aas={b['id']:b for b in after.get('dependencyBindings',[])}
    for bid in sorted(set(bs)|set(aas)):
        old=bs.get(bid);new=aas.get(bid);binding=new or old
        if not binding.get('enabled') or binding['targetId'] not in entities(after) or binding['targetId'] not in entities(before):continue
        policy=_policy_at(after,binding['policyId'],binding['policyVersion']) or _policy_at(before,binding['policyId'],binding['policyVersion'])
        if not policy:continue
        if not (old and new and old.get('enabled') and new.get('enabled')):continue
        semantic=lambda value:{k:v for k,v in value.items() if k not in ('revision','status','reasonCode')}
        if semantic(old)!=semantic(new):continue
        if policy['status']=='disabled':continue
        if policy['pattern']=='roles' or policy['pattern']=='direct' and any(r['watch'] not in DEPENDENCY_WATCH for r in policy['rules']):
            rows.extend(POLICIES.role_impacts(before,after,policy,binding,sys.modules[__name__],cosmetic_ids,event))
            continue
        for rule in policy['rules']:
            if not rule['enabled']:continue
            watched=rule['watch']
            if policy['pattern']=='direct':
                source=binding['sourceId']
                diffs=_policy_part_differences(before,after,source,watched,cosmetic_ids)
                for op,member,relation in diffs:
                    if op not in rule['operations']:continue
                    rows.append({'edgeId':'binding:'+bid,'sourceId':source,'dependentId':binding['targetId'],
                        'level':'custom','changedParts':[DEPENDENCY_WATCH_PARTS[watched]],
                        'origin':'policy','policyId':policy['id'],'policyVersion':policy['version'],
                        'policyName':policy['name'],'ruleId':rule['id'],'ruleName':rule['name'],
                        'bindingId':bid,'triggerOperation':op,
                        'matchedParticipants':{'sourceId':source,'targetId':binding['targetId'],
                            **({'memberId':member} if member!=source else {})},
                        'matchedRelations':[relation] if relation else []})
            else:
                parent=binding['parentId']
                if not (_structural_decision_parent(before,parent,binding['targetId']) and
                        _structural_decision_parent(after,parent,binding['targetId'])):
                    continue
                pre=_context_sources(before,parent);post=_context_sources(after,parent)
                prior={r['sourceId']:r['projection'] for r in pre};cur={r['sourceId']:r['projection'] for r in post}
                operations=([('added',i) for i in sorted(set(cur)-set(prior))]+
                    [('removed',i) for i in sorted(set(prior)-set(cur))]+
                    [('changed',i) for i in sorted(set(cur)&set(prior)) if
                        _policy_part_differences(before,after,i,'definition',cosmetic_ids)])
                for op,member in operations:
                    if op not in rule['operations']:continue
                    membership_edges=[e['id'] for e in after['edges']+before['edges'] if e['type']=='DEPENDS_ON' and
                        e.get('dependencyPurpose')=='decisionContext' and e['from']==member and e['to']==parent]
                    membership_edges=sorted(set(membership_edges))
                    parent_edges=[e['id'] for e in after['edges'] if e['from']==parent and e['to']==binding['targetId'] and
                                  e['type'] in ('INTRODUCES','REQUIRES_ACTION')]
                    rows.append({'edgeId':'binding:'+bid,'sourceId':member,'dependentId':binding['targetId'],
                        'level':'custom','changedParts':['context'],'origin':'policy',
                        'policyId':policy['id'],'policyVersion':policy['version'],
                        'policyName':policy['name'],'ruleId':rule['id'],'ruleName':rule['name'],
                        'bindingId':bid,'triggerOperation':op,
                        'matchedParticipants':{'sourceId':member,'contextId':member,'parentId':parent,
                                               'targetId':binding['targetId']},
                        'matchedRelations':sorted(set(parent_edges+membership_edges))})
    for hit in rows:
        if 'ruleSnapshot' not in hit:
            p=_policy_at(after,hit['policyId'],hit['policyVersion']) or _policy_at(before,hit['policyId'],hit['policyVersion'])
            hit['ruleSnapshot']=copy.deepcopy(next(r for r in p['rules'] if r['id']==hit['ruleId']))
            hit['participantSnapshot']={i:{'id':i,'kind':n['kind'],'title':n['title']} for i in set(hit['matchedParticipants'].values()) if (n:=(entities(after).get(i) or entities(before).get(i)))}
    return rows


def require(ok, code):
    if not ok:
        normalized = {'SCHEMA_INVALID', 'RESULT_EVIDENCE_REQUIRED',
                      'ACTION_OUTCOME_REQUIRED', 'ACTION_OUTCOME_NOT_ALLOWED',
                      'ACTION_TARGETS_INVALID', 'INITIAL_RELATION_UNRELATED',
                      'RELATION_ENDPOINT_TYPES', 'REFERENCE_MISSING', 'ENTITY_ID_CONFLICT',
                      'NO_ACTIVE_BASIS', 'REVIEW_REQUIRED', 'NO_CHANGE',
                      'OPERATION_RECORD_ONLY', 'OBLIGATIONS_OPEN'}
        prefix = code.split(':', 1)[0]
        raise ValueError(code if prefix in normalized or code.startswith('DECISION_')
                         else 'DECISION_' + code)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def unique_strings(value):
    return isinstance(value, list) and all(text(x) for x in value) and len(value) == len(set(value))


def _uuid(value):
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError, TypeError):
        return False


def entities(g):
    """All owner-scoped identities; external Actions share IDs but not canvas scope."""
    cache = ANALYSIS.active_read_cache(g)
    if cache is not None and "scopedImmutableEntities" in cache:
        return cache["scopedImmutableEntities"]
    result = {n['id']: n for n in [*g.get('nodes', []), *g.get('objects', []), *g.get('externalActions', [])]}
    if cache is not None and cache.get('scopedImmutableEntityMode'):
        cache['scopedImmutableEntities'] = result
    return result


def active_edges(g):
    # Decision v1 relations are removed through explicit unlink, never soft-archived.
    return list(g.get('edges', []))


def decision_memberships(g):
    return [{'id': member['id'], 'type': 'DECISION_MEMBER', 'from': group['parentId'],
             'to': member['decisionId'], 'groupId': group['id']}
            for group in g.get('decisionGroups', []) for member in group['members']]


def blank(ident, title, space, root, root_title, scope='Explicit working scope',
          root_reason='Explicit primary reason for this process'):
    require(text(root_reason), 'ROOT_REASON_REQUIRED')
    return {
        'schemaVersion': 1, 'actionModel': 'candidate-v6', 'coreModel': PROFILE,
        'id': ident, 'title': title, 'identitySpace': space, 'revision': 1,
        'rootRequirementId': root,
        'rootCauses': [{'id': 'RC1', 'requirementId': root, 'reason': root_reason, 'enabled': True}],
        'nodes': [{'id': root, 'kind': 'requirement', 'title': root_title,
                   'description': root_title, 'scope': scope, 'revision': 1,
                   'result': {'state': 'open', 'truth': 'unknown'}}],
        'objects': [], 'externalActions': [], 'edges': [], 'decisionGroups': [],
        'workGraphs': [],
        'events': [], 'recommendationPackageIds': [],
        'dependencyPolicies': [], 'dependencyBindings': [], 'dependencyPresets': []
    }


def _validate_policy(n):
    if 'policy' in n:
        p = n['policy']
        require(isinstance(p, dict) and set(p) <= {'mode', 'authorityPrincipal'} and
                p.get('mode') in ('ordinary', 'stable', 'protected') and
                (p['mode'] != 'protected' or text(p.get('authorityPrincipal'))), 'POLICY')
    if 'locks' in n:
        locks = n['locks']
        require(isinstance(locks, dict), 'LOCKS')
        for operation, spec in locks.items():
            require(operation in LOCK_OPERATIONS and isinstance(spec, dict) and
                    set(spec) == {'mode', 'principals', 'message'} and
                    spec.get('mode') in ('warning', 'hard') and unique_strings(spec.get('principals')) and
                    text(spec.get('message')) and (spec['mode'] != 'hard' or bool(spec['principals'])), 'LOCK_SPEC')
    if 'review' in n:
        r = n['review']
        require(isinstance(r, dict) and set(r) == {'required', 'causeEventIds', 'pins'} and
                isinstance(r.get('required'), bool) and unique_strings(r.get('causeEventIds')) and
                isinstance(r.get('pins'), list), 'REVIEW')


def validate_estimates(value):
    import math
    require(isinstance(value,dict) and set(value)<={'complexity','time','basis'} and
            bool({'complexity','time'} & set(value)), 'ACTION_ESTIMATES')
    for key in ('complexity','basis'):
        if key in value:require(text(value[key]), 'ACTION_ESTIMATES')
    if 'time' in value:
        row=value['time']
        require(isinstance(row,dict) and set(row)=={'minSeconds','maxSeconds'} and
                all(type(row[k]) in (int,float) and 0<=row[k]<=1.7976931348623157e308 and math.isfinite(row[k])
                    for k in row) and row['minSeconds']<=row['maxSeconds'], 'ACTION_ESTIMATES_TIME')


def validate_theory(n):
    # Keep the legacy General text in place. Reading never normalizes an owner.
    require(isinstance(n.get('guidance'), str), 'CANON_GUIDANCE')
    require('canons' not in n or isinstance(n['canons'], str), 'THEORY_CANONS')
    rows = n.get('knownErrors', [])
    require(isinstance(rows, list), 'THEORY_KNOWN_ERRORS')
    seen = set()
    for row in rows:
        require(isinstance(row, dict) and set(row) == {'id', 'title', 'description'} and
                text(row.get('id')) and text(row.get('title')) and
                isinstance(row.get('description'), str), 'THEORY_KNOWN_ERROR')
        require(row['id'] not in seen, 'THEORY_ERROR_ID_DUPLICATE')
        seen.add(row['id'])
    require(text(n['guidance']) or text(n.get('canons')) or bool(rows), 'CANON_GUIDANCE')


def _validate_entity(n, expected_kind, events):
    require(isinstance(n, dict) and n.get('kind') == expected_kind and text(n.get('id')) and
            text(n.get('title')) and isinstance(n.get('description'), str) and
            type(n.get('revision')) is int and n['revision'] >= 1, 'ENTITY')
    fields = set(ENTITY_BASE_FIELDS)
    if expected_kind in ('finding', 'decision'):fields |= FINDINGS.COMMON
    specific = {
        'requirement': {'scope', 'result'},
        'decision': {'selectionState', 'result', 'decisionContextIds', 'contextNotes', 'analysisSources', 'findingOrigin', 'impactTargetIds'},
        'action': {'result', 'actionType', 'lowLevel', 'targetIds', 'groupIds', 'estimates', 'resultCondition', 'subjectRefs', 'referenceBindings'},
        'canon': {'guidance', 'canons', 'knownErrors'}, 'context': {'value','contextGroupId','scope','version','source','artifact'}, 'info': {'value'},
        'evidence': {'claim', 'scope', 'version', 'source', 'artifact'}, 'finding': FINDINGS.FIELDS,
        'question': {'relatedRefs','sourceRefs','impact','answerCondition','blocking','answers','answerHistory','assessment','assessmentHistory','assessmentReviewRequired','referenceBindings'}
    }[expected_kind]
    fields |= specific
    required = {'id', 'kind', 'title', 'description', 'revision'} | {
        'requirement': {'result', 'scope'},
        'decision': {'result', 'selectionState'},
        'action': {'result', 'actionType', 'lowLevel', 'targetIds', 'groupIds'},
        'canon': {'guidance'}, 'context': {'value'}, 'info': {'value'},
        'evidence': {'claim', 'scope', 'version', 'source'}, 'finding': {'subjectId','subjectSnapshot','findingType','rationale','evidenceIds','disposition','dispositionHistory'},
        'question': {'relatedRefs','sourceRefs','impact','answerCondition','answers','assessmentHistory','assessmentReviewRequired'}
    }[expected_kind]
    require(set(n) <= fields and required <= set(n), 'ENTITY_FIELDS')
    if 'tags' in n:
        require(unique_strings(n['tags']), 'TAGS')
    _validate_policy(n)
    if expected_kind in ('finding','decision'):FINDINGS.validate_extras(n,sys.modules[__name__])
    if expected_kind=='decision' and 'findingOrigin' in n:
        origin=n['findingOrigin'];require(isinstance(origin,dict) and {'findingId','subjectId','title','role'}<=set(origin)<={'findingId','subjectId','title','role','recordedOnly'} and all(text(origin.get(k)) for k in ('findingId','subjectId','title')) and origin.get('role') in ('response','proposal') and type(origin.get('recordedOnly',False)) is bool,'FINDING_ORIGIN')
    if expected_kind == 'finding':FINDINGS.validate_entity(n,sys.modules[__name__])
    if expected_kind == 'requirement':
        require(text(n.get('scope')), 'REQUIREMENT_SCOPE')
    elif expected_kind == 'decision':
        require(n.get('selectionState') in ('discovered', 'unselected', 'selected'), 'DECISION_SELECTION_STATE')
        if 'decisionContextIds' in n:require(unique_strings(n['decisionContextIds']), 'DECISION_CONTEXT_REFS')
    elif expected_kind == 'action':
        require('resultCondition' not in n or isinstance(n['resultCondition'],str),'ACTION_RESULT_CONDITION')
        if 'subjectRefs' in n:
            require(n.get('actionType')=='task' and n.get('lowLevel') is False and isinstance(n['subjectRefs'],list),'ACTION_SUBJECTS')
            for ref in n['subjectRefs']:REFERENCES.validate_reference(ref,allow_scope=True)
            require(len({json.dumps(r,sort_keys=True) for r in n['subjectRefs']})==len(n['subjectRefs']),'ACTION_SUBJECT_DUPLICATE')
            require(isinstance(n.get('referenceBindings',{}),dict) and all(text(k) and text(v) for k,v in n.get('referenceBindings',{}).items()),'ACTION_REF_BINDINGS')
        if 'estimates' in n:
            validate_estimates(n['estimates'])
            require(n.get('actionType')=='task' or n.get('lowLevel') is False,'ACTION_ESTIMATES_ROLE')
        require(n.get('actionType') in ('task', 'select_decision', 'decide_acceptance',
                'discover_requirement', 'discover_decision', 'rename_block') and
                isinstance(n.get('lowLevel'), bool) and unique_strings(n.get('targetIds')) and
                unique_strings(n.get('groupIds')), 'ACTION_FIELDS')
    elif expected_kind == 'canon':
        validate_theory(n)
    elif expected_kind in ('context', 'info'):
        require(text(n.get('value')), 'OBJECT_VALUE')
    if expected_kind == 'context':
        require(all(isinstance(n[k],str) for k in ('scope','version','source') if k in n),'CONTEXT_SOURCE_FIELDS')
    if expected_kind in ('context','evidence'):
        if expected_kind=='evidence':require(all(text(n.get(k)) for k in ('claim', 'scope', 'version', 'source')), 'EVIDENCE_FIELDS')
        if 'artifact' in n:
            a = n['artifact']
            require(isinstance(a, dict) and set(a) == {'path', 'sha256'} and text(a.get('path')) and
                    re.fullmatch('[0-9a-f]{64}', a.get('sha256', '')) is not None, 'EVIDENCE_ARTIFACT')
    if expected_kind in ('requirement', 'decision', 'action'):
        result = n['result']
        require(isinstance(result, dict) and set(result) <= {'state', 'truth', 'eventId'} and
                result.get('state') in ('open', 'confirmed') and
                result.get('truth') in (('true', 'false', 'unknown') if expected_kind == 'requirement'
                                        else ('true', 'unknown')) and
                ((result['state'] == 'confirmed') == (result['truth'] == 'true')), 'RESULT')
        if result['state'] == 'confirmed':
            ev = events.get(result.get('eventId'))
            require(ev is not None and ev.get('type') == RESULT_TYPES[expected_kind] and
                    n['id'] in ev.get('nodeIds', []), 'RESULT_EVENT_REQUIRED')
    if expected_kind == 'action' and n.get('lowLevel') is False:
        require(n['actionType'] in ('task', 'select_decision', 'decide_acceptance'), 'GRAPH_ACTION_TYPE')


def _validate_event(ev):
    allowed = {'id', 'type', 'transactionId', 'recordedAt', 'by', 'nodeIds', 'basis',
               'evidenceIds', 'placementIds', 'observedPins', 'operationActionId',
               'recommendationPins', 'lensPins', 'actionResult', 'relationIds', 'lockWarnings',
               'workGraphChange', 'dependencyImpacts', 'dependencyTransitions', 'reviewResolutions', 'findingChange','historyDetail'}
    require(isinstance(ev, dict) and set(ev) <= allowed and
            {'id', 'type', 'transactionId', 'recordedAt', 'by', 'nodeIds', 'basis'} <= set(ev) and
            _uuid(ev.get('id')) and _uuid(ev.get('transactionId')) and ev.get('type') in EVENT_TYPES and
            isinstance(ev.get('recordedAt'), str) and re.search(r'(?:Z|[+-]\d{2}:\d{2})$', ev['recordedAt']) and
            ev.get('by') in ('user', 'assistant') and unique_strings(ev.get('nodeIds')) and text(ev.get('basis')), 'EVENT')
    if 'historyDetail' in ev:HISTORY.validate(ev['historyDetail'],sys.modules[__name__])
    for key in ('evidenceIds', 'placementIds', 'relationIds'):
        if key in ev:
            require(unique_strings(ev[key]), 'EVENT_' + key.upper())
    if 'observedPins' in ev:
        require(isinstance(ev['observedPins'], list) and all(isinstance(ref, dict) and
                set(ref) == {'schemaVersion','packageId','identitySpace','nodeId','mode',
                             'revision','graphRevision','sha256'} and
                ref['schemaVersion'] == 1 and _uuid(ref['packageId']) and
                _uuid(ref['identitySpace']) and text(ref['nodeId']) and
                ref['mode'] == 'historical' and type(ref['revision']) is int and
                ref['revision'] >= 1 and type(ref['graphRevision']) is int and
                ref['graphRevision'] >= 1 and isinstance(ref['sha256'], str) and
                re.fullmatch('[0-9a-f]{64}', ref['sha256']) for ref in ev['observedPins']) and
                len({r['nodeId'] for r in ev['observedPins']}) == len(ev['observedPins']),
                'EVENT_OBSERVED_PINS')
    for name in ('recommendationPins','lensPins'):
        if name in ev:
            require(isinstance(ev[name],list),'EVENT_PINS')
            for pin in ev[name]:
                if name=='lensPins':require(_valid_pin(pin),'EVENT_LENS_PIN')
                else:require(isinstance(pin,dict) and set(pin)=={'packageId','revision','sha256'} and _uuid(pin['packageId']) and type(pin['revision']) is int and pin['revision']>=1 and isinstance(pin['sha256'],str) and re.fullmatch('[0-9a-f]{64}',pin['sha256']) is not None,'EVENT_RECOMMENDATION_PIN')
    if 'lockWarnings' in ev:
        require(isinstance(ev['lockWarnings'], list) and all(isinstance(w, dict) and
                set(w) == {'nodeId', 'operation', 'message'} and text(w['nodeId']) and
                w['operation'] in LOCK_OPERATIONS and text(w['message']) for w in ev['lockWarnings']) and
                len({(w['nodeId'], w['operation'], w['message']) for w in ev['lockWarnings']}) == len(ev['lockWarnings']),
                'EVENT_LOCK_WARNINGS')
    if 'actionResult' in ev:
        result = ev['actionResult']
        require(isinstance(result, dict) and set(result) == {'decisionId', 'decisionOutcome'} and
                text(result.get('decisionId')) and result.get('decisionOutcome') in ('selected', 'unselected') and
                ev.get('type') == 'action_executed' and text(ev.get('operationActionId')), 'ACTION_RESULT_EVENT')
    if 'dependencyImpacts' in ev:
        impacts=ev['dependencyImpacts']
        require(isinstance(impacts,list) and all(isinstance(row,dict) and
            {'edgeId','sourceId','dependentId','level','changedParts'} <= set(row) <=
            {'edgeId','sourceId','dependentId','level','changedParts','origin','preset','viaIds',
             'policyId','policyVersion','policyName','ruleId','ruleName','bindingId',
             'triggerOperation','matchedParticipants','matchedRelations','ruleSnapshot','participantSnapshot','valueSnapshot'} and
            all(text(row[k]) for k in ('edgeId','sourceId','dependentId')) and
            row['level'] in ('L1','L2','custom') and
            (('origin' not in row) or row['origin'] in ('structural','manual','decisionContext','canon','policy','finding-subject')) and
            (('preset' not in row) or text(row['preset'])) and
            (('viaIds' not in row) or unique_strings(row['viaIds'])) and
            ('policyId' not in row or (all(text(row.get(x)) for x in ('policyId','policyName','ruleId','ruleName','bindingId')) and
                type(row.get('policyVersion')) is int and row['policyVersion']>=1 and
                row.get('triggerOperation') in POLICY_OPERATIONS and
                isinstance(row.get('matchedParticipants'),dict) and
                all(text(v) for v in row['matchedParticipants'].values()) and
                unique_strings(row.get('matchedRelations')))) and
            isinstance(row['changedParts'],list) and bool(row['changedParts']) and
            all(p in ('definition','direct-scope','source-removed','source-added','selection',
                      'result','context','canon','info','structure','basis')
              for p in row['changedParts']) for row in impacts), 'EVENT_DEPENDENCY_IMPACTS')
    if 'reviewResolutions' in ev:
        require(isinstance(ev['reviewResolutions'],list) and all(isinstance(r,dict) and
            set(r)=={'nodeId','causeEventIds'} and text(r['nodeId']) and unique_strings(r['causeEventIds'])
            for r in ev['reviewResolutions']), 'EVENT_REVIEW_RESOLUTIONS')
    if 'dependencyTransitions' in ev:
        require(isinstance(ev['dependencyTransitions'],list) and all(
            isinstance(t,dict) and {'bindingId','policyId','policyVersion','policyName','from','to','reasonCode','violations','participants','relations'}<=set(t)<=
            {'bindingId','policyId','policyVersion','policyName','from','to','reasonCode','violations','participants','relations','targetId','participantRoles','relationSnapshot'}
            and text(t['bindingId']) and text(t['policyId']) and type(t['policyVersion']) is int
            and t['from'] in ('active','disabled') and t['to'] in ('active','disabled','deleted')
            and isinstance(t['violations'],list) and isinstance(t['participants'],dict)
            and unique_strings(t['relations']) and ('targetId' not in t or text(t['targetId']))
            and ('participantRoles' not in t or isinstance(t['participantRoles'],dict) and all(text(k) and unique_strings(v) for k,v in t['participantRoles'].items()))
            and ('relationSnapshot' not in t or isinstance(t['relationSnapshot'],list) and all(isinstance(r,dict) and text(r.get('id')) for r in t['relationSnapshot']))
            for t in ev['dependencyTransitions']), 'EVENT_DEPENDENCY_TRANSITIONS')
    if 'workGraphChange' in ev:
        change = ev['workGraphChange']
        require(ev.get('type') == 'work_graph_changed' and isinstance(change, dict) and
                set(change) == {'action', 'workGraphId', 'title', 'before', 'after'} and
                change.get('action') in ('created', 'updated') and text(change.get('workGraphId')) and
                text(change.get('title')), 'EVENT_WORK_GRAPH_CHANGE')
        require((change['action'] == 'created' and change['before'] is None) or
                (change['action'] == 'updated' and isinstance(change['before'], dict)),
                'EVENT_WORK_GRAPH_BEFORE')
        for name in ('before', 'after'):
            value = change[name]
            if value is None:
                require(name == 'before' and change['action'] == 'created', 'EVENT_WORK_GRAPH_SNAPSHOT')
                continue
            require(isinstance(value, dict) and
                    {'title', 'rootIds', 'memberIds'} <= set(value) <=
                    {'title', 'rootIds', 'memberIds', 'colorKey'} and text(value.get('title')) and
                    unique_strings(value.get('rootIds')) and unique_strings(value.get('memberIds')) and
                    set(value['rootIds']) <= set(value['memberIds']) and
                    ('colorKey' not in value or value['colorKey'] in WORK_GRAPH_COLOR_KEYS),
                    'EVENT_WORK_GRAPH_SNAPSHOT')
        require(change['after']['title'] == change['title'], 'EVENT_WORK_GRAPH_TITLE')


def _relation_error(relation, ns, groups=None):
    require(isinstance(relation, dict) and set(relation) <=
            {'id', 'type', 'from', 'to', 'dependencyLevel', 'dependencyRule', 'dependencyPurpose', 'findingId'} and
            {'id', 'type', 'from', 'to'} <= set(relation) and text(relation.get('id')) and
            relation.get('type') in RELATION_TYPES and relation.get('from') in ns and
            relation.get('to') in ns and relation['from'] != relation['to'], 'RELATION')
    source, target = ns[relation['from']]['kind'], ns[relation['to']]['kind']
    allowed_source, allowed_target = RELATION_PAIRS[relation['type']]
    require(source in allowed_source and target in allowed_target, 'RELATION_ENDPOINT_TYPES')
    require(not (source == 'decision' and target == 'decision' and
                 relation['type'] not in ('DEPENDS_ON','FINDING_RESPONSE','FINDING_PROPOSAL')), 'DECISION_TO_DECISION_FORBIDDEN')
    require(('findingId' in relation) == (relation['type'] in FINDINGS.RELATIONS), 'FINDING_RELATION_FIELDS')
    if relation['type'] == 'DEPENDS_ON':
        require(('dependencyLevel' in relation) != ('dependencyRule' in relation),
                'DEPENDENCY_RULE_OR_LEVEL_REQUIRED')
        if 'dependencyLevel' in relation:
            require(relation['dependencyLevel'] in ('L1','L2'), 'DEPENDENCY_LEVEL_REQUIRED')
        else:
            validate_dependency_rule(relation['dependencyRule'],source)
        if 'dependencyPurpose' in relation:
            require(relation['dependencyPurpose']=='decisionContext' and target=='decision',
                    'DEPENDENCY_PURPOSE')
    else:
        require(not ({'dependencyLevel','dependencyRule','dependencyPurpose'} & set(relation)),
                'DEPENDENCY_RULE_UNEXPECTED')


def _selected_conflicts(g, decision_ids):
    ns = entities(g)
    chosen = set(decision_ids)
    for group in g['decisionGroups']:
        if not group['mutuallyExclusive']:
            continue
        members = {m['decisionId'] for m in group['members']}
        selected = {i for i in members if ns[i]['selectionState'] == 'selected'} | (members & chosen)
        require(len(selected) <= 1, 'DECISION_GROUP_CONFLICT')


def _has_parent_basis(g, decision_id, active=None):
    active = set(active if active is not None else support_state(g)['activeIds'])
    ns = entities(g)
    if any(e['type'] in ('DRIVES','FINDING_RESPONSE','FINDING_PROPOSAL') and e['to'] == decision_id and e['from'] in active
           for e in active_edges(g)):
        return True
    return any(group['parentId'] in active and any(m['decisionId'] == decision_id for m in group['members'])
               for group in g['decisionGroups'])


def support_state(g):
    """Least fixed point of enabled roots and selected composition, not graph reachability."""
    ns = entities(g); edges = active_edges(g); active = set(); basis = defaultdict(set); queue = deque()
    def add(ident, cause):
        if ident not in active:
            active.add(ident); queue.append(ident)
        basis[ident].add(cause)
    for cause in g.get('rootCauses', []):
        if cause['enabled']:
            add(cause['requirementId'], 'rootCause:' + cause['id'])
    memberships_by_parent = defaultdict(set)
    for group in g.get('decisionGroups', []):
        for member in group['members']:
            memberships_by_parent[group['parentId']].add(member['decisionId'])
    while queue:
        ident = queue.popleft(); node = ns[ident]
        if node['kind'] == 'requirement':
            for edge in edges:
                if edge['from'] != ident:
                    continue
                if edge['type'] in ('DERIVES', 'REQUIRES_ACTION'):
                    add(edge['to'], 'relation:' + edge['id'])
                elif edge['type'] in ('DRIVES','FINDING_RESPONSE') and ns[edge['to']]['selectionState'] == 'selected':
                    add(edge['to'], 'relation:' + edge['id'])
            for decision_id in memberships_by_parent.get(ident, set()):
                if ns[decision_id]['selectionState'] == 'selected':
                    add(decision_id, 'membership:' + ident + ':' + decision_id)
        elif node['kind'] == 'decision' and node['selectionState'] == 'selected':
            for edge in edges:
                if edge['from'] != ident:continue
                if edge['type'] in ('INTRODUCES','REQUIRES_ACTION') or (edge['type'] in FINDINGS.RELATIONS and ns[edge['to']]['selectionState']=='selected'):
                    add(edge['to'], 'relation:' + edge['id'])
            for decision_id in memberships_by_parent.get(ident,set()):
                if ns[decision_id]['selectionState']=='selected':add(decision_id,'membership:'+ident+':'+decision_id)
        elif node['kind']=='action':
            for edge in edges:
                if edge['from']==ident and edge['type']=='FINDING_RESPONSE' and ns[edge['to']]['selectionState']=='selected':add(edge['to'],'relation:'+edge['id'])
    return {'activeIds': sorted(active), 'basisById': {i: sorted(v) for i, v in basis.items()}}


def group_visibility(g, show_excluded=False):
    ns = entities(g); out = []
    for group in g['decisionGroups']:
        members = [m['decisionId'] for m in group['members']]
        selected = [i for i in members if ns[i]['selectionState'] == 'selected']
        hidden = sorted(i for i in members if group['mutuallyExclusive'] and selected and
                        i not in selected and not show_excluded)
        out.append({'groupId': group['id'], 'visibleIds': sorted(set(members) - set(hidden)),
                    'hiddenIds': hidden})
    return out


def _digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _valid_pin(pin,entity=False):
    fields={'packageId','identitySpace','graphRevision','sha256'}|({'schemaVersion','nodeId','mode','revision'} if entity else set())
    return (isinstance(pin,dict) and set(pin)==fields and _uuid(pin.get('packageId')) and _uuid(pin.get('identitySpace')) and
        type(pin.get('graphRevision')) is int and pin['graphRevision']>=1 and isinstance(pin.get('sha256'),str) and re.fullmatch('[0-9a-f]{64}',pin['sha256']) is not None and
        (not entity or pin.get('schemaVersion')==1 and text(pin.get('nodeId')) and pin.get('mode') in ('current','historical','inherited') and type(pin.get('revision')) is int and pin['revision']>=1))


def validate(g):
    optional={'externalRefs','inheritedHistory','factLineage','entityLineage',
              'dependencyPolicies','dependencyBindings','dependencyPresets','dependencyAutomaticStates','dependencyPolicyAliases','contextGroups'}
    require(isinstance(g, dict) and GRAPH_FIELDS<=set(g) and set(g)<=GRAPH_FIELDS|optional and g.get('schemaVersion') == 1 and
            g.get('actionModel') == 'candidate-v6' and g.get('coreModel') == PROFILE and
            text(g.get('id')) and text(g.get('title')) and _uuid(g.get('identitySpace')) and
            type(g.get('revision')) is int and g['revision'] >= 1, 'PROFILE_OR_OWNER')
    require(g.get('rootRequirementId') is None or text(g.get('rootRequirementId')), 'ROOT_ID')
    for key in ('rootCauses', 'nodes', 'objects', 'externalActions', 'edges', 'decisionGroups',
                'workGraphs', 'events', 'recommendationPackageIds'):
        require(isinstance(g.get(key), list), 'ARRAY_' + key.upper())
    require(unique_strings(g['recommendationPackageIds']) and all(_uuid(i) for i in g['recommendationPackageIds']), 'RECOMMENDATION_PACKAGE_IDS')
    for field in ('dependencyPolicies','dependencyBindings','dependencyPresets'):
        require(isinstance(g.get(field,[]),list),'POLICY_CATALOG_TYPE')
    validate_policy_catalog(g)
    require(isinstance(g.get('dependencyPolicyAliases',{}),dict) and all(text(k) and text(v) for k,v in g.get('dependencyPolicyAliases',{}).items()),'POLICY_ALIASES')
    require(isinstance(g.get('dependencyAutomaticStates',{}),dict),'POLICY_AUTOMATIC_STATE')
    for key,state in g.get('dependencyAutomaticStates',{}).items():
        require(isinstance(state,dict) and state.get('id')==key and state.get('status') in ('active','disabled','deleted') and all(text(state.get(f)) for f in ('sourceId','targetId','origin')) and state['origin'] in ('structural','canon','structural-topology','finding-subject') and key==POLICIES.automatic_key({'origin':state['origin'],'sourceId':state['sourceId'],'dependentId':state['targetId']}) and type(state.get('revision')) is int and state['revision']>=1,'POLICY_AUTOMATIC_STATE')
    events = {}
    for ev in g['events']:
        _validate_event(ev)
        require(ev['id'] not in events, 'DUPLICATE_EVENT_ID')
        events[ev['id']] = ev
    require(all(isinstance(g.get(field,{}),dict) for field in ('inheritedHistory','factLineage','entityLineage')),'LINEAGE_SCHEMA')
    for key,value in g.get('inheritedHistory',{}).items():
        require(isinstance(value,dict) and {'source','events','eventsSHA256'}==set(value) and _valid_pin(value['source']) and key==value['source']['sha256'] and
            isinstance(value['events'],list) and value['eventsSHA256']==_digest(value['events']),'INHERITED_HISTORY')
        for ev in value['events']:_validate_event(ev)
    for nid,links in g.get('factLineage',{}).items():
        require(text(nid) and isinstance(links,dict),'INHERITED_FACT')
        for event_id,link in links.items():
            require(isinstance(link,dict) and set(link)=={'historyKey','sourceId'} and text(link['sourceId']),'INHERITED_FACT')
            history=g.get('inheritedHistory',{}).get(link.get('historyKey'),{})
            found=next((e for e in history.get('events',[]) if e['id']==event_id and link.get('sourceId') in e['nodeIds']),None)
            require(found is not None,'INHERITED_FACT')
            candidate=copy.deepcopy(found);candidate['nodeIds']=[nid];events[event_id]={**candidate,'nodeIds':sorted(set(candidate['nodeIds'])|set(events.get(event_id,{}).get('nodeIds',[])))}
    ns = {}
    for field, kinds in (('nodes', NODE_KINDS), ('objects', OBJECT_KINDS), ('externalActions', {'action'})):
        for node in g[field]:
            require(isinstance(node, dict) and node.get('kind') in kinds and node.get('id') not in ns, 'DUPLICATE_ENTITY_ID')
            _validate_entity(node, node['kind'], events)
            if 'subjectRefs' in node:require(field=='externalActions','ACTION_SUBJECTS_EXTERNAL_ONLY')
            if field == 'nodes' and node['kind'] == 'action':
                require(node.get('lowLevel') is False, 'LOW_LEVEL_ACTION_OUTSIDE_GRAPH')
            if field == 'externalActions':
                require(node.get('lowLevel') is True or node.get('actionType') == 'task', 'EXTERNAL_ACTION_ROLE')
            ns[node['id']] = node
    require(g['rootRequirementId'] is None or
            (g['rootRequirementId'] in ns and ns[g['rootRequirementId']]['kind'] == 'requirement'), 'ROOT')
    all_ids = set(ns)
    # A Decision's factual situation references *existing* blocks in this same
    # process owner. D→D manual subscriptions are separate from these legacy refs.
    allowed_context = ENTITY_KINDS
    for decision in g['nodes']:
        if decision['kind'] != 'decision':continue
        require(all(ref != decision['id'] and ref in ns and
                    ns[ref]['kind'] in allowed_context and
                    ref in {row['id'] for row in g['nodes'] + g['objects']}
                    for ref in decision.get('decisionContextIds', [])), 'DECISION_CONTEXT_REFS')
        require(unique_strings(decision.get('impactTargetIds',[])) and set(decision.get('impactTargetIds',[]))<=set(ns),'PROPOSAL_IMPACT_TARGETS')
        require(not any(edge['type']=='DEPENDS_ON' and edge.get('dependencyPurpose')=='decisionContext' and
                    edge['to']==decision['id'] and edge['from'] in decision.get('decisionContextIds',[])
                    for edge in g['edges']), 'DEPENDENCY_CONTEXT_DUPLICATE_SOURCE')
    causes = set()
    for cause in g['rootCauses']:
        require(isinstance(cause, dict) and set(cause) == {'id', 'requirementId', 'reason', 'enabled'} and
                text(cause.get('id')) and cause['id'] not in causes and cause['id'] not in all_ids and
                cause.get('requirementId') in ns and ns[cause['requirementId']]['kind'] == 'requirement' and
                text(cause.get('reason')) and isinstance(cause.get('enabled'), bool), 'ROOT_CAUSE')
        causes.add(cause['id'])
    work_ids = set()
    for wg in g['workGraphs']:
        require(isinstance(wg, dict) and
                {'id', 'title', 'rootIds', 'memberIds'} <= set(wg) <=
                {'id', 'title', 'rootIds', 'memberIds', 'colorKey'} and
                text(wg.get('id')) and wg['id'] not in work_ids and wg['id'] not in all_ids and
                text(wg.get('title')) and unique_strings(wg.get('rootIds')) and unique_strings(wg.get('memberIds')) and
                set(wg['rootIds']) <= set(wg['memberIds']) and set(wg['memberIds']) <= (set(ns) - {i for i,n in ns.items() if i in {a['id'] for a in g['externalActions']}}) and
                all(ns[i]['kind'] == 'requirement' for i in wg['rootIds']) and
                ('colorKey' not in wg or wg['colorKey'] in WORK_GRAPH_COLOR_KEYS), 'WORK_GRAPH')
        work_ids.add(wg['id'])
    edge_ids = set(); edge_keys = set()
    graph_entity_ids = {n['id'] for n in [*g['nodes'], *g['objects']]}
    for relation in g['edges']:
        _relation_error(relation, ns)
        require(relation['from'] in graph_entity_ids and relation['to'] in graph_entity_ids,
                'EXTERNAL_ACTION_RELATION_FORBIDDEN')
        require(relation['id'] not in edge_ids and relation['id'] not in all_ids, 'DUPLICATE_RELATION_ID')
        edge_ids.add(relation['id'])
        key=(relation['type'],relation['from'],relation['to'],
             relation.get('dependencyLevel') if relation['type']=='DEPENDS_ON' else None)
        require(key not in edge_keys,'DUPLICATE_RELATION')
        edge_keys.add(key)
    group_ids = set(); membership_ids = set(); membership_pairs = set()
    for group in g['decisionGroups']:
        require(isinstance(group, dict) and set(group) == {'id', 'parentId', 'title', 'selectionRequired', 'mutuallyExclusive', 'members'} and
                text(group.get('id')) and group['id'] not in group_ids and group['id'] not in all_ids and
                group['id'] not in edge_ids and text(group.get('title')) and
                group.get('parentId') in ns and ns[group['parentId']]['kind'] in ('requirement','decision') and
                isinstance(group.get('selectionRequired'), bool) and isinstance(group.get('mutuallyExclusive'), bool) and
                isinstance(group.get('members'), list) and bool(group['members']), 'DECISION_GROUP')
        group_ids.add(group['id']); local_decisions = set()
        for member in group['members']:
            require(isinstance(member, dict) and set(member) == {'id', 'decisionId'} and text(member.get('id')) and
                    member['id'] not in membership_ids and member['id'] not in edge_ids and member['id'] not in all_ids and
                    member.get('decisionId') in ns and ns[member['decisionId']]['kind'] == 'decision' and
                    member['decisionId'] not in local_decisions, 'DECISION_GROUP_MEMBER')
            membership_ids.add(member['id']); local_decisions.add(member['decisionId'])
            membership_pairs.add((group['parentId'], member['decisionId']))
        selected = [m['decisionId'] for m in group['members'] if ns[m['decisionId']]['selectionState'] == 'selected']
        require(not group['mutuallyExclusive'] or len(selected) <= 1, 'DECISION_GROUP_CONFLICT')
    require(not any(e['type'] == 'DRIVES' and (e['from'], e['to']) in membership_pairs for e in g['edges']),
            'DUPLICATE_MEMBERSHIP_SOURCE')
    for node in ns.values():
        if node['kind'] == 'action':
            require(set(node['targetIds']) <= {i for i,n in ns.items() if n['kind']=='decision' or node['actionType']=='task' and n['kind'] in NODE_KINDS}, 'ACTION_TARGETS')
            require(set(node['groupIds']) <= group_ids, 'ACTION_GROUPS')
    require(set(g.get('factLineage',{}))<=set(ns) and set(g.get('entityLineage',{}))<=set(ns),'LINEAGE_OWNER')
    for nid,refs in g.get('entityLineage',{}).items():require(isinstance(refs,list) and all(_valid_pin(r,True) and r['mode']!='current' for r in refs),'ENTITY_LINEAGE')
    require(isinstance(g.get('externalRefs',[]),list) and unique_strings([r.get('id') for r in g.get('externalRefs',[]) if isinstance(r,dict)]),'EXTERNAL_REF_IDS')
    for ref in g.get('externalRefs',[]):
        require(isinstance(ref,dict) and set(ref)=={'id','localId','direction','relation','target','observed','reason'} and ref['localId'] in ns and ref['direction'] in ('incoming','outgoing','peer'),'EXTERNAL_REF')
        pin=ref['target'];require(_valid_pin(pin,True) and isinstance(ref['observed'],dict) and text(ref['reason']),'EXTERNAL_REF_PIN')
    active = set(support_state(g)['activeIds'])
    require(all(n['selectionState'] != 'selected' or n['id'] in active
                for n in ns.values() if n['kind'] == 'decision'), 'SELECTED_DECISION_WITHOUT_BASIS')
    FINDINGS.validate_graph(g,sys.modules[__name__])
    QUESTIONS.validate_graph(g,sys.modules[__name__],events)
    for action in g['externalActions']:
        for ref in action.get('subjectRefs',[]):
            if 'nodeId' in ref and action.get('referenceBindings',{}).get(QUESTIONS.reference_key(ref)) in ns:
                QUESTIONS.reference_id(g,ref,sys.modules[__name__],action)

    ANALYSIS.validate_groups(g,sys.modules[__name__])
    ANALYSIS.validate_notes(g,sys.modules[__name__])
    return g


def edit_external_reference(original,reference_id,replacement,event):
    validate(original);g=copy.deepcopy(original);record=next((r for r in g.get('externalRefs',[]) if r['id']==reference_id),None)
    require(record is not None,'EXTERNAL_REFERENCE_NOT_FOUND');node=entities(g)[record['localId']];guard(node,event,'edit')
    previous=copy.deepcopy(record);g['externalRefs'].remove(record)
    if replacement is not None:
        require(replacement['id']==reference_id and replacement['localId']==node['id'],'EXTERNAL_REF')
        g['externalRefs'].append(copy.deepcopy(replacement))
    affected=_review_impact(g,{node['id']});_mark_review(g,affected,event['id'],raw_event=event)
    pin=copy.deepcopy(previous['target']);pin['mode']='historical'
    g['events'].append({'id':event['id'],'type':'edited','transactionId':event['verifiedTrustReceipt']['transactionId'],
        'recordedAt':event['recordedAt'],'by':event['by'],'nodeIds':sorted(affected),'basis':event['note'],'observedPins':[pin]})
    g['revision']+=1;validate(g);return g,sorted(affected)


def validate_role(g, role, plan=None):
    validate(g)
    return _validate_role_on_validated_graph(g, role, plan)


def _validate_role_on_validated_graph(g, role, plan=None):
    """Role constraints only, for Graphs already validated in the same call.

    External callers must use validate_role(); this internal entry point is
    intended only for snapshot() immediately after validate_graph_payload().
    """
    require(role in ('working', 'ready', 'copy', 'lens'), 'DOCUMENT_ROLE')
    if role in ('ready', 'lens'):
        require(not any(any(k in node for k in ('decisionContextIds','contextNotes','analysisSources')) for node in g['nodes'] if node['kind']=='decision') and
                not any(edge.get('dependencyPurpose')=='decisionContext' for edge in g['edges']),
                'DECISION_CONTEXT_PROCESS_ONLY')
        require(not any(g.get(k) for k in ('inheritedHistory','factLineage','externalRefs')),'PAPER_NO_INHERITED_HISTORY')
        require(plan is None, 'PAPER_NO_PLAN')
        require(not any(e['type'] in ('decision_selected', 'decision_unselected', 'branch_cancelled',
                'action_executed', 'requirement_achieved', 'decision_completed', 'reopened') for e in g['events']),
                'PAPER_NO_WORK_HISTORY')
        for node in entities(g).values():
            if node['kind'] in ('requirement', 'decision', 'action'):
                require(node['result'] == {'state': 'open', 'truth': 'unknown'}, 'PAPER_RESULT_OPEN')
            if node['kind'] == 'decision':
                require(node['selectionState'] in ('discovered', 'unselected'), 'PAPER_DECISION_UNSELECTED')
            if node['kind']=='question':
                require(not node['answers'] and not node.get('answerHistory') and not node.get('assessment') and not node['assessmentHistory'] and not node['sourceRefs'] and not any(r.get('kind') or r.get('mode')=='historical' for r in node['relatedRefs']),'QUESTION_TEMPLATE_LIVE_DATA')
            require(not node.get('review', {}).get('required'), 'PAPER_NO_REVIEW')
    return g


def pins(g, nid):
    ns = entities(g); require(nid in ns, 'PIN_TARGET')
    relevant = {nid}
    if ns[nid]['kind']=='finding' and ns[nid]['subjectId'] in ns:relevant.add(ns[nid]['subjectId'])
    if ns[nid]['kind']=='decision':
        relevant.update(r['sourceId'] for r in decision_context(g,nid) if r['present'])
        relevant.update(p['findingId'] for r in decision_context(g,nid) for p in r['provenance'])
    for edge in active_edges(g):
        if edge['to'] == nid and edge['type'] in DEPENDENCY_TYPES | {'CANON_FOR'}:
            relevant.add(edge['from'])
        if edge['to'] == nid and edge['type'] == 'DRIVES':
            relevant.add(edge['from'])
    if ns[nid]['kind']=='decision':
        relevant.update(e['from'] for e in active_edges(g) if e['type']=='DEPENDS_ON' and
            e['to']==nid and e.get('dependencyPurpose')=='decisionContext')
    for group in g['decisionGroups']:
        member_ids = {m['decisionId'] for m in group['members']}
        if group['parentId'] == nid or nid in member_ids:
            relevant.add(group['parentId']); relevant.update(member_ids)
    for binding in g.get('dependencyBindings',[]):
        if binding['targetId']!=nid or not binding['enabled']:continue
        policy=_policy_at(g,binding['policyId'],binding['policyVersion'])
        matched,_,_=POLICIES.resolve(g,policy,binding,sys.modules[__name__])
        relevant.update(i for ids in matched.values() for i in ids)
    return {i: ns[i]['revision'] for i in sorted(relevant) if i in ns}


def guard(n, ev, operation='edit'):
    policy = n.get('policy', {'mode': 'ordinary'})
    if n['kind'] == 'requirement' and policy['mode'] == 'stable':
        require(text(ev.get('reasonForReconsideration')), 'STABLE_REASON_REQUIRED')
    if policy['mode'] == 'protected':
        require(ev.get('by') == 'user' and ev.get('authorityPrincipal') == policy['authorityPrincipal'], 'PROTECTED_OWNER_GRANT_REQUIRED')
    spec = n.get('locks', {}).get(operation)
    if spec:
        if spec['mode'] == 'warning':
            warning = {'nodeId': n['id'], 'operation': operation, 'message': spec['message']}
            warnings = ev.setdefault('lockWarnings', [])
            if warning not in warnings:
                warnings.append(warning)
        else:
            require(ev.get('authorityPrincipal') in spec['principals'], 'OBJECT_OPERATION_LOCK_REQUIRED')


def _bump(ns, ident, touched):
    if ident in ns and ident not in touched:
        ns[ident]['revision'] += 1
        touched.add(ident)


def _mark_review(g, ids, event_id, touched=None, raw_event=None):
    ns = entities(g); touched = touched if touched is not None else set()
    targets = [ns[i] for i in sorted(set(ids)) if i in ns and ns[i]['kind'] in REVIEW_KINDS]
    # Review invalidation is a real write on each affected node. Locks/policy
    # must be checked for the entire set before the first review is changed.
    if raw_event is not None:
        for node in targets:
            guard(node, raw_event, 'review')
    for node in targets:
        review = node.setdefault('review', {'required': False, 'causeEventIds': [], 'pins': []})
        review['required'] = True
        if event_id not in review['causeEventIds']:
            review['causeEventIds'].append(event_id)
        review['pins'] = []
        _bump(ns, node['id'], touched)


def _review_impact(g, seeds):
    """Compatibility helper for direct editing. No recursive stale traversal."""
    return set(seeds) & set(entities(g))


def _cascade(g, transaction_id, timestamp, by, basis, seed_ids, serial, raw_event, before_active, touched):
    """Withdraw selected Decisions that lose every basis; keep their result/history."""
    ns = entities(g); affected = set(seed_ids); changed = []
    while True:
        active = set(support_state(g)['activeIds'])
        lost = sorted(n['id'] for n in ns.values() if n['kind'] == 'decision' and
                      n['selectionState'] == 'selected' and n['id'] not in active)
        if not lost:
            break
        for ident in lost:
            guard(ns[ident], raw_event, 'withdraw')
            ns[ident]['selectionState'] = 'unselected'; _bump(ns, ident, touched)
            affected.add(ident); changed.append(ident)
    lost_active = set(before_active) - set(support_state(g)['activeIds'])
    cancelled_ids = set(changed) | lost_active
    if cancelled_ids:
        event_id = str(uuid.uuid5(uuid.UUID(transaction_id), 'branch_cancelled:' + str(serial)))
        g['events'].append({'id': event_id, 'type': 'branch_cancelled', 'transactionId': transaction_id,
            'recordedAt': timestamp, 'by': by, 'nodeIds': sorted(cancelled_ids), 'basis': basis})
    return sorted(set(changed))


def _event(raw, cmd, data, transaction_id=None, timestamp=None, by=None, node_ids=None,
           event_type=None, relation_ids=None, evidence_ids=None, action_result=None, operation_action_id=None):
    raw = raw or {}; receipt = raw.get('verifiedTrustReceipt') if isinstance(raw.get('verifiedTrustReceipt'), dict) else {}
    ident = raw.get('id')
    tx = transaction_id or raw.get('transactionId') or receipt.get('transactionId') or ident
    when = timestamp or raw.get('recordedAt')
    actor = by or raw.get('by')
    basis = data.get('basis') if isinstance(data, dict) else None
    basis = basis if text(basis) else raw.get('note')
    require(_uuid(ident) and _uuid(tx) and isinstance(when, str) and
            re.search(r'(?:Z|[+-]\d{2}:\d{2})$', when) and actor in ('user', 'assistant') and text(basis), 'EVENT_RECEIPT')
    result = {'id': ident, 'type': event_type or 'edited', 'transactionId': tx,
              'recordedAt': when, 'by': actor, 'nodeIds': sorted(set(node_ids or [])), 'basis': basis}
    if evidence_ids is not None:
        result['evidenceIds'] = sorted(set(evidence_ids))
    if relation_ids is not None:
        result['relationIds'] = sorted(set(relation_ids))
    if raw.get('lockWarnings'):
        result['lockWarnings'] = copy.deepcopy(raw['lockWarnings'])
    if action_result is not None:
        result['actionResult'] = copy.deepcopy(action_result)
        result['operationActionId'] = operation_action_id
    return result


def _append_event(g, ev, extra=None):
    if extra:
        ev.update(extra)
    g['events'].append(ev)


def _validate_new_relation(g, relation, new_id=None):
    ns = entities(g)
    _relation_error(relation, ns)
    require(relation['type'] not in FINDINGS.RELATIONS,'FINDING_WORKFLOW_RETIRED')
    require(not any(e['id'] == relation['id'] for e in g['edges']) and
            not any(m['id'] == relation['id'] for group in g['decisionGroups'] for m in group['members']), 'RELATION_ID_CONFLICT')
    if new_id is not None:
        require((relation['from'] == new_id) != (relation['to'] == new_id), 'INITIAL_RELATION_UNRELATED')
    key = (relation['type'], relation['from'], relation['to'])
    require(not any((e['type'], e['from'], e['to']) == key for e in g['edges']), 'DUPLICATE_RELATION')
    require(not (relation['type'] == 'DRIVES' and any(group['parentId'] == relation['from'] and
            any(m['decisionId'] == relation['to'] for m in group['members']) for group in g['decisionGroups'])),
            'DUPLICATE_MEMBERSHIP_SOURCE')


def _selection_allowed(g, decision_ids, ev):
    ns = entities(g); active = set(support_state(g)['activeIds'])
    require(all(i in ns and ns[i]['kind'] == 'decision' for i in decision_ids), 'DECISION_TARGET_REQUIRED')
    for ident in decision_ids:
        require(_has_parent_basis(g, ident, active) or _has_parent_basis(g, ident, active | {ident}), 'NO_ACTIVE_BASIS')
        require(ns[ident]['result']['state'] != 'confirmed', 'DECISION_REOPEN_REQUIRED')
        require(not ns[ident].get('review', {}).get('required'), 'REVIEW_REQUIRED')
        guard(ns[ident], ev, 'select')
        parents = {e['from'] for e in active_edges(g) if e['type'] in ('DRIVES','FINDING_RESPONSE','FINDING_PROPOSAL') and e['to'] == ident}
        parents.update(group['parentId'] for group in g['decisionGroups']
                       if any(m['decisionId'] == ident for m in group['members']))
        for parent_id in parents:
            if parent_id in active:
                require(not ns[parent_id].get('review', {}).get('required'), 'REVIEW_REQUIRED')
                guard(ns[parent_id], ev, 'select')
    candidate = copy.deepcopy(g); cns = entities(candidate)
    for ident in decision_ids:
        cns[ident]['selectionState'] = 'selected'
    _selected_conflicts(candidate, decision_ids)


def completion_state(g):
    validate(g)
    ns = entities(g); active = set(support_state(g)['activeIds']); blockers = {}
    for ident, node in ns.items():
        if node['kind'] not in NODE_KINDS:
            continue
        rows = set()
        if ident in active and node['kind'] == 'requirement':
            rows.update(e['to'] for e in active_edges(g) if e['from'] == ident and e['type'] in ('DERIVES', 'REQUIRES_ACTION'))
            rows.update(e['to'] for e in active_edges(g) if e['from'] == ident and e['type'] == 'DRIVES' and ns[e['to']]['selectionState'] == 'selected')
            for group in g['decisionGroups']:
                if group['parentId'] != ident:
                    continue
                selected = [m['decisionId'] for m in group['members'] if ns[m['decisionId']]['selectionState'] == 'selected']
                rows.update(selected)
                if group['selectionRequired'] and not selected:
                    rows.add('group:' + group['id'])
        elif ident in active and node['kind'] == 'decision':
            rows.update(e['to'] for e in active_edges(g) if e['from'] == ident and e['type'] in ('INTRODUCES', 'REQUIRES_ACTION'))
        rows.update(e['to'] for e in active_edges(g) if e['from']==ident and e['type'] in FINDINGS.RELATIONS and ns[e['to']]['selectionState']=='selected')
        for group in g['decisionGroups']:
            if group['parentId']==ident and node['kind']=='decision':
                rows.update(m['decisionId'] for m in group['members'] if ns[m['decisionId']]['selectionState']=='selected')
                if group['selectionRequired'] and not any(ns[m['decisionId']]['selectionState']=='selected' for m in group['members']):rows.add('group:'+group['id'])
        blockers[ident] = rows
    eligible = {i for i, n in ns.items() if n['kind'] in NODE_KINDS and
                (i in active or i in {a['id'] for a in g['externalActions']
                    if a['actionType'] in ('task','discover_requirement','discover_decision','rename_block')}) and
                n['result']['state'] == 'confirmed' and not n.get('review', {}).get('required')}
    while True:
        removed = {i for i in eligible if any(child.startswith('group:') or child not in eligible for child in blockers.get(i, set()))}
        if not removed:
            break
        eligible.difference_update(removed)
    out = {}
    for ident, node in ns.items():
        if node['kind'] not in NODE_KINDS:
            continue
        previous = node['result']['state'] == 'confirmed'
        unresolved = sorted(blockers.get(ident, set()) - eligible)
        review = bool(node.get('review', {}).get('required') or (previous and unresolved))
        out[ident] = {'complete': ident in eligible, 'active': ident in active,
            'previouslyConfirmed': previous, 'reviewRequired': review,
            'truth': node['result'].get('truth', 'unknown') if ident in eligible else ('unknown' if review else node['result'].get('truth', 'unknown')),
            'currentScopeComplete': ident in eligible, 'eventId': node['result'].get('eventId'),
            'basis': copy.deepcopy(node['result']), 'historyPending': False,
            'blockers': unresolved, 'autoDerived': False}
    return out


def focused_view(g, nid, *, include_completion=True):
    validate(g); ns = entities(g); require(nid in ns, 'FOCUS_UNKNOWN')
    node = ns[nid]; edges = active_edges(g); chosen = {nid}; visible_edges = []
    if node['kind'] == 'requirement':
        chosen.update(e['from'] for e in edges if e['to'] == nid and e['type'] in ('DERIVES', 'INTRODUCES'))
        chosen.update(e['from'] for e in edges if e['to'] == nid and e['type'] in ('CANON_FOR', 'CONTEXT_FOR', 'INFO_FOR', 'EVIDENCE_FOR'))
        chosen.update(e['to'] for e in edges if e['from'] == nid and e['type'] in ('DERIVES', 'DRIVES', 'REQUIRES_ACTION'))
        chosen.update(g['rootCauses'][i]['requirementId'] for i in range(len(g['rootCauses'])) if g['rootCauses'][i]['requirementId'] == nid)
        for group in g['decisionGroups']:
            if group['parentId'] == nid:
                chosen.update(m['decisionId'] for m in group['members'])
    elif node['kind'] == 'decision':
        chosen.update(e['from'] for e in edges if e['to'] == nid and e['type'] == 'DRIVES')
        chosen.update(e['from'] for e in edges if e['to'] == nid and e['type'] in ('CANON_FOR', 'CONTEXT_FOR', 'INFO_FOR', 'EVIDENCE_FOR'))
        chosen.update(r['sourceId'] for r in decision_context(g,nid) if r['present'])
        chosen.update(e['to'] for e in edges if e['from'] == nid and e['type'] in ('INTRODUCES', 'REQUIRES_ACTION'))
        for group in g['decisionGroups']:
            if any(m['decisionId'] == nid for m in group['members']):
                chosen.add(group['parentId'])
    elif node['kind'] == 'action':
        chosen.update(e['from'] for e in edges if e['to'] == nid and e['type'] == 'REQUIRES_ACTION')
        chosen.update(e['from'] for e in edges if e['to'] == nid and e['type'] in ('CANON_FOR', 'CONTEXT_FOR', 'INFO_FOR', 'EVIDENCE_FOR'))
    else:
        chosen.update(e['from'] for e in edges if e['to'] == nid)
        chosen.update(e['to'] for e in edges if e['from'] == nid)
    chosen.update(e['to'] for e in edges if e['from']==nid and e['type'] in FINDINGS.RELATIONS)
    chosen.update(e['from'] for e in edges if e['to']==nid and e['type'] in FINDINGS.RELATIONS)
    if node['kind']=='finding':chosen.update(i for i in (node['subjectId'],*node.get('evidenceIds',[])) if i in ns)
    visible_edges = [copy.deepcopy(e) for e in edges
                     if (e['from'] == nid and e['to'] in chosen) or
                        (e['to'] == nid and e['from'] in chosen)]
    relevant_groups = [group for group in g['decisionGroups']
        if (node['kind'] in ('requirement','decision') and group['parentId'] == nid) or
           (node['kind'] == 'decision' and any(m['decisionId'] == nid for m in group['members']))]
    scoped_groups = [{**copy.deepcopy(group), 'members':[
        copy.deepcopy(member) for member in group['members']
        if member['decisionId'] in chosen and (node['kind'] != 'decision' or member['decisionId'] == nid)]}
        for group in relevant_groups]
    return {'profile': PROFILE, 'identitySpace': g['identitySpace'], 'ownerId': g['id'],
        'revision': g['revision'], 'focusId': nid, 'focusKind': node['kind'],
        'entities': [copy.deepcopy(ns[i]) for i in sorted(chosen)], 'edges': visible_edges,
        'decisionMemberships': [m for m in decision_memberships(g) if m['from'] in chosen and m['to'] in chosen],
        'decisionGroups': scoped_groups,
        'workGraphIds': [w['id'] for w in g['workGraphs'] if nid in w['memberIds']],
        **({'completion': completion_state(g)} if include_completion else {}), 'viewOnly': True}


def detached_components(g, work_graph_id=None):
    validate(g); ns = entities(g); edges = active_edges(g); out = []
    for wg in g['workGraphs']:
        if work_graph_id is not None and wg['id'] != work_graph_id:
            continue
        members = set(wg['memberIds']); reached = set(wg['rootIds']); queue = deque(reached)
        while queue:
            source = queue.popleft()
            for edge in edges:
                if edge['from'] == source and edge['type'] in ('DERIVES', 'DRIVES', 'INTRODUCES', 'REQUIRES_ACTION') and edge['to'] in members and edge['to'] not in reached:
                    reached.add(edge['to']); queue.append(edge['to'])
            for group in g['decisionGroups']:
                if group['parentId'] == source:
                    for member in group['members']:
                        if member['decisionId'] in members and member['decisionId'] not in reached:
                            reached.add(member['decisionId']); queue.append(member['decisionId'])
        for ident in sorted(members - reached):
            out.append({'workGraphId': wg['id'], 'memberIds': [ident], 'reviewIds': [ident] if ns[ident].get('review', {}).get('required') else [], 'rootIds': list(wg['rootIds']), 'derived': True})
    if work_graph_id is not None:
        require(any(w['id'] == work_graph_id for w in g['workGraphs']), 'WORK_GRAPH_UNKNOWN')
    return out


def native_dependency_edges(g):
    validate(g)
    return [copy.deepcopy(e) for e in g['edges'] if e['type'] == 'DEPENDS_ON']


def _native_definition(g, ident):
    node = entities(g).get(ident)
    if node is None:
        return None
    # A semantic definition, not an entity revision or review/result event.
    keys = {'title', 'description', 'tags', 'scope', 'guidance', 'canons', 'knownErrors', 'value',
            'claim', 'version', 'source', 'artifact', 'actionType', 'targetIds', 'groupIds',
            'subjectId','findingType','rationale','evidenceIds','impactTargetIds','estimates','subjectRefs','resultCondition',
            'relatedRefs','sourceRefs','impact','answerCondition','blocking','answers','assessment'}
    value={k: copy.deepcopy(node[k]) for k in sorted(keys) if k in node}
    if node['kind']=='evidence' and 'claim' in value:value['value']=value.pop('claim')
    return value


def _native_direct_scope(g, ident, *, include_findings=True):
    ns = entities(g)
    if ident not in ns:
        return []
    node = ns[ident]
    rows = []
    for edge in active_edges(g):
        kind = node['kind']
        if kind == 'requirement':
            include = ((edge['from'] == ident and edge['type'] in ('DERIVES', 'DRIVES', 'REQUIRES_ACTION')) or
                       (edge['to'] == ident and edge['type'] in ('DERIVES', 'INTRODUCES')))
        elif kind == 'decision':
            include = ((edge['from'] == ident and edge['type'] in ('INTRODUCES', 'REQUIRES_ACTION')) or
                       (edge['to'] == ident and edge['type'] == 'DRIVES'))
        elif kind == 'action':
            include = edge['to'] == ident and edge['type'] == 'REQUIRES_ACTION'
        else:
            include = False
        # Direct Canon and factual Context are part of the source's L2 scope.
        # INFO_FOR/EVIDENCE_FOR are explanatory, never implicit subscriptions.
        if edge['to']==ident and edge['type'] in ('CANON_FOR','CONTEXT_FOR'):
            include=True
        if edge['type'] in FINDINGS.RELATIONS and ident in (edge['from'],edge['to']):include=True
        if include:
            endpoint = edge['to'] if edge['from'] == ident else edge['from']
            rows.append({'id':edge['id'], 'type':edge['type'], 'from':edge['from'], 'to':edge['to'],
                         'endpoint':endpoint, 'endpointDefinition':_native_definition(g,endpoint)})
    if node['kind'] in ('requirement', 'decision'):
        for group in g.get('decisionGroups', []):
            if group['parentId'] != ident and not any(m['decisionId'] == ident for m in group['members']):
                continue
            rows.append({'type':'DECISION_GROUP', 'id':group['id'], 'parentId':group['parentId'],
                         'selectionRequired':group['selectionRequired'],
                         'mutuallyExclusive':group['mutuallyExclusive'],
                         'members':sorted(m['decisionId'] for m in group['members'])})
    if node['kind'] == 'decision':
        context_ids={r['sourceId'] for r in ANALYSIS.context(g,ident,sys.modules[__name__],derived=include_findings) if r['present']}
        for ref in sorted(context_ids):
            rows.append({'type':'DECISION_CONTEXT', 'id':ref, 'endpoint':ref,
                         'endpointDefinition':_native_definition(g,ref)})
    return sorted(rows,key=lambda row:(row['type'],row['id']))


def semantic_projection(g, nid, level='L1'):
    """Native semantic L1/L2, matching the core contract's content comparison.

    L1 follows the source definition. L2 additionally follows only immediate
    real requirements, decisions, group rules and decision context; it does not
    recurse into a neighbor's children or treat a generic revision as content.
    """
    if isinstance(level,dict):
        source=entities(g).get(nid)
        if source is None:return None
        validate_dependency_rule(level,source['kind'])
        return {'level':level['preset'],'sourceId':nid,'sourceRevision':source['revision'],
                'affectedIds':[nid],'profile':PROFILE,'rule':copy.deepcopy(level),
                'watched':_observable(g,nid,level)}
    require(level in ('L1','L2'), 'DEPENDENCY_LEVEL')
    node=entities(g).get(nid)
    if node is None:
        return None
    # Keep the existing public projection fields for Application/API clients;
    # revisions and legacy affected-ID hints are metadata, not semantic impact.
    related={nid}
    if level=='L2':
        related.update(e['to'] for e in active_edges(g) if e['from']==nid and e['type'] in DEPENDENCY_TYPES)
        related.update(m['decisionId'] for group in g['decisionGroups'] if group['parentId']==nid for m in group['members'])
    result={'level':level,'sourceId':nid,'sourceRevision':node['revision'],
            'affectedIds':sorted(related),'kind':node['kind'],
            'definition':_native_definition(g,nid),'profile':PROFILE}
    if level=='L2':
        result['directScope']=_native_direct_scope(g,nid)
    return result


def decision_context(g, ident):
    return ANALYSIS.context(g,ident,sys.modules[__name__])


def _context_sources(g, ident, *, include_findings=True):
    rows=[]
    for row in ANALYSIS.context(g,ident,sys.modules[__name__],derived=include_findings):
        i=row['sourceId']
        if not row['present']:continue
        edge=next((e for e in g['edges'] if e['type']=='DEPENDS_ON' and e.get('dependencyPurpose')=='decisionContext' and e['from']==i and e['to']==ident),None)
        rule=dependency_rule(edge) if edge else {'preset':'L1','watch':['definition']}
        active=row['manual'] or any(p['enabled'] for p in row['provenance'])
        rows.append({'sourceId':i,'rule':rule,'projection':_observable(g,i,rule,include_context=False,include_findings=include_findings) if active else None,
                     **({'comment':row['comment']} if row['comment'] else {})})
    return rows


def _canon_sources(g, ident):
    ns=entities(g)
    return sorted([{'edgeId':e['id'],'canonId':e['from'],
                    'definition':_native_definition(g,e['from'])}
                   for e in g['edges'] if e['type']=='CANON_FOR' and e['to']==ident
                   and e['from'] in ns],key=lambda x:x['edgeId'])


def _observable(g, ident, rule, *, include_context=True, include_findings=True):
    ns=entities(g);node=ns.get(ident)
    if node is None:return None
    values={}
    for part in rule['watch']:
        if part=='definition':values[part]=_native_definition(g,ident)
        elif part=='directScope':values[part]=_native_direct_scope(g,ident,include_findings=include_findings)
        elif part=='selection':values[part]=node.get('selectionState')
        elif part=='result':values[part]=copy.deepcopy(node.get('result'))
        elif part=='context':
            # Never recursively expand a D->D context subscription.
            values[part]=_context_sources(g,ident,include_findings=include_findings) if include_context else None
        elif part=='canon':values[part]=_canon_sources(g,ident)
        elif part=='info':
            target_canons={c['canonId'] for c in _canon_sources(g,ident)} if node['kind']=='decision' else {ident}
            values[part]=sorted([{'edgeId':e['id'],'infoId':e['from'],
                'definition':_native_definition(g,e['from'])}
                for e in g['edges'] if e['type']=='INFO_FOR' and e['to'] in target_canons
                and e['from'] in ns],key=lambda x:x['edgeId'])
    return values


def _effective_observable(g, ident, rule, cosmetic_ids, *, include_findings=True):
    observed=_observable(g,ident,rule,include_findings=include_findings)
    if observed is None:return None
    # A permitted cosmetic rename affects no subscribed source, including
    # immediate L2 neighbors, Canon, and legacy/context source snapshots.
    def ignore(value):
        if isinstance(value,dict):
            if value.get('sourceId') in cosmetic_ids and isinstance(value.get('projection'),dict):
                value['projection'].get('definition',{}).pop('title',None)
            if value.get('endpoint') in cosmetic_ids:
                value.get('endpointDefinition',{}).pop('title',None)
            if value.get('canonId') in cosmetic_ids:
                value.get('definition',{}).pop('title',None)
            if value.get('infoId') in cosmetic_ids:
                value.get('definition',{}).pop('title',None)
            for item in value.values():ignore(item)
        elif isinstance(value,list):
            for item in value:ignore(item)
    if ident in cosmetic_ids and 'definition' in observed:
        observed['definition'].pop('title',None)
    ignore(observed)
    return observed


def _subscriptions(g):
    """Unified rules: real structural children, manual subscriptions and Canon.

    Do not traverse grandchildren. A configured Context may observe its one-hop
    facts, but the resulting stale flag is NOT a recursively observed change.
    """
    ns=entities(g);rules={}
    for edge in g['edges']:
        src,dst=edge['from'],edge['to']
        if src not in ns or dst not in ns:continue
        if edge['type'] in STRUCTURAL_KINDS:
            parent=ns[src];watch=['definition']
            if parent['kind']=='decision':watch.append('context')
            rules['struct:'+edge['id']]={'id':edge['id'],'sourceId':src,'dependentId':dst,
                'origin':'structural','rule':{'preset':'L1','watch':watch}}
        elif edge['type']=='DEPENDS_ON':
            rules['manual:'+edge['id']]={'id':edge['id'],'sourceId':src,'dependentId':dst,
                'origin':'manual','rule':dependency_rule(edge)}
        elif edge['type']=='CANON_FOR' and ns[dst]['kind'] in NODE_KINDS:
            rules['canon:'+edge['id']]={'id':edge['id'],'sourceId':src,'dependentId':dst,
                'origin':'canon','rule':{'preset':'canon_criteria','watch':['definition']}}
    for group in g.get('decisionGroups',[]):
        for m in group['members']:
            src,dst=group['parentId'],m['decisionId']
            if src in ns and dst in ns:
                rules['member:'+m['id']]={'id':m['id'],'sourceId':src,'dependentId':dst,
                    'origin':'structural','rule':{'preset':'L1','watch':['definition']},
                    'membership':{'groupId':group['id'], 'selectionRequired':group['selectionRequired'],
                                  'mutuallyExclusive':group['mutuallyExclusive']}}
    for f in g['objects']:
        if f['kind']=='finding' and f['subjectId'] in ns:
            key='finding:'+f['id']
            rules[key]={'id':key,'sourceId':f['subjectId'],'dependentId':f['id'],'origin':'finding-subject','rule':{'preset':'L1','watch':['definition']}}
    for decision in g['nodes']:
        if decision['kind']!='decision':continue
        existing={e['from'] for e in g['edges'] if e['type']=='DEPENDS_ON' and
                  e.get('dependencyPurpose')=='decisionContext' and e['to']==decision['id']}
        for ref in decision.get('decisionContextIds',[]):
            if ref in ns and ref not in existing:
                key='legacy:'+decision['id']+':'+ref
                rules[key]={'id':key,'sourceId':ref,'dependentId':decision['id'],
                    'origin':'decisionContext','rule':{'preset':'L1','watch':['definition']}}
    return rules


def _native_dependency_impacts_unscoped(before, after, *, cosmetic_ids=(), command=None, changed_id=None, policy_event=None):
    """One deterministic evaluator for structural, manual, legacy and Canon rules.

    Structural changes have a one-hop impact, even if the fixed-point support
    cascade cancels many deeper nodes. Only the initiating changed Decision may
    invalidate its own immediate children; the cascade does not re-seed stale.
    """
    old=_subscriptions(before);new=_subscriptions(after)
    rows=[]
    for key in sorted(set(old)|set(new)):
        row=new.get(key) or old[key];before_row=old.get(key);after_row=new.get(key)
        src,dst=row['sourceId'],row['dependentId']
        # When a structural obligation changes, its direct OWNER also needs
        # review of the new obligation set. No traversal to grandparents.
        if row['origin']=='structural' and src in entities(after) and src in entities(before) and (
                before_row is None or after_row is None or
                before_row.get('membership')!=after_row.get('membership')):
            rows.append({'edgeId':'owner:'+row['id'],'sourceId':dst,
                'dependentId':src,'level':'L1','changedParts':['structure'],
                'origin':'structural','preset':'L1'})
        # A newly authored dependent has no previous acceptance to invalidate.
        if dst not in entities(after) or dst not in entities(before):continue
        if row['origin']=='finding-subject' and (before_row is None or after_row is None):continue
        if before_row is None or after_row is None:
            # Subscription and direct membership were created/removed.
            parts=['structure']
        else:
            prior=_effective_observable(before,src,before_row['rule'],cosmetic_ids)
            current=_effective_observable(after,src,after_row['rule'],cosmetic_ids)
            parts=[]
            if prior is None or current is None:parts=['source-removed' if current is None else 'source-added']
            else:
                for field in sorted(set(prior)|set(current)):
                    if prior.get(field)!=current.get(field):parts.append(DEPENDENCY_WATCH_PARTS[field])
            if before_row.get('membership')!=after_row.get('membership'):parts.append('structure')
            if before_row['rule']!=after_row['rule']:parts.append('structure')
        # Direct structural descendants respond to their parent's own changed
        # choice/basis, never cascading auto-withdrawals of distant descendants.
        if row['origin']=='structural' and src==changed_id and command=='withdraw':
            if entities(before).get(src,{}).get('selectionState')=='selected' and \
                    entities(after).get(src,{}).get('selectionState')=='unselected':
                parts.append('basis')
        if not parts:continue
        parts=sorted(set(parts))
        level='L1' if row['origin']!='manual' else row['rule']['preset'] if row['rule']['preset'] in ('L1','L2') else 'custom'
        impact={'edgeId':row['id'],'sourceId':src,'dependentId':dst,'level':level,
                'changedParts':parts}
        if row['origin']!='manual' or 'dependencyRule' in next((e for e in after['edges'] if e['id']==row['id']),{}):
            impact['origin']=row['origin'];impact['preset']=row['rule']['preset']
        rows.append(impact)
    # Multiple legacy subscriptions are deduped, but distinct named policy
    # rules retain their own independently auditable historical triggers.
    policy_rows=policy_binding_impacts(before,after,cosmetic_ids,policy_event)
    seen=set();filtered=[]
    for row in sorted(rows,key=lambda r:(r['dependentId'],r['sourceId'],r.get('origin')!='manual',r['edgeId'])):
        parts=[p for p in row['changedParts'] if (row['sourceId'],row['dependentId'],p) not in seen]
        if not parts:continue
        for part in parts:seen.add((row['sourceId'],row['dependentId'],part))
        filtered.append({**row,'changedParts':parts})
    filtered=POLICIES.explain_automatic(filtered,before,after,sys.modules[__name__],cosmetic_ids)
    return sorted(filtered+policy_rows,key=lambda r:(r['edgeId'],r['dependentId'],r.get('ruleId',''),r.get('sourceId','')))


def native_dependency_impacts(before, after, *, cosmetic_ids=(), command=None, changed_id=None, policy_event=None):
    """Evaluate every operation on its own Graph image; never cache writes.

    Dependency policy/context projections are read-only during this evaluation.
    Reuse derived relations only until the evaluation returns, *not* between
    operations: apply() mutates the same Graph dict in the next step. A fresh
    scope also isolates this writer from an unrelated nested read scope.
    """
    with ANALYSIS.read_scope(after, fresh=True):
        return _native_dependency_impacts_unscoped(before, after,
            cosmetic_ids=cosmetic_ids, command=command,
            changed_id=changed_id, policy_event=policy_event)


def affected(before, after, changed, *, cosmetic_ids=()):
    return set(changed)|{row['dependentId'] for row in native_dependency_impacts(
        before,after,cosmetic_ids=cosmetic_ids)}


def _cascade_event_ids(g, raw, serial):
    receipt = raw.get('verifiedTrustReceipt', {}) if isinstance(raw.get('verifiedTrustReceipt'), dict) else {}
    tx = raw.get('transactionId') or receipt.get('transactionId') or raw.get('id')
    return tx, raw.get('recordedAt'), raw.get('by')


def apply(original, patch, trusted_verified=False, *, coordinated=False, paper=False, resolve_data=None):
    validate(original)
    require(trusted_verified, 'TRUST_RECEIPT_REQUIRED')
    require(isinstance(patch, dict) and patch.get('schemaVersion') == 1 and
            patch.get('expectedRevision') == original['revision'], 'REVISION_CONFLICT')
    require(isinstance(patch.get('operations'), list) and bool(patch['operations']), 'OPERATIONS')
    g = copy.deepcopy(original)
    for serial, op in enumerate(patch['operations']):
        require(isinstance(op, dict) and op.get('op') == 'graph_edit' and
                isinstance(op.get('action'), str) and op['action'].startswith('core_') and
                op['action'][5:] in COMMANDS, 'OPERATION_REQUIRED')
        cmd = op['action'][5:]; data = op.get('data', {})
        if resolve_data is not None:data=resolve_data(data,g)
        raw_event = copy.deepcopy(op.get('event'))
        require(isinstance(data, dict) and isinstance(raw_event, dict) and text(raw_event.get('id')) and
                isinstance(raw_event.get('verifiedTrustReceipt'), dict) and text(raw_event.get('note')) and
                raw_event.get('by') in ('assistant', 'user') and not ({'before','after','affectedIds','cosmetic'} & set(raw_event)), 'EVENT_RECEIPT')
        receipt = raw_event['verifiedTrustReceipt']
        tx = raw_event.get('transactionId') or receipt.get('transactionId') or raw_event['id']
        require(_uuid(tx), 'TRANSACTION_ID')
        timestamp = raw_event.get('recordedAt')
        require(isinstance(timestamp, str) and re.search(r'(?:Z|[+-]\d{2}:\d{2})$', timestamp), 'RECORDED_AT_REQUIRED')
        actor = raw_event['by']; basis = data.get('basis') if text(data.get('basis')) else raw_event['note']
        ns = entities(g); nid = data.get('nodeId'); node = ns.get(nid)
        before_operation = copy.deepcopy(g)
        before_support = set(support_state(g)['activeIds']); touched = set()
        affected = set(); event_type = 'edited'; relation_ids = []
        evidence_ids = None; action_result = None; operation_action_id = None
        review_refs = None
        review_resolutions = None
        operation_record_type = None; operation_record_title = None; operation_record_target = None
        selected_by_action = []
        def target(kind=None, operation='edit'):
            require(node is not None and (kind is None or node['kind'] == kind), 'TARGET_KIND')
            guard(node, raw_event, operation); return node
        if cmd=='recommendation_packages':
            require(set(data)=={'packageIds'} and unique_strings(data['packageIds']) and all(_uuid(i) for i in data['packageIds']),'SCHEMA_INVALID')
            require(g['recommendationPackageIds']!=data['packageIds'],'NO_CHANGE')
            for root in g['rootCauses']:guard(ns[root['requirementId']],raw_event,'edit')
            g['recommendationPackageIds']=copy.deepcopy(data['packageIds'])
        elif cmd=='lens_application':
            require(set(data)=={'nodeIds','observedPins','recommendationPins','lensPins','evidenceIds'} and unique_strings(data['nodeIds']) and
                all(i in ns for i in data['nodeIds']) and unique_strings(data['evidenceIds']) and
                all(ns.get(i,{}).get('kind') in ('context','evidence') for i in data['evidenceIds']),'SCHEMA_INVALID')
            for i in data['nodeIds']:guard(ns[i],raw_event,'edit')
            affected.update(data['nodeIds']);event_type='lens_application_recorded'
        elif cmd in ('finding_disposition',):
            require(not paper,'FINDING_PROCESS_ONLY')
            affected,relation_ids,evidence_ids=FINDINGS.mutate(g,cmd,data,raw_event,sys.modules[__name__])
            if cmd=='finding_disposition':touched.update(affected)
            else:event_type='created' if data['decisionId'] not in entities(before_operation) else 'linked'
        elif cmd in ('finding_transfer','decision_context','context_group','requirement_decision','context_record'):
            require(not paper,'ANALYSIS_PROCESS_ONLY')
            affected=ANALYSIS.mutate(g,cmd,data,raw_event,sys.modules[__name__])
            touched.update(affected)
            if cmd=='requirement_decision':event_type='linked' if data['decisionId'] in entities(before_operation) else 'created'
            if cmd=='finding_transfer':_mark_review(g,{data['nodeId']},raw_event['id'],touched,raw_event)
        elif cmd == 'lock_set':
            require(set(data) == {'nodeId','operation','mode','principals','message'}, 'LOCK_SET_FIELDS')
            locked_node = target(operation='lock_set')
            require(actor == 'user' and text(raw_event.get('authorityPrincipal')), 'LOCK_USER_PATH_REQUIRED')
            spec = {'mode':data['mode'], 'principals':copy.deepcopy(data['principals']), 'message':data['message']}
            candidate = copy.deepcopy(locked_node); candidate['locks'] = copy.deepcopy(locked_node.get('locks', {}))
            candidate['locks'][data['operation']] = spec
            _validate_policy(candidate)
            require(locked_node.get('locks', {}).get(data['operation']) != spec, 'NO_CHANGE')
            locked_node.setdefault('locks', {})[data['operation']] = spec
            _bump(ns, nid, touched); affected.add(nid); event_type = 'lock_set'
        elif cmd == 'lock_remove':
            require(set(data) == {'nodeId','operation','disposition'} and text(data.get('disposition')), 'LOCK_REMOVE_FIELDS')
            locked_node = target(operation='lock_remove')
            require(actor == 'user' and text(raw_event.get('authorityPrincipal')), 'LOCK_USER_PATH_REQUIRED')
            require(data['operation'] in locked_node.get('locks', {}), 'LOCK_NOT_FOUND')
            del locked_node['locks'][data['operation']]
            if not locked_node['locks']: locked_node.pop('locks')
            _bump(ns, nid, touched); affected.add(nid); event_type = 'lock_removed'
        elif cmd == 'add':
            require(set(data) <= {'entity','location','workGraphId','initialRelations'} and isinstance(data.get('entity'), dict), 'ADD_FIELDS')
            value = copy.deepcopy(data['entity']); location = data.get('location', 'graph')
            require(location in ('graph','external') and text(value.get('id')) and value['id'] not in ns, 'NEW_ENTITY')
            kind = value.get('kind'); require(kind in ENTITY_KINDS, 'NEW_ENTITY_KIND')
            require('revision' not in value or value['revision'] == 1, 'NEW_REVISION_MUST_START_AT_ONE')
            require('review' not in value, 'NEW_REVIEW_NOT_ALLOWED')
            if kind in NODE_KINDS:
                require('result' not in value or value['result'] ==
                        {'state':'open','truth':'unknown'}, 'NEW_RESULT_NOT_ALLOWED')
            value['revision'] = 1
            if kind in NODE_KINDS:
                value['result'] = {'state':'open','truth':'unknown'}
            if kind == 'decision':
                require('findingOrigin' not in value,'NEW_FINDING_ORIGIN_NOT_ALLOWED')
                require(not paper or 'decisionContextIds' not in value, 'DECISION_CONTEXT_PROCESS_ONLY')
                if 'contextNotes' in value:require(isinstance(value['contextNotes'],dict) and all(text(i) and text(v) for i,v in value['contextNotes'].items()),'CONTEXT_NOTES')
                require(value.get('selectionState', 'discovered') in ('discovered','unselected'), 'NEW_DECISION_STATE')
                value['selectionState'] = value.get('selectionState', 'discovered')
                require(unique_strings(value.get('decisionContextIds', [])) and
                        all(ref != value['id'] and ref in ns and
                            ns[ref]['kind'] in ENTITY_KINDS and
                            ref in {n['id'] for n in g['nodes']+g['objects']}
                            for ref in value.get('decisionContextIds', [])), 'DECISION_CONTEXT_REFS')
            if kind == 'action':
                require('referenceBindings' not in value,'ACTION_REF_BINDINGS_READ_ONLY')
                require(value.get('actionType') in ('task','select_decision','decide_acceptance','discover_requirement','discover_decision','rename_block') and
                        isinstance(value.get('lowLevel'), bool) and unique_strings(value.get('targetIds', [])) and unique_strings(value.get('groupIds', [])), 'NEW_ACTION_FIELDS')
                require(value['actionType'] not in ('discover_requirement', 'discover_decision', 'rename_block'),
                        'OPERATION_RECORD_ONLY')
                value.setdefault('targetIds', []); value.setdefault('groupIds', [])
                if location == 'graph':
                    require(value['lowLevel'] is False and value['actionType'] in ('task','select_decision','decide_acceptance'), 'GRAPH_ACTION_TYPE')
                else:
                    require(value['lowLevel'] is True or value['actionType'] == 'task', 'EXTERNAL_ACTION_ROLE')
            require(text(value.get('title')) and isinstance(value.get('description'), str), 'NEW_ENTITY_TEXT')
            if kind == 'finding':
                require(not paper,'FINDING_PROCESS_ONLY')
                FINDINGS.normalize(g,value,sys.modules[__name__],raw_event)
            QUESTIONS.legacy_write(value,None)
            if kind == 'question':
                require(not paper or not value.get('answers') and not value.get('sourceRefs'),'QUESTION_TEMPLATE_LIVE_DATA')
                QUESTIONS.create(value,g,sys.modules[__name__])
            if kind == 'requirement': require(text(value.get('scope')), 'REQUIREMENT_SCOPE')
            if kind == 'canon': validate_theory(value)
            if kind in ('context','info'): require(text(value.get('value')), 'OBJECT_VALUE')
            require(kind!='evidence','EVIDENCE_RETIRED_USE_CONTEXT')
            if location == 'external':
                require(kind == 'action' and 'initialRelations' not in data and 'workGraphId' not in data, 'EXTERNAL_ACTION_ADD')
                g['externalActions'].append(value)
            else:
                g['nodes' if kind in NODE_KINDS else 'objects'].append(value)
                if data.get('workGraphId') is not None:
                    wg = next((w for w in g['workGraphs'] if w['id'] == data['workGraphId']), None)
                    require(wg is not None, 'WORK_GRAPH_UNKNOWN')
                    if value['id'] not in wg['memberIds']: wg['memberIds'].append(value['id'])
                relations = data.get('initialRelations', [])
                require(isinstance(relations, list), 'INITIAL_RELATIONS')
                for relation in relations:
                    _validate_new_relation(g, relation, value['id'])
                    relation_ns = entities(g)
                    guard(relation_ns[relation['from']], raw_event, 'link')
                    guard(relation_ns[relation['to']], raw_event, 'link')
                g['edges'].extend(copy.deepcopy(relations)); relation_ids = [r['id'] for r in relations]
                if relations:
                    endpoints = {endpoint for relation in relations for endpoint in (relation['from'], relation['to'])}
                    existing_endpoints = endpoints - {value['id']}
                    affected |= _review_impact(g, existing_endpoints)
                    # Affected owners are reviewed through the unified before/after comparison.
            affected.add(value['id']); event_type = 'created'
            if kind in ('requirement', 'decision') and not paper:
                operation_record_type = ('discover_requirement' if kind == 'requirement' else 'discover_decision')
                operation_record_title = value['title']
                operation_record_target = value['id']
        elif cmd=='question_migrate':
            require(not paper,'QUESTION_PROCESS_ONLY')
            target()
            require(node['kind'] in ('finding','decision'),'QUESTION_MIGRATE_KIND')
            created=QUESTIONS.migrate(node,data,g,sys.modules[__name__],raw_event)
            _bump(ns,nid,touched);affected.update([nid,*created])
        elif cmd in ('question_answer','question_assess'):
            require(not paper,'QUESTION_PROCESS_ONLY')
            target('question')
            if cmd=='question_answer':QUESTIONS.answer(node,data,g,sys.modules[__name__],raw_event)
            else:QUESTIONS.assess(node,data,raw_event)
            _bump(ns,nid,touched);affected.add(nid)
        elif cmd == 'edit':
            target();editable={'title','description','tags'}|{
                'requirement':{'scope'},'decision':{'decisionContextIds','contextNotes','analysisSources','impactTargetIds'},'action':{'actionType','targetIds','groupIds','estimates','resultCondition','subjectRefs'},
                'canon':{'guidance','canons','knownErrors'},'context':{'value','contextGroupId','scope','version','source','artifact'},'info':{'value'},'evidence':{'claim','scope','version','source'},'finding':FINDINGS.EDITABLE,'question':{'relatedRefs','sourceRefs','impact','answerCondition','blocking'}}[node['kind']]
            if node['kind']=='decision':editable |= FINDINGS.COMMON
            require(set(data) == {'nodeId','changes','cosmetic'} and isinstance(data.get('changes'), dict) and
                bool(data['changes']) and set(data['changes']) <= editable and isinstance(data['cosmetic'], bool), 'EDIT_FIELDS')
            if data['cosmetic']:
                require(set(data['changes']) == {'title'}, 'COSMETIC_SEMANTIC_EDIT')
            if 'decisionContextIds' in data['changes']:
                require(not paper, 'DECISION_CONTEXT_PROCESS_ONLY')
                refs=data['changes']['decisionContextIds']
                require(unique_strings(refs) and all(ref != nid and ref in ns and
                        ns[ref]['kind'] in ENTITY_KINDS and
                        ref in {n['id'] for n in g['nodes']+g['objects']}
                        for ref in refs), 'DECISION_CONTEXT_REFS')
            if 'contextNotes' in data['changes']:require(isinstance(data['changes']['contextNotes'],dict) and all(text(i) and text(v) for i,v in data['changes']['contextNotes'].items()),'CONTEXT_NOTES')
            if node['kind']=='canon':validate_theory({**node,**data['changes']})
            require(any(node.get(k) != v for k,v in data['changes'].items()), 'NO_CHANGE')
            if node['kind']=='finding' and 'evidenceIds' in data['changes']:
                require(unique_strings(data['changes']['evidenceIds']) and all(ns.get(i,{}).get('kind') in ('context','evidence') for i in data['changes']['evidenceIds']),'FINDING_EVIDENCE_REQUIRED')
            previous_title = node['title']
            changes=copy.deepcopy(data['changes'])
            QUESTIONS.legacy_write(changes,node)
            if node['kind']=='action' and changes.get('estimates','missing') is None:
                node.pop('estimates',None);changes.pop('estimates')
            if node['kind']=='context' and 'contextGroupId' in changes and changes['contextGroupId'] is None:
                node.pop('contextGroupId',None);changes.pop('contextGroupId')
            if node['kind']=='question':
                QUESTIONS.refs(changes.get('relatedRefs',node['relatedRefs']),g,sys.modules[__name__],node)
                QUESTIONS.refs(changes.get('sourceRefs',node['sourceRefs']),g,sys.modules[__name__],node)
                if 'assessment' in node and not data['cosmetic']:node['assessmentReviewRequired']=True
            node.update(changes); _bump(ns, nid, touched); affected |= _review_impact(g, {nid})
            if not paper and node['kind'] in ('requirement', 'decision') and previous_title != node['title']:
                operation_record_type = 'rename_block'
                operation_record_title = node['title']
                operation_record_target = nid
            if not data['cosmetic']:
                if node['kind'] in REVIEW_KINDS and _native_definition(before_operation,nid)!=_native_definition(g,nid):
                    _mark_review(g, {nid}, raw_event['id'], touched, raw_event)
            event_type = 'edited'
        elif cmd == 'policy_change':
            require(not paper,'POLICY_PROCESS_ONLY')
            action=data.get('action')
            require(action in ('policy_save','preset_save','binding_save','binding_remove','binding_activate','binding_disable','automatic_activate','automatic_disable','automatic_remove','catalog_migrate','policy_status'), 'POLICY_ACTION')
            require(set(data)=={'action','value'}, 'POLICY_CHANGE_FIELDS')
            value=copy.deepcopy(data['value'])
            require(isinstance(value,dict),'POLICY_CHANGE_SCHEMA')
            if 'expectedRevision' in value:require(type(value['expectedRevision']) is int and value['expectedRevision']>=1,'POLICY_BINDING_CAS')
            if action=='policy_save':
                require(not value.get('id','').startswith('builtin:') and value.get('origin','user')=='user','POLICY_SYSTEM_IMMUTABLE')
                existing=_policy_versions(g,value.get('id'))
                require(value.get('version')==(existing[-1]['version']+1 if existing else 1),'POLICY_VERSION_CONFLICT')
                POLICIES.validate_definition(value,sys.modules[__name__])
                g.setdefault('dependencyPolicies',[]).append(value);event_type='policy_changed'
            elif action=='catalog_migrate':
                g['dependencyPresets']=[];event_type='policy_changed'
            elif action=='policy_status':
                require(set(value)=={'id','version','status'} and value['status'] in POLICY_STATUSES,'POLICY_STATUS')
                prior=_policy_at(g,value['id'],value['version'])
                require(prior is not None and not prior['id'].startswith('builtin:'),'POLICY_SYSTEM_IMMUTABLE')
                prior['status']=value['status'];event_type='policy_changed'
            elif action=='preset_save':
                # Compatibility for old clients; new UI never creates presets.
                require(not any(p['id']==value.get('id') for p in g.get('dependencyPresets',[])), 'POLICY_PRESET_CONFLICT')
                g.setdefault('dependencyPresets',[]).append(value);event_type='policy_changed'
            elif action.startswith('automatic_'):
                require(set(value)<={'id','expectedRevision'} and text(value.get('id')),'POLICY_AUTOMATIC_FIELDS')
                key=value.get('id');states=g.setdefault('dependencyAutomaticStates',{})
                row=POLICIES.automatic_matches(g,sys.modules[__name__]).get(key)
                prior=states.get(key)
                require(value.get('expectedRevision',(prior or {}).get('revision',1))==(prior or {}).get('revision',1),'POLICY_BINDING_CAS')
                require(row is not None or prior is not None,'POLICY_AUTOMATIC_UNKNOWN')
                require(not prior or prior['status']!='deleted','POLICY_BINDING_DELETED')
                if action=='automatic_activate':require(row is not None,'POLICY_BINDING_INAPPLICABLE:AUTOMATIC_RELATION_MISSING')
                source=row['sourceId'] if row else prior['sourceId'];target=row['dependentId'] if row else prior['targetId']
                for endpoint in (source,target):
                    if endpoint in ns:
                        guard(ns[endpoint],raw_event,'unlink' if action=='automatic_remove' else 'link')
                        if action=='automatic_remove':guard(ns[endpoint],raw_event,'dependency_remove')
                states[key]={**(prior or {}),'id':key,'sourceId':source,'targetId':target,
                    'origin':row['origin'] if row else prior['origin'],
                    'status':'active' if action=='automatic_activate' else 'deleted' if action=='automatic_remove' else 'disabled',
                    'reasonCode':None if action=='automatic_activate' else 'removed' if action=='automatic_remove' else 'manual',
                    'revision':(prior or {}).get('revision',0)+1}
                affected.update(i for i in (source,target) if i in ns)
                event_type='binding_changed'
            else:
                prior=next((b for b in g.get('dependencyBindings',[]) if b['id']==value.get('id')),None)
                if action!='binding_save':
                    require(prior is not None and set(value)<={'id','expectedRevision'},'POLICY_BINDING_UNKNOWN')
                    require(value.get('expectedRevision',prior.get('revision',1))==prior.get('revision',1),'POLICY_BINDING_CAS')
                    value=copy.deepcopy(prior)
                    value['enabled']=action=='binding_activate'
                    value['status']='deleted' if action=='binding_remove' else 'active' if value['enabled'] else 'disabled'
                    value['reasonCode']=None if value['enabled'] else 'removed' if action=='binding_remove' else 'manual'
                require(prior is None or prior.get('status')!='deleted','POLICY_BINDING_DELETED')
                require('observedSources' not in value or value['observedSources']==(prior or {}).get('observedSources'),'POLICY_OBSERVATION_SNAPSHOT_READONLY')
                if prior and 'observedSources' in prior:value.setdefault('observedSources',copy.deepcopy(prior['observedSources']))
                candidate=_policy_at(g,value.get('policyId'),value.get('policyVersion'))
                require(candidate is not None,'POLICY_BINDING_POLICY')
                require(not candidate.get('automatic'),'POLICY_AUTOMATIC_MATCH_ONLY')
                configuration_changed=prior is None or any(prior.get(k)!=value.get(k) for k in ('policyId','policyVersion','targetId','sourceId','parentId','participantBindings'))
                if configuration_changed:
                    POLICIES.binding_valid(value,candidate,sys.modules[__name__])
                    _,_,problems=POLICIES.resolve(g,candidate,value,sys.modules[__name__])
                    require(not problems,'POLICY_BINDING_INAPPLICABLE:'+','.join(problems))
                if value.get('enabled'):
                    require(candidate['status']!='disabled' and (prior is not None or candidate['status']=='active'),'POLICY_VERSION_DISABLED')
                    POLICIES.binding_valid(value,candidate,sys.modules[__name__])
                    _,_,problems=POLICIES.resolve(g,candidate,value,sys.modules[__name__])
                    require(not problems,'POLICY_BINDING_INAPPLICABLE:'+','.join(problems))
                participants={value.get('targetId'),value.get('sourceId'),value.get('parentId')} | set(value.get('participantBindings',{}).values())
                if prior:
                    participants|={prior['targetId'],prior['sourceId'],prior['parentId']}|set(prior.get('participantBindings',{}).values())
                    require(value.get('revision',prior.get('revision',1))==prior.get('revision',1),'POLICY_BINDING_CAS')
                for endpoint in participants:
                    if endpoint in ns:guard(ns[endpoint],raw_event,'unlink' if action=='binding_remove' else 'link')
                value['revision']=(prior.get('revision',1)+1 if prior else 1)
                value.setdefault('status','active' if value.get('enabled') else 'disabled')
                value.setdefault('reasonCode',None if value.get('enabled') else 'manual')
                if prior:g['dependencyBindings'].remove(prior)
                g.setdefault('dependencyBindings',[]).append(value)
                event_type='binding_changed'
                if value.get('targetId') in ns:affected.add(value['targetId'])
            validate_policy_catalog(g)
        elif cmd == 'dependency_rule':
            require(not paper, 'DECISION_CONTEXT_PROCESS_ONLY')
            mode=data.get('mode')
            require(mode in ('save','remove'), 'DEPENDENCY_RULE_MODE')
            if mode=='save':
                require(set(data)<= {'mode','relation','convertLegacy'} and
                        isinstance(data.get('relation'),dict),'DEPENDENCY_RULE_FIELDS')
                relation=copy.deepcopy(data['relation'])
                _relation_error(relation,ns)
                require(relation['type']=='DEPENDS_ON','DEPENDENCY_RULE_RELATION')
                old=next((e for e in g['edges'] if e['id']==relation['id']),None)
                if old:
                    require(old['type']=='DEPENDS_ON' and old['from']==relation['from'] and
                            old['to']==relation['to'],'DEPENDENCY_RULE_ENDPOINT_LOCKED')
                    require(old!=relation,'NO_CHANGE')
                else:
                    _validate_new_relation(g,relation)
                legacy=data.get('convertLegacy')
                if legacy is not None:
                    require(legacy==relation['from'] and relation.get('dependencyPurpose')=='decisionContext' and
                        ns[relation['to']]['kind']=='decision' and
                        legacy in ns[relation['to']].get('decisionContextIds',[]),
                        'DEPENDENCY_LEGACY_CONVERSION')
                    guard(ns[relation['to']],raw_event,'edit')
                    ns[relation['to']]['decisionContextIds'].remove(legacy)
                else:
                    require(not(relation.get('dependencyPurpose')=='decisionContext' and
                        relation['from'] in ns[relation['to']].get('decisionContextIds',[])),
                        'DEPENDENCY_LEGACY_CONVERSION_REQUIRED')
                guard(ns[relation['from']],raw_event,'link')
                guard(ns[relation['to']],raw_event,'link')
                if old:g['edges'].remove(old)
                g['edges'].append(relation)
                for i in (relation['from'],relation['to']):_bump(ns,i,touched)
                affected.update((relation['from'],relation['to']))
                relation_ids=[relation['id']]
                event_type='edited' if old else 'linked'
            else:
                require(set(data)=={'mode','edgeId'} and text(data.get('edgeId')),
                        'DEPENDENCY_RULE_FIELDS')
                old=next((e for e in g['edges'] if e['id']==data['edgeId'] and
                          e['type']=='DEPENDS_ON'),None)
                require(old is not None,'DEPENDENCY_RULE_UNKNOWN')
                for i in (old['from'],old['to']):guard(ns[i],raw_event,'unlink')
                g['edges'].remove(old)
                for i in (old['from'],old['to']):_bump(ns,i,touched)
                affected.update((old['from'],old['to']))
                relation_ids=[old['id']];event_type='unlinked'
        elif cmd == 'link':
            require(set(data) in ({'relation'},{'edge'}), 'LINK_FIELDS')
            relation = copy.deepcopy(data.get('relation', data.get('edge'))); _validate_new_relation(g, relation)
            require(not(relation.get('dependencyPurpose')=='decisionContext' and
                relation['from'] in ns[relation['to']].get('decisionContextIds',[])),
                'DEPENDENCY_LEGACY_CONVERSION_REQUIRED')
            guard(ns[relation['from']], raw_event, 'link'); guard(ns[relation['to']], raw_event, 'link')
            g['edges'].append(relation); relation_ids = [relation['id']]
            for endpoint in (relation['from'], relation['to']):
                _bump(ns, endpoint, touched); affected.add(endpoint)
            affected |= _review_impact(g, {relation['from'], relation['to']}); # Subscription/structural changes are handled by unified impact calculation.
            event_type = 'linked'
        elif cmd == 'unlink':
            require(set(data) <= {'edgeId','relationId','disposition'} and text(data.get('edgeId') or data.get('relationId')), 'UNLINK_FIELDS')
            rel_id = data.get('edgeId') or data.get('relationId')
            detached_proposals=[]
            relation = next((e for e in g['edges'] if e['id'] == rel_id), None)
            if relation:
                guard(ns[relation['from']], raw_event, 'unlink'); guard(ns[relation['to']], raw_event, 'unlink')
                if relation['type']=='FINDING_RESPONSE':
                    detached_proposals=[e for e in g['edges'] if e['type']=='FINDING_PROPOSAL' and e['from']==relation['to'] and e.get('findingId')==relation['findingId']]
                    for edge in detached_proposals:
                        guard(ns[edge['from']],raw_event,'unlink');guard(ns[edge['to']],raw_event,'unlink');affected.update((edge['from'],edge['to']))
                    g['edges']=[e for e in g['edges'] if e not in detached_proposals]
                    for group in list(g['decisionGroups']):
                        if ns[group['parentId']]['kind']=='decision':
                            group['members']=[m for m in group['members'] if any(e['type']=='FINDING_PROPOSAL' and e['from']==group['parentId'] and e['to']==m['decisionId'] for e in g['edges'])]
                            if not group['members']:g['decisionGroups'].remove(group)
                    for ident in affected:_bump(ns,ident,touched)
                g['edges'].remove(relation); affected.update((relation['from'], relation['to']))
                for endpoint in (relation['from'], relation['to']): _bump(ns, endpoint, touched)
            else:
                found = None
                for group in g['decisionGroups']:
                    for member in group['members']:
                        if member['id'] == rel_id: found = (group, member); break
                    if found: break
                require(found is not None, 'RELATION_NOT_FOUND')
                group, member = found; require(len(group['members']) > 1, 'GROUP_EMPTY')
                guard(ns[group['parentId']], raw_event, 'unlink'); guard(ns[member['decisionId']], raw_event, 'unlink')
                group['members'].remove(member); affected.update((group['parentId'], member['decisionId']))
                _bump(ns, group['parentId'], touched); _bump(ns, member['decisionId'], touched)
            relation_ids = [rel_id]+[e['id'] for e in detached_proposals]; event_type = 'unlinked'
            affected |= _review_impact(g, affected); # Subscription/structural changes are handled by unified impact calculation.
        elif cmd == 'select':
            target('decision', 'select'); require(set(data) == {'nodeId'}, 'SELECT_FIELDS')
            require(node['selectionState'] != 'selected', 'NO_CHANGE')
            _selection_allowed(g, [nid], raw_event)
            require(not node.get('review', {}).get('required'), 'REVIEW_REQUIRED')
            node['selectionState'] = 'selected'; _bump(ns, nid, touched); affected.add(nid); event_type = 'decision_selected'
        elif cmd == 'withdraw':
            target('decision', 'withdraw'); require(set(data) == {'nodeId'}, 'WITHDRAW_FIELDS')
            require(node['selectionState'] == 'selected', 'NO_CHANGE')
            require(node['result']['state'] != 'confirmed', 'DECISION_REOPEN_REQUIRED')
            node['selectionState'] = 'unselected'; _bump(ns, nid, touched); affected.add(nid); event_type = 'decision_unselected'
        elif cmd == 'complete':
            require(set(data) <= {'nodeId','basis','evidenceIds','decisionOutcome'} and
                    {'nodeId','basis','evidenceIds'} <= set(data) and text(data.get('basis')) and
                    unique_strings(data.get('evidenceIds')), 'SCHEMA_INVALID')
            require('decisionOutcome' not in data or data['decisionOutcome'] in
                    ('selected','unselected'), 'SCHEMA_INVALID')
            completion_target = ns.get(nid); require(completion_target is not None and completion_target['kind'] in NODE_KINDS, 'COMPLETE_TARGET')
            if (completion_target['kind'] == 'action' and completion_target['lowLevel']
                    and completion_target['actionType'] != 'task'):
                require(False, 'OPERATION_RECORD_ONLY')
            if completion_target['kind'] == 'decision': require(completion_target['selectionState'] == 'selected', 'DECISION_NOT_SELECTED')
            guard(completion_target, raw_event, 'complete')
            evidence_ids = data['evidenceIds']
            external_task = completion_target in g['externalActions'] and completion_target['kind'] == 'action' and completion_target['actionType'] == 'task'
            require(nid in set(support_state(g)['activeIds']) or external_task, 'NO_ACTIVE_BASIS')
            require(not completion_target.get('review', {}).get('required'), 'REVIEW_REQUIRED')
            state = completion_state(g).get(nid, {'blockers': []})
            require(not state['blockers'], 'OBLIGATIONS_OPEN:' + ','.join(state['blockers']))
            require(bool(evidence_ids) and all(i in ns and ns[i]['kind'] in ('context','evidence')
                    for i in evidence_ids), 'RESULT_EVIDENCE_REQUIRED')
            if completion_target['kind'] == 'action' and completion_target['actionType'] in ('select_decision','decide_acceptance'):
                targets = completion_target['targetIds']; require(bool(targets), 'ACTION_TARGETS_INVALID')
                if completion_target['actionType'] == 'decide_acceptance':
                    require('decisionOutcome' in data, 'ACTION_OUTCOME_REQUIRED')
                    require(len(targets) == 1, 'ACTION_TARGETS_INVALID')
                    _selection_allowed(g, targets, raw_event) if data['decisionOutcome'] == 'selected' else None
                    if data['decisionOutcome'] == 'unselected':
                        d = ns[targets[0]]
                        require(d['result']['state'] != 'confirmed', 'DECISION_REOPEN_REQUIRED')
                        if d['selectionState'] == 'selected':
                            guard(d, raw_event, 'withdraw')
                    action_result = {'decisionId': targets[0], 'decisionOutcome': data['decisionOutcome']}; operation_action_id = nid
                else:
                    require('decisionOutcome' not in data, 'ACTION_OUTCOME_NOT_ALLOWED')
                    require(all(ns[i]['selectionState'] != 'selected' for i in targets), 'NO_CHANGE')
                    _selection_allowed(g, targets, raw_event)
                    selected_by_action = sorted(targets)
                # Validate the complete target set before changing any target.
                if completion_target['actionType'] == 'select_decision' or data.get('decisionOutcome') == 'selected':
                    for decision_id in targets:
                        ns[decision_id]['selectionState'] = 'selected'; _bump(ns, decision_id, touched)
                else:
                    ns[targets[0]]['selectionState'] = 'unselected'; _bump(ns, targets[0], touched)
                affected.update(targets)
            else:
                require('decisionOutcome' not in data, 'ACTION_OUTCOME_NOT_ALLOWED')
            require(completion_target['result']['state'] != 'confirmed', 'NO_CHANGE')
            completion_target['result'] = {'state':'confirmed','truth':'true','eventId':raw_event['id']}; _bump(ns, nid, touched)
            affected.add(nid)
            event_type = RESULT_TYPES[completion_target['kind']]
        elif cmd == 'reopen':
            target(operation='reopen'); require(set(data) == {'nodeId','basis'} and text(data.get('basis')), 'REOPEN_FIELDS')
            require(node['kind'] in NODE_KINDS and node['result']['state'] == 'confirmed', 'REOPEN_REQUIRED')
            node['result'] = {'state':'open','truth':'unknown'}; _bump(ns, nid, touched); affected.add(nid)
            affected |= {e['from'] for e in active_edges(g) if e['to'] == nid and e['type'] in DEPENDENCY_TYPES}
            affected |= {group['parentId'] for group in g['decisionGroups'] if any(m['decisionId'] == nid for m in group['members'])}
            event_type = 'reopened'
        elif cmd == 'decision_group':
            require(data.get('group',{}).get('parentId') not in {n['id'] for n in g['nodes'] if n['kind']=='decision'} or any(v['id']==data.get('group',{}).get('id') for v in g['decisionGroups']),'FINDING_WORKFLOW_RETIRED')
            require(set(data) == {'group'} and isinstance(data['group'], dict), 'DECISION_GROUP_FIELDS')
            group = copy.deepcopy(data['group']); old = next((x for x in g['decisionGroups'] if x['id'] == group.get('id')), None)
            parent = ns.get(group.get('parentId')); require(parent is not None and parent['kind'] in ('requirement','decision'), 'DECISION_GROUP_PARENT')
            guard(parent, raw_event, 'link')
            if old:
                guard(ns[old['parentId']], raw_event, 'unlink')
                for member in old['members']:
                    if member['decisionId'] in ns: guard(ns[member['decisionId']], raw_event, 'unlink')
            require(isinstance(group.get('members'), list) and bool(group['members']), 'DECISION_GROUP_MEMBERS')
            for member in group['members']:
                require(isinstance(member, dict) and set(member) == {'id','decisionId'} and text(member.get('id')) and
                        member.get('decisionId') in ns and ns[member['decisionId']]['kind'] == 'decision', 'DECISION_GROUP_MEMBER')
                guard(ns[member['decisionId']], raw_event, 'link')
            require(len({m['id'] for m in group['members']}) == len(group['members']) and
                    len({m['decisionId'] for m in group['members']}) == len(group['members']), 'DECISION_GROUP_MEMBER_DUPLICATE')
            require(old != group, 'NO_CHANGE')
            membership_pairs={(group['parentId'],m['decisionId']) for m in group['members']}
            replaced=[e for e in g['edges'] if e['type']=='DRIVES' and (e['from'],e['to']) in membership_pairs]
            for e in replaced:
                guard(ns[e['from']],raw_event,'unlink');guard(ns[e['to']],raw_event,'unlink')
            g['edges']=[e for e in g['edges'] if e not in replaced]
            if old: g['decisionGroups'].remove(old)
            g['decisionGroups'].append(group)
            _selected_conflicts(g, [])
            affected.add(group['parentId']); affected.update(m['decisionId'] for m in group['members'])
            if old:
                affected.add(old['parentId'])
                affected.update(m['decisionId'] for m in old['members'])
            for ident in affected:
                _bump(ns, ident, touched)
            affected |= _review_impact(g, affected); # Unified one-hop structural impact below.
            event_type = 'group_changed'
        elif cmd == 'root_cause':
            require(set(data) == {'cause'} and isinstance(data['cause'], dict) and
                    set(data['cause']) == {'id','requirementId','reason','enabled'}, 'ROOT_CAUSE_FIELDS')
            cause = copy.deepcopy(data['cause']); parent = ns.get(cause.get('requirementId'))
            require(text(cause.get('id')) and parent is not None and parent['kind'] == 'requirement' and
                    text(cause.get('reason')) and isinstance(cause.get('enabled'), bool), 'ROOT_CAUSE')
            old = next((x for x in g['rootCauses'] if x['id'] == cause['id']), None)
            guard(parent, raw_event, 'link' if cause['enabled'] else 'withdraw')
            if old == cause: raise ValueError('DECISION_NO_CHANGE')
            if old:
                previous=ns[old['requirementId']]
                guard(previous, raw_event, 'unlink')
                affected.add(old['requirementId'])
                _bump(ns, old['requirementId'], touched)
                g['rootCauses'].remove(old)
            g['rootCauses'].append(cause); _bump(ns, parent['id'], touched)
            affected.add(parent['id']); affected |= _review_impact(g, affected); # Root support changes are structural, not a recursive stale cascade.
            event_type = 'root_cause_changed'
        elif cmd == 'work_graph':
            require(set(data) == {'workGraph'}, 'WORK_GRAPH_FIELDS')
            wg = copy.deepcopy(data['workGraph'])
            require(isinstance(wg, dict) and
                    {'id','title','rootIds','memberIds'} <= set(wg) <=
                    {'id','title','rootIds','memberIds','colorKey'} and text(wg.get('id')) and
                    text(wg.get('title')) and unique_strings(wg.get('rootIds')) and unique_strings(wg.get('memberIds')) and
                    set(wg['rootIds']) <= set(wg['memberIds']) and set(wg['memberIds']) <= set(ns) and
                    all(ns[i]['kind'] == 'requirement' for i in wg['rootIds']) and
                    ('colorKey' not in wg or wg['colorKey'] in WORK_GRAPH_COLOR_KEYS), 'WORK_GRAPH')
            old_index = next((index for index, value in enumerate(g['workGraphs']) if value['id'] == wg['id']), None)
            old = g['workGraphs'][old_index] if old_index is not None else None
            if old and 'colorKey' not in wg and 'colorKey' in old:
                wg['colorKey'] = old['colorKey']
            require(old != wg, 'NO_CHANGE')
            before_members = set(old['memberIds']) if old else set()
            after_members = set(wg['memberIds'])
            before_roots = set(old['rootIds']) if old else set()
            after_roots = set(wg['rootIds'])
            guarded_ids = (before_members ^ after_members) | (before_roots ^ after_roots)
            for ident in sorted(guarded_ids): guard(ns[ident], raw_event, 'edit')
            # The history event references the complete before/after membership,
            # but cosmetic metadata changes do not revise every member entity.
            affected.update(before_members | after_members)
            if old_index is not None: g['workGraphs'][old_index] = wg
            else: g['workGraphs'].append(wg)
            for ident in sorted(guarded_ids): _bump(ns, ident, touched)
            event_type = 'work_graph_changed'
        elif cmd == 'review':
            require(set(data) <= {'nodeId','nodeIds','observed','observedPins','basis'} and
                    ('nodeId' in data or 'nodeIds' in data), 'REVIEW_FIELDS')
            targets = data.get('nodeIds', [data.get('nodeId')]); require(unique_strings(targets), 'REVIEW_TARGETS')
            observed = data.get('observed', data.get('observedPins'))
            require(isinstance(observed, dict), 'REVIEW_PINS_REQUIRED')
            expected_pins = {}
            for ident in targets:
                target_node = ns.get(ident)
                require(target_node is not None and target_node.get('review', {}).get('required'), 'REVIEW_REQUIRED')
                guard(target_node, raw_event, 'review')
                for pin_id, revision in pins(g, ident).items():
                    require(pin_id not in expected_pins or expected_pins[pin_id] == revision,
                            'REVIEW_INPUTS_CHANGED')
                    expected_pins[pin_id] = revision
            require(observed == expected_pins, 'REVIEW_INPUTS_CHANGED')
            pin_context = raw_event.get('reviewPinContext')
            require(isinstance(pin_context, dict) and
                    set(pin_context) == {'packageId', 'graphRevision', 'sha256'} and
                    _uuid(pin_context.get('packageId')) and
                    pin_context.get('graphRevision') == g['revision'] and
                    pin_context.get('sha256') == hashlib.sha256(json.dumps(
                        g, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                        allow_nan=False).encode('utf-8')).hexdigest(), 'REVIEW_PIN_CONTEXT_REQUIRED')
            review_refs = [{'schemaVersion':1, 'packageId':pin_context['packageId'],
                            'identitySpace':g['identitySpace'], 'nodeId':ident,
                            'mode':'historical', 'revision':revision,
                            'graphRevision':g['revision'], 'sha256':pin_context['sha256']}
                           for ident, revision in sorted(expected_pins.items())]
            review_resolutions=[{'nodeId':ident,'causeEventIds':copy.deepcopy(ns[ident]['review']['causeEventIds'])} for ident in targets]
            for ident in targets:
                ns[ident]['review'] = {'required':False,'causeEventIds':[],'pins':[]}; _bump(ns, ident, touched)
            affected.update(targets); event_type = 'edited'
        elif cmd == 'remove':
            require(coordinated, 'REMOVE_REQUIRES_COORDINATOR')
            require(set(data) == {'nodeIds'} and unique_strings(data.get('nodeIds')) and bool(data['nodeIds']), 'REMOVE_FIELDS')
            removed = set(data['nodeIds']); require(removed <= set(ns), 'REMOVE_TARGETS')
            require(not any(n['kind'] == 'requirement' and n['id'] in removed and
                any(c['enabled'] and c['requirementId'] == n['id'] for c in g['rootCauses'])
                for n in ns.values()), 'ROOT_CAUSE_REMOVE_REQUIRES_DISABLE')
            review_ids = _review_impact(g, removed) - removed
            for decision in g['nodes']:
                if (decision['kind'] == 'decision' and decision['id'] not in removed and
                        removed.intersection(decision.get('decisionContextIds', []))):
                    guard(decision, raw_event, 'edit')
                    decision['decisionContextIds'] = [r for r in decision['decisionContextIds'] if r not in removed]
                    review_ids.add(decision['id'])
                    affected.add(decision['id'])
                if decision['id'] not in removed and removed.intersection(decision.get('impactTargetIds',[])):
                    guard(decision,raw_event,'edit');decision['impactTargetIds']=[i for i in decision['impactTargetIds'] if i not in removed];affected.add(decision['id'])
            for other in g['nodes']:
                if other.get('findingOrigin',{}).get('findingId') in removed:
                    guard(other,raw_event,'edit');other['findingOrigin']['recordedOnly']=True;affected.add(other['id'])
            QUESTIONS.remove_refs(g,removed,raw_event,sys.modules[__name__],affected,touched)
            for ident in removed: guard(ns[ident], raw_event, 'remove')
            lost_finding_subjects={f['id'] for f in g['objects'] if f['kind']=='finding' and f['subjectId'] in removed}
            removed_relations = [e for e in g['edges'] if e['from'] in removed or e['to'] in removed or e.get('findingId') in (removed|lost_finding_subjects)]
            relation_ids = [e['id'] for e in removed_relations]
            for relation in removed_relations:
                guard(ns[relation['from']], raw_event, 'unlink')
                guard(ns[relation['to']], raw_event, 'unlink')
            for group in list(g['decisionGroups']):
                affected_members = [m for m in group['members'] if m['decisionId'] in removed]
                if group['parentId'] in removed or affected_members:
                    guard(ns[group['parentId']], raw_event, 'unlink')
                    for member in group['members']:
                        guard(ns[member['decisionId']], raw_event, 'unlink')
                    affected.add(group['parentId'])
                    affected.update(m['decisionId'] for m in group['members'])
                    relation_ids.extend(m['id'] for m in
                        (group['members'] if group['parentId'] in removed else affected_members))
                if group['parentId'] in removed:
                    g['decisionGroups'].remove(group)
                else:
                    group['members'] = [m for m in group['members'] if m['decisionId'] not in removed]
                    if not group['members']: g['decisionGroups'].remove(group)
            g['edges'] = [e for e in g['edges'] if e not in removed_relations]
            for group in list(g['decisionGroups']):
                if ns[group['parentId']]['kind']=='decision':
                    group['members']=[m for m in group['members'] if any(e['type']=='FINDING_PROPOSAL' and e['from']==group['parentId'] and e['to']==m['decisionId'] for e in g['edges'])]
                    if not group['members']:g['decisionGroups'].remove(group)
            g['rootCauses'] = [c for c in g['rootCauses'] if c['requirementId'] not in removed]
            g['workGraphs'] = [{**w,'rootIds':[i for i in w['rootIds'] if i not in removed],
                                'memberIds':[i for i in w['memberIds'] if i not in removed]} for w in g['workGraphs']]
            remaining_group_ids = {group['id'] for group in g['decisionGroups']}
            for action in [n for n in g['nodes'] if n['kind'] == 'action'] + g['externalActions']:
                old_targets = list(action['targetIds']); old_groups = list(action['groupIds'])
                action['targetIds'] = [i for i in old_targets if i not in removed]
                action['groupIds'] = [i for i in old_groups if i in remaining_group_ids]
                if old_targets != action['targetIds'] or old_groups != action['groupIds']:
                    if action['id'] not in removed:
                        guard(action, raw_event, 'edit')
                        _bump(ns, action['id'], touched)
                    affected.add(action['id'])
            affected.update(review_ids); affected.update(removed)
            for ident in affected - removed:
                _bump(ns, ident, touched)
            # Unified one-hop structural impact is checked after the removal.
            g['nodes'] = [n for n in g['nodes'] if n['id'] not in removed]
            g['objects'] = [n for n in g['objects'] if n['id'] not in removed]
            g['externalActions'] = [n for n in g['externalActions'] if n['id'] not in removed]
            g['externalRefs']=[r for r in g.get('externalRefs',[]) if r['localId'] not in removed]
            for field in ('factLineage','entityLineage'):
                if field in g:g[field]={i:v for i,v in g[field].items() if i not in removed}
            if g['rootRequirementId'] in removed: g['rootRequirementId'] = None
            relation_ids = sorted(set(relation_ids))
            event_type = 'removed'
        else:
            raise ValueError('DECISION_COMMAND_UNSUPPORTED')
        # Recompute the fixed point after every basis/composition change. The one
        # deterministic cancellation event records all selected descendants lost.
        if cmd in ('withdraw','root_cause','unlink','decision_group','remove','complete','requirement_decision','finding_transfer'):
            cancelled = _cascade(g, tx, timestamp, actor, basis, affected, serial, raw_event, before_support, touched)
            affected.update(cancelled)
        # Single evaluator for *all* stale causes. Structural cascade above
        # remains independent and may legitimately run through grandchildren.
        policy_event={**raw_event,'id':raw_event['id'],'recordedAt':timestamp,'type':event_type,
            'nodeIds':sorted(affected | ({nid} if nid else set()))}
        dependency_transitions=POLICIES.reconcile(before_operation,g,sys.modules[__name__],policy_event)
        dependency_transitions+=POLICIES.reconcile_automatic(before_operation,g,sys.modules[__name__],policy_event)
        dependency_transitions+=POLICIES.lifecycle_transitions(before_operation,g,sys.modules[__name__],dependency_transitions)
        if policy_event.get('lockWarnings'):raw_event['lockWarnings']=policy_event['lockWarnings']
        ANALYSIS.record_disabled_sources(before_operation,g,sys.modules[__name__])
        note_changes=ANALYSIS.reconcile_notes(before_operation,g,raw_event,sys.modules[__name__]);affected.update(note_changes);touched.update(note_changes)
        native_impacts = native_dependency_impacts(before_operation, g,
            cosmetic_ids={nid} if cmd=='edit' and data.get('cosmetic') else (),
            command=cmd,changed_id=nid,policy_event=policy_event)
        for hit in native_impacts:
            endpoints=(hit['sourceId'],hit['dependentId'])
            if hit['changedParts']==['definition'] and any((entities(g).get(i) or entities(before_operation).get(i) or {}).get('kind')=='finding' for i in endpoints):
                hit['valueSnapshot']={'before':_native_definition(before_operation,hit['sourceId']),'after':_native_definition(g,hit['sourceId'])}
        native_targets={row['dependentId'] for row in native_impacts if row['dependentId'] in entities(g)}
        if native_targets and not paper:
            _mark_review(g,native_targets,raw_event['id'],touched,raw_event)
            affected.update(native_targets)
        node_ids = sorted(affected or ({nid} if nid else set()))
        event = _event(raw_event, cmd, data, transaction_id=tx, timestamp=timestamp, by=actor,
            node_ids=node_ids, event_type=event_type, relation_ids=relation_ids if relation_ids else None,
            evidence_ids=evidence_ids, action_result=action_result, operation_action_id=operation_action_id)
        finding_id=data.get('findingId',data.get('nodeId')) if cmd!='add' else data['entity']['id']
        if entities(g).get(finding_id,{}).get('kind')=='finding' and cmd in ('add','edit','finding_disposition','finding_transfer'):
            event['findingChange']={'findingId':finding_id,'before':copy.deepcopy(entities(before_operation).get(finding_id)), 'after':copy.deepcopy(entities(g)[finding_id])}
        if cmd == 'work_graph':
            def work_graph_snapshot(value):
                if value is None: return None
                return {key: copy.deepcopy(value[key]) for key in ('title', 'rootIds', 'memberIds', 'colorKey') if key in value}
            event['workGraphChange'] = {
                'action': 'updated' if old else 'created', 'workGraphId': wg['id'],
                'title': wg['title'], 'before': work_graph_snapshot(old),
                'after': work_graph_snapshot(wg)}
        if dependency_transitions:
            POLICIES.transition_evidence(before_operation,g,sys.modules[__name__],dependency_transitions)
            event['dependencyTransitions']=dependency_transitions
        if review_resolutions is not None:event['reviewResolutions']=review_resolutions
        if native_impacts:
            event['dependencyImpacts'] = native_impacts
        if review_refs is not None:
            event['observedPins'] = review_refs
        if cmd=='complete' and 'placementIds' in raw_event:event['placementIds']=copy.deepcopy(raw_event['placementIds'])
        if cmd=='lens_application':
            for field in ('observedPins','recommendationPins','lensPins','evidenceIds'):event[field]=copy.deepcopy(data[field])
        if cmd == 'add' and relation_ids:
            linked_id = str(uuid.uuid5(uuid.UUID(tx), 'connected-linked:' + str(serial)))
            linked_endpoints = sorted({i for rel in data['initialRelations'] for i in (rel['from'], rel['to'])})
            linked = {'id':linked_id, 'type':'linked', 'transactionId':tx,
                      'recordedAt':timestamp, 'by':actor, 'nodeIds':linked_endpoints,
                      'basis':basis, 'relationIds':sorted(relation_ids)}
            g['events'].append(linked)
        # One host-allocated low-level execution fact accompanies semantic
        # discovery/rename. Paper authoring never manufactures execution history.
        if operation_record_type is not None:
            operation_action_id = 'OP-' + uuid.uuid5(uuid.UUID(tx), 'operation-action:' + str(serial)).hex
            executed_event_id = str(uuid.uuid5(uuid.UUID(tx), 'operation-executed:' + str(serial)))
            require(operation_action_id not in entities(g), 'OPERATION_ACTION_ID_CONFLICT')
            operation_action = {'id':operation_action_id, 'kind':'action',
                'title':operation_record_type + ': ' + operation_record_title,
                'description':basis, 'revision':1,
                'result':{'state':'confirmed','truth':'true','eventId':executed_event_id},
                'actionType':operation_record_type, 'lowLevel':True,
                'targetIds':([operation_record_target] if entities(g)[operation_record_target]['kind'] == 'decision' else []),
                'groupIds':[]}
            g['externalActions'].append(operation_action)
            g['events'].append({'id':executed_event_id, 'type':'action_executed',
                'transactionId':tx, 'recordedAt':timestamp, 'by':actor,
                'nodeIds':[operation_action_id], 'basis':basis,
                'operationActionId':operation_action_id})
            event['operationActionId'] = operation_action_id
            event['nodeIds'] = sorted(set(event['nodeIds']) | {operation_action_id})
        for decision_id in selected_by_action:
            selection_event_id = str(uuid.uuid5(uuid.UUID(tx),
                'action-decision-selected:' + str(serial) + ':' + decision_id))
            g['events'].append({'id':selection_event_id, 'type':'decision_selected',
                'transactionId':tx, 'recordedAt':timestamp, 'by':actor,
                'nodeIds':[decision_id], 'basis':basis, 'operationActionId':nid})
        # A real acceptance Action also records the resulting Decision choice.
        # Its execution and the choice are separate facts of the same operation.
        if cmd=='complete' and node['kind']=='action' and node['actionType']=='decide_acceptance':
            decision_id=node['targetIds'][0];old_state=entities(before_operation)[decision_id]['selectionState'];new_state=entities(g)[decision_id]['selectionState']
            if old_state!=new_state:
                choice_type='decision_selected' if new_state=='selected' else 'decision_unselected'
                g['events'].append({'id':str(uuid.uuid5(uuid.UUID(tx),'acceptance-choice:'+str(serial)+':'+decision_id)),
                    'type':choice_type,'transactionId':tx,'recordedAt':timestamp,'by':actor,'nodeIds':[decision_id],
                    'basis':basis,'operationActionId':nid})
        # _event must use the exact source event ID so result.eventId remains stable.
        _append_event(g, event)
        HISTORY.annotate(before_operation,g,event,cmd,data,sys.modules[__name__],process=not paper)
        validate(g)
    g['revision'] = original['revision'] + 1
    validate(g)
    return g, True


def fact_record(graph,owner,event_id,relation=False):
    event=next((e for e in graph['events'] if e['id']==event_id and owner in e.get('nodeIds',[])),None)
    if event:return event,owner,graph['events']
    link=graph.get('factLineage',{}).get(owner,{}).get(event_id)
    if link:
        history=graph.get('inheritedHistory',{}).get(link['historyKey'],{})
        events=history.get('events',[])
        event=next((e for e in events if e['id']==event_id and link['sourceId'] in e.get('nodeIds',[])),None)
        return event,link['sourceId'],events
    return None,owner,graph['events']
