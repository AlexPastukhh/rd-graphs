const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const crypto=require('node:crypto');
const stable=x=>JSON.stringify(x,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b,'en'))):v);
const ROOT=path.resolve(__dirname,'..');
const projection=require('../tools/rdg-root-projection.js');
const REQUIRED=['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js',
  'rdg-modules.py','rdg-module-registry.json','rdg-module-test.py','graph-apply.py','graph-index.py','rdg-catalog.py','graph-package.py','rdg-transaction-io.py','rdg-v7-model.py','rdg-completion-context.py',
  'rdg-v6-action-reconsider.py','rdg-v6-action-trust.py'];
function setup(){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-v6-action-writer-'));
 fs.mkdirSync(path.join(dir,'tools'),{recursive:true});
 for(const file of REQUIRED)fs.copyFileSync(path.join(ROOT,'tools',file),path.join(dir,'tools',file));
 const graphPath=path.join(dir,'graphs/workspaces/action-pilot/graph.json');
 const request=path.join(dir,'request.json');
 const key=crypto.randomBytes(32).toString('hex');
 const expiresAt=Math.floor(Date.now()/1000)+500;
 function run(pkg,flags=[]){
  const ops=pkg.changes.flatMap(c=>(c.patch||{}).operations||[]);
  if(ops.some(op=>['select_action','link_action_requirement','reconsider_action','transition_qrpe'].includes(op.op))){
   for(const op of ops){
    if(op.op==='transition_qrpe')op.authorityPrincipal='synthetic-issuer';
    else if(['select_action','link_action_requirement','reconsider_action'].includes(op.op))
     op.event.authorityPrincipal='synthetic-issuer';
   }
   const claim={purpose:'rdg-v6-material-action-v1',principal:'synthetic-issuer',expiresAt};
   const payload={transactionId:pkg.transactionId,changes:pkg.changes,principal:claim.principal,
    expiresAt,purpose:claim.purpose};
   claim.signature=crypto.createHmac('sha256',key).update(stable(payload)).digest('hex');
   pkg.trustedApproval=claim;
  }
  fs.writeFileSync(request,JSON.stringify(pkg));
  return spawnSync('python3',[path.join(dir,'tools/graph-apply.py'),'--package',
    '--patch',request,...flags],{encoding:'utf8',env:{...process.env,RDG_ISOLATED_TEST_ONLY:'1',RDG_V6_TRUST_KEY:key}});
 }
 function runPatch(ops,expectedRevision,tid){
  return run({schemaVersion:1,transactionId:tid,changes:[{
   file:'workspaces/action-pilot/graph.json',
   patch:{schemaVersion:1,expectedRevision,operations:ops}
  }]});
 }
 const initial={schemaVersion:1,revision:1,id:'action-pilot',title:'Action pilot',
  planningScale:'module',identitySpace:'action-pilot',rootRequirementId:'R0',
  actionModel:'candidate-v6',
  nodes:[{id:'R0',kind:'requirement',title:'Достичь результата',status:'active'}],
  edges:[],events:[]};
 const create={schemaVersion:1,transactionId:'create-action-pilot',changes:[{
  file:'workspaces/action-pilot/graph.json',create:initial
 }]};
 const read=()=>JSON.parse(fs.readFileSync(graphPath,'utf8'));
 const a={id:'A1',kind:'action',title:'Разложить реализацию',status:'candidate',
  canonBlock:{recommended:[{id:'C1',text:'Декомпозиция уменьшает сложность'}],contraindicated:[]},
  qrpe:[{id:'Q1',text:'Не создаст ли декомпозиция лишнюю работу?',status:'open'}]};
 const add=[{op:'add_action',requirementId:'R0',action:a}];
 const select=[{op:'select_action',actionId:'A1',event:{id:'E1',type:'action_selected',
    actionId:'A1',driverRequirementId:'R0',by:'user',
    note:'Это учебное, явно атрибутированное решение — не выбор в реальном проекте'},
  children:[
    {role:'subgoal',requirement:{id:'R1',kind:'requirement',title:'Реализовать часть 1'}},
    {role:'subgoal',requirement:{id:'R2',kind:'requirement',title:'Реализовать часть 2'}}
  ]}];
 return {dir,run,runPatch,graphPath,create,read,initial,add,select,
  cleanup:()=>fs.rmSync(dir,{force:true,recursive:true})};
}
function mustPass(res){assert.equal(res.status,0,res.stderr||res.stdout);}
function mustFail(res,pattern){assert.notEqual(res.status,0,res.stdout);assert.match(res.stderr,pattern);}
function singleGraph(g){
 return {graphs:[{slug:'action-pilot',graph:g,group:'workspaces',folder:'workspaces'}],
   relations:[]};
}

