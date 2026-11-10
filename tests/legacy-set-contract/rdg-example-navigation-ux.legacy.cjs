const {test}=require('node:test'),assert=require('node:assert/strict');
const {simulate}=require('./viewer-test-helper.cjs');
const rows=u=>u.ids['graph-list'].children;
test('examples use four data-driven rows and a separate archive folder',async()=>{
 const u=simulate({useBundle:true});await u.flush();u.openFolder('examples');
 assert.deepEqual(rows(u).map(n=>n.getAttribute('data-set')),['example-prepared','context-prepared','context-working','example-working']);
 assert.match(rows(u)[0].textContent,/Готовый.*Учебный/);assert.match(rows(u)[0].textContent,/6 графов/);
 assert.match(rows(u).find(n=>n.getAttribute('data-set')==='example-working').textContent,/Рабочий.*Учебный/);assert.match(rows(u).find(n=>n.getAttribute('data-set')==='example-working').textContent,/10 графов/);
 assert(u.ids['folder-list'].children.some(n=>n.getAttribute('data-folder')==='examples/archive'));
 assert.equal(u.ids['folder-view-cards'],undefined);assert.equal(u.ids['example-map-working'],undefined);
});
test('a set row opens the current graph of graphs and its alternatives stay reachable',async()=>{
 const u=simulate({useBundle:true});await u.flush();
 for(const [id,count] of [['example-prepared',6],['example-working',5]]){
  u.openFolder('examples');await rows(u).find(n=>n.getAttribute('data-set')===id).onclick();
  assert.equal(u.ids.catalog.hidden,true);assert.equal(u.ids.content.hidden,false);
  assert.equal(u.root.querySelectorAll('.node').length,count);
  assert(u.root.querySelectorAll('.node').every(n=>n.classList.contains('graph')));
  assert.equal(u.ids['edges-core'].hidden,true);
  if(id==='example-working'){u.ids['variants-all'].onclick();assert.equal(u.root.querySelectorAll('.node').length,10);}
 }
});
test('set map opens the exact graph and returns with camera and search intact',async()=>{
 const u=simulate({useBundle:true});await u.flush();await u.openSet('example-prepared');
 u.ids.search.value='функцион';u.ids.search.oninput({target:u.ids.search});
 const camera=u.root.getElementById('scene').getAttribute('transform');
 const n=u.root.querySelectorAll('.node').find(n=>n.getAttribute('data-graph')==='reference-prepared-planning-tree');
 n.listeners.click({stopPropagation(){}});await u.flush();
 assert.equal(u.ids['example-set-map'].hidden,false);assert(u.root.querySelectorAll('.node').some(n=>n.getAttribute('data-id')==='R-PLAN'));
 await u.ids['example-set-map'].onclick();assert.equal(u.root.getElementById('scene').getAttribute('transform'),camera);assert.equal(u.ids.search.value,'функцион');
});
test('archives stay reachable without adding a special archive mode to the Viewer',async()=>{
 const u=simulate({useBundle:true});await u.flush();u.openFolder('examples/archive');
 assert(rows(u).some(n=>n.getAttribute('data-set')==='archive-booking'));
 await rows(u).find(n=>n.getAttribute('data-set')==='archive-booking').onclick();
 assert(u.root.querySelectorAll('.node').some(n=>n.getAttribute('data-graph')==='reference-complete-app'));
 assert.match(u.text(),/Архив/);assert.match(u.text(),/Учебный/);
});
