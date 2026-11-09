'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {simulate}=require('./viewer-test-helper.cjs');
const projector=require('../tools/rdg-root-projection.js');

function walk(node,predicate,out=[]) {
  if(predicate(node))out.push(node);
  for(const child of node.children||[])walk(child,predicate,out);
  return out;
}
async function full(slug) {
  const ui=simulate({useBundle:true});
  await ui.flush();
  await ui.host.rdgExplorer.openFull(slug);
  return ui;
}
function clickNode(ui,id) {
  const node=ui.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')===id);
  assert(node,'missing node '+id);
  node.listeners.click({stopPropagation(){}});
  return ui.info();
}
function clickableEdge(ui,part) {
  const edges=walk(ui.ids.canvas,n=>n.tag==='path'&&
    typeof n.getAttribute==='function'&&
    (n.getAttribute('data-edge-id')||'').includes(part));
  assert(edges.length,'missing edge '+part);
  edges[0].listeners.click({stopPropagation(){}});
  return ui.info();
}
test('full prepared Option inspector retains kind, true ID, canon, origin and sources',async()=>{
  const ui=await full('reference-prepared-planning-tree');
  ui.ids['edges-all'].onclick();
  const s=clickNode(ui,'__cause__reference-prepared-planning-tree::O-FEATURE');
  assert.match(s,/Option/);
  assert.match(s,/O-FEATURE/);
  assert.match(s,/Канонические ситуации/);
  assert.match(s,/Происхождение/);
  assert.doesNotMatch(s,/Requirement ID: __cause__/);
  assert.doesNotMatch(s,/Потенциальная R/);
});
test('full working Decision inspector shows real selection basis, T1, QRPE, no Requirement alias',async()=>{
  const ui=await full('reference-mixed-active-work');
  ui.ids['edges-all'].onclick();
  const s=clickNode(ui,'__cause__reference-mixed-active-work::D-A');
  assert.match(s,/Decision/);
  assert.match(s,/Основание выбора/);
  assert.match(s,/R-ACT-2/);
  assert.match(s,/O-FEATURE-minus-1/);
  assert.match(s,/QR-A/);
  assert.match(s,/T1/);
  assert.doesNotMatch(s,/Requirement ID: __cause__/);
});
test('full detailed relation inspector names actual endpoints R to D and cause to R',async()=>{
  const ui=await full('reference-mixed-active-work');
  ui.ids['edges-all'].onclick();
  const s=clickableEdge(ui,'__attachment__reference-mixed-feature-consistency::DRV-ACT2');
  assert.match(s,/Requirement.*Decision|R .* → Decision /);
  assert.doesNotMatch(s,/Причинный переход R: R-COMP → D-A/);
});
test('DERIVES refinement stays visible across detail and coverage, never selected child',async()=>{
  const ui=await full('reference-mixed-active-work');
  const visible=()=>walk(ui.ids.canvas,n=>n.tag==='path'&&
    n.getAttribute?.('data-relation-kind')==='refinement');
  assert.equal(visible().length,1,'R-only refinement');
  ui.ids['edges-all'].onclick();
  assert.equal(visible().length,1,'detailed refinement');
  assert.match(clickableEdge(ui,'refinement'),/Уточнение|уточнение/);
  ui.ids['variants-all'].onclick();
  assert.equal(visible().length,1,'all-branches detailed refinement');
  ui.ids['edges-core'].onclick();
  assert.equal(visible().length,1,'all-branches R-only refinement');
});
test('example-only D is active only with all isolation guards, including no main adoption',()=>{
  const valid={exampleOnly:true,hypothetical:true,readOnly:true,selectedInProject:false};
  assert.equal(projector.decisionActive({status:'selected-in-example-only'},valid),true);
  for(const key of ['exampleOnly','hypothetical','readOnly','selectedInProject']){
    const broken={...valid,[key]:key==='selectedInProject'?true:false};
    assert.equal(projector.decisionActive({status:'selected-in-example-only'},broken),false,key);
  }
  assert.equal(projector.decisionActive({status:'committed'},{exampleOnly:false}),true);
  assert.equal(projector.decisionActive({status:'committed'},{exampleOnly:true}),false);
});
test('full detail does not mark invalid example-only Decision or Option as accepted',async()=>{
  const ui=simulate({useBundle:true});
  await ui.flush();
  const item=ui.context.RDG_EMBEDDED_GRAPHS.graphs.find(x=>x.slug==='reference-mixed-active-work');
  assert(item);
  item.graph.hypothetical=false;
  // Catalog and data bundle have distinct objects: invalidate the actual owner.
  ui.host.rdgExplorer.getCatalog().graphs.find(x=>x.slug==='reference-mixed-active-work').graph.hypothetical=false;
  await ui.host.rdgExplorer.openFull('reference-mixed-active-work');
  ui.ids['variants-all'].onclick(); // invalid teaching D remains potential, not main
  ui.ids['edges-all'].onclick();
  const decision=ui.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')==='__cause__reference-mixed-active-work::D-A');
  assert(decision,'D remains discoverable as option under visible refined R');
  assert.equal(decision.getAttribute('data-branch-state'),'potential');
  const option=ui.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')==='__cause__reference-mixed-active-work::O-A');
  assert(option);
  assert.equal(option.getAttribute('data-branch-state'),'potential');
});
