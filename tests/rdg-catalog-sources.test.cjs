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
test('old plain graph with no metadata remains readable with unknown usage',()=>{
 const p=temp();try{const g=graph('a');delete g.catalogSlug;json(p,'unclassified/a/graph.json',g);const r=discover(p);assert.equal(r.status,0,r.stderr);assert.equal(JSON.parse(r.stdout)[0][0].presentation.usage,undefined);}finally{fs.rmSync(p,{recursive:true,force:true})}
});
test('nested workspace writer accepts a guarded transaction and refuses outside/read-only destinations',()=>{
 const p=temp();try{fs.mkdirSync(path.join(p,'tools'));for(const f of ['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js','rdg-modules.py','rdg-module-registry.json','rdg-module-test.py','graph-apply.py','graph-package.py','rdg-transaction-io.py','graph-index.py','rdg-catalog.py','rdg-v7-model.py','rdg-v6-action-reconsider.py','rdg-v6-action-trust.py','rdg-graph-api.py','rdg-completion-context.py'])fs.copyFileSync(path.join(ROOT,'tools',f),path.join(p,'tools',f));
 const file='workspaces/project/levels/root/graph.json',g={...graph('nested-stable'),actionModel:'candidate-v6',planningScale:'module',events:[]};
 const pkg={schemaVersion:1,transactionId:'nested-create',changes:[{file,create:g}]};json(p,'package.json',pkg);
 const run=()=>cp.spawnSync('python3',[path.join(p,'tools/graph-apply.py'),'--package','--patch',path.join(p,'package.json')],{encoding:'utf8'});
 let r=run();assert.equal(r.status,0,r.stderr);assert(fs.existsSync(path.join(p,'graphs',file)));const idx=JSON.parse(fs.readFileSync(path.join(p,'graphs/index.json')));assert.equal(idx.graphs[0].slug,'nested-stable');assert.equal(idx.graphs[0].file,file);
 const before=fs.readFileSync(path.join(p,'graphs',file),'utf8');pkg.transactionId='invalid-target';pkg.changes[0].file='workspaces/../examples/no/graph.json';json(p,'package.json',pkg);r=run();assert.notEqual(r.status,0);assert.equal(fs.readFileSync(path.join(p,'graphs',file),'utf8'),before);
 json(p,'graphs/workspaces/project/readonly/graph.json',{...graph('readonly'),planningScale:'unit',events:[],readOnly:true});pkg.transactionId='readonly';pkg.changes=[{file:'workspaces/project/readonly/graph.json',patch:{schemaVersion:1,expectedRevision:1,operations:[]}}];json(p,'package.json',pkg);r=run();assert.notEqual(r.status,0);assert.match(r.stderr,/READ_ONLY|ACTIVE_ONLY_CANDIDATE_V6/);
 }finally{fs.rmSync(p,{recursive:true,force:true})}
});

