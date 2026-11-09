'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const P=require('../tools/rdg-visual-projection.js'),L=require('../tools/rdg-layout-core.js');
const entities=[
 {id:'R1',kind:'requirement',title:'One'},
 {id:'R2',kind:'requirement',title:'Two'},
 {id:'A1',kind:'action',title:'Shared'},
 {id:'R3',kind:'requirement',title:'Output'},
 {id:'A4',kind:'action',title:'Continuation'},
 {id:'A2',kind:'action',title:'Other source'}
];
const edges=[
 {id:'d1',type:'DRIVES',from:'R1',to:'A1'},
 {id:'d2',type:'DRIVES',from:'R2',to:'A1'},
 {id:'o1',type:'INTRODUCES',from:'A1',to:'R3',origin:{role:'subgoal',requirementIds:['R1']}},
 {id:'d3',type:'DRIVES',from:'R3',to:'A4'},
 {id:'o2',type:'INTRODUCES',from:'A2',to:'R3',origin:{role:'method_correctness'}}
];
const positions=Object.fromEntries(entities.map((n,i)=>[n.id,{x:i*240,y:10}]));
test('one action rendered near two requirements has one identity and two true DRIVES',()=>{
 const occurrences={'occ-near-R2':{entityId:'A1',x:490,y:125,parentId:'R2',viaEdgeId:'d2'}};
 const projection=P.project(entities,edges,positions,occurrences);
 const a=projection.nodes.filter(n=>n.entityId==='A1');
 assert.equal(a.length,2);
 assert.equal(projection.counts.get('A1'),2);
 assert.equal(new Set(a.map(n=>n.node)).size,1);
 assert.deepEqual(projection.routes.filter(r=>['d1','d2'].includes(r.edge.id))
   .map(r=>[r.edge.id,r.from,r.to]).sort(),[['d1','R1','A1'],['d2','R2','occ-near-R2']]);
 assert.deepEqual(projection.routes.find(r=>r.edge.id==='o1').edge.origin,{role:'subgoal',requirementIds:['R1']});
});
test('two actions can display the same output R and its continuation twice',()=>{
 const occ={'occ-output-from-A2':{entityId:'R3',x:450,y:300,parentId:'A2',viaEdgeId:'o2'}};
 let count=0;const ids=()=> 'occ-'+(++count);
 const extended=P.addBranch(entities,edges,positions,occ,'occ-output-from-A2',1,ids,{duplicateRoot:false});
 assert.equal(extended.occurrences['occ-1'].entityId,'A4');
 assert.equal(extended.occurrences['occ-1'].viaEdgeId,'d3');
 const projection=P.project(entities,edges,positions,extended.occurrences);
 assert.equal(projection.counts.get('R3'),2);
 assert.equal(projection.counts.get('A4'),2);
 assert(projection.routes.some(r=>r.edge.id==='d3'&&r.from==='R3'&&r.to==='A4'));
 assert(projection.routes.some(r=>r.edge.id==='d3'&&r.from==='occ-output-from-A2'&&r.to==='occ-1'));
});
test('repeat whole R/A fragment to two levels without domain data duplication',()=>{
 let i=0;const before=JSON.stringify({entities,edges});
 const result=P.addBranch(entities,edges,positions,{},'A1',2,()=> 'occ-'+(++i));
 const projection=P.project(entities,edges,positions,result.occurrences);
 assert.equal(projection.counts.get('A1'),2);
 assert.equal(projection.counts.get('R3'),2);
 assert.equal(projection.counts.get('A4'),2);
 assert.deepEqual(projection.routes.filter(r=>r.edge.id==='o1').map(r=>r.from).sort(),['A1',result.root].sort());
 assert.equal(JSON.stringify({entities,edges}),before);
});
test('cycles terminate, invalid display routes cannot invent semantic edges',()=>{
 const cyclic=[...edges,{id:'cycle',type:'INTRODUCES',from:'A4',to:'R1'}];let i=0;
 const result=P.addBranch(entities,cyclic,positions,{},'R1',3,()=> 'occ-'+(++i));
 assert(Object.keys(result.occurrences).length<20);
 const bogus={'occ-fake':{entityId:'A1',x:20,y:20,parentId:'R3',viaEdgeId:'not-an-edge'}};
 assert(P.project(entities,edges,positions,bogus).routes.every(r=>r.edge.id!=='not-an-edge'));
});
test('layout v1 adds occurrences without changing previous positions and remaps source edge identities',()=>{
 const old=L.empty(),key=L.graphKey('source','graph');
 const positionsCopy={R1:{x:10,y:20}};
 const records={'occ-01':{entityId:'A1',x:180,y:80,parentId:'R2',viaEdgeId:'d2'}};
 const updated=L.commit(L.apply(old,[{type:'set_positions',graphKey:key,positions:positionsCopy},
   {type:'set_occurrences',graphKey:key,occurrences:records}]),0);
 assert.equal(updated.schemaVersion,1);
 assert.equal(updated.layouts[key].positions.R1.x,10);
 const copy=L.remap(updated,{sourceSpace:'source',targetSpace:'new',
   viewMap:{graph:'new-graph'},entityMap:Object.fromEntries(entities.map(n=>[n.id,'new-'+n.id])),
   sourceIds:entities.map(n=>n.id),sourceSlugs:['graph'],
   edgeMap:Object.fromEntries(edges.map(e=>[e.id,'new-'+e.id])),
   edgeEndpoints:Object.fromEntries(edges.map(e=>[e.id,{from:e.from,to:e.to}]))});
 const output=copy.document.layouts[L.graphKey('new','new-graph')];
 assert.deepEqual(output.occurrences['occ-01'],{entityId:'new-A1',x:180,y:80,parentId:'new-R2',viaEdgeId:'new-d2'});
 assert.equal(updated.layouts[key].occurrences['occ-01'].entityId,'A1');
 assert.throws(()=>L.apply(old,{type:'set_occurrences',graphKey:key,occurrences:
   {'occ-bad':{entityId:'A1',x:Infinity,y:1}}}),/LAYOUT_OCCURRENCE_INVALID/);
 assert.throws(()=>L.remap(updated,{sourceSpace:'source',targetSpace:'new',
   viewMap:{graph:'new-graph'},entityMap:{A1:'new-A1',R2:'new-R2'},sourceIds:entities.map(n=>n.id),
   sourceSlugs:['graph'],edgeMap:{d2:'new-d2'},edgeEndpoints:{d2:{from:'R1',to:'A1'}}}),/LAYOUT_OCCURRENCE_PARENT/);
});

