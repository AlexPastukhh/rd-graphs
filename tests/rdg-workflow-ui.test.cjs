'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const UI=require('../tools/rdg-workflow-ui.js');
const {simulate}=require('./viewer-test-helper.cjs');
function doc(){
  const createElement=tag=>{
    let own='';const classes=new Set(),attrs={};
    const n={tag,children:[],value:'',disabled:false,hidden:false,
      appendChild(x){n.children.push(x);return x;},replaceChildren(...xs){n.children=xs;},
      setAttribute(k,v){attrs[k]=String(v);},getAttribute:k=>attrs[k]??null,classList:{contains:x=>classes.has(x),add:x=>classes.add(x),remove:x=>classes.delete(x),toggle:(x,on)=>on?classes.add(x):classes.delete(x)},
      get textContent(){return own+n.children.map(x=>x.textContent).join('');},
      set textContent(x){own=String(x);n.children=[];}};
    if(['select','textarea'].includes(tag))Object.defineProperty(n,'type',{get:()=>tag==='select'?'select-one':'textarea'});
    return n;
  };
  return {createElement};
}
function minimal(){
 const graph={identitySpace:'test',revision:1,nodes:[{id:'R0',kind:'requirement',title:'Root',status:'active'}],edges:[],events:[]};
 return {title:'Plan',graphFile:'workspaces/test/graph.json',planFile:'plans/test/plan.json',
   permissions:['graph.write','graph.read','plan.read','plan.edit'],future:[],history:[],unresolved:[],
   sources:{graphs:{'workspaces/test/graph.json':graph},completion:{},
     plan:{revision:1,steps:[],timeConstraints:[],sequence:[]}}};
}
test('grant panel stays hidden without explicit admin and never exposes a secret in state',async()=>{
 const d=doc(),snapshot=minimal(),container=d.createElement('div');let requests=0;
 const ui=UI.mount(container,{read:async()=>snapshot,admin:async()=>{requests++;return {revision:1,grants:[]};}},{document:d});
 await ui.refresh();
 const panel=container.children.find(n=>n.tag==='details'&&n.classList.contains('wf-grants'));
 assert(panel);assert.equal(panel.hidden,true);assert.equal(requests,0);
 snapshot.grantAdminAvailable=true;await ui.refresh();assert.equal(panel.hidden,false);
 assert.equal(requests,0,'admin must not auto-issue/list a grant');
});
test('admin issue from Viewer uses existing authorized transport and never puts bearer in graph state',async()=>{
 const d=doc(),snapshot=minimal(),container=d.createElement('div');snapshot.grantAdminAvailable=true;
 let revision=1;const grants=[],requests=[];
 const transport={read:async()=>snapshot,admin:async r=>{
   requests.push(structuredClone(r));
   if(r.operation==='list')return {revision,grants:structuredClone(grants)};
   assert.equal(r.expectedRevision,revision++);
   if(r.operation==='issue'){
     const item={id:'g_test',label:r.grant.label,permissions:r.grant.permissions,scopes:r.grant.scopes,active:true,owner:false};
     grants.push(item);return {id:item.id,token:'rdg_'+'s'.repeat(40),replayed:false};
   }
   if(r.operation==='amend'){
     const item=grants.find(g=>g.id===r.id);Object.assign(item,r.grant);
     return {id:r.id,active:item.active,replayed:false};
   }
   if(r.operation==='revoke'){
     grants.find(g=>g.id===r.id).active=false;return {id:r.id,active:false,replayed:false};
   }
   throw Error('unexpected');
 }};
 const ui=UI.mount(container,transport,{document:d});await ui.refresh();
 const panel=container.children.find(n=>n.classList.contains('wf-grants'));
 const controls=panel.children.filter(n=>n.tag==='button');
 const button=label=>controls.find(n=>n.textContent===label);
 await button('Просмотреть права').onclick();
 const field=label=>panel.children.find(n=>n.tag==='label'&&n.textContent.startsWith(label)).children[0];
 field('Метка полномочия').value='Test read';
 field('Разрешения').value='graph.read';field('Области доступа').value='workspaces/test/graph.json';
 button('Выдать токен').onclick();
 await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(requests.find(r=>r.operation==='issue').grant.permissions[0],'graph.read');
 assert(panel.textContent.includes('rdg_'+'s'.repeat(40)));
 assert(!JSON.stringify(ui.view).includes('rdg_'+'s'.repeat(40)));
 button('Скрыть показанный токен').onclick();
 assert(!panel.textContent.includes('rdg_'+'s'.repeat(40)));
 assert.equal(field('Метка полномочия').value,'Test read','list must populate selected grant');
 field('Метка полномочия').value='Updated grant';
 button('Изменить выбранный grant').onclick();await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(grants[0].label,'Updated grant');
 button('Отозвать выбранный grant').onclick();await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(grants[0].active,false);assert(!panel.textContent.includes('rdg_'+'s'.repeat(40)), 'next mutation clears displayed token');
});
test('confirmed grant issue followed by failed list remains accepted and cannot issue twice',async()=>{
 const d=doc(),container=d.createElement('div'),snapshot=minimal();snapshot.grantAdminAvailable=true;
 let issueCount=0,listCount=0;
 const admin=async req=>{
  if(req.operation==='list'){
   if(++listCount===2)throw Error('transient refresh failure');
   return {revision:issueCount+1,grants:[]};
  }
  if(req.operation==='issue'){
   ++issueCount;
   assert.equal(issueCount,1,'duplicate grant must not be issued');
   return {id:'g1',token:'rdg_'+'v'.repeat(40),replayed:false};
  }
  throw Error('unexpected operation '+req.operation);
 };
 const ui=UI.mount(container,{read:async()=>snapshot,admin},{document:d});await ui.refresh();
 const panel=container.children.find(n=>n.classList.contains('wf-grants'));
 const button=label=>panel.children.find(n=>n.tag==='button'&&n.textContent===label);
 await button('Просмотреть права').onclick();
 const field=label=>panel.children.find(n=>n.tag==='label'&&n.textContent.startsWith(label)).children[0];
 field('Метка полномочия').value='one';field('Разрешения').value='graph.read';
 field('Области доступа').value='workspaces/demo/graph.json';
 button('Выдать токен').onclick();await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(issueCount,1);
 assert.match(panel.textContent,/Изменение полномочий принято/);
 assert.match(panel.textContent,/Не удалось обновить список прав/);
 assert(!panel.textContent.includes('Исход запроса неизвестен'));
 assert.equal(button('Повторить тот же запрос').hidden,true);
 assert.equal(button('Выдать токен').disabled,true,'require fresh revision');
 assert(panel.textContent.includes('rdg_'+'v'.repeat(40)),'successful issue token remains visible');
 await button('Просмотреть права').onclick();
 assert.equal(button('Выдать токен').disabled,false);
 assert.equal(issueCount,1);
});
test('uncertain grant mutation preserves exact request for retry without a second issue',async()=>{
 const d=doc(),container=d.createElement('div'),snapshot=minimal();snapshot.grantAdminAvailable=true;
 const requests=[];let accepted=0;
 const admin=async req=>{
  if(req.operation==='list')return {revision:accepted+1,grants:[]};
  requests.push(structuredClone(req));
  if(requests.length===1)throw Error('synthetic lost reply');
  ++accepted;return {id:'g2',token:'rdg_'+'q'.repeat(40),replayed:true};
 };
 const ui=UI.mount(container,{read:async()=>snapshot,admin},{document:d});await ui.refresh();
 const panel=container.children.find(n=>n.classList.contains('wf-grants'));
 const button=label=>panel.children.find(n=>n.tag==='button'&&n.textContent===label);
 await button('Просмотреть права').onclick();
 const field=label=>panel.children.find(n=>n.tag==='label'&&n.textContent.startsWith(label)).children[0];
 field('Метка полномочия').value='retry';field('Разрешения').value='graph.read';
 field('Области доступа').value='workspaces/demo/graph.json';
 button('Выдать токен').onclick();await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(button('Повторить тот же запрос').hidden,false);
 assert.equal(button('Выдать токен').disabled,true);
 button('Повторить тот же запрос').onclick();await new Promise(resolve=>setTimeout(resolve,0));
 assert.deepEqual(requests[0],requests[1]);
 assert.equal(accepted,1);
 assert.match(panel.textContent,/Повтор подтверждён/);
 assert.equal(button('Повторить тот же запрос').hidden,true);
});
test('lost response retains exact request, blocks a new action and permits safe retry',async()=>{
 const d=doc(),container=d.createElement('div'),snapshot=minimal(),requests=[];
 let count=0;
 const ui=UI.mount(container,{read:async()=>snapshot,write:async r=>{
   requests.push(structuredClone(r));if(count++===0)throw Error('connection lost');
   return {saved:true,replayed:true,view:snapshot};
 }},{document:d});
 await ui.refresh();ui.fields.title.value='New';ui.fields.recommended.value='Case';ui.fields.note.value='Manual change';
 await ui.buttons.add.onclick();assert(ui.pending);assert.equal(ui.view.history.length,0);
 const first=structuredClone(ui.pending);await ui.run('edit_title');assert.equal(requests.length,1);
 await ui.buttons.retry.onclick();assert.equal(ui.pending,null);assert.deepEqual(requests,[first,first]);
 assert.match(ui.status,/повторного действия нет/);
});
test('known rejection preserves source state and clears uncertain request',async()=>{
 const d=doc(),snapshot=minimal();
 const ui=UI.mount(d.createElement('div'),{read:async()=>snapshot,write:async()=>{
   const e=Error('CAS_MISMATCH');e.definite=true;throw e;
 }},{document:d});
 await ui.refresh();ui.fields.note.value='note';await ui.buttons.title.onclick();
 assert.equal(ui.pending,null);assert.equal(ui.view.sources.graphs[ui.view.graphFile].revision,1);
 assert.match(ui.status,/отклонена/);
});
test('a render failure after save reports saved, rather than an unknown writer outcome',async()=>{
 const d=doc(),snapshot=minimal();let fail=false;
 const ui=UI.mount(d.createElement('div'),{read:async()=>snapshot,write:async()=>({saved:true,view:snapshot})},
   {document:d,graphContainer:d.createElement('section'),onGraph:async()=>{if(fail)throw Error('render failed');}});
 await ui.refresh();fail=true;ui.fields.note.value='note';await ui.buttons.title.onclick();
 assert.equal(ui.pending,null);assert.match(ui.status,/Запись сохранена/);
 assert.doesNotMatch(ui.status,/Исход запроса не подтверждён/);
});
test('read-only and protected sessions disable writes, source text is rendered as text',async()=>{
 const d=doc(),snapshot=minimal();snapshot.permissions=['graph.read','plan.read'];
 snapshot.sources.graphs[snapshot.graphFile].nodes[0].title='<img src=x onerror=alert(1)>';
 const container=d.createElement('div');
 const ui=UI.mount(container,{read:async()=>snapshot},{document:d});await ui.refresh();
 for(const key of ['add','title','complete','place','unplace'])assert.equal(ui.buttons[key].disabled,true,key);
 assert(container.textContent.includes('<img src=x onerror=alert(1)>'));
 snapshot.permissions=['graph.read','graph.write','plan.read','plan.edit'];
 snapshot.sources.graphs[snapshot.graphFile].nodes[0].reconsiderationPolicy={mode:'protected',authorityPrincipal:'owner'};
 await ui.refresh();
 for(const key of ['add','title','complete','qrpe'])assert.equal(ui.buttons[key].disabled,true,key+' protected');
 assert.equal(ui.buttons.place.disabled,false,'placement does not mutate protected graph');
});
test('plan tab opens without requesting files and preserves graph and editor across switches',async()=>{
 const viewer=simulate();let picks=0;viewer.window.showDirectoryPicker=async()=>{picks++;throw Error('unexpected picker');};
 await viewer.flush();assert.equal(viewer.ids['workflow-toggle'].hidden,false);
 await viewer.loadFile(viewer.fixture);const before=viewer.root.querySelectorAll('.node').map(n=>n.getAttribute('data-id'));
 viewer.ids['workflow-toggle'].onclick();
 assert.equal(viewer.ids['workflow-page'].hidden,false);assert.equal(viewer.ids['graph-pane'].hidden,true);
 assert.equal(viewer.ids['workflow-toggle'].getAttribute('aria-selected'),'true');assert.equal(picks,0);
 const panel=viewer.host.rdgWorkflow.attach();assert.equal(panel.hidden,false);
 viewer.ids['graph-tab'].onclick();assert.equal(viewer.ids['workflow-page'].hidden,true);
 assert.equal(viewer.ids['graph-pane'].hidden,false);assert.equal(viewer.ids['graph-tab'].getAttribute('aria-selected'),'true');
 assert.deepEqual(viewer.root.querySelectorAll('.node').map(n=>n.getAttribute('data-id')),before);
 viewer.ids['workflow-toggle'].onclick();assert.equal(panel.hidden,false);assert.equal(picks,0);
});
test('manual controls traverse real HTTP, writers and Viewer: A1 -> withdraw -> A2',
 {skip:!process.env.RDG_WORKFLOW_TEST_URL&&!process.env.RDG_WORKFLOW_TEST_DIR},async()=>{
 const fileDir=process.env.RDG_WORKFLOW_TEST_DIR;
 const fs=require('node:fs/promises'),path=require('node:path');
 const missing=e=>{if(e.code==='ENOENT'){const error=Error('Not found');error.name='NotFoundError';throw error;}throw e;};
 const directory={async getFileHandle(name,options={}){
   assert.match(name,/^[A-Za-z0-9_.-]+$/);const file=path.join(fileDir,name);
   if(!options.create)await fs.stat(file).catch(missing);
   return {async getFile(){return {async text(){return fs.readFile(file,'utf8').catch(missing);}};},
     async createWritable(){let text='';return {async write(x){text=x;},async close(){await fs.writeFile(file,text);}};}};
 },async removeEntry(name){await fs.unlink(path.join(fileDir,name));}};
 const base=new URL(process.env.RDG_WORKFLOW_TEST_URL||'http://127.0.0.1/'),session=base.pathname.split('/').filter(Boolean).at(-1);
 const request=async(path,body)=>{
   const r=await fetch(new URL(path,base),{method:body?'POST':'GET',headers:{
     'X-RDG-Session':session,...(body?{'Content-Type':'application/json','Origin':base.origin}:{})},
     ...(body?{body:JSON.stringify(body)}:{})});
   const x=await r.json();if(!r.ok){const e=Error(x.error);e.definite=true;throw e;}return x;
 };
 const viewer=simulate();await viewer.flush();const d=doc();
 const transport=fileDir?UI.fileTransport(directory,{timeoutMs:30000,pollMs:10}):{read:()=>request('state'),write:r=>request('command',r)};
 const ui=UI.mount(viewer.host.rdgWorkflow.attach(),transport,
   {document:d,graphContainer:d.createElement('section'),onGraph:g=>viewer.host.rdgWorkflow.loadGraph(g)});
 await ui.refresh();assert(ui.view);
 const choose=id=>{ui.fields.target.value=id;ui.fields.target.onchange();};
 const click=async name=>{assert.equal(ui.buttons[name].disabled,false,name+' should be available');
   await ui.buttons[name].onclick();assert.match(ui.status,/Запись сохранена/,ui.status);};
 ui.fields.note.value='User entered synthetic change/result';
 ui.fields.title.value='First action';ui.fields.recommended.value='Applicable';
 await click('add');const a1=ui.fields.target.value;
 assert.equal(ui.buttons.place.disabled,true,'candidate Action cannot be placed before Graph selection');
 await click('select');ui.fields.at.value='2026-10-21';await click('place');
 choose('R0');ui.fields.title.value='Second action';ui.fields.recommended.value='Different applicable method';
 await click('add');const a2=ui.fields.target.value;assert.notEqual(a1,a2);
 assert.equal(ui.buttons.place.disabled,true,'unselected alternative is not executable');
 await click('select');ui.fields.at.value='2026-10-22';await click('place');
 choose('R0');ui.fields.at.value='2026-10-23';await click('place');
 assert.equal(ui.view.future.length,3);
 choose(a1);await click('complete');
 assert.deepEqual(ui.view.future.map(r=>r.nodeId),[a2,'R0'],
   'planning the root Requirement does not complete it when an Action executes');
 await click('withdraw');assert(ui.view.future.some(r=>r.nodeId==='R0'));
 choose(a2);assert(ui.view.future.some(r=>r.nodeId===a2));await click('complete');
 assert.equal(ui.view.future.length,0,'no further active placements in this synthetic completion context');
 const facts=ui.view.history.filter(r=>r.kind==='action_executed'||r.kind==='action_withdrawn');
 assert.deepEqual(facts.map(r=>[r.kind,r.targetId]),[
   ['action_executed',a1],['action_withdrawn',a1],['action_executed',a2]]);
 assert(ui.text.includes('Отозван Action'));assert(ui.text.includes('First action'));
 if(fileDir)assert.deepEqual((await fs.readdir(fileDir)).filter(n=>!n.startsWith('.')),['session.json'],'client removes only its own exchange files');
 const graph=ui.view.sources.graphs[ui.view.graphFile];
 assert.equal(graph.events.filter(e=>e.type==='action_executed'&&e.targetId===a1).length,1);
 // Build a deeper preliminary branch through the actual controls, without selecting its ancestors.
 choose('R0');ui.fields.title.value='Unselected decomposition';ui.fields.recommended.value='Split when useful';ui.fields.actionType.value='decomposition';
 await click('add');const draft=ui.fields.target.value;
 ui.fields.title.value='Deep potential goal';ui.fields.childRole.value='subgoal';await click('requirement');const potential=ui.fields.target.value;
 ui.fields.qrpe.value='Review this potential goal';await click('qrpe');
 ui.fields.title.value='Deep candidate action';ui.fields.recommended.value='Deep applicable case';ui.fields.actionType.value='general';await click('add');
 const deep=ui.fields.target.value;ui.fields.recommended.value='Updated deep canon';await click('canon');
 const finalGraph=ui.view.sources.graphs[ui.view.graphFile];
 assert.equal(finalGraph.nodes.find(n=>n.id===draft).status,'candidate');
 assert.equal(finalGraph.nodes.find(n=>n.id===potential).status,'potential');
 assert.equal(finalGraph.nodes.find(n=>n.id===deep).status,'candidate');
 assert.equal(finalGraph.nodes.find(n=>n.id===potential).qrpe[0].text,'Review this potential goal');
 assert(viewer.root.querySelectorAll('.node').length>0,'the same source is rendered by Viewer');
 assert.equal(ui.pending,null);
});

