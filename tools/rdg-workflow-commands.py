#!/usr/bin/env python3
"""Application command builders shared by task and manual transports.

No Helper, filesystem, HTTP or authorization dependency. The caller supplies
its attribution context; canonical writers still authorize the result.
"""
import copy
import hashlib
import json
import re
import uuid

def require(ok,code):
    if not ok:raise ValueError(code)

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()

def operation(context, req, graph, kernel):
    if graph.get('coreModel'):
        core=kernel
        command=req.get('action','')
        allowed = core.commands_for(graph) if hasattr(core, 'commands_for') else core.COMMANDS
        require(command.startswith('core_') and command[5:] in allowed - {'remove'},
                'CORE_COMMAND_REQUIRED')
        return {'op':'graph_edit','action':command,'data':copy.deepcopy(req.get('data',{})),
                'event':context.event(req['transactionId'],'core_change',req.get('note',''),
                    reasonForReconsideration=req.get('note',''),
                    **({'evidenceRefs':copy.deepcopy(req['evidenceRefs'])} if req.get('evidenceRefs') else {}))}
    action, tid = req['action'], req['transactionId']
    nodes = {n['id']:n for n in graph['nodes']}
    nid = req.get('nodeId')
    node = nodes.get(nid)
    note = req.get('note', '').strip()
    require(note, 'RESULT_OR_CHANGE_NOTE_REQUIRED')
    # Local manual attribution does not unlock protected-owner policy.
    require(not any(n.get('reconsiderationPolicy', {}).get('mode') == 'protected'
                    for n in graph['nodes']), 'HELPER_PROTECTED_OWNER_APPROVAL_UNAVAILABLE')
    def target(kind=None):
        require(node and not node.get('projectionOf') and
                (not kind or node['kind'] == kind), 'HELPER_TARGET_NOT_OWNED')
    if action == 'configure_graph_modules':
        return {'op':'configure_modules','modules':req.get('modules'),
                'disabledModules':req.get('disabledModules',[]),
                'event':context.event(tid,'modules_configured',note)}
    if action == 'module_operation':
        return {'op':'module_operation','module':req.get('module'),'version':req.get('version'),
                'operation':req.get('operation'),'node':copy.deepcopy(req.get('node')),
                'event':context.event(tid,'module_event',note)}
    if action == 'add_action':
        require(node and node['kind']=='requirement' and (not node.get('projectionOf') or
            nid==graph.get('rootRequirementId') and graph.get('expansionOf')==node['projectionOf']),
            'HELPER_TARGET_NOT_OWNED_OR_CONTINUATION_ROOT')
        title = req.get('title', '').strip()
        cases = req.get('recommended', '').splitlines()
        negative = req.get('contraindicated', '').splitlines()
        require(title and any(x.strip() for x in cases), 'ACTION_TITLE_AND_CANON_REQUIRED')
        aid = 'A-'+tid
        return {'op':'add_action', 'requirementId':nid,
            'action':{'id':aid,'kind':'action','title':title,'status':'candidate',
                'actionType':req.get('actionType','general'), 'qrpe':[],
                'canonBlock':{key:[{'id':prefix+tid+'-'+str(i),'text':x.strip()}
                                  for i,x in enumerate(values) if x.strip()]
                    for key,prefix,values in [('recommended','C-',cases),
                                             ('contraindicated','N-',negative)]}}}
    if action == 'edit_title':
        target()
        require(node['kind'] in ('action','requirement'), 'HELPER_TARGET_KIND')
        title = req.get('title','').strip();require(title, 'TITLE_REQUIRED')
        reformulate=node['kind']=='requirement'
        action_kind='reformulate_requirement' if reformulate else 'edit_node'
        return {'op':'graph_edit','action':action_kind,'nodeId':nid,'changes':{'title':title},
                'event':context.event(tid,'graph_changed',note,operation=action_kind)}
    if action == 'prepare_requirement':
        target('action')
        title=req.get('title','').strip();require(title,'TITLE_REQUIRED')
        return {'op':'graph_edit','action':'prepare_action_requirement','actionId':nid,
                'node':{'id':'R-'+tid,'kind':'requirement','title':title},
                'edgeId':'PE-'+tid,'childRole':req.get('childRole'),
                'event':context.event(tid,'graph_changed',note,operation='prepare_action_requirement')}
    if action == 'edit_canon':
        target('action')
        old=node.get('canonBlock',{})
        require(set(old)<={'recommended','contraindicated'} and all(
            set(c)<={'id','text'} for values in old.values() for c in values),
            'HELPER_COMPLEX_CANON_USE_FULL_API')
        plus=[x.strip() for x in req.get('recommended','').splitlines() if x.strip()]
        minus=[x.strip() for x in req.get('contraindicated','').splitlines() if x.strip()]
        require(plus,'CANON_RECOMMENDED_REQUIRED')
        canon={key:[{'id':prefix+tid+'-'+str(i),'text':x} for i,x in enumerate(values)]
               for key,prefix,values in [('recommended','C-',plus),('contraindicated','N-',minus)]}
        return {'op':'graph_edit','action':'edit_node','nodeId':nid,'changes':{'canonBlock':canon},
                'event':context.event(tid,'graph_changed',note,operation='edit_node')}
    if action == 'add_qrpe':
        target()
        text=req.get('title','').strip();require(text,'QRPE_TEXT_REQUIRED')
        return {'op':'append_qrpe','targetId':nid,
                'issue':{'id':'Q-'+tid,'text':text,'status':'open'}}
    if action == 'select':
        target('action')
        drivers=[e['from'] for e in graph['edges'] if e['type']=='DRIVES' and
                 e['to']==nid and not e.get('archived')]
        require(len(drivers)==1,'ACTION_DRIVER_REQUIRED')
        return {'op':'select_action','actionId':nid,
                'event':context.event(tid,'action_selected',note,actionId=nid,driverRequirementId=drivers[0])}
    if action == 'complete':
        target()
        require(node['kind'] in ('action','requirement'),'HELPER_TARGET_KIND')
        kind='action_executed' if node['kind']=='action' else 'requirement_achieved'
        return {'op':'record_action_execution' if node['kind']=='action' else 'record_requirement_achievement',
                'targetId':nid,'event':context.event(tid,kind,note,targetId=nid)}
    if action == 'withdraw':
        target('action')
        drivers=[e['from'] for e in graph['edges'] if e['type']=='DRIVES' and
                 e['to']==nid and not e.get('archived')]
        require(len(drivers)==1,'ACTION_DRIVER_REQUIRED')
        return {'op':'withdraw_action','actionId':nid,'dispositions':req.get('dispositions',[]),
                'event':context.event(tid,'action_withdrawn',note,actionId=nid,driverRequirementId=drivers[0])}
    raise ValueError('HELPER_UNKNOWN_ACTION')


