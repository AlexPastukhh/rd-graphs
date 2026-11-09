'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process');
const {simulate}=require('./viewer-test-helper.cjs');
const projection=require('../tools/rdg-root-projection.js'),catalog=require('../tools/rdg-catalog.js');
const ROOT=path.resolve(__dirname,'..'),index=require('../graphs/index.json');
const fixture=require('./fixtures/root-migration-baseline.json');
const read=file=>JSON.parse(fs.readFileSync(path.join(ROOT,file),'utf8'));
const graph=slug=>read('graphs/'+index.graphs.find(x=>x.slug===slug).file);
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const current=['reference-prepared-planning-tree','reference-mixed-active-work'];
const nodes=u=>u.root.querySelectorAll('.node');
const ids=u=>nodes(u).map(n=>n.getAttribute('data-id'));
const settle=async()=>new Promise(resolve=>setImmediate(resolve));
const view=async slug=>{const u=simulate({useBundle:true});await u.flush();await u.host.rdgExplorer.openFull(slug);return u;};
const catalogWithSources=()=>({...index,graphs:index.graphs.map(x=>({...x,graph:graph(x.slug)}))});
test('Examples offers the two legacy roots and the current Action workflow, no blank set folders',async()=>{
 const model=catalog.normalizeCatalog(index);
 const cards=catalog.listFolder(model,'examples').filter(x=>x.kind==='full-graph');
 assert.deepEqual(cards.map(c=>c.slug).sort(),[...current,'reference-action-time-plan'].sort());
 assert.equal(catalog.listFolder(model,'examples').filter(x=>x.kind==='folder').length,1);
 const u=simulate({useBundle:true});await u.flush();u.openFolder('examples');
 const list=u.ids['graph-list'].children;
 assert.deepEqual(list.map(x=>x.getAttribute('data-full-root')).filter(Boolean).sort(),[...current,'reference-action-time-plan'].sort());
 for(const slug of current){await u.host.rdgExplorer.openFull(slug);assert(u.ids.catalog.hidden);u.ids.back.onclick();assert(!u.ids.catalog.hidden);}
 for(const folder of ['context-prepared','context-working','example-prepared','example-working','archive/archive-booking','archive/archive-features']){
  assert(!fs.existsSync(path.join(ROOT,'graphs/examples',folder)),folder+' is an empty leftover directory');
  assert(!index.folders.some(x=>x.id==='examples/'+folder));
 }
});
test('six historical tiny context graphs are archived exactly, not silently deleted or misrepresented as active',()=>{
 for(const role of ['prepared','working'])for(const level of ['root','current','alternative']){
  const slug='context-'+role+'-'+level,file='examples/'+slug+'/graph.json';
  const archived='examples/archive/'+slug+'/graph.json';
  const expected=fixture.sourceGraphSHA256[file];assert(expected,'old Context graph missing from baseline: '+file);
  assert.equal(digest(fs.readFileSync(path.join(ROOT,'graphs',archived))),expected,'archived bytes changed '+slug);
  assert.equal(index.graphs.find(x=>x.slug===slug).folder,'examples/archive');
  assert(index.graphs.find(x=>x.slug===slug).presentation.archived);
 }
 assert(index.fullGraphs.filter(x=>x.folder==='examples/archive'&&x.slug.startsWith('context-')).length===2);
});
test('each full example owns the same three field roles and local theory, with no cross-identity answers',()=>{
 const [r,w]=current.map(graph);
 for(const [g,slug] of [[r,current[0]],[w,current[1]]]){
  assert(g.readOnly&&g.exampleOnly&&g.contextFieldsComplete);
  assert.deepEqual(g.contextFields.map(x=>x.id).sort(),['accessibility','alternative-details','delivery']);
  assert(g.knowledgeSources.some(x=>x.id==='wai-planning'&&x.url.includes('w3.org/WAI')));
  for(const f of g.contextFields)for(const ref of f.sourceRefs||[])assert.equal(ref.graphSlug,slug);
 }
 assert(!r.nodes.some(n=>n.contextValue),'prepared template must not get a user/project answer');
 const answer=w.nodes.find(n=>n.id==='C-ACCESS-RECORDED');
 assert.deepEqual(answer.contextFieldRef,{graphSlug:current[1],fieldId:'accessibility'});
 assert.equal(answer.contextValue.scope,'project');
 assert(w.nodes.some(n=>n.id==='C-DEADLINE-UNMAPPED'&&!n.contextFieldRef&&!n.contextValue));
 assert(!r.nodes.some(n=>n.id==='C-ACCESS-RECORDED'));
});
test('Context CLI reports reused working answer and scenario details deferred; no third tiny full view required',()=>{
 for(const [slug,answer] of [[current[0],'missing'],[current[1],'known']]){
  const result=cp.spawnSync('python3',[path.join(ROOT,'tools/rdg-context.py'),'--fields','--root-graph-slug',slug],{encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  const out=JSON.parse(result.stdout),by=Object.fromEntries(out.fields.map(x=>[x.fieldRef.fieldId,x]));
  assert.deepEqual(Object.keys(by).sort(),['accessibility','alternative-details','delivery']);
  assert.equal(by.accessibility.state,'now');assert.equal(by.accessibility.answerStatus,answer);
  assert.equal(by.delivery.state,'now');assert.equal(by.delivery.answerStatus,'missing');
  assert.equal(by['alternative-details'].state,'later');assert.equal(by['alternative-details'].question,false);
  assert(out.fields.every(x=>x.fieldRef.graphSlug===slug));
 }
});
test('interpreted and link-only canon are real additional methods on a child R and do not rewrite pinned historical choices',async()=>{
 const pair=[['reference-prepared-feature-consistency','RF-2','reference-prepared-planning-tree'],
  ['reference-mixed-feature-consistency','R-ACT-2','reference-mixed-active-work']];
 for(const [slug,rid,owner] of pair){
  const g=graph(slug);assert.equal(g.rootRequirementId,rid);
  const options=g.nodes.filter(n=>n.id.startsWith('O-A11Y-'));
  assert.equal(options.length,2);
  assert.deepEqual(options.map(n=>n.canonBlock.preparation).sort(),['interpreted','link-only']);
  assert(g.edges.every(e=>e.type!=='OPTION_FOR'||e.from===rid));
  for(const n of options){
   assert(n.canonBlock.sourceRefs.some(x=>x.graphSlug===owner&&x.sourceId==='wai-planning'));
   assert(n.canonBlock.recommended[0].contextUses.some(x=>x.fieldRef.graphSlug===owner));
   assert.equal(n.canonBlock.fieldsComplete,n.canonBlock.preparation==='interpreted');
  }
  const u=simulate({useBundle:true});await u.flush();await u.openCard(slug);
  const target=nodes(u).find(n=>n.getAttribute('data-id')===options.find(x=>x.canonBlock.preparation==='link-only').id);
  assert(target);target.listeners.click({stopPropagation(){}});assert.match(u.info(),/пока только ссылка/);
  assert.match(u.info(),/W3C|WAI/);
 }
 const prepared=graph(current[0]),working=graph(current[1]);
 const one=id=>prepared.nodes.find(n=>n.id===id),two=id=>working.nodes.find(n=>n.id===id);
 assert.deepEqual(one('O-FEATURE').canonBlock,two('O-A').canonBlock);
 assert.deepEqual(one('O-SCENARIO').canonBlock,two('O-B').canonBlock);
 assert.deepEqual(two('D-A').selectionBasis.optionSnapshot.canonBlock,two('O-A').canonBlock);
 assert.equal(two('D-A').selectionBasis.optionSnapshot.preparedSource.version,'3');
 assert.equal(two('O-A').preparedSource.version,String(prepared.revision));
 assert.equal(index.sourceUpdateAlerts.length,0);
});
test('full graph has unique links and visibly different selected, potential and refinement semantics',async()=>{
 const data=catalogWithSources();const [ready,working]=current.map(slug=>projection.project(data,slug));
 assert.equal(ready.nodes.length,6);assert.equal(ready.edges.length,5);
 assert.equal(working.nodes.length,40);assert.equal(working.edges.length,39);
 for(const projected of [ready,working]){
  const keys=projected.edges.map(e=>[e.from,e.to,e.kind,e.causeId].join(':'));
  assert.equal(new Set(keys).size,keys.length,'duplicate projection arrows');
 }
 assert(working.edges.some(e=>e.kind==='refinement'&&e.from==='R0'&&e.to==='R-COMP'));
 assert(!working.edges.some(e=>e.kind==='selected'&&e.from==='R0'&&e.to==='R-COMP'));
 const u=await view(current[1]);
 assert(ids(u).includes('R-COMP'));assert(!ids(u).some(x=>x.startsWith('__cause__')));
 assert(!ids(u).includes('P-RF-DEEP'));
 u.ids['variants-all'].onclick();assert(ids(u).includes('P-RF-DEEP'));
 u.ids['edges-all'].onclick();assert(ids(u).some(x=>x.startsWith('__cause__')));
 u.ids['edges-core'].onclick();assert(!ids(u).some(x=>x.startsWith('__cause__')));
});
test('DERIVES composite stays in the original requirement column in both view modes',async()=>{
 const u=await view('reference-mixed-active-work');
 const xpos=id=>{const node=nodes(u).find(x=>x.getAttribute('data-id')===id);assert(node,id);return Number(node.getAttribute('transform').match(/translate\(([-\d.]+)/)[1]);};
 for(const full of [false,true]){
  if(full)u.ids['edges-all'].onclick();
  assert.equal(xpos('R0'),xpos('R-COMP'),'refinement must not be drawn as a new child generation');
  assert(xpos('R-ACT-1')>xpos('R-COMP'),'real introduced R should be in next generation');
 }
});
