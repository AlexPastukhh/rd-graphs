const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const read=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const catalog=read('graphs/index.json');
const relations=catalog.relations;
const originalRelations=relations.filter(x=>x.identitySpace==='demo:feature-functional');
const bySlug=new Map(catalog.graphs.map(x=>[x.slug,x]));
const readGraph=slug=>read('graphs/'+bySlug.get(slug).file);
const scope='demo:feature-functional';

test('relation index records five exact R identities, not links between similarly named files',()=>{
 assert.equal(originalRelations.length,5);
 const expected=[
  ['reference-feature-root','reference-reusable-vs-concrete','DEMO-R-FUNCTIONALITY'],
  ['reference-reusable-vs-concrete','reference-feature-auth','DEMO-R-FEATURE-AUTH'],
  ['reference-reusable-vs-concrete','reference-feature-catalog','DEMO-R-FEATURE-CATALOG'],
  ['reference-reusable-vs-concrete','reference-feature-cart','DEMO-R-FEATURE-CART'],
  ['reference-reusable-vs-concrete','reference-feature-payment','DEMO-R-FEATURE-PAYMENT'],
 ];
 for(const [from,to,id] of expected){
  const link=originalRelations.find(r=>r.from===from&&r.to===to&&r.requirementId===id);
  assert(link,from+' → '+to);
  const src=readGraph(from),dst=readGraph(to);
  assert.equal(src.identitySpace,scope);
  assert.equal(dst.identitySpace,scope);
  assert.equal(dst.rootRequirementId,id);
  const incoming=src.edges.find(e=>e.type==='INTRODUCES'&&e.to===id);
  assert(incoming);
  assert.equal(link.introducedByDecisionId,incoming.from);
  assert.equal(link.introductionEdgeId,incoming.id);
  assert(src.nodes.some(n=>n.kind==='requirement'&&n.id===id));
  assert(dst.nodes.some(n=>n.kind==='requirement'&&n.id===id));
  assert(!src.nodes.some(n=>n.nextGraphSlug!==undefined));
  assert.equal(dst.parentGraphSlug,undefined);
 }
 assert(originalRelations.every(r=>r.identitySpace===scope));
});

test('examples map has six connected graphs and four isolated; 2D template map has no invented arrows',()=>{
 const examples=catalog.graphs.filter(x=>x.group==='examples'&&x.catalogLegacy&&x.slug!=='reference-module-units'&&!x.slug.startsWith('reference-unit-')&&!x.slug.startsWith('reference-complete-')&&!['reference-prepared-planning-tree','reference-mixed-active-work','reference-mixed-feature-availability','reference-mixed-feature-consistency','reference-prepared-feature-path','reference-prepared-scenario-path','reference-prepared-feature-depth','reference-mixed-planned-feature','reference-mixed-planned-scenario','reference-mixed-planned-feature-depth'].includes(x.slug));
 const template=catalog.graphs.filter(x=>x.group==='2d'&&x.planningScale==='module');
 assert.equal(examples.length,10);assert.equal(template.length,10);
 const original=relations.filter(r=>r.identitySpace==='demo:feature-functional');
 const participants=new Set(original.flatMap(r=>[r.from,r.to]));
 assert.equal(examples.filter(g=>participants.has(g.slug)).length,6);
 assert.deepEqual(examples.filter(g=>!participants.has(g.slug)).map(g=>g.slug).sort(),[
  'example','reference-app-definition','reference-behavior-review','reference-delegation-status']);
 assert(original.every(r=>r.fromGroup==='examples'&&r.toGroup==='examples'));
 assert(relations.filter(r=>r.fromGroup==='2d').every(r=>r.relationKind==='prepared'));
 assert(template.every(g=>!participants.has(g.slug)));
 const bundled=fs.readFileSync(path.join(root,'tools/rd-graph-data.js'),'utf8');
 const context={};vm.runInNewContext(bundled,context);
 assert.equal(context.RDG_EMBEDDED_GRAPHS.relations.length,relations.length);
 assert.deepEqual(JSON.parse(JSON.stringify(context.RDG_EMBEDDED_GRAPHS.relations)),relations);
});

test('identity is scoped, not assumed by equal title or same folder; no hard-coded graph arrows',()=>{
 const seen=new Set();
 for(const entry of catalog.graphs){
  const g=readGraph(entry.slug);
  if(!g.identitySpace||!g.rootRequirementId)continue;
  const key=g.identitySpace+'\x1f'+g.rootRequirementId;
  assert(!seen.has(key),'Duplicate root identity: '+key);seen.add(key);
 }
 for(const e of catalog.graphs.filter(x=>x.group==='examples')){
  const g=readGraph(e.slug);
  assert(!JSON.stringify(g).includes('"nextGraphSlug"'));
  assert(!JSON.stringify(g).includes('"parentGraphSlug"'));
 }
 for(const relation of relations){
  const src=readGraph(relation.from),dst=readGraph(relation.to);
  assert.notEqual(src.id,dst.id);
  assert.equal(src.identitySpace,dst.identitySpace);
  assert.equal(relation.requirementId,dst.rootRequirementId);
  if(['selected','prepared'].includes(relation.relationKind)){
   const edge=src.edges.find(e=>e.id===relation.introductionEdgeId);
   assert(edge&&edge.type==='INTRODUCES'&&edge.to===relation.requirementId);
  }else if(relation.relationKind==='derived'){
   assert(src.edges.some(e=>e.id===relation.derivationEdgeId&&e.type==='DERIVES'&&e.to===relation.requirementId));
  }else assert.equal(dst.expansionOf.graphSlug,src.id);
 }
});

