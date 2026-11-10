const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process');
const core=require('../tools/rdg-layout-core.js');
const {simulate}=require('./viewer-test-helper.cjs');
const node=(u,id)=>u.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')===id);
const ids=u=>u.root.querySelectorAll('.node').map(n=>n.getAttribute('data-id'));
const xy=(u,id)=>node(u,id)?.getAttribute('transform');
const camera=u=>u.root.getElementById('scene').getAttribute('transform');
const click=(u,id)=>{assert(node(u,id),'not visible '+id);node(u,id).listeners.click({stopPropagation(){}});};
const plain=x=>JSON.parse(JSON.stringify(x));
const fixture=(id='fix-fixture')=>({schemaVersion:1,id,revision:1,identitySpace:'layout-fix-test',rootRequirementId:'R',
 nodes:[{id:'R',kind:'requirement',title:'Root'},{id:'O',kind:'option',title:'Method'},...['A','B','C','DEEP'].map(id=>({id,kind:'requirement',title:id})),{id:'AO',kind:'option',title:'Child method'},{id:'DEEP-O',kind:'option',title:'Deep method'}],
 edges:[{id:'ro',type:'OPTION_FOR',from:'R',to:'O'},...['A','B','C'].map(id=>({id:'e'+id,type:'OUTCOME_OF',from:'O',to:id})),{id:'ao',type:'OPTION_FOR',from:'A',to:'AO'},{id:'deep',type:'OUTCOME_OF',from:'AO',to:'DEEP'},{id:'deep-o',type:'OPTION_FOR',from:'DEEP',to:'DEEP-O'}],
 collections:[{id:'list',title:'Three R',anchor:'O',memberRefs:['A','B','C']}]});
function memory(initial=core.empty()){
 let content=JSON.stringify(initial);return {name:'layouts.json',getFile:async()=>({text:async()=>content}),
 createWritable:async()=>{let draft;return {write:async text=>{draft=text},close:async()=>{content=draft},abort:async()=>{}}},
 read:()=>JSON.parse(content),replace:doc=>{content=JSON.stringify(doc)}};
}
async function setup(){const u=simulate();await u.loadFile(fixture());const h=memory();await u.host.rdgLayout.attachFile(h);return{u,h,a:u.host.rdgLayout};}
function pauseWrite(h){let enteredResolve,release;const entered=new Promise(r=>enteredResolve=r),gate=new Promise(r=>release=r),normal=h.createWritable;
 h.createWritable=async()=>{const w=await normal();return {...w,write:async text=>{await w.write(text);enteredResolve();await gate;}}};return{entered,release:()=>release()};}

