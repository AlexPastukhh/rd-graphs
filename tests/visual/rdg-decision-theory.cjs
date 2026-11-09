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
 await clickText('Изменить содержание','.rdg-canon-card');await fill('Каноны','Useful for bounded load; risky for bursts; borderline without measurements.');
 await clickText('Добавить ошибку');await fill('Название ошибки','Assuming capacity');await fill('Описание ошибки','A free comment with a source https://example.test/error');
 await clickText('Добавить ошибку');
 let editors=await page.$$eval('[data-theory-error-edit-id]',nodes=>nodes.map(n=>n.dataset.theoryErrorEditId));assert.equal(editors.length,2);
 await fill('Название ошибки','No description required','[data-theory-error-edit-id="'+editors[1]+'"]');
 await clickText('Ниже','[data-theory-error-edit-id="'+editors[0]+'"]');
 await fill('Основание изменения','Edit theory sections through Viewer');await save();
 let state=await api({method:'read',packageId:pid}),theory=state.graph.objects.find(n=>n.id==='C-OLD');
 assert.equal(theory.guidance,'Entire old text\nhttps://example.test/source');assert.equal(theory.knownErrors[0].title,'No description required');assert.equal(theory.knownErrors[0].description,'');assert.deepEqual(theory.knownErrors.map(n=>n.id),[editors[1],editors[0]]);
 await open('D-UI','Структура');assert((await page.$eval('[data-theory-id="C-OLD"]',n=>n.textContent)).includes('risky for bursts'));
 await clickText('Записать файндинг','.rdg-canon-actions');await fill('Название файндинга','Capacity assumption may fail');await fill('Тип файндинга','risk');await fill('Обоснование находки','Burst growth can exceed the assumed capacity');await fill('Основание изменения','Record analysis with complete theory excerpt');await save('Проверить файндинг');
 state=await api({method:'read',packageId:pid});const finding=state.graph.objects.find(n=>n.kind==='finding');assert(finding);const excerpt=finding.analysisSources[0].excerpt;for(const text of ['Useful for bounded','Entire old text','Assuming capacity','No description required','https://example.test/error'])assert(excerpt.includes(text),text);
 assert.equal(state.graph.nodes.find(n=>n.id==='D-UI').selectionState,'discovered');
 await open('D-UI','Структура');await clickText('Изменить содержание','.rdg-canon-card');await fill('Общее','General changed from Structure');await clickText('Удалить ошибку','[data-theory-error-edit-id="'+editors[1]+'"]');await fill('Основание изменения','Remove one error, preserve identity');await save();
 state=await api({method:'read',packageId:pid});theory=state.graph.objects.find(n=>n.id==='C-OLD');assert.equal(theory.knownErrors.length,1);assert.equal(theory.knownErrors[0].id,editors[0]);assert.equal(theory.guidance,'General changed from Structure');assert(state.graph.nodes.find(n=>n.id==='D-UI').review.required);
 await page.reload({waitUntil:'load'});await page.waitForFunction(()=>!!RDG_PORTABLE_EDITOR&&!RDG_PORTABLE_EDITOR.busy);await open('D-UI','Структура');
 assert((await page.$eval('[data-theory-id="C-OLD"]',n=>n.textContent)).includes('General changed from Structure'));
 const screenshot=path.join(process.env.RDG_SCREENSHOT_DIR||base,'rdg-decision-theory.png');fs.mkdirSync(path.dirname(screenshot),{recursive:true});await page.screenshot({path:screenshot,fullPage:true});
 await clickText('Добавить теорию');await fill('Название','Created from Structure');await fill('Каноны','Only this section is sufficient');await fill('Основание изменения','Create partial theory from Structure');await save('Добавить блок');
 state=await api({method:'read',packageId:pid});const created=state.graph.objects.find(n=>n.title==='Created from Structure');assert(created&&created.kind==='canon');assert.equal(created.guidance,'');assert.equal(created.canons,'Only this section is sufficient');assert(state.graph.edges.some(e=>e.type==='CANON_FOR'&&e.from===created.id&&e.to==='D-UI'));
 await open('D-UI');assert((await page.$$eval('[data-theory-id]',nodes=>nodes.map(n=>n.textContent))).some(t=>t.includes('Only this section is sufficient')));
 assert.deepEqual(errors,[]);console.log('DECISION_THEORY_VIEWER PASS',JSON.stringify({legacyRead:true,graphAndStructure:true,create:true,editAndOrderAndDeleteErrors:true,sourceExcerpt:true,reload:true,screenshot}));
}catch(e){console.error('DECISION_THEORY_VIEWER FAIL',e.stack||e);process.exitCode=1;
}finally{await stop();fs.rmSync(base,{recursive:true,force:true});}})();
