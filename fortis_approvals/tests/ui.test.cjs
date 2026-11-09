'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const test=require('node:test');

function harness(){
  const elements=new Map(),notifications=[],requests=[],timers=[];
  const state={pending:[],history:[], logged:true, csrf:'known-csrf',permission:'default'};
  class Element{
    constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.hidden=false;this.textContent='';
      this.classList={toggle(){}};this.onclick=null;this.onsubmit=null;}
    replaceChildren(...args){this.children=[...args];}
    append(...args){this.children.push(...args);}
    get childElementCount(){return this.children.length;}
  }
  const document={title:'Fortis Approvals',hidden:false, createElement:tag=>new Element(tag),
    createTextNode:text=>String(text),addEventListener() {},
    getElementById(id){if(!elements.has(id))elements.set(id,new Element(id));return elements.get(id);}};
  class BrowserNotification{
    static get permission(){return state.permission;}
    static async requestPermission(){state.permission='granted';return state.permission;}
    constructor(title,opts){notifications.push({title,opts});}
  }
  const response=value=>({ok:true,json:async()=>value});
  const fetch=async(url,opts={})=>{
    requests.push({url,opts});
    if(url==='/v1/owner/session')return state.logged?response({owner:'owner',csrf:state.csrf}):{
      ok:false,status:403,json:async()=>({error:'OWNER_SESSION_REQUIRED'})};
    if(url==='/v1/owner/pending')return response(state.pending);
    if(url==='/v1/owner/history')return response(state.history);
    if(url==='/v1/owner/decision/session'){
      const body=JSON.parse(opts.body);
      assert.equal(opts.headers['X-Fortis-CSRF'],state.csrf);
      const index=state.pending.findIndex(r=>r.requestId===body.requestId&&r.fingerprint===body.fingerprint);
      assert.notEqual(index,-1);
      const row=state.pending.splice(index,1)[0];const changed={...row,state:body.decision==='approve'?'EXECUTED':'REJECTED'};
      state.history.push(changed);return response(changed);
    }
    throw Error('Unexpected request '+url);
  };
  const context=vm.createContext({document,window:{Notification:BrowserNotification,focus(){}},
    Notification:BrowserNotification,fetch, setInterval:(f,ms)=>timers.push({f,ms}),
    navigator:{credentials:{}},PublicKeyCredential:{},isSecureContext:true,
    confirm:()=>true, Uint8Array,atob,btoa,console,Error,Set});
  const js=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
  new vm.Script(js).runInContext(context);
  const flush=async()=>{for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));};
  return {document,state,elements,notifications,requests,timers,flush};
}
const row=id=>({requestId:id,fingerprint:'a'.repeat(64),state:'PENDING',actor:'agent-1',
  request:{service:'synthetic',operation:'set_ask',target:'R3',reason:'demo'},preview:{before:{value:'old'},after:{value:'new'}},
  requiresStrongProof:false,result:null,failure:null});

test('auto-polls pending even while history tab selected and notifies only new arrivals',async()=>{
  const h=harness();await h.flush();
  assert.equal(h.timers.length,1);assert.equal(h.timers[0].ms,5000);
  assert.equal(h.notifications.length,0);
  await h.elements.get('notifications').onclick();
  assert.equal(h.state.permission,'granted');
  const historyButton=h.elements.get('history-tab');await historyButton.onclick();
  h.state.pending.push(row('request-new'));
  await h.timers[0].f();await h.flush();
  assert.equal(h.notifications.length,1);
  assert.equal(h.notifications[0].title,'Fortis Approvals: новая заявка');
  assert.equal(h.document.title,'(1) Fortis Approvals');
  assert.equal(h.elements.get('pending-count').textContent,' · 1');
  await h.timers[0].f();await h.flush();
  assert.equal(h.notifications.length,1,'no duplicates on every refresh');
  assert.equal(h.requests.filter(r=>r.url==='/v1/owner/pending').length>=3,true);
});

test('candidate G4 ASK preview cannot approve while WRITE disabled, but can reject',async()=>{
  const h=harness();await h.flush();
  h.state.pending.push({...row('g4-readonly'),requiresStrongProof:true,approvalAllowed:false,
    request:{service:'sonarcloud',operation:'accept_issue',target:'ISSUE-1',reason:'review'}});
  await h.timers[0].f();await h.flush();
  h.elements.get('requests').children[0].onclick();
  const buttons=h.elements.get('detail').children.filter(e=>e.tag==='button');
  assert.equal(buttons.length,2);
  assert.equal(buttons[0].textContent,'Подтвердить');
  assert.equal(buttons[0].disabled,true);
  assert.equal(buttons[0].onclick,null);
  assert.equal(buttons[1].textContent,'Отклонить');
  assert.equal(typeof buttons[1].onclick,'function');
  assert.equal(h.requests.some(r=>r.url.includes('/v1/owner/decision')),false);
});

test('ordinary approval uses session+CSRF+exact fingerprint, not WebAuthn prompt',async()=>{
  const h=harness();await h.flush();
  h.state.pending.push(row('request-ordinary'));
  await h.timers[0].f();await h.flush();
  const buttons=h.elements.get('requests').children;
  assert.equal(buttons.length,1);
  buttons[0].onclick();
  const decisionButton=h.elements.get('detail').children.find(e=>e.tag==='button'&&e.textContent==='Подтвердить');
  assert.ok(decisionButton);
  await decisionButton.onclick();await h.flush();
  const decision=h.requests.find(r=>r.url==='/v1/owner/decision/session');
  assert.ok(decision,'session endpoint invoked');
  assert.equal(JSON.parse(decision.opts.body).fingerprint,'a'.repeat(64));
  assert.equal(h.state.pending.length,0);
  assert.equal(h.state.history.length,1);
  assert.equal(h.requests.some(r=>r.url==='/v1/owner/decision/begin'),false);
});
