"""Canonical process Questions: a small, fail-closed T3 API slice.

Questions live in objects, not the Graph/Structure node tree. References are
historical qualified entity pins from the existing reference codec. No
subscription or permission is inferred from these references.
"""
import copy
import json
import re
import uuid

ANSWER_KINDS=('hypothesis','observation','user_answer')
BLOCKING=('blocking','non-blocking','partially-blocking')


def require(ok, code):
    if not ok:raise ValueError('DECISION_QUESTION_'+code)


def text(value):
    return isinstance(value,str) and bool(value.strip())


def uuid_value(value):
    try:return str(uuid.UUID(value))==value
    except (ValueError,TypeError,AttributeError):return False


def refs(value, graph, kernel, question=None):
    require(isinstance(value,list),'REFS')
    seen=set()
    for ref in value:
        require(isinstance(ref,dict),'REFS')
        if 'kind' in ref:
            kind=ref.get('kind')
            if kind=='document':
                require(set(ref)=={'schemaVersion','kind','uri'} and ref['schemaVersion']==1 and
                        isinstance(ref['uri'],str) and ref['uri'].startswith('https://'),'REFS')
            else:
                fields={'schemaVersion','kind','packageId','identitySpace'}|({'workGraphId'} if kind=='workGraph' else set())
                require(kind in ('process','workGraph','lens') and set(ref)==fields and
                        ref['schemaVersion']==1 and uuid_value(ref['packageId']) and
                        ref['identitySpace']==graph['identitySpace'] and
                        (kind!='workGraph' or ref['workGraphId'] in {w['id'] for w in graph['workGraphs']}),'REFS')
            key=json.dumps(ref,sort_keys=True)
        else:
            require(kernel._valid_pin(ref,True) and
                    (ref['mode']=='historical' or reference_id(graph,ref,kernel,question) is not None),'REFS')
            key=ref['nodeId']
        require(key not in seen,'DUPLICATE_REF');seen.add(key)


def validate_entity(question, events, kernel):
    require(text(question.get('title')) and isinstance(question.get('description'),str),'ENTITY')
    require(set(question)<=set(kernel.ENTITY_BASE_FIELDS)|{
        'relatedRefs','sourceRefs','impact','answerCondition','blocking',
        'answers','answerHistory','assessment','assessmentHistory','assessmentReviewRequired','referenceBindings'},'FIELDS')
    require({'relatedRefs','sourceRefs','answers','assessmentHistory','assessmentReviewRequired'}<=set(question),
            'FIELDS')
    require(text(question.get('impact')) and text(question.get('answerCondition')),'CONDITION')
    require(isinstance(question['answers'],list) and isinstance(question.get('answerHistory',[]),list)
            and isinstance(question['assessmentHistory'],list) and
            type(question['assessmentReviewRequired']) is bool,'ANSWERS')
    if 'blocking' in question:
        require(isinstance(question['blocking'],dict) and
                question['blocking'].get('mode') in BLOCKING and
                set(question['blocking'])<={'mode','scope'} and
                (question['blocking']['mode']!='partially-blocking' or text(question['blocking'].get('scope'))),'BLOCKING')
    for source in (question['answers'],question['assessmentHistory']):require(isinstance(source,list),'ANSWERS')
    def check_answer(answer):
        require(isinstance(answer,dict) and set(answer)-{'userSource'}=={
            'id','kind','text','sourceRefs','recordedBy','recordedAt','eventId'} and
            uuid_value(answer.get('id')) and
            answer.get('kind') in ANSWER_KINDS and text(answer.get('text')) and
            answer.get('recordedBy') in ('assistant','user') and
            isinstance(answer.get('recordedAt'),str) and
            re.search(r'(?:Z|[+-]\d{2}:\d{2})$',answer['recordedAt']) and
            uuid_value(answer.get('eventId')) and
            answer['eventId'] in events and question['id'] in events[answer['eventId']]['nodeIds'] and
            events[answer['eventId']]['by']==answer['recordedBy'] and events[answer['eventId']]['recordedAt']==answer['recordedAt'],
            'ANSWER')
        require(isinstance(answer['sourceRefs'],list),'ANSWER')
        if answer['kind']=='observation':require(bool(answer['sourceRefs']),'OBSERVATION_SOURCE_REQUIRED')
        if answer['kind']=='user_answer':
            source=answer.get('userSource',{})
            require(isinstance(source,dict) and source.get('mode') in ('direct-user-entry','user-context') and
                    set(source)==({'mode','eventId'} if source.get('mode')=='direct-user-entry' else {'mode','eventId','nodeId'}) and
                    source.get('eventId') in events and events[source['eventId']]['by']=='user' and
                    (source['mode']!='direct-user-entry' or source['eventId']==answer['eventId'] and answer['recordedBy']=='user') and
                    (source['mode']!='user-context' or source.get('nodeId') in events[source['eventId']]['nodeIds'] and any(r.get('nodeId')==source.get('nodeId') for r in answer['sourceRefs'])), 'USER_SOURCE_REQUIRED')
        else:require('userSource' not in answer,'USER_SOURCE_FIELDS')

    active={}
    for answer in question['answers']:
        check_answer(answer)
        require(answer['id'] not in active,'DUPLICATE_ANSWER_ID')
        active[answer['id']]=answer
    last={}
    order={eid:i for i,eid in enumerate(events)}
    for entry in question.get('answerHistory',[]):
        require(isinstance(entry,dict) and set(entry)=={
            'action','previous','eventId','recordedBy','recordedAt'} and
            entry.get('action') in ('edit','remove') and uuid_value(entry.get('eventId')) and
            entry['eventId'] in events and question['id'] in events[entry['eventId']]['nodeIds'] and
            entry.get('recordedBy') in ('assistant','user') and
            isinstance(entry.get('recordedAt'),str) and
            re.search(r'(?:Z|[+-]\d{2}:\d{2})$',entry['recordedAt']) and
            events[entry['eventId']]['recordedAt']==entry['recordedAt'] and
            events[entry['eventId']]['by']==entry['recordedBy'],'ANSWER_HISTORY')
        old=entry['previous']
        check_answer(old)
        require(order[old['eventId']]<order[entry['eventId']] and
            (old['id'] not in last or last[old['id']]==old['eventId']),'ANSWER_HISTORY_CHAIN')
        last[old['id']]=entry['eventId'] if entry['action']=='edit' else None
    for ident,last_event in last.items():
        require((ident in active and active[ident]['eventId']==last_event) if last_event
                else ident not in active,'ANSWER_HISTORY_STATE')
    known=set(active)|set(last)
    for row in [*question['assessmentHistory'],*([question['assessment']] if 'assessment' in question else [])]:
        require(isinstance(row,dict) and set(row)=={
            'id','answerIds','sufficient','basis','recordedBy','recordedAt','eventId'} and
            uuid_value(row.get('id')) and isinstance(row.get('answerIds'),list) and
            len(set(row['answerIds']))==len(row['answerIds']) and
            set(row['answerIds'])<=known and type(row.get('sufficient')) is bool and
            text(row.get('basis')) and row.get('recordedBy') in ('assistant','user') and
            isinstance(row.get('recordedAt'),str) and
            re.search(r'(?:Z|[+-]\d{2}:\d{2})$',row['recordedAt']) and
            uuid_value(row.get('eventId')) and
            row['eventId'] in events and question['id'] in events[row['eventId']]['nodeIds'],'ASSESSMENT')

