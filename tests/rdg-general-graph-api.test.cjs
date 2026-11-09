'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..');
const files=['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js',
 'rdg-modules.py','rdg-module-registry.json','rdg-module-test.py','graph-apply.py','graph-index.py','rdg-catalog.py','graph-package.py','rdg-transaction-io.py','rdg-v7-model.py',
 'rdg-v6-action-reconsider.py','rdg-v6-action-trust.py','rdg-graph-api.py'];
const canonical=x=>JSON.stringify(x,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?
 Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b,'en'))):v);
function sandbox(){
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-api-'));
 fs.mkdirSync(path.join(base,'tools'));
 for(const f of files)fs.copyFileSync(path.join(ROOT,'tools',f),path.join(base,'tools',f));
 const dest='workspaces/api/graph.json',graphPath=path.join(base,'graphs',dest);
 const key=crypto.randomBytes(32).toString('hex');
 function run(pkg){const p=path.join(base,'package.json');fs.writeFileSync(p,JSON.stringify(pkg));
  return spawnSync('python3',[path.join(base,'tools/graph-apply.py'),'--package','--patch',p],
  {encoding:'utf8',env:{...process.env,RDG_V6_TRUST_KEY:key,RDG_ISOLATED_TEST_ONLY:'1'}});
 }
 const graph={schemaVersion:1,revision:1,id:'api',title:'Graph API',planningScale:'module',identitySpace:'api',
 rootRequirementId:'R0',actionModel:'candidate-v6',nodes:[{id:'R0',kind:'requirement',title:'Root',status:'active'}],edges:[],events:[]};
 const create=()=>run({schemaVersion:1,transactionId:'bootstrap',changes:[{file:dest,create:graph}]});
 const patch=(operation,revision,id)=>({schemaVersion:1,transactionId:id,changes:[{
  file:dest,patch:{schemaVersion:1,expectedRevision:revision,operations:[structuredClone(operation)]}}]});
 function sign(pkg){const principal='synthetic-issuer',expiresAt=Math.floor(Date.now()/1000)+450;
  const op=pkg.changes[0].patch.operations[0];
  op.event.authorityPrincipal=principal;
  const claim={purpose:'rdg-v6-material-action-v1',principal,expiresAt};
  const payload={transactionId:pkg.transactionId,changes:pkg.changes,principal,expiresAt,purpose:claim.purpose};
  claim.signature=crypto.createHmac('sha256',key).update(canonical(payload)).digest('hex');
  pkg.trustedApproval=claim;return pkg;
 }
 let seq=0;
 function cmd(action,rest={},by='assistant'){const id='E'+(++seq);return {op:'graph_edit',action,...structuredClone(rest),
 event:{id,type:'graph_changed',operation:action,by,note:'Meaningful synthetic action for sandbox test'}};}
 return {run,graphPath,create,patch,sign,cmd,read:()=>JSON.parse(fs.readFileSync(graphPath,'utf8')),
  cleanup:()=>fs.rmSync(base,{recursive:true,force:true})};
}
function success(r){assert.equal(r.status,0,r.stderr||r.stdout);}
function rejected(r,regex){assert.notEqual(r.status,0,r.stdout);assert.match(r.stderr,regex);}
test('general graph API creates/updates/deletes via signed normal operations (not Lens)',()=>{
 const w=sandbox();try{
  success(w.create());
  const node={id:'R1',kind:'requirement',title:'Research',status:'active'};
  const create=w.cmd('create_requirement',{node,parentRequirementId:'R0',edgeId:'R0-DERIVES-R1'});
  rejected(w.run(w.patch(create,1,'unsigned')),/TRUST_REQUIRED/);
  success(w.run(w.sign(w.patch(create,1,'create-r'))));
  assert.equal(w.read().events[0].verifiedTrustReceipt.principal,'synthetic-issuer');
  const update=w.cmd('edit_node',{nodeId:'R1',changes:{title:'Investigate new options',concept:'Decision value'}});
  success(w.run(w.sign(w.patch(update,2,'edit-r'))));
  assert.equal(w.read().nodes.find(n=>n.id==='R1').concept,'Decision value');
  const archive=w.cmd('archive_edge',{edgeId:'R0-DERIVES-R1'});
  success(w.run(w.sign(w.patch(archive,3,'unlink-r'))));
  const deactivate=w.cmd('deactivate_requirement',{nodeId:'R1'});
  success(w.run(w.sign(w.patch(deactivate,4,'inactive-r'))));
  assert.equal(w.read().nodes.find(n=>n.id==='R1').status,'inactive');
  assert.equal(w.read().events.length,4);
  const history=w.read().events.find(e=>e.type==='requirement_reformulated');
  assert.equal(history.priorNodeSnapshot.title,'Research');
  assert.equal(history.previousRequirementSnapshot.title,'Research');
  assert.equal(history.newRequirementSnapshot.title,'Investigate new options');
 }finally{w.cleanup();}
});
test('archived-only R can be removed with snapshot, but not if still attached',()=>{
 const w=sandbox();try{
  success(w.create());
  success(w.run(w.sign(w.patch(w.cmd('create_requirement',
   {node:{id:'R2',kind:'requirement',title:'Temporary'},parentRequirementId:'R0',edgeId:'D-R2'}),1,'make-r2'))));
  rejected(w.run(w.sign(w.patch(w.cmd('delete_orphan_requirement',{nodeId:'R2'}),2,'reject-r2'))),
   /REQUIREMENT_HAS_DEPENDENTS/);
  success(w.run(w.sign(w.patch(w.cmd('archive_edge',{edgeId:'D-R2'}),2,'archive-r2'))));
  success(w.run(w.sign(w.patch(w.cmd('delete_orphan_requirement',{nodeId:'R2'}),3,'delete-r2'))));
  assert(!w.read().nodes.some(n=>n.id==='R2'));
  assert(!w.read().edges.some(e=>e.from==='R2'||e.to==='R2'));
  assert.equal(w.read().events.at(-1).priorNodeSnapshot.id,'R2');
  assert.equal(w.read().events.at(-1).priorEdges[0].id,'D-R2');
 }finally{w.cleanup();}
});
test('reconsideration policy is separate from truth and blocks unapproved user-R edits',()=>{
 const w=sandbox();try{
  success(w.create());
  const policy=w.cmd('set_reconsideration_policy',{nodeId:'R0',policy:{mode:'protected',authorityPrincipal:'synthetic-issuer'}},'user');
  success(w.run(w.sign(w.patch(policy,1,'policy'))));
  const edit=w.cmd('edit_node',{nodeId:'R0',changes:{title:'Changed goal'}});
  rejected(w.run(w.sign(w.patch(edit,2,'bad-edit'))),/PROTECTED_OWNER_GRANT_REQUIRED/);
  const good=w.cmd('edit_node',{nodeId:'R0',changes:{title:'Clarified goal'}},'user');
  success(w.run(w.sign(w.patch(good,2,'owner-edit'))));
  assert.equal(w.read().nodes[0].title,'Clarified goal');
  assert.equal(w.read().events[1].priorNodeSnapshot.title,'Root');
 }finally{w.cleanup();}
});
test('hard delete never silently destroys selected history or shared support',()=>{
 const w=sandbox();try{
  success(w.create());
  const node={id:'R1',kind:'requirement',title:'Active requirement'};
  success(w.run(w.sign(w.patch(w.cmd('create_requirement',
   {node,parentRequirementId:'R0',edgeId:'derive'}),1,'create'))));
  const deleteR=w.cmd('delete_orphan_requirement',{nodeId:'R1'});
  rejected(w.run(w.sign(w.patch(deleteR,2,'bad-delete'))),/REQUIREMENT_HAS_DEPENDENTS/);
  const createA={op:'add_action',requirementId:'R0',action:{id:'A1',kind:'action',title:'Unselected',status:'candidate'}};
  success(w.run({schemaVersion:1,transactionId:'create-a',changes:[{file:'workspaces/api/graph.json',
   patch:{schemaVersion:1,expectedRevision:2,operations:[createA]}}]}));
  const deleteA=w.cmd('delete_candidate',{nodeId:'A1'});
  success(w.run(w.sign(w.patch(deleteA,3,'delete-a'))));
  assert(!w.read().nodes.some(n=>n.id==='A1'));
  assert(w.read().events.at(-1).targetDeleted);
  assert.equal(w.read().events.at(-1).priorNodeSnapshot.id,'A1');
 }finally{w.cleanup();}
});
test('protected parent blocks unapproved child, edge removal and reparent (authorized owner allowed)',()=>{
 const w=sandbox();try{
  success(w.create());
  success(w.run(w.sign(w.patch(w.cmd('set_reconsideration_policy',
   {nodeId:'R0',policy:{mode:'protected',authorityPrincipal:'synthetic-issuer'}},'user'),1,'protect-root'))));
  let bad=w.cmd('create_requirement',{node:{id:'R1',kind:'requirement',title:'Unapproved'},
   parentRequirementId:'R0',edgeId:'E-DERIVES-R1'});
  rejected(w.run(w.sign(w.patch(bad,2,'bad-child'))),/PROTECTED_OWNER_GRANT_REQUIRED/);
  assert.equal(w.read().revision,2);
  const good=w.cmd('create_requirement',{node:{id:'R1',kind:'requirement',title:'Allowed'},
   parentRequirementId:'R0',edgeId:'E-DERIVES-R1'},'user');
  success(w.run(w.sign(w.patch(good,2,'allowed-child'))));
  bad=w.cmd('add_edge',{edge:{id:'der-2',type:'DERIVES',from:'R0',to:'R1'}});
  rejected(w.run(w.sign(w.patch(bad,3,'bad-edge'))),/PROTECTED_OWNER_GRANT_REQUIRED/);
  bad=w.cmd('archive_edge',{edgeId:'E-DERIVES-R1'});
  rejected(w.run(w.sign(w.patch(bad,3,'bad-detach'))),/PROTECTED_OWNER_GRANT_REQUIRED/);
  const ownArchive=w.cmd('archive_edge',{edgeId:'E-DERIVES-R1'},'user');
  success(w.run(w.sign(w.patch(ownArchive,3,'allow-detach'))));
  assert.equal(w.read().edges[0].archived,true);
 }finally{w.cleanup();}
});
test('general reparent is history-preserving and safe for active DAG requirements',()=>{
 const w=sandbox();try{
  success(w.create());
  function cr(nodeId,parent,edge,rev){
   success(w.run(w.sign(w.patch(w.cmd('create_requirement',{
    node:{id:nodeId,kind:'requirement',title:nodeId},
    parentRequirementId:parent,edgeId:edge}),rev,'make-'+nodeId))));
  }
  cr('R1','R0','root-r1',1);
  cr('R2','R0','root-r2',2);
  const move=w.cmd('reparent_requirement',{nodeId:'R1',newParentRequirementId:'R2',newEdgeId:'r2-r1'});
  success(w.run(w.sign(w.patch(move,3,'move-r1'))));
  const after=w.read();
  assert.equal(after.edges.find(e=>e.id==='root-r1').archived,true);
  assert.deepEqual(after.events.at(-1).priorEdges.map(e=>e.id),['root-r1']);
  assert.equal(after.edges.find(e=>e.id==='r2-r1').to,'R1');
  rejected(w.run(w.sign(w.patch(w.cmd('reparent_requirement',{
   nodeId:'R2',newParentRequirementId:'R1',newEdgeId:'cycle'}),4,'cycle-r2'))),/cycle in plan/);
  assert.equal(w.read().revision,4);
 }finally{w.cleanup();}
});
test('protected parent also gates selected Action introductions and shared-R link',()=>{
 const w=sandbox();try{
  success(w.create());
  const pol=w.cmd('set_reconsideration_policy',{
    nodeId:'R0',policy:{mode:'protected',authorityPrincipal:'synthetic-issuer'}},'user');
  success(w.run(w.sign(w.patch(pol,1,'protect-select'))));
  const add=(id,rev)=>w.run({schemaVersion:1,transactionId:'add-'+id,changes:[{
   file:'workspaces/api/graph.json',patch:{schemaVersion:1,expectedRevision:rev,
    operations:[{op:'add_action',requirementId:'R0',action:{id,kind:'action',title:id,status:'candidate'}}]}}]});
  success(add('A1',2));
  const selected=(id,evId,by,children=[])=>({op:'select_action',actionId:id,children,event:{
   id:evId,type:'action_selected',by,actionId:id,driverRequirementId:'R0',
   note:'Selected in isolated test'}});
  const child={requirement:{id:'R1',kind:'requirement',title:'New child R'},role:'subgoal'};
  rejected(w.run(w.sign(w.patch(selected('A1','SEL1','assistant',[child]),3,'unapproved-action'))),
   /PROTECTED_OWNER_GRANT_REQUIRED/);
  assert.equal(w.read().revision,3);
  success(w.run(w.sign(w.patch(selected('A1','SEL2','user',[child]),3,'owner-action'))));
  const setChild=w.cmd('set_reconsideration_policy',{nodeId:'R1',
   policy:{mode:'protected',authorityPrincipal:'synthetic-issuer'}},'user');
  success(w.run(w.sign(w.patch(setChild,4,'protect-child'))));
  success(add('A2',5));
  success(w.run(w.sign(w.patch(selected('A2','SEL3','assistant'),6,'select-no-introduction'))));
  const link=(by,evId)=>({op:'link_action_requirement',actionId:'A2',requirementId:'R1',
   edgeId:'A2-TO-R1',childRole:'subgoal',event:{id:evId,type:'action_requirement_linked',
    by,actionId:'A2',requirementId:'R1',driverRequirementId:'R0',edgeId:'A2-TO-R1',
    note:'Linking independently supported R'}});
  rejected(w.run(w.sign(w.patch(link('assistant','LINK-BAD'),7,'unapproved-link'))),
   /PROTECTED_OWNER_GRANT_REQUIRED/);
  success(w.run(w.sign(w.patch(link('user','LINK-OK'),7,'owner-link'))));
  assert.equal(w.read().edges.find(e=>e.id==='A2-TO-R1').type,'INTRODUCES');
 }finally{w.cleanup();}
});
test('Requirement reformulation preserves old/new snapshots and does not rewrite existing Actions or subgoals',()=>{
 const w=sandbox();try{
  success(w.create());
  const child=w.cmd('create_requirement',{node:{id:'R1',kind:'requirement',title:'Dependent goal'},
    parentRequirementId:'R0',edgeId:'DERIVE-R1'});
  success(w.run(w.sign(w.patch(child,1,'create-child'))));
  const before=w.read(),event=w.cmd('reformulate_requirement',{
    nodeId:'R0',changes:{title:'Reformulated root',requirementText:'Achieve scope B'}},'user');
  success(w.run(w.sign(w.patch(event,2,'reformulate-root'))));
  const after=w.read(),item=after.events.at(-1);
  assert.equal(item.type,'requirement_reformulated');
  assert.equal(item.operation,'reformulate_requirement');
  assert.equal(item.previousRequirementSnapshot.title,'Root');
  assert.equal(item.newRequirementSnapshot.title,'Reformulated root');
  assert.equal(item.newRequirementSnapshot.requirementText,'Achieve scope B');
  assert.equal(item.targetId,'R0');
  const reader=`from importlib.machinery import SourceFileLoader
import json,sys
`+
    `m=SourceFileLoader('rdg_activity_reader',sys.argv[1]).load_module()
`+
    `result=m.read_activity(sys.argv[2],['workspaces/api/graph.json'])
`+
    `print(json.dumps(result['activities']))`;
  const history=spawnSync('python3',['-B','-c',reader,path.join(ROOT,'tools/rdg-activity.py'),
    path.join(path.dirname(w.graphPath),'../..')],
    {encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
  assert.equal(history.status,0,history.stderr);
  const reform=JSON.parse(history.stdout).find(e=>e.kind==='requirement_reformulated');
  assert(reform,'real activity reader must preserve the distinct reformulation event');
  assert.equal(reform.targetId,'R0');
  assert.equal(reform.previousRequirementSnapshot.title,'Root');
  assert.equal(reform.newRequirementSnapshot.title,'Reformulated root');
  assert.equal(item.authorityPrincipal,'synthetic-issuer');
  assert(item.verifiedTrustReceipt);
  assert.equal(after.nodes.length,before.nodes.length,'no duplicate goal created');
  assert.deepEqual(after.nodes.find(n=>n.id==='R1'),before.nodes.find(n=>n.id==='R1'),
    'subgoals are queued for review, not silently rewritten');
  const bad=w.cmd('reformulate_requirement',{nodeId:'R0',changes:{title:'Reformulated root'}},'user');
  rejected(w.run(w.sign(w.patch(bad,3,'no-change'))),/REFORMULATE_EXPLICIT_MEANINGFUL_CHANGE_REQUIRED/);
  const stolen=w.cmd('reformulate_requirement',{nodeId:'R0',changes:{title:'Not approved'}},'assistant');
  rejected(w.run(w.sign(w.patch(stolen,3,'owner-only'))),/ROOT_REQUIREMENT_REQUIRES_OWNER/);
  assert.equal(w.read().revision,3);
 }finally{w.cleanup();}
});