test('F-P-01: edits during save remain dirty, and a second save persists them',async()=>{
 const {u,h,a}=await setup(),pause=pauseWrite(h),key=a.graphKey();a.apply({type:'set_positions',positions:{R:{x:100,y:100}}});
 const saving=a.save();await pause.entered;a.apply({type:'set_positions',positions:{R:{x:900,y:900}}});
 await assert.rejects(a.save(),/завершения/);assert.equal(u.ids['layout-save'].disabled,true);
 pause.release();await saving;
 assert.equal(h.read().layouts[key].positions.R.x,100);assert.equal(a.getDocument().layouts[key].positions.R.x,900);
 assert.equal(xy(u,'R'),'translate(900 900)');assert.match(u.ids['layout-save'].textContent,/\*/);assert.equal(u.ids['layout-save'].disabled,false);
 await a.save();assert.equal(h.read().layouts[key].positions.R.x,900);assert.equal(h.read().revision,2);assert(!u.ids['layout-save'].textContent.includes('*'));
});
test('F-P-01: an edit on graph B survives the completion of graph A save',async()=>{
 const {u,h,a}=await setup(),pause=pauseWrite(h),keyA=a.graphKey();a.apply({type:'set_positions',positions:{R:{x:1,y:2}}});const saving=a.save();await pause.entered;
 await u.loadFile(fixture('graph-b'));a.apply({type:'set_positions',positions:{R:{x:800,y:700}}});const keyB=a.graphKey();
 pause.release();await saving;assert.equal(h.read().layouts[keyA].positions.R.x,1);assert(!h.read().layouts[keyB]);assert.equal(a.getDocument().layouts[keyB].positions.R.x,800);assert.match(u.ids['layout-save'].textContent,/\*/);
 await a.save();assert.equal(h.read().layouts[keyB].positions.R.x,800);assert.equal(h.read().layouts[keyA].positions.R.x,1);
});
test('F-P-01/04: a reset during save remains pending and the next commit removes the override',async()=>{
 const {u,h,a}=await setup(),pause=pauseWrite(h),key=a.graphKey();a.apply({type:'set_positions',positions:{R:{x:900,y:800}}});const saving=a.save();await pause.entered;
 a.apply({type:'clear_layout'});assert.notEqual(xy(u,'R'),'translate(900 800)');pause.release();await saving;
 assert.equal(a.getDocument().layouts[key],undefined);assert.match(u.ids['layout-save'].textContent,/\*/);await a.save();assert.equal(h.read().layouts[key],undefined);
});
test('F-P-01: failed buffered writes preserve the full newer draft for retry',async()=>{
 const {u,h,a}=await setup(),normal=h.createWritable;let aborted=false;
 h.createWritable=async()=>({write:async()=>{a.apply({type:'set_positions',positions:{R:{x:701,y:702}}});throw Error('injected I/O failure')},abort:async()=>{aborted=true}});
 a.apply({type:'set_positions',positions:{R:{x:100,y:200}}});await assert.rejects(a.save(),/injected/);assert(aborted);assert.equal(h.read().revision,0);assert.equal(a.getDocument().layouts[a.graphKey()].positions.R.x,701);assert.match(u.ids['layout-save'].textContent,/\*/);
 h.createWritable=normal;await a.save();assert.equal(h.read().layouts[a.graphKey()].positions.R.x,701);
});
test('F-P-02: a group moved after collapse keeps its latest position after save and reload',async()=>{
 const {u,h,a}=await setup(),id='__collection__list';a.apply({type:'set_positions',positions:{[id]:{x:600,y:400}}});click(u,id);u.ids['collections-collapse'].onclick();a.apply({type:'set_positions',positions:{[id]:{x:1100,y:700}}});
 await a.save();assert.deepEqual(h.read().layouts[a.graphKey()].positions[id],{x:1100,y:700});const u2=simulate();u2.host.rdgLayout.load(h.read());await u2.loadFile(fixture());assert.equal(xy(u2,id),'translate(1100 700)');
});
test('F-P-02: a command targeting a hidden header overrides its remembered position',async()=>{
 const {u,h,a}=await setup(),id='__collection__list';click(u,id);a.apply({type:'set_positions',positions:{[id]:{x:-800,y:-300}}});await a.save();assert.deepEqual(h.read().layouts[a.graphKey()].positions[id],{x:-800,y:-300});u.ids['collections-collapse'].onclick();assert.equal(xy(u,id),'translate(-800 -300)');
});
test('F-P-04: the API clear command and the reset button both commit deletion, not old or automatic coordinates',async()=>{
 for(const reset of ['api','button']){const {u,h,a}=await setup(),key=a.graphKey(),automatic=xy(u,'R');a.apply({type:'set_positions',positions:{R:{x:900,y:800}}});await a.save();
 if(reset==='api')a.apply({type:'clear_layout'});else u.ids['layout-reset'].onclick();assert.equal(xy(u,'R'),automatic);await a.save();assert.equal(h.read().layouts[key],undefined);
 const u2=simulate();u2.host.rdgLayout.load(h.read());await u2.loadFile(fixture());assert.equal(xy(u2,'R'),automatic);}
});
test('F-P-03: a manual graph without opt-in opens local one-level continuations and returns without changing records',async()=>{
 const u=simulate(),g=fixture(),before=JSON.stringify(g);await u.loadFile(g);const rootKey=u.host.rdgLayout.graphKey();click(u,'__collection__list');const rootCamera=camera(u);assert(!node(u,'AO')&&!node(u,'DEEP'));
 click(u,'A');await u.flush();assert.deepEqual(ids(u).sort(),['A','AO','DEEP'].sort());assert(!node(u,'DEEP-O'));assert.deepEqual(JSON.parse(u.host.rdgLayout.graphKey()),['layout-fix-test','fix-fixture','A']);
 click(u,'DEEP');await u.flush();assert.deepEqual(ids(u).sort(),['DEEP','DEEP-O'].sort());await u.ids['level-up'].onclick();assert.deepEqual(ids(u).sort(),['A','AO','DEEP'].sort());
 await u.ids['level-up'].onclick();assert.equal(u.host.rdgLayout.graphKey(),rootKey);assert.equal(camera(u),rootCamera);assert(node(u,'A')&&!node(u,'__collection__list'));assert.equal(u.ids['level-up'].hidden,true);assert.equal(JSON.stringify(g),before);
});
test('F-P-03: legacy inferred roots also stop at one level and allow local expansion',async()=>{
 const u=simulate(),g=fixture();delete g.rootRequirementId;g.nodes[1].kind='decision';g.edges[0]={id:'ro',type:'DRIVES',from:'R',to:'O'};for(const e of g.edges)if(e.from==='O'){e.type='INTRODUCES';e.parent='R'};await u.loadFile(g);click(u,'__collection__list');assert(!node(u,'AO'));click(u,'A');await u.flush();assert(node(u,'AO')&&!node(u,'R'));
});
test('local levels save separately in the common format and CLI accepts a rooted key',async()=>{
 const {u,h,a}=await setup();click(u,'__collection__list');const rootKey=a.graphKey();a.apply({type:'set_positions',positions:{R:{x:42,y:84}}});await a.save();click(u,'A');await u.flush();const childKey=a.graphKey();a.apply({type:'set_positions',positions:{A:{x:-700,y:-400}}});await a.save();
 assert.equal(h.read().layouts[rootKey].positions.R.x,42);assert.equal(h.read().layouts[childKey].positions.A.x,-700);await u.ids['level-up'].onclick();assert.equal(xy(u,'R'),'translate(42 84)');
 const reload=simulate();reload.host.rdgLayout.load(h.read());await reload.loadFile(fixture());click(reload,'__collection__list');click(reload,'A');await reload.flush();assert.equal(xy(reload,'A'),'translate(-700 -400)');assert.equal(reload.host.rdgLayout.graphKey(),childKey);
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-root-key-'));try{const file=path.join(dir,'layouts.json'),commands=path.join(dir,'commands.json');fs.writeFileSync(file,JSON.stringify(core.empty()));
 const key=core.graphKey('rdg-example-prepared-v7','reference-prepared-planning-tree','RF-1');fs.writeFileSync(commands,JSON.stringify({type:'set_positions',graphKey:key,positions:{'RF-1-O1':{x:-10,y:-20}}}));
 const r=cp.spawnSync(process.execPath,[path.resolve(__dirname,'../tools/rdg-layout-cli.cjs'),'--file',file,'--expect-revision','0','--commands-file',commands],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);assert.equal(JSON.parse(fs.readFileSync(file)).layouts[key].positions['RF-1-O1'].x,-10);
 }finally{fs.rmSync(dir,{recursive:true,force:true})}
});
const walk=(root,pred)=>{const out=[];function visit(n){if(pred(n))out.push(n);for(const c of n.children||[])visit(c)}visit(root);return out};
const coords=n=>n.getAttribute('transform').match(/[-\d.]+/g).map(Number);
test('a method shared with another R remains visible when it directly answers the current root',async()=>{
 const g={schemaVersion:1,id:'shared-root-answer',rootRequirementId:'R',nodes:[{id:'R',kind:'requirement',title:'Root'},{id:'S',kind:'requirement',title:'Other R'},{id:'D',kind:'decision',title:'Shared answer'},{id:'CHILD',kind:'requirement',title:'Child'}],edges:[{id:'a',type:'DRIVES',from:'R',to:'D'},{id:'b',type:'DRIVES',from:'S',to:'D'},{id:'c',type:'INTRODUCES',from:'D',to:'CHILD',parent:'R'}]};
 const u=simulate();await u.loadFile(g);assert(node(u,'D')&&node(u,'CHILD'));assert.equal(JSON.stringify(g.nodes.map(n=>n.id)),JSON.stringify(['R','S','D','CHILD']));
});
test('F-P-05: routing and labels translate with nodes through all four quadrants and fit includes labels',async()=>{
 const u=simulate();await u.loadFile({schemaVersion:1,id:'geometry',rootRequirementId:'R',nodes:[{id:'R',kind:'requirement',title:'Root'},{id:'O',kind:'option',title:'Option'}],edges:[{id:'ro',type:'OPTION_FOR',from:'R',to:'O'}]});
 let base;
 for(const [dx,dy] of [[0,0],[-900,0],[0,-600],[-900,-600]]){
 u.host.rdgLayout.apply({type:'set_positions',positions:{R:{x:60+dx,y:60+dy},O:{x:460+dx,y:60+dy}}});u.ids.fit.onclick();
 const path=walk(u.ids.canvas,n=>n.classList?.contains('edge'))[0].getAttribute('d').match(/[-\d.]+/g).map(Number),label=walk(u.ids.canvas,n=>n.classList?.contains('edge-label'))[0],l=coords(label);
 if(!base)base={path,l};else{assert.deepEqual(path,base.path.map((p,i)=>p+(i%2?dy:dx)));assert.deepEqual(l,[base.l[0]+dx,base.l[1]+dy]);}
 const [tx,ty,scale]=coords(u.root.getElementById('scene'));assert(l[0]*scale+tx>=0&&l[0]*scale+tx<=800);assert(l[1]*scale+ty>=0&&l[1]*scale+ty<=500);
 }
});
test('F-P-06: opening and closing alternatives preserves pan, zoom and surviving node positions',async()=>{
 const u=simulate({useBundle:true});await u.flush();await u.openCard('reference-mixed-active-work');
 u.ids.canvas.listeners.pointerdown({button:0,target:{closest:()=>null},pointerId:2,clientX:200,clientY:200});u.ids.canvas.listeners.pointermove({pointerId:2,clientX:450,clientY:280});u.ids.canvas.listeners.pointerup({pointerId:2});u.ids.canvas.listeners.wheel({preventDefault(){},clientX:300,clientY:300,deltaY:-1});
 const before=camera(u),root=xy(u,'R0'),chosen=xy(u,'R-COMP');for(let i=0;i<2;i++){u.ids['variants-all'].onclick();assert.equal(camera(u),before);assert.equal(xy(u,'R0'),root);assert.equal(xy(u,'R-COMP'),chosen)}
});
test('F-P-07: file input survives event retargeting after await and is cleared on read failure too',async()=>{
 const u=simulate(),input={files:[],value:'fixture.json'},event={target:input};input.files=[{name:'fixture.json',text:async()=>{event.target=null;return JSON.stringify(fixture())}}];await u.ids.picker.onchange(event);assert.equal(input.value,'');assert(node(u,'R'));
 input.value='broken.json';input.files=[{name:'broken.json',text:async()=>{throw Error('read failed')}}];await u.ids.picker.onchange({target:input});assert.equal(input.value,'');assert.match(u.text(),/read failed/);assert(node(u,'R'));
});
test('reading a file does not overwrite edits made while that read is pending',async()=>{
 const {u,a}=await setup();let release;const h={name:'slow.json',getFile:async()=>({text:()=>new Promise(r=>release=r)})};const reading=a.attachFile(h);await u.flush();a.apply({type:'set_positions',positions:{R:{x:810,y:820}}});release(JSON.stringify(core.empty()));await assert.rejects(reading,/новые перемещения/);assert.equal(xy(u,'R'),'translate(810 820)');assert.equal(a.getDocument().layouts[a.graphKey()].positions.R.x,810);
});
test('same-origin Web Locks serializes connected browser clients and stale second save is rejected',async()=>{
 const u=simulate(),v=simulate();await u.loadFile(fixture());await v.loadFile(fixture());const h=memory(),a=u.host.rdgLayout,b=v.host.rdgLayout;await a.attachFile(h);await b.attachFile(h);
 let queue=Promise.resolve();const locks={request:(name,callback)=>{const running=queue.catch(()=>{}).then(callback);queue=running;return running}};u.context.navigator={locks};v.context.navigator={locks};a.apply({type:'set_positions',positions:{R:{x:1,y:2}}});b.apply({type:'set_positions',positions:{R:{x:3,y:4}}});
 const result=await Promise.allSettled([a.save(),b.save()]);assert.equal(result[0].status,'fulfilled');assert.equal(result[1].status,'rejected');assert.match(result[1].reason.message,/изменён извне/);assert.equal(h.read().layouts[a.graphKey()].positions.R.x,1);assert.equal(b.getDocument().layouts[b.graphKey()].positions.R.x,3);
});


