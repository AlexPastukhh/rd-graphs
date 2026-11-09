'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require('/opt/dc/node_modules/puppeteer-core');
const root=path.resolve(__dirname,'../../..'),out=__dirname;
(async()=>{
 const browser=await puppeteer.launch({executablePath:'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell',
  args:['--no-sandbox','--disable-dev-shm-usage','--allow-file-access-from-files']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewport({width:1440,height:900});await page.goto('file://'+path.join(root,'tests/visual/rdg-viewer.html'));
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  const click=id=>page.evaluate(id=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById(id).click(),id);
  await click('launch');
  await page.evaluate(()=>document.getElementById('rdg-viewer-root').rdgExplorer.openFull('reference-action-time-plan'));
  await click('edges-all');await click('fit');await page.screenshot({path:path.join(out,'action-full-map.png')});
  // Property links in full mode remain inspectable and have no arrow.
  await page.evaluate(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot,e=s.querySelector('.canon-attachment');
   if(!e||e.hasAttribute('marker-end'))throw Error('Missing property connector');e.dispatchEvent(new MouseEvent('click',{bubbles:true}));
  });
  await click('workflow-example');
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-history .wf-card'));
  const before=await page.evaluate(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   const h=s.querySelector('.wf-history [data-node-id="A-LOCAL"][data-event-kind="action_executed"]');
   const placements=[...s.querySelectorAll('.wf-future [data-context="placement"]')].map(n=>n.dataset.nodeId);
   return {history:h?.textContent,placements,editor:s.querySelector('.wf-editor').hidden,
    graphEditor:s.getElementById('workflow-graph-toggle').hidden,connection:s.getElementById('workflow-connection').textContent};
  });
  assert.match(before.history,/Устройство личное/);assert.doesNotMatch(before.history,/После проверки политики/);
  assert.match(before.history,/Канон на момент записи/);
  assert.deepEqual(new Set(before.placements),new Set(['R-INPUT','R-SEND','A-IDEMPOTENT','A-SERVER']));
  assert(before.editor);assert.match(before.connection,/только чтение/);
  await page.screenshot({path:path.join(out,'action-history.png')});
  await page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-jump-plan').click());
  await page.waitForFunction(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot,p=s.getElementById('workflow-page'),
    first=s.querySelector('.wf-future [data-context="placement"]'),bar=s.querySelector('.wf-toolbar');
   return p.scrollTop>0&&Math.abs(first.getBoundingClientRect().top-
     (p.getBoundingClientRect().top+bar.getBoundingClientRect().height+16))<2;
  });
  await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  await page.screenshot({path:path.join(out,'action-plan.png')});
  await page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-future [data-context="placement"][data-node-id="R-INPUT"] .wf-card-title').click());
  await page.waitForFunction(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;return !s.getElementById('graph-pane').hidden&&s.querySelector('.node.selected')?.dataset.id==='R-INPUT';});
  const goal=await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;return {root:s.querySelector('.node.root')?.dataset.id,selected:s.querySelector('.node.selected')?.dataset.id};});
  assert.deepEqual(goal,{root:'R0',selected:'R-INPUT'});
  await click('workflow-toggle');
  await page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-history [data-node-id="A-LOCAL"][data-event-kind="action_executed"] .wf-open-graph').click());
  await page.waitForFunction(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;return !s.getElementById('graph-pane').hidden&&s.querySelector('.node.selected')?.dataset.id==='A-LOCAL';});
  const historical=await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;return {root:s.querySelector('.node.root')?.dataset.id,selected:s.querySelector('.node.selected')?.dataset.id,info:s.getElementById('info').textContent};});
  assert.equal(historical.root,'R-INPUT');assert.match(historical.info,/superseded/);
  await page.screenshot({path:path.join(out,'action-history-in-graph.png')});
  await click('workflow-toggle');await page.setViewport({width:390,height:844});
  const mobile=await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot,p=s.getElementById('workflow-page');return {overflow:p.scrollWidth-p.clientWidth};});
  assert(mobile.overflow<=1);await page.screenshot({path:path.join(out,'action-mobile.png')});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'action-browser-results.json'),JSON.stringify({version:'2.3.0',errors,before,goal,historical,mobile},null,2));
  console.log('ACTION_BROWSER_PASS: history snapshot, explicit placements, canonical R/withdrawn Action navigation, mobile');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
