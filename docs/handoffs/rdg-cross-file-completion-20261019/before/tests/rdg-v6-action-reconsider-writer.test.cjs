'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const crypto=require('node:crypto');
const stable=x=>JSON.stringify(x,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b,'en'))):v);
const ROOT=path.resolve(__dirname,'..');
const REQUIRED=['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js',
  'graph-apply.py','graph-index.py','rdg-catalog.py','graph-package.py','rdg-v7-model.py',
  'rdg-v6-action-reconsider.py','rdg-v6-action-trust.py'];
function setup(){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-v6-reconsider-'));
 const tools=path.join(dir,'tools');fs.mkdirSync(tools,{recursive:true});
 for(const f of REQUIRED)fs.copyFileSync(path.join(ROOT,'tools',f),path.join(tools,f));
 const location='workspaces/reconsider/graph.json',gp=path.join(dir,'graphs',location);
 const issuerKey=crypto.randomBytes(32).toString('hex');
 const expiresAt=Math.floor(Date.now()/1000)+600;
 let proofMode='valid';
 const run=(body)=>{
  // Synthetic issuer in tests ONLY. No signing endpoint is included in RDG.
  const ops=body.changes.flatMap(c=>(c.patch||{}).operations||[]);
  const owner=fs.existsSync(gp)?JSON.parse(fs.readFileSync(gp,'utf8')):null;
  if(owner){
   const n=owner.nodes.find(x=>x.id==='R0');
   const hash=crypto.createHash('sha256').update(stable(n)).digest('hex');
   const ref='graph-node:R0@'+hash;
   for(const op of ops){
    if(op.op==='add_action' && op.action.qrpe)
     for(const q of op.action.qrpe)if(q.resolutionEvidenceRefs)
      q.resolutionEvidenceRefs=q.resolutionEvidenceRefs.map(r=>r.startsWith('test:')?ref:r);
    if(op.op==='select_action'||op.op==='link_action_requirement')
     op.event.authorityPrincipal='test-authorized-invoker';
    if(op.op==='reconsider_action'){
     op.event.authorityPrincipal='test-authorized-invoker';
     for(const check of op.event.canonChecks||[])
      check.evidenceRefs=check.evidenceRefs?.map(r=>r.startsWith('test:')?ref:r);
    }
   }
  }
  if(ops.some(op=>['select_action','link_action_requirement','reconsider_action'].includes(op.op)) &&
      (!ops.some(op=>op.op==='reconsider_action')||proofMode!=='missing')){
   const claim={purpose:ops.some(op=>op.op==='reconsider_action')?
    'rdg-v6-action-reconsider-v1':'rdg-v6-material-action-v1',principal:'test-authorized-invoker',expiresAt};
   const payload={transactionId:body.transactionId,changes:body.changes,
    principal:claim.principal,expiresAt:claim.expiresAt,purpose:claim.purpose};
   claim.signature=crypto.createHmac('sha256',issuerKey).update(stable(payload)).digest('hex');
   if(proofMode==='tampered')claim.signature='0'.repeat(64);
   if(proofMode==='expired')claim.expiresAt=Math.floor(Date.now()/1000)-60;
   body.trustedApproval=claim;
   if(proofMode==='changedPayloadAfterSign')
    ops.find(op=>op.op==='reconsider_action').dispositions[0].reason='altered after signature';
  }
  const pkg=path.join(dir,'package.json');fs.writeFileSync(pkg,JSON.stringify(body));
  return spawnSync('python3',[path.join(tools,'graph-apply.py'),'--package','--patch',pkg],{
   encoding:'utf8',env:{...process.env,RDG_ISOLATED_TEST_ONLY:'1',
    RDG_V6_TRUST_KEY:proofMode==='wrongSecret'?'x'.repeat(64):
      proofMode==='noSecret'?'':issuerKey}});
 };
 const patch=(ops,revision,tid)=>run({schemaVersion:1,transactionId:tid,changes:[
  {file:location,patch:{schemaVersion:1,expectedRevision:revision,operations:ops}}]});
 const graph={schemaVersion:1,revision:1,id:'reconsider',title:'Reconsider graph',
  planningScale:'module',identitySpace:'reconsider',rootRequirementId:'R0',actionModel:'candidate-v6',
  nodes:[{id:'R0',kind:'requirement',title:'Root',status:'active'}],edges:[],events:[]};
 const create=()=>run({schemaVersion:1,transactionId:'create',changes:[{file:location,create:graph}]});
 return {dir,tools,location,gp,create,patch,run,read:()=>JSON.parse(fs.readFileSync(gp,'utf8')),
  setProofMode:mode=>{proofMode=mode;},
  cleanup:()=>fs.rmSync(dir,{force:true,recursive:true})};
}
function ok(res){assert.equal(res.status,0,res.stderr||res.stdout);}
function bad(res,pattern){assert.notEqual(res.status,0,res.stdout);assert.match(res.stderr,pattern);}
function original(){return [{op:'add_action',requirementId:'R0',action:{id:'A1',kind:'action',title:'Original choice',status:'candidate',
  canonBlock:{recommended:[{id:'C-OLD',text:'Original suitable'}],contraindicated:[]},
  qrpe:[{id:'Q-OLD',text:'Should we retain children?',status:'open'}]}},
  {op:'select_action',actionId:'A1',event:{id:'EV-OLD',type:'action_selected',actionId:'A1',
    driverRequirementId:'R0',by:'user',note:'Synthetic original approval'},children:[
   {role:'subgoal',requirement:{id:'R1',kind:'requirement',title:'Child one'}},
   {role:'subgoal',requirement:{id:'R2',kind:'requirement',title:'Child two'}}]}];}