def validate_graph(graph,kernel,events):
    inventory=event_inventory(graph,kernel)
    for node in graph.get('objects',[]):
        if node['kind']!='question':continue
        require(isinstance(node.get('referenceBindings',{}),dict),'REF_BINDINGS')
        refs(node['relatedRefs'],graph,kernel,node)
        refs(node['sourceRefs'],graph,kernel,node)
        for answer in node['answers']:refs(answer['sourceRefs'],graph,kernel,node)
        for entry in node.get('answerHistory',[]):refs(entry['previous']['sourceRefs'],graph,kernel,node)
        validate_entity(node,inventory,kernel)


def create(value,graph,kernel):
    require('referenceBindings' not in value,'REF_BINDINGS_READ_ONLY')
    require(not value.get('answers') and not value.get('answerHistory') and 'assessment' not in value and
            not value.get('assessmentHistory') and
            not value.get('assessmentReviewRequired'),'NEW_ANSWER_FORBIDDEN')
    value.setdefault('sourceRefs',[])
    value.setdefault('answers',[])
    value.setdefault('answerHistory',[])
    value.setdefault('assessmentHistory',[])
    value.setdefault('assessmentReviewRequired',False)
    refs(value.get('relatedRefs'),graph,kernel)
    refs(value['sourceRefs'],graph,kernel)
    require(text(value.get('impact')) and text(value.get('answerCondition')),'CONDITION')


