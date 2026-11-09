const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {simulate}=require('./viewer-test-helper.cjs');
const ROOT=path.resolve(__dirname,'..');
const read=p=>JSON.parse(fs.readFileSync(path.join(ROOT,p),'utf8'));
const modern=['reference-prepared-planning-tree','reference-mixed-active-work'];
test('all 100 graphs have unique nodes/edges and valid root refs without rewriting protected files',()=>{
 const manifest=read('graphs/index.json');
 assert.equal(manifest.graphs.length,100);
 assert.equal(manifest.graphs.filter(x=>x.group==='2d').length,48);
 assert.equal(manifest.graphs.filter(x=>x.group==='examples').length,51);
 assert.equal(manifest.graphs.filter(x=>x.group==='workspaces').length,1);
 for(const item of manifest.graphs){
  const g=read('graphs/'+item.file);
  const ids=new Set(g.nodes.map(x=>x.id));
  assert.equal(ids.size,g.nodes.length,item.slug+' duplicate nodes');
  assert.equal(new Set(g.edges.map(x=>x.id)).size,g.edges.length,item.slug+' duplicate edges');
  for(const edge of g.edges)assert(ids.has(edge.from)&&ids.has(edge.to),item.slug+' dangling '+edge.id);
  if(g.rootRequirementId)assert(g.nodes.some(n=>n.id===g.rootRequirementId&&n.kind==='requirement'),item.slug+' missing root');
 }
});
test('modern examples are data-driven sets; old illustrations remain marked and accessible in archive',async()=>{
 const manifest=read('graphs/index.json');const entry=x=>manifest.graphs.find(g=>g.slug===x);
 for(const slug of modern){assert.equal(entry(slug).catalogLegacy,false);assert.equal(entry(slug).catalogHidden,false);}
 assert.equal(manifest.graphs.filter(x=>x.group==='examples'&&x.catalogLegacy).length,29);
 const ui=simulate({useBundle:true});await ui.flush();ui.openFolder('examples');
 assert.deepEqual(ui.ids['graph-list'].children.map(n=>n.getAttribute('data-set')),['example-prepared','context-prepared','context-working','example-working']);
 ui.openFolder('examples/archive');assert(ui.ids['graph-list'].children.some(n=>n.getAttribute('data-set')==='archive-booking'));
 await ui.openSet('archive-booking');assert(ui.root.querySelectorAll('.node').some(n=>n.getAttribute('data-graph')==='reference-complete-app'));
});

test('modern option badge, full canon text, selected D canon and QRPE are discoverable',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();
 await ui.openCard('reference-prepared-planning-tree');
 const opts=()=>ui.root.querySelectorAll('.node');
 let option=opts().find(x=>x.getAttribute('data-id')==='O-FEATURE');
 assert(option);
 assert.match(option.textContent,/канон \+2\/−2/);
 option.listeners.click({stopPropagation(){}});
 assert.match(ui.info(),/Канонические ситуации \(\+\)/);
 assert.match(ui.info(),/Канонические ситуации \(−\)/);
 assert.match(ui.info(),/Нужна независимая проработка частей/);
 assert.match(ui.info(),/Нет записанных QRPE/);
 ui.ids.back.onclick();
 await ui.openLevel('reference-mixed-active-work','R-COMP');
 const d=opts().find(x=>x.getAttribute('data-id')==='D-A');assert(d);
 d.listeners.click({stopPropagation(){}});
 assert.match(ui.info(),/Канон выбранного варианта По Features/);
 assert.match(ui.info(),/Критичны сквозные зависимости/);
 assert.match(ui.info(),/QRPE/);
});
test('two active v7 examples carry canonical cases and explicit QRPE slots on every R/D/option',()=>{
 for(const slug of modern){
  const g=read('graphs/examples/'+slug+'/graph.json');
  assert.equal(g.readOnly,true);
  assert.equal(g.exampleOnly,true);
  const options=g.nodes.filter(n=>n.kind==='option');
  assert.equal(options.length,slug==='reference-prepared-planning-tree'?12:13);
  for(const node of g.nodes.filter(n=>['requirement','decision','option'].includes(n.kind)))
   assert(Array.isArray(node.qrpe),'missing QRPE on '+slug+':'+node.id);
  for(const option of options){
   assert(option.canonBlock&&Array.isArray(option.canonBlock.recommended));
   assert(Array.isArray(option.canonBlock.contraindicated));
   assert(option.canonBlock.recommended.length>=1&&option.canonBlock.contraindicated.length>=1);
   for(const side of ['recommended','contraindicated'])
    assert(option.canonBlock[side].every(x=>x.text&&x.id));
  }
 }
});