test('WorkGraph external aliases are boundary views, never membership or extra entity',()=>{
 const members=[entities[0]];const out=P.boundaries(entities,edges,['R1']);
 assert(out.some(b=>b.edge.id==='d1'&&b.outside==='A1'&&b.direction==='out'));
 const alias={'occ-outside':{entityId:'A1',x:200,y:90,parentId:'R1',viaEdgeId:'d1'}};
 const projection=P.project(members,[],{R1:{x:10,y:20}},alias,{externalEntities:entities,externalEdges:edges});
 assert.deepEqual(projection.nodes.map(n=>n.id),['R1','occ-outside']);
 assert.deepEqual(projection.routes.map(r=>[r.edge.id,r.from,r.to]),[['d1','R1','occ-outside']]);
 assert.equal(projection.counts.get('A1'),1,'outside alias does not create an extra primary card');
 assert.deepEqual(projection.invalid,[]);
});
test('companions can repeat with original direction Context/Canon to Action',()=>{
 const objects=[{id:'CTX',kind:'context',title:'Situation'},{id:'CANON',kind:'canon',title:'Applicability'}];
 const companions=[{id:'ctx-edge',type:'CONTEXT_FOR',from:'CTX',to:'A1'},
                   {id:'canon-edge',type:'CANON_FOR',from:'CANON',to:'A1'}];
 let i=0;const snapshot=[...entities,...objects];
 const result=P.addBranch(snapshot,[...edges,...companions],positions,{},'A1',1,()=> 'occ-'+(++i),
   {duplicateRoot:false,includeCompanions:true,onlyCompanions:true});
 assert.deepEqual(Object.values(result.occurrences).map(o=>o.entityId).sort(),['CANON','CTX']);
 assert(Object.values(result.occurrences).every(o=>o.reverse===true));
 const projection=P.project(snapshot,[...edges,...companions],positions,result.occurrences);
 for(const e of companions)assert(projection.routes.some(r=>r.edge.id===e.id&&
   r.from.startsWith('occ-')&&r.to==='A1'));
 const k=L.graphKey('source','graph'),layout=L.apply(L.empty(),
   {type:'set_occurrences',graphKey:k,occurrences:result.occurrences});
 const copy=L.remap(layout,{sourceSpace:'source',targetSpace:'new',viewMap:{graph:'new-graph'},
   entityMap:Object.fromEntries(snapshot.map(n=>[n.id,'n-'+n.id])),sourceIds:snapshot.map(n=>n.id),sourceSlugs:['graph'],
   edgeMap:Object.fromEntries([...edges,...companions].map(e=>[e.id,'n-'+e.id])),
   edgeEndpoints:Object.fromEntries([...edges,...companions].map(e=>[e.id,{from:e.from,to:e.to}]))});
 assert(Object.values(copy.document.layouts[L.graphKey('new','new-graph')].occurrences)
   .every(o=>o.reverse===true&&o.parentId==='n-A1'));
});

