// RDG default coordinates are an ephemeral view, not a graph or layout write.
'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const P=require('../tools/rdg-visual-projection.js');
const L=require('../tools/rdg-layout-core.js');
const sources=path.join(__dirname,'../tools/rdg-agent-lenses');
const cards=(projection)=>projection.nodes.map(n=>({id:n.id,entityId:n.entityId,
  point:projection.occurrences[n.id]||projection.positions[n.id]}));
function assertNoOverlap(projection,label){
 const positioned=cards(projection);
 assert.equal(new Set(positioned.map(p=>p.id)).size,positioned.length,label+' image identities');
 assert(positioned.every(({point})=>point&&Number.isFinite(point.x)&&Number.isFinite(point.y)),label+' missing coordinate');
 for(let i=0;i<positioned.length;i++)for(let j=i+1;j<positioned.length;j++){
  const a=positioned[i],b=positioned[j];
  assert(Math.abs(a.point.x-b.point.x)>=220||Math.abs(a.point.y-b.point.y)>=126,
    `${label}: cards overlap: ${a.id} and ${b.id}`);
 }
}
function view(graph,spec){return {spec,entities:[...graph.nodes,...graph.objects],edges:graph.edges,
  decisionMemberships:(graph.decisionGroups||[]).flatMap(g=>g.members.map(m=>({
    id:m.id,type:'DECISION_MEMBER',from:g.parentId,to:m.decisionId,groupId:g.id}))),groupVisibility:[]};}