test('generated workflow controller matches the shared source exactly',()=>{
 const fs=require('node:fs'),path=require('node:path');const text=fs.readFileSync(path.join(__dirname,'../tools/rd-graph-viewer.user.js'),'utf8');
 const begin='// BEGIN GENERATED RDG WORKFLOW UI\n',end='// END GENERATED RDG WORKFLOW UI\n';
 assert.equal(text.slice(text.indexOf(begin)+begin.length,text.indexOf(end)),fs.readFileSync(path.join(__dirname,'../tools/rdg-workflow-ui.js'),'utf8'));
});

test('cross-owner Helper: manual action under projection root completes the owning parent',
 {skip:!process.env.RDG_CROSS_TEST_URL},async()=>{
 const base=new URL(process.env.RDG_CROSS_TEST_URL),session=base.pathname.split('/').filter(Boolean).at(-1);
 const request=async(path,body)=>{
   const r=await fetch(new URL(path,base),{method:body?'POST':'GET',headers:{
     'X-RDG-Session':session,...(body?{'Content-Type':'application/json','Origin':base.origin}:{})},
     ...(body?{body:JSON.stringify(body)}:{})});
   const x=await r.json();if(!r.ok){const e=Error(x.error);e.definite=x.definite!==false;throw e;}return x;
 };
 const d=doc(),viewer=simulate();await viewer.flush();
 const ui=UI.mount(viewer.host.rdgWorkflow.attach(),{read:()=>request('state'),write:r=>request('command',r)},
   {document:d,graphContainer:d.createElement('section'),onGraph:g=>viewer.host.rdgWorkflow.loadGraph(g)});
 await ui.refresh();assert(ui.view,ui.status);assert.equal(ui.view.continuationRootId,'R1');
 assert.equal(ui.fields.target.value,'R1');assert.equal(ui.buttons.add.disabled,false);
 ui.fields.title.value='Manual child action';ui.fields.recommended.value='Suitable method';ui.fields.note.value='Manual cross-owner proof';
 await ui.buttons.add.onclick();assert.match(ui.status,/Запись сохранена/,ui.status);
 const action=ui.fields.target.value;
 ui.fields.target.value='R1';ui.fields.target.onchange();assert.equal(ui.buttons.place.disabled,false);
 ui.fields.at.value='2026-10-21';await ui.buttons.place.onclick();assert.match(ui.status,/Запись сохранена/,ui.status);
 const row=ui.view.future.find(r=>r.nodeId==='R1');assert(row);assert.notEqual(row.ownerRef.graphFile,row.graphRef.graphFile);
 ui.fields.target.value=action;ui.fields.target.onchange();await ui.buttons.select.onclick();assert.match(ui.status,/Запись сохранена/,ui.status);
 await ui.buttons.complete.onclick();assert.match(ui.status,/Запись сохранена/,ui.status);
 assert.equal(ui.view.future.length,0);
 const parent=ui.view.sources.graphs[row.ownerRef.graphFile];
 assert(parent.events.some(e=>e.type==='requirement_achieved'&&e.targetId==='R0'));
 assert(ui.view.history.some(r=>r.kind==='requirement_achieved'&&r.targetId==='R1'));
 assert(viewer.root.querySelectorAll('.node').length>0);
});