test('invalid visual links are diagnosed, and occurrence parent cycles are refused',()=>{
 const bad={'occ-missing':{entityId:'A1',x:20,y:20,parentId:'R1',viaEdgeId:'absent'}};
 const picture=P.project(entities,edges,positions,bad);
 assert.equal(picture.invalid.length,1);
 assert.equal(picture.invalid[0].id,'occ-missing');
 const layout=L.empty(),key=L.graphKey('scope','graph');
 assert.throws(()=>L.apply(layout,{type:'set_occurrences',graphKey:key,occurrences:{
   'occ-a':{entityId:'A1',x:0,y:0,parentId:'occ-b',viaEdgeId:'d1'},
   'occ-b':{entityId:'R1',x:1,y:1,parentId:'occ-a',viaEdgeId:'d2'}
 }}),/LAYOUT_OCCURRENCE_CYCLE/);
});
test('generated Viewer embeds exact pure visual projector, without a second copy',()=>{
 const fs=require('node:fs'),path=require('node:path'),viewer=fs.readFileSync(
   path.join(__dirname,'../tools/rd-graph-viewer.user.js'),'utf8');
 const first='// BEGIN GENERATED RDG VISUAL PROJECTION\n',last='// END GENERATED RDG VISUAL PROJECTION\n';
 assert(viewer.includes(first)&&viewer.includes(last));
 assert.equal(viewer.split(first)[1].split(last)[0],fs.readFileSync(
   path.join(__dirname,'../tools/rdg-visual-projection.js'),'utf8'));
});

