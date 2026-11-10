const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const index=JSON.parse(fs.readFileSync(path.join(root,'graphs/index.json'),'utf8'));
const read=slug=>JSON.parse(fs.readFileSync(path.join(root,'graphs',index.graphs.find(x=>x.slug===slug).file),'utf8'));
const {simulate}=require('./viewer-test-helper.cjs');
const walk=(n,p)=>[...(p(n)?[n]:[]),...(n.children||[]).flatMap(c=>walk(c,p))];
test('38 source Units have distinct R graphs, shared identity, direct methods and no duplicated full source',()=>{
 const parents=index.graphs.filter(x=>x.group==='2d'&&x.planningScale==='module');
 assert.equal(parents.length,10);let count=0;
 for(const item of parents){
  const g=read(item.slug);assert.equal(g.preparedModule.goalRequirementId,g.rootRequirementId);
  for(const id of g.unitIds){
   const child=index.graphs.find(x=>x.group==='2d'&&x.planningScale==='unit'&&read(x.slug).rootRequirementId===id&&read(x.slug).identitySpace===g.identitySpace);
   assert(child,id);count++;const unit=read(child.slug);assert.equal(unit.nodes.length,2);
   assert.equal(unit.nodes[0].projectionOf.graphSlug,g.id);assert.equal(unit.nodes[0].id,id);
   assert.equal(unit.preparedModule.childRequirementIds.length,0);
   assert.equal(unit.sourceMarkdown,undefined);assert.equal(unit.sourceOwnerGraphSlug,g.id);
   assert.equal(unit.sourceContentSHA256,g.sourceContentSHA256);assert.deepEqual(unit.events,[]);
   assert(index.relations.some(r=>r.from===g.id&&r.to===unit.id&&r.relationKind==='prepared'));
   assert(!g.nodes.some(n=>n.id==='TEMPLATE-D-'+id));
  }
 }assert.equal(count,38);
});
test('2D explorer lists ten sets; each map includes its Unit levels without bypass arrows',async()=>{
 const app=simulate({useBundle:true});await app.flush();app.openFolder('2d');
 const sets=app.ids['graph-list'].children;assert.equal(sets.length,10);
 for(const row of sets){
  const id=row.getAttribute('data-set');assert(id);await app.openSet(id);
  const catalog=app.host.rdgExplorer.getCatalog(),set=catalog.graphSets.find(s=>s.id===id),nodes=app.root.querySelectorAll('.node');
  assert.deepEqual(nodes.map(n=>n.getAttribute('data-graph')).sort(),set.members.slice().sort());
  assert(nodes.some(n=>read(n.getAttribute('data-graph')).planningScale==='unit'));
  const edges=walk(app.ids.canvas,n=>n.classList?.contains('edge'));
  assert.equal(edges.length,catalog.relations.filter(r=>set.members.includes(r.from)&&set.members.includes(r.to)).length);
 }
});