test('real package writer creates opt-in Action graph with legacy schemaVersion 1',()=>{
 const w=setup();try{
  mustPass(w.run(w.create));
  const g=w.read();
  assert.equal(g.schemaVersion,1);
  assert.equal(g.actionModel,'candidate-v6');
  assert.deepEqual(g.events,[]);
  assert.equal(g.revision,1);
 }finally{w.cleanup();}
});

test('writer selects same Action ID with T1 evidence and grouped child Requirements',()=>{
 const w=setup();try{
  mustPass(w.run(w.create));
  mustPass(w.runPatch(w.add,1,'add-action'));
  const candidate=w.read();
  assert.equal(candidate.revision,2);
  assert.equal(candidate.nodes.find(n=>n.id==='A1').status,'candidate');
  assert.deepEqual(candidate.events,[]);
  assert.equal(candidate.edges.find(e=>e.to==='A1').type,'DRIVES');
  mustPass(w.runPatch(w.select,2,'select-action'));
  const g=w.read();
  assert.equal(g.revision,3);
  assert.equal(g.nodes.find(n=>n.id==='A1').status,'selected');
  assert.equal(g.nodes.filter(n=>n.kind==='action').length,1);
  assert.equal(g.nodes.filter(n=>n.kind==='decision').length,0);
  const a=g.nodes.find(n=>n.id==='A1');
  assert.equal(a.selectionBasis.actionSnapshot.id,'A1');
  assert.equal(a.selectionBasis.actionSnapshot.status,'candidate');
  assert.equal(a.selectionBasis.driverSnapshot.id,'R0');
  assert.equal(a.qrpe[0].id,'Q1');
  assert.equal(g.events[0].actionId,'A1');
  assert.equal(g.events[0].by,'user');
  assert.deepEqual(g.edges.filter(e=>e.type==='INTRODUCES').map(e=>e.to),['R1','R2']);
  // The index+reader projection sees the actual child goals without D.
  const tree=projection.project(singleGraph(g),'action-pilot');
  const selected=tree.edges.filter(e=>e.kind==='selected');
  assert.deepEqual(selected.map(e=>e.to).sort(),['R1','R2']);
  assert(selected.every(e=>e.causeKind==='action' && e.causeId==='A1'));
  mustPass(w.runPatch(w.select,2,'select-action')); // same request is idempotent
  assert.equal(w.read().revision,3);
 }finally{w.cleanup();}
});

test('canonical writer rejects a legacy Graph even when old validators can read it',()=>{
 const w=setup();try{
  const legacy=structuredClone(w.initial);delete legacy.actionModel;legacy.id='legacy-pilot';
  w.create.changes[0].create=legacy;
  mustFail(w.run(w.create),/ACTIVE_ONLY_CANDIDATE_V6/);
  assert(!fs.existsSync(path.join(w.dir,'graphs/workspaces/action-pilot/graph.json')),'rejected legacy create must not write an owner');
 }finally{w.cleanup();}
});

test('plain add_node cannot bypass the closed active Graph writer',()=>{
 const w=setup();try{
  mustPass(w.run(w.create));
  const before=JSON.stringify(w.read()),a=structuredClone(w.add[0].action);
  mustFail(w.runPatch([{op:'add_node',node:a}],1,'bad-kind'),/ACTION_MODEL_GUARD/);
  assert.equal(JSON.stringify(w.read()),before);
 }finally{w.cleanup();}
});

test('unattributed or fake-actor Action selection leaves graph and revision unchanged',()=>{
 const w=setup();try{
  mustPass(w.run(w.create));mustPass(w.runPatch(w.add,1,'add-action'));
  for(const by of ['template','example',null]){
   const before=JSON.stringify(w.read()),bad=structuredClone(w.select);
   bad[0].event.by=by;
   mustFail(w.runPatch(bad,2,'bad-actor-'+String(by).replace(/[^a-z]/g,'')),/attributed material event/);
   assert.equal(JSON.stringify(w.read()),before);
  }
  const tampered=structuredClone(w.select);
  tampered[0].event.actionId='A-OTHER';
  mustFail(w.runPatch(tampered,2,'wrong-action-event'),/attributed material event/);
  assert.equal(w.read().revision,2);
 }finally{w.cleanup();}
});