test('canonical Question remains outside Decision Graph projection',()=>{
 const {graph,view}=decisionFixture();
 const q={id:'Q-1',kind:'question',title:'Waiting for evidence'};
 for(const group of graph.decisionGroups)group.title=group.id;
 for(const node of graph.nodes)node.title=node.id;
 graph.objects.push(q);view.entities.push(q);
 const projection=P.decisionProject(graph,view);
 assert(!projection.nodes.some(n=>n.entityId===q.id));
 assert(!P.decisionOutline(graph,view).rows.some(n=>n.entityId===q.id));
 assert(graph.objects.some(n=>n.id===q.id),'question stays in owner data');
});
function decisionFixture(){const graph={coreModel:'rdg-decision-v1',identitySpace:'a0d9d5c0-9cb2-4e45-8e43-dbeae9b17492',id:'process',rootCauses:[{requirementId:'R0',enabled:true}],nodes:[{id:'R0',kind:'requirement'},{id:'D1',kind:'decision'},{id:'D2',kind:'decision'},{id:'SH',kind:'requirement'},{id:'NEXT',kind:'decision'}],objects:[],decisionGroups:[{id:'G1',parentId:'R0',members:[{id:'M1',decisionId:'D1'},{id:'M2',decisionId:'D2'}]},{id:'G2',parentId:'R0',members:[{id:'M3',decisionId:'D1'}]}],edges:[{id:'I1',type:'INTRODUCES',from:'D1',to:'SH'},{id:'I2',type:'INTRODUCES',from:'D2',to:'SH'},{id:'RD',type:'DRIVES',from:'SH',to:'NEXT'}]};const view={spec:{kind:'graph'},entities:graph.nodes,edges:graph.edges,decisionMemberships:graph.decisionGroups.flatMap(g=>g.members.map(m=>({id:m.id,type:'DECISION_MEMBER',from:g.parentId,to:m.decisionId,groupId:g.id}))),groupVisibility:[]};return {graph,view};}
test('Decision projector deduplicates overlapping group entry and locally expands shared continuation',()=>{const {graph,view}=decisionFixture(),before=JSON.stringify(graph),collapsed=P.decisionProject(graph,view);assert.equal(collapsed.nodes.filter(n=>n.entityId==='D1').length,1);const alias=collapsed.nodes.find(n=>n.entityId==='SH'&&n.alias);assert(alias);assert.equal(collapsed.nodes.filter(n=>n.entityId==='NEXT').length,1);view.spec.expandedOccurrenceIds=[alias.id];const expanded=P.decisionProject(graph,view);assert.equal(expanded.nodes.filter(n=>n.entityId==='NEXT').length,2);assert.equal(JSON.stringify(graph),before);assert.equal(expanded.factsCreated,false);for(const r of expanded.routes)assert([...graph.edges,...view.decisionMemberships].some(e=>e.id===r.edge.id));});

test('decision-group labels preserve all canonical memberships on a shared R→D pair',()=>{
 const {graph,view}=decisionFixture(),before=JSON.stringify(graph);
 for(const compactGraph of [true,false]){
  view.spec.compactGraph=compactGraph;
  const p=P.decisionProject(graph,view);
  const shared=p.groupLabels.filter(m=>m.from==='R0'&&m.to==='D1');
  assert.deepEqual(shared.map(m=>m.groupId).sort(),['G1','G2']);
  const routes=p.routes.filter(r=>r.edge.type==='DECISION_MEMBER'&&r.edge.from==='R0'&&r.edge.to==='D1');
  assert.deepEqual(routes.map(r=>r.edge.id).sort(),['M1','M3'],
   'both canonical membership relation IDs remain present in the projection');
  assert.equal(new Set(routes.map(r=>r.from+'|'+r.to)).size,1,
   'all members of the same endpoint pair share one visual route location, to be labeled once by Viewer');
  assert(!p.nodes.some(n=>n.entityId==='G1'||n.entityId==='G2'),
   'group captions must not be promoted into extra Graph entities');
 }
 assert.equal(JSON.stringify(graph),before,'group label placement is presentation-only');
});
test('focus layout compacts the saved process positions without writes',()=>{
 const {graph,view}=decisionFixture();
 view.spec={kind:'focus',id:'D1'};
 view.entities=graph.nodes.filter(n=>['R0','D1','SH'].includes(n.id));
 view.edges=graph.edges.filter(e=>e.from==='D1');
 view.decisionMemberships=view.decisionMemberships.filter(e=>e.to==='D1');
 const saved={positions:{R0:{x:10,y:20},D1:{x:3500,y:2800},SH:{x:9000,y:7600}}};
 const before=JSON.stringify(saved);
 const result=P.decisionProject(graph,view,saved);
 assert(result.positions.R0.x<result.positions.D1.x);
 assert(result.positions.D1.x<result.positions.SH.x);
 assert(result.positions.SH.x-result.positions.R0.x<800);
 assert.equal(JSON.stringify(saved),before);
 assert.equal(result.occurrences['occ-missing'],undefined);
});
test('Decision copy rekeys real occurrence route with independent UUIDv5 oracle and preserves positions',()=>{const crypto=require('node:crypto'),{graph,view}=decisionFixture(),p=P.decisionProject(graph,view),alias=p.nodes.find(n=>n.entityId==='SH'&&n.alias),original=p.occurrences[alias.id];original.x=-345;original.y=654;const targetSpace='f3d1f460-0004-4c94-9ed7-5e10f9439c84',key=L.graphKey(graph.identitySpace,graph.id),entityMap=Object.fromEntries(graph.nodes.map(n=>[n.id,'copy-'+n.id])),edgeMap=Object.fromEntries([...graph.edges,...view.decisionMemberships].map(e=>[e.id,'copy-'+e.id]));const result=L.remap({schemaVersion:1,revision:2,layouts:{[key]:{positions:p.positions,occurrences:p.occurrences}}},{profile:'rdg-decision-v1',sourceSpace:graph.identitySpace,targetSpace,viewMap:{process:'copy-process'},entityMap,sourceIds:graph.nodes.map(n=>n.id),sourceSlugs:['process'],edgeMap,edgeEndpoints:Object.fromEntries([...graph.edges,...view.decisionMemberships].map(e=>[e.id,{from:e.from,to:e.to}]))}).document.layouts[L.graphKey(targetSpace,'copy-process')];const route=[[edgeMap[original.viaEdgeId],false]],name=JSON.stringify([entityMap[original.parentId],route,entityMap.SH]);const raw=crypto.createHash('sha1').update(Buffer.from(targetSpace.replaceAll('-',''),'hex')).update(name).digest().subarray(0,16);raw[6]=(raw[6]&15)|80;raw[8]=(raw[8]&63)|128;const h=raw.toString('hex'),id='occ-'+[h.slice(0,8),h.slice(8,12),h.slice(12,16),h.slice(16,20),h.slice(20)].join('-');assert(result.occurrences[id]);assert.notEqual(id,alias.id);assert.deepEqual([result.occurrences[id].x,result.occurrences[id].y],[-345,654]);assert.equal(result.occurrences[id].entityId,entityMap.SH);});
test('Decision projector terminates cyclic continuation and reports stale real relation without inventing a route',()=>{const {graph,view}=decisionFixture();graph.edges.push({id:'BACK',type:'INTRODUCES',from:'NEXT',to:'SH'});view.edges=graph.edges;const first=P.decisionProject(graph,view);view.spec.expandedOccurrenceIds=Object.keys(first.occurrences);const second=P.decisionProject(graph,view,first);assert(second.nodes.length<30);const bad={'occ-stale':{entityId:'SH',x:8,y:9,parentId:'D1',viaEdgeId:'removed-edge'}};const p=P.decisionProject(graph,view,{occurrences:bad});assert(p.invalid.some(r=>r.id==='occ-stale'));assert(!p.routes.some(r=>r.edge.id==='removed-edge'));});

