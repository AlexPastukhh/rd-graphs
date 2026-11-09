const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {simulate}=require('./viewer-test-helper.cjs');
const ROOT=path.resolve(__dirname,'..');
const load=slug=>JSON.parse(fs.readFileSync(path.join(ROOT,'graphs/examples',slug,'graph.json'),'utf8'));
const all=ui=>ui.root.querySelectorAll('.node');
const byId=(ui,id)=>all(ui).find(x=>x.getAttribute('data-id')===id);
const click=(ui,id)=>{const n=byId(ui,id);assert(n,'missing rendered node '+id);n.listeners.click({stopPropagation(){}});};
test('canon inspector retains typed IDs, cross-file references, categories and evidence limits',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();await ui.openCard('reference-mixed-active-work');
 ui.ids['variants-all'].onclick();click(ui,'__canon__O-C');
 const text=ui.info();
 for(const field of ['O-C-plus-1','O-C-minus-1','R-TECH','COL-ROOT-TECH','архитектура','не подтверждена']){
   assert(text.includes(field),field+' is missing from inspector');
 }
 click(ui,'R-COMP');await ui.flush();click(ui,'D-A');
 for(const field of ['Основание выбора','Осознанно принятые противопоказания',
                     'Оставленные открытыми QRPE','O-FEATURE-minus-1','R-TECH']){
   assert(ui.info().includes(field),'selected D missing '+field);
 }
 const linked=simulate({useBundle:true});await linked.flush();await linked.openLevel('reference-mixed-active-work','R-COMP');
 click(linked,'R-ACT-1');await linked.flush();click(linked,'__canon__O-ACT-1');
 for(const field of ['O-ACT-1-plus-1','reference-mixed-active-work / COL-ROOT-TECH','R-TECH']){
   assert(linked.info().includes(field),'cross-file case missing '+field);
 }
});
test('QRPE visible as badges; direct tutorial D gets explicit disclaimer without fake canon',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();await ui.openLevel('reference-mixed-active-work','R-COMP');
 assert(byId(ui,'D-A').textContent.includes('QRPE !2'));
 assert(byId(ui,'__canon__O-A').textContent.includes('ещё…'),
  'compact labels must show that canon has more cases; full content is in inspector');
 const before=load('reference-mixed-active-work');
 click(ui,'R-ACT-2');await ui.flush();
 assert(byId(ui,'D-ACT-2').textContent.includes('QRPE ✓1'));
 click(ui,'D-ACT-2');
 assert(ui.info().includes('ПРЯМОЕ УЧЕБНОЕ D'));
 assert(ui.info().includes('не представлены')); 
 assert(!byId(ui,'__canon__D-ACT-2'),'direct D has no artificial canon card');
 assert.deepEqual(load('reference-mixed-active-work'),before);
});
test('Collections retain original candidate R and remain reversible with group labels',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();await ui.openCard('reference-mixed-active-work');
 ui.ids['variants-all'].onclick();
 const id='__collection__COL-FEATURE';
 assert(byId(ui,id).textContent.includes('Группа'));
 click(ui,id);
 assert(!byId(ui,id),'expanded group header disappears'); 
 assert(byId(ui,'R-PREV-FEATURE-1'));
 ui.ids['collections-collapse'].onclick();assert(!byId(ui,'R-PREV-FEATURE-1'));assert(byId(ui,id));
});
