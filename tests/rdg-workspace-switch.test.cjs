'use strict';
// Synthetic workspace-switch acceptance, invoked by Python's real-writer FileSession fixture.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const UI=require('../tools/rdg-workflow-ui.js');
const directoryName=process.env.RDG_WORKSPACE_TEST_DIR;
function documentStub(){
 const createElement=tag=>{
  let own='';const classes=new Set(),attrs={};
  const n={tag,children:[],value:'',disabled:false,hidden:false,open:false,
   appendChild(x){n.children.push(x);return x;},replaceChildren(...xs){n.children=xs;},
   setAttribute(k,v){attrs[k]=String(v);},getAttribute:k=>attrs[k]??null,
   classList:{contains:x=>classes.has(x),add:x=>classes.add(x),remove:x=>classes.delete(x),toggle:(x,on)=>on?classes.add(x):classes.delete(x)},
   get textContent(){return own+n.children.map(x=>x.textContent).join('');},
   set textContent(x){own=String(x);n.children=[];}};
  return n;
 };
 return {createElement};
}
test('a selected full graph switches to its own Plan and never carries A into B',
 {skip:!directoryName},async()=>{
 const directory={async getFileHandle(name,options={}){
  assert.match(name,/^[A-Za-z0-9_.-]+$/);const file=path.join(directoryName,name);
  if(!options.create)await fs.stat(file).catch(e=>{if(e.code==='ENOENT'){e.name='NotFoundError';}throw e;});
  return {async getFile(){return {text:async()=>fs.readFile(file,'utf8').catch(e=>{if(e.code==='ENOENT')e.name='NotFoundError';throw e;})};},
   async createWritable(){let text='';return {write:async value=>{text=value;},close:async()=>fs.writeFile(file,text)};}};
 },async removeEntry(name){await fs.unlink(path.join(directoryName,name));}};
 const transport=UI.fileTransport(directory,{timeoutMs:30000,pollMs:10});
 const descriptor=await transport.describe();assert.equal(descriptor.active,true);
 assert.equal(descriptor.contexts.length,2);
 const c=id=>{const r=descriptor.contexts.find(x=>x.rootSlug===id);assert(r);return {contextId:id,graphFile:r.graphFile,identitySpace:r.identitySpace,title:id};};
 const doc=documentStub(),ui=UI.mount(doc.createElement('div'),transport,{document:doc});
 const a=c('demo'),b=c('beta');
 assert.equal(await ui.switchWorkspace(a),true);assert.equal(ui.view.contextId,'demo');
 assert.equal(ui.view.sources.plan.id,'demo');assert.equal(ui.fields.target.value,'R0');
 ui.fields.note.value='Synthetic A write';ui.fields.title.value='Action only in A';ui.fields.recommended.value='Synthetic applicability A';
 await ui.buttons.add.onclick();assert.match(ui.status,/Запись сохранена/);
 const graphA=ui.view.sources.graphs[a.graphFile];assert(graphA.nodes.some(n=>n.title==='Action only in A'));
 ui.fields.at.value='2026-10-24';await ui.buttons.place.onclick();assert.match(ui.status,/Запись сохранена/);
 assert.equal(ui.view.sources.plan.steps.length,1);

 assert.equal(await ui.switchWorkspace(b),true);assert.equal(ui.view.contextId,'beta');
 assert.equal(ui.view.sources.plan.id,'beta');assert.equal(ui.fields.target.value,'RB');
 assert.equal(ui.view.sources.graphs[b.graphFile].nodes.some(n=>n.title==='Action only in A'),false);
 ui.fields.note.value='Synthetic B write';ui.fields.title.value='Action only in B';ui.fields.recommended.value='Synthetic applicability B';
 await ui.buttons.add.onclick();assert.match(ui.status,/Запись сохранена/);
 assert.equal(ui.view.sources.graphs[b.graphFile].nodes.some(n=>n.title==='Action only in B'),true);
 ui.fields.at.value='2026-10-25';await ui.buttons.place.onclick();assert.match(ui.status,/Запись сохранена/);
 assert.equal(ui.view.sources.plan.steps.length,1);

 assert.equal(await ui.switchWorkspace(a),true);assert.equal(ui.view.sources.plan.id,'demo');
 assert.equal(ui.view.sources.graphs[a.graphFile].nodes.some(n=>n.title==='Action only in A'),true);
 assert.equal(ui.view.sources.graphs[a.graphFile].nodes.some(n=>n.title==='Action only in B'),false);
 assert.equal(ui.view.sources.plan.steps.length,1);
 assert.equal(ui.view.sources.plan.steps[0].actionRef.graphFile,a.graphFile);

 // Cross-graph forged target is rejected by the real writer, not by UI convention.
 const wrong={contextId:'beta',action:'edit_title',transactionId:'cross-target-attack',
  nodeId:'RB',graphFile:a.graphFile,expectedGraphRevision:2,expectedPlanRevision:2,
  title:'Wrong file',note:'Synthetic negative check'};
 await assert.rejects(()=>transport.write(wrong),/HELPER_GRAPH_WRITE_FILE_BOUND/);
 await assert.rejects(()=>transport.write({contextId:'beta',action:'place',
  transactionId:'cross-context-placement',nodeId:'R0',graphFile:a.graphFile,
  expectedGraphRevision:2,expectedPlanRevision:2,at:'2026-10-30'}),/HELPER_PLACEMENT_SOURCE_NOT_READ/);
 // No mapping or denied target may display a stale, editable old Plan.
 assert.equal(await ui.switchWorkspace({contextId:'unknown',graphFile:a.graphFile,identitySpace:'demo',title:'Unknown'}),false);
 assert.equal(ui.view,null);assert.match(ui.status,/WORKSPACE_NOT_REGISTERED/);
 assert.equal(await ui.switchWorkspace(null,'Для этого графа нет плана'),false);
 assert.equal(ui.view,null);assert.equal(ui.buttons.add.disabled,true);
 assert.match(ui.status,/нет плана/);
 assert.deepEqual((await fs.readdir(directoryName)).filter(n=>n!=='session.json'),[]);
});
