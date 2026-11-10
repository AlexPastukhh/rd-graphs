/* Real persisted Graph + Plan writer history + Gendocen receipts -> active Viewer,
 * with a simulated local folder transport, not fabricated demo state. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const ROOT=path.resolve(__dirname,'../..');
const loaded=spawnSync('python3',['-B','tests/rdg-active-example-fixture.py'],
 {cwd:ROOT,encoding:'utf8',timeout:90000,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
assert.equal(loaded.status,0,loaded.stderr||loaded.stdout);
const {view,report}=JSON.parse(loaded.stdout);
const SLUG='requirements-dependencies-demo';
assert(view.history.some(row=>row.kind==='requirement_reformulated'));
assert(view.history.some(row=>row.kind==='plan_created'));
const graphSaves=view.history.filter(row=>row.kind==='graph_saved');
const semanticKeys=new Set(view.history.filter(row=>row.kind!=='graph_saved'&&!row.kind.startsWith('plan_'))
 .map(row=>row.transactionId+'::'+row.graphFile));
const expectedCards=view.history.length-graphSaves.filter(row=>semanticKeys.has(row.transactionId+'::'+row.graphFile)).length;
const expectedWarnings=report.rows.filter(row=>row.status==='review_required').map(row=>row.nodeId);
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell',
  headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--allow-file-access-from-files']});
 try{
  const page=await browser.newPage(),pageErrors=[];page.on('pageerror',error=>pageErrors.push(error.message));
  await page.setViewport({width:1420,height:900});
  const descriptor={schemaVersion:1,kind:'rdg-local-manual-session',active:true,session:'isolated-real-owner-read',
   contexts:[{rootSlug:SLUG,graphFile:view.graphFile,planFile:view.planFile,
    identitySpace:view.sources.graphs[view.graphFile].identitySpace,rootRequirementId:'R0'}]};
  await page.evaluateOnNewDocument(data=>{
   window.__live=data;window.__requests=[];
   Object.defineProperty(window,'showDirectoryPicker',{configurable:true,value:async()=>{
    const files=new Map([['session.json',JSON.stringify(data.descriptor)]]);
    return {name:'real-example-session',kind:'directory',queryPermission:async()=>'granted',requestPermission:async()=>'granted',
      async getFileHandle(name,opt={}){
       if(!opt.create&&!files.has(name))throw new DOMException('not found','NotFoundError');
       return {getFile:async()=>({text:async()=>files.get(name)}),createWritable:async()=>{let value='';return {
        write:async text=>{value=text;},close:async()=>{
         files.set(name,value);
         if(name.endsWith('.ready')){
          const key=name.replace('.ready','.json'),req=JSON.parse(files.get(key));
          window.__requests.push(req);
          const matching=req.body?.contextId===data.descriptor.contexts[0].rootSlug;
          const reply=!matching?{ok:false,error:'WORKSPACE_NOT_REGISTERED',definite:true}:
            req.kind==='state'?{ok:true,result:data.view}:
            req.kind==='dependencies'?{ok:true,result:{available:true,report:data.report}}:
            {ok:false,error:'READ_ONLY_TRANSPORT_IN_BROWSER_QA',definite:true};
          files.set(name.replace('request-','response-').replace('.ready','.json'),JSON.stringify(reply));
         }
        }};}};
      },async removeEntry(name){files.delete(name);}};
   }});
  },{descriptor,view,report});
  await page.goto('file://'+path.join(__dirname,'rdg-viewer.html'),{waitUntil:'load'});
  await page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  const catalogs=await page.evaluate(()=>document.getElementById('rdg-viewer-root').rdgExplorer.getCatalog());
  assert(catalogs.fullGraphs.some(g=>g.slug===SLUG));
  assert(catalogs.graphs.every(g=>g.actionModel==='candidate-v6'));
  await page.evaluate(async slug=>{
   const h=document.getElementById('rdg-viewer-root');
   h.shadowRoot.getElementById('launch').click();await h.rdgExplorer.openFull(slug);
   h.shadowRoot.getElementById('workflow-toggle').click();
   h.shadowRoot.getElementById('workflow-settings').open=true;
   h.shadowRoot.getElementById('workflow-connect').click();
  },SLUG);
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-history')?.textContent.includes('Переформулирована')&&
    document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-future')?.textContent.includes('R-CANON'),{timeout:24000});
  const plan=await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;
   return {history:s.querySelector('.wf-history').textContent,
    future:s.querySelector('.wf-future').textContent,connection:s.getElementById('workflow-connection').textContent,
    planCards:s.querySelectorAll('.wf-history .wf-card').length,
    eventKinds:[...s.querySelectorAll('.wf-history [data-context="history"]')].map(e=>e.getAttribute('data-event-kind')),
    created:s.querySelector('.wf-history [data-change-kind="graph_created"]')?.textContent,
    actions:[...s.querySelectorAll('.wf-history [data-change-kind="action_added"]')].map(e=>e.textContent),
    decomposition:[...s.querySelectorAll('.wf-history [data-event-kind="action_selected"]')]
      .find(e=>e.textContent.includes('R-CANON'))?.textContent,
    introduced:[...s.querySelectorAll('.wf-history .wf-introduced-requirement')].map(e=>e.textContent),
    technicalCount:s.querySelectorAll('.wf-history .wf-save-details').length};});
  assert.match(plan.history,/Выбран|ВЫБОР/);
  assert.match(plan.history,/Переформулирован|Было/);
  assert.match(plan.history,/Сохранено размещение|Создан настоящий Plan owner|Создан Plan/);
  assert.match(plan.future,/R-VERIFY|A-CANON/);
  assert.equal(plan.planCards,expectedCards,'accepted saves are grouped with semantic operations without losing history');
  assert.match(plan.created,/Создан рабочий Graph/);
  assert.equal(plan.actions.length,graphSaves.filter(r=>r.changeKind==='action_added').length,
   'every standalone Action creation is present in history');
  assert.doesNotMatch(plan.history,/Добавлен контекст|Установлена связь контекста с Action|C-ASSURANCE/);
  assert.match(plan.decomposition,/В рамках этого выбора введены Requirements/);
  assert(plan.introduced.some(x=>x.includes('R-CANON'))&&plan.introduced.some(x=>x.includes('R-VERIFY')));
  assert.equal(plan.technicalCount,graphSaves.length,'all accepted technical saves remain accessible');
  await page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('dependency-toggle').click());
  await page.waitForFunction(count=>document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('.dep-item').length===count,{timeout:20000},report.rows.filter(r=>r.status!=='valid').length);
  const deps=await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;
   return {status:s.getElementById('dependency-status').textContent,
    changed:[...s.querySelectorAll('.dep-item[data-status="review_required"] h3')].map(x=>x.textContent),
    links:[...s.querySelectorAll('.dep-item button')].map(x=>({name:x.textContent,disabled:x.disabled})),
    preOpened:s.querySelectorAll('.dep-item details[open]').length,
    requests:window.__requests.map(x=>x.kind)};
  });
  assert.equal(deps.changed.length,expectedWarnings.length);
  for(const id of expectedWarnings)assert(deps.changed.some(x=>x.includes(id)),id);
  assert.equal(deps.preOpened,0,'Gendocen receipts expand only on demand');
  assert(deps.links.some(x=>x.name.includes('Graph')&&!x.disabled),
   'real owner graph references permit navigation');
  assert(deps.requests.includes('state')&&deps.requests.includes('dependencies'));
  assert.equal(pageErrors.length,0,pageErrors.join('\n'));
  console.log('REAL_WORKING_GRAPH_PLAN_GENDOCEN_BROWSER_PASS',JSON.stringify({
   graphRevision:view.sources.graphs[view.graphFile].revision,
   planRevision:view.sources.plan.revision,historyCards:plan.planCards,
   changed:deps.changed,engineStatuses:report.rows.length,pageErrors:pageErrors.length}));
  // Direct loopback sessions do not have sessionContexts. The exact authenticated
  // Workflow snapshot must still resolve the same active owner & dependencies.
  const direct=await browser.newPage(),directErrors=[];
  direct.on('pageerror',e=>directErrors.push(e.message));
  await direct.evaluateOnNewDocument(data=>{
   window.RDG_LOCAL_WORKFLOW=true;window.RDG_SESSION='authorized-loopback-qa';
   // The Python Helper handles real grants and Gendocen in its integration
   // suite. This browser checks its actual script order and the transport's
   // UI binding using real owner/engine snapshots, without opening a port.
   window.fetch=async uri=>{
    const path=String(uri);
    if(path.endsWith('/state'))return {ok:true,json:async()=>data.view};
    if(path.endsWith('/dependencies'))return {ok:true,json:async()=>({available:true,report:data.report})};
    return {ok:false,json:async()=>({error:'BROWSER_LOOPBACK_STUB_UNKNOWN_ROUTE'})};
   };
  },{view,report});
  await direct.goto('file://'+path.join(__dirname,'rdg-viewer.html'),{waitUntil:'load'});
  // The real Helper serves viewer.js first and ui.js second. That second
  // module must call host.rdgStart(), since the Viewer suppresses autostart.
  await direct.addScriptTag({path:path.join(ROOT,'tools/rdg-workflow-ui.js')});
  await direct.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog(),{timeout:15000});
  await direct.evaluate(async data=>{
   const host=document.getElementById('rdg-viewer-root');
   host.shadowRoot.getElementById('launch').click();
   await host.rdgWorkflow.loadGraph(data.graph,data.view);
   await host.rdgExplorer.openFull('requirements-dependencies-demo');
   host.shadowRoot.getElementById('dependency-toggle').click();
  },{graph:view.sources.graphs[view.graphFile],view});
  await direct.waitForFunction(count=>document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('.dep-item').length===count,{timeout:15000},report.rows.filter(r=>r.status!=='valid').length);
  const directState=await direct.evaluate(()=>({status:document.getElementById('rdg-viewer-root').shadowRoot.getElementById('dependency-status').textContent,
   warnings:document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('.dep-item[data-status="review_required"]').length}));
  assert.match(directState.status,/Gendocen/);assert.equal(directState.warnings,expectedWarnings.length);
  assert.equal(directErrors.length,0,directErrors.join('\n'));
  console.log('LOOPBACK_WORKSPACE_GENDOCEN_BROWSER_PASS',JSON.stringify(directState));
  await direct.close();
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
