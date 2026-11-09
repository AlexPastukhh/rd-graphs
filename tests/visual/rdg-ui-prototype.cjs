'use strict';
// Standalone Decision prototype only: no Helper, writers, live owners or credentials.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),http=require('node:http'),os=require('node:os');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const ROOT=path.resolve(__dirname,'../..'),file=path.join(ROOT,'tests/visual/rdg-ui-prototype.html');
(async()=>{
 const source=fs.readFileSync(file,'utf8'),checks=[];
 const declarations=source.slice(source.indexOf('const initialNodes='),source.indexOf('const canonGuidance='))+source.slice(source.indexOf('const initialActions='),source.indexOf('let nodes,actions,'));
 const data=vm.runInNewContext(declarations+';({nodes:initialNodes,edges:initialEdges,actions:initialActions})');
 const graphNode=id=>data.nodes.find(n=>n.id===id);
 assert.equal(data.nodes.filter(n=>n.kind==='action').length,2);
 assert(data.actions.every(n=>n.kind==='action'&&!data.nodes.some(g=>g.id===n.id)));
 assert(data.edges.filter(e=>e.type==='REQUIRES_ACTION').every(e=>['requirement','decision'].includes(graphNode(e.from)?.kind)&&graphNode(e.to)?.kind==='action'));
 assert(data.edges.every(e=>!(graphNode(e.from)?.kind==='decision'&&graphNode(e.to)?.kind==='decision')));
 assert(data.edges.filter(e=>e.type==='DECISION_MEMBER').every(e=>graphNode(e.from)?.kind==='requirement'&&graphNode(e.to)?.kind==='decision'));
 assert.equal(new Set([...data.nodes,...data.actions].map(n=>n.id)).size,data.nodes.length+data.actions.length);
 assert(!source.includes('OPERATES_ON'));assert(!source.includes('decisionGroupsMarkup'));
 const embedded=source.split('/* RDG_PROTOTYPE_LAYOUT_CORE_BEGIN */\n')[1]?.split('/* RDG_PROTOTYPE_LAYOUT_CORE_END */')[0];
 assert.equal(embedded,fs.readFileSync(path.join(ROOT,'tools/rdg-layout-core.js'),'utf8'),'prototype must embed the exact shared layout core');
 const visualCore=source.split('/* RDG_PROTOTYPE_VISUAL_CORE_BEGIN */\n')[1]?.split('/* RDG_PROTOTYPE_VISUAL_CORE_END */')[0];
 assert.equal(visualCore,fs.readFileSync(path.join(ROOT,'tools/rdg-visual-projection.js'),'utf8'),'prototype must embed the exact shared visual core');
 const server=http.createServer((req,res)=>{if(req.url!=='/rdg-ui-prototype.html'){res.writeHead(404);res.end();return;}res.setHeader('Content-Type','text/html; charset=utf-8');res.setHeader('Cache-Control','no-store');res.end(fs.readFileSync(file));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const url='http://127.0.0.1:'+server.address().port+'/rdg-ui-prototype.html';
 const profile=fs.mkdtempSync(path.join(process.env.RDG_SCREENSHOT_DIR||os.tmpdir(),'rdg-prototype-profile-'));
 const launchOptions={executablePath:process.env.RDG_CHROME_PATH,headless:true,userDataDir:profile,args:['--no-sandbox','--disable-dev-shm-usage']};
 let browser;
 try{
  browser=await puppeteer.launch(launchOptions);
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewport({width:1440,height:1000});await page.goto(url,{waitUntil:'load'});
  const count=selector=>page.$$eval(selector,es=>es.length);
  const text=selector=>page.$eval(selector,e=>e.textContent);
  const visible=selector=>page.$eval(selector,e=>!e.hidden);
  const historyIds=()=>page.$$eval('[data-event-id]',es=>es.map(e=>e.dataset.eventId));
  const planIds=branch=>page.$$eval('[data-placement-branch="'+branch+'"]',es=>es.map(e=>e.dataset.placementId));
  const openWindow=async()=>{if(!await visible('#roadWindowPanel'))await page.click('#roadWindowButton');};
  const closeWindow=async()=>{if(await visible('#roadWindowPanel'))await page.click('[data-act="closeRoadWindow"]');};
  const type=async(selector,value,enter=true)=>{
   await page.click(selector);await page.keyboard.down('Control');await page.keyboard.press('KeyA');await page.keyboard.up('Control');if(value==='')await page.keyboard.press('Backspace');else await page.keyboard.type(value);if(enter)await page.keyboard.press('Enter');
  };
  const bound=async(area,edge,value)=>{await openWindow();await type('[data-road-bound="'+area+'.'+edge+'"]',value);};
  const day=(area,value)=>page.click('[data-road-day="'+value+'"][data-area="'+area+'"]');
  const restore=async()=>{
   await bound('history','from','17.10.2026');await bound('history','to','26.10.2026');
   await bound('plan','from','26.10.2026');await bound('plan','to','04.11.2026');await closeWindow();
  };
  const check=async(name,run)=>{try{await run();}catch(error){
   console.error('PROTOTYPE_FAILURE',JSON.stringify({name,errors,forms:await page.evaluate(()=>Array.from(document.forms).map(f=>({kind:f.dataset.form,data:Object.fromEntries(new FormData(f)),invalid:Array.from(f.elements).filter(e=>e.validity&&!e.validity.valid).map(e=>({name:e.name,value:e.value,message:e.validationMessage}))})))}));
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-failure.png')});throw error;
  }checks.push(name);console.log('PASS '+name);};
  await check('closed settings and existing model boundaries',async()=>{
   assert.equal(await visible('#catalogDrawer'),false);assert.equal(await page.$eval('#graphsButton',e=>e.getAttribute('aria-expanded')),'false');
   assert.equal(await visible('#roadWindowPanel'),false);assert.equal(await count('#nodes [data-node]'),12);
   assert.equal(await count('[data-visible-plan-branch="manual"]'),1);assert.equal(await count('[data-visible-plan-branch="auto"]'),0);
   assert.equal(await count('[data-event-id]'),9);assert.equal(await count('.decision-groups-panel'),0);
  });
  const originalHistory=await historyIds(),originalPlan=await planIds('manual'),originalGraph=await page.$eval('#graph',e=>e.innerHTML);
  await check('independent typed date ranges and inclusive boundaries',async()=>{
   await bound('history','from','24.10.2026');assert.deepEqual(await historyIds(),['e5','e8','e6','e7','e9']);
   assert.deepEqual(await planIds('manual'),originalPlan);assert.equal(await page.$eval('#graph',e=>e.innerHTML),originalGraph);
   await bound('history','to','25.10.2026');assert.deepEqual(await historyIds(),['e5','e8']);
   await bound('history','from','17.10.2026');await bound('history','to','26.10.2026');assert.deepEqual(await historyIds(),originalHistory);
  });
  await check('invalid dates and reverse ranges preserve the applied window',async()=>{
   await bound('history','from','31.02.2026');assert.equal(await visible('#roadWindowError'),true);assert.deepEqual(await historyIds(),originalHistory);
   await bound('plan','to','04.11.2026');assert.equal(await visible('#roadWindowError'),true);assert.match(await text('#roadWindowError'),/History:/);
   await bound('history','from','27.10.2026');assert.equal(await visible('#roadWindowError'),true);assert.deepEqual(await historyIds(),originalHistory);
   await bound('history','from','17.10.2026');assert.equal(await visible('#roadWindowError'),false);
   await bound('history','to','18.10.2026');await bound('history','from','23.10.2026');assert.equal(await visible('#roadWindowError'),true);
   await bound('history','to','26.10.2026');assert.equal(await visible('#roadWindowError'),false);
  });
  await check('calendar clicks update typed dates and support reverse selection',async()=>{
   await day('history','2026-10-26');await day('history','2026-10-23');
   assert.equal(await page.$eval('[data-road-bound="history.from"]',e=>e.value),'23.10.2026');
   assert.equal(await page.$eval('[data-road-bound="history.to"]',e=>e.value),'26.10.2026');
   assert.deepEqual(await historyIds(),['e1','e5','e8','e6','e7','e9']);
   await day('plan','2026-10-30');await page.click('[data-road-month="1"][data-area="plan"]');await day('plan','2026-11-02');
   assert.equal(await page.$eval('[data-road-bound="plan.from"]',e=>e.value),'30.10.2026');
   assert.equal(await page.$eval('[data-road-bound="plan.to"]',e=>e.value),'02.11.2026');
   assert.deepEqual(await planIds('manual'),originalPlan); // start/deadline interval overlaps 30 October
   const calendarPlan=await planIds('manual');await bound('plan','from','2026-10-30');await bound('plan','to','2026-11-02');assert.deepEqual(await planIds('manual'),calendarPlan);
  });
  await check('one viewed branch, retained alternative, unchanged Graph/History',async()=>{
   await restore();const historyBefore=await historyIds(),graphBefore=await page.$eval('#graph',e=>e.innerHTML),commonBefore=await planIds('main');
   await page.select('[data-plan-branch="verification"]','auto');
   assert.equal(await count('[data-visible-plan-branch]'),1);assert.equal(await count('[data-visible-plan-branch="manual"]'),0);
   assert.deepEqual(await planIds('auto'),['D4','A8','A9','A10','R2']);assert.deepEqual(await planIds('main'),commonBefore);
   assert.deepEqual(await historyIds(),historyBefore);assert.equal(await page.$eval('#graph',e=>e.innerHTML),graphBefore);
   await page.select('[data-plan-branch="verification"]','manual');assert.deepEqual(await planIds('manual'),originalPlan);
   await page.evaluate(()=>{const t=document.querySelector('#timelineBody'),f=document.querySelector('[data-plan-fork]');t.scrollTop+=f.getBoundingClientRect().top-t.getBoundingClientRect().top-16;});await page.evaluate(()=>new Promise(requestAnimationFrame));
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-branch.png')});
  });
  await check('undated steps retain order and share one period across branches',async()=>{
   await bound('plan','from','31.10.2026');await bound('plan','to','31.10.2026');
   assert.deepEqual(await planIds('manual'),['D3','A5','A7','R2']);
   await closeWindow();await page.select('[data-plan-branch="verification"]','auto');
   assert.deepEqual(await planIds('auto'),['D4','A9','A10']);assert.equal(await count('[data-hidden-plan-step="A8"]'),1);
   await page.select('[data-plan-branch="verification"]','manual');assert.deepEqual(await planIds('manual'),['D3','A5','A7','R2']);
   await restore();assert.deepEqual(await planIds('manual'),originalPlan);
  });
  await check('empty window, low-level filter, Escape and separate geometry settings',async()=>{
   await bound('history','to','18.10.2026');await bound('history','from','18.10.2026');assert.equal(await count('[data-event-id]'),0);assert.match(await text('#roadGraph'),/Нет событий/);
   await restore();await openWindow();await page.keyboard.press('Escape');assert.equal(await visible('#roadWindowPanel'),false);
   assert.equal(await page.$eval('#roadWindowButton',e=>document.activeElement===e),true);
   await page.click('#roadSettingsButton');assert.equal(await visible('#roadSettings'),true);
   await page.click('#roadShowLowLevel');assert.equal((await historyIds()).includes('e9'),false);
   await page.click('#roadWindowButton');assert.equal(await visible('#roadSettings'),false);assert.equal(await visible('#roadWindowPanel'),true);
   await page.click('#roadSettingsButton');await page.click('#roadShowLowLevel');await page.click('#roadSettingsButton');assert.deepEqual(await historyIds(),originalHistory);
  });
  await check('desktop popover placement during pointer/keyboard split resizing',async()=>{
   await openWindow();
   for(const width of [1280,1024,1440]){
    await page.setViewport({width,height:1000});
    const split=await page.$('#workspaceSplitter'),r=await split.boundingBox();
    await page.mouse.move(r.x+r.width/2,r.y+60);await page.mouse.down();await page.mouse.move(r.x-90,r.y+60,{steps:5});await page.mouse.up();
    // Pointer interaction closes the popover; reopen at the new width.
    await openWindow();
    const geometry=await page.evaluate(()=>{const panel=document.querySelector('#roadWindowPanel'),t=document.querySelector('#timeline'),h=t.querySelector('.timeline-head'),a=panel.getBoundingClientRect(),b=t.getBoundingClientRect();return {left:a.left,right:a.right,top:a.top,headerBottom:h.getBoundingClientRect().bottom,timelineLeft:b.left,timelineRight:b.right,overflow:panel.scrollWidth>panel.clientWidth,pageOverflow:document.querySelector('.app').scrollWidth>innerWidth,legendOverflow:document.querySelector('.legend').getBoundingClientRect().right>document.querySelector('#canvas').getBoundingClientRect().right+1}});
    assert(geometry.left>=geometry.timelineLeft);assert(geometry.right<=geometry.timelineRight+1);assert(geometry.top>=geometry.headerBottom);assert.equal(geometry.overflow,false);assert.equal(geometry.pageOverflow,false);assert.equal(geometry.legendOverflow,false);
   }
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-windows.png')});
   await closeWindow();await page.focus('#workspaceSplitter');await page.keyboard.press('ArrowRight');await openWindow();
   assert.equal(await page.evaluate(()=>document.querySelector('#roadWindowPanel').getBoundingClientRect().top>=document.querySelector('.timeline-head').getBoundingClientRect().bottom),true);
   await closeWindow();
  });
  await check('placement form: order only or optional typed time, never regrouped by date',async()=>{
   await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="place"]');
   assert.equal(await page.$eval('[data-form="place"] [name="timeAt"]',e=>e.disabled),true);
   await page.select('[data-form="place"] [name="node"]','A5');await page.select('[data-form="place"] [name="branch"]','main');
   await type('[data-form="place"] [name="order"]','5',false);await page.select('[data-form="place"] [name="timeKind"]','estimate');
   await page.$eval('[data-form="place"] [name="timeAt"]',e=>e.value='2026-10-27T12:00');await page.click('[data-form="place"] [type="submit"]');
   assert.deepEqual(await planIds('main'),['D1','A5','A3','A4','D5']);
   const graphBeforePlanning=await page.$eval('#graph',e=>e.innerHTML);
   await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="place"]');
   await page.select('[data-form="place"] [name="node"]','D2');await page.select('[data-form="place"] [name="branch"]','main');
   await type('[data-form="place"] [name="order"]','2',false);await page.click('[data-form="place"] [type="submit"]');
   assert((await planIds('main')).includes('D2')); // Planning is allowed while D2 is unselected and G1's D1 is selected.
   assert.equal(await page.$eval('#graph',e=>e.innerHTML),graphBeforePlanning);

   await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="place"]');
   await page.select('[data-form="place"] [name="node"]','A8');await page.select('[data-form="place"] [name="branch"]','auto');
   await page.select('[data-form="place"] [name="timeKind"]','start_deadline');
   await page.$eval('[name="startAt"]',e=>e.value='2026-10-31T12:00');await page.$eval('[name="deadlineAt"]',e=>e.value='2026-10-30T12:00');
   const before=await historyIds();await page.click('[data-form="place"] [type="submit"]');assert.match(await text('#toast'),/Начало не может/);assert.deepEqual(await historyIds(),before);
  });
  await check('Action details, targets and full group details remain navigable',async()=>{
   await page.click('#side [data-act="close"]');
   await page.click('[data-placement-branch="manual"] [data-action-node="A6"]');assert.equal(await text('#panelTitle'),'Action · A6');
   await page.click('#side [data-select="D3"]');assert.match(await text('#status'),/^D3/);
   const before=await page.$eval('#graph',e=>e.getAttribute('viewBox').split(' ').slice(2));
   await page.click('[data-plan-fork="verification"] [data-group-ref="G4"]');assert.equal(await text('#panelTitle'),'Группа · G4');
   assert.deepEqual(await page.$$eval('[data-group-details="G4"] [data-graph-ref]',es=>es.map(e=>e.dataset.graphRef)),['R2','D3','D4']);
   assert.deepEqual(await page.$eval('#graph',e=>e.getAttribute('viewBox').split(' ').slice(2)),before);
   await page.click('#side [data-graph-ref="R2"]');assert.equal(await text('#panelTitle'),'Сведения · R2');
  });
  await check('single click and keyboard enter local Decision/Requirement focus with real provenance',async()=>{
   await page.reload({waitUntil:'load'});
   const graphIds=()=>page.$$eval('#nodes [data-node]',es=>es.map(e=>e.dataset.node).sort());
   await page.click('#nodes [data-node="D1"]');assert.match(await text('#breadcrumb'),/Фокус · граф D1/);
   assert.deepEqual(await graphIds(),['C1','D1','K1','R0','R1','R2']);
   await page.click('#nodes [data-node="R1"]');assert.match(await text('#breadcrumb'),/Фокус · граф R1/);
   assert.deepEqual(await graphIds(),['D1','R1']);
   assert.equal(await count('#edges [data-edge-from="D1"][data-edge-to="R1"][data-edge-type="INTRODUCES"]'),1);
   assert.equal(await count('#nodes [data-node="R0"]'),0); // R0 is not a direct mandatory parent of R1.
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-requirement-focus.png')});
   assert.equal(await count('#edges [data-edge-from="R0"][data-edge-to="R1"]'),0); // No invented direct parent edge.
   const contained=await page.evaluate(()=>{const graph=document.querySelector('#graph').getBoundingClientRect();return ['D1','R1'].every(id=>{const r=document.querySelector('[data-node="'+id+'"]').getBoundingClientRect();return r.left>=graph.left-1&&r.right<=graph.right+1&&r.top>=graph.top-1&&r.bottom<=graph.bottom+1;});});assert(contained);
   await page.click('#nodes [data-node="D1"]');await page.$eval('#nodes [data-node="R2"]',e=>e.focus());await page.keyboard.press('Enter');
   assert.match(await text('#breadcrumb'),/Фокус · граф R2/);assert.equal(await count('#nodes [data-node="D1"]'),1);
   await page.click('#allButton');assert.equal((await graphIds()).length,12);assert.doesNotMatch(await text('#breadcrumb'),/Фокус/);
  });
  await check('incoming direct Requirement parent and leaving a group scope retain mandatory origins',async()=>{
   await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="link"]');
   await page.select('[data-form="link"] [name="from"]','R1');await page.select('[data-form="link"] [name="to"]','R2');await page.select('[data-form="link"] [name="type"]','DERIVES');await page.click('[data-form="link"] [type="submit"]');
   await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="link"]');
   await page.select('[data-form="link"] [name="from"]','R1');await page.select('[data-form="link"] [name="to"]','D3');await page.select('[data-form="link"] [name="type"]','DRIVES');await page.click('[data-form="link"] [type="submit"]');
   await page.click('#nodes [data-node="R2"]');assert.match(await text('#breadcrumb'),/Фокус · граф R2/);
   assert.equal(await count('#edges [data-edge-from="D1"][data-edge-to="R1"]'),0);
   assert.equal(await count('#edges [data-edge-from="R1"][data-edge-to="D3"]'),0); // A relation between two neighbours is outside the R2 focus.
   for(const id of ['D1','R1','R2'])assert.equal(await count('#nodes [data-node="'+id+'"]'),1);
   assert.equal(await count('#nodes [data-node="R0"]'),0);
   assert.equal(await text('#edges [data-edge-from="R1"][data-edge-to="R2"] + text'),'Обязательная под-R');
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-requirement-origin.png')});
   await page.click('#allButton');assert.equal(await count('#edges [data-edge-from="R1"][data-edge-to="D3"]'),1);await page.click('#edges [data-group-ids="G4"]');assert.equal(await text('#panelTitle'),'Группа · G4');
   assert.equal(await count('#nodes [data-node="D1"]'),0); // Group-only scope is intentional until a block is opened.
   await page.click('#nodes [data-node="R2"]');assert.match(await text('#breadcrumb'),/Фокус · граф R2/);
   assert.equal(await count('#nodes [data-node="D1"]'),1);assert.equal(await count('#nodes [data-node="R1"]'),1);
   assert.equal(await text('#panelTitle'),'Сведения · R2');
   await page.click('#nodes [data-node="R1"]');
   assert.deepEqual(await page.$$eval('#nodes [data-node]',es=>es.map(e=>e.dataset.node).sort()),['D1','D3','R1','R2']);
   assert.equal(await count('#edges [data-edge-from="R1"][data-edge-to="R2"]'),1);assert.equal(await count('#edges [data-edge-from="R1"][data-edge-to="D3"]'),1);
   assert.equal(await count('#edges [data-edge-from="R2"][data-edge-to="D3"]'),0);
  });
  await check('Plan/History and Action target references enter focus without changing zoom or accepting Decision',async()=>{
   await page.reload({waitUntil:'load'});
   const box=()=>page.$eval('#graph',e=>e.getAttribute('viewBox').split(' ').map(Number));
   const size=(await box()).slice(2);
   await page.click('[data-placement-branch="manual"] [data-select="R2"]');assert.match(await text('#breadcrumb'),/Фокус · граф R2/);
   assert.equal(await count('#nodes [data-node="D1"]'),1);assert.deepEqual((await box()).slice(2),size);
   await page.click('.road-row.history [data-history-node="R1"]');assert.match(await text('#breadcrumb'),/Фокус · граф R1/);
   assert.equal(await count('#nodes [data-node="D1"]'),1);assert.deepEqual((await box()).slice(2),size);
   const beforeAction=await box();await page.click('[data-action-node="A4"]');assert.equal(await text('#panelTitle'),'Action · A4');assert.deepEqual(await box(),beforeAction);
   await page.click('#side [data-select="D1"]');assert.match(await text('#breadcrumb'),/Фокус · граф D1/);assert.deepEqual((await box()).slice(2),size);
   for(const id of ['R0','R1','R2'])assert.equal(await count('#nodes [data-node="'+id+'"]'),1);
   await page.click('[data-placement-branch="manual"] [data-select="D3"]');assert.match(await text('#breadcrumb'),/Фокус · граф D3/);
   assert.match(await text('#nodes [data-node="D3"]'),/обнаружено/);assert.deepEqual((await box()).slice(2),size);
   for(let i=0;i<9;i++)await page.click('[data-act="in"]');
   const zoomed=(await box()).slice(2);await page.click('.road-row.history [data-history-node="R1"]');
   assert.deepEqual((await box()).slice(2),zoomed);
   assert(await page.evaluate(()=>{const v=document.querySelector('#graph').getBoundingClientRect(),r=document.querySelector('[data-node="R1"]').getBoundingClientRect();return r.left>=v.left&&r.right<=v.right&&r.top>=v.top&&r.bottom<=v.bottom;}));

  });
  const workGraphStorageKey='rdg.prototype.workgraphs.v1';
  const graphIds=()=>page.$$eval('#nodes [data-node]',es=>es.map(e=>e.dataset.node).sort());
  const openArea=async(id)=>{if(!await visible('#catalogDrawer'))await page.click('#graphsButton');await page.click('[data-workgraph-process="service"][data-workgraph-open="'+id+'"]');assert.equal(await visible('#catalogDrawer'),true);await page.click('#catalogHeader');};
  const workGraphState=()=>page.evaluate(key=>localStorage.getItem(key),workGraphStorageKey);
  let createdAreaId,areaState;
  await check('Explorer stays open for Process/Working Graph navigation and closes explicitly from its header',async()=>{
   await page.reload({waitUntil:'load'});assert.equal(await visible('#catalogDrawer'),false);await page.click('#graphsButton');
   assert.match(await text('[data-catalog-folder="working"]'),/Процесс-графы/);
   assert.deepEqual(await page.$$eval('[data-process-graph="service"] [data-workgraph-open]',es=>es.map(e=>e.dataset.workgraphOpen)),['WG1','WG2']);
   await page.click('#catalogHeader .explorer-name');assert.equal(await visible('#catalogDrawer'),false);assert.equal(await page.$eval('#graphsButton',e=>e.getAttribute('aria-expanded')),'false');
   await page.click('#graphsButton');await page.focus('#catalogHeader');await page.keyboard.press('Enter');assert.equal(await visible('#catalogDrawer'),false);
   const launcher=await page.evaluate(()=>{const icon=document.querySelector('#graphsButton .explorer-trigger-icon'),label=document.querySelector('#graphsButton .brand');return {same:icon.closest('button')===label.closest('button'),left:icon.getBoundingClientRect().right<label.getBoundingClientRect().left,iconWidth:icon.getBoundingClientRect().width,iconHeight:icon.getBoundingClientRect().height,headerHeight:document.querySelector('.top').getBoundingClientRect().height};});assert(launcher.same&&launcher.left);assert.equal(launcher.iconWidth,18);assert.equal(launcher.iconHeight,18);assert(launcher.headerHeight<64);
   await page.click('#graphsButton .explorer-trigger-icon');assert.equal(await visible('#catalogDrawer'),true);await page.click('#catalogHeader');
   await page.click('#graphsButton .brand');assert.equal(await visible('#catalogDrawer'),true);await page.click('#catalogHeader');
   await page.click('#graphsButton');
   const beforeNavigation=await workGraphState(),historyBeforeNavigation=await historyIds();
   await page.click('[data-catalog-package="service"]');assert.equal(await visible('#catalogDrawer'),true);assert.equal(await page.$eval('#graphsButton',e=>e.getAttribute('aria-expanded')),'true');
   assert.equal(await page.evaluate(()=>document.activeElement.dataset.catalogPackage),'service');
   await page.click('[data-workgraph-open="WG1"]');assert.equal(await visible('#catalogDrawer'),true);assert.deepEqual(await graphIds(),['C1','D1','K1','R1']);
   assert.equal(await page.evaluate(()=>document.activeElement.dataset.workgraphOpen),'WG1');
   await page.focus('[data-workgraph-open="WG2"]');await page.keyboard.press('Enter');assert.equal(await visible('#catalogDrawer'),true);assert.deepEqual(await graphIds(),['D1','D3','D4','D5','R2']);
   await page.click('[data-catalog-package="service"]');assert.equal(await visible('#catalogDrawer'),true);assert.equal((await graphIds()).length,12);
   assert.equal(await workGraphState(),beforeNavigation);assert.deepEqual(await historyIds(),historyBeforeNavigation);
   await type('#catalogSearch','Подготовка окружения',false);
   assert.equal(await count('[data-process-graph="service"]'),1);assert.equal(await count('[data-workgraph-open="WG1"]'),1);assert.equal(await count('[data-workgraph-open="WG2"]'),0);
   assert.equal(await count('[data-catalog-folder="ready"]'),0);
   await type('#catalogSearch','',false);await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-working-explorer.png')});await page.click('#catalogHeader');
  });
  await check('Working Graphs overlap through shared entities and real edges, without separate Plan or History',async()=>{
   const historyBefore=await historyIds(),planBefore=await planIds('main');
   await openArea('WG1');assert.deepEqual(await graphIds(),['C1','D1','K1','R1']);assert.match(await text('#workGraphBar'),/4 из 12/);
   assert.equal(await count('#edges [data-edge-from="D1"][data-edge-to="R1"]'),1);assert.equal(await count('#edges [data-edge-to="R2"]'),0);
   assert.deepEqual(await historyIds(),historyBefore);assert.deepEqual(await planIds('main'),planBefore);assert.match(await text('#timelineScope'),/процесса · Запуск сервиса/);
   await page.click('#nodes [data-node="D1"]');await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="edit"]');
   await type('[data-form="edit"] [name="title"]','Общая стратегия запуска',false);await page.click('[data-form="edit"] [type="submit"]');
   await openArea('WG2');assert.deepEqual(await graphIds(),['D1','D3','D4','D5','R2']);assert.match(await text('#nodes [data-node="D1"]'),/Общая стратегия/);
   await page.click('[data-act="processGraph"]');assert.equal((await graphIds()).length,12);assert.match(await text('#nodes [data-node="D1"]'),/Общая стратегия/);
   await openArea('WG1');assert.match(await text('#nodes [data-node="D1"]'),/Общая стратегия/);assert.equal(await workGraphState(),null); // Viewing/semantic edits do not copy or rewrite memberships.
   await page.click('[data-act="processGraph"]');assert.equal((await historyIds()).length,historyBefore.length+1);
   await page.reload({waitUntil:'load'});
  });
  await check('area boundaries open complete entity focus, mark external nodes and leave membership unchanged',async()=>{
   await openArea('WG2');const before=await workGraphState();
   await page.click('[data-act="workGraphLinks"]');assert.match(await text('#panelTitle'),/Границы/);
   await page.click('#side [data-graph-ref="R0"]');assert.match(await text('#breadcrumb'),/Фокус · граф R0/);
   assert.equal(await count('#nodes [data-node="R0"][data-outside-workgraph="true"]'),1);
   assert.equal(await count('#nodes [data-node="D2"][data-outside-workgraph="true"]'),1);
   assert.equal(await count('#nodes [data-node="D1"][data-outside-workgraph="false"]'),1);
   await page.click('#allButton');assert.deepEqual(await graphIds(),['D1','D3','D4','D5','R2']);assert.equal(await workGraphState(),before);
   await page.click('#side [data-act="close"]');await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-working-area.png')});
   await page.click('[data-act="processGraph"]');
  });
  await check('create/edit working scope persists references, validates roots and preserves excluded entities',async()=>{
   await page.click('#graphsButton');await page.click('[data-workgraph-create="service"]');assert.equal(await visible('#catalogDrawer'),true);await page.click('#catalogHeader');
   await type('[data-form="workGraph"] [name="title"]','Общая проверка',false);
   await page.$$eval('[data-form="workGraph"] [name="memberId"]',es=>es.forEach(e=>e.checked=['D1','R1','R2'].includes(e.value)));
   await page.select('[data-form="workGraph"] [name="rootId"]','R0');await page.click('[data-form="workGraph"] [type="submit"]');
   assert.match(await text('#workGraphError'),/должен входить/);assert.equal(await workGraphState(),null);
   await page.select('[data-form="workGraph"] [name="rootId"]','R1');await page.click('[data-form="workGraph"] [type="submit"]');
   assert.deepEqual(await graphIds(),['D1','R1','R2']);
   let doc=JSON.parse(await workGraphState()),areas=doc.processes.service.workGraphs;assert.equal(areas.length,3);assert.equal(doc.revision,1);
   createdAreaId=areas.find(w=>w.title==='Общая проверка').id;
   assert.deepEqual(Object.keys(areas[2]).sort(),['id','memberIds','rootIds','title']);assert.deepEqual(areas[2].rootIds,['R1']);
   await page.click('[data-workgraph-edit="'+createdAreaId+'"]');
   await type('[data-form="workGraph"] [name="title"]','Общая проверка · уточнено',false);await page.click('[name="memberId"][value="R2"]');
   await page.click('[data-form="workGraph"] [type="submit"]');assert.deepEqual(await graphIds(),['D1','R1']);
   areaState=await workGraphState();doc=JSON.parse(areaState);assert.equal(doc.revision,2);assert.equal(doc.processes.service.workGraphs.length,3);
   await page.click('[data-act="processGraph"]');assert.equal(await count('#nodes [data-node="R2"]'),1);assert.equal((await graphIds()).length,12);
   await page.reload({waitUntil:'load'});assert.equal(await visible('#catalogDrawer'),false);await page.click('#graphsButton');await page.click('[data-workgraph-open="'+createdAreaId+'"]');assert.equal(await visible('#catalogDrawer'),true);await page.click('#catalogHeader');assert.deepEqual(await graphIds(),['D1','R1']);
   assert.match(await text('.project h1'),/Общая проверка · уточнено/);assert.equal(await workGraphState(),areaState);
   await page.click('[data-act="processGraph"]');
   await page.click('#graphsButton');await page.click('[data-catalog-package="mobile"]');assert.equal(await visible('#catalogDrawer'),true);assert.equal(await count('[data-process-graph="mobile"] [data-workgraph-open]'),0);
   await page.click('[data-catalog-package="service"]');await page.click('#catalogHeader');assert.equal((await graphIds()).length,12);
  });
  await check('failed working-area persistence keeps applied scope and durable references',async()=>{
   await openArea(createdAreaId);await page.click('[data-workgraph-edit="'+createdAreaId+'"]');
   await type('[data-form="workGraph"] [name="title"]','Не сохранённая правка',false);
   await page.evaluate(key=>{window.rdgWorkGraphSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k===key)throw new DOMException('Fixture unavailable','QuotaExceededError');return window.rdgWorkGraphSet.call(this,k,v);};},workGraphStorageKey);
   await page.click('[data-form="workGraph"] [type="submit"]');assert.match(await text('#workGraphError'),/не сохранена/);assert.equal(await workGraphState(),areaState);assert.match(await text('#workGraphBar'),/Общая проверка · уточнено/);
   await page.evaluate(()=>{Storage.prototype.setItem=window.rdgWorkGraphSet;delete window.rdgWorkGraphSet;});await page.click('#side [data-act="close"]');
   await page.click('[data-act="processGraph"]');
  });

  await check('new Requirement Decision and Graph Action join the current WG while external Actions stay outside',async()=>{
   await openArea('WG1');const before=JSON.parse(await workGraphState()),other=before.processes.service.workGraphs.find(w=>w.id==='WG2').memberIds,created=[];
   for(const kind of ['requirement','decision']){await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="add"]');await page.select('[data-form="add"] [name="kind"]',kind);await type('[data-form="add"] [name="title"]',kind==='requirement'?'Новый результат области':'Новый способ области',false);await page.click('[data-form="add"] [type="submit"]');const id=(await text('#status')).split(' · ')[0];created.push(id);assert.equal(await count('#nodes [data-node="'+id+'"][data-outside-workgraph="true"]'),0);await page.click('#allButton');assert((await graphIds()).includes(id));}
   await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="addGraphAction"]');await type('[data-form="addAction"] [name="title"]','Обязательное действие области',false);await page.click('[data-form="addAction"] [type="submit"]');created.push((await text('#status')).split(' · ')[0]);await page.click('#allButton');assert(created.every(id=>!['D1','R1','C1','K1'].includes(id)));
   let doc=JSON.parse(await workGraphState()),members=doc.processes.service.workGraphs.find(w=>w.id==='WG1').memberIds;assert(created.every(id=>members.includes(id)));assert(!members.includes('R2'));assert.deepEqual(doc.processes.service.workGraphs.find(w=>w.id==='WG2').memberIds,other);const scope=await workGraphState();
   await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="addAction"]');await type('[data-form="addAction"] [name="title"]','Внешнее действие из области',false);await page.click('[data-form="addAction"] [type="submit"]');assert.equal(await workGraphState(),scope);await page.click('[data-act="processGraph"]');assert.equal((await graphIds()).length,15);
   await page.reload({waitUntil:'load'});assert.equal((await graphIds()).length,12);await openArea('WG1');assert.deepEqual(await graphIds(),['C1','D1','K1','R1']);await page.click('[data-workgraph-edit="WG1"]');for(const id of created)assert.equal(await count('[data-form="workGraph"] [name="memberId"][value="'+id+'"]'),0);await page.click('[data-form="workGraph"] [type="submit"]');areaState=await workGraphState();await page.click('[data-act="processGraph"]');
  });
  await check('WG authoring storage failure creates neither a Graph entity nor a partial membership or event',async()=>{
   await openArea('WG1');const before=await workGraphState(),ids=await graphIds(),history=await historyIds();await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="add"]');await type('[data-form="add"] [name="title"]','Повтор создания после ошибки',false);
   await page.evaluate(key=>{window.rdgWorkGraphSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k===key)throw new DOMException('Fixture unavailable','QuotaExceededError');return window.rdgWorkGraphSet.call(this,k,v);};},workGraphStorageKey);await page.click('[data-form="add"] [type="submit"]');assert.match(await text('[data-create-scope-error]'),/Блок не создан/);assert.equal(await workGraphState(),before);assert.deepEqual(await graphIds(),ids);assert.deepEqual(await historyIds(),history);
   await page.evaluate(()=>{Storage.prototype.setItem=window.rdgWorkGraphSet;delete window.rdgWorkGraphSet;});await page.click('[data-form="add"] [type="submit"]');const id=(await text('#status')).split(' · ')[0];assert(JSON.parse(await workGraphState()).processes.service.workGraphs.find(w=>w.id==='WG1').memberIds.includes(id));await page.reload({waitUntil:'load'});await openArea('WG1');assert(!(await graphIds()).includes(id));await page.click('[data-workgraph-edit="WG1"]');await page.click('[data-form="workGraph"] [type="submit"]');areaState=await workGraphState();await page.click('[data-act="processGraph"]');
  });

  const screenIds=()=>page.$$eval('[data-screen-tab]',es=>es.map(e=>e.dataset.screenTab));
  const switchTab=id=>page.click('[data-screen-tab="'+id+'"]');
  const graphBox=()=>page.$eval('#graph',e=>e.getAttribute('viewBox'));
  await check('tab chrome keeps close controls bounded and keyboard focus visible without clipping or changing data',async()=>{
   await page.reload({waitUntil:'load'});const historyBefore=await historyIds(),planBefore=await planIds('main');
   await page.click('#newScreenButton');await page.click('#newScreenButton');const ids=await screenIds();
   const bounds=await page.$$eval('.screen-tab-shell',es=>es.map(e=>{const shell=e.getBoundingClientRect(),close=e.querySelector('[data-close-screen-tab]').getBoundingClientRect(),label=e.querySelector('[role="tab"]').getBoundingClientRect();return {shell:{x:shell.x,y:shell.y,right:shell.right,bottom:shell.bottom,width:shell.width},close:{x:close.x,y:close.y,right:close.right,bottom:close.bottom,width:close.width,height:close.height},labelRight:label.right};}));
   assert(bounds.every(r=>r.close.width>=22&&r.close.width<=28&&r.close.width===r.close.height&&r.close.x>=r.labelRight&&r.close.right<=r.shell.right&&r.close.y>r.shell.y&&r.close.bottom<r.shell.bottom));
   assert.equal(new Set(bounds.map(r=>r.shell.width)).size,1);
   await page.hover('[data-close-screen-tab="'+ids[0]+'"]');assert.equal(await page.$eval('#screenTabs [role="tab"][aria-selected="true"]',e=>e.dataset.screenTab),ids[2]);
   await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>document.activeElement.dataset.closeScreenTab),ids[2]);
   assert(await page.evaluate(()=>document.activeElement.matches(':focus-visible')));
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-tab-close-focus.png'),clip:{x:0,y:0,width:1440,height:145}});
   await page.click('[data-close-screen-tab="'+ids[0]+'"]');assert.equal(await page.$eval('#screenTabs [role="tab"][aria-selected="true"]',e=>e.dataset.screenTab),ids[2]);assert.equal(await page.evaluate(()=>document.activeElement.dataset.screenTab),ids[2]);
   await page.keyboard.press('ArrowLeft');assert.equal(await page.$eval('#screenTabs [role="tab"][aria-selected="true"]',e=>e.dataset.screenTab),ids[1]);
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-tab-selection-focus.png'),clip:{x:0,y:0,width:1440,height:145}});
   for(let i=0;i<6;i++)await page.click('#newScreenButton');
   const activeVisible=()=>page.evaluate(()=>{const list=document.querySelector('#screenTabs').getBoundingClientRect(),shell=document.querySelector('.screen-tab-shell.current').getBoundingClientRect();return shell.left>=list.left-1&&shell.right<=list.right+1;});assert(await activeVisible());
   await page.click('.screen-tab-shell.current [data-close-screen-tab]');assert(await activeVisible());
   await page.keyboard.press('Home');assert(await activeVisible());assert.equal(await page.$eval('#screenTabs',e=>e.scrollLeft),0);
   assert.deepEqual(await historyIds(),historyBefore);assert.deepEqual(await planIds('main'),planBefore);assert.equal(await page.evaluate(()=>document.querySelector('.app').scrollWidth<=innerWidth),true);
  });
  await check('screen tabs occupy row two and restore independent area/focus, camera and Plan view settings',async()=>{
   await page.reload({waitUntil:'load'});
   const geometry=await page.evaluate(()=>({top:document.querySelector('.top').getBoundingClientRect().bottom,tabs:document.querySelector('.screen-tabs-row').getBoundingClientRect(),tools:document.querySelector('.tab-tools').getBoundingClientRect(),controls:['allButton','planButton','dependenciesButton','requestsButton','infoButton','decisionsButton'].every(id=>document.getElementById(id).closest('.tab-tools'))}));
   // DOMRects are serialized explicitly below; all old row-two actions share row three.
   assert(geometry.controls);assert(await page.evaluate(()=>document.querySelector('.screen-tabs-row').getBoundingClientRect().top>=document.querySelector('.top').getBoundingClientRect().bottom&&document.querySelector('.tab-tools').getBoundingClientRect().top>=document.querySelector('.screen-tabs-row').getBoundingClientRect().bottom));
   await openArea('WG1');await page.click('#planButton');assert.equal(await visible('#timeline'),false);await page.click('[data-act="in"]');const firstBox=await graphBox(),first=(await screenIds())[0];
   await page.click('#newScreenButton');const second=(await screenIds())[1];assert.equal(await visible('#timeline'),false);assert.equal(await graphBox(),firstBox);
   await openArea('WG2');await page.click('#planButton');assert.equal(await visible('#timeline'),true);
   await page.select('[data-plan-branch="verification"]','auto');await bound('history','from','24.10.2026');await closeWindow();
   await page.click('#nodes [data-node="D3"]');await page.click('[data-act="in"]');const secondBox=await graphBox();
   await switchTab(first);assert.deepEqual(await graphIds(),['C1','D1','K1','R1']);assert.equal(await graphBox(),firstBox);assert.equal(await visible('#timeline'),false);
   await page.click('#planButton');assert.equal(await visible('#timeline'),true);assert.equal(await page.$eval('[data-plan-branch="verification"]',e=>e.value),'manual');await openWindow();assert.equal(await page.$eval('[data-road-bound="history.from"]',e=>e.value),'17.10.2026');await closeWindow();
   await switchTab(second);assert.equal(await graphBox(),secondBox);assert.match(await text('#breadcrumb'),/Фокус · граф D3/);assert.equal(await visible('#timeline'),true);assert.equal(await page.$eval('[data-plan-branch="verification"]',e=>e.value),'auto');
   await openWindow();assert.equal(await page.$eval('[data-road-bound="history.from"]',e=>e.value),'24.10.2026');await closeWindow();
   await page.click('[data-act="fit"]');
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-screen-tabs.png')});
   await page.click('#planButton');await switchTab(first);assert.equal(await visible('#timeline'),true);await switchTab(second);assert.equal(await visible('#timeline'),false);
  });
  await check('two screens reference the same process Graph, Plan placements and History without duplicate events',async()=>{
   await page.reload({waitUntil:'load'});await openArea('WG1');const first=(await screenIds())[0];await page.click('#newScreenButton');const second=(await screenIds())[1];await openArea('WG2');
   const before=(await historyIds()).length;
   await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="place"]');await page.select('[data-form="place"] [name="node"]','D2');await type('[data-form="place"] [name="order"]','2',false);await page.click('[data-form="place"] [type="submit"]');
   await page.click('#nodes [data-node="D1"]');await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="edit"]');await type('[data-form="edit"] [name="title"]','Стратегия общая для вкладок',false);await page.click('[data-form="edit"] [type="submit"]');
   await switchTab(first);assert.match(await text('#workGraphBar'),/Подготовка окружения/);assert.match(await text('#nodes [data-node="D1"]'),/Стратегия общая/);assert.equal((await historyIds()).length,before+2);assert.equal((await planIds('main')).filter(id=>id==='D2').length,1);
   await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="place"]');await page.select('[data-form="place"] [name="node"]','D2');await type('[data-form="place"] [name="order"]','5',false);await page.click('[data-form="place"] [type="submit"]');
   await switchTab(second);assert.equal((await historyIds()).length,before+3);assert.equal((await planIds('main')).filter(id=>id==='D2').length,1);assert.equal(await page.$eval('[data-placement-branch="main"][data-placement-id="D2"]',e=>e.dataset.placementOrder),'5');assert.match(await text('#nodes [data-node="D1"]'),/Стратегия общая/);
  });
  await check('each screen retains inspector and unsubmitted form state while process edits remain shared',async()=>{
   await page.reload({waitUntil:'load'});await openArea('WG1');const first=(await screenIds())[0];await page.click('#requestsButton');await page.click('#newScreenButton');const second=(await screenIds())[1];
   await page.click('#nodes [data-node="R1"]');await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="edit"]');await type('[data-form="edit"] [name="title"]','Черновик второго экрана',false);await type('[data-form="edit"] [name="description"]','Описание ещё не сохранено',false);
   await switchTab(first);assert.equal(await text('#panelTitle'),'Запросы изменений');assert.doesNotMatch(await text('#nodes [data-node="R1"]'),/Черновик/);
   await switchTab(second);assert.equal(await text('#panelTitle'),'Изменить R1');assert.equal(await page.$eval('[data-form="edit"] [name="title"]',e=>e.value),'Черновик второго экрана');assert.equal(await page.$eval('[data-form="edit"] [name="description"]',e=>e.value),'Описание ещё не сохранено');
   await page.click('[data-form="edit"] [type="submit"]');await switchTab(first);assert.match(await text('#nodes [data-node="R1"]'),/Черновик второго/);assert.equal(await text('#panelTitle'),'Запросы изменений');
  });
  await check('Explorer can open another screen; keyboard and close preserve views and process ownership',async()=>{
   await page.reload({waitUntil:'load'});const first=(await screenIds())[0];await page.click('#graphsButton');await page.keyboard.down('Control');await page.click('[data-workgraph-open="WG2"]');await page.keyboard.up('Control');assert.equal(await visible('#catalogDrawer'),true);assert.equal((await screenIds()).length,2);await page.click('#catalogHeader');const second=(await screenIds())[1];
   await page.focus('[data-screen-tab="'+second+'"]');await page.keyboard.press('ArrowLeft');assert.equal((await graphIds()).length,12);await page.keyboard.press('ArrowRight');assert.deepEqual(await graphIds(),['D1','D3','D4','D5','R2']);
   await page.click('#graphsButton');await page.click('[data-catalog-package="copy-service"]');await page.click('#catalogHeader');
   await page.click('#nodes [data-node="R0"]');await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="edit"]');await type('[data-form="edit"] [name="title"]','Результат отдельного процесса',false);await page.click('[data-form="edit"] [type="submit"]');
   await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="place"]');await page.select('[data-form="place"] [name="node"]','A5');await page.click('[data-form="place"] [type="submit"]');assert((await planIds('main')).includes('A5'));
   await switchTab(first);assert.match(await text('#nodes [data-node="R0"]'),/Запустить сервис/);assert(!(await planIds('main')).includes('A5'));assert.equal((await historyIds()).length,9);
   await switchTab(second);assert.match(await text('#nodes [data-node="R0"]'),/Результат отдельного/);assert((await planIds('main')).includes('A5'));
   await page.click('[data-close-screen-tab="'+second+'"]');assert.equal((await screenIds()).length,1);assert.equal((await historyIds()).length,9);assert.equal(await page.$eval('[data-close-screen-tab]',e=>e.disabled),true);
   await page.click('#newScreenButton');await page.click('[data-close-screen-tab="'+first+'"]');assert.equal((await screenIds()).length,1);assert.equal((await historyIds()).length,9);assert.equal((await graphIds()).length,12);
   await page.reload({waitUntil:'load'});
  });

  const openCatalogGraph=async id=>{
   if(!await visible('#catalogDrawer'))await page.click('#graphsButton');
   await page.click('[data-explorer-tab="graphs"]');await type('#catalogSearch',id,false);await page.click('[data-catalog-package="'+id+'"]');assert.equal(await visible('#catalogDrawer'),true);await type('#catalogSearch','',false);await page.click('#catalogHeader');
  };
  const insertTemplate=async(anchor='',process='service')=>{
   await page.click('[data-act="insertTemplate"]');await page.select('[data-form="readyWorkflow"] [name="processId"]',process);await page.select('[data-form="readyWorkflow"] [name="anchorId"]',anchor);await page.click('[data-form="readyWorkflow"] [type="submit"]');
  };
  const ensurePlan=async()=>{if(!await visible('#timeline'))await page.click('#planButton');};
  await check('ready areas contain templates and reusable lenses with distinct previews and explicit Graph Actions',async()=>{
   await page.reload({waitUntil:'load'});await page.click('#graphsButton');
   for(const area of ['ready-apps','ready-2d','ready-3d','ready-code','ready-rdg']){
    if(await page.$eval('[data-catalog-folder="'+area+'"]',e=>e.getAttribute('aria-expanded'))!=='true')await page.click('[data-catalog-folder="'+area+'"]');
    for(const suffix of ['templates','lenses'])if(await page.$eval('[data-catalog-folder="'+area+'-'+suffix+'"]',e=>e.getAttribute('aria-expanded'))!=='true')await page.click('[data-catalog-folder="'+area+'-'+suffix+'"]');
    assert(await count('[data-ready-area="'+area+'"][data-ready-kind="template"]'));assert(await count('[data-ready-area="'+area+'"][data-ready-kind="lens"]'));
   }
   assert(await page.$eval('#catalogDrawer .catalog-body',e=>e.scrollWidth<=e.clientWidth+1));assert.equal(await page.$eval('#catalogDrawer .catalog-body',e=>e.scrollLeft),0);
   for(const area of ['ready-3d','ready-code','ready-rdg'])await page.click('[data-catalog-folder="'+area+'"]');await page.$eval('#catalogDrawer .catalog-body',e=>e.scrollTop=0);
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-ready-catalog.png')});await page.click('#catalogHeader');
   await openCatalogGraph('ready-2d-layout');assert.match(await text('#readyGraphBar'),/Шаблон графа · 2D/);assert.match(await text('#nodes'),/2D-композицию/);assert.equal((await graphIds()).length,8);assert.equal(await count('#nodes [data-node="A1"]'),1);assert.equal(await page.$eval('#planButton',e=>e.disabled),true);
   await page.click('[data-act="readyContents"]');assert.equal(await count('#side [data-graph-ref="A1"]'),1);await page.click('#side [data-graph-ref="A1"]');assert.equal(await text('#panelTitle'),'Сведения · A1');assert.match(await text('#breadcrumb'),/Фокус · граф A1/);await page.click('#allButton');assert.equal((await graphIds()).length,8);
   await page.click('#side [data-act="close"]');await page.click('#nodes [data-node="C1"]');await page.click('#infoButton');assert.match(await text('#panelBody'),/Иерархия, интервалы/);assert.doesNotMatch(await text('#panelBody'),/Цена ошибки/);
   await openCatalogGraph('lens-code-review');assert.match(await text('#readyGraphBar'),/Граф линзы · Программирование/);assert.equal(await count('[data-act="insertTemplate"]'),0);assert.equal(await count('[data-act="openLensContext"]'),1);assert.equal((await graphIds()).length,7);
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-ready-lens.png')});
  });
  await check('template insertion remaps Graph, groups and Actions into the process without importing choices or Plan placements',async()=>{
   await page.reload({waitUntil:'load'});const oldNodes=await graphIds(),oldPlan=await planIds('main'),oldHistory=await historyIds();await openCatalogGraph('ready-app-flow');
   await insertTemplate('R0');assert.equal(await visible('#readyGraphBar'),false);assert.match(await text('.project h1'),/Запуск сервиса/);assert.equal((await graphIds()).length,20);
   const root=(await text('#status')).split(' · ')[0];assert(!oldNodes.includes(root));assert.equal(await count('#edges [data-edge-from="R0"][data-edge-to="'+root+'"][data-edge-type="DERIVES"]'),1);
   const newNodes=(await graphIds()).filter(id=>!oldNodes.includes(id));assert.equal(new Set(newNodes).size,8);assert.equal(await count('#nodes [data-node^="A"]'),4);
   const newDecisions=await page.$$eval('#nodes [data-node]',(es,old)=>es.filter(e=>!old.includes(e.dataset.node)&&e.textContent.includes('Decision')).map(e=>({id:e.dataset.node,text:e.textContent})),oldNodes);assert.equal(newDecisions.length,2);assert(newDecisions.every(d=>d.text.includes('обнаружено')));
   await ensurePlan();assert.deepEqual(await planIds('main'),oldPlan);assert.equal((await historyIds()).length,oldHistory.length+1);assert.equal(new Set(await historyIds()).size,oldHistory.length+1);
   const group=await page.$eval('#edges [data-group-ids]:not([data-group-ids="G1"]):not([data-group-ids="G1,G2"]):not([data-group-ids="G2"]):not([data-group-ids="G3"]):not([data-group-ids="G4"])',e=>e.dataset.groupIds);
   await page.click('#edges [data-group-ids="'+group+'"]');assert.equal(await text('#panelTitle'),'Группа · '+group);assert.deepEqual((await page.$$eval('#side [data-graph-ref]',es=>es.map(e=>e.dataset.graphRef))).sort(),[root,...newDecisions.map(d=>d.id)].sort());
   await page.click('#side [data-act="close"]');await page.click('#allButton');await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="place"]');
   const actionIds=await page.$$eval('[data-form="place"] [name="node"] option',es=>es.map(e=>e.value).filter(id=>/^A/.test(id)&&Number(id.slice(1))>12));assert.equal(actionIds.length,2);assert(actionIds.every(id=>newNodes.includes(id)));
   await page.select('[data-form="place"] [name="node"]',actionIds[0]);await page.click('[data-form="place"] [type="submit"]');assert((await planIds('main')).includes(actionIds[0]));await page.click('[data-placement-branch="main"] [data-action-node="'+actionIds[0]+'"]');assert.equal(await text('#panelTitle'),'Action · '+actionIds[0]);
   const actionTargets=await page.$$eval('#side [data-select]',es=>es.map(e=>e.dataset.select));assert(actionTargets.length>0&&actionTargets.every(id=>newNodes.includes(id)));assert.equal(await count('#side [data-group-ref="'+group+'"]'),1);await page.click('#side [data-act="close"]');
   await page.click('#nodes [data-node="'+root+'"]');await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="edit"]');await type('[data-form="edit"] [name="title"]','Моя структура приложения',false);await page.click('[data-form="edit"] [type="submit"]');
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-inserted-template.png')});
   await openCatalogGraph('ready-app-flow');assert.match(await text('#nodes [data-node="R0"]'),/Создать работающее/);assert.doesNotMatch(await text('#nodes'),/Моя структура/);
   await openCatalogGraph('service');assert.equal((await graphIds()).length,20);assert.match(await text('#nodes [data-node="'+root+'"]'),/Моя структура/);
  });
  await check('repeated insertion produces independent instances visible from all screens of the target process',async()=>{
   await page.reload({waitUntil:'load'});const first=(await screenIds())[0],initial=await graphIds(),before=await historyIds();await page.click('#newScreenButton');const second=(await screenIds())[1];
   await openCatalogGraph('ready-2d-layout');await insertTemplate();const firstAdded=(await graphIds()).filter(id=>!initial.includes(id));assert.equal(firstAdded.length,8);
   await switchTab(first);assert.equal((await graphIds()).length,20);assert(firstAdded.every(id=>!initial.includes(id)));await switchTab(second);
   await openCatalogGraph('ready-2d-layout');await insertTemplate();assert.equal((await graphIds()).length,28);assert.equal(new Set(await graphIds()).size,28);await ensurePlan();assert.equal((await historyIds()).length,before.length+2);
   const secondAdded=(await graphIds()).filter(id=>!initial.includes(id)&&!firstAdded.includes(id));assert.equal(secondAdded.length,8);
   await switchTab(first);assert.equal((await graphIds()).length,28);assert(secondAdded.every(id=>!firstAdded.includes(id)));
   await switchTab(second);await openCatalogGraph('ready-code-change');await insertTemplate('','mobile');assert.match(await text('.project h1'),/Мобильное приложение/);assert.equal((await graphIds()).length,20);
   await switchTab(first);assert.match(await text('.project h1'),/Запуск сервиса/);assert.equal((await graphIds()).length,28);
  });
  await check('a thematic lens binds to a process/area/focus and can be reused without inserting Graph or History',async()=>{
   await page.reload({waitUntil:'load'});const first=(await screenIds())[0],beforeNodes=await graphIds(),beforeHistory=await historyIds(),beforePlan=await planIds('main');await page.click('#newScreenButton');const second=(await screenIds())[1];
   await openCatalogGraph('lens-2d-review');await page.click('[data-act="openLensContext"]');await page.select('[data-form="readyWorkflow"] [name="scope"]','workGraph:WG2');await page.click('[data-form="readyWorkflow"] [type="submit"]');assert.match(await text('#readyGraphBar'),/Для: Запуск сервиса · Проверка сценариев/);assert.equal((await graphIds()).length,7);
   await switchTab(first);assert.deepEqual(await graphIds(),beforeNodes);assert.deepEqual(await historyIds(),beforeHistory);assert.deepEqual(await planIds('main'),beforePlan);
   await switchTab(second);assert.match(await text('#readyGraphBar'),/Проверка сценариев/);assert.equal(await page.$eval('#planButton',e=>e.disabled),true);
   await page.click('[data-act="openLensContext"]');await page.select('[data-form="readyWorkflow"] [name="scope"]','focus:R1');await page.click('[data-form="readyWorkflow"] [type="submit"]');assert.match(await text('#readyGraphBar'),/Фокус R1/);
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-bound-lens.png')});await page.click('[data-act="lensProcess"]');assert.match(await text('#breadcrumb'),/Фокус · граф R1/);assert.deepEqual(await graphIds(),['D1','R1']);
   await switchTab(first);assert.deepEqual(await graphIds(),beforeNodes);assert.deepEqual(await historyIds(),beforeHistory);
   await switchTab(second);await openCatalogGraph('lens-2d-review');await page.click('[data-act="openLensContext"]');await page.select('[data-form="readyWorkflow"] [name="processId"]','mobile');await page.click('[data-form="readyWorkflow"] [type="submit"]');assert.match(await text('#readyGraphBar'),/Для: Мобильное приложение/);assert.equal((await graphIds()).length,7);
   await switchTab(first);assert.deepEqual(await graphIds(),beforeNodes);assert.deepEqual(await historyIds(),beforeHistory);
  });
  await check('ready workflow drafts remain screen-local and cancellation does not insert a template',async()=>{
   await page.reload({waitUntil:'load'});await openCatalogGraph('ready-3d-scene');const first=(await screenIds())[0];await page.click('[data-act="insertTemplate"]');await page.select('[data-form="readyWorkflow"] [name="processId"]','mobile');await page.select('[data-form="readyWorkflow"] [name="anchorId"]','R1');
   await page.click('#newScreenButton');const second=(await screenIds())[1];await page.click('#side [data-act="close"]');await switchTab(first);assert.equal(await page.$eval('[data-form="readyWorkflow"] [name="processId"]',e=>e.value),'mobile');assert.equal(await page.$eval('[data-form="readyWorkflow"] [name="anchorId"]',e=>e.value),'R1');
   await page.click('#side [data-act="close"]');await openCatalogGraph('mobile');assert.equal((await graphIds()).length,12);await ensurePlan();assert.equal((await historyIds()).length,9);await switchTab(second);assert.equal(await visible('#side'),false);assert.match(await text('#readyGraphBar'),/Шаблон графа · 3D/);
   await page.reload({waitUntil:'load'});
  });

  const operation=async name=>{await page.click('#decisionsButton');await page.click('#decisionMenu [data-act="'+name+'"]');};
  const showInfo=async id=>{
   await page.click('#allButton');await page.click('#nodes [data-node="'+id+'"]');
   if(await page.$eval('#infoButton',e=>e.getAttribute('aria-expanded'))!=='true')await page.click('#infoButton');
   assert.equal(await text('#panelTitle'),'Сведения · '+id);
  };
  const recommended=()=>page.$$eval('#side [data-recommendation-lens]',es=>es.map(e=>e.dataset.recommendationLens).sort());
  const setChecks=async(selector,values)=>page.$$eval(selector,(es,vs)=>{for(const e of es){e.checked=vs.includes(e.value);e.dispatchEvent(new Event('change',{bubbles:true}));}},values);
  const fillRule=async({types=['requirement','decision','action'],scope='all',anchor='R0',state='any',tag='',lenses=['lens-code-review']}={})=>{
   await setChecks('[data-form="recommendationPackage"] [name="nodeKind"]',types);await page.select('[data-form="recommendationPackage"] [name="scopeKind"]',scope);
   if(scope!=='all')await page.select('[data-form="recommendationPackage"] [name="anchorId"]',anchor);
   await page.select('[data-form="recommendationPackage"] [name="conditionState"]',state);await type('[data-form="recommendationPackage"] [name="tag"]',tag,false);await setChecks('[data-form="recommendationPackage"] [name="lensId"]',lenses);
  };
  const newPackage=async(title,rule)=>{
   await page.click('#lensesButton');await page.click('[data-act="addRecommendationPackage"]');await page.click('[data-act="newRecommendationPackage"]');await type('[data-form="recommendationPackage"] [name="title"]',title,false);await fillRule(rule);await page.click('[data-form="recommendationPackage"] [type="submit"]');
   return page.$$eval('[data-recommendation-package]',(es,title)=>es.find(e=>e.querySelector('.connected-package-title')?.textContent===title)?.dataset.recommendationPackage,title);
  };
  const connectPackages=async ids=>{
   await page.click('#lensesButton');const current=await page.$$eval('#side [data-recommendation-package]',es=>es.map(e=>e.dataset.recommendationPackage));
   for(const id of current)if(!ids.includes(id))await page.click('#side [data-detach-recommendation-package="'+id+'"]');
   for(const id of ids)if(!current.includes(id)){await page.click('[data-act="addRecommendationPackage"]');await type('#recommendationPickerSearch',id,false);await page.click('#side [data-attach-recommendation-package="'+id+'"]');}
  };
  await check('explicit Graph Actions, low-level operations and arbitrary Plan Actions have separate membership and one identity each',async()=>{
   await page.reload({waitUntil:'load'});assert.equal(await count('#nodes [data-node^="A"]'),2);for(const id of ['A1','A2','A3'])assert.equal(await count('#nodes [data-node="'+id+'"]'),0);
   await showInfo('R2');assert.equal(await count('#edges [data-edge-type="REQUIRES_ACTION"][data-edge-to="A11"]'),1);
   await page.click('#nodes [data-node="A11"]');assert.deepEqual(await graphIds(),['A11','R2']);assert.match(await text('#panelBody'),/Action/);
   await page.click('#allButton');const beforeGraph=await graphIds(),beforeEdges=await page.$eval('#edges',e=>e.innerHTML);
   await operation('addAction');assert.equal(await count('[data-form="addAction"] [name="parentId"]'),0);await type('[data-form="addAction"] [name="title"]','Обсудить результат на встрече',false);await page.click('[data-form="addAction"] [type="submit"]');
   const external=(await text('#panelTitle')).split(' · ')[1];assert(/^A/.test(external));assert.match(await text('#panelBody'),/Action вне Graph/);assert.equal(await count('#side [data-graph-ref="'+external+'"]'),0);assert.deepEqual(await graphIds(),beforeGraph);assert.equal(await page.$eval('#edges',e=>e.innerHTML),beforeEdges);
   assert.deepEqual(await recommended(),['lens-human','lens-plan']);await operation('place');const options=await page.$$eval('[data-form="place"] [name="node"] option',es=>es.map(e=>e.value));assert.equal(options.filter(id=>id==='A11').length,1);assert.equal(options.filter(id=>id===external).length,1);
   await page.select('[data-form="place"] [name="node"]',external);await page.click('[data-form="place"] [type="submit"]');assert((await planIds('main')).includes(external));assert.deepEqual(await graphIds(),beforeGraph);
   await page.click('[data-placement-id="'+external+'"] [data-action-node="'+external+'"]');await page.click('[data-configure-node-lenses="'+external+'"]');assert.equal(await page.$eval('[name="anchorId"]',e=>e.value),external);await type('[data-form="recommendationPackage"] [name="title"]','Линза для внешнего Action',false);await setChecks('[name="lensId"]',['lens-code-review']);await page.click('[data-form="recommendationPackage"] [type="submit"]');
   await page.click('[data-placement-id="'+external+'"] [data-action-node="'+external+'"]');assert((await recommended()).includes('lens-code-review'));await page.click('[data-recommended-lens="lens-code-review"]');assert.match(await text('#readyGraphBar'),new RegExp('Action '+external+' · вне Graph'));await page.click('[data-act="lensProcess"]');assert.equal(await text('#panelTitle'),'Action · '+external);assert.deepEqual(await graphIds(),beforeGraph);
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-external-action-lenses.png')});
  });
  await check('mandatory R/Decision Actions participate in completion and can be planned without selecting their parent',async()=>{
   await page.reload({waitUntil:'load'});await operation('add');await type('[data-form="add"] [name="title"]','Проверяемый результат',false);await page.click('[data-form="add"] [type="submit"]');const requirement=(await text('#status')).split(' · ')[0];
   await operation('addGraphAction');assert.equal(await page.$eval('[name="parentId"]',e=>e.value),requirement);await type('[data-form="addAction"] [name="title"]','Выполнить конкретную проверку',false);await page.click('[data-form="addAction"] [type="submit"]');const action=(await text('#status')).split(' · ')[0];
   assert.deepEqual(await graphIds(),[action,requirement].sort());assert.equal(await count('#edges [data-edge-from="'+requirement+'"][data-edge-to="'+action+'"][data-edge-type="REQUIRES_ACTION"]'),1);
   await operation('achieveRequirement');await page.select('[data-form="achieveRequirement"] [name="node"]',requirement);await page.click('[data-form="achieveRequirement"] [type="submit"]');assert.match(await text('#toast'),/нельзя закрыть/);
   await operation('completeAction');assert.equal(await page.$eval('[data-form="completeAction"] [name="node"]',e=>e.value),action);await page.click('[data-form="completeAction"] [type="submit"]');
   await operation('achieveRequirement');await page.select('[data-form="achieveRequirement"] [name="node"]',requirement);await page.click('[data-form="achieveRequirement"] [type="submit"]');assert.match(await text('#toast'),/Requirement закрыт/);
   await showInfo('D3');await page.click('#side [data-act="completeDecision"]');assert.match(await text('#toast'),/сначала должен быть selected/);await operation('place');await page.select('[data-form="place"] [name="node"]','A12');await page.click('[data-form="place"] [type="submit"]');await showInfo('D3');assert.match(await text('#nodes [data-node="D3"]'),/обнаружено/);
   await page.click('#side [data-act="selectDecision"]');await page.click('#side [data-act="completeDecision"]');assert.match(await text('#toast'),/открыты обязательные A12/);await operation('completeAction');await page.select('[data-form="completeAction"] [name="node"]','A12');await page.click('[data-form="completeAction"] [type="submit"]');await showInfo('D3');await page.click('#side [data-act="completeDecision"]');assert.match(await text('#nodes [data-node="D3"]'),/завершено/);
   await showInfo('R2');await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-graph-actions.png')});
  });
  await check('creation and rename record low-level Actions outside Graph; discovery never resets a later Decision choice',async()=>{
   await page.reload({waitUntil:'load'});const before=await historyIds();await operation('add');await page.select('[data-form="add"] [name="kind"]','decision');await type('[data-form="add"] [name="title"]','Новый вариант для discovery',false);await page.click('[data-form="add"] [type="submit"]');const decision=(await text('#status')).split(' · ')[0],creation=(await historyIds()).find(id=>!before.includes(id));
   const activity=await page.$eval('[data-event-id="'+creation+'"] [data-action-node]',e=>e.dataset.actionNode);assert.notEqual(activity,decision);assert.equal(await count('#nodes [data-node="'+activity+'"]'),0);assert.equal(await count('#nodes [data-node="'+decision+'"]'),1);
   await page.click('#roadSettingsButton');await page.click('#roadShowLowLevel');assert(!(await historyIds()).includes(creation));assert.equal(await count('#nodes [data-node="'+decision+'"]'),1);await page.click('#roadShowLowLevel');await page.click('#roadSettingsButton');
   await showInfo('D1');const beforeRename=await historyIds();await operation('edit');await type('[data-form="edit"] [name="title"]','Принятый вариант с новым именем',false);await page.click('[data-form="edit"] [type="submit"]');const renamed=(await historyIds()).find(id=>!beforeRename.includes(id));await page.click('[data-event-id="'+renamed+'"] [data-action-node]');assert.match(await text('#panelBody'),/переименовать блок/);assert.match(await text('#panelBody'),/low-level операция/);await page.click('#allButton');assert.equal((await graphIds()).length,13);
   await showInfo('D1');await operation('addAction');await page.select('[data-form="addAction"] [name="actionType"]','discover_decision');await type('[data-form="addAction"] [name="title"]','Подтвердить создание существующего D1',false);await page.click('[data-form="addAction"] [type="submit"]');await operation('completeAction');await page.click('[data-form="completeAction"] [type="submit"]');await showInfo('D1');assert.match(await text('#nodes [data-node="D1"]'),/выбрано/);await page.click('#allButton');assert.equal(await count('#nodes [data-node^="A"]'),2);
  });
  await check('fundamental package is attached by default and reusable type/state/tag rules apply to both Action representations',async()=>{
   await page.reload({waitUntil:'load'});await page.click('#lensesButton');assert.equal(await count('#side [data-recommendation-package="RP-fundamental"]'),1);
   for(const id of ['R0','D1']){await showInfo(id);assert.deepEqual(await recommended(),['lens-core','lens-human']);}
   await showInfo('A11');assert.deepEqual(await recommended(),['lens-human','lens-plan']);
   const pack=await newPackage('Проверка незавершённых действий',{types:['action'],state:'open'});assert(pack);await showInfo('A11');assert((await recommended()).includes('lens-code-review'));await ensurePlan();await page.click('[data-placement-id="A3"] [data-action-node="A3"]');assert((await recommended()).includes('lens-code-review'));
   await page.click('[data-event-id="e8"] [data-action-node="A1"]');assert(!(await recommended()).includes('lens-code-review'));await showInfo('R0');assert(!(await recommended()).includes('lens-code-review'));
   await openCatalogGraph('mobile');await page.click('#lensesButton');assert.equal(await count('#side [data-recommendation-package="RP-fundamental"]'),1);assert.equal(await count('#side [data-recommendation-package="'+pack+'"]'),0);await connectPackages(['RP-fundamental',pack,'RP-2d']);await showInfo('A11');assert((await recommended()).includes('lens-code-review'));assert(!(await recommended()).includes('lens-2d-review'));
   await operation('edit');await type('[data-form="edit"] [name="tags"]','2d',false);await page.click('[data-form="edit"] [type="submit"]');await showInfo('A11');assert((await recommended()).includes('lens-2d-review'));
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-lens-recommendations.png')});
  });
  await check('identity-bound descendant recommendations follow semantic composition and cannot match equal short IDs in another process',async()=>{
   await page.reload({waitUntil:'load'});await operation('add');await type('[data-form="add"] [name="title"]','Дочерний результат D3',false);await page.click('[data-form="add"] [type="submit"]');const child=(await text('#status')).split(' · ')[0];
   await operation('link');await page.select('[data-form="link"] [name="from"]','D3');await page.select('[data-form="link"] [name="to"]',child);await page.select('[data-form="link"] [name="type"]','INTRODUCES');await page.click('[data-form="link"] [type="submit"]');
   const pack=await newPackage('Потомки R2',{types:['requirement','decision'],scope:'descendants',anchor:'R2'});assert(pack);
   for(const id of ['D3','D4','D5',child]){await showInfo(id);assert((await recommended()).includes('lens-code-review'));assert.match(await text('[data-recommendation-lens="lens-code-review"]'),/Потомки R2/);}
   for(const id of ['R2','R1','D1','A11']){await showInfo(id);assert(!(await recommended()).includes('lens-code-review'));}
   await openCatalogGraph('mobile');await connectPackages(['RP-fundamental',pack]);await page.click('#lensesButton');assert.match(await text('[data-recommendation-package="'+pack+'"]'),/совпадений 0/);await showInfo('D3');assert(!(await recommended()).includes('lens-code-review'));await openCatalogGraph('service');await showInfo(child);assert((await recommended()).includes('lens-code-review'));
   await page.click('#lensesButton');await page.click('[data-edit-recommendation-package="'+pack+'"]');await page.select('[name="scopeKind"]','children');await page.click('[data-form="recommendationPackage"] [type="submit"]');await showInfo(child);assert(!(await recommended()).includes('lens-code-review'));await showInfo('D3');assert((await recommended()).includes('lens-code-review'));
   await page.click('#lensesButton');await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-recommendation-packages.png')});
  });
  await check('multiple package rules merge lens recommendations with reasons; state changes reevaluate without executing a lens',async()=>{
   await page.reload({waitUntil:'load'});await page.click('#lensesButton');await page.click('[data-act="addRecommendationPackage"]');await page.click('[data-act="newRecommendationPackage"]');await type('[data-form="recommendationPackage"] [name="title"]','Правила для решений',false);await fillRule({types:['decision'],lenses:['lens-code-review']});await page.click('[data-act="addRecommendationRule"]');
   await fillRule({types:['decision'],scope:'entity',anchor:'D3',state:'discovered',lenses:['lens-code-review','lens-2d-review']});await page.click('[data-form="recommendationPackage"] [type="submit"]');await showInfo('D3');assert.equal((await recommended()).filter(id=>id==='lens-code-review').length,1);assert.equal(await count('[data-recommendation-lens="lens-code-review"] [data-recommendation-source]'),2);assert((await recommended()).includes('lens-2d-review'));
   await page.click('#side [data-act="selectDecision"]');assert(!(await recommended()).includes('lens-2d-review'));assert.equal(await count('[data-recommendation-lens="lens-code-review"] [data-recommendation-source]'),1);
   const beforeHistory=await historyIds(),beforePlan=await planIds('main');await page.click('[data-recommended-lens="lens-code-review"]');assert.match(await text('#readyGraphBar'),/Фокус D3/);await page.click('[data-act="lensProcess"]');assert.deepEqual(await historyIds(),beforeHistory);assert.deepEqual(await planIds('main'),beforePlan);assert.match(await text('#nodes [data-node="D3"]'),/выбрано/);
  });
  await check('template companion packages remap anchor identities independently for repeated insertions and stay inside each fragment',async()=>{
   await page.reload({waitUntil:'load'});const original=await graphIds();await openCatalogGraph('ready-2d-layout');await page.click('#lensesButton');assert.match(await text('#panelBody'),/потомки|потомк/iu);await page.click('#side [data-act="close"]');await insertTemplate();const first=(await graphIds()).filter(id=>!original.includes(id));
   const firstD=await page.$$eval('#nodes [data-node]',(es,ids)=>es.find(e=>ids.includes(e.dataset.node)&&e.textContent.includes('Decision'))?.dataset.node,first);await showInfo(firstD);assert((await recommended()).includes('lens-2d-review'));const source1=await page.$eval('[data-recommendation-lens="lens-2d-review"] [data-recommendation-source]',e=>e.dataset.recommendationSource);await showInfo('D3');assert(!(await recommended()).includes('lens-2d-review'));
   await openCatalogGraph('ready-2d-layout');await insertTemplate();const second=(await graphIds()).filter(id=>!original.includes(id)&&!first.includes(id)),secondD=await page.$$eval('#nodes [data-node]',(es,ids)=>es.find(e=>ids.includes(e.dataset.node)&&e.textContent.includes('Decision'))?.dataset.node,second);await showInfo(secondD);const source2=await page.$eval('[data-recommendation-lens="lens-2d-review"] [data-recommendation-source]',e=>e.dataset.recommendationSource);assert.notEqual(source1,source2);assert.equal(await count('[data-recommendation-lens="lens-2d-review"] [data-recommendation-source]'),1);await showInfo(firstD);assert.equal(await page.$eval('[data-recommendation-lens="lens-2d-review"] [data-recommendation-source]',e=>e.dataset.recommendationSource),source1);
   await operation('add');await type('[data-form="add"] [name="title"]','Новый результат внутри первой вставки',false);await page.click('[data-form="add"] [type="submit"]');const laterChild=(await text('#status')).split(' · ')[0];await operation('link');await page.select('[name="from"]',firstD);await page.select('[name="to"]',laterChild);await page.select('[name="type"]','INTRODUCES');await page.click('[data-form="link"] [type="submit"]');await showInfo(laterChild);assert.equal(await page.$eval('[data-recommendation-lens="lens-2d-review"] [data-recommendation-source]',e=>e.dataset.recommendationSource),source1);assert.equal(await count('[data-recommendation-lens="lens-2d-review"] [data-recommendation-source]'),1);
   await connectPackages(['RP-fundamental',source2]);await showInfo(firstD);assert(!(await recommended()).includes('lens-2d-review'));await showInfo(laterChild);assert(!(await recommended()).includes('lens-2d-review'));await showInfo(secondD);assert((await recommended()).includes('lens-2d-review'));
  });
  await check('a user-created template carries recommendation packages and separate Graph/Plan Actions into another process',async()=>{
   await page.reload({waitUntil:'load'});const original=await graphIds();const reusable=await newPackage('Проверка действий фрагмента',{types:['action'],lenses:['lens-2d-review']});assert(reusable);const pack=await newPackage('Локальный пакет для упаковки',{types:['requirement','decision','action'],scope:'descendants',anchor:'R2',lenses:['lens-app-review']});assert(pack);
   await operation('packReadyGraph');await type('[data-form="packReadyGraph"] [name="title"]','Мой повторяемый процесс',false);await page.click('[data-form="packReadyGraph"] [type="submit"]');assert.match(await text('#readyGraphBar'),/Мой повторяемый процесс/);const template=await page.$eval('[data-catalog-package].active',e=>e.dataset.catalogPackage);assert(template.startsWith('ready-custom-'));assert.equal((await graphIds()).length,original.length);assert.match(await text('#nodes [data-node="D1"]'),/обнаружено/);
   await page.click('#lensesButton');assert.match(await text('#panelBody'),/Локальный пакет для упаковки/);await page.click('#side [data-act="close"]');await insertTemplate('','mobile');const added=(await graphIds()).filter(id=>!original.includes(id));assert.equal(added.length,original.length);
   const r2=await page.$$eval('#nodes [data-node]',(es,ids)=>es.find(e=>ids.includes(e.dataset.node)&&e.textContent.includes('Проверить рабочие сценарии'))?.dataset.node,added);assert(r2);const decision=await page.$eval('#edges [data-edge-from="'+r2+'"][data-edge-type="DECISION_MEMBER"]',e=>e.dataset.edgeTo);await showInfo(decision);assert((await recommended()).includes('lens-app-review'));await showInfo('D3');assert(!(await recommended()).includes('lens-app-review'));
   const fragmentAction=added.find(id=>/^A/.test(id));await showInfo(fragmentAction);assert((await recommended()).includes('lens-2d-review'));await showInfo('A11');assert(!(await recommended()).includes('lens-2d-review'));
   await operation('place');const options=await page.$$eval('[name="node"] option',es=>es.map(e=>e.value));assert.equal(new Set(options).size,options.length);const external=options.filter(id=>/^A/.test(id)&&Number(id.slice(1))>12&&!added.includes(id));assert(external.length>0);assert.equal(await count('#nodes [data-node="'+external[0]+'"]'),0);await page.click('#side [data-act="close"]');
   await openCatalogGraph('service');await showInfo('D3');assert((await recommended()).includes('lens-app-review'));await openCatalogGraph(template);assert.equal((await graphIds()).length,original.length);await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-user-template.png')});
  });
  await check('packaging rejects recommendation anchors outside the chosen fragment without changing the source',async()=>{
   await page.reload({waitUntil:'load'});await newPackage('Правило от R0',{types:['requirement','decision'],scope:'descendants',anchor:'R0'});await showInfo('R1');const before=await historyIds(),view=await graphIds();await operation('packReadyGraph');await type('[data-form="packReadyGraph"] [name="title"]','Фрагмент без внешней опоры',false);await page.select('[data-form="packReadyGraph"] [name="scope"]','view');await page.click('[data-form="packReadyGraph"] [type="submit"]');assert.match(await text('#packReadyError'),/опорные блоки вне фрагмента/);assert.deepEqual(await graphIds(),view);assert.deepEqual(await historyIds(),before);assert.equal(await visible('#readyGraphBar'),false);await page.click('#side [data-act="close"]');
  });
  await check('custom lens graphs are reusable catalog entries and can be referenced by recommendation packages',async()=>{
   await page.reload({waitUntil:'load'});await showInfo('R1');await operation('packReadyGraph');await type('[data-form="packReadyGraph"] [name="title"]','Моя линза проверки',false);await page.select('[data-form="packReadyGraph"] [name="readyKind"]','lens');await page.select('[data-form="packReadyGraph"] [name="scope"]','view');await page.click('[data-form="packReadyGraph"] [type="submit"]');const lens=await page.$eval('[data-catalog-package].active',e=>e.dataset.catalogPackage);assert(lens.startsWith('lens-custom-'));assert.equal(await count('[data-act="insertTemplate"]'),0);assert.equal(await count('[data-act="openLensContext"]'),1);
   await openCatalogGraph('service');await newPackage('Моя линза для требований',{types:['requirement'],lenses:[lens]});await showInfo('R1');assert((await recommended()).includes(lens));const before=await historyIds();await page.click('[data-recommended-lens="'+lens+'"]');assert.match(await text('#readyGraphBar'),/Моя линза проверки/);await page.click('[data-act="lensProcess"]');assert.deepEqual(await historyIds(),before);assert.deepEqual(await graphIds(),['D1','R1']);
  });
  await check('recommendation drafts, validation and cancel preserve saved rules and independent screen state',async()=>{
   await page.reload({waitUntil:'load'});const first=(await screenIds())[0],before=await historyIds();await showInfo('R1');await page.click('[data-configure-node-lenses="R1"]');assert.equal(await page.$eval('[name="scopeKind"]',e=>e.value),'entity');await type('[data-form="recommendationPackage"] [name="title"]','Черновик рекомендации',false);await page.click('[data-form="recommendationPackage"] [type="submit"]');assert.match(await text('#recommendationError'),/хотя бы один граф линзы/);assert.deepEqual(await historyIds(),before);
   await fillRule({types:['requirement'],scope:'descendants',anchor:'R1',state:'open',tag:'2d',lenses:['lens-2d-review']});await page.$eval('#panelBody',e=>e.scrollTop=0);await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-recommendation-editor.png')});await page.click('#newScreenButton');const second=(await screenIds())[1];await page.click('[data-act="recommendationPackages"]');await switchTab(first);assert.equal(await page.$eval('[name="title"]',e=>e.value),'Черновик рекомендации');assert.equal(await page.$eval('[name="anchorId"]',e=>e.value),'R1');assert.equal(await page.$eval('[name="conditionState"]',e=>e.value),'open');assert.equal(await page.$eval('[name="tag"]',e=>e.value),'2d');assert.equal(await page.$eval('[name="lensId"][value="lens-2d-review"]',e=>e.checked),true);await page.click('[data-act="recommendationPackages"]');assert.equal(await count('#side [data-edit-recommendation-package]:not([hidden])'),0);await switchTab(second);assert.equal(await text('#panelTitle'),'Пакеты рекомендаций линз');assert.deepEqual(await historyIds(),before);
   await page.reload({waitUntil:'load'});
  });

  const showPackageCatalog=async()=>{
   if(!await visible('#catalogDrawer'))await page.click('#graphsButton');await page.click('[data-explorer-tab="packages"]');
   if(await count('#explorerPackageContent [data-explorer-packages-back]'))await page.click('[data-explorer-packages-back]');
   if(await count('#explorerPackageContent [data-form="recommendationPackage"]'))await page.click('#explorerPackageContent form>button[data-act="recommendationPackages"]');
  };
  const closeExplorer=async()=>{if(await visible('#catalogDrawer'))await page.click('#catalogHeader');};
  await check('a graph lists only connected packages; Add uses a searchable paged picker and detach preserves the catalog entry',async()=>{
   await page.reload({waitUntil:'load'});await page.click('#lensesButton');assert.equal(await count('#side [data-recommendation-package]'),1);assert.equal(await count('#side [name="packageId"]'),0);assert.equal(await count('#side [data-recommendation-package="RP-2d"]'),0);assert.equal(await count('#side [data-act="newRecommendationPackage"]'),0);
   const before=await historyIds(),nodesBefore=await graphIds();await page.click('[data-act="addRecommendationPackage"]');assert.equal(await count('#side [data-package-candidate]'),10);assert.equal(await count('#side [data-package-candidate="RP-fundamental"]'),0);await page.click('#side [data-package-page="1"]');assert(await count('#side [data-package-candidate]')>0);await type('#recommendationPickerSearch','нет такого пакета',false);assert.equal(await count('#side [data-package-candidate]'),0);await page.click('#side [data-act="recommendationPackages"]');assert.deepEqual(await historyIds(),before);
   await page.click('[data-act="addRecommendationPackage"]');await type('#recommendationPickerSearch','RP-2d',false);assert.equal(await count('#side [data-package-candidate]'),1);await page.click('[data-attach-recommendation-package="RP-2d"]');assert.equal(await count('#side [data-recommendation-package]'),2);await page.click('[data-detach-recommendation-package="RP-2d"]');assert.equal(await count('#side [data-recommendation-package]'),1);assert.deepEqual(await graphIds(),nodesBefore);
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-connected-packages.png')});await showPackageCatalog();await type('#packageSearch','RP-2d',false);assert.equal(await count('[data-package-row="RP-2d"]'),1);
  });
  await check('Explorer package search, details, lens links and usage stay inside the drawer without changing Graph or Plan',async()=>{
   await page.reload({waitUntil:'load'});const beforeNodes=await graphIds(),beforeHistory=await historyIds(),beforePlan=await planIds('main'),beforeBox=await graphBox();await page.click('#graphsButton');await type('#catalogSearch','Запуск сервиса',false);await page.click('[data-explorer-tab="packages"]');assert.equal(await visible('#explorerGraphsPanel'),false);assert.equal(await visible('#explorerPackagesPanel'),true);assert.equal(await count('[data-package-row]'),10);
   await type('#packageSearch','RP-fundamental',false);await page.click('[data-package-row="RP-fundamental"]');assert.match(await text('#explorerPackageHeading'),/фундаментальные/);assert.equal(await count('#explorerPackageContent [data-explorer-edit-package]'),0);assert.equal(await count('#explorerPackageContent [data-explorer-copy-package]'),1);assert.equal(await count('#explorerPackageContent [data-package-usage-graph]'),3);assert(await count('#explorerPackageContent [data-explorer-lens]')>0);
   assert.deepEqual(await graphIds(),beforeNodes);assert.deepEqual(await historyIds(),beforeHistory);assert.deepEqual(await planIds('main'),beforePlan);assert.equal(await graphBox(),beforeBox);
   await page.click('[data-explorer-tab="graphs"]');assert.equal(await page.$eval('#catalogSearch',e=>e.value),'Запуск сервиса');await page.focus('[data-explorer-tab="graphs"]');await page.keyboard.press('ArrowRight');assert.equal(await visible('#explorerPackagesPanel'),true);assert.match(await text('#explorerPackageHeading'),/фундаментальные/);await page.click('[data-explorer-packages-back]');assert.equal(await page.$eval('#packageSearch',e=>e.value),'RP-fundamental');
   for(const width of [1024,1440]){await page.setViewport({width,height:1000});assert(await page.$eval('#explorerPackagesPanel',e=>e.scrollWidth<=e.clientWidth+1));assert(await page.evaluate(()=>document.querySelector('.app').scrollWidth<=innerWidth));}
   await page.click('[data-package-row="RP-fundamental"]');await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-explorer-package-details.png')});await page.click('#catalogHeader .explorer-name');assert.equal(await visible('#catalogDrawer'),false);
  });
  await check('Explorer creates, edits and copies packages without implicit attachment and keeps an unfinished catalog draft across screen switches',async()=>{
   await page.reload({waitUntil:'load'});const beforeNodes=await graphIds(),beforeHistory=await historyIds();await showPackageCatalog();await page.click('[data-explorer-new-package]');assert.equal(await page.$eval('#explorerPackageContent [name="connectAfterSave"]',e=>e.checked),false);await type('#explorerPackageContent [name="title"]','Создано в каталоге',false);await fillRule({types:['action'],lenses:['lens-code-review']});await page.select('#explorerPackageContent [name="contextGraphId"]','lens-app-review');
   await closeExplorer();await page.click('#newScreenButton');await page.click('#graphsButton');assert.equal(await page.$eval('#explorerPackageContent [name="title"]',e=>e.value),'Создано в каталоге');assert.equal(await page.$eval('#explorerPackageContent [name="contextGraphId"]',e=>e.value),'lens-app-review');await page.click('#explorerPackageContent [type="submit"]');assert.equal(await text('#explorerPackageHeading'),'Создано в каталоге');assert.equal(await count('#explorerPackageContent [data-package-usage-graph]'),0);assert.deepEqual(await graphIds(),beforeNodes);assert.deepEqual(await historyIds(),beforeHistory);assert.equal(await visible('#side'),false);
   const pack=await page.$eval('#explorerPackageContent [data-explorer-edit-package]',e=>e.dataset.explorerEditPackage);await page.click('[data-explorer-edit-package="'+pack+'"]');await type('#explorerPackageContent [name="title"]','Уточнённый пакет каталога',false);await page.click('#explorerPackageContent [type="submit"]');assert.equal(await text('#explorerPackageHeading'),'Уточнённый пакет каталога');assert.match(await text('#explorerPackageContent'),/revision 2/);await page.click('[data-explorer-edit-package="'+pack+'"]');await type('#explorerPackageContent [name="title"]','Несохранённое имя',false);await page.click('#explorerPackageContent form>button[data-act="recommendationPackages"]');await type('#packageSearch',pack,false);await page.click('[data-package-row="'+pack+'"]');assert.equal(await text('#explorerPackageHeading'),'Уточнённый пакет каталога');
   await showPackageCatalog();await type('#packageSearch','RP-fundamental',false);await page.click('[data-package-row="RP-fundamental"]');await page.click('[data-explorer-copy-package="RP-fundamental"]');await type('#explorerPackageContent [name="title"]','Моя копия фундаментального пакета',false);await page.click('#explorerPackageContent [type="submit"]');assert.equal(await text('#explorerPackageHeading'),'Моя копия фундаментального пакета');assert.equal(await count('#explorerPackageContent [data-package-usage-graph]'),0);assert.deepEqual(await historyIds(),beforeHistory);await closeExplorer();await page.click('#lensesButton');assert.equal(await count('#side [data-recommendation-package]'),1);
  });
  await check('saving a package in Explorer preserves an unrelated unfinished node recommendation editor',async()=>{
   await page.reload({waitUntil:'load'});await showInfo('R1');await page.click('[data-configure-node-lenses="R1"]');await type('#side [name="title"]','Несохранённые линзы для R1',false);await setChecks('#side [name="lensId"]',['lens-core']);await showPackageCatalog();await page.click('[data-explorer-new-package]');await type('#explorerPackageContent [name="title"]','Отдельный пакет каталога',false);await setChecks('#explorerPackageContent [name="lensId"]',['lens-human']);await page.click('#explorerPackageContent [type="submit"]');assert.equal(await text('#explorerPackageHeading'),'Отдельный пакет каталога');await closeExplorer();assert.equal(await page.$eval('#side [name="title"]',e=>e.value),'Несохранённые линзы для R1');assert.equal(await page.$eval('#side [name="lensId"][value="lens-core"]',e=>e.checked),true);assert.equal(await page.$eval('#side [name="scopeKind"]',e=>e.value),'entity');assert.equal(await page.$eval('#side [name="anchorId"]',e=>e.value),'R1');await page.click('#side [type="submit"]');assert.match(await text('#side'),/Несохранённые линзы для R1/);assert.doesNotMatch(await text('#side'),/Отдельный пакет каталога/);
  });
  await check('Explorer graph trees expose package participation for processes, templates and lenses, including editable lens recommendations',async()=>{
   await page.reload({waitUntil:'load'});const pack=await newPackage('Общий пакет для трёх графов',{lenses:['lens-3d-review']});assert(pack);await openCatalogGraph('ready-app-flow');const templateNodes=await graphIds();await connectPackages(['RP-template-ready-app-flow',pack]);assert.deepEqual(await graphIds(),templateNodes);assert.equal(await page.$eval('#planButton',e=>e.disabled),true);
   await openCatalogGraph('lens-app-review');await connectPackages(['RP-lens-lens-app-review',pack]);await showInfo('R1');assert((await recommended()).includes('lens-3d-review'));assert((await recommended()).includes('lens-code-review'));
   await page.click('#graphsButton');await page.click('[data-explorer-tab="graphs"]');await type('#catalogSearch',pack,false);for(const id of ['service','ready-app-flow','lens-app-review'])assert.equal(await count('[data-graph-packages="'+id+'"] [data-explorer-package="'+pack+'"]'),1);
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-explorer-graph-packages.png')});await page.click('[data-graph-packages="lens-app-review"] [data-explorer-package="'+pack+'"]');assert.equal(await visible('#catalogDrawer'),true);assert.equal(await count('#explorerPackageContent [data-package-usage-graph]'),3);for(const id of ['service','ready-app-flow','lens-app-review'])assert.equal(await count('#explorerPackageContent [data-package-usage-graph="'+id+'"]'),1);
   await page.click('[data-package-usage-graph="ready-app-flow"]');assert.equal(await visible('#catalogDrawer'),true);assert.match(await text('#readyGraphBar'),/Шаблон графа/);assert.equal(await visible('#explorerPackagesPanel'),true);
  });
  await check('nested and cyclic lens references preserve the original process and per-screen return chain without automatic execution',async()=>{
   await page.reload({waitUntil:'load'});await openCatalogGraph('lens-human');await newPackage('Из результата вернуться к приложению',{types:['requirement'],lenses:['lens-app-review']});await openCatalogGraph('service');await newPackage('Для D3 начать проверку приложения',{types:['decision'],scope:'entity',anchor:'D3',lenses:['lens-app-review']});await showInfo('D3');const beforeHistory=await historyIds(),beforePlan=await planIds('main');await page.click('[data-recommended-lens="lens-app-review"]');assert.match(await text('#readyGraphBar'),/Фокус D3/);await showInfo('R0');const appBox=await graphBox(),first=(await screenIds())[0];await page.click('#newScreenButton');const second=(await screenIds())[1];
   await page.click('[data-recommended-lens="lens-code-review"]');assert.equal(await count('#readyGraphBar [data-lens-trail-index]'),1);assert.match(await text('#readyGraphBar'),/Фокус D3/);await showInfo('R0');await page.click('[data-recommended-lens="lens-human"]');assert.equal(await count('#readyGraphBar [data-lens-trail-index]'),2);assert.match(await text('#readyGraphBar'),/Для: Запуск сервиса/);
   await switchTab(first);assert.match(await text('#readyGraphBar'),/Проверка приложения/);assert.equal(await count('#readyGraphBar [data-lens-trail-index]'),0);await switchTab(second);assert.equal(await count('#readyGraphBar [data-lens-trail-index]'),2);await showInfo('R0');await page.click('[data-recommended-lens="lens-app-review"]');assert.equal(await count('#readyGraphBar [data-lens-trail-index]'),3);assert.equal((await graphIds()).length,7);await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-nested-lenses.png')});
   await page.click('[data-lens-trail-index="0"]');assert.equal(await count('#readyGraphBar [data-lens-trail-index]'),0);assert.equal(await graphBox(),appBox);assert.equal(await text('#panelTitle'),'Сведения · R0');await page.click('[data-act="lensProcess"]');assert.match(await text('#breadcrumb'),/Фокус · граф D3/);assert.match(await text('#nodes [data-node="D3"]'),/обнаружено/);await ensurePlan();assert.deepEqual(await historyIds(),beforeHistory);assert.deepEqual(await planIds('main'),beforePlan);await page.click('#allButton');assert.equal((await graphIds()).length,12);
  });
  await check('attaching an identity-bound foreign package to a template cannot silently rebind equal short IDs on insertion',async()=>{
   await page.reload({waitUntil:'load'});const pack=await newPackage('Внешняя опора R0 процесса',{scope:'descendants',anchor:'R0'}),beforeNodes=await graphIds(),beforeHistory=await historyIds();await openCatalogGraph('ready-app-flow');await connectPackages(['RP-template-ready-app-flow',pack]);assert.match(await text('#side [data-recommendation-package="'+pack+'"]'),/совпадений 0/);await page.click('#side [data-act="close"]');await insertTemplate('R0');assert.equal(await visible('#readyWorkflowError'),true);assert.match(await text('#readyWorkflowError'),/опора в другом графе/);await openCatalogGraph('service');assert.deepEqual(await graphIds(),beforeNodes);await ensurePlan();assert.deepEqual(await historyIds(),beforeHistory);
  });
  await check('a custom lens carries its own recommendation package and can delegate another lens while keeping the working entity identity',async()=>{
   await page.reload({waitUntil:'load'});await newPackage('Следующая линза для R1',{types:['requirement'],scope:'entity',anchor:'R1',lenses:['lens-code-review']});await showInfo('R1');await operation('packReadyGraph');await type('[data-form="packReadyGraph"] [name="title"]','Линза с вложенной рекомендацией',false);await page.select('[data-form="packReadyGraph"] [name="readyKind"]','lens');await page.select('[data-form="packReadyGraph"] [name="scope"]','view');await page.click('[data-form="packReadyGraph"] [type="submit"]');const lens=await page.$eval('[data-catalog-package].active',e=>e.dataset.catalogPackage);await page.click('[data-act="openLensContext"]');await page.select('[data-form="readyWorkflow"] [name="scope"]','focus:R1');await page.click('[data-form="readyWorkflow"] [type="submit"]');await showInfo('R1');assert((await recommended()).includes('lens-code-review'));await page.click('[data-recommended-lens="lens-code-review"]');assert.match(await text('#readyGraphBar'),/Фокус R1/);assert.match(await text('#readyGraphBar'),/Линза с вложенной рекомендацией/);await page.click('[data-lens-trail-index="0"]');assert.equal(await text('#panelTitle'),'Сведения · R1');await page.click('#lensesButton');const bundle=await page.$eval('#side [data-recommendation-package]',e=>e.dataset.recommendationPackage);await page.click('#side [data-explorer-package="'+bundle+'"]');assert.equal(await count('#explorerPackageContent [data-package-usage-graph="'+lens+'"]'),1);assert.equal(await count('#explorerPackageContent [data-package-usage-graph="service"]'),0);await closeExplorer();await page.click('[data-act="lensProcess"]');assert.deepEqual(await graphIds(),['D1','R1']);await page.reload({waitUntil:'load'});
  });

  const groupMembers=()=>page.$$eval('[data-form="decisionGroup"] [name="member"]:checked',es=>es.map(e=>e.value).sort());
  const groupEditor=async id=>{await operation('decisionGroup');await page.select('[data-form="decisionGroup"] [name="group"]',id);};
  const setGroupPolicy=async(id,exclusive)=>{await groupEditor(id);await page.$eval('[data-form="decisionGroup"] [name="mutuallyExclusive"]',(e,v)=>e.checked=v,exclusive);await page.click('[data-form="decisionGroup"] [type="submit"]');};
  const externalSelectionAction=async(title,targets,kind='select_decision')=>{
   await operation('addAction');await page.select('[data-form="addAction"] [name="actionType"]',kind);await type('[data-form="addAction"] [name="title"]',title,false);
   await setChecks('[data-form="addAction"] [name="targetRef"]',targets);await setChecks('[data-form="addAction"] [name="groupRef"]',[]);
   if(kind==='decide_acceptance')await page.select('[data-form="addAction"] [name="decisionOutcome"]','unselected');
   await page.click('[data-form="addAction"] [type="submit"]');return (await text('#panelTitle')).split(' · ')[1];
  };
  await check('group selector restores the chosen policy and participants without committing a draft',async()=>{
   await page.reload({waitUntil:'load'});await showInfo('D1');const history=await historyIds();await groupEditor('G4');assert.deepEqual(await groupMembers(),['D3','D4']);assert.equal(await page.$eval('[name="selectionRequired"]',e=>e.checked),true);
   await page.select('[data-form="decisionGroup"] [name="group"]','G3');assert.deepEqual(await groupMembers(),['D5']);assert.equal(await page.$eval('[name="selectionRequired"]',e=>e.checked),false);assert.equal(await page.$eval('[name="mutuallyExclusive"]',e=>e.checked),false);await page.$eval('[name="selectionRequired"]',e=>e.checked=true);await page.select('[data-form="decisionGroup"] [name="group"]','G4');assert.deepEqual(await groupMembers(),['D3','D4']);assert.equal(await page.$eval('[name="mutuallyExclusive"]',e=>e.checked),true);assert.deepEqual(await historyIds(),history);await page.click('#side [data-act="close"]');
  });
  await check('group membership changes update real graph relations and strict focus as one state',async()=>{
   await page.reload({waitUntil:'load'});await showInfo('D1');await groupEditor('G1');await setChecks('[data-form="decisionGroup"] [name="member"]',['D1','D3']);await page.click('[data-form="decisionGroup"] [type="submit"]');await page.click('#allButton');
   const pairs=await page.$$eval('#edges path[data-edge-type="DECISION_MEMBER"]',es=>es.map(e=>({from:e.dataset.edgeFrom,to:e.dataset.edgeTo,groups:e.nextElementSibling?.dataset.groupIds})).filter(e=>e.from==='R0'));
   assert.equal(pairs.find(e=>e.to==='D2').groups,'G2');assert.equal(pairs.find(e=>e.to==='D3').groups,'G1,G2');assert.equal(pairs.filter(e=>e.to==='D3').length,1);await showInfo('D3');assert.match(await text('#side'),/G1/);await page.click('#side [data-group-ref="G1"]');assert.deepEqual(await graphIds(),['D1','D3','R0']);assert.equal(await count('#edges [data-group-ids="G1,G2"]'),1);assert.equal(await count('#nodes [data-node="D2"]'),0);
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-group-membership.png')});
  });
  await check('exclusive group validation rejects conflicting selected members without partial mutation',async()=>{
   await page.reload({waitUntil:'load'});await showInfo('D3');await setGroupPolicy('G4',false);await showInfo('D3');await page.click('#side [data-act="selectDecision"]');await showInfo('D4');await page.click('#side [data-act="selectDecision"]');await groupEditor('G4');const before=await historyIds();await page.$eval('[name="mutuallyExclusive"]',e=>e.checked=true);await page.click('[data-form="decisionGroup"] [type="submit"]');assert.match(await text('[data-decision-group-error]'),/выбраны D3, D4/);assert.deepEqual(await historyIds(),before);await page.click('#side [data-act="close"]');await groupEditor('G4');assert.equal(await page.$eval('[name="mutuallyExclusive"]',e=>e.checked),false);await page.click('#side [data-act="close"]');
   await showInfo('D4');await page.click('#side [data-act="markUnselected"]');await setGroupPolicy('G4',true);await groupEditor('G4');assert.equal(await page.$eval('[name="mutuallyExclusive"]',e=>e.checked),true);await page.click('#side [data-act="close"]');
  });
  await check('selection Actions validate all targets before writing and preserve completed Decisions',async()=>{
   await page.reload({waitUntil:'load'});await showInfo('D3');let action=await externalSelectionAction('Несовместимый выбор двух решений',['D3','D4']);await page.click('#allButton');await operation('completeAction');await page.select('[data-form="completeAction"] [name="node"]',action);let history=await historyIds();await page.click('[data-form="completeAction"] [type="submit"]');assert.match(await text('#toast'),/G4.*не более одного/);await page.click('#allButton');assert.match(await text('#nodes [data-node="D3"]'),/обнаружено/);assert.match(await text('#nodes [data-node="D4"]'),/обнаружено/);assert.deepEqual(await historyIds(),history);assert.equal(await count('[data-form="completeAction"] [name="node"] option[value="'+action+'"]'),1);await page.click('#side [data-act="close"]');
   action=await externalSelectionAction('Выбор без указанного решения',[]);await operation('completeAction');await page.select('[data-form="completeAction"] [name="node"]',action);history=await historyIds();await page.click('[data-form="completeAction"] [type="submit"]');assert.match(await text('#toast'),/хотя бы на один Decision/);assert.deepEqual(await historyIds(),history);
   await page.reload({waitUntil:'load'});await showInfo('D3');await page.click('#side [data-act="selectDecision"]');await operation('completeAction');await page.select('[data-form="completeAction"] [name="node"]','A12');await page.click('[data-form="completeAction"] [type="submit"]');await showInfo('D3');await page.click('#side [data-act="completeDecision"]');assert.match(await text('#nodes [data-node="D3"]'),/завершено/);
   action=await externalSelectionAction('Отмена уже завершённого решения',['D3'],'decide_acceptance');await operation('completeAction');await page.select('[data-form="completeAction"] [name="node"]',action);history=await historyIds();await page.click('[data-form="completeAction"] [type="submit"]');assert.match(await text('#toast'),/Завершённый Decision/);assert.deepEqual(await historyIds(),history);await page.click('#allButton');assert.match(await text('#nodes [data-node="D3"]'),/завершено/);
  });

  const graphCamera=()=>page.$eval('#graph',svg=>{const m=svg.getScreenCTM();return {viewBox:svg.getAttribute('viewBox'),matrix:[m.a,m.b,m.c,m.d,m.e,m.f]};});
  const branchRoots=()=>page.$$eval('#nodes [data-occurrence][data-branch-root="true"]',es=>es.map(e=>({id:e.dataset.occurrence,entityId:e.dataset.entityId,expanded:e.dataset.branchExpanded==='true'})));
  const branchRoot=async id=>{const item=(await branchRoots()).find(x=>x.entityId===id);assert(item,'branch entrance for '+id);return item.id;};
  const branchSelector=id=>'#nodes [data-occurrence="'+id+'"]';
  const branchShot=async name=>{await page.waitForFunction(()=>document.querySelector('#toast').hidden,{timeout:5000});await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-shared-branch-'+name+'.png')});};
  await check('full Graph routes a shared Decision to a local collapsed reference of the same kind',async()=>{
   await page.reload({waitUntil:'load'});if(await visible('#timeline'))await page.click('#planButton');await page.click('#allButton');const root=await branchRoot('D3');
   assert.equal((await branchRoots()).length,1);assert.equal(await page.$eval(branchSelector(root),e=>e.getAttribute('aria-expanded')),'false');assert.equal(await count('#nodes [data-node]'),12);
   const routes=await page.$$eval('#edges path[data-edge-to="D3"]',es=>es.map(e=>({from:e.dataset.edgeFrom,to:e.dataset.routeTo})));assert.deepEqual(routes,[{from:'R0',to:root},{from:'R2',to:'D3'}]);
   const palette=await page.$$eval('#nodes [data-entity-id="D3"] .border',es=>es.map(e=>e.getAttribute('fill')));assert.equal(palette.length,2);assert.equal(palette[0],palette[1]);assert.match(await text(branchSelector(root)),/общая ветка/);
   assert.equal(await count('#nodes [data-occurrence][data-entity-id="D1"]'),0);assert.equal(await count('#nodes [data-occurrence][data-entity-id="D2"]'),0);assert(await page.$$eval('#nodes text[font-size="14"]',es=>es.every(e=>e.getComputedTextLength()<=192.5)));await branchShot('collapsed');
  });
  await check('expansion repeats downstream Actions with true endpoints and never adds Plan or History entries',async()=>{
   const root=await branchRoot('D3'),beforeHistory=await historyIds(),beforePlan=await planIds('manual'),beforeMain=await planIds('main'),beforeGraph=await graphIds();
   const collapsedCamera=await graphCamera();await page.$eval('[data-branch-toggle="'+root+'"]',e=>e.focus());await page.keyboard.press('Enter');assert.deepEqual(await graphCamera(),collapsedCamera,'expansion preserves scale and camera');assert.equal(await page.$eval(branchSelector(root),e=>e.getAttribute('aria-expanded')),'true');
   const child=await page.$eval('#nodes [data-occurrence][data-entity-id="A12"]',e=>e.dataset.occurrence);assert.equal(await count('#edges [data-route-from="'+root+'"][data-route-to="'+child+'"][data-edge-type="REQUIRES_ACTION"]'),1);
   assert.deepEqual(await graphIds(),beforeGraph);assert.deepEqual(await historyIds(),beforeHistory);assert.deepEqual(await planIds('manual'),beforePlan);assert.deepEqual(await planIds('main'),beforeMain);await page.click('[data-act="fit"]');await branchShot('expanded');
   await page.click('[data-occurrence-details="'+root+'"]');assert.doesNotMatch(await text('#breadcrumb'),/Фокус/);assert.match(await text('#side'),/Одна общая сущность · D3/);
   await operation('place');const ids=await page.$$eval('[data-form="place"] [name="node"] option',es=>es.map(e=>e.value));assert.equal(ids.filter(id=>id==='D3').length,1);assert.equal(ids.filter(id=>id==='A12').length,1);await page.click('#side [data-act="close"]');
   await page.click('#nodes [data-node="D3"]');assert.equal(await count('#nodes [data-occurrence]'),0);assert.deepEqual(await graphIds(),['A12','D3','R0','R2']);await page.click('#allButton');assert.equal(await page.$eval(branchSelector(root),e=>e.dataset.branchExpanded),'true');
   const expandedCamera=await graphCamera();await page.$eval(branchSelector(root),e=>e.focus());await page.keyboard.press('Space');assert.equal(await count('#nodes [data-occurrence][data-entity-id="A12"]'),0);assert.deepEqual(await graphCamera(),expandedCamera,'collapse preserves scale and camera');
   await page.click('[data-act="in"]');const zoomedCamera=await graphCamera();await page.hover(branchSelector(root));await page.mouse.wheel({deltaY:60});await page.waitForFunction(previous=>document.querySelector('#graph').getAttribute('viewBox')!==previous,{},zoomedCamera.viewBox);const adjustedCamera=await graphCamera();assert.notDeepEqual(adjustedCamera,expandedCamera);
   await page.click(branchSelector(root));assert.equal(await page.$eval(branchSelector(root),e=>e.dataset.branchExpanded),'true');assert.deepEqual(await graphCamera(),adjustedCamera,'pointer expansion preserves user zoom and pan');
   await page.click('[data-branch-toggle="'+root+'"]');assert.equal(await page.$eval(branchSelector(root),e=>e.dataset.branchExpanded),'false');assert.deepEqual(await graphCamera(),adjustedCamera,'pointer collapse preserves user zoom and pan');assert.deepEqual(await historyIds(),beforeHistory);
  });
  await check('a shared Requirement keeps its identity and descendants when one Decision is unselected',async()=>{
   await page.reload({waitUntil:'load'});await operation('link');await page.select('[data-form="link"] [name="from"]','D2');await page.select('[data-form="link"] [name="to"]','R2');await page.select('[data-form="link"] [name="type"]','INTRODUCES');await page.click('[data-form="link"] [type="submit"]');await page.click('#allButton');
   const root=await branchRoot('R2'),beforeHistory=await historyIds(),beforeGraph=await graphIds(),beforeCamera=await graphCamera();await page.click('[data-branch-toggle="'+root+'"]');assert.deepEqual(await graphCamera(),beforeCamera,'shared Requirement expansion preserves the camera');
   for(const id of ['D3','D4','D5','A11','A12'])assert.equal(await count('#nodes [data-occurrence][data-branch-root="false"][data-entity-id="'+id+'"]'),1,id);assert.deepEqual(await graphIds(),beforeGraph);assert.deepEqual(await historyIds(),beforeHistory);await page.click('[data-act="fit"]');await branchShot('requirement');
   await showInfo('D1');await page.click('#side [data-act="markUnselected"]');await showInfo('D2');await page.click('#side [data-act="selectDecision"]');assert.match(await text('#nodes [data-node="D2"]'),/выбрано/);
   await showInfo('R2');assert.deepEqual(await graphIds(),['A11','D1','D2','D3','D4','D5','R2']);assert.match(await text('#nodes [data-node="R2"]'),/Активна/);assert.equal(await count('#nodes [data-occurrence]'),0);assert.equal(await count('#edges [data-edge-to="R2"][data-edge-type="INTRODUCES"]'),2);assert.match(await text('#side'),/Одна общая сущность · R2/);
   await page.click('#allButton');assert.deepEqual(await graphIds(),beforeGraph);assert.equal(await page.$eval(branchSelector(root),e=>e.dataset.branchExpanded),'true');
  });
  await check('editing through a repeated block updates the one entity and all visual labels',async()=>{
   await page.reload({waitUntil:'load'});await page.click('#allButton');const root=await branchRoot('D3');await page.click('[data-branch-toggle="'+root+'"]');const before=await historyIds(),ids=await graphIds();
   await page.click('[data-occurrence-details="'+root+'"]');assert.doesNotMatch(await text('#breadcrumb'),/Фокус/);await page.click('#side [data-act="edit"]');await type('[data-form="edit"] [name="title"]','Общий способ проверки',false);await page.click('[data-form="edit"] [type="submit"]');
   const labels=await page.$$eval('#nodes [data-entity-id="D3"]',es=>es.map(e=>e.textContent));assert.equal(labels.length,2);assert(labels.every(s=>s.includes('Общий способ проверки')));assert.deepEqual(await graphIds(),ids);assert.equal((await historyIds()).length,before.length+1);assert.equal(await count('#nodes [data-node="D3"]'),1);assert.doesNotMatch(await text('#breadcrumb'),/Фокус/);await branchShot('edited');
   await page.click('[data-occurrence-details="'+root+'"]');await page.click('#side [data-graph-ref="D3"]');assert.equal(await count('#nodes [data-occurrence]'),0);assert.match(await text('#nodes [data-node="D3"]'),/Общий способ проверки/);await page.click('#allButton');assert.equal(await page.$eval(branchSelector(root),e=>e.dataset.branchExpanded),'true');
  });
  await check('screens keep independent branch expansion while sharing the same edited identity',async()=>{
   await page.reload({waitUntil:'load'});await page.click('#allButton');const first=(await screenIds())[0],root=await branchRoot('D3');await page.click('[data-branch-toggle="'+root+'"]');await page.click('[data-new-screen]');const second=(await screenIds()).find(id=>id!==first);
   await page.click('[data-branch-toggle="'+root+'"]');assert.equal(await page.$eval(branchSelector(root),e=>e.dataset.branchExpanded),'false');await switchTab(first);assert.equal(await page.$eval(branchSelector(root),e=>e.dataset.branchExpanded),'true');await switchTab(second);assert.equal(await page.$eval(branchSelector(root),e=>e.dataset.branchExpanded),'false');
   await page.click('[data-occurrence-details="'+root+'"]');await page.click('#side [data-act="edit"]');await type('[data-form="edit"] [name="title"]','Общая правка во вкладках',false);await page.click('[data-form="edit"] [type="submit"]');const after=await historyIds();await switchTab(first);assert.equal(await page.$eval(branchSelector(root),e=>e.dataset.branchExpanded),'true');assert.match(await text(branchSelector(root)),/Общая правка во вкладках/);assert.match(await text('#nodes [data-node="D3"]'),/Общая правка во вкладках/);assert.deepEqual(await historyIds(),after);await page.reload({waitUntil:'load'});
  });

  const layoutStorageKey='rdg.prototype.layouts.v1',serviceLayoutKey=JSON.stringify(['rdg-prototype-decision-v1','service']);
  const position=async(id,targetPage=page)=>targetPage.$eval('#nodes [data-node="'+id+'"]',e=>{const m=e.transform.baseVal.consolidate().matrix;return {x:m.e,y:m.f};});
  const storedLayout=()=>page.evaluate(key=>localStorage.getItem(key),layoutStorageKey);
  const dragNode=async(id,dx,dy,occurrence=false)=>{
   const selector=occurrence?branchSelector(id):'#nodes [data-node="'+id+'"]';
   const move=await page.$eval(selector,(e,delta)=>{
    const svg=document.querySelector('#graph'),rect=e.getBoundingClientRect(),frame=svg.getBoundingClientRect(),x=(Math.max(rect.left,frame.left)+Math.min(rect.right,frame.right))/2,y=(Math.max(rect.top,frame.top)+Math.min(rect.bottom,frame.bottom))/2;
    const p=svg.createSVGPoint();p.x=x;p.y=y;const a=p.matrixTransform(svg.getScreenCTM().inverse());p.x+=delta.dx;p.y+=delta.dy;const b=p.matrixTransform(svg.getScreenCTM().inverse());
    const m=e.transform.baseVal.consolidate().matrix;return {x,y,expected:{x:m.e+b.x-a.x,y:m.f+b.y-a.y}};
   },{dx,dy});
   await page.mouse.move(move.x,move.y);await page.mouse.down();await page.mouse.move(move.x+dx,move.y+dy,{steps:8});await page.mouse.up();
   const actual=await page.$eval(selector,e=>{const m=e.transform.baseVal.consolidate().matrix;return {x:m.e,y:m.f};});assert(Math.abs(actual.x-move.expected.x)<0.15);assert(Math.abs(actual.y-move.expected.y)<0.15);return actual;
  };
  let durableR0,durableR1,durableAction,durableBranchRoot,durableBranchChild;
  const occurrencePosition=(id,targetPage=page)=>targetPage.$eval(branchSelector(id),e=>{const m=e.transform.baseVal.consolidate().matrix;return {x:m.e,y:m.f};});
  await check('drag moves world coordinates and edges, persists state, and does not activate focus',async()=>{
   await page.reload({waitUntil:'load'});
   const beforeHistory=await historyIds(),beforeBox=await page.$eval('#graph',e=>e.getAttribute('viewBox'));
   const beforeEdge=await page.$eval('[data-edge-from="R0"][data-edge-to="D1"]',e=>e.getAttribute('d'));
   durableR0=await dragNode('R0',-90,45);assert(durableR0.x<0);
   assert.doesNotMatch(await text('#breadcrumb'),/Фокус/);assert.deepEqual(await historyIds(),beforeHistory);
   assert.equal(await page.$eval('#graph',e=>e.getAttribute('viewBox')),beforeBox);
   assert.notEqual(await page.$eval('[data-edge-from="R0"][data-edge-to="D1"]',e=>e.getAttribute('d')),beforeEdge);
   assert.equal(await count('#nodes [data-node]'),12);assert.match(await text('#layoutStatus'),/сохранено/);
   const state=JSON.parse(await storedLayout());assert.equal(state.schemaVersion,1);assert.equal(state.revision,1);
   assert(Math.abs(state.layouts[serviceLayoutKey].positions.R0.x-durableR0.x)<0.15);
   const actionEdge=await page.$eval('[data-edge-to="A11"][data-edge-type="REQUIRES_ACTION"]',e=>e.getAttribute('d'));durableAction=await dragNode('A11',25,-15);assert.notEqual(await page.$eval('[data-edge-to="A11"][data-edge-type="REQUIRES_ACTION"]',e=>e.getAttribute('d')),actionEdge);assert.deepEqual(await historyIds(),beforeHistory);
   await page.reload({waitUntil:'load'});assert.deepEqual(await position('R0'),durableR0);assert.deepEqual(await position('A11'),durableAction);
   const savedBeforeFocus=await storedLayout();
   await page.click('#nodes [data-node="D1"]');assert.match(await text('#breadcrumb'),/Фокус · граф D1/); // short clicks still work after a drag
   assert.equal(await storedLayout(),savedBeforeFocus);
  });
  await check('visual occurrences drag independently, cancel cleanly, and restore collapsed or expanded branch coordinates',async()=>{
   await page.click('#allButton');const root=await branchRoot('D3'),canonicalD=await position('D3'),canonicalA=await position('A12'),beforeHistory=await historyIds(),beforePlan=await planIds('manual');
   durableBranchRoot={id:root,...await dragNode(root,22,-12,true)};assert.equal(await page.$eval(branchSelector(root),e=>e.dataset.branchExpanded),'false');
   await page.click('[data-branch-toggle="'+root+'"]');await page.click('[data-act="fit"]');const child=await page.$eval('#nodes [data-occurrence][data-entity-id="A12"]',e=>e.dataset.occurrence);durableBranchChild={id:child,...await dragNode(child,20,10,true)};
   const saved=await storedLayout(),old=await occurrencePosition(root),rect=await page.$eval(branchSelector(root),e=>{const r=e.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/3};});
   await page.mouse.move(rect.x,rect.y);await page.mouse.down();await page.mouse.move(rect.x+25,rect.y+15,{steps:5});await page.keyboard.press('Escape');await page.mouse.up();assert.deepEqual(await occurrencePosition(root),old);assert.equal(await storedLayout(),saved);
   assert.deepEqual(await position('D3'),canonicalD);assert.deepEqual(await position('A12'),canonicalA);assert.deepEqual(await historyIds(),beforeHistory);assert.deepEqual(await planIds('manual'),beforePlan);
   const state=JSON.parse(saved);assert.equal(state.layouts[serviceLayoutKey].occurrences[root].entityId,'D3');assert.equal(state.layouts[serviceLayoutKey].occurrences[child].entityId,'A12');assert.equal(state.layouts[serviceLayoutKey].occurrences[child].parentId,root);
   await page.reload({waitUntil:'load'});assert.deepEqual(await occurrencePosition(root),{x:durableBranchRoot.x,y:durableBranchRoot.y});assert.equal(await page.$eval(branchSelector(root),e=>e.dataset.branchExpanded),'false');assert.equal(await count(branchSelector(child)),0);await page.click('[data-branch-toggle="'+root+'"]');assert.deepEqual(await occurrencePosition(child),{x:durableBranchChild.x,y:durableBranchChild.y});await page.click('[data-branch-toggle="'+root+'"]');await page.click('#nodes [data-node="D1"]');
  });
  await check('drag under zoom, cancellation, canvas pan and independent Graph layout scopes',async()=>{
   await page.click('[data-act="in"]');await page.click('[data-act="in"]');const beforeBox=await page.$eval('#graph',e=>e.getAttribute('viewBox'));
   durableR1=await dragNode('R1',32,-18);assert.match(await text('#breadcrumb'),/Фокус · граф D1/);assert.equal(await page.$eval('#graph',e=>e.getAttribute('viewBox')),beforeBox);
   const saved=await storedLayout(),original=await position('D1'),rect=await page.$eval('[data-node="D1"]',e=>{const r=e.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};});
   await page.mouse.move(rect.x,rect.y);await page.mouse.down();await page.mouse.move(rect.x+35,rect.y+20,{steps:5});await page.keyboard.press('Escape');await page.mouse.up();
   assert.deepEqual(await position('D1'),original);assert.equal(await storedLayout(),saved);assert.match(await text('#layoutStatus'),/отменено/);
   await page.click('#allButton');
   const start=await page.evaluate(()=>{const v=document.querySelector('#graph').getBoundingClientRect();for(const [dx,dy] of [[20,100],[25,200],[v.width-25,100]]){const x=v.left+dx,y=v.top+dy;if(!document.elementFromPoint(x,y).closest('[data-node],[data-group-ids],.canvas-head,.zoom'))return {x,y};}throw Error('No blank canvas point');});
   const panBox=await page.$eval('#graph',e=>e.getAttribute('viewBox'));await page.mouse.move(start.x,start.y);await page.mouse.down();await page.mouse.move(start.x+40,start.y+25,{steps:5});await page.mouse.up();
   assert.notEqual(await page.$eval('#graph',e=>e.getAttribute('viewBox')),panBox);assert.equal(await storedLayout(),saved);assert.deepEqual(await position('R0'),durableR0);
   await page.click('#graphsButton');await page.click('[data-catalog-package="copy-service"]');assert.equal(await visible('#catalogDrawer'),true);await page.click('#catalogHeader');
   assert.deepEqual(await position('R0'),{x:65,y:300});const copyPosition=await dragNode('R0',65,20);
   await page.click('#graphsButton');await page.click('[data-catalog-package="service"]');assert.equal(await visible('#catalogDrawer'),true);await page.click('#catalogHeader');
   assert.deepEqual(await position('R0'),durableR0);assert.deepEqual(await position('R1'),durableR1);
   const doc=JSON.parse(await storedLayout());assert(Math.abs(doc.layouts[JSON.stringify(['rdg-prototype-decision-v1','copy-service'])].positions.R0.x-copyPosition.x)<0.15);
   await page.screenshot({path:path.join(process.env.RDG_SCREENSHOT_DIR,'rdg-prototype-drag-layout.png')});
  });
  await check('a working area uses the same saved coordinates as its Process Graph',async()=>{
   const before=await storedLayout();await openArea('WG1');assert.deepEqual(await position('R1'),durableR1);assert.equal(await storedLayout(),before);
   durableR1=await dragNode('R1',20,10);const after=JSON.parse(await storedLayout());assert.equal(Object.keys(after.layouts).length,2);assert(after.layouts[serviceLayoutKey]);
   await page.click('[data-act="processGraph"]');assert.deepEqual(await position('R1'),durableR1);assert.equal(await workGraphState(),areaState);
  });
  await check('storage write failure is explicit and preserves the last durable layout',async()=>{
   const saved=await storedLayout();
   await page.evaluate(key=>{window.rdgTestStorageSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k===key)throw new DOMException('Fixture storage unavailable','QuotaExceededError');return window.rdgTestStorageSet.call(this,k,v);};},layoutStorageKey);
   await dragNode('R0',20,15);assert.match(await text('#layoutStatus'),/не сохранено/);assert.equal(await storedLayout(),saved);
   await page.evaluate(()=>{Storage.prototype.setItem=window.rdgTestStorageSet;delete window.rdgTestStorageSet;});
   await page.reload({waitUntil:'load'});assert.deepEqual(await position('R0'),durableR0);assert.deepEqual(await position('A11'),durableAction);assert.deepEqual(await position('R1'),durableR1);
  });
  await check('occurrence persistence failure keeps live placement explicit and preserves the last durable coordinates',async()=>{
   await page.click('#allButton');const root=await branchRoot('D3'),saved=await storedLayout(),canonical=await position('D3');
   await page.evaluate(key=>{window.rdgTestStorageSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k===key)throw new DOMException('Fixture storage unavailable','QuotaExceededError');return window.rdgTestStorageSet.call(this,k,v);};},layoutStorageKey);
   await dragNode(root,20,15,true);assert.match(await text('#layoutStatus'),/повторения не сохранено/);assert.equal(await storedLayout(),saved);assert.deepEqual(await position('D3'),canonical);
   await page.evaluate(()=>{Storage.prototype.setItem=window.rdgTestStorageSet;delete window.rdgTestStorageSet;});await page.reload({waitUntil:'load'});assert.deepEqual(await occurrencePosition(root),{x:durableBranchRoot.x,y:durableBranchRoot.y});
  });
  await check('layout survives a real browser restart and demo reset clears only its own state',async()=>{
   await browser.close();browser=await puppeteer.launch(launchOptions);const reopened=await browser.newPage();reopened.on('pageerror',e=>errors.push(e.message));await reopened.setViewport({width:1440,height:1000});await reopened.goto(url,{waitUntil:'load'});
   assert.deepEqual(await position('R0',reopened),durableR0);assert.deepEqual(await position('R1',reopened),durableR1);assert.deepEqual(await position('A11',reopened),durableAction);
   assert.deepEqual(await occurrencePosition(durableBranchRoot.id,reopened),{x:durableBranchRoot.x,y:durableBranchRoot.y});assert.equal(await reopened.$eval(branchSelector(durableBranchRoot.id),e=>e.dataset.branchExpanded),'false');await reopened.click('[data-branch-toggle="'+durableBranchRoot.id+'"]');assert.deepEqual(await occurrencePosition(durableBranchChild.id,reopened),{x:durableBranchChild.x,y:durableBranchChild.y});
   assert.equal(await reopened.evaluate(key=>localStorage.getItem(key),workGraphStorageKey),areaState);
   assert.equal(await reopened.$eval('#catalogDrawer',e=>e.hidden),true);await reopened.click('#graphsButton');await reopened.click('[data-workgraph-open="'+createdAreaId+'"]');await reopened.click('#catalogHeader');assert.equal(await reopened.$$eval('#nodes [data-node]',es=>es.length),2);
   await reopened.click('[data-act="processGraph"]');await reopened.evaluate(()=>localStorage.setItem('rdg-test-unrelated','keep'));
   await reopened.click('[data-act="reset"]');assert.equal(await reopened.$eval('#catalogDrawer',e=>e.hidden),true);assert.equal(await reopened.$eval('#graphsButton',e=>e.getAttribute('aria-expanded')),'false');assert.deepEqual(await position('R0',reopened),{x:65,y:300});assert.deepEqual(await position('R1',reopened),{x:770,y:150});
   assert.equal(await reopened.evaluate(key=>localStorage.getItem(key),workGraphStorageKey),null);
   assert.equal(await reopened.evaluate(key=>localStorage.getItem(key),layoutStorageKey),null);assert.equal(await reopened.evaluate(()=>localStorage.getItem('rdg-test-unrelated')),'keep');
   await reopened.reload({waitUntil:'load'});assert.deepEqual(await position('R0',reopened),{x:65,y:300});
  });
  assert.deepEqual(errors,[]);console.log('RDG_UI_PROTOTYPE PASS '+checks.length+'/'+checks.length+'; desktop only; isolated standalone prototype.');
 }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));fs.rmSync(profile,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
