'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const path=require('node:path'),crypto=require('node:crypto'),os=require('node:os'),cp=require('node:child_process');
const root=path.resolve(__dirname,'..'),source=path.join(root,'graphs');
const fixture=require('./fixtures/root-migration-baseline.json');
const index=require('../graphs/index.json'),catalog=require('../tools/rdg-catalog.js');
const {simulate}=require('./viewer-test-helper.cjs');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const project=p=>JSON.parse(fs.readFileSync(path.join(source,p),'utf8'));
test('all 100 originals are accounted for: 6 relocated untouched, approved example sources enriched, unrelated graphs byte-identical',()=>{
 assert.equal(Object.keys(fixture.sourceGraphSHA256).length,100);
 const modified=new Set([
  'reference-prepared-planning-tree','reference-mixed-active-work',
  'reference-prepared-feature-path','reference-prepared-scenario-path','reference-prepared-feature-depth','reference-prepared-scenario-consistency',
  'reference-mixed-feature-availability','reference-mixed-planned-scenario',
  'reference-prepared-feature-consistency','reference-mixed-feature-consistency',
  'reference-mixed-contextual-split','reference-mixed-planned-feature',
  'reference-mixed-planned-feature-consistency','reference-mixed-planned-feature-depth',
  'reference-mixed-planned-scenario-consistency'
 ]);
 const oldFiles=new Map(Object.entries(fixture.sourceGraphSHA256));
 for(const [file,expected] of oldFiles){
  const m=file.match(/^examples\/(context-(?:prepared|working)-(?:root|current|alternative))\/graph.json$/);
  if(m){
    assert.equal(sha(path.join(source,'examples/archive',m[1],'graph.json')),expected,
      'archival Context source must remain byte-identical');continue;
  }
  const slug=path.dirname(file).split('/').at(-1);
  if(modified.has(slug)){
   const graph=project(file);assert(graph.revision>=2);
   continue;
  }
  assert.equal(sha(path.join(source,file)),expected,'unrelated canonical graph modified: '+file);
 }
 for(const old of ['context-prepared','context-working','example-prepared','example-working',
                     'archive/archive-booking','archive/archive-features'])
   assert(!fs.existsSync(path.join(source,'examples',old)),'empty old set folder returned: '+old);
});
test('16 historical roots and 90 member references are preserved as source identity, not a set manifest',()=>{
 assert.equal(fixture.legacyRootEntries.length,16);
 assert.equal(fixture.legacyRootEntries.reduce((n,x)=>n+x.legacySourceSlugs.length,0),90);
 const by=new Map(index.graphs.map(e=>[e.slug,e]));
 for(const old of fixture.legacyRootEntries){
   const e=index.fullGraphs.find(x=>x.slug===old.rootGraphSlug);
   assert(e,'lost full R entry: '+old.id);
   assert.equal(e.rootRequirementId,old.rootRequirementId);
   assert.equal(e.title,old.title);
   assert.equal(e.presentation.usage,old.usage);
   assert.equal(!!e.presentation.archived,old.rootGraphSlug.startsWith('context-')?true:!!old.archived);
   for(const slug of old.legacySourceSlugs)assert(by.has(slug),'lost graph source '+slug);
 }
 assert(index.fullGraphs.length>=17,'independent sources should be discoverable as full roots');
 assert(!('graphSets' in index),'obsolete set inventory must not be authoritative');
});
test('index and embedded bundle have the same root entries with no set-membership dependency',()=>{
 const txt=fs.readFileSync(path.join(root,'tools/rd-graph-data.js'),'utf8');
 const vm=require('node:vm'),ctx={};vm.runInNewContext(txt,ctx);
 const bundle=ctx.RDG_EMBEDDED_GRAPHS;
 assert.deepEqual(JSON.parse(JSON.stringify(bundle.fullGraphs)),index.fullGraphs);
 assert.equal(bundle.graphs.length,index.graphs.length);
 const c=catalog.normalizeCatalog(bundle);
 assert(c.fullGraphs.some(g=>g.slug==='reference-complete-app'&&g.folder==='examples/archive'));
 assert(catalog.listFolder(c,'2d').filter(e=>e.kind==='full-graph').length===10);
});
test('catalog rejects forged full root and unsafe graph file paths, including hostile folder metadata',()=>{
 const valid={schemaVersion:1,graphs:[{slug:'x',file:'src/x/graph.json',folder:'src',rootRequirementId:'R',identitySpace:'space'}],folders:[{id:'src',folder:'',title:'src'}],fullGraphs:[{kind:'full-graph',slug:'x',file:'src/x/graph.json',folder:'src',rootRequirementId:'R',identitySpace:'space'}]};
 assert.equal(catalog.normalizeCatalog(valid).fullGraphs.length,1);
 for(const patch of [{file:'../escape/graph.json'},{file:'src/%2e/../evil/graph.json'}, {file:'https://example.com/graph.json'}, {folder:'../../evil'}]){
  const x=JSON.parse(JSON.stringify(valid));Object.assign(x.fullGraphs[0],patch);
  assert.throws(()=>catalog.normalizeCatalog(x),'forged entry accepted '+JSON.stringify(patch));
 }
 for(const file of ['../evil/graph.json','/root/graph.json','https://evil/graph.json','C:/evil/graph.json']){
  const x=JSON.parse(JSON.stringify(valid));x.graphs[0].file=file;
  assert.throws(()=>catalog.normalizeCatalog(x),'unsafe owner accepted '+file);
 }
});
test('catalog handles Unicode, literal hash and percent paths without URL interpretation',()=>{
 const choices=['Планы и цели','Plans #1','Percent 100%'];
 for(const prefix of choices){
  const slug='root';const file=prefix+'/root/graph.json';const item={slug,file,folder:prefix,rootRequirementId:'R',identitySpace:'space'};
  const model={schemaVersion:1,graphs:[item],folders:[{id:prefix,folder:'',title:prefix}],fullGraphs:[{...item,kind:'full-graph'}]};
  const c=catalog.normalizeCatalog(model);const entry=catalog.listFolder(c,prefix).find(e=>e.slug===slug);
  assert(entry);
  const url=new URL(file.split('/').map(encodeURIComponent).join('/'),'file:///root/');
  assert.equal(decodeURIComponent(url.pathname.slice('/root/'.length)),file);
  assert.equal(url.hash,'');assert.equal(url.search,'');
 }
});
test('full root scoped context CLI and Viewer give equal field states',async()=>{
 const u=simulate({useBundle:true});await u.flush();await u.host.rdgExplorer.openFull('context-working-root');
 const cli=cp.spawnSync('python3',[path.join(root,'tools/rdg-context.py'),'--fields','--root-graph-slug','context-working-root'],{encoding:'utf8'});
 assert.equal(cli.status,0,cli.stderr);
 assert.deepEqual(JSON.parse(JSON.stringify(u.host.rdgState.list())),JSON.parse(cli.stdout));
 const r=JSON.parse(cli.stdout);
 assert(r.fields.some(f=>f.answerStatus==='known'&&f.state==='now'));
 assert(r.fields.some(f=>f.state==='later'),'unselected branch fields must stay conditional');
});
test('full-R layout key is separate from local-R key and does not overwrite old graph-set positions',async()=>{
 const u=simulate({useBundle:true});await u.flush();await u.host.rdgExplorer.openFull('reference-prepared-planning-tree');
 const full=u.host.rdgLayout.graphKey();const parts=JSON.parse(full);
 assert.deepEqual(parts,['rdg-example-prepared-v7','full-reference-prepared-planning-tree','R-PLAN']);
 assert.notEqual(full,JSON.stringify({type:'graph-set',id:'example-prepared'}));
 const graph=u.root.querySelectorAll('.node').find(x=>x.getAttribute('data-id')==='RF-1');
 graph.listeners.click({stopPropagation(){}});await u.flush();
 assert.notEqual(u.host.rdgLayout.graphKey(),full);
 u.ids.back.onclick();await u.flush();assert.equal(u.host.rdgLayout.graphKey(),full);
});
test('real index discovers separate root graphs even where user folders coincide',()=>{
 const byFolder=new Map();
 for(const e of index.fullGraphs){const arr=byFolder.get(e.folder)||[];arr.push(e);byFolder.set(e.folder,arr);}
 assert.deepEqual((byFolder.get('examples')||[]).map(x=>x.slug).sort(),['reference-action-time-plan','reference-mixed-active-work','reference-prepared-planning-tree']);
 for(const entry of index.fullGraphs){const root=project(entry.file);
  assert.equal(entry.rootRequirementId,root.rootRequirementId);
  assert(root.nodes.some(n=>n.kind==='requirement'&&n.id===entry.rootRequirementId));}
});
test('all two noncausal legacy groups preserve supplementary source navigation without false causal parents',()=>{
 const projection=require('../tools/rdg-root-projection.js');
 const bundled={...index,graphs:index.graphs.map(x=>({...x,graph:project(x.file)}))};
 for(const slug of ['reference-complete-app','reference-mixed-active-work']){
  const p=projection.project(bundled,slug);
  assert(p.supplementaryViews.some(r=>['derived','same-requirement'].includes(r.relationKind)));
  for(const edge of p.edges)assert(!['same-requirement','derived'].includes(edge.kind));
 }
});
test('catalog discovery refuses a graph.json symlink escaping the root, without needing a set manifest',()=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-no-set-symlink-'));
 const outside=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-outside-'));
 try{
  const origin={schemaVersion:1,id:'outside',catalogSlug:'outside',revision:1,
    rootRequirementId:'R',identitySpace:'u:outside',nodes:[{kind:'requirement',id:'R',title:'Outside'}],edges:[]};
  fs.writeFileSync(path.join(outside,'graph.json'),JSON.stringify(origin));
  fs.mkdirSync(path.join(base,'entry'));fs.symlinkSync(path.join(outside,'graph.json'),path.join(base,'entry','graph.json'));
  const code=`from pathlib import Path\nfrom importlib.machinery import SourceFileLoader\nimport sys\nm=SourceFileLoader('root_catalog',sys.argv[1]).load_module()\nm.discover(Path(sys.argv[2]))`;
  const r=cp.spawnSync('python3',['-c',code,path.join(root,'tools/rdg-catalog.py'),base],{encoding:'utf8'});
  assert.notEqual(r.status,0,'outside symlink must not be accepted');
  assert.match(r.stderr,/outside|symlink|graph/);
 }finally{fs.rmSync(base,{recursive:true,force:true});fs.rmSync(outside,{recursive:true,force:true});}
});
test('writer/index supports independently authored writable paper continuations across graph.json files',()=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-writable-branches-'));
 try{
  const tools=path.join(base,'tools'),graphs=path.join(base,'graphs');fs.mkdirSync(tools);fs.mkdirSync(graphs);
  for(const name of ['graph-index.py','rdg-catalog.py','rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js'])
    fs.copyFileSync(path.join(root,'tools',name),path.join(tools,name));
  const req=(id,title,extra={})=>({kind:'requirement',id,title,...extra});
  const opt=id=>({kind:'option',id,title:id,status:'candidate',origin:'situational'});
  const edge=(type,from,to)=>({type,from,to,id:type+from+to});
  const parent={schemaVersion:1,id:'root',catalogSlug:'root',identitySpace:'user:paper',rootRequirementId:'R0',
   revision:1,readOnly:false,nodes:[req('R0','Goal'),opt('O-A'),opt('O-B'),req('R1','Potential', {status:'candidate'}),req('R-OTHER','Alternative',{status:'candidate'})],
   edges:[edge('OPTION_FOR','R0','O-A'),edge('OPTION_FOR','R0','O-B'),edge('OUTCOME_OF','O-A','R1'),edge('OUTCOME_OF','O-B','R-OTHER')],events:[]};
  const child={schemaVersion:1,id:'child',catalogSlug:'child',identitySpace:'user:paper',rootRequirementId:'R1',revision:1,
    readOnly:false,expansionOf:{graphSlug:'root',nodeId:'R1'},nodes:[req('R1','Potential',{status:'candidate',projectionOf:{graphSlug:'root',nodeId:'R1'}}),opt('O-NEXT'),req('R2','Grandchild',{status:'candidate'})],
    edges:[edge('OPTION_FOR','R1','O-NEXT'),edge('OUTCOME_OF','O-NEXT','R2')],events:[]};
  for(const [name,obj] of [['root',parent],['child',child]]){
    fs.mkdirSync(path.join(graphs,name));fs.writeFileSync(path.join(graphs,name,'graph.json'),JSON.stringify(obj));}
  const execute=()=>cp.spawnSync('python3',[path.join(tools,'graph-index.py')],{encoding:'utf8'});
  let r=execute();assert.equal(r.status,0,r.stderr);
  const manifest=JSON.parse(fs.readFileSync(path.join(graphs,'index.json'),'utf8'));
  assert.equal(manifest.fullGraphs.length,1);
  assert(manifest.relations.some(x=>x.relationKind==='potential'&&x.from==='root'&&x.to==='child'&&x.requirementId==='R1'));
  assert.equal(JSON.parse(fs.readFileSync(path.join(graphs,'root','graph.json'))).events.length,0);
  child.nodes[0].projectionOf={graphSlug:'wrong-owner',nodeId:'R1'};
  fs.writeFileSync(path.join(graphs,'child','graph.json'),JSON.stringify(child));
  r=execute();assert.notEqual(r.status,0,'broken identity binding must be rejected');
  assert.match(r.stderr,/owner|projection|invalid|unresolved/i);
 }finally{fs.rmSync(base,{recursive:true,force:true});}
});
test('five old unscoped standalone graph.json remain discoverable without forged full identities',async()=>{
 const c=catalog.normalizeCatalog(index);
 for(const slug of ['try-it','example','reference-app-definition','reference-behavior-review','reference-delegation-status']){
  const item=c.standalone.find(x=>x.slug===slug);assert(item,'lost local standalone '+slug);
  assert(!c.fullGraphs.some(e=>e.slug===slug));
  assert(catalog.listFolder(c,item.folder).some(e=>e.slug===slug));
 }
 const u=simulate({useBundle:true});await u.flush();u.openFolder('workspaces');
 assert(u.ids['graph-list'].children.some(n=>n.getAttribute('data-graph')==='try-it'));
 await u.openCard('try-it');
 assert(u.root.querySelectorAll('.node').some(n=>n.getAttribute('data-id')==='R-001'));
});
