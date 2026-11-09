const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const base=path.resolve(__dirname,'..');
const updater=path.join(base,'tools/graph-apply.py');
const root=path.join(base,'graphs','workspaces');
function setup(){
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-apply-test-'));
 const dir=path.join(temp,'graphs/workspaces/test');fs.mkdirSync(dir,{recursive:true});
 fs.mkdirSync(path.join(temp,'tools'));
 for(const file of ['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js','rdg-modules.py','rdg-module-registry.json','rdg-module-test.py','graph-apply.py','graph-index.py','rdg-catalog.py','graph-package.py','rdg-transaction-io.py','rdg-v7-model.py'])fs.copyFileSync(path.join(base,'tools',file),path.join(temp,'tools',file));
 const graph=path.join(dir,'graph.json'),patch=path.join(dir,'patch.json');
 const initial={schemaVersion:1,id:'test-cli',revision:1,title:'Test',
   nodes:[{id:'R-001',kind:'requirement',title:'Goal'}],edges:[],events:[]};
 fs.writeFileSync(graph,JSON.stringify(initial));
 const run=(doc,dry=false)=>{
   fs.writeFileSync(patch,JSON.stringify(doc));
   return spawnSync('python3',[path.join(temp,'tools/graph-apply.py'),'--graph',graph,'--patch',patch,
     ...(dry?['--dry-run']:[])],{encoding:'utf8',env:{...process.env,RDG_ISOLATED_TEST_ONLY:'1'}});
 };
 const read=()=>JSON.parse(fs.readFileSync(graph,'utf8'));
 const clean=()=>fs.rmSync(temp,{recursive:true,force:true});
 return {run,read,clean};
}
const accepted={schemaVersion:1,expectedRevision:1,operations:[
 {op:'add_node',node:{id:'D-001',kind:'decision',title:'Decompose',status:'committed'}},
 {op:'add_node',node:{id:'R-002',kind:'requirement',title:'Child'}},
 {op:'add_edge',edge:{id:'E-001',type:'DRIVES',from:'R-001',to:'D-001'}},
 {op:'add_edge',edge:{id:'E-002',type:'INTRODUCES',from:'D-001',to:'R-002',parent:'R-001'}},
 {op:'append_event',event:{id:'EV-001',type:'decision_selected',
   decisionId:'D-001',by:'user',note:'User explicitly selected this demo answer'}}
]};
test('CLI dry-run validates without changing graph or revision',()=>{
 const x=setup();
 try{
  const result=x.run(accepted,true);
  assert.equal(result.status,0,result.stderr);
  assert.match(result.stdout,/DRY_RUN changed=True revision=1 -> 2/);
  assert.equal(x.read().revision,1);assert.equal(x.read().nodes.length,1);
 }finally{x.clean();}
});
test('CLI acceptance atomically updates nodes edges events',()=>{
 const x=setup();
 try{
  const result=x.run(accepted);
  assert.equal(result.status,0,result.stderr);
  assert.match(result.stdout,/APPLIED revision=1 -> 2/);
  const g=x.read();
  assert.equal(g.revision,2);assert.equal(g.nodes.length,3);
  assert.equal(g.edges.length,2);assert.equal(g.events.length,1);
 }finally{x.clean();}
});
test('CLI stale expectedRevision rejects without modifying graph',()=>{
 const x=setup();
 try{
  assert.equal(x.run(accepted).status,0);
  const g=JSON.stringify(x.read());
  const result=x.run(accepted);
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/REVISION_CONFLICT/);
  assert.equal(JSON.stringify(x.read()),g);
 }finally{x.clean();}
});
test('CLI no-op does not increase revision',()=>{
 const x=setup();
 try{
  const result=x.run({schemaVersion:1,expectedRevision:1,operations:[]});
  assert.equal(result.status,0,result.stderr);
  assert.match(result.stdout,/NO_CHANGE revision=1/);
  assert.equal(x.read().revision,1);
 }finally{x.clean();}
});
test('CLI rejects D without decision_selected event',()=>{
 const x=setup();
 try{
  const p=structuredClone(accepted);
  p.operations=p.operations.filter(op=>op.op!=='append_event');
  const result=x.run(p);
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/decision_selected/);
  assert.equal(x.read().revision,1);
 }finally{x.clean();}
});
test('CLI rejects wrong parent semantics and keeps file',()=>{
 const x=setup();
 try{
  const p=structuredClone(accepted);
  p.operations.find(op=>op.op==='add_edge'&&op.edge.type==='INTRODUCES').edge.parent='R-002';
  const result=x.run(p);
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/parent must drive/);
  assert.equal(x.read().revision,1);
 }finally{x.clean();}
});
test('CLI rejects cyclical decomposition',()=>{
 const x=setup();
 try{
  const p=structuredClone(accepted);
  p.operations.push({op:'add_edge',edge:{id:'E-003',type:'DERIVES',from:'R-002',to:'R-001'}});
  const result=x.run(p);
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/cycle in plan/);
  assert.equal(x.read().edges.length,0);
 }finally{x.clean();}
});
test('CLI rejects unsupported operations',()=>{
 const x=setup();
 try{
  const result=x.run({schemaVersion:1,expectedRevision:1,operations:[{op:'delete_all'}]});
  assert.notEqual(result.status,0);assert.match(result.stderr,/unsupported operation/);
  assert.equal(x.read().revision,1);
 }finally{x.clean();}
});
test('pilot try-it file remains initial until user selects D',()=>{
 const file=path.join(base,'graphs/workspaces/try-it/graph.json'),g=JSON.parse(fs.readFileSync(file));
 assert.equal(g.revision,1);
 assert.deepEqual(g.edges,[]);
 assert.equal(g.nodes.length,1);
 assert.deepEqual(g.events,[]);
});

