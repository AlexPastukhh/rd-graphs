"""Finding values and commands, executed inside the existing Graph transaction.

No store, authority, evaluator or proposal state machine lives here.
"""
import copy
import uuid

TYPES = ('problem', 'risk', 'decision_uncertainty', 'improvement_opportunity')
DISPOSITIONS = ('unresolved', 'deferred', 'resolved', 'invalidated', 'superseded')
RELATIONS = ('FINDING_RESPONSE', 'FINDING_PROPOSAL')
COMMON = {'questions', 'reviewLimitations', 'userAssistance', 'interventionPriority', 'userReviewPriority'}
FIELDS = {'subjectId', 'subjectSnapshot', 'findingType', 'rationale', 'evidenceIds',
          'disposition', 'dispositionHistory', 'reviewScope','analysisSources'} | COMMON
EDITABLE = {'findingType', 'rationale', 'evidenceIds', 'reviewScope','analysisSources'} | COMMON


def validate_extras(n, K):
    for field in ('interventionPriority', 'userReviewPriority', 'reviewScope', 'userAssistance'):
        if field in n:
            K.require(isinstance(n[field], str), 'FINDING_TEXT')
    for field in ('questions', 'reviewLimitations'):
        rows = n.get(field, [])
        K.require(isinstance(rows, list), 'FINDING_QUESTIONS')
        ids = set()
        for r in rows:
            K.require(isinstance(r, dict) and K.text(r.get('id')) and r['id'] not in ids,
                      'FINDING_QUESTION_ID')
            ids.add(r['id'])
            if field == 'questions':
                K.require(set(r) == {'id', 'question', 'impact', 'blocking', 'scope', 'closeCondition'} and
                          all(K.text(r.get(f)) for f in ('question', 'impact', 'closeCondition')) and
                          r.get('blocking') in ('blocking', 'non-blocking', 'partially-blocking') and
                          isinstance(r.get('scope'), str) and
                          (r['blocking'] != 'partially-blocking' or K.text(r['scope'])), 'FINDING_QUESTION')
            else:
                K.require(set(r) == {'id', 'claim', 'reason', 'limitation'} and
                          all(K.text(r.get(f)) for f in ('claim', 'reason', 'limitation')), 'FINDING_LIMITATION')


def validate_entity(n, K):
    K.require(K.text(n.get('subjectId')) and n.get('findingType') in TYPES and
              K.text(n.get('rationale')) and K.unique_strings(n.get('evidenceIds')),
              'FINDING_FIELDS')
    snap = n.get('subjectSnapshot')
    K.require(isinstance(snap, dict) and {'id','kind','title'}<=set(snap)<={'id','kind','title','revision','definition'} and
              snap['id'] == n['subjectId'] and snap['kind'] in K.NODE_KINDS and
              K.text(snap['title']), 'FINDING_SUBJECT_SNAPSHOT')
    history = n.get('dispositionHistory', [])
    K.require(isinstance(history, list), 'FINDING_DISPOSITION_HISTORY')
    for d in [n.get('disposition'), *history]:
        K.require(isinstance(d, dict) and {'code', 'basis', 'evidenceIds'} <= set(d) <=
                  {'code', 'basis', 'evidenceIds', 'eventId', 'recordedAt', 'reviewRevision',
                   'revisitTrigger', 'replacementId', 'label'} and d['code'] in DISPOSITIONS and
                  isinstance(d['basis'], str) and K.unique_strings(d['evidenceIds']), 'FINDING_DISPOSITION')
        if d['code'] != 'unresolved':
            K.require(K.text(d['basis']) and K._uuid(d.get('eventId')) and
                      K.text(d.get('recordedAt')) and type(d.get('reviewRevision')) is int,
                      'FINDING_DISPOSITION_BASIS')
        if d['code'] == 'deferred':K.require(K.text(d.get('revisitTrigger')), 'FINDING_REVISIT_REQUIRED')
        if d['code'] in ('resolved', 'invalidated'):K.require(bool(d['evidenceIds']), 'FINDING_OUTCOME_EVIDENCE_REQUIRED')
        if d['code'] == 'superseded':K.require(K.text(d.get('replacementId')) and d['replacementId'] != n['id'], 'FINDING_REPLACEMENT_REQUIRED')


def normalize(g, n, K, event):
    subject = K.entities(g).get(n.get('subjectId'))
    K.require(subject is not None and subject['kind'] == 'decision' and
              subject in g['nodes'], 'FINDING_SUBJECT_REQUIRED')
    K.guard(subject, event, 'link')
    K.require(not ({'disposition', 'dispositionHistory', 'subjectSnapshot'} & set(n)), 'NEW_FINDING_FACT_NOT_ALLOWED')
    n['subjectSnapshot'] = {f: subject[f] for f in ('id', 'kind', 'title','revision')}
    n['subjectSnapshot']['definition']=K._native_definition(g,subject['id'])
    n['evidenceIds'] = n.get('evidenceIds', [])
    K.require(K.unique_strings(n['evidenceIds']) and all(K.entities(g).get(i,{}).get('kind') in ('context','evidence') for i in n['evidenceIds']),'FINDING_EVIDENCE_REQUIRED')
    n['disposition'] = {'code': 'unresolved', 'basis': '', 'evidenceIds': []}
    n['dispositionHistory'] = []