test('compact overview is deterministic, space-efficient, and never changes persisted layout',()=>{
 const {graph,view}=decisionFixture();
 const saved={positions:{
  R0:{x:10000,y:12500},D1:{x:12000,y:20000},D2:{x:14000,y:21000},
  SH:{x:24000,y:26000},NEXT:{x:30000,y:31000}
 }};
 const raw=JSON.stringify(saved),ordinary=P.decisionProject(graph,view,saved);
 view.spec.compactGraph=true;
 const compact=P.decisionProject(graph,view,saved);
 assert.equal(JSON.stringify(saved),raw,'read-only compact mode must not overwrite process layout');
 assert.equal(compact.compact,true);
 assert.deepEqual(compact.routes.map(r=>r.edge.id).sort(),ordinary.routes.map(r=>r.edge.id).sort());
 assert.deepEqual(compact.nodes.map(n=>n.entityId).sort(),ordinary.nodes.map(n=>n.entityId).sort());
 const coord=n=>compact.occurrences[n.id]||compact.positions[n.id];
 const locations=compact.nodes.map(coord);
 assert(locations.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));
 const keys=locations.map(p=>p.x+','+p.y);
 assert.equal(new Set(keys).size,keys.length,'cards cannot occupy the same grid slot');
 const bounds=positions=>Math.max(...positions.map(p=>p.x))-Math.min(...positions.map(p=>p.x))+
   Math.max(...positions.map(p=>p.y))-Math.min(...positions.map(p=>p.y));
 assert(bounds(locations)<3500,'overview must ignore enormous distances between stored cards');
 assert.deepEqual(P.decisionProject(graph,view,saved).positions,compact.positions);
 view.spec.compactGraph=false;
 assert.deepEqual(P.decisionProject(graph,view,saved).positions.SH,saved.positions.SH,
   'switching back restores the original positions');
});