test('full two-level workflow: selected D introduces next R and stays traceable',()=>{
 const x=setup();
 try {
  assert.equal(x.run(accepted).status,0);
  const step2={schemaVersion:1,expectedRevision:2,operations:[
   {op:'add_node',node:{id:'D-002',kind:'decision',title:'Choose scenarios',status:'committed'}},
   {op:'add_node',node:{id:'R-003',kind:'requirement',title:'Describe booking scenario'}},
   {op:'add_edge',edge:{id:'E-003',type:'DRIVES',from:'R-002',to:'D-002'}},
   {op:'add_edge',edge:{id:'E-004',type:'INTRODUCES',from:'D-002',to:'R-003',parent:'R-002'}},
   {op:'append_event',event:{id:'EV-002',type:'decision_selected',decisionId:'D-002',
     by:'user',note:'Demo second explicit selection'}}
  ]};
  const result=x.run(step2);
  assert.equal(result.status,0,result.stderr);
  const g=x.read();
  assert.equal(g.revision,3);
  const edges=new Set(g.edges.map(e=>e.from+'>'+e.to));
  for(const relation of ['R-001>D-001','D-001>R-002','R-002>D-002','D-002>R-003'])
   assert(edges.has(relation),'missing '+relation);
  assert.equal(g.events.length,2);
  assert(g.nodes.every(n=>!n.achievement||n.achievement!=='verified'));
 } finally {x.clean();}
});

