const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process');
const core=require('../tools/rdg-layout-core.js');
const {simulate,code}=require('./viewer-test-helper.cjs');
const plain=x=>JSON.parse(JSON.stringify(x));
const list=ui=>ui.root.querySelectorAll('.node');
const node=(ui,id)=>list(ui).find(n=>n.getAttribute('data-id')===id);
const click=(ui,id)=>{const n=node(ui,id);assert(n,id);n.listeners.click({stopPropagation(){}});};
const xy=(ui,id)=>node(ui,id).getAttribute('transform');
const fixture=()=>({schemaVersion:1,id:'layout-fixture',revision:1,identitySpace:'isolated-layout-test',rootRequirementId:'R',view:{requirementDepth:1},
 nodes:[{id:'R',kind:'requirement',title:'Root'},{id:'O',kind:'option',title:'Method'},...['A','B','C','D','E','F','GRAND'].map(id=>({id,kind:'requirement',title:id})),{id:'CHILD-O',kind:'option',title:'Hidden child method'}],
 edges:[{id:'o',type:'OPTION_FOR',from:'R',to:'O'},...['A','B','C','D','E','F'].map(id=>({id:'e'+id,type:'OUTCOME_OF',from:'O',to:id})),{id:'co',type:'OPTION_FOR',from:'A',to:'CHILD-O'},{id:'grand',type:'OUTCOME_OF',from:'CHILD-O',to:'GRAND'}],
 collections:[{id:'one',title:'First list',anchor:'O',memberRefs:['A','B','C']},{id:'two',title:'Second list',anchor:'O',memberRefs:['D','E','F']}]});
