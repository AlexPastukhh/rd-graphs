'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {simulate}=require('./viewer-test-helper.cjs');
const ids=u=>u.root.querySelectorAll('.node').map(n=>n.getAttribute('data-id'));
async function viewer(slug){const u=simulate({useBundle:true});await u.flush();await u.host.rdgExplorer.openFull(slug);return u;}
test('folder catalog directly lists full-graph roots without graph-set intermediate cards',async()=>{
 const u=await viewer('reference-prepared-planning-tree');const entries=u.host.rdgExplorer.getCatalog();
 assert.equal(entries.fullGraphs.length,18);
 assert(entries.fullGraphs.some(e=>e.slug==='reference-prepared-planning-tree'));
 assert(u.ids.catalog.hidden);
 assert.deepEqual(new Set(ids(u)),new Set(['R-PLAN','RF-1','RF-2','RS-1','RS-2','RF-DEEP']));
 assert(ids(u).every(id=>!id.startsWith('__cause__')));
 u.ids.back.onclick();assert(!u.ids.catalog.hidden);
 const cards=u.ids['graph-list'].children;assert(cards.some(e=>e.getAttribute('data-full-root')==='reference-prepared-planning-tree'));
 assert(cards.every(e=>e.getAttribute('data-set')===null));
});
test('working view is accepted R-only by default and independent coverage/detail switches',async()=>{
 const u=await viewer('reference-mixed-active-work');
 assert(ids(u).includes('R-ACT-1'));
 assert(!ids(u).includes('P-RF-DEEP'));
 assert(ids(u).every(x=>!x.startsWith('__cause__')));
 u.ids['variants-all'].onclick();assert(ids(u).includes('P-RF-DEEP'));assert(ids(u).includes('R-ACT-1'));
 assert(ids(u).every(x=>!x.startsWith('__cause__')));
 u.ids['edges-all'].onclick();assert(ids(u).some(x=>x.startsWith('__cause__')));
 u.ids['variants-all'].onclick();assert(!ids(u).includes('P-RF-DEEP'));assert(ids(u).some(x=>x.startsWith('__cause__')));
 u.ids['edges-core'].onclick();assert(ids(u).every(x=>!x.startsWith('__cause__')));
});
test('click R opens its own one-wave display, and back returns full root',async()=>{
 const u=await viewer('reference-prepared-planning-tree');const n=u.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')==='RF-1');
 n.listeners.click({stopPropagation(){}});await u.flush();assert(ids(u).includes('RF-1'));
 assert(ids(u).includes('RF-1-O1'));
 assert(u.host.rdgLayout.graphKey().includes('reference-prepared-feature-path'), 'opened child own expansion graph');
 assert(!ids(u).includes('R-PLAN'));
 u.ids.back.onclick();await u.flush();assert(ids(u).includes('R-PLAN'));assert(ids(u).includes('RF-DEEP'));
});
test('refinement is not a duplicate synthetic Requirement; noncausal sources accessible',async()=>{
 const u=await viewer('reference-mixed-active-work');
 assert(!ids(u).some(x=>x.startsWith('__cause__')));
 assert(ids(u).includes('R-COMP'));
 assert(u.info().includes('Связанное представление')||u.info().includes('Requirements'));
});
test('full scoped context fields available without a setId',async()=>{
 const u=await viewer('context-working-root');u.ids['context-fields'].onclick();
 assert(u.info().includes('Общий контекст проекта'));
 assert(u.info().includes('Контекст полного графа'));
});
test('detailed full graph de-duplicates projected Options from separate R files',async()=>{
 const u=await viewer('reference-prepared-planning-tree');
 u.ids['edges-all'].onclick();
 const options=ids(u).filter(x=>x.startsWith('__cause__')&&x.includes('RF-1-O1'));
 assert.equal(options.length,1,'a projected Option should not appear twice in the same full graph');
 assert.equal(options[0],'__cause__reference-prepared-planning-tree::RF-1-O1');
 assert(ids(u).includes('__cause__reference-prepared-planning-tree::RF-1-O2'));
});