test('placement selection reloads shown fields and protects unsupported rules',async()=>{
 const d=doc(),snapshot=minimal(),ref={graphFile:snapshot.graphFile,identitySpace:'test',nodeId:'R0'};
 snapshot.sources.plan.steps=['P1','P2'].map(id=>({id,title:id,kind:'requirement',state:'planned',requirementRef:{...ref}}));
 snapshot.sources.plan.steps.push({id:'OTHER',title:'Other owner',kind:'requirement',requirementRef:{...ref,graphFile:'workspaces/other/graph.json'}});
 snapshot.sources.plan.timeConstraints=[
   {stepId:'P1',type:'notBefore',at:'2026-10-20',strength:'hard'},
   {stepId:'P1',type:'deadline',at:'2026-10-25',strength:'hard'},
   {stepId:'P2',type:'notBefore',at:'2026-10-23',strength:'soft'}];
 const ui=UI.mount(d.createElement('div'),{read:async()=>snapshot},{document:d});await ui.refresh();
 assert(!ui.fields.placement.children.some(x=>x.value==='OTHER'));
 ui.fields.placement.value='P1';ui.fields.placement.onchange();
 assert.equal(ui.fields.at.value,'2026-10-20');assert(ui.text.includes('Срок до 2026-10-25 [hard]'));
 ui.fields.placement.value='P2';ui.fields.placement.onchange();assert.equal(ui.fields.at.value,'2026-10-23');
 snapshot.sources.plan.timeConstraints[2].at='2026-10-23T10:00:00Z';
 ui.fields.placement.onchange();assert.equal(ui.buttons.place.disabled,true);assert(ui.text.includes('полный API'));
 snapshot.sources.plan.timeConstraints[2].at='2026-10-23';
 snapshot.sources.plan.sequence=[{before:'P1',after:'P2'}];
 ui.fields.placement.onchange();assert.equal(ui.fields.after.value,'P1');
 assert(ui.fields.after.children.some(x=>x.value==='P1'),'another placement of the same entity is a valid predecessor');
 snapshot.sources.plan.sequence.push({before:'OTHER',after:'P2'});
 ui.fields.placement.onchange();assert.equal(ui.buttons.place.disabled,true);
 assert.equal(ui.buttons.unplace.disabled,false,'explicit unplace remains separate from editing');
});

test('manual date and order edits preserve successor, deadline and strength through real writers',
 {skip:!process.env.RDG_PLACEMENT_TEST_URL},async()=>{
 const base=new URL(process.env.RDG_PLACEMENT_TEST_URL),session=base.pathname.split('/').filter(Boolean).at(-1);
 const request=async(path,body)=>{
   const r=await fetch(new URL(path,base),{method:body?'POST':'GET',headers:{
     'X-RDG-Session':session,...(body?{'Content-Type':'application/json','Origin':base.origin}:{})},
     ...(body?{body:JSON.stringify(body)}:{})});
   const value=await r.json();if(!r.ok){const error=Error(value.error);error.definite=true;throw error;}return value;
 };
 const d=doc(),ui=UI.mount(d.createElement('div'),{read:()=>request('state'),write:r=>request('command',r)},{document:d});
 await ui.refresh();
 const choose=id=>{ui.fields.target.value=id;ui.fields.target.onchange();};
 const save=async()=>{assert.equal(ui.buttons.place.disabled,false);await ui.buttons.place.onclick();assert.match(ui.status,/Запись сохранена/,ui.status);};
 const plan=()=>ui.view.sources.plan;
 const deadline=structuredClone(plan().timeConstraints.find(r=>r.type==='deadline'));
 const order=structuredClone(plan().sequence);
 choose('A1');assert.equal(ui.fields.at.value,'2026-10-20');ui.fields.at.value='2026-10-21';await save();
 assert.deepEqual(plan().sequence,order);assert.deepEqual(plan().timeConstraints.find(r=>r.type==='deadline'),deadline);
 assert.equal(plan().timeConstraints.find(r=>r.stepId==='S-A1'&&r.type==='notBefore').strength,'hard');
 choose('A2');assert.equal(ui.fields.after.value,'S-A1');
 ui.fields.after.value='S-A3';await save();
 assert.deepEqual(plan().sequence,[{before:'S-A3',after:'S-A2',minDelayDays:2}]);
 ui.fields.after.value='';ui.fields.at.value='2026-10-23';await save();assert.deepEqual(plan().sequence,[]);
 choose('A1');ui.fields.at.value='';await save();
 assert.deepEqual(plan().timeConstraints.filter(r=>r.stepId==='S-A1'),[deadline]);
 assert.equal(ui.pending,null);
});