test('shared layout commands are immutable, preserve other graphs and guard revisions/coordinates',()=>{
 const initial=core.empty(),key=core.graphKey('scope','graph');
 const draft=core.apply(initial,{type:'set_positions',graphKey:key,positions:{R:{x:-340,y:50}}});
 assert.equal(Object.keys(initial.layouts).length,0);assert.equal(draft.revision,0);
 const saved=core.commit(draft,0);assert.equal(saved.revision,1);assert.equal(saved.layouts[key].positions.R.x,-340);
 assert.throws(()=>core.commit(saved,0),/ревизии/);
 for(const value of [Infinity,NaN,1000001])assert.throws(()=>core.apply(initial,{type:'set_positions',graphKey:key,positions:{R:{x:value,y:0}}}),/координаты/);
 assert.throws(()=>core.apply(initial,JSON.parse('{"type":"set_positions","graphKey":"__proto__","positions":{}}')));
 const other=core.graphKey('scope','other');
 const two=core.apply(saved,{type:'set_positions',graphKey:other,positions:{Q:{x:1,y:2}}});
 assert.deepEqual(core.apply(two,{type:'clear_layout',graphKey:key}).layouts,{[other]:{positions:{Q:{x:1,y:2}}}});
});
test('browser embeds the exact same command core that the CLI imports',()=>{
 const actual=code.split('// BEGIN GENERATED RDG LAYOUT CORE\n')[1].split('// END GENERATED RDG LAYOUT CORE\n')[0];
 assert.equal(actual,fs.readFileSync(path.join(__dirname,'../tools/rdg-layout-core.js'),'utf8'));
});
test('opening multiple lists removes headers, reveals only R, preserves camera and unaffected positions',async()=>{
 const g=fixture(),before=JSON.stringify(g),ui=simulate();await ui.loadFile(g);
 const camera=()=>ui.root.getElementById('scene').getAttribute('transform');
 const originalCamera=camera(),r=xy(ui,'R'),o=xy(ui,'O');
 click(ui,'__collection__one');assert(!node(ui,'__collection__one'));
 for(const id of ['A','B','C'])assert(node(ui,id));
 for(const id of ['CHILD-O','GRAND'])assert(!node(ui,id),'descendant leaked: '+id);
 assert.equal(camera(),originalCamera);assert.equal(xy(ui,'R'),r);assert.equal(xy(ui,'O'),o);
 click(ui,'__collection__two');for(const id of ['D','E','F'])assert(node(ui,id));
 assert(!node(ui,'__collection__two'));assert.equal(ui.ids['collections-collapse'].disabled,false);
 ui.ids['collections-collapse'].onclick();
 for(const id of ['A','B','C','D','E','F','CHILD-O','GRAND'])assert(!node(ui,id));
 assert(node(ui,'__collection__one')&&node(ui,'__collection__two'));
 assert.equal(camera(),originalCamera);assert.equal(xy(ui,'R'),r);assert.equal(ui.ids['collections-collapse'].disabled,true);
 assert.equal(JSON.stringify(g),before);
});
test('two-R lists are inline; groups reject non-R members without partial loading',async()=>{
 const g=fixture();g.collections=[{id:'small',title:'Two R',anchor:'O',memberRefs:['A','B']}];
 const ui=simulate();await ui.loadFile(g);assert(node(ui,'A')&&node(ui,'B'));assert(!node(ui,'__collection__small'));assert(!node(ui,'CHILD-O'));
 const originalKey=ui.host.rdgLayout.graphKey(),invalid=fixture();invalid.id='invalid-source';invalid.collections[0].memberRefs=['CHILD-O'];await ui.loadFile(invalid);assert.match(ui.text(),/должна содержать только R/);assert.equal(ui.host.rdgLayout.graphKey(),originalKey,'failed validation must preserve previous source graph');
});
test('prepared leaves open their own graphs; contextual work starts a separate one-level graph',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();await ui.openCard('reference-prepared-planning-tree');
 for(const id of ['RF-1','RF-2','RS-1','RS-2'])assert(node(ui,id)&&node(ui,id).classList.contains('drill'));
 assert(!node(ui,'RF-1-O1')&&!node(ui,'RF-DEEP')&&!node(ui,'__collection__FEATURE-POTENTIAL'));
 click(ui,'RF-2');await ui.flush();assert(node(ui,'RF-2-O1')&&node(ui,'RF-2-O2'));
 await ui.openCard('reference-mixed-active-work');assert(node(ui,'R-COMP'));assert(!node(ui,'D-A')&&!node(ui,'R-ACT-1'));
 click(ui,'R-COMP');await ui.flush();assert(node(ui,'R-COMP')&&node(ui,'D-A')&&node(ui,'R-ACT-1'));assert(!node(ui,'O-ACT-1'));
 click(ui,'D-A');assert.match(ui.info(),/Полный исторический снимок/);assert.match(ui.info(),/"version": "3"/);
 click(ui,'R-ACT-1');await ui.flush();assert(node(ui,'O-ACT-1')&&node(ui,'O-ACT-2'));
});
function memoryHandle(initial){let content=JSON.stringify(initial);return {name:'layouts.json',getFile:async()=>({text:async()=>content}),
 createWritable:async()=>{let pending='';return {write:async text=>{pending=text},close:async()=>{content=pending},abort:async()=>{}}},
 read:()=>JSON.parse(content),replace:doc=>{content=JSON.stringify(doc)}};}
