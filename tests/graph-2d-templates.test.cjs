const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const sourceRoot='/workspace/repos/obs-planning-docs/planning/documentation/idtspe-methodology/active/profiles/visual-production-2d/target-modules';
const models=fs.readdirSync(sourceRoot).filter(n=>/^TM-2D-.*\.md$/.test(n)).sort();
const graphByModel=id=>JSON.parse(fs.readFileSync(path.join(root,'graphs','2d','template-'+id.toLowerCase(),'graph.json'),'utf8'));
test('all 10 registered 2D Target Modules are present, exactly once',()=>{
 assert.equal(models.length,10);
 const reg=fs.readFileSync(path.join(sourceRoot,'../registries/TARGET-MODULE-REGISTRY.md'),'utf8');
 for(const filename of models){
  const id=filename.replace(/\.md$/,'');
  const g=graphByModel(id);
  assert.equal(g.originalTargetModuleId,id);
  assert(reg.includes('`'+id+'`'),id);
  assert(g.templateOnly===true&&g.readOnly===true&&g.selected===false);
  assert.deepEqual(g.events,[]);
  assert.equal(g.revision,2);
 }
});
test('source content is bit-preserved; inventory, Unit IDs and guidance roundtrip',()=>{
 let allUnits=0;
 for(const file of models){
  const source=fs.readFileSync(path.join(sourceRoot,file),'utf8');
  const g=graphByModel(file.slice(0,-3));
  assert.equal(g.sourceMarkdown,source,file);
  const hash=crypto.createHash('sha256').update(source).digest('hex');
  assert.equal(g.sourceContentSHA256,hash,file);
  const rawIDs=[...source.matchAll(/^\|\s*`(RU-[A-Za-z0-9-]+)`\s*\|/gm)].map(x=>x[1]);
  assert.equal(g.unitCount,rawIDs.length,file);
  assert.deepEqual(g.unitIds,rawIDs,file);
  assert.equal(g.nodes.length,2+rawIDs.length);
  assert.equal(g.edges.length,1+rawIDs.length);
  allUnits+=rawIDs.length;
  const ids=new Set(g.nodes.map(n=>n.id));
  for(const id of rawIDs){
   const n=g.nodes.find(n=>n.id===id);
   const unit=JSON.parse(fs.readFileSync(path.join(root,'graphs/2d',g.id+'-unit-'+id.toLowerCase(),'graph.json'),'utf8'));
   const prepared=unit.nodes.find(n=>n.id==='TEMPLATE-D-'+id);
   assert.equal(n.kind,'requirement',id);
   assert.equal(n.status,'not-instantiated',id);
   assert(n.guidanceMarkdown.includes('`'+id+'`'),id);
   assert(source.includes(n.inventoryRow),id);
   assert(source.replace(/\r\n/g,'\n').includes(n.guidanceMarkdown),id);
   assert.equal(prepared.status,'reusable-unselected',id);
   assert.equal(prepared.sourceUnitId,id);
   assert.equal(prepared.explicitSubrequirements,false);
   assert(g.edges.some(e=>e.from===g.originalTargetModuleId&&e.to===id&&e.type==='INTRODUCES'),id);
   assert(unit.edges.some(e=>e.from===id&&e.to===prepared.id&&e.type==='DRIVES'),id);
   assert.equal(unit.nodes.find(n=>n.id===id).projectionOf.graphSlug,g.id);
  }
  for(const edge of g.edges) {
   assert(ids.has(edge.from)&&ids.has(edge.to));
   if(edge.type==='INTRODUCES')assert(ids.has(edge.parent));
   assert.equal(edge.templateOnly,true);
  }
  assert(g.nodes.every(x=>x.kind!=='decision'||x.selected===false));
 }
 assert.equal(allUnits,38);
});
test('original module whole guidance preserved: gates, workflow, validators, sources, file contracts',()=>{
 for(const file of models){
  const g=graphByModel(file.slice(0,-3));
  const s=g.sourceMarkdown;
  for(const key of ['Purpose','Target Step Result','Module-defined Unit Inventory',
                    'Source Contract','Validators','Handoff','Revalidation','Artifact / File Contract'])
   assert(s.includes('## '+key),file+' missing '+key);
  assert(g.originalSections['Purpose']);
  assert(g.originalSections['Module-defined Unit Inventory']);
  assert(g.originalSections['Artifact / File Contract']);
  assert(g.originalTargetModuleId.startsWith('TM-2D-'));
 }
});
test('source files are not copied into graph as accepted project state',()=>{
 for(const file of models){
  const g=graphByModel(file.slice(0,-3));
  assert(g.nodes.every(n=>!['committed','selected','resolved'].includes(n.status)),file);
  assert.equal(g.events.length,0);
  assert.equal(g.templateOnly,true);
 }
 const live=JSON.parse(fs.readFileSync(path.join(root,'graphs/workspaces/try-it/graph.json'),'utf8'));
 assert.equal(live.revision,1);assert.equal(live.nodes.length,1);
});
test('template protection refuses writer without creating lock',()=>{
 const id=models[0].replace(/\.md$/,'').toLowerCase();
 const file=path.join(root,'graphs/2d/template-'+id+'/graph.json');
 const lock=path.join(path.dirname(file),'.graph-apply.lock');
 const patch=path.join(root,'graphs/workspaces/try-it/patches/accept-example.DO-NOT-APPLY.json');
 assert(!fs.existsSync(lock));
 const proc=spawnSync('python3',[path.join(root,'tools/graph-apply.py'),
   '--graph',file,'--patch',patch,'--dry-run'],{encoding:'utf8'});
 assert.notEqual(proc.status,0);
 assert.match(proc.stderr,/READ_ONLY_GRAPH/);
 assert(!fs.existsSync(lock));
});
test('browser index and bundled Javascript expose all ten reusable template graphs',()=>{
 const index=JSON.parse(fs.readFileSync(path.join(root,'graphs/index.json'),'utf8'));
 const expected=models.map(name=>'template-'+name.replace(/\.md$/,'').toLowerCase());
 const seen=index.graphs.filter(x=>x.group==='2d'&&x.planningScale==='module').map(x=>x.slug);
 assert.deepEqual(seen.sort(),expected.sort());
 const js=fs.readFileSync(path.join(root,'tools/rd-graph-data.js'),'utf8');
 const vm=require('node:vm'),context={};vm.runInNewContext(js,context);
 const data=context.RDG_EMBEDDED_GRAPHS;
 assert.equal(data.graphs.length,100);
 assert.equal(data.graphs.filter(x=>x.group==='2d'&&x.graph.planningScale==='module').length,10);
 for(const item of data.graphs.filter(x=>x.group==='2d'&&x.graph.planningScale==='module'))
  assert(item.graph.sourceMarkdown.length>4000);
});
