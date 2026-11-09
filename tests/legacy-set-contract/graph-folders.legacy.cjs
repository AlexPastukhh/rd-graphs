const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const graphs=path.join(root,'graphs');
const groups=['workspaces','examples','2d'];
const catalog=JSON.parse(fs.readFileSync(path.join(graphs,'index.json'),'utf8'));
const dataCode=fs.readFileSync(path.join(root,'tools/rd-graph-data.js'),'utf8');
const ctx={};vm.runInNewContext(dataCode,ctx);
const bundled=ctx.RDG_EMBEDDED_GRAPHS;
test('folder catalog maps all 100 unique stable slugs to actual grouped files',()=>{
 const files=groups.flatMap(group=>fs.readdirSync(path.join(graphs,group),{withFileTypes:true})
   .filter(entry=>entry.isDirectory()&&fs.existsSync(path.join(graphs,group,entry.name,'graph.json')))
   .map(entry=>group+'/'+entry.name+'/graph.json'));
 assert.equal(files.length,100);
 assert.equal(catalog.graphs.length,100);
 assert.equal(bundled.graphs.length,100);
 assert.equal(new Set(catalog.graphs.map(e=>e.slug)).size,100);
 assert.deepEqual(new Set(catalog.graphs.map(e=>e.file)),new Set(files));
 for(const item of catalog.graphs){
  assert.equal(item.file,item.group+'/'+item.slug+'/graph.json');
  const graph=JSON.parse(fs.readFileSync(path.join(graphs,item.file),'utf8'));
  assert.equal(item.title,graph.title);
  const bundledItem=bundled.graphs.find(x=>x.slug===item.slug);
  assert(bundledItem);
  assert.equal(bundledItem.group,item.group);
  assert.equal(JSON.stringify(bundledItem.graph),JSON.stringify(graph));
 }
});
test('three category groups have exact counts and nested level visibility',()=>{
 const all=group=>catalog.graphs.filter(x=>x.group===group);
 assert.equal(all('workspaces').length,1);
 assert.equal(all('examples').length,51);
 assert.equal(all('2d').length,48);
 assert.equal(all('workspaces').filter(x=>!x.catalogHidden).length,1);
 assert.equal(all('examples').filter(x=>!x.catalogHidden&&x.planningScale!=='unit').length,15);
 assert.equal(all('2d').filter(x=>!x.catalogHidden).length,10);
 assert.equal(catalog.defaultGraph,'try-it');
 assert(!catalog.graphs.find(x=>x.slug==='reference-feature-root').catalogHidden);
 assert(catalog.graphs.find(x=>x.slug==='reference-feature-auth').catalogHidden);
});
test('working graph only writable type; all examples and 2d graphs are readOnly',()=>{
 for(const group of ['examples','2d']){
  for(const item of catalog.graphs.filter(x=>x.group===group)){
   const graph=JSON.parse(fs.readFileSync(path.join(graphs,item.file),'utf8'));
   if(item.slug!=='example')assert.equal(graph.readOnly,true,item.file); // legacy smoke graph is protected by folder-level writer guard
  }
 }
 const pilot=JSON.parse(fs.readFileSync(path.join(graphs,'workspaces/try-it/graph.json'),'utf8'));
 assert.equal(pilot.revision,1);assert.equal(pilot.nodes.length,1);
 assert.equal(pilot.edges.length,0);assert.equal(pilot.events.length,0);
});
test('original user example preserved at relocated path with expected exact hash',()=>{
 const file=path.join(root,'docs/examples/requirements-decisions-graph-examples-v0.2.source.md');
 const text=fs.readFileSync(file,'utf8');
 let h=2166136261;
 for(let i=0;i<text.length;i++)h=Math.imul(h^text.charCodeAt(i),16777619)>>>0;
 assert.equal(text.length,30360);assert.equal(h.toString(16),'896505f4');
 assert.match(fs.readFileSync(path.join(root,'work-kit/modules/rdg.work.examples.module.md'),'utf8'),/docs\/examples\/EXAMPLE-COVERAGE.md/);
 assert.match(fs.readFileSync(path.join(root,'docs/2d/2D-TEMPLATE-GRAPHS.md'),'utf8'),/graphs\/2d\/template-tm-2d-/);
});
