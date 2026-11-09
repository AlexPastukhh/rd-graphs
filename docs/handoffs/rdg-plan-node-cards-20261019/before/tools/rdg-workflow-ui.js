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
        const random=typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
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
    return {read:()=>exchange('state',null),write:body=>exchange('command',body),
      setStatus:callback=>{report=callback;}};
  }
  function mount(container,transport,options={}){
    const doc=options.document||document,fields={},buttons={};
    let view=null,busy=false,pending=null,activeId=null;
    const make=(tag,text,parent)=>{const x=doc.createElement(tag);if(text!==undefined)x.textContent=text;
      if(parent)parent.appendChild(x);return x;};
    const toolbar=make('div',undefined,container);toolbar.classList.add('wf-toolbar');
    const heading=make('h3','Данные плана',toolbar);
    const refresh=make('button','Обновить',toolbar);
    const status=make('div','Данные ещё не загружены. Нажмите «Обновить».',toolbar);status.classList.add('wf-status');status.setAttribute('role','status');
    const editor=make('details',undefined,container);editor.classList.add('wf-editor');editor.hidden=true;
    make('summary','Разместить / создать',editor);
    make('h3','Размещение цели или Action',editor);
    const grid=make('div',undefined,container);grid.classList.add('wf-grid');grid.hidden=true;
    if(transport.setStatus)transport.setStatus(message=>{status.textContent=message;});
    const future=make('section',undefined,grid),history=make('section',undefined,grid);
    let fieldParent=editor;
    function field(name,label,tag='input',type='text'){
      const l=make('label',label,fieldParent),x=make(tag,undefined,l);
      if(tag==='input')x.type=type;x.value='';
      x.setAttribute('aria-label',label);fields[name]=x;return x;
    }
    const target=field('target','Цель или Action','select');
    const details=make('p','',editor);
    field('note','Основание изменения или результат выполнения','textarea');
    field('placement','Сохранённое размещение','select');
    field('at','Дата начала не ранее','input','date');
    field('after','После размещённой цели или Action','select');
    const placementDetails=make('p',undefined,editor);
    const planControls=make('div',undefined,editor);
    const graphEditor=make('details',undefined,editor);
    make('summary','Изменить граф или записать результат',graphEditor);
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
      buttons.retry.hidden=!pending;buttons.retry.disabled=busy||!pending;buttons.refresh.disabled=busy;
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
      heading.textContent=view.title;grid.hidden=false;editor.hidden=false;focus();
      if(options.onGraph)await options.onGraph(graph());
    }
    async function refreshView(){
      if(busy)return;busy=true;updateControls();status.textContent='Запрашиваю данные локального Helper…';
      try{await install(await transport.read());status.textContent='Данные перечитаны.';status.classList.remove('wf-error');}
      catch(e){status.textContent='Не удалось загрузить данные: '+e.message+(view?' Показаны ранее загруженные данные.':'');status.classList.add('wf-error');}
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
      get busy(){return busy;},get status(){return status.textContent;},get text(){return container.textContent;}};
  }
  return {mount,fileTransport};
});
