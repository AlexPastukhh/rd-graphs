'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const f=require('./fixtures/rdg-action-lens-pilot-v1.json');
const {createSession,parsePreparedLens,hash}=require('../tools/rdg-lens-session.cjs');
const {eligible,capture,lastRelevant}=require('../tools/rdg-lens-research.cjs');
const lens=f.lensDefinitions.find(x=>x.id==='L-MAINT');
const dry=f.lensDefinitions.find(x=>x.id==='L-DRY');
const args=action=>({targetGraphId:'project-A',targetRequirementId:'R0',
 targetActionId:action,arguments:{reviewType:'maintenance',locale:'lt'},
 relevantInputs:{costEvidence:'cost-v1',externalSourceVersion:1}});
const claim={persistRequested:true,materialUnresolvedWork:true,costlyToRecreate:true,
 likelyFutureUse:true,notAlreadyAvailableInTarget:true,stableEnoughForReuse:true,
 maintenanceWorthwhile:true,reason:'Open QRPE for unselected strategy A1 needs later evidence'};
test('prepared Lens is a connected ordinary RDG graph; separate A1/A2 sessions do not write',()=>{
 assert.equal(parsePreparedLens(lens).rootRequirement.id,'R-L-MAINT');
 const a1=createSession(lens,args('A1'));const a2=createSession(lens,args('A2'));
 assert.equal(a1.kind,'working-lens-graph');assert.equal(a1.persisted,false);
 assert.equal(a1.materialGraphOperations.length,0);
 assert.equal(a1.rootResult,'unknown');
 assert.notEqual(a1.bindings.targetActionId,a2.bindings.targetActionId);
 assert(a1.unresolvedQrpe.length>0);
 assert.equal(eligible(a1,null).save,false);
});
test('material unresolved canon/QRPE can be saved once, but obsolete and duplicate work is skipped',()=>{
 const pending=createSession(lens,args('A1'));
 const saved=capture(pending,claim,'2026-10-17T12:00:00Z');
 assert.equal(saved.saved,true);
 assert.equal(saved.workingGraph.bindings.targetActionId,'A1');
 assert.equal(saved.metadata.unresolvedQrpe.length,pending.unresolvedQrpe.length);
 assert.equal(capture(pending,{...claim,notAlreadyAvailableInTarget:false},'2026-10-17T12:00:00Z').saved,false);
 assert.equal(capture(pending,{...claim,stableEnoughForReuse:false},'2026-10-17T12:00:00Z').saved,false);
 assert.equal(capture(pending,{...claim,persistRequested:false},'2026-10-17T12:00:00Z').saved,false);
});
test('lookup finds the latest *saved* matching A1, not A2 or latest actual unsaved run',()=>{
 const s1=capture(createSession(lens,args('A1')),claim,'2026-10-17T12:00:00Z');
 const s2=capture(createSession(lens,args('A2')),claim,'2026-10-17T13:00:00Z');
 const s3=capture(createSession(lens,args('A1')),claim,'2026-10-17T15:00:00Z');
 const metadata=[s1.metadata,s2.metadata,s3.metadata];
 const query={...args('A1'),lensId:lens.id,definitionDigest:hash(lens),evidenceStillValid:true};
 const result=lastRelevant(metadata,query);
 assert.equal(result.found,true);assert.equal(result.metadata.recordedAt,s3.metadata.recordedAt);
 assert.equal(result.fullGraphLoaded,false);assert.equal(result.reuseStatus,'candidate-for-reuse');
 assert.match(result.disclaimer,/СОХРАНЁННОЕ/);
 assert.equal(lastRelevant(metadata,{...query,targetActionId:'A3'}).found,false);
 const stale=lastRelevant(metadata,{...query,relevantInputs:{costEvidence:'cost-v2'},evidenceStillValid:false});
 assert.equal(stale.reuseStatus,'needs-reassessment');
 assert(stale.reasons.includes('relevant-inputs-changed'));
 assert(stale.reasons.includes('evidence-freshness-unverified'));
});
test('no root achievement from an unsupported canon, stale assessment, or open QRPE',()=>{
 const a=createSession(dry,args('A1'),{rootAssessment:{requirementId:'R-L-DRY',result:'achieved',evidenceRefs:['e:1']}});
 assert.equal(a.rootResult,'unknown');
 const blocked=createSession(dry,args('A1'),{rootAssessment:{requirementId:'R-L-DRY',
  result:'blocked',evidenceRefs:['e:blocked']}});
 assert.equal(blocked.rootResult,'unknown');
 assert.equal(blocked.rootAssessment.result,'blocked');
 const id=dry.actions.find(a=>a.canonBlock?.recommended?.length).id;
 assert.throws(()=>createSession(dry,args('A1'),{canonAssessments:[{actionId:id,caseId:'not-there',result:'applicable'}]}),
  /LENS_SESSION_CANON_CASE_UNKNOWN/);
});
test('generic Lens runner also accepts ordinary candidate-v6 graph.json, not special DRY source kind',()=>{
 const graph={schemaVersion:1,revision:1,id:'L-ORDINARY',actionModel:'candidate-v6',
  rootRequirementId:'LR',identitySpace:'test-lens',nodes:[{id:'LR',kind:'requirement',title:'Understand target'},
   {id:'LA',kind:'action',title:'Research',status:'candidate',qrpe:[]}],
  edges:[{id:'DR',type:'DRIVES',from:'LR',to:'LA'}],events:[]};
 const sess=createSession(graph,{targetGraphId:'project-A',targetActionId:null,relevantInputs:{scope:'R1'}});
 assert.equal(sess.lensId,'L-ORDINARY');
 assert.equal(sess.graph.nodes.length,2);
 assert.equal(sess.rootResult,'unknown');
});
test('ordinary Lens rejects selected Action without real T1 selection history',()=>{
 const graph={schemaVersion:1,revision:1,id:'bad-lens',actionModel:'candidate-v6',
  identitySpace:'test',rootRequirementId:'LR',nodes:[
   {id:'LR',kind:'requirement',title:'Root'},
   {id:'A1',kind:'action',title:'Already selected',status:'selected'}],
  edges:[{id:'drive',type:'DRIVES',from:'LR',to:'A1'}],events:[]};
 assert.throws(()=>createSession(graph,args('A1')),/LENS_SESSION_INVALID_ORDINARY_GRAPH/);
});
test('completed canon evidence for an unselected target Action may be saved, not arbitrary pending claims',()=>{
 const a=dry.actions.find(a=>a.canonBlock?.recommended?.length);
 const canon=a.canonBlock.recommended[0].id;
 const sess=createSession(dry,args('A1'),{canonAssessments:[{
   actionId:a.id,caseId:canon,result:'applicable',reason:'Scoped source evidence collected',
   evidenceRefs:['example:cost-study']} ]});
 // Clearing unresolved work is not an assertion of root achievement.
 sess.unresolvedQrpe=[];sess.unassessedOrStaleCanons=[];
 const pendingClaim={...claim,pendingDecisionForActionId:'A1',pendingDecisionState:'unselected'};
 assert.equal(eligible(sess,pendingClaim).save,true);
 const saved=capture(sess,pendingClaim,'2026-10-17T18:00:00Z');
 assert.equal(saved.saved,true);
 assert.equal(saved.metadata.pendingDecisionForActionId,'A1');
 assert.equal(saved.metadata.canonAssessmentCount,1);
 assert.equal(eligible(sess,{...pendingClaim,pendingDecisionForActionId:'A2'}).save,false);
 assert.equal(eligible({...sess,canonAssessments:[],requirementAssessments:[]},pendingClaim).save,false);
 assert.equal(eligible(sess,{...pendingClaim,maintenanceWorthwhile:false}).save,false);
});


