'use strict';
// Full graph retains a two-mode projection; each one-wave local R graph
// shows every accepted relationship by default WITHOUT a redundant selector.
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--allow-file-access-from-files']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewport({width:1360,height:870});
  await page.goto('file://'+path.join(__dirname,'rdg-viewer.html'),{waitUntil:'load'});
  await page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  const inspect=()=>page.evaluate(()=>{
   const h=document.getElementById('rdg-viewer-root'),s=h.shadowRoot,$=id=>s.getElementById(id);
   const nodes=[...s.querySelectorAll('g.node')],arcs=[...s.querySelectorAll('path.edge[data-edge-id]')];
   return {version:$('viewer-version').textContent,scope:$('graph-scope-hint').textContent,
    selectorHidden:$('edges-selector').hidden,
    selectorDisplay:getComputedStyle($('edges-selector')).display,
    modes:[...$('edges-mode').options].map(o=>o.textContent),
    nodes:nodes.map(n=>({id:n.getAttribute('data-id'),kind:n.getAttribute('data-view-role'),
       label:n.getAttribute('aria-label'),inset:!!n.querySelector('rect.requirement-graph-outline')})),
    arcs:arcs.map(a=>a.getAttribute('data-edge-id')),
    selectedMode:$('edges-mode').value};
  });
  await page.evaluate(async()=>{
   const h=document.getElementById('rdg-viewer-root');h.shadowRoot.getElementById('launch').click();
   await h.rdgExplorer.openFull('requirements-dependencies-demo');
  });
  const overview=await inspect();
  const version=fs.readFileSync(path.resolve(__dirname,'../../tools/rd-graph-viewer.user.js'),'utf8').match(/^\/\/ @version\s+(\d+\.\d+\.\d+)/m)?.[1];
  assert(version,'Viewer source has no @version');
  assert.equal(overview.version,'Viewer v'+version);
  assert.equal(overview.selectorHidden,false);
  assert.deepEqual(overview.modes,['Графы Requirements','Графы + Actions и каноны']);
  assert(overview.nodes.length>=3);
  assert(overview.nodes.every(n=>n.kind==='requirement-graph'&&n.inset));
  await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot,
    mode=s.getElementById('edges-mode');mode.value='all';mode.dispatchEvent(new Event('change',{bubbles:true}));});
  const detailed=await inspect();
  assert(detailed.nodes.some(n=>n.kind==='action'));
  assert(detailed.nodes.some(n=>n.kind==='requirement-graph'));
  async function openRFromOverview(rid){
   await page.evaluate(async id=>{
    const h=document.getElementById('rdg-viewer-root');
    await h.rdgExplorer.openFull('requirements-dependencies-demo');
    h.shadowRoot.querySelector('g.node.requirement-graph[data-id="'+id+'"]')
      .dispatchEvent(new MouseEvent('click',{bubbles:true}));
   },rid);
   await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot
     .getElementById('graph-scope-hint').textContent.includes('ЛОКАЛЬНЫЙ ГРАФ ОДНОЙ ВОЛНЫ'),{timeout:12000});
   return inspect();
  }
  for(const [rid,action] of [['R0','A-DESIGN'],['R-CANON','A-CANON'],['R-VERIFY','A-VERIFY']]){
   const local=await openRFromOverview(rid);
   assert.equal(local.selectorHidden,true,'no relation-mode selector in a one-wave local graph');
   assert.equal(local.selectorDisplay,'none','CSS also hides old select');
   assert.equal(local.selectedMode,'all','local mode is always the complete relation view');
   assert.match(local.scope,/все отношения/);
   assert(local.nodes.some(n=>n.id===rid&&n.kind==='requirement'));
   assert(local.nodes.some(n=>n.id===action&&n.kind==='action'));
   assert(local.nodes.every(n=>n.kind!=='requirement-graph'));
   assert(!local.nodes.some(n=>n.id==='C-ASSURANCE'),'retired artificial context not presented');
   assert(!local.arcs.some(id=>id.startsWith('context-for-')),'archived Context links not shown');
   // Old hidden selector cannot sneak in a second local rendering mode, even
   // under programmatic change or a stale UI saved preference.
   await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot,
    mode=s.getElementById('edges-mode');mode.value='core';mode.dispatchEvent(new Event('change',{bubbles:true}));});
   const after=await inspect();
   assert.deepEqual(after.nodes,local.nodes);
   assert.deepEqual(after.arcs,local.arcs);
  }
  // From the local root, an R child still opens its own one-wave view.
  await openRFromOverview('R0');
  await page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot
   .querySelector('g.node.requirement[data-id="R-CANON"]').dispatchEvent(new MouseEvent('click',{bubbles:true})));
  await page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root').shadowRoot
   .querySelector('g.node.action[data-id="A-CANON"]'),{timeout:12000});
  const nextWave=await inspect();
  assert(nextWave.selectorHidden&&nextWave.nodes.some(n=>n.id==='A-CANON'));
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('BROWSER_LOCAL_ONE_WAVE_ALWAYS_FULL_AND_FULL_GRAPH_SWITCH_PASS',JSON.stringify({
   overviewGraphs:overview.nodes.length,fullDetailedActions:detailed.nodes.filter(n=>n.kind==='action').length,
   localRoots:['R0','R-CANON','R-VERIFY'],localSelectorRemoved:true,
   retiredContextHidden:true,childNavigation:true,pageerrors:errors.length}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