function sessionDirectory(descriptor,config={}){
 const files=new Map(descriptor===undefined?[]:[['session.json',JSON.stringify(descriptor)]]);
 const directory={async getFileHandle(name,options={}){
   if(options.create&&config.denied){const e=Error('denied');e.name='NotAllowedError';throw e;}
   if(!options.create&&!files.has(name)){const e=Error('missing');e.name='NotFoundError';throw e;}
   return {async getFile(){return {text:async()=>files.get(name)};},async createWritable(){let text;
     return {async write(value){text=value;},async close(){files.set(name,text);}};}};
 },async removeEntry(name){files.delete(name);}};
 return {directory,files};
}
const liveSession={schemaVersion:1,kind:'rdg-local-manual-session',active:true,session:'synthetic-test-session'};
test('closed Helper descriptor without a token reports ended session and queues no request',async()=>{
 const {directory,files}=sessionDirectory({schemaVersion:1,kind:'rdg-local-manual-session',active:false});
 await assert.rejects(UI.fileTransport(directory).read(),e=>e.definite===true&&/Сессия Helper завершена/.test(e.message));
 assert.equal(files.size,1);
});
test('wrong folder and incomplete descriptor produce actionable read errors',async()=>{
 for(const descriptor of [undefined,null,{...liveSession,session:''}]){
   const {directory,files}=sessionDirectory(descriptor);
   await assert.rejects(UI.fileTransport(directory).read(),e=>e.definite===true&&/session|сессии|Helper/.test(e.message));
   assert.equal(files.size,descriptor===undefined?0:1);
 }
});
test('denied write access stops before ready marker and explains reconnect',async()=>{
 const {directory,files}=sessionDirectory(liveSession,{denied:true});
 await assert.rejects(UI.fileTransport(directory).write({transactionId:'test'}),
   e=>e.definite===true&&/разрешите чтение и запись/.test(e.message));
 assert.equal(files.size,1);
});
test('unresponsive Helper shows progress then unlocks refresh without showing empty form',async()=>{
 const {directory}=sessionDirectory(liveSession),messages=[],states=[],d=doc(),container=d.createElement('div');
 const transport=UI.fileTransport(directory,{timeoutMs:25,pollMs:1});
 const setStatus=transport.setStatus;transport.setStatus=callback=>setStatus(message=>{messages.push(message);callback(message);});
 const ui=UI.mount(container,transport,{document:d,onStateChange:s=>states.push(s)});
 await ui.refresh();assert.equal(ui.view,null);assert.equal(ui.busy,false);assert.equal(ui.pending,null);
 assert.match(ui.status,/Helper не ответил/);assert(messages.some(m=>m.includes('Ожидаю ответ')));
 assert.equal(ui.buttons.refresh.disabled,false);assert.equal(ui.buttons.place.disabled,true);
 assert(container.children.find(n=>n.classList&&n.children.some(c=>c.tag==='section')).hidden);
 assert(states.some(s=>s.busy));assert.equal(states.at(-1).busy,false);
});
test('unanswered file command keeps exact pending transaction and blocks further edits',async()=>{
 const {directory}=sessionDirectory(liveSession),d=doc();
 const transport=UI.fileTransport(directory,{timeoutMs:20,pollMs:1});
 const ui=UI.mount(d.createElement('div'),{read:async()=>minimal(),write:transport.write},{document:d});
 await ui.refresh();ui.fields.note.value='Synthetic note';await ui.run('edit_title');
 assert(ui.pending);assert.match(ui.status,/Исход запроса не подтверждён/);
 assert.equal(ui.buttons.title.disabled,true);assert.equal(ui.buttons.retry.hidden,false);
 const transaction=ui.pending.transactionId;await ui.buttons.retry.onclick();assert.equal(ui.pending.transactionId,transaction);
});


function tree(root,predicate){return [...(predicate(root)?[root]:[]),...root.children.flatMap(n=>tree(n,predicate))];}
function nodeSnapshot(){
 const fs=require('node:fs'),path=require('node:path'),v=minimal();
 const g=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/rdg-v6-action-optin/graph.json'),'utf8'));
 v.sources.graphs[v.graphFile]=g;
 const ref={graphFile:v.graphFile,identitySpace:g.identitySpace,nodeId:'R0'};
 v.sources.plan.steps=[{id:'S-R0',title:g.nodes[0].title,kind:'requirement',requirementRef:ref}];
 v.future=[{stepId:'S-R0',nodeId:'R0',kind:'requirement',graphRef:ref,timeConstraints:[{type:'notBefore',at:'2026-10-23',strength:'hard'}],sequence:[]}];
 return v;
}
test('plan shows graph cards and Action canon/QRPE, and contains no creation controls',async()=>{
 const d=doc(),container=d.createElement('div'),graphContainer=d.createElement('section'),snapshot=nodeSnapshot(),writes=[],navigation=[];
 const g=snapshot.sources.graphs[snapshot.graphFile],alternative=structuredClone(g.nodes.find(n=>n.id==='A1'));
 alternative.id='A2';alternative.title='Another method';alternative.status='candidate';alternative.qrpe=[{id:'Q2',text:'Check second method',status:'open'}];
 alternative.canonBlock.recommended=[{id:'C2',text:'Use when second case applies'}];
 g.nodes.push(alternative);g.edges.push({id:'drive-A2',type:'DRIVES',from:'R0',to:'A2'});
 const before=JSON.stringify(snapshot);
 const ui=UI.mount(container,{read:async()=>snapshot,write:async r=>writes.push(r)},
   {document:d,graphContainer,onNavigate:async ref=>navigation.push(ref)});await ui.refresh();
 assert(!container.textContent.includes('Создать вариант Action'));assert(!container.textContent.includes('Добавить дочернюю R'));
 assert(graphContainer.textContent.includes('Создать вариант Action'));
 const future=tree(container,n=>n.classList.contains('wf-future'))[0];
 const cards=tree(future,n=>n.tag==='article'&&n.classList.contains('wf-card'));
 assert.equal(cards.length,3,'one placed goal and its two Action variants; unplaced group is separate');
 assert(tree(container,n=>n.classList.contains?.('wf-unplaced-card')).length>0,'graph entities without time placement remain visible separately');
 assert(container.textContent.includes('Use when second case applies'));assert(container.textContent.includes('Check second method'));
 assert.equal(snapshot.future.length,1);assert.equal(JSON.stringify(snapshot),before);assert.equal(writes.length,0);
 const titles=tree(container,n=>n.tag==='button'&&n.textContent==='Another method');await titles[0].onclick();
 assert.equal(navigation[0].nodeId,'A2');assert.equal(writes.length,0);
 ui.editPlacement(snapshot.future[0].graphRef,'S-R0');assert.equal(ui.fields.target.value,'R0');assert.equal(ui.fields.placement.value,'S-R0');
});
test('projection navigation resolves the owning declaration and its introducing context',async()=>{
 const v=nodeSnapshot(),g=v.sources.graphs[v.graphFile],childFile='workspaces/test/child/graph.json';
 const child={identitySpace:g.identitySpace,rootRequirementId:'R1',nodes:[{id:'R1',kind:'requirement',title:'Personal R graph',projectionOf:{graphSlug:'test',nodeId:'R1'}}],edges:[],events:[]};
 v.sources.graphs[childFile]=child;const owner={graphFile:v.graphFile,identitySpace:g.identitySpace,nodeId:'R1'};
 v.sources.completion[childFile]={R1:{ownerRef:owner}};
 const projection={...owner,graphFile:childFile},origin=UI.declarationFor(v,projection);
 assert.equal(origin.ref.graphFile,v.graphFile);assert.equal(origin.contextRootId,'R0');
 const viewer=simulate();await viewer.flush();const result=await viewer.host.rdgWorkflow.openDeclaration(projection,v);
 assert.equal(result.graphFile,v.graphFile);assert.equal(result.contextRootId,'R0');assert.equal(result.nodeId,'R1');
 const shown=viewer.root.querySelectorAll('.node');assert(shown.some(n=>n.getAttribute('data-id')==='R0'));
 assert(shown.some(n=>n.getAttribute('data-id')==='R1'&&n.classList.contains('selected')));
 assert.equal(viewer.ids['workflow-page'].hidden,true);
 delete v.sources.completion[childFile];assert.throws(()=>UI.declarationFor(v,projection),/Владелец проекции не подтверждён/);
 assert.throws(()=>UI.declarationFor(v,{...owner,identitySpace:'another project'}),/недоступен/);
});
test('a deep goal opens its parent wave, while an Action opens its driver wave',()=>{
 const v=nodeSnapshot(),g=v.sources.graphs[v.graphFile];
 g.nodes.push({id:'A2',kind:'action',title:'Deep method',status:'candidate'},{id:'R3',kind:'requirement',title:'Deep child',status:'potential'});
 g.edges.push({id:'d2',type:'DRIVES',from:'R1',to:'A2'},{id:'i2',type:'INTRODUCES',from:'A2',to:'R3',parent:'R1'});
 const ref=id=>({graphFile:v.graphFile,identitySpace:g.identitySpace,nodeId:id});
 assert.equal(UI.declarationFor(v,ref('R3')).contextRootId,'R1');
 assert.equal(UI.declarationFor(v,ref('A2')).contextRootId,'R1');
});


