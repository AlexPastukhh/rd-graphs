/* Isolated browser QA; directory permissions and Helper replies are simulated. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const output=path.resolve(process.env.RDG_SCREENSHOT_DIR||'/workspace/repo/rdg-workflow-tabs-browser');
const chrome=process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell';
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--allow-file-access-from-files']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewport({width:1440,height:900});
  await page.evaluateOnNewDocument(()=>{
   window.__picks=0;window.__mode='cancel';
   Object.defineProperty(window,'showDirectoryPicker',{configurable:true,value:async()=>{
    window.__picks++;if(window.__mode==='cancel')throw new DOMException('cancelled','AbortError');
    const mode=window.__mode,files=new Map([['session.json',JSON.stringify({schemaVersion:1,kind:'rdg-local-manual-session',
      active:mode!=='expired',...(mode!=='expired'?{session:'synthetic-browser-test'}:{})})]]);
    return {name:'session',queryPermission:async()=>'prompt',requestPermission:async()=>mode==='denied'?'denied':'granted',
      async getFileHandle(name,options={}){
       if(!options.create&&!files.has(name))throw new DOMException('missing','NotFoundError');
       return {getFile:async()=>({text:async()=>files.get(name)}),createWritable:async()=>{let text;return {
        write:async value=>{text=value;},close:async()=>{files.set(name,text);
         if(name.endsWith('.ready')&&mode==='ready')files.set(name.replace('request-','response-').replace('.ready','.json'),
           JSON.stringify({ok:true,result:window.__snapshot}));
        }};}};
      },removeEntry:async name=>{files.delete(name);}};
   }});
  });
  await page.goto('file://'+path.join(__dirname,'rdg-viewer.html'),{waitUntil:'load'});
  await page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  const run=(fn,arg)=>page.evaluate(fn,arg);
  const click=id=>run(id=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;
   if(id==='workflow-connect'){const settings=s.getElementById('workflow-settings');if(settings&&!settings.open)settings.querySelector('summary').click();}
   s.getElementById(id).click();},id);
  const status=()=>run(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-connection').textContent);
  const waitText=async text=>{try{await page.waitForFunction(text=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-panel').textContent.includes(text),{timeout:15000},text);}catch(e){
   console.error('UI_STATE',await status(),await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-panel').textContent));
   await page.screenshot({path:path.join(output,'failure.png')});throw e;}};
  const screenshot=name=>page.screenshot({path:path.join(output,name+'.png')});
  const graph=JSON.parse(fs.readFileSync(path.join(__dirname,'../../graphs/examples/example/graph.json'),'utf8'));
  const geometry=()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot,p=s.getElementById('panel').getBoundingClientRect(),c=s.getElementById('canvas').getBoundingClientRect();return {canvasTop:c.top,canvasHeight:c.height,panelHeight:p.height};};
  if(process.env.RDG_BASELINE_VIEWER){
   const baseline=await browser.newPage();await baseline.setViewport({width:1440,height:900});
   await baseline.setRequestInterception(true);baseline.on('request',r=>r.url().endsWith('/rd-graph-viewer.user.js')?
     r.respond({status:200,contentType:'text/javascript',body:fs.readFileSync(process.env.RDG_BASELINE_VIEWER,'utf8')}):r.continue());
   await baseline.goto('file://'+path.join(__dirname,'rdg-viewer.html'),{waitUntil:'load'});
   await baseline.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
   await baseline.evaluate(async graph=>{const h=document.getElementById('rdg-viewer-root');h.shadowRoot.getElementById('launch').click();await h.rdgWorkflow.loadGraph(graph);},graph);
   console.log('BASELINE_GRAPH_GEOMETRY',JSON.stringify(await baseline.evaluate(geometry)));
   await baseline.screenshot({path:path.join(output,'graph-before.png')});await baseline.close();
  }
  await click('launch');await run(async graph=>{await document.getElementById('rdg-viewer-root').rdgWorkflow.loadGraph(graph);},graph);
  const compact=await run(geometry);console.log('COMPACT_GRAPH_GEOMETRY',JSON.stringify(compact));
  assert(compact.canvasHeight/compact.panelHeight>.70,'desktop canvas should occupy most of the window');
  await screenshot('graph-compact');await click('workflow-toggle');
  assert.equal(await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-settings').open),false);
  assert.equal(await run(()=>window.__picks),0);
  assert.equal(await run(()=>getComputedStyle(document.getElementById('rdg-viewer-root').shadowRoot.getElementById('graph-pane')).display),'none');
  assert.match(await status(),/не подключена/);await screenshot('plan-disconnected');
  await click('workflow-connect');await page.waitForFunction(()=>!document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-connect').disabled);
  assert.match(await status(),/отменены/);
  await run(()=>{window.__mode='denied';});await click('workflow-connect');
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-connection').textContent.includes('Нет разрешения'));
  assert.match(await status(),/разрешите чтение и запись/);
  await run(()=>{window.__mode='expired';});await click('workflow-connect');await waitText('Сессия Helper завершена');
  await screenshot('plan-expired');
  assert.equal(await run(()=>getComputedStyle(document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-grid')).display),'none');
  await run(()=>{window.__mode='stalled';});await click('workflow-connect');await waitText('Ожидаю ответ');
  await waitText('Helper не ответил за 10 с');await screenshot('plan-helper-unresponsive');
  assert.equal(await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-connect').disabled),false);
  console.log('BROWSER_STAGE ready snapshot');await run(graph=>{
   const graphFile='workspaces/synthetic/graph.json',requirement=graph.nodes.find(n=>n.kind==='requirement');
   window.__snapshot={title:'Тестовый план',graphFile,permissions:['graph.read','plan.read'],future:[{title:'Первый тестовый шаг',nodeId:requirement.id,
     timeConstraints:[{at:'2026-10-22'}],sequence:[]}],history:[],unresolved:[],sources:{graphs:{[graphFile]:graph},completion:{},
     plan:{revision:1,steps:[],timeConstraints:[],sequence:[]}}};window.__mode='ready';
  },graph);
  console.log('BROWSER_STAGE ready connect');await click('workflow-connect');console.log('BROWSER_STAGE awaiting ready');await waitText('Данные перечитаны.');assert.match(await status(),/подключена/);
  assert.equal(await run(()=>getComputedStyle(document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-grid')).display),'grid');
  const collapsed=await run(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot,e=s.querySelector('.wf-editor');return {
    settings:s.getElementById('workflow-settings').open,editor:e.open,fieldVisible:e.querySelector('select').checkVisibility(),
    futureTop:s.querySelector('.wf-grid').getBoundingClientRect().top};});
  assert.equal(collapsed.settings,false);assert.equal(collapsed.editor,false);assert.equal(collapsed.fieldVisible,false);
  assert(collapsed.futureTop<240,'future and history should appear near the top');
  await screenshot('plan-connected');
  await run(()=>{const e=document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-editor');e.querySelector('summary').click();e.querySelector('textarea').value='Retained draft';});
  assert(await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-editor select').getBoundingClientRect().height>0));
  await screenshot('plan-editor-open');
  await run(()=>{const e=document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-editor');e.querySelector('summary').click();e.querySelector('summary').click();});
  assert.equal(await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-editor textarea').value),'Retained draft');
  await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-editor summary').click());
  await click('graph-tab');assert.equal(await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-page').hidden),true);
  await click('workflow-toggle');await waitText('Первый тестовый шаг');
  await page.setViewport({width:390,height:844});
  const sizes=await run(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-page');return [s.scrollWidth,s.clientWidth];});
  assert(sizes[0]<=sizes[1]+1,'mobile plan must not overflow horizontally');await screenshot('plan-mobile');
  await click('graph-tab');const mobile=await run(geometry);console.log('MOBILE_GRAPH_GEOMETRY',JSON.stringify(mobile));
  assert(mobile.canvasHeight/mobile.panelHeight>.50,'mobile graph must retain usable height');await screenshot('graph-mobile');
  assert.deepEqual(errors,[]);console.log('BROWSER_WORKFLOW_TABS_PASS: tabs, cancel, denied, expired, timeout, connected, mobile; pageerrors=0');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