test('selection requires real existing Action and protects candidate versus selected identity',()=>{
 const w=setup();try{
  mustPass(w.run(w.create));
  mustFail(w.runPatch(w.select,1,'no-action-yet'),/current candidate/);
  mustPass(w.runPatch(w.add,1,'add-action'));
  const patched=structuredClone(w.select);patched[0].children[1].requirement.id='R1';
  mustFail(w.runPatch(patched,2,'duplicate-child'),/selected child requires new Requirement/);
  assert.equal(w.read().nodes.find(n=>n.id==='A1').status,'candidate');
  mustPass(w.runPatch(w.select,2,'choose-correctly'));
  mustFail(w.runPatch(w.select,3,'choose-again'),/current candidate/);
  assert.equal(w.read().revision,3);
 }finally{w.cleanup();}
});

test('generic update_node cannot rewrite Action or normative Requirement in opt-in graph',()=>{
 const w=setup();try{
  mustPass(w.run(w.create));mustPass(w.runPatch(w.add,1,'add-action'));
  mustPass(w.runPatch(w.select,2,'select-action'));
  for(const [id,changes,pattern] of [
   ['A1',{title:'Переименован'},/ACTION_HISTORY_GUARD|ACTION_MODEL_GUARD/],
   ['A1',{status:'candidate'},/ACTION_HISTORY_GUARD|ACTION_MODEL_GUARD/],
   ['R0',{title:'Новая скрытая цель'},/REQUIREMENT_HISTORY_GUARD|ACTION_MODEL_GUARD/],
   ['R1',{status:'inactive'},/REQUIREMENT_HISTORY_GUARD|ACTION_MODEL_GUARD/]
  ]){
   mustFail(w.runPatch([{op:'update_node',id,changes}],3,'edit-'+id+'-'+Object.keys(changes)[0]),pattern);
   assert.equal(w.read().revision,3);
  }
 }finally{w.cleanup();}
});

test('reader rejects fake selected state without matching event and avoids false prepared adoption',()=>{
 const w=setup();try{
  mustPass(w.run(w.create));mustPass(w.runPatch(w.add,1,'add-action'));
  const raw=w.read();
  const fabricated=structuredClone(raw);
  const a=fabricated.nodes.find(n=>n.id==='A1');
  a.status='selected';
  fabricated.nodes.push({id:'R1',kind:'requirement',title:'Untrusted child'});
  fabricated.edges.push({id:'fake',type:'INTRODUCES',from:'A1',to:'R1',parent:'R0'});
  let tree=projection.project(singleGraph(fabricated),'action-pilot');
  assert.equal(tree.edges.filter(e=>e.kind==='selected').length,0);
  mustFail(w.runPatch([{op:'update_node',id:'A1',changes:{status:'selected'}}],2,'forge-selected'),
    /ACTION_HISTORY_GUARD|ACTION_MODEL_GUARD/);
 }finally{w.cleanup();}
});

test('failed revision or child transaction never commits a partial Action',()=>{
 const w=setup();try{
  mustPass(w.run(w.create));
  const bad=structuredClone(w.add);
  bad[0].action.id='R0';
  mustFail(w.runPatch(bad,1,'duplicate-action-id'),/Action ID collision/);
  assert.equal(w.read().revision,1);
  mustPass(w.runPatch(w.add,1,'add-action'));
  mustFail(w.runPatch(w.select,1,'stale-revision'),/REVISION_CONFLICT/);
  assert.equal(w.read().revision,2);
 }finally{w.cleanup();}
});
test('Action accepts append-only QRPE without splitting into Option and Decision',()=>{
 const w=setup();try{
  mustPass(w.run(w.create));
  mustPass(w.runPatch(w.add,1,'add-action'));
  const issue={id:'Q2',text:'Проверить неизвестную зависимость',status:'open'};
  mustPass(w.runPatch([{op:'append_qrpe',targetId:'A1',issue}],2,'append-qrpe'));
  const g=w.read();
  assert.equal(g.nodes.find(n=>n.id==='A1').qrpe.length,2);
  assert.equal(g.nodes.find(n=>n.id==='A1').qrpe[1].status,'open');
  assert(!g.nodes.some(n=>n.kind==='decision'||n.kind==='option'));
  mustPass(w.runPatch([{op:'transition_qrpe',targetId:'A1',issueId:'Q2',
    transition:{id:'Q2-CLOSE',recordedAt:'T2',status:'resolved',note:'Проверено в учебном контексте'}}],
    3,'transition-qrpe'));
  const q=w.read().nodes.find(n=>n.id==='A1').qrpe[1];
  assert.equal(q.status,'resolved');
  assert.equal(q.statusHistory.at(-1).id,'Q2-CLOSE');
 }finally{w.cleanup();}
});