test('editing a placed Action variant keeps the actual projection placement and step identity',async()=>{
 const v=nodeSnapshot(),g=v.sources.graphs[v.graphFile],file='workspaces/test/child/graph.json';
 const canonical={graphFile:v.graphFile,identitySpace:g.identitySpace,nodeId:'A1'},projection={...canonical,graphFile:file};
 v.sources.graphs[file]={identitySpace:g.identitySpace,nodes:[{id:'A1',kind:'action',title:'Projection of method',status:'selected',projectionOf:{graphSlug:'test',nodeId:'A1'}}],edges:[],events:[]};
 v.sources.completion[file]={A1:{ownerRef:canonical}};v.capabilities=['plan.place.from-read-sources'];
 v.sources.plan.steps.push({id:'ORIGINAL-PLACEMENT',title:'Existing method placement',kind:'action',actionRef:projection});
 v.future.push({stepId:'ORIGINAL-PLACEMENT',kind:'action',nodeId:'A1',graphRef:projection,timeConstraints:[],sequence:[]});
 const d=doc(),container=d.createElement('div'),ui=UI.mount(container,{read:async()=>v},{document:d});await ui.refresh();
 const variant=tree(container,n=>n.tag==='article'&&n.children.some(c=>c.tag==='small'&&c.textContent.includes('размещён отдельно')))[0];
 assert(variant);const edit=variant.children.find(n=>n.tag==='button'&&n.textContent==='Изменить размещение');
 assert.equal(edit.disabled,false);edit.onclick();
 assert.equal(ui.fields.graph.value,file);assert.equal(ui.fields.target.value,'A1');assert.equal(ui.fields.placement.value,'ORIGINAL-PLACEMENT');
});


test('a goal collects Action variants from its continuation graph without changing its own declaration',async()=>{
 const v=nodeSnapshot(),g=v.sources.graphs[v.graphFile],child='workspaces/test/continuation/graph.json';
 const owner={graphFile:v.graphFile,identitySpace:g.identitySpace,nodeId:'R0'};
 v.sources.graphs[child]={identitySpace:g.identitySpace,rootRequirementId:'R0',
  nodes:[{id:'R0',kind:'requirement',title:'Continuation root',projectionOf:{graphSlug:'test',nodeId:'R0'}},
   {id:'A-CHILD',kind:'action',title:'Method defined in continuation',status:'candidate',
    canonBlock:{recommended:[{id:'CC',text:'Applicable continuation case'}],contraindicated:[]},qrpe:[{id:'QC',text:'Continuation question',status:'open'}]}],
  edges:[{id:'DC',type:'DRIVES',from:'R0',to:'A-CHILD'}],events:[]};
 v.sources.completion[child]={R0:{ownerRef:owner}};
 const d=doc(),container=d.createElement('div'),navigations=[];
 const ui=UI.mount(container,{read:async()=>v},{document:d,onNavigate:async ref=>navigations.push(ref)});await ui.refresh();
 assert(container.textContent.includes('Method defined in continuation'));assert(container.textContent.includes('Applicable continuation case'));
 assert(container.textContent.includes('Continuation question'));assert.equal(v.future.length,1);
 await tree(container,n=>n.tag==='button'&&n.textContent==='Method defined in continuation')[0].onclick();
 assert.equal(navigations[0].graphFile,child);assert.equal(navigations[0].nodeId,'A-CHILD');
 assert.equal(UI.declarationFor(v,{...owner,graphFile:child}).ref.graphFile,v.graphFile);
});


test('graph authoring reports uncertain writes and exposes exact retry on the graph surface',async()=>{
 const d=doc(),graphContainer=d.createElement('section'),v=minimal();let request=null,count=0;
 const ui=UI.mount(d.createElement('div'),{read:async()=>v,write:async r=>{
   if(count++===0){request=structuredClone(r);throw Error('Lost response');}
   assert.deepEqual(r,request);return {saved:true,replayed:true,view:v};
 }},{document:d,graphContainer});await ui.refresh();ui.fields.note.value='Graph edit';
 await ui.buttons.title.onclick();assert(ui.pending);assert(graphContainer.textContent.includes('Исход запроса не подтверждён'));
 const retry=tree(graphContainer,n=>n.tag==='button'&&n.textContent==='Повторить тот же запрос')[0];
 assert.equal(retry.hidden,false);await retry.onclick();assert.equal(ui.pending,null);
 assert(graphContainer.textContent.includes('повторного действия нет'));
});

