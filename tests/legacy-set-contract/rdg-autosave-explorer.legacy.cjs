const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process');
const {simulate}=require('./viewer-test-helper.cjs'),core=require('../tools/rdg-layout-core.js'),catalog=require('../tools/rdg-catalog.js');
const plain=x=>JSON.parse(JSON.stringify(x));
const fixture=id=>({schemaVersion:1,id:id||'auto-test',identitySpace:'autosave-test',rootRequirementId:'R',revision:1,nodes:[{id:'R',kind:'requirement',title:'Goal'}],edges:[]});
function clock(){let next=1;const jobs=new Map();return{timers:{setTimeout:fn=>{const id=next++;jobs.set(id,fn);return id},clearTimeout:id=>jobs.delete(id)},tick(){const callbacks=[...jobs.values()];jobs.clear();callbacks.forEach(fn=>fn())},size:()=>jobs.size};}
function memory(initial=core.empty()){let body=JSON.stringify(initial),writes=0;return{name:'layouts.json',queryPermission:async()=> 'granted',getFile:async()=>({text:async()=>body}),createWritable:async()=>{let pending;return{write:async text=>{pending=text;writes++},close:async()=>{body=pending},abort:async()=>{}}},read:()=>JSON.parse(body),replace:d=>{body=JSON.stringify(d)},writes:()=>writes};}
async function setup(){const c=clock(),u=simulate({timers:c.timers});await u.loadFile(fixture());const h=memory();await u.host.rdgLayout.attachFile(h);return{u,a:u.host.rdgLayout,h,c};}
async function settle(u){for(let i=0;i<8;i++)await u.flush();}
test('autosave coalesces changes after drag and confirms only a read-back of the latest edit',async()=>{
 const {u,a,h,c}=await setup();a.apply({type:'set_positions',positions:{R:{x:1,y:2}}});a.apply({type:'set_positions',positions:{R:{x:3,y:4}}});
 assert.equal(h.writes(),0);assert.equal(c.size(),1);assert.equal(u.ids['layout-status'].textContent,'Ожидает сохранения');
 c.tick();await settle(u);assert.equal(h.writes(),1);assert.equal(h.read().layouts[a.graphKey()].positions.R.x,3);
 assert.equal(u.ids['layout-status'].textContent,'Сохранено');assert.equal(a.status().dirty,false);
});
test('autosave records a real pointer drag without moving the camera',async()=>{
 const {u,a,h,c}=await setup(),node=u.root.querySelectorAll('.node')[0],camera=u.root.getElementById('scene').getAttribute('transform');
 u.ids.canvas.listeners.pointerdown({button:0,target:node,pointerId:1,clientX:10,clientY:10});
 u.ids.canvas.listeners.pointermove({pointerId:1,clientX:110,clientY:60});assert.equal(c.size(),0);
 u.ids.canvas.listeners.pointerup({pointerId:1});assert.equal(c.size(),1);c.tick();await settle(u);
 assert(h.read().layouts[a.graphKey()].positions.R);assert.equal(u.root.getElementById('scene').getAttribute('transform'),camera);
});
test('new edits during a buffered write automatically receive their own next save, including another graph',async()=>{
 const {u,a,h,c}=await setup();let release,entered;
 const original=h.createWritable;h.createWritable=async()=>{const w=await original();return{...w,write:async text=>{await w.write(text);entered=true;await new Promise(r=>release=r)}}};
 a.apply({type:'set_positions',positions:{R:{x:10,y:20}}});c.tick();await settle(u);assert(entered);
 await u.loadFile(fixture('second'));const second=a.graphKey();a.apply({type:'set_positions',positions:{R:{x:70,y:80}}});
 h.createWritable=original;release();await settle(u);assert(a.status().dirty);assert.notEqual(u.ids['layout-status'].textContent,'Сохранено');assert.equal(c.size(),1);
 c.tick();await settle(u);assert.equal(h.read().layouts[second].positions.R.x,70);assert.equal(h.writes(),2);assert.equal(u.ids['layout-status'].textContent,'Сохранено');
});
test('external changes stop the automatic queue without overwriting the other writer',async()=>{
 const {u,a,h,c}=await setup();a.apply({type:'set_positions',positions:{R:{x:10,y:20}}});h.replace(core.commit(core.empty(),0));
 c.tick();await settle(u);assert.match(u.ids['layout-status'].textContent,/Конфликт/);assert(a.status().dirty);assert.equal(c.size(),0);assert.equal(h.writes(),0);assert.equal(h.read().revision,1);
});
test('revoked permissions do not open prompts from autosave; draft remains available',async()=>{
 const {u,a,h,c}=await setup();let requests=0;h.queryPermission=async()=> 'prompt';h.requestPermission=async()=>{requests++;return 'granted'};
 a.apply({type:'set_positions',positions:{R:{x:10,y:20}}});c.tick();await settle(u);assert.equal(requests,0);assert.equal(h.writes(),0);assert.match(u.ids['layout-status'].textContent,/Нет доступа/);
 await a.save();assert.equal(requests,1);assert.equal(h.writes(),1);assert.equal(u.ids['layout-status'].textContent,'Сохранено');
});
test('write errors remain dirty and are not retried endlessly',async()=>{
 const {u,a,h,c}=await setup();h.createWritable=async()=>{throw Error('disk full')};a.apply({type:'clear_layout'});c.tick();await settle(u);
 assert(a.status().dirty);assert.match(u.ids['layout-status'].textContent,/Ошибка записи/);assert.equal(c.size(),0);
});
test('pause provides a visible sequential handoff to CLI; resume schedules pending work',async()=>{
 const {u,a,h,c}=await setup();a.pause();a.apply({type:'set_positions',positions:{R:{x:1,y:2}}});assert.equal(c.size(),0);assert.match(u.ids['layout-status'].textContent,/приостановлено/);
 a.resume();assert.equal(c.size(),1);c.tick();await settle(u);assert.equal(h.writes(),1);
 a.apply({type:'clear_layout'});c.tick();await settle(u);assert.equal(h.read().layouts[a.graphKey()],undefined);
});
test('without a connected file changes remain a draft and no picker opens automatically',async()=>{
 const c=clock(),u=simulate({timers:c.timers});await u.loadFile(fixture());let picks=0;u.window.showSaveFilePicker=async()=>{picks++;return memory()};
 u.host.rdgLayout.apply({type:'set_positions',positions:{R:{x:1,y:2}}});assert.equal(c.size(),0);assert.equal(picks,0);assert.match(u.ids['layout-status'].textContent,/подключите/);
});
test('a crash draft restores without silently replacing a newer external base',async()=>{
 const {u,a,h,c}=await setup();a.apply({type:'set_positions',positions:{R:{x:33,y:44}}});
 const doc=core.commit(core.empty(),0),files={'index.json':JSON.stringify({schemaVersion:1,graphs:[],layouts:doc}),'layouts.json':JSON.stringify(doc)};
 await settle(u);const journal=(await a.drafts()).find(d=>d.own);
 const v=simulate({files,storage:u.storage});await settle(v);await v.loadFile(fixture());await v.host.rdgLayout.recoverDraft(journal.id);
 assert(v.host.rdgLayout.status().dirty);assert.match(v.ids['layout-status'].textContent,/Конфликт/);
 assert.equal(v.host.rdgLayout.getDocument().layouts[a.graphKey()].positions.R.x,33);assert.equal(h.read().revision,0);
});
test('graph-set keys cannot collide with legacy graph keys; UI and CLI share the same file',async()=>{
 const u=simulate({useBundle:true});await settle(u);await u.openSet('example-prepared');const a=u.host.rdgLayout,key=a.graphKey(),slug='reference-prepared-planning-tree';
 assert.deepEqual(JSON.parse(key),{type:'graph-set',id:'example-prepared'});assert.notEqual(key,core.graphKey('graph-set','example-prepared'));
 const h=memory();await a.attachFile(h);a.apply({type:'set_positions',positions:{[slug]:{x:-400,y:-300}}});await a.save();assert.equal(h.read().layouts[key].positions[slug].x,-400);
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-set-cli-'));try{const file=path.join(tmp,'layouts.json'),cmd=path.join(tmp,'commands.json');fs.writeFileSync(file,JSON.stringify(h.read()));fs.writeFileSync(cmd,JSON.stringify({type:'set_positions',graphKey:key,positions:{[slug]:{x:111,y:222}}}));
 const r=cp.spawnSync(process.execPath,[path.resolve(__dirname,'../tools/rdg-layout-cli.cjs'),'--file',file,'--expect-revision','1','--commands-file',cmd],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);
 a.load(JSON.parse(fs.readFileSync(file)));assert.equal(u.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')===slug).getAttribute('transform'),'translate(111 222)');
 }finally{fs.rmSync(tmp,{recursive:true,force:true})}
});
test('catalog helpers handle an unrelated folder, mixed usages and unconnected set members',()=>{
 const g=(slug,folder,presentation,setId)=>({slug,folder,group:'other',file:folder+'/'+slug+'/graph.json',title:slug,presentation,...(setId?{setId}:{})});
 const c=catalog.normalizeCatalog({schemaVersion:1,folders:[{id:'other/deep',folder:'other',title:'Deep',kind:'folder'}],graphs:[g('a','other',{usage:'ready'},'s'),g('b','other',{usage:'working'},'s'),g('c','other',{})],graphSets:[{id:'s',kind:'graph-set',folder:'other',title:'Set',members:['a','b'],entryGraphSlugs:['a']}],relations:[]});
 assert.deepEqual(catalog.listFolder(c,'other').map(e=>e.kind).sort(),['folder','graph','graph-set']);assert.equal(catalog.buildGraphSetView(c,'s').graphs.length,2);assert.equal(catalog.buildGraphSetView(c,'s').relations.length,0);assert(catalog.searchCatalog(c,'b').some(g=>g.slug==='b'));
 for(const file of ['other/../a/graph.json','C:/a/graph.json','other/./graph.json'])assert.throws(()=>catalog.normalizeCatalog({schemaVersion:1,graphs:[{slug:'a',file}]}));
});
test('catalog generated helper in the userscript is byte-identical to the CLI source',()=>{
 const {code}=require('./viewer-test-helper.cjs');assert.equal(code.split('// BEGIN GENERATED RDG CATALOG\n')[1].split('// END GENERATED RDG CATALOG\n')[0],fs.readFileSync(path.resolve(__dirname,'../tools/rdg-catalog.js'),'utf8'));
});

