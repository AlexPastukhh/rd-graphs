'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const core=require('../tools/rdg-layout-core.js');
const spec={sourceSpace:'source',targetSpace:'copy',viewMap:{old:'new','full-WG':'full-copy-WG'},
 entityMap:{R:'copy-R',A:'copy-A'},sourceIds:['R','A','OUT'],sourceSlugs:['old']};
function document(){return {schemaVersion:1,revision:8,layouts:{
 [core.graphKey('source','old','R')]:{zoom:1.5,positions:{R:{x:10,y:20,note:'manual'},A:{x:33,y:44},OUT:{x:55,y:66},'__canon__A':{x:77,y:88}}},
 [core.graphKey('source','full-WG','R')]:{positions:{'old::R':{x:12,y:23},'__canon__old::A':{x:34,y:45}}},
 [core.graphKey('source','old','OUT')]:{positions:{OUT:{x:8,y:9}}},
 [core.graphKey('another','foreign','R')]:{positions:{R:{x:111,y:222}}}}};}
test('remaps addresses, local/full/virtual IDs and preserves manual coordinates',()=>{
 const source=document(),before=JSON.stringify(source),result=core.remap(source,spec),layouts=result.document.layouts;
 assert.deepEqual(layouts[core.graphKey('copy','new','copy-R')].positions['copy-R'],{x:10,y:20,note:'manual'});
 assert.deepEqual(layouts[core.graphKey('copy','new','copy-R')].positions['__canon__copy-A'],{x:77,y:88});
 assert.deepEqual(layouts[core.graphKey('copy','full-copy-WG','copy-R')].positions['new::R'],undefined);
 assert.deepEqual(layouts[core.graphKey('copy','full-copy-WG','copy-R')].positions['new::copy-R'],{x:12,y:23});
 assert.equal(layouts[core.graphKey('copy','new','copy-R')].zoom,1.5);
 assert.equal(JSON.stringify(source),before);assert.equal(result.report.skippedKeys.length,2);
 assert.equal(result.report.skippedPositionIds.length,1);assert.equal(Object.keys(layouts).length,2);
});
test('unknown view/position is explicit failure rather than silent loss',()=>{
 const source=document();source.layouts[core.graphKey('source','unknown','R')]={positions:{R:{x:1,y:2}}};
 assert.throws(()=>core.remap(source,spec),/LAYOUT_VIEW_UNMAPPED/);
 const wrong=document();wrong.layouts[core.graphKey('source','old','R')].positions.mystery={x:1,y:2};
 assert.throws(()=>core.remap(wrong,spec),/LAYOUT_POSITION_UNMAPPED/);
});
test('same shared codec handles ordinary CAS layout commands',()=>{
 const key=core.graphKey('copy','new','copy-R');const before=core.empty();
 const after=core.commit(core.apply(before,{type:'set_positions',graphKey:key,positions:{'copy-R':{x:1,y:2}}}),0);
 assert.equal(after.revision,1);assert.deepEqual(after.layouts[key].positions['copy-R'],{x:1,y:2});
 const metadata={...after,layouts:{[key]:{...after.layouts[key],zoom:1.75}}};
 assert.equal(core.apply(metadata,{type:'set_positions',graphKey:key,positions:{'copy-R':{x:8,y:9}}}).layouts[key].zoom,1.75);
 assert.throws(()=>core.commit(after,0),/Конфликт/);assert.equal(before.revision,0);
});


test('shared layout codec rejects invalid coordinates and isolates graph layouts',()=>{
 const initial=core.empty(),a=core.graphKey('process','full'),b=core.graphKey('process','full-other');
 const positioned=core.apply(initial,{type:'set_positions',graphKey:a,positions:{R1:{x:-340,y:50}}});
 assert.equal(Object.keys(initial.layouts).length,0,'commands must not mutate input');
 assert.equal(positioned.revision,0);
 const saved=core.commit(positioned,0);
 assert.equal(saved.revision,1);
 assert.throws(()=>core.commit(saved,0),/ревизии/);
 for(const value of [Infinity,NaN,1000001])
   assert.throws(()=>core.apply(initial,{type:'set_positions',graphKey:a,positions:{R1:{x:value,y:0}}}),/координаты/);
 assert.throws(()=>core.apply(initial,JSON.parse('{"type":"set_positions","graphKey":"__proto__","positions":{}}')));
 const both=core.apply(saved,{type:'set_positions',graphKey:b,positions:{R2:{x:1,y:2}}});
 assert.deepEqual(core.apply(both,{type:'clear_layout',graphKey:a}).layouts,{[b]:{positions:{R2:{x:1,y:2}}}});
});
test('generated Viewer includes the exact shared layout codec',()=>{
 const fs=require('node:fs'),path=require('node:path');
 const viewer=fs.readFileSync(path.join(__dirname,'../tools/rd-graph-viewer.user.js'),'utf8');
 const start='// BEGIN GENERATED RDG LAYOUT CORE\n',end='// END GENERATED RDG LAYOUT CORE\n';
 assert(viewer.includes(start)&&viewer.includes(end));
 const embedded=viewer.split(start)[1].split(end)[0];
 assert.equal(embedded,fs.readFileSync(path.join(__dirname,'../tools/rdg-layout-core.js'),'utf8'));
});
