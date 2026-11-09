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
 const examples=catalog.graphs.filter(x=>x.group==='examples'&&x.catalogLegacy&&x.slug!=='reference-module-units'&&!x.slug.startsWith('context-')&&!x.slug.startsWith('reference-unit-')&&!x.slug.startsWith('reference-complete-')&&!['reference-prepared-planning-tree','reference-mixed-active-work','reference-mixed-feature-availability','reference-mixed-feature-consistency','reference-prepared-feature-path','reference-prepared-scenario-path','reference-prepared-feature-depth','reference-mixed-planned-feature','reference-mixed-planned-scenario','reference-mixed-planned-feature-depth'].includes(x.slug));
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
