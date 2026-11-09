const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {simulate}=require('./viewer-test-helper.cjs');
const ROOT=path.resolve(__dirname,'..');
const read=slug=>JSON.parse(fs.readFileSync(path.join(ROOT,'graphs/examples',slug,'graph.json'),'utf8'));
const ids=u=>u.root.querySelectorAll('.node').map(n=>n.getAttribute('data-id'));
const node=(u,id)=>u.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')===id);
const click=(u,id)=>{const n=node(u,id);assert(n,'not displayed: '+id);n.listeners.click({stopPropagation(){}});};
test('single-R context lists stay inline without a group header',async()=>{
 const baseline=read('reference-mixed-active-work');
 const ui=simulate({useBundle:true});await ui.flush();await ui.openCard(baseline.id);
 for(const [group,member] of [['COL-ROOT-TECH','R-TECH'],['COL-ROOT-DEADLINE','R-DEADLINE'],['COL-ROOT-INTEGRATION','R-LEGACY-API']]){
  assert(!ids(ui).includes('__collection__'+group));assert(ids(ui).includes(member));
  click(ui,member);assert(ui.info().includes(member));
 }
 assert.deepEqual(read(baseline.id),baseline);
});
test('canonical situations are visible blocks and inspectable for selected and unselected options',async()=>{
 for(const [slug,canonId] of [['reference-prepared-planning-tree','O-FEATURE'],['reference-mixed-contextual-split','O-A']]){
  const ui=simulate({useBundle:true});await ui.flush();if(slug==='reference-mixed-contextual-split')await ui.openLevel('reference-mixed-active-work','R-COMP');else await ui.openCard(slug);
  const cid='__canon__'+canonId;
  assert(ids(ui).includes(cid),slug+': canonical block hidden');
  const card=node(ui,cid);assert(card.textContent.includes('КАНОН'));
  assert(card.textContent.includes('+')&&card.textContent.includes('−'));
  click(ui,cid);
  assert(ui.info().includes('Канонические ситуации (+)'));
  assert(ui.info().includes('Канонические ситуации (−)'));
  assert(ui.info().includes('Блок канона'));
  assert(!read(slug).nodes.some(n=>n.id===cid),'view-only canon must not be persisted as R/D');
 }
 const ui=simulate({useBundle:true});await ui.flush();await ui.openCard('reference-mixed-active-work');
 assert(!ids(ui).includes('__canon__O-B'),'unselected branch hidden until toggle');
 ui.ids['variants-all'].onclick();
 assert(ids(ui).includes('__canon__O-B'));
});
test('ten prospective candidate R preserve reversible collection and candidate status',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();await ui.openCard('reference-mixed-active-work');
 ui.ids['variants-all'].onclick();
 const col='__collection__COL-FEATURE';
 assert(ids(ui).includes(col));
 click(ui,col);
 assert(!ids(ui).includes(col),'expanded group header disappears');
 assert(ids(ui).includes('R-PREV-FEATURE-1'));
 click(ui,'R-PREV-FEATURE-1');
 assert(ui.info().includes('candidate'));
 ui.ids['collections-collapse'].onclick();
 assert(!ids(ui).includes('R-PREV-FEATURE-1'));assert(ids(ui).includes(col));
});
