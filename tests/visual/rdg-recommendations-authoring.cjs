'use strict';
// T3/T4 form-writing acceptance on a disposable local preview owner.
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process'),readline=require('node:readline');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const ROOT=path.resolve(__dirname,'../..');
const chrome=process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell';
const base=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-recommendations-'));
let child,browser;
const errors=[];
const browserEnv={...process.env};
if(process.env.RDG_TEST_FONT_DIR){
 const config=path.join(base,'fonts.conf');
 fs.writeFileSync(config,'<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>'+
   process.env.RDG_TEST_FONT_DIR+'</dir><cachedir>'+path.join(base,'font-cache')+'</cachedir></fontconfig>');
 browserEnv.FONTCONFIG_FILE=config;
}

async function start(){
 return new Promise((resolve,reject)=>{
  let stderr='';
  child=spawn('python3',['-B','-u',path.join(ROOT,'tools/rdg-preview.py'),
   '--test-preview','--model-profile','rdg-decision-v1','--data-dir',path.join(base,'owner'),'--port','0'],
   {env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
  const timer=setTimeout(()=>reject(Error('preview startup timeout '+stderr.slice(-600))),30000);
  child.stderr.on('data',s=>stderr+=s);
  child.once('error',reject);
  child.once('exit',code=>{if(code){clearTimeout(timer);reject(Error('preview exited '+code+' '+stderr.slice(-600)));}});
  readline.createInterface({input:child.stdout}).on('line',line=>{
   if(line.startsWith('{"url":')){clearTimeout(timer);resolve(JSON.parse(line));}
  });
 });
}
async function stop(){
 if(browser){await browser.close();browser=null;}
 if(child&&child.exitCode===null){
  const wait=new Promise(resolve=>child.once('exit',resolve));child.kill();await wait;
 }
}
(async()=>{try{
 const ready=await start();
 browser=await puppeteer.launch({executablePath:chrome,headless:true,
  args:['--no-sandbox','--disable-dev-shm-usage'],env:browserEnv,
  userDataDir:path.join(base,'browser')});
 const page=await browser.newPage();
 page.on('pageerror',e=>errors.push(e.message));
 await page.setViewport({width:1250,height:860});
 await page.goto(ready.url,{waitUntil:'load'});
 await page.waitForFunction(()=>!!globalThis.RDG_PORTABLE_EDITOR&&!RDG_PORTABLE_EDITOR.busy);
 const api=message=>page.evaluate(m=>RDG_PORTABLE_EDITOR.api(m),message);
 const idle=()=>page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy);
 const create=(await api({method:'schema',op:'create',coreModel:'rdg-decision-v1'})).request;
 Object.assign(create,{path:'working/recommendations-ui-test',role:'working',title:'Questions panel check',
  scope:'Synthetic UI only',rootReason:'Test Question navigation without modifying live owners'});
 async function apply(request){
  const preview=await api({method:'preflight',request});
  const result=await api({method:'apply',request,expectedInputBinding:preview.inputBinding});
  assert.equal(result.published,true);return result;
 }
 const pid=(await apply(create)).packages[0].packageId;
 async function core(command,nodeId='R1',kind){
  return (await api({method:'schema',op:'core',packageId:pid,command,nodeId,
   ...(kind?{entityKind:kind}:{})})).request;
 }

 const req=(await api({method:'schema',op:'create',coreModel:'rdg-decision-v1',role:'lens'})).request;Object.assign(req,{path:'lenses/recommendation-work',role:'lens',lensKey:'work',coreModel:'rdg-decision-v1',graph:JSON.parse(fs.readFileSync(path.join(ROOT,'tools/rdg-agent-lenses/work-decision.json'),'utf8')),rootReason:'Isolated recommendation test'});const lensId=(await apply(req)).packages[0].packageId;
 await page.reload({waitUntil:'load'});await page.waitForFunction(()=>!!RDG_PORTABLE_EDITOR&&!RDG_PORTABLE_EDITOR.busy);
 const click=async(text,scope='')=>{await page.evaluate(({text,scope})=>{const b=[...document.querySelectorAll((scope?scope+' ':'')+'button')].find(n=>n.textContent===text&&n.offsetParent!==null&&!n.disabled);if(!b)throw Error('Missing '+text);b.click();},{text,scope});await idle();};
 const fill=async(label,value)=>{await page.evaluate(({label,value})=>{const row=[...document.querySelectorAll('.rdg-modal label')].find(n=>n.firstChild?.textContent.trim()===label);const field=row?.querySelector('input,textarea,select');if(!field)throw Error('Missing field '+label);field.value=value;field.dispatchEvent(new Event(field.tagName==='SELECT'?'change':'input',{bubbles:true}));},{label,value});await idle();};
 const save=async()=>{await click('Проверить рекомендацию');await click('Сохранить');assert.equal(await page.$eval('.rdg-status',n=>n.classList.contains('rdg-error')?n.textContent:''),'');};
 await page.evaluate(pid=>RDG_PORTABLE_EDITOR.open(pid,{kind:'focus',id:'R1'}),pid);await idle();await click('Граф');await click('Сведения');await page.click('[data-inspector-tab="recommendations"]');await idle();assert((await page.$eval('[data-recommendations-for="R1"]',n=>n.textContent)).includes('Рекомендаций пока нет'));
 for(const usage of ['Read the principle','Follow the method when needed']){await click('Добавить рекомендацию');await fill('Название рекомендации',usage);await fill('Линза',lensId);await fill('Когда использовать','When evaluating alternatives');await fill('Как использовать',usage);await fill('Основание изменения','Explicit authored advice');await save();}
 let row=await api({method:'read',packageId:pid});assert.equal(row.recommendations.matches.length,2);assert.equal(new Set(row.recommendations.matches.map(m=>m.recommendationId)).size,2);
 const first=await page.$eval('[data-recommendation-id]',n=>n.dataset.recommendationId);await click('Изменить рекомендацию','[data-recommendation-id="'+first+'"]');await fill('Как использовать','Clarified intent');await fill('Основание изменения','Correct usage');await save();
 await click('Структура');const before=(await api({method:'read',packageId:pid})).graph;await page.click('[data-recommendation-id] button');await idle();assert.equal((await page.evaluate(()=>RDG_PORTABLE_EDITOR.view)).package.packageId,lensId);await click('Граф');await click('К процессу');assert.equal((await page.evaluate(()=>RDG_PORTABLE_EDITOR.view)).package.packageId,pid);assert.equal(await page.$eval('.rdg-presentation-modes button[aria-pressed="true"]',n=>n.textContent),'Структура');assert.deepEqual((await api({method:'read',packageId:pid})).graph,before);assert(await page.$('[data-inspector-panel="recommendations"]:not([hidden])'));
 await page.reload({waitUntil:'load'});await page.waitForFunction(()=>!!RDG_PORTABLE_EDITOR&&!RDG_PORTABLE_EDITOR.busy);await page.evaluate(pid=>RDG_PORTABLE_EDITOR.open(pid,{kind:'focus',id:'R1'}),pid);await idle();await click('Сведения');await page.click('[data-inspector-tab="recommendations"]');await idle();assert.equal(await page.$$eval('[data-recommendation-id]',n=>n.length),2);
 const screenshot=path.join(process.env.RDG_SCREENSHOT_DIR||base,'rdg-recommendations-authoring.png');fs.mkdirSync(path.dirname(screenshot),{recursive:true});await page.screenshot({path:screenshot,fullPage:true});
 await click('Убрать рекомендацию');await click('Сохранить');row=await api({method:'read',packageId:pid});assert.equal(row.recommendations.matches.length,1);
 await page.$eval('.rdg-actions',n=>n.open=true);await click('Рекомендации процесса');await click('Добавить рекомендацию');await fill('Название рекомендации','Process advice');await fill('Линза',lensId);await fill('Как использовать','Consult as needed');await fill('Основание изменения','Process scope');await save();row=await api({method:'read',packageId:pid});assert(row.recommendations.matches.some(m=>m.nodeId===row.graph.id));assert(!row.graph.events.some(e=>e.type==='lens_application_recorded'));assert.deepEqual(errors,[]);
 console.log('RECOMMENDATION_AUTHORING PASS',JSON.stringify({create:true,edit:true,detach:true,distinctIntents:true,processScope:true,readback:true,reload:true,modeAndTabReturn:true,noImplicitExecution:true,screenshot}));
}catch(e){console.error('RECOMMENDATION_AUTHORING FAIL',e.stack||e);process.exitCode=1;}finally{await stop();fs.rmSync(base,{recursive:true,force:true});}})();
