/* Local manual workflow controller. Same Graph/Plan writers, no optimistic facts. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else{
    root.RDGWorkflowUI=api;
    const host=document.getElementById('rdg-viewer-root');
    if(host&&root.RDG_LOCAL_WORKFLOW){
      // The Viewer defers catalog initialization in a loopback Helper page.
      // The standalone controller is responsible for bootstrapping it once.
      // Otherwise folder/root selection stays unavailable despite a healthy
      // authenticated snapshot and a running Gendocen engine.
      if(typeof host.rdgStart==='function')void host.rdgStart();
      const base=new URL('./',location.href),session=root.RDG_SESSION;
      const request=async(path,body)=>{
        const response=await fetch(new URL(path,base),{method:body?'POST':'GET',credentials:'omit',
          redirect:'error',headers:{'X-RDG-Session':session,...(body?{'Content-Type':'application/json'}:{})},
          ...(body?{body:JSON.stringify(body)}:{})});
        const result=await response.json();
        if(!response.ok){const error=Error(result.error||'Запрос отклонён');error.definite=result.definite!==false;throw error;}
        return result;
      };
      root.RDG_LOCAL_DEPENDENCIES=body=>request('dependencies',body);
      const ui=api.mount(host.rdgWorkflow.attach(),{read:()=>request('state'),write:r=>request('command',r),admin:r=>request('admin',r)},
        {document,graphContainer:host.rdgWorkflow.graphEditor(),onGraph:(g,v)=>host.rdgWorkflow.loadGraph(g,v),onNavigate:(ref,v)=>host.rdgWorkflow.openDeclaration(ref,v)});
      root.RDG_LOCAL_EDITOR=ui;void ui.refresh();
    }
  }
})(globalThis,function(){
  'use strict';
  function fileTransport(directory,options={}){
    const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
    let report=options.onStatus||(()=>{});
    const readJson=async name=>JSON.parse(await (await directory.getFileHandle(name)).getFile().then(f=>f.text()));
    const writeJson=async(name,value)=>{
      const file=await directory.getFileHandle(name,{create:true}),writer=await file.createWritable();
      await writer.write(JSON.stringify(value));await writer.close();
    };
    const checkDescriptor=async()=>{
      let descriptor;
      try{descriptor=await readJson('session.json');}
      catch(e){
        if(e.name==='NotFoundError')throw Error('В этой папке нет session.json. Выберите папку session, созданную локальным Helper.');
        throw e;
      }
      if(!descriptor||descriptor.schemaVersion!==1||descriptor.kind!=='rdg-local-manual-session')
        throw Error('Это не папка сессии RDG. Выберите папку session, созданную локальным Helper.');
      if(descriptor.active===false)throw Error('Сессия Helper завершена. Запустите новую сессию и подключите её папку.');
      if(descriptor.active!==true||typeof descriptor.session!=='string'||!descriptor.session)
        throw Error('Файл session.json повреждён или неполон. Запустите новую сессию Helper и подключите её папку.');
      return descriptor;
    };
    async function exchange(kind,body){
      let queued=false;
      try{
        report('Проверяю папку сессии…');
        const descriptor=await checkDescriptor();
        const random=randomId();
        const id='io-'+random,request='request-'+id+'.json',ready='request-'+id+'.ready',response='response-'+id+'.json';
        report('Записываю запрос в папку сессии… Если браузер просит доступ к записи, подтвердите его для выбранной папки session.');
        await writeJson(request,{session:descriptor.session,kind,body});
        // A failed close of the ready marker may still have queued the request.
        queued=true;await writeJson(ready,{ready:true});
        const started=Date.now(),timeout=options.timeoutMs??(kind==='state'?10000:45000);
        let checked=started,shown=-1;
        while(Date.now()-started<timeout){
          let result;
          try{result=await readJson(response);}
          catch(e){if(e.name!=='NotFoundError')throw e;}
          if(result){
            for(const name of [ready,request,response]){
              try{await directory.removeEntry(name);}catch{/* cleanup never changes accepted outcome */}
            }
            if(!result.ok){const error=Error(result.error||'Запрос отклонён');error.definite=result.definite!==false;throw error;}
            return result.result;
          }
          const seconds=Math.floor((Date.now()-started)/1000);
          if(seconds!==shown){shown=seconds;report('Ожидаю ответ локального Helper… '+seconds+' с.');}
          if(Date.now()-checked>=1000){
            const current=await checkDescriptor();checked=Date.now();
            if(current.session!==descriptor.session)throw Error('В папке уже другая сессия Helper. Подключите папку заново.');
          }
          await pause(options.pollMs??150);
        }
        throw Error(kind==='state'?
          'Helper не ответил за '+Math.round(timeout/1000)+' с. Проверьте, что он запущен и выбрана его папка session. Затем нажмите «Обновить» или подключите новую папку.':
          'Helper не ответил. Исход записи неизвестен. Проверьте Helper, обновите данные и повторите тот же запрос.');
      }catch(e){
        if(e.name==='NotAllowedError'||e.name==='SecurityError'){
          const error=Error('Нет доступа к папке сессии. Подключите её заново и разрешите чтение и запись.');
          error.definite=!queued||kind==='state';throw error;
        }
        if(!queued||kind==='state')e.definite=true;
        throw e;
      }
    }
    return {describe:checkDescriptor,read:contextId=>exchange('state',contextId==null?null:{contextId}),
      write:body=>exchange('command',body),admin:body=>exchange('admin',body),
      dependencies:body=>exchange('dependencies',body),
      setStatus:callback=>{report=callback;}};
  }
  // Internal educational view only. Real working graphs require a saved
  // Plan owner; do not expose a generated empty Plan as if it were persisted.
  function localPlanPreview(entry,graphs,{exampleOnly=false}={}){
    if(!entry||!entry.slug||!entry.file||!graphs||!graphs[entry.file])
      throw Error('LOCAL_PLAN_WORKSPACE_REQUIRED');
    const root=graphs[entry.file],identitySpace=root.identitySpace||'legacy-'+entry.slug;
    const educational=exampleOnly||!!root.readOnly||!!root.exampleOnly;
    const sanitized={};for(const [file,g] of Object.entries(graphs)){
      if(g&&Array.isArray(g.nodes)&&Array.isArray(g.edges)&&Array.isArray(g.events)&&
         (file===entry.file||g.identitySpace&&g.identitySpace===root.identitySpace))
        sanitized[file]={...g,identitySpace};
    }
    // Published read-only examples may already carry an explicit authored
    // workflow snapshot. Reuse it instead of erasing historical/future cards.
    if(educational&&root.workflowExample){
      const authored=JSON.parse(JSON.stringify(root.workflowExample));
      if(authored.graphFile===entry.file&&authored.sources?.plan&&
         Array.isArray(authored.history)&&Array.isArray(authored.future)){
        // An educational timeline is not permission to fabricate placements.
        // Every referenced step must resolve to an existing owned Graph node.
        const steps=authored.sources.plan.steps;
        if(!Array.isArray(steps)||!steps.every(step=>{
          const ref=step.actionRef||step.requirementRef;
          const owner=ref&&sanitized[ref.graphFile];
          const node=owner?.nodes?.find(n=>n.id===ref.nodeId);
          return !ref||!!(node&&owner.identitySpace===ref.identitySpace&&
              node.kind===step.kind&&step.kind=== (step.actionRef?'action':'requirement'));
        })||!authored.future.every(row=>{
          const step=steps.find(step=>step.id===row.stepId),ref=row.graphRef;
          const owner=ref&&sanitized[ref.graphFile];
          const node=owner?.nodes?.find(n=>n.id===ref.nodeId);
          const original=step&&(step.actionRef||step.requirementRef);
          return !!(step&&node&&owner.identitySpace===ref.identitySpace&&
            node.kind===step.kind&&row.kind===step.kind&&row.nodeId===ref.nodeId&&
            original?.graphFile===ref.graphFile&&original.identitySpace===ref.identitySpace&&
            original.nodeId===ref.nodeId&&
            (node.kind!=='action'||node.status==='selected'));
        }))throw Error('EDUCATIONAL_PLAN_REFERENCES_MUST_EXIST_IN_GRAPH');
        for(const g of Object.values(sanitized))delete g.workflowExample;
        return {...authored,localPreview:false,examplePreview:true,authoredExamplePreview:true,
          planFile:null,permissions:[],grantAdminAvailable:false,
          planProvenance:{mode:'embedded-read-only-example',persisted:false},
          sources:{...authored.sources,graphs:sanitized}};
      }
    }
    const history=[];
    const types={module_event:'module_event',modules_configured:'modules_configured',
      graph_changed:'graph_saved',action_executed:'action_executed',
      requirement_achieved:'requirement_achieved',action_withdrawn:'action_withdrawn',
      action_reconsidered:'action_reconsidered',action_selected:'action_selected',
      requirement_reformulated:'requirement_reformulated'};
    for(const [file,g] of Object.entries(sanitized))for(const [index,event] of g.events.entries()){
      if(!types[event.type])continue;
      const id=event.targetId||event.actionId||event.requirementId||null;
      const node=g.nodes.find(n=>n.id===id)||null;
      const savedSelection=node?.selectionBasis?.actionSnapshot;
      const snapshot=event.viewSnapshot||event.priorActionSnapshot||
        event.previousRequirementSnapshot||savedSelection||null;
      history.push({id:file+'::'+(event.id||index),graphFile:file,
        kind:types[event.type],sourceEventType:event.type,targetId:id,
        title:node?.title||snapshot?.title||null,
        nodeSnapshot:snapshot,materialSnapshotAvailable:!!snapshot,
        recordedAt:event.recordedAt||null,note:event.note||null,
        previousRequirementSnapshot:event.previousRequirementSnapshot||null,
        newRequirementSnapshot:event.newRequirementSnapshot||null,
        transition:event.type==='action_reconsidered'?event.transition:null,
        reviewActionId:event.reviewActionId||null,
        summary:event.label||event.note||null,by:event.by||null});
    }
    // Known timestamps are sorted; unknown timestamps remain visibly unknown.
    history.sort((a,b)=>String(a.recordedAt||'').localeCompare(String(b.recordedAt||''))||a.id.localeCompare(b.id));
    const plan={schemaVersion:1,kind:'temporalPlan',id:entry.slug,title:'План · '+(entry.title||root.title||entry.slug),
      identitySpace,revision:1,status:'candidate',steps:[],sequence:[],branches:[],timeConstraints:[]};
    return {schemaVersion:1,title:plan.title,planFile:null,graphFile:entry.file,
      planId:plan.id,planProvenance:{mode:educational?'educational-example-no-owner':'internal-unpersisted-view',persisted:false},
      coverage:'events visible in available Graph files; writer journal not independently loaded',
      localPreview:!educational,examplePreview:educational,authoredExamplePreview:false,
      permissions:[],history,future:[],unresolved:[],
      sources:{plan,graphs:sanitized,completion:{}},excludedPlacements:[]};
  }
  function localPlanFromOwner(entry,graphs,store){
    // View the *real persisted owner*. Never synthesize an empty Plan for a
    // missing file. Cryptographic journal validation is delegated to Helper.
    const expected='plans/'+entry.slug+'/plan.json';
    const root=graphs?.[entry.file];
    const space=root?.identitySpace||'legacy-'+entry.slug;
    if(!root||!store||store.kind!=='temporalPlanOwner'||store.schemaVersion!==1||
       store.owner?.sourcePath!==expected||store.owner?.planId!==entry.slug||
       store.owner?.identitySpace!==space||!Number.isInteger(store.revision)||
       store.revision<1||!Array.isArray(store.versions)||store.versions.length!==store.revision)
      throw Error('PLAN_OWNER_NOT_MATCHING_GRAPH');
    const last=store.versions[store.versions.length-1];
    const plan=last?.plan;
    if(last.revision!==store.revision||plan?.id!==entry.slug||plan?.identitySpace!==space||
       plan?.revision!==store.revision||!Array.isArray(plan.steps)||
       !Array.isArray(plan.sequence)||!Array.isArray(plan.timeConstraints)||!Array.isArray(plan.branches))
      throw Error('PLAN_OWNER_RECORD_INVALID');
    const base=localPlanPreview(entry,graphs);
    if(base.examplePreview)throw Error('PLAN_EXAMPLE_CANNOT_OVERRIDE_AUTHORED_SNAPSHOT');
    const covered=new Set(plan.timeConstraints.map(x=>x.stepId));
    for(const edge of plan.sequence){covered.add(edge.before);covered.add(edge.after);}
    const future=[];const unresolved=[];
    for(const step of plan.steps){
      if(!['action','requirement'].includes(step.kind)||!covered.has(step.id))continue;
      const ref=step.actionRef||step.requirementRef,own=ref&&base.sources.graphs[ref.graphFile];
      const node=own?.nodes?.find(n=>n.id===ref.nodeId);
      if(!node||own.identitySpace!==ref.identitySpace||node.kind!==step.kind){
        unresolved.push({nodeId:ref?.nodeId||step.id,reason:'owner not verified without Helper'});continue;
      }
      future.push({stepId:step.id,kind:step.kind,graphRef:ref,nodeId:ref.nodeId,
        title:node.title,plannedTitle:step.title,state:step.state,
        timeConstraints:plan.timeConstraints.filter(x=>x.stepId===step.id),
        sequence:plan.sequence.filter(x=>x.before===step.id||x.after===step.id)});
    }
    // File-only mode may read the real Plan owner versions. Show recorded
    // placement changes, not fabricated executions. Helper remains the
    // independent authority for Graph writer journals and completion.
    const placementHistory=[];let prior=new Map(),priorPosition=new Map();
    for(const version of store.versions){
      const current=new Map(version.plan.steps.map(step=>[step.id,step]));
      const positions=new Map([...current.keys()].map(id=>[id,{
        timeConstraints:version.plan.timeConstraints.filter(t=>t.stepId===id),
        sequence:version.plan.sequence.filter(e=>id===e.before||id===e.after)}]));
      for(const [id,step] of current){
        if(JSON.stringify(prior.get(id))===JSON.stringify(step)&&
           JSON.stringify(priorPosition.get(id))===JSON.stringify(positions.get(id)))continue;
        const ref=step.actionRef||step.requirementRef;if(!ref)continue;
        placementHistory.push({id:expected+'::plan-r'+version.revision+'::'+id,
          kind:'plan_placement_saved',graphFile:ref.graphFile,targetId:ref.nodeId,
          title:step.title,recordedAt:version.recordedAt,planRevision:version.revision,
          summary:'Сохранено размещение '+step.kind+' '+ref.nodeId+' в Plan owner',
          transactionId:version.transactionId,
          previousPlacementSnapshot:priorPosition.get(id)||null,
          newPlacementSnapshot:positions.get(id)||null,materialSnapshotAvailable:false});
      }
      for(const [id,step] of prior){
        if(current.has(id))continue;
        const ref=step.actionRef||step.requirementRef;if(!ref)continue;
        placementHistory.push({id:expected+'::plan-r'+version.revision+'::'+id,
          kind:'plan_placement_removed',graphFile:ref.graphFile,targetId:ref.nodeId,
          title:step.title,recordedAt:version.recordedAt,planRevision:version.revision,
          summary:'Удалено размещение '+step.kind+' '+ref.nodeId+' из Plan owner',
          transactionId:version.transactionId,materialSnapshotAvailable:false});
      }
      if(version.revision===1)placementHistory.push({id:expected+'::created',
        kind:'plan_created',recordedAt:version.recordedAt,planRevision:1,
        summary:'Создан настоящий Plan owner '+plan.id,
        transactionId:version.transactionId,materialSnapshotAvailable:false});
      prior=current;priorPosition=positions;
    }
    return {...base,localPreview:false,storedPlanReadOnly:true,title:plan.title,planFile:expected,
      planId:plan.id,planProvenance:{mode:'local-plan-file',persisted:true,
        revision:store.revision,journalVerified:false},
      history:[...base.history,...placementHistory].sort((a,b)=>String(a.recordedAt||'').localeCompare(String(b.recordedAt||''))||a.id.localeCompare(b.id)),
      sources:{...base.sources,plan},future,unresolved,
      coverage:'Saved Plan owner file; full graph journal and completion require Helper'};
  }
  // Independent dimensions: Graph completion, Plan placement, Graph branch
  // applicability. Never infer an execution from a date, selection or absence
  // of entries in the historical UI; completion is only from owner evidence.
  function historyKind(kind){
    if(['module_event','module_plan_changed','modules_configured'].includes(kind))
      return {group:'module',label:'МОДУЛЬ',description:'Изменение модуля — не факт выполнения'};
    if(['plan_created','plan_placement_saved','plan_placement_removed'].includes(kind))
      return {group:'plan',label:'ПЛАН',description:'Версия Plan owner — размещение, не выполнение Action'};
    if(['action_executed','requirement_achieved'].includes(kind))
      return {group:'result',label:'РЕЗУЛЬТАТ',description:'Подтверждённый результат / запись выполнения'};
    if(['requirement_falsified','action_reopened','core_requirement_necessity_changed','core_review_confirmed'].includes(kind))
      return {group:'state',label:'АКТУАЛЬНОСТЬ',description:'Проверка, потеря истинности или повторное открытие'};
    if(typeof kind==='string'&&kind.startsWith('core_'))return {group:'change',label:'ИЗМЕНЕНИЕ ГРАФА',description:'Принятое изменение уточнённой модели'};
    if(['requirement_activated','requirement_deactivated','action_withdrawn',
        'action_reconsidered'].includes(kind))
      return {group:'state',label:'СОСТОЯНИЕ',description:'Изменение актуальности или отзыв'};
    if(['action_selected','decision_selected','decision_revised'].includes(kind))
      return {group:'choice',label:'ВЫБОР',description:'Выбор способа или решения — не выполнение'};
    if(['graph_saved','graph_changed','requirement_reformulated','requirement_reparented','context_discovered',
        'action_requirement_linked'].includes(kind))
      return {group:'change',label:'ИЗМЕНЕНИЕ ГРАФА',description:'Изменено определение работы или контекст'};
    return {group:'other',label:'ДРУГОЕ СОБЫТИЕ',description:'Неуточнённый тип события'};
  }
  function planningInventory(view){
    const graphSet=view?.sources?.graphs||{},states=view?.sources?.completion||{};
    const plan=view?.sources?.plan||{},steps=Array.isArray(plan.steps)?plan.steps:[];
    const placeIds=new Set((plan.timeConstraints||[]).map(x=>x.stepId));
    for(const edge of plan.sequence||[]){placeIds.add(edge.before);placeIds.add(edge.after);}
    const placed=new Set();
    for(const row of view.future||[]){
      const ref=row.graphRef;
      if(ref)placed.add([ref.graphFile,ref.identitySpace,ref.nodeId].join('|'));
    }
    for(const step of steps){
      if(!placeIds.has(step.id))continue;
      const ref=step.actionRef||step.requirementRef;
      if(ref)placed.add([ref.graphFile,ref.identitySpace,ref.nodeId].join('|'));
    }
    const result={unplaced:[],placedCount:0,completedCount:0,needsVerification:[],excludedCount:0};
    for(const [file,g] of Object.entries(graphSet)){
      if(!g||!Array.isArray(g.nodes))continue;
      for(const n of g.nodes){
        if(!['requirement','action'].includes(n.kind)||n.projectionOf){continue;}
        const key=[file,g.identitySpace,n.id].join('|'),state=states[file]?.[n.id];
        const inactive=n.active===false||['inactive','superseded','rejected'].includes(n.status);
        const preliminary=['candidate','potential'].includes(n.status);
        if(inactive||preliminary||n.kind==='action'&&n.status!=='selected'||
            state?.reason==='potential-inactive-or-unavailable-owner'){
          result.excludedCount++;continue;
        }
        const current=state?.currentScopeComplete===true;
        if(state?.reviewRequired){result.needsVerification.push({graphFile:file,nodeId:n.id,kind:n.kind,title:n.title,reason:'dependency-review-required'});continue;}
        // An Action execution is immutable history even after the definition
        // changes. A Requirement is achieved only in its current scope.
        if(state?.historyPending){
          result.needsVerification.push({graphFile:file,nodeId:n.id,kind:n.kind,title:n.title,
            reason:state.reason||'history-record-not-confirmed'});continue;
        }
        const finished=n.kind==='action'?state?.complete===true&&!!state?.eventId:
          current&&!!state?.eventId;
        if(finished){result.completedCount++;continue;}
        if(state?.complete===true||current&&!state?.eventId){
          result.needsVerification.push({graphFile:file,nodeId:n.id,kind:n.kind,title:n.title,
            reason:state.reason||'history-record-not-confirmed'});continue;
        }
        if(placed.has(key)){result.placedCount++;continue;}
        result.unplaced.push({graphFile:file,identitySpace:g.identitySpace,
          nodeId:n.id,kind:n.kind,title:n.title,
          verification:state?'not-complete-in-current-authorized-view':'completion-not-verified'});
      }
    }
    return result;
  }
  function declarationFor(view,reference){
    const graphs=view?.sources?.graphs||{};
    let ref={...reference},node,graph,kind=null;const seen=new Set();
    for(;;){
      const key=[ref.graphFile,ref.identitySpace,ref.nodeId].join('|');
      if(seen.has(key))throw Error('Цикл ссылок на объявление узла');seen.add(key);
      graph=graphs[ref.graphFile];node=graph?.nodes.find(n=>n.id===ref.nodeId);
      if(!graph||graph.identitySpace!==ref.identitySpace||!node)throw Error('Граф объявления недоступен в подключённой сессии');
      if(kind&&node.kind!==kind)throw Error('Тип узла владельца не совпадает с проекцией');kind=node.kind;
      if(!node.projectionOf)break;
      const owner=view.sources.completion?.[ref.graphFile]?.[ref.nodeId]?.ownerRef;
      if(!owner||owner.identitySpace!==ref.identitySpace)throw Error('Владелец проекции не подтверждён; переход к личному графу не выполняется');
      ref={...owner};
    }
    const root=graph.rootRequirementId||graph.nodes.find(n=>n.kind==='requirement')?.id;
    let contextRootId=root;
    if(node.kind==='requirement'&&node.id!==root){
      // A historical Requirement may only have archived introduction edges.
      // Resolve its *existing* owner and fall back to the owner graph when
      // historic hierarchy is no longer part of the active composition.
      const candidates=graph.edges.filter(e=>e.type==='INTRODUCES'&&e.to===node.id);
      const introductions=candidates.some(e=>!e.archived)?candidates.filter(e=>!e.archived):candidates;
      const contexts=introductions.flatMap(e=>e.parent?[e.parent]:graph.edges.filter(d=>
        ['DRIVES','OPTION_FOR'].includes(d.type)&&d.to===e.from).map(d=>d.from));
      contextRootId=contexts.find(id=>graph.nodes.some(n=>n.id===id&&n.kind==='requirement'))||root;
    }else if(node.kind==='action'){
      contextRootId=graph.edges.find(e=>['DRIVES','OPTION_FOR'].includes(e.type)&&e.to===node.id&&!e.archived)?.from||
        graph.edges.find(e=>['DRIVES','OPTION_FOR'].includes(e.type)&&e.to===node.id)?.from||root;
    }
    if(!contextRootId||!graph.nodes.some(n=>n.id===contextRootId&&n.kind==='requirement'))
      throw Error('В исходном графе нет доступной корневой Requirement');
    return {ref,graph,node,contextRootId};
  }
  function randomId(){return typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);}
  // A read guard for local snapshots. The authoritative mutation validator remains Python.
  function validateCoreSnapshot(g){
    const fail=message=>{throw Error('CORE_SNAPSHOT: '+message);};
    if(g?.coreModel!=='rdg-core-v1'||g.actionModel!=='candidate-v6'||g.schemaVersion!==1)fail('неподдерживаемый профиль');
    for(const k of ['nodes','objects','edges','events','workGraphs'])if(!Array.isArray(g[k]))fail('нет массива '+k);
    const ids=new Set(),kinds=new Map();
    for(const [values,allowed] of [[g.nodes,['requirement','action']],[g.objects,['context','canon','info','evidence']]])for(const n of values){
      if(!n||typeof n.id!=='string'||!n.id||ids.has(n.id)||typeof n.title!=='string'||!n.title.trim()||!allowed.includes(n.kind)||!Number.isInteger(n.revision)||n.revision<1)fail('некорректный блок');
      ids.add(n.id);kinds.set(n.id,n.kind);
    }
    if(kinds.get(g.rootRequirementId)!=='requirement')fail('нет корневой R');
    const relations=new Set(['DRIVES','RELATES_R','DERIVES','INTRODUCES','CONTEXT_FOR','DEPENDS_ON','CANON_FOR','INFO_FOR','EVIDENCE_FOR']),edges=new Set();
    for(const e of g.edges){
      if(!e||!e.id||edges.has(e.id)||!ids.has(e.from)||!ids.has(e.to)||!relations.has(e.type))fail('некорректная связь');edges.add(e.id);
      if(e.origin!==undefined){
        const o=e.origin;
        if(e.type!=='INTRODUCES'||!o||typeof o!=='object'||Array.isArray(o))fail('происхождение выхода');
        if(o.role==='method_correctness'){if(Object.keys(o).length!==1)fail('поля корректности способа');}
        else if(o.role!=='subgoal'||Object.keys(o).sort().join(',')!=='requirementIds,role'||!Array.isArray(o.requirementIds)||!o.requirementIds.length||new Set(o.requirementIds).size!==o.requirementIds.length||o.requirementIds.some(i=>kinds.get(i)!=='requirement'))fail('исходные цели выхода');
      }
    }
    // Import is read-only, but status labels must not accept invented completion/selection events.
    const eventById=new Map();
    for(const e of g.events){
      if(!e||typeof e.id!=='string'||!e.id.trim()||eventById.has(e.id)||
          typeof e.type!=='string'||!e.type.trim()||!['assistant','user'].includes(e.by)||
          typeof e.note!=='string'||!e.note.trim())fail('некорректное событие');
      eventById.set(e.id,e);
    }
    for(const n of [...g.nodes,...g.objects]){
      if(n.kind==='requirement'&&(!['active','potential','inactive'].includes(n.status)||
          typeof n.description!=='string'||!n.description.trim()||
          typeof n.scope!=='string'||!n.scope.trim()))fail('некорректная R');
      if(n.kind==='action'&&!['candidate','selected','rejected','superseded'].includes(n.status))fail('некорректный статус A');
      if(['requirement','action'].includes(n.kind)){
        const r=n.result;
        if(!r||!['open','confirmed'].includes(r.state)||!['true','false','unknown'].includes(r.truth)||
            (r.state==='confirmed')!==(r.truth==='true')||
            (n.kind==='action'&&r.truth==='false'))fail('противоречивый результат');
        if(r.state==='confirmed'){
          const e=eventById.get(r.eventId);
          if(!e||e.type!==(n.kind==='action'?'action_executed':'requirement_achieved')||
              e.targetId!==n.id||!Array.isArray(e.evidenceRefs)||!e.evidenceRefs.length)
            fail('результат без события и доказательств');
        }
        if(n.kind==='requirement'&&r.truth==='false'){
          const e=eventById.get(r.eventId);
          if(!e||e.type!=='requirement_falsified'||e.targetId!==n.id||
              !Array.isArray(e.evidenceRefs)||!e.evidenceRefs.length)fail('потеря истинности без доказательств');
        }
      }
      if(n.kind==='action'&&n.status==='selected'){
        const e=eventById.get(n.selectedEventId);
        if(!e||e.type!=='action_selected'||e.targetId!==n.id||
            !g.edges.some(d=>!d.archived&&d.type==='DRIVES'&&d.to===n.id))
          fail('выбор A без действующего основания и события');
      }
      if(n.kind==='canon'){
        const mode=n.evaluationMode||'legacy-arguments-v1';
        if(!['legacy-arguments-v1','comment-only-v1'].includes(mode)||!Array.isArray(n.arguments)||
            (mode==='comment-only-v1'&&(typeof n.comment!=='string'||n.arguments.length))||
            (mode==='legacy-arguments-v1'&&!n.arguments.length))fail('некорректный формат канона');
      }
      if(n.assessment){
        const e=eventById.get(n.assessment.eventId);
        if(n.kind!=='action'||!e||e.type!=='core_canon_assessed'||e.targetId!==n.id)
          fail('оценка без события');
      }
    }
    if(g.lensRecommendations!==undefined){
      if(!Array.isArray(g.lensRecommendations))fail('рекомендации линз должны быть списком');
      const seen=new Set();
      for(const r of g.lensRecommendations){
        if(!r||typeof r!=='object'||Array.isArray(r)||!
          ([2,3].includes(Object.keys(r).length))||
          Object.keys(r).some(k=>!['lensKey','text','targetId'].includes(k))||
          typeof r.lensKey!=='string'||!(/^[a-z][a-z0-9-]*$/).test(r.lensKey)||
          typeof r.text!=='string'||!r.text.trim()||r.text.length>10000||
          (r.targetId!==undefined&&!['requirement','action','canon'].includes(kinds.get(r.targetId))))
          fail('некорректная рекомендация линзы');
        const key=JSON.stringify([r.lensKey,r.targetId||null,r.text]);
        if(seen.has(key))fail('повтор рекомендации');seen.add(key);
      }
    }
    if(!g.workGraphs.length)fail('нет рабочего scope');
    const members=new Set();
    for(const w of g.workGraphs){
      if(!Array.isArray(w.memberIds)||!Array.isArray(w.rootIds)||!w.rootIds.length||
          w.memberIds.some(i=>!ids.has(i))||w.rootIds.some(i=>!w.memberIds.includes(i)||kinds.get(i)!=='requirement'))
        fail('некорректный рабочий граф');
      w.memberIds.forEach(i=>members.add(i));
    }
    if(members.size!==ids.size)fail('блок вне рабочего scope');
    return g;
  }
  function coreOutputOrigin(g,e){
    const drivers=[...new Set(g.edges.filter(d=>!d.archived&&d.type==='DRIVES'&&d.to===e.from).map(d=>d.from))].sort();
    const role=e.origin?.role||'unspecified',declared=role==='subgoal'?e.origin.requirementIds:role==='method_correctness'?drivers:[];
    const externalRequirementRefs=(e.origin?.externalRequirementRefs||[]).map(x=>({...x}));
    const actualExternal=(g.externalRefs||[]).filter(r=>r.localId===e.from&&r.direction==='incoming'&&
      r.relation?.type==='DRIVES'&&!r.relation?.archived).map(r=>r.target);
    const missingExternalDriverRefs=externalRequirementRefs.filter(ref=>!actualExternal.some(target=>
      ['packageId','identitySpace','nodeId'].every(k=>ref[k]===target[k])));
    return {externalRequirementRefs,missingExternalDriverRefs,edgeId:e.id,actionId:e.from,role,requirementIds:[...declared].sort(),
      activeRequirementIds:declared.filter(i=>drivers.includes(i)).sort(),missingDriverIds:declared.filter(i=>!drivers.includes(i)).sort()};
  }
  // Focused projections of the closed core. They never become writable owners.
  function coreFocusedView(g,id){
    validateCoreSnapshot(g);
    const all=[...g.nodes,...g.objects],by=new Map(all.map(n=>[n.id,n])),focus=by.get(id);
    if(!focus)throw Error('CORE_FOCUS_UNKNOWN');
    const edges=g.edges.filter(e=>!e.archived),chosen=new Set([id]),terminal=new Set(),origins=[],originDetails=[];
    for(const e of edges){
      if(focus.kind==='requirement'){
        if(e.from===id&&['DRIVES','DERIVES'].includes(e.type)){chosen.add(e.to);terminal.add(e.to);}
        if(e.to===id&&['INTRODUCES','DERIVES'].includes(e.type)){
          chosen.add(e.from);origins.push(e);
          if(e.type==='INTRODUCES'){
            const detail=coreOutputOrigin(g,e);originDetails.push(detail);
            for(const d of edges)if(d.to===e.from&&d.type==='DRIVES'&&(detail.role==='unspecified'||detail.activeRequirementIds.includes(d.from))){chosen.add(d.from);origins.push(d);}
          }
        }
      }else if(focus.kind==='action'){
        if(e.to===id&&['DRIVES','RELATES_R','CONTEXT_FOR','CANON_FOR'].includes(e.type))chosen.add(e.from);
        if(e.from===id&&e.type==='INTRODUCES'){chosen.add(e.to);terminal.add(e.to);}
      }else if(focus.kind==='canon'&&e.from===id&&e.type==='CANON_FOR'){chosen.add(e.to);terminal.add(e.to);}
    }
    for(const e of edges)if(chosen.has(e.to)&&['INFO_FOR','EVIDENCE_FOR'].includes(e.type))chosen.add(e.from);
    const allowed=focus.kind==='requirement'?['DRIVES','DERIVES','INTRODUCES','INFO_FOR','EVIDENCE_FOR']:
      ['DRIVES','RELATES_R','CONTEXT_FOR','CANON_FOR','INTRODUCES','INFO_FOR','EVIDENCE_FOR'];
    return {focusId:id,focusKind:focus.kind,entities:all.filter(n=>chosen.has(n.id)),
      edges:edges.filter(e=>chosen.has(e.from)&&chosen.has(e.to)&&allowed.includes(e.type)&&
        !(focus.kind==='requirement'&&terminal.has(e.from)&&e.type==='INTRODUCES')),
      terminalIds:[...terminal],origins,originDetails,viewOnly:true};
  }
  function mountCore(container,g,{document:doc=globalThis.document,onCommand=null,onFocus=null,focusId=null,readOnly=false}={}){
    const make=(tag,text,parent=container)=>{const n=doc.createElement(tag);if(text!==undefined)n.textContent=text;parent.appendChild(n);return n;};
    const kinds={requirement:'R · требуемая истинность',action:'A · способ',context:'Context · факты',canon:'Канон',info:'Информация',evidence:'Evidence'};
    const roles={DRIVES:'реализует R',RELATES_R:'относится к R',DERIVES:'непосредственная под-R',INTRODUCES:'вводит R',CONTEXT_FOR:'контекст A',CANON_FOR:'оценивает A',DEPENDS_ON:'рабочая зависимость',INFO_FOR:'поясняет',EVIDENCE_FOR:'подтверждает'};
    const all=[...g.nodes,...g.objects],by=new Map(all.map(n=>[n.id,n]));
    const section=make('section');section.className='rdg-core';
    const style=make('style',undefined,section);style.textContent='.rdg-core{padding:16px;overflow:auto;color:#e7eff7;background:#17283b}.rdg-core label{display:block;margin:10px 0}.rdg-core input,.rdg-core select,.rdg-core textarea{display:block;box-sizing:border-box;max-width:100%;width:100%;padding:7px;color:inherit;background:#102235;border:1px solid #607a96}.rdg-core textarea{min-height:70px}.rdg-core button{padding:7px;margin:6px}.rdg-core svg{position:static;display:block;width:100%;min-width:700px;background:#102235;height:auto;touch-action:auto;cursor:default}.rdg-core .core-map{overflow:auto;max-height:65vh}.rdg-core summary{cursor:pointer}.rdg-core table{border-collapse:collapse;width:100%}.rdg-core td,.rdg-core th{padding:5px;border-bottom:1px solid #526680;text-align:left}';
    make('h3','Собственные графы R, A и канонов',section);
    make('p','Рабочий scope и фокус различаются. Нажатие на блок открывает его собственный граф; терминальные блоки здесь не разворачиваются.',section);
    const work=make('select',undefined,make('label','Рабочий граф',section));
    for(const w of g.workGraphs){const o=make('option',w.title,work);o.value=w.id;}
    const focus=make('select',undefined,make('label','Открыть собственный граф',section));
    const content=make('div',undefined,section),form=make('details',undefined,section);make('summary','Изменить граф или подтвердить результат',form);
    const body=make('div',undefined,form),status=make('p','',form);status.setAttribute('role','status');
    const option=(s,v,t)=>{const o=make('option',t,s);o.value=v;return o;};
    const field=(parent,label,value='',tag='input')=>{const e=make(tag,undefined,make('label',label,parent));e.value=value;return e;};
    const select=(parent,label,items,value)=>{const e=field(parent,label,'','select');for(const [v,t] of items)option(e,v,t);if(value!=null)e.value=value;return e;};
    const choose=id=>{focus.value=id;draw();if(onFocus)onFocus(id);};
    function fill(){
      const w=g.workGraphs.find(w=>w.id===work.value);focus.replaceChildren();
      const visible=all.filter(n=>w.memberIds.includes(n.id));
      for(const n of visible)option(focus,n.id,n.title+' · '+kinds[n.kind]);
      focus.value=visible.some(n=>n.id===focusId)?focusId:w.rootIds[0];draw();
    }
    work.onchange=fill;focus.onchange=()=>choose(focus.value);
    if(focusId){const w=g.workGraphs.find(w=>w.memberIds.includes(focusId));if(w)work.value=w.id;}
    const commands=[['add','Создать блок'],['edit','Уточнить описание'],['link','Добавить связь'],['unlink','Снять связь'],['output_origin','Уточнить происхождение выходной R'],
      ['assess','Сопоставить каноны'],['select','Выбрать способ'],['review','Подтвердить актуальность'],['complete','Подтвердить результат'],
      ['falsify','Зафиксировать потерю истинности R'],['reopen','Вернуться к прежнему A'],['requirement_state','Пересмотреть необходимость R'],
      ['withdraw','Отказаться от способа'],['lens_recommendations','Рекомендовать линзу текстом'],['work_graph','Добавить рабочий граф'],['join','Соединить рабочие графы'],['include','Показать тот же блок в другом рабочем графе'],['finding','Записать находку']];
    const cmd=select(body,'Действие',commands,'edit'),details=make('div',undefined,body);
    let build=()=>({}),proofNeeded=false;
    function editForm(){
      details.replaceChildren();const n=by.get(focus.value);if(!n)return;
      proofNeeded=['complete','falsify','review'].includes(cmd.value);
      const pick=(label,values=all)=>select(details,label,values.map(n=>[n.id,n.title+' · '+n.id]));
      function originFields(parent,initial={}){
        const role=select(parent,'Назначение выходной R',[['subgoal','Подцель исходных R'],['method_correctness','Корректность самого Action']],initial.role||'subgoal');
        const ids=field(parent,'Исходные R: ID через запятую',(initial.requirementIds||[]).join(', '));
        const update=()=>{ids.parentElement.hidden=role.value!=='subgoal';};role.onchange=update;update();
        return ()=>role.value==='subgoal'?{role:'subgoal',requirementIds:ids.value.split(',').map(s=>s.trim()).filter(Boolean)}:{role:'method_correctness'};
      }
      if(cmd.value==='add'){
        const kind=select(details,'Роль блока',Object.entries(kinds),'requirement');
        const title=field(details,'Смысловой заголовок'),description=field(details,'Подробное описание','','textarea');
        const scope=field(details,'Область истинности / применения',by.get(g.rootRequirementId).scope||'');
        make('p','Для сложной R предпочтительны полезные под-R. Подробности без пользы отдельной под-R остаются в описании.',details);
        const extras=make('div',undefined,details);let extraValues=()=>({});
        function kindFields(){
          extras.replaceChildren();extraValues=()=>({});
          if(kind.value==='requirement'){
            const status=select(extras,'Нормативный статус',[['potential','Потенциальная R на бумаге'],['active','Установленная R']],'potential');
            extraValues=()=>({scope:scope.value,status:status.value});
          }else if(kind.value==='evidence'){
            const claim=field(extras,'Какое утверждение подтверждается','','textarea'),version=field(extras,'Версия проверенного объекта'),source=field(extras,'Источник доказательства');
            extraValues=()=>({scope:scope.value,claim:claim.value,version:version.value,source:source.value});
          }else if(kind.value==='canon'){
            const comment=field(extras,'Комментарий к применимости Action','','textarea');
            extraValues=()=>({evaluationMode:'comment-only-v1',comment:comment.value,arguments:[]});
          }
        }
        kind.onchange=kindFields;kindFields();
        build=()=>{const id=(kind.value==='action'?'A-':kind.value==='requirement'?'R-':'O-')+randomId();
          return {entity:{id,kind:kind.value,title:title.value,description:description.value,...extraValues()},workGraphId:work.value};};
      }else if(cmd.value==='edit'){
        const title=field(details,'Заголовок',n.title),description=field(details,'Описание',n.description||'','textarea');
        const scope=n.kind==='requirement'?field(details,'Область истинности',n.scope):null;
        const comment=n.kind==='canon'?field(details,'Комментарий к применимости Action',n.comment||'','textarea'):null;
        const migrate=n.kind==='canon'&&n.evaluationMode!=='comment-only-v1'?field(details,'Преобразовать этот канон в свободный комментарий','','input'):null;
        if(migrate){migrate.type='checkbox';make('p','Прежние условия сохранятся в истории. Перед записью проверьте изменение.',details);}
        build=()=>({nodeId:n.id,changes:{title:title.value,description:description.value,...(scope?{scope:scope.value}:{}),
          ...(comment&&(n.evaluationMode==='comment-only-v1'||migrate?.checked)?{comment:comment.value}:{}),
          ...(migrate?.checked?{evaluationMode:'comment-only-v1',arguments:[]}:{})},
          ...(migrate?.checked?{legacyCanonMigrationAcknowledged:true}:{})});
      }else if(cmd.value==='link'){
        const type=select(details,'Смысл связи',Object.entries(roles),'DRIVES'),from=pick('Источник'),to=pick('Получатель');
        const role=select(details,'Роль относящейся R',[['affected','Затрагиваемая'],['constraining','Ограничивающая']]);
        const originBox=make('div',undefined,details),origin=originFields(originBox);
        type.onchange=()=>{originBox.hidden=type.value!=='INTRODUCES';role.parentElement.hidden=type.value!=='RELATES_R';};type.onchange();
        from.value=n.id;build=()=>({edge:{id:'E-'+randomId(),type:type.value,from:from.value,to:to.value,...(type.value==='RELATES_R'?{role:role.value}:{}),...(type.value==='INTRODUCES'?{origin:origin()}:{})}});
      }else if(cmd.value==='output_origin'){
        const outputs=g.edges.filter(e=>!e.archived&&e.type==='INTRODUCES'&&(e.from===n.id||e.to===n.id));
        const edge=select(details,'Выход способа',outputs.map(e=>[e.id,by.get(e.from).title+' → '+by.get(e.to).title]));
        const box=make('div',undefined,details);let readOrigin=()=>({});
        edge.onchange=()=>{box.replaceChildren();readOrigin=originFields(box,outputs.find(e=>e.id===edge.value)?.origin);};edge.onchange();
        build=()=>({edgeId:edge.value,origin:readOrigin()});
      }else if(cmd.value==='unlink'){
        const edges=g.edges.filter(e=>!e.archived&&(e.from===n.id||e.to===n.id));
        const edge=select(details,'Снимаемая связь',edges.map(e=>[e.id,(by.get(e.from)?.title||e.from)+' → '+(by.get(e.to)?.title||e.to)+' · '+roles[e.type]]));
        const disposition=field(details,'Судьба обязательств после снятия связи','','textarea');build=()=>({edgeId:edge.value,disposition:disposition.value});
      }else if(cmd.value==='assess'){
        const matches={},situation=g.edges.filter(e=>!e.archived&&e.to===n.id&&['DRIVES','RELATES_R','CONTEXT_FOR'].includes(e.type)).map(e=>by.get(e.from));
        function conditions(c,cid,parent){
          if(c.all||c.any){make('strong',c.all?'Все условия AND':'Хотя бы одно условие OR',parent);for(const child of c.all||c.any)conditions(child,cid,parent);return;}
          const row=make('fieldset',undefined,parent);make('legend',c.text,row);
          const result=select(row,'Результат сравнения',[['unknown','Неизвестно'],['match','Совпало'],['partial','Частичное сходство'],['no-match','Не совпало']]);
          const reason=field(row,'Основание смыслового сопоставления','','textarea'),source=select(row,'Факт рабочей ситуации',situation.map(n=>[n.id,n.title]));
          matches[cid][c.id]=()=>({result:result.value,reason:reason.value,sourceIds:source.value?[source.value]:[]});
        }
        for(const e of g.edges.filter(e=>!e.archived&&e.type==='CANON_FOR'&&e.to===n.id)){
          const canon=by.get(e.from);matches[canon.id]={};make('h4',canon.title,details);
          if(canon.evaluationMode==='comment-only-v1')make('p',canon.comment,details);
          for(const a of canon.arguments){make('p',(a.polarity==='against'?'Против':'За')+' · '+(a.strength==='hard'?'жёсткая несовместимость':'мягкий довод')+': '+a.text,details);conditions(a.condition,canon.id,details);}
        }
        build=()=>({nodeId:n.id,matches:Object.fromEntries(Object.entries(matches).map(([cid,v])=>[cid,Object.fromEntries(Object.entries(v).map(([id,fn])=>[id,fn()]))]))});
      }else if(cmd.value==='review'){
        const allStale=field(details,'Проверены все затронутые элементы вместе?','','input');allStale.type='checkbox';
        make('p','Stale требует проверки. Подтверждение сохраняет прежний результат; не заменяет доказательство его потери.',details);
        build=()=>{const ids=allStale.checked?all.filter(n=>n.review?.required).map(n=>n.id):[n.id];const observed={};
          for(const id of ids){observed[id]=by.get(id).revision;for(const e of g.edges)if(!e.archived&&e.to===id&&!['INFO_FOR','EVIDENCE_FOR'].includes(e.type))observed[e.from]=by.get(e.from).revision;}
          return {nodeIds:ids,observed};};
      }else if(cmd.value==='withdraw'){
        const outputs=g.edges.filter(e=>!e.archived&&e.from===n.id&&e.type==='INTRODUCES');const fields=outputs.map(e=>[e.to,field(details,'Судьба R: '+by.get(e.to).title,'','textarea')]);
        build=()=>({nodeId:n.id,dispositions:Object.fromEntries(fields.map(([id,f])=>[id,f.value]))});
      }else if(cmd.value==='requirement_state'){
        const state=select(details,'Необходимость R',[['active','Нужна'],['inactive','Не требуется']]),disposition=field(details,'Основание и последствия для общей работы','','textarea');
        const shared=field(details,'Рассмотрены последствия для всех общих родителей?','','input');shared.type='checkbox';
        const linked=g.edges.filter(e=>!e.archived&&e.type==='DRIVES'&&e.from===n.id).map(e=>by.get(e.to))
          .filter(a=>a?.kind==='action'&&a.status==='selected'&&a.result?.state==='confirmed');
        const decision=select(details,'Подтверждённый Action решения о ненужности',linked.map(a=>[a.id,a.title+' · '+a.id]));
        make('p','Сначала создайте, выберите и подтвердите связанный с этой R Action проверки необходимости. Writer проверит актуальность результата и evidence.',details);
        const update=()=>{decision.parentElement.hidden=state.value!=='inactive';};
        state.onchange=update;update();
        build=()=>({nodeId:n.id,state:state.value,disposition:disposition.value,acceptSharedConsequences:shared.checked,
          ...(state.value==='inactive'?{decisionActionId:decision.value}:{})});
      }else if(cmd.value==='lens_recommendations'){
        const lens=field(details,'Ключ рекомендуемой линзы (из каталога)');
        const text=field(details,'Когда и для чего её использовать','','textarea');
        const target=select(details,'К чему относится рекомендация',[
          ['', 'Ко всему графу'],...all.filter(x=>['requirement','action','canon'].includes(x.kind)).map(x=>[x.id,x.title+' · '+x.id])],n.id);
        make('p','Это только текстовая рекомендация. Линза не запускается, действия не выбираются и evidence не создаётся.',details);
        build=()=>({recommendations:[...(g.lensRecommendations||[]),{
          lensKey:lens.value.trim(),text:text.value,...(target.value?{targetId:target.value}:{})}]});
      }else if(cmd.value==='work_graph'){
        const title=field(details,'Название рабочего scope');const root=pick('Корневая R',all.filter(n=>n.kind==='requirement'));
        build=()=>({id:'WG-'+randomId(),title:title.value,rootIds:[root.value],memberIds:[root.value]});
      }else if(cmd.value==='join'||cmd.value==='include'){
        const other=select(details,'Другой рабочий граф',g.workGraphs.filter(w=>w.id!==work.value).map(w=>[w.id,w.title]));
        build=()=>cmd.value==='join'?{workGraphIds:[work.value,other.value]}:{nodeId:n.id,workGraphId:other.value};
      }else if(cmd.value==='finding'){
        const type=select(details,'Тип находки',[['problem','Подтверждённая проблема'],['risk','Риск'],['decision-uncertainty','Развилка решения'],['opportunity','Улучшение']]);const description=field(details,'Ситуация и основания','','textarea');
        build=()=>({nodeId:n.id,finding:{id:'F-'+randomId(),type:type.value,text:description.value}});
      }else{make('p',cmd.value==='select'?'Выбор принимает все актуальные выходные R способа. Совместимые способы допускаются; hard-несовместимость не компенсируется плюсами.':'Записывается отдельный факт; история прежних достижений сохраняется.',details);build=()=>({nodeId:n.id});}
      const note=field(details,'Основание действия / результат проверки','','textarea');
      const path=proofNeeded?field(details,'Проверенный файл результата, путь в рабочем owner'):null;
      const sha=proofNeeded?field(details,'SHA256 проверенного файла'):null;
      const submit=make('button','Записать и перечитать',details);submit.disabled=readOnly||!onCommand;
      submit.onclick=async()=>{submit.disabled=true;status.textContent='Проверяю и записываю…';try{
        const request={action:'core_'+cmd.value,transactionId:'ui-'+randomId(),nodeId:n.id,data:build(),note:note.value,expectedGraphRevision:g.revision};
        if(path?.value)request.evidenceRefs=[{path:path.value,sha256:sha.value}];
        await onCommand(request);status.textContent='Результат запроса показан в статусе writer.';
      }catch(e){status.textContent=e.message;}finally{submit.disabled=readOnly||!onCommand;}};
    }
    cmd.onchange=editForm;
    function draw(){
      const n=by.get(focus.value);if(!n)return;focusId=n.id;content.replaceChildren();
      const v=coreFocusedView(g,n.id);make('h4',kinds[n.kind]+' · '+n.title,content);
      make('p',(n.review?.required?'Требует проверки актуальности. ':'')+(n.result?.state==='confirmed'?'Результат ранее подтверждён. ':'')+'Область: '+(n.scope||g.title),content);
      for(const item of g.lensRecommendations||[]){
        if(item.targetId&&item.targetId!==n.id)continue;
        make('p','Рекомендуемая линза '+item.lensKey+(item.targetId?' для '+item.targetId:' для графа')+': '+item.text,content);
      }
      for(const origin of v.originDetails){
        const names=origin.activeRequirementIds.map(i=>by.get(i).title+' · '+i).join(', ');
        make('p',origin.role==='subgoal'?'Подцель через Action для: '+names:origin.role==='method_correctness'?'Требование корректности Action; он служит: '+names:'Происхождение выхода ещё не уточнено; цели Action не объявляются родителями автоматически.',content);
        if(origin.missingDriverIds.length)make('p','Связи с исходными R изменились. Пересмотрите происхождение: '+origin.missingDriverIds.join(', '),content);
      }
      const wrap=make('div',undefined,content);wrap.className='core-map';
      const ns='http://www.w3.org/2000/svg',svg=doc.createElementNS(ns,'svg');wrap.appendChild(svg);
      const groups=[v.entities.filter(x=>x.id!==n.id&&!v.terminalIds.includes(x.id)),[n],v.entities.filter(x=>v.terminalIds.includes(x.id))];
      const rows=Math.max(...groups.map(x=>x.length),1),height=rows*155+70;svg.setAttribute('viewBox','0 0 1060 '+height);svg.style.height=height+'px';
      const pos=new Map();groups.forEach((items,col)=>items.forEach((x,row)=>pos.set(x.id,{x:175+col*350,y:85+row*155})));
      const shape=(tag,attrs,parent=svg)=>{const e=doc.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);parent.appendChild(e);return e;};
      const markerId='core-arrow-'+randomId(),defs=shape('defs',{}),marker=shape('marker',{id:markerId,viewBox:'0 0 10 10',refX:10,refY:5,markerWidth:7,markerHeight:7,orient:'auto'},defs);
      shape('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#a7c4dc'},marker);
      for(const e of v.edges){
        const a=pos.get(e.from),b=pos.get(e.to),aw=by.get(e.from).kind==='action'?62:125,bw=by.get(e.to).kind==='action'?62:125;
        let points;
        if(a.x===b.x)points=[[a.x-aw,a.y],[20,a.y],[20,b.y],[b.x-bw,b.y]];
        else if(Math.abs(a.x-b.x)>350)points=[[a.x+aw,a.y],[350,a.y],[350,height-20],[700,height-20],[700,b.y],[b.x-bw,b.y]];
        else{const lane=(a.x+b.x)/2;points=[[a.x+aw,a.y],[lane,a.y],[lane,b.y],[b.x-bw,b.y]];}
        shape('polyline',{points:points.map(p=>p.join(',')).join(' '),fill:'none',stroke:['INFO_FOR','EVIDENCE_FOR'].includes(e.type)?'#92a8b8':'#84b5df','stroke-width':2,'marker-end':'url(#'+markerId+')','stroke-dasharray':['INFO_FOR','EVIDENCE_FOR'].includes(e.type)?'5 4':'none'});
      }
      for(const x of v.entities){const p=pos.get(x.id),group=shape('g',{'role':'button','tabindex':'0','aria-label':'Открыть '+x.title});
        const color={requirement:'#234e75',action:'#72532b',context:'#245c57',canon:'#573f7b',info:'#3c4c5b',evidence:'#3e624f'}[x.kind];
        shape(x.kind==='action'?'circle':'rect',x.kind==='action'?{cx:p.x,cy:p.y,r:62,fill:color,stroke:x.review?.required?'#ffc18c':'#a7c4dc'}:{x:p.x-125,y:p.y-55,width:250,height:110,rx:7,fill:color,stroke:x.review?.required?'#ffc18c':'#a7c4dc'},group);
        const limit=x.kind==='action'?14:30,lines=x.title.match(new RegExp('.{1,'+limit+'}(?:\\s|$)|.{1,'+limit+'}','gu'))||[x.title];
        const tooltip=shape('title',{},group);tooltip.textContent=x.title;
        for(let i=0;i<Math.min(lines.length,3);i++){const t=shape('text',{x:p.x,y:p.y-18+i*18,fill:'#fff','font-size':14,'text-anchor':'middle'},group);t.textContent=lines[i]+(i===2&&lines.length>3?'…':'');}
        const label=shape('text',{x:p.x,y:p.y+42,fill:'#d8e8f6','font-size':11,'text-anchor':'middle'},group);label.textContent=x.id+(v.terminalIds.includes(x.id)?' ↗':'');
        group.onclick=()=>choose(x.id);group.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(x.id);}};
      }
      const table=make('table',undefined,content);for(const e of v.edges){const tr=make('tr',undefined,table);make('td',by.get(e.from).title,tr);make('td',roles[e.type]+(e.role?' · '+e.role:'')+(e.origin?' · '+(e.origin.role==='subgoal'?'подцель '+e.origin.requirementIds.join(', '):'корректность Action'):''),tr);make('td',by.get(e.to).title,tr);}
      if(n.kind==='action'&&n.assessment){
        const current=Object.entries(n.assessment.pins||{}).every(([id,revision])=>by.get(id)?.revision===revision);
        const record=g.events.find(e=>e.id===n.assessment.eventId),assessment=make('section',undefined,content);
        make('h4',current?'Сохранённая оценка текущей ситуации':'Историческая оценка: нужна проверка актуальности',assessment);
        if(record?.verdict)make('p','Вывод оценки: '+({incompatible:'жёсткая несовместимость',undetermined:'существенная неизвестность',assessed:'сопоставление зафиксировано'}[record.verdict.verdict]||record.verdict.verdict),assessment);
        for(const [canon,matches] of Object.entries(n.assessment.matches))for(const [condition,m] of Object.entries(matches))
          make('p',(by.get(canon)?.title||canon)+' / '+condition+': '+m.result+' · '+m.reason+' · факты: '+m.sourceIds.map(id=>by.get(id)?.title||id).join(', '),assessment);
      }
      for(const x of v.entities){const d=make('details',undefined,content);make('summary',kinds[x.kind]+' · '+x.title+' · версия '+x.revision,d);make('p',x.description||x.claim||'',d);
        if(x.kind==='evidence')make('p','Утверждение: '+x.claim+' · область: '+x.scope+' · версия: '+x.version+' · источник: '+x.source,d);
        if(x.kind==='info')for(const usage of g.edges.filter(e=>!e.archived&&e.from===x.id&&e.type==='INFO_FOR')){const b=make('button','Поясняет: '+by.get(usage.to).title,d);b.onclick=()=>choose(usage.to);}
        if(x.kind==='canon'){
          if(x.evaluationMode==='comment-only-v1')make('p',x.comment,d);
          else for(const arg of x.arguments){make('p',(arg.strength==='hard'?'Hard':'Soft')+' · '+arg.text,d);const condition=c=>c.all?'AND ('+c.all.map(condition).join('; ')+')':c.any?'OR ('+c.any.map(condition).join('; ')+')':c.text;make('p',condition(arg.condition),d);}
        }
        if(x.review?.required)make('p','Причины проверки: '+x.review.causes.map(c=>c.sourceId+' @ '+c.sourceRevision).join(', '),d);
      }
      editForm();
    }
    fill();form.hidden=readOnly;
    return {focus:choose,get focusId(){return focusId;},projection:()=>coreFocusedView(g,focusId)};
  }

  function mount(container,transport,options={}){
    const doc=options.document||document,fields={},buttons={};
    let view=null,busy=false,pending=null,activeId=null,workspace=null,contextSelectionRequired=false;const cardControls=[];let graphStatus=null,graphRetry=null;
    const make=(tag,text,parent)=>{const x=doc.createElement(tag);if(text!==undefined)x.textContent=text;
      if(parent)parent.appendChild(x);return x;};
    const toolbar=make('div',undefined,container);toolbar.classList.add('wf-toolbar');
    const heading=make('h3','Данные плана',toolbar);
    const refresh=make('button','Обновить',toolbar);
    const jump=make('button','Перейти к плану ↓',toolbar);jump.classList.add('wf-jump-plan');
    jump.disabled=true;buttons.jumpPlan=jump;let firstPlannedCard=null;
    jump.onclick=()=>{
      if(!firstPlannedCard)return;
      const scrollRoot=container.closest?.('#workflow-page');
      const behavior=typeof matchMedia==='function'&&matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth';
      if(scrollRoot?.scrollTo){
        const top=firstPlannedCard.getBoundingClientRect().top-scrollRoot.getBoundingClientRect().top+
          scrollRoot.scrollTop-toolbar.getBoundingClientRect().height-16;
        scrollRoot.scrollTo({top,behavior});
      }else firstPlannedCard.scrollIntoView?.({block:'start',behavior});
      firstPlannedCard.focus?.({preventScroll:true});
    };
    const status=make('div','Данные ещё не загружены. Нажмите «Обновить».',toolbar);status.classList.add('wf-status');status.setAttribute('role','status');
    // No admin bearer or token is stored in this UI. A trusted owner must
    // explicitly enable the optional admin endpoint when starting Helper.
    const modulePanel=make('details',undefined,container);modulePanel.classList.add('wf-modules');
    make('summary','Модули · в разработке',modulePanel);
    make('p','Экспериментальная подсистема. Используйте для разработки и проверки модулей.',modulePanel);
    const moduleList=make('div',undefined,modulePanel);
    function renderModules(){
      moduleList.replaceChildren();
      make('p','Базовый модуль · Requirements, Actions, история и Plan',moduleList);
      const all=view?.moduleCapabilities;
      if(!all){make('p','Для управления модулями подключите авторизованный Helper.',moduleList);return;}
      for(const scope of ['graph','plan']){
        const caps=all[scope];if(!caps)continue;
        for(const [mid,versions] of Object.entries(caps.available||{})){
          const enabled=Object.hasOwn(caps.enabled||{},mid);
          const row=make('p',scope+' · '+mid+' · '+(enabled?'включён':'выключен')+' ',moduleList);
          const button=make('button',enabled?'Отключить':'Подключить',row);
          const can=scope==='plan'?view.permissions?.includes('plan.edit'):
            view.permissions?.some(p=>p==='graph.write'||p==='graph.configure_modules');
          button.disabled=busy||!!pending||!!options.readOnly||!!options.localPreview||!can;
          button.onclick=()=>configureModule(scope,mid,!enabled);
        }
      }
    }
    async function configureModule(scope,mid,enable){
      if(busy||pending||!view)return;
      const caps=view.moduleCapabilities?.[scope];
      if(!caps?.available?.[mid])throw Error('Модуль недоступен в выбранной области');
      const modules={...caps.pinned};
      if(enable)modules[mid]??=Math.min(...caps.available[mid]);
      const disabled=new Set(caps.disabled||[]);
      if(enable)disabled.delete(mid);else disabled.add(mid);
      const owner=view.sources.graphs[view.graphFile];
      const random=randomId();
      return send({...(workspace?.contextId!=null?{contextId:workspace.contextId}:{}),
        action:scope==='plan'?'configure_plan_modules':'configure_graph_modules',
        transactionId:'ui-'+random,modules,disabledModules:[...disabled],
        note:(enable?'Подключение':'Отключение')+' модуля '+mid+' для '+scope,
        expectedGraphRevision:owner.revision,expectedPlanRevision:view.sources.plan.revision});
    }
    const grantPanel=make('details',undefined,container);grantPanel.classList.add('wf-grants');grantPanel.hidden=true;
    make('summary','Управление полномочиями',grantPanel);
    make('p','Только доверенная административная сессия. Новый токен показывается после выдачи; сохраните его самостоятельно.',grantPanel);
    const grantStatus=make('p','Нажмите «Просмотреть права».',grantPanel);grantStatus.setAttribute('role','status');
    const grantSelect=make('select',undefined,make('label','Выданный grant',grantPanel));
    grantSelect.setAttribute('aria-label','Выданный grant');
    const grantLabel=make('input',undefined,make('label','Метка полномочия',grantPanel));
    grantLabel.setAttribute('aria-label','Метка полномочия');
    make('p','Разрешение grant.admin не выдаётся через этот интерфейс; управление выдачей прав остаётся у владельца.',grantPanel);
    const grantPermissions=make('textarea',undefined,make('label','Разрешения — по одному в строке',grantPanel));
    grantPermissions.setAttribute('aria-label','Разрешения — по одному в строке');
    const grantScopes=make('textarea',undefined,make('label','Области доступа — по одной в строке',grantPanel));
    grantScopes.setAttribute('aria-label','Области доступа — по одной в строке');
    const grantRead=make('button','Просмотреть права',grantPanel);
    const grantIssue=make('button','Выдать токен',grantPanel);
    const grantAmend=make('button','Изменить выбранный grant',grantPanel);
    const grantRevoke=make('button','Отозвать выбранный grant',grantPanel);
    const grantRetry=make('button','Повторить тот же запрос',grantPanel);grantRetry.hidden=true;
    const grantSecret=make('code','',grantPanel);grantSecret.setAttribute('aria-label','Новый токен — одноразовый показ');
    const grantHide=make('button','Скрыть показанный токен',grantPanel);grantHide.onclick=()=>{grantSecret.textContent='';};
    let grants=[],grantRevision=null,grantBusy=false,grantPending=null;
    const lines=v=>v.split(/\r?\n|,/).map(x=>x.trim()).filter(Boolean);
    const grantSpec=()=>({label:grantLabel.value.trim(),permissions:lines(grantPermissions.value),scopes:lines(grantScopes.value)});
    const grantChoice=()=>grants.find(g=>g.id===grantSelect.value);
    function grantControls(){
      const ready=!grantBusy&&grantRevision!==null&&!grantPending;
      grantRead.disabled=grantBusy||!!grantPending;
      grantIssue.disabled=!ready;
      grantAmend.disabled=!ready||!grantChoice();grantRevoke.disabled=!ready||!grantChoice();
      grantRetry.hidden=!grantPending;grantRetry.disabled=grantBusy||!grantPending;
    }
    function grantRender(result){
      grants=(result.grants||[]).filter(g=>!g.owner);
      grantRevision=result.revision;
      const previous=grantSelect.value;
      grantSelect.replaceChildren();
      for(const g of grants){const option=make('option',g.id+' · '+(g.label||'Без метки')+(g.active?'':' · отозван'),grantSelect);option.value=g.id;}
      grantSelect.value=grants.some(g=>g.id===previous)?previous:(grants[0]?.id||'');
      grantFillSelected();grantControls();
    }
    function grantFillSelected(){
      const g=grantChoice();
      grantLabel.value=g?.label||'';
      grantPermissions.value=(g?.permissions||[]).join('\n');
      grantScopes.value=(g?.scopes||[]).join('\n');
    }
    grantSelect.onchange=()=>{
      grantSecret.textContent='';grantFillSelected();grantControls();
    };
    async function grantRefresh(){
      if(grantBusy||grantPending)return;
      grantBusy=true;grantControls();grantSecret.textContent='';
      try{grantRender(await transport.admin({operation:'list'}));grantStatus.textContent='Права перечитаны. Токены существующих grants не отображаются.';}
      catch(e){grantStatus.textContent='Не удалось прочитать права: '+e.message;}
      finally{grantBusy=false;grantControls();}
    }
    async function grantSend(req){
      if(grantBusy||!req)return;
      grantBusy=true;grantPending=req;grantControls();grantSecret.textContent='';
      let accepted;
      try{
        accepted=await transport.admin(req);
      }catch(e){
        // Only uncertainty about the mutation itself permits exact retry.
        if(e.definite)grantPending=null;
        grantStatus.textContent=(e.definite?'Запрос отклонён: ':'Исход запроса неизвестен; повторите тот же запрос: ')+e.message;
        grantBusy=false;grantControls();return;
      }
      grantPending=null;
      if(req.operation==='issue'&&accepted.token){
        grantSecret.textContent='Новый токен (сохраните сейчас): '+accepted.token;
      }
      const outcome=accepted.replayed?'Повтор подтверждён, дополнительного grant нет.':'Изменение полномочий принято.';
      try{
        // Refresh is independent of the already accepted mutation. A failed
        // refresh must not call the mutation uncertain or enable its retry.
        const listed=await transport.admin({operation:'list'});
        grantRender(listed);
        grantStatus.textContent=outcome;
      }catch(e){
        grantRevision=null; // Avoid a new mutation using an outdated grant revision.
        grantStatus.textContent=outcome+' Не удалось обновить список прав: '+e.message+' Нажмите «Просмотреть права».';
      }finally{grantBusy=false;grantControls();}
    }
    const newGrantRequest=operation=>{
      if(grantPending)return null;
      if(grantRevision===null)throw Error('Сначала просмотрите права.');
      const uuid=randomId();
      const request={operation,transactionId:'grant-ui-'+uuid,expectedRevision:grantRevision};
      if(operation==='issue')request.grant=grantSpec();
      else{if(!grantChoice())throw Error('Выберите существующий grant.');request.id=grantSelect.value;
        if(operation==='amend')request.grant=grantSpec();}
      return request;
    };
    function performGrant(operation){try{const request=newGrantRequest(operation);if(request)void grantSend(request);}
      catch(e){grantStatus.textContent=e.message;}}
    grantRead.onclick=()=>void grantRefresh();
    grantIssue.onclick=()=>performGrant('issue');
    grantAmend.onclick=()=>performGrant('amend');
    grantRevoke.onclick=()=>performGrant('revoke');
    grantRetry.onclick=()=>void grantSend(grantPending);
    const editor=make('details',undefined,container);editor.classList.add('wf-editor');editor.hidden=true;
    make('summary','Разместить из графа',editor);
    make('h3','Размещение цели или Action',editor);
    const grid=make('div',undefined,container);grid.classList.add('wf-grid');grid.classList.add('wf-timeline');grid.hidden=true;
    if(transport.setStatus)transport.setStatus(message=>{status.textContent=message;syncStatus();});
    const history=make('section',undefined,grid),future=make('section',undefined,grid),
      unplaced=make('section',undefined,grid);
    history.classList.add('wf-history');history.setAttribute('aria-label','История');
    future.classList.add('wf-future');future.setAttribute('aria-label','План во времени');
    unplaced.classList.add('wf-unplaced');unplaced.setAttribute('aria-label','Без места во времени');
    let fieldParent=editor;
    function field(name,label,tag='input',type='text'){
      const l=make('label',label,fieldParent),x=make(tag,undefined,l);
      if(tag==='input')x.type=type;x.value='';
      x.setAttribute('aria-label',label);fields[name]=x;return x;
    }
    field('graph','Граф с существующей целью или Action','select');
    const target=field('target','Цель или Action','select');
    const details=make('p','',editor);
    field('note','Основание изменения или результат выполнения','textarea');
    field('placement','Сохранённое размещение','select');
    field('at','Дата начала не ранее','input','date');
    field('after','После размещённой цели или Action','select');
    const placementDetails=make('p',undefined,editor);
    const planControls=make('div',undefined,editor);
    const graphEditor=make('details',undefined,options.graphContainer);
    make('summary','Редактировать граф / записать результат',graphEditor);
    graphEditor.open=!!options.graphContainer;
    graphStatus=make('div','',graphEditor);graphStatus.setAttribute('role','status');
    graphRetry=make('button','Повторить тот же запрос',graphEditor);graphRetry.onclick=()=>send(pending);
    function syncStatus(){if(graphStatus){graphStatus.textContent=status.textContent;graphStatus.classList.toggle('wf-error',!!status.classList.contains?.('wf-error'));}if(graphRetry){graphRetry.hidden=!pending;graphRetry.disabled=busy||!pending;}}
    const corePane=make('div',undefined,graphEditor);corePane.hidden=true;let coreEditor=null,coreFocusId=null;
    make('p','Изменения в подключённом графе. Размещение во времени выполняется на вкладке плана.',graphEditor);
    const graphTarget=make('select',undefined,make('label','Сущность графа',graphEditor));
    graphTarget.setAttribute('aria-label','Сущность редактируемого графа');
    const graphNote=make('textarea',undefined,make('label','Основание изменения или результат',graphEditor));
    graphNote.setAttribute('aria-label','Основание изменения графа');
    graphNote.oninput=()=>{fields.note.value=graphNote.value;};
    fields.note.oninput=()=>{graphNote.value=fields.note.value;};
    fieldParent=graphEditor;
    field('title','Название');
    field('actionType','Тип нового Action','select');
    field('recommended','Когда способ подходит — по одному случаю на строку','textarea');
    field('contraindicated','Когда способ не подходит','textarea');
    field('childRole','Роль новой дочерней R','select');
    field('qrpe','Новая запись QRPE');
    const childBox=make('div',undefined,graphEditor);make('p','При отзыве укажите судьбу каждой введённой R. Изменения примет только штатный writer.',childBox);
    const dispositionFields=[];
    const controls=make('div',undefined,graphEditor);
    function button(name,title,action){
      const b=make('button',title,['place','unplace'].includes(name)?planControls:controls);b.onclick=()=>run(action);buttons[name]=b;return b;
    }
    button('add','Создать вариант Action','add_action');button('title','Изменить название','edit_title');
    button('canon','Записать канон','edit_canon');button('requirement','Добавить дочернюю R','prepare_requirement');
    button('qrpe','Добавить QRPE','add_qrpe');button('select','Выбрать Action','select');
    button('complete','Записать выполнение / достижение','complete');button('withdraw','Отозвать выполненный Action','withdraw');
    button('place','Разместить / изменить место','place');button('unplace','Снять размещение','unplace');
    buttons.retry=make('button','Повторить тот же запрос',container);buttons.retry.onclick=()=>send(pending);
    buttons.refresh=refresh;refresh.onclick=()=>refreshView();
    function optionsFor(select,items,value){
      select.replaceChildren();for(const [id,title] of items){const o=make('option',title,select);o.value=id;}
      select.value=items.some(x=>x[0]===value)?value:(items[0]?.[0]||'');
    }
    optionsFor(fields.actionType,[['general','Обычный'],['decomposition','Выделение подцелей']],'general');
    optionsFor(fields.childRole,[['subgoal','Часть разбиения родительской цели'],['method_correctness','Нужно для корректного выполнения Action']],'subgoal');
    function selectedFile(){return fields.graph.value||view?.graphFile;}
    function graph(){return view?.sources.graphs[selectedFile()];}
    function fillTargets(id=activeId){
      optionsFor(target,(graph()?.nodes||[]).filter(n=>['action','requirement'].includes(n.kind)).map(n=>[n.id,n.title+' · '+n.kind+' · '+(n.status||'active')]),id);
      focus();
    }
    fields.graph.onchange=()=>fillTargets(null);
    graphTarget.onchange=()=>{fields.graph.value=view.graphFile;fillTargets(graphTarget.value);};
    function selected(){return graph()?.nodes.find(n=>n.id===target.value);}
    function updateControls(){
      renderModules();
      const n=selected(),perms=view?.permissions||[],graphWrite=p=>selectedFile()===view?.graphFile&&(perms.includes('graph.write')||perms.includes('graph.'+p));
      const protectedGraph=view&&Object.values(view.sources.graphs).some(g=>g.nodes.some(n=>n.reconsiderationPolicy?.mode==='protected'));
      jump.disabled=!view||!firstPlannedCard;
      const locked=busy||!!pending||!view,own=n&&!n.projectionOf,executed=graph()?.events.some(e=>e.type==='action_executed'&&e.targetId===n?.id);
      const policy=protectedGraph||!own;
      const canDrive=own||n?.id===view?.continuationRootId;
      buttons.add.disabled=locked||protectedGraph||!canDrive||n?.kind!=='requirement'||!graphWrite('add_action');
      buttons.title.disabled=locked||policy||!graphWrite('graph_edit.edit_node');
      buttons.canon.disabled=locked||policy||n?.kind!=='action'||!graphWrite('graph_edit.edit_node');
      buttons.requirement.disabled=locked||policy||n?.kind!=='action'||!graphWrite('graph_edit.prepare_action_requirement');
      buttons.qrpe.disabled=locked||policy||!graphWrite('append_qrpe');
      buttons.select.disabled=locked||policy||n?.kind!=='action'||n.status!=='candidate'||!graphWrite('select_action');
      buttons.complete.disabled=locked||policy||executed||n?.status==='superseded'||
        !graphWrite(n?.kind==='action'?'record_action_execution':'record_requirement_achievement');
      buttons.withdraw.disabled=locked||policy||n?.kind!=='action'||n.status!=='selected'||!executed||!graphWrite('withdraw_action');
      buttons.place.disabled=locked||!n||!perms.includes('plan.edit')||placementState().complex||
        (n.kind==='action'&&n.status!=='selected');
      buttons.unplace.disabled=locked||!fields.placement.value||!perms.includes('plan.edit');
      for(const control of cardControls)control.button.disabled=locked||!perms.includes('plan.edit')||!control.allowed;
      buttons.retry.hidden=!pending;buttons.retry.disabled=busy||!pending;buttons.refresh.disabled=busy;
      syncStatus();
      if(options.onStateChange)options.onStateChange({busy,pending:!!pending,ready:!!view});
    }
    function placementState(){
      const plan=view?.sources.plan,chosen=plan?.steps.find(s=>s.id===fields.placement.value);
      const rules=chosen?(plan.timeConstraints||[]).filter(r=>r.stepId===chosen.id):[];
      const starts=rules.filter(r=>r.type==='notBefore');
      const incoming=chosen?(plan.sequence||[]).filter(e=>e.after===chosen.id):[];
      return {chosen,rules,starts,incoming,complex:starts.length>1||incoming.length>1||
        starts.some(r=>!/^\d{4}-\d{2}-\d{2}$/.test(r.at))};
    }
    function loadPlacement(){
      const p=placementState();
      fields.at.value=p.starts.length===1&&!p.complex?p.starts[0].at:'';
      const steps=view.sources.plan.steps.filter(s=>s.id!==p.chosen?.id);
      optionsFor(fields.after,[['','Без порядка'],...steps.map(s=>[s.id,s.title])],
        p.incoming.length===1?p.incoming[0].before:'');
      placementDetails.textContent=p.complex?'Сложное размещение: измените его через полный API. Сохранённые правила не будут обрезаны.':
        p.rules.map(r=>(r.type==='deadline'?'Срок до ':'Начать не ранее ')+r.at+' ['+r.strength+']').join('; ')+
        (p.incoming[0]?.minDelayDays!==undefined?' · Интервал после предшественника: '+p.incoming[0].minDelayDays+' дн.':'');
      updateControls();
    }
    function focus(){
      const n=selected();if(!n)return;activeId=n.id;
      if(selectedFile()===view.graphFile)graphTarget.value=n.id;
      graphNote.value=fields.note.value;
      fields.title.value=n.title;
      fields.recommended.value=(n.canonBlock?.recommended||[]).map(c=>c.text).join('\n');
      fields.contraindicated.value=(n.canonBlock?.contraindicated||[]).map(c=>c.text).join('\n');
      const completion=view.sources.completion?.[selectedFile()]?.[n.id];
      details.textContent=n.id+' · '+n.kind+' · '+(n.status||'active')+
        (completion?.complete&&!completion.historyPending?' · выполнено':completion?.historyPending?' · результат ожидает записи writer':' · не завершено')+
        (n.projectionOf&&completion?.ownerRef?' · владелец: '+completion.ownerRef.graphFile:'')+
        (n.qrpe?.length?'\nQRPE: '+n.qrpe.map(q=>'['+q.status+'] '+q.text).join('; '):'')+
        (n.reconsiderationPolicy?.mode==='protected'?' · защищено: ручная запись недоступна':'');
      const placements=view.sources.plan.steps.filter(s=>{
        const ref=s.actionRef||s.requirementRef;
        return ref?.nodeId===n.id&&ref.graphFile===selectedFile()&&ref.identitySpace===graph().identitySpace;
      });
      optionsFor(fields.placement,[['','Выберите размещение'],...placements.map(s=>[s.id,s.title+' · '+s.id])],
        placements.length===1?placements[0].id:'');
      loadPlacement();
      childBox.replaceChildren();dispositionFields.length=0;
      for(const e of graph().edges.filter(e=>e.type==='INTRODUCES'&&e.from===n.id&&!e.archived)){
        const row=make('label',graph().nodes.find(n=>n.id===e.to)?.title||e.to,childBox);
        const select=make('select',undefined,row);optionsFor(select,[['','Выберите судьбу R'],['retain_supported','Сохранить: поддержана другим выбранным Action'],['deactivate','Деактивировать: нет других зависимостей']],'');
        dispositionFields.push({id:e.to,select});
      }
      updateControls();
    }
    target.onchange=focus;fields.placement.onchange=loadPlacement;
    function reference(file,id){return {graphFile:file,identitySpace:view.sources.graphs[file]?.identitySpace,nodeId:id};}
    function nodeAt(ref){return view.sources.graphs[ref.graphFile]?.identitySpace===ref.identitySpace?
      view.sources.graphs[ref.graphFile].nodes.find(n=>n.id===ref.nodeId):null;}
    function editPlacement(ref,stepId){
      if(!view.sources.graphs[ref.graphFile]||!nodeAt(ref))return;
      if(ref.graphFile!==view.graphFile&&!view.capabilities?.includes('plan.place.from-read-sources')){status.textContent='Для размещения из другого графа обновите локальный Helper.';return;}
      fields.graph.value=ref.graphFile;fillTargets(ref.nodeId);
      if(stepId){fields.placement.value=stepId;loadPlacement();}
      editor.open=true;editor.scrollIntoView?.({block:'nearest',behavior:'smooth'});
    }
    async function navigate(ref){
      try{
        const origin=declarationFor(view,ref);
        if(origin.ref.graphFile===view.graphFile||view.capabilities?.includes('plan.place.from-read-sources')){fields.graph.value=origin.ref.graphFile;fillTargets(origin.ref.nodeId);}
        if(!options.onNavigate)throw Error('Переход доступен в подключённом Viewer');
        await options.onNavigate(origin.ref,view);
      }catch(e){status.textContent='Не удалось открыть объявление: '+e.message;status.classList.add('wf-error');}
    }
    function declarationLink(parent,ref,label='Открыть блок в графе ↗'){
      let verified=null,problem=null;
      try{verified=declarationFor(view,ref);}catch(error){problem=error.message;}
      const button=make('button',label,parent);button.classList.add('wf-open-graph');
      button.setAttribute('data-node-id',ref.nodeId);
      button.setAttribute('data-graph-file',ref.graphFile);
      button.disabled=!verified||!options.onNavigate;
      button.title=verified?'Открыть объявление и выделить блок в графе':
        'Переход недоступен: '+(problem||'Viewer не подключён');
      button.onclick=()=>navigate(ref);
      return button;
    }
    const refKey=ref=>[ref.graphFile,ref.identitySpace,ref.nodeId].join('|');
    function entityKey(ref){try{return refKey(declarationFor(view,ref).ref);}catch{return refKey(ref);}}
    function material(card,node,historical=false){
      if(node.kind==='action'||node.kind==='option'){
        const canon=make('details',undefined,card);canon.classList.add('wf-canon');
        canon.open=!historical;
        const positive=node.canonBlock?.recommended||[],negative=node.canonBlock?.contraindicated||[];
        make('summary',(node.kind==='option'?'Канон варианта решения':historical?'Канон на момент записи':'Канон Action')+' (+'+positive.length+'/−'+negative.length+')',canon);
        for(const [label,rows] of [['Когда подходит',positive],['Когда не подходит',negative]]){
          const block=make('div',undefined,canon);block.classList.add('wf-canon-case');
          block.setAttribute('data-valence',label==='Когда подходит'?'positive':'negative');
          make('strong',label,block);const ul=make('ul',undefined,block);
          if(!rows.length)make('li','Не заполнено',ul);
          for(const c of rows)make('li',c.text,ul);
        }
      }
      const issues=node.qrpe||[],open=issues.filter(q=>!['closed','resolved','invalidated'].includes(q.status));
      const qrpe=make('details',undefined,card);qrpe.classList.add('wf-qrpe');qrpe.open=!historical&&open.length>0;
      make('summary',(historical?'QRPE на момент записи':'QRPE')+' · '+open.length+' открыто / '+issues.length,qrpe);
      if(!issues.length)make('p','Записей QRPE нет.',qrpe);
      for(const q of issues)make('p','['+q.status+'] '+q.text,qrpe);
      if(historical&&open.length){const warning=make('p',open[0].text,card);warning.classList.add('wf-qrpe-preview');}
    }
    function card(parent,ref,{row=null,variant=false,historical=false,event=null,title=null,variants=true}={}){
      const local=nodeAt(ref);let origin=null;try{origin=declarationFor(view,ref);}catch{}
      const n=historical?(event?.nodeSnapshot||local):origin?.node||local;
      if(!n){make('p','Узел недоступен: '+ref.nodeId,parent);return;}
      const article=make('article',undefined,parent);article.classList.add('wf-card');article.classList.add(n.kind);
      article.setAttribute('data-node-id',n.id);article.setAttribute('data-graph-file',ref.graphFile);
      article.setAttribute('data-status',n.status||'active');
      article.setAttribute('data-placement-id',row?.stepId||'');article.setAttribute('data-context',variant?'variant':historical?'history':'placement');
      const kind=n.kind==='action'?'Action / способ':n.kind==='option'?'Option / вариант решения':'R / цель';
      const state={selected:'выбран',candidate:'кандидат',potential:'предварительная',active:'активная',superseded:'пересмотрен',inactive:'неактивная'}[n.status]||n.status||'';
      const placements=view.future.filter(r=>entityKey(r.graphRef||reference(view.graphFile,r.nodeId))===entityKey(ref));
      const isPlaced=placements.length>0;
      const meta=make('small',undefined,article);meta.classList.add('wf-card-meta');
      make('span',kind,meta).classList.add('wf-kind-badge');
      if(state)make('span',historical?'На момент записи: '+state:state,meta).classList.add('wf-state-badge');
      if(variant){
        const chosen=n.kind==='option'&&origin?.graph?.nodes?.some(d=>d.kind==='decision'&&
          d.selectedOptionId===n.id&&['committed','selected-in-example-only'].includes(d.status));
        make('span',n.kind==='option'?(chosen?'выбран в Decision (не Action)':'альтернатива Decision'):
          isPlaced?'размещён отдельно':'вариант Action, не размещён',meta);
      }
      if(event){
        article.setAttribute('data-event-kind',event.kind);classifyEvent(article,event);
        make('span',eventLabels[event.kind]||event.kind,meta).classList.add('wf-event-badge');
        eventTime(article,event.recordedAt);
      }
      const open=make('button',title||n.title,article);open.classList.add('wf-card-title');open.onclick=()=>navigate(ref);
      open.disabled=!origin||!options.onNavigate;open.title=origin?'Открыть место объявления в графе':'Объявление недоступно в подключённой сессии';
      make('small',n.id,article);
      if(n.kind==='action'&&origin&&!variant){
        const goalRef={...origin.ref,nodeId:origin.contextRootId},goal=nodeAt(goalRef);
        if(goal){
          const context=make('p','Для цели: ',article),link=make('button',goal.title,context);link.classList.add('wf-card-goal');
          link.onclick=()=>navigate(goalRef);link.disabled=!options.onNavigate;
          if(!view.future.some(r=>entityKey(r.graphRef||reference(view.graphFile,r.nodeId))===entityKey(goalRef)))
            make('small','Цель показана для контекста и не размещена.',context);
        }
      }
      if(row){
        for(const rule of row.timeConstraints||[])make('p',(rule.type==='deadline'?'Срок до ':'Начать не ранее ')+rule.at+' ['+rule.strength+']',article);
        for(const link of row.sequence||[]){
          const sid=link.after===row.stepId?link.before:link.after,step=view.sources.plan.steps.find(s=>s.id===sid);
          const targetRef=step?.actionRef||step?.requirementRef,other=targetRef&&nodeAt(targetRef);
          make('p',(link.after===row.stepId?'После: ':'Перед: ')+(other?.title||step?.title||sid)+
            (link.minDelayDays!==undefined?' · интервал '+link.minDelayDays+' дн.':''),article);
        }
      }
      if(event?.note){const note=make('p',event.note,article);note.classList.add('wf-result-note');}
      if(historical&&!event?.materialSnapshotAvailable)
        make('p','Канон и QRPE на момент записи не сохранены. Текущий материал доступен по переходу в граф.',article);
      else if(historical||origin||!n.projectionOf)material(article,n,historical);
      else make('p','Канон и QRPE владельца недоступны в этой сессии.',article);
      if(!variant)declarationLink(article,ref);
      if(!historical&&!options.readOnly&&n.kind!=='option'){
        const placement=row||(variant?placements[0]:null),placementRef=placement?.graphRef||ref;
        const edit=make('button',variant&&!isPlaced?'Разместить':variant&&placements.length>1?'К первому размещению':'Изменить размещение',article);
        const selectable=n.kind!=='action'||n.status==='selected';
        edit.disabled=!selectable||busy||!!pending||!(view.permissions||[]).includes('plan.edit');
        edit.onclick=()=>editPlacement(placementRef,placement?.stepId);edit.classList.add('wf-card-place');
        const inAuthorizedGraph=placementRef.graphFile===view.graphFile||!!view.capabilities?.includes('plan.place.from-read-sources');
        const allowed=selectable&&inAuthorizedGraph;
        cardControls.push({button:edit,allowed});if(!allowed){edit.disabled=true;
          edit.title=!selectable?'Сначала выберите Action в графе. Сам Plan не выбирает Action.':
            'Для размещения из другого графа обновите локальный Helper';}
      }
      if(variants&&origin&&['requirement','action'].includes(n.kind)){
        const alternatives=[],seen=new Set();
        const context=origin.contextRootId;
        for(const [file,source] of Object.entries(view.sources.graphs)){
          if(source.identitySpace!==origin.ref.identitySpace)continue;
          const driverIds=n.kind==='requirement'?[n.id]:[context];
          for(const edge of source.edges.filter(e=>['DRIVES','OPTION_FOR'].includes(e.type)&&
              driverIds.includes(e.from)&&!e.archived)){
            const child=source.nodes.find(a=>a.id===edge.to&&
              ['action','option'].includes(a.kind));
            // Retired alternatives are still helpful for comparing canons;
            // their status is shown, never converted to Plan placement.
            if(!child||child.id===n.id)continue;
            const ref=reference(file,child.id),key=refKey(ref);
            if(!seen.has(key)){seen.add(key);alternatives.push({node:child,ref});}
          }
        }
        if(alternatives.length){
          const chain=make('details',undefined,article);chain.classList.add('wf-variants');
          chain.open=true;
          const kinds=new Set(alternatives.map(a=>a.node.kind));
          const text=kinds.has('action')?'Способы Action для этой цели — канон каждого, выбор ≠ выполнение':
            'Варианты Decision — канон каждого; это не исполняемые Actions';
          make('summary',text+' · '+alternatives.length,chain);
          const list=make('div',undefined,chain);list.classList.add('wf-variant-list');
          for(const alternative of alternatives)card(list,alternative.ref,{variant:true,historical:false,variants:false});
        }
      }
      return article;
    }
    function classifyEvent(article,event){
      const description={
        graph_created:['НОВЫЙ GRAPH','Создан действительный Graph owner, не выполнена цель'],
        context_added:['ДОБАВЛЕН КОНТЕКСТ','Сохранено основание/условие выбора способа, не Action и не подцель'],
        context_link_added:['КОНТЕКСТНАЯ СВЯЗЬ','Контекст подключён к Action и показывается в полном режиме связей'],
        action_added:['НОВЫЙ ACTION','Добавлен способ-кандидат. Это не выбор и не выполнение'],
        requirement_added:['НОВАЯ R','Добавлено активное объявление Requirement. Это не достижение'],
        requirement_prepared:['ПОТЕНЦИАЛЬНАЯ R','Создан кандидат/потенциальная R, ещё не введённая выбранным Action'],
        requirement_activated:['АКТИВИРОВАНА R','Requirement переведена в активное состояние. Это не достижение'],
        requirement_deactivated:['ДЕАКТИВИРОВАНА R','Requirement исключена из активной работы, но история сохранена'],
        action_removed:['УДАЛЁН ACTION','Удалена декларация Action — не исполнение и не отзыв результата'],
        requirement_removed:['УДАЛЕНА R','Удалена декларация Requirement — не достигнута цель'],
      };
      const diff=event.kind==='graph_saved'&&description[event.changeKind];
      const family=diff?{...historyKind(event.kind),label:diff[0],description:diff[1]}:
        historyKind(event.kind);
      article.classList.add('wf-event-'+family.group);
      article.setAttribute('data-event-family',family.group);
      const head=article.querySelector?.('.wf-card-meta')||article;
      const badge=make('span',family.label,head);badge.classList.add('wf-event-family');
      badge.title=family.description;
      if(event.exampleOnly)make('small','Учебное событие, не подтверждённое журналом владельца',article);
    }
    function renderReformulation(parent,r){
      if(r.kind!=='requirement_reformulated')return;
      const section=make('section',undefined,parent);section.classList.add('wf-reformulation');
      const before=r.previousRequirementSnapshot||r.nodeSnapshot;
      const after=r.newRequirementSnapshot;
      if(!before||!after){make('p','Исторический снимок «было / стало» недоступен; не реконструируем его из текущего графа.',section);return;}
      make('strong','Переформулировка Requirement · '+r.targetId,section);
      for(const field of new Set([...Object.keys(before),...Object.keys(after)])){
        if(['id','kind','revision'].includes(field)||JSON.stringify(before[field])===JSON.stringify(after[field]))continue;
        make('p','Было ('+field+'): '+(typeof before[field]==='object'?JSON.stringify(before[field]):before[field]??'—'),section);
        make('p','Стало ('+field+'): '+(typeof after[field]==='object'?JSON.stringify(after[field]):after[field]??'—'),section);
      }
      make('small','Событие изменения Graph. Зависимые Actions и каноны требуют повторной проверки в Gendocen.',section);
    }
    function renderReconsideration(parent,r){
      if(r.kind!=='action_reconsidered')return;
      const panel=make('div',undefined,parent);panel.classList.add('wf-action-switch');
      const transition=r.transition;
      if(!transition){
        make('p','Action пересмотрен. Механизм отмены последствий и новый способ не указаны в исторической записи.',panel);
        return;
      }
      const actionName=id=>Object.values(view.sources?.graphs||{}).flatMap(g=>g.nodes||[])
        .find(n=>n.id===id)?.title||id;
      make('strong','Смена: '+actionName(r.targetId)+' → '+actionName(transition.replacementActionId),panel);
      const cancellation=transition.cancellation;
      if(cancellation?.mode==='no_additional_action')
        make('p','Отмена последствий: дополнительных действий не потребовалось (зафиксированная оценка). '+cancellation.reason,panel);
      else if(cancellation?.mode==='compensating_action')
        make('p','Отмена последствий: выполнен Action «'+actionName(cancellation.actionId)+'».'+
          ' Событие результата: '+cancellation.executionEventId+'. '+cancellation.reason,panel);
      make('small','Пересмотр, выбор замены и компенсация — разные факты. Запись пересмотра не выполняет действий.',panel);
    }
    const changeLabels={graph_created:'Создан рабочий Graph',
      context_added:'Добавлен контекст',context_link_added:'Установлена связь контекста с Action',
      action_added:'Добавлен кандидат Action',
      requirement_added:'Создана Requirement',requirement_prepared:'Подготовлена Requirement',
      requirement_activated:'Активирована Requirement',requirement_deactivated:'Деактивирована Requirement',
      action_removed:'Удалён Action',
      requirement_removed:'Удалена Requirement'};
    function historicalDisplay(historyRows){
      // A writer transaction may yield one technical graph_saved row and one
      // semantic Action/Requirement event. Keep both in provenance, show one
      // primary operation card with an expandable technical save record.
      const technical=new Map(),semantic=new Set();
      const transactionKey=r=>r.transactionId&&r.graphFile?
        r.transactionId+'\0'+r.graphFile:null;
      for(const row of historyRows){
        const key=transactionKey(row);if(!key)continue;
        if(row.kind==='graph_saved')technical.set(key,row);
        else if(!row.kind.startsWith('plan_'))semantic.add(key);
      }
      const retained=new Set();
      return historyRows.flatMap(row=>{
        const key=transactionKey(row);
        if(row.kind==='graph_saved'&&key&&semantic.has(key))return [];
        if(key&&row.kind!=='graph_saved'&&semantic.has(key)&&!retained.has(key)){
          retained.add(key);
          return [{...row,technicalSave:technical.get(key)||null}];
        }
        return [row];
      });
    }
    function renderIntroducedRequirements(article,r){
      if(r.kind!=='action_selected')return;
      const section=make('section',undefined,article);section.classList.add('wf-introduced-requirements');
      if(!Array.isArray(r.introducedRequirements)){
        make('small','Снимок введённых подцелей из транзакции недоступен. Не восстанавливаем их по текущему графу.',section);
        return;
      }
      if(!r.introducedRequirements.length){
        make('small','Выбор Action не вводил новых Requirements в этой транзакции.',section);
        return;
      }
      make('strong','В рамках этого выбора введены Requirements:',section);
      for(const item of r.introducedRequirements){
        const mode=item.introductionMode==='created'?'создана и активирована':
          item.introductionMode==='activated'?'активирована из '+item.previousStatus:
          'связана с Action (уже существовала)';
        const role=item.childRole==='subgoal'?'Подцель':
          item.childRole==='method_correctness'?'Проверка корректности способа':'Requirement';
        const line=make('div',undefined,section);line.classList.add('wf-introduced-requirement');
        make('span',role+' '+item.nodeId+' — '+mode+' · '+item.title,line);
        const linked=reference(item.graphFile||r.graphFile||view.graphFile,item.nodeId);
        if(nodeAt(linked))declarationLink(line,linked,'Открыть R в графе ↗');
        else make('small','Ранее введённый узел недоступен в подключённом Graph owner.',line);
      }
      make('small','Введение или активация подцели ≠ размещение во времени и ≠ достижение цели.',section);
    }
    function renderSaveDetails(article,r){
      const save=r.technicalSave||(r.kind==='graph_saved'?r:null);
      if(!save)return;
      const detail=make('details',undefined,article);detail.classList.add('wf-save-details');
      make('summary','Технические сведения о транзакции',detail);
      const prev=save.previousRevision;
      const revision=save.revision;
      if(revision!=null)make('p','Ревизия Graph: '+(prev==null?'создание → ':'r'+prev+' → ')+'r'+revision,detail);
      if(save.transactionId)make('p','Транзакция: '+save.transactionId,detail);
      if(save.changed){
        const listed=save.changed.nodes||[];
        if(listed.length)make('p','Затронутые узлы: '+listed.join(', '),detail);
        if(save.changed.edges?.length)make('p','Затронутые связи: '+save.changed.edges.join(', '),detail);
      }
      make('small','Сведения из принятого журнала writer. Дополнительного выполнения Action эта запись не означает.',detail);
    }
    const eventLabels={module_event:'Событие модуля',module_plan_changed:'Изменение Plan модулем',
      modules_configured:'Изменено подключение модулей',graph_saved:'Изменён граф',action_executed:'Выполнен Action',
      requirement_achieved:'Достигнута цель',action_withdrawn:'Отозван Action',
      decision_selected:'Учебный выбор решения',context_discovered:'Выявлен контекст',
      requirement_reparented:'Уточнена связь Requirement',
      plan_created:'Создан Plan',plan_placement_saved:'Размещён шаг Plan',
      plan_placement_removed:'Удалено размещение Plan',
      requirement_reformulated:'Переформулирована Requirement',
      requirement_deactivated:'Requirement деактивирована',
      requirement_activated:'Requirement активирована',action_selected:'Выбран Action',
      action_reconsidered:'Action пересмотрен',action_requirement_linked:'Связан Action и Requirement',
      decision_revised:'Решение пересмотрено'};
    function eventTime(parent,at){
      const time=make('time',undefined,parent);time.classList.add('wf-event-time');
      const value=at&&new Date(at);
      time.textContent=value&&!Number.isNaN(value.getTime())?
        'Записано '+value.toLocaleString('ru-RU',{dateStyle:'medium',timeStyle:'short'}):
        (at&&/^T[0-9]+$/.test(at)?'Учебный момент '+at:'Время записи неизвестно');
      if(at&&!/^T[0-9]+$/.test(at))time.setAttribute('datetime',at);
      if(at)time.title=at;
    }
    function renderPlan(){
      cardControls.length=0;firstPlannedCard=null;
      history.replaceChildren();make('h3','История',history);
      if(!view.history.length)make('p',view.localPreview&&!view.examplePreview?'В доступных событиях графа записей нет; журнал writer не загружен.':'Записей ещё нет.',history);
      let lastDay=null;
      for(const r of historicalDisplay(view.history)){
        const date=r.recordedAt&&new Date(r.recordedAt),valid=date&&!Number.isNaN(date.getTime());
        const day=valid?date.toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'}):
          r.symbolicTime?'Учебная последовательность':'Без времени записи';
        if(day!==lastDay){const divider=make('h4',day,history);divider.classList.add('wf-day');lastDay=day;}
        const ref=reference(r.graphFile||view.graphFile,r.targetId),node=nodeAt(ref);
        if(historyKind(r.kind).group==='result'&&
          ['action','requirement'].includes((r.nodeSnapshot||node)?.kind)){
          card(history,ref,{historical:true,event:r,title:r.title||r.nodeSnapshot?.title||node?.title,variants:false});
        }else{
          const event=make('article',undefined,history);event.classList.add('wf-history-event');event.classList.add('wf-card');
          event.setAttribute('data-context','history');event.setAttribute('data-event-kind',r.kind);
          if(r.changeKind)event.setAttribute('data-change-kind',r.changeKind);
          classifyEvent(event,r);
          make('strong',(r.kind==='graph_saved'&&changeLabels[r.changeKind])||eventLabels[r.kind]||r.kind,event);
          eventTime(event,r.recordedAt||r.symbolicTime);
          make('p',r.summary||r.title||r.note||'Запись об изменении графа.',event);
          if(r.kind==='graph_saved'&&r.note&&r.note!==r.summary)
            make('p','Заметка автора: '+r.note,event);
          renderReformulation(event,r);
          renderReconsideration(event,r);
          renderIntroducedRequirements(event,r);
          renderSaveDetails(event,r);
          const links=make('div',undefined,event);links.classList.add('wf-changed-nodes');
          const ids=[...(r.changed?.nodes||[]),...(r.technicalSave?.changed?.nodes||[]),
            r.changeTargetId,r.targetId,r.actionId,r.requirementId,
            r.reviewActionId,r.transition?.replacementActionId,r.transition?.cancellation?.actionId];
          for(const id of new Set(ids.filter(Boolean))){
            const changedRef=reference(r.graphFile||view.graphFile,id),changed=nodeAt(changedRef);
            if(!changed||!['action','requirement'].includes(changed.kind))continue;
            declarationLink(links,changedRef,'Открыть блок в графе ↗ '+changed.title);
          }
          if(r.note&&r.note!==(r.summary||r.title)){const note=make('p',r.note,event);note.classList.add('wf-result-note');}
          if(r.targetId&&!node)make('small','Узел '+r.targetId+' недоступен в подключённом графе.',event);
        }
      }
      future.replaceChildren();
      const boundary=make('header',undefined,future);boundary.classList.add('wf-plan-boundary');
      make('small','Конец истории · далее запланированное',boundary);
      make('h3','План во времени',boundary);
      if(view.examplePreview&&view.relatedActionExampleSlug&&options.onOpenExample){
        const jumpExample=make('button','Открыть отдельный учебный граф с Actions и их канонами →',boundary);
        jumpExample.classList.add('wf-example-switch');
        jumpExample.onclick=()=>options.onOpenExample(view.relatedActionExampleSlug);
      }
      make('p',view.examplePreview?(view.authoredExamplePreview?
        'Учебный снимок: явно размещённые шаги · '+view.future.length+' (не пользовательский Plan owner).':
        'Учебный пример: запланированных шагов нет. Это пример графа, не сохранённый пользовательский Plan.'):
        view.localPreview?'Сохранённый Plan owner не подключён; размещения не подтверждены.':
        view.future.length?'Явно размещённые цели и Actions · '+view.future.length:
        'Пока нет запланированных целей или Actions.',boundary);
      for(const row of view.future){
        const article=card(future,row.graphRef||reference(view.graphFile,row.nodeId),{row});
        if(!firstPlannedCard&&article){firstPlannedCard=article;article.setAttribute('tabindex','-1');}
      }
      if(view.unresolved.length)make('p','Не разрешены ссылки: '+view.unresolved.map(r=>r.nodeId).join(', '),future);
      unplaced.replaceChildren();
      const inventory=planningInventory(view);
      const group=make('details',undefined,unplaced);group.classList.add('wf-unplaced-group');
      const summary=make('summary','Без места во времени · '+inventory.unplaced.length,group);
      summary.title='Актуальные цели и выбранные Actions, которым ещё не задано место в Plan';
      group.open=inventory.unplaced.length<=16;
      make('p','Сущности из Graph без размещения в Plan. Это НЕ доказательство их невыполнения. Выполнение определяется только настоящими событиями и расчётом зависимостей Graph.',group);
      const list=make('div',undefined,group);list.classList.add('wf-unplaced-list');
      for(const row of inventory.unplaced){
        const ref={graphFile:row.graphFile,identitySpace:row.identitySpace,nodeId:row.nodeId};
        const article=card(list,ref,{variants:true});
        if(!article)continue;
        article.classList.add('wf-unplaced-card');
        make('small',row.verification==='completion-not-verified'?
          'Результат не проверен по writer':'Результат пока не подтверждён',article);
      }
      if(inventory.needsVerification.length)
        make('p','Требуют проверки результата/журнала: '+inventory.needsVerification.length+
          '. Не помечены выполненными автоматически.',unplaced);
      jump.disabled=!firstPlannedCard;
      jump.title=firstPlannedCard?'Перейти к первому запланированному блоку':'В плане пока нет доступных блоков';
    }
    async function install(next){
      view=next;
      optionsFor(fields.graph,Object.entries(view.sources.graphs).filter(([file,g])=>g.identitySpace===view.sources.graphs[view.graphFile].identitySpace&&(file===view.graphFile||view.capabilities?.includes('plan.place.from-read-sources')))
        .map(([file,g])=>[file,(g.title||file)+' · '+file]),fields.graph.value||view.graphFile);
      optionsFor(graphTarget,view.sources.graphs[view.graphFile].nodes.filter(n=>['action','requirement'].includes(n.kind)).map(n=>[n.id,n.title+' · '+n.id]),activeId);
      fillTargets();renderPlan();
      heading.textContent=view.title;grid.hidden=false;editor.hidden=!!options.readOnly;
      grantPanel.hidden=!!options.readOnly||!view.grantAdminAvailable||!transport.admin;
      if(grantPanel.hidden){grantSecret.textContent='';grants=[];grantRevision=null;grantPending=null;}
      grantControls();
      const owner=view.sources.graphs[view.graphFile],core=owner.coreModel==='rdg-core-v1';
      for(const child of graphEditor.children)if(child!==corePane&&child.tagName?.toLowerCase()!=='summary')child.hidden=core;
      corePane.hidden=!core;
      if(core){corePane.replaceChildren();coreEditor=mountCore(corePane,owner,{document:doc,readOnly:!!options.readOnly,
        focusId:coreFocusId,onFocus:id=>{coreFocusId=id;},onCommand:async request=>{
          if(workspace?.contextId!=null)request.contextId=workspace.contextId;
          const result=await send(request);if(!result?.saved)throw Error(status.textContent);return result;}});}
      if(options.onGraph)await options.onGraph(owner,view);
    }
    async function refreshView(){
      if(contextSelectionRequired&&!workspace){updateControls();return;}
      if(busy)return;busy=true;updateControls();status.textContent=options.localPreview?'Открываю учебную временную ленту…':options.readOnly?'Открываю учебный план…':'Запрашиваю данные локального Helper…';syncStatus();
      try{
        const next=await transport.read(workspace?.contextId);
        if(workspace){
          if(next.graphFile!==workspace.graphFile||
            (workspace.planFile!=null&&next.planFile!==workspace.planFile)||
            next.sources?.graphs?.[next.graphFile]?.identitySpace!==workspace.identitySpace||
            (workspace.contextId!=null&&next.contextId!==workspace.contextId))
            throw Error('PLAN_WORKSPACE_IDENTITY_MISMATCH: Helper вернул другой рабочий граф.');
        }
        await install(next);
        status.textContent=next.storedPlanReadOnly?'Сохранённый Plan из файла · только чтение; полный журнал истории и результаты выполнения требуют Helper.':options.localPreview?(next.examplePreview?'Учебный пример · только чтение; собственный Plan-файл у примера отсутствует.':'Нет подключённого Plan owner; размещения не подтверждены.'):options.readOnly?'Учебный снимок · только чтение.':'Данные перечитаны.';status.classList.remove('wf-error');
      }
      catch(e){status.textContent='Не удалось загрузить данные: '+e.message+(view?' Показаны ранее загруженные данные.':'');status.classList.add('wf-error');}
      finally{busy=false;updateControls();}
    }
    async function switchWorkspace(next,missingMessage='Для этого рабочего графа план пока не подключён.'){
      if(busy||pending||grantBusy||grantPending)throw Error('Завершите прежний запрос перед переключением рабочего графа.');
      // Drop the previous source *before* attempting a new read. An error
      // must never leave another workspace's Plan visible or writable.
      contextSelectionRequired=true;workspace=next;view=null;activeId=null;heading.textContent=next?.title||'План во времени';
      grid.hidden=true;editor.hidden=true;grantPanel.hidden=true;grantSecret.textContent='';
      grants=[];grantRevision=null;firstPlannedCard=null;
      history.replaceChildren();future.replaceChildren();unplaced.replaceChildren();cardControls.length=0;
      if(options.graphContainer)options.graphContainer.hidden=true;
      status.textContent=next?'Подключаю план выбранного рабочего графа…':missingMessage;
      status.classList.toggle('wf-error',!next);syncStatus();updateControls();
      if(next)await refreshView();
      return !!view;
    }
    function request(action){
      const n=selected();if(!n)throw Error('Выберите сущность графа');
      const random=randomId();
      const req={...(workspace?.contextId!=null?{contextId:workspace.contextId}:{}),action,transactionId:'ui-'+random,nodeId:n.id,note:fields.note.value,
        expectedGraphRevision:graph().revision,expectedPlanRevision:view.sources.plan.revision};
      if(['add_action','edit_title','prepare_requirement'].includes(action))req.title=fields.title.value;
      if(['add_action','edit_canon'].includes(action)){req.recommended=fields.recommended.value;req.contraindicated=fields.contraindicated.value;}
      if(action==='add_action')req.actionType=fields.actionType.value;
      if(action==='prepare_requirement')req.childRole=fields.childRole.value;
      if(action==='add_qrpe')req.title=fields.qrpe.value;
      if(action==='place'){if(selectedFile()!==view.graphFile)req.graphFile=selectedFile();req.at=fields.at.value;req.afterStepId=fields.after.value;req.stepId=fields.placement.value;}
      if(action==='unplace')req.stepId=fields.placement.value;
      if(action==='withdraw'){
        req.dispositions=dispositionFields.map(d=>{
          if(!d.select.value)throw Error('Укажите судьбу каждой дочерней R');
          const result={requirementId:d.id,effect:d.select.value,reason:fields.note.value};
          if(d.select.value==='deactivate')result.downstreamScope='single_graph_verified';
          else result.supportingActionIds=graph().edges.filter(e=>e.type==='INTRODUCES'&&e.to===d.id&&e.from!==n.id&&!e.archived&&
            graph().nodes.some(n=>n.id===e.from&&n.status==='selected')).map(e=>e.from);
          return result;
        });
      }
      return req;
    }
    async function run(action){
      if(busy)return;
      if(!['place','unplace'].includes(action)&&selectedFile()!==view?.graphFile){status.textContent='Изменять можно только подключённый граф. Выберите его сущность на вкладке графа.';return;}
      if(pending){status.textContent='Сначала проверьте исход предыдущего запроса или повторите тот же запрос.';return;}
      try{return await send(request(action));}
      catch(e){status.textContent=e.message;status.classList.add('wf-error');syncStatus();}
    }
    async function send(req){
      if(busy||!req)return;busy=true;pending=req;let accepted=false;updateControls();status.textContent='Сохранение…';syncStatus();
      try{
        const result=await transport.write(req);
        if(!result.saved)throw Error('Writer не подтвердил сохранение');
        pending=null;accepted=true;
        if(req.action==='add_action')activeId='A-'+req.transactionId;
        if(req.action==='prepare_requirement')activeId='R-'+req.transactionId;
        if(result.view)await install(result.view);
        status.textContent=result.refreshError?'Запись сохранена, но перечитать данные не удалось: '+result.refreshError:
          result.replayed?'Предыдущая запись подтверждена; повторного действия нет.':'Запись сохранена и перечитана.';
        if(result.dependencyUpdate?.refreshed===false)
          status.textContent+=' '+result.dependencyUpdate.warning;
        else if(result.dependencyUpdate?.refreshed===true)
          status.textContent+=' Gendocen: зависимости обновлены; статусы проверки доступны во вкладке «Зависимости».';
        status.classList.toggle('wf-error',!!result.refreshError||result.dependencyUpdate?.refreshed===false);
        return result;
      }catch(e){
        if(e.definite)pending=null;
        status.textContent=accepted?'Запись сохранена, интерфейс не обновлён: '+e.message:(e.definite?'Запись отклонена: ':'Исход запроса не подтверждён; обновите данные и повторите тот же запрос: ')+e.message;
        status.classList.add('wf-error');
      }finally{busy=false;updateControls();}
    }
    updateControls();
    return {fields,buttons,refresh:refreshView,switchWorkspace,run,editPlacement,navigate,configureModule,
      focusCore(id){if(!coreEditor||!view?.sources.graphs[view.graphFile].coreModel)return false;coreEditor.focus(id);return true;},
      get switchBlocked(){return busy||!!pending||grantBusy||!!grantPending;},
      get view(){return view;},get pending(){return pending;},
      get busy(){return busy;},get status(){return status.textContent;},get text(){return container.textContent;}};
  }
  return {mount,mountCore,coreFocusedView,validateCoreSnapshot,fileTransport,declarationFor,localPlanPreview,localPlanFromOwner,planningInventory,historyKind};
});
