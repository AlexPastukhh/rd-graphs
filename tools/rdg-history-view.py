"""Read-only History classification from recorded operations and preserved versions.

This is a projection of Graph facts, not another journal, status or writer.
"""
import copy

MODES=('important','meaningful','technical','all')
RESULTS={'decision_selected','decision_unselected','branch_cancelled','action_executed','requirement_achieved','decision_completed','reopened','completed'}
TECHNICAL={'graph_title','context_group','context_record','work_graph','decision_group','policy_change','dependency_rule','lock_set','lock_remove','recommendation_packages','lens_application','operation_record'}

def snapshot(n):
    return {k:copy.deepcopy(n[k]) for k in ('id','kind','title','lowLevel') if k in n}

def detail(before,after,command,data,K,*,process=True):
    old=K.entities(before) if before else {};new=K.entities(after)
    target=data.get('nodeId')
    ids=([data['entity']['id']] if command=='add' else list(data['nodeIds']) if 'nodeIds' in data else [target] if target else [])
    if command=='requirement_decision':ids=list(dict.fromkeys([*ids,data['decisionId']]))
    if command=='root_cause':ids=[data['cause']['requirementId']]
    relations={e['id']:e for g in (before or {},after) for e in g.get('edges',[])}
    refs=[data['relation']['id']] if isinstance(data.get('relation'),dict) else [data['edgeId']] if data.get('edgeId') else [e['id'] for e in data.get('initialRelations',[])]
    result={'command':command,'targetIds':ids,'subjects':{i:snapshot(new.get(i) or old[i]) for i in ids if i in new or i in old},
        'createdIds':[i for i in ids if i not in old and i in new] if command in ('add','create') else [],
        'fields':sorted(data.get('changes',{})),'cosmetic':bool(data.get('cosmetic',False)),
        'relations':[{k:relations[i][k] for k in ('id','type','from','to')} for i in refs if i in relations],
        'process':process,'activatedRequirementIds':[],'deactivatedRequirementIds':[],'edits':[]}
    for relation in result['relations']:
        for ident in (relation['from'],relation['to']):
            if ident in new or ident in old:result['subjects'][ident]=snapshot(new.get(ident) or old[ident])
    if command=='graph_title':
        result['fields']=['title'];result['cosmetic']=True
        result['edits']=[{'field':'title','beforePresent':True,'before':before['title'],
                         'afterPresent':True,'after':after['title']}]
    if command in ('question_answer','question_assess'):
        result['fields']=['answers','answerHistory','assessment','assessmentHistory','assessmentReviewRequired']
    if command=='question_migrate':
        result['targetIds']=list(dict.fromkeys([*ids,*(i for i,n in new.items() if i not in old and n['kind']=='question')]))
        result['createdIds']=[i for i in result['targetIds'] if i not in old]
        result['subjects'].update({i:snapshot(new[i]) for i in result['createdIds']})
        result['fields']=['questions']
    if command in ('edit','question_answer','question_assess','question_migrate') and target in old and target in new:
        for field in result['fields']:
            if old[target].get(field)==new[target].get(field) and (field in old[target])==(field in new[target]):continue
            result['edits'].append({'field':field,'beforePresent':field in old[target],'before':copy.deepcopy(old[target].get(field)),
                'afterPresent':field in new[target],'after':copy.deepcopy(new[target].get(field))})
    if command=='decision_context' and target in old and target in new:
        result['fields']=[k for k in ('decisionContextIds','contextNotes') if old[target].get(k)!=new[target].get(k)]
    return result