test('pausing after an edit cancels the already scheduled automatic write',async()=>{
 const {u,a,h,c}=await setup();a.apply({type:'set_positions',positions:{R:{x:1,y:2}}});assert.equal(c.size(),1);a.pause();assert.equal(c.size(),0);c.tick();await settle(u);assert.equal(h.writes(),0);assert(a.status().dirty);
});
test('returning to the explorer preserves the set address while its save is queued',async()=>{
 const c=clock(),u=simulate({useBundle:true,timers:c.timers});await settle(u);await u.openSet('example-prepared');
 const a=u.host.rdgLayout,h=memory(),slug='reference-prepared-planning-tree';await a.attachFile(h);
 const key=a.graphKey();a.apply({type:'set_positions',positions:{[slug]:{x:-20,y:120}}});u.openFolder('examples');
 assert.equal(a.graphKey(),key);c.tick();await settle(u);assert.equal(h.read().layouts[key].positions[slug].x,-20);assert.equal(u.ids.catalog.hidden,false);
});

test('saving or discarding one tab cannot delete another tab recovery journal, even for the same graph',async()=>{
 const storage=new Map(),a=simulate({storage}),b=simulate({storage});await settle(a);await settle(b);
 await a.loadFile(fixture());await b.loadFile(fixture());const handle=memory();await b.host.rdgLayout.attachFile(handle);
 a.host.rdgLayout.apply({type:'set_positions',positions:{R:{x:101,y:102}}});await settle(a);
 const own=(await a.host.rdgLayout.drafts()).find(d=>d.own);assert(own);
 b.host.rdgLayout.apply({type:'set_positions',positions:{R:{x:901,y:902}}});await b.host.rdgLayout.save();await settle(b);
 assert(storage.has(own.id));assert.equal(JSON.parse(storage.get(own.id)).commands[0].positions.R.x,101);
 b.ids['layout-discard'].onclick();await settle(b);assert(storage.has(own.id));
 const c=simulate({storage});await settle(c);await c.loadFile(fixture());assert.equal(c.host.rdgLayout.status().dirty,false);
 assert((await c.host.rdgLayout.drafts()).some(d=>d.id===own.id&&!d.own));
 await c.host.rdgLayout.recoverDraft(own.id);assert.equal(c.host.rdgLayout.getDocument().layouts[a.host.rdgLayout.graphKey()].positions.R.x,101);
 assert(storage.has(own.id),'recovery must preserve the foreign source');
 await assert.rejects(c.host.rdgLayout.recoverDraft(own.id),/Сначала/);
});
test('the legacy draft is copied without deleting the migration source',async()=>{
 const storage=new Map(),base=core.empty(),key=core.graphKey('autosave-test','auto-test');
 const legacy='rdg-layout-document:file:///C:/Users/alexa/Repos/rd-graphs/graphs/:draft';
 storage.set(legacy,JSON.stringify({base,commands:[{type:'set_positions',graphKey:key,positions:{R:{x:12,y:34}}}]}));
 const u=simulate({storage,useBundle:true});await settle(u);await u.loadFile(fixture());assert(u.host.rdgLayout.status().dirty);assert(storage.has(legacy));
 const drafts=await u.host.rdgLayout.drafts();assert(drafts.some(d=>d.own));assert(drafts.some(d=>d.legacy));
 u.ids['layout-discard'].onclick();await settle(u);
 const reloaded=simulate({storage,useBundle:true});await settle(reloaded);
 assert.equal(reloaded.host.rdgLayout.status().dirty,false,'legacy migration must not replay discarded/saved edits');
 assert((await reloaded.host.rdgLayout.drafts()).some(d=>d.legacy),'legacy source remains explicitly recoverable');
});
test('the first real drag without a file visibly changes the status and never says saved',async()=>{
 const u=simulate();await settle(u);await u.loadFile(fixture());const before=u.ids['layout-status'].textContent;
 const n=u.root.querySelectorAll('.node')[0];u.ids.canvas.listeners.pointerdown({button:0,target:n,pointerId:1,clientX:10,clientY:10});
 u.ids.canvas.listeners.pointermove({pointerId:1,clientX:110,clientY:60});u.ids.canvas.listeners.pointerup({pointerId:1});
 assert.notEqual(u.ids['layout-status'].textContent,before);assert.match(u.ids['layout-status'].textContent,/Изменения не записаны/);
 assert.equal(u.ids['layout-status'].getAttribute('data-state'),'dirty');
});

