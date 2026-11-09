const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const text=p=>fs.readFileSync(path.join(root,p),'utf8');
const graph=slug=>JSON.parse(text('graphs/'+(slug==='try-it'?'workspaces':'examples')+'/'+slug+'/graph.json'));
const rootSlug='reference-feature-root',level='reference-reusable-vs-concrete';
const features=['AUTH','CATALOG','CART','PAYMENT'];
const child=id=>'reference-feature-'+id.toLowerCase();
const children=features.map(child);
const all=[rootSlug,level,...children];
const node=(g,id)=>g.nodes.find(n=>n.id===id);
const related=JSON.parse(text('graphs/index.json')).relations;
const link=(source,target,rid)=>related.find(x=>x.from===source&&x.to===target&&x.requirementId===rid);

test('all six hierarchical graphs are read-only demos with exactly one indicated root Requirement',()=>{
 for(const slug of all) {
  const g=graph(slug),first=g.nodes[0];
  assert.equal(g.id,slug);assert.equal(g.readOnly,true);assert.equal(g.exampleOnly,true);
  assert.equal(g.hypothetical,true);assert.equal(g.selectedInProject,false);
  assert.equal(first.id,g.rootRequirementId);assert.equal(first.kind,'requirement');
  assert.equal(g.nodes.filter(n=>n.id===g.rootRequirementId).length,1);
  assert.deepEqual(g.events,[]);
  assert(g.nodes.every(n=>n.id.startsWith('DEMO-')));
  const ids=new Set(g.nodes.map(n=>n.id));
  for(const e of g.edges) {
   assert(ids.has(e.from)&&ids.has(e.to),slug+' dangling edge: '+e.id);
   if(e.type==='INTRODUCES')assert(ids.has(e.parent));
  }
 }
});

test('parent level delegates a neutral Requirement, not a Feature choice or TM',()=>{
 const g=graph(rootSlug),childR=node(g,'DEMO-R-FUNCTIONALITY');
 assert(childR);
 assert.equal(childR.title,'Расписать функционал');
 assert.equal(childR.nextGraphSlug,undefined,'Do not wire navigation manually');
 assert(link(rootSlug,level,childR.id),'Child graph derived from INTRODUCES + same R identity');
 assert(g.edges.some(e=>e.type==='INTRODUCES'&&e.to===childR.id&&e.parent===g.rootRequirementId));
 assert(!JSON.stringify(g).includes('TM-FEATURE'));
 assert(!g.nodes.some(n=>n.id==='DEMO-D-BY-FEATURE'));
});

test('R «Расписать функционал» owns both prepared options, one sample choice, four R',()=>{
 const g=graph(level);
 assert.equal(g.rootRequirementId,'DEMO-R-FUNCTIONALITY');
 assert.equal(g.parentGraphSlug,undefined,'Parent not manually encoded');
 assert(link(rootSlug,level,g.rootRequirementId));
 const prepared=node(g,'DEMO-V-BY-FEATURE');
 assert.equal(prepared.kind,'variant');
 assert.equal(prepared.status,'reusable-unselected');
 assert.equal(prepared.repetition.mode,'PER_ITEM');
 assert.equal(prepared.repetition.cardinality,'1..N');
 assert.equal(prepared.repetition.preparedModelId,'TM-FEATURE');
 assert(node(g,'DEMO-V-OTHER').status==='reusable-unselected');
 assert.equal(g.edges.filter(e=>e.type==='OPTION_FOR'&&e.from===g.rootRequirementId).length,2);
 const selected=node(g,'DEMO-D-BY-FEATURE');
 assert.equal(selected.status,'selected-in-example-only');
 assert.equal(selected.selectedInProject,false);
 assert.equal(selected.concreteBranchCount,4);
 assert.equal(selected.modelApplicationCount,4);
 assert.equal(selected.usesPreparedDecompositionRef,'DEMO-V-BY-FEATURE');
 const introductions=g.edges.filter(e=>e.type==='INTRODUCES');
 assert.equal(introductions.length,4);
 assert(introductions.every(e=>e.from===selected.id&&e.parent===g.rootRequirementId));
 assert.equal(new Set(introductions.map(e=>e.to)).size,4);
 assert(!introductions.some(e=>e.from===prepared.id));
 for(const id of features)assert(introductions.some(e=>e.to==='DEMO-R-FEATURE-'+id));
});

test('each concrete child Requirement becomes identical root ID at its own level',()=>{
 const middle=graph(level);
 for(const id of features){
  const r='DEMO-R-FEATURE-'+id;
  const childR=node(middle,r);
  const leaf=graph(child(id));
  assert.equal(childR.nextGraphSlug,undefined);
  assert(link(level,child(id),r),'Matched R introduced in level 2');
  assert.equal(leaf.rootRequirementId,r);
  assert.equal(leaf.nodes[0].id,r);
  assert.equal(leaf.parentGraphSlug,undefined);
  assert.equal(leaf.identitySpace,middle.identitySpace);
  assert.equal(leaf.nodes.filter(n=>n.kind==='decision').length,0);
  assert(leaf.nodes.some(n=>n.preparedModelRef==='TM-FEATURE'&&n.status==='reusable-unselected'));
 }
});

test('index and bootstrap expose only the entry level, without inventing new prompts',()=>{
 const manifest=JSON.parse(text('graphs/index.json'));
 const bundled=text('tools/rd-graph-data.js');
 const src=text('work-kit/modules/rdg.work.examples.module.md');
 assert.equal(manifest.graphs.length,100);
 assert.equal(manifest.graphs.filter(v=>v.catalogHidden).length,66);
 assert.equal(manifest.graphs.find(v=>v.slug===rootSlug).catalogHidden,false);
 assert(all.slice(1).every(slug=>manifest.graphs.find(v=>v.slug===slug)?.catalogHidden));
 assert(bundled.includes(rootSlug));
 assert(src.includes(rootSlug)&&src.includes(level));
 const boot=text('work-kit/prompts/rdg.work.bootstrap.prompt.md');
 assert(boot.includes('[[module:rdg.work.examples]]'));
 const original=text('docs/examples/requirements-decisions-graph-examples-v0.2.source.md');
 assert(!original.includes('DEMO-V-BY-FEATURE'));
 const live=graph('try-it');
 assert.equal(live.revision,1);assert.equal(live.nodes.length,1);assert.equal(live.events.length,0);
});

test('writer blocks changes to all reference levels without creating locks',()=>{
 const patch=path.join(root,'graphs/workspaces/try-it/patches/accept-example.DO-NOT-APPLY.json');
 for(const slug of all) {
  const f=path.join(root,'graphs','examples',slug,'graph.json');
  const lock=path.join(path.dirname(f),'.graph-apply.lock');
  assert(!fs.existsSync(lock));
  const result=spawnSync('python3',[path.join(root,'tools/graph-apply.py'),
   '--graph',f,'--patch',patch,'--dry-run'],{encoding:'utf8'});
  assert.notEqual(result.status,0);assert.match(result.stderr,/READ_ONLY_GRAPH/);
  assert(!fs.existsSync(lock));
 }
});
