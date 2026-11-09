'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),slug='requirements-dependencies-demo';
const rootRel=`workspaces/${slug}/graph.json`,planRel=`plans/${slug}/plan.json`;
const read=rel=>JSON.parse(fs.readFileSync(path.join(ROOT,rel),'utf8'));
const graph=()=>read('graphs/'+rootRel),plan=()=>read(planRel);
const journals=()=>fs.readdirSync(path.join(ROOT,'graphs/workspaces/.transactions'))
 .filter(f=>f.endsWith('.json')).map(f=>read('graphs/workspaces/.transactions/'+f));
const records=()=>journals().flatMap(j=>j.records.filter(r=>r.file===rootRel&&r.changed)
 .map(r=>({journal:j,record:r}))).sort((a,b)=>a.record.after.revision-b.record.after.revision);

test('active catalog admits working candidate-v6 owners and keeps legacy sources archived',()=>{
 const index=read('graphs/index.json');
 const {normalizeCatalog,listFolder}=require('../tools/rdg-catalog.js');
 const app=normalizeCatalog(index);
 assert(app.fullGraphs.some(g=>g.slug===slug));
 assert(listFolder(app,'examples').some(g=>g.slug===slug));
 assert(app.graphs.length>0);
 assert(app.graphs.every(g=>g.actionModel==='candidate-v6'&&g.file.startsWith('workspaces/')));
 assert(!app.graphs.some(g=>g.file.startsWith('examples/')||g.file.startsWith('2d/')));
 const archive=index.graphs.find(g=>g.file==='examples/reference-mixed-active-work/graph.json');
 assert(archive&&archive.catalogHidden,'legacy source remains archived, not operational');
 const bundle=fs.readFileSync(path.join(ROOT,'tools/rd-graph-data.js'),'utf8');
 assert(!bundle.includes('"slug": "reference-mixed-active-work"'));
 assert(bundle.includes(slug));
});

test('another working root remains visible without replacing the teaching graph',()=>{
 const index=structuredClone(read('graphs/index.json'));
 const original=index.graphs.find(g=>g.slug===slug),entry=index.fullGraphs.find(g=>g.slug===slug);
 const extra={slug:'additional-working-root',file:'workspaces/additional-working-root/graph.json',
  identitySpace:'additional-working-space',rootRequirementId:'ADDITIONAL-R0'};
 index.graphs.push({...original,...extra});
 index.fullGraphs.push({...entry,...extra});
 const {normalizeCatalog,listFolder}=require('../tools/rdg-catalog.js');
 const app=normalizeCatalog(index);
 assert(app.fullGraphs.some(g=>g.slug===slug)&&app.fullGraphs.some(g=>g.slug===extra.slug));
 assert(listFolder(app,entry.folder).some(g=>g.slug===extra.slug));
 // The extra entry is an isolated catalog input, not a newly authored real owner.
});

test('accepted Graph journal reconstructs the current owner across later revisions',()=>{
 const g=graph(),rows=records();
 assert.equal(g.actionModel,'candidate-v6');
 assert.equal(g.readOnly,undefined);assert.equal(g.exampleOnly,undefined);
 assert.equal(g.rootRequirementId,'R0');assert(!('workflowExample' in g));
 assert(g.nodes.some(n=>n.id===g.rootRequirementId&&n.kind==='requirement'));
 assert(g.nodes.every(n=>['requirement','action'].includes(n.kind)));
 assert(!g.nodes.some(n=>n.id==='C-ASSURANCE'));
 assert(rows.length>0);
 let previous=null;
 for(const {journal,record} of rows){
  assert.equal(journal.state,'completed');
  assert.deepEqual(record.before,previous,'no missing or rewritten accepted Graph version');
  assert.equal(record.after.revision,(previous?.revision||0)+1);
  previous=record.after;
 }
 assert.deepEqual(previous,g,'current Graph is exactly the last accepted writer snapshot');
 for(const node of g.nodes.filter(n=>n.kind==='action'&&n.status==='selected'))
  assert(node.selectionBasis?.driverSnapshot,'selection keeps its actual basis');
});

