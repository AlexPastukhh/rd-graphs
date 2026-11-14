'use strict';
// B02A theory form-writing acceptance on a disposable local preview owner.
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process'),readline=require('node:readline');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const ROOT=path.resolve(__dirname,'../..');
const chrome=process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell';
const base=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-theory-edit-'));
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
 Object.assign(create,{path:'working/theory-ui-test',role:'working',title:'Theory panel check',
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
 const decision=await core('add','R1','decision');decision.note='Synthetic decision';decision.data.entity.id='D-UI';decision.data.entity.title='Theory subject';decision.data.initialRelations=[{id:'D-REL',type:'DRIVES',from:'R1',to:'D-UI'}];await apply(decision);
 const legacy=await core('add','D-UI','canon');legacy.note='Legacy theory fixture';legacy.data.entity={id:'C-OLD',kind:'canon',title:'Legacy theory',description:'Legacy description',guidance:'Entire old text\nhttps://example.test/source'};legacy.data.initialRelations=[{id:'C-REL',type:'CANON_FOR',from:'C-OLD',to:'D-UI'}];await apply(legacy);
 const info=await core('add','C-OLD','info');info.note='Linked Info';info.data.entity.id='I-UI';info.data.entity.title='Theory reference';info.data.entity.value='Retained related material';info.data.initialRelations=[{id:'I-REL',type:'INFO_FOR',from:'I-UI',to:'C-OLD'}];await apply(info);
 const clickText=async(text,scope='')=>{await page.evaluate(({text,scope})=>{const b=[...document.querySelectorAll((scope?scope+' ':'')+'button')].find(n=>n.textContent===text&&n.offsetParent!==null&&!n.disabled);if(!b)throw Error('Visible button missing: '+text);b.click();},{text,scope});await idle();};
 const fill=async(label,value,scope='.rdg-modal')=>{await page.evaluate(({label,value,scope})=>{const row=[...document.querySelectorAll(scope+' label')].find(n=>n.firstChild?.textContent.trim()===label);const field=row?.querySelector('input,textarea,select');if(!field)throw Error('Field missing: '+label);field.value=value;field.dispatchEvent(new Event(field.tagName==='SELECT'?'change':'input',{bubbles:true}));},{label,value,scope});await idle();};
 const save=async(check='Проверить содержание')=>{await clickText(check);assert(await page.$('.rdg-modal'));await clickText('Сохранить');assert.equal(await page.$eval('.rdg-status',n=>n.classList.contains('rdg-error')?n.textContent:''),'');};
 const open=async(id,mode='Граф')=>{await page.evaluate(({pid,id})=>RDG_PORTABLE_EDITOR.open(pid,{kind:'focus',id}),{pid,id});await idle();await clickText(mode);await clickText('Сведения');if(id==='D-UI'){await page.click('[data-inspector-tab="canon"]');await idle();}};
 const before=(await api({method:'read',packageId:pid})).graph;
 await open('D-UI');
 assert.equal(await page.$eval('[data-inspector-tab="canon"]',n=>n.textContent),'Теория принятия решения');
 assert((await page.$eval('[data-theory-id="C-OLD"]',n=>n.textContent)).includes('Entire old text'));
 assert((await page.$eval('.rdg-canon-card',n=>n.textContent)).includes('Theory reference'));
 assert.deepEqual((await api({method:'read',packageId:pid})).graph,before);
 await open('R1');assert.equal(await page.$('[data-inspector-tab="canon"]'),null);
 await open('D-UI');
 await clickText('Изменить содержание','.rdg-canon-card');
 assert.equal(await page.$('[data-theory-errors-editor]'),null);
 await fill('Каноны','Good for bounded load. Bad under bursts. Known mistake: assuming capacity without measuring recovery.');
 await fill('Основание изменения','Use unified canons');await save();
 let state=await api({method:'read',packageId:pid}),theory=state.graph.objects.find(n=>n.id==='C-OLD');
 assert.equal(theory.guidance,'Entire old text\nhttps://example.test/source');assert(!theory.knownErrors?.length);assert(theory.canons.includes('Known mistake'));
 await open('D-UI','Структура');
 assert.deepEqual(await page.$$eval('[data-theory-id="C-OLD"] h4',ns=>ns.map(n=>n.textContent)),['Общее','Каноны · прежний текст']);
 await clickText('Записать файндинг','.rdg-canon-actions');await fill('Название файндинга','Capacity assumption may fail');await fill('Тип файндинга','risk');await fill('Обоснование находки','Burst growth can exceed the assumed capacity');await fill('Основание изменения','Record complete theory excerpt');await save('Проверить файндинг');
 state=await api({method:'read',packageId:pid});const finding=state.graph.objects.find(n=>n.kind==='finding');assert(finding);
 for(const text of ['Good for bounded','Bad under bursts','Known mistake','Entire old text'])assert(finding.analysisSources[0].excerpt.includes(text),text);
 assert.equal(state.graph.nodes.find(n=>n.id==='D-UI').selectionState,'discovered');
 const action=await core('add','R1','action');action.note='A whole task may have theory';action.data.entity.id='A-UI';action.data.entity.title='Whole task';action.data.entity.description='Inputs, internal method, output and acceptance stay in this Action.';action.data.initialRelations=[{id:'A-REL',type:'REQUIRES_ACTION',from:'R1',to:'A-UI'}];await apply(action);
 await open('A-UI','Структура');await page.click('[data-inspector-tab="canon"]');await idle();
 await clickText('Добавить теорию');await fill('Название','Action execution theory');await fill('Каноны','Good with verified input. Known mistake: accepting a partial output as complete.');await fill('Основание изменения','Create Action theory');await save('Добавить блок');
 state=await api({method:'read',packageId:pid});const at=state.graph.objects.find(n=>n.title==='Action execution theory');assert(at);assert(state.graph.edges.some(e=>e.type==='CANON_FOR'&&e.from===at.id&&e.to==='A-UI'));
 const beforeBad=state.graph;const bad=await core('link','R1');bad.note='Reject theory on Requirement';bad.data={relation:{id:'BAD-R',type:'CANON_FOR',from:at.id,to:'R1'}};
 await assert.rejects(()=>api({method:'preflight',request:bad}),/THEORY_TARGET_DECISION_OR_ACTION/);
 assert.deepEqual((await api({method:'read',packageId:pid})).graph,beforeBad);
 await page.reload({waitUntil:'load'});await page.waitForFunction(()=>!!RDG_PORTABLE_EDITOR&&!RDG_PORTABLE_EDITOR.busy);await open('A-UI','Структура');
 assert((await page.$eval('[data-theory-id="'+at.id+'"]',n=>n.textContent)).includes('Known mistake'));

 await open('D-UI');await clickText('Изменить содержание','.rdg-canon-card');
 await clickText('Добавить канон');await fill('Название','Owned canon','[data-theory-editor="canonItems"]');await fill('Текст канона','Complete canon, including the boundary case.','[data-theory-editor="canonItems"]');
 await clickText('Вставить ссылку в Общее','[data-theory-editor="canonItems"]');
 await clickText('Добавить источник');await fill('Название','Linked material','[data-theory-editor="recommendations"]');await fill('Ссылка HTTPS','https://example.org/read-more','[data-theory-editor="recommendations"]');
 await clickText('Вставить ссылку в Общее','[data-theory-editor="recommendations"]');await fill('Основание изменения','Add owned canon and typed material');await save();
 state=await api({method:'read',packageId:pid});theory=state.graph.objects.find(n=>n.id==='C-OLD');
 const owned=theory.canonItems[0],recommended=theory.recommendations[0];assert(owned&&recommended);assert.deepEqual(Object.keys(recommended).sort(),['id','targetRef','title']);
 assert(theory.guidance.includes('theory:canons/'+owned.id));assert(theory.guidance.includes('theory:recommendations/'+recommended.id));
 const beforeRead=state.graph;await page.click('[data-theory-link="canons/'+owned.id+'"]');await idle();
 assert((await page.$eval('[data-theory-item="canons/'+owned.id+'"]',n=>n.textContent)).includes(owned.body));
 await page.click('[data-theory-link="recommendations/'+recommended.id+'"]');await idle();assert(await page.$('[data-theory-item="recommendations/'+recommended.id+'"]'));
 assert.deepEqual((await api({method:'read',packageId:pid})).graph,beforeRead);
 await page.$eval('[data-theory-collection="recommendations"]',n=>n.open=true);
 const filter=await page.$('[data-theory-collection="recommendations"] select');await filter.select('lens');assert.equal(await page.$$eval('[data-theory-entry^="recommendations/"]',ns=>ns.length),0);await filter.select('material');assert.equal(await page.$$eval('[data-theory-entry^="recommendations/"]',ns=>ns.length),1);
 await page.reload({waitUntil:'load'});await page.waitForFunction(()=>!!RDG_PORTABLE_EDITOR&&!RDG_PORTABLE_EDITOR.busy);await open('D-UI');
 assert(await page.$('[data-theory-link="canons/'+owned.id+'"]'));
 await open('R1');assert.equal(await page.$('[data-inspector-tab="canon"]'),null);
 await open('D-UI');const screenshot=path.join(process.env.RDG_SCREENSHOT_DIR||base,'rdg-decision-theory.png');fs.mkdirSync(path.dirname(screenshot),{recursive:true});await page.screenshot({path:screenshot,fullPage:true});
 assert.deepEqual(errors,[]);console.log('DECISION_THEORY_VIEWER PASS',JSON.stringify({generalPreserved:true,twoSections:true,decisionAndAction:true,noRequirementTheory:true,sourceExcerpt:true,reload:true,screenshot}));
}catch(e){console.error('DECISION_THEORY_VIEWER FAIL',e.stack||e);process.exitCode=1;
}finally{await stop();fs.rmSync(base,{recursive:true,force:true});}})();