function sample(key){return JSON.parse(fs.readFileSync(path.join(sources,key+'-decision.json'),'utf8'));}
function canonOnlyInfoIds(graph){
 const canons=new Set((graph.objects||[]).filter(n=>n.kind==='canon').map(n=>n.id));
 const edges=(graph.edges||[]).filter(e=>!e.archived);
 return new Set((graph.objects||[]).filter(n=>n.kind==='info').filter(n=>{
  const links=edges.filter(e=>e.from===n.id||e.to===n.id);
  return links.length>0&&links.every(e=>e.type==='INFO_FOR'&&e.from===n.id&&canons.has(e.to));
 }).map(n=>n.id));
}
for(const key of ['orient','review','decision-logic','lens-system'])test(key+': default overview and focused view are stable, typed and never overlap',()=>{
 const graph=sample(key),before=JSON.stringify(graph),layout={positions:{},occurrences:{}};
 const v=view(graph,{kind:'graph',compactGraph:true,showAllBlocks:true}),compact=P.decisionProject(graph,v,layout);
 assertNoOverlap(compact,key+' compact');
 const hiddenCanonInfo=canonOnlyInfoIds(graph);
 const visibleIds=new Set([...graph.nodes,...graph.objects].filter(n=>n.kind!=='canon'&&!hiddenCanonInfo.has(n.id)).map(n=>n.id));
 assert.equal(compact.nodes.length,visibleIds.size,'Canon remains model data, not a graph image');
 assert(!compact.nodes.some(n=>n.node.kind==='canon'));
 assert.deepEqual(compact.routes.map(r=>r.edge.id).sort(),
   graph.edges.filter(e=>visibleIds.has(e.from)&&visibleIds.has(e.to)).map(e=>e.id).sort());
 assert.deepEqual(P.decisionProject(graph,v,layout).positions,compact.positions,'deterministic reload');
 for(const route of compact.routes.filter(r=>['DRIVES','DERIVES','INTRODUCES','REQUIRES_ACTION'].includes(r.edge.type))){
  const from=compact.positions[route.from],to=compact.positions[route.to];
  // Directed acyclic branches should flow down; cross-links/cycles are allowed.
  if(from&&to&&route.edge.from!==route.edge.to&&route.edge.type==='DRIVES')
    assert(to.y>=from.y,key+' drives '+route.edge.id);
 }
 const manual=P.decisionProject(graph,view(graph,{kind:'graph',compactGraph:false,showAllBlocks:true}),layout);
 assertNoOverlap(manual,key+' new manual canvas');
 const comparePositions=picture=>Object.fromEntries([...visibleIds].map(id=>[id,picture.positions[id]]));
 assert.deepEqual(comparePositions(manual),comparePositions(compact),
   'visible entities start at the same coordinates; hidden Canon coordinates are not projected');
 const focus=P.decisionProject(graph,view(graph,{kind:'focus',id:graph.rootRequirementId}),layout);
 assertNoOverlap(focus,key+' focus');
 assert.equal(focus.occurrences&&Object.keys(focus.occurrences).length,0);
 assert.equal(JSON.stringify(graph),before,'projection never changes domain model');
 assert.deepEqual(layout,{positions:{},occurrences:{}},'projection never writes owner layout');
});
test('saved manual coordinates stay authoritative; new nodes do not overlap them',()=>{
 const graph=sample('review'),id=graph.nodes[0].id;
 const layout={positions:{[id]:{x:-9000,y:7000}},occurrences:{}};
 const original=JSON.stringify(layout),v=view(graph,{kind:'graph',compactGraph:false,showAllBlocks:true});
 const picture=P.decisionProject(graph,v,layout);
 assert.deepEqual(picture.positions[id],layout.positions[id]);
 assertNoOverlap(picture,'partially-saved manual layout');
 assert.equal(JSON.stringify(layout),original,'no implicit persist/overwrite');
 v.spec.compactGraph=true;
 const compact=P.decisionProject(graph,v,layout);
 assertNoOverlap(compact,'temporary compact with saved outlier');
 assert.equal(JSON.stringify(layout),original);
 v.spec.compactGraph=false;
 assert.deepEqual(P.decisionProject(graph,v,layout).positions[id],layout.positions[id]);
});
test('many neighbors in a focused view wrap into columns; explicit focus drag is respected',()=>{
 const graph=sample('decision-logic'),spec={kind:'focus',id:graph.rootRequirementId};
 const data=view(graph,spec),original=JSON.stringify(graph);
 const projected=P.decisionProject(graph,data);
 assertNoOverlap(projected,'large focus');
 const ys=cards(projected).map(x=>x.point.y);
 assert(Math.max(...ys)-Math.min(...ys)<1000,'focus should not require 20+ stacked rows');
 const manuallyMoved={x:projected.positions[graph.rootRequirementId].x+45,y:projected.positions[graph.rootRequirementId].y+30};
 spec.focusPositions={[graph.rootRequirementId]:manuallyMoved};
 const after=P.decisionProject(graph,data);
 assert.deepEqual(after.positions[graph.rootRequirementId],manuallyMoved);
 assert.deepEqual(JSON.stringify(graph),original);
});
test('shared branches remain distinct images and keep real routes in both layout modes',()=>{
 const graph={identitySpace:'550e8400-e29b-41d4-a716-446655440000',rootCauses:[{requirementId:'R0',enabled:true}],
  nodes:[{id:'R0',kind:'requirement'},{id:'D1',kind:'decision'},{id:'D2',kind:'decision'},
    {id:'R1',kind:'requirement'},{id:'A1',kind:'action'}],objects:[],decisionGroups:[],edges:[
    {id:'e1',type:'DRIVES',from:'R0',to:'D1'},{id:'e2',type:'DRIVES',from:'R0',to:'D2'},
    {id:'e3',type:'INTRODUCES',from:'D1',to:'R1'},{id:'e4',type:'INTRODUCES',from:'D2',to:'R1'},
    {id:'e5',type:'REQUIRES_ACTION',from:'R1',to:'A1'}]};
 const original=JSON.stringify(graph);
 for(const compactGraph of [true,false]){
  const pic=P.decisionProject(graph,view(graph,{kind:'graph',compactGraph}));
  assertNoOverlap(pic,compactGraph?'compact repeat':'manual repeat');
  assert.equal(pic.nodes.filter(n=>n.entityId==='R1').length,2);
  assert.equal(pic.routes.length,5);
  assert(pic.routes.some(r=>r.from==='D2'&&r.to.startsWith('occ-')));
  assert.deepEqual(pic.nodes.map(n=>n.node.kind).sort(),['requirement','decision','decision','requirement','requirement','action'].sort());
 }
 assert.equal(JSON.stringify(graph),original);
});
test('root-only, disconnected, and cyclic views always get finite independent coordinates',()=>{
 const graph={identitySpace:'550e8400-e29b-41d4-a716-446655440000',rootCauses:[],
  nodes:Array.from({length:23},(_,i)=>({id:'N'+i,kind:i%3===0?'requirement':i%3===1?'decision':'action'})),objects:[],decisionGroups:[],edges:[]};
 const v=view(graph,{kind:'graph',compactGraph:true});
 assertNoOverlap(P.decisionProject(graph,v),'disconnected');
 graph.edges=[{id:'c1',type:'DRIVES',from:'N0',to:'N1'},
   {id:'c2',type:'DRIVES',from:'N1',to:'N2'},
   {id:'c3',type:'DRIVES',from:'N2',to:'N0'}];
 v.edges=graph.edges;const p=P.decisionProject(graph,v);assertNoOverlap(p,'cycle');
 assert.deepEqual(p.routes.map(r=>r.edge.id).sort(),['c1','c2','c3']);
});

