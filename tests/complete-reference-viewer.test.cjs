const {test}=require('node:test');
const assert=require('node:assert/strict');
const {simulate}=require('./viewer-test-helper.cjs');
const pick=(app,id)=>app.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')==='SH-'+id);
const walk=(root,predicate)=>{
 const list=[];const visit=n=>{if(predicate(n))list.push(n);for(const c of n.children||[])visit(c);};
 visit(root);return list;
};
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
