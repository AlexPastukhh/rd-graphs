'use strict';
const $=id=>document.getElementById(id);
let csrf=null,selected=null,tab='pending',pendingIds=null,pollBusy=false,decisionBusy=false;
const pollingIntervalMs=5000;
function status(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error);}
async function api(path,body=null,secured=false){
 const headers={'Accept':'application/json'};
 if(body!==null){headers['Content-Type']='application/json';if(secured)headers['X-Fortis-CSRF']=csrf;}
 const response=await fetch(path,{method:body===null?'GET':'POST',headers,credentials:'same-origin',cache:'no-store',
  ...(body===null?{}:{body:JSON.stringify(body)})});
 const data=await response.json();if(!response.ok){const error=new Error(data.error||`HTTP ${response.status}`);error.httpStatus=response.status;throw error;}
 return data;
}
const decode=text=>Uint8Array.from(atob(text.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));
const encode=value=>btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
async function ceremony(begin,registration=false){
 if(!isSecureContext||!navigator.credentials)throw Error('WebAuthn требует HTTPS или localhost.');
 const options=begin.options.publicKey;
 let credential;
 if(registration){
  const publicKey=PublicKeyCredential.parseCreationOptionsFromJSON?
    PublicKeyCredential.parseCreationOptionsFromJSON(options):
    {...options,challenge:decode(options.challenge),user:{...options.user,id:decode(options.user.id)},
     excludeCredentials:options.excludeCredentials?.map(v=>({...v,id:decode(v.id)}))};
  credential=await navigator.credentials.create({publicKey});
 }else{
  const publicKey=PublicKeyCredential.parseRequestOptionsFromJSON?
    PublicKeyCredential.parseRequestOptionsFromJSON(options):
    {...options,challenge:decode(options.challenge),allowCredentials:options.allowCredentials?.map(v=>({...v,id:decode(v.id)}))};
  credential=await navigator.credentials.get({publicKey});
 }
 if(!credential)throw Error('Операция отменена.');
 if(credential.toJSON)return credential.toJSON();
 const r=credential.response,standard={id:credential.id,rawId:encode(credential.rawId),type:credential.type,
  clientExtensionResults:credential.getClientExtensionResults()};
 if(registration)return {...standard,response:{clientDataJSON:encode(r.clientDataJSON),
  attestationObject:encode(r.attestationObject),transports:r.getTransports?.()||[]}};
 return {...standard,response:{clientDataJSON:encode(r.clientDataJSON),
  authenticatorData:encode(r.authenticatorData),signature:encode(r.signature),
  userHandle:r.userHandle==null?null:encode(r.userHandle)}};
}
function signedOut(message){
 csrf=null;pendingIds=null;selected=null;document.title='Fortis Approvals';
 $('workspace').hidden=true;$('signin').hidden=false;$('detail').replaceChildren();
 if(message)status(message,true);
}
async function login(){const begin=await api('/v1/login/begin',{});const response=await ceremony(begin);
 const result=await api('/v1/login/finish',{ceremonyId:begin.ceremonyId,response});csrf=result.csrf;
 $('signin').hidden=true;$('registration').hidden=true;$('workspace').hidden=false;status('Вход подтверждён');
 pendingIds=null;await refresh();}
function notifyOnNewPending(rows){
 const next=new Set(rows.map(r=>r.requestId));
 if(pendingIds!==null){
  const added=rows.filter(r=>!pendingIds.has(r.requestId));
  if(added.length){
   status(`Новых заявок: ${added.length}`);
   if('Notification' in window && Notification.permission==='granted'){
    try{const notification=new Notification('Fortis Approvals: новая заявка',
      {body:`Ожидают подтверждения: ${next.size}`,tag:'fortis-pending',renotify:true});
     notification.onclick=()=>{window.focus();notification.close();};}
    catch(_error){/* browser can disable notifications; queue remains visible */}
   }
  }
 }
 pendingIds=next;
 document.title=(next.size?`(${next.size}) `:'')+'Fortis Approvals';
 $('pending-count').textContent=next.size?` · ${next.size}`:'';
}
function render(rows){
 $('requests').replaceChildren();
 for(const row of rows){const btn=document.createElement('button');btn.type='button';btn.dataset.requestId=row.requestId;
  btn.textContent=`${row.request.service} · ${row.request.operation} · ${row.request.target} (${row.state})`;
  btn.onclick=()=>show(row);$('requests').append(btn);}
 if(selected){const matching=rows.find(r=>r.requestId===selected.requestId);
  if(matching && !decisionBusy && (matching.state!==selected.state || matching.fingerprint!==selected.fingerprint))show(matching);
  else if(!matching && !decisionBusy){selected=null;$('detail').replaceChildren();}
 }
 if(!selected && !$('detail').childElementCount){const p=document.createElement('p');p.textContent='Выберите заявку.';$('detail').append(p);}
}
async function refresh(){
 if(!csrf||pollBusy||decisionBusy)return;
 pollBusy=true;
 try{
  // Always check pending, including while the History tab is selected.
  const pending=await api('/v1/owner/pending');
  notifyOnNewPending(pending);
  const rows=tab==='pending'?pending:await api('/v1/owner/history');
  render(rows);
 }catch(err){if(err.httpStatus===403){signedOut('Сессия истекла — войдите снова.');}
  else status('Нет связи с сервисом: '+err.message,true);
 }finally{pollBusy=false;}
}
function line(label,value){const p=document.createElement('p');const b=document.createElement('strong');b.textContent=label+': ';
 p.append(b,document.createTextNode(String(value??'—')));return p;}
