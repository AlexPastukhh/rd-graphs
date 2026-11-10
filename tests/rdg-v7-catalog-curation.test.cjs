const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {simulate}=require('./viewer-test-helper.cjs');
const ROOT=path.resolve(__dirname,'..');
const read=p=>JSON.parse(fs.readFileSync(path.join(ROOT,p),'utf8'));
const modern=['reference-prepared-planning-tree','reference-mixed-active-work'];
test('all 102 graph source files (including archived originals) retain valid unique nodes/edges and valid root refs without rewriting protected files',()=>{
 const manifest=read('graphs/index.json');
 assert.equal(manifest.graphs.length,102);
 assert.equal(manifest.graphs.filter(x=>x.group==='2d').length,48);
 assert.equal(manifest.graphs.filter(x=>x.group==='examples').length,52);
 assert.equal(manifest.graphs.filter(x=>x.group==='workspaces').length,2);
 for(const item of manifest.graphs){
  const g=read('graphs/'+item.file);
  const ids=new Set(g.nodes.map(x=>x.id));
  assert.equal(ids.size,g.nodes.length,item.slug+' duplicate nodes');
  assert.equal(new Set(g.edges.map(x=>x.id)).size,g.edges.length,item.slug+' duplicate edges');
  for(const edge of g.edges)assert(ids.has(edge.from)&&ids.has(edge.to),item.slug+' dangling '+edge.id);
  if(g.rootRequirementId)assert(g.nodes.some(n=>n.id===g.rootRequirementId&&n.kind==='requirement'),item.slug+' missing root');
 }
});
test('old archived Decision/Option examples cannot be selected in the active Viewer',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();
 for(const slug of modern){
  await assert.rejects(ui.openCard(slug),/Неизвестный граф|OLD_GRAPH_MODEL_DISABLED/);
  assert(ui.host.rdgExplorer.getCatalog().graphs.every(x=>x.slug!==slug));
 }
});
test('two archived v7 source examples still carry canonical cases and explicit QRPE slots on every R/D/option',()=>{
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
