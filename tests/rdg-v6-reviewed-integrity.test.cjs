'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..');
const files=['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js',
 'rdg-modules.py','rdg-module-registry.json','rdg-module-test.py','graph-apply.py','graph-index.py','rdg-catalog.py','graph-package.py','rdg-transaction-io.py','rdg-v7-model.py',
 'rdg-v6-action-reconsider.py','rdg-v6-action-trust.py'];
const stable=x=>JSON.stringify(x,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?
 Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b,'en'))):v);
function sandbox(){
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-review-integrity-'));
 fs.mkdirSync(path.join(base,'tools'));for(const f of files)
  fs.copyFileSync(path.join(ROOT,'tools',f),path.join(base,'tools',f));
 const dest='workspaces/pilot/graph.json',graphPath=path.join(base,'graphs',dest),
  pkgPath=path.join(base,'package.json'),key=crypto.randomBytes(32).toString('hex');
 const run=(body,keyOverride=key)=>{
  fs.writeFileSync(pkgPath,JSON.stringify(body));
  return spawnSync('python3',[path.join(base,'tools/graph-apply.py'),
   '--package','--patch',pkgPath],{encoding:'utf8',
    env:{...process.env,RDG_ISOLATED_TEST_ONLY:'1',RDG_V6_TRUST_KEY:keyOverride}});
 };
 const patch=(ops,revision,id,metadata)=>({schemaVersion:1,transactionId:id,changes:[{
  file:dest,patch:{schemaVersion:1,expectedRevision:revision,operations:structuredClone(ops)},
  ...(metadata?{metadata}:{})}]});
 const signed=body=>{
  const principal='synthetic-integration-issuer';
  const operations=body.changes.flatMap(c=>c.patch?.operations||[]);
  for(const op of operations){
   if(['select_action','link_action_requirement','reconsider_action'].includes(op.op))
    op.event.authorityPrincipal=principal;
   if(op.op==='transition_qrpe')op.authorityPrincipal=principal;
  }
  const expiresAt=Math.floor(Date.now()/1000)+450;
  const claim={purpose:'rdg-v6-material-action-v1',principal,expiresAt};
  const payload={transactionId:body.transactionId,changes:body.changes,principal,expiresAt,purpose:claim.purpose};
  claim.signature=crypto.createHmac('sha256',key).update(stable(payload)).digest('hex');
  body.trustedApproval=claim;return body;
 };
 const baseGraph={schemaVersion:1,revision:1,id:'pilot',title:'Pilot',planningScale:'module',
  identitySpace:'pilot',rootRequirementId:'R0',actionModel:'candidate-v6',
  nodes:[{id:'R0',kind:'requirement',title:'Root',status:'active',concept:'C'}],
  edges:[],events:[]};
 const create=()=>run({schemaVersion:1,transactionId:'bootstrap',changes:[{file:dest,create:baseGraph}]});
 return {base,run,patch,signed,create,read:()=>JSON.parse(fs.readFileSync(graphPath,'utf8')),
  cleanup:()=>fs.rmSync(base,{force:true,recursive:true})};
}
function pass(x){assert.equal(x.status,0,x.stderr||x.stdout);}
function reject(x,re){assert.notEqual(x.status,0,x.stdout);assert.match(x.stderr,re);}
const added=[{op:'add_action',requirementId:'R0',action:{id:'A1',kind:'action',title:'Option',status:'candidate'}}];
const selected=[{op:'select_action',actionId:'A1',children:[{role:'subgoal',requirement:{id:'R1',kind:'requirement',title:'Goal R1'}}],
 event:{id:'EV-SELECT',type:'action_selected',actionId:'A1',driverRequirementId:'R0',
 by:'user',note:'synthetic consent only'}}];