def placement_request(context, req, view):
    action,tid=req['action'],req['transactionId']
    plan=view['sources']['plan']
    if action=='unplace':
        ops=[{'op':'unplace','stepId':req.get('stepId')}]
    else:
        target_file=req.get('graphFile',context.graph_file)
        require(target_file in view['sources']['graphs'],'HELPER_PLACEMENT_SOURCE_NOT_READ')
        target_graph=view['sources']['graphs'][target_file]
        require(target_graph['identitySpace']==plan['identitySpace'],'HELPER_PLAN_GRAPH_IDENTITY_MISMATCH')
        node=next((n for n in target_graph['nodes'] if n['id']==req.get('nodeId')),None)
        require(node and node['kind'] in ('action','requirement'),
                'HELPER_TARGET_NOT_OWNED')
        ref={'graphFile':target_file,'identitySpace':target_graph['identitySpace'],'nodeId':node['id']}
        field='actionRef' if node['kind']=='action' else 'requirementRef'
        matches=[s for s in plan['steps'] if all(s.get(field,{}).get(k)==v for k,v in ref.items())]
        require(len(matches)<=1 or req.get('stepId'), 'CHOOSE_EXISTING_PLACEMENT')
        existing=next((s for s in matches if s['id']==req.get('stepId')),None) if req.get('stepId') else next(iter(matches),None)
        require(not req.get('stepId') or existing, 'PLACEMENT_TARGET_MISMATCH')
        sid=existing['id'] if existing else 'S-'+node['id']
        if not existing and any(s['id']==sid for s in plan['steps']):
            sid='S-'+hashlib.sha256(canonical(ref)).hexdigest()[:24]
            require(not any(s['id']==sid for s in plan['steps']),'HELPER_PLACEMENT_ID_CONFLICT')
        step=copy.deepcopy(existing) if existing else {
            'id':sid,'title':node['title'],'kind':node['kind'],'state':'planned',field:ref}
        rules=copy.deepcopy([r for r in plan.get('timeConstraints',[]) if r['stepId']==sid])
        incoming=copy.deepcopy([e for e in plan.get('sequence',[]) if e['after']==sid])
        outgoing=copy.deepcopy([e for e in plan.get('sequence',[]) if e['before']==sid])
        starts=[r for r in rules if r['type']=='notBefore']
        if 'at' in req:
            require(len(starts)<=1 and all(re.fullmatch(r'\d{4}-\d{2}-\d{2}',r['at'])
                for r in starts),'HELPER_COMPLEX_PLACEMENT_USE_FULL_API')
            require(not req['at'] or re.fullmatch(r'\d{4}-\d{2}-\d{2}',req['at']),
                'HELPER_DATE_ONLY_USE_FULL_API')
            if starts:
                if req['at']:starts[0]['at']=req['at']
                else:rules=[r for r in rules if r['type']!='notBefore']
            elif req['at']:
                rules.append({'type':'notBefore','at':req['at'],'strength':'soft',
                    'basis':req.get('note') or 'Manual placement'})
        if 'afterStepId' in req:
            require(len(incoming)<=1,'HELPER_COMPLEX_PLACEMENT_USE_FULL_API')
            if req['afterStepId']:
                link=copy.deepcopy(incoming[0]) if incoming else {'after':sid}
                link['before']=req['afterStepId'];incoming=[link]
            else:incoming=[]
        operation={'op':'place','step':step,'timeConstraints':rules}
        if incoming!=[e for e in plan.get('sequence',[]) if e['after']==sid]:
            operation['sequence']=outgoing+incoming
        require(rules or outgoing or incoming,'EXPLICIT_TIME_OR_ORDER_REQUIRED')
        ops=[operation]
    request={'transactionId':tid,'op':'edit','file':context.plan_file,
        'expectedRevision':req['expectedPlanRevision'],'operations':ops}
    return request