test('UI uses shared commands, saves one file, restores positions and refuses external overwrite',async()=>{
 const ui=simulate();await ui.loadFile(fixture());const api=ui.host.rdgLayout,handle=memoryHandle(core.empty());
 await api.attachFile(handle);
 api.apply({type:'set_positions',positions:{R:{x:-123,y:88},O:{x:500,y:73}}});
 assert.equal(xy(ui,'R'),'translate(-123 88)');assert.equal(handle.read().revision,0,'preview must not save itself');
 const saved=await api.save();assert.equal(saved.revision,1);assert.equal(handle.read().revision,1);
 const ui2=simulate();ui2.host.rdgLayout.load(saved);await ui2.loadFile(fixture());assert.equal(xy(ui2,'R'),'translate(-123 88)');
 const external=core.commit(core.apply(handle.read(),{type:'set_positions',graphKey:api.graphKey(),positions:{R:{x:700,y:200}}}),1);handle.replace(external);
 api.apply({type:'set_positions',positions:{R:{x:42,y:21}}});
 await assert.rejects(api.save(),/изменён извне/);assert.equal(handle.read().layouts[api.graphKey()].positions.R.x,700);
 ui.ids['layout-discard'].onclick();await api.attachFile(handle);assert.equal(xy(ui,'R'),'translate(700 200)');
});
test('pointer movement at actual view scale changes node data without panning or opening its child',async()=>{
 const ui=simulate();await ui.loadFile(fixture());const target=node(ui,'R'),camera=ui.root.getElementById('scene').getAttribute('transform');
 const before=target.getAttribute('transform').match(/[-\d.]+/g).map(Number),scale=Number(camera.match(/scale\(([^)]+)\)/)[1]);
 ui.ids.canvas.listeners.pointerdown({button:0,target,pointerId:2,clientX:100,clientY:100});
 ui.ids.canvas.listeners.pointermove({pointerId:2,clientX:160,clientY:130});
 ui.ids.canvas.listeners.pointerup({pointerId:2});
 const p=ui.host.rdgLayout.getDocument().layouts[ui.host.rdgLayout.graphKey()].positions.R;
 assert(Math.abs(p.x-before[0]-60/scale)<.011);assert(Math.abs(p.y-before[1]-30/scale)<.011);
 assert.equal(ui.root.getElementById('scene').getAttribute('transform'),camera);
 assert.equal(ui.ids['inspector-toggle'].getAttribute('aria-expanded'),'false');
});
test('CLI commits shared format with read-back and rejects stale revisions and unknown nodes',()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-layout-')),file=path.join(temp,'layouts.json'),commands=path.join(temp,'commands.json');
 try{
  fs.writeFileSync(file,JSON.stringify(core.empty()));
  const key=core.graphKey('rdg-example-prepared-v7','reference-prepared-planning-tree');
  fs.writeFileSync(commands,JSON.stringify({type:'set_positions',graphKey:key,positions:{'R-PLAN':{x:-200,y:90}}}));
  const run=rev=>cp.spawnSync(process.execPath,[path.join(__dirname,'../tools/rdg-layout-cli.cjs'),'--file',file,'--expect-revision',String(rev),'--commands-file',commands],{encoding:'utf8'});
  let r=run(0);assert.equal(r.status,0,r.stderr);const saved=fs.readFileSync(file,'utf8');assert.equal(JSON.parse(saved).revision,1);
  r=run(0);assert.notEqual(r.status,0);assert.equal(fs.readFileSync(file,'utf8'),saved);
  fs.writeFileSync(commands,JSON.stringify({type:'set_positions',graphKey:key,positions:{'UNKNOWN':{x:0,y:0}}}));r=run(1);assert.notEqual(r.status,0);assert.match(r.stderr,/Неизвестный узел/);assert.equal(fs.readFileSync(file,'utf8'),saved);
 }finally{fs.rmSync(temp,{recursive:true,force:true});}
});

test('an older browser cache cannot replace a newer layout document delivered in the bundle',async()=>{
 const ui=simulate({useBundle:true});
 const bundled=plain(ui.context.RDG_EMBEDDED_GRAPHS.layouts),old=core.empty();
 ui.storage.set('rdg-layout-document:file:///C:/Users/alexa/Repos/rd-graphs/graphs/',JSON.stringify(old));
 await ui.flush();assert.equal(ui.host.rdgLayout.getDocument().revision,bundled.revision);
 assert.deepEqual(plain(ui.host.rdgLayout.getDocument()),bundled);
});
test('a file changed while the browser buffers a write is aborted before close',async()=>{
 const ui=simulate();await ui.loadFile(fixture());
 const api=ui.host.rdgLayout,handle=memoryHandle(core.empty());await api.attachFile(handle);
 let closed=false,aborted=false;
 handle.createWritable=async()=>({write:async()=>handle.replace(core.commit(core.empty(),0)),close:async()=>{closed=true},abort:async()=>{aborted=true}});
 api.apply({type:'set_positions',positions:{R:{x:9,y:8}}});
 await assert.rejects(api.save(),/изменён во время записи/);assert(aborted);assert(!closed);assert.equal(handle.read().revision,1);
});

test('set map renders derived R as an unselected refinement, distinct from a D',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();await ui.openSet('example-working');
 const all=[];const walk=n=>{all.push(n);for(const c of n.children||[])walk(c)};walk(ui.ids.canvas);
 const edge=all.find(n=>n.classList?.contains('edge')&&n.getAttribute('data-requirement')==='R-COMP');
 assert(edge&&edge.classList.contains('g-scope'));assert.equal(edge.getAttribute('data-relation-kind'),'derived');
 const label=all.find(n=>n.classList?.contains('edge-label')&&n.getAttribute('data-requirement')==='R-COMP');assert.match(label.textContent,/Уточнение R/);
 label.listeners.click({stopPropagation(){}});assert.match(ui.info(),/Без выбранного D/);
});