test('invalid Action canon and unscoped action model fail before writing',()=>{
 const w=setup();try{
  mustPass(w.run(w.create));
  const bad=structuredClone(w.add);
  bad[0].action.canonBlock.recommended.push({id:'C1',text:'Duplicate ID'});
  mustFail(w.runPatch(bad,1,'duplicate-canon'),/duplicate Action canon case/);
  assert.equal(w.read().revision,1);
 }finally{w.cleanup();}
});

test('cross-file reader recognizes selected Action introducing a root Requirement',()=>{
 const w=setup();try{
  mustPass(w.run(w.create));
  mustPass(w.runPatch(w.add,1,'add-action'));
  mustPass(w.runPatch(w.select,2,'select-action'));
  const child={
   schemaVersion:1,revision:1,id:'action-child',title:'Child R expansion',
   planningScale:'unit',identitySpace:'action-pilot',rootRequirementId:'R1',
   actionModel:'candidate-v6',
   nodes:[{id:'R1',kind:'requirement',title:'Реализовать часть 1',
     projectionOf:{graphSlug:'action-pilot',nodeId:'R1'}}],
   edges:[],events:[]
  };
  const res=w.run({schemaVersion:1,transactionId:'create-child',changes:[{
   file:'workspaces/action-child/graph.json',create:child
  }]});
  mustPass(res);
  const script=[
   'import json,importlib.machinery,sys',
   'm=importlib.machinery.SourceFileLoader("idx",sys.argv[1]).load_module()',
   'manifest,bundle=m.build_catalog()',
   'print(json.dumps({"relations":manifest["relations"],"graphs":bundle["graphs"]}))'
  ].join('\n');
  const output=spawnSync('python3',['-c',script,path.join(w.dir,'tools/graph-index.py')],
    {encoding:'utf8'});
  assert.equal(output.status,0,output.stderr);
  const parsed=JSON.parse(output.stdout);
  const relation=parsed.relations.find(x=>x.from==='action-pilot'&&x.to==='action-child');
  assert(relation);
  assert.equal(relation.requirementId,'R1');
  assert.equal(relation.introducedByActionId,'A1');
  assert.equal(relation.introducedByDecisionId,undefined);
  assert.equal(relation.relationKind,'selected');
  const tree=projection.project({
   graphs:parsed.graphs,relations:parsed.relations
  },'action-pilot');
  assert(tree.edges.some(e=>e.from==='R0'&&e.to==='R1'&&e.causeKind==='action'));
 }finally{w.cleanup();}
});

test('real application-format graph.json fixture validates and projects Action without Decision',()=>{
 const file=path.join(ROOT,'tests/fixtures/rdg-v6-action-optin/graph.json');
 const g=JSON.parse(fs.readFileSync(file,'utf8'));
 assert.equal(g.schemaVersion,1);
 assert.equal(g.actionModel,'candidate-v6');
 assert.deepEqual(g.nodes.filter(n=>n.kind==='action').map(n=>n.id),['A1']);
 assert(!g.nodes.some(n=>n.kind==='decision'));
 assert.equal(g.events.length,1);
 const js=projection.project({graphs:[{slug:'fixture',graph:g,group:'workspaces'}],
   relations:[]},'fixture');
 assert.deepEqual(js.edges.filter(e=>e.kind==='selected').map(e=>e.to).sort(),['R1','R2']);
});

test('generic Action or child edge mutation is rejected even after selected event',()=>{
 const w=setup();try{
  mustPass(w.run(w.create));
  mustFail(w.runPatch([{op:'add_node',node:w.add[0].action}],1,'forged-add'),
    /ACTION_HISTORY_GUARD|ACTION_MODEL_GUARD/);
  assert.equal(w.read().revision,1);
  mustPass(w.runPatch(w.add,1,'add-action'));
  mustPass(w.runPatch(w.select,2,'selected-action'));
  const badR=[{op:'add_node',node:{id:'R3',kind:'requirement',title:'New child'}},
    {op:'add_edge',edge:{id:'illegal-child',type:'INTRODUCES',from:'A1',to:'R3',parent:'R0'}}];
  mustFail(w.runPatch(badR,3,'silent-child'),/ACTION_HISTORY_GUARD|ACTION_MODEL_GUARD/);
  assert(!w.read().nodes.some(n=>n.id==='R3'));
  assert.equal(w.read().revision,3);
 }finally{w.cleanup();}
});