const {simulate}=require('./viewer-test-helper.cjs');
const walk=(root,predicate)=>{const out=[];const visit=n=>{if(predicate(n))out.push(n);for(const c of n.children||[])visit(c);};visit(root);return out;};
test('every explicit set names the main R and opens the same record',async()=>{
 const app=simulate({useBundle:true});await app.flush();
 for(const set of catalog.graphSets){
  await app.openSet(set.id);
  if(!app.ids['variants-all'].hidden&&app.ids['variants-all'].getAttribute('aria-pressed')==='false')app.ids['variants-all'].onclick();
  const nodes=app.root.querySelectorAll('.node');assert.equal(nodes.length,set.members.length);
  for(const node of nodes){const g=readGraph(node.getAttribute('data-graph')),r=g.nodes.find(n=>n.id===g.rootRequirementId)||g.nodes[0];assert(node.children.some(c=>c.tag==='title'&&c.textContent.includes(r.title)));}
 }
 await app.openSet('archive-booking');
 app.root.querySelectorAll('.node').find(n=>n.getAttribute('data-graph')==='reference-complete-functionality').listeners.click({stopPropagation(){}});
 await app.flush();assert.equal(app.ids['bar-title'].textContent,'Расписать функционал');
 assert(app.root.querySelectorAll('.node').some(n=>n.getAttribute('data-id')==='SH-R-FUNC'));
});

test('set arrow explains child identity and introducing decision, then opens that graph',async()=>{
 const app=simulate({useBundle:true});await app.flush();await app.openSet('archive-booking');
 const edge=walk(app.ids.canvas,n=>n.classList?.contains('edge-label')).find(n=>n.getAttribute('data-requirement')==='SH-R-FUNC');
 assert(edge);edge.listeners.keydown({key:'Enter',preventDefault(){},stopPropagation(){}});
 for(const phrase of ['Расписать функционал','Спланировать приложение бронирования','SH-R-FUNC','SH-D-APP-SPLIT','Выделить функционал, сценарии и реализационные требования'])assert(app.info().includes(phrase),phrase);
 assert.match(app.info(),/не задаёт очередь выполнения/);
 await app.ids.info.children.find(n=>n.getAttribute?.('data-open-related')).onclick();
 assert.equal(app.ids['bar-title'].textContent,'Расписать функционал');
});

test('all explicit set labels avoid graph blocks and other labels; fit covers all geometry',async()=>{
 const app=simulate({useBundle:true});await app.flush();
 const box=n=>{const [tx,ty]=n.getAttribute('transform').match(/-?\d+(?:\.\d+)?/g).map(Number),r=n.children.find(c=>c.tag==='rect');return{x:tx+Number(r.getAttribute('x')||0),y:ty+Number(r.getAttribute('y')||0),w:Number(r.getAttribute('width')),h:Number(r.getAttribute('height'))};};
 const overlap=(a,b)=>a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y;
 for(const set of catalog.graphSets){
  await app.openSet(set.id);
  if(!app.ids['variants-all'].hidden&&app.ids['variants-all'].getAttribute('aria-pressed')==='false')app.ids['variants-all'].onclick();
  const nodes=walk(app.ids.canvas,n=>n.classList?.contains('node')).map(box),labels=walk(app.ids.canvas,n=>n.classList?.contains('edge-label')).map(box);
  for(let i=0;i<labels.length;i++){assert(nodes.every(n=>!overlap(labels[i],n)),set.id);assert(labels.slice(i+1).every(n=>!overlap(labels[i],n)),set.id);}
  app.ids.fit.onclick();const [x,y,k]=app.root.getElementById('scene').getAttribute('transform').match(/-?\d+(?:\.\d+)?/g).map(Number);
  for(const b of [...nodes,...labels])assert(b.x*k+x>=-1&&b.y*k+y>=-1&&(b.x+b.w)*k+x<=801&&(b.y+b.h)*k+y<=501,set.id+' clipped');
 }
});

test('legacy DEMO levels project roots to exactly one existing R owner',()=>{
 const pairs=[
  ['reference-reusable-vs-concrete','reference-feature-root','DEMO-R-FUNCTIONALITY'],
  ['reference-feature-auth','reference-reusable-vs-concrete','DEMO-R-FEATURE-AUTH'],
  ['reference-feature-catalog','reference-reusable-vs-concrete','DEMO-R-FEATURE-CATALOG'],
  ['reference-feature-cart','reference-reusable-vs-concrete','DEMO-R-FEATURE-CART'],
  ['reference-feature-payment','reference-reusable-vs-concrete','DEMO-R-FEATURE-PAYMENT'],
 ];
 for(const [child,owner,id] of pairs){
  const graph=readGraph(child),origin=readGraph(owner);
  assert.equal(graph.rootRequirementId,id);
  const node=graph.nodes.find(n=>n.id===id),original=origin.nodes.find(n=>n.id===id);
  assert(node&&original);
  assert.deepEqual(node.projectionOf,{graphSlug:owner,nodeId:id});
  assert.equal(graph.identitySpace,origin.identitySpace);
  assert.equal(node.title,original.title);
  assert(relations.some(r=>r.from===owner&&r.to===child&&r.requirementId===id));
 }
});
