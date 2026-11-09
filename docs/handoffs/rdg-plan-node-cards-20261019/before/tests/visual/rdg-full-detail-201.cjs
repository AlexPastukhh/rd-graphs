'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const output=path.resolve(process.env.RDG_SCREENSHOT_DIR||'/workspace/repo/rdg-201-browser-verification');
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,headless:true,
   args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--allow-file-access-from-files'],
   userDataDir:path.join(output,'headless-profile')});
 try {
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.setViewport({width:1440,height:900});
  await page.goto('file://'+path.join(__dirname,'rdg-viewer.html'),{waitUntil:'load'});
  await page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  const open=slug=>page.evaluate(slug=>document.getElementById('rdg-viewer-root').rdgExplorer.openFull(slug),slug);
  const tap=id=>page.evaluate(id=>{
    const s=document.getElementById('rdg-viewer-root').shadowRoot;
    const node=[...s.querySelectorAll('#canvas .node')].find(n=>n.getAttribute('data-id')===id);
    if(!node)throw Error('No visible node '+id);node.dispatchEvent(new MouseEvent('click',{bubbles:true}));
    return s.querySelector('#info').textContent;
  },id);
  const button=id=>page.evaluate(id=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById(id).click(),id);
  const countRefine=()=>page.evaluate(()=>[...document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('#canvas path[data-relation-kind="refinement"]')].length);
  const nodes=()=>page.evaluate(()=>[...document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('#canvas .node')].map(n=>n.getAttribute('data-id')));
  const screen=async(name)=>page.screenshot({path:path.join(output,name+'.png')});
  assert.equal(await page.evaluate(()=>document.getElementById('rdg-viewer-root').dataset.rdgVersion),'2.2.4');
  await open('reference-prepared-planning-tree');
  assert((await nodes()).includes('RF-DEEP'),'complete prepared root covers grandchildren');
  await button('edges-all');
  const option=await tap('__cause__reference-prepared-planning-tree::O-FEATURE');
  assert.match(option,/O-FEATURE · Option/);
  assert.match(option,/Канонические ситуации/);
  assert.doesNotMatch(option,/Requirement ID: __cause__/);
  await screen('prepared-detail-option');
  await open('reference-mixed-active-work');
  assert.equal(await countRefine(),1);
  await button('edges-all');
  assert.equal(await countRefine(),1,'DERIVES still visible in detailed');
  const decision=await tap('__cause__reference-mixed-active-work::D-A');
  assert.match(decision,/D-A · Decision/);
  assert.match(decision,/Основание выбора/);
  assert.match(decision,/O-FEATURE-minus-1/);
  assert.match(decision,/QR-A/);
  assert.match(decision,/T1/);
  await screen('working-detail-decision');
  await button('variants-all');
  assert((await nodes()).includes('P-RF-DEEP'),'all branches includes prospective R');
  assert.equal(await countRefine(),1);
  await screen('working-detail-all-branches');
  await button('edges-core');
  assert.equal(await countRefine(),1);
  assert(!(await nodes()).some(n=>n.startsWith('__cause__')),'R-only hides D and O');
  await screen('working-R-only-all-branches');
  assert.deepEqual(errors,[],'no JavaScript page errors');
  console.log('BROWSER_FULL_DETAIL_202_PASS, screenshots: 4, version 2.2.4');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
