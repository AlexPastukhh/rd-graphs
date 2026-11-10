'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),puppeteer=require('/opt/dc/node_modules/puppeteer-core');
const out=process.env.RDG_SCREENSHOT_DIR,slug='reference-prepared-planning-tree';fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--allow-file-access-from-files'],userDataDir:path.join(out,'profile')});
 const errors=[],result={version:'1.6.1'};
 const boot=async p=>{p.on('pageerror',e=>errors.push(e.stack));p.on('dialog',d=>d.accept());await p.setViewport({width:1440,height:900});await p.goto('file://'+path.join(__dirname,'rdg-viewer.html'));await p.waitForFunction(()=>document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());await p.evaluate(()=>{const h=document.getElementById('rdg-viewer-root');h.shadowRoot.getElementById('launch').click();return h.rdgExplorer.openSet('example-prepared')});};
 const state=p=>p.evaluate(()=>{const h=document.getElementById('rdg-viewer-root');return {...h.rdgLayout.status(),text:h.shadowRoot.getElementById('layout-status').textContent}});
 try{
 const a=await browser.newPage();await boot(a);const before=await state(a);
 const box=await a.evaluate(slug=>{const s=document.getElementById('rdg-viewer-root').shadowRoot,q=s.getElementById('search');q.value=slug;q.dispatchEvent(new Event('input'));q.value='';q.dispatchEvent(new Event('input'));const b=s.querySelector('[data-id="'+slug+'"]').getBoundingClientRect();return{x:b.x+b.width/2,y:b.y+b.height/2}},slug);
 await a.mouse.move(box.x,box.y);await a.mouse.down();await a.mouse.move(box.x+80,box.y+35,{steps:10});await a.mouse.up();assert.match((await state(a)).text,/Изменения не записаны/);assert.notEqual((await state(a)).text,before.text);await a.screenshot({path:path.join(out,'01-unsaved-visible.png')});
 await a.evaluate(async()=>{const h=document.getElementById('rdg-viewer-root'),api=h.rdgLayout;h.shadowRoot.getElementById('layout-discard').click();const dir=await navigator.storage.getDirectory(),file=await dir.getFileHandle('fixes-layouts.json',{create:true}),w=await file.createWritable();await w.write(JSON.stringify(api.getDocument()));await w.close();await api.attachFile(file);});
 const copied=await a.evaluate(()=>Object.fromEntries(Object.entries(sessionStorage))),b=await browser.newPage();
 await b.evaluateOnNewDocument(values=>{for(const [k,v] of Object.entries(values))sessionStorage.setItem(k,v)},copied);await boot(b);assert.equal((await state(b)).dirty,false);
 for(const [p,x] of [[a,101],[b,901]])await p.evaluate(({slug,x})=>{const api=document.getElementById('rdg-viewer-root').rdgLayout;api.pause();api.apply({type:'set_positions',positions:{[slug]:{x,y:x+1}}})},{slug,x});
 const ownA=(await a.evaluate(()=>document.getElementById('rdg-viewer-root').rdgLayout.drafts())).find(d=>d.own),ownB=(await b.evaluate(()=>document.getElementById('rdg-viewer-root').rdgLayout.drafts())).find(d=>d.own);assert(ownA&&ownB);assert.notEqual(ownA.id,ownB.id);
 await b.evaluate(()=>document.getElementById('rdg-viewer-root').rdgLayout.save());assert.equal((await state(b)).dirty,false);
 const stored=await b.evaluate(async key=>new Promise((resolve,reject)=>{const r=indexedDB.open('rdg-layout-files',1);r.onsuccess=()=>{const db=r.result,q=db.transaction('handles').objectStore('handles').get(key);q.onsuccess=()=>{db.close();resolve(q.result)};q.onerror=()=>reject(q.error)};r.onerror=()=>reject(r.error)}),ownA.id);assert.equal(stored.commands[0].positions[slug].x,101);
 await a.reload();await a.waitForFunction(()=>document.getElementById('rdg-viewer-root')?.rdgLayout?.status().dirty);assert.match((await state(a)).blocked,/Конфликт/);await a.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('launch').click());await a.screenshot({path:path.join(out,'02-tab-draft-restored.png')});
 await b.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;s.getElementById('layout-controls').open=true;s.getElementById('layout-drafts').click()});await b.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('layout-draft-list').children.length>0);
 assert.match(await b.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('layout-draft-list').textContent),/Другая вкладка/);
 await b.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('layout-draft-list').firstElementChild.click());await b.waitForFunction(()=>document.getElementById('rdg-viewer-root').rdgLayout.status().dirty);
 assert((await b.evaluate(()=>document.getElementById('rdg-viewer-root').rdgLayout.drafts())).some(d=>d.id===ownA.id));assert.deepEqual(errors,[]);
 Object.assign(result,{duplicateTabOwnersDistinct:true,otherTabDraftRetainedInIndexedDB:true,reloadRestoresOwnDraftWithConflict:true,explicitRecoveryPreservesSource:true,pageErrors:errors});fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack);process.exitCode=1});