def answer(node,data,graph,kernel,event):
    require(isinstance(data,dict) and data.get('nodeId')==node['id'],'ANSWER_FIELDS')
    action=data.get('action','add')
    require(action in ('add','edit','remove'),'ANSWER_ACTION')
    if action=='add':
        require(set(data) in ({'nodeId','kind','text','sourceRefs'},
                             {'nodeId','action','kind','text','sourceRefs'}),'ANSWER_FIELDS')
        require(data['kind'] in ANSWER_KINDS and text(data['text']),'ANSWER_FIELDS')
        refs(data['sourceRefs'],graph,kernel)
        require(data['kind']!='observation' or data['sourceRefs'],'OBSERVATION_SOURCE_REQUIRED')
        user_source=answer_source(data,graph,kernel,event)
        ident=str(uuid.uuid5(uuid.UUID(event['id']),'answer'))
        node['answers'].append({'id':ident,'kind':data['kind'],'text':data['text'],
           'sourceRefs':copy.deepcopy(data['sourceRefs']),'recordedBy':event['by'],
           'recordedAt':event['recordedAt'],'eventId':event['id'],**({'userSource':user_source} if user_source else {})})
    else:
        fields={'nodeId','action','answerId','expectedAnswerEventId'}
        require(set(data)==(fields|{'kind','text','sourceRefs'} if action=='edit' else fields),
                'ANSWER_FIELDS')
        require(uuid_value(data.get('answerId')) and uuid_value(data.get('expectedAnswerEventId')),
                'ANSWER_ID')
        row=next((r for r in node['answers'] if r['id']==data['answerId']),None)
        require(row is not None,'ANSWER_NOT_FOUND')
        require(row['eventId']==data['expectedAnswerEventId'],'ANSWER_STALE')
        if action=='edit':
            require(data['kind'] in ANSWER_KINDS and text(data['text']),'ANSWER_FIELDS')
            refs(data['sourceRefs'],graph,kernel)
            require(data['kind']!='observation' or data['sourceRefs'],'OBSERVATION_SOURCE_REQUIRED')
            require((row['kind'],row['text'],row['sourceRefs'])!=
                    (data['kind'],data['text'],data['sourceRefs']),'ANSWER_NO_CHANGE')
        user_source=answer_source(data,graph,kernel,event) if action=='edit' else None
        node.setdefault('answerHistory',[]).append({
            'action':action,'previous':copy.deepcopy(row),'eventId':event['id'],
            'recordedBy':event['by'],'recordedAt':event['recordedAt']})
        ident=row['id']
        if action=='remove':node['answers'].remove(row)
        else:
            row.pop('userSource',None)
            if user_source:row['userSource']=user_source
            row.update(kind=data['kind'],text=data['text'],
                        sourceRefs=copy.deepcopy(data['sourceRefs']),
                        recordedBy=event['by'],recordedAt=event['recordedAt'],
                        eventId=event['id'])
    if 'assessment' in node:node['assessmentReviewRequired']=True
    return ident


def assess(node,data,event):
    require(isinstance(data,dict) and set(data)=={'nodeId','answerIds','sufficient','basis'} and
            isinstance(data['answerIds'],list) and
            len(set(data['answerIds']))==len(data['answerIds']) and
            set(data['answerIds'])<={r['id'] for r in node['answers']} and
            type(data.get('sufficient')) is bool and text(data.get('basis')),'ASSESS_FIELDS')
    if 'assessment' in node:node['assessmentHistory'].append(copy.deepcopy(node['assessment']))
    node['assessment']={'id':str(uuid.uuid5(uuid.UUID(event['id']),'assessment')),
        'answerIds':list(data['answerIds']),'sufficient':data['sufficient'],'basis':data['basis'],
        'recordedBy':event['by'],'recordedAt':event['recordedAt'],'eventId':event['id']}
    node['assessmentReviewRequired']=False

def require_owner_inputs(command,data,owner,graph,kernel,model):
    """Reject foreign packages even if an entity ID happens to match locally."""
    if command=='add' and data.get('entity',{}).get('kind')=='question':
        refs_to_check=data['entity'].get('relatedRefs',[])+data['entity'].get('sourceRefs',[])
    elif command=='edit' and ('relatedRefs' in data.get('changes',{}) or 'sourceRefs' in data.get('changes',{})):
        refs_to_check=data['changes'].get('relatedRefs',[])+data['changes'].get('sourceRefs',[])
    elif command=='question_answer':
        refs_to_check=data.get('sourceRefs',[])
    elif command=='question_migrate':refs_to_check=[data.get('sourceRef')]
    else:return
    if command=='edit':
        existing=kernel.entities(graph).get(data.get('nodeId'),{})
        if existing.get('kind')=='question':
            previous=existing['relatedRefs']+existing['sourceRefs']
            refs_to_check=[ref for ref in refs_to_check if ref not in previous]
    require(isinstance(refs_to_check,list) and all(isinstance(ref,dict) and
        (ref.get('kind')=='document' or ref.get('packageId')==owner) for ref in refs_to_check),'FOREIGN_REF_UNSUPPORTED')
    for ref in refs_to_check:
        if 'kind' in ref:
            refs([ref],graph,kernel);continue
        node=kernel.entities(graph).get(ref.get('nodeId'))
        require(node is not None and ref.get('mode')=='current' and
                ref.get('identitySpace')==graph['identitySpace'] and
                ref.get('graphRevision')==graph['revision'] and
                ref.get('revision')==node['revision'] and
                ref.get('sha256')==model.digest(graph),'SOURCE_PIN_CHANGED')


