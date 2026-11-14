"""Atomic same-owner RDG batch planner; runs inside Application's coordinator.

The batch is a single authorized prepared effect. Alias references use the
exact object {"$alias": "step-name"}, never plain string substitution.
"""
import copy
from datetime import datetime, timezone
import re
import uuid

GRAPH_COMMANDS = ('add','edit','link','unlink','decision_group','root_cause',
                  'work_graph','context_group','decision_context',
                  'requirement_decision','finding_transfer','context_record',
                  'select','withdraw','question_answer','question_assess','question_migrate')
PAPER_COMMANDS = ('add','edit','graph_title','link','unlink','decision_group','root_cause','work_graph','remove')
PLAN_COMMANDS = ('plan_create','place','unplace')
FUTURE = ()
EXCLUDED = ('graph_title','complete','finding_disposition','review','reopen','policy_change',
            'dependency_rule','lock_set','lock_remove','lens_application',
            'recommendation_packages','remove','attach_evidence','cross_owner_plan',
            'registry','migration')


def schema(role=None):
    paper=role in ('ready','lens')
    return {
        'schemaVersion':1,'op':'batch','maxSteps':100,
        'supportedRoles':['working','copy','ready','lens'],
        'steps':{'required':['alias','op'], 'core':{'op':'core','command':list(GRAPH_COMMANDS),
                 'data':'same as core command', 'note':'optional step note'},
                 'paper':{'op':'paper_edit','command':list(PAPER_COMMANDS),'data':'same as paper_edit command; no Plan or process transitions'},
                 'plan':list(PLAN_COMMANDS)+['plan_action'],
                 'planAction':{'op':'plan_action','entity':'ordinary external task with optional subjectRefs','placement':'optional placement fields','alias':'Action ID; alias+Placement identifies placement'},
                 'aliasRef':{'$alias':'earlier-step-alias'},
                 'entityRef':{'$entityRef':'earlier-step-alias'},
                 'aliasMeaning':'generated or explicit entity/edge/group/step ID'},
        'stepOp':'paper_edit' if paper else 'core',
        'unsupported':[c for c in EXCLUDED if not paper or c not in PAPER_COMMANDS],
        'unsupportedByRole':{'working/copy':list(EXCLUDED),
            'ready/lens':list(PLAN_COMMANDS)+['plan_action']+sorted(set(GRAPH_COMMANDS+EXCLUDED)-set(PAPER_COMMANDS))},
        'transaction':'one owner, one preflight/apply/receipt, one initial CAS',
        'required':['transactionId','targetPackageId','expectedPackageRevision',
                    'expectedGraphRevision','steps','note'],
        'optional':['expectedPlanRevision']
    }


