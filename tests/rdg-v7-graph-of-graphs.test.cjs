const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {simulate}=require('./viewer-test-helper.cjs');
const BASE=path.join(__dirname,'..'),load=s=>JSON.parse(fs.readFileSync(path.join(BASE,'graphs/examples',s,'graph.json'),'utf8'));
const ready=load('reference-prepared-planning-tree'),work=load('reference-mixed-active-work');
const idx=JSON.parse(fs.readFileSync(path.join(BASE,'graphs/index.json'),'utf8'));
const origin=new Map(ready.nodes.map(n=>[n.id,n]));
const dest=new Map(work.nodes.map(n=>[n.id,n]));
const nodes=ui=>ui.root.querySelectorAll('.node');
const find=(ui,id)=>nodes(ui).find(n=>n.getAttribute('data-id')===id);
const click=(ui,id)=>{const n=find(ui,id);assert(n,'missing visual '+id);n.listeners.click({stopPropagation(){}});};
const sort=v=>Array.isArray(v)?v.map(sort):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sort(v[k])])):v;
test('prepared and work preserve mapped data while goal applicability remains an educational assumption',()=>{
 assert.equal(origin.get('R-PLAN').title,dest.get('R0').title);
 const ref=work.preparedGraphSetReference;
 assert.equal(ref.copyStatus,'illustrative-equivalent-not-executed');
 assert.equal(ref.applicabilityStatus,'candidate-unverified');
 assert.equal(ref.sourceRootRevision,ready.revision);
 assert.equal(Object.keys(ref.nodeIdMap).length,ready.nodes.length);
 assert.equal(Object.keys(ref.edgeIdMap).length,ready.edges.length);
 assert.equal(ref.sourceGraphSlugs.length,4);
 assert.equal(ref.illustrativeTargetGraphSlugs.length,4);
 assert.equal(Object.keys(ref.sourceChildOwnedNodeIdMap).length,0);
 assert.equal(Object.keys(ref.sourceChildGraphSlugMap).length,3);
 for(const n of ready.nodes){
  const mapped=ref.nodeIdMap[n.id];
  assert(dest.has(mapped),'lost prepared source node '+n.id);
  const copy=dest.get(mapped);
  assert.equal(copy.kind,n.kind);
  if(n.kind==='option'){
   assert.deepEqual(copy.canonBlock,n.canonBlock);
   assert.equal(copy.preparedSource.graphSlug,ready.id);
   assert.equal(copy.preparedSource.version,String(ready.revision));
   assert.equal(copy.preparedSource.canonHash,crypto.createHash('sha256').update(JSON.stringify(sort(n.canonBlock))).digest('hex'));
  }
  if(n.id!=='R-PLAN'&&!['O-FEATURE','O-SCENARIO'].includes(n.id)){
   assert.equal(copy.sourcePreparedNodeId,n.id);
   assert.equal(copy.status,n.status);
  }
 }
 for(const e of ready.edges){
  const to=ref.edgeIdMap[e.id],edge=work.edges.find(x=>x.id===to);
  assert(edge,'lost source edge '+e.id);
  assert.equal(edge.from,ref.nodeIdMap[e.from]);
  assert.equal(edge.to,ref.nodeIdMap[e.to]);
  assert.equal(edge.type,e.type);
 }
 for(const [src,dst] of Object.entries(ref.sourceChildGraphSlugMap)){
  const a=load(src),b=load(dst);
  assert.equal(a.rootRequirementId.replace(/^P-/,'')===b.rootRequirementId.replace(/^P-/,''),true);
  for(const o of a.nodes.filter(n=>n.kind==='option'&&!n.projectionOf)){
   const mapped=ref.sourceChildOwnedNodeIdMap[o.id];
   const counterpart=b.nodes.find(n=>n.id===mapped);
   assert(counterpart,'lost extra prepared option '+o.id);
   assert.deepEqual(counterpart.canonBlock,o.canonBlock);
  }
 }
 assert.equal(ready.revision,6);assert.equal(ready.nodes.filter(n=>n.kind==='decision').length,0);
 const d=dest.get('D-A');
 assert.equal(d.status,'selected-in-example-only');
 assert.equal(d.selectionBasis.optionSnapshot.preparedSource.version,'3');
 assert.equal(work.revision,8);
 const old=fs.readFileSync(path.join(BASE,'graphs/source-versions/reference-prepared-planning-tree-rev3.json'));
 assert.equal(crypto.createHash('sha256').update(old).digest('hex'),'5247eadf78d1423e19f031a11fc68f453676a71d89b479a0fc41c32a45d7151f');
 assert.equal(JSON.parse(old).revision,3);
 assert.equal(idx.sourceUpdateAlerts.length,0);
 assert.deepEqual(d.selectionBasis.compositeSnapshot.history,[dest.get('R-COMP').history[0]]);
});
test('ten potential relations are typed, exact-option sourced, and do not invent chosen Decisions',()=>{
 const expected=[
 ['reference-prepared-planning-tree','reference-prepared-feature-path','O-FEATURE','RF-1'],
 ['reference-prepared-planning-tree','reference-prepared-feature-consistency','O-FEATURE','RF-2'],
 ['reference-prepared-planning-tree','reference-prepared-scenario-consistency','O-SCENARIO','RS-2'],
 ['reference-prepared-planning-tree','reference-prepared-scenario-path','O-SCENARIO','RS-1'],
 ['reference-prepared-feature-path','reference-prepared-feature-depth','RF-1-O2','RF-DEEP'],
 ['reference-mixed-active-work','reference-mixed-planned-feature','O-A','P-RF-1'],
 ['reference-mixed-active-work','reference-mixed-planned-feature-consistency','O-A','P-RF-2'],
 ['reference-mixed-active-work','reference-mixed-planned-scenario-consistency','O-B','P-RS-2'],
 ['reference-mixed-active-work','reference-mixed-planned-scenario','O-B','P-RS-1'],
 ['reference-mixed-planned-feature','reference-mixed-planned-feature-depth','P-RF-1-O2','P-RF-DEEP']
 ];
 assert.equal(idx.relations.filter(x=>x.relationKind==='potential'&&!x.from.startsWith('context-')).length,10);
 for(const [a,b,o,r] of expected){
  const rel=idx.relations.find(x=>x.from===a&&x.to===b);
  assert(rel,'missing prospective link '+a+' -> '+b);
  assert.equal(rel.relationKind,'potential');
  assert.equal(rel.originatingOptionId,o);assert.equal(rel.requirementId,r);
  assert.equal(rel.introducedByDecisionId,'');
  const src=load(a),dst=load(b);
  assert(src.edges.some(e=>e.id===rel.outcomeEdgeId&&e.type==='OUTCOME_OF'&&e.from===o&&e.to===r));
  assert.deepEqual(dst.expansionOf,{graphSlug:a,nodeId:r});
  assert.deepEqual(dst.nodes.find(x=>x.id===r).projectionOf,{graphSlug:a,nodeId:r});
  assert.equal(dst.nodes.filter(n=>n.kind==='decision').length,0);
 }
 assert.equal(idx.projectContexts['rdg-example-mixed-v7'],undefined);
});
test('archived Decision/Option prepared and working examples cannot open in the active viewer',async()=>{
 for(const old of [ready.id,work.id,'reference-prepared-feature-path','reference-mixed-planned-scenario']){
  const ui=simulate({useBundle:true});await ui.flush();
  await assert.rejects(ui.openCard(old),/Неизвестный граф|OLD_GRAPH_MODEL_DISABLED/);
  assert(!ui.host.rdgExplorer.getCatalog().graphs.some(g=>g.slug===old));
 }
});
test('canon research advice belongs to a real method; no third pseudo-option or executed experiment',()=>{
 for(const [pSlug,wSlug,pRoot,wRoot,pseudo,option,advice] of [
  ['reference-prepared-feature-path','reference-mixed-planned-feature','RF-1','P-RF-1','RF-1-EXPLORE','RF-1-O2','нарисовать альтернативные'],
  ['reference-prepared-scenario-path','reference-mixed-planned-scenario','RS-1','P-RS-1','RS-1-TRIAL','RS-1-O2','изолированные испытания']
 ]){
  const p=load(pSlug),w=load(wSlug);
  assert.equal(p.nodes.filter(n=>n.kind==='option').length,2);
  assert.equal(w.nodes.filter(n=>n.kind==='option').length,2);
  assert(!p.nodes.some(n=>n.id===pseudo));
  assert(!w.nodes.some(n=>n.id==='P-'+pseudo));
  assert(!p.edges.some(e=>e.to===pseudo));
  const original=p.nodes.find(n=>n.id===option),adapted=w.nodes.find(n=>n.id==='P-'+option);
  assert.deepEqual(original.canonBlock,adapted.canonBlock);
  assert(original.canonBlock.recommended.some(c=>c.text.includes(advice)));
  assert.equal(adapted.preparedSource.graphSlug,'reference-prepared-planning-tree');
  assert.equal(adapted.preparedSource.version,String(ready.revision));
  assert.equal(p.nodes.find(n=>n.id===option).projectionOf.graphSlug,'reference-prepared-planning-tree');
  assert.equal(w.nodes.find(n=>n.id==='P-'+option).projectionOf.graphSlug,'reference-mixed-active-work');
 }
});
test('catalog warns on changed prepared canon/revision without rewriting a T1 snapshot',()=>{
 const cp=require('node:child_process');
 const script=[
 'import json,copy,importlib.util',
 'spec=importlib.util.spec_from_file_location("idx","tools/graph-index.py")',
 'm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)',
 'path="graphs/examples/reference-prepared-planning-tree/graph.json"',
 'g=json.load(open(path))',
 'g["revision"]+=1',
 'next(n for n in g["nodes"] if n["id"]=="O-FEATURE")["canonBlock"]["recommended"][0]["text"]+=" CHANGED"',
 'ix,payload=m.build_catalog({"examples/reference-prepared-planning-tree/graph.json":g})',
 'assert ix["sourceUpdateAlerts"]',
 'assert any(a["nodeId"]=="O-A" and a["reason"]=="available-version-differs-from-pin" for a in ix["sourceUpdateAlerts"])',
 'assert payload["sourceUpdateAlerts"]==[] # archive source updates are not active browser warnings',
 'assert json.load(open("graphs/examples/reference-mixed-active-work/graph.json"))["nodes"][14]["id"]',
 'print("SOURCE_CHANGED_WARNING")'
 ].join('\n');
 const result=cp.spawnSync('python3',['-c',script],{cwd:BASE,encoding:'utf8',timeout:60000});
 assert.equal(result.status,0,result.stderr);
 assert(result.stdout.includes('SOURCE_CHANGED_WARNING'));
 assert.equal(idx.sourceUpdateAlerts.length,0,'unchanged source must be unflagged');
});