test('versioned Plan references existing Graph declarations without a fixed placement count',()=>{
 const store=plan(),g=graph();
 assert.equal(store.kind,'temporalPlanOwner');
 assert.equal(store.owner.identitySpace,g.identitySpace);
 assert.equal(store.versions.length,store.revision);
 assert(store.revision>=1);
 for(const [i,version] of store.versions.entries()){
  assert.equal(version.revision,i+1);assert.equal(version.plan.revision,version.revision);
 }
 const latest=store.versions.at(-1).plan;
 assert.equal(latest.kind,'temporalPlan');assert.equal(latest.id,slug);
 const stepIds=new Set(latest.steps.map(s=>s.id));
 for(const step of latest.steps){
  const ref=step.actionRef||step.requirementRef;
  assert(ref);assert.equal(ref.identitySpace,g.identitySpace);
  const source=read('graphs/'+ref.graphFile),declaration=source.nodes.find(n=>n.id===ref.nodeId);
  assert.equal(source.identitySpace,ref.identitySpace);
  assert(declaration);assert.equal(declaration.kind,step.kind);
 }
 assert(latest.timeConstraints.every(t=>stepIds.has(t.stepId)));
 assert(latest.sequence.every(e=>stepIds.has(e.before)&&stepIds.has(e.after)));
});

test('old-model workspace writes fail without affecting archive bytes',()=>{
 const original=fs.readFileSync(path.join(ROOT,'graphs/workspaces/try-it/graph.json'));
 const pkg={schemaVersion:1,transactionId:'archived-old-block-test',changes:[{
  file:'workspaces/try-it/graph.json',patch:{schemaVersion:1,expectedRevision:1,
   operations:[{op:'add_node',node:{id:'R-UNAUTHORIZED',kind:'requirement',title:'Invalid'}}]}}]};
 const tmp=require('node:os').tmpdir()+'/rdg-active-legacy-'+process.pid+'.json';
 try{
  fs.writeFileSync(tmp,JSON.stringify(pkg));
  const p=spawnSync('python3',[path.join(ROOT,'tools/graph-apply.py'),'--package','--patch',tmp],
   {encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1',RDG_AUTH_STORE:'',RDG_AUTH_TOKEN:''}});
  assert.notEqual(p.status,0);assert.match(p.stderr,/ACTIVE_ONLY_CANDIDATE_V6/);
  assert.deepEqual(fs.readFileSync(path.join(ROOT,'graphs/workspaces/try-it/graph.json')),original);
 }finally{fs.rmSync(tmp,{force:true});}
});

test('published snapshots retain accepted provenance and actual owner references as owners evolve',()=>{
 const pub=read('tools/rdg-published-owners.json'),allow=read('tools/rdg-published-owners.allowlist.json');
 assert.deepEqual(Object.keys(pub.owners).sort(),[...allow.slugs].sort());
 const data=fs.readFileSync(path.join(ROOT,'tools/rd-graph-data.js'),'utf8');
 const embedded=JSON.parse(data.split(' = ',2)[1].trim().replace(/;$/,''));
 assert.deepEqual(embedded.publishedOwners,pub.owners);
 const snapshot=pub.owners[slug],g=graph(),store=plan(),accepted=records();
 assert.equal(snapshot.mode,'published-owner-snapshot');
 assert.equal(snapshot.graphRevision,g.revision);assert.equal(snapshot.planRevision,store.revision);
 for(const [field,file] of [['graphSha256','graphs/'+rootRel],['planSha256',planRel]])
  assert.equal(snapshot[field],crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT,file))).digest('hex'));
 const saves=snapshot.history.filter(r=>r.kind==='graph_saved'&&r.graphFile===rootRel);
 assert.deepEqual(saves.map(r=>r.transactionId).sort(),accepted.map(r=>r.journal.transactionId).sort());
 for(const {journal,record} of accepted){
  const saved=saves.find(r=>r.transactionId===journal.transactionId);
  assert.equal(saved.revision,record.after.revision);
  assert.equal(saved.previousRevision,record.before?.revision??null);
 }
 for(const event of g.events){
  const row=snapshot.history.find(r=>r.id===rootRel+'::'+event.id);
  assert(row,'accepted semantic event is preserved');
  assert.equal(row.sourceEventType,event.type);
 }
 const planTransactions=new Set(store.versions.map(v=>v.transactionId));
 for(const row of snapshot.history.filter(r=>r.kind.startsWith('plan_')))
  assert(planTransactions.has(row.transactionId),'Plan provenance comes from an accepted version');
 assert.equal(snapshot.dependencies.engine,'gendocen');
 assert.equal(snapshot.dependencies.completionTruthAttested,false);
 const rows=snapshot.dependencies.rows;
 assert.deepEqual(Object.keys(snapshot.dependencyHistory).sort(),rows.map(r=>r.target).sort());
 for(const row of rows){
  const target=read('graphs/'+row.graphFile);
  assert(target.nodes.some(n=>n.id===row.nodeId&&n.kind===row.kind));
  for(const ref of row.uses)
   assert(read('graphs/'+ref.graphFile).nodes.some(n=>n.id===ref.nodeId&&n.kind==='requirement'));
 }
 assert(!JSON.stringify(snapshot).includes('RDG_AUTH_TOKEN'));
});