def decision_request_data(graph, command, node_id, kernel, entity_kind=None):
    ns=kernel.entities(graph);node=ns.get(node_id)
    work_id=next((w['id'] for w in graph['workGraphs'] if node_id in w['memberIds']), graph['workGraphs'][0]['id'] if graph['workGraphs'] else None)
    if command=='lock_set':return {'nodeId':node_id,'operation':'edit','mode':'hard','principals':[],'message':''}
    if command=='lock_remove':return {'nodeId':node_id,'operation':'edit','disposition':''}
    if command=='finding_disposition':
        return {'nodeId':node_id,'disposition':{'code':'unresolved','basis':'','evidenceIds':[]},'observed':kernel.pins(graph,node_id)}
    if command=='context_record':return {'nodeId':node_id}
    if command=='finding_transfer':return {'nodeId':node_id,'subjectId':'CHOOSE_DECISION_ID'}
    if command=='context_group':return {'action':'save','id':'CG-'+uuid.uuid4().hex,'title':'','parentId':None}
    if command=='decision_context':return {'nodeId':node_id,'sourceId':'CHOOSE_SOURCE_ID','action':'save','comment':''}
    if command=='requirement_decision':return {'nodeId':node_id,'parentId':graph['rootRequirementId'],'decisionId':'D-'+uuid.uuid4().hex,'title':'Считать requirement необходимым','description':''}
    if command=='policy_change':
        return {'action':'policy_save','value':{}}
    if command=='dependency_rule':
        return {'mode':'save','relation':{'id':'DEP-'+uuid.uuid4().hex,
            'type':'DEPENDS_ON','from':node_id,'to':'CHOOSE_DEPENDENT_ID',
            'dependencyRule':{'preset':'L1','watch':['definition']}}}
    if command=='question_answer':return {'nodeId':node_id,'action':'add','kind':'hypothesis','text':'','sourceRefs':[]}
    if command=='question_migrate':return {'nodeId':node_id,'sourceRef':None}
    if command=='question_assess':return {'nodeId':node_id,'answerIds':[],'sufficient':False,'basis':''}
    if command=='add':
        kind=entity_kind or ('action' if node and node['kind'] in ('requirement','decision') else 'requirement')
        require(kind in ('requirement','decision','action','canon','context','info','finding','question'),'ENTITY_KIND_UNSUPPORTED')
        ident={'requirement':'R-','decision':'D-','action':'A-','canon':'CAN-','context':'CTX-','info':'I-','finding':'F-','question':'Q-'}[kind]+uuid.uuid4().hex
        entity={'id':ident,'kind':kind,'title':'','description':'','revision':1,
                'result':{'state':'open','truth':'unknown'}}
        if kind not in ('requirement','decision','action'):entity.pop('result')
        relations=[]
        if kind=='action':
            entity.update(actionType='task',lowLevel=False,targetIds=[],groupIds=[])
            if node and node['kind'] in ('requirement','decision'):
                relations=[{'id':'REL-'+uuid.uuid4().hex,'type':'REQUIRES_ACTION','from':node_id,'to':ident}]
        elif kind=='requirement':
            entity.update(scope=ns.get(graph.get('rootRequirementId'),{}).get('scope','Explicit scope'))
            if node and node['kind']=='decision':
                relations=[{'id':'REL-'+uuid.uuid4().hex,'type':'INTRODUCES','from':node_id,'to':ident}]
            elif node and node['kind']=='requirement':
                relations=[{'id':'REL-'+uuid.uuid4().hex,'type':'DERIVES','from':node_id,'to':ident}]
        elif kind=='decision':
            entity['selectionState']='discovered'
            if node and node['kind']=='requirement':
                relations=[{'id':'REL-'+uuid.uuid4().hex,'type':'DRIVES','from':node_id,'to':ident}]
        elif kind=='question':
            entity.update(relatedRefs=[],sourceRefs=[],impact='',answerCondition='',answers=[],assessmentHistory=[],assessmentReviewRequired=False)
        elif kind=='finding':
            entity.update(subjectId=node_id if node and node['kind']=='decision' else 'CHOOSE_DECISION_ID',findingType='',rationale='',evidenceIds=[])
        elif kind in ('context','info'):entity['value']=''
        elif kind=='canon':entity.update(guidance='',canons='')
        if node and (kind=='canon' and node['kind'] in ('decision','action') or kind=='info'):
            relations=[{'id':'REL-'+uuid.uuid4().hex,'type':'CANON_FOR' if kind=='canon' else 'INFO_FOR','from':ident,'to':node_id}]
        if kind not in ('requirement','decision','action'):work_id=None
        return {'entity':entity,'location':'graph','workGraphId':work_id,'initialRelations':relations}
    if command=='edit':
        require(node is not None,'FOCUS_NOT_FOUND')
        return {'nodeId':node_id,'changes':{'title':node['title']},'cosmetic':True}
    if command=='link':
        require(node is not None,'FOCUS_NOT_FOUND')
        relation={'id':'REL-'+uuid.uuid4().hex,'type':'DRIVES' if node['kind']=='requirement' else
                  'INTRODUCES' if node['kind']=='decision' else 'REQUIRES_ACTION',
                  'from':node_id if node['kind']!='action' else 'CHOOSE_SOURCE_ID',
                  'to':'CHOOSE_TARGET_ID' if node['kind']!='action' else node_id}
        return {'relation':relation}
    if command=='unlink':return {'edgeId':'CHOOSE_ACTUAL_RELATION_ID'}
    if command in ('select','withdraw'):
        return {'nodeId':node_id if node and node['kind']=='decision' else 'CHOOSE_DECISION_ID'}
    if command=='complete':
        data={'nodeId':node_id or 'CHOOSE_TARGET_ID','basis':'Describe the observed result','evidenceIds':[]}
        if node and node.get('kind')=='action' and node.get('actionType')=='decide_acceptance':
            data['decisionOutcome']='selected'
        return data
    if command=='reopen':return {'nodeId':node_id or 'CHOOSE_TARGET_ID','basis':'Explain why the result is reopened'}
    if command=='decision_group':
        parent=node_id if node and node['kind']=='requirement' else graph.get('rootRequirementId')
        return {'group':{'id':'GROUP-'+uuid.uuid4().hex,'parentId':parent,'title':'',
            'selectionRequired':True,'mutuallyExclusive':True,
            'members':[{'id':'MEM-'+uuid.uuid4().hex,'decisionId':'CHOOSE_DECISION_ID'}]}}
    if command=='root_cause':
        cause=copy.deepcopy(graph['rootCauses'][0]) if graph['rootCauses'] else {
            'id':'RC-'+uuid.uuid4().hex,'requirementId':graph.get('rootRequirementId'),'reason':'','enabled':True}
        return {'cause':cause}
    if command=='work_graph':
        root=node_id if node and node['kind']=='requirement' else graph.get('rootRequirementId')
        return {'workGraph':{'id':'WG-'+uuid.uuid4().hex,'title':'',
            'rootIds':[root] if root else [],'memberIds':[root] if root else ([node_id] if node_id else [])}}
    if command=='review':
        require(node is not None,'FOCUS_NOT_FOUND')
        return {'nodeIds':[node_id],'observed':kernel.pins(graph,node_id),'basis':'Reviewed current inputs'}
    require(False,'DECISION_COMMAND_UNSUPPORTED')


