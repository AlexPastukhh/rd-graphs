'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const {parsePreparedLens,createSession}=require('../tools/rdg-lens-session.cjs');
const graph=JSON.parse(fs.readFileSync(path.join(__dirname,'../tools/rdg-agent-lenses/preserve.json'),'utf8'));
const root=graph.rootRequirementId;
const canon=graph.objects.find(n=>n.kind==='canon');
test('preserve has actual draw/skip Actions and local canon criteria, with no artificial subgoals',()=>{
 const parsed=parsePreparedLens(graph);
 assert.deepEqual(parsed.actions.map(a=>a.id).sort(),['A-PRESERVE-DRAW','A-PRESERVE-SKIP']);
 assert.equal(graph.nodes.filter(n=>n.kind==='requirement').length,1);
 assert.equal(graph.nodes[0].id,root);
 assert.deepEqual(canon.arguments[0].condition.all[0].any.map(c=>c.id),['C1','C2']);
 assert.equal(canon.arguments[0].condition.all[1].id,'C3');
 assert.deepEqual(graph.exclusionGroups[0].actionIds,['A-PRESERVE-DRAW','A-PRESERVE-SKIP']);
 assert(graph.nodes.filter(n=>n.kind==='action').every(n=>n.status==='candidate'));
});
test('canonical logical evaluator covers all eight combinations and unknown without executing work',()=>{
 const code="from importlib.machinery import SourceFileLoader;import json,sys;"+
  "m=SourceFileLoader('preserve_logic',sys.argv[1]).load_module();"+
  "c=json.load(sys.stdin)['objects'][0]['arguments'][0]['condition'];"+
  "print(json.dumps([m.evaluate_condition(c,{f'C{i+1}':{'result':'match' if v else 'no-match'} for i,v in enumerate(bits)}) for bits in [(False,False,False),(False,False,True),(False,True,False),(False,True,True),(True,False,False),(True,False,True),(True,True,False),(True,True,True)]]+[m.evaluate_condition(c,{'C1':{'result':'no-match'},'C2':{'result':'match'},'C3':{'result':'unknown'}})]))";
 const r=spawnSync('python3',['-c',code,path.join(__dirname,'../tools/rdg-core-model.py')],{input:JSON.stringify(graph),encoding:'utf8'});
 assert.equal(r.status,0,r.stderr);
 assert.deepEqual(JSON.parse(r.stdout),['no-match','no-match','no-match','match','no-match','match','no-match','match','unknown']);
});
test('opening guidance and claiming a root result never accepts selection, storage or execution',()=>{
 const before=JSON.stringify(graph);
 const bindings={targetGraphId:'test-target-only',targetRequirementId:'test-focus',relevantInputs:{fixture:true}};
 const session=createSession(graph,bindings,{rootAssessment:{requirementId:root,result:'achieved',evidenceRefs:['fixture:synthetic-assessment']}});
 assert.equal(session.rootResult,'unknown');assert.equal(session.persisted,false);
 assert.deepEqual(session.materialGraphOperations,[]);assert.deepEqual(session.graph.events,[]);
 assert(session.unassessedOrStaleCanons.includes('K-PRESERVE/ARG-PRESERVE'));
 assert.throws(()=>createSession(graph,bindings,{canonAssessments:[{actionId:'A-PRESERVE-DRAW',caseId:'ARG-PRESERVE',result:'applicable'}]}),/EXPLICIT_TYPED_WORKING_SITUATION/);
 assert.equal(JSON.stringify(graph),before);
});
