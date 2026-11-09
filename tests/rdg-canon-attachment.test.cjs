'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {simulate}=require('./viewer-test-helper.cjs');
const node=(ui,id)=>ui.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')===id);
const xy=(ui,id)=>node(ui,id).getAttribute('transform').match(/[-\d.]+/g).map(Number);
const walk=(root,match)=>[...(match(root)?[root]:[]),...(root.children||[]).flatMap(n=>walk(n,match))];
function fixture(){
 const g=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/rdg-v6-action-optin/graph.json'),'utf8'));
 const a=structuredClone(g.nodes.find(n=>n.id==='A1'));a.id='A2';a.title='Second method';a.status='candidate';delete a.selectionBasis;
 g.nodes.push(a);g.edges.push({id:'drives-A2',type:'DRIVES',from:'R0',to:'A2'});return g;
}
function above(ui,owner,id){
 const a=xy(ui,owner),c=xy(ui,id);assert.equal(c[0],a[0]);assert(c[1]+72<a[1],'canon is entirely above its owner');
 return {a,c};
}
test('two Action canons sit above their owners and remain outside the R-Action-R rank chain',async()=>{
 const ui=simulate(),g=fixture(),original=JSON.stringify(g);await ui.loadFile(g);ui.ids['variants-all'].onclick();
 for(const id of ['A1','A2'])above(ui,id,'__canon__'+id);
 assert(xy(ui,'R0')[0]<xy(ui,'A1')[0]);assert(xy(ui,'A1')[0]<xy(ui,'R1')[0]);
 const boxes=ui.root.querySelectorAll('.node').map(n=>({id:n.getAttribute('data-id'),p:xy(ui,n.getAttribute('data-id'))}));
 for(const box of boxes.filter(n=>n.id.startsWith('__canon__')))for(const other of boxes){
  if(box===other)continue;
  assert(!(Math.abs(box.p[0]-other.p[0])<222&&Math.abs(box.p[1]-other.p[1])<72),box.id+' overlaps '+other.id);
 }
 const edges=walk(ui.ids.canvas,n=>n.classList?.contains('edge'));
 const attachments=edges.filter(n=>n.classList.contains('canon-attachment'));assert.equal(attachments.length,2);
 for(const edge of attachments){
  assert.equal(edge.getAttribute('marker-end'),null,'property connector has no outgoing arrow');
  const p=edge.getAttribute('d').match(/[-\d.]+/g).map(Number);assert.equal(p[0],p[2]);
 }
 assert(edges.filter(n=>!n.classList.contains('canon-attachment')).every(n=>n.getAttribute('marker-end')==='url(#rdg-arrow)'));
 assert.equal(JSON.stringify(g),original);assert(!g.nodes.some(n=>n.kind==='canon'));
});
test('old saved canon coordinates do not detach it from a moved or restored Action',async()=>{
 const ui=simulate(),g=fixture();await ui.loadFile(g);
 ui.host.rdgLayout.apply({type:'set_positions',positions:{A1:{x:710,y:560},__canon__A1:{x:2000,y:1000}}});
 above(ui,'A1','__canon__A1');assert.deepEqual(xy(ui,'A1'),[710,560]);
 const saved=JSON.parse(JSON.stringify(ui.host.rdgLayout.getDocument()));
 const restored=simulate();restored.host.rdgLayout.load(saved);await restored.loadFile(g);
 above(restored,'A1','__canon__A1');assert.deepEqual(xy(restored,'A1'),[710,560]);
 assert.deepEqual(JSON.parse(JSON.stringify(restored.host.rdgLayout.getDocument())),saved,'view attachment does not rewrite stored layout');
 const canon=node(restored,'__canon__A1'),before=xy(restored,'A1');
 restored.ids.canvas.listeners.pointerdown({button:0,pointerId:7,clientX:100,clientY:100,target:canon});
 restored.ids.canvas.listeners.pointermove({pointerId:7,clientX:130,clientY:150});
 restored.ids.canvas.listeners.pointerup({pointerId:7});
 assert.notDeepEqual(xy(restored,'A1'),before,'dragging canon moves the owning pair');
 above(restored,'A1','__canon__A1');
});
test('selected legacy Decision retains its option canon above the Decision across variant toggles',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();await ui.openLevel('reference-mixed-active-work','R-COMP');
 const g=JSON.parse(fs.readFileSync(path.join(__dirname,'../graphs/examples/reference-mixed-contextual-split/graph.json'),'utf8'));
 const d=g.nodes.find(n=>n.kind==='decision'&&n.selectedOptionId&&node(ui,'__canon__'+n.selectedOptionId));
 assert(d);above(ui,d.id,'__canon__'+d.selectedOptionId);
 ui.ids['variants-all'].onclick();above(ui,d.id,'__canon__'+d.selectedOptionId);
 ui.ids['variants-all'].onclick();above(ui,d.id,'__canon__'+d.selectedOptionId);
});