test('timeline keeps history before the explicit plan and jumps to its first placed block',async()=>{
 const v=nodeSnapshot(),d=doc(),container=d.createElement('div'),scrolled=[];
 v.history=[
  {kind:'graph_saved',graphFile:v.graphFile,recordedAt:'2026-10-18T10:00:00Z',summary:'Prepared the graph',changed:{nodes:['R0']}},
  {kind:'action_executed',graphFile:v.graphFile,targetId:'A1',recordedAt:'2026-10-19T10:00:00Z',note:'Recorded actual result'},
  {kind:'action_withdrawn',graphFile:v.graphFile,targetId:'A1',recordedAt:null,note:'Unknown save time stays unknown'}];
 const frozen=JSON.stringify(v),ui=UI.mount(container,{read:async()=>v},{document:d});await ui.refresh();
 const cards=tree(container,n=>n.tag==='article'),timeline=container.children.find(n=>n.classList.contains('wf-timeline'));
 assert.equal(timeline.children[0].getAttribute('aria-label'),'История');
 assert.equal(timeline.children[1].getAttribute('aria-label'),'План во времени');
 const first=cards.find(n=>n.getAttribute('data-context')==='placement');
 assert.equal(first.getAttribute('data-node-id'),'R0');
 for(const card of cards)card.scrollIntoView=()=>scrolled.push(card);
 first.focus=()=>{};ui.buttons.jumpPlan.onclick();assert.deepEqual(scrolled,[first]);
 assert(container.textContent.includes('Recorded actual result'));assert(container.textContent.includes('Время записи неизвестно'));
 assert(container.textContent.indexOf('Unknown save time stays unknown')<container.textContent.indexOf('Конец истории'));
 assert.equal(JSON.stringify(v),frozen,'rendering and scrolling preserve every source and its order');
 v.future=[];await ui.refresh();assert.equal(ui.buttons.jumpPlan.disabled,true);ui.buttons.jumpPlan.onclick();assert.equal(scrolled.length,1);
});
test('completed history opens the canonical declaration even when the record refers to a projection',async()=>{
 const v=nodeSnapshot(),g=v.sources.graphs[v.graphFile],file='workspaces/test/personal/graph.json',d=doc(),container=d.createElement('div'),navigations=[];
 const owner={graphFile:v.graphFile,identitySpace:g.identitySpace,nodeId:'R1'};
 v.sources.graphs[file]={identitySpace:g.identitySpace,rootRequirementId:'R1',nodes:[{id:'R1',kind:'requirement',title:'Personal goal',projectionOf:{graphSlug:'test',nodeId:'R1'}}],edges:[],events:[]};
 v.sources.completion[file]={R1:{ownerRef:owner}};
 v.history=[{kind:'requirement_achieved',graphFile:file,targetId:'R1',title:'Historical goal title',recordedAt:'2026-10-19T10:00:00Z',note:'Reached the result'}];
 const ui=UI.mount(container,{read:async()=>v},{document:d,onNavigate:async ref=>navigations.push(ref)});await ui.refresh();
 const event=tree(container,n=>n.tag==='article'&&n.getAttribute('data-context')==='history')[0];
 const link=tree(event,n=>n.tag==='button'&&n.textContent==='Открыть блок в графе ↗')[0];
 assert.equal(link.disabled,false);await link.onclick();assert.deepEqual(navigations,[owner]);
 assert.equal(UI.declarationFor(v,navigations[0]).contextRootId,'R0');
 assert(event.textContent.includes('Historical goal title'));assert(event.textContent.includes('Reached the result'));
 assert.equal(tree(event,n=>n.classList.contains('wf-card-place')).length,0,'history contains no placement edits');
});
test('planned Requirements and Actions and historical Graph edits navigate to the same canonical owner',async()=>{
 const v=minimal(),file=v.graphFile,g=v.sources.graphs[file],d=doc(),container=d.createElement('div'),navigations=[];
 const ref=id=>({graphFile:file,identitySpace:'test',nodeId:id});
 g.nodes.push({id:'A1',kind:'action',title:'Chosen implementation',status:'selected'});
 g.edges.push({id:'e-a',type:'DRIVES',from:'R0',to:'A1'});
 v.sources.plan.steps=[
  {id:'S-R0',kind:'requirement',requirementRef:ref('R0')},
  {id:'S-A1',kind:'action',actionRef:ref('A1')}];
 v.sources.plan.timeConstraints=[{stepId:'S-R0',type:'notBefore',at:'2026-10-25'},
  {stepId:'S-A1',type:'notBefore',at:'2026-10-26'}];
 v.future=[{stepId:'S-R0',kind:'requirement',graphRef:ref('R0'),nodeId:'R0',timeConstraints:[],sequence:[]},
  {stepId:'S-A1',kind:'action',graphRef:ref('A1'),nodeId:'A1',timeConstraints:[],sequence:[]}];
 v.history=[{kind:'graph_saved',graphFile:file,recordedAt:'2026-10-20T10:00:00Z',
  summary:'Graph content changed',changed:{nodes:['A1','R0']}}];
 const ui=UI.mount(container,{read:async()=>v},{document:d,onNavigate:async r=>navigations.push(r)});
 await ui.refresh();
 const placed=tree(container,n=>n.classList.contains('wf-future'))[0];
 for(const id of ['R0','A1']){
  const card=tree(placed,n=>n.tag==='article'&&n.getAttribute('data-node-id')===id&&
    n.getAttribute('data-context')==='placement')[0];
  const link=tree(card,n=>n.tag==='button'&&n.classList.contains('wf-open-graph'))[0];
  assert(link&&!link.disabled,'explicit navigation in planned '+id);
  assert.equal(link.getAttribute('data-node-id'),id);await link.onclick();
 }
 const history=tree(container,n=>n.classList.contains('wf-history'))[0];
 const links=tree(history,n=>n.tag==='button'&&n.classList.contains('wf-open-graph'));
 assert.equal(links.length,2,'both changed nodes can be opened individually');
 for(const link of links){assert(!link.disabled);await link.onclick();}
 assert.deepEqual(navigations,[ref('R0'),ref('A1'),ref('A1'),ref('R0')]);
});
test('history of a changed Action links old, review, selected replacement, and executed compensation to Graph',async()=>{
 const v=minimal(),file=v.graphFile,g=v.sources.graphs[file],d=doc(),container=d.createElement('div'),navigations=[];
 const ids=['A-OLD','A-REVIEW','A-NEW','A-CLEAN'];
 for(const id of ids){g.nodes.push({id,kind:'action',title:id,status:id==='A-OLD'?'superseded':'selected'});
  g.edges.push({id:'DRIVES-'+id,type:'DRIVES',from:'R0',to:id});}
 v.history=[{id:'switch',kind:'action_reconsidered',graphFile:file,targetId:'A-OLD',
  reviewActionId:'A-REVIEW',note:'Transition accepted',
  transition:{replacementActionId:'A-NEW',cancellation:{mode:'compensating_action',
    actionId:'A-CLEAN',executionEventId:'EV-CLEAN',reason:'Cleanup executed'}},
  recordedAt:'2026-10-20T11:00:00Z'}];
 const ui=UI.mount(container,{read:async()=>v},{document:d,onNavigate:async ref=>navigations.push(ref)});
 await ui.refresh();
 const history=tree(container,n=>n.classList.contains('wf-history'))[0];
 const links=tree(history,n=>n.tag==='button'&&n.classList.contains('wf-open-graph'));
 assert.deepEqual(links.map(n=>n.getAttribute('data-node-id')),ids);
 for(const link of links){assert.equal(link.disabled,false);await link.onclick();}
 assert.deepEqual(navigations,ids.map(nodeId=>({graphFile:file,identitySpace:'test',nodeId})));
});
test('historically deactivated Requirement with archived introduction still resolves to its real Graph declaration',()=>{
 const v=minimal(),g=v.sources.graphs[v.graphFile];
 g.nodes.push({id:'D-REVIEW',kind:'decision',title:'Archive decision',status:'committed'},
  {id:'R-RETIRED',kind:'requirement',title:'Formerly relevant goal',status:'inactive',active:false});
 g.edges.push({id:'introduce-R',type:'INTRODUCES',from:'D-REVIEW',to:'R-RETIRED',parent:'R0',archived:true});
 const ref={graphFile:v.graphFile,identitySpace:'test',nodeId:'R-RETIRED'};
 const origin=UI.declarationFor(v,ref);
 assert.equal(origin.ref.nodeId,'R-RETIRED');assert.equal(origin.contextRootId,'R0');
 assert.equal(origin.node.active,false);
});
test('unavailable historical targets stay visible and offer no fabricated graph route',async()=>{
 const v=nodeSnapshot(),d=doc(),container=d.createElement('div');
 v.history=[{kind:'action_executed',graphFile:v.graphFile,targetId:'removed',title:'Past action',note:'Stored result',recordedAt:null}];
 const ui=UI.mount(container,{read:async()=>v},{document:d,onNavigate:async()=>assert.fail('unavailable target')});await ui.refresh();
 assert(container.textContent.includes('Past action'));assert(container.textContent.includes('removed недоступен'));
 assert.equal(tree(container,n=>n.tag==='article'&&n.getAttribute('data-context')==='history').length,1);
});

test('history uses immutable canon/QRPE snapshots and marks old missing material honestly',async()=>{
 const d=doc(),view=minimal(),file=view.graphFile;
 const current={id:'A',kind:'action',status:'superseded',title:'CURRENT TITLE',
  canonBlock:{recommended:[{text:'CURRENT CANON'}],contraindicated:[]},qrpe:[{status:'open',text:'CURRENT ISSUE'}]};
 view.sources.graphs[file].nodes.push(current);
 view.sources.graphs[file].edges.push({id:'D',type:'DRIVES',from:'R0',to:'A'});
 view.history=[{id:'old',kind:'action_executed',targetId:'A',graphFile:file,title:'HISTORICAL TITLE',
  materialSnapshotAvailable:true,nodeSnapshot:{...current,title:'HISTORICAL TITLE',status:'selected',
   canonBlock:{recommended:[{text:'SAVED CANON'}],contraindicated:[]},qrpe:[{status:'resolved',text:'SAVED ISSUE'}]}},
  {id:'legacy',kind:'action_executed',targetId:'A',graphFile:file,title:'LEGACY TITLE',
   materialSnapshotAvailable:false,nodeSnapshot:{id:'A',kind:'action',title:'LEGACY TITLE',status:'selected'}}];
 const container=d.createElement('div'),ui=UI.mount(container,{read:async()=>view},{document:d,onNavigate:async()=>{}});
 await ui.refresh();
 assert.match(container.textContent,/SAVED CANON/);assert.match(container.textContent,/SAVED ISSUE/);
 assert.match(container.textContent,/Канон на момент записи/);assert.match(container.textContent,/не сохранены/);
 const history=tree(container,n=>n.classList.contains('wf-history'))[0];
 assert.doesNotMatch(history.textContent,/CURRENT CANON|CURRENT ISSUE/,
   'historic card must not leak modern canon; live unplaced variants can show it separately');
 assert.match(container.textContent,/CURRENT CANON|CURRENT ISSUE/,
   'live canon is explicitly available outside historical snapshot');
});
test('previous embedded Action teaching timelines are unavailable in the active viewer',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();
 await assert.rejects(ui.host.rdgExplorer.openFull('reference-action-time-plan'),
  /Корневой граф недоступен|OLD_GRAPH_MODEL_DISABLED/);
 assert(!ui.host.rdgExplorer.getCatalog().fullGraphs.some(g=>g.slug==='reference-action-time-plan'));
 // The offline archived JSON remains readable by explicit migration tooling.
 const g=require('../graphs/examples/reference-action-time-plan/graph.json');
 assert(g.workflowExample?.history?.length>0);
});
test('workspace switching rejects mismatched Plan file and clears the preceding Plan',async()=>{
 const d=doc(),container=d.createElement('div');
 const expected={contextId:'alpha',graphFile:'workspaces/test/graph.json',
  planFile:'plans/alpha/plan.json',identitySpace:'test',title:'Alpha'};
 const snapshot=minimal();snapshot.contextId='alpha';snapshot.title='Alpha';
 let actual='plans/foreign/plan.json',reads=0;
 const ui=UI.mount(container,{read:async id=>{
  assert.equal(id,'alpha');++reads;return {...snapshot,planFile:actual};
 }},{document:d});
 assert.equal(await ui.switchWorkspace(expected),false);
 assert.equal(ui.view,null);
 assert.match(ui.status,/PLAN_WORKSPACE_IDENTITY_MISMATCH/);
 assert.equal(ui.buttons.add.disabled,true);
 actual=expected.planFile;
 assert.equal(await ui.switchWorkspace(expected),true);
 assert.equal(ui.view.planFile,expected.planFile);
 assert.equal(await ui.switchWorkspace(null,'Для другого графа нет плана'),false);
 assert.equal(ui.view,null);assert.equal(ui.buttons.add.disabled,true);
 await ui.refresh();assert.equal(reads,2,'refresh must not reattach an old Plan after no binding');
 assert.match(ui.status,/нет плана/);
});
test('working graph timeline requires matching persisted Plan owner, never a placeholder',()=>{
 const graphFile='workspaces/test-work/graph.json',entry={slug:'test-work',file:graphFile,title:'Real Workspace'};
 const g={schemaVersion:1,revision:1,id:'new-only',title:'Real Workspace',actionModel:'candidate-v6',identitySpace:'test-work-space',rootRequirementId:'R0',nodes:[{id:'R0',kind:'requirement',title:'Requirement'}],edges:[],events:[]};
 const plan={schemaVersion:1,kind:'temporalPlan',id:'test-work',title:'Real Plan',revision:1,
  identitySpace:'test-work-space',status:'candidate',steps:[],sequence:[],branches:[],timeConstraints:[]};
 const persisted={schemaVersion:1,kind:'temporalPlanOwner',revision:1,
  owner:{planId:'test-work',identitySpace:'test-work-space',sourcePath:'plans/test-work/plan.json'},
  versions:[{revision:1,plan,recordedAt:'2026-10-21T00:00:00Z',transactionId:'create-plan'}],transactions:{}};
 const result=UI.localPlanFromOwner(entry,{[graphFile]:g},persisted);
 assert.equal(result.planProvenance.persisted,true);
 assert.equal(result.planFile,'plans/test-work/plan.json');
 assert.equal(result.localPreview,false);assert.deepEqual(result.future,[]);assert.deepEqual(result.history.map(h=>h.kind),['plan_created']);
 assert.equal(result.sources.plan.title,'Real Plan');
 assert.throws(()=>UI.localPlanFromOwner(entry,{[graphFile]:g},null),/PLAN_OWNER_NOT_MATCHING_GRAPH/);
 assert.throws(()=>UI.localPlanFromOwner(entry,{[graphFile]:g},{...persisted,owner:{...persisted.owner,planId:'someone-else'}}),/PLAN_OWNER_NOT_MATCHING_GRAPH/);
 assert.throws(()=>UI.localPlanFromOwner(entry,{[graphFile]:g},{...persisted,versions:[{revision:1,plan:{...plan,identitySpace:'other'}}]}),/PLAN_OWNER_RECORD_INVALID/);
});