def annotate(before,after,primary,command,data,K,*,process=True):
    events=after['events'][len(before['events']):];old=K.entities(before);new=K.entities(after)
    for e in events:
        if e is primary:d=detail(before,after,command,data,K,process=process)
        else:
            cmd='select' if e['type']=='decision_selected' else 'cascade' if e['type']=='branch_cancelled' else 'operation_record' if e['type']=='action_executed' else 'link' if e['type']=='linked' else e['type']
            d=detail(before,after,cmd,{},K,process=process);d['targetIds']=list(e.get('nodeIds',[]));d['subjects']={i:snapshot(new.get(i) or old[i]) for i in d['targetIds'] if i in new or i in old}
            rels={r['id']:r for g in (before,after) for r in g['edges']}
            d['relations']=[{k:rels[i][k] for k in ('id','type','from','to')} for i in e.get('relationIds',[]) if i in rels]
        if e['type'] in ('decision_selected','decision_unselected'):
            d['edits']=[{'field':'selectionState','beforePresent':True,'before':old[i]['selectionState'],
                'afterPresent':True,'after':new[i]['selectionState']} for i in d['targetIds'] if old.get(i,{}).get('kind')=='decision' and new.get(i,{}).get('kind')=='decision' and old[i]['selectionState']!=new[i]['selectionState']]
        outcome=e.get('actionResult',{}).get('decisionId')
        if outcome in new or outcome in old:d['subjects'][outcome]=snapshot(new.get(outcome) or old[outcome])
        e['historyDetail']=d
    if not process:return
    pre=set(K.support_state(before)['activeIds']);post=set(K.support_state(after)['activeIds'])
    added=sorted(i for i in post-pre if new.get(i,{}).get('kind')=='requirement')
    removed=sorted(i for i in pre-post if old.get(i,{}).get('kind')=='requirement')
    carrier=next((e for typ in ('decision_selected','decision_unselected','branch_cancelled') for e in events if e['type']==typ),primary)
    d=carrier['historyDetail'];d['activatedRequirementIds']=added;d['deactivatedRequirementIds']=removed
    d['subjects'].update({i:snapshot(new.get(i) or old[i]) for i in added+removed})

def validate(d,K):
    fields={'command','targetIds','subjects','createdIds','fields','cosmetic','relations','process','activatedRequirementIds','deactivatedRequirementIds','edits'}
    K.require(isinstance(d,dict) and set(d)==fields and K.text(d['command']) and type(d['cosmetic']) is bool and type(d['process']) is bool,'HISTORY_DETAIL')
    for field in ('targetIds','createdIds','fields','activatedRequirementIds','deactivatedRequirementIds'):K.require(K.unique_strings(d[field]),'HISTORY_DETAIL_IDS')
    K.require(isinstance(d['subjects'],dict),'HISTORY_SUBJECTS')
    for i,n in d['subjects'].items():K.require(isinstance(n,dict) and {'id','kind','title'}<=set(n)<={'id','kind','title','lowLevel'} and n['id']==i and n['kind'] in K.ENTITY_KINDS and K.text(n['title']) and ('lowLevel' not in n or type(n['lowLevel']) is bool),'HISTORY_SUBJECT')
    K.require(isinstance(d['relations'],list) and all(isinstance(r,dict) and set(r)=={'id','type','from','to'} and all(K.text(v) for v in r.values()) and r['type'] in K.RELATION_TYPES for r in d['relations']),'HISTORY_RELATIONS')
    K.require(isinstance(d['edits'],list) and all(isinstance(r,dict) and set(r)=={'field','beforePresent','before','afterPresent','after'} and K.text(r['field']) and type(r['beforePresent']) is bool and type(r['afterPresent']) is bool for r in d['edits']),'HISTORY_EDITS')

def legacy_details(before,after,events,K,*,process=True):
    """Accepted transaction outcomes; never infer an old cosmetic flag or execution."""
    old=K.entities(before) if before else {};new=K.entities(after);result={}
    substantive=[e for e in events if e['type'] not in ('linked','unlinked','action_executed','decision_selected','branch_cancelled')]
    created=[e for e in events if e['type']=='created']
    for e in events:
        if 'historyDetail' in e:result[e['id']]=copy.deepcopy(e['historyDetail']);continue
        d=detail(before,after,'unknown',{},K,process=process);d['cosmetic']=None
        d['targetIds']=list(e.get('nodeIds',[]));d['subjects']={i:snapshot(new.get(i) or old[i]) for i in d['targetIds'] if i in new or i in old}
        rels={r['id']:r for g in (before or {},after) for r in g.get('edges',[])}
        d['relations']=[{k:rels[i][k] for k in ('id','type','from','to')} for i in e.get('relationIds',[]) if i in rels]
        if before and e['type']=='created' and len(created)==1:
            d['createdIds']=sorted(set(new)-set(old));d['targetIds']=d['createdIds'];d['subjects'].update({i:snapshot(new[i]) for i in d['createdIds']});d['command']='add'
        if before and e['type']=='edited' and len(substantive)==1:
            changed={i for i in set(old)&set(new) if {k:v for k,v in old[i].items() if k not in ('revision','review')}!={k:v for k,v in new[i].items() if k not in ('revision','review')}}
            if len(changed)==1:
                ident=next(iter(changed));fields=sorted(k for k in set(old[ident])|set(new[ident]) if k not in ('revision','review') and old[ident].get(k)!=new[ident].get(k))
                d=detail(before,after,'edit',{'nodeId':ident,'changes':{k:new[ident].get(k) for k in fields}},K,process=process);d['cosmetic']=None
            elif not changed and before.get('contextGroups',[])!=after.get('contextGroups',[]):d['command']='context_group'
        result[e['id']]=d
    if before and process and any('historyDetail' not in e for e in events):
        pre=set(K.support_state(before)['activeIds']);post=set(K.support_state(after)['activeIds'])
        added=sorted(i for i in post-pre if new.get(i,{}).get('kind')=='requirement');removed=sorted(i for i in pre-post if old.get(i,{}).get('kind')=='requirement')
        carrier=next((e for typ in ('decision_selected','decision_unselected','branch_cancelled') for e in events if e['type']==typ),next((e for e in events if e['type'] not in ('linked','unlinked','action_executed')),events[-1]))
        if 'historyDetail' not in carrier:
            d=result[carrier['id']];d['activatedRequirementIds']=added;d['deactivatedRequirementIds']=removed;d['subjects'].update({i:snapshot(new.get(i) or old[i]) for i in added+removed})
    return result

