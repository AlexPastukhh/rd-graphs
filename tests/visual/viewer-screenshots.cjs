const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),cp=require('node:child_process');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const root=path.resolve(__dirname,'../..'),out=path.resolve(process.env.RDG_SCREENSHOT_DIR||'/workspace/repo/rdg-interaction-output');
fs.mkdirSync(out,{recursive:true});
const sharedFile=path.join(out,'test-shared-layouts.json'),commandsFile=path.join(out,'test-layout-commands.json');
const core=require('../../tools/rdg-layout-core.js');
const initialLayout=core.validate(JSON.parse(fs.readFileSync(path.join(root,'graphs/layouts.json'),'utf8'))),initialRevision=initialLayout.revision;
fs.writeFileSync(sharedFile,JSON.stringify(initialLayout));
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--allow-file-access-from-files'],userDataDir:path.join(out,'isolated-profile')});
 const page=await browser.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});page.on('requestfailed',r=>errors.push(r.failure()?.errorText));
 await page.exposeFunction('rdgReadLayoutFile',()=>fs.readFileSync(sharedFile,'utf8'));
 await page.exposeFunction('rdgWriteLayoutFile',text=>{const tmp=sharedFile+'.tmp';fs.writeFileSync(tmp,text);fs.renameSync(tmp,sharedFile)});
 await page.evaluateOnNewDocument(()=>{
  // Test adapter only: real shared JSON on disk, no access to a user desktop.
  const handle={name:'layouts.json',getFile:async()=>({text:()=>globalThis.rdgReadLayoutFile()}),createWritable:async()=>{let buffer='';return {write:async text=>{buffer=text},close:()=>globalThis.rdgWriteLayoutFile(buffer),abort:async()=>{}}}};
  window.showSaveFilePicker=async()=>handle;window.showOpenFilePicker=async()=>[handle];
  globalThis.GM_xmlhttpRequest=details=>{
   if(!details.url.endsWith('/layouts.json'))return details.onerror({});
   globalThis.rdgReadLayoutFile().then(responseText=>details.onload({status:0,responseText}),e=>details.onerror(e));
  };
 });
 await page.setViewport({width:1440,height:900,deviceScaleFactor:1});
 const go=async()=>{await page.goto('file://'+path.join(__dirname,'rdg-viewer.html'),{waitUntil:'load'});await page.waitForFunction(()=>!!document.querySelector('#rdg-viewer-root')?.shadowRoot?.querySelector('[data-folder="examples"]'));};
 const click=async selector=>{
  const b=await page.evaluate(sel=>{const n=document.querySelector('#rdg-viewer-root').shadowRoot.querySelector(sel);if(!n)return null;const r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,h:r.height}},selector);
  assert(b&&b.w&&b.h&&b.x>0&&b.x<page.viewport().width&&b.y>0&&b.y<page.viewport().height,'not visible: '+selector+' '+JSON.stringify(b));
  await page.mouse.click(b.x,b.y);await new Promise(r=>setTimeout(r,210));
 };
 const has=async id=>page.evaluate(id=>!!document.querySelector('#rdg-viewer-root').shadowRoot.querySelector('#canvas [data-id="'+id+'"]'),id);
 const ids=async()=>page.evaluate(()=>[...document.querySelector('#rdg-viewer-root').shadowRoot.querySelectorAll('#canvas .node')].map(n=>n.getAttribute('data-id')));
 const focus=async id=>{await page.evaluate(id=>{const s=document.querySelector('#rdg-viewer-root').shadowRoot,n=s.querySelector('#search');n.value=id;n.dispatchEvent(new Event('input'));n.value='';n.dispatchEvent(new Event('input'))},id);};
 const openNode=async id=>{await focus(id);await click('#canvas [data-id="'+id+'"]');};
 const camera=async()=>page.evaluate(()=>document.querySelector('#rdg-viewer-root').shadowRoot.querySelector('#scene').getAttribute('transform'));
 const world=async id=>page.evaluate(id=>document.querySelector('#rdg-viewer-root').shadowRoot.querySelector('#canvas [data-id="'+id+'"]').getAttribute('transform'),id);
 const info=async()=>page.evaluate(()=>document.querySelector('#rdg-viewer-root').shadowRoot.querySelector('#info').textContent);
 const shot=async name=>{
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'document overflow '+name);
  const bad=await page.evaluate(()=>[...document.querySelector('#rdg-viewer-root').shadowRoot.querySelectorAll('#canvas .node')].filter(n=>{const a=n.querySelector('.node-kind'),b=n.querySelector('.qrpe-badge,.guide-badge');return a&&b&&a.getBBox().x+a.getBBox().width>b.getBBox().x}).map(n=>n.getAttribute('data-id')));
  assert.deepEqual(bad,[],'heading overlaps badge '+name);
  await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});console.log('SCREEN',name);
 };
 const openPrepared=async()=>{await click('#launch');await click('[data-folder="examples"]');await click('[data-set="example-prepared"]');await openNode('reference-prepared-planning-tree');};
 try{
  await go();await click('#launch');await shot('00-folders');await click('[data-folder="examples"]');await shot('01-example-cards');
  await click('[data-set="example-prepared"]');await openNode('reference-prepared-planning-tree');
  for(const id of ['RF-1','RF-2','RS-1','RS-2'])assert(await has(id));
  assert(!(await has('RF-1-O1'))&&!(await has('RF-DEEP'))&&!(await has('__collection__FEATURE-POTENTIAL')));
  await shot('02-prepared-one-level');
  await openNode('__canon__O-FEATURE');assert((await info()).includes('Канонические ситуации (+)'));await shot('03-prepared-canon');
  await openNode('RF-1');assert(await has('RF-1-O1'));assert(!(await has('RF-DEEP-O1')));await shot('04-child-one-level');
  await openNode('RF-DEEP');assert(await has('RF-DEEP-O1'));await shot('05-grandchild');
  await click('#level-up');await click('#level-up');assert(await has('RF-1'));assert(!(await has('RF-1-O1')));
  await click('#example-set-map');
  assert.equal(await page.evaluate(()=>document.querySelector('#rdg-viewer-root').shadowRoot.querySelectorAll('#canvas .node.graph').length),6);await shot('06-prepared-map');
  await click('#back');await click('[data-set="example-working"]');assert.equal(await page.evaluate(()=>document.querySelector('#rdg-viewer-root').shadowRoot.querySelectorAll('#canvas .node.graph').length),5);await shot('07-working-map');
  // The root of a large map can be below the first viewport; cards remain a direct entry.
  await openNode('reference-mixed-active-work');
  assert(await has('R-COMP'));assert(!(await has('D-A'))&&!(await has('R-ACT-1')));
  for(const id of ['R-TECH','R-DEADLINE','R-LEGACY-API'])assert(await has(id));
  await shot('08-working-root-one-level');
  await openNode('R-COMP');assert(await has('D-A'));assert(await has('R-ACT-1'));await shot('09-contextual-root');
  await openNode('D-A');assert((await info()).includes('"version": "3"'));await shot('10-selected-decision-history');
  await openNode('R-ACT-1');assert(await has('O-ACT-1')&&await has('O-ACT-2'));await shot('11-undecided-child');
  await click('#level-up');await click('#level-up');await click('#variants-all');
  assert(await has('O-B')&&await has('O-C'));assert(await has('P-RF-1'));assert(!(await has('P-RF-1-O1')));await shot('12-working-alternatives');
  await focus('__collection__COL-FEATURE');const before=await ids(),beforeCamera=await camera(),rootBefore=await world('R0'),optionBefore=await world('O-A');
  await click('#canvas [data-id="__collection__COL-FEATURE"]');
  assert(!(await has('__collection__COL-FEATURE')));assert.equal(await camera(),beforeCamera);assert.equal(await world('R0'),rootBefore);assert.equal(await world('O-A'),optionBefore);
  const revealed=(await ids()).filter(id=>!before.includes(id));assert.deepEqual(revealed.sort(),Array.from({length:10},(_,i)=>'R-PREV-FEATURE-'+(i+1)).sort());
  await shot('13-open-list-header-gone');
  await openNode('__collection__COL-SCENARIO');assert(!(await has('__collection__COL-SCENARIO')));await shot('14-two-lists-open');
  await click('#collections-collapse');for(const id of ['COL-FEATURE','COL-SCENARIO'])assert(await has('__collection__'+id));assert(!(await has('R-PREV-FEATURE-1')));await shot('15-lists-collapsed');
  // Direct pointer drag at a non-unit zoom: no click, navigation or viewport pan.
  await click('#example-set-map');await click('#back');await click('[data-set="example-prepared"]');await openNode('reference-prepared-planning-tree');
  await page.mouse.move(500,400);await page.keyboard.down('Control');await page.mouse.wheel({deltaY:-160});await page.keyboard.up('Control');await new Promise(r=>setTimeout(r,100));
  const beforeDrag=await camera(),rootBeforeDrag=(await world('R-PLAN')).match(/[-\d.]+/g).map(Number),dragScale=Number(beforeDrag.match(/scale\(([^)]+)\)/)[1]);
  assert.notEqual(dragScale,1,'drag must also work after zoom');
  const box=await page.evaluate(()=>{const r=document.querySelector('#rdg-viewer-root').shadowRoot.querySelector('#canvas [data-id="R-PLAN"]').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}});
  await page.mouse.move(box.x,box.y);await page.mouse.down();await page.mouse.move(box.x+95,box.y+45,{steps:12});await page.mouse.up();
  assert.equal(await camera(),beforeDrag,'node drag must not pan');
  const preview=await page.evaluate(()=>{const a=document.querySelector('#rdg-viewer-root').rdgLayout;return a.getDocument().layouts[a.graphKey()].positions['R-PLAN']});assert(preview);assert(Math.abs(preview.x-rootBeforeDrag[0]-95/dragScale)<.02&&Math.abs(preview.y-rootBeforeDrag[1]-45/dragScale)<.02,'browser pointer displacement must use graph zoom');
  await shot('16-node-drag-preview');
  await click('#layout-controls summary');await click('#layout-save');
  assert.equal(JSON.parse(fs.readFileSync(sharedFile)).revision,initialRevision+1);assert.deepEqual(JSON.parse(fs.readFileSync(sharedFile)).layouts[core.graphKey('rdg-example-prepared-v7','reference-prepared-planning-tree')].positions['R-PLAN'],preview);await shot('17-layout-saved');
  await page.reload({waitUntil:'load'});await page.waitForFunction(()=>!!document.querySelector('#rdg-viewer-root')?.shadowRoot?.querySelector('[data-folder="examples"]'));
  await openPrepared();assert.equal(await world('R-PLAN'),'translate('+preview.x+' '+preview.y+')');await shot('17a-user-layout-after-reload');
  await click('#layout-controls summary');await click('#layout-open');
  // AI/CLI writes the very same file; an already-open UI must reject stale writes.
  const key=core.graphKey('rdg-example-prepared-v7','reference-prepared-planning-tree');
  fs.writeFileSync(commandsFile,JSON.stringify({type:'set_positions',graphKey:key,positions:{'R-PLAN':{x:110,y:120}}}));
  cp.execFileSync(process.execPath,[path.join(root,'tools/rdg-layout-cli.cjs'),'--file',sharedFile,'--expect-revision',String(initialRevision+1),'--commands-file',commandsFile]);
  await page.evaluate(()=>document.querySelector('#rdg-viewer-root').rdgLayout.apply({type:'set_positions',positions:{'R-PLAN':{x:330,y:220}}}));
  await click('#layout-save');
  assert(await page.evaluate(()=>document.querySelector('#rdg-viewer-root').shadowRoot.querySelector('#message').textContent.includes('изменён извне')));assert.equal(JSON.parse(fs.readFileSync(sharedFile)).revision,initialRevision+2);await shot('18-external-change-protected');
  await click('#layout-discard');await click('#layout-open');assert.equal(await world('R-PLAN'),'translate(110 120)');await shot('19-cli-layout-read');
  await page.reload({waitUntil:'load'});await page.waitForFunction(()=>!!document.querySelector('#rdg-viewer-root')?.shadowRoot?.querySelector('[data-folder="examples"]'));await openPrepared();assert.equal(await world('R-PLAN'),'translate(110 120)');await shot('20-layout-after-reload');
  await page.setViewport({width:900,height:740,deviceScaleFactor:1});await openNode('__canon__O-FEATURE');await shot('21-inspector-900');
  await page.setViewport({width:390,height:844,deviceScaleFactor:1});await shot('22-mobile-canon');
  assert(await page.evaluate(()=>{const s=document.querySelector('#rdg-viewer-root').shadowRoot,c=s.querySelector('#canvas').getBoundingClientRect(),i=s.querySelector('#info').getBoundingClientRect();return c.height>=200&&i.bottom<=innerHeight}));
  await click('#example-set-map');await shot('23-mobile-prepared-map');await click('#back');await click('[data-set="example-working"]');await shot('24-mobile-working-map');
   await click('#fit');assert(await page.evaluate(()=>{const s=document.querySelector('#rdg-viewer-root').shadowRoot,m=s.querySelector('#canvas').getBoundingClientRect();return [...s.querySelectorAll('#canvas .node')].every(n=>{const r=n.getBoundingClientRect();return r.left>=m.left-1&&r.right<=m.right+1&&r.top>=m.top-1&&r.bottom<=m.bottom+1})}));
   await click('#back');await shot('25-mobile-explorer');
   await click('[data-set="example-working"]');await openNode('reference-mixed-active-work');await shot('26-mobile-working-root');
  await openNode('R-COMP');await openNode('D-A');await shot('27-mobile-selected-D');
  await page.setViewport({width:390,height:600,deviceScaleFactor:1});await shot('28-mobile-short');
  assert(await page.evaluate(()=>{const s=document.querySelector('#rdg-viewer-root').shadowRoot;return s.querySelector('#panel').getBoundingClientRect().bottom<=innerHeight&&s.querySelector('#info').getBoundingClientRect().bottom<=innerHeight}));
  assert.deepEqual(errors,[],'browser errors');console.log('VISUAL_HARNESS_PASS',out);
 }finally{await browser.close()}
})().catch(e=>{console.error('VISUAL_HARNESS_FAIL',e.stack);process.exitCode=1});
