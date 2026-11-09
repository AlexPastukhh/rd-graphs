'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'..');
const fixturePath=path.join(ROOT,'tests/fixtures/rdg-action-lens-pilot-v1.json');
const fixture=JSON.parse(fs.readFileSync(fixturePath,'utf8'));
const probe=require('../tools/rdg-action-lens-semantic-probe.cjs');
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');

test('candidate fixture remains deliberately outside the accepted graph.json schema and catalog',()=>{
 assert.equal(fixture.version,'rdg-action-lens-pilot/v1');
 assert.equal(fixture.mode,'read-only-test-fixture');
 assert.equal(fixture.lensDefinitions.length,2);
 assert.equal(fixture.targets.length,3);
 assert(!fixture.graphs && !fixture.events && !fixture.externalDependencies);
 const ids=fixture.lensDefinitions.map(l=>l.id);
 assert.deepEqual(ids,['L-DRY','L-MAINT']);
});

test('each lens has a real own root R, scoped A, canon cases, QRPE and conditional child R',()=>{
 for(const lens of fixture.lensDefinitions) {
  assert.equal(probe.lensFromFixture(fixture,lens.id),lens);
  assert(lens.rootRequirement.id.startsWith('R-'));
  assert(lens.requirements.some(r=>r.applicability==='required'));
  assert(lens.requirements.some(r=>r.applicability==='conditional'));
  assert.equal(lens.edges.length,lens.actions.length*2);
  assert(lens.edges.some(e=>e.type==='DRIVES'&&e.from===lens.rootRequirement.id));
  const ids=new Set(lens.requirements.map(r=>r.id));
  for(const a of lens.actions) {
   assert(a.id.startsWith('A-'));
   assert(a.reaches.length>0 && a.reaches.every(id=>ids.has(id)));
   assert(Array.isArray(a.canonBlock.recommended));
   assert(Array.isArray(a.canonBlock.contraindicated));
   assert(Array.isArray(a.qrpe));
  }
 }
 const revoke=probe.lensFromFixture(fixture,'L-MAINT').actions.find(a=>a.id==='A-L-MAINT-REVOKE');
 assert(revoke.effect && revoke.qrpe.some(q=>q.id==='Q-MAINT-EFFECTS'));
 assert(revoke.canonBlock.recommended[0].inputRefs.includes('target.actions'));
 assert(revoke.canonBlock.contraindicated.length>0);
});

test('DRY applies the same graph to different contexts, achieves goal each time, no graph writes',()=>{
 const before=hash(fs.readFileSync(fixturePath));
 const source=JSON.stringify(fixture);
 const clean=probe.readOnlyDryCheck(fixture,'T-CLEAN');
 const dup=probe.readOnlyDryCheck(fixture,'T-DUP');
 assert.equal(clean.achieved,true);
 assert.equal(dup.achieved,false,'potential duplication is not a proven DRY result');
 assert.deepEqual(dup.blockedRequirements,['R-L-DRY-ASSESS']);
 assert.equal(clean.rootRequirementId,dup.rootRequirementId);
 assert.notEqual(clean.targetId,dup.targetId);
 assert.equal(clean.result,'no_material_duplicate');
 assert.equal(dup.result,'needs_duplicate_research');
 assert.deepEqual(clean.conditionalSkipped,['R-L-DRY-REMEDY']);
 assert.deepEqual(dup.conditionalSkipped,['R-L-DRY-REMEDY']);
 assert(dup.qrpe.some(q=>q.questionId==='Q-DRY-DIVERGE'));
 assert.equal(clean.graphWrites+dup.graphWrites,0);
 assert.equal(JSON.stringify(fixture),source);
 assert.equal(hash(fs.readFileSync(fixturePath)),before);
 assert(clean.report && dup.report);
});