test('read-only archived full working example is an example, not a preliminary Plan',()=>{
 const ref='examples/reference-feature-root/graph.json';
 const entry={slug:'reference-feature-root',title:'Пример разбиения на Features',file:ref};
 const graph={schemaVersion:1,id:'example',revision:1,title:'Feature sample',
  identitySpace:'demo:feature-functional',readOnly:true,exampleOnly:true,
  nodes:[{id:'R',kind:'requirement',title:'R'}],edges:[],events:[]};
 const preview=UI.localPlanPreview(entry,{[ref]:graph},{exampleOnly:true});
 assert.equal(preview.examplePreview,true);
 assert.equal(preview.authoredExamplePreview,false);
 assert.equal(preview.localPreview,false);
 assert.equal(preview.planProvenance.persisted,false);
 assert.equal(preview.planProvenance.mode,'educational-example-no-owner');
 assert.deepEqual(preview.future,[]);
 assert.deepEqual(preview.history,[]);
});

test('placement and completion are independent: only authorized graph evidence proves completion',()=>{
 const graphFile='workspaces/test/graph.json',space='test',g={identitySpace:space,
  nodes:[
   {id:'R0',kind:'requirement',title:'Scheduled goal',status:'active'},
   {id:'R-OPEN',kind:'requirement',title:'Unplaced actual goal',status:'active'},
   {id:'R-DONE',kind:'requirement',title:'Completed goal',status:'active'},
   {id:'R-PENDING',kind:'requirement',title:'Derived result awaiting journal',status:'active'},
   {id:'R-POTENTIAL',kind:'requirement',title:'Unchosen path',status:'potential'},
   {id:'A-DONE',kind:'action',title:'Executed Action',status:'selected'},
   {id:'A-POSSIBLE',kind:'action',title:'Not selected Action',status:'candidate'},
   {id:'A-ACTUAL',kind:'action',title:'Selected but unplaced Action',status:'selected'}],edges:[],events:[]};
 const ref=id=>({graphFile,identitySpace:space,nodeId:id});
 const view={graphFile,sources:{graphs:{[graphFile]:g},plan:{
  steps:[{id:'S-1',kind:'requirement',requirementRef:ref('R0')}],
  timeConstraints:[{stepId:'S-1',type:'notBefore',at:'2026-11-01'}],sequence:[]},
  completion:{[graphFile]:{
   R0:{complete:false,currentScopeComplete:false,reason:'result-not-recorded'},
   'R-OPEN':{complete:false,reason:'result-not-recorded'},
   'R-DONE':{complete:true,currentScopeComplete:true,eventId:'EV-R-DONE'},
   'R-PENDING':{complete:true,currentScopeComplete:true,historyPending:true,eventId:null},
   'A-DONE':{complete:true,currentScopeComplete:false,eventId:'EV-A-DONE'},
   'A-ACTUAL':{complete:false,currentScopeComplete:false,reason:'result-not-recorded'}}}}};
 const inv=UI.planningInventory(view);
 assert.deepEqual(inv.unplaced.map(n=>n.nodeId),['R-OPEN','A-ACTUAL']);
 assert.equal(inv.placedCount,1);
 assert.equal(inv.completedCount,2,'executed Action stays historical after scope drift; achieved R requires current valid scope');
 assert.deepEqual(inv.needsVerification.map(n=>n.nodeId),['R-PENDING']);
 assert.equal(inv.excludedCount,2,'potential R and unselected Action are not obligatory actual work');
});
test('an unknown completion result must not be invented from absent history',()=>{
 const v=minimal();v.sources.graphs[v.graphFile].nodes.push({id:'R1',kind:'requirement',title:'R with unknown execution'});
 const inv=UI.planningInventory(v);
 assert.deepEqual(inv.unplaced.map(x=>x.nodeId),['R0','R1']);
 assert(inv.unplaced.every(x=>x.verification==='completion-not-verified'));
});
test('mixed educational workspace has historical changes and explicit R placements but no invented completed Actions',()=>{
 const example=require('../graphs/examples/reference-mixed-active-work/graph.json');
 const source='examples/reference-mixed-active-work/graph.json';
 const view=UI.localPlanPreview({slug:'reference-mixed-active-work',file:source,title:example.title},
   {[source]:example},{exampleOnly:true});
 assert.equal(view.examplePreview,true);assert.equal(view.authoredExamplePreview,true);
 assert.equal(view.planProvenance.persisted,false);
 assert.equal(view.history.length,5);
 assert.deepEqual(view.history.map(e=>e.id.split('::').at(-1)),
   ['EX-EV-A','EX-EV-T2','EX-EV-OTHER','EX-EV-INACTIVE','EX-EV-RELINK'].sort((a,b)=>{
     const x={ 'EX-EV-A':1,'EX-EV-T2':2,'EX-EV-OTHER':3,'EX-EV-INACTIVE':4,'EX-EV-RELINK':4};
     return x[a]-x[b]||a.localeCompare(b);
   }), 'symbolic T1..T4 chronology must be ordered, not input event-array order');
 assert.equal(view.history.every(e=>e.notAnExecution),true);
 assert.equal(view.history.some(e=>e.kind==='action_executed'||e.kind==='requirement_achieved'),false);
 assert.deepEqual(view.future.map(e=>e.nodeId),['R-ACT-1','R-ACT-2','R-TECH']);
 assert(view.future[0].sequence.length>0,'planned order is explicit');
 assert.equal(view.future[2].timeConstraints[0].strength,'hypothetical');
 const inventory=UI.planningInventory(view);
 assert.equal(inventory.completedCount,0);
 assert.equal(inventory.placedCount,3);
 assert(inventory.unplaced.some(e=>e.nodeId==='R0'));
 assert(inventory.unplaced.some(e=>e.nodeId==='R-COMP'));
 assert(!inventory.unplaced.some(e=>e.nodeId==='R-INACTIVE'));
 assert(!inventory.unplaced.some(e=>e.nodeId==='R-PREV-FEATURE-1'),'potential branch is not obligatory actual work');
});