function reviewer(){return [{op:'add_action',requirementId:'R0',action:{id:'A-REVIEW',kind:'action',
  title:'Reconsider original choice',status:'candidate',
  canonBlock:{recommended:[{id:'C-REVIEW',text:'Documented evidence makes change reasonable'}],contraindicated:[]},
  qrpe:[{id:'Q-REVIEW',text:'Check consequences of removing old choice',status:'resolved',
    resolutionEvidenceRefs:['test:qrpe-resolved']}]}},
  {op:'select_action',actionId:'A-REVIEW',event:{id:'EV-REVIEW',type:'action_selected',
    actionId:'A-REVIEW',driverRequirementId:'R0',by:'user',note:'Synthetic selection of reconsideration Action'},children:[]}];}
function reconsider(dispositions=[{requirementId:'R1',effect:'deactivate',reason:'No further need',downstreamScope:'single_graph_verified'},
 {requirementId:'R2',effect:'deactivate',reason:'No further need',downstreamScope:'single_graph_verified'}]){
 return [{op:'reconsider_action',actionId:'A1',reviewActionId:'A-REVIEW',dispositions,event:{
  id:'EV-RECONSIDER',type:'action_reconsidered',actionId:'A1',reviewActionId:'A-REVIEW',
  driverRequirementId:'R0',by:'user',approvalRef:'test-only-user-choice',contextVersion:'synthetic-T2',
  note:'Synthetic attributed decision on a disposable graph',
  canonChecks:[{caseId:'C-REVIEW',result:'applicable',reason:'Toy evidence provided',evidenceRefs:['test:assessment']}]}}];
}
function ready(w){ok(w.create());ok(w.patch(original(),1,'original'));ok(w.patch(reviewer(),2,'review'));assert.equal(w.read().revision,3);}
test('opt-in writer materially reconsiders an Action while preserving history',()=>{
 const w=setup();try{
  ready(w);ok(w.patch(reconsider(),3,'reconsider'));const g=w.read();
  assert.equal(g.revision,4);assert.equal(g.nodes.find(n=>n.id==='A1').status,'superseded');
  assert.equal(g.nodes.find(n=>n.id==='A-REVIEW').status,'selected');
  assert.equal(g.nodes.find(n=>n.id==='R1').status,'inactive');
  assert.equal(g.nodes.find(n=>n.id==='R2').status,'inactive');
  assert.deepEqual(g.edges.filter(e=>e.from==='A1'&&e.type==='INTRODUCES').map(e=>e.archived),[true,true]);
  const history=g.events.find(e=>e.id==='EV-RECONSIDER');
  assert.equal(history.priorActionSnapshot.status,'selected');
  assert.equal(history.priorActionSnapshot.selectionBasis.actionSnapshot.status,'candidate');
  assert.equal(history.priorIntroductionEdges.length,2);
  assert.equal(history.childDispositions.length,2);
  assert.equal(history.verifiedTrustReceipt.principal,'test-authorized-invoker');
  assert.equal(history.verifiedTrustReceipt.purpose,'rdg-v6-action-reconsider-v1');
  assert.equal(history.verifiedTrustReceipt.signature.length,64);
  assert.equal(history.verifiedTrustReceipt.transactionId,'reconsider');
  ok(w.patch(reconsider(),3,'reconsider'));assert.equal(w.read().revision,4);
 }finally{w.cleanup();}
});
test('missing review Action, approval, canon evidence or child decisions fail without writes',()=>{
 const w=setup();try{
  ready(w);let seq=0;const variants=[
   x=>{x[0].reviewActionId='A1';},
   x=>{delete x[0].event.approvalRef;},
   x=>{x[0].event.by='assistant';},
   x=>{x[0].event.canonChecks=[];},
   x=>{x[0].event.canonChecks[0].result='unknown';},
   x=>{x[0].dispositions.pop();},
   x=>{x[0].dispositions[0].effect='retain_supported';},
   x=>{x[0].dispositions[0].downstreamScope='unverified';},
   x=>{x[0].dispositions[0].requirementId='R0';},
  ];
  for(const change of variants){
   const before=JSON.stringify(w.read()),op=reconsider();change(op);
   const result=w.patch(op,3,'reject-'+(++seq));
   assert.notEqual(result.status,0,'should reject '+seq);
   assert.equal(JSON.stringify(w.read()),before,'must not partially write '+seq);
  }
 }finally{w.cleanup();}
});
test('open reviewer QRPE blocks a materially changing reconsideration',()=>{
 const w=setup();try{
  ready(w);const g=w.read();g.nodes.find(n=>n.id==='A-REVIEW').qrpe[0].status='open';
  fs.writeFileSync(w.gp,JSON.stringify(g));
  bad(w.patch(reconsider(),3,'qrpe-open'),/RECONSIDER_REVIEW_ACTION_QRPE_OPEN/);
  assert.equal(w.read().revision,3);
 }finally{w.cleanup();}
});
test('retiring an R with downstream work or a dependent Action fails closed',()=>{
 const w=setup();try{
  ready(w);let g=w.read();g.nodes.push({id:'R3',kind:'requirement',title:'Another goal',status:'active'});
  g.edges.push({id:'dep-R1-R3',type:'DERIVES',from:'R1',to:'R3'});
  fs.writeFileSync(w.gp,JSON.stringify(g));
  bad(w.patch(reconsider(),3,'has-dependent'),/RECONSIDER_CHILD_HAS_DEPENDENCIES/);
  assert.equal(w.read().revision,3);
 }finally{w.cleanup();}
});
test('shared R survives reconsideration of only one introducing Action',()=>{
 const w=setup();try{
  ready(w);
  const other=[{op:'add_action',requirementId:'R0',action:{id:'A3',kind:'action',title:'Independent support',status:'candidate'}},
   {op:'select_action',actionId:'A3',event:{id:'EV3',type:'action_selected',
     actionId:'A3',driverRequirementId:'R0',by:'assistant',note:'Synthetic additional support'},children:[]},
   {op:'link_action_requirement',actionId:'A3',requirementId:'R1',edgeId:'LINK-A3-R1',
    childRole:'subgoal',event:{id:'EV-LINK',type:'action_requirement_linked',actionId:'A3',requirementId:'R1',
     edgeId:'LINK-A3-R1',driverRequirementId:'R0',by:'user',note:'Independent reason for retaining same R'}}];
  ok(w.patch(other,3,'other-support'));
  const dispositions=[{requirementId:'R1',effect:'retain_supported',reason:'A3 independently supports R1',supportingActionIds:['A3']},
   {requirementId:'R2',effect:'deactivate',reason:'No additional support',downstreamScope:'single_graph_verified'}];
  ok(w.patch(reconsider(dispositions),4,'retire-old'));
  const g=w.read(),original=g.nodes.find(n=>n.id==='A1');
  assert.equal(original.status,'superseded');
  assert.equal(g.nodes.find(n=>n.id==='R1').status,'active');
  assert.equal(g.nodes.find(n=>n.id==='R2').status,'inactive');
  assert(g.edges.some(e=>e.id==='LINK-A3-R1'&&e.archived!==true));
  assert(g.edges.some(e=>e.id==='action-introduces-A1-R1'&&e.archived===true));
  const projection=require('../tools/rdg-root-projection.js').project({graphs:[{
   slug:'reconsider',graph:g,identitySpace:'reconsider'}]},'reconsider');
  assert(projection.nodes.some(n=>n.id==='R1'));
  assert(!projection.nodes.some(n=>n.id==='R2'));
  assert(projection.edges.some(e=>e.causeId==='A3'&&e.to==='R1'));
 }finally{w.cleanup();}
});
test('refuse to deactivate a shared R even if submitted disposition claims exclusivity',()=>{
 const w=setup();try{
  ready(w);
  const other=[{op:'add_action',requirementId:'R0',action:{id:'A3',kind:'action',title:'Independent',status:'candidate'}},
   {op:'select_action',actionId:'A3',event:{id:'EV3',type:'action_selected',
    actionId:'A3',driverRequirementId:'R0',by:'user',note:'Additional support'},children:[]},
   {op:'link_action_requirement',actionId:'A3',requirementId:'R1',edgeId:'LINK3',childRole:'subgoal',
    event:{id:'EV3-LINK',type:'action_requirement_linked',actionId:'A3',requirementId:'R1',
      edgeId:'LINK3',driverRequirementId:'R0',by:'assistant',note:'Same R independent support'}}];
  ok(w.patch(other,3,'new-support'));
  bad(w.patch(reconsider(),4,'invalid-retirement'),/RECONSIDER_CANNOT_DEACTIVATE_SHARED_R/);
  assert.equal(w.read().nodes.find(n=>n.id==='A1').status,'selected');
 }finally{w.cleanup();}
});
test('cross-file child continuation blocks retiring its owning R',()=>{
 const w=setup();try{
  ready(w);
  const child={schemaVersion:1,revision:1,id:'child',title:'R1 downstream',planningScale:'unit',
   identitySpace:'reconsider',rootRequirementId:'R1',actionModel:'candidate-v6',
   nodes:[{id:'R1',kind:'requirement',title:'Child one',status:'active',
     projectionOf:{graphSlug:'reconsider',nodeId:'R1'}}],edges:[],events:[]};
  ok(w.run({schemaVersion:1,transactionId:'create-child',changes:[{
   file:'workspaces/child/graph.json',create:child}]}));
  const before=JSON.stringify(w.read());
  const result=w.patch(reconsider(),3,'cross-file-retire');
  assert.notEqual(result.status,0,result.stdout);
  assert.equal(JSON.stringify(w.read()),before);
 }finally{w.cleanup();}
});
test('direct legacy deactivate_requirement cannot bypass the opt-in Action review gate',()=>{
 const w=setup();try{
  ready(w);
  const result=w.patch([{op:'deactivate_requirement',requirementId:'R1',
    event:{id:'BYPASS',type:'requirement_deactivated',requirementId:'R1',by:'user',note:'No review'}}],3,'no-bypass');
  bad(result,/ACTION_MODEL_GUARD/);
  assert.equal(w.read().nodes.find(n=>n.id==='R1').status,'active');
 }finally{w.cleanup();}
});
test('later QRPE updates on historical Action keep immutable T1 and older decision snapshot',()=>{
 const w=setup();try{
  ready(w);ok(w.patch(reconsider(),3,'reconsider'));
  const history=w.read().events.find(e=>e.id==='EV-RECONSIDER');
  const snapshot=JSON.stringify(history.priorActionSnapshot);
  const issue={id:'Q-LATER',text:'Challenge the historical choice later',status:'open'};
  ok(w.patch([{op:'append_qrpe',targetId:'A1',issue}],4,'later-challenge'));
  const after=w.read();
  assert.equal(after.nodes.find(n=>n.id==='A1').qrpe.length,2);
  assert.equal(JSON.stringify(after.events.find(e=>e.id==='EV-RECONSIDER').priorActionSnapshot),snapshot);
  assert.equal(after.nodes.find(n=>n.id==='A1').selectionBasis.actionSnapshot.id,'A1');
 }finally{w.cleanup();}
});
test('tampering with earlier T1/reconsideration evidence fails validation before write',()=>{
 const w=setup();try{
  ready(w);ok(w.patch(reconsider(),3,'reconsider'));
  const original=JSON.stringify(w.read()),graph=w.read();
  graph.events.find(e=>e.id==='EV-RECONSIDER').priorActionSnapshot.title='FALSE-HISTORY';
  fs.writeFileSync(w.gp,JSON.stringify(graph));
  const attempt=w.patch([{op:'append_qrpe',targetId:'A-REVIEW',issue:{
   id:'LATE',text:'Other issue',status:'open'}}],4,'attempt-altered-history');
  bad(attempt,/ACTION_RECONSIDERATION_PRIOR_SNAPSHOT_CHANGED/);
  assert.equal(JSON.stringify(w.read()),JSON.stringify(graph));
  assert.notEqual(original,JSON.stringify(graph));
 }finally{w.cleanup();}
});
test('a reconsideration Action may itself be reconsidered later without rewriting first history',()=>{
 const w=setup();try{
  ready(w);ok(w.patch(reconsider(),3,'first-reconsider'));
  const before=w.read().events.find(e=>e.id==='EV-RECONSIDER');
  const next=[{op:'add_action',requirementId:'R0',action:{id:'A-LATER',kind:'action',title:'Review prior review',status:'candidate',
    canonBlock:{recommended:[{id:'C-LATER',text:'Later review changes conclusion'}],contraindicated:[]},
    qrpe:[{id:'Q-LATER',text:'Are consequences known?',status:'resolved',resolutionEvidenceRefs:['test:later']}]}},
   {op:'select_action',actionId:'A-LATER',event:{id:'EV-LATER',type:'action_selected',actionId:'A-LATER',
    driverRequirementId:'R0',by:'user',note:'Synthetic later review selection'},children:[]}];
  ok(w.patch(next,4,'select-later'));
  const deeper=[{op:'reconsider_action',actionId:'A-REVIEW',reviewActionId:'A-LATER',dispositions:[],event:{
    id:'EV-LATER-RECONSIDER',type:'action_reconsidered',actionId:'A-REVIEW',reviewActionId:'A-LATER',
    driverRequirementId:'R0',by:'user',approvalRef:'test:second',contextVersion:'T3-example',
    note:'Review of the earlier review, on the disposable graph',
    canonChecks:[{caseId:'C-LATER',result:'applicable',reason:'Toy reason',evidenceRefs:['test:later']}]}}];
  ok(w.patch(deeper,5,'reconsider-review'));
  const g=w.read();assert.equal(g.nodes.find(n=>n.id==='A-REVIEW').status,'superseded');
  assert.equal(g.nodes.find(n=>n.id==='A-LATER').status,'selected');
  assert.deepEqual(g.events.find(e=>e.id==='EV-RECONSIDER'),before);
  assert.equal(g.events.filter(e=>e.type==='action_reconsidered').length,2);
 }finally{w.cleanup();}
});
test('authorization proof is mandatory, fresh, secret-backed and bound to exact transaction bytes',()=>{
 const w=setup();try{
  ready(w);
  const faults={missing:/TRUST_REQUIRED/,tampered:/TRUST_SIGNATURE_INVALID/,
   expired:/TRUST_APPROVAL_EXPIRED/,wrongSecret:/TRUST_SIGNATURE_INVALID/,
   noSecret:/TRUST_UNAVAILABLE/,changedPayloadAfterSign:/TRUST_SIGNATURE_INVALID/};
  let i=0;
  for(const [mode,expected] of Object.entries(faults)){
   w.setProofMode(mode);
   const before=JSON.stringify(w.read());
   bad(w.patch(reconsider(),3,'reject-trust-'+(++i)),expected);
   assert.equal(JSON.stringify(w.read()),before,mode+' was not allowed to write');
  }
  w.setProofMode('valid');
  ok(w.patch(reconsider(),3,'valid-trust'));
  assert.equal(w.read().nodes.find(n=>n.id==='A1').status,'superseded');
 }finally{w.cleanup();}
});
test('stale, nonexistent and unsupported evidence refs are denied even with a valid signature',()=>{
 const w=setup();try{
  ready(w);
  const refs=['graph-node:R0@'+'0'.repeat(64),
   'graph-node:R-NOT-THERE@'+'a'.repeat(64),'external:unverified'];
  for(let i=0;i<refs.length;i++){
   const op=reconsider();op[0].event.canonChecks[0].evidenceRefs= [refs[i]];
   const before=JSON.stringify(w.read());
   bad(w.patch(op,3,'bad-evidence-'+i),/EVIDENCE_STALE_OR_FORGED|EVIDENCE_NODE_NOT_FOUND|EVIDENCE_UNSUPPORTED_REFERENCE/);
   assert.equal(JSON.stringify(w.read()),before);
  }
 }finally{w.cleanup();}
});
test('direct unverified library call cannot perform a material reconsideration',()=>{
 const graph=JSON.parse(fs.readFileSync(path.join(ROOT,'tests/fixtures/rdg-v6-action-reconsidered/graph.json'),'utf8'));
 const script=`from importlib.machinery import SourceFileLoader
import json,sys
mod=SourceFileLoader('ap',sys.argv[1]).load_module()
g=json.load(open(sys.argv[2]))
try:mod.apply(g,{'schemaVersion':1,'expectedRevision':g['revision'],
'operations':[{'op':'reconsider_action'}]})
except ValueError as e:
 assert 'TRUST_REQUIRED' in str(e), str(e)
else: raise AssertionError('bypassed trusted writer')
`;
 const r=spawnSync('python3',['-c',script,path.join(ROOT,'tools/graph-apply.py'),
  path.join(ROOT,'tests/fixtures/rdg-v6-action-reconsidered/graph.json')],{encoding:'utf8'});
 assert.equal(r.status,0,r.stderr);
});
