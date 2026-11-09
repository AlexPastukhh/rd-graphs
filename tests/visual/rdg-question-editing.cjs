'use strict';
// T3/T4 form-writing acceptance on a disposable local preview owner.
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process'),readline=require('node:readline');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const ROOT=path.resolve(__dirname,'../..');
const chrome=process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell';
const base=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-question-edit-'));
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
 Object.assign(create,{path:'working/questions-ui-test',role:'working',title:'Questions panel check',
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
 const decision=await core('add','R1','decision');
 decision.note='Synthetic option';
 Object.assign(decision.data.entity,{id:'D-UI',title:'Inspect decision',description:'Not selected'});
 decision.data.initialRelations=[{id:'UI-DRIVES',type:'DRIVES',from:'R1',to:'D-UI'}];
 await apply(decision);
 const finding=await core('add','D-UI','finding');
 finding.note='Synthetic risk';
 Object.assign(finding.data.entity,{id:'F-UI',title:'Uncertain latency',
  description:'Cannot measure peak',subjectId:'D-UI',findingType:'risk',
  rationale:'No peak sample',evidenceIds:[]});
 await apply(finding);
 const context=await core('add','D-UI','context');
 context.note='Synthetic observed data';
 Object.assign(context.data.entity,{id:'CTX-UI',title:'Normal load data',
  description:'Synthetic sample',value:'7 rps'});
 await apply(context);
 const original=await api({method:'read',packageId:pid});
 const question=await core('add','D-UI','question');
 question.note='Question about peak latency';
 Object.assign(question.data.entity,{id:'Q-UI',title:'Peak latency under load?',
  description:'How long requests wait during peak periods',
  impact:'May change decision',answerCondition:'Peak p95 measurement',
  relatedRefs:[original.references['D-UI'],original.references['F-UI']]});
 await apply(question);
 const answerReq=await core('question_answer','Q-UI');
 answerReq.note='Synthetic hypothesis';answerReq.data.text='Perhaps under 50 ms';
 await apply(answerReq);
 const observed=await api({method:'read',packageId:pid});
 const answer=observed.graph.objects.find(n=>n.id==='Q-UI').answers[0];
 const assessment=await core('question_assess','Q-UI');
 assessment.note='Cannot determine sufficient evidence';
 Object.assign(assessment.data,{answerIds:[answer.id],sufficient:false,basis:'Peak measurement missing'});
 await apply(assessment);
 const edit=await core('question_answer','Q-UI');
 edit.note='Correct synthetic hypothesis';
 edit.data={nodeId:'Q-UI',action:'edit',answerId:answer.id,
  expectedAnswerEventId:answer.eventId,kind:'hypothesis',text:'Perhaps under 70 ms',sourceRefs:[]};
 await apply(edit);
 const fresh=await api({method:'read',packageId:pid});
 const other=await core('add','D-UI','question');
 other.note='Second question, not from Finding';
 Object.assign(other.data.entity,{id:'Q-OTHER',title:'Other pending research',
  description:'A decision-only question',impact:'Determines budget risk',
  answerCondition:'Estimate operating cost',relatedRefs:[fresh.references['D-UI']]});
 await apply(other);
 const graphBefore=(await api({method:'read',packageId:pid})).graph;
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),pid);
 await idle();
 assert.equal(await page.$eval('[data-questions-workspace-button]',b=>b.textContent),'Вопросы · 2');
 await page.click('[data-questions-workspace-button]');await idle();
 assert(await page.$('[data-questions-workspace]'));
 const groups=await page.$eval('[data-questions-workspace]',n=>n.textContent);
 assert(groups.includes('Вопросы Findings')&&groups.includes('Остальные вопросы'));
 assert(await page.$('[data-question-id="Q-UI"]'));
 assert(await page.$('[data-question-id="Q-OTHER"]'));
 await page.$eval('.rdg-question-list-head input',n=>{
  n.value='Other pending';n.dispatchEvent(new Event('input',{bubbles:true}));
 });
 assert(await page.$('[data-question-id="Q-OTHER"]'));
 assert.equal(await page.$('[data-question-id="Q-UI"]'),null);
 await page.$eval('.rdg-question-list-head input',n=>{
  n.value='';n.dispatchEvent(new Event('input',{bubbles:true}));
 });
 await page.click('[data-question-id="Q-UI"]');await idle();
 const detail=await page.$eval('[data-question-detail-id="Q-UI"]',n=>n.textContent);
 assert(detail.includes('Perhaps under 70 ms'));
 assert(detail.includes('Peak measurement missing'));
 assert(detail.includes('Требуется пересмотр достаточности'));
 assert(detail.includes('Perhaps under 50 ms'),'history of earlier answer preserved');
 const screenshot=path.join(process.env.RDG_SCREENSHOT_DIR||base,'rdg-questions-readonly.png');
 fs.mkdirSync(path.dirname(screenshot),{recursive:true});
 await page.screenshot({path:screenshot,fullPage:true});
 await page.click('[data-question-target-id="D-UI"]');await idle();
 assert.equal(await page.$('[data-questions-workspace]'),null);
 assert(await page.$('[data-inspector-tab="questions"]'));
 await page.click('[data-inspector-tab="questions"]');await idle();
 assert(await page.$('[data-related-question-id="Q-UI"]'));
 assert(await page.$('[data-related-question-id="Q-OTHER"]'));
 await page.click('[data-related-question-id="Q-UI"] button');await idle();
 assert(await page.$('[data-question-detail-id="Q-UI"]'));
 await page.click('[data-question-target-id="F-UI"]');await idle();
 assert(await page.$('.rdg-inspector [data-inspector-tab="findings"]'));
 assert(await page.$('[data-finding-id="F-UI"]'));
 assert(await page.$('[data-finding-id="F-UI"] [data-finding-question-id="Q-UI"]'));
 await page.click('[data-finding-id="F-UI"] [data-finding-question-id="Q-UI"]');await idle();
 assert(await page.$('[data-question-detail-id="Q-UI"]'));
 assert.equal(await page.$eval('.rdg-status',n=>n.classList.contains('rdg-error')?n.textContent:''),'');
 assert.deepEqual((await api({method:'read',packageId:pid})).graph,graphBefore);
 const clickText=async text=>{await page.evaluate(text=>{const b=[...document.querySelectorAll('button')].find(n=>n.textContent===text&&n.offsetParent!==null);if(!b)throw Error('Visible button missing: '+text);b.click();},text);await idle();};
 const fill=async(label,value)=>{await page.evaluate(({label,value})=>{const field=[...document.querySelectorAll('.rdg-modal label')].find(n=>n.textContent.startsWith(label));const input=field?.querySelector('input,textarea,select');if(!input)throw Error('Field missing: '+label);input.value=value;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));},{label,value});};
 const saveForm=async check=>{await clickText(check);assert(await page.$('.rdg-modal'));await clickText('Сохранить');await idle();const error=await page.$eval('.rdg-status',n=>n.classList.contains('rdg-error')?n.textContent:'');assert.equal(error,'');};
 const areaReq=await core('work_graph','R1');areaReq.note='Question scope fixture';areaReq.data={workGraph:{id:'QUESTION-AREA',title:'Research area',rootIds:['R1'],memberIds:['R1','D-UI']}};await apply(areaReq);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),pid);await idle();
 await clickText('Добавить вопрос');
 await fill('Название вопроса','Created through Viewer');await fill('На что влияет ответ','Changes cost');await fill('Условие достаточности','Actual user budget');await fill('Основание изменения','Browser form check');
 await fill('Документы-источники HTTPS','https://example.test/a\nhttps://example.test/b');
 await page.$eval('[data-question-area-picker]',n=>n.open=true);await page.click('[data-question-area-id="QUESTION-AREA"]');
 await saveForm('Проверить вопрос');
 let state=await api({method:'read',packageId:pid});
 const createdQ=state.graph.objects.find(n=>n.kind==='question'&&n.title==='Created through Viewer');assert(createdQ);assert(createdQ.relatedRefs.some(r=>r.kind==='workGraph'&&r.workGraphId==='QUESTION-AREA'));
 await page.click('[data-question-id="'+createdQ.id+'"]');await idle();
 await clickText('Изменить вопрос');await fill('Название вопроса','Edited through Viewer');await fill('Основание изменения','Edit Question without losing sources');await saveForm('Проверить вопрос');
 state=await api({method:'read',packageId:pid});const editedQ=state.graph.objects.find(n=>n.id===createdQ.id);assert.equal(editedQ.title,'Edited through Viewer');assert.deepEqual(editedQ.relatedRefs,createdQ.relatedRefs);assert.deepEqual(editedQ.sourceRefs,createdQ.sourceRefs);assert.equal(editedQ.sourceRefs.length,2);
 await clickText('Добавить ответ');await fill('Текст ответа','Budget is 100');await fill('Вид ответа','user_answer');await fill('Основание изменения','User entered directly');await saveForm('Проверить ответ');
 state=await api({method:'read',packageId:pid});let stored=state.graph.objects.find(n=>n.id===createdQ.id);
 assert.equal(stored.answers[0].kind,'user_answer');assert.equal(stored.answers[0].userSource.mode,'direct-user-entry');
 await clickText('Изменить ответ');await fill('Текст ответа','Budget is 120');await fill('Основание изменения','Correct budget');await saveForm('Проверить ответ');
 await clickText('Оценить достаточность');await fill('Обоснование оценки','Need currency too');await fill('Основание изменения','Check sufficiency');await saveForm('Проверить достаточность');
 await page.reload({waitUntil:'load'});await page.waitForFunction(()=>!!RDG_PORTABLE_EDITOR&&!RDG_PORTABLE_EDITOR.busy);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),pid);await idle();await page.click('[data-questions-workspace-button]');await idle();await page.click('[data-question-id="'+createdQ.id+'"]');await idle();
 assert((await page.$eval('[data-question-detail-id="'+createdQ.id+'"]',n=>n.textContent)).includes('Budget is 120'));
 await clickText('Удалить ответ');await fill('Основание изменения','Withdraw answer');await saveForm('Проверить удаление ответа');
 state=await api({method:'read',packageId:pid});stored=state.graph.objects.find(n=>n.id===createdQ.id);assert.equal(stored.answers.length,0);assert.equal(stored.answerHistory.length,2);assert.equal(stored.assessmentReviewRequired,true);
 const action=await core('add','D-UI','action');action.note='Browser estimate fixture';action.data.entity.id='A-EST';action.data.entity.title='Measure task';action.data.initialRelations=[{id:'EST-REL',type:'REQUIRES_ACTION',from:'D-UI',to:'A-EST'}];await apply(action);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'A-EST'}),pid);await idle();await clickText('Граф');await page.$eval('[data-entity-id="A-EST"]',n=>n.dispatchEvent(new MouseEvent('click',{bubbles:true})));await idle();
 await clickText('Изменить оценки');await fill('Сложность исполнения','Requires access');await fill('Минимум времени','60');await fill('Максимум времени','180');await fill('Основание оценки','Prior measurement');await fill('Основание изменения','Estimate through Viewer');await saveForm('Проверить оценки');
 state=await api({method:'read',packageId:pid});assert.deepEqual(state.graph.nodes.find(n=>n.id==='A-EST').estimates,{complexity:'Requires access',time:{minSeconds:60,maxSeconds:180},basis:'Prior measurement'});
 await page.reload({waitUntil:'load'});await page.waitForFunction(()=>!!RDG_PORTABLE_EDITOR&&!RDG_PORTABLE_EDITOR.busy);await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'A-EST'}),pid);await idle();await clickText('Граф');await page.$eval('[data-entity-id="A-EST"]',n=>n.dispatchEvent(new MouseEvent('click',{bubbles:true})));await idle();assert((await page.$eval('[data-action-estimates="A-EST"]',n=>n.textContent)).includes('60–180'));
 await clickText('Структура');assert((await page.$eval('[data-action-estimates="A-EST"]',n=>n.textContent)).includes('60–180'));
 await page.screenshot({path:screenshot.replace('readonly','editing'),fullPage:true});
 await clickText('Изменить оценки');await fill('Сложность исполнения','');await fill('Минимум времени','');await fill('Максимум времени','');await fill('Основание изменения','Clear estimates, keep prior basis in form');await saveForm('Проверить оценки');
 state=await api({method:'read',packageId:pid});assert(!('estimates' in state.graph.nodes.find(n=>n.id==='A-EST')));

 assert.deepEqual(errors,[]);
 console.log('QUESTION_VIEWER_EDITING PASS',JSON.stringify({
  createdQuestions:1,questionEditing:true,sourceDocuments:2,workGraphScope:true,userAnswerEditedAndRemoved:true,estimates:true,reload:true,
  screenshot:screenshot.replace('readonly','editing')}));
}catch(e){console.error('QUESTION_VIEWER_EDITING FAIL',e.stack||e);process.exitCode=1;
}finally{await stop();fs.rmSync(base,{recursive:true,force:true});}})();
