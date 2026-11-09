const {test}=require('node:test');
const assert=require('node:assert/strict');
const {simulate}=require('./viewer-test-helper.cjs');
const pick=(app,id)=>app.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')==='SH-'+id);
const walk=(root,predicate)=>{
 const list=[];const visit=n=>{if(predicate(n))list.push(n);for(const c of n.children||[])visit(c);};
 visit(root);return list;
};
test('showcase is one explicit archive set with all 14 R views and their exact relations',async()=>{
 const app=simulate({useBundle:true});await app.flush();await app.openSet('archive-booking');
 const catalog=app.host.rdgExplorer.getCatalog(),set=catalog.graphSets.find(s=>s.id==='archive-booking');
 assert.equal(set.members.length,14);assert.equal(app.root.querySelectorAll('.node').length,14);
 const expected=catalog.relations.filter(r=>set.members.includes(r.from)&&set.members.includes(r.to));
 assert.equal(walk(app.ids.canvas,n=>n.classList?.contains('edge')).length,expected.length);
 assert(app.root.querySelectorAll('.node').some(n=>n.getAttribute('data-graph')==='reference-complete-app'));
});

test('one Requirement remains same between successive graph files, 1..N differs from precisely two branches',async()=>{
 const app=simulate({useBundle:true});await app.flush();await app.openCard('reference-complete-app');app.ids['edges-all'].onclick();
 assert(pick(app,'R-APP'));
 pick(app,'R-FUNC').listeners.click({stopPropagation(){}});await app.flush();
 assert(pick(app,'R-FUNC'));assert(!pick(app,'R-APP'));
 pick(app,'V-BY-FEATURES').listeners.click({stopPropagation(){}});
 assert.match(app.info(),/1\.\.N/);
 pick(app,'D-CHOOSE-FEATURES').listeners.click({stopPropagation(){}});
 assert.match(app.info(),/2 Features/);
 pick(app,'R-FEAT-RES').listeners.click({stopPropagation(){}});await app.flush();
 assert(pick(app,'R-FEAT-RES'));assert(pick(app,'PR-STATE'));
 pick(app,'PR-STATE').listeners.click({stopPropagation(){}});
 assert.match(app.info(),/pending/);
 await app.ids['level-up'].onclick();assert(pick(app,'R-FUNC'));
 await app.ids['level-up'].onclick();assert(pick(app,'R-APP'));
 pick(app,'R-SCENARIOS').listeners.click({stopPropagation(){}});await app.flush();
 assert(pick(app,'R-SCENARIOS'));
 pick(app,'R-SCREATE').listeners.click({stopPropagation(){}});await app.flush();
 assert(pick(app,'R-SCREATE'));assert(!pick(app,'D-STATUS'));
 pick(app,'R-RESULT').listeners.click({stopPropagation(){}});await app.flush();assert(pick(app,'D-STATUS'));
});
test('showcase exposes all 17 named edge types in Viewer; edge inspector shows specific meaning',async()=>{
 const app=simulate({useBundle:true});await app.flush();await app.openSet('archive-booking');
 const names=['app','functionality','scenarios','realization','availability','reservation','scenario-create'];
 const seen=new Set();
 for(const name of names){
  const item=app.root.querySelectorAll('.node')
   .find(n=>n.getAttribute('data-graph')==='reference-complete-'+name);
  assert(item,'Map entry '+name);
  item.listeners.click({stopPropagation(){}});await app.flush();app.ids['edges-all'].onclick();
  await app.visitLevels(()=>{for(const n of walk(app.ids.canvas,x=>x.classList?.contains('edge-label')))
   seen.add(n.getAttribute('aria-label').split(' — ')[0]);});
  await app.ids.back.onclick();
 }
 assert.deepEqual([...seen].sort(),[
 'DRIVES','INTRODUCES','DERIVES','CONTEXT_FOR','APPLIES_TO','INFORMS','IDENTIFIES',
 'REVEALS_NEED','USES_VARIANT','OPTION_FOR','USES_PREPARED','PER_ITEM_MODEL',
 'GENERATES_ITEM_ROLE','INSTANCE_OF_MODEL','GOVERNED_BY_SHARED_CHOICE','QRPE_FOR','RECONSIDERS'
 ].sort());
 const scenario=app.root.querySelectorAll('.node')
   .find(n=>n.getAttribute('data-graph')==='reference-complete-scenario-create');
 scenario.listeners.click({stopPropagation(){}});await app.flush();app.ids['edges-all'].onclick();
 pick(app,'R-RESULT').listeners.click({stopPropagation(){}});await app.flush();
 pick(app,'D-STATUS').listeners.click({stopPropagation(){}});
 const owner=app.ids.info.children.find(n=>n.getAttribute?.('data-record-source')==='reference-complete-scenario-create');assert(owner);await owner.onclick();app.ids['edges-all'].onclick();
 const labels=walk(app.ids.canvas,x=>x.classList?.contains('edge-label'));
 const inform=labels.find(n=>n.getAttribute('aria-label').startsWith('INFORMS —'));
 assert(inform);
 inform.listeners.click({stopPropagation(){}});
 assert.match(app.info(),/Используется только содержание о потере ответа/);
 app.ids['edges-core'].onclick();
 assert.equal(app.ids['edges-core'].getAttribute('aria-pressed'),'true');
});