test('similar requirements may have justified different behavior, not blindly marked duplicative',()=>{
 const changed=structuredClone(fixture);
 const target=changed.targets.find(t=>t.id==='T-DUP');
 target.context.separateBehaviors=true;
 const result=probe.readOnlyDryCheck(changed,'T-DUP');
 assert.equal(result.result,'no_material_duplicate');
 assert.equal(result.suggestions.length,0);
});

test('maintenance lens discovers new action, leaves accepted choice unchanged and can only suggest revoke',()=>{
 const before=JSON.stringify(fixture);
 const result=probe.readOnlyMaintenanceCheck(fixture,'T-MAINT');
 assert(result.achieved);
 assert.equal(result.result,'propose_reconsideration');
 assert.deepEqual(result.conditionalSkipped,['R-L-MAINT-CHANGE']);
 assert(result.suggestions.some(s=>s.kind==='consider_new_action' && s.actionId==='A-NEW'));
 assert(!probe.targetFromFixture(fixture,'T-MAINT').actions.some(a=>a.id==='A-NEW'),'A-NEW must really be missing from working alternatives');
 const review=result.suggestions.find(s=>s.kind==='review_orphaned_requirements');
 assert.deepEqual(review.sharedRequirements,['R-SHARED']);
 assert.deepEqual(review.requirementIds,['R-OVERHEAD']);
 assert(result.qrpe.some(q=>q.questionId==='Q-MAINT-EFFECTS'));
 assert.equal(result.graphWrites,0);
 assert.equal(probe.targetFromFixture(fixture,'T-MAINT').actions.find(a=>a.id==='A-OLD').status,'selected');
 assert.equal(JSON.stringify(fixture),before);
});

test('different meanings of removing R: selection revoke does not remove independently supported R or undo effects',()=>{
 const target=probe.targetFromFixture(fixture,'T-MAINT');
 const before=JSON.stringify(target);
 assert.throws(()=>probe.simulateAuthorizedReconsideration(fixture,'T-MAINT'),/Authorization/);
 assert.throws(()=>probe.simulateAuthorizedReconsideration(fixture,'T-MAINT',{authorized:true,effect:'delete_everything'}),/Unsupported/);
 assert.throws(()=>probe.simulateAuthorizedReconsideration(fixture,'T-MAINT',{authorized:true,effect:'replace_selected_action'}),/QRPE/);
 assert.throws(()=>probe.simulateAuthorizedReconsideration(fixture,'T-MAINT',{authorized:true,effect:'replace_selected_action',reviewedQrpe:['Q-MAINT-EFFECTS'],reason:'Тест без делегирования'}),/not granted/);
 const approved=structuredClone(fixture);
 approved.targets.find(t=>t.id==='T-MAINT').context.approval='granted';
 const changed=probe.simulateAuthorizedReconsideration(approved,'T-MAINT',{authorized:true,effect:'replace_selected_action',reviewedQrpe:['Q-MAINT-EFFECTS'],reason:'Учебное принятие риска с сохранением shared R'});
 assert.equal(changed.target.actions.find(a=>a.id==='A-OLD').status,'superseded');
 assert.equal(changed.target.actions.find(a=>a.id==='A-NEW').status,'selected');
 assert(!target.actions.some(a=>a.id==='A-NEW'),'discovery does not write a new A into source');
 assert.deepEqual(changed.event.inactiveRequirementIds,['R-OVERHEAD']);
 assert.notEqual(changed.target.requirements.find(r=>r.id==='R-SHARED').status,'inactive');
 assert.notEqual(changed.target.requirements.find(r=>r.id==='R-REPORT').status,'inactive');
 assert.equal(changed.event.previousActionId,'A-OLD');
 assert.deepEqual(changed.event.reviewedQrpeIds,['Q-MAINT-EFFECTS']);
 assert.equal(JSON.stringify(target),before,'No change is written to source target');
 assert(changed.sourceUnchanged && changed.graphWrites===0);
});