test('a forged candidate graph root cannot masquerade as an existing Requirement projection',()=>{
 const cp=require('node:child_process');
 const py=[
  'import json,copy,importlib.util',
  'spec=importlib.util.spec_from_file_location("rdg_index","tools/graph-index.py")',
  'm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)',
  'p="graphs/examples/reference-prepared-feature-path/graph.json"',
  'g=json.load(open(p))',
  'g["nodes"][0]["projectionOf"]={"graphSlug":"reference-prepared-planning-tree","nodeId":"R-NOT-RF-1"}',
  'try: m.build_catalog({"examples/reference-prepared-feature-path/graph.json":g})',
  'except ValueError: print("REJECTED")',
  'else: raise AssertionError("forged owner was accepted")'
 ].join('\n');
 const ret=cp.spawnSync('python3',['-c',py],{cwd:BASE,encoding:'utf8',timeout:60000});
 assert.equal(ret.status,0,ret.stderr);
 assert(ret.stdout.includes('REJECTED'));
});
test('potential graph links remain read-only index projections, never writable workspace operations',()=>{
 const cp=require('node:child_process');
 const py=[
  'import json,importlib.util',
  'spec=importlib.util.spec_from_file_location("rdg_index","tools/graph-index.py")',
  'm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)',
  'g=json.load(open("graphs/examples/reference-mixed-planned-feature/graph.json"))',
  'g["readOnly"]=False',
  'idx,_=m.build_catalog({"examples/reference-mixed-planned-feature/graph.json":g})',
  'assert not any(r["relationKind"]=="potential" and r["to"]=="reference-mixed-planned-feature" for r in idx["relations"])',
  'print("NO_WRITABLE_POTENTIAL")'
 ].join('\n');
 const ret=cp.spawnSync('python3',['-c',py],{cwd:BASE,encoding:'utf8',timeout:60000});
 assert.equal(ret.status,0,ret.stderr);
 assert(ret.stdout.includes('NO_WRITABLE_POTENTIAL'));
});