test('a placed legacy option gets its own attached canon when all options are shown',async()=>{
 const ui=simulate(),g={schemaVersion:1,id:'canon-option',revision:1,rootRequirementId:'R',
 nodes:[{id:'R',kind:'requirement',title:'Goal'},{id:'D',kind:'decision',title:'Selected answer',status:'committed',selectedOptionId:'O'},
 {id:'O',kind:'option',title:'Selected option',canonBlock:{recommended:[{id:'C',text:'Applicable'}],contraindicated:[]}}],
 edges:[{id:'rd',type:'DRIVES',from:'R',to:'D'},{id:'ro',type:'OPTION_FOR',from:'R',to:'O'}]};
 await ui.loadFile(g);above(ui,'D','__canon__O');
 ui.ids['variants-all'].onclick();above(ui,'O','__canon__O');
 ui.ids['variants-all'].onclick();above(ui,'D','__canon__O');
});

function denseFixture(){
 const g=fixture();g.id='dense-canons';g.events=[];
 g.nodes=g.nodes.filter(n=>['R0','A1','A2'].includes(n.id));
 g.nodes.forEach(n=>{if(n.kind==='action'){n.status='candidate';delete n.selectionBasis;}});
 g.edges=g.edges.filter(e=>g.nodes.some(n=>n.id===e.from)&&g.nodes.some(n=>n.id===e.to));return g;
}
function assertClear(ui){
 const cards=ui.root.querySelectorAll('.node').map(n=>({id:n.getAttribute('data-id'),p:xy(ui,n.getAttribute('data-id'))}));
 for(let i=0;i<cards.length;i++)for(let j=i+1;j<cards.length;j++){
  const a=cards[i],b=cards[j];
  assert(!(Math.abs(a.p[0]-b.p[0])<222&&Math.abs(a.p[1]-b.p[1])<72),'overlap: '+a.id+' / '+b.id);
 }
}
test('dense saved Action coordinates automatically separate the complete canon/Action pairs',async()=>{
 const ui=simulate(),g=denseFixture();await ui.loadFile(g);
 ui.host.rdgLayout.apply({type:'set_positions',positions:{R0:{x:48,y:300},A1:{x:468,y:190},A2:{x:468,y:314}}});
 assertClear(ui);above(ui,'A1','__canon__A1');above(ui,'A2','__canon__A2');
 const layout=JSON.parse(JSON.stringify(ui.host.rdgLayout.getDocument()));
 const restored=simulate();restored.host.rdgLayout.load(layout);await restored.loadFile(g);assertClear(restored);
 for(const id of ['R0','A1','A2','__canon__A1','__canon__A2'])assert.deepEqual(xy(restored,id),xy(ui,id),'stable restored '+id);
 ui.ids['edges-all'].onclick();assertClear(ui);
 ui.ids['variants-all'].onclick();assertClear(ui);ui.ids['variants-all'].onclick();assertClear(ui);
});
test('dragging and saving a repaired dense layout preserve every reflowed pair on reload',async()=>{
 const ui=simulate(),g=denseFixture();await ui.loadFile(g);
 ui.host.rdgLayout.apply({type:'set_positions',positions:{R0:{x:48,y:300},A1:{x:468,y:190},A2:{x:468,y:314}}});
 const owner=node(ui,'A1');
 ui.ids.canvas.listeners.pointerdown({button:0,pointerId:8,clientX:100,clientY:100,target:owner});
 ui.ids.canvas.listeners.pointermove({pointerId:8,clientX:100,clientY:120});
 ui.ids.canvas.listeners.pointerup({pointerId:8});assertClear(ui);
 const layout=JSON.parse(JSON.stringify(ui.host.rdgLayout.getDocument())),restored=simulate();
 restored.host.rdgLayout.load(layout);await restored.loadFile(g);assertClear(restored);
 for(const id of ['R0','A1','A2','__canon__A1','__canon__A2'])assert.deepEqual(xy(restored,id),xy(ui,id),'saved geometry '+id);
});

test('full detailed maps attach canons above original methods without affecting the R-only projection',async()=>{
 for(const slug of ['reference-prepared-planning-tree','reference-mixed-active-work','reference-action-time-plan']){
  const ui=simulate({useBundle:true});await ui.flush();await ui.host.rdgExplorer.openFull(slug);
  const rootIds=ui.root.querySelectorAll('.node').map(n=>n.getAttribute('data-id')).sort();
  ui.ids['edges-all'].onclick();
  const canons=ui.root.querySelectorAll('.node').filter(n=>n.classList.contains('canon'));
  assert(canons.length>0,slug+' has no canons');
  for(const canon of canons){
   const id=canon.getAttribute('data-id'),owner=id.slice('__canon__'.length);
   above(ui,owner,id);
   canon.listeners.click({stopPropagation(){}});
   assert.match(ui.info(),/Канонические ситуации/);assert.match(ui.info(),/не дочерняя R/);
  }
  assertClear(ui);
  ui.ids['edges-core'].onclick();
  assert.deepEqual(ui.root.querySelectorAll('.node').map(n=>n.getAttribute('data-id')).sort(),rootIds);
 }
});
