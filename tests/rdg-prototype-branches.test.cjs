'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ROOT=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(ROOT,'tests/visual/rdg-ui-prototype.html'),'utf8');
const core=require(path.join(ROOT,'tools/rdg-visual-projection.js'));
const block=html.split('/* RDG_PROTOTYPE_BRANCH_PROJECTION_BEGIN */')[1]?.split('/* RDG_PROTOTYPE_BRANCH_PROJECTION_END */')[0];
assert(block,'prototype branch projector must be present');
const context=vm.createContext({RDGVisualProjection:core});vm.runInContext(block,context);const {build}=context.RDGPrototypeBranches;
const node=(id,kind)=>({id,kind,title:id});
const entities=[node('R0','requirement'),node('R1','requirement'),node('D1','decision'),node('D2','decision'),node('R2','requirement'),node('D3','decision'),node('A1','action')];
const edge=(id,from,to,type)=>({id,from,to,type});
const edges=[edge('e0','R0','D1','DECISION_MEMBER'),edge('e1','R1','D1','DECISION_MEMBER'),edge('e2','R0','D2','DECISION_MEMBER'),edge('e3','D1','R2','INTRODUCES'),edge('e4','D2','R2','INTRODUCES'),edge('e5','R2','D3','DECISION_MEMBER'),edge('e6','D3','A1','REQUIRES_ACTION')];
const positions={R0:{x:0,y:0},R1:{x:0,y:300},D1:{x:300,y:0},D2:{x:300,y:300},R2:{x:600,y:0},D3:{x:900,y:0},A1:{x:1200,y:0}};
const ref=(drawing,id,parent)=>drawing.points.find(p=>p.root&&p.entityId===id&&drawing.records[p.id].parentId===parent);
function checkRoutes(drawing,realEdges=edges){
 assert.equal(drawing.invalid.length,0);
 const byId=new Map(drawing.points.map(p=>[p.id,p]));
 for(const route of drawing.routes){assert(realEdges.some(e=>e.id===route.edge.id));assert.equal(byId.get(route.from).entityId,route.edge.from);assert.equal(byId.get(route.to).entityId,route.edge.to);}
}
test('shared R and D create local collapsed entrances, without copying semantic objects',()=>{
 const before=JSON.stringify({entities,edges}),d=build(entities,edges,positions);
 assert(ref(d,'D1','R1'));assert(ref(d,'R2','D2'));assert.equal(d.points.filter(p=>p.alias).length,2);
 for(const p of d.points)assert.equal(p.node,entities.find(n=>n.id===p.entityId));
 const entrance=ref(d,'D1','R1');assert(d.routes.some(r=>r.edge.id==='e1'&&r.to===entrance.id));assert(!d.routes.some(r=>r.edge.id==='e1'&&r.to==='D1'));assert(d.routes.some(r=>r.edge.id==='e0'&&r.to==='D1'));
 assert.equal(JSON.stringify({entities,edges}),before);checkRoutes(d);
});
test('multiple group memberships from one Requirement are one entrance',()=>{
 const es=[edge('g1','R0','D1','DECISION_MEMBER'),edge('g2','R0','D1','DECISION_MEMBER')],d=build(entities,es,positions);
 assert.equal(d.points.filter(p=>p.alias).length,0);assert.equal(d.routes.length,2);checkRoutes(d,es);
});
test('expanded entrance repeats all downstream kinds and deeper paths using original identity',()=>{
 const extra=[node('R3','requirement'),node('D4','decision'),node('R4','requirement')],ns=[...entities,...extra],es=[...edges,edge('e7','D3','R3','INTRODUCES'),edge('e8','R3','D4','DECISION_MEMBER'),edge('e9','D4','R4','INTRODUCES')],xy={...positions,R3:{x:1500,y:0},D4:{x:1800,y:0},R4:{x:2100,y:0}};
 const base=build(ns,es,xy),root=ref(base,'D1','R1'),d=build(ns,es,xy,{expanded:[root.id]});
 for(const id of ['R2','D3','A1','R3','D4','R4']){const p=d.points.find(p=>p.alias&&!p.root&&p.entityId===id);assert(p,id);assert.equal(p.node,ns.find(n=>n.id===id));}
 assert(d.points.find(p=>p.id===root.id).expanded);checkRoutes(d,es);
});
test('cycles terminate at an explicit reference rather than recursively expanding',()=>{
 const es=[...edges,edge('cycle','D3','R2','INTRODUCES')],base=build(entities,es,positions),root=ref(base,'D1','R1'),d=build(entities,es,positions,{expanded:[root.id]});
 assert(d.points.some(p=>p.cycle&&p.entityId==='R2'));assert(d.points.length<20);checkRoutes(d,es);
});
test('removing one origin retains the same shared Requirement and its surviving route',()=>{
 const es=edges.filter(e=>e.id!=='e3'),d=build(entities,es,positions);
 assert.equal(d.points.find(p=>p.id==='R2').node,entities.find(n=>n.id==='R2'));assert(!ref(d,'R2','D2'));assert(d.routes.some(r=>r.edge.id==='e4'&&r.to==='R2'));assert(d.routes.some(r=>r.edge.id==='e5'));checkRoutes(d,es);
});
test('dragging entities does not change primary entrance or path identity',()=>{
 const base=build(entities,edges,positions),moved={...positions,R0:{x:800,y:900},R1:{x:290,y:0}},d=build(entities,edges,moved,{primaryPositions:positions});
 assert.deepEqual([...d.primary],[...base.primary]);assert.deepEqual(Object.keys(d.records),Object.keys(base.records));
});
test('saved occurrence coordinates restore only when entity and source relation still match',()=>{
 const base=build(entities,edges,positions),root=ref(base,'R2','D2'),record=base.records[root.id],saved={[root.id]:{...record,x:-350,y:460}};
 const restored=build(entities,edges,positions,{saved});assert.equal(ref(restored,'R2','D2').x,-350);assert.equal(restored.points.find(p=>p.id==='R2').x,600);
 for(const bad of [{entityId:'D1'},{parentId:'D1'},{viaEdgeId:'other'}]){const d=build(entities,edges,positions,{saved:{[root.id]:{...saved[root.id],...bad}}});assert.notEqual(ref(d,'R2','D2').x,-350);}
});
test('explicit bounded expansion keeps canonical entities and only real routes',()=>{
 const base=build(entities,edges,positions),root=ref(base,'D1','R1'),d=build(entities,edges,positions,{expanded:[root.id],maxOccurrences:3});
 assert.equal(Object.keys(d.records).length,3);assert.equal(d.limited,true);assert.equal(d.points.filter(p=>!p.alias).length,entities.length);assert(d.points.find(p=>p.id===root.id).limited);checkRoutes(d);
});
test('occurrences share edited objects immediately without another projection or entity',()=>{
 const ns=entities.map(n=>({...n})),base=build(ns,edges,positions),root=ref(base,'D1','R1'),d=build(ns,edges,positions,{expanded:[root.id]});
 ns.find(n=>n.id==='R2').title='Изменённый общий результат';
 for(const p of d.points.filter(p=>p.entityId==='R2'))assert.equal(p.node.title,'Изменённый общий результат');
 assert.equal(ns.filter(n=>n.id==='R2').length,1);
});
