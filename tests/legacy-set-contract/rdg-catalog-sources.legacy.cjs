const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process');
const ROOT=path.resolve(__dirname,'..');
function temp(){const p=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-catalog-test-'));return p;}
function json(base,file,value){const f=path.join(base,file);fs.mkdirSync(path.dirname(f),{recursive:true});fs.writeFileSync(f,JSON.stringify(value));}
function graph(slug){return{schemaVersion:1,id:slug,catalogSlug:slug,revision:1,identitySpace:'test',rootRequirementId:slug+'-R',nodes:[{id:slug+'-R',kind:'requirement',title:slug}],edges:[]};}
function discover(base){const script="from importlib.machinery import SourceFileLoader\nfrom pathlib import Path\nimport json,sys\nm=SourceFileLoader('cat',sys.argv[1]).load_module()\nprint(json.dumps(m.discover(Path(sys.argv[2]))))";return cp.spawnSync('python3',['-c',script,path.join(ROOT,'tools/rdg-catalog.py'),base],{encoding:'utf8'});}
test('arbitrary nested and empty folders are discovered without adding code branches; ready/working are explicit',()=>{
 const p=temp();try{json(p,'new/deep/a/graph.json',{...graph('a'),presentation:{usage:'ready'}});json(p,'new/deep/b/graph.json',{...graph('b'),readOnly:true,presentation:{usage:'working',exampleOnly:true}});fs.mkdirSync(path.join(p,'empty'));
 const r=discover(p);assert.equal(r.status,0,r.stderr);const [graphs,folders]=JSON.parse(r.stdout);assert.equal(graphs.length,2);assert.equal(graphs[0].folder,'new/deep');assert(folders.some(f=>f.id==='empty'));assert.equal(graphs[1].presentation.usage,'working');assert.equal(graphs[1].graph.readOnly,true);
 assert.deepEqual(discover(p).stdout,r.stdout);
 }finally{fs.rmSync(p,{recursive:true,force:true})}
});
test('two sets in the same identity space keep explicit membership and stable slugs independent of paths',()=>{
 const p=temp();try{for(const id of ['a','b']){json(p,'members/'+id+'/graph.json',graph('stable-'+id));json(p,'sets/'+id+'/graph-set.json',{schemaVersion:1,id,revision:1,presentation:{usage:id==='a'?'ready':'working'},members:[{graphSlug:'stable-'+id,file:'../../members/'+id+'/graph.json'}],entryGraphSlugs:['stable-'+id]});}
 const r=discover(p);assert.equal(r.status,0,r.stderr);const [g,_,sets]=JSON.parse(r.stdout);assert.equal(sets.length,2);assert.equal(g.find(g=>g.slug==='stable-a').setId,'a');assert.equal(g.find(g=>g.slug==='stable-b').setId,'b');
 fs.mkdirSync(path.join(p,'moved'));fs.renameSync(path.join(p,'members/a'),path.join(p,'moved/root'));const descriptor=JSON.parse(fs.readFileSync(path.join(p,'sets/a/graph-set.json')));descriptor.members[0].file='../../moved/root/graph.json';json(p,'sets/a/graph-set.json',descriptor);
 const moved=discover(p);assert.equal(moved.status,0,moved.stderr);assert.equal(JSON.parse(moved.stdout)[0].find(g=>g.slug==='stable-a').file,'moved/root/graph.json');
 }finally{fs.rmSync(p,{recursive:true,force:true})}
});
test('missing, escaping, duplicated or ambiguous members fail explicitly',()=>{
 for(const mode of ['missing','escape','duplicate','ambiguous']){
  const p=temp();try{json(p,'a/graph.json',graph('a'));const set={schemaVersion:1,id:'set',revision:1,members:[{graphSlug:'a',file:'../a/graph.json'}],entryGraphSlugs:['a']};
  if(mode==='missing')set.members[0].file='../absent/graph.json';
  if(mode==='escape')set.members[0].file='../../../outside/graph.json';
  if(mode==='duplicate')set.members.push(set.members[0]);
  json(p,'set/graph-set.json',set);if(mode==='ambiguous')json(p,'other/graph-set.json',{...set,id:'other'});
  const r=discover(p);assert.notEqual(r.status,0,mode);assert.match(r.stderr,/missing|outside|duplicate|ambiguous/);
  }finally{fs.rmSync(p,{recursive:true,force:true})}
 }
});
test('symlink members cannot escape the connected graph root',()=>{
 const p=temp(),outside=temp();try{json(outside,'graph.json',graph('a'));fs.symlinkSync(outside,path.join(p,'linked'));json(p,'set/graph-set.json',{schemaVersion:1,id:'set',revision:1,members:[{graphSlug:'a',file:'../linked/graph.json'}],entryGraphSlugs:['a']});const r=discover(p);assert.notEqual(r.status,0);assert.match(r.stderr,/outside|symlink/);}finally{fs.rmSync(p,{recursive:true,force:true});fs.rmSync(outside,{recursive:true,force:true})}
});
test('old plain graph with no metadata remains readable with unknown usage',()=>{
 const p=temp();try{const g=graph('a');delete g.catalogSlug;json(p,'unclassified/a/graph.json',g);const r=discover(p);assert.equal(r.status,0,r.stderr);assert.equal(JSON.parse(r.stdout)[0][0].presentation.usage,undefined);}finally{fs.rmSync(p,{recursive:true,force:true})}
});
test('nested workspace writer accepts a guarded transaction and refuses outside/read-only destinations',()=>{
 const p=temp();try{fs.mkdirSync(path.join(p,'tools'));for(const f of ['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js','graph-apply.py','graph-package.py','graph-index.py','rdg-catalog.py','rdg-v7-model.py'])fs.copyFileSync(path.join(ROOT,'tools',f),path.join(p,'tools',f));
 const file='workspaces/project/levels/root/graph.json',g={...graph('nested-stable'),planningScale:'module',events:[]};
 const pkg={schemaVersion:1,transactionId:'nested-create',changes:[{file,create:g}]};json(p,'package.json',pkg);
 const run=()=>cp.spawnSync('python3',[path.join(p,'tools/graph-apply.py'),'--package','--patch',path.join(p,'package.json')],{encoding:'utf8'});
 let r=run();assert.equal(r.status,0,r.stderr);assert(fs.existsSync(path.join(p,'graphs',file)));const idx=JSON.parse(fs.readFileSync(path.join(p,'graphs/index.json')));assert.equal(idx.graphs[0].slug,'nested-stable');assert.equal(idx.graphs[0].file,file);
 const before=fs.readFileSync(path.join(p,'graphs',file),'utf8');pkg.transactionId='invalid-target';pkg.changes[0].file='workspaces/../examples/no/graph.json';json(p,'package.json',pkg);r=run();assert.notEqual(r.status,0);assert.equal(fs.readFileSync(path.join(p,'graphs',file),'utf8'),before);
 json(p,'graphs/workspaces/project/readonly/graph.json',{...graph('readonly'),planningScale:'unit',events:[],readOnly:true});pkg.transactionId='readonly';pkg.changes=[{file:'workspaces/project/readonly/graph.json',patch:{schemaVersion:1,expectedRevision:1,operations:[]}}];json(p,'package.json',pkg);r=run();assert.notEqual(r.status,0);assert.match(r.stderr,/READ_ONLY/);
 }finally{fs.rmSync(p,{recursive:true,force:true})}
});

test('producer and consumer accept literal hash, percent and Unicode folder names without URL interpretation',()=>{
 const catalog=require('../tools/rdg-catalog.js'),p=temp();
 try{for(const [i,folder] of ['Plans #1','Plan 100%','literal %2e','Планы и цели'].entries())json(p,folder+'/a/graph.json',graph('a'+i));
 const r=discover(p);assert.equal(r.status,0,r.stderr);const [graphs,folders,graphSets]=JSON.parse(r.stdout);
 const c=catalog.normalizeCatalog({schemaVersion:1,graphs,folders,graphSets});assert.equal(c.graphs.length,4);
 for(const g of c.graphs){const url=new URL(g.file.split('/').map(encodeURIComponent).join('/'),'file:///root/');
 assert.equal(decodeURIComponent(url.pathname.slice('/root/'.length)),g.file);assert.equal(url.hash,'');assert.equal(url.search,'');}
 for(const file of ['a/../b/graph.json','/root/a/graph.json','C:/a/graph.json','a\\b/graph.json','https://evil/a/graph.json'])
 assert.throws(()=>catalog.normalizeCatalog({schemaVersion:1,graphs:[{slug:'a',file}]}));
 }finally{fs.rmSync(p,{recursive:true,force:true})}
});
test('normal folder traversal reaches unlisted graphs inside set containers without changing membership',()=>{
 const catalog=require('../tools/rdg-catalog.js'),p=temp();
 try{json(p,'folder/set/levels/a/graph.json',graph('a'));json(p,'folder/set/extra/z/graph.json',graph('z'));
 json(p,'folder/set/graph-set.json',{schemaVersion:1,id:'s',revision:1,members:[{graphSlug:'a',file:'levels/a/graph.json'}],entryGraphSlugs:['a']});
 const r=discover(p);assert.equal(r.status,0,r.stderr);const [graphs,folders,graphSets]=JSON.parse(r.stdout);
 const c=catalog.normalizeCatalog({schemaVersion:1,graphs,folders,graphSets}),seen=new Set(),visited=new Set();
 function walk(folder=''){assert(!visited.has(folder));visited.add(folder);for(const e of catalog.listFolder(c,folder)){
 if(e.kind==='folder')walk(e.id);else if(e.kind==='graph')seen.add(e.slug);else e.members.forEach(s=>seen.add(s));}}
 walk();assert.deepEqual([...seen].sort(),['a','z']);assert.deepEqual(c.graphSets[0].members,['a']);assert.equal(c.graphs.find(g=>g.slug==='z').setId,undefined);
 assert(!folders.some(f=>f.id==='folder/set/levels'),'member internals remain hidden');
 }finally{fs.rmSync(p,{recursive:true,force:true})}
});
