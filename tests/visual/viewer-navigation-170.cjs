'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require('/opt/dc/node_modules/puppeteer-core');
const out=path.resolve(process.env.RDG_SCREENSHOT_DIR);fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--allow-file-access-from-files'],userDataDir:path.join(out,'isolated-profile')});
 const page=await browser.newPage(),errors=[],evidence={version:fs.readFileSync(path.join(__dirname,'../../tools/rd-graph-viewer.user.js'),'utf8').match(/@version\s+(\S+)/)[1]};
 page.on('pageerror',e=>errors.push(e.stack));page.on('dialog',d=>d.accept());
 const run=fn=>page.evaluate(fn),click=id=>page.evaluate(id=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById(id).click(),id);
 const camera=()=>run(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('scene').getAttribute('transform').match(/[-\d.]+/g).map(Number));
 const ids=()=>run(()=>[...document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('.node')].map(n=>n.getAttribute('data-id')));
 const world=()=>run(()=>Object.fromEntries([...document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('.node')].map(n=>[n.getAttribute('data-id'),n.getAttribute('transform')])));
 const shot=async name=>{await page.evaluate(()=>document.fonts.ready);await new Promise(r=>setTimeout(r,220));await page.screenshot({path:path.join(out,name+'.png')});console.log('SCREEN',name)};
 const boot=async()=>{await page.goto('file://'+path.join(__dirname,'rdg-viewer.html'));await page.waitForFunction(()=>document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());await click('launch')};
 const open=async id=>page.evaluate(id=>document.getElementById('rdg-viewer-root').rdgExplorer.openSet(id),id);
 const checkLabels=async()=>{
  const result=await run(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   const xy=n=>n.getAttribute('transform').match(/[-\d.]+/g).map(Number);
   const nodes=[...s.querySelectorAll('.node')].map(n=>{const [x,y]=xy(n);return{id:n.getAttribute('data-id'),x,y,w:222,h:72}});
   const labels=[...s.querySelectorAll('.edge-label')].map(n=>{const [x,y]=xy(n),r=n.querySelector('rect');return{id:n.getAttribute('data-edge-id'),target:n.getAttribute('data-label-target'),x:x+Number(r.getAttribute('x')),y:y+Number(r.getAttribute('y')),w:Number(r.getAttribute('width')),h:Number(r.getAttribute('height'))}});
   const hit=(a,b)=>a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y;
   return{labels:labels.length,overlaps:labels.flatMap((l,i)=>[...nodes,...labels.slice(i+1)].filter(n=>hit(l,n)).map(n=>[l.id,n.id])),
    distances:labels.map(l=>{const t=nodes.find(n=>n.id===l.target);return Math.hypot(Math.max(l.x-t.x-t.w,t.x-l.x-l.w,0),Math.max(l.y-t.y-t.h,t.y-l.y-l.h,0))}),
    leaders:s.querySelectorAll('[data-label-leader]').length};
  });assert.deepEqual(result.overlaps,[]);assert(result.distances.every(d=>d<=350),JSON.stringify(result));assert.equal(result.leaders,result.labels);return result;
 };
 try{
 await page.setViewport({width:1440,height:900});await boot();await open('example-working');assert.equal((await ids()).length,5);
 assert.equal(await run(()=>document.getElementById('rdg-viewer-root').dataset.rdgVersion),evidence.version);await shot('01-working-current');
 const scene=await run(()=>{const b=document.getElementById('rdg-viewer-root').shadowRoot.getElementById('canvas').getBoundingClientRect();return{x:b.x+b.width/2,y:b.y+b.height/2}});
 const originalPositions=await world(),originalDoc=await run(()=>document.getElementById('rdg-viewer-root').rdgLayout.getDocument());
 await page.mouse.move(scene.x,scene.y);let a=await camera();await page.mouse.wheel({deltaY:90});await new Promise(r=>setTimeout(r,100));let b=await camera();assert.equal(b[2],a[2]);assert(b[1]<a[1]);assert.equal(b[0],a[0]);
 await page.keyboard.down('Shift');a=await camera();await page.mouse.wheel({deltaY:75});await page.keyboard.up('Shift');await new Promise(r=>setTimeout(r,100));b=await camera();assert(b[0]<a[0]);assert.equal(b[1],a[1]);assert.equal(b[2],a[2]);
 await page.keyboard.down('Control');await page.keyboard.down('Shift');a=await camera();await page.mouse.wheel({deltaY:-100});await page.keyboard.up('Shift');await page.keyboard.up('Control');await new Promise(r=>setTimeout(r,100));b=await camera();assert(b[2]>a[2]);
 assert.deepEqual(await world(),originalPositions);assert.deepEqual(await run(()=>document.getElementById('rdg-viewer-root').rdgLayout.getDocument()),originalDoc);evidence.realWheelModes=true;
 const c=await camera(),old=await world();await click('variants-all');assert.equal((await ids()).length,10);assert.deepEqual(await camera(),c);for(const [id,p] of Object.entries(old))assert.equal((await world())[id],p);
 await click('fit');evidence.workingLabels=await checkLabels();await shot('02-working-alternatives');
 const tones=await run(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;return Object.fromEntries(['selected','alternative'].map(state=>{const n=s.querySelector('.node[data-branch-state="'+state+'"]');return[state,{fill:getComputedStyle(n.querySelector('rect')).fill,text:n.textContent}]}))});assert.notEqual(tones.selected.fill,tones.alternative.fill);assert.match(tones.alternative.text,/не выбрано/);evidence.tones=tones;
 await run(async()=>{const h=document.getElementById('rdg-viewer-root'),api=h.rdgLayout,dir=await navigator.storage.getDirectory(),file=await dir.getFileHandle('viewer170-layouts.json',{create:true}),w=await file.createWritable();await w.write(JSON.stringify(api.getDocument()));await w.close();await api.attachFile(file);globalThis.native170=file;});
 const slug='reference-mixed-planned-feature',key=await run(()=>document.getElementById('rdg-viewer-root').rdgLayout.graphKey());
 await page.evaluate(slug=>document.getElementById('rdg-viewer-root').rdgLayout.apply({type:'set_positions',positions:{[slug]:{x:1080,y:120}}}),slug);
 await page.waitForFunction(()=>{const a=document.getElementById('rdg-viewer-root').rdgLayout;return a.status().lastSaved&&!a.status().dirty},{timeout:10000});
 const disk=await run(async()=>JSON.parse(await(await native170.getFile()).text()));assert.deepEqual(disk.layouts[key].positions[slug],{x:1080,y:120});await click('fit');await shot('03-position-autosaved');
 // Actual node drag shares the same commands and autosave path.
 await page.evaluate(slug=>{const s=document.getElementById('rdg-viewer-root').shadowRoot,q=s.getElementById('search');q.value=slug;q.dispatchEvent(new Event('input'));},slug);
 const box=await page.evaluate(slug=>{const r=document.getElementById('rdg-viewer-root').shadowRoot.querySelector('[data-id="'+slug+'"]').getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}},slug);
 await page.mouse.move(box.x,box.y);await page.mouse.down();await page.mouse.move(box.x+70,box.y+25,{steps:10});await page.mouse.up();await page.waitForFunction(()=>!document.getElementById('rdg-viewer-root').rdgLayout.status().dirty,{timeout:10000});
 const moved=await run(async()=>{const a=document.getElementById('rdg-viewer-root').rdgLayout;return JSON.parse(await(await native170.getFile()).text()).layouts[a.graphKey()].positions['reference-mixed-planned-feature']});assert.notDeepEqual(moved,{x:1080,y:120});
 const rememberedCamera=await camera();await page.evaluate(slug=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('[data-id="'+slug+'"]').dispatchEvent(new MouseEvent('click',{bubbles:true})),slug);
 // A recent drag suppresses the first click; wait for that guard before navigation.
 await new Promise(r=>setTimeout(r,400));await page.evaluate(slug=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('[data-id="'+slug+'"]')?.dispatchEvent(new MouseEvent('click',{bubbles:true})),slug);
 await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').rdgLayout.graphKey().startsWith('['));await click('back');assert.equal((await ids()).length,10);assert.deepEqual(await camera(),rememberedCamera);
 await boot();await open('example-working');assert.equal((await ids()).length,5);await click('variants-all');assert.equal((await world())[slug],'translate('+moved.x+' '+moved.y+')');evidence.nativeAutosaveAndReload=true;
 // Programmatic positions reverse/turn routes through the same layout API.
 await run(()=>document.getElementById('rdg-viewer-root').rdgLayout.apply({type:'set_positions',positions:{'reference-mixed-active-work':{x:700,y:50},'reference-mixed-contextual-split':{x:200,y:50},'reference-mixed-change-log':{x:700,y:-180},'reference-mixed-feature-availability':{x:200,y:350},'reference-mixed-feature-consistency':{x:-250,y:50}}}));
 await click('fit');evidence.reversedLabels=await checkLabels();await shot('04-reversed-and-vertical');
 await page.setViewport({width:390,height:844});await click('fit');assert(await run(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot,b=s.getElementById('variants-all').getBoundingClientRect();return b.width>0&&b.top>=0&&b.bottom<innerHeight}));await shot('05-mobile');
 await page.setViewport({width:1440,height:900});await open('example-prepared');assert.equal((await ids()).length,6);evidence.preparedLabels=await checkLabels();await shot('06-prepared');
 // A shared target with many incoming lines must not pile its labels at sources.
 const dense={schemaVersion:1,id:'dense',identitySpace:'dense',rootRequirementId:'R',revision:1,nodes:[{id:'R',kind:'requirement',title:'Root'},...Array.from({length:8},(_,i)=>({id:'D'+i,kind:'decision',title:'Answer '+i})),{id:'C',kind:'requirement',title:'Shared target'}],edges:Array.from({length:8},(_,i)=>[{id:'drive'+i,from:'R',to:'D'+i,type:'DRIVES'},{id:'intro'+i,from:'D'+i,to:'C',type:'INTRODUCES',parent:'R'}]).flat()};
 await page.evaluate(g=>{globalThis.denseGraph=g},dense);
 await page.evaluate(async()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot,p=s.getElementById('picker'),dt=new DataTransfer();dt.items.add(new File([JSON.stringify(denseGraph)],'dense.json',{type:'application/json'}));p.files=dt.files;p.dispatchEvent(new Event('change'));});
 await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('.node').length===10);await click('fit');evidence.denseLabels=await checkLabels();await shot('07-many-incoming');
 assert.deepEqual(errors,[]);evidence.pageErrors=errors;fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack);process.exitCode=1});
