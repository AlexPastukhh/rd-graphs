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
test('projection follows provenance, inherits alternatives and preserves shared targets and independent entries',()=>{
 const d=data(),before=JSON.stringify(d),a=catalog.projectGraphSet(d);
 assert.deepEqual(a.graphs.map(g=>g.slug),['root','context','actual','shared','unknown','entry2']);
 assert.equal(a.graphStates.context,'context');assert.equal(a.graphStates['local-selected'],'alternative');assert.equal(a.graphStates.shared,'selected');assert.equal(a.graphStates.entry2,'entry');assert.equal(a.graphStates.unknown,'unknown');
 const all=catalog.projectGraphSet(d,{showAlternatives:true});assert.equal(all.graphs.length,8);assert.equal(all.alternativeCount,2);assert.equal(all.edgeStates.at(-1),'alternative');assert.equal(JSON.stringify(d),before);
});
test('missing provenance and unknown links never masquerade as selected; archived links remain hidden',()=>{
 const d=data();d.relations=[{from:'root',to:'unknown',relationKind:'selected'},{from:'root',to:'potential',relationKind:'mystery'}, {from:'root',to:'actual',relationKind:'selected',introducedByDecisionId:'D',archived:true}];
 const p=catalog.projectGraphSet(d,{showAlternatives:true});assert.equal(p.graphStates.actual,'unknown');assert.equal(p.graphStates.unknown,'unknown');assert.deepEqual(p.edgeStates,['unknown','unknown','unknown']);assert.equal(p.relations.length,2);
 const undecided=catalog.projectGraphSet({...d,relations:[]});assert.equal(undecided.graphStates.root,'entry');assert(undecided.graphs.length>0);
});
test('prepared and contextual routes preserve their own meanings',()=>{
 const d=data();d.relations=[{from:'root',to:'actual',relationKind:'prepared',introducedByDecisionId:'templateD'}, {from:'actual',to:'context',relationKind:'same-requirement',requirementId:'R'}];
 const p=catalog.projectGraphSet(d);assert.equal(p.graphStates.actual,'prepared');assert.equal(p.graphStates.context,'context');assert.equal(p.alternativeCount,0);
});
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
test('working set defaults to five current/context graphs; toggle and search reveal alternatives without moving current nodes',async()=>{
 const u=simulate({useBundle:true});await settle(u);await u.openSet('example-working');assert.equal(ids(u).length,5);assert(!ids(u).includes('reference-mixed-planned-feature'));
 assert.equal(u.ids['variants-all'].textContent,'Показать альтернативы');const root='reference-mixed-active-work',c=camera(u),p=pos(node(u)(root)),key=u.host.rdgLayout.graphKey();
 u.ids['variants-all'].onclick();assert.equal(ids(u).length,10);assert.equal(pos(node(u)(root)),p);assert.equal(camera(u),c);assert.equal(u.host.rdgLayout.graphKey(),key);
 assert.equal(node(u)('reference-mixed-planned-feature').getAttribute('data-branch-state'),'alternative');assert.match(node(u)('reference-mixed-planned-feature').textContent,/не выбрано/);
 u.ids['variants-all'].onclick();assert.equal(ids(u).length,5);
 u.ids.search.value='reference-mixed-planned-feature';u.ids.search.oninput({target:u.ids.search});assert.equal(ids(u).length,10);
});
test('returning from a graph retains set filter, camera, search and shared programmatic positions',async()=>{
 const u=simulate({useBundle:true});await settle(u);await u.openSet('example-working');u.ids['variants-all'].onclick();
 const a=u.host.rdgLayout,key=a.graphKey(),slug='reference-mixed-planned-feature';a.apply({type:'set_positions',positions:{[slug]:{x:1020,y:123}}});
 u.ids.search.value=slug;u.ids.search.oninput({target:u.ids.search});const c=camera(u);node(u)(slug).listeners.click({stopPropagation(){}});await settle(u);await u.ids.back.onclick();await settle(u);
 assert.equal(ids(u).length,10);assert.equal(u.ids.search.value,slug);assert.equal(camera(u),c);assert.equal(pos(node(u)(slug)),'translate(1020 123)');assert.equal(a.graphKey(),key);
 u.ids['variants-all'].onclick();u.ids['variants-all'].onclick();assert.equal(pos(node(u)(slug)),'translate(1020 123)');
 u.ids['layout-reset'].onclick();assert.notEqual(pos(node(u)(slug)),'translate(1020 123)');
});
test('ready set opens prepared alternatives and labels them as templates, not actual choices',async()=>{
 const u=simulate({useBundle:true});await settle(u);await u.openSet('example-prepared');assert.equal(ids(u).length,6);assert.equal(u.ids['variants-all'].textContent,'Скрыть альтернативы');
 assert(nodes(u).filter(n=>n.getAttribute('data-branch-state')==='alternative').every(n=>n.textContent.includes('Вариант заготовки')));
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

test('an untyped catalog link stays visibly unconfirmed instead of being named a selected child',async()=>{
 const set={id:'other-set',kind:'graph-set',folder:'custom',title:'Other',members:['a','b'],entryGraphSlugs:['a'],presentation:{usage:'working'}};
 const entries=['a','b'].map(slug=>({slug,kind:'graph',setId:'other-set',folder:'custom',group:'custom',file:'custom/'+slug+'/graph.json',title:slug}));
 const files={'index.json':JSON.stringify({schemaVersion:1,folders:[{id:'custom',folder:'',title:'Custom'}],graphs:entries,graphSets:[set],relations:[{from:'a',to:'b',requirementId:'R'}]})};
 for(const g of entries)files[g.file]=JSON.stringify({schemaVersion:1,id:g.slug,rootRequirementId:'R',revision:1,nodes:[{id:'R',kind:'requirement',title:g.slug}],edges:[]});
 const u=simulate({files});await settle(u);await u.openSet('other-set');
 assert.equal(node(u)('b').getAttribute('data-branch-state'),'unknown');
 const edge=labels(u)[0];assert.equal(edge.getAttribute('data-branch-state'),'unknown');assert.match(edge.getAttribute('aria-label'),/Путь не подтверждён/);
 edge.listeners.click({stopPropagation(){}});assert.match(u.info(),/не подтверждено/);assert(!u.info().includes('Переход по выбранному разбиению'));
});

test('alternative routes to an already current graph keep their toggle even when no extra nodes exist',async()=>{
 const d={set:{id:'s',entryGraphSlugs:['a']},graphs:[{slug:'a'},{slug:'b'}],relations:[{from:'a',to:'b',relationKind:'selected',introducedByDecisionId:'D',requirementId:'R'},{from:'a',to:'b',relationKind:'potential',originatingOptionId:'O',requirementId:'R'}]};
 const projected=catalog.projectGraphSet(d);assert.equal(projected.alternativeCount,0);assert.equal(projected.alternativeRelationCount,1);assert.equal(projected.relations.length,1);
 assert.equal(catalog.projectGraphSet(d,{showAlternatives:true}).relations.length,2);assert.equal(projected.graphStates.b,'selected');
 const graphs=d.graphs.map(g=>({...g,setId:'s',file:'custom/'+g.slug+'/graph.json',folder:'custom',title:g.slug}));
 const files={'index.json':JSON.stringify({schemaVersion:1,graphs,folders:[{id:'custom',folder:'',title:'Custom'}],graphSets:[{...d.set,kind:'graph-set',folder:'custom',title:'S',members:['a','b'],presentation:{usage:'working'}}],relations:d.relations})};
 for(const g of graphs)files[g.file]=JSON.stringify({schemaVersion:1,id:g.slug,revision:1,rootRequirementId:'R',nodes:[{id:'R',kind:'requirement',title:g.slug}],edges:[]});
 const u=simulate({files});await settle(u);await u.openSet('s');assert.equal(u.ids['variants-all'].hidden,false);assert.equal(labels(u).length,1);
 u.ids['variants-all'].onclick();assert.equal(ids(u).length,2);assert.equal(labels(u).length,2);assert.equal(node(u)('b').getAttribute('data-branch-state'),'selected');
});
