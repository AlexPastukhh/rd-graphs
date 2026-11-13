'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process');
const readline=require('node:readline');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const ROOT=path.resolve(__dirname,'../..');
const chrome=process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell';
const base=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-markdown-search-'));
let child,browser;

async function start(){
 return new Promise((resolve,reject)=>{
  let stderr='';
  child=spawn('python3',['-B','-u',path.join(ROOT,'tools/rdg-preview.py'),
   '--test-preview','--model-profile','rdg-decision-v1','--data-dir',path.join(base,'owner'),'--port','0']);
  const timer=setTimeout(()=>reject(Error('preview startup timeout '+stderr.slice(-600))),30000);
  child.stderr.on('data',s=>stderr+=s);
  child.once('error',reject);
  child.once('exit',code=>{if(code){clearTimeout(timer);reject(Error('preview exited '+code+' '+stderr.slice(-600)));}});
  readline.createInterface({input:child.stdout}).on('line',line=>{
   if(line.startsWith('{"url":')){clearTimeout(timer);resolve(JSON.parse(line));}
  });
 });
}

(async()=>{try{
 const ready=await start();
 browser=await puppeteer.launch({executablePath:chrome,headless:true,
  args:['--no-sandbox','--disable-dev-shm-usage'],userDataDir:path.join(base,'browser')});
 const page=await browser.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setViewport({width:1200,height:820});
 await page.goto(ready.url,{waitUntil:'load'});
 const idle=()=>page.waitForFunction(()=>!!globalThis.RDG_PORTABLE_EDITOR&&!RDG_PORTABLE_EDITOR.busy);
 await idle();
 const api=message=>page.evaluate(m=>RDG_PORTABLE_EDITOR.api(m),message);
 async function apply(request){
  if(request.op!=='create')request.note='Prepare an isolated Markdown and search fixture';
  const preview=await api({method:'preflight',request});
  const result=await api({method:'apply',request,expectedInputBinding:preview.inputBinding});
  assert.equal(result.published,true);
  return result;
 }
 const create=(await api({method:'schema',op:'create',coreModel:'rdg-decision-v1'})).request;
 Object.assign(create,{path:'working/markdown-test',role:'working',title:'Search and Markdown',
  scope:'Isolated renderer test',rootReason:'Verify equivalent reading and literal search'});
 const pid=(await apply(create)).packages[0].packageId;
 const add=(await api({method:'schema',op:'core',packageId:pid,command:'add',nodeId:'R1',entityKind:'decision'})).request;
 Object.assign(add.data.entity,{title:'Index alternative p95',description:'Bounded query scope <img src=x onerror=alert(1)>'});
 await apply(add);
 const before=await api({method:'read',packageId:pid});
 const decision=before.graph.nodes.find(n=>n.title==='Index alternative p95');
 assert(decision);
 await page.evaluate(pid=>RDG_PORTABLE_EDITOR.open(pid,{kind:'graph'}),pid);
 await idle();
 const click=async(text,scope='')=>{
  await page.evaluate(({text,scope})=>{
   const button=[...document.querySelectorAll((scope?scope+' ':'')+'button')].find(n=>n.textContent===text&&n.offsetParent!==null&&!n.disabled);
   if(!button)throw Error('Missing '+text);
   button.click();
  },{text,scope});await idle();
 };
 await click('Markdown','.rdg-presentation-modes');
 await page.waitForSelector('[data-markdown-entity="'+decision.id+'"]');
 assert.equal(await page.$('.rdg-markdown-view img'),null);
 assert(await page.$eval('.rdg-markdown-view',n=>n.textContent.includes('Bounded query scope <img')));
 await click('Структура','.rdg-presentation-modes');
 await page.waitForSelector('.rdg-structure-canvas');
 await click('Поиск по тексту');
 const query=await page.waitForSelector('input[aria-label="Текст поиска"]');
 await query.type('P95');
 await query.press('Enter');
 await page.waitForSelector('[data-search-entity="'+decision.id+'"]');
 await click('Index alternative p95','.rdg-search-hit');
 await page.waitForSelector('[data-markdown-entity="'+decision.id+'"]');
 assert.equal(await page.$eval('.rdg-presentation-modes button[aria-pressed="true"]',n=>n.textContent),'Markdown');
 const focus=await page.evaluate(()=>RDG_PORTABLE_EDITOR.view.view.spec);
 assert.equal(focus.kind,'focus');assert.equal(focus.id,decision.id);
 await click('К результатам поиска');
 await page.waitForSelector('[data-search-entity="'+decision.id+'"]');
 assert.equal(await page.$eval('input[aria-label="Текст поиска"]',n=>n.value),'P95');
 assert.deepEqual((await api({method:'read',packageId:pid})).graph,before.graph);

 await click('Закрыть поиск');
 // The real 19-lens source set uses the same three presentations as working data.
 // Cover every definition, including shared roots and preserve's exclusive group.
 const lensKeys=Object.keys(JSON.parse(fs.readFileSync(path.join(ROOT,'tools/rdg-lens-content-plan.json'),'utf8')));
 for(const key of lensKeys){
  const graph=JSON.parse(fs.readFileSync(path.join(ROOT,'tools/rdg-agent-lenses',key+'-decision.json'),'utf8'));
  const form=(await api({method:'schema',op:'create',coreModel:'rdg-decision-v1',role:'lens'})).request;
  Object.assign(form,{path:'lenses/'+key,role:'lens',lensKey:key,title:graph.title,
   scope:'Isolated structured lens rendering',rootReason:'Read the actual converted lens without executing it',graph});
  const lensId=(await apply(form)).packages[0].packageId;
  const snapshot=(await api({method:'read',packageId:lensId})).graph;
  await page.evaluate(pid=>RDG_PORTABLE_EDITOR.open(pid,{kind:'graph'}),lensId);await idle();
  await click('Граф','.rdg-presentation-modes');
  await page.waitForSelector('.rdg-node[data-entity-id="'+graph.rootRequirementId+'"]');
  assert.deepEqual(new Set(await page.$$eval('.rdg-node[data-entity-id]',nodes=>nodes.map(n=>n.dataset.entityId))),
   new Set([...graph.nodes,...graph.objects,...graph.externalActions]
    .filter(n=>['requirement','decision','action','context'].includes(n.kind)).map(n=>n.id)),key+' Graph identities');
  if(process.env.RDG_LENS_SCREENSHOTS&&key==='lens-system'){
   fs.mkdirSync(process.env.RDG_LENS_SCREENSHOTS,{recursive:true});
   await page.screenshot({path:path.join(process.env.RDG_LENS_SCREENSHOTS,'lens-system-graph.png')});
  }
  await click('Структура','.rdg-presentation-modes');
  await page.waitForSelector('.rdg-structure-canvas');
  await page.waitForSelector('.rdg-outline-row[data-entity-id="'+graph.rootRequirementId+'"]');
  if(process.env.RDG_LENS_SCREENSHOTS&&key==='lens-system')
   await page.screenshot({path:path.join(process.env.RDG_LENS_SCREENSHOTS,'lens-system-structure.png')});
  await click('Markdown','.rdg-presentation-modes');
  await page.waitForSelector('[data-markdown-entity="'+graph.rootRequirementId+'"]');
  assert((await page.$eval('.rdg-markdown-view',n=>n.textContent)).includes(graph.rootRequirementId));
  if(process.env.RDG_LENS_SCREENSHOTS&&key==='lens-system')
   await page.screenshot({path:path.join(process.env.RDG_LENS_SCREENSHOTS,'lens-system-markdown.png')});
  assert.deepEqual((await api({method:'read',packageId:lensId})).graph,snapshot);
 }

 assert.deepEqual(errors,[]);
 console.log('MARKDOWN_SEARCH_BROWSER PASS · '+lensKeys.length+' structured lenses, three modes, no data writes');
}catch(e){console.error(e.stack||e);process.exitCode=1;}finally{
 if(browser)await browser.close();
 if(child&&child.exitCode===null){const exited=new Promise(r=>child.once('exit',r));child.kill();await exited;}
 fs.rmSync(base,{recursive:true,force:true});
}})();
