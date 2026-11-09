// ==UserScript==
// @name         R-D Graph Viewer
// @namespace    rdg.local
// @version      2.2.2
// @description  Local Requirements-Decisions JSON graph viewer
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @grant        GM_xmlhttpRequest
// @run-at       document-idle
// ==/UserScript==
// BEGIN GENERATED RDG WORKFLOW UI
/* Local manual workflow controller. Same Graph/Plan writers, no optimistic facts. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else{
    root.RDGWorkflowUI=api;
    const host=document.getElementById('rdg-viewer-root');
    if(host&&root.RDG_LOCAL_WORKFLOW){
      const base=new URL('./',location.href),session=root.RDG_SESSION;
      const request=async(path,body)=>{
        const response=await fetch(new URL(path,base),{method:body?'POST':'GET',credentials:'omit',
          redirect:'error',headers:{'X-RDG-Session':session,...(body?{'Content-Type':'application/json'}:{})},
          ...(body?{body:JSON.stringify(body)}:{})});
        const result=await response.json();
        if(!response.ok){const error=Error(result.error||'Запрос отклонён');error.definite=result.definite!==false;throw error;}
        return result;
      };
      const ui=api.mount(host.rdgWorkflow.attach(),{read:()=>request('state'),write:r=>request('command',r)},
        {document,onGraph:g=>host.rdgWorkflow.loadGraph(g)});
      root.RDG_LOCAL_EDITOR=ui;void ui.refresh();
    }
  }
})(globalThis,function(){
  'use strict';
  function fileTransport(directory,options={}){
    const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
    let descriptor=null;
    const readJson=async name=>JSON.parse(await (await directory.getFileHandle(name)).getFile().then(f=>f.text()));
    const writeJson=async(name,value)=>{
      const file=await directory.getFileHandle(name,{create:true}),writer=await file.createWritable();
      await writer.write(JSON.stringify(value));await writer.close();
    };
    async function exchange(kind,body){
      if(!descriptor){
        descriptor=await readJson('session.json');
        if(descriptor.schemaVersion!==1||descriptor.kind!=='rdg-local-manual-session'||!descriptor.active||typeof descriptor.session!=='string')
          throw Error('Выбрана неактивная папка сессии RDG');
      }
      const random=typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
      const id='io-'+random,request='request-'+id+'.json',ready='request-'+id+'.ready',response='response-'+id+'.json';
      await writeJson(request,{session:descriptor.session,kind,body});
      // The worker never reads a payload before its completed write/close marker.
      await writeJson(ready,{ready:true});
      const end=Date.now()+(options.timeoutMs||45000);
      while(Date.now()<end){
        let result;
        try{result=await readJson(response);}
        catch(e){if(e.name!=='NotFoundError')throw e;await pause(options.pollMs||150);continue;}
        for(const name of [ready,request,response]){
          try{await directory.removeEntry(name);}catch{/* cleanup failure never changes accepted outcome */}
        }
        if(!result.ok){const error=Error(result.error||'Запрос отклонён');error.definite=result.definite!==false;throw error;}
        return result.result;
      }
      throw Error('Время ожидания истекло. Проверьте, что локальный Helper запущен; исход записи пока неизвестен.');
    }
    return {read:()=>exchange('state',null),write:body=>exchange('command',body)};
  }
  function mount(container,transport,options={}){
    const doc=options.document||document,fields={},buttons={};
    let view=null,busy=false,pending=null,activeId=null;
    const make=(tag,text,parent)=>{const x=doc.createElement(tag);if(text!==undefined)x.textContent=text;
      if(parent)parent.appendChild(x);return x;};
    const heading=make('h2','План во времени и история',container);
    const status=make('div','Загрузка…',container);status.classList.add('wf-status');status.setAttribute('role','status');
    const refresh=make('button','Обновить',container);
    const grid=make('div',undefined,container);grid.classList.add('wf-grid');
    const editor=make('section',undefined,grid),future=make('section',undefined,grid),history=make('section',undefined,grid);
    make('h3','Работа с графом',editor);
    function field(name,label,tag='input',type='text'){
      const l=make('label',label,editor),x=make(tag,undefined,l);x.type=type;x.value='';
      x.setAttribute('aria-label',label);fields[name]=x;return x;
    }
    const target=field('target','Цель или Action','select');
    const details=make('p','',editor);
    field('title','Название');
    field('actionType','Тип нового Action','select');
    field('recommended','Когда способ подходит — по одному случаю на строку','textarea');
    field('contraindicated','Когда способ не подходит','textarea');
    field('childRole','Роль новой дочерней R','select');
    field('note','Основание изменения или результат выполнения','textarea');
    field('qrpe','Новая запись QRPE');
    field('at','Дата начала не ранее','input','date');
    field('after','После размещённой цели или Action','select');
    field('placement','Сохранённое размещение','select');
    const placementDetails=make('p',undefined,editor);
    const childBox=make('div',undefined,editor);make('p','При отзыве укажите судьбу каждой введённой R. Изменения примет только штатный writer.',childBox);
    const dispositionFields=[];
    const controls=make('div',undefined,editor);
    function button(name,title,action){
      const b=make('button',title,controls);b.onclick=()=>run(action);buttons[name]=b;return b;
    }
    button('add','Создать вариант Action','add_action');button('title','Изменить название','edit_title');
    button('canon','Записать канон','edit_canon');button('requirement','Добавить дочернюю R','prepare_requirement');
    button('qrpe','Добавить QRPE','add_qrpe');button('select','Выбрать Action','select');
    button('complete','Записать выполнение / достижение','complete');button('withdraw','Отозвать выполненный Action','withdraw');
    button('place','Разместить / изменить место','place');button('unplace','Снять размещение','unplace');
    buttons.retry=make('button','Повторить тот же запрос',controls);buttons.retry.onclick=()=>send(pending);
    buttons.refresh=refresh;refresh.onclick=()=>refreshView();
    function optionsFor(select,items,value){
      select.replaceChildren();for(const [id,title] of items){const o=make('option',title,select);o.value=id;}
      select.value=items.some(x=>x[0]===value)?value:(items[0]?.[0]||'');
    }
    optionsFor(fields.actionType,[['general','Обычный'],['decomposition','Выделение подцелей']],'general');
    optionsFor(fields.childRole,[['subgoal','Часть разбиения родительской цели'],['method_correctness','Нужно для корректного выполнения Action']],'subgoal');
    function graph(){return view?.sources.graphs[view.graphFile];}
    function selected(){return graph()?.nodes.find(n=>n.id===target.value);}
    function updateControls(){
      const n=selected(),perms=view?.permissions||[],graphWrite=p=>perms.includes('graph.write')||perms.includes('graph.'+p);
      const protectedGraph=view&&Object.values(view.sources.graphs).some(g=>g.nodes.some(n=>n.reconsiderationPolicy?.mode==='protected'));
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
      buttons.place.disabled=locked||!n||!perms.includes('plan.edit')||placementState().complex;
      buttons.unplace.disabled=locked||!fields.placement.value||!perms.includes('plan.edit');
      buttons.retry.disabled=busy||!pending;buttons.refresh.disabled=busy;
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
      fields.title.value=n.title;
      fields.recommended.value=(n.canonBlock?.recommended||[]).map(c=>c.text).join('\n');
      fields.contraindicated.value=(n.canonBlock?.contraindicated||[]).map(c=>c.text).join('\n');
      const completion=view.sources.completion?.[view.graphFile]?.[n.id];
      details.textContent=n.id+' · '+n.kind+' · '+(n.status||'active')+
        (completion?.complete&&!completion.historyPending?' · выполнено':completion?.historyPending?' · результат ожидает записи writer':' · не завершено')+
        (n.projectionOf&&completion?.ownerRef?' · владелец: '+completion.ownerRef.graphFile:'')+
        (n.qrpe?.length?'\nQRPE: '+n.qrpe.map(q=>'['+q.status+'] '+q.text).join('; '):'')+
        (n.reconsiderationPolicy?.mode==='protected'?' · защищено: ручная запись недоступна':'');
      const placements=view.sources.plan.steps.filter(s=>{
        const ref=s.actionRef||s.requirementRef;
        return ref?.nodeId===n.id&&ref.graphFile===view.graphFile&&ref.identitySpace===graph().identitySpace;
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
    function list(section,title,rows,empty){
      section.replaceChildren();make('h3',title,section);
      if(!rows.length){make('p',empty,section);return;}
      const ul=make('ul',undefined,section);for(const text of rows)make('li',text,ul);
    }
    async function install(next){
      view=next;
      optionsFor(target,graph().nodes.filter(n=>['action','requirement'].includes(n.kind)).map(n=>[n.id,n.title+' · '+n.kind+' · '+(n.status||'active')]),activeId);
      list(future,'Предстоит',view.future.map(r=>r.title+' · '+r.nodeId+
        (r.timeConstraints.length?' · '+r.timeConstraints.map(t=>t.at).join(', '):'')+
        (r.sequence.length?' · '+r.sequence.map(e=>e.before+' → '+e.after).join(', '):'')),'Нет предстоящих целей или Actions.');
      if(view.unresolved.length)make('p','Не разрешены ссылки: '+view.unresolved.map(r=>r.nodeId).join(', '),future);
      const labels={graph_saved:'Изменён граф',action_executed:'Выполнен Action',requirement_achieved:'Достигнута цель',action_withdrawn:'Отозван Action'};
      list(history,'История',view.history.map(r=>(labels[r.kind]||r.kind)+' · '+(r.title||r.summary||r.targetId||'')+
        (r.targetId?' · '+r.targetId:'')+' · '+(r.recordedAt||'Время неизвестно')),'Записей ещё нет.');
      heading.textContent=view.title+' · план и история';focus();
      if(options.onGraph)await options.onGraph(graph());
    }
    async function refreshView(){
      if(busy)return;busy=true;updateControls();
      try{await install(await transport.read());status.textContent='Данные перечитаны.';status.classList.remove('wf-error');}
      catch(e){status.textContent='Не удалось обновить: '+e.message;status.classList.add('wf-error');}
      finally{busy=false;updateControls();}
    }
    function request(action){
      const n=selected();if(!n)throw Error('Выберите сущность графа');
      const random=typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
      const req={action,transactionId:'ui-'+random,nodeId:n.id,note:fields.note.value,
        expectedGraphRevision:graph().revision,expectedPlanRevision:view.sources.plan.revision};
      if(['add_action','edit_title','prepare_requirement'].includes(action))req.title=fields.title.value;
      if(['add_action','edit_canon'].includes(action)){req.recommended=fields.recommended.value;req.contraindicated=fields.contraindicated.value;}
      if(action==='add_action')req.actionType=fields.actionType.value;
      if(action==='prepare_requirement')req.childRole=fields.childRole.value;
      if(action==='add_qrpe')req.title=fields.qrpe.value;
      if(action==='place'){req.at=fields.at.value;req.afterStepId=fields.after.value;req.stepId=fields.placement.value;}
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
      if(pending){status.textContent='Сначала проверьте исход предыдущего запроса или повторите тот же запрос.';return;}
      try{return await send(request(action));}
      catch(e){status.textContent=e.message;status.classList.add('wf-error');}
    }
    async function send(req){
      if(busy||!req)return;busy=true;pending=req;let accepted=false;updateControls();status.textContent='Сохранение…';
      try{
        const result=await transport.write(req);
        if(!result.saved)throw Error('Writer не подтвердил сохранение');
        pending=null;accepted=true;
        if(req.action==='add_action')activeId='A-'+req.transactionId;
        if(req.action==='prepare_requirement')activeId='R-'+req.transactionId;
        if(result.view)await install(result.view);
        status.textContent=result.refreshError?'Запись сохранена, но перечитать данные не удалось: '+result.refreshError:
          result.replayed?'Предыдущая запись подтверждена; повторного действия нет.':'Запись сохранена и перечитана.';
        status.classList.toggle('wf-error',!!result.refreshError);
        return result;
      }catch(e){
        if(e.definite)pending=null;
        status.textContent=accepted?'Запись сохранена, интерфейс не обновлён: '+e.message:(e.definite?'Запись отклонена: ':'Исход запроса не подтверждён; обновите данные и повторите тот же запрос: ')+e.message;
        status.classList.add('wf-error');
      }finally{busy=false;updateControls();}
    }
    updateControls();
    return {fields,buttons,refresh:refreshView,run,get view(){return view;},get pending(){return pending;},
      get status(){return status.textContent;},get text(){return container.textContent;}};
  }
  return {mount,fileTransport};
});
// END GENERATED RDG WORKFLOW UI
// BEGIN GENERATED RDG ROOT PROJECTION
/* Read-only root-Requirement projection for migration away from graph-set maps.
 * A folder is a navigation container; only typed graph edges establish lineage.
 * This does not import or promote a prepared graph into a writable project.
 */
(function(host, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else host.RDGRootProjection = api;
})(globalThis, function() {
  'use strict';
  const inactive = n => n?.active === false || ['inactive', 'superseded', 'rejected'].includes(n?.status);
  function index(manifest) {
    if (!manifest || !Array.isArray(manifest.graphs)) throw Error('Missing RDG graph sources');
    const bySlug = new Map();
    for (const item of manifest.graphs) {
      if (!item.graph) throw Error('Root projection needs bundled graph: ' + item.slug);
      if (bySlug.has(item.slug)) throw Error('Duplicate graph slug: ' + item.slug);
      bySlug.set(item.slug, item);
    }
    return bySlug;
  }
  // A root graph entry is a source graph not reached through another graph.
  // A same-requirement/refinement file is NOT automatically another project.
  function listEntries(manifest) {
    const bySlug = index(manifest);
    const downstream = new Set((manifest.relations || [])
      .filter(r => ['selected', 'prepared', 'potential', 'derived', 'same-requirement'].includes(r.relationKind))
      .map(r => r.to));
    return [...bySlug.values()].filter(item => {
      const root = item.graph.rootRequirementId;
      return root && item.graph.nodes.some(n => n.kind === 'requirement' && n.id === root) && !downstream.has(item.slug);
    }).map(item => ({kind: 'full-graph', slug: item.slug,
      rootRequirementId: item.graph.rootRequirementId,
      identitySpace: item.graph.identitySpace,
      folder: item.folder,
      title: item.presentation?.title || item.graph.title || item.title || item.slug,
      presentation: item.presentation || {}, file: item.file}));
  }
  function decisionActive(n, g) {
    if (!n || !g || inactive(n) || n.templateOnly === true || g.templateOnly === true) return false;
    return (n.status === 'committed' && g.exampleOnly !== true) ||
      (n.status === 'selected-in-example-only' && g.exampleOnly === true &&
      g.hypothetical === true && g.readOnly === true && g.selectedInProject === false);
  }
  // Every projection along the chain must be authorized, including its
  // canonical owner. Unavailable, cyclic and cross-project owners fail closed.
  function decisionGuard(bySlug, space) {
    return (decision, graph) => {
      let node=decision, owner=graph;
      const visited=new Set();
      while(true) {
        if(!decisionActive(node,owner)) return false;
        if(!node.projectionOf) return true;
        const ref=node.projectionOf, key=ref.graphSlug+'::'+ref.nodeId;
        if(visited.has(key))return false;
        visited.add(key);
        const next=bySlug.get(ref.graphSlug)?.graph;
        if(!next || next.identitySpace!==space || ref.nodeId!==node.id)return false;
        const canonical=next.nodes.find(n=>n.id===ref.nodeId&&n.kind==='decision');
        if(!canonical || node.selectedOptionId!==canonical.selectedOptionId)return false;
        node=canonical; owner=next;
      }
    };
  }
  // Read-only selection check for opt-in Action graphs; a source status alone
  // is not evidence that this Action was actually selected for this driver.
  function actionActive(action, graph, requirementId) {
    if (!action || !graph || graph.actionModel !== 'candidate-v6' ||
        action.kind !== 'action' || inactive(action) || action.status !== 'selected' ||
        graph.templateOnly === true || graph.exampleOnly === true) return false;
    const basis=action.selectionBasis;
    if (basis?.actionSnapshot?.id !== action.id || basis.actionSnapshot.status !== 'candidate' ||
        basis.driverSnapshot?.id !== requirementId) return false;
    const selected=(graph.events||[]).filter(ev=>ev.type==='action_selected' && ev.actionId===action.id);
    return selected.length===1 && selected[0].driverRequirementId===requirementId &&
      ['user','assistant'].includes(selected[0].by) &&
      typeof selected[0].note==='string' && selected[0].note.trim().length>0;
  }
  function project(manifest, rootSlug, {includePotential = true} = {}) {
    const bySlug = index(manifest);
    const entry = bySlug.get(rootSlug);
    if (!entry) throw Error('Unknown root graph: ' + rootSlug);
    const space = entry.graph.identitySpace, rootId = entry.graph.rootRequirementId;
    if (!space || !rootId) throw Error('Full root needs identitySpace and rootRequirementId');
    const sources = [...bySlug.values()].filter(it => it.graph.identitySpace === space);
    const activeCause=decisionGuard(bySlug,space);
    const records = new Map(), arcs = [], warnings = [];
    // projectionOf is a repeated representation, never a second R owner.
    for (const it of sources) for (const n of it.graph.nodes) {
      if (n.kind !== 'requirement' || inactive(n)) continue;
      const old = records.get(n.id);
      if (!old || old.node.projectionOf && !n.projectionOf)
        records.set(n.id, {node: n, source: it.slug});
    }
    if (!records.has(rootId)) throw Error('Root R missing: ' + rootId);
    const add = (from, to, kind, ref, source, childRole) => {
      if (!records.has(from) || !records.has(to) || from === to) return;
      arcs.push({from, to, kind, childRole, causeKind: ref.kind, causeId: ref.id,
        sourceGraphSlug: source, id: source + ':' + kind + ':' + ref.id + ':' + from + ':' + to});
    };
    for (const it of sources) {
      const g = it.graph, ns = new Map(g.nodes.map(n => [n.id, n]));
      const edges = g.edges.filter(e => e.archived !== true);
      for (const e of edges) {
        if (e.type === 'DERIVES' && !inactive(ns.get(e.from)) && !inactive(ns.get(e.to)))
          add(e.from, e.to, 'refinement', {kind: 'requirement', id: e.from}, it.slug);
        if (e.type === 'INTRODUCES') {
          const cause = ns.get(e.from);
          const actionMode = g.actionModel === 'candidate-v6';
          if (!cause || inactive(cause) || !ns.has(e.to) ||
              !(cause.kind === 'decision' || (actionMode && cause.kind === 'action'))) continue;
          if (!edges.some(x => x.type === 'DRIVES' && x.from === e.parent && x.to === cause.id)) {
            warnings.push({source: it.slug, edge: e.id, reason: 'unverified-driving-R'});continue;
          }
          const actionSelected = actionMode && actionActive(cause,g,e.parent);
          const type = cause.kind === 'decision' ?
            (activeCause(cause, g) ? 'selected' :
              (g.templateOnly === true || cause.status === 'reusable-unselected') ? 'prepared' : null) :
            (actionSelected ? 'selected' : null);
          if (type) add(e.parent, e.to, type, {kind:cause.kind, id:cause.id}, it.slug, e.childRole);
        }
        if (e.type === 'OUTCOME_OF') {
          const o = ns.get(e.from);
          if (!o || inactive(o)) continue;
          const action = g.actionModel === 'candidate-v6' && o.kind === 'action' && o.status === 'candidate';
          if (o.kind !== 'option' && !action) continue;
          for (const link of edges.filter(x => x.type === (action ? 'DRIVES' : 'OPTION_FOR') && x.to === o.id))
            add(link.from, e.to, 'potential', {kind:o.kind, id:o.id}, it.slug, e.childRole);
        }
      }
    }
    // Multiple physical R-view files may repeat the same canonical
    // OPTION_FOR+OUTCOME_OF or DRIVES+INTRODUCES answer. They are projections
    // of a *single* causal edge, not parallel routes for the overview.
    // Keep distinct origins / decisions, but collapse exact owner projections.
    const ownerFor = arc => {
      let slug=arc.sourceGraphSlug, record=bySlug.get(slug)?.graph.nodes.find(n=>n.id===arc.causeId&&n.kind===arc.causeKind);
      const visited=new Set();
      while(record?.projectionOf){
        const ref=record.projectionOf, k=ref.graphSlug+'::'+ref.nodeId;
        if(visited.has(k))break;visited.add(k);
        const target=bySlug.get(ref.graphSlug)?.graph.nodes.find(n=>n.id===ref.nodeId&&n.kind===arc.causeKind);
        if(!target||bySlug.get(ref.graphSlug).graph.identitySpace!==space)break;
        slug=ref.graphSlug;record=target;
      }
      return slug;
    };
    const unique=new Map();
    for (const arc of arcs) {
      const owner=ownerFor(arc), key=[arc.from,arc.to,arc.kind,arc.causeKind,owner,arc.causeId].join('|');
      const earlier=unique.get(key);
      if(!earlier||arc.sourceGraphSlug===owner&&earlier.sourceGraphSlug!==owner)unique.set(key,arc);
    }
    const causalArcs=[...unique.values()];
    const adjacency = new Map();
    for (const arc of causalArcs) {
      if (!adjacency.has(arc.from)) adjacency.set(arc.from, []);
      adjacency.get(arc.from).push(arc);
    }
    // Reachability is from this root only. Same identitySpace alone does not
    // prove that a second root is part of this full graph.
    const seen = new Set([rootId]), actual = new Set([rootId]);
    const queue = [{id:rootId, possible:false}], usedEdges = new Set();
    const visitedStates = new Set([rootId+':false']);
    for (let i=0; i<queue.length; i++) {
      const next = queue[i];
      for (const arc of adjacency.get(next.id) || []) {
        if (!includePotential && ['potential','prepared'].includes(arc.kind)) continue;
        const possible = next.possible || ['potential','prepared'].includes(arc.kind);
        usedEdges.add(arc.id); seen.add(arc.to);
        if (!possible) actual.add(arc.to);
        const state = arc.to + ':' + possible;
        if (!visitedStates.has(state)) {
          visitedStates.add(state); queue.push({id:arc.to, possible});
        }
      }
    }
    // Keep auxiliary files discoverable without claiming DERIVES or
    // same-requirement is a new child Requirement. Old sets could list both.
    const indexed = (manifest.relations || []).filter(r =>
      bySlug.has(r.from) && bySlug.has(r.to) &&
      bySlug.get(r.from).graph.identitySpace === space &&
      bySlug.get(r.to).graph.identitySpace === space);
    const navigableSources = new Set([rootSlug]);
    for (let changed=true; changed;) {
      changed=false;
      for (const r of indexed) if (navigableSources.has(r.from) && !navigableSources.has(r.to)) {
        navigableSources.add(r.to); changed=true;
      }
    }
    const supplementaryViews = indexed.filter(r =>
      navigableSources.has(r.from) && navigableSources.has(r.to) &&
      ['derived', 'same-requirement'].includes(r.relationKind))
      .map(r=>({fromGraphSlug:r.from,toGraphSlug:r.to,
        relationKind:r.relationKind,requirementId:r.requirementId}));
    return {schemaVersion:1, rootRequirementId:rootId, identitySpace:space, entryGraphSlug:rootSlug,
      nodes:[...seen].map(id=>({...records.get(id).node, id, kind:'requirement',
        sourceGraphSlug:records.get(id).source, branchState:actual.has(id)?'actual':'potential'})),
      edges:causalArcs.filter(a=>usedEdges.has(a.id)), supplementaryViews, warnings,
      coverage:'indexed-sources-only; unavailable continuation may exist'};
  }
  return Object.freeze({listEntries, project, decisionActive, decisionGuard, actionActive});
});
// END GENERATED RDG ROOT PROJECTION
// BEGIN GENERATED RDG VIEW GEOMETRY
/* Common camera and target-label geometry for R graphs and graph sets. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.RDGViewGeometry=api;})(globalThis,function(){
  'use strict';
  const clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
  function wheelView(view,event,point,size){
    const factor=event.deltaMode===1?16:event.deltaMode===2?size.height:1;
    const dx=(Number(event.deltaX)||0)*(event.deltaMode===2?size.width:factor),dy=(Number(event.deltaY)||0)*factor;
    if(event.ctrlKey){
      const delta=dy||dx;if(!delta)return {...view};
      const scale=clamp(view.scale*Math.exp(-clamp(delta,-600,600)*.0015),.07,3);
      return {x:point.x-(point.x-view.x)*scale/view.scale,y:point.y-(point.y-view.y)*scale/view.scale,scale};
    }
    return {...view,x:view.x-(event.shiftKey?(dx||dy):dx),y:view.y-(event.shiftKey?0:dy)};
  }
  const hit=(a,b,pad=6)=>a.x<b.x+b.w+pad&&a.x+a.w+pad>b.x&&a.y<b.y+b.h+pad&&a.y+a.h+pad>b.y;
  function placeTargetLabel({target,endpoint,width,height,nodeBoxes,labels,otherRoutes=[]}){
    const center={x:target.x+target.w/2,y:target.y+target.h/2};
    const distance=box=>Math.hypot(Math.max(box.x-endpoint.x,endpoint.x-box.x-box.w,0),Math.max(box.y-endpoint.y,endpoint.y-box.y-box.h,0));
    const crosses=box=>otherRoutes.reduce((n,ps)=>n+ps.slice(1).filter((p,i)=>{
      const a=ps[i];return a[0]===p[0]?a[0]>box.x&&a[0]<box.x+box.w&&Math.max(a[1],p[1])>box.y&&Math.min(a[1],p[1])<box.y+box.h:
        a[1]>box.y&&a[1]<box.y+box.h&&Math.max(a[0],p[0])>box.x&&Math.min(a[0],p[0])<box.x+box.w;
    }).length,0);
    const nearby=[];
    for(let ring=0;ring<=14;ring++){
      const candidates=[],step=height+8;
      for(const shift of ring?[ring*step,-ring*step]:[0]){
        candidates.push({x:target.x-width-12,y:endpoint.y-height/2+shift,w:width,h:height},
          {x:target.x+target.w+12,y:endpoint.y-height/2+shift,w:width,h:height},
          {x:center.x-width/2+shift,y:target.y-height-12,w:width,h:height},
          {x:center.x-width/2+shift,y:target.y+target.h+12,w:width,h:height});
      }
      const valid=candidates.filter(b=>!nodeBoxes.some(n=>hit(b,n))&&!labels.some(l=>hit(b,l)));
      for(const b of valid)nearby.push({...b,crowded:ring>5,score:distance(b)+crosses(b)*90+ring*2});
      if(ring>=5&&nearby.length){nearby.sort((a,b)=>a.score-b.score);return nearby[0];}
    }
    // Only physically packed/overlapping user layouts reach this local fallback.
    // Expand around the target, never use a shared gutter at the source.
    for(let ring=1;;ring++){
      const step=height+8;
      for(let i=-ring;i<=ring;i++)for(const [x,y] of [[i,-ring],[i,ring],[-ring,i],[ring,i]]){
        const b={x:center.x+x*(width+12)-width/2,y:center.y+y*step-height/2,w:width,h:height};
        if(!nodeBoxes.some(n=>hit(b,n))&&!labels.some(l=>hit(b,l)))return {...b,crowded:true};
      }
    }
  }
  return Object.freeze({wheelView,placeTargetLabel});
});
// END GENERATED RDG VIEW GEOMETRY
// BEGIN GENERATED RDG CATALOG
/* Folder-first catalog. Full graphs are entries rooted in semantic Requirements,
 * not graph file membership sets. Sources remain canonical graph.json files. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;else root.RDGCatalog=api;
})(globalThis,function(){
  'use strict';
  const path=p=>typeof p==='string'&&p.length>0&&!p.includes(String.fromCharCode(92))&&!/[?:]/.test(p)&&![...p].some(c=>c.charCodeAt(0)<32)&&p.split('/').every(x=>x&&x!=='.'&&x!=='..');
  function normalizeCatalog(manifest){
    if(!manifest||manifest.schemaVersion!==1||!Array.isArray(manifest.graphs)||!Array.isArray(manifest.fullGraphs))throw Error('Неверный каталог полных графов');
    const graphs=manifest.graphs.map(g=>{
      if(!g||!/^([a-z0-9][a-z0-9_-]*)$/.test(g.slug)||!path(g.file)||!g.file.endsWith('/graph.json'))throw Error('Недопустимый путь/slug графа');
      return {...g,kind:'graph',folder:g.folder??(g.group||'legacy'),presentation:g.presentation||{}};
    });
    const by=new Map(graphs.map(g=>[g.slug,g]));
    if(by.size!==graphs.length)throw Error('Дублирующийся граф');
    const folders=manifest.folders||[...new Set(graphs.map(g=>g.folder))].map(id=>({id,kind:'folder',folder:'',title:id,presentation:{}}));
    if(new Set(folders.map(f=>f.id)).size!==folders.length||folders.some(f=>!path(f.id)||f.folder!==''&&!path(f.folder)))throw Error('Неверные папки каталога');
    const fullGraphs=manifest.fullGraphs.map(entry=>{
      const g=by.get(entry.slug);
      if(!g||!entry.rootRequirementId||entry.rootRequirementId!==(g.rootRequirementId||g.graph?.rootRequirementId)||entry.identitySpace!==(g.identitySpace||g.graph?.identitySpace)||entry.file!==g.file||!path(entry.folder)&&entry.folder!=='')throw Error('Неверная точка входа полного графа: '+entry.slug);
      return {...entry,kind:'full-graph',presentation:entry.presentation||{}};
    });
    if(new Set(fullGraphs.map(x=>x.slug)).size!==fullGraphs.length)throw Error('Дублирующаяся точка входа');
    // Older standalone graphs without an identitySpace/rootRequirementId remain
    // accessible for editing. Do not pretend they have a proven full R closure.
    const fullSlugs=new Set(fullGraphs.map(e=>e.slug));
    const standalone=graphs.filter(g=>!fullSlugs.has(g.slug)&&(!g.identitySpace||!g.rootRequirementId))
      .map(g=>({...g,kind:'graph'}));
    return {graphs,folders,fullGraphs,standalone,relations:manifest.relations||[]};
  }
  function listFolder(catalog,folder='',query=''){
    const items=[...catalog.folders.filter(f=>f.folder===folder),
      ...catalog.fullGraphs.filter(g=>g.folder===folder),
      ...catalog.standalone.filter(g=>g.folder===folder)];
    const q=query.trim().toLowerCase();
    return items.filter(e=>!q||[e.title,e.slug,e.id,e.presentation?.description].join(' ').toLowerCase().includes(q))
      .sort((a,b)=>(a.kind==='folder'?0:1)-(b.kind==='folder'?0:1)||a.title.localeCompare(b.title));
  }
  function searchCatalog(catalog,query){
    const q=query.trim().toLowerCase();
    return [...catalog.folders,...catalog.fullGraphs,...catalog.standalone].filter(e=>[e.title,e.slug,e.id,e.presentation?.description].join(' ').toLowerCase().includes(q));
  }
  return Object.freeze({normalizeCatalog,listFolder,searchCatalog,validPath:path});
});
// END GENERATED RDG CATALOG
// BEGIN GENERATED RDG STATE
/* Shared RDG context contract, validation and projection. No network or writes. */
(function(root,factory){
  const api=factory(typeof module==='object'&&module.exports?require('./rdg-catalog.js'):root.RDGCatalog);
  if(typeof module==='object'&&module.exports)module.exports=api;else root.RDGState=api;
})(globalThis,function(catalog){
  'use strict';
  const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
  const text=v=>typeof v==='string'&&v.trim().length>0;
  const array=v=>Array.isArray(v);
  const check=(v,m)=>{if(!v)throw Error('CONTEXT_CONTRACT: '+m);};
  const slug=v=>typeof v==='string'&&/^[a-z0-9][a-z0-9_-]*$/.test(v);
  const object=v=>v&&typeof v==='object'&&!array(v);
  const key=r=>r.graphSlug+':'+r.fieldId;
  const safeURL=v=>{try{const u=new URL(v);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password;}catch(_){return false;}};
  function uses(g){
    const out=[];
    const add=(part,location)=>{for(const u of part.contextUses||[])out.push({...u,location});};
    add(g,'graph');
    for(const n of g.nodes||[]){
      if(n.projectionOf||n.active===false||['inactive','superseded','rejected','historical'].includes(n.status))continue;
      add(n,n.id);
      for(const polarity of ['recommended','contraindicated'])
        for(const c of n.canonBlock?.[polarity]||[])add(c,n.id+'/'+polarity+'/'+c.id);
    }
    return out;
  }
  function validate(items,{partial=false}={}){
    const by=new Map(items.map(i=>[i.slug,i]));
    const resolve=(ref,kind,local)=>{
      const id=kind==='field'?'fieldId':'sourceId',prop=kind==='field'?'contextFields':'knowledgeSources';
      check(object(ref)&&Object.keys(ref).length===2&&slug(ref.graphSlug)&&text(ref[id]),'invalid '+kind+' ref');
      const owner=by.get(ref.graphSlug);
      if(!owner){check(partial,'missing owner '+ref.graphSlug);return;}
      check((owner.graph[prop]||[]).some(x=>x.id===ref[id]),'missing '+kind+' '+ref[id]);
      if(owner.group==='workspaces'&&local.graph.identitySpace!==owner.graph.identitySpace)
        throw Error('CONTEXT_CONTRACT: cross-project definition/source ref');
    };
    const unique=(xs,label)=>{check(array(xs),label+' must be array');const ids=new Set();for(const x of xs){check(object(x)&&text(x.id)&&!ids.has(x.id),'duplicate/invalid '+label+' id');ids.add(x.id);}};
    const sources=(part,item)=>{
      if(own(part,'sourceRefs')){check(array(part.sourceRefs),'sourceRefs must be array');for(const r of part.sourceRefs)resolve(r,'source',item);}
    };
    const answerOwners=new Set();
    for(const item of items){
      const g=item.graph;
      unique(g.knowledgeSources||[],'knowledgeSources');
      for(const s of g.knowledgeSources||[])check(text(s.title)&&safeURL(s.url),'source needs title and safe http(s) URL');
      unique(g.contextFields||[],'contextFields');
      for(const f of g.contextFields||[]){check(text(f.title)&&text(f.explanation),'field needs title/explanation');sources(f,item);}
      if(own(g,'contextFieldsComplete'))check(typeof g.contextFieldsComplete==='boolean','invalid contextFieldsComplete');
      const parts=[g,...(g.nodes||[])];
      for(const n of g.nodes||[]){
        if(n.canonBlock){
          parts.push(n.canonBlock,...(n.canonBlock.recommended||[]),...(n.canonBlock.contraindicated||[]));
          const c=n.canonBlock;
          check(!own(c,'contextUses'),'contextUses belongs on graph, node or canon case, not canonBlock');
          if(own(c,'preparation'))check(['link-only','interpreted'].includes(c.preparation),'invalid preparation');
          if(c.preparation==='link-only')check(c.fieldsComplete!==true&&array(c.sourceRefs)&&c.sourceRefs.length,'link-only needs source; cannot declare complete');
          if(c.preparation==='interpreted')check(text(c.interpretation),'interpreted canon needs interpretation for R/option');
          if(own(c,'fieldsComplete'))check(typeof c.fieldsComplete==='boolean','invalid fieldsComplete');
        }
        check(!own(n,'contextAnswers'),'legacy contextAnswers history must be migrated to one current contextValue');
        if(own(n,'contextFieldRef')||own(n,'contextValue')){
          check(n.kind==='context'&&!n.projectionOf&&text(g.identitySpace),'only project-scoped owning Context stores field values');
          resolve(n.contextFieldRef,'field',item);
          if(own(n,'contextValue')){
            const v=n.contextValue;
            check(object(v)&&Object.keys(v).every(k=>['value','source','scope'].includes(k))&&
              text(v.value)&&text(v.source)&&text(v.scope),'contextValue needs value/source/scope, no history or dates');
          }
          if(item.group==='workspaces'&&n.active!==false&&!['inactive','superseded'].includes(n.status)){
            const k=g.identitySpace+'|'+key(n.contextFieldRef);check(!answerOwners.has(k),'duplicate project answer owner '+k);answerOwners.add(k);
          }
        }
      }
      for(const p of parts){
        sources(p,item);
        if(own(p,'contextUses')){
          check(array(p.contextUses),'contextUses must be array');
          for(const u of p.contextUses){
            check(object(u)&&text(u.purpose),'usage needs purpose');resolve(u.fieldRef,'field',item);
            if(own(u,'when')){
              check(object(u.when)&&Object.keys(u.when).length===1&&array(u.when.allSelected)&&u.when.allSelected.length,'when needs allSelected');
              for(const r of u.when.allSelected){
                check(object(r)&&Object.keys(r).length===2&&slug(r.graphSlug)&&text(r.optionId),'invalid selection condition');
                const target=by.get(r.graphSlug);
                if(!target){check(partial,'condition graph unavailable');continue;}
                check(target.graph.identitySpace===g.identitySpace,'cross-project condition');
                check(target.graph.nodes.some(n=>n.id===r.optionId&&n.kind==='option'),'missing condition option');
              }
            }
          }
        }
      }
    }
    return true;
  }
  function collect({items,manifest={},graphSlug,rootGraphSlug,identitySpace,scope='project'}){
    const by=new Map(items.filter(i=>i.graph).map(i=>[i.slug,i]));
    const rootSlug=rootGraphSlug||graphSlug;
    const targets=rootGraphSlug?(()=>{
      const included=new Set([rootGraphSlug]);
      let changed=true;
      while(changed){changed=false;for(const r of manifest.relations||[]){
        if(included.has(r.from)&&!included.has(r.to)&&
          ['selected','prepared','potential','derived','same-requirement'].includes(r.relationKind)){
          included.add(r.to);changed=true;
        }
      }}
      return [...included];
    })():[graphSlug];
    check(targets.length&&targets.every(s=>typeof s==='string'),'graphSlug or rootGraphSlug required');
    let states=null;
    if(rootGraphSlug){
      const actual=new Set([rootGraphSlug]),alternative=new Set();let changed=true;
      while(changed){changed=false;for(const r of manifest.relations||[]){
        const fromActual=actual.has(r.from),fromAlternative=alternative.has(r.from);
        const isAlternative=fromAlternative||r.relationKind==='potential'||r.relationKind==='prepared';
        const target=isAlternative?alternative:actual;
        if((fromActual||fromAlternative)&&!target.has(r.to)&&!actual.has(r.to)){
          target.add(r.to);changed=true;
        }
      }}
      states=Object.fromEntries(targets.map(x=>[x,alternative.has(x)?'alternative':actual.has(x)?'current':'unknown']));
    }
    const spaces=new Set(targets.map(s=>by.get(s)?.graph.identitySpace).filter(Boolean));
    if(identitySpace)check([...spaces].every(s=>s===identitySpace),'identitySpace mismatch');
    else if(spaces.size===1)identitySpace=[...spaces][0];
    check(spaces.size<=1,'mixed project graph set');
    const result={identitySpace:identitySpace||null,graphSlugs:targets,scope,fields:[],incomplete:[],freeformCandidates:[],coverage:'declared uses in available catalog; external sources not inspected'};
    const sourceList=refs=>(refs||[]).map(r=>{
      const s=by.get(r.graphSlug)?.graph.knowledgeSources?.find(s=>s.id===r.sourceId);
      return s?{...s,graphSlug:r.graphSlug}:{...r,unavailable:true};
    });
    const selected=r=>{
      const g=by.get(r.graphSlug)?.graph;
      if(!g)return null;
      return g.nodes.some(n=>n.kind==='decision'&&(n.status==='committed'&&g.exampleOnly!==true||n.status==='selected-in-example-only'&&g.exampleOnly===true&&g.hypothetical===true&&g.readOnly===true&&g.selectedInProject===false)&&n.selectedOptionId===r.optionId&&n.active!==false);
    };
    if(!identitySpace)result.incomplete.push({reason:'project-identity-unavailable'});
    const fields=new Map();
    for(const s of targets){
      const item=by.get(s),g=item?.graph;
      if(!g){result.incomplete.push({graphSlug:s,reason:'graph-unavailable'});continue;}
      if(g.contextFieldsComplete!==true)result.incomplete.push({graphSlug:s,reason:'field-list-not-declared-complete'});
      for(const n of g.nodes||[])if(n.canonBlock&&(n.canonBlock.preparation==='link-only'||n.canonBlock.fieldsComplete===false))
        result.incomplete.push({graphSlug:s,location:n.id,reason:'canon-fields-incomplete'});
      for(const u of uses(g)){
        const k=key(u.fieldRef),owner=by.get(u.fieldRef.graphSlug),def=owner?.graph.contextFields?.find(f=>f.id===u.fieldRef.fieldId);
        if(!fields.has(k))fields.set(k,{fieldRef:u.fieldRef,title:def?.title||k,explanation:def?.explanation||'Определение недоступно',sources:sourceList(def?.sourceRefs),definitionAvailable:!!def,usages:[],answer:null,answerStatus:'missing'});
        let state='now',reasons=[];
        if(states?.[s]==='alternative'){state='later';reasons.push('Граф относится к невыбранному пути');}
        else if(states?.[s]==='unknown'){state='unknown';reasons.push('Актуальность пути не установлена');}
        for(const condition of u.when?.allSelected||[]){
          const yes=selected(condition);const cg=by.get(condition.graphSlug)?.graph,option=cg?.nodes.find(n=>n.id===condition.optionId);
          reasons.push('После выбора «'+(option?.title||condition.optionId)+'» в «'+(cg?.title||condition.graphSlug)+'»');
          if(yes===false)state='later';else if(yes===null&&state!=='later')state='unknown';
        }
        fields.get(k).usages.push({...u,graphSlug:s,state,reasons});
      }
    }
    // Values are authoritative only in owning Context records in this project.
    for(const item of items){
      const g=item.graph;if(!g||!identitySpace||g.identitySpace!==identitySpace)continue;
      const teaching=targets.some(s=>by.get(s)?.group==='examples');
      if(item.group!=='workspaces'&&!(teaching&&item.group==='examples'))continue;
      if(g.templateOnly)continue;
      for(const n of g.nodes||[]){
        if(n.kind!=='context'||n.projectionOf||n.active===false||['inactive','superseded','candidate','potential'].includes(n.status))continue;
        if(!n.contextFieldRef){result.freeformCandidates.push({graphSlug:item.slug,nodeId:n.id,text:n.currentStatement||n.description||n.title,status:'mapping-needs-assessment'});continue;}
        const row=fields.get(key(n.contextFieldRef));if(!row||!n.contextValue)continue;
        const v=n.contextValue;
        const status=v.scope!=='project'&&v.scope!==scope?'scope-needs-assessment':'applicable';
        const candidate={...v,status,graphSlug:item.slug,nodeId:n.id,exampleOnly:item.group==='examples'};
        (row._candidates??=[]).push(candidate);
      }
    }
    for(const row of fields.values()){
      row.state=row.usages.some(u=>u.state==='now')?'now':row.usages.some(u=>u.state==='unknown')?'unknown':'later';
      const candidates=row._candidates||[];
      row.answerStatus=candidates.length>1?'conflict':candidates.length===1?
        (candidates[0].status==='applicable'?'known':'needs-assessment'):'missing';
      row.answer=candidates.length===1?candidates[0]:null;
      if(candidates.length>1)row.conflictingOwners=candidates;
      delete row._candidates;
      row.nextAction=row.state!=='now'?'defer':row.answerStatus==='known'?'reuse':'check-known-context-or-ask';
      row.question=row.state==='now'&&row.answerStatus!=='known';
      if(!row.definitionAvailable)result.incomplete.push({fieldRef:row.fieldRef,reason:'definition-unavailable'});
      result.fields.push(row);
    }
    result.fields.sort((a,b)=>key(a.fieldRef).localeCompare(key(b.fieldRef)));
    return result;
  }
  return Object.freeze({validate,collect,uses,safeURL});
});
// END GENERATED RDG STATE
// BEGIN GENERATED RDG LAYOUT CORE
/* Shared data/command layer; embedded into the userscript by build-rdg-layout.py. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.RDGLayoutCore=api;
})(globalThis,function(){
  'use strict';
  const clone=x=>JSON.parse(JSON.stringify(x));
  const object=x=>x&&typeof x==='object'&&!Array.isArray(x);
  const key=k=>typeof k==='string'&&k.length>0&&k.length<=500&&!['__proto__','prototype','constructor'].includes(k)&&!/[\x00-\x1f]/.test(k);
  const empty=()=>({schemaVersion:1,revision:0,layouts:{}});
  function validate(doc){
    if(!object(doc)||doc.schemaVersion!==1||!Number.isSafeInteger(doc.revision)||doc.revision<0||!object(doc.layouts))throw Error('Некорректный документ расположений');
    for(const [graphKey,layout] of Object.entries(doc.layouts)){
      if(!key(graphKey)||!object(layout)||!object(layout.positions))throw Error('Некорректный ключ графа/расположение');
      if(Object.keys(layout.positions).length>2000)throw Error('Слишком много координат');
      for(const [id,p] of Object.entries(layout.positions)){
        if(!key(id)||!object(p)||!Number.isFinite(p.x)||!Number.isFinite(p.y)||Math.abs(p.x)>1000000||Math.abs(p.y)>1000000)throw Error('Некорректные координаты: '+id);
      }
    }
    return clone(doc);
  }
  function graphKey(identitySpace,slug,rootRequirementId){
    if(!key(identitySpace)||!key(slug)||rootRequirementId!==undefined&&!key(rootRequirementId))throw Error('Для расположения нужны identitySpace, slug и допустимая корневая R');
    return JSON.stringify(rootRequirementId===undefined?[identitySpace,slug]:[identitySpace,slug,rootRequirementId]);
  }
  function apply(document,commands){
    const doc=validate(document);
    for(const cmd of Array.isArray(commands)?commands:[commands]){
      if(!object(cmd)||!key(cmd.graphKey))throw Error('Команда без graphKey');
      if(cmd.type==='set_positions'){
        if(!object(cmd.positions))throw Error('Нет positions');
        const current=doc.layouts[cmd.graphKey]?.positions||{};
        for(const id of Object.keys(cmd.positions))if(!key(id))throw Error('Некорректный ID');
        doc.layouts[cmd.graphKey]={positions:{...current,...clone(cmd.positions)}};
      }else if(cmd.type==='clear_layout')delete doc.layouts[cmd.graphKey];
      else throw Error('Неизвестная команда расположения: '+cmd.type);
    }
    return validate(doc);
  }
  function commit(document,expectedRevision){
    const doc=validate(document);
    if(doc.revision!==expectedRevision)throw Error('Конфликт ревизии расположений');
    doc.revision++;return validate(doc);
  }
  return Object.freeze({empty,validate,graphKey,apply,commit});
});
// END GENERATED RDG LAYOUT CORE
(() => {
  'use strict';
  if (document.getElementById('rdg-viewer-root')) return;
  const host = document.createElement('div');
  host.id = 'rdg-viewer-root';
  document.documentElement.appendChild(host);
  Object.assign(host.style, {position:'fixed',right:'14px',bottom:'94px',
    zIndex:'2147483600',display:'block'});
  const VIEWER_VERSION = '2.2.2';
  host.dataset.rdgVersion = VIEWER_VERSION;
  const root = host.attachShadow({ mode: 'open' });
  const ns = 'http://www.w3.org/2000/svg';
  // Local Windows directory belonging to this viewer. No filesystem picker on startup.
  const GRAPH_ROOT_URL = 'file:///C:/Users/alexa/Repos/rd-graphs/graphs/';
  let graph = null, sourceGraph = null, localRootId = null, selected = null, selectedEdge = null, showAuxiliaryEdges = false;
  // Variant visibility and collection folding are independent of the All Relations mode.
  let showAllVariants = false, expandedCollections = new Set();
  let graphs = [], projectContexts = {}, sourceUpdateAlerts = [], activeSlug = null, source = 'auto', catalogLoading = null;
  let selectedFolder = '', graphRelations = [], catalogModel=null, activeFullRootSlug=null, fullMode=false;
  const catalogCore=globalThis.RDGCatalog,viewGeometry=globalThis.RDGViewGeometry;
  let fullGraphData=null;
  const refreshedSpaces=new Set();
  const explorerStates=new Map(),fullViewStates=new Map();
  let levelStack = [];
  const embeddedSnapshot = typeof globalThis !== 'undefined' ? globalThis.RDG_EMBEDDED_GRAPHS : null;
  let privilegedRequest = null, startupRequested = false;
  let layoutBands = [], positions = new Map(), view = { x: 0, y: 0, scale: 1 };
  let graphWidth = 800, graphHeight = 600, renderBounds = null, drag = null;
  let viewportWidth=window.innerWidth,viewportHeight=window.innerHeight;
  let enteringNodes=new Set();
  const collectionPositions=new Map();
  const layoutCore=globalThis.RDGLayoutCore;
  let layoutDocument=layoutCore.empty(),layoutBaseDocument=layoutCore.empty(),layoutFileHandle=null,layoutFileRevision=null;
  let layoutReady=false,layoutDirty=false,nodeDrag=null,suppressNodeClickUntil=0;
  const layoutCacheKey='rdg-layout-document:'+GRAPH_ROOT_URL;
  let layoutPendingCommands=[],layoutSaving=false,layoutReading=false;
  let layoutAutoTimer=null,layoutAutoPaused=false,layoutAutoBlocked='',layoutLastSaved=null,layoutSavePromise=null;
  const legacyDraftKey=layoutCacheKey+':draft',draftPrefix=legacyDraftKey+':';
  const newDraftOwner=()=>typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
  let draftOwner=newDraftOwner(),draftKey=draftPrefix+draftOwner;
  // A duplicated tab may inherit sessionStorage. A document must hold its own lease
  // before reusing that owner; otherwise it gets a fresh journal.
  let draftOwnerInitialized=false,draftOwnerReady=initializeDraftOwner();
  async function initializeDraftOwner(){
    let previous;try{previous=sessionStorage.getItem(draftPrefix+'owner');}catch(_){}
    const claim=async owner=>{
      if(typeof navigator==='undefined'||!navigator.locks?.request)return false;
      return new Promise(resolve=>{
        navigator.locks.request(draftPrefix+owner,{ifAvailable:true},lock=>{
          resolve(!!lock);
          if(lock)return new Promise(()=>{}); // released by the browser when this document closes
        }).catch(()=>resolve(false));
      });
    };
    if(previous&&await claim(previous))draftOwner=previous;
    else await claim(draftOwner);
    draftKey=draftPrefix+draftOwner;
    try{sessionStorage.setItem(draftPrefix+'owner',draftOwner);}catch(_){}
    draftOwnerInitialized=true;
  }
  const currentLayoutKey=()=>fullMode?layoutCore.graphKey(sourceGraph.identitySpace,'full-'+activeFullRootSlug,sourceGraph.rootRequirementId):layoutCore.graphKey(sourceGraph?.identitySpace||'manual',activeSlug||sourceGraph?.id||'manual',localRootId||undefined);
  const savedPositions=()=>layoutDocument.layouts[currentLayoutKey()]?.positions||{};
  function clearCollectionPositionCache(key=currentLayoutKey()){if(fullMode&&key===currentLayoutKey()){const state=fullViewStates.get(activeFullRootSlug);if(state)delete state.positions;}const prefix=key+'::';for(const entry of collectionPositions.keys())if(entry.startsWith(prefix))collectionPositions.delete(entry);}
  function applyLayoutPositions(){const saved=savedPositions();if(Object.keys(saved).length)layoutBands=[];for(const [id,p] of Object.entries(saved))if(positions.has(id))positions.set(id,{x:p.x,y:p.y});}
  function updateLayoutControls(){
    if(!el('layout-save'))return;
    el('layout-save').textContent=layoutSaving?'Сохранение…':'Записать сейчас'+(layoutDirty?' *':'');
    for(const id of ['layout-save','layout-open','layout-discard'])el(id).disabled=layoutSaving||layoutReading;
    el('layout-pause').textContent=layoutAutoPaused?'Возобновить автосохранение':'Приостановить автосохранение';
    const status=layoutSaving?'Сохранение…':layoutReading?'Чтение файла…':layoutAutoBlocked||
      (layoutAutoPaused?'Автосохранение приостановлено':!layoutFileHandle?
      (layoutDirty?(typeof window.showSaveFilePicker==='function'?'Изменения не записаны — подключите файл расположений':'Изменения не записаны в файл · доступен экспорт'):(typeof window.showSaveFilePicker==='function'?'Для автосохранения подключите файл расположений':'Файл не подключён · доступен экспорт')):
      layoutDirty?'Ожидает сохранения':layoutLastSaved?'Сохранено':'Файл подключён · автосохранение включено');
    el('layout-status').textContent=status;
    el('layout-status').setAttribute('data-state',layoutSaving?'saving':layoutAutoBlocked?'error':layoutDirty?'dirty':layoutLastSaved?'saved':'idle');
    el('layout-connect').hidden=!!layoutFileHandle&&!layoutAutoBlocked;
    el('layout-status').title=(layoutFileHandle?.name||'Общий файл не подключён')+
      (layoutLastSaved?' · последняя проверенная запись '+new Date(layoutLastSaved).toLocaleTimeString():'');
  }
  let draftPersistence=Promise.resolve();
  async function draftStorage(key,value,write=false){
    if(typeof indexedDB==='undefined')return null;
    try{return await new Promise((resolve,reject)=>{
      const request=indexedDB.open('rdg-layout-files',1);
      request.onupgradeneeded=()=>request.result.createObjectStore('handles');
      request.onerror=()=>reject(request.error);
      request.onsuccess=()=>{const db=request.result,tx=db.transaction('handles',write?'readwrite':'readonly'),store=tx.objectStore('handles');
        const op=write?(value===null?store.delete(key):store.put(value,key)):key===null?store.getAllKeys():store.get(key);
        tx.oncomplete=()=>{db.close();resolve(write?null:op.result)};tx.onerror=()=>{db.close();reject(tx.error)};};
    });}catch(_){return null;}
  }
  function persistLayoutDraft(){
    const value=layoutPendingCommands.length?{base:layoutBaseDocument,commands:layoutPendingCommands,updatedAt:Date.now()}:null;
    const snapshot=value?JSON.parse(JSON.stringify(value)):null;
    // Only this document's journal is changed. Saving B cannot erase A's draft.
    const localWrite=()=>{try{if(snapshot)localStorage.setItem(draftKey,JSON.stringify(snapshot));else localStorage.removeItem(draftKey);}catch(_){}};
    const wroteSync=draftOwnerInitialized;if(wroteSync)localWrite();
    draftPersistence=draftPersistence.catch(()=>{}).then(async()=>{
      await draftOwnerReady;
      if(!draftOwnerInitialized)return;
      if(!wroteSync)localWrite();
      await draftStorage(draftKey,snapshot,true);
    });
  }
  async function readLayoutDraft(key){
    try{const raw=localStorage.getItem(key);if(raw!==null)return JSON.parse(raw);}catch(_){}
    return draftStorage(key);
  }
  async function listLayoutDrafts(){
    await draftOwnerReady;await draftPersistence;
    const keys=new Set(await draftStorage(null)||[]);
    try{for(let i=0;i<localStorage.length;i++)keys.add(localStorage.key(i));}catch(_){}
    const result=[];
    for(const key of keys){
      if(typeof key!=='string'||key!==legacyDraftKey&&!key.startsWith(draftPrefix))continue;
      const draft=await readLayoutDraft(key);
      if(draft?.commands?.length)result.push({id:key,own:key===draftKey,legacy:key===legacyDraftKey,updatedAt:draft.updatedAt||0,commands:draft.commands.length});
    }
    return result.sort((a,b)=>b.updatedAt-a.updatedAt);
  }
  async function recoverLayoutDraft(key){
    await draftOwnerReady;
    if(layoutDirty||layoutSaving||layoutReading)throw Error('Сначала сохраните или отмените текущие правки расположения');
    if(key!==legacyDraftKey&&!key.startsWith(draftPrefix))throw Error('Неверный черновик');
    const draft=await readLayoutDraft(key);
    if(layoutDirty||layoutSaving||layoutReading)throw Error('Сначала сохраните или отмените текущие правки расположения');
    if(!draft?.commands?.length)return false;
    const base=layoutCore.validate(draft.base);
    if(!Array.isArray(draft.commands))throw Error('Неверные команды черновика');
    layoutCore.apply(base,draft.commands);
    const same=JSON.stringify(base)===JSON.stringify(layoutBaseDocument);
    layoutPendingCommands=JSON.parse(JSON.stringify(draft.commands));installLayoutBase(base);
    layoutAutoBlocked=same?'Восстановлен локальный черновик — нажмите «Записать сейчас»':
      'Конфликт версий — восстановлен черновик прежней версии';
    persistLayoutDraft();await draftPersistence;
    // A foreign/legacy source remains intact: recovery copies it into our journal.
    collectionPositions.clear();for(const state of fullViewStates.values())delete state.positions;if(graph){layout();render();}updateLayoutControls();return true;
  }
  async function restoreLayoutDraft(){
    await draftOwnerReady;
    try{
      if((await readLayoutDraft(draftKey))?.commands?.length)await recoverLayoutDraft(draftKey);
      else {
        const legacy=await readLayoutDraft(legacyDraftKey),migrationKey=legacyDraftKey+':migration';
        const migrated=await readLayoutDraft(migrationKey);
        if(legacy?.commands?.length&&JSON.stringify(migrated?.source)!==JSON.stringify(legacy)){
          await recoverLayoutDraft(legacyDraftKey);
          // Keep the source recoverable, but do not automatically replay it after
          // the imported journal has already been saved or explicitly discarded.
          const marker={source:legacy};
          try{localStorage.setItem(migrationKey,JSON.stringify(marker));}catch(_){}
          await draftStorage(migrationKey,marker,true);
        }
      }
    }catch(_){layoutAutoBlocked='Не удалось восстановить локальный черновик';}
    updateLayoutControls();
  }
  async function showLayoutDrafts(){
    const list=el('layout-draft-list');list.replaceChildren();
    const drafts=await listLayoutDrafts();
    if(!drafts.length){list.textContent='Нет несохранённых черновиков';return;}
    for(const draft of drafts){
      const button=document.createElement('button');
      button.textContent=(draft.own?'Текущая вкладка':draft.legacy?'Прежний формат':'Другая вкладка / сеанс')+
        ' · '+draft.commands+' команд'+(draft.updatedAt?' · '+new Date(draft.updatedAt).toLocaleString():'');
      button.disabled=layoutDirty||layoutSaving||layoutReading;
      button.onclick=async()=>{try{await recoverLayoutDraft(draft.id);await showLayoutDrafts();}catch(error){message(error.message);}};
      list.appendChild(button);
    }
  }
  function scheduleLayoutSave(){
    if(layoutAutoTimer!==null&&typeof clearTimeout==='function')clearTimeout(layoutAutoTimer);
    layoutAutoTimer=null;
    if(!layoutDirty||layoutAutoPaused||layoutAutoBlocked||!layoutFileHandle||layoutSaving||layoutReading||nodeDrag?.moved||typeof setTimeout!=='function')return;
    layoutAutoTimer=setTimeout(()=>{layoutAutoTimer=null;if(layoutAutoPaused||layoutAutoBlocked||nodeDrag?.moved)return;void saveLayout({interactive:false}).catch(()=>{});},650);
  }
  function markLayoutDirty(){layoutDirty=true;persistLayoutDraft();updateLayoutControls();scheduleLayoutSave();}
  function recordLayoutCommands(commands){
    const next=layoutCore.apply(layoutDocument,commands);
    layoutPendingCommands.push(...JSON.parse(JSON.stringify(commands)));
    layoutDocument=next;markLayoutDirty();
  }
  function installLayoutBase(document){
    layoutBaseDocument=layoutCore.validate(document);
    layoutDocument=layoutCore.apply(layoutBaseDocument,layoutPendingCommands);
    layoutDirty=layoutPendingCommands.length>0;updateLayoutControls();
  }
  function captureLayoutCommand(){
    if(!sourceGraph)return null;
    const key=currentLayoutKey();
    const last=layoutPendingCommands.filter(c=>c.graphKey===key).at(-1);
    if(last?.type==='clear_layout')return null;
    const captured=Object.fromEntries([...positions].map(([id,p])=>[id,{x:p.x,y:p.y}]));
    for(const [cacheKey,p] of collectionPositions)if(cacheKey.startsWith(key+'::')){
      const id='__collection__'+cacheKey.slice((key+'::').length);
      if(!positions.has(id))captured[id]=savedPositions()[id]||{...p};
    }
    return {type:'set_positions',graphKey:key,positions:captured};
  }
  function discardLayoutChanges(){
    if(layoutSaving||layoutReading)throw Error('Дождитесь завершения файловой операции');
    layoutPendingCommands=[];layoutAutoBlocked='';collectionPositions.clear();for(const state of fullViewStates.values())delete state.positions;installLayoutBase(layoutBaseDocument);persistLayoutDraft();
    if(graph){layout();render();}message('Черновые перемещения отменены.');
  }
  function layoutCommand(commands){
    if(!sourceGraph)throw Error('Сначала откройте граф');
    const list=(Array.isArray(commands)?commands:[commands]).map(c=>({...c,graphKey:c.graphKey||currentLayoutKey()}));
    const allowed=new Set([...sourceGraph.nodes.map(n=>n.id),...sourceGraph.nodes.filter(n=>['option','action'].includes(n.kind)).map(n=>'__canon__'+n.id),...(sourceGraph.collections||[]).map(c=>'__collection__'+c.id)]);
    for(const c of list){
      if(c.graphKey!==currentLayoutKey())throw Error('Команда адресована другому открытому графу');
      for(const id of Object.keys(c.positions||{}))if(!allowed.has(id))throw Error('Неизвестный узел: '+id);
    }
    recordLayoutCommands(list);
    for(const c of list){
      if(c.type==='clear_layout')clearCollectionPositionCache(c.graphKey);
      else for(const [id,p] of Object.entries(c.positions))if(id.startsWith('__collection__'))
        collectionPositions.set(c.graphKey+'::'+id.slice('__collection__'.length),{...p});
    }
    if(list.some(c=>c.type==='clear_layout'))layout();else applyLayoutPositions();
    render();return layoutCore.validate(layoutDocument);
  }
  async function rememberLayoutHandle(handle){
    if(typeof indexedDB==='undefined'||typeof FileSystemFileHandle==='undefined'||!(handle instanceof FileSystemFileHandle))return;
    try{await new Promise((resolve,reject)=>{
      const request=indexedDB.open('rdg-layout-files',1);
      request.onupgradeneeded=()=>request.result.createObjectStore('handles');
      request.onerror=()=>reject(request.error);
      request.onsuccess=()=>{const db=request.result,tx=db.transaction('handles','readwrite');tx.objectStore('handles').put(handle,GRAPH_ROOT_URL);tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>{db.close();reject(tx.error);};};
    });}catch(_){/* Layout file remains saved even if remembering its handle is unavailable. */}
  }
  async function restoredLayoutHandle(){
    if(typeof indexedDB==='undefined')return null;
    try{return await new Promise((resolve,reject)=>{
      const request=indexedDB.open('rdg-layout-files',1);
      request.onupgradeneeded=()=>request.result.createObjectStore('handles');
      request.onerror=()=>reject(request.error);
      request.onsuccess=()=>{const db=request.result,read=db.transaction('handles').objectStore('handles').get(GRAPH_ROOT_URL);read.onsuccess=()=>{db.close();resolve(read.result||null);};read.onerror=()=>{db.close();reject(read.error);};};
    });}catch(_){return null;}
  }
  async function attachLayoutFile(handle){
    if(layoutSaving||layoutReading)throw Error('Дождитесь завершения файловой операции');
    if(layoutDirty)throw Error('Есть несохранённое расположение. Сначала сохраните его или сбросьте изменения.');
    layoutReading=true;updateLayoutControls();
    try{
      const doc=layoutCore.validate(JSON.parse(await (await handle.getFile()).text()));
      if(layoutDirty)throw Error('Во время чтения появились новые перемещения; файл не заменил черновик.');
      collectionPositions.clear();for(const state of fullViewStates.values())delete state.positions;layoutAutoBlocked='';layoutLastSaved=null;layoutFileHandle=handle;layoutFileRevision=doc.revision;installLayoutBase(doc);persistLayoutDraft();
      await rememberLayoutHandle(handle);
      if(graph){layout();render();}message('Расположение прочитано из '+handle.name);return layoutCore.validate(doc);
    }finally{layoutReading=false;updateLayoutControls();scheduleLayoutSave();}
  }
  async function writeLayoutSnapshot(snapshot,base,savedCommandCount,interactive){
    if(!layoutFileHandle){
      if(!interactive)throw Error('Нет доступа к файлу — подключите файл расположений');
      if(typeof window.showSaveFilePicker!=='function')throw Error('Запись общего файла недоступна. Используйте экспорт JSON и сохраните его как graphs/layouts.json.');
      const handle=await window.showSaveFilePicker({suggestedName:'layouts.json',types:[{description:'Расположение RDG (graphs/layouts.json)',accept:{'application/json':['.json']}}]});
      const text=await (await handle.getFile()).text();
      if(text.trim()){
        const disk=layoutCore.validate(JSON.parse(text));
        if(JSON.stringify(disk)!==JSON.stringify(base))throw Error('В выбранном файле другое расположение. Откройте его кнопкой «Файл расположений», затем повторите правки.');
        layoutFileRevision=disk.revision;
      }else layoutFileRevision=base.revision;
      layoutFileHandle=handle;
    }
    const handle=layoutFileHandle;
    if(handle.queryPermission&&await handle.queryPermission({mode:'readwrite'})!=='granted'){
      if(!interactive||!handle.requestPermission||await handle.requestPermission({mode:'readwrite'})!=='granted')throw Error('Нет доступа к файлу — подключите разрешение на запись');
    }
    const text=await (await handle.getFile()).text();
    const disk=text.trim()?layoutCore.validate(JSON.parse(text)):layoutCore.empty();
    if(text.trim()&&(disk.revision!==layoutFileRevision||JSON.stringify(disk)!==JSON.stringify(base)))throw Error('Файл расположений изменён извне. Правки не перезаписаны; перечитайте файл перед сохранением.');
    const committed=layoutCore.commit(snapshot,base.revision);
    const writable=await handle.createWritable();
    try{await writable.write(JSON.stringify(committed,null,2)+'\n');const latest=await (await handle.getFile()).text();if(latest!==text)throw Error('Файл расположений изменён во время записи; черновик не применён.');await writable.close();}catch(error){if(writable.abort)try{await writable.abort();}catch(_){}throw error;}
    const checked=layoutCore.validate(JSON.parse(await (await handle.getFile()).text()));
    if(JSON.stringify(checked)!==JSON.stringify(committed))throw Error('Проверка записанного файла не совпала');
    // Commands issued after the snapshot remain an unsaved draft, even on another graph.
    layoutPendingCommands=layoutPendingCommands.slice(savedCommandCount);
    layoutFileRevision=checked.revision;layoutLastSaved=Date.now();layoutAutoBlocked='';installLayoutBase(checked);persistLayoutDraft();
    try{localStorage.setItem(layoutCacheKey,JSON.stringify(checked));}catch(_){}
    if(graph){applyLayoutPositions();render();}
    await rememberLayoutHandle(handle);
    message('Расположение сохранено в '+handle.name+' · ревизия '+checked.revision+
      (layoutDirty?'. Новые перемещения остались в черновике.':''));
    return layoutCore.validate(checked);
  }
  function saveLayout({interactive=true}={}){
    if(layoutSaving)return Promise.reject(Error('Дождитесь завершения файловой операции'));
    if(layoutReading)return Promise.reject(Error('Дождитесь завершения файловой операции'));
    if(!sourceGraph)return Promise.reject(Error('Сначала откройте граф'));
    if(interactive){layoutAutoBlocked='';const capture=captureLayoutCommand();if(capture)recordLayoutCommands([capture]);}
    if(!layoutDirty)return Promise.resolve(layoutCore.validate(layoutDocument));
    const snapshot=layoutCore.validate(layoutDocument),base=layoutCore.validate(layoutBaseDocument),count=layoutPendingCommands.length;
    layoutSaving=true;updateLayoutControls();
    const task=async()=>{
      try{
        const write=()=>writeLayoutSnapshot(snapshot,base,count,interactive);
        if(typeof navigator!=='undefined'&&navigator.locks?.request&&layoutFileHandle)
          return await navigator.locks.request('rdg-layout-write:'+GRAPH_ROOT_URL,write);
        return await write();
      }catch(error){
        layoutAutoBlocked=/изменён|ревизи|другое расположение/.test(error.message)?'Конфликт версий — изменения не записаны':
          /разрешени|доступ/.test(error.message)?'Нет доступа к файлу — подключите разрешение':
          error.name==='AbortError'?'Выбор файла отменён · локальный черновик':'Ошибка записи — повторите сохранение';
        persistLayoutDraft();throw error;
      }finally{layoutSaving=false;layoutSavePromise=null;updateLayoutControls();scheduleLayoutSave();}
    };
    layoutSavePromise=task();return layoutSavePromise;
  }
  async function initializeLayouts(manifest){
    if(layoutReady)return;layoutReady=true;
    let doc=layoutCore.validate(manifest.layouts||layoutCore.empty());
    const handle=await restoredLayoutHandle();
    if(handle&&(!handle.queryPermission||await handle.queryPermission({mode:'read'})==='granted')){
      try{doc=layoutCore.validate(JSON.parse(await (await handle.getFile()).text()));layoutFileHandle=handle;layoutFileRevision=doc.revision;installLayoutBase(doc);await restoreLayoutDraft();return;}catch(_){}
    }
    try{doc=layoutCore.validate(JSON.parse(await readLocalFile('layouts.json')));}
    catch(_){try{const cache=localStorage.getItem(layoutCacheKey);if(cache){const cached=layoutCore.validate(JSON.parse(cache));if(cached.revision>doc.revision)doc=cached;}}catch(_){}}
    installLayoutBase(doc);await restoreLayoutDraft();
  }
  function exportLayout(){
    const capture=captureLayoutCommand();
    const draft=capture?layoutCore.apply(layoutDocument,capture):layoutDocument;
    const data=layoutCore.commit(draft,layoutDocument.revision),a=document.createElement('a');
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'}));
    a.href=url;a.download='layouts.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    message('JSON подготовлен к скачиванию. Для общей записи сохраните его в graphs/layouts.json.');return data;
  }
  host.rdgLayout={getDocument:()=>layoutCore.validate(layoutDocument),graphKey:currentLayoutKey,apply:layoutCommand,save:saveLayout,attachFile:attachLayoutFile,
    drafts:listLayoutDrafts,recoverDraft:recoverLayoutDraft,
    pause:()=>{layoutAutoPaused=true;updateLayoutControls();scheduleLayoutSave();},
    resume:()=>{layoutAutoPaused=false;updateLayoutControls();scheduleLayoutSave();},
    status:()=>({dirty:layoutDirty,saving:layoutSaving,paused:layoutAutoPaused,blocked:layoutAutoBlocked,lastSaved:layoutLastSaved}),
    load:document=>{if(layoutSaving||layoutReading||layoutDirty)throw Error('Есть несохранённые изменения или файловая операция');collectionPositions.clear();for(const state of fullViewStates.values())delete state.positions;layoutFileHandle=null;layoutFileRevision=null;layoutLastSaved=null;layoutAutoBlocked='';installLayoutBase(document);persistLayoutDraft();if(graph){layout();render();}return layoutCore.validate(layoutDocument);}};

  root.innerHTML = [
    '<style>:host{position:fixed;right:14px;bottom:94px;z-index:2147483600;color:#e4edf7;font:13px system-ui}',
    'button,input,select{font:inherit}button{cursor:pointer;border:1px solid #506681;border-radius:6px;background:#263b52;color:white;padding:7px}',
    '#launch{background:#295779;cursor:grab;touch-action:none;user-select:none}#launch:active{cursor:grabbing}#panel{display:none;position:fixed;inset:20px;background:#101b29;border:1px solid #45596c;border-radius:10px;box-shadow:0 12px 35px #0009;flex-direction:column}',
    '#panel.open{display:flex}#bar{position:relative;display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:9px 49px 9px 9px;background:#1a2a3d}#bar #close{position:absolute;top:9px;right:9px}',
    '#bar strong{margin-right:auto;font-size:16px}#viewer-version{font-size:12px;color:#b8c9da;white-space:nowrap}#bar input,#bar select{background:#102235;border:1px solid #526680;color:white;padding:7px;min-width:150px}',
    '#message{padding:8px;color:#b8c9da}#content{display:flex;flex:1;min-height:0}svg{width:100%;height:100%;background:#111d2a;touch-action:none;cursor:grab}',
    '#canvas-wrap{flex:1;min-width:0;min-height:0;position:relative;overflow:hidden}#canvas{position:absolute;inset:0;display:block}#inspector-toggle{display:block;position:absolute;right:8px;top:8px;z-index:1;background:#263b52}#pan-hint{display:none;position:absolute;left:8px;right:8px;bottom:7px;text-align:center;pointer-events:none;font-size:12px;color:#ddedf9;background:#0e2030d9;border:1px solid #4a657a;border-radius:6px;padding:5px 7px}#content.info-open #info{display:block}#info{display:none;width:355px;max-width:38%;overflow:auto;border-left:1px solid #42546a;padding:16px;font-size:14px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}',
    '#catalog{flex:1;min-height:0;overflow:auto;padding:26px 34px;background:linear-gradient(180deg,#142437,#101b29 45%)}',
    '#catalog-header{max-width:1050px;margin:0 auto 26px}#catalog h2{font-size:23px;font-weight:650;margin:0 0 8px}#catalog p{color:#9fb2c7;margin:0;font-size:14px}',
    '#graph-list,#folder-list{max-width:1050px;margin:0 auto;display:flex;flex-direction:column;gap:8px}#folder-list{margin-bottom:8px}#catalog-search{display:block;box-sizing:border-box;width:min(100%,1050px);margin:0 auto 16px;background:#102235;color:white;border:1px solid #526680;border-radius:6px;padding:10px}.explorer-row{display:flex;flex-direction:column;text-align:left;gap:5px;padding:15px 18px;background:#1b3047}.explorer-row:hover,.explorer-row:focus-visible{background:#24415e;border-color:#83b5d4}.explorer-title{font-size:16px;font-weight:650}.explorer-meta,.explorer-description{font-size:12px;color:#abc0d4}#folder-back{margin-bottom:16px}',
    '#breadcrumbs{display:flex;gap:5px;align-items:center;flex-wrap:wrap;padding:5px 10px;font-size:12px}#breadcrumbs button{padding:4px 7px;background:transparent}#layout-indicator{display:flex;gap:12px;align-items:center;padding:4px 10px;color:#b8c9da;font-size:12px}#layout-connect{padding:4px 7px}#layout-status[data-state=error]{color:#ffc49d}#layout-status[data-state=saved]{color:#9ed8b4}#layout-status{min-width:120px}.node.graph rect{fill:#213c52;stroke:#8ab8d8}.edge[data-relation-kind=potential]{stroke-dasharray:7 4}.edge[data-relation-kind=derived],.edge[data-relation-kind=same-requirement]{stroke-dasharray:2 5}.node.graph:focus rect{stroke:#dbf1ff;stroke-width:3}',
    '#catalog[hidden],#folder-list[hidden],#folder-back[hidden],#graph-list[hidden],#edge-toolbar[hidden],#content[hidden],#source-view[hidden],#source[hidden],#level-up[hidden],#back[hidden],#reload[hidden],#fit[hidden],#search[hidden]{display:none}',
    '#source-view{flex:1;min-height:0;overflow:auto;padding:24px;background:#111d2a}#source-text{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;max-width:1150px;margin:auto;color:#d7e5f2}',

    '@keyframes rdg-appear{from{opacity:0}to{opacity:1}}@media(prefers-reduced-motion:no-preference){.node.appearing{animation:rdg-appear .18s ease-out}}.node rect{fill:#263c52;stroke:#7590aa;stroke-width:1.5;rx:9}.node.requirement rect{fill:#183b50;stroke:#84b7d2}',
    '.node.decision rect{fill:#4a3724;stroke:#ccb17f}.node.context rect{fill:#264536;stroke:#80b499}.node.option rect{fill:#34415c;stroke:#9fbded}.node.action rect{fill:#294457;stroke:#9bc6d7}.node.collection rect{fill:#3b3254;stroke:#c0a8e6}.node.canon rect{fill:#244454;stroke:#63bdd2;stroke-dasharray:4 2}',
    '.node .qrpe-badge{fill:#7c4235;stroke:#eda987;stroke-width:1}.node .qrpe-badge-label{fill:#fff0d6;font-size:10px;font-weight:700}.node .guide-badge{fill:#285572;stroke:#8fbedb;stroke-width:1}.node .guide-badge-label{fill:#edf7ff;font-size:10px;font-weight:650}.node.selected rect{stroke:#ffe096;stroke-width:3}.node.root rect{stroke:#e5db9f;stroke-width:2.5}.node.drill rect{stroke:#88d4ff;stroke-width:2.3}.node.dim{opacity:.2}.node text{fill:#f3f5fa;font-size:13px;pointer-events:none}.node text.node-kind{font-size:12px}',
    '.edge{fill:none;stroke:#c0d2e2;stroke-width:1.9}.edge.g-core{stroke:#d2dce7;stroke-width:2.1}',
    '.edge.g-ground{stroke:#94b9cc;stroke-dasharray:8 4}.edge.g-origin{stroke:#a7c9ac;stroke-dasharray:4 3}',
    '.edge.g-ready{stroke:#d3be9e;stroke-dasharray:10 3 2 3}.edge.g-review{stroke:#d0a7b1;stroke-dasharray:2 4}',
    '.edge.g-scope{stroke:#c8bae4;stroke-dasharray:6 5}.edge.g-other{stroke:#a7b3c0;stroke-dasharray:5 5}',
    '.edge-label{cursor:pointer}.edge-label rect{fill:#152637;stroke:#466079;stroke-width:.8;rx:4;opacity:.98}',
    '.node.graph[data-branch-state=alternative] rect{fill:#1b2d3c;stroke:#566d80;stroke-dasharray:5 3}.node.graph[data-branch-state=unknown] rect{fill:#233440;stroke:#7d909f;stroke-dasharray:2 3}.node.graph[data-branch-state=alternative] text{fill:#c6d3de}.node.graph.selected rect,.node.graph:focus rect{stroke:#e5f1fa;stroke-width:3;stroke-dasharray:5 3}.edge[data-branch-state=alternative]{stroke:#617587;stroke-width:1.3}.edge-label[data-branch-state=alternative] rect{fill:#16232e;stroke:#4c6274}.edge-label[data-branch-state=alternative] text{fill:#c6d3de}',
    '.node.requirement[data-branch-state=potential] rect,.node.option[data-branch-state=potential] rect{fill:#182938;stroke:#738b9b;stroke-dasharray:6 4}.node.requirement[data-branch-state=potential] text,.node.option[data-branch-state=potential] text{fill:#d2dce4}.node.requirement[data-branch-state=actual] rect{stroke:#9fd0da}.node.decision[data-branch-state=actual] rect{stroke:#9fd0da}',
    '.edge-label text{font:11px system-ui;fill:#edf4fb;pointer-events:none}.edge-label.selected rect{stroke:#ffe096;stroke-width:2}',
    '.edge.selected{stroke:#ffe096;stroke-width:3}.edge.dim,.edge-label.dim{opacity:.13}.edge-label:hover rect{fill:#29435a;stroke:#cde5f7}',
    '#edge-toolbar{padding:8px 12px;border-bottom:1px solid #334d63;display:flex;flex-wrap:wrap;align-items:center;gap:9px;max-height:108px;overflow:auto}',
    '#layout-controls summary{cursor:pointer;border:1px solid #506681;border-radius:6px;padding:7px;background:#263b52}#layout-controls .layout-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}#edge-toolbar:has(#layout-controls[open]){max-height:220px}#edge-toolbar[hidden]{display:none}#edge-toolbar button[aria-pressed="true"]{background:#375773;border-color:#acd8f5}',
    '#edge-legend{display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-size:12px;color:#cfdfeb}',
    '.edge-legend-item{white-space:nowrap}.edge-legend-symbol{display:inline-block;width:22px;margin-right:5px;border-bottom:2px solid #ddd;vertical-align:middle}',
    '.edge-legend-symbol.g-ground{border-bottom-style:dashed;border-bottom-color:#94b9cc}',
    '.edge-legend-symbol.g-origin{border-bottom-style:dotted;border-bottom-color:#a7c9ac}',
    '.edge-legend-symbol.g-ready{border-bottom-style:dashed;border-bottom-color:#d3be9e}',
    '.edge-legend-symbol.g-review{border-bottom-style:dotted;border-bottom-color:#d0a7b1}',
    '.edge-legend-symbol.g-scope{border-bottom-style:dashed;border-bottom-color:#c8bae4}',
    '#workflow-panel{overflow:auto;max-height:58vh;flex-shrink:0;padding:14px;background:#17283b}#workflow-panel[hidden],#workflow-toggle[hidden]{display:none}#workflow-panel input,#workflow-panel textarea,#workflow-panel select{box-sizing:border-box;max-width:100%;background:#102235;color:white;padding:7px;border:1px solid #526680;border-radius:5px}#workflow-panel textarea{width:100%;min-height:54px}#workflow-panel label{display:block;margin:6px 0}#workflow-panel .wf-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}#workflow-panel button{margin:4px}#workflow-panel .wf-status{white-space:pre-wrap;padding:8px}#workflow-panel .wf-error{color:#ffc49d}#workflow-panel ul{padding-left:22px}#info a{color:#a7dcff}#info a:visited{color:#d2c0ff}#info section{border-top:1px solid #42546a;padding-top:8px}#info small{color:#adbfcd}',
    '@media(max-width:650px){#panel{inset:4px}#bar{gap:6px;padding:7px 48px 7px 7px;flex-shrink:0}#bar strong{font-size:14px}#message{max-height:58px;overflow:auto;flex-shrink:0}#content{flex-direction:column}#canvas-wrap{min-height:0}#info{display:none;width:auto;max-width:none;min-height:0;max-height:38%;box-sizing:border-box;flex:0 0 auto;border-left:none;border-top:1px solid #42546a;padding:12px;font-size:13px;line-height:1.4}#content.info-open #info{display:block}#inspector-toggle{display:block}#edge-toolbar{gap:5px;flex-shrink:0;max-height:92px}#edge-label-hint,#edge-legend{display:none}#pan-hint{display:block}}',
    '@media(max-width:650px) and (max-height:650px){#bar{max-height:28vh;overflow:auto}#message{max-height:40px}#edge-toolbar{max-height:70px}}</style>',
    '<button id="launch">Граф R–D</button><section id="panel"><div id="bar">',
    '<button id="back" hidden>← Назад</button><button id="level-up" hidden>← Уровень выше</button><button id="example-set-map" hidden>Карта набора графов</button><strong id="bar-title">Графы R–D</strong><span id="viewer-version" title="Версия скрипта R-D Graph Viewer" aria-label="Версия Viewer"></span>',
    '<button id="workflow-toggle" hidden>План и история</button><button id="file">Другой JSON</button><button id="source" hidden>Исходный модуль</button><button id="reload" hidden>Обновить</button><button id="fit" hidden title="Показывает всю схему; не меняет координаты блоков">Показать всю схему</button>',
    '<input type="search" id="search" hidden placeholder="Найти узел"><button id="close" aria-label="Закрыть">×</button></div>',
    '<div id="breadcrumbs" aria-label="Путь"></div><div id="layout-indicator"><span id="layout-status" role="status" aria-live="polite"></span><button id="layout-connect">Подключить файл расположений</button></div><div id="message">Загрузка локальных графов…</div>',
    '<div id="catalog"><div id="catalog-header"><button id="folder-back" hidden>← Все папки</button><h2 id="catalog-title">Папки графов</h2>',
    '<p id="catalog-description">Выберите папку, чтобы открыть рабочие графы, примеры или готовые 2D-модели.</p></div>',
    '<input id="catalog-search" type="search" placeholder="Найти папку, набор или граф" aria-label="Поиск в проводнике"><div id="folder-list" aria-label="Папки графов"></div>',
    '<div id="graph-list" aria-label="Графы и наборы"></div></div>',
    '<div id="edge-toolbar" hidden><span>Отношения:</span><button id="edges-core" aria-pressed="true" title="Требование → решение → дочерние требования. Дополнительные основания и контекст скрыты. Показ всех вариантов управляется отдельной кнопкой.">Основная цепочка</button><button id="edges-all" aria-pressed="false" title="Дополнительно показывает основания, контекст, вопросы и другие связи текущего графа. Невыбранные варианты включаются отдельно.">Связи и контекст</button><button id="variants-all" aria-pressed="false">Показать все варианты</button><button id="context-fields">Поля контекста</button><button id="context-mode" hidden aria-pressed="false">Просмотр контекста: выкл.</button><button id="collections-collapse" hidden>Свернуть в группы</button><details id="layout-controls"><summary>Расположение</summary><div class="layout-actions"><button id="layout-save">Записать сейчас</button><button id="layout-pause">Приостановить автосохранение</button><button id="layout-open">Файл расположений</button><button id="layout-export">Экспорт расположения</button><button id="layout-reset">Авторасположение</button><button id="layout-discard">Отменить правки расположения</button><button id="layout-drafts">Восстановить черновик…</button></div><div id="layout-draft-list" class="layout-actions"></div></details><div id="edge-legend"></div><span id="edge-label-hint"></span></div>',
    '<section id="workflow-panel" hidden aria-label="План и история"></section>',
    '<div id="content" hidden><div id="canvas-wrap"><svg id="canvas"></svg><button id="inspector-toggle" aria-controls="info" aria-expanded="false">Сведения</button><div id="pan-hint">↔ Перетащите схему: продолжение за краем экрана</div></div><aside id="info">Выберите узел или подпись стрелки.</aside></div>',
    '<div id="source-view" hidden><pre id="source-text"></pre></div></section>',
    '<input type="file" id="picker" accept=".json,application/json" hidden>'
  ].join('');
  const el = id => root.getElementById(id);
  el('viewer-version').textContent='Viewer v'+VIEWER_VERSION;
  const svg = el('canvas'), info = el('info');
  function setInspector(open){
    el('content').classList.toggle('info-open',open);
    el('inspector-toggle').setAttribute('aria-expanded',String(open));
    el('inspector-toggle').textContent=open?'Скрыть сведения':'Сведения';
  }
  el('inspector-toggle').onclick=()=>{
    setInspector(!el('content').classList.contains('info-open'));
    if(selected)centerNode(selected);else fit();
  };
  const message = text => { el('message').textContent = text; };
  const launcher = el('launch');
  if (!launcher) throw new Error('[RDG] Launcher was not created');
  console.info('[RDG Viewer] loaded v'+VIEWER_VERSION);
  const launcherPositionKey = 'rdg-viewer-launcher-position-v1';
  let launcherDrag = null;
  let suppressLauncherClickUntil = 0;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  function positionLauncher(x, y) {
    const rightmost = Math.max(8, window.innerWidth - launcher.offsetWidth - 8);
    const lowest = Math.max(8, window.innerHeight - launcher.offsetHeight - 8);
    host.style.right = 'auto';
    host.style.bottom = 'auto';
    host.style.left = clamp(x, 8, rightmost) + 'px';
    host.style.top = clamp(y, 8, lowest) + 'px';
  }
  try {
    const stored = JSON.parse(localStorage.getItem(launcherPositionKey));
    if (stored && Number.isFinite(stored.x) && Number.isFinite(stored.y))
      positionLauncher(stored.x, stored.y);
  } catch (_) { /* Local storage can be unavailable in restricted contexts. */ }
  launcher.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    const rect = launcher.getBoundingClientRect();
    launcherDrag = { id: event.pointerId, startX: event.clientX,
      startY: event.clientY, x: rect.left, y: rect.top, moved: false };
    launcher.setPointerCapture(event.pointerId);
  });
  launcher.addEventListener('pointermove', event => {
    if (!launcherDrag || event.pointerId !== launcherDrag.id) return;
    const dx = event.clientX - launcherDrag.startX;
    const dy = event.clientY - launcherDrag.startY;
    if (!launcherDrag.moved && Math.hypot(dx, dy) < 6) return;
    launcherDrag.moved = true;
    positionLauncher(launcherDrag.x + dx, launcherDrag.y + dy);
  });
  function endLauncherDrag(event) {
    if (!launcherDrag || event.pointerId !== launcherDrag.id) return;
    if (launcherDrag.moved) {
      suppressLauncherClickUntil = Date.now() + 350;
      try {
        localStorage.setItem(launcherPositionKey, JSON.stringify({
          x: parseFloat(host.style.left), y: parseFloat(host.style.top)
        }));
      } catch (_) { /* The button remains movable without persistence. */ }
    }
    launcherDrag = null;
  }
  launcher.addEventListener('pointerup', endLauncherDrag);
  launcher.addEventListener('pointercancel', endLauncherDrag);
  window.addEventListener('resize', () => {
    if(viewportWidth===window.innerWidth&&viewportHeight===window.innerHeight)return;
    viewportWidth=window.innerWidth;viewportHeight=window.innerHeight;
    if (host.style.left) positionLauncher(parseFloat(host.style.left), parseFloat(host.style.top));
    if(graph&&!el('content').hidden){if(selected)centerNode(selected);else fit();}

  });
  function folderLabel(id){return catalogModel?.folders.find(f=>f.id===id)?.title||id||'Папки';}
  function rememberFullView(){if(fullMode&&sourceGraph)fullViewStates.set(activeFullRootSlug,{view:{...view},search:el('search').value,showAlternatives:showAllVariants,showDetails:showAuxiliaryEdges,positions:[...positions].map(([id,p])=>[id,{...p}])});}
  function breadcrumbs(){
    const target=el('breadcrumbs');target.replaceChildren();
    const add=(title,fn)=>{const button=document.createElement('button');button.textContent=title;button.onclick=fn;target.appendChild(button);};
    add('Папки',()=>openFolder(''));
    let prefix='';
    for(const piece of (selectedFolder||'').split('/').filter(Boolean)){
      prefix=prefix?prefix+'/'+piece:piece;const id=prefix;add(folderLabel(id),()=>openFolder(id));
    }
    if(activeFullRootSlug&&!el('content').hidden){const full=catalogModel?.fullGraphs.find(g=>g.slug===activeFullRootSlug);if(full)add(full.title,()=>openFullGraph(full.slug));}
    if(!fullMode&&!el('content').hidden&&graph){const title=document.createElement('span');title.textContent=graphRoot(graph)?.title||graph.title||'Граф';target.appendChild(title);}
  }
  function openFolder(id){
    explorerStates.set(selectedFolder,{query:el('catalog-search').value,scroll:el('catalog').scrollTop||0});
    selectedFolder=id;activeFullRootSlug=null;
    showCatalog();
    const state=explorerStates.get(id);el('catalog-search').value=state?.query||'';renderCatalog();el('catalog').scrollTop=state?.scroll||0;
  }
  function showCatalog(){
    rememberFullView();
    el('catalog').hidden=false;el('content').hidden=true;el('edge-toolbar').hidden=true;
    el('source-view').hidden=true;el('source').hidden=true;
    for(const id of ['back','level-up','example-set-map','reload','fit','search'])el(id).hidden=true;
    levelStack=[];renderCatalog();
    el('bar-title').textContent=folderLabel(selectedFolder);
    message(catalogModel?'Выберите папку и полный граф Requirements; старые одиночные графы остаются доступными отдельно.':'Загрузка локальных графов…');
    breadcrumbs();updateLayoutControls();
  }
  function showGraph(){
    el('catalog').hidden=true;el('content').hidden=false;el('edge-toolbar').hidden=false;el('source-view').hidden=true;
    el('context-mode').hidden=!fullMode;
    el('context-mode').setAttribute('aria-pressed',String(stateMode));
    el('context-mode').textContent='Просмотр контекста: '+(stateMode?'вкл.':'выкл.');
    renderEdgeLegend();
    el('source').hidden=fullMode||sourceMarkdownFor(graph)===null;el('source').textContent='Исходный модуль';
    for(const id of ['back','fit','search'])el(id).hidden=false;
    el('reload').hidden=false;
    el('level-up').hidden=fullMode||!(levelStack.length||incomingToGraph(activeSlug).length);
    el('level-up').textContent=levelStack.at(-1)?.reference?'← К предыдущему графу':'← Уровень выше';
    const opened=graphs.find(x=>x.slug===activeSlug);
    if(!activeFullRootSlug&&!fullMode)activeFullRootSlug=null;
    el('example-set-map').hidden=fullMode||!activeFullRootSlug;
    el('example-set-map').textContent='К полному графу';
    el('edges-core').textContent=fullMode?'Только Requirements':'Основные связи';
    el('edges-all').textContent=fullMode?'Показать всё':'Связи и контекст';
    el('bar-title').textContent=fullMode?graph.title:graphRoot(graph)?.title||graph?.title||'Граф';
    for(const id of ['edges-core','edges-all'])el(id).hidden=false;
    el('search').placeholder=fullMode?'Найти Requirement':'Найти узел';
    fit(!fullMode);breadcrumbs();updateLayoutControls();
  }
  function outgoingForRequirement(slug,id){return graphRelations.filter(r=>r.from===slug&&r.requirementId===id);}
  function incomingToGraph(slug){return graphRelations.filter(r=>r.to===slug);}
  function childLevelForRequirement(id){
    if(id===graphRoot(graph)?.id)return null;
    const matches=outgoingForRequirement(activeSlug,id);
    if(matches.length===1)return matches[0].to;
    return sourceGraph?.edges.some(e=>e.from===id&&e.archived!==true&&['OPTION_FOR','DRIVES','DERIVES'].includes(e.type))?
      {localRootId:id}:null;
  }
  function graphRoot(g) {
    if(!g?.nodes)return null;
    if(g.rootRequirementId)return g.nodes.find(n=>n.id===g.rootRequirementId&&n.kind==='requirement')||null;
    // Older teaching files start with their main R. This display fallback
    // does not create identities, hierarchy links or new persisted records.
    const first=g.nodes[0];
    if(first?.kind!=='requirement'||g.edges?.some(e=>e.type==='INTRODUCES'&&e.to===first.id))return null;
    return g.nodes.length===1||g.edges?.some(e=>e.type==='DRIVES'&&e.from===first.id)?first:null;
  }
  function isUnit(item){return (item.planningScale||item.graph?.planningScale)==='unit';}
  function scaleLabel(g){return g?.planningScale==='unit'?'Узкая задача · Unit':'План · TM';}
  function sourceMarkdownFor(g){
    const seen=new Set();
    while(g && typeof g.sourceMarkdown!=='string' && g.sourceOwnerGraphSlug){
      if(seen.has(g.sourceOwnerGraphSlug))return null;
      seen.add(g.sourceOwnerGraphSlug);g=graphs.find(x=>x.slug===g.sourceOwnerGraphSlug)?.graph;
    }
    return typeof g?.sourceMarkdown==='string'?g.sourceMarkdown:null;
  }
  function graphCaption(item){return graphRoot(item.graph)?.title||item.title||item.slug;}
  function usageLabel(p){return p?.usage==='ready'?'Готовый':p?.usage==='working'?'Рабочий':'Назначение не указано';}
  function itemMeta(item){
    const p=item.presentation||{};
    return [item.kind==='folder'?'Папка':item.kind==='full-graph'?'Полный граф':'Граф',
      item.kind==='folder'?'':usageLabel(p),p.exampleOnly?'Учебный':'',p.archived?'Архив':'',
      item.graph?.readOnly?'Только чтение':''].filter(Boolean).join(' · ');
  }
  function renderCatalog(){
    const list=el('graph-list'),folderList=el('folder-list');list.replaceChildren();folderList.replaceChildren();
    list.hidden=false;folderList.hidden=false;
    el('folder-back').hidden=!selectedFolder;
    el('catalog-title').textContent=folderLabel(selectedFolder);
    el('catalog-description').textContent=catalogModel?.folders.find(f=>f.id===selectedFolder)?.presentation?.description||'Папки и полные графы Requirements';
    if(!catalogModel)return;
    const query=el('catalog-search').value||'';
    const entries=query.trim()?catalogCore.searchCatalog(catalogModel,query):catalogCore.listFolder(catalogModel,selectedFolder);
    for(const item of entries){
      const row=document.createElement('button');row.type='button';row.className='explorer-row';
      row.setAttribute('data-kind',item.kind);
      if(item.kind==='folder')row.setAttribute('data-folder',item.id);
      else if(item.kind==='full-graph')row.setAttribute('data-full-root',item.slug);
      else row.setAttribute('data-graph',item.slug);
      const title=document.createElement('span');title.className='explorer-title';title.textContent=item.title;row.appendChild(title);
      const meta=document.createElement('span');meta.className='explorer-meta';meta.textContent=itemMeta(item);row.appendChild(meta);
      if(item.presentation?.description){const desc=document.createElement('span');desc.className='explorer-description';desc.textContent=item.presentation.description;row.appendChild(desc);}
      row.onclick=async()=>{
        if(item.kind==='folder'){openFolder(item.id);return;}
        explorerStates.set(selectedFolder,{query:el('catalog-search').value,scroll:el('catalog').scrollTop||0});
        if(item.kind==='full-graph'){await openFullGraph(item.slug);return;}
        activeFullRootSlug=null;selectedFolder=item.folder;
        try{await loadGraphSlug(item.slug);}catch(error){message(error.message);}
      };
      (item.kind==='folder'?folderList:list).appendChild(row);
    }
    if(!entries.length){const empty=document.createElement('p');empty.textContent=query?'Ничего не найдено.':'В этой папке пока нет графов.';list.appendChild(empty);}
  }
  const rootProjection=globalThis.RDGRootProjection;
  function fullProjectedGraph(){
    const wanted=sourceGraph.nodes.filter(n=>
      (showAllVariants||n.branchState!=='potential')&&
      (showAuxiliaryEdges||n.kind==='requirement'));
    const ids=new Set(wanted.map(n=>n.id));
    return {...sourceGraph,nodes:wanted,edges:sourceGraph.edges.filter(e=>
      ids.has(e.from)&&ids.has(e.to)&&(showAllVariants||e.branchState!=='alternative')&&
      (showAuxiliaryEdges?!e.rootOnly:!e.fullDetailOnly)),
      alternativeCount:sourceGraph.nodes.filter(n=>n.kind==='requirement'&&n.branchState==='potential').length};
  }
  async function openFullGraph(slug,{fresh=false}={}){
    if(!catalogModel)throw Error('Каталог ещё не загружен');
    // A user-requested refresh reads a NEW index and ALL files in this
    // identitySpace. Do not blend stale embedded graphs with current files.
    // Only swap the catalog after every source and the projection validates.
    const manifest=fresh?JSON.parse(await readLocalFile('index.json')):null;
    const nextCatalog=fresh?catalogCore.normalizeCatalog(manifest):catalogModel;
    const entry=nextCatalog.fullGraphs.find(g=>g.slug===slug);
    if(!entry)throw Error('Корневой граф отсутствует в доступном индексе: '+slug);
    const all=[],missing=[];
    for(const it of nextCatalog.graphs){
      if((it.identitySpace||it.graph?.identitySpace)!==entry.identitySpace)continue;
      if(!fresh&&it.graph){all.push(it);continue;}
      try{
        const graph=validate(JSON.parse(await readLocalFile(it.file)));
        if(graph.identitySpace!==entry.identitySpace||
           graph.rootRequirementId!==(it.rootRequirementId||graph.rootRequirementId))
          throw Error('Расхождение identitySpace/rootRequirementId с индексом');
        all.push({...it,graph});
      }catch(error){
        if(fresh)throw Error('Полный граф не обновлён: '+it.slug+' — '+error.message);
        missing.push(it.slug);
      }
    }
    const data=rootProjection.project({graphs:all,relations:nextCatalog.relations},slug);
    // Preserve current content and navigation if the refresh fails.
    rememberFullView();
    if(fresh){
      for(const item of all)nextCatalog.graphs.find(g=>g.slug===item.slug).graph=item.graph;
      catalogModel=nextCatalog;graphs=catalogModel.graphs;
      graphRelations=catalogModel.relations.filter(r=>r&&
        graphs.some(g=>g.slug===r.from)&&graphs.some(g=>g.slug===r.to));
      stateSources=manifest.stateGraphs||[];
      projectContexts=manifest.projectContexts&&typeof manifest.projectContexts==='object'?manifest.projectContexts:{};
      sourceUpdateAlerts=Array.isArray(manifest.sourceUpdateAlerts)?manifest.sourceUpdateAlerts:[];
      refreshedSpaces.add(entry.identitySpace);
      renderCatalog();
    }
    const indexedBySlug=new Map(all.map(g=>[g.slug,g]));
    // The same D/Option can have exact projectionOf representations in child
    // files. Show its authoritative semantic record only once in full detail.
    const canonicalCause=(slug,record)=>{
      let owner=slug,node=record;const visited=new Set();
      while(node?.projectionOf){
        const ref=node.projectionOf,key=ref.graphSlug+'|'+ref.nodeId;
        if(visited.has(key))break;visited.add(key);
        const candidate=indexedBySlug.get(ref.graphSlug)?.graph;
        const target=candidate?.nodes.find(n=>n.id===ref.nodeId&&n.kind===node.kind);
        if(!target||candidate.identitySpace!==data.identitySpace)break;
        owner=ref.graphSlug;node=target;
      }
      return {id:'__cause__'+owner+'::'+node.id,sourceGraphSlug:owner,node};
    };
    const decisionAccepted=rootProjection.decisionGuard(indexedBySlug,data.identitySpace);
    const activeProjectionDecision=(d,g)=>decisionAccepted(d,g);
    const nodes=data.nodes.map(n=>({...n,graphSlug:n.sourceGraphSlug}));
    const edges=[];
    const extras=new Map();
    for(const a of data.edges){
      const effective=nodes.find(n=>n.id===a.to)?.branchState==='potential'||
        nodes.find(n=>n.id===a.from)?.branchState==='potential'?'potential':a.kind;
      const state=effective==='potential'||effective==='prepared'?'alternative':'selected';
      const relation={from:a.from,to:a.to,requirementId:a.to,relationKind:a.kind,childRole:a.childRole,
        originatingOptionId:a.causeKind==='option'?a.causeId:null,
        introducedByDecisionId:a.causeKind==='decision'?a.causeId:null,
        introducedByActionId:a.causeKind==='action'?a.causeId:null,
        sourceGraphSlug:a.sourceGraphSlug};
      const item=indexedBySlug.get(a.sourceGraphSlug);
      const cause=item?.graph.nodes.find(n=>n.id===a.causeId && n.kind===a.causeKind);
      if(cause && ['decision','option','action'].includes(a.causeKind)){
        const owner=canonicalCause(a.sourceGraphSlug,cause),causeKey=owner.id;
        if(!extras.has(causeKey))extras.set(causeKey,{...owner.node,id:causeKey,
          title:owner.node.title,branchState:state==='alternative'?'potential':'actual',sourceGraphSlug:owner.sourceGraphSlug});
        edges.push({id:'__r_details_from__'+a.id,type:'VIEW_SET_'+a.kind.toUpperCase(),from:causeKey,to:a.to,
          branchState:state,relation,meaning:'Порождает R: '+a.to});
      }
      edges.push({id:'__r_full__'+a.id,type:'VIEW_SET_'+(a.kind==='refinement'?'DERIVED':a.kind==='potential'||state==='alternative'?'POTENTIAL':a.kind.toUpperCase()),
        from:a.from,to:a.to,branchState:state,relation,
        meaning:'R → R по '+a.causeKind+' '+a.causeId});
    }
    // Full detail includes ALL prepared options and decisions directly attached
    // to reached Requirements, even when a variant introduces no new R.
    // The R-only projection never renders these as source Requirements.
    const reached=new Map(nodes.map(n=>[n.id,n]));
    const attached=new Set();
    for(const it of all){
      if(it.graph.identitySpace!==data.identitySpace)continue;
      const g=it.graph,by=new Map(g.nodes.map(n=>[n.id,n]));
      for(const edge of g.edges){
        if(edge.archived===true||!['OPTION_FOR','DRIVES'].includes(edge.type)||!reached.has(edge.from))continue;
        const cause=by.get(edge.to);
        if(!cause||!(edge.type==='OPTION_FOR'?cause.kind==='option':
          (cause.kind==='decision'||g.actionModel==='candidate-v6'&&cause.kind==='action'))||
          cause.active===false||cause.status==='inactive')continue;
        const currentParent=reached.get(edge.from).branchState==='actual';
        // Same authorization semantics as the R-only root projection.
        const selected=(cause.kind==='action'&&rootProjection.actionActive(cause,g,edge.from))||
          (cause.kind==='decision'&&activeProjectionDecision(cause,g,it.slug))||
          (cause.kind==='option'&&g.nodes.some(d=>d.kind==='decision'&&
            d.active!==false&&activeProjectionDecision(d,g,it.slug)&&d.selectedOptionId===cause.id));
        const effective=currentParent&&selected?'actual':'potential';
        const owner=canonicalCause(it.slug,cause),causeKey=owner.id;
        if(!extras.has(causeKey))extras.set(causeKey,{...owner.node,id:causeKey,
          sourceGraphSlug:owner.sourceGraphSlug,branchState:effective});
        const attachmentKey=edge.from+'→'+causeKey;
        if(attached.has(attachmentKey))continue;
        attached.add(attachmentKey);
        const id='__attachment__'+it.slug+'::'+edge.id;
        const relation={from:edge.from,to:edge.to,requirementId:edge.from,
          relationKind:effective==='actual'?'selected':'potential',sourceGraphSlug:it.slug,
          originatingOptionId:cause.kind==='option'?cause.id:null,
          introducedByDecisionId:cause.kind==='decision'?cause.id:null,
          introducedByActionId:cause.kind==='action'?cause.id:null};
        edges.push({id,type:effective==='actual'?'VIEW_SET_SELECTED':'VIEW_SET_POTENTIAL',
          from:edge.from,to:causeKey,branchState:effective==='actual'?'selected':'alternative',
          relation,fullDetailOnly:true,meaning:'Способ/вариант для R '+edge.from});
      }
    }
    // In the detailed mode replace each R→R shortcut with its exact cause.
    for(const e of edges)if(e.id.startsWith('__r_details_'))e.fullDetailOnly=true;
    for(const e of edges)if(e.id.startsWith('__r_full__')&&e.relation.relationKind!=='refinement')e.rootOnly=true; // DERIVES remains visible in both modes.
    const state=fullViewStates.get(slug);
    fullMode=true;activeFullRootSlug=slug;selectedFolder=entry.folder;activeSlug=null;localRootId=null;levelStack=[];
    showAllVariants=state?.showAlternatives??entry.presentation?.usage==='ready';
    showAuxiliaryEdges=state?.showDetails??false;
    expandedCollections=new Set();selected=null;selectedEdge=null;setInspector(false);
    fullGraphData={rootSlug:slug,projection:data,entry,missing,fresh:fresh||refreshedSpaces.has(entry.identitySpace)};
    sourceGraph={schemaVersion:1,id:'full:'+slug,revision:1,title:entry.title,identitySpace:data.identitySpace,
      rootRequirementId:data.rootRequirementId,readOnly:true,exampleOnly:entry.presentation?.exampleOnly===true,
      nodes:[...nodes,...extras.values()],edges};
    graph=fullProjectedGraph();el('search').value=state?.search||'';
    layout();render();showGraph();
    if(state){for(const [id,p] of state.positions||[])if(positions.has(id))positions.set(id,p);
      applyLayoutPositions();render();Object.assign(view,state.view);transform();}
    message('Полный граф R · '+entry.title+' · '+data.nodes.length+' R'+
      (fullGraphData.fresh?' · ранее перечитано из файлов по обновлённому индексу':' · встроенная копия; для изменений нажмите «Обновить»')+
      (missing.length?' · НЕПОЛНЫЙ каталог: '+missing.length+' недоступных файлов':''));
  }
  async function openFullRequirement(n){
    if(n.kind!=='requirement')return;
    const space=sourceGraph.identitySpace;
    const matching=graphs.filter(g=>g.graph?.identitySpace===space&&
      g.graph.rootRequirementId===n.id&&g.slug!==n.sourceGraphSlug&&
      (g.graph.expansionOf?.nodeId===n.id||
       g.graph.nodes.some(x=>x.kind==='requirement'&&x.id===n.id&&x.projectionOf?.nodeId===n.id)));
    if(matching.length>1){
      setInspector(true);info.textContent='Для '+n.title+' найдены несколько представлений. Выберите нужное:';
      for(const item of matching){const button=document.createElement('button');
        button.textContent=item.title;button.onclick=()=>{
          rememberFullView();void loadGraphSlug(item.slug,{localRootId:n.id}).catch(e=>message(e.message));};info.appendChild(button);}
      return;
    }
    rememberFullView();
    await loadGraphSlug(matching[0]?.slug||n.sourceGraphSlug,{localRootId:n.id});
  }
  function projectFullGraph(){return fullProjectedGraph();}
  function graphBranchCaption(n){
    return n.branchState==='potential'?'Потенциальная R · не принята':'Requirement текущего пути';
  }
  function layoutFullGraph(){
    positions=new Map();layoutBands=[];
    // Calculate geometry from what is ACTUALLY on screen. Hidden D/Options
    // must not create invisible generations or distort R-only spacing.
    const indegree=new Map(graph.nodes.map(n=>[n.id,0])),depth=new Map(),children=new Map(graph.nodes.map(n=>[n.id,[]]));
    for(const e of graph.edges){
      if(!indegree.has(e.to)||!children.has(e.from))continue;
      indegree.set(e.to,indegree.get(e.to)+1);children.get(e.from).push(e.to);
    }
    const queue=graph.nodes.filter(n=>!indegree.get(n.id)).map(n=>n.id);
    queue.forEach(id=>depth.set(id,0));
    for(let i=0;i<queue.length;i++)for(const child of children.get(queue[i])){
      // DERIVES is a refinement of the same planning problem, not a
      // next-generation Requirement introduced by a chosen method.
      // Keep source R and its composite refinement in one visual column.
      const refinement=graph.edges.some(e=>e.from===queue[i]&&e.to===child&&
        e.relation?.relationKind==='refinement');
      depth.set(child,Math.max(depth.get(child)||0,Math.min(30,depth.get(queue[i])+(refinement?0:1))));
      indegree.set(child,indegree.get(child)-1);if(!indegree.get(child))queue.push(child);
    }
    const columns=new Map();
    for(const n of graph.nodes){const d=depth.get(n.id)||0;if(!columns.has(d))columns.set(d,[]);columns.get(d).push(n);}
    const incoming=new Map(graph.nodes.map(n=>[n.id,graph.edges.filter(e=>e.to===n.id)]));
    const group=n=>{
      const e=(incoming.get(n.id)||[]).find(e=>e.relation?.originatingOptionId)||
        (incoming.get(n.id)||[]).find(e=>e.relation?.introducedByDecisionId)||
        (incoming.get(n.id)||[])[0];
      return e?.relation?.originatingOptionId||e?.relation?.introducedByDecisionId||e?.from||'';
    };
    const maxRows=Math.max(1,...[...columns.values()].map(xs=>xs.length));
    for(const [d,items] of columns){
      items.sort((a,b)=>(a.branchState==='potential'?1:0)-(b.branchState==='potential'?1:0)||
        group(a).localeCompare(group(b))||a.id.localeCompare(b.id));
      items.forEach((n,i)=>positions.set(n.id,{x:48+d*450,y:72+(maxRows-items.length)*72+i*160}));
    }
    const visible=new Set(graph.nodes.map(n=>n.id));for(const id of positions.keys())if(!visible.has(id))positions.delete(id);
    applyLayoutPositions();
  }
  const edgeDefinitions={
    VIEW_SET_UNKNOWN:{label:'Путь не подтверждён',group:'other',detail:'Тип или основание перехода не подтверждено. Он не объявляется выбранным решением.'},
    VIEW_SET_SELECTED:{label:'Дочерняя R',group:'core',detail:'Переход по выбранному разбиению. Учебный выбор не является решением проекта.'},
    VIEW_SET_PREPARED:{label:'Готовое разбиение',group:'core',detail:'Подготовленный состав, не принятое решение проекта.'},
    VIEW_SET_POTENTIAL:{label:'Потенциальная R',group:'ready',detail:'Будущее продолжение непринятого варианта; не факт исполнения.'},
    VIEW_SET_DERIVED:{label:'Уточнение R',group:'scope',detail:'Уточнение содержания, не выбранное D.'},
    VIEW_SET_SAME_REQUIREMENT:{label:'Та же R',group:'scope',detail:'Другое представление записи той же идентичности.'},
    DRIVES:{label:'требует ответа от D',group:'core',detail:'Requirement является драйвером конкретного Decision; само по себе не означает разбиение.'},
    INTRODUCES:{label:'вводит дочерний R',group:'core',detail:'Решение о разбиении вводит конкретное дочернее Requirement.'},
    DERIVES:{label:'уточняется в R',group:'core',detail:'Содержательное уточнение R, не подмена INTRODUCES.'},
    CONTEXT_FOR:{label:'задаёт условия выбора',group:'ground',detail:'Контекст является основанием/условием решения; не создаёт Requirement.'},
    INFORMS:{label:'передаёт содержание в D',group:'ground',detail:'Содержательная часть одного ответа используется в другом решении; не дочерний Requirement.'},
    IDENTIFIES:{label:'выявляет требование',group:'origin',detail:'Решение обнаружило актуальное Requirement; это не декомпозиция родительской цели.'},
    REVEALS_NEED:{label:'выявляет потребность',group:'origin',detail:'Анализ ответа обнаружил отдельную потребность; не обязательное под-R.'},
    USES_VARIANT:{label:'использует готовый вариант',group:'ready',detail:'Конкретное D или кандидат ссылается на готовый переиспользуемый способ.'},
    OPTION_FOR:{label:'имеет вариант ответа',group:'ready',detail:'Потенциально доступный способ ответа на R, не принятый выбор.'},
    USES_PREPARED:{label:'использует заготовку',group:'ready',detail:'Условное конкретное решение использует подготовленный способ.'},
    PER_ITEM_MODEL:{label:'использует модель элемента',group:'ready',detail:'Повторяемая готовая модель, не количество конкретных применений.'},
    GENERATES_ITEM_ROLE:{label:'задаёт роль элемента',group:'ready',detail:'Роль повторяемого Requirement в готовой схеме; не фактическая ветвь.'},
    INSTANCE_OF_MODEL:{label:'имеет конкретное применение',group:'ready',detail:'Отдельное применение общей модели, не копия её определения.'},
    GOVERNED_BY_SHARED_CHOICE:{label:'задаёт общий способ',group:'ready',detail:'Одно конкретное решение задаёт способ для нескольких применений.'},
    QRPE_FOR:{label:'ставит вопрос к R или D',group:'review',detail:'Вопрос необходимости R или достаточности D; не принятое изменение.'},
    RECONSIDERS:{label:'предлагает пересмотр',group:'review',detail:'Кандидат предлагает пересмотреть выбор; ещё не пересмотренное Decision.'},
    APPLIES_TO:{label:'распространяется на',group:'scope',detail:'Одно сквозное R применяется к другой R, но не является дочерней задачей.'},
    OUTCOME_OF:{label:'возможная под-R',group:'ready',detail:'Потенциальная дочерняя R непринятого способа. Не является текущим обязательством.'},
    VIEW_COLLECTION:{label:'группировка',group:'core',detail:'Список Requirements. Раскрытие показывает только его R; продолжения R открываются отдельными графами.'},
    VIEW_CANON:{label:'показывает канон',group:'ready',detail:'Отдельный блок только для просмотра. Не является R, D, фактом или самостоятельным ребром данных.'}
  };
  const edgeGroups=[
    ['core','Планирование / разбиение'],['ground','Основания выбора'],
    ['origin','Происхождение R'],['ready','Готовые варианты'],
    ['review','Проверка / пересмотр'],['scope','Область действия'],
    ['other','Другие связи']
  ];
  const edgeMeta=type=>edgeDefinitions[type]||{label:String(type),group:'other',detail:'Иллюстративная связь без отдельного согласованного контракта.'};
  // A prepared option is visible by default while its own R has no selected D.
  // A selected ancestor cannot hide options of an undecided child R.
  function optionVisible(id) {
    if(showAllVariants)return true;
    const edge=graph.edges.find(e=>e.type==='OPTION_FOR'&&e.to===id);
    if(!edge)return true;
    return !(sourceGraph?.nodes||graph.nodes).some(n=>n.kind==='decision'&&['committed','selected-in-example-only'].includes(n.status)&&
      n.selectedOptionId&&(sourceGraph?.edges||graph.edges).some(x=>x.type==='OPTION_FOR'&&x.from===edge.from&&x.to===n.selectedOptionId));
  }
  const spineEdge=e=>fullMode||e.type==='VIEW_CANON'||edgeMeta(e.type).group==='core'||
    (e.type==='OPTION_FOR'&&graph.nodes.some(n=>n.id===e.to&&n.kind==='option')&&optionVisible(e.to))||
    (e.type==='OUTCOME_OF'&&optionVisible(e.from));
  const edgeIsVisible=e=>e.archived!==true&&positions.has(e.from)&&positions.has(e.to)&&
    (showAuxiliaryEdges||spineEdge(e));
  const edgeLabel=e=>{
    if(!fullMode)return e.templateOnly&&e.type==='INTRODUCES'?'готовое разбиение · под-R':
      e.templateOnly&&e.type==='DRIVES'?'готовый способ для R':edgeMeta(e.type).label;
    if(e.relation?.relationKind==='refinement')return 'Уточнение R';
    const from=graph.nodes.find(n=>n.id===e.from),to=graph.nodes.find(n=>n.id===e.to);
    const prospective=e.branchState==='alternative';
    if(from?.kind==='requirement'&&to?.kind==='action')
      return prospective?'Action · кандидат':'Action · выбран';
    if(from?.kind==='action'&&to?.kind==='requirement')return prospective?'Возможная R':'R введена Action';
    if(from?.kind==='requirement'&&to?.kind==='decision')
      return prospective?'Рассматривается D':sourceGraph.exampleOnly?'Учебное выбранное D':'Принятое D';
    if(from?.kind==='requirement'&&to?.kind==='option')
      return prospective?'Вариант для R':'Выбранный вариант';
    if(from?.kind==='decision'&&to?.kind==='requirement')
      return prospective?'Возможная R':sourceGraph.exampleOnly?'R от учебно выбранного D':'R от принятого D';
    if(from?.kind==='option'&&to?.kind==='requirement')return 'Возможная R от варианта';
    return prospective?'Возможная R':'Действующая R';
  };
  function renderEdgeLegend(){
    const legend=el('edge-legend');legend.replaceChildren();
    if(!graph)return;
    if(fullMode){
      legend.textContent='Сплошные связи — выбранные Requirements; потенциальные ветви отмечены отдельно. Ни один режим просмотра не принимает решение.'+
        (fullGraphData?.fresh?' Данные перечитаны из файлов по обновлённому индексу.':
          ' Встроенная копия: после изменения файлов нажмите «Обновить».');
      el('edge-label-hint').textContent='Requirements: '+graph.nodes.filter(n=>n.kind==='requirement').length+
        ' · переходов: '+graph.edges.length+(fullGraphData.missing.length?' · возможны недоступные продолжения':'');
      el('variants-all').hidden=!sourceGraph.nodes.some(n=>n.branchState==='potential');
      el('variants-all').setAttribute('aria-pressed',String(showAllVariants));
      el('variants-all').textContent=showAllVariants?'Принятое':'Все ветви';
      el('edges-all').setAttribute('aria-pressed',String(showAuxiliaryEdges));
      el('edges-core').setAttribute('aria-pressed',String(!showAuxiliaryEdges));
      el('collections-collapse').hidden=true;return;
    }
    const present=new Set(graph.edges.filter(edgeIsVisible).map(e=>edgeMeta(e.type).group));
    for(const [group,caption] of edgeGroups){
      if(!present.has(group) || (!showAuxiliaryEdges&&group!=='core'))continue;
      const entry=document.createElement('span');entry.className='edge-legend-item';
      const sample=document.createElement('span');sample.className='edge-legend-symbol g-'+group;
      entry.appendChild(sample);const label=document.createElement('span');
      label.textContent=caption+' ('+graph.edges.filter(e=>edgeIsVisible(e)&&edgeMeta(e.type).group===group).length+')';entry.appendChild(label);legend.appendChild(entry);
    }
    el('edge-label-hint').textContent=(showAuxiliaryEdges?'Связи и контекст текущего графа; основания и вопросы вынесены отдельно. Невыбранные варианты включаются отдельной кнопкой.':'Основной R и его цепочка ответов: '+positions.size+' из '+graph.nodes.length+' записей. Остальные доступны через «Связи и контекст».')+' Нажмите стрелку для пояснения; колесо — вверх/вниз, Shift + колесо — влево/вправо, Ctrl + колесо — масштаб. Перетаскивание — перемещение.';
    el('edges-all').setAttribute('aria-pressed',String(showAuxiliaryEdges));
    el('edges-core').setAttribute('aria-pressed',String(!showAuxiliaryEdges));
    el('variants-all').hidden=sourceGraph?.templateOnly===true||!!graphRoot(graph)&&!sourceGraph.edges.some(e=>e.from===graphRoot(graph).id&&
      (e.type==='OPTION_FOR'||e.type==='DRIVES'&&sourceGraph.actionModel==='candidate-v6'));
    el('collections-collapse').hidden=!(graph?.collections||[]).some(c=>c.memberRefs.length>2);
    el('collections-collapse').disabled=expandedCollections.size===0;
    el('variants-all').setAttribute('aria-pressed',String(showAllVariants));
    el('variants-all').textContent=showAllVariants?'Скрыть невыбранные':'Показать все варианты';
  }
  function validate(g) {
    if (!g || g.schemaVersion !== 1 || !Array.isArray(g.nodes) || !Array.isArray(g.edges))
      throw Error('Нужны schemaVersion=1, nodes[] и edges[]');
    if(g.planningScale!==undefined&&!['module','unit'].includes(g.planningScale))throw Error('Некорректный масштаб графа');
    if (g.nodes.length > 500) throw Error('В этой версии максимум 500 узлов');
    const ids = new Set(), eid = new Set();
    for (const n of g.nodes) {
      if (!n || typeof n.id !== 'string' || typeof n.title !== 'string' || typeof n.kind !== 'string' || ids.has(n.id))
        throw Error('Некорректный или повторный узел: ' + (n && n.id));
      ids.add(n.id);
    }
    for (const e of g.edges) {
      if (!e || !e.id || eid.has(e.id) || !ids.has(e.from) || !ids.has(e.to) || !e.type)
        throw Error('Некорректная связь: ' + (e && e.id));
      eid.add(e.id);
      if (e.type === 'INTRODUCES' && !ids.has(e.parent)) throw Error('Нет parent для ' + e.id);
    }
    if (g.events !== undefined) {
      if (!Array.isArray(g.events)) throw Error('events должен быть массивом');
      const eventIds=new Set();
      for(const e of g.events){
        if(!e || typeof e.id!=='string' || !e.id.trim() || eventIds.has(e.id) ||
           typeof e.type!=='string' || !e.type.trim() ||
           (e.decisionId!==undefined && !g.nodes.some(n=>n.id===e.decisionId&&n.kind==='decision'))||
           (e.actionId!==undefined && !g.nodes.some(n=>n.id===e.actionId&&n.kind==='action'))) 
          throw Error('Некорректное событие: '+(e&&e.id));
        eventIds.add(e.id);
      }
    }
    for(const n of g.nodes){
      for(const key of ['answerParts','answerBindings','delegations']){
        if(n[key]!==undefined && (!Array.isArray(n[key])||n[key].some(x=>!x||typeof x!=='object')))
          throw Error('Некорректное поле '+key+' узла '+n.id);
      }
    }
    for(const n of g.nodes){
      if(n.answerParts?.some(p=>typeof p.id!=='string'||typeof p.text!=='string'))
        throw Error('Некорректная часть ответа '+n.id);
      if(n.answerBindings?.some(b=>typeof b.requirementId!=='string'||!Array.isArray(b.parts)||b.parts.some(p=>typeof p!=='string')||typeof b.sufficiency!=='string'))
        throw Error('Некорректная адресация ответа '+n.id);
    }
    if(g.collections!==undefined){
      if(!Array.isArray(g.collections))throw Error('collections должен быть массивом');
      const names=new Set();
      for(const c of g.collections){
        if(!c||typeof c.id!=='string'||names.has(c.id)||!ids.has(c.anchor)||!Array.isArray(c.memberRefs)||new Set(c.memberRefs).size!==c.memberRefs.length||
          c.memberRefs.some(id=>id===g.rootRequirementId||!g.nodes.some(n=>n.id===id&&n.kind==='requirement')))
          throw Error('Группа '+(c?.id||'?')+' должна содержать только R с уникальными ID и допустимым anchor');
        names.add(c.id);
      }
    }
    return g;
  }
  function make(tag, parent, attrs, text) {
    const n = document.createElementNS(ns, tag);
    for (const [key,val] of Object.entries(attrs || {})) n.setAttribute(key, String(val));
    if (text !== undefined) n.textContent = text;
    parent.appendChild(n); return n;
  }
  function label(s) {
    const words = String(s).split(/\s+/), result = [''];
    for (const w of words) {
      const i = result.length-1;
      if ((result[i]+' '+w).length > 27 && result[i]) result.push(w);
      else result[i] = (result[i]+' '+w).trim();
    }
    return result.slice(0,2).map((x,i) => x.length > 27 || i===1&&result.length>2 ? x.slice(0,26)+'…' : x);
  }
  function layout() {
    if(fullMode){layoutFullGraph();return;}
    positions=new Map();layoutBands=[];
    const order=new Map(graph.nodes.map((n,i)=>[n.id,i]));
    const coreEdges=graph.edges.filter(e=>e.archived!==true&&spineEdge(e));
    const adjacent=new Map(graph.nodes.map(n=>[n.id,[]]));
    for(const e of coreEdges){adjacent.get(e.from).push(e.to);adjacent.get(e.to).push(e.from);}
    const rootId=graphRoot(graph)?.id;
    const main=new Set(),queue=rootId?[rootId]:[];
    for(let i=0;i<queue.length;i++){
      const id=queue[i];if(main.has(id))continue;main.add(id);
      for(const next of adjacent.get(id)||[])if(!main.has(next))queue.push(next);
    }
    if(!main.size)for(const e of coreEdges){main.add(e.from);main.add(e.to);}
    if(!rootId&&!coreEdges.length){
      graph.nodes.forEach((n,i)=>positions.set(n.id,{x:48+(i%3)*420,y:72+Math.floor(i/3)*124}));
      layoutBands.push({text:'Записи · основной R не задан',x:48,y:50});
      graphWidth=Math.max(360,...[...positions.values()].map(p=>p.x+262));
      graphHeight=Math.max(180,...[...positions.values()].map(p=>p.y+112));applyLayoutPositions();return;
    }
    // "Связи и контекст" adds relation layers, but must not turn on hidden alternatives.
    const hidden=new Set(graph.nodes.filter(n=>n.kind==='option'&&!optionVisible(n.id)).map(n=>n.id));
    let changed=true;
    while(changed){changed=false;for(const e of graph.edges){
      if(e.type==='OUTCOME_OF'&&e.archived!==true&&hidden.has(e.from)&&!hidden.has(e.to)&&
         !graph.edges.some(x=>x.type==='INTRODUCES'&&x.to===e.to&&x.archived!==true)){
        hidden.add(e.to);changed=true;
      }
    }}
    const visible=showAuxiliaryEdges?new Set(graph.nodes.filter(n=>!hidden.has(n.id)).map(n=>n.id)):
      new Set([...main].filter(id=>!hidden.has(id)));
    const core=new Set([...main,...coreEdges.flatMap(e=>[e.from,e.to])].filter(id=>visible.has(id)));
    const unseen=new Set(core),components=[];
    for(const first of [rootId,...core]){
      if(!unseen.has(first))continue;
      const members=[],todo=[first];unseen.delete(first);
      for(let i=0;i<todo.length;i++){
        const id=todo[i];members.push(id);
        for(const next of adjacent.get(id)||[])if(unseen.delete(next))todo.push(next);
      }
      components.push(members);
    }
    let nextY=72;
    // Rank only the actual R-D spine. Auxiliary records never become root peers
    // merely because a particular relationship is absent from the rank graph.
    const arrange=(ids,relations,caption)=>{
      if(!ids.length)return;
      const set=new Set(ids),out=new Map(ids.map(id=>[id,[]])),inc=new Map(ids.map(id=>[id,0]));
      const links=relations.filter(e=>set.has(e.from)&&set.has(e.to)&&e.from!==e.to);
      for(const e of links){out.get(e.from).push(e.to);inc.set(e.to,inc.get(e.to)+1);}
      const depth=new Map(),todo=ids.filter(id=>!inc.get(id));
      for(const id of todo)depth.set(id,0);
      for(let i=0;i<todo.length;i++)for(const id of out.get(todo[i])){
        depth.set(id,Math.max(depth.get(id)||0,(depth.get(todo[i])||0)+1));
        inc.set(id,inc.get(id)-1);if(!inc.get(id))todo.push(id);
      }
      // Cyclic reference/review links are displayed, without a fictitious rank.
      for(const id of ids)if(!depth.has(id))depth.set(id,0);
      const columns=new Map();
      for(const id of ids){const d=depth.get(id);if(!columns.has(d))columns.set(d,[]);columns.get(d).push(id);}
      const ranks=[...columns.keys()].sort((a,b)=>a-b);
      for(const xs of columns.values())xs.sort((a,b)=>order.get(a)-order.get(b));
      // Barycentric ordering reduces branch crossings; IDs are identity, not order.
      for(let pass=0;pass<4;pass++){
        const traversal=pass%2?[...ranks].reverse():ranks;
        const slot=new Map();for(const xs of columns.values())xs.forEach((id,i)=>slot.set(id,i));
        for(const rank of traversal){
          const xs=columns.get(rank),score=id=>{
            const ns=links.filter(e=>pass%2?e.from===id:e.to===id).map(e=>pass%2?e.to:e.from);
            return ns.length?ns.reduce((sum,n)=>sum+slot.get(n),0)/ns.length:slot.get(id);
          };
          const scores=new Map(xs.map(id=>[id,score(id)]));
          xs.sort((a,b)=>scores.get(a)-scores.get(b)||order.get(a)-order.get(b));
          xs.forEach((id,i)=>slot.set(id,i));
        }
      }
      const rows=Math.max(...[...columns.values()].map(xs=>xs.length));
      layoutBands.push({text:caption,x:48,y:nextY-22});
      for(const [rank,xs] of columns){
        const shift=(rows-xs.length)*124/2;
        xs.forEach((id,i)=>positions.set(id,{x:48+rank*420,y:nextY+shift+i*124}));
      }
      nextY+=rows*124+68;
    };
    components.forEach((ids,i)=>arrange(ids,coreEdges,i===0?'Основной R → конкретный ответ D → под-R':'Связанная цепочка R → D'));
    if(showAuxiliaryEdges){
      const extras=graph.nodes.filter(n=>visible.has(n.id)&&!core.has(n.id));
      const groups=[['grounds','Основания и контекст'],['ready','Готовые варианты и применения'],['review','Вопросы и пересмотр'],['other','Другие записи']];
      const category=n=>n.kind==='context'||n.kind==='decision'?'grounds':
        ['variant','application','target_module'].includes(n.kind)||n.templateRole||
        graph.edges.some(e=>e.archived!==true&&edgeMeta(e.type).group==='ready'&&(e.from===n.id||e.to===n.id))?'ready':
        ['question','proposal','problem','risk'].includes(n.kind)?'review':'other';
      for(const [key,caption]of groups){
        const ids=extras.filter(n=>category(n)===key).map(n=>n.id);
        let links=graph.edges.filter(e=>e.archived!==true&&edgeMeta(e.type).group!=='review');
        if(!links.some(e=>ids.includes(e.from)&&ids.includes(e.to))){
          // Independent records fill a compact grid instead of one tall column.
          if(!ids.length)continue;
          layoutBands.push({text:caption,x:48,y:nextY-22});
          ids.forEach((id,i)=>positions.set(id,{x:48+(i%3)*420,y:nextY+Math.floor(i/3)*124}));
          nextY+=Math.ceil(ids.length/3)*124+68;
        }else arrange(ids,links,caption);
      }
    }
    applyLayoutPositions();
    graphWidth=Math.max(360,...[...positions.values()].map(p=>p.x+262));
    graphHeight=Math.max(180,...[...positions.values()].map(p=>p.y+112));
  }
  function centerNode(id){
    const p=positions.get(id);
    if(!p)return;
    view.x=(svg.clientWidth||800)/2-(p.x+111)*view.scale;
    view.y=(svg.clientHeight||500)/2-(p.y+36)*view.scale;
    transform();
  }
  function transform() {
    const scene=el('scene');
    if(scene)scene.setAttribute('transform','translate('+view.x+' '+view.y+') scale('+view.scale+')');
  }
  function fit(readable=true) {
    if(!graph)return;
    const w=svg.clientWidth||800,h=svg.clientHeight||500,points=[...positions.values()];
    if(!points.length)return;
    const bounds=renderBounds||{minX:Math.min(...points.map(p=>p.x)),minY:Math.min(...points.map(p=>p.y)),maxX:Math.max(...points.map(p=>p.x+222)),maxY:Math.max(...points.map(p=>p.y+72))};
    const minX=bounds.minX-20,minY=bounds.minY-30;
    const width=bounds.maxX+20-minX,height=bounds.maxY+20-minY;
    const fitted=Math.min(1.1,(w-30)/width,(h-30)/height);
    const minimum=.82;
    view.scale=readable===false?Math.max(.07,fitted):Math.max(minimum,fitted);
    view.x=width*view.scale>w-29?16-minX*view.scale:(w-width*view.scale)/2-minX*view.scale;
    const goal=positions.get(graphRoot(graph)?.id);
    view.y=height*view.scale>h-29&&goal?h/2-(goal.y+36)*view.scale:(h-height*view.scale)/2-minY*view.scale;
    transform();
  }
  function render() {
    svg.replaceChildren();
    const defs=make('defs',svg),marker=make('marker',defs,
      {id:'rdg-arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto'});
    make('path',marker,{d:'M0,0 L10,5 L0,10 z',fill:'#92a9bb'});
    const scene=make('g',svg,{id:'scene'}),edges=make('g',scene);
    const leaderLayer=make('g',scene,{id:'edge-label-leaders','pointer-events':'none'});
    const nodes=make('g',scene);
    const labels=make('g',scene,{id:'edge-labels'});
    const visibleNodes=graph.nodes.filter(n=>positions.has(n.id));
    graphWidth=Math.max(360,...[...positions.values()].map(p=>p.x+262));
    graphHeight=Math.max(180,...[...positions.values()].map(p=>p.y+112));
    for(const band of layoutBands)make('text',scene,{x:band.x,y:band.y,fill:'#b8cfe0','font-size':14,'font-weight':600,'data-layout-band':band.text},band.text);
    const occupied=visibleNodes.map(n=>{
      const p=positions.get(n.id);return {x:p.x,y:p.y,w:222,h:72};
    });
    const nodeBoxes=visibleNodes.map(n=>({...positions.get(n.id),w:222,h:72,id:n.id}));
    renderStateCard(scene,occupied,nodeBoxes);
    const routes=[];
    const clean=points=>points.filter((p,i)=>!i||p[0]!==points[i-1][0]||p[1]!==points[i-1][1])
      .filter((p,i,xs)=>!i||i===xs.length-1||!((xs[i-1][0]===p[0]&&p[0]===xs[i+1][0])||(xs[i-1][1]===p[1]&&p[1]===xs[i+1][1])));
    const hitsNode=(points,source,target)=>points.some((p,i)=>i&&nodeBoxes.some(r=>{
      // Only the first/last port stem may touch its own endpoint rectangle.
      if(i===1&&r.id===source||i===points.length-1&&r.id===target)return false;
      const a=points[i-1],pad=8;
      return a[0]===p[0]?a[0]>r.x-pad&&a[0]<r.x+r.w+pad&&Math.max(a[1],p[1])>r.y-pad&&Math.min(a[1],p[1])<r.y+r.h+pad:
        a[1]>r.y-pad&&a[1]<r.y+r.h+pad&&Math.max(a[0],p[0])>r.x-pad&&Math.min(a[0],p[0])<r.x+r.w+pad;
    }));
    const visibleEdges=graph.edges.filter(edgeIsVisible).sort((a,b)=>(edgeMeta(a.type).group==='core'?0:1)-(edgeMeta(b.type).group==='core'?0:1));
    const route=(e,index)=>{
      const a=positions.get(e.from),b=positions.get(e.to),forward=b.x>a.x,same=b.x===a.x;
      const outgoing=visibleEdges.filter(x=>x.from===e.from),incoming=visibleEdges.filter(x=>x.to===e.to);
      const sy=a.y+12+48*(outgoing.indexOf(e)+1)/(outgoing.length+1);
      let ty=b.y+12+48*(incoming.indexOf(e)+1)/(incoming.length+1);if(e.from===e.to)ty=a.y+60;
      const start=[a.x+(forward||same?222:0),sy],end=[b.x+(forward?0:222),ty];
      const stub=[start[0]+(forward||same?18:-18),sy],tail=[end[0]+(forward?-18:18),ty];
      const candidates=[],track=(index%12)*12;
      const xs=[(stub[0]+tail[0])/2+track,same?Math.max(stub[0],tail[0])+38+track:(stub[0]+tail[0])/2,...nodeBoxes.flatMap(r=>[r.x-28-track,r.x+r.w+28+track])];
      for(const x of xs)candidates.push([start,stub,[x,sy],[x,ty],tail,end]);
      const ys=[(sy+ty)/2,Math.min(sy,ty)-36-track,Math.max(sy,ty)+36+track,...nodeBoxes.flatMap(r=>[r.y-28-track,r.y+r.h+28+track])];
      for(const y of ys)candidates.push([start,stub,[stub[0],y],[tail[0],y],tail,end]);
      const overlap=points=>{
        let penalty=0;
        for(let i=1;i<points.length;i++)for(const old of routes)for(let j=1;j<old.length;j++){
          const a=points[i-1],b=points[i],c=old[j-1],d=old[j];
          if(a[0]===b[0]&&c[0]===d[0]&&a[0]===c[0])penalty+=Math.max(0,Math.min(Math.max(a[1],b[1]),Math.max(c[1],d[1]))-Math.max(Math.min(a[1],b[1]),Math.min(c[1],d[1])))*2;
          if(a[1]===b[1]&&c[1]===d[1]&&a[1]===c[1])penalty+=Math.max(0,Math.min(Math.max(a[0],b[0]),Math.max(c[0],d[0]))-Math.max(Math.min(a[0],b[0]),Math.min(c[0],d[0])))*2;
        }
        return penalty;
      };
      const cost=points=>points.reduce((sum,p,i)=>sum+(i?Math.abs(p[0]-points[i-1][0])+Math.abs(p[1]-points[i-1][1]):0),0)+points.length*12+overlap(points);
      const valid=candidates.map(clean).filter(ps=>!hitsNode(ps,e.from,e.to));
      valid.sort((x,y)=>cost(x)-cost(y));
      const top=Math.min(...nodeBoxes.map(r=>r.y))-40-track;
      const points=valid[0]||clean([start,stub,[stub[0],top],[tail[0],top],tail,end]);
      routes.push(points);return points;
    };
    // Orthogonal routes use separate endpoint ports and avoid other node boxes.
    const routedEdges=visibleEdges.map((e,index)=>({e,points:route(e,index)}));
    const labelBoxes=[];
    for(const {e,points} of routedEdges){
      const meta=edgeMeta(e.type);
      const path=points.map((p,i)=>(i?'L':'M')+p.join(',')).join(' ');
      const visual=make('path',edges,{d:path,class:'edge g-'+meta.group+
        (selectedEdge===e.id?' selected':selectedEdge?' dim':''),'data-edge-id':e.id,...(fullMode?{'data-requirement':e.relation.requirementId,'data-relation-kind':e.relation.relationKind,'data-branch-state':e.branchState}:{}),
        'marker-end':'url(#rdg-arrow)'});
      make('title',visual,{},e.type+' — '+meta.label+(e.meaning?'\n'+e.meaning:''));
      const words=edgeLabel(e),lines=[];
      for(const word of words.split(' ').flatMap(w=>w.match(/.{1,24}/gu)||[])){
        if(!lines.length||lines.at(-1).length+word.length>24)lines.push(word);
        else lines[lines.length-1]+=' '+word;
      }
      if(lines.length>3){lines.splice(3);lines[2]=lines[2].slice(0,22)+'…';}
      const width=Math.max(76,Math.max(...lines.map(l=>l.length))*6.5+20),height=lines.length*14+10;
      const target=nodeBoxes.find(n=>n.id===e.to),last=points.at(-1),anchor={x:last[0],y:last[1]};
      const box=viewGeometry.placeTargetLabel({target,endpoint:anchor,width,height,nodeBoxes,labels:labelBoxes,
        otherRoutes:routedEdges.filter(r=>r.e!==e).map(r=>r.points)});
      labelBoxes.push(box);occupied.push(box);
      const mx=box.x+width/2,my=box.y+height/2;
      const near={x:clamp(anchor.x,box.x,box.x+box.w),y:clamp(anchor.y,box.y,box.y+box.h)};
      make('path',leaderLayer,{d:'M'+anchor.x+','+anchor.y+' L'+near.x+','+near.y,
        fill:'none',stroke:'#617f96','stroke-width':1,'stroke-dasharray':'3 3','data-label-leader':e.id});
      graphWidth=Math.max(graphWidth,box.x+box.w+40);
      graphHeight=Math.max(graphHeight,box.y+box.h+40);
      const group=make('g',labels,{class:'edge-label g-'+meta.group+
        (selectedEdge===e.id?' selected':selectedEdge?' dim':''),'data-edge-id':e.id,
        transform:'translate('+mx+' '+my+')',...(fullMode?{'data-requirement':e.relation.requirementId,'data-relation-kind':e.relation.relationKind,'data-branch-state':e.branchState}:{}),tabindex:0,role:'button',
        'aria-label':e.type+' — '+words,'data-label-target':e.to,'data-label-crowded':String(box.crowded)});
      make('rect',group,{x:-width/2,y:-height/2,width:width,height});
      lines.forEach((line,i)=>make('text',group,{'text-anchor':'middle',y:-height/2+15+i*14},line));
      make('title',group,{},e.type+' — '+words+
        '\n'+meta.detail+(e.meaning?'\nВ примере: '+e.meaning:''));
      const inspect=event=>{event.stopPropagation();chooseEdge(e.id);};
      group.addEventListener('click',inspect);
      group.addEventListener('keydown',event=>{
        if(event.key==='Enter'||event.key===' '){event.preventDefault();inspect(event);}
      });
      visual.addEventListener('click',inspect);
    }
    for(const n of visibleNodes){
      const nextLevel=n.kind==='requirement'?childLevelForRequirement(n.id):null;
      const p=positions.get(n.id),g=make('g',nodes,
        {class:'node '+n.kind+(enteringNodes.has(n.id)?' appearing':'')+(n.id===graphRoot(graph)?.id?' root':'')+(nextLevel?' drill':''),transform:'translate('+p.x+' '+p.y+')','data-id':n.id,...(fullMode?{'data-graph':n.sourceGraphSlug||n.graphSlug,'data-branch-state':n.branchState}:{} )});
      make('rect',g,{width:222,height:72});
      const teachingExample=graphs.find(item=>item.slug===activeSlug)?.group==='examples';
      const canon=['option','action'].includes(n.kind)&&n.canonBlock;
      const canonBadge=canon?' · канон +'+(canon.recommended||[]).length+
        '/−'+(canon.contraindicated||[]).length:'';
      const readableKind={graph:'Граф',requirement:'Требование / цель',decision:'Способ / решение',action:'Action / способ',context:'Условие',canon:'Блок канона (вид)',question:'Вопрос',proposal:'Предложение',variant:'Готовый вариант',application:'Применение',collection:'Группа'};
      make('text',g,{x:10,y:20,'font-weight':'bold',class:'node-kind'},
        fullMode?(n.kind==='requirement'?(n.id===graphRoot(graph)?.id?'R · исходная цель':
          n.branchState==='potential'?'R · потенциальная':'R · текущий путь'):
          n.kind==='option'?'Option · вариант':n.kind==='decision'?'Decision · ответ':n.kind==='action'?'Action · '+n.status:n.id):
        n.kind==='graph'?graphBranchCaption(n):
        n.kind==='canon'?'КАНОН (+'+(n.canonBlock?.recommended||[]).length+'/−'+(n.canonBlock?.contraindicated||[]).length+')':
        n.kind==='collection'?'Группа '+(n.expanded?'▾':'▸'):
        canon?'Вариант · канон':
        teachingExample?(readableKind[n.kind]||'Запись графа'):n.id);
      make('title',g,{},n.title+'\n'+(n.kind==='collection'?'Группа, '+n.memberCount+' R. Нажмите, чтобы '+(n.expanded?'свернуть':'раскрыть')+'.\n':'')+'ID: '+n.id+canonBadge);
      if(n.kind==='canon'){
        const preview=(cases,sign)=>{
          const first=String(cases?.[0]?.text||'нет записей');
          const limit=cases?.length>1?12:24;
          return sign+first.slice(0,limit)+(first.length>limit?'…':'')+
            (cases?.length>1?' (ещё '+(cases.length-1)+')':'');
        };
        make('text',g,{x:10,y:40},preview(n.canonBlock?.recommended,'+ '));
        make('text',g,{x:10,y:56},preview(n.canonBlock?.contraindicated,'− '));
        make('title',g,{},'Канон '+n.canonForId+' (ID и адреса проверки — по клику)');
      }else label(n.title).forEach((line,i)=>make('text',g,{x:10,y:40+i*16},line));
      // Summary badges never change source statuses; no badge means no recorded QRPE.
      const qrpe=n.qrpe||[],open=qrpe.filter(q=>!['resolved','closed','invalidated'].includes(q.status)).length;
      const badge=open?'QRPE !'+open:qrpe.length?'QRPE ✓'+qrpe.length:
        n.kind==='collection'?(n.candidateMemberCount?'Канд. '+n.candidateMemberCount:'R: '+n.memberCount):
        n.kind==='decision'&&!n.selectedOptionId?'Прямое D':
        n.kind==='requirement'&&n.compositeOf?'Композит':'';
      if(badge){
        make('rect',g,{x:147,y:2,width:73,height:21,class:open?'qrpe-badge':'guide-badge',rx:5});
        make('text',g,{x:151,y:17,class:open?'qrpe-badge-label':'guide-badge-label'},badge);
        make('title',g,{},open?'Нерешённые вопросы QRPE: '+open:
          qrpe.length?'Записано QRPE: '+qrpe.length:
          n.compositeOf?'Композитное R':'Прямое D: отдельный вариант/канон не показан.');
      }
      if(nextLevel)make('text',g,{x:196,y:20,'font-size':17},'↗');
      g.style.cursor=nextLevel?'zoom-in':'pointer';
      g.setAttribute('tabindex','0');
      g.setAttribute('role','button');
      g.setAttribute('aria-label',n.title+(fullMode?' · '+graphBranchCaption(n):'')+(canon?' · канон':'')+(n.kind==='collection'?' · '+(n.expanded?'свернуть':'раскрыть'):''));
      if(n.kind==='collection')g.setAttribute('aria-expanded',String(n.expanded));
      g.addEventListener('click',e=>{e.stopPropagation();
        if(Date.now()<suppressNodeClickUntil)return;
        if(fullMode){if(stateMode){showStateFields(n.sourceGraphSlug);return;}if(n.kind!=='requirement'){choose(n.id);return;}void openFullRequirement(n).catch(error=>message(error.message));return;}
        if(n.kind==='collection'){toggleCollection(n.collectionId);return;}
        choose(n.id,false);
        if(nextLevel)openChildLevel(nextLevel);
        else choose(n.id);
      });
      if(!nextLevel)g.addEventListener('keydown',e=>{
        if(fullMode&&(e.key==='Enter'||e.key===' ')){e.preventDefault();if(stateMode){showStateFields(n.sourceGraphSlug);return;}if(n.kind!=='requirement'){choose(n.id);return;}void openFullRequirement(n).catch(error=>message(error.message));return;}
        if(e.key==='Enter'||e.key===' '){e.preventDefault();if(n.kind==='collection')toggleCollection(n.collectionId);else choose(n.id);}
      });
      if(nextLevel)g.addEventListener('keydown',e=>{
        if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(n.id,false);openChildLevel(nextLevel);}
      });
    }
    const routePoints=routes.flat();
    renderBounds=occupied.length?{
      minX:Math.min(...occupied.map(b=>b.x),...routePoints.map(p=>p[0])),
      minY:Math.min(...occupied.map(b=>b.y),...routePoints.map(p=>p[1])),
      maxX:Math.max(...occupied.map(b=>b.x+b.w),...routePoints.map(p=>p[0])),
      maxY:Math.max(...occupied.map(b=>b.y+b.h),...routePoints.map(p=>p[1]))}:null;
    enteringNodes.clear();
    transform();choose(selected&&graph.nodes.some(n=>n.id===selected)?selected:null,false);
  }
  function chooseEdge(id){
    if(fullMode){
      const edge=graph.edges.find(e=>e.id===id);if(!edge)return;
      selected=null;selectedEdge=id;render();setInspector(true);
      const r=edge.relation;
      const describeEnd=id=>{
        const n=sourceGraph.nodes.find(node=>node.id===id);
        return (n?.kind==='decision'?'Decision ':n?.kind==='action'?'Action ':n?.kind==='option'?'Option ':'Requirement ')+
          (n?.id?.startsWith('__cause__')?n.id.split('::').slice(1).join('::'):n?.id||id);
      };
      info.textContent=(r.relationKind==='refinement'?'Содержательное уточнение Requirement: ':'Связь: ')+
        describeEnd(edge.from)+' → '+describeEnd(edge.to)+'\n'+
        'Тип: '+edge.type+' · '+r.relationKind+'\n'+
        'Статус пути: '+(edge.branchState==='alternative'?'ПОТЕНЦИАЛЬНО, НЕ ПРИНЯТО':'ДОСТУПЕН ПО ТЕКУЩЕМУ ПУТИ')+'\n'+
        (r.childRole?'Роль дочерней R: '+(r.childRole==='subgoal'?'подцель разбиения':'корректность выполнения Action')+'\n':'')+
        'Основание: '+(r.relationKind==='refinement'?'DERIVES — уточнение R, НЕ выбранная дочерняя R':r.introducedByActionId?'Action '+r.introducedByActionId:r.introducedByDecisionId?'Decision '+r.introducedByDecisionId:r.originatingOptionId?'Option '+r.originatingOptionId:'прямая связь из source')+
        '\nИсточник записи: '+r.sourceGraphSlug+(sourceGraph.exampleOnly?'\nУчебный выбор не принят в основном проекте.':'')+'\nПросмотр не принимает решения.';
      return;
    }
    const e=graph?.edges.find(x=>x.id===id);
    if(!e)return;
    if(!edgeIsVisible(e)){showAuxiliaryEdges=true;layout();renderEdgeLegend();}
    setInspector(true);
    selected=null;selectedEdge=id;
    render();
    const meta=edgeMeta(e.type);
    const from=graph.nodes.find(n=>n.id===e.from),to=graph.nodes.find(n=>n.id===e.to);
    info.textContent='Отношение: '+edgeLabel(e)+' ('+e.type+')'+
      '\n\n'+e.from+' → '+e.to+
      '\n\nКак читать: «'+(from?.title||e.from)+'» → '+meta.label+' → «'+(to?.title||e.to)+'»'+
      '\n\nИсточник: '+(from?.title||e.from)+
      '\nПолучатель: '+(to?.title||e.to)+
      '\n\nСмысл: '+meta.detail+
      (e.meaning?'\n\nКонкретно в этом примере: '+e.meaning:'')+
      (e.parent?'\n\nРодительский Requirement: '+e.parent:'')+
      '\n\nНаличие связи не подтверждает выполнение R или реализацию D.'+
      (graph.exampleOnly?'\n\nЭто read-only учебная проекция; не каждый тип связи поддержан writer.':'');
  }
  function recordSourceFor(local){
    if(typeof graph.identitySpace!=='string'||!graph.identitySpace.trim())return null;
    let node=local,ownerGraph=graph,slug=activeSlug;const seen=new Set();
    while(node?.projectionOf){
      const ref=node.projectionOf,key=ref.graphSlug+'|'+ref.nodeId;
      if(seen.has(key)||ref.nodeId!==local.id)return null;seen.add(key);
      const item=graphs.find(item=>item.slug===ref.graphSlug);
      if(!item?.graph||item.graph.identitySpace!==graph.identitySpace)return null;
      const next=item.graph.nodes.find(n=>n.id===ref.nodeId&&n.kind===local.kind);
      if(!next)return null;
      node=next;ownerGraph=item.graph;slug=item.slug;
    }
    return node===local?null:{node,graph:ownerGraph,slug};
  }
  // Canon cases are search directions, not evidence that a fact is proven.
  function canonCasesText(cases,checks=[]) {
    const ref=v=>typeof v==='string'?v:
      v&&typeof v==='object'?((v.graphSlug||'текущий граф')+' / '+(v.collectionId||v.id||'?')):String(v);
    if(!cases?.length)return '— случаи не записаны';
    return cases.map(c=>{
      const notes=[];
      if(c.checkRequirements?.length)notes.push('  Проверить R: '+c.checkRequirements.map(ref).join(', '));
      if(c.checkCollections?.length)notes.push('  Проверить Collections: '+c.checkCollections.map(ref).join(', '));
      if(c.checkCategories?.length)notes.push('  Категории поиска (не доказано): '+c.checkCategories.map(ref).join(', '));
      for(const key of ['sourceRef','evidence','source','provenance']){
        if(c[key])notes.push('  '+key+': '+(typeof c[key]==='string'?c[key]:JSON.stringify(c[key])));
      }
      const recorded=(checks||[]).filter(x=>x.canonCaseId===c.id);
      if(recorded.length)notes.push('  Записанные оценки: '+recorded.map(x=>
        (x.requirementId||x.contextRef||'источник не указан')+' · '+x.state+
        (x.impact?' · '+x.impact:'')+(x.knownAt?' · известно '+x.knownAt:'')).join('; '));
      else notes.push('  Применимость в этом контексте: не подтверждена, проверки случая не записаны.');
      return '- ['+(c.id||'без ID')+'] '+c.text+'\n'+notes.join('\n');
    }).join('\n');
  }
  function appendCanonMaterial(n){
    const material=n?.canonBlock;if(!material)return;
    const p=document.createElement('p');p.textContent='Материал канона: '+(material.preparation==='link-only'?'пока только ссылка · список полей неполон':material.interpretation||'интерпретация отдельно не записана');info.appendChild(p);
    const items=new Map([...stateSources,...graphs.filter(i=>i.graph)].map(i=>[i.slug,i]));if(sourceGraph)items.set(sourceGraph.id,{graph:sourceGraph});
    appendSources(info,(material.sourceRefs||[]).map(r=>items.get(r.graphSlug)?.graph.knowledgeSources?.find(x=>x.id===r.sourceId)||r));
  }
  // Read-only full projection: inspect the original kind and semantic ID.
  // Display aliases (__cause__) never turn Options/Decisions into Requirements.
  function fullRecordDetails(n){
    const owner=catalogModel?.graphs.find(item=>item.slug===n.sourceGraphSlug)?.graph;
    const kind=({requirement:'Requirement',decision:'Decision',option:'Option',action:'Action'})[n.kind]||n.kind;
    const id=n.id.startsWith('__cause__')?n.id.split('::').slice(1).join('::'):n.id;
    const completionHistory=(owner?.events||[]).filter(e=>e.targetId===id&&['action_executed','requirement_achieved'].includes(e.type));
    const state=n.kind==='action'&&n.status==='superseded'?
      'Исторический Action · выбор пересмотрен, не действует на текущем пути':
      n.kind==='requirement'?graphBranchCaption(n):
      n.branchState==='potential'?'Вариант / решение пока не принято на текущем пути':
      'Доступно на текущем пути (не равно выполнению)';
    const selected=n.kind==='decision'&&n.selectedOptionId?
      owner?.nodes.find(o=>o.kind==='option'&&o.id===n.selectedOptionId):null;
    const cases=(block,checks)=>block?'\nКанонические ситуации (+):\n'+canonCasesText(block.recommended,checks)+
      '\nКанонические ситуации (−):\n'+canonCasesText(block.contraindicated,checks):'';
    const qrpe=(n.qrpe||[]).map(q=>q.id+' ['+q.status+'] '+q.text+
      (q.recordedAt?' · записано '+q.recordedAt:'')+
      (q.statusHistory?.length?' · История: '+q.statusHistory.map(t=>t.status+' ('+t.recordedAt+')').join(' → '):'')).join('\n');
    return id+' · '+kind+(n.status?' · '+n.status:'')+'\n'+n.title+'\n'+state+
      '\nВладелец: '+n.sourceGraphSlug+
      (owner?.exampleOnly?'\nУЧЕБНЫЙ пример, не принят в основном проекте.':'')+
      (n.kind==='option'?'\nПроисхождение: '+({prepared:'готовый',situational:'ситуативный',adapted:'адаптированный'}[n.origin]||n.origin||'не указано')+
        (n.preparedSource?'\nПодготовленный источник: '+JSON.stringify(n.preparedSource):''):'')+
      (n.kind==='decision'?'\nВыбранный вариант: '+(n.selectedOptionId||'не указан')+
        (selected?' · '+selected.title:''):'')+
      (n.kind==='action'?'\nAction: '+(n.status==='selected'?(completionHistory.length?'выбран; запись выполнения — в истории':'выбран, не доказано исполнение'):n.status==='superseded'?'исторически выбран, затем пересмотрен':'не выбран')+
        '\nВыбор и достижение Requirement — разные факты.':'')+
      (n.kind==='action'&&n.reconsiderationEventId?
        '\nПересмотр: '+n.reconsiderationEventId+' · Action '+(n.reconsideredByActionId||'?')+
        '\nПричина: '+(owner?.events?.find(e=>e.id===n.reconsiderationEventId)?.note||'не указана'):'')+
      (n.description?'\n'+n.description:'')+
      cases(n.canonBlock,n.contextChecks)+
      (selected?.canonBlock?'\nКанон выбранного варианта '+selected.title+cases(selected.canonBlock,selected.contextChecks):'')+
      (n.compositeOf?'\nУточняет: '+n.compositeOf:'')+
      (n.history?.length?'\nИстория R:\n'+n.history.map(h=>h.id+' · '+h.statement+' · записано '+h.recordedAt+
        (h.knownAt?' · известно '+h.knownAt:'')+(h.effectiveAt?' · действует '+h.effectiveAt:'')).join('\n'):'')+
      (n.kind==='action'?'\nТип Action: '+(n.actionType==='decomposition'?'выделение подцели / связанного набора подцелей':'общий'):'')+
      (completionHistory.length?'\n\nИстория результатов (в своей сохранённой композиции):\n'+completionHistory.map(e=>e.id+' · '+(e.type==='action_executed'?'выполнен Action':'достигнута R')+' · '+e.note).join('\n'):'')+
      '\n\nQRPE:\n'+(qrpe||'Нет записанных QRPE; это не доказывает отсутствия рисков.')+
      (n.selectionBasis?'\n\nОснование выбора (известно '+(n.selectionBasis.knownAt||'не указано')+'): '+
        (n.selectionBasis.rationale||n.selectionBasis.note||'не указано')+
        (n.selectionBasis.acceptedContraindicationCaseIds?.length?'\nОсознанные противопоказания: '+n.selectionBasis.acceptedContraindicationCaseIds.join(', '):'')+
        (n.selectionBasis.outstandingRiskIssueIds?.length?'\nОткрытые QRPE: '+n.selectionBasis.outstandingRiskIssueIds.join(', '):'')+
        '\nИсторический снимок:\n'+JSON.stringify(n.selectionBasis,null,2):'')+
      (n.source?'\nИсточник: '+n.source:'')+
      '\nПросмотр не принимает D и не изменяет исходные файлы.';
  }
  function choose(id,center=true){
    if(fullMode){
      selected=id;
      for(const node of root.querySelectorAll('.node'))node.classList.toggle('selected',node.getAttribute('data-id')===id);
      const record=graph.nodes.find(n=>n.id===id);
      if(record){
        info.textContent=fullRecordDetails(record);
        appendCanonMaterial(record);
        if(center){setInspector(true);centerNode(id);}
      }else{
        info.textContent=graph.title+'\n'+graph.nodes.filter(n=>n.kind==='requirement').length+
          ' Requirements. Корневая R: '+sourceGraph.rootRequirementId+
          '\nФайл-источник не ограничивает полный граф.';
        for(const r of fullGraphData?.projection?.supplementaryViews||[]){
          const button=document.createElement('button');button.textContent='Связанное представление '+r.relationKind+': '+r.toGraphSlug;
          button.onclick=()=>loadGraphSlug(r.toGraphSlug);info.appendChild(button);
        }
      }
      return;
    }
    if(id&&!positions.has(id)){showAuxiliaryEdges=true;layout();render();renderEdgeLegend();}
    if(id && selectedEdge){selectedEdge=null;render();}
    selected=id;
    if(id&&center)setInspector(true);
    for(const node of root.querySelectorAll('.node')){
      const nId=node.getAttribute('data-id'),n=graph.nodes.find(x=>x.id===nId);
      const q=el('search').value.trim().toLowerCase();
      node.classList.toggle('selected',id===nId);
      const focusedEdge=selectedEdge?graph.edges.find(e=>e.id===selectedEdge):null;
      node.classList.toggle('dim',!!focusedEdge&&nId!==focusedEdge.from&&nId!==focusedEdge.to||!!q&&!(n.id+' '+n.title).toLowerCase().includes(q)&&id!==nId);
    }
    if(!id){
      const count=Array.isArray(graph.events)?graph.events.length:0;
      const modernOptions=graph.nodes.filter(n=>['option','action'].includes(n.kind)&&n.canonBlock);
      const archive=graphs.find(x=>x.slug===activeSlug)?.catalogLegacy;
      info.textContent=(graph.title||graph.id||'Граф')+
        (archive?'\nАРХИВНАЯ ПРОЕКЦИЯ: в этом файле нет полной модели canonBlock/QRPE v7. Для современных примеров откройте reference-prepared-planning-tree или reference-mixed-active-work.':
          modernOptions.length?'\nВарианты с блоками канонов: '+modernOptions.length+
          '. Нажмите узел «Вариант · канон» для подробных ситуаций; если D выбран, нажмите «Показать все варианты».':'')+
        '\n\n'+graph.nodes.length+
        ' узлов / '+graph.edges.length+' связей\nПоказано: '+positions.size+' записей'+(showAuxiliaryEdges?' · связи и контекст':' · основная цепочка')+'\nRevision: '+(graph.revision||'?')+'\nМасштаб: '+scaleLabel(graph)+
        (graph.templateOnly?'\nЗаготовка Target Module/Unit · НЕ ПРИНЯТО\nЭто не результат проекта и не применённая модель.':graph.readOnly?'\nЭталон · только чтение':'')+
        (graph.coverage?'\n\nСодержание:\n'+graph.coverage:'')+
        (graph.sourceSections?'\n\nРазделы: '+graph.sourceSections.join(', '):'')+
        (graph.sourceDocument?'\nИсточник: '+graph.sourceDocument:'')+
        (count?'\n\nСобытия ('+count+'):\n'+graph.events.map(e=>
          e.id+' · '+e.type+(e.note?'\n'+e.note:'')).join('\n\n'):'')+
        projectContextSummary()+
        (graph.preparedGraphSetReference?.applicabilityStatus==='candidate-unverified'?
          '\n\nПРИМЕНИМОСТЬ: совпадение корневых заголовков — учебное допущение, не подтверждение одной нормативной цели/scope. Исторический T1 не менялся.':'')+
        (sourceUpdateAlerts.some(a=>a.graphSlug===activeSlug)?
          '\n\nИЗМЕНИЛСЯ ПОДГОТОВЛЕННЫЙ ИСТОЧНИК: проверьте исторические pins и применимость перед новым использованием; прежний T1 не обновляется.':'')+
        '\n\nВыберите узел, чтобы увидеть его основания и связи.';
      return;
    }
    const local=graph.nodes.find(x=>x.id===id);
    if(!local) {
      // A previously focused node can become hidden after a different view is
      // loaded. Do not crash or silently pretend that a choice was erased.
      selected=null;
      message('Узел '+id+' сейчас скрыт. Раскройте его коллекцию или варианты.');
      return;
    }
    const record=recordSourceFor(local);
    const n=record?{...local,...record.node,projectionOf:local.projectionOf}:local;
    const related=graph.edges.filter(e=>e.from===id||e.to===id);
    const outgoing=n.kind==='requirement'?outgoingForRequirement(activeSlug,id):[];
    const incoming=n.kind==='requirement'&&id===graph.rootRequirementId?
      incomingToGraph(activeSlug):[];
    const history=((record?.graph||graph).events||[]).filter(e=>e.decisionId===id||e.actionId===id||e.targetId===id);
    const chosenOption=n.kind==='decision'&&n.selectedOptionId?
      (sourceGraph?.nodes||graph.nodes).find(x=>x.id===n.selectedOptionId&&x.kind==='option'):null;
    const canonOption=n.kind==='canon'?
      (sourceGraph?.nodes||graph.nodes).find(x=>x.id===n.canonForId&&x.kind==='option'):null;
    const caseChecks=canonOption?.contextChecks||n.contextChecks||[];
    const chosenCanon=chosenOption?.canonBlock;
    const canonExcerpt=chosenCanon?'\n\nКанон выбранного варианта '+chosenOption.title+
      ' (+):\n'+canonCasesText(chosenCanon.recommended,chosenOption.contextChecks)+
      '\nКанон (−):\n'+canonCasesText(chosenCanon.contraindicated,chosenOption.contextChecks)+
      '\nИсходный вариант доступен через «Показать все варианты».':'';

    info.textContent=n.id+' · '+n.kind+(n.status?' · '+n.status:'')+'\n\n'+n.title+
      (graphs.find(x=>x.slug===activeSlug)?.catalogLegacy?
        '\n\nАРХИВНЫЙ ПРИМЕР: это прежняя иллюстративная схема без полноценного canonBlock/QRPE v7.':'')+
      (n.templateRole?'\n\nРоль заготовки: '+n.templateRole+'\nНе является принятым проектным решением.':'')+
      (n.kind==='action'?'\n\nТип Action: '+(n.actionType==='decomposition'?'выделение подцели / связанного набора подцелей':'общий')+'\nAction: '+(n.status==='selected'?(history.some(e=>e.type==='action_executed')?'выбран; запись выполнения — в истории':'выбран, исполнение не подтверждено'):n.status==='superseded'?'исторически выбран, затем пересмотрен':'не выбран'):'')+
      (n.kind==='option'?'\n\nПроисхождение: '+({prepared:'готовый',situational:'ситуативный',adapted:'адаптированный'}[n.origin]||'не указано')+
       (n.preparedSource?'\nПодготовленный источник: '+JSON.stringify(n.preparedSource):''):'')+
      (n.currentStatement&&n.currentStatement!==n.title?'\n\nТекущая формулировка: '+n.currentStatement:'')+
      (n.description?'\n\n'+n.description:'')+
      (n.id===graph.rootRequirementId&&graph.preparedGraphSetReference?.applicabilityStatus==='candidate-unverified'?
        '\n\nПРИМЕНИМОСТЬ: одинаковые заголовки R0/R-PLAN в учебном примере не подтверждают нормативную эквивалентность или scope. Историческая T1 сохранена.':'')+
      (sourceUpdateAlerts.filter(a=>a.graphSlug===activeSlug&&a.nodeId===id).map(a=>
        '\n\nИсточник требует проверки: '+a.sourceGraphSlug+':'+a.sourceOptionId+
        ', pin '+a.pinnedVersion+', доступна '+(a.availableVersion||'не найдена')+
        '. Это НЕ значит, что исторический T1 использовал новую версию.').join(''))+
      (n.kind==='collection'?'\n\nГРУППИРОВКА, а не R/Unit. Участников: '+n.memberCount+
        ' (кандидатных R: '+n.candidateMemberCount+').'+(n.memberCount===1?
          ' Один R выделен в группу только для показа контекста.':'')+
        ' '+(n.expanded?'Нажмите для сворачивания.':'Нажмите для раскрытия.')+
        ' Состояния исходных R не меняются.':'')+
      (n.kind==='canon'?'\n\nБлок канона варианта '+n.canonForId+' — только отображение одного блока с ситуациями (+/−); не отдельный R или D.':'')+
      (canonExcerpt||'')+
      (n.canonBlock?'\n\nКанонические ситуации (+):\n'+canonCasesText(n.canonBlock.recommended,caseChecks)+
       '\nКанонические ситуации (−):\n'+canonCasesText(n.canonBlock.contraindicated,caseChecks):'')+
      (n.compositeRequirementId?'\n\nКомпозит для оценки этого варианта: '+n.compositeRequirementId:'')+
      (n.contextChecks?.length?'\n\nПроверенные факторы до выбора:\n'+n.contextChecks.map(x=>
        x.canonCaseId+': '+x.requirementId+' · '+x.state+(x.impact?' · '+x.impact:'')).join('\n'):'')+
      (n.kind==='decision'&&n.status==='selected-in-example-only'&&!n.selectedOptionId?
        '\n\nПРЯМОЕ УЧЕБНОЕ D: отдельные option/канон и снимок выбора в этом примере не представлены. Это не доказательство оценки по канонам.':'')+
      (n.compositeOf?'\n\nКомпозит исходной R: '+n.compositeOf+
       '\nВерсии / факторы:\n'+(n.history||[]).map(x=>x.id+' · '+x.recordedAt+' · '+x.statement).join('\n'):'')+
      '\n\nQRPE:\n'+(n.qrpe?.length?n.qrpe.map(x=>'['+x.status+'] '+x.text+
        (x.recordedAt?' (записано '+x.recordedAt+')':'')+
        (x.statusHistory?.length?'\nИстория: '+x.statusHistory.map(t=>t.status+' ('+t.recordedAt+')'+(t.note?': '+t.note:'')).join(' → '):'')).join('\n'):'Нет записанных QRPE. Это НЕ доказывает отсутствие рисков.')+
      (n.implementationStatus?'\n\nРеализация: '+n.implementationStatus:'')+
      (n.goalAchievementStatus?'\nДостижение R: '+n.goalAchievementStatus:'')+
      (n.selectionBasis?'\n\nОснование выбора (срез '+(n.selectionBasis.knownAt||'дата не указана')+
        '):\n'+(n.selectionBasis.rationale||n.selectionBasis.note||'основание не указано')+
        (n.selectionBasis.acceptedContraindicationCaseIds?.length?
          '\nОсознанно принятые противопоказания: '+n.selectionBasis.acceptedContraindicationCaseIds.join(', '):'')+
        (n.selectionBasis.outstandingRiskIssueIds?.length?
          '\nОставленные открытыми QRPE: '+n.selectionBasis.outstandingRiskIssueIds.join(', '):'')+
        '\n\nПолный исторический снимок:\n'+JSON.stringify(n.selectionBasis,null,2):'')+
      (outgoing.length?'\n\n↗ Отдельный граф того же R: '+outgoing.map(r=>r.to+
        ' [R: '+r.requirementId+
        (r.relationKind==='potential'?', планируется вариантом '+r.originatingOptionId+'; D НЕ выбран':
         r.introducedByDecisionId?', введён D '+r.introducedByDecisionId+', статус '+r.relationKind:
         ', отношение '+r.relationKind+', без выбранного D')+']').join(', ')+
        '\nНажмите узел, чтобы перейти.':'')+
      (incoming.length?'\n\nПереход к этой R:\n'+incoming.map(r=>r.from+
        ' [R: '+r.requirementId+
        (r.relationKind==='potential'?', потенциальный путь через O: '+r.originatingOptionId+', НЕ выбран':', D: '+r.introducedByDecisionId)+']').join('\n'):'')+
      (n.preparedModelRef?'\nГотовая модель: '+(typeof n.preparedModelRef==='object'?JSON.stringify(n.preparedModelRef,null,2):n.preparedModelRef):'')+
      (n.repetition?'\nПовторяемость: '+n.repetition.mode+' '+n.repetition.cardinality:'')+
      (n.scope?'\n\nScope: '+n.scope:'')+
       (n.supersededBy?'\nЗаменён ответом: '+n.supersededBy:'')+
      (n.targetModule?'\n\nМесто ответа: '+n.targetModule:'')+
      (n.evidenceStatus?'\nПроверка: '+n.evidenceStatus:'')+
      (n.openQuestion?'\nОткрытый вопрос: '+n.openQuestion:'')+
      (n.source?'\n\nИсточник: '+n.source:'')+
      '\n\nСвязи:\n'+(related.length?related.map(e=>e.from+' —'+e.type+' ('+edgeMeta(e.type).label+')→ '+e.to+
        (e.parent?' (parent '+e.parent+')':'')+(e.meaning?' · '+e.meaning:'')).join('\n'):'нет')+
      (history.length?'\n\n'+((record?.graph||graph).exampleOnly||history.every(e=>e.exampleOnly===true||['example','example-only'].includes(e.by))?'История (иллюстрация)':'История')+':\n'+history.map(e=>
        e.id+' · '+e.type+(e.note?': '+e.note:'')+(e.previousDecisionSnapshot?'\nПрежний ответ: '+JSON.stringify(e.previousDecisionSnapshot,null,2):'')).join('\n'):'');
    if(n.preparedModelRef && typeof n.preparedModelRef==='object'){
      const ref=n.preparedModelRef,button=document.createElement('button');
      button.textContent='Открыть готовый модуль · '+ref.id;
      button.onclick=async()=>{if(await loadGraphSlug(ref.graphSlug,{reference:true}))focusRecord(ref.methodDecisionId);};
      info.appendChild(button);
    }
    if(n.answerParts)info.textContent+='\n\nЧасти ответа:\n'+n.answerParts.map(p=>p.id+': '+p.text).join('\n');
    if(n.answerBindings)info.textContent+='\n\nНа какие R отвечает:\n'+n.answerBindings.map(b=>b.requirementId+' ← '+b.parts.join(', ')+' · '+b.sufficiency).join('\n');
    if(n.blocking)info.textContent+='\n\nВлияние вопроса: '+n.blocking+(n.blocks?' · '+n.blocks:'')+(n.closesWith?'\nЗакрывается: '+n.closesWith:'');
    if(n.delegations)info.textContent+='\n\nДелегации (не выполнение):\n'+n.delegations.map(d=>d.targetModuleInstance+' · модель '+d.modelRef+' · ответ '+d.answerRef).join('\n');
    const ref=n.projectionOf;
    if(ref && graph.identitySpace && ref.nodeId===n.id && graphs.some(item=>item.slug===ref.graphSlug&&item.graph?.identitySpace===graph.identitySpace)){
      info.textContent+='\n\nИсточник той же записи: '+ref.graphSlug+' · '+ref.nodeId;
      const link=document.createElement('button');
      link.type='button';link.textContent='Открыть источник '+ref.nodeId;
      link.setAttribute('data-record-source',ref.graphSlug);
      link.onclick=async()=>{
        if(await loadGraphSlug(ref.graphSlug,{reference:true}))focusRecord(ref.nodeId);
      };
      info.appendChild(link);
    }
    appendCanonMaterial(n.kind==='canon'?sourceGraph.nodes.find(o=>o.id===n.canonForId):n);
    if(center)centerNode(id);
  }
  // View-only Collections and canonical situation blocks never persist as
  // Requirements/Decisions/edges. The underlying source JSON is unchanged.
  function localLevelSource(source,id){
    const byId=new Map(source.nodes.map(n=>[n.id,n])),keep=new Set([id]),queue=[id];
    const structural=new Set(['OPTION_FOR','DRIVES','DERIVES','INTRODUCES','OUTCOME_OF','GENERATES_ITEM_ROLE']);
    for(let i=0;i<queue.length;i++){
      const current=queue[i],n=byId.get(current);
      if(n?.kind==='decision'&&n.selectedOptionId&&byId.has(n.selectedOptionId))keep.add(n.selectedOptionId);
      if(n?.kind==='requirement'&&current!==id)continue;
      for(const e of source.edges)if(e.archived!==true&&e.from===current&&structural.has(e.type)&&!keep.has(e.to)){keep.add(e.to);queue.push(e.to);}
      for(const c of source.collections||[])if(c.anchor===current)for(const ref of c.memberRefs)if(!keep.has(ref)){keep.add(ref);queue.push(ref);}
    }
    // Include local grounds/review records without following another R's answer.
    let changed=true;
    while(changed){changed=false;for(const e of source.edges){
      if(e.archived===true||structural.has(e.type))continue;
      const other=keep.has(e.from)?e.to:keep.has(e.to)?e.from:null;
      if(other&&!keep.has(other)&&byId.has(other)){keep.add(other);changed=true;}
    }}
    return {...source,rootRequirementId:id,nodes:source.nodes.filter(n=>keep.has(n.id)),
      edges:source.edges.filter(e=>keep.has(e.from)&&keep.has(e.to)),
      collections:(source.collections||[]).filter(c=>keep.has(c.anchor)&&c.memberRefs.every(ref=>keep.has(ref))&&
        (c.anchor===id||byId.get(c.anchor)?.kind!=='requirement'))};
  }
  function displayGraph(source) {
    if(localRootId)source=localLevelSource(source,localRootId);
    const nodes=source.nodes.slice(),edges=source.edges.slice();
    const hidden=new Set(),virtualNodes=[],virtualEdges=[];
    const rootId=graphRoot(source)?.id;
    const bounded=!!rootId;
    const protectedRoot=new Set([rootId,...edges.filter(e=>e.from===rootId&&e.archived!==true&&['OPTION_FOR','DRIVES','DERIVES'].includes(e.type)).map(e=>e.to)]);
    if(bounded){
      // A non-root R is a boundary, including a composite/derived R.
      // Its own answers belong in a separate graph of the same identity.
      for(const e of edges){
        if(e.archived===true||e.from===rootId)continue;
        if(['OPTION_FOR','DRIVES','DERIVES'].includes(e.type)&&!protectedRoot.has(e.to)&&nodes.some(n=>n.id===e.from&&n.kind==='requirement'))hidden.add(e.to);
      }
    }
    for(const col of source.collections||[]){
      const candidateMembers=col.memberRefs.map(ref=>source.nodes.find(n=>n.id===ref));
      if(candidateMembers.some(n=>!n||n.kind!=='requirement'))throw Error('Группа '+col.id+' должна содержать только R');
      const expanded=col.memberRefs.length<=2||expandedCollections.has(col.id);
      const id='__collection__'+col.id;
      if(!expanded){
        const statuses=candidateMembers.filter(n=>n.status==='candidate').length;
        virtualNodes.push({id,kind:'collection',collectionId:col.id,title:col.title,
          memberCount:col.memberRefs.length,candidateMemberCount:statuses,expanded:false});
        virtualEdges.push({id:'__group__'+col.id,type:'VIEW_COLLECTION',from:col.anchor,to:id});
        for(const member of col.memberRefs)hidden.add(member);
      }else for(const member of col.memberRefs){
        const connected=source.edges.some(e=>e.archived!==true&&(e.from===member||e.to===member));
        if(!connected)virtualEdges.push({id:'__groupmember__'+col.id+'__'+member,
          type:'VIEW_COLLECTION',from:col.anchor,to:member});
      }
      // Opening a list reveals its R, never the R's own options/answers.
      for(const e of source.edges)if(e.archived!==true&&col.memberRefs.includes(e.from)&&
        ['OPTION_FOR','DRIVES','DERIVES'].includes(e.type))hidden.add(e.to);
    }
    // While a Collection is folded, do not leak its descendant candidates
    // into All Relations. This does not delete the source records.
    let changed=true;
    while(changed){
      changed=false;
      for(const e of source.edges){
        if(e.archived===true||!hidden.has(e.from)||
           !['OPTION_FOR','OUTCOME_OF','DRIVES','INTRODUCES','DERIVES'].includes(e.type)||hidden.has(e.to)||protectedRoot.has(e.to))continue;
        hidden.add(e.to);changed=true;
      }
    }
    // A selected option is hidden as a candidate; show its actual canon
    // next to selected D instead. Other options retain one block per option.
    const chosen=new Map();
    for(const d of source.nodes.filter(n=>n.kind==='decision'&&
      ['committed','selected-in-example-only'].includes(n.status)&&n.selectedOptionId)){
      const parentEdge=source.edges.find(e=>e.type==='OPTION_FOR'&&e.to===d.selectedOptionId);
      if(parentEdge)chosen.set(parentEdge.from,d);
    }
    for(const option of source.nodes.filter(n=>['option','action'].includes(n.kind)&&n.canonBlock)){
      const parentEdge=source.edges.find(e=>e.type==='OPTION_FOR'&&e.to===option.id)||
        source.edges.find(e=>e.type==='DRIVES'&&e.to===option.id);
      const selected=option.kind==='option'?(parentEdge?chosen.get(parentEdge.from):source.nodes.find(n=>n.kind==='decision'&&['committed','selected-in-example-only'].includes(n.status)&&n.selectedOptionId===option.id)):null;
      if(selected&&!showAllVariants&&option.id!==selected.selectedOptionId)continue;
      const anchor=selected&&!showAllVariants?selected.id:option.id;
      if(hidden.has(option.id)||hidden.has(anchor))continue;
      const id='__canon__'+option.id;
      virtualNodes.push({id,kind:'canon',canonForId:option.id,
        title:'Канон '+option.title,canonBlock:option.canonBlock});
      virtualEdges.push({id:'__viewcanon__'+option.id,type:'VIEW_CANON',from:anchor,to:id});
    }
    // A collapsed outer Collection may hide another group's anchor.
    const candidateNodes=[...nodes.filter(n=>!hidden.has(n.id)),...virtualNodes];
    const candidateIds=new Set(candidateNodes.map(n=>n.id));
    const visibleVirtual=virtualNodes.filter(n=>{
      const link=virtualEdges.find(e=>e.to===n.id);
      return !link||candidateIds.has(link.from);
    });
    const visibleIds=new Set([...nodes.filter(n=>!hidden.has(n.id)),...visibleVirtual].map(n=>n.id));
    return {...source,...(rootId?{rootRequirementId:rootId}:{}),nodes:[...nodes.filter(n=>!hidden.has(n.id)),...visibleVirtual],
      edges:[...edges.filter(e=>visibleIds.has(e.from)&&visibleIds.has(e.to)),
        ...virtualEdges.filter(e=>visibleIds.has(e.from)&&visibleIds.has(e.to))]};
  }
  function updateCollections(openId){
    const before=new Map(positions),camera={...view};
    const opening=!!openId;
    if(opening){
      if(positions.has('__collection__'+openId))collectionPositions.set(currentLayoutKey()+'::'+openId,{...positions.get('__collection__'+openId)});
      expandedCollections.add(openId);
    }else expandedCollections.clear();
    graph=displayGraph(sourceGraph);selected=null;selectedEdge=null;
    layout();
    for(const [id,p] of before)if(positions.has(id))positions.set(id,p);
    const occupied=[...positions].filter(([id])=>before.has(id)).map(([,p])=>p);
    for(const col of sourceGraph.collections||[]){
      if(col.memberRefs.length<=2)continue;
      const remembered=collectionPositions.get(currentLayoutKey()+'::'+col.id);
      if(!remembered)continue;
      if(!expandedCollections.has(col.id)){
        if(positions.has('__collection__'+col.id))positions.set('__collection__'+col.id,{...remembered});
      }else if(openId===col.id){
        for(const [i,id] of col.memberRefs.entries()){
          if(!positions.has(id)||before.has(id))continue;
          let p={x:remembered.x,y:remembered.y+i*112};
          while(occupied.some(q=>Math.abs(q.x-p.x)<250&&Math.abs(q.y-p.y)<90))p.y+=112;
          positions.set(id,p);occupied.push(p);
        }
      }
    }
    enteringNodes=new Set([...positions.keys()].filter(id=>!before.has(id)));
    applyLayoutPositions();Object.assign(view,camera);render();renderEdgeLegend();
  }
  function toggleCollection(id){updateCollections(id);}
  el('collections-collapse').onclick=()=>updateCollections(null);
  const stateCore=globalThis.RDGState;
  let stateMode=false,stateSources=[];
  function stateProjection(slug=null){
    const items=new Map(stateSources.map(i=>[i.slug,i]));
    for(const item of graphs)if(item.graph)items.set(item.slug,item);
    if(!fullMode&&sourceGraph){
      const id=sourceGraph.id||activeSlug||'local';
      items.set(id,{...(items.get(id)||{}),slug:id,group:sourceGraph.readOnly?'examples':'workspaces',graph:sourceGraph});
    }
    stateCore.validate([...items.values()],{partial:true});
    return stateCore.collect({items:[...items.values()],manifest:catalogModel||{},
      ...(fullMode?{rootGraphSlug:slug||activeFullRootSlug}:{graphSlug:slug||sourceGraph?.id||activeSlug})});
  }
  function appendSources(parent,refs){
    for(const s of refs||[]){
      const line=document.createElement('p');
      if(s.url&&stateCore.safeURL(s.url)){
        const a=document.createElement('a');a.setAttribute('href',s.url);a.setAttribute('target','_blank');a.setAttribute('rel','noopener noreferrer');
        a.textContent=s.title||s.url;line.appendChild(a);
      }else line.textContent='Источник недоступен: '+(s.sourceId||'не указан');
      parent.appendChild(line);
    }
  }
  function showStateFields(slug=null){
    try{
      const data=stateProjection(slug);setInspector(true);selected=null;selectedEdge=null;
      info.textContent=(slug?'Поля графа: '+slug:fullMode?'Контекст полного графа':'Контекст графа')+
        '\nОбщий контекст проекта · '+(data.identitySpace||'проект не указан')+
        '\nСначала используйте известный ответ. Условные вопросы — после соответствующего выбора.\n';
      for(const state of ['now','later','unknown']){
        const rows=data.fields.filter(f=>f.state===state);if(!rows.length)continue;
        const h=document.createElement('h3');h.textContent=({now:'Актуально сейчас',later:'После выбора ветки',unknown:'Актуальность требует проверки'})[state];info.appendChild(h);
        for(const f of rows){
          const box=document.createElement('section');box.setAttribute('data-state-field',f.fieldRef.graphSlug+':'+f.fieldRef.fieldId);
          const title=document.createElement('h4');title.textContent=f.title+' · '+({known:'поле заполнено',missing:'поле пустое',conflict:'противоречивые владельцы','needs-assessment':'область значения требует проверки'})[f.answerStatus];box.appendChild(title);
          const explain=document.createElement('p');explain.textContent=f.explanation;box.appendChild(explain);appendSources(box,f.sources);
          const details=document.createElement('p');details.textContent=f.usages.map(u=>u.graphSlug+' / '+u.location+': '+u.purpose+(u.reasons.length?' · '+u.reasons.join('; '):' · нужно сейчас')).join('\n');box.appendChild(details);
          for(const a of f.answer?[f.answer]:f.conflictingOwners||[]){const answer=document.createElement('p');answer.textContent=a.value+' · '+a.source+' · '+({applicable:'применим', 'scope-needs-assessment':'область применимости требует проверки'})[a.status]+(a.exampleOnly?' · УЧЕБНЫЙ ОТВЕТ':'');box.appendChild(answer);}
          const id=document.createElement('small');id.textContent='Поле: '+f.fieldRef.graphSlug+':'+f.fieldRef.fieldId+(f.question?' · нужно уточнить':'');box.appendChild(id);info.appendChild(box);
        }
      }
      if(!data.fields.length){const p=document.createElement('p');p.textContent='Явно объявленных использований полей пока нет.';info.appendChild(p);}
      if(data.incomplete.length){const p=document.createElement('p');p.setAttribute('data-state-incomplete','true');p.textContent='НЕПОЛНЫЙ СПИСОК: '+data.incomplete.map(x=>(x.graphSlug||x.fieldRef?.graphSlug||'')+' '+(x.location||'')+' · '+x.reason).join('\n');info.appendChild(p);}
      if(data.freeformCandidates.length){const p=document.createElement('p');p.textContent='Свободный контекст доступен для смысловой проверки при необходимости; не нужно перечитывать все записи для каждого поля.\n'+data.freeformCandidates.map(c=>c.graphSlug+':'+c.nodeId+' — '+c.text).join('\n');info.appendChild(p);}
      const help=document.createElement('p');help.textContent='Запись текущего значения: set_context_value через штатный writer с проверкой ревизии. Просмотр не изменяет факты или выбор решения.';info.appendChild(help);
      if(slug){const b=document.createElement('button');b.textContent='Открыть граф';b.onclick=()=>loadGraphSlug(slug);info.appendChild(b);}
      return data;
    }catch(error){message('Контекст: '+error.message);return null;}
  }
  function renderStateCard(scene,occupied,nodeBoxes){
    if(!graph||!stateCore)return;
    const rootId=graphRoot(graph)?.id;
    const anchor=positions.get(rootId)||positions.values().next().value||{x:48,y:72};
    const box={x:anchor.x-50,y:Math.min(anchor.y,...occupied.map(b=>b.y))-130,w:290,h:86,id:'__state_info__'};
    let data;try{data=stateProjection();}catch(_){}
    const group=make('g',scene,{id:'context-summary',class:'context-summary',transform:'translate('+box.x+' '+box.y+')',tabindex:0,role:'button','aria-label':fullMode?'Контекст полного графа':'Поля контекста графа'});
    make('rect',group,{width:box.w,height:box.h,rx:10,fill:'#263f49',stroke:'#8eb6bc','stroke-dasharray':'5 3'});
    make('text',group,{x:12,y:23,fill:'#e5f1f4','font-weight':'bold'},fullMode?'Контекст полного графа':'Поля контекста графа');
    make('text',group,{x:12,y:46,fill:'#d6e7ec'},data?'Сейчас: '+data.fields.filter(f=>f.state==='now').length+' · После выбора: '+data.fields.filter(f=>f.state==='later').length:'Список требует проверки');
    make('text',group,{x:12,y:67,fill:'#d6e7ec'},data?.incomplete.length?'Список неполон · открыть':'Общие ответы проекта · открыть');
    const open=e=>{e.stopPropagation();showStateFields();};
    group.addEventListener('pointerdown',e=>e.stopPropagation());
    group.addEventListener('click',open);group.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open(e);}});
    occupied.push(box);nodeBoxes.push(box);
  }

  host.rdgState={list:stateProjection,show:showStateFields};
  function projectContextSummary() {
    const source=sourceGraph||graph;
    if(!source||!source.identitySpace||source.readOnly||source.exampleOnly)return '';
    const fromIndex=projectContexts[source.identitySpace];
    const today=new Date().toISOString().slice(0,10);
    const rows=fromIndex?.records?.map(n=>{
      const since=n.effectiveAt||n.validFrom;
      const until=n.validUntil||n.validTo;
      // Freeform Context is current project state, not a temporal evidence record.
      const timing=n.kind==='context'?'':since&&since.slice(0,10)>today?' · БУДУЩЕЕ, с '+since:
        until&&until.slice(0,10)<today?' · ИСТЕКЛО '+until:
        since||until?' · дата действия требует проверки':' · дата действия неизвестна';
      const scope=n.kind==='context'?(n.scope?' · scope '+n.scope:''):
        n.scope?' · scope '+n.scope+' (применимость не подтверждена)':' · scope не указан';
      return n.kind.toUpperCase().slice(0,1)+' '+n.id+': '+(n.currentStatement||n.title)+
        ' ['+n.graphSlug+']'+timing+scope+
        (n.scopeCompatibility==='declared-unverified'?' · совместимость scope НЕ ДОКАЗАНА':'');
    })||[];
    if(!fromIndex){
      for(const n of source.nodes||[]){
        if(n.projectionOf||n.active===false||n.status==='inactive'||n.status==='candidate'||n.status==='superseded')continue;
        if(['requirement','context'].includes(n.kind)||n.kind==='decision'&&['committed','selected-in-example-only'].includes(n.status))
          rows.push(n.kind[0].toUpperCase()+' '+n.id+': '+n.title);
      }
    }
    return '\n\nПроектные записи для проверки (инвентарь, НЕ доказанная текущая применимость; '+source.identitySpace+'):\n'+
      (rows.slice(0,40).join('\n')||'Пока нет подтверждённых элементов')+
      (fromIndex?'\nЛокально проиндексированы графы: '+fromIndex.graphSlugs.join(', '):'\nДля этого проекта общий индекс контекста недоступен.')+
      (fromIndex?.reviewAlerts?.length?'\n\nТребуют проверки после изменения R:\n'+
        fromIndex.reviewAlerts.slice(0,30).map(a=>a.graphSlug+':'+a.nodeId+
        ' ← '+a.sourceRequirementIds.join(', ')).join('\n'):'')+
      '\nОхват внешних источников неизвестен; недоступно ≠ не существует.';
  }
  async function load(text,description,options={}){
    try{
      const validated=validate(JSON.parse(text));
      if(options.localRootId&&!validated.nodes.some(n=>n.id===options.localRootId&&n.kind==='requirement'))throw Error('В обновлённом графе нет R текущего уровня: '+options.localRootId);
      if(fullMode){rememberFullView();fullMode=false;}
      sourceGraph=validated;localRootId=options.localRootId||null;expandedCollections=new Set();showAllVariants=false;setInspector(false);
      graph=displayGraph(sourceGraph);selected=null;selectedEdge=null;el('search').value='';
      layout();render();fit();message(description+' · revision '+(graph.revision||'?'));
      return true;
    }catch(e){message('Ошибка: '+e.message);return false;}
  }
  function requestBackend() {
    if(typeof privilegedRequest === 'function') return privilegedRequest;
    if(typeof GM_xmlhttpRequest === 'function') return GM_xmlhttpRequest;
    if(typeof GM !== 'undefined' && GM && typeof GM.xmlHttpRequest === 'function')
      return details => GM.xmlHttpRequest(details);
    return null;
  }
  function readLocalFile(relativePath) {
    const request=requestBackend();
    if(!request)
      return Promise.reject(Error('Нет API локального чтения в Tampermonkey. Установите актуальный Local Loader v2.5.2 с @grant GM_xmlhttpRequest.'));
    if(relativePath!=='index.json'&&relativePath!=='layouts.json'&&
       (!catalogCore.validPath(relativePath)||!relativePath.endsWith('/graph.json')))
      return Promise.reject(Error('Недопустимый путь графа'));
    return new Promise((resolve,reject) => {
      request({
        method:'GET', url:GRAPH_ROOT_URL+relativePath.split('/').map(encodeURIComponent).join('/'), timeout:15000, nocache:true,
        onload: response => {
          if(response.status !== 0 && response.status !== 200)
            return reject(Error('HTTP/file status: '+response.status));
          if(typeof response.responseText !== 'string' || !response.responseText.length)
            return reject(Error('Файл пустой или не читается: '+relativePath));
          resolve(response.responseText);
        },
        onerror: err => reject(Error('Доступ к локальному файлу запрещён или файл не найден: '+relativePath)),
        ontimeout: () => reject(Error('Время чтения файла истекло: '+relativePath))
      });
    });
  }
  function navigationView(){return {showAllVariants,expandedCollections:[...expandedCollections],showAuxiliaryEdges,
    selectedEdge,search:el('search').value,view:{...view},positions:[...positions].map(([id,p])=>[id,{...p}])};}
  function navigationEntry(){return {slug:activeSlug,manualGraph:sourceGraph,manualSource:source,localRootId,focus:selected,returnView:navigationView()};}
  function showLocalLevel(id){
    localRootId=id;expandedCollections=new Set();showAllVariants=false;selected=null;selectedEdge=null;setInspector(false);
    graph=displayGraph(sourceGraph);layout();render();showGraph();
  }
  function focusRecord(id){
    if(!graph.nodes.some(n=>n.id===id)){
      const n=sourceGraph.nodes.find(n=>n.id===id);
      const parent=n?.kind==='requirement'?id:sourceGraph.edges.find(e=>e.to===id&&['DRIVES','OPTION_FOR'].includes(e.type))?.from;
      if(parent)showLocalLevel(parent);
    }
    choose(id);
  }
  async function openChildLevel(target){
    try {
      if(typeof target==='object'&&target.localRootId){
        levelStack.push(navigationEntry());showLocalLevel(target.localRootId);
      }else await loadGraphSlug(target,{child:true});
    }
    catch(err) { message('Следующий уровень недоступен: '+err.message); }
  }
  function refreshNavigationSources(slug,updated){
    levelStack=levelStack.filter(previous=>{
      if(previous.slug!==slug||!previous.manualGraph)return true;
      const rootId=previous.localRootId||graphRoot(previous.manualGraph)?.id;
      if(rootId&&!updated.nodes.some(n=>n.id===rootId&&n.kind==='requirement'))return false;
      previous.manualGraph=updated;
      previous.localRootId=rootId===graphRoot(updated)?.id?null:rootId;
      return true;
    });
  }
  async function loadGraphSlug(slug, options={}) {
    const candidate = graphs.find(item => item.slug===slug);
    if(!candidate) throw Error('Неизвестный граф: '+slug);
    const bundled=!!candidate.graph && !options.fresh;
    const data=bundled ? JSON.stringify(candidate.graph) : await readLocalFile(candidate.file);
    const fromSlug=activeSlug, fromSelected=selected;
    const fromGraph=sourceGraph,fromSource=source,fromLocalRoot=localRootId;
    const returnView=navigationView();
    // The rendering pass must see the target graph identity, not the old level.
    activeSlug=slug;
    const ok=await load(data,(bundled?'Встроенный локальный граф: ':'Локальный граф: ')+candidate.file,{localRootId:options.localRootId|| (options.fresh?fromLocalRoot:null)});
    if(!ok)activeSlug=fromSlug;
    if(ok) {
      if(options.fresh)refreshNavigationSources(slug,sourceGraph);
      if((options.child||options.reference) && fromSlug)levelStack.push({slug:fromSlug,manualGraph:fromGraph,manualSource:fromSource,localRootId:fromLocalRoot,focus:fromSelected,returnView,reference:!!options.reference});
      else if((options.child||options.reference)&&fromGraph)levelStack.push({manualGraph:fromGraph,manualSource:fromSource,localRootId:fromLocalRoot,focus:fromSelected,returnView,reference:!!options.reference});
      else if(!options.returning)levelStack=[];
      if(!bundled)candidate.graph=sourceGraph;
      source=bundled?'embedded':'auto'; activeSlug=slug;
      showGraph();
    }
    return ok;
  }
  async function loadCatalog() {
    if(catalogLoading) return catalogLoading;
    catalogLoading=(async()=>{
      // Data loaded by @require is available without a privileged file:// XHR.
      const manifest=embeddedSnapshot && embeddedSnapshot.schemaVersion===1
        ? embeddedSnapshot : JSON.parse(await readLocalFile('index.json'));
      if(!manifest || manifest.schemaVersion!==1 || !Array.isArray(manifest.graphs))
        throw Error('Неверный graphs/index.json');
      await initializeLayouts(manifest);
      stateSources=manifest.stateGraphs||[];
      projectContexts=manifest.projectContexts&&typeof manifest.projectContexts==='object'?manifest.projectContexts:{};
      sourceUpdateAlerts=Array.isArray(manifest.sourceUpdateAlerts)?manifest.sourceUpdateAlerts:[];
      catalogModel=catalogCore.normalizeCatalog(manifest);
      graphs=catalogModel.graphs;graphRelations=catalogModel.relations.filter(r=>
        r&&typeof r.requirementId==='string'&&typeof r.identitySpace==='string'&&
        graphs.some(g=>g.slug===r.from)&&graphs.some(g=>g.slug===r.to));
      renderCatalog();
      if(!el('catalog').hidden) showCatalog();
    })().catch(err=>{
      message('Автозагрузка недоступна: '+err.message+
        '. Проверьте доступ Tampermonkey к file://. Можно выбрать «Другой JSON».');
      console.warn('[RDG Viewer] Local graph load failed:',err);
    }).finally(()=>{catalogLoading=null;});
    return catalogLoading;
  }
  async function reload() {
    if(fullMode && activeFullRootSlug){
      try {await openFullGraph(activeFullRootSlug,{fresh:true});return true;}
      catch(err){message('Обновление полного графа не выполнено: '+err.message+
        '. Показана прежняя копия; проверьте доступ к файлам и обновите индекс.');return false;}
    }
    if(source==='auto' && activeSlug) {
      try {return await loadGraphSlug(activeSlug,{returning:true,fresh:true});}
      catch(err){message('Не удалось обновить файл: '+err.message+'. Сохраняется ранее открытый граф.');return false;}
    }
    if(source==='embedded') {
      const candidate=graphs.find(g=>g.slug===activeSlug);
      if(candidate){
        try{
          const fresh=await readLocalFile(candidate.file);
          if(await load(fresh,'Файл: '+candidate.file,{localRootId})) {
            source='auto';
            candidate.graph=sourceGraph;refreshNavigationSources(activeSlug,sourceGraph);
          }
          return;
        }catch(err){
          message('Граф загружен через локальный @require. Для обновления данных '+
            'перезагрузите страницу ChatGPT. Прямой запрос к файлу не разрешён.');
          return;
        }
      }
    }
    message('Для обновления вручную выбранного файла укажите его повторно.');
    el('picker').click();
  }
  launcher.onclick=()=>{
    if (Date.now() < suppressLauncherClickUntil) return;
    el('panel').classList.add('open');launcher.hidden=true;showCatalog();
  };
  el('close').onclick=()=>{if(layoutDirty&&!layoutAutoPaused&&!layoutAutoBlocked&&layoutFileHandle)void saveLayout({interactive:false}).catch(()=>{});el('panel').classList.remove('open');el('launch').hidden=false;};
  el('back').onclick=()=>{if(!fullMode&&activeFullRootSlug)void openFullGraph(activeFullRootSlug);else {const folder=selectedFolder;activeFullRootSlug=null;openFolder(folder);}};
  el('folder-back').onclick=()=>openFolder(selectedFolder.includes('/')?selectedFolder.slice(0,selectedFolder.lastIndexOf('/')):'');
  el('example-set-map').onclick=()=>openFullGraph(activeFullRootSlug);
  el('catalog-search').oninput=renderCatalog;
  function restoreNavigationView(previous){
    const state=previous.returnView;
    if(state){
      showAllVariants=state.showAllVariants;
      expandedCollections=new Set(state.expandedCollections);
      showAuxiliaryEdges=state.showAuxiliaryEdges;
      selectedEdge=null;
      el('search').value=state.search;
      graph=displayGraph(sourceGraph);
      layout();for(const [id,p] of state.positions||[])if(positions.has(id))positions.set(id,p);
      applyLayoutPositions();render();renderEdgeLegend();
      Object.assign(view,state.view);
      transform();
    }
    if(previous.focus)choose(previous.focus,false);
    else choose(null,false);
  }
  el('level-up').onclick=async()=>{
    if(levelStack.length){
      const prev=levelStack.at(-1);
      let ok=false;
      if(prev.manualGraph){
        activeSlug=prev.slug||null;
        ok=await load(JSON.stringify(prev.manualGraph),'Ранее открытый JSON',{localRootId:prev.localRootId});
        if(ok){source=prev.manualSource;showGraph();}
      }else ok=await loadGraphSlug(prev.slug,{returning:true});
      if(ok){
        levelStack.pop();
        el('level-up').hidden=!(levelStack.length||incomingToGraph(activeSlug).length);
        restoreNavigationView(prev);
      }
      return;
    }
    const incoming=incomingToGraph(activeSlug);
    if(incoming.length===1)await loadGraphSlug(incoming[0].from,{returning:true});
  };
  el('source').onclick=()=>{
    const originalSource=sourceMarkdownFor(graph);
    if(originalSource===null)return;
    const opening=el('source-view').hidden;
    el('source-view').hidden=!opening;
    el('content').hidden=opening;
    el('edge-toolbar').hidden=opening;
    el('source-text').textContent=originalSource;
    el('source').textContent=opening?'← К графу':'Исходный модуль';
    for(const id of ['fit','search']) el(id).hidden=opening;
    if(!opening)fit();
  };
  el('file').onclick=()=>el('picker').click();
  el('picker').onchange=async e=>{
    const input=e.target,file=input.files&&input.files[0];
    if(!file)return;
    const fromSlug=activeSlug;
    try{
      const text=await file.text();activeSlug=null;
      const ok=await load(text,'Файл: '+file.name);
      if(ok){source='file';activeSlug=null;levelStack=[];showGraph();}
      else activeSlug=fromSlug;
    }catch(error){activeSlug=fromSlug;message('Ошибка чтения файла: '+error.message);}
    finally{input.value='';}
  };
  el('reload').onclick=reload;
  el('fit').onclick=()=>fit(false);
  el('context-fields').onclick=()=>showStateFields();
  el('context-mode').onclick=()=>{stateMode=!stateMode;el('context-mode').setAttribute('aria-pressed',String(stateMode));el('context-mode').textContent='Просмотр контекста: '+(stateMode?'вкл.':'выкл.');message(stateMode?'Просмотр контекста: нажмите граф, чтобы увидеть его поля.':'Навигация: нажмите граф, чтобы открыть его.');};
  el('edges-all').onclick=()=>{showAuxiliaryEdges=true;selectedEdge=null;if(fullMode)graph=projectFullGraph();layout();render();renderEdgeLegend();fit();};
  el('edges-core').onclick=()=>{showAuxiliaryEdges=false;selectedEdge=null;selected=null;el('search').value='';if(fullMode)graph=projectFullGraph();layout();render();renderEdgeLegend();fit();};
  el('variants-all').onclick=()=>{
    const before=new Map(positions),camera={...view};
    rememberFullView();showAllVariants=!showAllVariants;graph=fullMode?projectFullGraph():displayGraph(sourceGraph);
    selected=null;selectedEdge=null;setInspector(false);layout();
    for(const [id,p] of before)if(positions.has(id))positions.set(id,p);
    const occupied=[...positions].filter(([id])=>before.has(id)).map(([,p])=>p);
    for(const [id,value] of positions)if(!before.has(id)&&!savedPositions()[id]){
      const p={...value};while(occupied.some(q=>Math.abs(q.x-p.x)<250&&Math.abs(q.y-p.y)<90))p.y+=112;
      positions.set(id,p);occupied.push(p);
    }
    enteringNodes=new Set([...positions.keys()].filter(id=>!before.has(id)));
    applyLayoutPositions();Object.assign(view,camera);render();renderEdgeLegend();rememberFullView();
  };
  el('search').oninput=e=>{
    if(!graph)return;
    const q=e.target.value.trim().toLowerCase();
    let found=graph.nodes.find(n=>n.id.toLowerCase()===q)||graph.nodes.find(n=>(n.id+' '+n.title).toLowerCase().includes(q));
    if(q&&!found&&fullMode){
      const hidden=sourceGraph.nodes.find(n=>n.id.toLowerCase()===q)||sourceGraph.nodes.find(n=>(n.id+' '+n.title).toLowerCase().includes(q));
      if(hidden){if(!showAllVariants)el('variants-all').onclick();found=graph.nodes.find(n=>n.id===hidden.id);}
    }
    if(q&&!found&&!fullMode){
      const record=sourceGraph.nodes.find(n=>n.id.toLowerCase()===q)||sourceGraph.nodes.find(n=>(n.id+' '+n.title).toLowerCase().includes(q));
      const parent=record?.kind==='requirement'?record.id:sourceGraph.edges.find(e=>e.to===record?.id&&['OPTION_FOR','DRIVES'].includes(e.type))?.from;
      if(parent&&sourceGraph.nodes.some(n=>n.id===parent&&n.kind==='requirement')){
        openChildLevel({localRootId:parent});found=graph.nodes.find(n=>n.id===record.id);
      }
    }
    choose(q&&found?found.id:null,!!(q&&found));
  };
  svg.addEventListener('pointerdown',e=>{
    if(e.button!==0)return;
    const target=e.target.closest('[data-id]'),id=target?.getAttribute('data-id');
    if(id&&positions.has(id)){nodeDrag={id,pointerId:e.pointerId,x:e.clientX,y:e.clientY,start:{...positions.get(id)},moved:false};return;}
    drag={x:e.clientX,y:e.clientY,ox:view.x,oy:view.y};svg.setPointerCapture(e.pointerId);
  });
  svg.addEventListener('pointermove',e=>{
    if(nodeDrag){
      if(e.pointerId!==nodeDrag.pointerId)return;
      const dx=e.clientX-nodeDrag.x,dy=e.clientY-nodeDrag.y;
      if(!nodeDrag.moved&&Math.hypot(dx,dy)<6)return;
      nodeDrag.moved=true;svg.setPointerCapture(e.pointerId);
      const p={x:Math.round((nodeDrag.start.x+dx/view.scale)*100)/100,y:Math.round((nodeDrag.start.y+dy/view.scale)*100)/100};
      layoutCommand({type:'set_positions',positions:{[nodeDrag.id]:p}});return;
    }
    if(!drag)return;
    view.x=drag.ox+e.clientX-drag.x;view.y=drag.oy+e.clientY-drag.y;transform();
  });
  const stop=e=>{
    if(nodeDrag){if(nodeDrag.moved){suppressNodeClickUntil=Date.now()+350;choose(nodeDrag.id,false);}nodeDrag=null;scheduleLayoutSave();}
    drag=null;
    if(e&&svg.hasPointerCapture?.(e.pointerId))svg.releasePointerCapture(e.pointerId);
  };
  svg.addEventListener('pointerup',stop);svg.addEventListener('pointercancel',stop);
  el('layout-save').onclick=async()=>{try{await saveLayout();}catch(e){message(e.name==='AbortError'?'Сохранение отменено; расположение осталось в черновике.':e.message);}};
  el('layout-open').onclick=async()=>{try{
    if(typeof window.showOpenFilePicker!=='function')throw Error('Выбор общего файла недоступен в этом браузере');
    const [handle]=await window.showOpenFilePicker({multiple:false,types:[{description:'RDG layouts.json',accept:{'application/json':['.json']}}]});
    await attachLayoutFile(handle);
  }catch(e){message(e.name==='AbortError'?'Выбор файла отменён.':e.message);}};
  el('layout-connect').onclick=async()=>{
    if(sourceGraph&&layoutDirty)return el('layout-save').onclick();
    try{
      if(typeof window.showOpenFilePicker!=='function')throw Error('Прямое подключение файла недоступно; используйте экспорт');
      const [handle]=await window.showOpenFilePicker({multiple:false,types:[{description:'RDG layouts.json',accept:{'application/json':['.json']}}]});
      if(handle.requestPermission&&await handle.requestPermission({mode:'readwrite'})!=='granted')throw Error('Нет разрешения на запись');
      await attachLayoutFile(handle);
    }catch(error){message(error.name==='AbortError'?'Выбор файла отменён.':error.message);}
  };
  el('layout-pause').onclick=()=>{layoutAutoPaused=!layoutAutoPaused;updateLayoutControls();scheduleLayoutSave();};
  window.addEventListener('beforeunload',event=>{if(layoutDirty){event.preventDefault();event.returnValue='';}});
  window.addEventListener('pagehide',()=>{persistLayoutDraft();});
  el('layout-export').onclick=()=>{try{exportLayout();}catch(e){message(e.message);}};
  el('layout-drafts').onclick=()=>{void showLayoutDrafts().catch(error=>message(error.message));};
  el('layout-discard').onclick=()=>{try{discardLayoutChanges();}catch(error){message(error.message);}};
  el('layout-reset').onclick=()=>{
    if(!sourceGraph)return;
    layoutCommand({type:'clear_layout'});
    message('Автоматическое расположение восстановлено. Изменение будет сохранено при подключённом файле.');
  };
  svg.addEventListener('wheel',e=>{
    if(!graph)return;
    e.preventDefault();
    const rect=svg.getBoundingClientRect();
    Object.assign(view,viewGeometry.wheelView(view,e,{x:e.clientX-rect.left,y:e.clientY-rect.top},
      {width:rect.width,height:rect.height}));transform();
  },{passive:false});
  // @require executes before the loader body. The loader passes its privileged
  // GM request function explicitly; a direct install starts on the next microtask.
  function startViewer(request) {
    if(typeof request === 'function') privilegedRequest = request;
    if(startupRequested) {
      if(request && !graph) return loadCatalog();
      return catalogLoading;
    }
    startupRequested = true;
    return loadCatalog();
  }
  host.rdgExplorer=Object.freeze({openFolder,openFull:openFullGraph,openGraph:async slug=>{
    const item=graphs.find(g=>g.slug===slug);if(!item)throw Error('Неизвестный граф: '+slug);
    activeFullRootSlug=null;selectedFolder=item.folder;
    return loadGraphSlug(slug);
  },getCatalog:()=>JSON.parse(JSON.stringify(catalogModel))});
  let workflowAttached=false;
  host.rdgWorkflow=Object.freeze({
    attach(){workflowAttached=true;el('workflow-toggle').hidden=false;el('workflow-panel').hidden=false;
      el('panel').classList.add('open');return el('workflow-panel');},
    async loadGraph(data){
      const ok=await load(JSON.stringify(data),'Локальный Helper');
      if(!ok)throw Error('Helper вернул некорректный граф');
      source='helper';activeSlug=null;showGraph();
    }
  });
  el('workflow-toggle').hidden=typeof window.showDirectoryPicker!=='function';el('workflow-panel').hidden=true;
  let manualEditor=null;
  el('workflow-toggle').onclick=async()=>{
    if(workflowAttached||manualEditor||globalThis.RDG_LOCAL_WORKFLOW){el('workflow-panel').hidden=!el('workflow-panel').hidden;return;}
    try{
      if(typeof window.showDirectoryPicker!=='function')throw Error('Выбор папки сессии недоступен');
      const handle=await window.showDirectoryPicker({mode:'readwrite'});
      if(handle.requestPermission&&await handle.requestPermission({mode:'readwrite'})!=='granted')throw Error('Нет разрешения на папку сессии');
      const api=globalThis.RDGWorkflowUI;
      if(!api)throw Error('Обновите исходник Viewer с модулем ручного интерфейса');
      manualEditor=api.mount(host.rdgWorkflow.attach(),api.fileTransport(handle),
        {document,onGraph:g=>host.rdgWorkflow.loadGraph(g)});
      await manualEditor.refresh();
    }catch(error){message(error.name==='AbortError'?'Подключение сессии отменено.':error.message);}
  };
  host.rdgStart = startViewer;
  Promise.resolve().then(() => {
    if(!startupRequested && !globalThis.RDG_LOCAL_WORKFLOW) return startViewer();
  });
})();