test('prepared broad → split Unit → leaf Unit keeps R IDs and back; direct Unit has no forced split',async()=>{
 const app=simulate({useBundle:true});await app.flush();await app.openCard('reference-module-units');
 const click=async id=>{const n=app.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')===id);assert(n,id);n.listeners.click({stopPropagation(){}});await app.flush();};
 await click('UD-R-STATE-PATH');assert.match(app.info(),/Узкая задача · Unit/);
 assert(app.root.querySelectorAll('.node').some(n=>n.getAttribute('data-id')==='UD-R-STATE-PATH'));
 await click('UD-R-STATES');assert.match(app.ids['bar-title'].textContent,/Определить состояния/);
 await app.ids['level-up'].onclick();assert.match(app.ids['bar-title'].textContent,/Проработать состояние/);
 await app.ids['level-up'].onclick();assert.match(app.ids['bar-title'].textContent,/Проработать функцию/);
 await click('UD-R-RESULT');assert.equal(app.root.querySelectorAll('.node').length,2);
 app.ids.source.onclick();assert.match(app.ids['source-text'].textContent,/Модуль и Unit/);
});
function fixture(){
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-tmu-package-'));fs.mkdirSync(path.join(tmp,'tools'));
 for(const f of ['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js','graph-apply.py','graph-index.py','rdg-catalog.py','graph-package.py','rdg-v7-model.py'])fs.copyFileSync(path.join(root,'tools',f),path.join(tmp,'tools',f));
 const r=(id,title)=>({id,kind:'requirement',title}),d=(id,title)=>({id,kind:'decision',title,status:'committed'});
 const event=id=>({id:'E-'+id,type:'decision_selected',decisionId:id,by:'user',note:'Fixture explicit selection'});
 const parent={schemaVersion:1,id:'plan',revision:1,identitySpace:'fixture',rootRequirementId:'R',planningScale:'module',
   nodes:[r('R','Parent'),d('D','Split'),r('C','Child')],edges:[{id:'DR',type:'DRIVES',from:'R',to:'D'},{id:'IN',type:'INTRODUCES',from:'D',to:'C',parent:'R'}],events:[event('D')]};
 const child={schemaVersion:1,id:'child',revision:1,identitySpace:'fixture',rootRequirementId:'C',planningScale:'unit',
   nodes:[{...r('C','Child'),projectionOf:{graphSlug:'plan',nodeId:'C'}},d('CD','Direct')],
   edges:[{id:'CDR',type:'DRIVES',from:'C',to:'CD'}],events:[event('CD')]};
 const pkg={schemaVersion:1,transactionId:'fixture-create',changes:[{file:'workspaces/plan/graph.json',create:parent},{file:'workspaces/child/graph.json',create:child}]};
 const run=(payload,flags=[])=>{const file=path.join(tmp,'patch.json');fs.writeFileSync(file,JSON.stringify(payload));return spawnSync('python3',[path.join(tmp,'tools/graph-apply.py'),'--package','--patch',file,...flags],{encoding:'utf8',env:{...process.env,RDG_ISOLATED_TEST_ONLY:'1'}});};
 return {tmp,parent,child,pkg,run};
}
test('package dry-run creates nothing; apply/readback/replay preserve files and reject changed transaction IDs',()=>{
 const f=fixture();try{
  let r=f.run(f.pkg,['--dry-run']);assert.equal(r.status,0,r.stderr);assert(!fs.existsSync(path.join(f.tmp,'graphs/workspaces/plan')));
  r=f.run(f.pkg);assert.equal(r.status,0,r.stderr);assert.match(r.stdout,/APPLIED/);
  for(const c of f.pkg.changes)assert.deepEqual(JSON.parse(fs.readFileSync(path.join(f.tmp,'graphs',c.file))),c.create);
  r=f.run(f.pkg);assert.equal(r.status,0,r.stderr);assert.match(r.stdout,/ALREADY_APPLIED/);
  const changed=structuredClone(f.pkg);changed.changes[0].create.title='another';
  r=f.run(changed);assert.notEqual(r.status,0);assert.match(r.stderr,/TRANSACTION_ID_CONFLICT/);
 }finally{fs.rmSync(f.tmp,{recursive:true,force:true});}
});
test('invalid owner or prepared version fails before either workspace file is written',()=>{
 const f=fixture();try{
  const bad=structuredClone(f.pkg);bad.changes[1].create.nodes[0].projectionOf.graphSlug='missing';
  let r=f.run(bad);assert.notEqual(r.status,0);assert.match(r.stderr,/unresolved identity owner/);
  assert(!fs.existsSync(path.join(f.tmp,'graphs/workspaces/plan/graph.json')));
  const badModel=structuredClone(f.pkg);badModel.changes[0].create.nodes[1].preparedModelRef={graphSlug:'missing',id:'X',version:'1',targetRequirementId:'R'};
  r=f.run(badModel);assert.notEqual(r.status,0);assert.match(r.stderr,/unresolved prepared module/);
  assert(!fs.existsSync(path.join(f.tmp,'graphs/workspaces/plan/graph.json')));
 }finally{fs.rmSync(f.tmp,{recursive:true,force:true});}
});
test('D revision archives former answer, scope, drivers and edges, preserving child IDs and history',()=>{
 const f=fixture();try{
  assert.equal(f.run(f.pkg).status,0);
  const revised={schemaVersion:1,transactionId:'fixture-revise',changes:[{file:'workspaces/plan/graph.json',patch:{schemaVersion:1,expectedRevision:1,operations:[{
   op:'revise_decision',id:'D',decision:{id:'D2',kind:'decision',title:'A new method',scope:'new scope',status:'committed'},
   edges:[{id:'IN2',type:'INTRODUCES',from:'D2',to:'C',parent:'R'}],
   event:{id:'REV',type:'decision_revised',decisionId:'D2',previousDecisionId:'D',by:'user',note:'Fixture actual revision'}
  }]}}]};
  let r=f.run(revised);assert.equal(r.status,0,r.stderr);
  const g=JSON.parse(fs.readFileSync(path.join(f.tmp,'graphs/workspaces/plan/graph.json')));
  assert.equal(g.revision,2);assert.equal(g.nodes.find(n=>n.id==='D').status,'superseded');
  const ev=g.events.find(e=>e.id==='REV');assert.equal(ev.previousDecisionSnapshot.title,'Split');
  assert.equal(ev.driverSnapshots[0].id,'R');assert(ev.previousEdges.some(e=>e.id==='IN'));
  assert.equal(g.edges.find(e=>e.id==='IN').archived,true);
  const m=JSON.parse(fs.readFileSync(path.join(f.tmp,'graphs/index.json')));assert.equal(m.relations[0].introducedByDecisionId,'D2');
  r=f.run({...revised,transactionId:'conflict'});assert.notEqual(r.status,0);assert.match(r.stderr,/REVISION_CONFLICT/);
 }finally{fs.rmSync(f.tmp,{recursive:true,force:true});}
});
test('interrupted journal completes on retry',()=>{
 const f=fixture();try{
  const script=path.join(f.tmp,'prepare.py');
  fs.writeFileSync(script,[
   'import importlib.machinery,json,hashlib',
   'm=importlib.machinery.SourceFileLoader("pkg","'+f.tmp+'/tools/graph-package.py").load_module()',
   'p=json.load(open("'+f.tmp+'/patch.json"))',
   'r=m.prepare(p)',
   'j={"schemaVersion":1,"state":"prepared","transactionId":p["transactionId"],"requestSHA256":hashlib.sha256(m.encoded(p).encode()).hexdigest(),"records":r}',
   'm.write_json(m.journal_dir()/(p["transactionId"]+".json"),j)',
   'm.write_json(m.target_path(r[0]["file"]),r[0]["after"])'
  ].join('\n'));
  fs.writeFileSync(path.join(f.tmp,'patch.json'),JSON.stringify(f.pkg));
  let r=spawnSync('python3',[script],{encoding:'utf8',env:{...process.env,RDG_ISOLATED_TEST_ONLY:'1'}});assert.equal(r.status,0,r.stderr);
  r=f.run(f.pkg);assert.equal(r.status,0,r.stderr);assert.match(r.stdout,/recovered=1/);
  assert(fs.existsSync(path.join(f.tmp,'graphs/workspaces/child/graph.json')));
 }finally{fs.rmSync(f.tmp,{recursive:true,force:true});}
});

test('typed prepared application pins source version, driver and the whole declared composition',()=>{
 const f=fixture();try{
  const src={schemaVersion:1,id:'prepared',revision:1,identitySpace:'prepared',rootRequirementId:'P-R',planningScale:'module',
   readOnly:true,templateOnly:true,sourceContentSHA256:'source-hash',
   nodes:[{id:'P-R',kind:'requirement',title:'Pattern'},{id:'P-D',kind:'decision',title:'Method',status:'reusable-unselected'},{id:'P-C',kind:'requirement',title:'Part'}],
   edges:[{id:'pd',type:'DRIVES',from:'P-R',to:'P-D',templateOnly:true},{id:'pi',type:'INTRODUCES',from:'P-D',to:'P-C',parent:'P-R',templateOnly:true}],events:[],
   preparedModule:{id:'PM',version:'v1',goalRequirementId:'P-R',methodDecisionId:'P-D',childRequirementIds:['P-C'],applicability:'A matching task',successCriteria:'Required outcome'}};
  const dir=path.join(f.tmp,'graphs/examples/prepared');fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(path.join(dir,'graph.json'),JSON.stringify(src));
  const pkg=structuredClone(f.pkg);
  pkg.changes[0].create.nodes[1].preparedModelRef={graphSlug:'prepared',...src.preparedModule,sourceContentSHA256:'source-hash',targetRequirementId:'R',requirementBindings:{'P-C':['C']}};
  let r=f.run(pkg,['--dry-run']);assert.equal(r.status,0,r.stderr);
  const wrong=structuredClone(pkg);wrong.changes[0].create.nodes[1].preparedModelRef.version='v2';
  r=f.run(wrong);assert.notEqual(r.status,0);assert.match(r.stderr,/module\/version/);
  const missing=structuredClone(pkg);missing.changes[0].create.nodes[1].preparedModelRef.requirementBindings={};
  r=f.run(missing);assert.notEqual(r.status,0);assert.match(r.stderr,/prepared child bindings/);
  const excess=structuredClone(pkg);
  excess.changes[0].create.nodes.push({id:'EXTRA',kind:'requirement',title:'Extra unbound task'});
  excess.changes[0].create.edges.push({id:'EXTRA-I',type:'INTRODUCES',from:'D',to:'EXTRA',parent:'R'});
  r=f.run(excess,['--dry-run']);assert.notEqual(r.status,0);assert.match(r.stderr,/bindings omit introduced Requirements/);
  r=f.run(pkg);assert.equal(r.status,0,r.stderr);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(f.tmp,'graphs/examples/prepared/graph.json'))),src);
 }finally{fs.rmSync(f.tmp,{recursive:true,force:true});}
});
test('cycles split across files are rejected before committing a package',()=>{
 const f=fixture();try{
  const pkg=structuredClone(f.pkg),c=pkg.changes[1].create;
  c.nodes.push({id:'R',kind:'requirement',title:'Parent',projectionOf:{graphSlug:'plan',nodeId:'R'}});
  c.edges.push({id:'cycle',type:'INTRODUCES',from:'CD',to:'R',parent:'C'});
  const r=f.run(pkg);assert.notEqual(r.status,0);assert.match(r.stderr,/cycle across graph levels/);
  assert(!fs.existsSync(path.join(f.tmp,'graphs/workspaces/plan/graph.json')));
 }finally{fs.rmSync(f.tmp,{recursive:true,force:true});}
});
test('recovery refuses an external change and does not publish the remaining file',()=>{
 const f=fixture();try{
  const script=path.join(f.tmp,'blocked.py');
  fs.writeFileSync(path.join(f.tmp,'patch.json'),JSON.stringify(f.pkg));
  fs.writeFileSync(script,[
   'import importlib.machinery,json,hashlib',
   'm=importlib.machinery.SourceFileLoader("pkg","'+f.tmp+'/tools/graph-package.py").load_module()',
   'p=json.load(open("'+f.tmp+'/patch.json"))',
   'r=m.prepare(p)',
   'j={"schemaVersion":1,"state":"prepared","transactionId":p["transactionId"],"requestSHA256":hashlib.sha256(m.encoded(p).encode()).hexdigest(),"records":r}',
   'm.write_json(m.journal_dir()/(p["transactionId"]+".json"),j)',
   'r[0]["after"]["title"]="External change"',
   'm.write_json(m.target_path(r[0]["file"]),r[0]["after"])'
  ].join('\n'));
  let r=spawnSync('python3',[script],{encoding:'utf8',env:{...process.env,RDG_ISOLATED_TEST_ONLY:'1'}});assert.equal(r.status,0,r.stderr);
  r=f.run(f.pkg);assert.notEqual(r.status,0);assert.match(r.stderr,/RECOVERY_CONFLICT/);
  assert.equal(JSON.parse(fs.readFileSync(path.join(f.tmp,'graphs/workspaces/plan/graph.json'))).title,'External change');
  assert(!fs.existsSync(path.join(f.tmp,'graphs/workspaces/child/graph.json')));
 }finally{fs.rmSync(f.tmp,{recursive:true,force:true});}
});
