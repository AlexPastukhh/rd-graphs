const {test}=require('node:test'),assert=require('node:assert/strict');
const core=require('../tools/rdg-state.js');
function input(){
 const graph={id:'g',identitySpace:'project',contextFields:[{id:'f',title:'Field',explanation:'Meaning'}],contextFieldsComplete:true,
 contextUses:[{fieldRef:{graphSlug:'g',fieldId:'f'},purpose:'Use'}],nodes:[
 {id:'C',kind:'context',title:'Answer',contextFieldRef:{graphSlug:'g',fieldId:'f'},contextValue:{value:'Earlier',source:'User',scope:'project'}}]};
 return {graph,items:[{slug:'g',group:'workspaces',graph}]};
}
test('current context is one value, never a dated answer timeline',()=>{
 const {graph,items}=input(),read=(scope='project')=>core.collect({items,graphSlug:'g',scope}).fields[0];
 assert.equal(read().answer.value,'Earlier');assert.equal(read().answerStatus,'known');
 graph.nodes[0].contextValue={value:'Updated',source:'User clarification',scope:'project'};
 assert.equal(read().answer.value,'Updated');assert(!('recordedAt' in read().answer));
 graph.nodes[0].contextValue.scope='branch/a';
 assert.equal(read().answerStatus,'needs-assessment');assert.equal(read('branch/a').answerStatus,'known');
 delete graph.nodes[0].contextValue;
 assert.equal(read().answerStatus,'missing');assert.equal(read().question,true);
});
test('dated legacy answers are rejected; unscoped owner rejected; unavailable condition unknown',()=>{
 const {graph,items}=input();graph.nodes[0].contextValue.recordedAt='2026-02-31T12:00:00Z';
 assert.throws(()=>core.validate(items),/no history or dates/);
 delete graph.nodes[0].contextValue.recordedAt;
 graph.nodes[0].contextAnswers=[{id:'T1',value:'Old',recordedAt:'2026-10-01'}];
 assert.throws(()=>core.validate(items),/legacy contextAnswers/);
 delete graph.nodes[0].contextAnswers;delete graph.identitySpace;
 assert.throws(()=>core.validate(items),/project-scoped/);
 graph.identitySpace='project';graph.contextUses[0].when={allSelected:[{graphSlug:'unavailable',optionId:'O'}]};
 assert(core.validate(items,{partial:true}));assert.throws(()=>core.validate(items),/unavailable/);
 const r=core.collect({items,graphSlug:'g'});assert.equal(r.fields[0].state,'unknown');assert.equal(r.fields[0].question,false);
});
test('unsupported root-level canon usages fail instead of silently disappearing from the field list',()=>{
 const {graph,items}=input();
 graph.nodes.push({id:'O',kind:'option',title:'Option',canonBlock:{recommended:[],contraindicated:[],
  contextUses:[{fieldRef:{graphSlug:'g',fieldId:'f'},purpose:'Hidden root usage'}]}});
 assert.throws(()=>core.validate(items),/contextUses belongs on graph, node or canon case/);
 delete graph.nodes.at(-1).canonBlock.contextUses;
 graph.nodes.at(-1).canonBlock.recommended.push({id:'case',contextUses:[{fieldRef:{graphSlug:'g',fieldId:'f'},purpose:'Case use'}]});
 assert.equal(core.validate(items),true);
 assert(core.collect({items,graphSlug:'g'}).fields[0].usages.some(u=>u.location==='O/recommended/case'));
});
test('multiple conditions retain all consumers; one current usage wins without merging definitions by name',()=>{
 const {graph,items}=input();graph.nodes.push({id:'O',kind:'option',title:'Option'});
 graph.contextUses.push({fieldRef:{graphSlug:'g',fieldId:'f'},purpose:'Only after selection',when:{allSelected:[{graphSlug:'g',optionId:'O'}]}});
 const r=core.collect({items,graphSlug:'g'}).fields[0];assert.equal(r.usages.length,2);assert.equal(r.state,'now');assert(r.usages.some(u=>u.state==='later'));
});
test('unrelated freeform record does not hide missing current field',()=>{
 const {graph,items}=input();delete graph.nodes[0].contextValue;
 graph.nodes.push({id:'C2',kind:'context',title:'Unrelated note'});
 const r=core.collect({items,graphSlug:'g'});
 assert.equal(r.fields[0].answerStatus,'missing');assert.equal(r.fields[0].nextAction,'check-known-context-or-ask');
 assert.equal(r.fields[0].question,true);assert.equal(r.freeformCandidates.length,1);
});
