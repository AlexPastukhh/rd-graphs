const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const read=(relative)=>fs.readFileSync(path.join(root,relative),'utf8');
const src=read('docs/examples/requirements-decisions-graph-examples-v0.2.source.md');
const graph=id=>JSON.parse(read('graphs/'+(id==='try-it'?'workspaces':'examples')+'/'+id+'/graph.json'));
const refs=['reference-app-definition','reference-delegation-status','reference-behavior-review'];
function hash(s){let h=2166136261;for(let i=0;i<s.length;i++)h=Math.imul(h^s.charCodeAt(i),16777619)>>>0;return h.toString(16);}
test('verbatim 0.2 source from original user upload remains unchanged',()=>{
 assert.equal(src.length,30360);assert.equal(hash(src),'896505f4');
 assert.match(src,/Версия: 0.2, 2026-10-10/);
 assert.match(src,/PR-GEX-001\/003\/004/);
});
test('three read-only reference views have intact IDs, edges and source provenance',()=>{
 for(const id of refs){
  const g=graph(id),ids=new Set(g.nodes.map(n=>n.id)),edids=new Set();
  assert.equal(g.schemaVersion,1);assert.equal(g.revision,1);
  assert.equal(g.readOnly,true);assert.equal(g.exampleOnly,true);
  assert.equal(ids.size,g.nodes.length);
  assert.equal(g.sourceDocument,'docs/examples/requirements-decisions-graph-examples-v0.2.source.md');
  assert(g.nodes.every(n=>n.id.startsWith('EX-')&&src.includes(n.id)));
  for(const e of g.edges){
   assert(!edids.has(e.id));edids.add(e.id);
   assert(ids.has(e.from)&&ids.has(e.to),e.id);
   if(e.type==='INTRODUCES')assert(ids.has(e.parent),e.id);
   if(g.illustrativeTypes?.includes(e.type))assert(e.illustrative===true,e.id);
  }
 }
});
test('App Definition contains seven sibling R and concrete scenario-to-feature information',()=>{
 const g=graph('reference-app-definition');
 const parent=g.edges.filter(e=>e.from==='EX-D-APP'&&e.type==='INTRODUCES');
 assert.equal(parent.length,7);assert(parent.every(e=>e.parent==='EX-R-PLAN'));
 assert.equal(g.nodes.length,23);assert.equal(g.edges.length,29);
 const f=g.edges.filter(e=>e.to==='EX-D-FEATURES'&&e.type==='INFORMS');
 assert.deepEqual(new Set(f.map(e=>e.from)),new Set(['EX-D-SCREATE','EX-D-SCANCEL','EX-D-SLOOKUP']));
 assert.equal(g.nodes.filter(n=>n.id.startsWith('EX-RR-')).length,3);
 assert(g.edges.some(e=>e.from==='EX-Q-R-INDEPENDENT'&&e.to==='EX-RR-INDEPENDENT'&&e.type==='QRPE_FOR'));
});
test('Scenario delegation is one stable R ID and status QRPE does not assert completion',()=>{
 const g=graph('reference-delegation-status');
 assert.equal(g.nodes.filter(n=>n.id==='EX-R-DESCRIBE-CREATE').length,1);
 assert.match(g.nodes.find(n=>n.id==='EX-R-DESCRIBE-CREATE').targetModule,/Scenario S-CREATE/);
 assert(!g.nodes.some(n=>n.id==='EX-TM-SCREATE'));
 const status=g.nodes.find(n=>n.id==='EX-D-STATUS');
 assert.equal(status.evidenceStatus,'unverified');
 assert.equal(status.openQuestion,'EX-Q-D-STATUS');
 assert(g.edges.some(e=>e.type==='REVEALS_NEED'&&e.from==='EX-D-SCREATE'&&e.to==='EX-R-RESULT'));
});
test('Behavior distinguishes shared scope, local D, pending candidates and hypothetical events',()=>{
 const g=graph('reference-behavior-review');
 assert.equal(g.nodes.find(n=>n.id==='EX-D-BEHAVIOR').scope,'Behavior всех Feature Target Modules данного приложения');
 assert.equal(g.nodes.find(n=>n.id==='EX-PR-STATE').status,'pending');
 assert.equal(g.nodes.find(n=>n.id==='EX-PR-HYBRID').status,'pending');
 assert.equal(g.nodes.filter(n=>n.id==='EX-D-BEHAVIOR').length,1);
 assert.equal(g.events.length,3);
 assert.deepEqual(g.events.map(e=>e.id),['EX-E1','EX-E2','EX-E3']);
 assert.equal(g.events[0].by,'example');
 assert(!g.events.some(e=>e.by==='user'));
});
test('bootstrap uses reference-index module but pilot has no preselected decisions',()=>{
 const bootstrap=read('work-kit/prompts/rdg.work.bootstrap.prompt.md');
 const module=read('work-kit/modules/rdg.work.examples.module.md');
 assert.match(bootstrap,/\[\[module:rdg\.work\.examples\]\]/);
 assert.match(bootstrap,/EXAMPLE-COVERAGE\.md/);
 for(const id of refs)assert(module.includes(id));
 const pilot=graph('try-it');assert.equal(pilot.revision,1);
 assert.equal(pilot.nodes.length,1);assert.equal(pilot.events.length,0);
});

test('reference-only graphs reject updater commands without creating write locks',()=>{
 const {spawnSync}=require('node:child_process');
 const file=path.join(root,'graphs/examples/reference-app-definition/graph.json');
 const patch=path.join(root,'graphs/workspaces/try-it/patches/accept-example.DO-NOT-APPLY.json');
 const before=fs.readFileSync(file,'utf8');
 const lock=path.join(root,'graphs/examples/reference-app-definition/.graph-apply.lock');
 assert.equal(fs.existsSync(lock),false,'Reference lock unexpectedly exists');
 const output=spawnSync('python3',[path.join(root,'tools/graph-apply.py'),
   '--graph',file,'--patch',patch,'--dry-run'],{encoding:'utf8'});
 assert.notEqual(output.status,0);
 assert.match(output.stderr,/READ_ONLY_GRAPH/);
 assert.equal(fs.readFileSync(file,'utf8'),before);
 assert.equal(fs.existsSync(lock),false,'Read-only preflight must not create lock');
});