test('ordinary paper Lens preserves potential child branches without fabricated selection',()=>{
 const fs=require('node:fs'),path=require('node:path');
 const graph=JSON.parse(fs.readFileSync(path.join(__dirname,'../tools/rdg-agent-lenses/explore.json'),'utf8'));
 const before=JSON.stringify(graph);
 const prepared=parsePreparedLens(graph);
 assert.equal(graph.coreModel,'rdg-core-v1');
 const branch=prepared.edges.find(e=>e.type==='INTRODUCES');
 assert(branch);
 assert.deepEqual(branch.origin,{role:'subgoal',requirementIds:[graph.rootRequirementId]});
 assert.deepEqual(branch.origin,graph.edges.find(e=>e.id===branch.id).origin);
 assert(prepared.actions.find(a=>a.id===branch.from).reaches.includes(branch.to));
 const session=createSession(graph,args('A1'));
 assert.equal(JSON.stringify(graph),before);
 assert.deepEqual(session.graph.events,[]);
 assert(session.graph.nodes.filter(n=>n.kind==='action').every(n=>n.status==='candidate'));
 assert(session.graph.nodes.filter(n=>n.kind==='requirement'&&n.id!==graph.rootRequirementId)
  .every(n=>n.status==='potential'));
 assert.equal(session.materialGraphOperations.length,0);
 assert.equal(session.rootResult,'unknown');
 const malformed=structuredClone(graph);
 malformed.edges.find(e=>e.type==='INTRODUCES').origin.requirementIds=['missing-parent'];
 assert.throws(()=>parsePreparedLens(malformed),/INVALID_ORDINARY_GRAPH/);
});
