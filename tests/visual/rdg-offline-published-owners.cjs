'use strict';
// True disconnected browser: NO Helper, NO accessible file:// Plan.
// Published snapshots must be strictly real owner/engine derived, READ-ONLY.
const path=require('node:path'),assert=require('node:assert/strict'),fs=require('node:fs');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const SLUG='requirements-dependencies-demo';
const published=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../tools/rdg-published-owners.json'),'utf8')).owners[SLUG];
const warningIds=published.dependencies.rows.filter(r=>r.status==='review_required').map(r=>r.nodeId);
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--allow-file-access-from-files']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewport({width:1450,height:920});
  await page.evaluateOnNewDocument(()=>{
   window.__planQueries=[];
   window.GM_xmlhttpRequest=request=>{
    window.__planQueries.push(request.url);
    queueMicrotask(()=>request.onerror({}));
   };
   Object.defineProperty(window,'showDirectoryPicker',{configurable:true,value:async()=>{
    throw Error('A disconnected published-only session must not require a folder');
   }});
  });
  await page.goto('file://'+path.join(__dirname,'rdg-viewer.html'),{waitUntil:'load'});
  await page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  await page.evaluate(async slug=>{
   const host=document.getElementById('rdg-viewer-root');
   host.shadowRoot.getElementById('launch').click();
   await host.rdgExplorer.openFull(slug);
   host.shadowRoot.getElementById('workflow-toggle').click();
  },SLUG);
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-connection').textContent.includes('опубликованный снимок'),{timeout:12000});
  const plan=await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;
   return {status:s.getElementById('workflow-connection').textContent,
    history:s.querySelector('.wf-history')?.textContent||'',future:s.querySelector('.wf-future')?.textContent||'',
    queryCount:window.__planQueries.length,planCards:s.querySelectorAll('.wf-history .wf-card').length};});
  assert.match(plan.status,/только чтение/);assert(plan.status.includes('r'+published.planRevision));
  assert.match(plan.history,/Было/);assert.match(plan.history,/Создан Plan/);
  for(const id of ['R-CANON','R-VERIFY','A-CANON'])assert(plan.future.includes(id),id);
  assert(plan.queryCount>0,'real disk read attempted before fallback');
  await page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('dependency-toggle').click());
  await page.waitForFunction(count=>document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('.dep-item').length===count,{timeout:12000},published.dependencies.rows.filter(r=>r.status!=='valid').length);
  const deps=await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;
   return {status:s.getElementById('dependency-status').textContent,
    warnings:[...s.querySelectorAll('.dep-item[data-status="review_required"] h3')].map(x=>x.textContent),
    opens:s.querySelectorAll('.dep-item details[open]').length,
    navigable:[...s.querySelectorAll('.dep-item button')].filter(b=>!b.disabled).length};});
  assert.match(deps.status,/СНИМОК/);assert.match(deps.status,/НЕ текущая проверка/);
  assert.equal(deps.opens,0);assert(deps.navigable>0);
  assert.equal(deps.warnings.length,warningIds.length);
  for(const id of warningIds)assert(deps.warnings.some(x=>x.includes(id)),id);
  await page.evaluate(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   s.querySelector('.dep-item details').open=true;
  });
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.dep-history')?.textContent.includes('Receipts:'),{timeout:12000});
  const history=await page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.dep-history').textContent);
  assert.match(history,/receipt/);
  // Navigation must work from historical source and dependent Action without
  // needing the live Helper, because these declarations are published already.
  await page.evaluate(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   s.querySelector('.dep-item button:not([disabled])').click();
  });
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('graph-tab').getAttribute('aria-selected')==='true',{timeout:12000});
  const nav=await page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('info').textContent);
  assert.match(nav,/A-CANON|R-CANON/);
  // A user could open an updated Graph with stale embedded owner. The source
  // revision must defeat the older snapshot rather than masquerade as current.
  const snapshotGuard=await page.evaluate(()=>{
   const saved=window.RDG_EMBEDDED_GRAPHS.publishedOwners['requirements-dependencies-demo'];
   return {graphRevision:saved.graphRevision,planRevision:saved.planRevision};
  });
  assert.deepEqual(snapshotGuard,{graphRevision:published.graphRevision,planRevision:published.planRevision});
  // A mismatch in the published Graph revision means NO fallback.
  await page.evaluate(()=>{
   window.RDG_EMBEDDED_GRAPHS.publishedOwners['requirements-dependencies-demo'].graphRevision-=1;
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   s.getElementById('graph-tab').click();
   s.getElementById('workflow-toggle').click();
  });
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-connection').textContent.includes('не открыт'),{timeout:12000});
  const staleStatus=await page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-connection').textContent);
  assert.match(staleStatus,/PLAN_FILE_NOT_FOUND_OR_ACCESS_DENIED/);
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('OFFLINE_PUBLISHED_ACTUAL_PLAN_AND_GENDOCEN_PASS',JSON.stringify({planCards:plan.planCards,history:history.length,warnings:deps.warnings,navigable:deps.navigable,pageerrors:errors.length}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
