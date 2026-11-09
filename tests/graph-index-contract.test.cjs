const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
function fixtures(){
 const parent={schemaVersion:1,revision:1,identitySpace:'test',rootRequirementId:'R',
  nodes:[{id:'R',kind:'requirement',title:'Parent'},{id:'D',kind:'decision',title:'Choice',status:'committed'},{id:'C',kind:'requirement',title:'Child'}],
  edges:[{id:'drive',type:'DRIVES',from:'R',to:'D'},{id:'intro',type:'INTRODUCES',from:'D',to:'C',parent:'R'}],events:[]};
 const child={schemaVersion:1,revision:1,identitySpace:'test',rootRequirementId:'C',
  nodes:[{id:'C',kind:'requirement',title:'Child',projectionOf:{graphSlug:'parent',nodeId:'C'}}],edges:[],events:[]};
 return {parent,child};
}
function run(gs){
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-index-contract-'));
 try{
  fs.mkdirSync(path.join(tmp,'tools'));for(const f of ['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js'])fs.copyFileSync(path.join(root,'tools',f),path.join(tmp,'tools',f));fs.copyFileSync(path.join(root,'tools/graph-index.py'),path.join(tmp,'tools/graph-index.py'));fs.copyFileSync(path.join(root,'tools/rdg-catalog.py'),path.join(tmp,'tools/rdg-catalog.py'));
  for(const [slug,g] of Object.entries(gs)){const dir=path.join(tmp,'graphs/examples',slug);fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(path.join(dir,'graph.json'),JSON.stringify(g));}
  const result=spawnSync('python3',[path.join(tmp,'tools/graph-index.py')],{encoding:'utf8'});
  return {...result,manifest:result.status===0?JSON.parse(fs.readFileSync(path.join(tmp,'graphs/index.json'),'utf8')):null};
 }finally{fs.rmSync(tmp,{recursive:true,force:true});}
}
test('index links chosen decomposition with its parent driver, including explicitly hypothetical selection',()=>{
 const gs=fixtures();let r=run(gs);assert.equal(r.status,0,r.stderr);assert.equal(r.manifest.relations.length,1);
 Object.assign(gs.parent,{exampleOnly:true,hypothetical:true,readOnly:true,selectedInProject:false});
 gs.parent.nodes[1].status='selected-in-example-only';
 r=run(gs);assert.equal(r.status,0,r.stderr);assert.equal(r.manifest.relations.length,1);
});
test('pending, superseded and template introductions never become proven child levels',()=>{
 for(const status of ['pending','proposed','superseded','reusable-unselected']){
  const gs=fixtures();gs.parent.nodes[1].status=status;
  const r=run(gs);assert.equal(r.status,0,r.stderr);assert.equal(r.manifest.relations.length,0);
 }
 for(const mutate of [g=>g.templateOnly=true,g=>g.nodes[1].templateOnly=true,g=>g.edges[1].templateOnly=true,g=>g.edges[1].candidate=true]){
  const gs=fixtures();mutate(gs.parent);const r=run(gs);assert.equal(r.status,0,r.stderr);assert.equal(r.manifest.relations.length,0);
 }
});
test('index rejects a chosen introduction whose parent does not drive D',()=>{
 const gs=fixtures();gs.parent.edges.shift();const r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/parent does not drive/);
});
test('same R identity requires one owner; projected titles may differ but normative text may not',()=>{
 let gs=fixtures();gs.child.nodes[0].title='A different display title';
 let r=run(gs);assert.equal(r.status,0,r.stderr);assert.equal(r.manifest.relations.length,1);
 delete gs.child.nodes[0].projectionOf;
 r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/duplicate identity owner/);
 gs=fixtures();gs.child.nodes[0].requirementText='An incompatible normative statement';
 r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/projection overrides requirementText/);
 gs=fixtures();gs.parent.nodes[2].requirementText={bad:'shape'};
 r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/invalid Requirement statement/);
});
test('duplicate auxiliary ID is rejected even when neither occurrence is a graph root',()=>{
 const gs=fixtures();
 gs.parent.nodes.push({id:'AUX',kind:'requirement',title:'First'});
 gs.child.nodes.push({id:'AUX',kind:'requirement',title:'Second'});
 let r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/duplicate identity owner/);
 gs.child.nodes.at(-1).projectionOf={graphSlug:'parent',nodeId:'AUX'};
 r=run(gs);assert.equal(r.status,0,r.stderr);
});
test('unresolved, wrong-scope and cyclic record owner links are rejected',()=>{
 let gs=fixtures();gs.parent.nodes[2].projectionOf={graphSlug:'missing',nodeId:'C'};
 let r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/unresolved identity owner/);
 gs=fixtures();delete gs.child.identitySpace;
 r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/projection requires identitySpace/);
 gs=fixtures();gs.parent.nodes[2].projectionOf={graphSlug:'child',nodeId:'C'};gs.child.identitySpace='another';
 r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/unresolved identity owner/);
 gs=fixtures();gs.parent.nodes[2].projectionOf={graphSlug:'child',nodeId:'C'};gs.child.nodes[0].projectionOf={graphSlug:'parent',nodeId:'C'};
 r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/cyclic projectionOf/);
});


test('invalid graph schema and changed source Markdown fail closed before catalog publication',()=>{
 const gs=fixtures();gs.parent.schemaVersion=2;
 let r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/invalid graph schemaVersion/);
 gs.parent.schemaVersion=1;gs.parent.sourceMarkdown='Original source';gs.parent.sourceContentSHA256='unchanged-old-hash';
 r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/sourceContentSHA256 differs from sourceMarkdown/);
});
test('Unit source owner and anchor resolve to existing source text',()=>{
 const gs=fixtures();
 const crypto=require('node:crypto');
 const text=['Primary source','# Child','Section anchor present'].join(String.fromCharCode(10));
 gs.parent.sourceMarkdown=text;
 gs.parent.sourceContentSHA256=crypto.createHash('sha256').update(text).digest('hex');
 gs.child.sourceOwnerGraphSlug='parent';
 gs.child.sourceContentSHA256=gs.parent.sourceContentSHA256;
 gs.child.sourceAnchor='Section anchor';
 let r=run(gs);assert.equal(r.status,0,r.stderr);
 gs.child.sourceAnchor='anchor does not exist';
 r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/unresolved source anchor/);
 gs.child.sourceAnchor='Section anchor';gs.child.sourceOwnerGraphSlug='missing';
 r=run(gs);assert.notEqual(r.status,0);assert.match(r.stderr,/unresolved source owner/);
});
