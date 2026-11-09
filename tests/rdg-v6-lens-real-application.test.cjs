'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..');
const script=path.join(ROOT,'tools/rdg-v6-lens-apply.cjs');
const clean=path.join(ROOT,'tests/fixtures/rdg-v6-lens-dry-target/graph.json');
const maint=path.join(ROOT,'tests/fixtures/rdg-v6-lens-maintenance-target/graph.json');
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
const stable=x=>JSON.stringify(x,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?
  Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
function inspect(file,lens,command=script,extra=[],env=process.env){
 return spawnSync('node',[command,'--graph',file,'--lens',lens,...extra],{encoding:'utf8',env});
}
function validResult(result){assert.equal(result.status,0,result.stderr);return JSON.parse(result.stdout);}
function sandbox(){
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-lens-real-'));
 const tools=path.join(base,'tools'),graphs=path.join(base,'graphs/workspaces/lens-target');
 const definitions=path.join(base,'tests/fixtures');
 fs.mkdirSync(tools,{recursive:true});fs.mkdirSync(graphs,{recursive:true});
 fs.mkdirSync(definitions,{recursive:true});
 for(const n of ['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js',
  'rdg-modules.py','rdg-module-registry.json','rdg-module-test.py','graph-apply.py','graph-index.py','rdg-catalog.py','graph-package.py','rdg-transaction-io.py','rdg-v7-model.py',
  'rdg-v6-action-trust.py','rdg-v6-action-reconsider.py',
  'rdg-action-lens-semantic-probe.cjs','rdg-v6-lens-apply.cjs'])
  fs.copyFileSync(path.join(ROOT,'tools',n),path.join(tools,n));
 fs.copyFileSync(path.join(ROOT,'tests/fixtures/rdg-action-lens-pilot-v1.json'),
  path.join(definitions,'rdg-action-lens-pilot-v1.json'));
 const graphPath=path.join(graphs,'graph.json');fs.copyFileSync(maint,graphPath);
 const key=crypto.randomBytes(32).toString('hex');
 const packagePath=path.join(base,'package.json');
 function makePackage(){
  const graph=JSON.parse(fs.readFileSync(graphPath,'utf8'));
  const context=graph.nodes.find(n=>n.id==='CTX-MAINT');
  const ref='graph-node:CTX-MAINT@'+sha(stable(context));
  const prepared=require('../tools/rdg-v6-lens-apply.cjs').runInspection(
   JSON.parse(fs.readFileSync(path.join(ROOT,'tests/fixtures/rdg-action-lens-pilot-v1.json'))),
   graph,'maintenance');
  const effect={lensId:prepared.lensId,lensActionId:'A-L-MAINT-REVOKE',
   conditionalRequirementId:'R-L-MAINT-CHANGE',
   lensRootRequirementId:prepared.rootRequirementId,definitionDigest:prepared.definitionDigest,
   targetGraphId:graph.id,targetRevision:graph.revision,
   effectQrpe:{questionId:'Q-MAINT-EFFECTS',status:'accepted-risk',
    reason:'Synthetic evidence only: this is not real-world compensation',evidenceRefs:[ref]}};
  const body={schemaVersion:1,transactionId:'lens-approved-reconsider',changes:[{
   file:'workspaces/lens-target/graph.json',patch:{schemaVersion:1,expectedRevision:graph.revision,
    operations:[{op:'reconsider_action',actionId:'A1',reviewActionId:'A-REVIEW',
     dispositions:[{requirementId:'R1',effect:'deactivate',reason:'Synthetic model removes duplicate requirement',downstreamScope:'single_graph_verified'},
      {requirementId:'R2',effect:'deactivate',reason:'Synthetic model also retires old exclusive R',downstreamScope:'single_graph_verified'}],
     event:{id:'EV-LENS-REVIEW',type:'action_reconsidered',actionId:'A1',reviewActionId:'A-REVIEW',
      driverRequirementId:'R0',by:'user',approvalRef:'test:trusted-issuer',authorityPrincipal:'test-principal',
      contextVersion:'candidate-T2',note:'Synthetic authorized maintenance lens review, not a real user consent',
      canonChecks:[{caseId:'C-REVIEW',result:'applicable',reason:'Anchored graph comparison',evidenceRefs:[ref]}],
      lensApplication:effect}
    }]}
  }]};
  const expiresAt=Math.floor(Date.now()/1000)+450;
  const claim={purpose:'rdg-v6-action-reconsider-v1',principal:'test-principal',expiresAt};
  const payload={transactionId:body.transactionId,changes:body.changes,principal:claim.principal,
   expiresAt:claim.expiresAt,purpose:claim.purpose};
  claim.signature=crypto.createHmac('sha256',key).update(stable(payload)).digest('hex');
  body.trustedApproval=claim;
  fs.writeFileSync(packagePath,JSON.stringify(body));
  return body;
 }
 return {base,graphPath,packagePath,makePackage,key,cmd:path.join(tools,'rdg-v6-lens-apply.cjs'),
  cleanup:()=>fs.rmSync(base,{recursive:true,force:true})};
}

test('same prepared DRY Lens runs against real opt-in graph with zero writes',()=>{
 const before=fs.readFileSync(clean);const result=validResult(inspect(clean,'dry'));
 assert.equal(result.rootRequirementId,'R-L-DRY');assert.equal(result.rootAchieved,true);
 assert.equal(result.semanticResult,'no_material_duplicate');
 assert.equal(result.graphWrites,0);assert.equal(result.persistedLensRun,false);
 assert.equal(result.sourceGraphSHA256,sha(before));assert.equal(sha(fs.readFileSync(clean)),sha(before));
});
test('DRY on a possibly duplicated real graph remains unresolved, and ignores fake success',()=>{
 const box=sandbox();try{
  const graph=JSON.parse(fs.readFileSync(clean,'utf8'));
  graph.nodes.find(n=>n.id==='R2').concept=graph.nodes.find(n=>n.id==='R1').concept;
  fs.writeFileSync(box.graphPath,JSON.stringify(graph));
  const result=validResult(inspect(box.graphPath,'dry',box.cmd));
  assert.equal(result.rootAchieved,false);
  assert.equal(result.semanticResult,'needs_duplicate_research');
  assert(result.openQrpe.some(q=>q.questionId==='Q-DRY-DIVERGE'));
  assert.equal(result.graphWrites,0);
 }finally{box.cleanup();}
});
test('Maintenance Lens sees real selected Action and discovered alternative without changing target',()=>{
 const before=fs.readFileSync(maint);const result=validResult(inspect(maint,'maintenance'));
 assert.equal(result.rootRequirementId,'R-L-MAINT');
 assert.equal(result.semanticResult,'propose_reconsideration');
 assert.equal(result.targetSelectedActionId,'A1');
 assert.equal(result.targetResearchActionId,'A-NEW');
 assert.equal(result.evidenceSource.nodeId,'CTX-MAINT');
 assert.equal(result.graphWrites,0);assert.equal(result.persistedLensRun,false);
 assert.equal(sha(fs.readFileSync(maint)),sha(before));
});
test('Maintenance Lens without actual comparison evidence does not claim achievement',()=>{
 const result=validResult(inspect(path.join(ROOT,'tests/fixtures/rdg-v6-action-optin/graph.json'),'maintenance'));
 assert.equal(result.rootAchieved,false);
 assert.equal(result.semanticResult,'needs_evidence');
 assert.equal(result.graphWrites,0);
});
test('trusted, fully scoped package can enact material Action from prepared Maintenance Lens once',()=>{
 const box=sandbox();try{
  const initial=JSON.parse(fs.readFileSync(box.graphPath,'utf8'));
  box.makePackage();
  const args=['--mode','apply','--package',box.packagePath];
  const env={...process.env,RDG_V6_TRUST_KEY:box.key};
  const result=validResult(inspect(box.graphPath,'maintenance',box.cmd,args,env));
  assert.equal(result.graphWrites,1);assert.equal(result.rootAchieved,true);
  assert.equal(result.semanticResult,'reconsideration_applied');
  assert(result.performedLensActionIds.includes('A-L-MAINT-REVOKE'));
  assert(!result.skippedConditionalRequirements.includes('R-L-MAINT-CHANGE'));
  assert(!result.openQrpe.some(q=>q.questionId==='Q-MAINT-EFFECTS'));
  assert.equal(result.resolvedEffectQrpe.status,'accepted-risk');
  assert.equal(result.afterRevision,initial.revision+1);
  assert.equal(result.persistedLensRun,false);
  const final=JSON.parse(fs.readFileSync(box.graphPath,'utf8'));
  assert.equal(final.nodes.find(n=>n.id==='A1').status,'superseded');
  assert.equal(final.nodes.find(n=>n.id==='R1').status,'inactive');
  assert.equal(final.nodes.find(n=>n.id==='R2').status,'inactive');
  assert.equal(final.events.find(e=>e.id==='EV-LENS-REVIEW').type,'action_reconsidered');
  assert.equal(final.events.find(e=>e.id==='EV-LENS-REVIEW').verifiedTrustReceipt.principal,'test-principal');
 }finally{box.cleanup();}
});
test('untrusted Lens package is rejected and never mutates the graph',()=>{
 const box=sandbox();try{
  box.makePackage();
  const before=sha(fs.readFileSync(box.graphPath));
  const result=inspect(box.graphPath,'maintenance',box.cmd,['--mode','apply','--package',box.packagePath],
    {...process.env,RDG_V6_TRUST_KEY:'invalid-key-longer-than-thirty-two-bytes'});
  assert.notEqual(result.status,0);assert.match(result.stderr,/LENS_WRITER_REJECTED/);
  assert.equal(sha(fs.readFileSync(box.graphPath)),before);
 }finally{box.cleanup();}
});
test('Lens apply cannot smuggle another operation into signed package',()=>{
 const box=sandbox();try{
  const body=box.makePackage();
  body.changes[0].patch.operations.push({op:'add_node',node:{id:'R-ATTACK',kind:'requirement',title:'Unreviewed'}});
  fs.writeFileSync(box.packagePath,JSON.stringify(body));
  const before=sha(fs.readFileSync(box.graphPath));
  const result=inspect(box.graphPath,'maintenance',box.cmd,['--mode','apply','--package',box.packagePath],
    {...process.env,RDG_V6_TRUST_KEY:box.key});
  assert.notEqual(result.status,0);assert.match(result.stderr,/LENS_PACKAGE_ACTION_MISMATCH/);
  assert.equal(sha(fs.readFileSync(box.graphPath)),before);
 }finally{box.cleanup();}
});
test('stale comparative evidence forces the Maintenance Lens into unknown and forbids apply',()=>{
 const box=sandbox();try{
  const g=JSON.parse(fs.readFileSync(box.graphPath,'utf8'));
  g.nodes.find(n=>n.id==='CTX-MAINT').maintenanceComparison.stale=true;
  fs.writeFileSync(box.graphPath,JSON.stringify(g));
  const report=validResult(inspect(box.graphPath,'maintenance',box.cmd));
  assert.equal(report.rootAchieved,false);
  assert.equal(report.semanticResult,'needs_evidence');
  assert.deepEqual(report.suggestions,[]);
  box.makePackage();
  const before=sha(fs.readFileSync(box.graphPath));
  const applied=inspect(box.graphPath,'maintenance',box.cmd,['--mode','apply','--package',box.packagePath],
    {...process.env,RDG_V6_TRUST_KEY:box.key});
  assert.notEqual(applied.status,0);assert.match(applied.stderr,/LENS_NOT_READY/);
  assert.equal(sha(fs.readFileSync(box.graphPath)),before);
 }finally{box.cleanup();}
});
test('DRY report rejects graphs with fabricated or missing R root',()=>{
 const box=sandbox();try{
  const g=JSON.parse(fs.readFileSync(clean,'utf8'));
  g.rootRequirementId='nonexistent';
  fs.writeFileSync(box.graphPath,JSON.stringify(g));
  const result=inspect(box.graphPath,'dry',box.cmd);
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/Malformed target graph/);
 }finally{box.cleanup();}
});
test('a signed package with open or missing Lens effects QRPE cannot modify even a favorable target',()=>{
 for(const mode of ['missing','open','wrongAction','wrongEvidence']){
  const box=sandbox();try{
   const pkg=box.makePackage();
   const op=pkg.changes[0].patch.operations[0];
   if(mode==='missing')delete op.event.lensApplication;
   if(mode==='open')op.event.lensApplication.effectQrpe.status='open';
   if(mode==='wrongAction')op.event.lensApplication.lensActionId='A-L-MAINT-CHECK';
   if(mode==='wrongEvidence')op.event.lensApplication.effectQrpe.evidenceRefs=['graph-node:CTX-MAINT@'+'0'.repeat(64)];
   const payload={transactionId:pkg.transactionId,changes:pkg.changes,
    principal:pkg.trustedApproval.principal,expiresAt:pkg.trustedApproval.expiresAt,
    purpose:pkg.trustedApproval.purpose};
   pkg.trustedApproval.signature=crypto.createHmac('sha256',box.key).update(stable(payload)).digest('hex');
   fs.writeFileSync(box.packagePath,JSON.stringify(pkg));
   const before=sha(fs.readFileSync(box.graphPath));
   const attempt=inspect(box.graphPath,'maintenance',box.cmd,['--mode','apply','--package',box.packagePath],
    {...process.env,RDG_V6_TRUST_KEY:box.key});
   assert.notEqual(attempt.status,0,mode+' must reject');
   assert.match(attempt.stderr,/LENS_EFFECT_QRPE_NOT_RESOLVED/,mode);
   assert.equal(sha(fs.readFileSync(box.graphPath)),before,mode+' must be atomic');
  }finally{box.cleanup();}
 }
});
test('Lens does not claim root achievement on graph rejected by the authoritative validator',()=>{
 const box=sandbox();try{
  const g=JSON.parse(fs.readFileSync(clean,'utf8'));
  g.edges[0].to='A-GHOST';
  fs.writeFileSync(box.graphPath,JSON.stringify(g));
  const r=inspect(box.graphPath,'dry',box.cmd);
  assert.notEqual(r.status,0);assert.match(r.stderr,/LENS_INVALID_SOURCE_GRAPH/);
 }finally{box.cleanup();}
});
