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
  const graph=JSON.parse(fs.readFileSync(path.join(__dirname,'../../graphs/workspaces/requirements-dependencies-demo/graph.json'),'utf8'));
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
  assert.equal(await run(()=>getComputedStyle(document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-grid')).display),'block');
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
  await click('workflow-toggle');await waitText(graph.nodes.find(n=>n.kind==='requirement').title);
  const candidate=JSON.parse(fs.readFileSync(path.join(__dirname,'../../tests/fixtures/rdg-v6-action-optin/graph.json'),'utf8'));
  const alternative=structuredClone(candidate.nodes.find(n=>n.id==='A1'));alternative.id='A2';alternative.title='Другой способ достижения цели';alternative.status='candidate';
  delete alternative.selectionBasis;
  alternative.canonBlock={recommended:[{id:'C-A2',text:'Когда нужен другой способ'}],contraindicated:[{id:'NC-A2',text:'Когда этот способ не подходит'}]};
  alternative.qrpe=[{id:'Q-A2',text:'Проверить ограничения второго способа',status:'open'}];
  candidate.nodes.push(alternative);candidate.edges.push({id:'drive-A2',type:'DRIVES',from:'R0',to:'A2'});
  await run(g=>{
   const file='workspaces/synthetic/graph.json',child='workspaces/synthetic/child/graph.json';
   const ref=id=>({graphFile:file,identitySpace:g.identitySpace,nodeId:id});
   const projection={...ref('R1'),graphFile:child};
   const v=window.__snapshot;v.capabilities=['plan.place.from-read-sources'];v.sources.graphs={[file]:g,[child]:{schemaVersion:1,id:'continuation',revision:1,title:'Личный граф цели',actionModel:'candidate-v6',planningScale:'module',
    identitySpace:g.identitySpace,rootRequirementId:'R1',expansionOf:{graphSlug:'synthetic',nodeId:'R1'},
    nodes:[{id:'R1',kind:'requirement',title:'Личный граф цели',status:'potential',projectionOf:{graphSlug:'synthetic',nodeId:'R1'}},
     {id:'A3',kind:'action',title:'Способ в личном графе цели',status:'candidate',actionType:'general',
      canonBlock:{recommended:[{id:'C3',text:'Канон способа из другого файла'}],contraindicated:[]},qrpe:[{id:'Q3',text:'QRPE другого файла',status:'open'}]}],
    edges:[{id:'drive-A3',type:'DRIVES',from:'R1',to:'A3'}],events:[]}};
   v.sources.completion={[child]:{R1:{ownerRef:ref('R1')}}};v.permissions=['graph.read','graph.write','plan.read','plan.edit'];
   v.sources.plan={revision:1,steps:[{id:'S-R0',title:'Goal',kind:'requirement',requirementRef:ref('R0')},{id:'S-R1',title:'Child',kind:'requirement',requirementRef:projection}],timeConstraints:[],sequence:[]};
   v.future=[{stepId:'S-R0',nodeId:'R0',kind:'requirement',graphRef:ref('R0'),timeConstraints:[{type:'notBefore',at:'2026-10-23',strength:'hard'}],sequence:[]},
    {stepId:'S-R1',nodeId:'R1',kind:'requirement',graphRef:projection,timeConstraints:[{type:'notBefore',at:'2026-10-24',strength:'soft'}],sequence:[]}];
  },candidate);
  await run(()=>{const b=[...document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('#workflow-panel button')].find(b=>b.textContent==='Обновить');b.click();});
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('.wf-future .wf-variants .wf-card.action').length===3);
  assert.equal(await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-panel').textContent.includes('Создать вариант Action')),false);
  assert.equal(await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('.wf-future>.wf-card[data-context="placement"]').length),2);
  await run(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;
   for(const e of s.querySelectorAll('.wf-variants .wf-card details'))e.open=true;});
  await waitText('Когда нужен другой способ');await waitText('Проверить ограничения второго способа');await screenshot('plan-node-cards-canons-qrpe');
  await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-card[data-context="placement"][data-node-id="R1"] .wf-card-title').click());
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('#canvas .node[data-id="R1"].selected'));
  assert.equal(await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('#canvas .node[data-id="R0"]')!==null),true);
  assert.match(await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('message').title),/Объявление: workspaces\/synthetic\/graph.json/);
  await screenshot('goal-original-declaration');
  await click('workflow-toggle');await waitText('Канон способа из другого файла');
  await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-card.action[data-node-id="A3"] .wf-card-title').click());
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('#canvas .node[data-id="A3"].selected'));
  assert.match(await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('message').title),/Объявление: workspaces\/synthetic\/child\/graph.json/);
  await screenshot('continuation-action-declaration');
  await click('workflow-toggle');
  await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-card.action[data-node-id="A2"] .wf-card-title').click());
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('#canvas .node[data-id="A2"].selected'));
  await screenshot('action-original-declaration');
  await click('workflow-graph-toggle');
  assert.equal(await run(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;return [...s.querySelectorAll('#workflow-graph-editor button')].some(b=>b.textContent==='Создать вариант Action'&&b.checkVisibility());}),true);
  await click('workflow-graph-toggle');await click('workflow-toggle');

  // One chronology, real scrolling to the first placement, then historical owner navigation.
  await run(()=>{
   const v=window.__snapshot,file=v.graphFile,child='workspaces/synthetic/child/graph.json';
   v.history=[
    {kind:'graph_saved',graphFile:file,recordedAt:'2026-10-17T09:00:00Z',summary:'Подготовлены варианты достижения цели',changed:{nodes:['R0','A1','A2']}},
    {kind:'action_executed',graphFile:file,targetId:'A1',title:'Первый выполненный способ',recordedAt:'2026-10-18T09:00:00Z',note:'Получен результат первого способа.'},
    {kind:'requirement_achieved',graphFile:child,targetId:'R1',title:'Достигнутая дочерняя цель',recordedAt:'2026-10-18T09:30:00Z',note:'Результат подтверждён в графе владельца.'},
    {kind:'action_withdrawn',graphFile:file,targetId:'A1',title:'Пересмотр первого способа',recordedAt:'2026-10-19T09:00:00Z',note:'Изменились условия применимости.'},
    {kind:'graph_saved',graphFile:file,recordedAt:'2026-10-19T10:00:00Z',summary:'Уточнён канон второго способа',changed:{nodes:['A2']}},
    {kind:'action_executed',graphFile:file,targetId:'A1',title:'Старый результат без даты записи',recordedAt:null,note:'Сохранена неизвестность времени.'}
   ];
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   [...s.querySelectorAll('#workflow-panel button')].find(b=>b.textContent==='Обновить').click();
  });
  await waitText('Получен результат первого способа.');
  const chronology=await run(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot,t=s.querySelector('.wf-timeline');
   return {sections:[...t.children].map(n=>n.getAttribute('aria-label')),events:s.querySelectorAll('.wf-history>.wf-card').length,
    first:s.querySelector('.wf-future>.wf-card')?.getAttribute('data-node-id'),count:s.querySelectorAll('.wf-future>.wf-card').length};
  });
  assert.deepEqual(chronology.sections,['История','План во времени','Без места во времени']);assert.equal(chronology.events,6);assert.equal(chronology.count,2);
  await run(()=>{document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-page').scrollTop=0;});
  await screenshot('timeline-history');
  const jump=async()=>{
   await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-jump-plan').click());
   await page.waitForFunction(()=>{
    const s=document.getElementById('rdg-viewer-root').shadowRoot,first=s.querySelector('.wf-future>.wf-card'),bar=s.querySelector('.wf-toolbar');
    return s.getElementById('workflow-page').scrollTop>0&&Math.abs(first.getBoundingClientRect().top-bar.getBoundingClientRect().bottom-16)<4;
   },{timeout:5000});
   const focused=await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.activeElement?.getAttribute('data-placement-id'));
   assert.equal(focused,'S-R0','jump lands on the first placed card, not a historical card or nested variant');
  };
  await jump();await screenshot('timeline-plan-jump');
  const planPalette=await run(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   const color=selector=>getComputedStyle(s.querySelector(selector)).backgroundColor;
   return {requirement:color('.wf-future>.wf-card.requirement'),action:color('.wf-variants .wf-card.action'),
    canon:color('.wf-variants .wf-canon'),qrpe:color('.wf-variants .wf-qrpe')};
  });
  assert.equal(new Set(Object.values(planPalette)).size,4,'entity, canon and QRPE colors are distinct');
  const badges=await run(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   return [getComputedStyle(s.querySelector('.wf-future>.wf-card.requirement>.wf-card-meta>.wf-kind-badge')).backgroundColor,
    getComputedStyle(s.querySelector('.wf-variants .wf-card.action>.wf-card-meta>.wf-kind-badge')).backgroundColor];
  });assert.notEqual(badges[0],badges[1],'nested Action badges keep their own color inside a goal');
  await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('.wf-history>.wf-card[data-event-kind="requirement_achieved"] .wf-open-graph').click());
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('#canvas .node[data-id="R1"].selected'));
  assert.equal(await run(()=>!!document.getElementById('rdg-viewer-root').shadowRoot.querySelector('#canvas .node[data-id="R0"]')),true);
  assert.match(await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('message').title),/Объявление: workspaces\/synthetic\/graph.json/);
  const graphPalette=await run(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   return {requirement:getComputedStyle(s.querySelector('#canvas .node.requirement rect')).fill,
    action:getComputedStyle(s.querySelector('#canvas .node.action rect')).fill};
  });
  assert.equal(graphPalette.requirement,planPalette.requirement);assert.equal(graphPalette.action,planPalette.action);
  await screenshot('historical-goal-declaration');
  await click('workflow-toggle');

  await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'reduce'}]);
  await page.setViewport({width:390,height:844});
  await jump();
  const sizes=await run(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-page');return [s.scrollWidth,s.clientWidth];});
  assert(sizes[0]<=sizes[1]+1,'mobile plan must not overflow horizontally');await screenshot('plan-mobile');
  await click('graph-tab');await run(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;if(s.getElementById('inspector-toggle').getAttribute('aria-expanded')==='true')s.getElementById('inspector-toggle').click();});const mobile=await run(geometry);console.log('MOBILE_GRAPH_GEOMETRY',JSON.stringify(mobile));
  assert(mobile.canvasHeight/mobile.panelHeight>.50,'mobile graph must retain usable height');await screenshot('graph-mobile');
  assert.deepEqual(errors,[]);console.log('BROWSER_WORKFLOW_TABS_PASS: tabs, timeline, real scroll, shared colors, history owner navigation, cancel, denied, expired, timeout, connected, mobile; pageerrors=0');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