test('history event categories visually distinguish results, state changes, selection, and edits',()=>{
 for(const [type,group] of [
   ['action_executed','result'],['requirement_achieved','result'],
   ['action_withdrawn','state'],['requirement_deactivated','state'],
   ['requirement_activated','state'],['action_reconsidered','state'],
   ['action_selected','choice'],['decision_selected','choice'],
   ['graph_saved','change'],['context_discovered','change'],
   ['requirement_reparented','change']]){
   const family=UI.historyKind(type);
   assert.equal(family.group,group,type);
   assert(family.label.length>2);
 }
 assert.notEqual(UI.historyKind('action_executed').group,UI.historyKind('action_selected').group);
});
test('educational Plan refuses a nonexistent Graph Action, a nonexistent step, or an unselected Action',()=>{
 const g=require('../graphs/examples/reference-action-time-plan/graph.json');
 const entry={slug:'reference-action-time-plan',title:g.title,file:'examples/reference-action-time-plan/graph.json'};
 const source=structuredClone(g);
 const files={[entry.file]:source};
 assert.equal(UI.localPlanPreview(entry,files,{exampleOnly:true}).future.length,4);
 const bad=structuredClone(g);bad.workflowExample.future[0].nodeId='ACTION-NOT-IN-GRAPH';
 assert.throws(()=>UI.localPlanPreview(entry,{[entry.file]:bad},{exampleOnly:true}),
   /EDUCATIONAL_PLAN_REFERENCES_MUST_EXIST_IN_GRAPH/);
 const badStep=structuredClone(g);badStep.workflowExample.future[0].stepId='FAKE-STEP';
 assert.throws(()=>UI.localPlanPreview(entry,{[entry.file]:badStep},{exampleOnly:true}),
   /EDUCATIONAL_PLAN_REFERENCES_MUST_EXIST_IN_GRAPH/);
 const noSelection=structuredClone(g),planned=noSelection.workflowExample.future.find(x=>x.kind==='action');
 noSelection.nodes.find(x=>x.id===planned.nodeId).status='candidate';
 assert.throws(()=>UI.localPlanPreview(entry,{[entry.file]:noSelection},{exampleOnly:true}),
   /EDUCATIONAL_PLAN_REFERENCES_MUST_EXIST_IN_GRAPH/);
});
test('paired Action change visibly distinguishes replacement, assessed no-extra cleanup, and executed compensation',async()=>{
 const file='workspaces/test/graph.json',d=doc(),parent=d.createElement('div'),v=minimal();
 const g=v.sources.graphs[file];g.nodes.push(
   {id:'A1',kind:'action',title:'Old method',status:'superseded'},
   {id:'A2',kind:'action',title:'New method',status:'selected'},
   {id:'A3',kind:'action',title:'Undo old code',status:'selected'});
 const common={kind:'action_reconsidered',graphFile:file,targetId:'A1',title:'Old method',
   note:'Reconsider methods',recordedAt:'2026-10-20T11:00:00.000Z'};
 v.history=[
  {...common,id:'H-NO-EXTRA',transition:{replacementActionId:'A2',cancellation:{mode:'no_additional_action',
    reason:'Only graph selection changed',assessmentEvidenceRefs:['graph-node:R0@'+'a'.repeat(64)]}}},
  {...common,id:'H-COMPENSATED',recordedAt:'2026-10-20T12:00:00.000Z',transition:{replacementActionId:'A2',
    cancellation:{mode:'compensating_action',actionId:'A3',executionEventId:'EV-CLEANUP',
      reason:'Removed obsolete code after actual execution'}}},
  {...common,id:'H-OLDER',recordedAt:'2026-10-20T13:00:00.000Z'}
 ];
 const ui=UI.mount(parent,{read:async()=>v},{document:d,readOnly:true});await ui.refresh();
 const history=parent.children.flatMap(c=>c.children).find(n=>n.classList.contains('wf-history'));
 assert(history);
 const events=history.children.filter(n=>n.tag==='article'&&n.getAttribute('data-event-kind')==='action_reconsidered');
 assert.equal(events.length,3);
 assert(events.every(e=>e.getAttribute('data-event-family')==='state'));
 assert.match(events[0].textContent,/Смена: Old method → New method/);
 assert.match(events[0].textContent,/дополнительных действий не потребовалось/);
 assert.match(events[1].textContent,/выполнен Action «Undo old code»/);
 assert.match(events[1].textContent,/EV-CLEANUP/);
 assert.match(events[2].textContent,/Механизм отмены последствий и новый способ не указаны/);
 assert(!events[2].textContent.includes('дополнительных действий не потребовалось'));
});
test('Requirement reformulation history shows the actual signed old/new snapshots and the Graph target',async()=>{
 const view=minimal(),file=view.graphFile,d=doc(),host=d.createElement('div'),visited=[];
 view.sources.graphs[file].nodes[0].title='New requirements';
 view.history=[{id:'reform',kind:'requirement_reformulated',graphFile:file,targetId:'R0',
  previousRequirementSnapshot:{id:'R0',kind:'requirement',title:'Old requirements',requirementText:'Scope A'},
  newRequirementSnapshot:{id:'R0',kind:'requirement',title:'New requirements',requirementText:'Scope B'},
  nodeSnapshot:{id:'R0',kind:'requirement',title:'Old requirements',requirementText:'Scope A'},
  materialSnapshotAvailable:true,recordedAt:'2026-10-21T00:00:00Z'}];
 const ui=UI.mount(host,{read:async()=>view},{document:d,onNavigate:async r=>visited.push(r)});
 await ui.refresh();
 const rows=tree(host,n=>n.getAttribute?.('data-event-kind')==='requirement_reformulated');
 assert.equal(rows.length,1);
 assert.match(rows[0].textContent,/Было \(title\): Old requirements/);
 assert.match(rows[0].textContent,/Стало \(title\): New requirements/);
 assert.match(rows[0].textContent,/Было \(requirementText\): Scope A/);
 assert.match(rows[0].textContent,/Стало \(requirementText\): Scope B/);
 const link=tree(rows[0],n=>n.tag==='button'&&n.classList.contains('wf-open-graph'));
 assert.equal(link.length,1);assert.equal(link[0].disabled,false);
 await link[0].onclick();
 assert.deepEqual(visited,[{graphFile:file,identitySpace:'test',nodeId:'R0'}]);
});

test('history distinguishes creation, candidate Action, selected Action with introduced Rs and groups technical save',async()=>{
 const v=minimal(),file=v.graphFile,d=doc(),host=d.createElement('div');
 v.sources.graphs[file].revision=4;
 v.sources.graphs[file].nodes.push({id:'A1',kind:'action',title:'Разложить на подцели',status:'selected',
   canonBlock:{recommended:[{id:'C1',text:'When complexity warrants decomposition'}],contraindicated:[]}},
  {id:'R1',kind:'requirement',title:'Подцель I',status:'active'},
  {id:'R2',kind:'requirement',title:'Подцель II',status:'active'});
 v.history=[
  {kind:'graph_saved',changeKind:'graph_created',summary:'Создан рабочий Graph: Root',
   graphFile:file,transactionId:'tx1',revision:1,changed:{nodes:['R0'],edges:[]},recordedAt:'2026-10-21T12:00:00Z'},
  {kind:'graph_saved',changeKind:'action_added',changeTargetId:'A1',summary:'Добавлен кандидат Action: Разложить на подцели',
   graphFile:file,transactionId:'tx2',previousRevision:1,revision:2,changed:{nodes:['A1'],edges:['E1']},recordedAt:'2026-10-21T12:01:00Z'},
  {kind:'graph_saved',changeKind:'graph_saved',graphFile:file,transactionId:'tx3',previousRevision:2,revision:3,
   changed:{nodes:['A1','R1','R2'],edges:['E2','E3']},summary:'Выбран Action',recordedAt:'2026-10-21T12:02:00Z'},
  {kind:'action_selected',graphFile:file,transactionId:'tx3',targetId:'A1',recordedAt:'2026-10-21T12:02:00Z',
   note:'Выбор способа не является выполнением.',
   introducedRequirements:[
    {nodeId:'R1',title:'Подцель I',kind:'requirement',status:'active',introductionMode:'created',childRole:'subgoal',graphFile:file},
    {nodeId:'R2',title:'Подцель II',kind:'requirement',status:'active',previousStatus:'potential',introductionMode:'activated',childRole:'subgoal',graphFile:file}]}
 ];
 const ui=UI.mount(host,{read:async()=>v},{document:d});await ui.refresh();
 const history=tree(host,n=>n.tag==='article'&&n.getAttribute?.('data-context')==='history');
 assert.equal(history.length,3,'one main card per transaction, technical duplicate hidden');
 assert.deepEqual(history.map(n=>n.getAttribute('data-event-kind')),
  ['graph_saved','graph_saved','action_selected']);
 assert.match(history[0].textContent,/Создан рабочий Graph/);
 assert.match(history[1].textContent,/Добавлен кандидат Action/);
 assert.match(history[2].textContent,/Подцель I/);
 assert.match(history[2].textContent,/Подцель II/);
 assert.match(history[2].textContent,/активирована из potential/);
 assert.match(history[2].textContent,/Введение или активация подцели ≠ размещение/);
 const links=tree(history[2],n=>n.tag==='button'&&n.textContent.includes('Открыть R в графе'));
 assert.equal(links.length,2,'each introduced R is navigable');
 const tech=tree(history[2],n=>n.tag==='details'&&n.classList.contains('wf-save-details'));
 assert.equal(tech.length,1);assert.match(tech[0].textContent,/r2 → r3/);
 assert.match(tech[0].textContent,/tx3/);
 assert.equal(v.history.length,4,'original immutable API history rows retained');
 assert(!history[2].textContent.includes('Выполнен Action'));
});