def classify(event,d):
    typ=event['type'];cmd=d.get('command');subjects=d.get('subjects',{});ids=d.get('targetIds',[])
    targets=[subjects[i] for i in ids if i in subjects];known=bool(ids) and len(targets)==len(ids)
    technical=cmd in TECHNICAL or typ in ('group_changed','work_graph_changed','lock_set','lock_removed','policy_changed','binding_changed','lens_application_recorded') or d.get('cosmetic') is True
    if cmd=='edit' and d.get('fields')==['contextGroupId']:technical=True
    if cmd=='decision_context' and d.get('fields')!=['contextNotes']:technical=True
    if cmd=='edit' and set(d.get('fields',[]))&{'decisionContextIds'}:technical=True
    if typ in ('linked','unlinked') and d.get('relations') and all(r['type']=='DEPENDS_ON' for r in d['relations']):technical=True
    if known and all(n.get('lowLevel') is True for n in targets) and typ not in ('decision_selected','decision_unselected','branch_cancelled'):technical=True
    level='technical' if technical else 'semantic';reason='recorded-operation' if 'historyDetail' in event else 'preserved-record'
    if not technical and typ in RESULTS:level='important'
    context=known and cmd in ('add','edit','remove','create') and any(n['kind'] in ('context','evidence') for n in targets)
    unknown_rename=cmd=='edit' and d.get('fields')==['title'] and d.get('cosmetic') is None
    if not technical and context and ((typ=='created' and bool(d.get('createdIds'))) or typ in ('edited','removed')):level='important'
    if unknown_rename:level='unknown';reason='cosmetic-flag-not-recorded'
    operation_level=level
    if d.get('activatedRequirementIds') or d.get('deactivatedRequirementIds'):level='important';reason='recorded-requirement-activity'
    if not d.get('process',True) and level=='important':level='semantic'
    label=None
    if typ=='decision_unselected' and any(r['field']=='selectionState' and r['before']!='selected' for r in d.get('edits',[])):label='Решение не принято'
    if cmd=='edit' and d.get('cosmetic') is True:label='Переименовано без изменения смысла'
    elif cmd=='edit' and d.get('fields')==['title']:label='Изменено название · семантика не записана' if d.get('cosmetic') is None else 'Изменён смысл названия'
    elif cmd=='context_group':label='Организация групп контекста'
    elif cmd=='context_record':label='Прежняя запись переведена в контекст'
    elif cmd=='review' or event.get('reviewResolutions'):label='Подтверждён пересмотр'
    elif context and typ=='created' and d.get('createdIds'):label='Добавлены данные контекста'
    elif context and typ=='edited' and not technical:label='Изменены данные контекста'
    elif context and typ=='removed':label='Удалены данные контекста'
    return {'level':level,'operationLevel':operation_level,'reason':reason,'label':label,'targetIds':ids,'createdIds':d.get('createdIds',[]),'subjects':subjects,
        'activatedRequirementIds':d.get('activatedRequirementIds',[]),'deactivatedRequirementIds':d.get('deactivatedRequirementIds',[]),
        'edits':d.get('edits',[]),'decisionOutcome':copy.deepcopy(event.get('actionResult')) if isinstance(event.get('actionResult'),dict) and 'decisionOutcome' in event['actionResult'] else None,'relations':d.get('relations',[]),'detailSource':'recorded' if 'historyDetail' in event else 'preserved-versions'}

def accepts(level,mode):
    if mode not in MODES:raise ValueError('HISTORY_MODE')
    return mode=='all' or mode=='important' and level=='important' or mode=='technical' and level=='technical' or mode=='meaningful' and level!='technical'
