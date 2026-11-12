#!/usr/bin/env python3
"""Create the current full RDG teaching process through schema/preflight/apply.

Existing examples are never changed. The local operator journal preserves exact
transaction IDs and input bindings across uncertain transport outcomes.
"""
import argparse
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import uuid

ROOT=Path(__file__).resolve().parents[1]
TITLE='Пример · выбор, анализ и выполнение'
PATH='examples/decision-readiness-20261112'
JOURNAL=SourceFileLoader('rdg_example_journal',str(ROOT/'tools/rdg-example-journal.py')).load_module()

def run(client,journal_file,path=PATH,progress=print):
    journal_file=Path(journal_file)
    journal=JOURNAL.Journal(journal_file,{'operations':{},'path':path,'day':datetime.now(ZoneInfo('Asia/Bangkok')).date().isoformat()})
    if journal.state['path']!=path:raise ValueError('EXAMPLE_JOURNAL_PATH_MISMATCH')
    try:return _run(client,journal,path,progress)
    finally:journal.checkpoint()


def _run(client,journal,path,progress):
    state=journal.state
    def save(key=None):journal.append(key)
    def accepted(key,op):
        req=op['request'];result=op['result'];pid=req.get('targetPackageId') or result['packages'][0]['packageId']
        if not op.get('receipt',{}).get('found'):
            op['receipt']=client.call({'method':'receipt','packageId':pid,'transactionId':req['transactionId']});save(key)
        if not op['receipt'].get('found') or not op['receipt'].get('published'):raise RuntimeError('RECEIPT_UNCONFIRMED:'+req['transactionId'])
        return result
    def write(key,request):
        op=state['operations'].get(key)
        if op and op.get('result',{}).get('published'):return accepted(key,op)
        if op and not op.get('applyAttempted'):
            state.setdefault('unappliedAttempts',[]).append(op);op=None
        if op is None:op={'request':request};state['operations'][key]=op;save(key)
        req=op['request']
        if 'preview' not in op:op['preview']=client.call({'method':'preflight','request':req});save(key)
        op['applyAttempted']=True;save(key)
        try:op['result']=client.call({'method':'apply','request':req,'expectedInputBinding':op['preview']['inputBinding']});save(key)
        except Exception as exc:op['uncertain']=str(exc);save(key);raise RuntimeError('Retry the same journal; preserved transactionId='+req['transactionId']) from exc
        if not op['result'].get('published'):raise RuntimeError('PUBLICATION_UNCONFIRMED:'+req['transactionId'])
        progress(key);return accepted(key,op)
    if 'create' not in state['operations']:
        catalog=client.call({'method':'catalog'})
        if any(p['path']==path for p in catalog['packages']):raise ValueError('EXAMPLE_PATH_EXISTS_WITHOUT_JOURNAL')
        if not any(p.get('role')=='lens' and p.get('lensKey')=='work' and p.get('coreModel')=='rdg-decision-v1' for p in catalog['packages']):raise ValueError('EXAMPLE_REQUIRES_EXISTING_DECISION_WORK_LENS')
        probe=next((p for p in catalog['packages'] if p.get('coreModel')=='rdg-decision-v1' and p.get('role') in ('working','copy')),None)
        if probe and not client.call({'method':'read','packageId':probe['packageId']}).get('capabilities',{}).get('capabilities',{}).get('actionEstimates'):raise ValueError('INSTALL_QUESTIONS_ESTIMATES_RUNTIME_FIRST')
        if probe and not client.call({'method':'read','packageId':probe['packageId']}).get('capabilities',{}).get('capabilities',{}).get('decisionTheory'):raise ValueError('INSTALL_DECISION_THEORY_RUNTIME_FIRST')
        if probe and not client.call({'method':'read','packageId':probe['packageId']}).get('capabilities',{}).get('capabilities',{}).get('recommendationAuthoring'):raise ValueError('INSTALL_RECOMMENDATION_RUNTIME_FIRST')
        if probe and not client.call({'method':'read','packageId':probe['packageId']}).get('capabilities',{}).get('capabilities',{}).get('planningMetaAction'):raise ValueError('INSTALL_PLANNING_META_ACTION_RUNTIME_FIRST')
        read_schema=client.call({'method':'schema','op':'read'})
        if not {'focus','branch'} <= set(read_schema.get('read',{}).get('detail',[])):raise ValueError('INSTALL_FOCUS_BRANCH_RUNTIME_FIRST')
        if probe and 'fork-end' not in client.call({'method':'read','packageId':probe['packageId']}).get('capabilities',{}).get('planFeatures',[]):raise ValueError('INSTALL_TEMPORAL_PLAN_RUNTIME_FIRST')
    req=client.call({'method':'schema','op':'create'})['request'];req.update(path=path,role='working',coreModel='rdg-decision-v1',title=TITLE,scope='Полноценный учебный процесс: данные, бумажные альтернативы, принятие/отмена, подтверждённые учебные результаты и будущие ветви Plan',rootReason='Учебная демонстрация текущей модели. Не выполнение боевых работ.')
    pid=write('create',req)['packages'][0]['packageId'];state['packageId']=pid;save()
    def read():return client.call({'method':'read','packageId':pid,'includePlan':True})
    if state.get('verified'):
        read()  # Confirm the owner still exists, without replaying completed work.
        progress('EXAMPLE_READY '+json.dumps({'packageId':pid,'title':TITLE,'path':path,**state['verified']},ensure_ascii=False));return state
    initial=read()
    if 'fork-end' not in initial.get('capabilities',{}).get('planFeatures',[]):raise ValueError('INSTALL_TEMPORAL_PLAN_RUNTIME_FIRST')
    if not initial.get('capabilities',{}).get('capabilities',{}).get('decisionTheory'):raise ValueError('INSTALL_DECISION_THEORY_RUNTIME_FIRST')
    root=initial['graph']['rootRequirementId']
    def core(key,command,data,node=None):
        if state['operations'].get(key,{}).get('applyAttempted'):return write(key,state['operations'][key]['request'])
        req=client.call({'method':'schema','op':'core','packageId':pid,'nodeId':node or data.get('nodeId') or root,'command':command})['request'];req.update(data=data,note='Учебный сценарий: '+key);return write(key,req)
    def add(i,kind,title,parent=None,relation=None,**fields):
        entity={'id':i,'kind':kind,'title':title,'description':'Учебный процесс; факты относятся только к этому примеру.',**fields}
        if kind=='requirement':entity.setdefault('scope','Учебное представление решения и его результата')
        if kind=='action':entity.update(actionType='task',lowLevel=False,targetIds=[],groupIds=[])
        data={'entity':entity,'location':'graph'}
        if parent:data['initialRelations']=[{'id':'REL-'+i,'type':relation,'from':i if relation in ('CANON_FOR','INFO_FOR') else parent,'to':parent if relation in ('CANON_FOR','INFO_FOR') else i}]
        return core('add-'+i,'add',data)
    for i,title in [('R-STORE','Выбрать способ учебного хранения'),('R-CACHE','Определить кеширование'),('R-SCALE','Подготовить рост нагрузки'),('R-LATENCY','Отклик не дольше 150 мс'),('R-SAFE','Сохранять согласованность'),('R-RELEASE','Подготовить учебный выпуск')]:add(i,'requirement',title,root,'DERIVES')
    for i,title,parent in [('D-SQL','Использовать SQL-таблицу','R-STORE'),('D-FILE','Использовать файловый прототип','R-STORE'),('D-TEMP','Добавить временный кеш','R-CACHE'),('D-NOCACHE','Продолжить без кеша','R-CACHE'),('D-UP','Увеличить ресурсы сервера','R-SCALE'),('D-OUT','Добавить отдельную реплику','R-SCALE')]:add(i,'decision',title,parent,'DRIVES')
    for i,title,parent,rel in [('R-DDL','Подготовить учебную схему','D-SQL','INTRODUCES'),('R-DOC','Описать учебную схему','R-DDL','DERIVES'),('R-FILE','Подготовить файловый формат','D-FILE','INTRODUCES'),('R-MEM','Подготовить память кеша','D-TEMP','INTRODUCES'),('R-TTL','Определить срок жизни записей','R-MEM','DERIVES'),('R-CPU','Подготовить ресурсный профиль','D-UP','INTRODUCES'),('R-REPL','Подготовить правила чтения с реплики','D-OUT','INTRODUCES')]:add(i,'requirement',title,parent,rel)
    for i,title,parent in [('A-DDL','Записать учебный DDL','R-DDL'),('A-DOC','Записать описание схемы','R-DOC'),('A-FILE','Записать файловый формат','R-FILE'),('A-CACHE','Проверить правила кеша','R-TTL'),('A-CPU','Проверить ресурсный профиль','R-CPU'),('A-REPL','Проверить задержку реплики','R-REPL'),('A-RELEASE','Подготовить учебную поставку','R-RELEASE'),('A-MEASURE','Измерить задержку учебного запроса','R-LATENCY')]:
        details={'description':'Цельное учебное задание: из проверенных исходников подготовить поставку. Входы: принятый scope и доступные исходники. Внутри Action выбрать достаточный состав, собрать и проверить комплект, записать состав и SHA. Результат: проверяемый учебный комплект и инструкция продолжения. Действительная публикация и установка вне этого задания; наличие архива не доказывает их выполнения.'} if i=='A-RELEASE' else {}
        add(i,'action',title,parent,'REQUIRES_ACTION',**details)
    core('shared-requirement','link',{'relation':{'id':'SHARED-SAFE','type':'INTRODUCES','from':'D-TEMP','to':'R-SAFE'}})
    for ident,parent,title,members,required,exclusive in [('G-STORE','R-STORE','Способ хранения',['D-SQL','D-FILE'],True,True),('G-CACHE','R-CACHE','Кеширование',['D-TEMP','D-NOCACHE'],True,True),('G-SCALE','R-SCALE','Способы масштабирования',['D-UP','D-OUT'],False,False)]:core('group-'+ident,'decision_group',{'group':{'id':ident,'title':title,'parentId':parent,'selectionRequired':required,'mutuallyExclusive':exclusive,'members':[{'id':ident+'-'+i,'decisionId':i} for i in members]}})
    for i,title,parent in [('CG-BASE','Предпосылки',None),('CG-LOAD','Нагрузка','CG-BASE'),('CG-PROOF','Подтверждения',None),('CG-TIME','Сроки',None),('CG-LIMITS','Ограничения',None),('CG-BUDGET','Бюджет','CG-LIMITS')]:core('context-group-'+i,'context_group',{'action':'save','id':i,'title':title,'parentId':parent})
    def day(n):return (datetime.fromisoformat(state['day']).date()+timedelta(days=n)).isoformat()
    for i,title,value,group in [('C-LOAD','Прогноз нагрузки','100 запросов/с','CG-LOAD'),('C-SERVER','Ресурс сервера','4 vCPU, 8 ГБ RAM; учебная конфигурация','CG-LOAD'),('C-LATENCY','Учебный замер задержки','p95 = 350 мс при требовании 150 мс','CG-PROOF'),('C-DDL','Учебный DDL','Ожидает записи учебного текста','CG-PROOF'),('C-DOC','Описание схемы','Таблица содержит идентификатор и текст заявки; учебное описание.','CG-PROOF'),('C-DEADLINE','Срок учебного выпуска',day(7),'CG-TIME'),('C-BUDGET','Бюджет','Учебное ограничение: один сервер в первом выпуске','CG-BUDGET'),('C-FRESH','Свежесть чтения','Допустимая задержка отчётов — до 5 секунд','CG-BASE')]:add(i,'context',title,value=value,contextGroupId=group,source='Учебный сценарий RDG',version='1')
    add('CAN-SQL','canon','Применимость табличного хранения','D-SQL','CANON_FOR',guidance='Проверить согласованность, реальные запросы и задержку. Учебный текст схемы и эксплуатационная пригодность — разные результаты.',canons='Уместно при связных данных и транзакциях; неудачно для произвольного потока файлов. При редких запросах польза зависит от цены сопровождения. Известная ошибка: принять учебный текст за доказательство пригодности — нужно проверить реальный запрос и нагрузку; пример схемы этого не доказывает. Плохой случай: не учитывать сопровождение.')
    add('CAN-REPL','canon','Применимость отдельной реплики','D-OUT','CANON_FOR',guidance='Проверить допустимую свежесть данных и цену сопровождения. Ссылка на теорию не является фактом процесса.')
    add('CAN-TASK','canon','Применимость цельного задания','A-RELEASE','CANON_FOR',guidance='Action может содержать целый способ выполнения без отдельного дерева R/D, если им достаточно управлять как одним заданием.',canons='Хорошо: входы, границы и проверяемый выход понятны. Плохо: внутри скрыт существенный выбор, которым нужно управлять отдельно. Известная ошибка: считать положение в Plan или наличие архива доказательством публикации и установки.')
    core('role-load','decision_context',{'nodeId':'D-SQL','sourceId':'C-LOAD','action':'save','comment':'Нагрузка нужна для оценки применимости способа хранения.'})
    for ident,subject,typ,title,why,sources in [('F-P','D-SQL','problem','Учебный запрос превышает 150 мс','В рассматриваемой учебной конфигурации подтверждено 350 мс; это текущее отклонение.',['C-LATENCY','R-LATENCY']),('F-R','D-NOCACHE','risk','Рост нагрузки может исчерпать ресурс','Возможен дефицит CPU при росте нагрузки; будущий сбой не подтверждён.',['C-LOAD','C-SERVER']),('F-U','D-OUT','decision_uncertainty','Читать свежие данные с primary или разгрузить его?','Оба пути жизнеспособны; последствия для задержки и нагрузки различаются.',['C-FRESH']),('F-O','D-SQL','improvement_opportunity','Генерировать учебный DDL из описания','Записанный вручную текст способен выполнить учебную цель, но генерация может упростить путь.',['C-DDL'])]:
        add(ident,'finding',title,subjectId=subject,findingType=typ,rationale=why,evidenceIds=[])
        for src in sources:core('dep-'+ident+'-'+src,'link',{'relation':{'id':'DEP-'+ident+'-'+src,'type':'DEPENDS_ON','from':src,'to':ident,'dependencyLevel':'L1'}})
    for ident,title,members in [('WG-DATA','Хранение и качество',['R-STORE','D-SQL','D-FILE','R-DDL','R-DOC','A-DDL','A-DOC','R-LATENCY','C-LOAD']),('WG-OPS','Ресурсы и выпуск',['R-CACHE','D-TEMP','D-NOCACHE','R-SCALE','D-UP','D-OUT','R-RELEASE','A-RELEASE','C-LOAD'])]:core('area-'+ident,'work_graph',{'workGraph':{'id':ident,'title':title,'rootIds':[members[0]],'memberIds':members}})
    core('estimate-measure','edit',{'nodeId':'A-MEASURE','changes':{'estimates':{'complexity':'Нужен доступ к учебному стенду','time':{'minSeconds':60,'maxSeconds':180},'basis':'Учебная оценка, не факт исполнения'}},'cosmetic':False})
    for qid,title,related,condition in [('Q-PEAK','Какова задержка в час пик?',['D-NOCACHE','F-R','F-U'],'Замер p95 на ожидаемой пиковой нагрузке'),('Q-BUDGET','Какой бюджет реально подтвердит пользователь?',['D-UP','D-OUT'],'Настоящий ответ пользователя с валютой и периодом')]:
        row=read()
        add(qid,'question',title,relatedRefs=[row['references'][i] for i in related],sourceRefs=[row['references']['C-LOAD']],impact='Ответ влияет на пригодность способа масштабирования',answerCondition=condition)
    row=read();core('answer-peak','question_answer',{'nodeId':'Q-PEAK','kind':'observation','text':next(n for n in row['graph']['objects'] if n['id']=='C-LATENCY')['value'],'sourceRefs':[row['references']['C-LATENCY']]})
    q=next(n for n in read()['graph']['objects'] if n['id']=='Q-PEAK')
    core('assess-peak','question_assess',{'nodeId':'Q-PEAK','answerIds':[q['answers'][0]['id']],'sufficient':False,'basis':'Учебный замер не подтверждает ожидаемую пиковую нагрузку'})
    core('hypothesis-peak','question_answer',{'nodeId':'Q-PEAK','kind':'hypothesis','text':'Возможно потребуется отдельный замер на большей нагрузке','sourceRefs':[]})
    if state['operations'].get('plan-create',{}).get('applyAttempted'):write('plan-create',state['operations']['plan-create']['request'])
    elif not read()['plan']:write('plan-create',client.call({'method':'schema','op':'plan_create','packageId':pid})['request'])
    if state['operations'].get('plan-content',{}).get('applyAttempted'):write('plan-content',state['operations']['plan-content']['request'])
    elif not state['operations'].get('plan-content',{}).get('result',{}).get('published'):
        req=client.call({'method':'schema','op':'plan_edit','packageId':pid})['request'];plan=req['plan'];g=read()['graph'];P=SourceFileLoader('example_plan_model',str(ROOT/'tools/rdg-portable-model.py')).load_module();ns={n['id']:n for n in g['nodes']+g['externalActions']};steps=[];times=[]
        def step(node,n,possible=False):
            sid='S-'+node;steps.append({'id':sid,'title':ns[node]['title'],'kind':ns[node]['kind'],'state':'possible' if possible else 'planned','ref':P.reference(pid,g,node)});times.extend([{'stepId':sid,'type':'notBefore','at':day(n),'strength':'soft','basis':'Учебная оценка времени'},{'stepId':sid,'type':'deadline','at':day(n+2),'strength':'soft','basis':'Учебная оценка времени'}]);return sid
        main=[step('R-CACHE',3),step('R-SAFE',3),step('R-LATENCY',4),step('A-RELEASE',5),step('R-RELEASE',6)]
        sql=[step(n,0,True) for n in ('A-DDL','A-DOC','A-MEASURE','R-DOC','R-DDL','R-STORE')];file=[step(n,1,True) for n in ('R-FILE','A-FILE')]
        up=[step(n,6,True) for n in ('R-CPU','A-CPU')];out=[step(n,7,True) for n in ('R-REPL','A-REPL')]
        plan.update(steps=steps,mainStepIds=main,timeConstraints=times,forks=[{'id':'FORK-STORE','title':'Способ хранения во времени','afterStepId':None,'startAt':day(0)+'T09:00:00+07:00','end':{'title':'Общие условия выпуска','at':day(3)},'cases':[{'id':'CASE-SQL','title':'SQL-таблица','decisionIds':['D-SQL'],'stepIds':sql},{'id':'CASE-FILE','title':'Файловый прототип','decisionIds':['D-FILE'],'stepIds':file}]},{'id':'FORK-SCALE','title':'Возможный рост после выпуска','afterStepId':main[-1],'startAt':day(6)+'T15:00:00+07:00','cases':[{'id':'CASE-UP','title':'Один более мощный сервер','decisionIds':['D-UP'],'stepIds':up},{'id':'CASE-OUT','title':'Отдельная реплика','decisionIds':['D-OUT'],'stepIds':out}]}]);write('plan-content',req)
    def review(key):
        if state.setdefault('reviews',{}).get(key):return
        if state['operations'].get(key,{}).get('applyAttempted'):write(key,state['operations'][key]['request'])
        else:
            row=read();nodes=[n for n in row['graph']['nodes']+row['graph']['objects']+row['graph']['externalActions'] if n.get('review',{}).get('required')]
            if nodes:
                req=client.call({'method':'schema','op':'core','packageId':pid,'nodeId':nodes[0]['id'],'command':'review'})['request']
                # Union the exact schema-built observations at one unchanged owner revision.
                observed=dict(req['data']['observed'])
                for n in nodes[1:]:
                    part=client.call({'method':'schema','op':'core','packageId':pid,'nodeId':n['id'],'command':'review'})['request']
                    if part['expectedGraphRevision']!=req['expectedGraphRevision'] or part['expectedPackageRevision']!=req['expectedPackageRevision']:raise RuntimeError('EXAMPLE_CHANGED_DURING_REVIEW')
                    observed.update(part['data']['observed'])
                req['data'].update(nodeIds=[n['id'] for n in nodes],observed=observed,basis='Проверены текущие учебные входы');req['note']=req['data']['basis'];write(key,req)
        state['reviews'][key]=True;save()
    def complete(key,node,proof):
        review('review-'+key);core(key,'complete',{'nodeId':node,'basis':'Учебный результат подтверждён записанными данными Context','evidenceIds':[proof]})
    review('review-sql');core('select-sql','select',{'nodeId':'D-SQL'})
    core('write-ddl','edit',{'nodeId':'C-DDL','changes':{'value':'CREATE TABLE requests (id INTEGER PRIMARY KEY, body TEXT); — учебный текст записан в Context.'},'cosmetic':False})
    complete('complete-ddl-action','A-DDL','C-DDL');complete('complete-doc-action','A-DOC','C-DOC');complete('complete-measure','A-MEASURE','C-LATENCY');complete('complete-doc-requirement','R-DOC','C-DOC');complete('complete-schema-requirement','R-DDL','C-DDL');complete('complete-sql-decision','D-SQL','C-DDL');complete('complete-storage-requirement','R-STORE','C-DDL')
    review('review-cache');core('select-temp-cache','select',{'nodeId':'D-TEMP'});core('withdraw-temp-cache','withdraw',{'nodeId':'D-TEMP'});review('review-no-cache');core('select-no-cache','select',{'nodeId':'D-NOCACHE'})
    review('review-before-final-changes');core('rename-cosmetic','edit',{'nodeId':'C-LOAD','changes':{'title':'Нагрузка запросов'},'cosmetic':True});core('rename-semantic','edit',{'nodeId':'D-NOCACHE','changes':{'title':'Продолжить без кеша с лимитом нагрузки'},'cosmetic':False});core('raise-load','edit',{'nodeId':'C-LOAD','changes':{'value':'1000 запросов/с'},'cosmetic':False})
    if not read().get('capabilities',{}).get('capabilities',{}).get('recommendationAuthoring'):raise ValueError('INSTALL_RECOMMENDATION_RUNTIME_FIRST')
    lens=next((p for p in client.call({'method':'catalog'})['packages'] if p.get('role')=='lens' and p.get('lensKey')=='work' and p.get('coreModel')=='rdg-decision-v1'),None)
    if lens is None:raise ValueError('EXAMPLE_REQUIRES_EXISTING_DECISION_WORK_LENS')
    for index,(target,usage) in enumerate([('D-SQL','Перечитать методику перед пересмотром решения; сохранить только полезные результаты работы.'),('Q-PEAK','Уточнить следующий шаг исследования. Методика не требует копирования её графа.')]):
        key='recommendation-'+str(index)
        if state['operations'].get(key,{}).get('applyAttempted'):write(key,state['operations'][key]['request']);continue
        current=read();reg=client.call({'method':'recommendation_catalog','limit':1});definition={'id':str(uuid.uuid5(uuid.UUID(pid),key)),'revision':1,'key':key+'-'+pid,'title':'Учебная рекомендация методики','supplied':False,'authored':True,'rules':[{'id':'advice','nodeKinds':['decision' if target=='D-SQL' else 'question'],'scope':'identity','anchor':{'packageId':pid,'identitySpace':current['graph']['identitySpace'],'nodeId':target},'state':'any','whenText':'При уточнении учебного решения или его оснований','usageText':usage,'lensRefs':[{k:lens[k] for k in ('packageId','identitySpace','lensKey')}]}]}
        write(key,{'op':'recommendation_edit','transactionId':str(uuid.uuid4()),'expectedRegistryRevision':reg['registryRevision'],'action':'create','definition':definition,'attachTo':{'packageId':pid,'expectedPackageRevision':current['package']['revision'],'expectedGraphRevision':current['graph']['revision']},'note':'Явный учебный совет; не глобальная раздача линз'})
    for index,title in enumerate(['Уточнить достаточность ответа о пиковом потоке','Пересмотреть решение по методике Work']):
        key='planning-meta-action-'+str(index)
        if state['operations'].get(key,{}).get('applyAttempted'):write(key,state['operations'][key]['request']);continue
        current=read();lensrow=client.call({'method':'read','packageId':lens['packageId']})
        refs=[current['references']['Q-PEAK' if index==0 else 'D-SQL']]
        if index==1:refs.append({**lensrow['scopeReferences']['process'],'kind':'lens'})
        req=client.call({'method':'schema','op':'plan_action','packageId':pid})['request'];req.update(note='Явное учебное планирование; предметы работы не изменяются',entity={'kind':'action','actionType':'task','lowLevel':False,'title':title,'description':'Учебная будущая работа над самим процессом','resultCondition':'Получены полезные результаты; сохраняемая часть выбрана по критериям','subjectRefs':refs,'estimates':{'time':{'minSeconds':60,'maxSeconds':600},'basis':'Учебная оценка, не подтверждение исполнения'}},placement={'afterStepId':current['plan']['mainStepIds'][-1] if current['plan']['mainStepIds'] else None})
        write(key,req)
    row=read();g=row['graph'];ns={n['id']:n for n in g['nodes']+g['objects']};hist=client.call({'method':'history','packageId':pid})
    assert ns['D-SQL']['selectionState']=='selected' and ns['D-SQL']['result']['state']=='confirmed'
    assert ns['D-TEMP']['selectionState']=='unselected' and ns['D-NOCACHE']['selectionState']=='selected'
    assert all(n['kind']!='evidence' for n in g['objects']) and all(e['type'] not in ('FINDING_RESPONSE','FINDING_PROPOSAL') for e in g['edges'])
    assert ns['F-R']['review']['required'] and all(ns[i]['disposition']['code']=='unresolved' for i in ('F-P','F-R','F-U','F-O'))
    assert len(g['nodes'])>=25 and len(row['plan']['forks'])==2
    assert ns['Q-PEAK']['assessmentReviewRequired'] and not ns['Q-BUDGET']['answers'] and ns['A-MEASURE']['estimates']['time']['maxSeconds']==180
    assert all(n['id']!='A-ANALYSIS' for n in g['nodes']) and row['plan']['forks'][0]['afterStepId'] is None
    assert row['plan']['forks'][0]['end']['title']=='Общие условия выпуска' and len(row['plan']['mainStepIds'])==len(set(row['plan']['mainStepIds']))
    assert 'Известная ошибка:' in ns['CAN-SQL']['canons'] and not ns['CAN-SQL'].get('knownErrors') and ns['CAN-REPL']['guidance']
    assert len([a for a in g['externalActions'] if 'subjectRefs' in a])==2
    reader=SourceFileLoader('rdg_example_scoped',str(ROOT/'tools/rdg-scoped-read.py')).load_module()
    for root in ('D-SQL','R-STORE','R-SAFE','R1'):
        focused=reader.read_pages(client,{'method':'read','packageId':pid,'detail':'focus','nodeId':root,'limit':100},True)
        assert focused['reading']['pagesComplete'] and focused['data']['entities']['items'][0]['entity']['id']==root
        if root=='D-SQL':
            ids={r['entity']['id'] for r in focused['data']['entities']['items']}
            assert 'D-FILE' not in ids and 'R-DOC' not in ids
            assert 'C-LOAD' in ids and 'CAN-SQL' in ids
            group=next(g for g in focused['data']['decisionGroups']['items'] if g['id']=='G-STORE')
            assert not group['membersComplete'] and group['originalMemberCount']==2
            assert [m['decisionId'] for m in group['members']]==['D-SQL']
    branch=reader.read_pages(client,{'method':'read','packageId':pid,'detail':'branch','nodeId':'R-STORE','limit':100},True)
    assert {'R-STORE','D-SQL','D-FILE','R-DDL'} <= {r['nodeId'] for r in branch['data']['outline']['items']}
    state['verified']={'nodeCount':len(g['nodes']),'contexts':sum(n['kind']=='context' for n in g['objects']),'findings':4,'questions':2,'actionEstimates':1,'theorySections':2,'actionTheories':1,'authoredRecommendations':2,'planningMetaActions':2,'focusReadCases':4,'branchReadCases':1,'forks':2,'placements':len(row['plan']['steps']),'historyLevels':sorted({r['historyView']['level'] for r in hist['events']})};save();progress('EXAMPLE_READY '+json.dumps({'packageId':pid,'title':TITLE,'path':path,**state['verified']},ensure_ascii=False));return state

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--context',type=Path,required=True);parser.add_argument('--journal',type=Path,required=True);parser.add_argument('--path',default=PATH);parser.add_argument('--expected-source')
    args=parser.parse_args()
    if args.expected_source:
        ci=SourceFileLoader('example_source_check',str(ROOT/'tools/rdg-ci.py')).load_module()
        if ci.fingerprint()!=args.expected_source:raise SystemExit('Repo differs from the checked build; use the matching example command.')
    C=SourceFileLoader('example_remote_client',str(ROOT/'tools/rdg-remote-client.py')).load_module();run(C.Client(json.loads(args.context.read_text())),args.journal,args.path)
