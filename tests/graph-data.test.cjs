const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const base=path.resolve(__dirname,'..');
const graph=JSON.parse(fs.readFileSync(path.join(base,'graphs/examples/example/graph.json'),'utf8'));
const script=fs.readFileSync(path.join(base,'tools/rd-graph-viewer.user.js'),'utf8');
const start=script.indexOf('  function validate(g) {');
const end=script.indexOf('  function make(',start);
assert(start>=0 && end>start);
const validate=vm.runInNewContext('('+script.slice(start,end).trim()+')');
const copy=()=>JSON.parse(JSON.stringify(graph));
test('G01 example: 9 nodes / 8 edges, contiguous IDs, meaningful chain',()=>{
  assert.equal(validate(copy()).nodes.length,9);
  assert.equal(graph.edges.length,8);
  assert.equal(graph.revision,1);
  const ids=new Set(graph.nodes.map(n=>n.id));
  assert(graph.edges.every(e=>ids.has(e.from)&&ids.has(e.to)));
  assert(graph.edges.some(e=>e.from==='R-001'&&e.to==='D-001'&&e.type==='DRIVES'));
  assert(graph.edges.some(e=>e.from==='D-001'&&e.to==='R-002'&&e.parent==='R-001'));
});
test('G02 duplicate node ID is rejected',()=>{
  const g=copy();g.nodes.push({...g.nodes[0]});assert.throws(()=>validate(g));
});
test('G03 duplicate edge ID is rejected',()=>{
  const g=copy();g.edges.push({...g.edges[0]});assert.throws(()=>validate(g));
});
test('G04 dangling edge is rejected',()=>{
  const g=copy();g.edges[0].to='MISSING';assert.throws(()=>validate(g));
});
test('G05 INTRODUCES without parent is rejected',()=>{
  const g=copy();delete g.edges.find(e=>e.type==='INTRODUCES').parent;assert.throws(()=>validate(g));
});
test('G12 incompatible schemaVersion is rejected',()=>{
  const g=copy();g.schemaVersion=2;assert.throws(()=>validate(g));
});
test('G13 empty graph can be validated',()=>{
  const g={schemaVersion:1,id:'empty',title:'Empty',revision:1,nodes:[],edges:[],events:[]};
  assert.equal(validate(g),g);
});
test('G13 isolated requirement without a decision is allowed',()=>{
  const g={schemaVersion:1,revision:1,nodes:[{id:'R-X',kind:'requirement',title:'Unresolved'}],edges:[],events:[]};
  assert.equal(validate(g).nodes.length,1);
});
test('G14 Unicode / literal HTML-like content are valid data',()=>{
  const g=copy();g.nodes[0].title='Цель «доступность» <script>alert(1)</script> 😃';
  assert.equal(validate(g).nodes[0].title,g.nodes[0].title);
});
test('G15 valid 500-node limit',()=>{
  const nodes=Array.from({length:500},(_,i)=>({id:'R-'+i,kind:'requirement',title:'Node '+i}));
  const g={schemaVersion:1,revision:1,nodes,edges:[]};assert.equal(validate(g).nodes.length,500);
});
test('G15 501 nodes are rejected',()=>{
  const nodes=Array.from({length:501},(_,i)=>({id:'R-'+i,kind:'requirement',title:'Node '+i}));
  assert.throws(()=>validate({schemaVersion:1,revision:1,nodes,edges:[]}));
});