test('crosscutting R applies to two R without cloning or decision event',()=>{
 const x=setup();
 try{
  assert.equal(x.run(accepted).status,0);
  const patch={schemaVersion:1,expectedRevision:2,operations:[
   {op:'add_node',node:{id:'R-X1',kind:'requirement',title:'Accessibility across flows',
     crosscutting:true,scope:'booking and cancellation'}},
   {op:'add_edge',edge:{id:'E-X1',type:'APPLIES_TO',from:'R-X1',to:'R-001'}},
   {op:'add_edge',edge:{id:'E-X2',type:'APPLIES_TO',from:'R-X1',to:'R-002'}}
  ]};
  const result=x.run(patch);
  assert.equal(result.status,0,result.stderr);
  const g=x.read();
  assert.equal(g.revision,3);
  assert.equal(g.nodes.filter(n=>n.id==='R-X1').length,1);
  assert.equal(g.edges.filter(e=>e.type==='APPLIES_TO').length,2);
  assert.equal(g.events.length,1); // only original decision selection
 } finally{x.clean();}
});
test('crosscutting APPLIES_TO refuses unmarked source and self-link',()=>{
 const x=setup();
 try{
  assert.equal(x.run(accepted).status,0);
  const patch={schemaVersion:1,expectedRevision:2,operations:[
   {op:'add_edge',edge:{id:'E-X1',type:'APPLIES_TO',from:'R-001',to:'R-002'}}
  ]};
  const result=x.run(patch);
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/crosscutting Requirement/);
  assert.equal(x.read().revision,2);
  const self={schemaVersion:1,expectedRevision:2,operations:[
   {op:'update_node',id:'R-001',changes:{crosscutting:true}},
   {op:'add_edge',edge:{id:'E-X2',type:'APPLIES_TO',from:'R-001',to:'R-001'}}
  ]};
  const output=x.run(self);
  assert.notEqual(output.status,0);
  assert.match(output.stderr,/cannot reference itself/);
  assert.equal(x.read().revision,2);
 } finally{x.clean();}
});

test('writer rejects non-workspace graph even without readOnly flag',()=>{
 const dir=fs.mkdtempSync(path.join(base,'graphs','examples','.guard-test-'));
 const file=path.join(dir,'graph.json');
 const before={schemaVersion:1,id:'guarded-example',revision:1,title:'Guarded',
   nodes:[{id:'R-001',kind:'requirement',title:'Not a workspace'}],edges:[],events:[]};
 fs.writeFileSync(file,JSON.stringify(before));
 try {
   const patch=path.join(dir,'patch.json');
   fs.writeFileSync(patch,JSON.stringify({schemaVersion:1,expectedRevision:1,operations:[]}));
   const result=spawnSync('python3',[updater,'--graph',file,'--patch',patch,'--dry-run'],{encoding:'utf8',env:{...process.env,RDG_ISOLATED_TEST_ONLY:'1'}});
   assert.notEqual(result.status,0);
   assert.match(result.stderr,/NON_WORKSPACE_GRAPH/);
   assert.equal(fs.existsSync(path.join(dir,'.graph-apply.lock')),false);
   assert.deepEqual(JSON.parse(fs.readFileSync(file,'utf8')),before);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});


test('history guard rejects rewriting, broadening or superseding an accepted D without losing original',()=>{
 const x=setup();
 try{
  assert.equal(x.run(accepted).status,0);const original=x.read();
  for(const changes of [{title:'Different answer'},{scope:'Broader scope'},{description:'Different rationale'},{status:'superseded'},{newMeaning:'Different payload'}]){
   const r=x.run({schemaVersion:1,expectedRevision:2,operations:[{op:'update_node',id:'D-001',changes}]});
   assert.notEqual(r.status,0);assert.match(r.stderr,/DECISION_HISTORY_GUARD/);assert.deepEqual(x.read(),original);
  }
 }finally{x.clean();}
});
test('verification metadata may advance without overwriting the accepted answer or adding fictitious choice',()=>{
 const x=setup();
 try{
  assert.equal(x.run(accepted).status,0);
  const r=x.run({schemaVersion:1,expectedRevision:2,operations:[{op:'update_node',id:'D-001',changes:{evidenceStatus:'unverified',openQuestion:'Status contract still unknown'}}]});
  assert.equal(r.status,0,r.stderr);
  const g=x.read();assert.equal(g.revision,3);
  assert.equal(g.nodes.find(n=>n.id==='D-001').title,'Decompose');assert.equal(g.events.length,1);
 }finally{x.clean();}
});
test('unchanged accepted D fields remain no-op under history guard',()=>{
 const x=setup();
 try{
  assert.equal(x.run(accepted).status,0);
  const r=x.run({schemaVersion:1,expectedRevision:2,operations:[{op:'update_node',id:'D-001',changes:{title:'Decompose',status:'committed'}}]});
  assert.equal(r.status,0,r.stderr);assert.match(r.stdout,/NO_CHANGE/);assert.equal(x.read().revision,2);
 }finally{x.clean();}
});