test('local continuations retain a Requirement used as a ground without opening its own answer',async()=>{
 const g=fixture();g.nodes.push({id:'CONSTRAINT',kind:'requirement',title:'Applies here'},{id:'EXTRA-D',kind:'decision',title:'Answer elsewhere'});
 g.edges.push({id:'ground',type:'CONTEXT_FOR',from:'CONSTRAINT',to:'AO'},{id:'elsewhere',type:'DRIVES',from:'CONSTRAINT',to:'EXTRA-D'});
 const u=simulate();await u.loadFile(g);click(u,'__collection__list');click(u,'A');await u.flush();u.ids['edges-all'].onclick();assert(node(u,'CONSTRAINT'));assert(!node(u,'EXTRA-D'));
});
test('reload keeps the current local root and a missing root in an updated file preserves the old view',async()=>{
 const initial=JSON.parse(fs.readFileSync(path.join(__dirname,'../graphs/examples/example/graph.json'))),updated=plain(initial);updated.revision=2;
 const files={'examples/example/graph.json':JSON.stringify(updated)},u=simulate({useBundle:true,files});await u.flush();await u.openCard('example');click(u,'R-002');await u.flush();const key=u.host.rdgLayout.graphKey();
 await u.ids.reload.onclick();assert.equal(u.host.rdgLayout.graphKey(),key);assert(node(u,'R-002')&&!node(u,'R-001'));assert.match(u.info(),/Revision: 2/);
 await u.ids['level-up'].onclick();assert(node(u,'R-001'));u.ids.search.oninput({target:{value:''}});assert.match(u.info(),/Revision: 2/);click(u,'R-002');await u.flush();assert.equal(u.host.rdgLayout.graphKey(),key);
 updated.nodes=updated.nodes.filter(n=>n.id!=='R-002');updated.edges=updated.edges.filter(e=>e.from!=='R-002'&&e.to!=='R-002'&&e.parent!=='R-002');files['examples/example/graph.json']=JSON.stringify(updated);
 await u.ids.reload.onclick();assert.equal(u.host.rdgLayout.graphKey(),key);assert(node(u,'R-002'));assert.match(u.text(),/нет R текущего уровня/);
});