def plan(app, request, *, attribution, trust, recorded_at=None):
    check=app.check
    allowed={'op','transactionId','targetPackageId','expectedPackageRevision',
             'expectedGraphRevision','expectedPlanRevision','steps','note'}
    check(set(request) <= allowed,'BATCH_FIELDS')
    steps=request.get('steps')
    check(isinstance(steps,list) and 1<=len(steps)<=100,'BATCH_STEPS')
    check(isinstance(request.get('note'),str) and bool(request['note'].strip()),'BATCH_NOTE')
    expanded=[];placements=[]
    for step in steps:
        if isinstance(step,dict) and step.get('op')=='plan_action':
            check(set(step)<={'op','alias','entity','placement','note'},'PLAN_ACTION_FIELDS')
            check(isinstance(step.get('alias'),str),'BATCH_ALIAS_UNKNOWN')
            entity=copy.deepcopy(step.get('entity',{}))
            check(isinstance(entity,dict) and entity.get('kind','action')=='action' and
                  entity.get('actionType','task')=='task' and entity.get('lowLevel',False) is False,'PLAN_ACTION_KIND')
            entity.update(kind='action',actionType='task',lowLevel=False)
            entity.setdefault('subjectRefs',[])
            expanded.insert(next((i for i,v in enumerate(expanded) if v.get('op') in PLAN_COMMANDS),len(expanded)),{'alias':step['alias'],'op':'core','command':'add',
                'data':{'entity':entity,'location':'external'},'note':step.get('note',request['note'])})
            placement=copy.deepcopy(step.get('placement',{}))
            check(isinstance(placement,dict) and set(placement)<={'stepId','afterStepId','caseId','at','deadline'},'PLAN_ACTION_PLACEMENT')
            placements.append({**placement,'alias':step['alias']+'Placement','op':'place',
                'nodeId':{'$alias':step['alias']},'note':step.get('note',request['note'])})
        else:expanded.append(step)
    steps=expanded+placements
    ident=request.get('targetPackageId')
    check(isinstance(ident,str) and bool(ident),'BATCH_OWNER')
    tx=uuid.UUID(request['transactionId'])
    requested_plan=any(isinstance(step,dict) and step.get('op') in PLAN_COMMANDS for step in steps)
    read_plan=requested_plan or 'expectedPlanRevision' in request
    row=app.snapshot(ident,read_plan)
    check(row['graph'].get('coreModel')=='rdg-decision-v1', 'BATCH_PROFILE')
    paper=row['head']['role'] in ('ready','lens')
    check(row['head']['role'] in ('working','copy','ready','lens') and not
          (row['head'].get('lineage',{}).get('supplied') and
           not row['head'].get('lineage',{}).get('userManaged')),'PACKAGE_IMMUTABLE')
    check(request.get('expectedPackageRevision')==row['head']['revision'],'PACKAGE_CAS_MISMATCH')
    check(request.get('expectedGraphRevision')==row['graph']['revision'],'GRAPH_CAS_MISMATCH')
    if requested_plan or 'expectedPlanRevision' in request:
        check(request.get('expectedPlanRevision') ==
              (row['plan']['revision'] if row['plan'] else None),'PLAN_CAS_MISMATCH')
    check(not paper or not requested_plan,'BATCH_PAPER_PLAN_UNSUPPORTED')
    aliases={};results=[];operations=[];plan_specs=[];graph_phase=True
    external_rows={};boundary=None
    now=recorded_at if recorded_at is not None else datetime.now(timezone.utc).isoformat()
    def external(source_id):
        if source_id==ident:return row
        if source_id not in external_rows:external_rows[source_id]=app.snapshot(source_id,layouts=False)
        return external_rows[source_id]
    def resolve(value):
        if isinstance(value,dict):
            if '$entityRef' in value:
                check(set(value)=={'$entityRef'} and value['$entityRef'] in aliases and aliases[value['$entityRef']] is not None,'BATCH_ALIAS_UNKNOWN')
                return {'$entityRefId':aliases[value['$entityRef']]}
            check('$entityRefId' not in value,'BATCH_ALIAS_INTERNAL')
            if '$alias' in value:
                check(set(value)=={'$alias'} and isinstance(value['$alias'],str) and
                      value['$alias'] in aliases and aliases[value['$alias']] is not None,
                      'BATCH_ALIAS_UNKNOWN')
                return aliases[value['$alias']]
            return {k:resolve(v) for k,v in value.items()}
        if isinstance(value,list):return [resolve(v) for v in value]
        return value
    for index,step in enumerate(steps):
        check(isinstance(step,dict),'BATCH_STEP')
        alias=step.get('alias')
        check(isinstance(alias,str) and bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',alias))
              and alias not in aliases,'BATCH_ALIAS_DUPLICATE')
        op=step.get('op')
        check(op in (('paper_edit',) if paper else ('core',)+PLAN_COMMANDS),'BATCH_STEP_UNSUPPORTED')
        note=step.get('note',request['note'])
        check(isinstance(note,str) and bool(note.strip()),'BATCH_STEP_NOTE')
        if op in ('core','paper_edit'):
            check(graph_phase,'BATCH_GRAPH_AFTER_PLAN_UNSUPPORTED')
            check(set(step)<={'alias','op','command','data','note'},'BATCH_STEP_FIELDS')
            command=step.get('command')
            check(command in (PAPER_COMMANDS if paper else GRAPH_COMMANDS),'BATCH_COMMAND_UNSUPPORTED')
            check(command in app.authoring_commands(row['graph'],row['head']['role']),'CORE_COMMAND')
            check(isinstance(step.get('data'),dict),'BATCH_DATA')
            data=copy.deepcopy(step['data'])
            result_id=None
            if command=='add':
                entity=data.get('entity')
                check(isinstance(entity,dict),'BATCH_ENTITY')
                result_id=entity.get('id') or str(uuid.uuid5(tx,'entity:'+alias))
                check(isinstance(result_id,str) and bool(result_id),'BATCH_ENTITY_ID')
                entity['id']=result_id
            elif command=='link':
                edge=data.get('edge',data.get('relation'))
                check(isinstance(edge,dict),'BATCH_EDGE')
                result_id=edge.get('id') or str(uuid.uuid5(tx,'edge:'+alias))
                check(isinstance(result_id,str) and bool(result_id),'BATCH_EDGE_ID')
                edge['id']=result_id
            elif command in ('decision_group','root_cause','work_graph'):
                field={'decision_group':'group','root_cause':'cause','work_graph':'workGraph'}[command]
                value=data.get(field)
                check(isinstance(value,dict),'BATCH_GROUP')
                result_id=value.get('id') or str(uuid.uuid5(tx,field+':'+alias))
                check(isinstance(result_id,str) and bool(result_id),'BATCH_GROUP_ID')
                value['id']=result_id
            elif command=='context_group' and data.get('action')=='save':
                result_id=data.get('id') or str(uuid.uuid5(tx,'context-group:'+alias))
                data['id']=result_id
            elif command=='requirement_decision':
                result_id=data.get('decisionId') or str(uuid.uuid5(tx,'decision:'+alias))
                data['decisionId']=result_id
            elif command in ('edit','unlink','select','withdraw','decision_context','finding_transfer','context_record','question_migrate'):
                result_id=data.get('nodeId') or data.get('edgeId')
            elif command in ('question_answer','question_assess'):
                result_id=(str(uuid.uuid5(uuid.uuid5(tx,'batch-event:'+str(index)),'answer' if command=='question_answer' else 'assessment'))
                           if data.get('action','add')=='add' else data.get('answerId'))
            # Assign ID first, allowing self-reference but never forward-reference.
            result_id=resolve(result_id)
            aliases[alias]=result_id
            data=resolve(data)
            def static_refs(value):
                if isinstance(value,dict):
                    if set(value)=={'$entityRefId'}:return None
                    return {k:static_refs(v) for k,v in value.items()}
                if isinstance(value,list):return [static_refs(v) for v in value if not isinstance(v,dict) or set(v)!={'$entityRefId'}]
                return value
            if command!='question_migrate' or not isinstance(data.get('sourceRef'),dict) or '$entityRefId' not in data['sourceRef']:
                app.kernel.for_graph(row['graph']).QUESTIONS.require_owner_inputs(command,static_refs(data),ident,row['graph'],app.kernel.for_graph(row['graph']),app.model)
            if command in ('select','withdraw'):
                if boundary is None:
                    def external(source_id):
                        if source_id==ident:return row
                        if source_id not in external_rows:
                            external_rows[source_id]=app.snapshot(source_id,layouts=False)
                        return external_rows[source_id]
                    boundary=app.boundaries(row,external)
                targets={data.get('nodeId')}
                check(not targets & set(boundary['reviewIds']),'EXTERNAL_DEPENDENCY_REVIEW_REQUIRED')
                if command=='select':
                    check(not targets & set(boundary['conflictIds']),'EXTERNAL_EXCLUSION_CONFLICT')
            ev={'id':str(uuid.uuid5(tx,'batch-event:'+str(index))),
                'type':'requested','by':attribution,'note':note,'recordedAt':now,
                'verifiedTrustReceipt':copy.deepcopy(trust) if trust else
                    {'mode':'local-manual-session' if attribution=='user' else 'portable-planning',
                     'transactionId':str(tx)}}
            operations.append({'op':'graph_edit','action':'core_'+command,
                               'data':data,'event':ev})
            results.append({'alias':alias,'op':op,'command':command,'id':result_id})
        else:
            graph_phase=False
            check(set(step)<={'alias','op','title','nodeId','stepId','afterStepId',
                              'caseId','at','deadline','note'},'BATCH_PLAN_FIELDS')
            if op=='plan_create':
                check(isinstance(step.get('title'),str) and bool(step['title'].strip()),'PLAN_TITLE_REQUIRED')
                result_id=str(uuid.uuid5(tx,'plan:'+alias))
            elif op=='place':
                check('nodeId' in step,'BATCH_PLACEMENT_NODE')
                result_id=step.get('stepId') or str(uuid.uuid5(tx,'placement:'+alias))
            else:
                check('stepId' in step,'BATCH_PLACEMENT_STEP')
                result_id=step['stepId']
            result_id=resolve(result_id)
            aliases[alias]=result_id
            plan_specs.append((op,resolve(copy.deepcopy(step)),result_id))
            results.append({'alias':alias,'op':op,'id':result_id})
    check(bool(operations or plan_specs),'BATCH_STEPS')
    # All Graph operations run through the existing kernel as one ordered patch.
    graph=row['graph'];removed_ids=set();removal=False
    if operations:
        def resolve_data(value,current):
            if isinstance(value,dict):
                if set(value)=={'$entityRefId'}:return app.model.reference(ident,current,value['$entityRefId'])
                return {k:resolve_data(v,current) for k,v in value.items()}
            if isinstance(value,list):return [resolve_data(v,current) for v in value]
            return value
        validation_index=0
        def checked_data(value,current):
            nonlocal validation_index
            command=operations[validation_index]['action'][5:];validation_index+=1
            value=resolve_data(value,current)
            app.validate_action_subjects(command,value,ident,current,external)
            app.validate_theory_sources(command,value,ident,current,external,role=row['head']['role'])
            if command=='remove':removed_ids.update(value.get('nodeIds',[]))
            return value
        graph,_=app.kernel.for_graph(graph).apply(graph,{'schemaVersion':1,
            'expectedRevision':graph['revision'],'operations':operations},True,resolve_data=checked_data,paper=paper,
            coordinated=paper and any(o['action']=='core_remove' for o in operations))
        if paper:app.ergonomics.normalize_paper(app,graph)
        app.kernel.for_graph(graph).validate_authored_theory(graph,row['graph'])
        app.model.validate_graph_payload(graph,app.kernel)
        app.kernel.validate_role(graph,row['head']['role'])
    registry_row=None
    if paper and removed_ids:
        check(not removed_ids & set(app.kernel.entities(graph)),'BATCH_REMOVED_ID_REUSED')
        foreign,registry_row=app.ergonomics.paper_removal_guard(app,row,removed_ids,graph)
        external_rows.update(foreign);removal=True
    actual_plan=row['plan']
    if plan_specs:
        for operation,spec,result_id in plan_specs:
            if operation=='plan_create':
                check(actual_plan is None,'PLAN_ALREADY_EXISTS_OR_PAPER')
                actual_plan=app.empty_plan(result_id,graph['identitySpace'],spec['title'],decision=True)
            else:
                check(actual_plan is not None,'PLAN_OWNER_REQUIRED')
                if operation=='place':
                    node_id=spec['nodeId']
                    node=app.kernel.entities(graph).get(node_id)
                    check(node is not None,'PLACEMENT_NODE_UNKNOWN')
                    ref=app.model.reference(ident,graph,node_id)
                else:
                    node=None;ref=None
                placement={k:v for k,v in spec.items() if k not in ('alias','title')}
                placement.update(op=operation,stepId=result_id,note=spec.get('note',request['note']))
                actual_plan=app.model.place(actual_plan,placement,ref,node)
        app.model.validate_plan(actual_plan)
        app.validate_new_placements(row['plan'],actual_plan) if row['plan'] else None
        for step in actual_plan['steps']:
            ref=step['ref']
            check(ref['packageId']==ident and ref['identitySpace']==graph['identitySpace'],
                  'UNSUPPORTED_PROFILE_CAPABILITY:cross-owner-plan')
            node=app.kernel.entities(graph).get(ref['nodeId'])
            check(node is not None and node['kind']==step['kind'],'PLAN_REFERENCE_MISMATCH')
            if not row['plan'] or not any(old['id']==step['id'] and old['ref']==ref
                                         for old in row['plan']['steps']):
                check(ref==app.model.reference(ident,graph,ref['nodeId']),'PLAN_REFERENCE_PIN_CHANGED')
    permissions=(['graph.write'] if operations else [])+(
        ['plan.create'] if plan_specs and row['plan'] is None else
        ['plan.edit'] if plan_specs else [])
    if plan_specs and row['plan'] and actual_plan.get('forks')!=row['plan'].get('forks'):
        permissions.append('plan.branch')
    read_permissions=['graph.read']+(['plan.read'] if read_plan and row['plan'] else [])
    checks=[{'namespaceId':app.store.namespace_id,'packageId':ident,'path':row['path'],
             'permissions':read_permissions},
            {'namespaceId':app.store.namespace_id,'packageId':ident,'path':row['path'],
             'permissions':permissions}]
    for source_id,source in external_rows.items():
        checks.append({'namespaceId':app.store.namespace_id,'packageId':source_id,
                       'path':source['path'],'permissions':['graph.read']+(['plan.read'] if source.get('plan') else [])})
    if registry_row is not None:
        checks.append({'namespaceId':app.store.namespace_id,'packageId':None,'path':None,'permissions':['graph.read']})
    for entry in checks:
        app.authorize(entry['packageId'],entry['permissions'],entry['path'])
    effect={'operation':'batch','aliasIds':{k:v for k,v in aliases.items() if v is not None},
            'stepResults':results,'stepCount':len(steps),
            'graphRevision':graph['revision']}
    if removal:effect.update(app.ergonomics.removal_effects(app,row['graph'],graph))
    if plan_specs:effect['planRevision']=actual_plan['revision']
    changed={'path':row['path'],'before':row,'permissions':permissions,
             'effects':copy.deepcopy(effect)}
    if operations:changed['graph']=graph
    if removal and row['layouts'] is not None:changed['layouts']=app.ergonomics.cleaned_layouts(app,row,graph)
    if plan_specs:changed['plan']=actual_plan
    readset={ident:row['headSHA256'], **{sid:source['headSHA256'] for sid,source in external_rows.items()}}
    pins=[{'kind':'package','namespaceId':app.store.namespace_id,'packageId':sid,
           'revision':source['head']['revision'],'sha256':source['headSHA256']}
          for sid,source in sorted({ident:row,**external_rows}.items())]
    if registry_row is not None:
        readset[app.store.registry_key()]=registry_row['headSHA256']
        if registry_row['headSHA256']:
            pins.append({'kind':'recommendationRegistry','namespaceId':app.store.namespace_id,
                'revision':registry_row['registry']['revision'],'sha256':registry_row['headSHA256']})
    return {'changes':{ident:changed},'checks':checks,
            'readset':readset,'ownerPins':pins,
            'decisionProfile':True,
            'catalog':app.store.catalog_signature(ignore_ids=set()),
            'effects':effect,'allocation':None}
