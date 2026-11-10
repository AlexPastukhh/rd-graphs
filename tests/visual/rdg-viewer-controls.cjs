'use strict';
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const published=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../tools/rdg-published-owners.json'),'utf8')).owners['requirements-dependencies-demo'];
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell',
  headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--allow-file-access-from-files']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));
  const inspect=()=>page.evaluate(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot,$=id=>s.getElementById(id);
   const visible=el=>!!el&&getComputedStyle(el).display!=='none'&&!el.hidden;
   return {version:$('viewer-version').textContent,tabs:[...s.querySelectorAll('#view-tabs [role=tab]')].map(b=>b.textContent),
    obsolete:!!$('workflow-example'),back:visible($('back')),map:visible($('example-set-map')),
    edges:visible($('edges-core')),edgesMode:$('edges-mode').value,edgeAll:$('edges-all').getAttribute('aria-pressed'),
    fit:visible($('fit')),search:visible($('search')),more:visible($('viewer-more')),
    settings:visible($('view-options')),layoutStatus:$('layout-status').textContent,
    graph:visible($('graph-pane')),plan:visible($('workflow-page')),
    crumb:s.getElementById('breadcrumbs').textContent,help:$('workflow-help').textContent,
    canvasHeight:$('canvas-wrap').getBoundingClientRect().height};
  });
  const act=(fn,arg)=>page.evaluate(fn,arg);
  await page.setViewport({width:1460,height:920});
  const planOwner=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../plans/requirements-dependencies-demo/plan.json'),'utf8'));
  await page.evaluateOnNewDocument(store=>{
   window.GM_xmlhttpRequest=req=>queueMicrotask(()=>req.url.endsWith('/plans/requirements-dependencies-demo/plan.json')?
     req.onload({status:200,responseText:JSON.stringify(store)}):req.onerror({}));
  },planOwner);
  await page.goto('file://'+path.join(__dirname,'rdg-viewer.html'),{waitUntil:'load'});
  await page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  await act(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('launch').click());
  await act(()=>document.getElementById('rdg-viewer-root').rdgExplorer.openFull('requirements-dependencies-demo'));
  const start=await inspect();
  const version=fs.readFileSync(path.resolve(__dirname,'../../tools/rd-graph-viewer.user.js'),'utf8').match(/^\/\/ @version\s+(\d+\.\d+\.\d+)/m)?.[1];
  assert(version,'Viewer source has no @version');
  assert.equal(start.version,'Viewer v'+version);assert.deepEqual(start.tabs,['Граф','План во времени','Зависимости']);
  assert.equal(start.obsolete,false);assert.equal(start.back,false);assert.equal(start.map,false);
  assert.equal(start.edges,false);assert.equal(start.edgesMode,'core');
  console.log('GRAPH_CONTROLS_242',JSON.stringify(start));
  assert(start.fit&&start.search&&start.settings&&start.more&&start.graph);
  console.log('CONTROL_INITIAL_GEOMETRY',JSON.stringify(start));assert(start.canvasHeight>350,'graph has a usable canvas');
  assert.match(start.crumb,/Папки.*Рабочий пример/);
  assert.doesNotMatch(start.help,/предварительн.*план/i);
  await act(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot,select=s.getElementById('edges-mode');
   select.value='all';select.dispatchEvent(new Event('change',{bubbles:true}));
  });
  let view=await inspect();assert.equal(view.edgesMode,'all');assert.equal(view.edgeAll,'true');
  await act(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   s.getElementById('variants-all').click();s.getElementById('view-options').open=true;
  });
  const controls=await act(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot,$=id=>s.getElementById(id);
   return {variant:$('variants-all').textContent,optionsOpen:$('view-options').open,
    context:$('context-fields').getBoundingClientRect().height,layout:$('layout-controls').getBoundingClientRect().height,
    help:$('graph-help').getBoundingClientRect().height,menuVisible:$('view-options').querySelector('.view-options-body').getBoundingClientRect().height};
  });
  assert.match(controls.variant,/Варианты:/);assert(controls.optionsOpen&&controls.context>0&&controls.layout>0&&controls.help>0&&controls.menuVisible>60);
  await act(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('context-fields').click());
  assert(await act(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('content').classList.contains('info-open')));
  await act(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   s.getElementById('view-options').open=false;s.getElementById('viewer-more').open=true;
  });
  const overflow=await act(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot,$=id=>s.getElementById(id);
   return {file:$('file').textContent,refresh:$('reload').textContent,refreshVisible:getComputedStyle($('reload')).display!=='none',
     menuHeight:s.querySelector('.viewer-more-actions').getBoundingClientRect().height};
  });
  assert.match(overflow.file,/JSON/);assert.match(overflow.refresh,/Перечитать/);assert(overflow.refreshVisible&&overflow.menuHeight>45);
  await act(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('dependency-toggle').click());
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot
    .getElementById('dependency-status').textContent.includes('ОПУБЛИКОВАННЫЙ СНИМОК'));
  assert.match(await act(()=>document.getElementById('rdg-viewer-root').shadowRoot
    .getElementById('dependency-status').textContent),/НЕ текущая проверка/);
  assert.equal(await act(()=>document.getElementById('rdg-viewer-root').shadowRoot
    .querySelectorAll('.dep-item[data-status="review_required"]').length),published.dependencies.rows.filter(r=>r.status==='review_required').length,
    'published Gendocen review statuses are real snapshot receipts, never invented availability');
  await act(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-toggle').click());
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-panel').textContent.includes('История'));
  view=await inspect();assert(!view.graph&&view.plan);
  const planOverflow=await act(()=>getComputedStyle(document.getElementById('rdg-viewer-root').shadowRoot.getElementById('viewer-more')).display);
  assert.equal(planOverflow,'none','file controls must not overlay a Plan');
  assert.doesNotMatch(view.help,/предварительн.*план/i);
  await act(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('graph-tab').click());
  await page.setViewport({width:400,height:850});
  await act(()=>{
    const s=document.getElementById('rdg-viewer-root').shadowRoot;
    s.getElementById('view-options').open=true;s.getElementById('layout-controls').open=true;
  });
  const mobile=await act(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot,$=id=>s.getElementById(id);
   const rect=$('view-options').querySelector('.view-options-body').getBoundingClientRect();
   return {canvas:$('canvas-wrap').getBoundingClientRect().height,toolbar:$('edge-toolbar').getBoundingClientRect().height,
    menu:{left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom,width:rect.width,height:rect.height},
    screen:{w:innerWidth,h:innerHeight},layout:$('layout-controls').open,
    more:$('viewer-more').open};
  });
  console.log('MOBILE_CONTROLS_GEOMETRY',JSON.stringify(mobile));assert(mobile.canvas>210,'mobile graph canvas must remain usable');
  assert(mobile.menu.left>=-2&&mobile.menu.right<=mobile.screen.w+2,'settings popup stays horizontally in viewport');
  assert(mobile.menu.height>85&&mobile.layout,'layout settings must remain accessible on mobile');
  const moreMobile=await act(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   s.getElementById('view-options').open=false;
   s.getElementById('viewer-more').open=true;
   const box=s.querySelector('.viewer-more-actions').getBoundingClientRect();
   return {left:box.left,right:box.right,top:box.top,bottom:box.bottom,
    refreshVisible:getComputedStyle(s.getElementById('reload')).display!=='none'};
  });
  assert(moreMobile.left>=-2&&moreMobile.right<=mobile.screen.w+2,'mobile overflow menu stays inside screen');
  assert(moreMobile.refreshVisible,'refresh remains in the overflow menu');
  await act(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('breadcrumbs').querySelector('button').click());
  assert(await act(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('catalog').hidden===false),
    'breadcrumb remains the primary return route, without duplicate Back buttons');
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('BROWSER_VIEWER_240_CONTROLS_PASS',JSON.stringify({desktop:start.canvasHeight,menu:controls.menuVisible,mobile}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