test('Viewer reads hash and percent paths through encoded local file URLs',async()=>{
 const g=fixture(),file='Plans #1/100%/graph.json',entry={slug:'encoded',file,folder:'Plans #1',title:'Encoded',identitySpace:g.identitySpace};
 const files={'index.json':JSON.stringify({schemaVersion:1,graphs:[entry],folders:[{id:'Plans #1',folder:'',title:'Plans',kind:'folder'}],graphSets:[],relations:[]}),[file.split('/').map(encodeURIComponent).join('/')]:JSON.stringify(g)};
 const u=simulate({files});await settle(u);await u.openCard('encoded');assert.equal(u.root.querySelectorAll('.node').length,1);assert.equal(u.root.querySelectorAll('.node')[0].getAttribute('data-id'),'R');
});

test('draft recovery refuses an edit made while the source is being read',async()=>{
 const storage=new Map(),a=simulate({storage}),b=simulate({storage});await settle(a);await settle(b);await a.loadFile(fixture());await b.loadFile(fixture());
 a.host.rdgLayout.apply({type:'set_positions',positions:{R:{x:101,y:102}}});const draft=(await a.host.rdgLayout.drafts()).find(d=>d.own);
 const original=b.context.localStorage.getItem;b.context.localStorage.getItem=key=>{const raw=original(key);if(key===draft.id)b.host.rdgLayout.apply({type:'set_positions',positions:{R:{x:701,y:702}}});return raw};
 await assert.rejects(b.host.rdgLayout.recoverDraft(draft.id),/Сначала/);
 assert.equal(b.host.rdgLayout.getDocument().layouts[b.host.rdgLayout.graphKey()].positions.R.x,701);
});
