const {test}=require('node:test'),assert=require('node:assert/strict');
const catalog=require('../tools/rdg-catalog.js'),geometry=require('../tools/rdg-view-geometry.js');
const {simulate}=require('./viewer-test-helper.cjs');
const plain=x=>JSON.parse(JSON.stringify(x));
const fixture=()=>({schemaVersion:1,id:'camera',identitySpace:'camera',revision:1,rootRequirementId:'R',nodes:[{id:'R',kind:'requirement',title:'Goal'},{id:'D',kind:'decision',title:'Answer'},{id:'C',kind:'requirement',title:'Child'}],edges:[{id:'drive',from:'R',to:'D',type:'DRIVES'},{id:'intro',from:'D',to:'C',type:'INTRODUCES',parent:'R'}]});
const walk=(n,p)=>{const out=[];function visit(x){if(p(x))out.push(x);for(const c of x.children||[])visit(c)}visit(n);return out};
const labels=u=>walk(u.ids.canvas,n=>n.classList?.contains('edge-label'));
const nodes=u=>u.root.querySelectorAll('.node');
const camera=u=>u.root.getElementById('scene').getAttribute('transform');
const node=u=>id=>nodes(u).find(n=>n.getAttribute('data-id')===id);
const pos=n=>n.getAttribute('transform');
const ids=u=>nodes(u).map(n=>n.getAttribute('data-id'));
const settle=async u=>{for(let i=0;i<8;i++)await u.flush()};
function data(){
 const names=['root','context','actual','potential','local-selected','shared','unknown','entry2'];
 const relation=(from,to,relationKind,fields={})=>({from,to,relationKind,requirementId:to,...fields});
 return {set:{id:'arbitrary',members:names,entryGraphSlugs:['root','entry2']},graphs:names.map(slug=>({slug})),external:[],
  relations:[relation('root','context','derived',{derivationEdgeId:'derive'}),
   relation('context','actual','selected',{introducedByDecisionId:'D'}),
   relation('actual','context','same-requirement'),
   relation('root','potential','potential',{originatingOptionId:'O'}),
   relation('potential','local-selected','selected',{introducedByDecisionId:'localD'}),
   relation('actual','shared','selected',{introducedByDecisionId:'D'}),
   relation('potential','shared','selected',{introducedByDecisionId:'localD'})]};
}
test('wheel modes normalize pixels, lines, pages and touchpad axes without changing scale while panning',()=>{
 const v={x:40,y:80,scale:1.2},point={x:200,y:140},size={width:800,height:500};
 assert.deepEqual(geometry.wheelView(v,{deltaY:20},point,size),{x:40,y:60,scale:1.2});
 assert.deepEqual(geometry.wheelView(v,{deltaY:20,shiftKey:true},point,size),{x:20,y:80,scale:1.2});
 assert.equal(geometry.wheelView(v,{deltaY:20,deltaX:12,shiftKey:true},point,size).x,28);
 assert.deepEqual(geometry.wheelView(v,{deltaY:2,deltaX:1,deltaMode:1},point,size),{x:24,y:48,scale:1.2});
 assert.deepEqual(geometry.wheelView(v,{deltaY:1,deltaX:1,deltaMode:2},point,size),{x:-760,y:-420,scale:1.2});
 const z=geometry.wheelView(v,{deltaY:-100,ctrlKey:true,shiftKey:true},point,size);assert(z.scale>v.scale);
 assert(Math.abs((point.x-z.x)/z.scale-(point.x-v.x)/v.scale)<1e-9);assert(Math.abs((point.y-z.y)/z.scale-(point.y-v.y)/v.scale)<1e-9);
 assert.equal(geometry.wheelView({...v,scale:3},{deltaY:-1e8,ctrlKey:true},point,size).scale,3);
 assert.equal(geometry.wheelView({...v,scale:.07},{deltaY:1e8,ctrlKey:true},point,size).scale,.07);
});
test('camera events on the real Viewer leave node positions, layout commands and dirty status unchanged',async()=>{
 const u=simulate();await u.loadFile(fixture());const before=pos(node(u)('R')),doc=plain(u.host.rdgLayout.getDocument()),dirty=u.host.rdgLayout.status().dirty,c=camera(u);
 u.ids.canvas.listeners.wheel({preventDefault(){},clientX:100,clientY:150,deltaY:60});assert.notEqual(camera(u),c);
 u.ids.canvas.listeners.wheel({preventDefault(){},clientX:100,clientY:150,deltaY:60,shiftKey:true});
 u.ids.canvas.listeners.wheel({preventDefault(){},clientX:100,clientY:150,deltaY:-60,ctrlKey:true});
 assert.equal(pos(node(u)('R')),before);assert.deepEqual(plain(u.host.rdgLayout.getDocument()),doc);assert.equal(u.host.rdgLayout.status().dirty,dirty);
});
test('target labels stay near each target for left, right, vertical, return and multiple incoming routes',async()=>{
 const u=simulate();await u.loadFile(fixture());
 for(const coordinates of [{R:{x:0,y:0},D:{x:600,y:0},C:{x:600,y:300}},{R:{x:800,y:0},D:{x:300,y:0},C:{x:300,y:-300}}]){
  u.host.rdgLayout.apply({type:'set_positions',positions:coordinates});
  for(const l of labels(u)){const id=l.getAttribute('data-label-target'),p=coordinates[id],nums=pos(l).match(/[-\d.]+/g).map(Number);
   assert(Math.hypot(nums[0]-(p.x+111),nums[1]-(p.y+36))<320,id+' label too far from target');
  }
 }
 const target={x:800,y:200,w:222,h:72},source={x:0,y:0,w:222,h:72},placed=[];
 for(let i=0;i<8;i++){const b=geometry.placeTargetLabel({target,endpoint:{x:800,y:210+i*6},width:135,height:24,nodeBoxes:[target,source],labels:placed});assert(Math.hypot(b.x-target.x,b.y-target.y)<350);placed.push(b)}
});
test('view geometry embedded in the userscript is byte-identical to the shared module',()=>{
 const fs=require('node:fs'),path=require('node:path'),s=require('./viewer-test-helper.cjs').code;
 assert.equal(s.split('// BEGIN GENERATED RDG VIEW GEOMETRY\n')[1].split('// END GENERATED RDG VIEW GEOMETRY\n')[0],fs.readFileSync(path.join(__dirname,'../tools/rdg-view-geometry.js'),'utf8'));
});