def event_inventory(graph,kernel):
    """Resolve inherited evidence through the existing hashed history and lineage."""
    result={}
    for key,history in graph.get('inheritedHistory',{}).items():
        mapping={ref['nodeId']:ident for ident,refs_ in graph.get('entityLineage',{}).items()
                 for ref in refs_ if ref['sha256']==key}
        for event in history['events']:
            row=copy.deepcopy(event)
            row['nodeIds']=list(dict.fromkeys([*row['nodeIds'],*(mapping.get(i,i) for i in row['nodeIds'])]))
            result.setdefault(row['id'],row)
    result.update({e['id']:e for e in graph['events']})
    return result


def answer_source(data,graph,kernel,event):
    if data['kind']!='user_answer':return None
    if event['by']=='user':return {'mode':'direct-user-entry','eventId':event['id']}
    # An AI can quote an existing user-authored Context exactly, never attest itself.
    for ref in data['sourceRefs']:
        node=kernel.entities(graph).get(ref.get('nodeId'),{})
        if node.get('kind')!='context' or node.get('value')!=data['text']:continue
        for prior in reversed(graph['events']):
            detail=prior.get('historyDetail',{})
            changed=node['id'] in detail.get('targetIds',[]) and any(r['field']=='value' for r in detail.get('edits',[]))
            created=node['id'] in detail.get('createdIds',[])
            if created or changed:
                require(prior['by']=='user','USER_SOURCE_REQUIRED')
                return {'mode':'user-context','eventId':prior['id'],'nodeId':node['id']}
    require(False,'USER_SOURCE_REQUIRED')


def legacy_write(value,previous):
    if 'questions' not in value:return
    require(value['questions']==(previous or {}).get('questions',[]),'LEGACY_MIGRATION_REQUIRED')


def migrate(node,data,graph,kernel,event):
    require(set(data)=={'nodeId','sourceRef'} and data['sourceRef']['nodeId']==node['id'] and
            node.get('questions'),'MIGRATE_FIELDS')
    result=[]
    for old in node['questions']:
        ident='Q-'+str(uuid.uuid5(uuid.UUID(event['id']),node['id']+':'+old['id']))
        value={'id':ident,'kind':'question','title':old['question'],'description':'', 'revision':1,
               'relatedRefs':[copy.deepcopy(data['sourceRef'])], 'sourceRefs':[copy.deepcopy(data['sourceRef'])],
               'impact':old['impact'],'answerCondition':old['closeCondition'],
               'blocking':{'mode':old['blocking'],**({'scope':old['scope']} if old.get('scope') else {})}}
        create(value,graph,kernel);graph['objects'].append(value);result.append(ident)
    node['questions']=[]
    return result


def remove_refs(graph,removed,event,kernel,affected,touched):
    for question in graph['objects']:
        if question['kind']!='question' or question['id'] in removed:continue
        lists=[question['relatedRefs'],question['sourceRefs'],
               *(a['sourceRefs'] for a in question['answers']),
               *(h['previous']['sourceRefs'] for h in question.get('answerHistory',[]))]
        changed=False
        for rows in lists:
            for ref in rows:
                if reference_id(graph,ref,kernel,question) in removed and ref.get('mode')!='historical':
                    kernel.guard(question,event,'edit');ref['mode']='historical';changed=True
        if changed:
            if 'assessment' in question:question['assessmentReviewRequired']=True
            kernel._bump(kernel.entities(graph),question['id'],touched);affected.add(question['id'])


def reference_key(ref):
    return json.dumps([ref.get(k) for k in ('packageId','identitySpace','nodeId')],separators=(',',':'))


def reference_id(graph,ref,kernel,question=None):
    """Copy bindings are writer-derived identity data; the observed source pin stays intact."""
    if ref.get('mode')=='historical':return None
    bound=(question or {}).get('referenceBindings',{}).get(reference_key(ref))
    if bound:
        origins=graph.get('entityLineage',{}).get(bound,[])
        require(any(all(origin.get(k)==ref.get(k) for k in ('packageId','identitySpace','nodeId')) for origin in origins),'REF_BINDING_LINEAGE')
        return bound if bound in kernel.entities(graph) else None
    if ref.get('identitySpace')==graph['identitySpace'] and ref.get('nodeId') in kernel.entities(graph):return ref['nodeId']
    if ref.get('mode')!='inherited':return None
    candidates=[ident for ident,origins in graph.get('entityLineage',{}).items()
                if any(all(origin.get(k)==ref.get(k) for k in ('packageId','identitySpace','nodeId')) for origin in origins)]
    require(len(candidates)<=1,'REF_BINDING_AMBIGUOUS')
    return candidates[0] if candidates else None
