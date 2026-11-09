'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const UI=require('../tools/rdg-workflow-ui.js');
const {simulate}=require('./viewer-test-helper.cjs');
function doc(){
  const createElement=tag=>{
    let own='';const classes=new Set();
    const n={tag,children:[],value:'',disabled:false,hidden:false,
      appendChild(x){n.children.push(x);return x;},replaceChildren(...xs){n.children=xs;},
      setAttribute(){},classList:{add:x=>classes.add(x),remove:x=>classes.delete(x),toggle:(x,on)=>on?classes.add(x):classes.delete(x)},
      get textContent(){return own+n.children.map(x=>x.textContent).join('');},
      set textContent(x){own=String(x);n.children=[];}};
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
   {document:d,onGraph:async()=>{if(fail)throw Error('render failed');}});
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
test('Viewer keeps manual controls detached until explicit local attachment',async()=>{
 const viewer=simulate();await viewer.flush();assert.equal(viewer.ids['workflow-toggle'].hidden,true);
 const panel=viewer.host.rdgWorkflow.attach();assert.equal(viewer.ids['workflow-toggle'].hidden,false);
 assert.equal(panel.hidden,false);viewer.ids['workflow-toggle'].onclick();assert.equal(panel.hidden,true);
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
   {document:d,onGraph:g=>viewer.host.rdgWorkflow.loadGraph(g)});
 await ui.refresh();assert(ui.view);
 const choose=id=>{ui.fields.target.value=id;ui.fields.target.onchange();};
 const click=async name=>{assert.equal(ui.buttons[name].disabled,false,name+' should be available');
   await ui.buttons[name].onclick();assert.match(ui.status,/Запись сохранена/,ui.status);};
 ui.fields.note.value='User entered synthetic change/result';
 ui.fields.title.value='First action';ui.fields.recommended.value='Applicable';
 await click('add');const a1=ui.fields.target.value;
 ui.fields.at.value='2026-10-21';await click('place');
 choose('R0');ui.fields.title.value='Second action';ui.fields.recommended.value='Different applicable method';
 await click('add');const a2=ui.fields.target.value;assert.notEqual(a1,a2);
 ui.fields.at.value='2026-10-22';await click('place');
 choose('R0');ui.fields.at.value='2026-10-23';await click('place');
 assert.equal(ui.view.future.length,3);
 choose(a1);await click('select');await click('complete');
 assert.deepEqual(ui.view.future.map(r=>r.nodeId),[a2]);
 await click('withdraw');assert(ui.view.future.some(r=>r.nodeId==='R0'));
 choose(a2);await click('select');assert(ui.view.future.some(r=>r.nodeId===a2));await click('complete');
 assert.equal(ui.view.future.length,0);
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
   {document:d,onGraph:g=>viewer.host.rdgWorkflow.loadGraph(g)});
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