test('dependencies already live in action canon references, no mandatory external block or derived view',()=>{
 for(const lens of fixture.lensDefinitions)for(const a of lens.actions) {
  for(const caseRecord of [...a.canonBlock.recommended,...a.canonBlock.contraindicated]) {
   if(caseRecord.inputRefs)assert(caseRecord.inputRefs.every(x=>x.startsWith('target.')));
  }
 }
 assert.equal(Object.hasOwn(fixture,'externalDependencies'),false);
 assert.equal(Object.hasOwn(fixture,'dependencyOverview'),false);
});

test('legacy writer/schema is not silently changed by the candidate semantic fixture',()=>{
 const guide=fs.readFileSync(path.join(ROOT,'docs/guides/RDG-V7-WORKING-GRAPHS.md'),'utf8');
 assert.match(guide,/kind=option|Option/);
 const original=fs.readFileSync(path.join(ROOT,'graphs/examples/reference-prepared-planning-tree/graph.json'),'utf8');
 const prepared=JSON.parse(original);
 assert.equal(prepared.schemaVersion,1);
 assert(prepared.nodes.some(n=>n.kind==='option'));
 assert(!prepared.nodes.some(n=>n.kind==='action'));
});
// Regression of review F-P-01: an absent or unverified empty scope is not a DRY pass.
test('DRY does not claim success on an empty or unverified requirement scope',()=>{
 const unknown=structuredClone(fixture);
 const target=unknown.targets.find(t=>t.id==='T-CLEAN');
 target.requirements=[];
 const result=probe.readOnlyDryCheck(unknown,'T-CLEAN');
 assert.equal(result.achieved,false);
 assert.equal(result.result,'needs_input');
 assert(result.qrpe.some(q=>q.questionId==='Q-DRY-INPUT'));
 assert.deepEqual(result.achievedRequirements,[]);
 assert.equal(result.graphWrites,0);
 target.context.requirementsScopeVerified=true;
 const explicitlyEmpty=probe.readOnlyDryCheck(unknown,'T-CLEAN');
 assert.equal(explicitlyEmpty.achieved,false);
 assert.equal(explicitlyEmpty.result,'not_applicable');
 assert.deepEqual(explicitlyEmpty.qrpe,[]);
});

// Review F-P-02: two missing comparison keys are unknown, not a duplicate.
test('DRY unknown concept never becomes positive evidence of duplication',()=>{
 const unknown=structuredClone(fixture);
 const target=unknown.targets.find(t=>t.id==='T-CLEAN');
 target.requirements=[{id:'R-A',title:'A'},{id:'R-B',title:'B'}];
 const result=probe.readOnlyDryCheck(unknown,'T-CLEAN');
 assert.equal(result.achieved,false);
 assert.equal(result.result,'needs_input');
 assert.deepEqual(result.suggestions,[]);
 assert(result.qrpe.some(q=>q.questionId==='Q-DRY-INPUT'));
 target.requirements=[{id:'R-A',concept:'A'},{id:'R-B',title:'B'}];
 assert.equal(probe.readOnlyDryCheck(unknown,'T-CLEAN').result,'needs_input');
});

// Review F-P-03: no, stale, contradictory evidence is not enough to keep A.
test('Maintenance returns an unresolved QRPE when alternative evidence is unavailable or stale',()=>{
 for(const mutate of [
   t=>{t.actionEvidence={};},
   t=>{t.actionEvidence['A-NEW'].stale=true;},
   t=>{delete t.actionEvidence['A-NEW'].outcomeCovered;},
   t=>{t.actionEvidence['A-NEW'].cost=-1;},
   t=>{t.actionEvidence['A-OLD'].outcomeCovered=false;t.actionEvidence['A-NEW'].outcomeCovered=false;}
 ]) {
   const copy=structuredClone(fixture),target=copy.targets.find(t=>t.id==='T-MAINT');
   mutate(target);
   const outcome=probe.readOnlyMaintenanceCheck(copy,'T-MAINT');
   assert.equal(outcome.achieved,false);
   assert.equal(outcome.result,'needs_evidence');
   assert.deepEqual(outcome.suggestions,[]);
   assert(outcome.qrpe.some(q=>q.questionId==='Q-MAINT-ALTERNATIVE'));
   assert.deepEqual(outcome.blockedRequirements,['R-L-MAINT-ALTS']);
 }
});

