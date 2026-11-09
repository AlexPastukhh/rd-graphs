'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const P=require('../tools/rdg-visual-projection.js');
function fixture(){
 const graph={identitySpace:'space',nodes:[],objects:[],externalActions:[]},plan={schemaVersion:3,revision:1,steps:[],mainStepIds:[],forks:[],timeConstraints:[]};
 const step=id=>{graph.nodes.push({id,kind:'action',title:id});plan.steps.push({id,kind:'action',title:id,state:'possible',ref:{packageId:'owner',identitySpace:'space',nodeId:id}});return id;};
 for(let f=0;f<30;f++)plan.forks.push({id:'F'+f,title:'Fork '+f,afterStepId:null,startAt:'2026-11-06',end:{title:'Common boundary',at:'2026-11-07'},cases:Array.from({length:3},(_,c)=>({id:'F'+f+'C'+c,title:'Case '+c,decisionIds:[],stepIds:Array.from({length:10},(_,i)=>step('F'+f+'C'+c+'S'+i))}))});
 plan.mainStepIds=[step('COMMON')];return {graph,plan};
}
test('many forks display one lane each and one common continuation, without a Cartesian product or owner mutation',()=>{
 const {plan,graph}=fixture(),before=JSON.stringify({plan,graph});
 for(let c=0;c<3;c++){
  const view=P.temporalPlan(plan,graph,{}, {shownCases:Object.fromEntries(plan.forks.map(f=>[f.id,f.cases[c].id]))},'owner');
  assert.equal(plan.steps.length,901);assert.equal(view.placements.length,301);assert.equal(view.road.length,361);
  assert.equal(new Set(view.shownStepIds).size,301);assert.equal(view.shownStepIds.filter(i=>i==='COMMON').length,1);
  assert.equal(view.road.filter(r=>r.type==='join').length,30);assert.equal(view.factsCreated,false);
 }
 assert.equal(JSON.stringify({plan,graph}),before);
});
test('optional end is a Plan boundary; its date does not change graph facts or create an execution status',()=>{
 const {plan,graph}=fixture();delete plan.forks[0].end;
 const view=P.temporalPlan(plan,graph,{}, {},'owner');assert(!view.road.some(r=>r.type==='join'&&r.forkId==='F0'));assert.equal(view.placements.at(-1).step.id,'COMMON');
 assert.throws(()=>P.temporalPlan(plan,graph,{}, {shownCases:{missing:'C'}},'owner'),/PLAN_VIEW_CASES/);
});
