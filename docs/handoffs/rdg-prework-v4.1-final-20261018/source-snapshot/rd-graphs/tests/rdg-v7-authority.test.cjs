const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..');
function setup(){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-commit-boundary-'));
 fs.mkdirSync(path.join(dir,'tools'),{recursive:true});
 for(const f of ['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js','graph-apply.py','graph-package.py','graph-index.py','rdg-catalog.py','rdg-v7-model.py'])
  fs.copyFileSync(path.join(ROOT,'tools',f),path.join(dir,'tools',f));
 const file=path.join(dir,'request.json');
 const run=(pkg,extra=[])=>{
  fs.writeFileSync(file,JSON.stringify(pkg));
  return spawnSync('python3',[path.join(dir,'tools/graph-apply.py'),
    '--package','--patch',file,...extra],{encoding:'utf8'});
 };
 const base={schemaVersion:1,transactionId:'boundary-create',changes:[{
  file:'workspaces/commit-test/graph.json',create:{
   schemaVersion:1,revision:1,id:'commit-test',
   planningScale:'module',identitySpace:'commit-test',rootRequirementId:'R',
   title:'Isolated test only',nodes:[{id:'R',kind:'requirement',title:'Root'}],
   edges:[],events:[]
  }
 }]};
 const selected={schemaVersion:1,transactionId:'boundary-select',changes:[{
  file:'workspaces/commit-test/graph.json',patch:{
   schemaVersion:1,expectedRevision:1,
   operations:[
    {op:'add_node',node:{id:'D',kind:'decision',title:'Chosen synthetic method',status:'committed'}},
    {op:'add_edge',edge:{id:'DR',type:'DRIVES',from:'R',to:'D'}},
    {op:'append_event',event:{id:'E',type:'decision_selected',decisionId:'D',
      by:'user',note:'Synthetic writer transaction, not an actual user project'}}
   ]
  }
 }]};
 const read=()=>JSON.parse(fs.readFileSync(path.join(dir,'graphs/workspaces/commit-test/graph.json')));
 return {dir,run,base,selected,read,cleanup:()=>fs.rmSync(dir,{force:true,recursive:true})};
}
test('normal writer commits a valid D without key or receipt and idempotently replays',()=>{
 const f=setup();try{
  assert.equal(f.run(f.base).status,0);
  const r=f.run(f.selected);assert.equal(r.status,0,r.stderr);
  const g=f.read();assert.equal(g.revision,2);
  assert.equal(g.nodes.find(n=>n.id==='D').status,'committed');
  assert.equal(g.events[0].decisionId,'D');
  const second=f.run(f.selected);assert.equal(second.status,0,second.stderr);
  assert.match(second.stdout,/ALREADY_APPLIED/);
  assert.equal(f.read().revision,2);
 }finally{f.cleanup();}
});
test('missing selection event cannot create a committed D through legacy path',()=>{
 const f=setup();try{
  assert.equal(f.run(f.base).status,0);
  const bad=structuredClone(f.selected);
  bad.changes[0].patch.operations.pop();
  let r=f.run(bad);assert.notEqual(r.status,0);assert.match(r.stderr,/requires decision_selected event/);
  assert.equal(f.read().revision,1);
  bad.changes[0].patch.operations.push({op:'append_event',event:{
    id:'E',type:'decision_selected',decisionId:'D',by:'template',
    note:'A source text cannot be an actor of a real writer event'}});
  r=f.run(bad);assert.notEqual(r.status,0);assert.match(r.stderr,/truthful user\/assistant author/);
  assert.equal(f.read().revision,1);
 }finally{f.cleanup();}
});
test('stale revision, changed replay and invalid path cannot silently mutate committed D',()=>{
 const f=setup();try{
  assert.equal(f.run(f.base).status,0);
  assert.equal(f.run(f.selected).status,0);
  const changed=structuredClone(f.selected);
  changed.changes[0].patch.operations[0].node.title='Unrecorded replacement';
  let r=f.run(changed);assert.notEqual(r.status,0);assert.match(r.stderr,/TRANSACTION_ID_CONFLICT/);
  changed.transactionId='distinct-retry';
  r=f.run(changed);assert.notEqual(r.status,0);assert.match(r.stderr,/REVISION_CONFLICT/);
  const outsider=structuredClone(f.base);outsider.transactionId='outsider';
  outsider.changes[0].file='examples/forbidden/graph.json';
  r=f.run(outsider);assert.notEqual(r.status,0);assert.match(r.stderr,/NON_WORKSPACE_GRAPH/);
  assert.equal(f.read().revision,2);
 }finally{f.cleanup();}
});
test('dry run previews a valid selected transaction without mutating graph',()=>{
 const f=setup();try{
  assert.equal(f.run(f.base).status,0);
  const r=f.run(f.selected,['--dry-run']);
  assert.equal(r.status,0,r.stderr);
  assert.match(r.stdout,/DRY_RUN/);
  assert.equal(f.read().revision,1);
 }finally{f.cleanup();}
});
test('create with committed D needs a real selection event shape, not a status alone',()=>{
 const f=setup();try{
  const bad=structuredClone(f.base);
  bad.changes[0].create.nodes.push({id:'D',kind:'decision',title:'Premade',status:'committed'});
  bad.changes[0].create.edges.push({id:'ED',type:'DRIVES',from:'R',to:'D'});
  let r=f.run(bad);assert.notEqual(r.status,0);
  assert.match(r.stderr,/requires decision_selected event/);
  assert(!fs.existsSync(path.join(f.dir,'graphs/workspaces/commit-test/graph.json')));
 }finally{f.cleanup();}
});

test('truthful assistant-authored intentional commit counts as an accepted D',()=>{
 const f=setup();try{
  assert.equal(f.run(f.base).status,0);
  const patch=structuredClone(f.selected);
  patch.changes[0].patch.operations[2].event.by='assistant';
  patch.changes[0].patch.operations[2].event.note='Isolated deliberate assistant-authored synthetic writer event';
  const r=f.run(patch);assert.equal(r.status,0,r.stderr);
  assert.equal(f.read().events[0].by,'assistant');
  assert.equal(f.read().nodes.find(n=>n.id==='D').status,'committed');
 }finally{f.cleanup();}
});