test('candidate-v6 blocks silent writes to R, Context, edges, events and owner root',()=>{
 const w=sandbox();try{
  pass(w.create());pass(w.run(w.patch(added,1,'draft')));
  const cases=[
   [{op:'append_qrpe',targetId:'A1',issue:{id:'Q-FORGED',text:'Already closed',status:'resolved'}}],
   [{op:'update_node',id:'R0',changes:{concept:'rewritten',sourceUserGoal:'fake'}}],
   [{op:'add_node',node:{id:'R2',kind:'requirement',title:'Unapproved R'}}],
   [{op:'add_node',node:{id:'C1',kind:'context',title:'Value'}}],
   [{op:'add_edge',edge:{id:'D-1',type:'DERIVES',from:'R0',to:'R0'}}],
   [{op:'append_event',event:{id:'E',type:'action_selected',by:'user',note:'forge'}}],
   [{op:'set_context_value',contextId:'R0',fieldRef:{key:'cost'},value:1}],
  ];
  let seq=0;
  for(const ops of cases){const before=JSON.stringify(w.read());
   reject(w.run(w.patch(ops,2,'reject-'+seq++)),/ACTION_MODEL_GUARD|ACTION_QRPE_GUARD/);
   assert.equal(JSON.stringify(w.read()),before);
  }
  reject(w.run(w.patch([],2,'root-metadata',{rootRequirementId:'R2'})),/ACTION_MODEL_GUARD/);
  assert.equal(w.read().revision,2);
 }finally{w.cleanup();}
});
test('untrusted selected Action cannot mint a child Requirement or claim user consent',()=>{
 const w=sandbox();try{
  pass(w.create());pass(w.run(w.patch(added,1,'draft')));
  reject(w.run(w.patch(selected,2,'unsigned-selection')),/TRUST_REQUIRED/);
  assert.equal(w.read().revision,2);
  const body=w.signed(w.patch(selected,2,'invalid-signature'));
  body.changes[0].patch.operations[0].children[0].requirement.title='changed-after-sign';
  reject(w.run(body),/TRUST_SIGNATURE_INVALID/);
  assert.equal(w.read().revision,2);
  pass(w.run(w.signed(w.patch(selected,2,'approved-selection'))));
  const g=w.read();assert.equal(g.nodes.find(n=>n.id==='A1').status,'selected');
  assert.equal(g.nodes.find(n=>n.id==='R1').title,'Goal R1');
  const evt=g.events.find(e=>e.id==='EV-SELECT');
  assert.equal(evt.verifiedTrustReceipt.principal,'synthetic-integration-issuer');
  assert.equal(g.revision,3);
 }finally{w.cleanup();}
});
test('shared-R introduction and a QRPE state transition require separate scoped proof',()=>{
 const w=sandbox();try{
  pass(w.create());pass(w.run(w.patch(added,1,'draft')));
  pass(w.run(w.signed(w.patch(selected,2,'approved-selection'))));
  const extra=[{op:'add_action',requirementId:'R0',action:{id:'A2',kind:'action',title:'Independent',status:'candidate'}}];
  pass(w.run(w.patch(extra,3,'add-second')));
  pass(w.run(w.signed(w.patch([{
   op:'select_action',actionId:'A2',children:[],event:{id:'EV-A2',type:'action_selected',
    actionId:'A2',driverRequirementId:'R0',by:'assistant',note:'synthetic delegated selection'}
  }],4,'select-second'))));
  const link=[{op:'link_action_requirement',actionId:'A2',requirementId:'R1',edgeId:'LINK-A2-R1',childRole:'subgoal',
   event:{id:'EV-LINK',type:'action_requirement_linked',actionId:'A2',requirementId:'R1',
    edgeId:'LINK-A2-R1',driverRequirementId:'R0',by:'assistant',note:'synthetic independent support'}}];
  reject(w.run(w.patch(link,5,'unsigned-link')),/TRUST_REQUIRED/);
  pass(w.run(w.signed(w.patch(link,5,'signed-link'))));
  assert.equal(w.read().edges.filter(e=>e.to==='R1'&&e.type==='INTRODUCES').length,2);
  pass(w.run(w.patch([{op:'append_qrpe',targetId:'A1',issue:{id:'Q1',text:'Why?',status:'open'}}],6,'new-question')));
  const transition=[{op:'transition_qrpe',targetId:'A1',issueId:'Q1',
   transition:{id:'Q1-T1',recordedAt:'2026-10-17',status:'resolved',note:'Toy research'}}];
  reject(w.run(w.patch(transition,7,'unsigned-qrpe')),/TRUST_REQUIRED/);
  pass(w.run(w.signed(w.patch(transition,7,'signed-qrpe'))));
  const q=w.read().nodes.find(n=>n.id==='A1').qrpe.find(q=>q.id==='Q1');
  assert.equal(q.status,'resolved');
  assert.equal(q.statusHistory.at(-1).verifiedTrustReceipt.principal,'synthetic-integration-issuer');
 }finally{w.cleanup();}
});
test('no newly selected Action may be smuggled through opt-in graph creation without a receipt',()=>{
 const w=sandbox();try{
  const initial={schemaVersion:1,revision:1,id:'pilot',title:'Graph',planningScale:'module',
   identitySpace:'pilot',rootRequirementId:'R0',actionModel:'candidate-v6',
   nodes:[{id:'R0',kind:'requirement',title:'Root',status:'active'},
    {id:'A1',kind:'action',title:'Chosen',status:'selected'}],edges:[],events:[]};
  reject(w.run({schemaVersion:1,transactionId:'create-chosen',changes:[{file:'workspaces/pilot/graph.json',create:initial}]}),/TRUST_REQUIRED/);
 }finally{w.cleanup();}
});