test('checkpoint: overview is six structural cards and five links, with access to hidden content',()=>{
 const graph=sample('checkpoint'),layout={positions:{},occurrences:{}};
 const original=JSON.stringify(graph),base=JSON.stringify(layout);
 const spec={kind:'graph',compactGraph:true};
 const v=view(graph,spec),brief=P.decisionProject(graph,v,layout);
 assertNoOverlap(brief,'checkpoint overview');
 assert.deepEqual(brief.nodes.map(n=>n.node.kind).sort(),['requirement',...Array(5).fill('decision')].sort());
 assert.deepEqual(brief.routes.map(r=>r.edge.type),Array(5).fill('DRIVES'));
 assert.deepEqual(brief.supportingCounts['R-LENS-CHECKPOINT'],{info:1});
 for(let i=1;i<=5;i++)assert.deepEqual(brief.supportingCounts['CP-A'+i],{info:7});
 spec.showAllBlocks=true;
 const expanded=P.decisionProject(graph,v,layout);
 assertNoOverlap(expanded,'checkpoint full');
 assert.equal(expanded.nodes.length,7,'Canon and its Canon-only Info stay in the inspector, not on the graph canvas');
 assert(!expanded.nodes.some(n=>n.node.kind==='canon'));
 assert(!expanded.nodes.some(n=>n.node.id==='CP-C1'),'Canon-only Info is not left as an orphan graph image');
 assert.deepEqual(expanded.routes.reduce((result,r)=>(result[r.edge.type]=(result[r.edge.type]||0)+1,result),{}),
   {DRIVES:5,INFO_FOR:1});
 assert.deepEqual(expanded.supportingCounts,{});
 spec.showAllBlocks=false;
 const restored=P.decisionProject(graph,v,layout);
 assert.deepEqual(restored.nodes.map(n=>n.id),brief.nodes.map(n=>n.id));
 assert.equal(JSON.stringify(graph),original);
 assert.equal(JSON.stringify(layout),base);
});
test('overview hides only Canon and Info; Context and Evidence stay visible, even in workGraph',()=>{
 const graph=sample('model'),spec={kind:'graph',compactGraph:true};
 const a=P.decisionProject(graph,view(graph,spec));
 assert(!a.nodes.some(n=>['canon','info'].includes(n.node.kind)));
 assert(a.nodes.some(n=>n.node.kind==='context'));
 const full=P.decisionProject(graph,view(graph,{kind:'graph',compactGraph:false,showAllBlocks:true}));
 assert(!full.nodes.some(n=>n.node.kind==='canon'),'show-all must not put Canon back on the canvas');
 const focus=P.decisionProject(graph,view(graph,{kind:'focus',id:graph.rootRequirementId}));
 assert(!focus.nodes.some(n=>n.node.kind==='canon'),'focus must also keep Canon in the inspector');
 spec.kind='workGraph';spec.id='WG-test';
 const b=P.decisionProject(graph,view(graph,spec));
 assert.deepEqual(b.nodes.map(n=>n.entityId),a.nodes.map(n=>n.entityId));
 const layout={positions:{[graph.rootRequirementId]:{x:-900,y:1300}},occurrences:{}};
 const m=P.decisionProject(graph,view(graph,{kind:'graph',compactGraph:false}),layout);
 assert.equal(m.positions[graph.rootRequirementId].x,-900);
 assert.equal(m.positions[graph.rootRequirementId].y,1300);
 assertNoOverlap(m,'manual brief');
 // A saved supporting occurrence must survive a later write from the brief
 // 'My layout' mode. The presentation must not draw the hidden occurrence.
 const supporting=graph.objects.find(n=>n.kind==='info');
 const relation=graph.edges.find(e=>e.type==='INFO_FOR'&&e.from===supporting.id);
 assert(relation,'fixture must have a valid supporting relation');
 const manual={positions:{[graph.rootRequirementId]:{x:-900,y:1300}},occurrences:{
   'occ-saved-context':{entityId:supporting.id,x:2400,y:100,parentId:relation.to,viaEdgeId:relation.id,reverse:true}
 }};
 const snapshot=JSON.stringify(manual);
 const q=P.decisionProject(graph,view(graph,{kind:'graph',compactGraph:false}),manual);
 assert.deepEqual(q.occurrences['occ-saved-context'],manual.occurrences['occ-saved-context']);
 assert(!q.nodes.some(n=>n.id==='occ-saved-context'));
 assert.equal(JSON.stringify(manual),snapshot);
});
test('Canon and Canon-only Info stay in details; standalone Info remains accessible',()=>{
 const g={id:'G',identitySpace:'550e8400-e29b-41d4-a716-446655440000',rootCauses:[],nodes:[],
    objects:[{id:'C1',kind:'canon'},{id:'I1',kind:'info'},{id:'I2',kind:'info'}],decisionGroups:[],
    edges:[{id:'i1',type:'INFO_FOR',from:'I1',to:'C1'}]};
 const p=P.decisionProject(g,view(g,{kind:'graph',compactGraph:true}));
 assert.deepEqual(p.nodes.map(n=>n.entityId),['I2']);
 assert.equal(p.routes.length,0,'Canon-only Info is not orphaned from its hidden Canon');
 const full=P.decisionProject(g,view(g,{kind:'graph',showAllBlocks:true}));
 assert.deepEqual(full.nodes.map(n=>n.entityId),['I2']);
 assert(!full.nodes.some(n=>n.entityId==='C1'));
 const focused=P.decisionProject(g,view(g,{kind:'focus',id:'I1'}));
 assert(focused.nodes.some(n=>n.entityId==='I1'),'Canon-only Info remains directly inspectable from its own reference');
 assert(!focused.nodes.some(n=>n.node.kind==='canon'),'Canon itself remains inspector-only');
});