function show(row){selected=row;const area=$('detail');area.replaceChildren();
 const h=document.createElement('h2');h.textContent=`${row.request.service} · ${row.request.operation}`;area.append(h,
 line('Состояние',row.state),line('Инициатор',row.actor||'проверенный клиент'),
 line('Объект',row.request.target),line('Причина',row.request.reason),line('ID',row.requestId));
 const label=document.createElement('h3');label.textContent='Точное изменение и состояние';area.append(label);
 const preview=document.createElement('pre');preview.textContent=JSON.stringify({request:row.request,preview:row.preview},null,2);area.append(preview);
 if(row.result){const p=document.createElement('pre');p.textContent='Результат: '+JSON.stringify(row.result,null,2);area.append(p);}
 if(row.failure)area.append(line('Причина остановки',row.failure));
 if(row.state==='PENDING'){
  if(row.approvalAllowed===false)area.append(line('Запись','Для этой операции пока отключена. Можно только отклонить заявку.'));
  else if(row.requiresStrongProof)area.append(line('Проверка','Для этой операции требуется дополнительное подтверждение ключом.'));
  for(const [decision,title] of [['approve','Подтвердить'],['reject','Отклонить']]){
   const btn=document.createElement('button');btn.type='button';btn.textContent=title;
   if(decision==='approve'&&row.approvalAllowed===false){btn.disabled=true;btn.title='Запись для этой операции отключена';}
   else btn.onclick=action(()=>decide(row,decision));
   area.append(btn);
  }
 }
}
async function decide(row,decision){
 if(decisionBusy)return;
 decisionBusy=true;
 try{
  let result;
  if(row.requiresStrongProof){
   const begin=await api('/v1/owner/decision/begin',{requestId:row.requestId,decision},true);
   const response=await ceremony(begin);
   result=await api('/v1/owner/decision/finish',{requestId:row.requestId,decision,
      ceremonyId:begin.ceremonyId,response},true);
  }else{
   result=await api('/v1/owner/decision/session',{
     requestId:row.requestId,fingerprint:row.fingerprint,decision},true);
  }
  selected=null;$('detail').replaceChildren();status(`Результат: ${result.state}`);
 }finally{decisionBusy=false;await refresh();}
}
async function allowNotifications(){
 if(!('Notification' in window)){status('Этот браузер не поддерживает уведомления.',true);return;}
 if(Notification.permission==='denied'){status('Уведомления заблокированы в настройках браузера.',true);return;}
 const permission=await Notification.requestPermission();
 status(permission==='granted'?'Уведомления включены для открытой вкладки.':'Уведомления не разрешены.',permission!=='granted');
}
function action(fn){return async e=>{e?.preventDefault?.();try{await fn(e);}catch(err){
 if(err.httpStatus===403 && err.message==='OWNER_SESSION_REQUIRED'){signedOut('Сессия истекла — войдите снова.');}
 else status(err.message,true);
}};}
$('login').onclick=action(login);
$('show-enroll').onclick=()=>{$('registration').hidden=!$('registration').hidden;};
$('enroll').onsubmit=action(async()=>{const begin=await api('/v1/enroll/begin',{invitation:$('invitation').value});
 const response=await ceremony(begin,true);await api('/v1/enroll/finish',{ceremonyId:begin.ceremonyId,response});
 $('invitation').value='';$('registration').hidden=true;status('Ключ зарегистрирован. Теперь войдите.');});
$('pending-tab').onclick=action(async()=>{tab='pending';selected=null;$('detail').replaceChildren();await refresh();});
$('history-tab').onclick=action(async()=>{tab='history';selected=null;$('detail').replaceChildren();await refresh();});
$('refresh').onclick=action(refresh);
$('notifications').onclick=action(allowNotifications);
setInterval(()=>{if(csrf)refresh();},pollingIntervalMs);
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&csrf)refresh();});
api('/v1/owner/session').then(async data=>{csrf=data.csrf;$('signin').hidden=true;$('workspace').hidden=false;await refresh();}).catch(()=>{});