test('WorkGraph omits orphan process repeats but keeps shared Action identities and local edges',()=>{
 const graph={coreModel:'rdg-decision-v1',identitySpace:'a0d9d5c0-9cb2-4e45-8e43-dbeae9b17492',
  id:'process',rootCauses:[{requirementId:'R1',enabled:true}],
  nodes:[
   {id:'R1',kind:'requirement'},{id:'D1',kind:'decision'},
   {id:'R2',kind:'requirement'},{id:'R3',kind:'requirement'},{id:'R5',kind:'requirement'},
   {id:'A5',kind:'action'},{id:'A6',kind:'action'},{id:'A17',kind:'action'}],
  objects:[],decisionGroups:[{id:'G1',parentId:'R1',members:[{id:'M1',decisionId:'D1'}]}],
  edges:[
   {id:'to-R2',type:'INTRODUCES',from:'D1',to:'R2'},
   {id:'to-R3',type:'INTRODUCES',from:'D1',to:'R3'},
   {id:'to-R5',type:'INTRODUCES',from:'D1',to:'R5'},
   {id:'R2-A5',type:'REQUIRES_ACTION',from:'R2',to:'A5'},
   {id:'R3-A5',type:'REQUIRES_ACTION',from:'R3',to:'A5'},
   {id:'R3-A6',type:'REQUIRES_ACTION',from:'R3',to:'A6'},
   {id:'R3-A17',type:'REQUIRES_ACTION',from:'R3',to:'A17'},
   {id:'R5-A17',type:'REQUIRES_ACTION',from:'R5',to:'A17'}]};
 const membership={id:'M1',type:'DECISION_MEMBER',from:'R1',to:'D1',groupId:'G1'};
 const members=new Set(['R1','D1','R3','A5','A6','A17']);
 const view={spec:{kind:'workGraph',id:'WG2',compactGraph:true},
  entities:graph.nodes.filter(n=>members.has(n.id)),
  edges:graph.edges.filter(e=>members.has(e.from)&&members.has(e.to)),
  decisionMemberships:[membership],groupVisibility:[]};
 const localA5Id=L.occurrenceKey(graph.identitySpace,'R3',[['R3-A5',false]],'A5');
 const layout={positions:Object.fromEntries(graph.nodes.map((n,i)=>[n.id,{x:i*800-2000,y:i*400}])),
  occurrences:{
   [localA5Id]:{entityId:'A5',parentId:'R3',viaEdgeId:'R3-A5',x:250,y:150},
   'occ-A17-from-R5':{entityId:'A17',parentId:'R5',viaEdgeId:'R5-A17',x:4000,y:-1100}}};
 const before=JSON.stringify(layout);
 const compact=P.decisionProject(graph,view,layout);
 assert.deepEqual(compact.nodes.map(n=>n.entityId).sort(),[...members].sort(),
   'WorkGraph must not import duplicate images whose other parent is outside its scope');
 assert.deepEqual(compact.routes.filter(r=>r.edge.type==='REQUIRES_ACTION')
   .map(r=>[r.from,r.to]).sort(),[['R3','A5'],['R3','A6'],['R3','A17']].sort());
 assert(compact.positions.A5.y>compact.positions.R3.y);
 assert(compact.positions.A17.y>compact.positions.R3.y);
 assert.equal(JSON.stringify(layout),before);
 view.spec.compactGraph=false;
 const manual=P.decisionProject(graph,view,layout);
 assert.deepEqual(manual.nodes.map(n=>n.entityId).sort(),[...members].sort(),
   'The old manual layout must also hide outside-scope aliases');
 // In another scope, both parents can be visible: local repeat is legitimate.
 const both=new Set(['R1','D1','R2','R3','A5']);
 view.entities=graph.nodes.filter(n=>both.has(n.id));
 view.edges=graph.edges.filter(e=>both.has(e.from)&&both.has(e.to));
 const shared=P.decisionProject(graph,view,layout);
 assert.equal(shared.nodes.filter(n=>n.entityId==='A5').length,2);
 assert(shared.routes.some(r=>r.to===localA5Id&&r.from==='R3'));
});
