/* Portable UI: application projections and intents only. No domain writer. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else{
    root.RDGPortableUI=api;
    if(root.RDG_LOCAL_PORTABLE)Promise.resolve().then(()=>{
      const host=document.createElement('div');host.id='rdg-viewer-root';document.body.appendChild(host);
      const base=new URL('./',location.href);
      const send=async (route,body)=>{
        const response=await fetch(new URL(route,base),{method:'POST',credentials:root.RDG_AUTHENTICATED_SERVER?'same-origin':'omit',redirect:'error',
          headers:{'Content-Type':'application/json','X-RDG-Session':root.RDG_SESSION},body:JSON.stringify(body)});
        const value=await response.json();
        if(!response.ok){const error=Error(value.error||'Запрос отклонён');error.definite=value.definite!==false;throw error;}
        return value;
      };
      const call=body=>send('command',body),approval=root.RDG_APPROVAL_AVAILABLE?body=>send('approval',body):undefined;
      root.RDG_PORTABLE_EDITOR=api.mount(host,{call,approval},{document});void root.RDG_PORTABLE_EDITOR.start();
    });
  }
})(globalThis,function(){
  'use strict';
  const clone=value=>JSON.parse(JSON.stringify(value));
  const names={working:'Рабочий',ready:'Шаблон ready',copy:'Копия',lens:'Линза'};
  const statuses={future:'Предстоящие',possible:'Возможные',unresolved:'Требуют решения',excluded:'Не входят в предстоящее'};
  function diffRows(before,after,path=''){
    if(JSON.stringify(before)===JSON.stringify(after))return [];
    if(Array.isArray(before)&&Array.isArray(after)){
      const keyed=value=>value.every(v=>v&&typeof v==='object'&&typeof v.id==='string')&&new Set(value.map(v=>v.id)).size===value.length;
      if(keyed(before)&&keyed(after)){
        const old=new Map(before.map(v=>[v.id,v])),next=new Map(after.map(v=>[v.id,v])),rows=[];
        const ids=[...new Set([...old.keys(),...next.keys()])].sort();
        for(const id of ids)rows.push(...diffRows(old.get(id),next.get(id),path+'['+id+']'));
        const oldOrder=before.map(v=>v.id),newOrder=after.map(v=>v.id);
        if(JSON.stringify(oldOrder)!==JSON.stringify(newOrder))rows.push({path:path+' · порядок',before:oldOrder,after:newOrder});
        return rows;
      }
    }else if(before&&after&&typeof before==='object'&&typeof after==='object'&&!Array.isArray(before)&&!Array.isArray(after)){
      return [...new Set([...Object.keys(before),...Object.keys(after)])].sort().flatMap(
        key=>diffRows(before[key],after[key],path?path+'.'+key:key));
    }
    return [{path:path||'Содержимое',before,after}];
  }
  async function browserAssertion(begin){
    if(!globalThis.isSecureContext||!globalThis.navigator?.credentials?.get)throw Error('WebAuthn недоступен в этом браузере или по этому адресу.');
    const decode=text=>Uint8Array.from(atob(text.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));
    const encode=value=>btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
    const options=begin.options.publicKey;
    const publicKey=globalThis.PublicKeyCredential?.parseRequestOptionsFromJSON?
      globalThis.PublicKeyCredential.parseRequestOptionsFromJSON(options):
      {...options,challenge:decode(options.challenge),allowCredentials:options.allowCredentials?.map(c=>({...c,id:decode(c.id)}))};
    const credential=await navigator.credentials.get({publicKey});
    if(!credential)throw Error('Подтверждение отменено.');
    if(credential.toJSON)return credential.toJSON();
    const r=credential.response;
    return {id:credential.id,rawId:encode(credential.rawId),type:credential.type,
      clientExtensionResults:credential.getClientExtensionResults(),
      response:{authenticatorData:encode(r.authenticatorData),clientDataJSON:encode(r.clientDataJSON),
        signature:encode(r.signature),userHandle:r.userHandle==null?null:encode(r.userHandle)}};
  }
  async function browserRegistration(begin){
    if(!globalThis.isSecureContext||!navigator.credentials?.create)throw Error('Регистрация ключа недоступна в этом браузере.');
    const decode=text=>Uint8Array.from(atob(text.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));
    const encode=value=>btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
    const options=begin.options.publicKey;
    const publicKey=globalThis.PublicKeyCredential?.parseCreationOptionsFromJSON?
      PublicKeyCredential.parseCreationOptionsFromJSON(options):
      {...options,challenge:decode(options.challenge),user:{...options.user,id:decode(options.user.id)},
       excludeCredentials:options.excludeCredentials?.map(c=>({...c,id:decode(c.id)}))};
    const credential=await navigator.credentials.create({publicKey});
    if(!credential)throw Error('Регистрация отменена.');
    if(credential.toJSON)return credential.toJSON();
    return {id:credential.id,rawId:encode(credential.rawId),type:credential.type,
      clientExtensionResults:credential.getClientExtensionResults(),
      response:{attestationObject:encode(credential.response.attestationObject),
                clientDataJSON:encode(credential.response.clientDataJSON),
                transports:credential.response.getTransports?.()||[]}};
  }
  function mount(container,transport,{document:doc=globalThis.document,onStateChange=()=>{},getAssertion=null,startInExplorer=globalThis.RDG_DECISION_EXPLORER===true}={}){
    let decisionController=null,decisionActive=false;let catalog=null,migrationSources=null,view=null,selected=null,focus={kind:'graph'},busy=false,pending=null,draft=null,history=null,lensReturn=null;
    let approvalList=null,approvalCurrent=null,approvalMessage='',approvalUncertain=false,approvalWorking=false,approvalOpening=null,enrollment=null,enrollmentMessage='';
    const root=doc.createElement('section');root.className='rdgp';container.replaceChildren(root);
    const style=doc.createElement('style');style.textContent=`
      .rdgp{font:14px/1.5 system-ui;color:#e3edf7;background:#14263a;padding:16px;border-radius:10px;min-width:0}
      .rdgp *{box-sizing:border-box}.rdgp h2,.rdgp h3{margin:8px 0}.rdgp button,.rdgp input,.rdgp select,.rdgp textarea{font:inherit;color:inherit;background:#203b53;border:1px solid #65849f;border-radius:5px;padding:6px 9px}
      .rdgp button{cursor:pointer}.rdgp button:disabled{opacity:.5;cursor:default}.rdgp label{display:block;margin:7px 0}.rdgp input,.rdgp textarea,.rdgp select{max-width:100%}.rdgp textarea{width:100%;min-height:90px}.rdgp pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 ui-monospace,monospace}
      .rdgp .rp-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.rdgp .rp-grid{display:grid;grid-template-columns:minmax(180px,260px) minmax(0,1fr);gap:16px}.rdgp .rp-catalog button{display:block;width:100%;text-align:left;margin:7px 0}.rdgp .rp-catalog small{display:block;overflow-wrap:anywhere;color:#bdd0df}.rdgp .rp-card{border:1px solid #58748c;border-radius:7px;padding:10px;margin:10px 0}.rdgp .rp-error{color:#ffc5ab}.rdgp .rp-stale{color:#ffd28f}.rdgp summary{cursor:pointer;font-weight:600}.rdgp svg{width:100%;min-height:260px;background:#102033;border-radius:6px;touch-action:none}.rdgp svg text{fill:#e3edf7;font:12px system-ui;pointer-events:none}.rdgp svg .rp-node{cursor:pointer}.rdgp .rp-status{white-space:pre-wrap;margin:10px 0}.rdgp .rp-graph-tools{display:flex;gap:8px;flex-wrap:wrap}.rdgp .rp-pill{border:1px solid #6c8399;border-radius:12px;padding:2px 8px;display:inline-block;margin-right:6px}@media(max-width:720px){.rdgp .rp-grid{grid-template-columns:1fr}.rdgp .rp-catalog{max-height:220px;overflow:auto}}
    `;root.appendChild(style);
    style.textContent+=".rdgp .rp-diff{width:100%;table-layout:fixed;border-collapse:collapse;margin:10px 0}.rdgp .rp-diff th,.rdgp .rp-diff td{border:1px solid #58748c;padding:7px;vertical-align:top;overflow-wrap:anywhere}.rdgp .rp-diff th{text-align:left}.rdgp .rp-diff pre{margin:0}.rdgp .rp-approvals{overflow-wrap:anywhere}.rdgp .rp-approvals button{max-width:100%;overflow-wrap:anywhere}.rdgp .rp-approvals>button{margin:4px}.rdgp .rp-approval-status{white-space:pre-wrap}";
    style.textContent+=`
      .rdgp .rp-approval-header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px}
      .rdgp .rp-approval-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:10px;margin:12px 0}
      .rdgp .rp-request{display:flex;flex-direction:column;align-items:flex-start;gap:7px;text-align:left;padding:12px;min-width:0}
      .rdgp .rp-request strong{font-size:15px;line-height:1.4}.rdgp .rp-request[aria-pressed="true"]{background:#24506b;border-color:#8ccbf0;box-shadow:inset 3px 0 #8ccbf0}
      .rdgp .rp-request-summary{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:13px;color:#c4d4e2}
      .rdgp .rp-request-meta{font-size:13px;color:#bdd0df}.rdgp .rp-badge{font-size:12px;padding:2px 8px;border-radius:10px;background:#152b3d;color:#d5e7f3}
      .rdgp .rp-enrollment{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:10px 12px;margin:12px 0;background:#102033;border:1px solid #496880;border-radius:6px}
      .rdgp .rp-enrollment details{margin-left:auto}.rdgp .rp-enrollment p{margin:0}.rdgp .rp-selected-request{border-color:#8ccbf0}
      .rdgp .rp-approval-status{padding:10px 12px;background:#203b53;border-radius:6px}
    `;
    const approvals=el('section',null,'rp-card rp-approvals');approvals.setAttribute('aria-label','Запросы подтверждения');
    const heading=el('h2','Graph · пакеты'),status=el('p','Подключение…','rp-status'),bar=el('div',null,'rp-bar');
    const grid=el('div',null,'rp-grid'),aside=el('nav',null,'rp-catalog'),main=el('main'),preview=el('section',null,'rp-card');
    root.appendChild(heading);root.appendChild(bar);root.appendChild(status);root.appendChild(preview);root.appendChild(approvals);root.appendChild(grid);grid.appendChild(aside);grid.appendChild(main);
    style.textContent+=".rdgp.rdgp-decision-host{padding:0;border-radius:0;height:100%;min-height:490px}body:has(#rdg-viewer-root .rdgp-decision-host){margin:0;background:#0e1927}#rdg-viewer-root:has(.rdgp-decision-host){height:100dvh}body:has(#rdg-viewer-root .rdgp-decision-host)>.rdg-session-notice{display:none}";
    const decisionHost=el('section');decisionHost.style.height='100%';decisionHost.hidden=true;root.appendChild(decisionHost);
    function decisionMode(enabled){decisionActive=enabled;root.classList.toggle('rdgp-decision-host',enabled);for(const n of [heading,bar,status,preview,approvals,grid])n.style.display=enabled?'none':'';decisionHost.hidden=!enabled;}
    function el(tag,text,cls){const n=doc.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;}
    function button(parent,text,fn,disabled=false){const n=el('button',text);n.type='button';n.disabled=disabled;n.onclick=()=>run(fn);parent.appendChild(n);return n;}
    function field(parent,title,value='',type='text'){const label=el('label',title+' '),n=el(type==='textarea'?'textarea':'input');if(type!=='textarea')n.type=type;n.value=value;label.appendChild(n);parent.appendChild(label);return n;}
    function select(parent,title,items,value){const label=el('label',title+' '),n=el('select');for(const [id,text] of items){const o=el('option',text);o.value=id;n.appendChild(o);}n.value=value??items[0]?.[0]??'';label.appendChild(n);parent.appendChild(label);return n;}
    function details(parent,title){const n=el('details'),s=el('summary',title);n.appendChild(s);parent.appendChild(n);return n;}
    function json(parent,value){const pre=el('pre',JSON.stringify(value,null,2));parent.appendChild(pre);return pre;}
    function note(text,error=false){status.textContent=text;status.className='rp-status'+(error?' rp-error':'');}
    async function run(fn){if(busy)return;busy=true;onStateChange();try{await fn();}catch(e){note(e.message,true);}finally{busy=false;onStateChange();}}
    const call=message=>transport.call?transport.call(message):transport.write(message);
    function guarded(){if(pending)throw Error('Сначала завершите или отмените подготовленную операцию.');}
    function cleanLayout(){if(draft)throw Error('Сначала сохраните или отмените изменения раскладки.');}
    function activateDecision(){const api=typeof module==='object'&&module.exports?require('./rdg-decision-ui.js'):globalThis.RDGDecisionUI;if(!api)throw Error('Decision Viewer недоступен.');decisionController??=api.mount(decisionHost,{call,approval:transport.approval},{document:doc,onLegacyOpen:async id=>{decisionMode(false);return open(id);}});decisionMode(true);return decisionController;}
    async function refresh(){if(decisionActive)return decisionController.refresh();guarded();catalog=await call({method:'catalog'});if(!selected&&catalog.packages.some(p=>p.coreModel==='rdg-decision-v1'))return activateDecision().start(catalog);migrationSources=await call({method:'migration_sources'});renderCatalog();if(selected)await open(selected,focus);else renderEmpty();await refreshApprovals();note('Каталог прочитан из фактических папок.');}
    async function open(id,spec={kind:'graph'}){
      guarded();cleanLayout();const current=await call({method:'read',packageId:id,includePlan:true,view:spec});
      if(current.graph.coreModel==='rdg-decision-v1'){
        await activateDecision().open(id,spec);return decisionController.view;
      }
      decisionMode(false);selected=id;focus=spec;view=current;history=null;render();return view;
    }
    async function schema(op,nodeId,extra={}){return (await call({method:'schema',op,packageId:selected,nodeId,...extra})).request;}
    async function prepare(request){
      if(decisionActive)return decisionController.prepare(request);
      guarded();if(request.op!=='layout_edit')cleanLayout();
      const exact=clone(request);
      if(transport.approval&&['lock_set','lock_remove'].includes(exact.op))exact.authorityPrincipal='';
      let result;
      try{result=await call({method:'preflight',request:exact});}
      catch(error){
        if(transport.approval&&error.message.includes('VERIFIED_APPROVAL_REQUIRED')){
          const proposed=await call({method:'approval_request',request:exact,rationale:exact.note});
          await refreshApprovals();await openApproval(proposed.requestId);
          note('Проверьте изменение замка и подтвердите его зарегистрированным ключом.');return;
        }
        throw error;
      }
      pending={request:exact,preview:result,uncertain:false};renderPreview();note('Проверьте последствия и подтвердите сохранение.');
    }
    async function commit(){
      if(decisionActive)return decisionController.commit();
      if(!pending)return;const exact=pending.request;
      try{
        const result=await call({method:'apply',request:exact});
        if(result.published!==true)throw Error('Сохранение не подтверждено. Проверьте receipt.');
        const created=result.packages?.find(r=>r.receipt?.effects?.createdPackageId)?.receipt.effects.createdPackageId;
        const committed=exact.op;pending=null;if(committed==='layout_edit')draft=null;renderPreview();
        catalog=await call({method:'catalog'});migrationSources=await call({method:'migration_sources'});renderCatalog();
        if(created)await open(created);else if(selected)await open(selected,committed==='delete'||committed==='apply_ready'?{kind:'graph'}:focus);
        note('Изменения сохранены. Receipt подтверждён.');return result;
      }catch(e){if(pending)pending.uncertain=e.definite!==true;renderPreview();throw e;}
    }
    function renderPreview(){
      preview.replaceChildren();preview.hidden=!pending;if(!pending)return;
      preview.appendChild(el('h3',pending.uncertain?'Исход операции нужно подтвердить':'Предварительная проверка'));
      preview.appendChild(el('p','Операция: '+pending.request.op+' · '+pending.request.transactionId));
      if(pending.request.data?.cosmetic===true)preview.appendChild(el('p','Косметическая правка: изменение определения не вызывает пересмотр у L1/L2-подписчиков.'));
      const effects=clone(pending.preview.effects||{});
      for(const key of ['graphs','plans'])if(effects[key])effects[key]=Object.fromEntries(Object.entries(effects[key]).map(([id,value])=>[id,{revision:value.revision,entities:value.nodes?.length,placements:value.steps?.length}]));
      json(preview,effects);
      button(preview,pending.uncertain?'Повторить тот же запрос':'Сохранить',commit);
      button(preview,'Отменить подготовку',async()=>{pending=null;renderPreview();note('Подготовка отменена.');},pending.uncertain);
      button(preview,'Прочитать receipt',async()=>{
        const result=await call({method:'receipt',packageId:pending.preview.effects?.createdPackageId||pending.request.targetPackageId||selected,transactionId:pending.request.transactionId});json(preview,result);
      });
    }
    const approvalLabels={pending:'Ожидает решения',rejected:'Отклонено',
      'approved-awaiting-recovery':'Подтверждено · требуется восстановление',
      'executed-approved':'Выполнено после подтверждения','executed-independently':'Выполнено самостоятельно'};
    const approveCall=message=>{
      if(!transport.approval)throw Error('Подтверждение недоступно в этом подключении.');
      return transport.approval(message);
    };
    function approvalError(error){
      if(/CAS_MISMATCH|REVISION_CONFLICT|PIN_CHANGED/.test(error.message))return 'Запрос создан для прежней версии. Инициатор должен подготовить новый запрос.';
      if(/PREVIEW_CHANGED|INCOMING_|REQUEST_CHANGED/.test(error.message))return 'Данные изменились. Обновите изменения и подтвердите их заново.';
      if(/VIEW_UNAVAILABLE|CEREMONY_UNAVAILABLE/.test(error.message))return 'Подтверждение больше не действует. Обновите изменения.';
      if(/CREDENTIAL_UNAVAILABLE|PRINCIPAL_NOT_ENROLLED|BINDING_UNAVAILABLE/.test(error.message))return 'Ключ отозван или недоступен. Для нового ключа требуется приглашение владельца.';
      if(/AUTH_|EXECUTOR_BINDING/.test(error.message))return 'Право исполнения недоступно. Обновите запрос или обратитесь к владельцу прав.';
      return error.message;
    }
    async function refreshApprovals(){
      if(!transport.approval){renderApprovals();return;}
      const result=await approveCall({method:'list'});approvalList=result.requests;enrollment=result.enrollment||null;renderApprovals();
    }
    async function openApproval(requestId){
      guarded();cleanLayout();
      approvalOpening=requestId;approvalCurrent=null;approvalUncertain=false;
      approvalMessage='Открываем запрос…';note(approvalMessage);renderApprovals();
      try{
        approvalCurrent=await approveCall({method:'open',requestId});
        approvalMessage='';note('Запрос открыт. Сравните изменения ниже.');return approvalCurrent;
      }catch(error){
        approvalMessage='Не удалось открыть запрос: '+approvalError(error);throw error;
      }finally{
        approvalOpening=null;renderApprovals();
        if(approvalCurrent)approvals.querySelector?.('[data-approval-current]')?.scrollIntoView?.({block:'nearest',behavior:'smooth'});
      }
    }
    async function approvalStatus(){
      if(!approvalCurrent)return;
      const requestId=approvalCurrent.record.requestId;
      const record=await approveCall({method:'status',requestId});
      approvalCurrent={record,previewAvailable:false,preview:null};
      approvalUncertain=false;renderApprovals();return record;
    }
    async function refreshAfterApproval(){
      catalog=await call({method:'catalog'});renderCatalog();
      await refreshApprovals();
      if(selected)await open(selected,{kind:'graph'});
    }
    async function decideApproval(decision){
      guarded();cleanLayout();
      if(!approvalCurrent?.viewId||approvalUncertain)throw Error('Сначала обновите изменения запроса.');
      approvalWorking=true;approvalMessage='Проверка запроса…';renderApprovals();
      let submitted=false;
      try{
        const begin=await approveCall({method:'choose',viewId:approvalCurrent.viewId,decision});
        approvalMessage='Подтвердите решение средствами браузера.';renderApprovals();
        const response=await (getAssertion||browserAssertion)(begin);
        submitted=true;
        await approveCall({method:'complete',ceremonyId:begin.ceremonyId,response});
        const state=await approvalStatus();
        approvalMessage=state.state==='rejected'?'Запрос отклонён. Предложенные изменения не выполнены.':
          state.state==='executed-approved'?'Подтверждённые изменения выполнены.':
          'Решение сохранено. Прочитайте состояние операции.';
        try{await refreshAfterApproval();}catch(e){approvalMessage+=' Не удалось обновить Graph или список: '+e.message;}
      }catch(error){
        if(submitted){
          approvalUncertain=true;approvalMessage='Ответ исполнения не получен. Проверяется фактическое состояние…';renderApprovals();
          try{
            const state=await approvalStatus();
            approvalMessage=state.state==='executed-approved'?'Изменения выполнены; результат подтверждён чтением состояния.':
              state.state==='approved-awaiting-recovery'?'Операция принята. Завершите восстановление без нового подтверждения.':
              state.state==='rejected'?'Запрос отклонён.':
              approvalError(error)+' Принятие не подтверждено. Обновите изменения перед новым решением.';
            if(state.state==='executed-approved')try{await refreshAfterApproval();}catch(e){approvalMessage+=' Graph нужно перечитать: '+e.message;}
          }catch(_){approvalMessage='Исход исполнения неизвестен. Сначала прочитайте состояние запроса.';}
        }else{
          approvalMessage=['NotAllowedError','AbortError'].includes(error.name)?
            'Подтверждение отменено в браузере. Изменения не отправлены.':approvalError(error);
          approvalCurrent.viewId=null;approvalCurrent.previewAvailable=false;
          approvalCurrent.previewStale=true;
        }
      }finally{approvalWorking=false;renderApprovals();}
    }
    async function recoverApproval(){
      guarded();cleanLayout();
      if(!approvalCurrent||approvalCurrent.record.state!=='approved-awaiting-recovery')throw Error('Нет принятой операции для восстановления.');
      approvalWorking=true;approvalMessage='Завершение ранее принятой операции…';renderApprovals();
      try{
        await approveCall({method:'recover',requestId:approvalCurrent.record.requestId});
        await approvalStatus();approvalMessage='Ранее принятые изменения восстановлены.';
        try{await refreshAfterApproval();}catch(e){approvalMessage+=' Graph нужно перечитать: '+e.message;}
      }catch(e){
        approvalUncertain=true;approvalMessage='Исход восстановления нужно проверить.';
        try{await approvalStatus();}catch(_){/* keep the unknown result visible */}
      }finally{approvalWorking=false;renderApprovals();}
    }
    async function registerCredential(){
      guarded();cleanLayout();approvalWorking=true;enrollmentMessage='Подготовка регистрации…';renderApprovals();
      let submitted=false;
      try{
        const begin=await approveCall({method:'registration_begin'});
        enrollmentMessage='Зарегистрируйте свой ключ средствами браузера.';renderApprovals();
        const response=await browserRegistration(begin);
        submitted=true;
        await approveCall({method:'registration_complete',ceremonyId:begin.ceremonyId,response});
        await refreshApprovals();enrollmentMessage='Ключ зарегистрирован. Привязка сохранена.';
      }catch(error){
        if(submitted){
          try{
            await refreshApprovals();
            enrollmentMessage=enrollment?.state==='completed'?'Ключ зарегистрирован; результат подтверждён чтением состояния.':
              'Регистрация не подтверждена. Проверьте состояние приглашения.';
          }catch(_){enrollmentMessage='Исход регистрации неизвестен. Обновите запросы перед повтором.';}
        }else enrollmentMessage=['NotAllowedError','AbortError'].includes(error.name)?
          'Регистрация отменена в браузере.':approvalError(error);
      }finally{approvalWorking=false;renderApprovals();}
    }
    function renderEnrollment(){
      if(!enrollment)return;
      const box=el('section',null,'rp-enrollment');box.setAttribute('data-enrollment-state',enrollment.state);
      approvals.appendChild(box);
      if(enrollment.state==='completed'){
        box.appendChild(el('strong','Ключ зарегистрирован'));
        box.appendChild(el('span','Можно подтверждать запросы.','rp-request-meta'));
        const account=details(box,'Учётная запись');account.appendChild(el('p',enrollment.displayName+' · '+enrollment.principalId));
        return;
      }
      box.appendChild(el('h3','Регистрация ключа'));
      box.appendChild(el('p','Учётная запись: '+enrollment.displayName+' · '+enrollment.principalId));
      box.appendChild(el('p','Ключ будет связан с существующими правами этой учётной записи.'));
      if(enrollmentMessage){const message=el('p',enrollmentMessage);message.setAttribute('role','status');box.appendChild(message);}
      if(['issued','started'].includes(enrollment.state)){
        box.appendChild(el('p','Приглашение на регистрацию подготовлено владельцем Authority.'));
        button(box,'Зарегистрировать ключ',registerCredential,approvalWorking||!globalThis.isSecureContext||!globalThis.navigator?.credentials?.create);
      }else box.appendChild(el('p',enrollment.state==='completed'?'Ключ зарегистрирован.':
        enrollment.state==='revoked'?'Ключ отозван. Для нового ключа нужно новое приглашение владельца.':
        'Приглашение больше не действует. Требуется новое приглашение владельца.'));
    }
    function operationLabel(request){
      const operation=request.command||request.op,target=request.data?.nodeId||request.nodeId;
      const labels={edit:'Изменить блок',lock_set:'Установить замок',lock_remove:'Снять замок',
        delete:'Удалить блок',select:'Выбрать Action',review:'Подтвердить пересмотр',
        complete:'Подтвердить результат',dependency_add:'Добавить зависимость',dependency_remove:'Снять зависимость'};
      return (labels[operation]||operation)+(target?' · '+target:'')+(request.data?.cosmetic===true?' · Косметическая правка':'');
    }
    function requestTitle(item){
      return catalog?.packages?.find(row=>row.packageId===item.targetPackageId)?.title||operationLabel(item.request);
    }
    function renderApprovals(){
      approvals.replaceChildren();
      const header=el('div',null,'rp-approval-header');approvals.appendChild(header);
      const waiting=approvalList?.filter(item=>item.state==='pending').length;
      header.appendChild(el('h3','Запросы подтверждения'+(waiting!=null?' · '+waiting+' ожидают решения':'')));
      if(!transport.approval){approvals.appendChild(el('p','Подтверждение недоступно в этом подключении.'));return;}
      button(header,'Обновить запросы',refreshApprovals,approvalWorking||!!approvalOpening);renderEnrollment();
      if(approvalList===null)approvals.appendChild(el('p','Список ещё не прочитан.'));
      else if(!approvalList.length)approvals.appendChild(el('p','Доступных запросов нет.'));
      else{
        approvals.appendChild(el('p','Выберите запрос, чтобы сравнить «Было / Станет» и принять решение.','rp-request-meta'));
        const list=el('div',null,'rp-approval-list');approvals.appendChild(list);
        for(const item of approvalList){
          const b=button(list,'',()=>openApproval(item.requestId),approvalWorking||!!approvalOpening);
          b.className='rp-request';b.setAttribute('data-approval-request',item.requestId);
          b.setAttribute('aria-pressed',String((approvalOpening||approvalCurrent?.record.requestId)===item.requestId));
          b.appendChild(el('span',approvalOpening===item.requestId?'Открываем…':approvalLabels[item.state]||item.state,'rp-badge'));
          b.appendChild(el('strong',requestTitle(item)));
          b.appendChild(el('span',operationLabel(item.request),'rp-request-meta'));
          b.appendChild(el('span',item.rationale,'rp-request-summary'));
        }
      }
      if(approvalMessage){const message=el('p',approvalMessage,'rp-approval-status');message.setAttribute('role','status');approvals.appendChild(message);}
      if(!approvalCurrent)return;
      const value=approvalCurrent.record,card=el('article',null,'rp-card rp-selected-request');
      card.setAttribute('data-approval-current',value.requestId);approvals.appendChild(card);
      card.appendChild(el('span',approvalLabels[value.state]||value.state,'rp-badge'));
      card.appendChild(el('h3',operationLabel(value.request)));
      card.appendChild(el('p',value.rationale));
      const metadata=details(card,'Сведения о запросе');
      metadata.appendChild(el('p','Запрос: '+value.requestId));
      metadata.appendChild(el('p','Пакет: '+value.targetPackageId+' · инициатор: '+value.initiator.grantId));
      if(approvalUncertain)card.appendChild(el('p','Результат пока неизвестен. Новое решение заблокировано.','rp-error'));
      if(approvalCurrent.previewStale)card.appendChild(el('p','Показанные изменения больше не разрешают исполнение. Обновите карточку.','rp-stale'));
      const shown=approvalCurrent.preview;
      if(shown){
        card.appendChild(el('p','Затронутых пакетов: '+shown.owners.length,'rp-request-meta'));
        for(const owner of shown.owners){
          const box=el('section',null,'rp-card');box.setAttribute('data-approval-owner',owner.packageId);card.appendChild(box);
          box.appendChild(el('h3',owner.before?.graph?.title||owner.after.graph?.title||owner.path));
          box.appendChild(el('p',owner.path,'rp-request-meta'));
          const table=el('table',null,'rp-diff'),head=el('tr');
          for(const text of ['Поле','Было','Станет'])head.appendChild(el('th',text));
          table.appendChild(head);
          const rows=diffRows(owner.before,owner.after),audit=rows.filter(r=>/^graph\.events(?:\[|\s|$)/.test(r.path)||/(^|\.)revision$/.test(r.path));
          const material=rows.filter(r=>!audit.includes(r)).sort((a,b)=>{
            const rank=r=>/\.(title|description|scope)$/.test(r.path)?0:/\.review$/.test(r.path)?2:1;
            return rank(a)-rank(b)||a.path.localeCompare(b.path);
          });
          for(const row of material){
            const label=row.path.replace(/^graph\.nodes/,'Блоки').replace(/^graph\.objects/,'Объекты').replace(/^graph\.edges/,'Связи')
              .replace(/\.title$/,' · Название').replace(/\.description$/,' · Описание').replace(/\.scope$/,' · Область').replace(/\.review$/,' · Пересмотр');
            const tr=el('tr');tr.appendChild(el('td',label));
            for(const value of [row.before,row.after]){
              const cell=el('td');
              if(/\.review$/.test(row.path)&&value&&typeof value.required==='boolean'){
                cell.appendChild(el('p',value.required?'Требуется пересмотр.':'Пересмотр не требуется.'));json(details(cell,'Основания'),value);
              }else cell.appendChild(el('pre',value===undefined?'Отсутствует':typeof value==='string'?value:JSON.stringify(value,null,2)));
              tr.appendChild(cell);
            }
            table.appendChild(tr);
          }
          if(material.length)box.appendChild(table);
          for(const kind of ['graph','plan','layouts'])if(owner.after[kind]?.revision!=null)box.appendChild(el('p','Версия '+kind+': '+(owner.before?.[kind]?.revision??'нет')+' → '+owner.after[kind].revision));
          if(audit.length){
            const added=(owner.after.graph?.events?.length||0)-(owner.before?.graph?.events?.length||0);
            if(added>0)box.appendChild(el('p','В историю будет добавлено записей: '+added+'.'));
            const technical=details(box,'Записи истории и служебные версии');technical.setAttribute('data-approval-audit','');json(technical,audit);
          }
          if(owner.artifacts.length){box.appendChild(el('p','Добавляемые файлы:'));json(box,owner.artifacts);}
        }
        const full=details(card,'Все согласуемые данные');json(full,shown);
      }else if(value.state==='pending'){
        card.appendChild(el('p','Полный просмотр изменений недоступен. Подтверждение выполнения заблокировано.','rp-stale'));
        if(/CAS_MISMATCH|REVISION_CONFLICT|PIN_CHANGED/.test(approvalCurrent.blocker||''))card.appendChild(el('p','Запрос создан для прежней версии. Инициатор должен подготовить новый запрос.','rp-stale'));
        if(approvalCurrent.blocker)json(details(card,'Причина недоступности'),{error:approvalCurrent.blocker});
      }
      const request=details(card,'Точное тело запроса');json(request,value.request);
      if(value.authorizationContext)json(details(card,'Инициатор, подтвердивший и исполнитель'),value.authorizationContext);
      const canSign=getAssertion!==null||!!globalThis.navigator?.credentials?.get&&globalThis.isSecureContext;
      if(value.state==='pending'){
        if(!canSign)card.appendChild(el('p','В этом браузере или по этому адресу WebAuthn недоступен.','rp-stale'));
        button(card,'Подтвердить',()=>decideApproval('approve'),approvalWorking||approvalUncertain||!canSign||!approvalCurrent.previewAvailable||!approvalCurrent.viewId);
        button(card,'Отклонить',()=>decideApproval('reject'),approvalWorking||approvalUncertain||!canSign||!approvalCurrent.viewId);
        button(card,'Обновить изменения',()=>openApproval(value.requestId),approvalWorking||approvalUncertain);
      }
      button(card,'Прочитать состояние',async()=>{try{await approvalStatus();approvalMessage='Состояние перечитано.';}catch(e){approvalMessage=approvalError(e);}renderApprovals();},approvalWorking);
      if(value.state==='approved-awaiting-recovery')button(card,'Завершить принятую операцию',recoverApproval,approvalWorking||approvalUncertain);
    }
    function renderCatalog(){
      aside.replaceChildren();aside.appendChild(el('h3','Папки и Graph'));
      const folders=new Map([['',aside]]);
      function folder(path){
        if(folders.has(path))return folders.get(path);
        const parts=path.split('/'),name=parts.pop(),parent=folder(parts.join('/'));
        const box=details(parent,name);box.open=true;folders.set(path,box);return box;
      }
      for(const row of catalog?.folders||[])folder(row.path);
      const stages=(catalog?.packages||[]).filter(r=>r.health==='unaccepted-stage');
      const stageBox=stages.length?details(aside,'Непринятые операции · '+stages.length):null;
      for(const row of catalog?.packages||[]){
        const parent=folder(row.path.split('/').slice(0,-1).join('/'));
        const b=button(row.health==='unaccepted-stage'?stageBox:parent,(names[row.role]||'Пакет')+' · '+(row.title||row.packageId||row.path),()=>open(row.packageId));
        b.setAttribute('data-package-id',row.packageId||'');
        b.appendChild(el('small',row.path+(row.lensKey?' · lensKey: '+row.lensKey:'')));
        if(row.health!=='metadata-verified')b.appendChild(el('small',row.error||row.health,'rp-error'));
      }
    }
    function renderEmpty(){main.replaceChildren();main.appendChild(el('p','Выберите пакет или создайте Graph.'));createForm(main);}
    function createForm(parent){
      const form=details(parent,'Создать Graph');const role=select(form,'Назначение',Object.entries(names).filter(([k])=>k!=='copy'));
      const profile=select(form,'Модель',[['rdg-core-v1','R / Action'],['rdg-decision-v1','R / Decision / Action']]);
      const reason=field(form,'Основание процесса');
      const path=field(form,'Папка относительно корня пакетов'),title=field(form,'Название и корневая R'),scope=field(form,'Область применения'),lens=field(form,'lensKey для линзы');
      button(form,'Проверить создание',async()=>{
        const request=(await call({method:'schema',op:'create'})).request;Object.assign(request,{role:role.value,path:path.value,title:title.value,scope:scope.value,coreModel:profile.value});
        if(profile.value==='rdg-decision-v1')request.rootReason=reason.value;
        if(role.value==='lens')request.lensKey=lens.value;await prepare(request);
      });
      const folders=details(parent,'Папки');
      for(const row of catalog?.folders||[])folders.appendChild(el('p',row.path));
      const destination=field(folders,'Новая папка'),source=field(folders,'Текущая папка для переноса');
      button(folders,'Проверить создание папки',async()=>{const request=(await call({method:'schema',op:'folder_create'})).request;request.path=destination.value;await prepare(request);});
      button(folders,'Проверить перенос папки',async()=>{const request=(await call({method:'schema',op:'folder_move',sourcePath:source.value})).request;request.path=destination.value;await prepare(request);});
      const recovery=field(folders,'ID уже принятой операции');
      button(folders,'Завершить принятую операцию',async()=>{guarded();cleanLayout();await call({method:'recover',transactionId:recovery.value.trim()});await refresh();});
      button(folders,'Снять блокировку непринятой миграции',async()=>{guarded();cleanLayout();await call({method:'cancel_migration',transactionId:recovery.value.trim()});await refresh();});
      if(migrationSources?.sources?.some(s=>!s.route)){
        const migration=details(parent,'Перенести прежний owner в пакет');
        const sources=select(migration,'Источник',migrationSources.sources.filter(s=>!s.route).map(s=>[s.sourceKey,s.sourceKey+' · '+s.graphFile]));
        const path=field(migration,'Папка нового пакета');
        const switchOwner=field(migration,'Переключить owner и запретить прежнюю запись',false,'checkbox');
        const quiesced=field(migration,'Прежние Helper и writers остановлены',false,'checkbox');
        const complete=field(migration,'Все сохранённые раскладки включены',false,'checkbox');
        const paused=field(migration,'Запись раскладок приостановлена',false,'checkbox');
        const gaps=field(migration,'Прочитал и принимаю ограничения исторических доказательств',false,'checkbox');
        button(migration,'Прочитать preflight источника',async()=>json(migration,await call({method:'migration_inspect',sourceKey:sources.value})));
        button(migration,'Проверить переключение owner',async()=>{
          const request=(await call({method:'schema',op:'migrate',sourceKey:sources.value})).request;
          Object.assign(request,{path:path.value,confirmOwnerSwitch:switchOwner.checked,legacyWritersQuiesced:quiesced.checked,presentationSourcesComplete:complete.checked,
            presentationWritersPaused:paused.checked,acknowledgeHistoricalGaps:gaps.checked});await prepare(request);
        });
      }
    }
    function render(){
      main.replaceChildren();bar.replaceChildren();button(bar,'Обновить каталог',refresh);button(bar,'Все пакеты',async()=>{guarded();cleanLayout();selected=null;view=null;renderEmpty();});
      main.appendChild(el('h2',view.graph.title));main.appendChild(el('p',(names[view.package.role]||view.package.role)+' · '+view.path));
      const work=view.package.role==='working'||view.package.role==='copy';
      const choices=[['graph','Весь Graph'],...view.graph.workGraphs.map(w=>['workGraph:'+w.id,'Область: '+w.title]),
        ...[...view.graph.nodes,...view.graph.objects,...(view.graph.externalActions||[])].map(n=>['focus:'+n.id,n.kind+' · '+n.title])];
      const picker=select(main,'Представление',choices,focus.kind==='graph'?'graph':focus.kind+':'+focus.id);
      picker.onchange=()=>run(()=>{const [kind,...id]=picker.value.split(':');return open(selected,kind==='graph'?{kind}:{kind,id:id.join(':')});});
      if(lensReturn&&view.package.role==='lens')button(bar,'К процессу',async()=>{const target=lensReturn;lensReturn=null;await open(target.id,target.spec);});
      if(work)for(const lens of (catalog?.packages||[]).filter(r=>r.role==='lens'))button(bar,'Открыть линзу · '+lens.title,async()=>{
        const definition=await call({method:'read',packageId:lens.packageId});
        if(definition.graph.coreModel!==view.graph.coreModel)throw Error('Линза не поддерживает модель этого процесса');
        lensReturn={id:selected,spec:clone(focus)};await open(lens.packageId);
      });
      if(view.graph.coreModel==='rdg-decision-v1'){
        for(const g of view.view.decisionGroups||[])main.appendChild(el('p',g.title+' · '+g.parentId+' · '+g.members.map(m=>m.decisionId).join(', ')+
          (g.selectionRequired?' · выбор необходим':' · выбор необязателен')+(g.mutuallyExclusive?' · взаимоисключение':'')));
        if(view.view.externalAction){const info=details(main,'Внешний Action');info.open=true;json(info,view.view.externalAction);}
      }
      draw(main);renderDetached(main);renderReferences(main);renderOperations(main,work);
      if(work){renderPlan(main);const historyBox=details(main,'История Graph и версии Plan');
        button(historyBox,'Прочитать историю',async()=>{history=await call({method:'history',packageId:selected});renderHistory(historyBox,history);});}
      createForm(main);
    }
    function draw(parent,snapshot=view,{readOnly=false,onOpen=null}={}){
      const box=el('section',null,'rp-card'),tools=el('div',null,'rp-graph-tools');
      parent.appendChild(box);box.appendChild(tools);
      const key=snapshot.view.graphKey,saved=snapshot.layouts?.layouts?.[key]||{};
      const active=!readOnly&&draft?.key===key?draft:null;
      const positions=clone(active?.positions||saved.positions||{});
      const occurrences=clone(active?.occurrences||saved.occurrences||{});
      const nodes=snapshot.view.entities;
      for(const canon of nodes.filter(n=>n.kind==='canon'&&n.evaluationMode==='comment-only-v1')){
        const comment=details(box,'Комментарий канона · '+canon.title);comment.open=snapshot.view.spec.kind==='focus';
        comment.appendChild(el('p',canon.comment));
      }
      nodes.forEach((n,i)=>{positions[n.id]??={x:30+(i%3)*235,y:30+Math.floor(i/3)*115};});
      const projection=(typeof module==='object'&&module.exports?require('./rdg-visual-projection.js'):globalThis.RDGVisualProjection);
      const allEntities=[...snapshot.graph.nodes,...snapshot.graph.objects];
      const allEdges=snapshot.graph.edges.filter(e=>!e.archived).concat(snapshot.view.decisionMemberships||[]);
      const picture=projection.project(nodes,snapshot.view.edges.concat((snapshot.view.decisionMemberships||[]).filter(m=>!snapshot.view.edges.some(e=>e.id===m.id))),positions,occurrences,
        {externalEntities:allEntities,externalEdges:allEdges});
      const external=snapshot.view.spec.kind==='workGraph'?projection.boundaries(
        allEntities,allEdges,nodes.map(n=>n.id)):[];
      const exteriorNodes=new Map(allEntities.map(n=>[n.id,n]));
      const renderedBoundary=new Set(picture.routes.map(r=>r.edge.id));
      const ports=external.filter(e=>!renderedBoundary.has(e.edge.id)).slice(0,100).map((item,i)=>{
        const base=positions[item.inside]||{x:30,y:30};
        return {...item,x:base.x+(item.direction==='out'?265:-190),y:base.y+(i%5)*23};
      });
      const ns='http://www.w3.org/2000/svg',svg=doc.createElementNS(ns,'svg');box.appendChild(svg);
      const points=[...picture.nodes.map(n=>n.position).filter(Boolean),...ports];
      const maxX=Math.max(500,...points.map(p=>p.x+230)),maxY=Math.max(280,...points.map(p=>p.y+110));
      const minX=Math.min(0,...points.map(p=>p.x-10)),minY=Math.min(0,...points.map(p=>p.y-10));
      svg.setAttribute('viewBox',[minX,minY,maxX-minX,maxY-minY].join(' '));
      svg.setAttribute('aria-label','Граф: '+snapshot.graph.title);
      const append=(tag,attrs,text)=>{const n=doc.createElementNS(ns,tag);
        for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));
        if(text!=null)n.textContent=text;svg.appendChild(n);return n;};
      const edgeVisuals=[];
      for(const route of picture.routes)edgeVisuals.push([route,
        append('line',{stroke:'#8bb5cc','stroke-width':1.5}),
        append('text',{'text-anchor':'middle'},route.edge.type+' →')]);
      const visualPosition=id=>occurrences[id]||positions[id];
      function paintEdges(){for(const [route,line,text] of edgeVisuals){
        const a=visualPosition(route.from),b=visualPosition(route.to);if(!a||!b)continue;
        for(const [k,v] of Object.entries({x1:a.x+100,y1:a.y+38,x2:b.x+100,y2:b.y+38}))
          line.setAttribute(k,String(v));
        text.setAttribute('x',String((a.x+b.x)/2+100));
        text.setAttribute('y',String((a.y+b.y)/2+29));
      }}
      paintEdges();
      for(const item of ports){
        const inside=positions[item.inside];if(!inside)continue;
        const anchorX=item.x+65,anchorY=item.y+8;
        append('line',{x1:inside.x+100,y1:inside.y+38,x2:anchorX,y2:anchorY,
          stroke:'#7892a5','stroke-width':1,'stroke-dasharray':'5 5'});
        const externalNode=exteriorNodes.get(item.outside);
        const port=append('text',{x: item.x,y:item.y,'aria-label':'Вне WorkGraph: '+(externalNode?.title||item.outside)},
          '↗ '+item.edge.type+' · '+(externalNode?.title||item.outside).slice(0,23));
        port.setAttribute('role','button');port.setAttribute('tabindex','0');port.style.pointerEvents='auto';
        const openPort=()=>readOnly?onOpen?.(item.outside):open(selected,{kind:'focus',id:item.outside});
        port.ondblclick=()=>run(openPort);
        port.onkeydown=e=>{if(e.key==='Enter')void run(openPort);};
      }
      if(picture.invalid.length)box.appendChild(el('p',
        'Есть недействительные визуальные ссылки: '+picture.invalid.map(v=>v.id).join(', '),'rp-error'));
      const editable=()=>!readOnly&&!pending&&!busy;
      const changed=()=>{draft={key,positions,occurrences};note('Раскладка изменена. Сохраните её перед copy или переходом.');};
      const change=fn=>{if(readOnly||pending)return;fn();changed();render();};
      const idFactory=()=> 'occ-'+(globalThis.crypto?.randomUUID?.()||String(Date.now())+'-'+Math.random().toString(36).slice(2));
      const focusNode=n=>readOnly?onOpen?.(n.entityId):open(selected,{kind:'focus',id:n.entityId});
      const groups=[];
      for(const n of picture.nodes){
        const p=visualPosition(n.id);if(!p)continue;
        const state=snapshot.completion[n.entityId]||{};
        const group=doc.createElementNS(ns,'g');
        group.setAttribute('transform',`translate(${p.x},${p.y})`);
        group.setAttribute('class','rp-node');
        group.setAttribute('data-entity-id',n.entityId);
        group.setAttribute('data-occurrence-id',n.id);
        group.setAttribute('tabindex','0');group.setAttribute('role','button');
        const repeated=(picture.counts.get(n.entityId)||0)>1;
        const isOutside=snapshot.view.spec.kind==='workGraph'&&!nodes.some(entity=>entity.id===n.entityId);
        const label=n.node.title+(repeated?' · визуально повторён':'')+(isOutside?' · вне WorkGraph':'');
        group.setAttribute('aria-label',label);svg.appendChild(group);groups.push(group);
        if(repeated){const title=doc.createElementNS(ns,'title');title.textContent='Та же R/A показана в других местах этого вида';group.appendChild(title);}
        const rect=doc.createElementNS(ns,'rect');
        for(const [k,v] of Object.entries({width:205,height:80,rx:9,fill:n.node.kind==='requirement'?'#1c4a60':'#314d63',
          stroke:state.reviewRequired?'#ffc179':'#9fbed0','stroke-width':state.reviewRequired?3:1.5,
          ...(isOutside?{'stroke-dasharray':'5 4'}:{})}))
          rect.setAttribute(k,String(v));group.appendChild(rect);
        for(const [i,line] of [[n.node.kind,n.node.selectionState||n.node.status].filter(Boolean).join(' · '),
          n.node.title.length>27?n.node.title.slice(0,26)+'…':n.node.title,
          state.reviewRequired?'Нужна проверка':state.complete?'Подтверждено':n.entityId.slice(0,24)].entries()){
          const t=doc.createElementNS(ns,'text');t.setAttribute('x','10');t.setAttribute('y',String(20+i*22));
          t.textContent=line;group.appendChild(t);
        }
        if(repeated){const mark=doc.createElementNS(ns,'text');mark.setAttribute('x','186');mark.setAttribute('y','18');mark.setAttribute('aria-hidden','true');mark.textContent='⧉';group.appendChild(mark);}
        const choose=()=>focusNode(n);
        group.ondblclick=()=>run(choose);group.onkeydown=e=>{if(e.key==='Enter')void run(choose);};
        group.onclick=()=>{for(const item of groups)
          item.setAttribute('opacity',item.getAttribute('data-entity-id')===n.entityId?'1':'0.5');};
        let drag=null;
        group.onpointerdown=e=>{if(!editable())return;
          drag={x:e.clientX,y:e.clientY,original:{...visualPosition(n.id)},moved:false};group.setPointerCapture?.(e.pointerId);};
        group.onpointermove=e=>{if(!drag)return;const bounds=svg.getBoundingClientRect();
          const x=drag.original.x+(e.clientX-drag.x)*(maxX-minX)/bounds.width,
            y=drag.original.y+(e.clientY-drag.y)*(maxY-minY)/bounds.height;
          drag.moved ||= Math.abs(e.clientX-drag.x)+Math.abs(e.clientY-drag.y)>3;
          if(drag.moved){
            if(n.alias)Object.assign(occurrences[n.id],{x,y});else positions[n.id]={x,y};
            draft={key,positions,occurrences};group.setAttribute('transform',`translate(${x},${y})`);paintEdges();
          }};
        group.onpointerup=()=>{if(drag?.moved)changed();drag=null;};
        button(tools,n.node.title,choose);
      }
      if(ports.length){
        const boundary=details(tools,'Связи за пределами WorkGraph · '+external.length);
        for(const item of external){
          const text=item.edge.type+' · '+(item.direction==='in'?'из':'к')+' '+(exteriorNodes.get(item.outside)?.title||item.outside);
          button(boundary,text,()=>readOnly?onOpen?.(item.outside):open(selected,{kind:'focus',id:item.outside}));
          if(!readOnly)button(boundary,'Показать внешнюю R/A здесь · '+item.outside,()=>change(()=>{
            const outside=exteriorNodes.get(item.outside);
            if(!outside||!['requirement','action'].includes(outside.kind))return;
            const anchor=positions[item.inside]||{x:30,y:30},id=idFactory();
            occurrences[id]={entityId:item.outside,x:anchor.x+235,y:anchor.y+35,parentId:item.inside,
              viaEdgeId:item.edge.id,...(item.direction==='in'?{reverse:true}:{})};
          }));
        }
      }
      if(!readOnly&&snapshot.graph.coreModel!=='rdg-decision-v1'){
        const controls=details(tools,'Визуальные повторы R/A');
        controls.appendChild(el('p','Повторяются только изображения. Identity, связи, история и Plan общие.'));
        if(picture.invalid.length)button(controls,'Убрать недействительные визуальные ссылки',()=>change(()=>{
          const removal=new Set(picture.invalid.map(row=>row.id));let changed=true;
          while(changed){changed=false;for(const [id,o] of Object.entries(occurrences))
            if(o.parentId&&removal.has(o.parentId)&&!removal.has(id)){removal.add(id);changed=true;}}
          for(const id of removal)delete occurrences[id];
        }));
        const choices=picture.nodes.filter(n=>['action','requirement'].includes(n.node.kind))
          .map(n=>[n.id,(n.alias?'⧉ ':'')+n.node.title+' · '+n.id]);
        if(choices.length){
          const pick=select(controls,'Блок или визуальное вхождение',choices);
          button(controls,'Повторить только блок',()=>change(()=>{
            const src=picture.nodes.find(n=>n.id===pick.value),pos=visualPosition(src.id);
            const id=idFactory();occurrences[id]={entityId:src.entityId,x:pos.x+245,y:pos.y+45};
          }));
          for(const [label,depth] of [['Повторить ветвь · 1 уровень',1],['Повторить ветвь · 2 уровня',2],
            ['Раскрыть здесь следующий уровень',0]]){
            button(controls,label,()=>change(()=>{
              const result=projection.addBranch(allEntities,allEdges,positions,occurrences,pick.value,depth||1,idFactory,{duplicateRoot:depth!==0});
              Object.assign(occurrences,result.occurrences);
            }));
          }
          const removeButton=button(controls,'Убрать только это изображение',()=>change(()=>{
            if(!Object.hasOwn(occurrences,pick.value))throw Error('Основное изображение нельзя убрать');
            const removal=new Set([pick.value]);let changed=true;
            while(changed){changed=false;for(const [id,o] of Object.entries(occurrences))
              if(o.parentId&&removal.has(o.parentId)&&!removal.has(id)){removal.add(id);changed=true;}}
            for(const id of removal)delete occurrences[id];
          }),!Object.hasOwn(occurrences,pick.value));
          pick.onchange=()=>{removeButton.disabled=!Object.hasOwn(occurrences,pick.value);};
          button(controls,'Показать Context/Canon и сведения здесь',()=>change(()=>{
            const result=projection.addBranch(allEntities,allEdges,positions,occurrences,
              pick.value,1,idFactory,{duplicateRoot:false,includeCompanions:true,onlyCompanions:true});
            Object.assign(occurrences,result.occurrences);
          }));
          button(controls,'Свернуть визуальное продолжение здесь',()=>change(()=>{
            const removal=new Set();let progress=true;
            while(progress){progress=false;for(const [id,o] of Object.entries(occurrences))
              if(o.parentId&&(o.parentId===pick.value||removal.has(o.parentId))&&!removal.has(id)){
                removal.add(id);progress=true;
              }}
            for(const id of removal)delete occurrences[id];
          }));
          button(controls,'Разместить общие блоки возле остальных входящих R/A',()=>change(()=>{
            const inbound=new Map();
            for(const e of snapshot.view.edges.filter(e=>['DRIVES','INTRODUCES','DERIVES'].includes(e.type))){
              const list=inbound.get(e.to)||[];list.push(e);inbound.set(e.to,list);
            }
            for(const list of inbound.values())if(list.length>1){
              for(const e of list.slice(1)){
                if(Object.values(occurrences).some(o=>o.viaEdgeId===e.id))continue;
                const parent=positions[e.from];if(!parent)continue;
                const id=idFactory();occurrences[id]={entityId:e.to,x:parent.x+235,y:parent.y+15,parentId:e.from,viaEdgeId:e.id};
              }
            }
          }));
        }
      }
      if(!readOnly){
        button(tools,'Сохранить раскладку',async()=>{
          const request=await schema('layout_edit');
          request.commands=[{type:'set_positions',graphKey:key,positions},{type:'set_occurrences',graphKey:key,occurrences}];
          await prepare(request);
        });
        button(tools,'Отменить изменения раскладки',async()=>{draft=null;render();});
      }
    }
    function renderDetached(parent){
      const box=details(parent,'Отрезанные графы · '+view.detached.length);
      box.appendChild(el('p','Эти блоки принадлежат этому Graph. Выбор и необходимость проверки сохранены.'));
      for(const component of view.detached){const card=el('div',null,'rp-card');box.appendChild(card);
        card.appendChild(el('p',component.reviewIds.length?'Нужна проверка':'Отрезанный компонент',component.reviewIds.length?'rp-stale':null));
        for(const id of component.memberIds){const n=[...view.graph.nodes,...view.graph.objects].find(n=>n.id===id);button(card,n?.title||id,()=>open(selected,{kind:'focus',id}));}}
    }
    async function historicalGraph(parent,pin,spec={kind:'graph'}){
      const snapshot=await call({method:'source_snapshot',packageId:selected,pin,view:spec});
      const box=details(parent,'Сохранённый Graph · версия '+pin.graphRevision);box.open=true;
      box.appendChild(el('p',snapshot.graph.title+' · только чтение'));
      draw(box,snapshot,{readOnly:true,onOpen:id=>historicalGraph(box,pin,{kind:'focus',id})});
    }
    function renderReferences(parent){
      const box=details(parent,'Внешние зависимости и ссылки · '+view.external.states.length);
      for(const state of view.external.states){const card=el('div',null,'rp-card');box.appendChild(card);
        card.appendChild(el('p',state.relation.type+' · '+state.direction+' · '+state.target.nodeId));
        card.appendChild(el('p',state.resolved.status+(state.reviewRequired?' · нужна проверка':''),state.reviewRequired?'rp-stale':null));
        button(card,'Открыть исходный Graph',()=>open(state.target.packageId,{kind:'focus',id:state.target.nodeId}));
        button(card,'Открыть сохранённый Graph',()=>historicalGraph(card,Object.fromEntries(['packageId','identitySpace','graphRevision','sha256'].map(k=>[k,state.target[k]]))));
        button(card,'Прочитать сохранённую ссылку',async()=>json(card,await call({method:'resolve',packageId:selected,reference:state.target})));
        button(card,'Принять текущую версию ссылки',async()=>{
          const source=await call({method:'read',packageId:state.target.packageId});
          const n=[...source.graph.nodes,...source.graph.objects].find(n=>n.id===state.target.nodeId);if(!n)throw Error('В текущем исходнике этого блока нет. Выберите новую связь или удалите прежнюю.');
          const request=await schema('external_edit');request.referenceId=state.referenceId;
          request.target=source.references[n.id];
          request.note='Проверена текущая версия внешнего блока';await prepare(request);
        });
        const alternatives=select(card,'Переназначить на Graph',(catalog?.packages||[]).filter(r=>r.packageId).map(r=>[r.packageId,r.title||r.path]),state.target.packageId);
        const endpoint=field(card,'ID блока в выбранном Graph',state.target.nodeId),reason=field(card,'Основание изменения ссылки');
        button(card,'Проверить новую связь',async()=>{
          const source=await call({method:'read',packageId:alternatives.value});
          if(!source.references[endpoint.value])throw Error('В выбранном Graph нет этого блока.');
          const request=await schema('external_edit');request.referenceId=state.referenceId;request.target=source.references[endpoint.value];request.note=reason.value;await prepare(request);
        });
        button(card,'Убрать внешнюю связь',async()=>{const request=await schema('external_edit');request.referenceId=state.referenceId;delete request.target;request.remove=true;request.note=reason.value;await prepare(request);});
      }
    }
    function renderOperations(parent,work){
      if(view.graph.coreModel==='rdg-decision-v1')return renderDecisionOperations(parent,work);
      const box=details(parent,'Изменить Graph');const entities=[...view.graph.nodes,...view.graph.objects];
      const focusId=focus.kind==='focus'?focus.id:view.graph.rootRequirementId||view.graph.fragmentFocus?.id;
      const node=entities.find(n=>n.id===focusId),noteInput=field(box,'Основание изменения','','textarea');
      const kind=select(box,'Новый блок',[['action','Action'],['requirement','Requirement'],['context','Context'],['canon','Канон'],['info','Информация']]);
      const title=field(box,'Название'),description=field(box,'Описание','','textarea'),scope=field(box,'Область R');
      const cosmetic=node?field(box,'Косметическая правка: не требовать пересмотра у L1/L2-подписчиков из-за изменения определения.','','checkbox'):null;
      const comment=field(box,'Комментарий канона',node?.kind==='canon'?node.comment||'':'','textarea');
      const migrate=node?.kind==='canon'&&node.evaluationMode!=='comment-only-v1'?field(box,'Преобразовать выбранный канон в свободный комментарий'):null;
      if(migrate){migrate.type='checkbox';box.appendChild(el('p','Прежние условия сохранятся в истории; изменение будет показано перед записью.'));}
      button(box,'Добавить блок',async()=>{
        const request=await schema(work?'core':'paper_edit',focusId,{command:'add'});const id=(globalThis.crypto?.randomUUID?.()||String(Date.now())+Math.random()).replaceAll('.','');
        const entity={id,kind:kind.value,title:title.value,description:description.value};
        if(kind.value==='requirement')entity.scope=scope.value;
        if(kind.value==='canon')Object.assign(entity,{evaluationMode:'comment-only-v1',comment:comment.value,arguments:[]});
        request.data={entity,workGraphId:view.graph.workGraphs.find(w=>w.memberIds.includes(focusId))?.id||view.graph.workGraphs[0]?.id};request.note=noteInput.value;await prepare(request);
      });
      if(node){button(box,'Изменить выбранный блок',async()=>{const request=await schema(work?'core':'paper_edit',node.id,{command:'edit'});
        request.data={nodeId:node.id,changes:{title:title.value||node.title,description:description.value,
          ...(node.kind==='canon'&&(node.evaluationMode==='comment-only-v1'||migrate?.checked)?{comment:comment.value}:{}),
          ...(migrate?.checked?{evaluationMode:'comment-only-v1',arguments:[]}:{})},
          ...(migrate?.checked?{legacyCanonMigrationAcknowledged:true}:{}),
           ...(cosmetic?.checked?{cosmetic:true}:{})};
        request.note=noteInput.value;await prepare(request);});
        if(work){for(const [command,label] of [['select','Выбрать Action'],['review','Подтвердить пересмотр']])button(box,label,async()=>{const request=await schema('core',node.id,{command});request.note=noteInput.value;await prepare(request);},command==='select'&&node.kind!=='action');}
        if(work)button(box,'Убрать блок из Graph',async()=>{const request=await schema('delete',node.id);request.note=noteInput.value;await prepare(request);});}
      const from=select(box,'От',entities.map(n=>[n.id,n.kind+' · '+n.title]));
      const relation=select(box,'Связь',['DRIVES','DERIVES','INTRODUCES','RELATES_R','CONTEXT_FOR','CANON_FOR','INFO_FOR','DEPENDS_ON'].map(x=>[x,x]));
      const to=select(box,'К',entities.map(n=>[n.id,n.kind+' · '+n.title]));
      button(box,'Добавить связь',async()=>{const request=await schema(work?'core':'paper_edit',focusId,{command:'link'});request.data={edge:{id:globalThis.crypto.randomUUID(),type:relation.value,from:from.value,to:to.value,...(relation.value==='INTRODUCES'?{origin:{role:'method_correctness'}}:{})}};request.note=noteInput.value;await prepare(request);});
      if(work){
        const native=details(parent,'Нативные зависимости L1/L2');
        const dependencySources=entities.filter(n=>['requirement','action','context','info'].includes(n.kind));
        const dependencyTargets=entities.filter(n=>['requirement','action','context'].includes(n.kind));
        const dependencySource=select(native,'Источник',dependencySources.map(n=>[n.id,n.kind+' · '+n.title]),focusId);
        const dependencyTarget=select(native,'Зависимый блок',dependencyTargets.map(n=>[n.id,n.kind+' · '+n.title]),focusId);
        const dependencyLevel=select(native,'Уровень',[['L1','L1 · собственное определение'],['L2','L2 · прямой семантический scope']],'L1');
        const dependencyNote=field(native,'Основание зависимости','','textarea');
        button(native,'Добавить L1/L2 зависимость',async()=>{const request=await schema('dependency_add',focusId);
          request.sourceId=dependencySource.value;request.dependentId=dependencyTarget.value;
          request.dependencyLevel=dependencyLevel.value;request.note=dependencyNote.value;await prepare(request);});
        for(const edge of view.graph.edges.filter(e=>!e.archived&&e.type==='DEPENDS_ON'&&e.dependencyLevel)){
          const row=el('div',null,'rp-card');native.appendChild(row);
          row.appendChild(el('p',edge.dependencyLevel+' · '+edge.from+' → '+edge.to));
          const removeNote=field(row,'Причина снятия','','textarea');
          button(row,'Снять зависимость',async()=>{const request=await schema('dependency_remove',focusId);
            request.edgeId=edge.id;request.disposition=removeNote.value;request.note=removeNote.value;await prepare(request);});
        }
        const lockNode=entities.find(n=>n.id===focusId);
        if(lockNode){
          const lockBox=details(parent,'Замок object+operation');
          const lockOperation=select(lockBox,'Операция',[['edit','Изменение определения'],['link','Изменение связи'],['unlink','Снятие связи'],['select','Выбор Action'],['withdraw','Отказ от Action'],['complete','Подтверждение результата'],['dependency_add','Создание зависимости'],['dependency_remove','Снятие зависимости']],'edit');
          const lockMode=select(lockBox,'Режим',[['warning','Warning · только сообщение'],['hard','Hard · требует principal']],'hard');
          const lockPrincipals=field(lockBox,'Разрешённые principals, через запятую');
          const lockMessage=field(lockBox,'Сообщение замка','','textarea');
          const authorityPrincipal=transport.approval?{value:''}:field(lockBox,'Principal текущего user path');
          if(transport.approval)lockBox.appendChild(el('p','Исполнитель будет установлен по зарегистрированному ключу при подтверждении.'));
          button(lockBox,'Установить замок',async()=>{const request=await schema('lock_set',focusId);
            request.nodeId=lockNode.id;request.operation=lockOperation.value;request.mode=lockMode.value;
            request.principals=lockPrincipals.value.split(',').map(x=>x.trim()).filter(Boolean);
            request.message=lockMessage.value;request.authorityPrincipal=authorityPrincipal.value;
            request.note=lockMessage.value;await prepare(request);});
          for(const [operation,spec] of Object.entries(lockNode.locks||{})){
            const row=el('div',null,'rp-card');lockBox.appendChild(row);
            row.appendChild(el('p',operation+' · '+spec.mode+' · '+spec.message));
            const removeDisposition=field(row,'Причина снятия','','textarea');
            button(row,'Снять замок',async()=>{const request=await schema('lock_remove',focusId);
              request.nodeId=lockNode.id;request.operation=operation;
              request.disposition=removeDisposition.value;request.authorityPrincipal=authorityPrincipal.value;
              request.note=removeDisposition.value;await prepare(request);});
          }
        }
      }
      const transfer=details(parent,'Шаблон, копирование и вставка');
      const sources=select(transfer,'Источник',(catalog?.packages||[]).filter(r=>r.packageId).map(r=>[r.packageId,(names[r.role]||'')+' · '+(r.title||r.path)]),selected);
      const path=field(transfer,'Папка новой копии'),reason=field(transfer,'Основание');
      transfer.appendChild(el('p','Если папка не указана, копия попадёт в папку даты Asia/Bangkok с уникальным именем.'));
      const moved=field(transfer,'Новое расположение этого пакета');button(transfer,'Проверить перемещение пакета',async()=>{const request=await schema('move');request.path=moved.value;request.note=reason.value;await prepare(request);});
      button(transfer,focus.kind==='focus'?'Скопировать этот фокус':'Скопировать весь Graph',async()=>{const request=await schema('copy');if(path.value.trim())request.path=path.value;request.note=reason.value;request.focus=focus.kind==='focus'?{kind:node.kind,id:node.id}:{kind:'graph'};await prepare(request);},focus.kind==='focus'&&!['action','requirement','canon'].includes(node?.kind));
      if(work){button(transfer,'Вставить копию источника целиком',async()=>{const request=await schema('insert_copy',focusId,{sourcePackageId:sources.value});request.note=reason.value;await prepare(request);});
        const mode=select(transfer,'Применить весь шаблон',[['ADD_ROOT','Добавить корень'],['REPLACE_R','Заменить выбранную R']]);
        button(transfer,'Проверить применение ready',async()=>{const request=await schema('apply_ready',focusId,{sourcePackageId:sources.value});request.mode=mode.value;if(mode.value==='REPLACE_R')request.targetRequirementId=focusId;request.note=reason.value;await prepare(request);});}
      const advanced=details(parent,'Дополнительные команды');advanced.appendChild(el('p','Для сложного origin, канонов, evidence и ветвления доступны те же команды, что у Agent.'));
      const command=field(advanced,'Команда (например, output_origin или complete)'),input=field(advanced,'Параметры команды','','textarea');
      button(advanced,'Получить форму команды',async()=>{const value=await schema(work?'core':'paper_edit',focusId,{command:command.value});input.value=JSON.stringify(value,null,2);});
      button(advanced,'Проверить команду',()=>prepare(JSON.parse(input.value)));
    }
    function renderDecisionOperations(parent,work){
      const box=details(parent,'Изменить Graph'),entities=[...view.graph.nodes,...view.graph.objects,...view.graph.externalActions];
      const focusId=focus.kind==='focus'?focus.id:view.graph.rootRequirementId,node=entities.find(n=>n.id===focusId);
      if(node){box.appendChild(el('p',node.description||''));if(node.guidance)box.appendChild(el('p',node.guidance));}
      const noteInput=field(box,'Основание изменения','','textarea');
      const kind=select(box,'Новый блок',[['decision','Decision'],['requirement','Requirement'],['action','Обязательный Graph Action'],['external','Внешний Action']]);
      const title=field(box,'Название'),description=field(box,'Описание','','textarea');
      const scope=field(box,'Область R',node?.scope||view.graph.nodes.find(n=>n.kind==='requirement')?.scope||'');
      button(box,'Добавить блок',async()=>{
        const request=await schema(work?'core':'paper_edit',focusId,{command:'add'}),id=globalThis.crypto.randomUUID();
        const entity={id,kind:kind.value==='external'?'action':kind.value,title:title.value,description:description.value};
        if(entity.kind==='requirement')entity.scope=scope.value;
        if(entity.kind==='action')Object.assign(entity,{actionType:'task',lowLevel:false,targetIds:node?[node.id]:[],groupIds:[]});
        const data={entity,location:kind.value==='external'?'external':'graph'};
        if(data.location==='graph'){
          if(focus.kind==='workGraph')data.workGraphId=focus.id;
          let type=null;
          if(node?.kind==='requirement')type=entity.kind==='decision'?'DRIVES':entity.kind==='requirement'?'DERIVES':'REQUIRES_ACTION';
          if(node?.kind==='decision')type=entity.kind==='requirement'?'INTRODUCES':entity.kind==='action'?'REQUIRES_ACTION':null;
          if(type)data.initialRelations=[{id:globalThis.crypto.randomUUID(),type,from:node.id,to:id}];
        }
        request.data=data;request.note=noteInput.value;await prepare(request);
      });
      if(node){
        button(box,'Переименовать блок',async()=>{
          const request=await schema(work?'core':'paper_edit',node.id,{command:'edit'});
          request.data={nodeId:node.id,changes:{title:title.value||node.title},cosmetic:true};request.note=noteInput.value;await prepare(request);
        });
        if(work){
          button(box,'Подтвердить пересмотр',async()=>{const request=await schema('core',node.id,{command:'review'});request.note=noteInput.value;await prepare(request);});
          if(node.kind==='decision')for(const [command,label] of [['select','Выбрать Decision'],['withdraw','Отказаться от Decision']])
            button(box,label,async()=>{const request=await schema('core',node.id,{command});request.note=noteInput.value;await prepare(request);});
        }
      }
      const advanced=details(box,'Команда API'),command=field(advanced,'Команда'),input=field(advanced,'Параметры команды','','textarea');
      button(advanced,'Получить форму команды',async()=>{input.value=JSON.stringify(await schema(work?'core':'paper_edit',focusId,{command:command.value}),null,2);});
      button(advanced,'Проверить команду',()=>prepare(JSON.parse(input.value)));
    }

    function renderPlan(parent){
      const box=details(parent,'План во времени');if(!view.plan){box.appendChild(el('p','У этого пакета нет Plan.'));button(box,'Добавить план во времени',async()=>prepare(await schema('plan_create')));return;}
      for(const bucket of Object.keys(statuses)){box.appendChild(el('h3',statuses[bucket]));
        for(const item of view.planView.placements.filter(r=>r.bucket===bucket)){const card=el('div',null,'rp-card');box.appendChild(card);
          card.appendChild(el('p',(item.node?.title||item.step.title)+(item.reason?' · '+item.reason:'')));
          button(card,'Открыть блок',()=>open(item.step.ref.packageId,{kind:'focus',id:item.step.ref.nodeId}));
          button(card,'Убрать размещение',async()=>{const request=await schema('unplace');request.stepId=item.step.id;request.note='Убрано размещение';await prepare(request);});}}
      const target=select(box,'Разместить блок',[...view.graph.nodes,...(view.graph.externalActions||[])].map(n=>[n.id,n.kind+' · '+n.title]));
      const at=field(box,'Не раньше','', 'date');button(box,'Проверить размещение',async()=>{const request=await schema('place',target.value);request.at=at.value;request.note='Явное размещение во времени';await prepare(request);});
      if(view.plan.schemaVersion===3){box.appendChild(el('p','Порядок: '+view.plan.mainStepIds.map(id=>view.plan.steps.find(s=>s.id===id)?.title).join(' → ')));return;}
      const branches=details(box,'Порядок, условия и исходы ветвей');json(branches,{sequence:view.planView.sequence,branches:view.planView.branches});
      const plan=field(branches,'Изменение Plan','','textarea');button(branches,'Получить текущую форму',async()=>{plan.value=JSON.stringify(await schema('plan_edit'),null,2);});button(branches,'Проверить изменение',()=>prepare(JSON.parse(plan.value)));
    }
    function renderHistory(parent,value){
      for(const event of value.events){const box=details(parent,(event.inherited?'Унаследовано · ':'')+event.event.type+' · '+(event.event.recordedAt||event.acceptedAt||'время не установлено'));json(box,event);button(box,'Открыть Graph на момент события',()=>historicalGraph(box,event.source));}
      for(const version of value.planVersions){const box=details(parent,'Plan '+version.plan.revision+(version.inherited?' · унаследованная версия':'')+(version.legacy?' · прежний формат':''));json(box,version);}
      if(value.migrationEvidenceGaps?.length)json(parent,{migrationEvidenceGaps:value.migrationEvidenceGaps});
    }
    button(bar,'Обновить каталог',refresh);renderPreview();renderApprovals();renderEmpty();if(startInExplorer)activateDecision();
    return {start:()=>run(()=>startInExplorer?activateDecision().start():refresh()),refresh,open,prepare,commit,refreshApprovals,openApproval,decideApproval,approvalStatus,recoverApproval,registerCredential,get enrollment(){return enrollment;},get approval(){return approvalCurrent;},get view(){return decisionActive?decisionController.view:view;},get session(){return decisionActive?decisionController.session:undefined;},api(message){if(decisionActive)return decisionController.api(message);return call(message);},get busy(){return busy||decisionActive&&!!decisionController?.busy;},get pending(){return decisionActive?decisionController.pending:pending;},get switchBlocked(){return decisionActive?decisionController.switchBlocked:!!pending||!!draft;}};
  }
  return {mount,diffRows};
});