def validate_graph(g, K):
    ns = K.entities(g)
    for n in ns.values():
        if n['kind'] != 'finding':continue
        subject = ns.get(n['subjectId'])
        K.require(subject is None or subject['kind'] in K.NODE_KINDS, 'FINDING_SUBJECT_KIND')
        for ident in n['evidenceIds']:
            K.require(ident not in ns or ns[ident]['kind'] in ('context','evidence'), 'FINDING_EVIDENCE_KIND')
    for e in g['edges']:
        if e['type'] not in RELATIONS:continue
        f = ns.get(e.get('findingId'))
        K.require(f is not None and f['kind'] == 'finding', 'FINDING_RELATION_TARGET')
        if e['type'] == 'FINDING_RESPONSE':
            K.require(e['from'] == f['subjectId'], 'FINDING_RESPONSE_SUBJECT')
        else:
            K.require(any(r['type'] == 'FINDING_RESPONSE' and r['to'] == e['from'] and
                          r.get('findingId') == f['id'] for r in g['edges']), 'FINDING_RESPONSE_REQUIRED')
            K.require(any(r['type'] == 'DEPENDS_ON' and r['from'] == f['id'] and
                          r['to'] == e['to'] and r.get('dependencyPurpose') == 'decisionContext'
                          for r in g['edges']), 'FINDING_PROPOSAL_CONTEXT_REQUIRED')
    for group in g['decisionGroups']:
        if ns[group['parentId']]['kind'] == 'decision':
            K.require(all(any(e['type'] == 'FINDING_PROPOSAL' and e['from'] == group['parentId'] and
                              e['to'] == m['decisionId'] for e in g['edges']) for m in group['members']),
                      'FINDING_GROUP_PROPOSALS_REQUIRED')


def mutate(g, command, data, event, K):
    """Return affected IDs, relation IDs and evidence; caller writes the event."""
    K.require(command=='finding_disposition','FINDING_WORKFLOW_RETIRED')
    ns = K.entities(g);fid = data.get('findingId', data.get('nodeId'));f = ns.get(fid)
    K.require(f is not None and f['kind'] == 'finding', 'FINDING_REQUIRED')
    if command == 'finding_disposition':
        K.require(set(data) == {'nodeId', 'disposition', 'observed'}, 'FINDING_DISPOSITION_FIELDS')
        K.guard(f, event, 'review')
        K.require(data['observed'] == K.pins(g, fid), 'REVIEW_INPUTS_CHANGED')
        d = copy.deepcopy(data['disposition'])
        K.require(isinstance(d, dict) and set(d) <= {'code', 'basis', 'evidenceIds', 'revisitTrigger', 'replacementId', 'label'}, 'FINDING_DISPOSITION_FIELDS')
        K.require(K.text(d.get('basis')), 'FINDING_DISPOSITION_BASIS')
        evidence = d.get('evidenceIds', [])
        K.require(K.unique_strings(evidence) and all(ns.get(i, {}).get('kind') in ('context','evidence') for i in evidence), 'FINDING_EVIDENCE_REQUIRED')
        for ident in evidence:K.guard(ns[ident], event, 'review')
        if d.get('code') == 'superseded':
            replacement = ns.get(d.get('replacementId'))
            K.require(replacement is not None and replacement['kind'] == 'finding' and replacement['id'] != fid, 'FINDING_REPLACEMENT_REQUIRED')
        d.update(eventId=event['id'], recordedAt=event['recordedAt'], reviewRevision=g['revision'])
        candidate = {**f, 'disposition': d};validate_entity(candidate, K)
        K.require(d['code'] not in ('resolved', 'invalidated') or not f.get('review', {}).get('required'), 'REVIEW_REQUIRED')
        f['dispositionHistory'].append(copy.deepcopy(f['disposition']));f['disposition'] = d
        f['revision'] += 1
        return {fid}, [], evidence
    raise ValueError('FINDING_WORKFLOW_RETIRED')


def describe(g, K, scope_id=None):
    """Read-only cards; no permanent CURRENT/UPSTREAM or Next Gate field."""
    ns = K.entities(g);rows = []
    scope = ns.get(scope_id) if scope_id else None
    ancestors=set();descendants={scope_id} if scope else set()
    structural=[e for e in K.active_edges(g) if e['type'] in K.STRUCTURAL_KINDS]
    if hasattr(K,'decision_memberships'):structural += K.decision_memberships(g)
    while True:
        more={e['from'] for e in structural if e['to'] in ancestors|({scope_id} if scope else set())}
        if more<=ancestors:break
        ancestors|=more
    while True:
        more={e['to'] for e in structural if e['from'] in descendants}
        if more<=descendants:break
        descendants|=more
    for f in g['objects']:
        if f['kind'] != 'finding':continue
        subject = ns.get(f['subjectId'])
        rows.append({'findingId': f['id'], 'subject': {**(subject or f['subjectSnapshot']), 'present': subject is not None},
                     'responseIds': [e['to'] for e in g['edges'] if e['type'] == 'FINDING_RESPONSE' and e.get('findingId') == f['id']],
                     'proposalIds': [e['to'] for e in g['edges'] if e['type'] == 'FINDING_PROPOSAL' and e.get('findingId') == f['id']],
                     'proposalImpacts':[{'decisionId':e['to'],'targetIds':ns[e['to']].get('impactTargetIds',[]),'relativeLevel':'UPSTREAM' if set(ns[e['to']].get('impactTargetIds',[]))&ancestors else 'CURRENT' if set(ns[e['to']].get('impactTargetIds',[]))&descendants else None} for e in g['edges'] if e['type']=='FINDING_PROPOSAL' and e.get('findingId')==f['id']],
                     'scopeId': scope_id, 'relativeLevel': 'CURRENT' if f['subjectId'] in descendants else 'UPSTREAM' if f['subjectId'] in ancestors else None})
    for row in rows:
        if not row['responseIds'] and not row['proposalIds']:
            for key in ('responseIds','proposalIds','proposalImpacts'):row.pop(key)
    return rows
