/* Viewer E2E: real Plan owner and Graph source, no preliminary Plan or legacy model. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const slug='requirements-dependencies-demo',ref='plans/'+slug+'/plan.json';
const owner=JSON.parse(fs.readFileSync(path.join(__dirname,'../../',ref),'utf8'));
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--allow-file-access-from-files']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewport({width:1240,height:820});
  await page.evaluateOnNewDocument(data=>{
   window.__planAvailable=true;window.__pickerCalls=0;
   window.GM_xmlhttpRequest=req=>queueMicrotask(()=>{
    if(window.__planAvailable&&req.url.endsWith('/plans/requirements-dependencies-demo/plan.json'))
      req.onload({status:200,responseText:JSON.stringify(data)});
    else req.onerror({});
   });
   Object.defineProperty(window,'showDirectoryPicker',{configurable:true,value:async()=>{
    window.__pickerCalls++;throw Error('Unexpected Helper file picker');}});
  },owner);
  await page.goto('file://'+path.join(__dirname,'rdg-viewer.html'),{waitUntil:'load'});
  await page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  await page.evaluate(async slug=>{
   const h=document.getElementById('rdg-viewer-root');h.shadowRoot.getElementById('launch').click();
   await h.rdgExplorer.openFull(slug);h.shadowRoot.getElementById('workflow-toggle').click();
  },slug);
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-connection').textContent.includes('Сохранённый Plan'),{timeout:15000});
  const view=await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;
   return {status:s.getElementById('workflow-connection').textContent,
    history:s.querySelector('.wf-history').textContent,future:s.querySelector('.wf-future').textContent,
    unplaced:s.querySelector('.wf-unplaced')?.textContent,picks:window.__pickerCalls};});
  assert.match(view.status,/из файла/);assert.match(view.history,/Создан Plan/);
  assert.match(view.history,/Размещён шаг Plan|Сохранено размещение/);
  assert.match(view.history,/Переформулирована Requirement|Было/);
  assert.match(view.future,/R-CANON/);assert.match(view.future,/A-CANON/);
  assert.match(view.future,/R-VERIFY/);
  assert.equal(view.picks,0);assert.doesNotMatch(view.history,/Выполнен Action|Достигнута цель/);
  await page.evaluate(()=>{window.__planAvailable=false;});
  await page.evaluate(async slug=>{
   const h=document.getElementById('rdg-viewer-root');h.shadowRoot.getElementById('graph-tab').click();
   await h.rdgExplorer.openFull(slug);h.shadowRoot.getElementById('workflow-toggle').click();
  },slug);
  // A vanished local Plan falls back ONLY to a published, verified
  // read-only snapshot of the very same real Plan owner (never empty fake).
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-connection').textContent.includes('опубликованный снимок'),{timeout:15000});
  const published=await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;return {
   status:s.getElementById('workflow-connection').textContent,
   history:s.querySelector('.wf-history')?.textContent,
   future:s.querySelector('.wf-future')?.textContent};});
  assert.match(published.status,/только чтение/);
  assert.match(published.status,/Данные могут устареть/);
  assert.match(published.history,/Переформулирована/);
  assert.match(published.future,/R-CANON/);
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('REAL_OWNER_ALWAYS_ON_PLAN_PASS',JSON.stringify({steps:owner.versions.at(-1).plan.steps.length,historyContainsReformulation:true,publishedReadOnlyOnDiskFailure:true}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