def core_request_data(graph,command,node_id,kernel,entity_kind=None):
    if graph.get('coreModel') == 'rdg-decision-v1':
        return decision_request_data(graph, command, node_id, kernel,entity_kind)
    require(entity_kind is None,'ENTITY_KIND_REQUIRES_DECISION_PROFILE')
    ns=kernel.entities(graph);node=ns.get(node_id)
    if node is None and command=='add':
        return {'entity':{'id':'N-'+uuid.uuid4().hex,'kind':'requirement','title':'','description':'','scope':'','status':'potential'},
                'workGraphId':graph['workGraphs'][0]['id'] if graph['workGraphs'] else None}
    if command=='lens_recommendations':return {'recommendations':copy.deepcopy(graph.get('lensRecommendations',[]))}
    require(node is not None,'FOCUS_NOT_FOUND')
    if command=='add':
        kind='requirement' if node['kind']=='action' else 'action'
        entity={'id':('R-' if kind=='requirement' else 'A-')+uuid.uuid4().hex,'kind':kind,'title':'',
                'description':'','status':'potential' if kind=='requirement' else 'candidate'}
        if kind=='requirement':entity['scope']=ns.get(graph.get('rootRequirementId'),node).get('scope','')
        return {'entity':entity,'workGraphId':next(w['id'] for w in graph['workGraphs'] if node_id in w['memberIds'])}
    if command=='edit':return {'nodeId':node_id,'changes':{'description':node.get('description','')},'cosmetic':False}
    if command=='link':return {'edge':{'id':'E-'+uuid.uuid4().hex,'type':'INTRODUCES' if node['kind']=='action' else 'DRIVES',
                                     'from':node_id,'to':'CHOOSE_ACTUAL_TARGET_ID',
                                     **({'origin':{'role':'subgoal','requirementIds':[]}} if node['kind']=='action' else {})}}
    if command=='lens_recommendations':return {'recommendations':copy.deepcopy(graph.get('lensRecommendations',[]))}
    if command=='output_origin':return {'edgeId':'CHOOSE_ACTUAL_INTRODUCES_EDGE_ID',
                                       'origin':{'role':'subgoal','requirementIds':[]}}
    if command=='unlink':return {'edgeId':'CHOOSE_ACTUAL_EDGE_ID','disposition':''}
    if command=='review':return {'nodeIds':[node_id],'observed':kernel.pins(graph,node_id)}
    if command=='assess':
        require(node['kind']=='action','ASSESS_ACTION_REQUIRED')
        canons=[ns[e['from']] for e in kernel.active_edges(graph) if e['type']=='CANON_FOR' and e['to']==node_id]
        return {'nodeId':node_id,'matches':{c['id']:{leaf['id']:{'result':'unknown','reason':'','sourceIds':[]}
                for a in c['arguments'] for leaf in kernel.argument_leaves(a['condition'])} for c in canons}}
    if command=='withdraw':return {'nodeId':node_id,'dispositions':{e['to']:'' for e in kernel.active_edges(graph) if e['type']=='INTRODUCES' and e['from']==node_id}}
    if command=='requirement_state':
        inactive=node['status']=='active'
        return {'nodeId':node_id,'state':'inactive' if inactive else 'active','disposition':'',
                'acceptSharedConsequences':False,
                **({'decisionActionId':'CHOOSE_CONFIRMED_LINKED_ACTION_ID'} if inactive else {})}
    if command=='work_graph':
        root=node_id if node['kind']=='requirement' else graph.get('rootRequirementId')
        return {'id':'WG-'+uuid.uuid4().hex,'title':'','rootIds':[root] if root else [],'memberIds':[root] if root else [node_id]}
    if command=='include':return {'nodeId':node_id,'workGraphId':'CHOOSE_ACTUAL_WORK_GRAPH_ID'}
    if command=='join':return {'workGraphIds':['CHOOSE_ACTUAL_FIRST_WORK_GRAPH','CHOOSE_ACTUAL_SECOND_WORK_GRAPH']}
    if command=='exclusion_group':return {'id':'X-'+uuid.uuid4().hex,'actionIds':[node_id,'CHOOSE_ANOTHER_ACTION_ID'],'reason':''}
    if command=='finding':return {'nodeId':node_id,'finding':{'id':'F-'+uuid.uuid4().hex,'type':'risk','text':''}}
    if command=='resolve_finding':return {'nodeId':node_id,'findingId':'CHOOSE_ACTUAL_FINDING_ID'}
    return {'nodeId':node_id}
