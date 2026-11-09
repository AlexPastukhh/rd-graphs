'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const g=require('../graphs/examples/reference-action-time-plan/graph.json'),v=g.workflowExample;
const projection=require('../tools/rdg-root-projection.js');
const root=path.resolve(__dirname,'..'),read=slug=>JSON.parse(fs.readFileSync(path.join(root,'graphs/examples',slug,'graph.json')));
const node=id=>g.nodes.find(n=>n.id===id);
const canonical=o=>Array.isArray(o)?o.map(canonical):o&&typeof o==='object'?Object.fromEntries(Object.keys(o).sort().map(k=>[k,canonical(o[k])])):o;
test('current Action example covers both roles, real history, explicit planning and no accepted project choice',()=>{
 assert(g.readOnly&&g.exampleOnly&&g.hypothetical&&g.selectedInProject===false);
 assert.equal(g.actionModel,'candidate-v6');assert(!g.nodes.some(n=>n.kind==='option'||n.kind==='decision'));
 assert.equal(new Set(g.edges.filter(e=>e.from==='A-SPLIT'&&e.type==='INTRODUCES').map(e=>e.childRole)).size,2);
 const done=v.sources.completion[v.graphFile];
 assert(done['A-SPLIT'].complete);assert(!done.R0.complete);
 assert(done['A-LOCAL'].complete);assert(!done['R-INPUT'].complete);
 assert.equal(node('A-LOCAL').status,'superseded');assert.equal(node('A-SERVER').status,'selected');
 assert(!done['A-SERVER'].complete);
 assert.deepEqual(new Set(v.future.map(r=>r.nodeId)),new Set(['R-INPUT','R-SEND','A-IDEMPOTENT','A-SERVER']));
 for(const id of ['A-ATOMIC','A-QUERY','A-RETRY-TEST'])assert(!v.sources.plan.steps.some(s=>(s.actionRef||s.requirementRef)?.nodeId===id),id+' silently placed');
 const e=g.events.find(e=>e.type==='action_executed'&&e.targetId==='A-LOCAL');
 const hash=crypto.createHash('sha256').update(JSON.stringify(canonical(e.viewSnapshot))).digest('hex');
 assert.equal(e.viewSnapshotSHA256,hash);
 assert.notDeepEqual(e.viewSnapshot.canonBlock,node('A-LOCAL').canonBlock);
 assert.notDeepEqual(e.viewSnapshot.qrpe,node('A-LOCAL').qrpe);
 const projected=projection.project({graphs:[{slug:g.id,graph:g}]},g.id);
 assert(projected.nodes.some(n=>n.id==='R-INPUT'&&n.branchState!=='potential'));
 const unsafe=structuredClone(g);unsafe.readOnly=false;
 assert(!projection.actionActive(node('A-SPLIT'),unsafe,'R0'),'incomplete example flags never authorize an Action path');
});
test('legacy lower methods have specific results and WAI preparation does not fabricate a study alternative',()=>{
 for(const slug of ['reference-prepared-planning-tree','reference-mixed-active-work']){
  const graph=read(slug);
  for(const n of graph.nodes.filter(n=>n.kind==='option')){
   assert(!['Непосредственное уточнение результата','Через отдельные состояния и проверки','По состояниям','По инвариантам'].includes(n.title),n.id);
  }
 }
 for(const slug of ['reference-prepared-feature-consistency','reference-mixed-feature-consistency']){
  const pair=read(slug).nodes.filter(n=>n.id.startsWith('O-A11Y-'));
  assert.equal(pair.length,2);assert(pair.every(n=>n.description.includes('Результат:')));
  assert(pair.every(n=>!/^Сначала изучить/.test(n.title)));
  assert.notEqual(pair[0].canonBlock.recommended[0].text,pair[1].canonBlock.recommended[0].text);
  assert.notEqual(pair[0].canonBlock.contraindicated[0].text,pair[1].canonBlock.contraindicated[0].text);
 }
});