test('Maintenance can retain existing selection when evaluated alternative is worse',()=>{
 const copy=structuredClone(fixture),target=copy.targets.find(t=>t.id==='T-MAINT');
 target.actionEvidence['A-NEW'].cost=100;
 const evaluated=probe.readOnlyMaintenanceCheck(copy,'T-MAINT');
 assert.equal(evaluated.achieved,true);
 assert.equal(evaluated.result,'keep_selected');
 assert.deepEqual(evaluated.qrpe,[]);
 target.actionEvidence['A-NEW'].cost=3;
 target.actionEvidence['A-NEW'].outcomeCovered=false;
 const notEquivalent=probe.readOnlyMaintenanceCheck(copy,'T-MAINT');
 assert.equal(notEquivalent.result,'keep_selected');
});

// Review F-P-04: do not require artificial canons or QRPE for simple A.
test('a simple Lens Action without canon/QRPE is valid; malformed supplied fields are not',()=>{
 const copy=structuredClone(fixture),lens=copy.lensDefinitions.find(l=>l.id==='L-DRY');
 const action=lens.actions.find(a=>a.id==='A-L-DRY-SCAN');
 delete action.canonBlock;
 delete action.qrpe;
 assert.equal(probe.lensFromFixture(copy,'L-DRY'),lens);
 assert.equal(probe.readOnlyDryCheck(copy,'T-CLEAN').achieved,true);
 action.qrpe='not an array';
 assert.throws(()=>probe.lensFromFixture(copy,'L-DRY'),/Malformed optional QRPE/);
 delete action.qrpe;
 action.canonBlock={recommended:[]};
 assert.throws(()=>probe.lensFromFixture(copy,'L-DRY'),/Malformed optional canonBlock/);
});

// This candidate graph has no iterative execution semantics: prevent accidental cycles.
test('an unintended cycle in the candidate Lens topology is rejected',()=>{
 const copy=structuredClone(fixture),lens=copy.lensDefinitions.find(l=>l.id==='L-DRY');
 lens.edges.push({id:'backedge',type:'DRIVES',from:'R-L-DRY-ASSESS',to:'A-L-DRY-SCAN'});
 assert.throws(()=>probe.lensFromFixture(copy,'L-DRY'),/Unbounded cycle/);
});

test('pilot is not mistaken for a real self-initiating runner or canon evaluator',()=>{
 const doc=fs.readFileSync(path.join(ROOT,'docs/examples/RDG-ACTION-LENS-SEMANTIC-PILOT.md'),'utf8');
 assert.match(doc,/частичн|часть|ограниченн/i);
 assert.match(doc,/не универсальный DSL канонов/);
 assert.match(doc,/не.*Lens-runner/);
});


// A syntactic flag cannot override target-scoped approval and verified comparative evidence.
test('illustrative change refuses favorable flag when target/evidence disagrees',()=>{
 const unauthorized=structuredClone(fixture);
 assert.throws(()=>probe.simulateAuthorizedReconsideration(unauthorized,'T-MAINT',{
  authorized:true,effect:'replace_selected_action',reviewedQrpe:['Q-MAINT-EFFECTS'],
  reason:'Flag alone cannot grant permission'
 }),/not granted/);
 const insuff=structuredClone(fixture),target=insuff.targets.find(t=>t.id==='T-MAINT');
 target.context.approval='granted';
 target.actionEvidence['A-NEW'].outcomeCovered=false;
 assert.throws(()=>probe.simulateAuthorizedReconsideration(insuff,'T-MAINT',{
  authorized:true,effect:'replace_selected_action',reviewedQrpe:['Q-MAINT-EFFECTS'],
  reason:'Even with approval, alternative is not suitable'
 }),/Insufficient evidence/);
});
