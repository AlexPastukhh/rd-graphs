'use strict';
// Chromium -> real authenticated Helper -> Graph/Plan writers, only temporary owners.
const assert=require('node:assert/strict'),path=require('node:path');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
(async()=>{
 const url=process.env.RDG_MODULE_TEST_URL;
 assert(url,'Run via tests/rdg-modules.test.py (isolated Helper)');
 const session=url.replace(/\/$/,'').split('/').at(-1),origin=new URL(url).origin;
 async function call(route,body){
  const response=await fetch(url+route,{method:body?'POST':'GET',
   headers:{'X-RDG-Session':session,...(body?{'Content-Type':'application/json',Origin:origin}:{})},
   ...(body?{body:JSON.stringify(body)}:{})});
  const value=await response.json();
  if(!response.ok){const error=Error(value.error);error.definite=true;throw error;}
  return value;
 }
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,
  headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',e=>{errors.push(e.message);console.error('MODULE_PAGE_ERROR',e.message);});
  await page.exposeFunction('helperRead',()=>call('state'));
  await page.exposeFunction('helperWrite',body=>call('command',body));
  await page.setContent('<main id="workflow"></main>');
  await page.addScriptTag({path:path.resolve(__dirname,'../../tools/rdg-workflow-ui.js')});
  await page.evaluate(async()=>{
   window.controller=RDGWorkflowUI.mount(document.getElementById('workflow'),
    {read:()=>window.helperRead(),write:q=>window.helperWrite(q)});
   await controller.refresh();
  });
  assert(await page.$('.wf-modules'));
  await page.evaluate(()=>{document.querySelector('.wf-modules').open=true;});
  // Real UI buttons connect Graph and Plan independently.
  for(const scope of ['graph','plan']){
   await page.evaluate(scope=>{
    const row=[...document.querySelectorAll('.wf-modules p')].find(x=>x.textContent.startsWith(scope+' ·'));
    if(!row)throw Error('Missing scope '+scope);
    row.querySelector('button').click();
   },scope);
   try{await page.waitForFunction(scope=>!!controller.view?.moduleCapabilities?.[scope]?.enabled?.['rdg-test'],
      {timeout:15000},scope);}catch(e){console.error('MODULE_UI_STATE',await page.evaluate(()=>({status:controller.status,pending:controller.pending,caps:controller.view?.moduleCapabilities,text:document.querySelector('.wf-modules').textContent})));throw e;}
   assert.equal(await page.evaluate(()=>controller.pending),null);
  }
  // Execute module code through the same browser transport, then reread its history.
  const created=await page.evaluate(async()=>{
   const view=controller.view;
   return window.helperWrite({action:'module_operation',module:'rdg-test',version:1,
    operation:'rdg-test.create',transactionId:'browser-module-node',note:'Synthetic browser module probe',
    expectedGraphRevision:view.sources.graphs[view.graphFile].revision,
    expectedPlanRevision:view.sources.plan.revision,
    node:{id:'BROWSER1',kind:'rdg-test.marker',title:'Browser marker',module:{id:'rdg-test',version:1},
      data:{value:' browser code ',inputs:[]}}});
  });
  assert(created.saved);
  await page.evaluate(()=>controller.refresh());
  assert((await page.$eval('#workflow',e=>e.textContent)).includes('BROWSER CODE'));
  for(const scope of ['graph','plan']){
   await page.evaluate(scope=>controller.configureModule(scope,'rdg-test',false),scope);
   assert.equal(await page.evaluate(scope=>Object.hasOwn(controller.view.moduleCapabilities[scope].enabled,'rdg-test'),scope),false);
  }
  assert((await page.$eval('#workflow',e=>e.textContent)).includes('BROWSER CODE'),'history remains after disable');
  assert.deepEqual(errors,[]);
  console.log('MODULE_CODE_CONNECTION_GRAPH_PLAN_HISTORY_BROWSER_PASS');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
