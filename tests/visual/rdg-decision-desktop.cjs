'use strict';
// The manual entry point must preserve the accepted Process Graph / Working Graph UX.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {spawn}=require('node:child_process'),readline=require('node:readline');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const ROOT=path.resolve(__dirname,'../..'),workfiles=process.env.RDG_WORKFILES||'/workspace/repo/Workfiles';
fs.mkdirSync(workfiles,{recursive:true});
const base=fs.mkdtempSync(path.join(workfiles,'rdg-decision-desktop-'));
const env={...process.env,PYTHONDONTWRITEBYTECODE:'1'};for(const k of Object.keys(env))if(k.startsWith('RDG_AUTH_'))delete env[k];
let child,browser,page,ready,referenceServer;const checks=[],errors=[],requests=[],timings={};
const safe=e=>String(e.stack||e).replace(/http:\/\/(?:127\.0\.0\.1|localhost):\d+\/session\/[A-Za-z0-9_-]+\//g,'http://loopback/session/[redacted]/');
async function start(){return new Promise((resolve,reject)=>{let stderr='';child=spawn('python3',['-B','-u',path.join(ROOT,'tools/rdg-preview.py'),'--test-preview','--model-profile','rdg-decision-v1','--data-dir',path.join(base,'data'),'--port','0'],{env});const timer=setTimeout(()=>reject(Error('startup timeout '+stderr.slice(-1000))),30000);child.stderr.on('data',s=>stderr+=s);child.once('error',reject);child.once('exit',code=>{if(code){clearTimeout(timer);reject(Error(stderr.slice(-1000)));}});readline.createInterface({input:child.stdout}).on('line',line=>{if(line.startsWith('{"url":')){clearTimeout(timer);resolve(JSON.parse(line));}});});}
(async()=>{try{
 ready=await start();browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,headless:true,protocolTimeout:30000,args:['--no-sandbox','--disable-dev-shm-usage'],env});page=await browser.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('request',req=>{try{const body=JSON.parse(req.postData()||'{}');if(body.method)requests.push(body.method);}catch{}});await page.setViewport({width:1440,height:1000});
 const idle=()=>page.waitForFunction(()=>globalThis.RDG_PORTABLE_EDITOR&&!RDG_PORTABLE_EDITOR.busy),state=()=>page.evaluate(()=>RDG_PORTABLE_EDITOR.view),api=message=>page.evaluate(message=>RDG_PORTABLE_EDITOR.api(message),message);
 const click=async(text,scope='.rdg-decision')=>{for(let i=0;i<8;i++){const summary=await page.evaluateHandle(({text,scope})=>{const b=[...document.querySelectorAll(scope+' button')].find(b=>(b.textContent===text||b.getAttribute('aria-label')===text)&&!b.disabled);let outer=null;for(let n=b?.parentElement;n;n=n.parentElement)if(n.tagName==='DETAILS'&&!n.open)outer=n;return outer?.querySelector(':scope > summary')||null;},{text,scope});if(!summary.asElement()){await summary.dispose();break;}await summary.asElement().click();await summary.dispose();await idle();}const target=await page.evaluateHandle(({text,scope})=>[...document.querySelectorAll(scope+' button')].find(b=>(b.textContent===text||b.getAttribute('aria-label')===text)&&!b.disabled),{text,scope});assert(target.asElement(),'Missing '+text);await target.asElement().click();await target.dispose();await idle();assert.equal(await page.$eval('.rdg-status',n=>n.classList.contains('rdg-error')?n.textContent:''),'',text);};
 const field=async(label,value,scope='.rdg-modal')=>{await page.evaluate(({label,value,scope})=>{const row=[...document.querySelectorAll(scope+' label')].find(n=>n.firstChild?.textContent.trim()===label);if(!row)throw Error('Missing field '+label);const n=row.querySelector('input,textarea,select');if(n.type==='checkbox')n.checked=!!value;else n.value=value;n.dispatchEvent(new Event(n.tagName==='SELECT'?'change':'input',{bubbles:true}));},{label,value,scope});await idle();};
 const save=()=>click('Сохранить','.rdg-modal');
 const launch=async()=>{await page.setRequestInterception(true);let delay=true;const intercept=req=>{let body;try{body=JSON.parse(req.postData()||'{}');}catch{}if(delay&&body?.method==='catalog'){delay=false;setTimeout(()=>void req.continue(),600);}else void req.continue();};page.on('request',intercept);await page.goto(ready.url,{waitUntil:'load'});await page.waitForSelector('.rdg-explorer-home');assert.equal(await page.$eval('.rp-grid',n=>getComputedStyle(n).display),'none');assert.equal(await page.$('.rdg-graph'),null);await page.waitForSelector('.rdg-tree-process > [data-package-id]');await idle();page.off('request',intercept);await page.setRequestInterception(false);assert.equal(await state(),null);assert.deepEqual((await page.evaluate(()=>RDG_PORTABLE_EDITOR.session)).screens,[]);assert.equal(requests.filter(m=>m==='read').length,0);const box=await page.$eval('.rdg-explorer-home',n=>({x:n.getBoundingClientRect().x,width:n.getBoundingClientRect().width}));assert.deepEqual(box,{x:0,width:1440});await page.screenshot({path:path.join(base,'startup-explorer.png'),fullPage:true});checks.push('first paint is full-window Explorer, no legacy flash, graph read or implicit selection');await click('Пакеты','.rdg-explorer-tabs');assert(await page.$eval('.rdg-explorer-list',n=>n.textContent.includes('Определений: 0')));await click('Создать пакет','.rdg-explorer-list');await idle();assert(await page.$('.rdg-explorer-list h3'));assert.equal(await state(),null);await click('Графы','.rdg-explorer-tabs');checks.push('empty recommendation registry is valid; package editor opens from Explorer before any process is selected');await click('Ручная проверка Decision','.rdg-explorer');await page.waitForSelector('.rdg-decision[data-ui-build="decision-desktop-20261103-inspector-tabs"] svg');await idle();};await launch();
 // Real checkpoint lens fixture through the disposable preview API: the same
 // layout/viewer implementation works for working, ready and lens roles.
 const originalProcessId=(await state()).package.packageId;
 // This example is an ordinary synthetic Process Graph constructed through
 // public create/core-edit calls. Application startup has no demo injection.
 const writeExample=async request=>{const pre=await api({method:'preflight',request});
   const done=await api({method:'apply',request,expectedInputBinding:pre.inputBinding});
   assert(done.published);return done;};
 async function temporalPlanAcceptance(){
 const create=(await api({method:'schema',op:'create'})).request;Object.assign(create,{path:'processes/temporal-plan-ui',role:'working',title:'Temporal Plan UI',scope:'Synthetic temporal ordering only',coreModel:'rdg-decision-v1',rootReason:'No fake anchor action'});const pid=(await writeExample(create)).packages[0].packageId;
 const core=async(command,data)=>{const r=(await api({method:'schema',op:'core',packageId:pid,command})).request;r.note='Synthetic temporal fixture';r.data=data;await writeExample(r);};
 for(const id of ['D1','D2'])await core('add',{entity:{id,kind:'decision',title:id==='D1'?'Первый способ':'Второй способ',description:'A paper root'},initialRelations:[{id:'R'+id,type:'DRIVES',from:'R1',to:id}]});
 for(const [id,parent] of [['A1','D1'],['A2','D2'],['COMMON','R1']])await core('add',{entity:{id,kind:'action',title:id==='COMMON'?'Общий отчёт':'Работа '+id,description:'Actual task, never a branch marker',actionType:'task',lowLevel:false,targetIds:[],groupIds:[]},initialRelations:[{id:'REQUIRES-'+id,type:'REQUIRES_ACTION',from:parent,to:id}]});
 for(const [id,title,exclusive,required] of [['G','Выбор метода',true,true],['J','Совместное исследование',false,false]])await core('decision_group',{group:{id,title,parentId:'R1',selectionRequired:required,mutuallyExclusive:exclusive,members:[{id:id+'1',decisionId:'D1'},{id:id+'2',decisionId:'D2'}]}});
 await writeExample((await api({method:'schema',op:'plan_create',packageId:pid})).request);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),pid);await idle();const graphBefore=(await state()).graph;
 const dates=await page.evaluate(()=>{const f=n=>{const d=new Date();d.setDate(d.getDate()+n);return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');};return {start:f(0),end:f(2)};});
 await click('Ветвление Plan','.rdg-tools');await field('Название ветви','Выбрать способ по времени');await field('Начало после','');await field('Первое продолжение','Путь один');await field('Второе продолжение','Путь два');await field('Decision первого варианта','D1');await field('Decision второго варианта','D2');
 await field('Отметить конец ветвления',true);await field('Название общей части','Общая подготовка');await field('Дата начала',dates.start);await field('Время начала','09:30');await field('Дата конца',dates.end);await field('Время конца','10:15');await click('Проверить ветвление');await save();
 let row=await state(),fork=row.plan.forks[0];assert.equal(fork.afterStepId,null);assert(fork.startAt.startsWith(dates.start+'T09:30:00'));assert(fork.end.at.startsWith(dates.end+'T10:15:00'));assert.equal(row.plan.steps.length,0);assert.deepEqual(row.graph,graphBefore);
 const start='[data-fork-id="'+fork.id+'"]',end='[data-fork-end-id="'+fork.id+'"]';assert(await page.$(start));assert(await page.$(end));assert(!(await page.$eval(start,n=>n.textContent)).includes('Сохранённый факт'));
 assert((await page.$eval(start+' .rdg-road-card > [data-plan-root-id="D1"]',n=>n.textContent)).includes('На бумаге'));assert((await page.$eval(start+' .rdg-road-card > [data-plan-root-id="D1"]',n=>n.textContent)).includes('Взаимоисключающие'));assert((await page.$eval(start+' .rdg-road-card > [data-plan-root-id="D1"]',n=>n.textContent)).includes('Совместный выбор'));
 checks.push('Plan start/end are independent dated markers, without anchor Actions or saved-fact placeholders; root Decisions expose every real group and its choice rules');
 const edit=(await api({method:'schema',op:'plan_edit',packageId:pid})).request;const refs=row.references;edit.plan.steps=['A1','A2','COMMON'].map(id=>({id:'S-'+id,title:id,kind:'action',state:id==='COMMON'?'planned':'possible',ref:refs[id]}));edit.plan.mainStepIds=['S-COMMON'];edit.plan.forks[0].cases.forEach((c,i)=>c.stepIds=['S-A'+(i+1)]);await writeExample(edit);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),pid);await idle();row=await state();fork=row.plan.forks[0];const planBefore=JSON.stringify(row.plan),firstCase=fork.cases[0].id,secondCase=fork.cases[1].id;
 await page.evaluate(()=>{globalThis.__planCanvas=document.querySelector('.rdg-canvas');globalThis.__planRoad=document.querySelector('.rdg-road');});
 const begin=requests.length,t0=Date.now();await field('Показать продолжение',secondCase,start);timings.planCaseSwitchMs=Date.now()-t0;const used=requests.slice(begin);assert(used.length&&used.every(m=>m==='view_session'),JSON.stringify(used));assert(timings.planCaseSwitchMs<1500,'Case switch should use the snapshot, not expensive owner reads');
 assert(await page.evaluate(()=>globalThis.__planCanvas===document.querySelector('.rdg-canvas')&&globalThis.__planRoad===document.querySelector('.rdg-road')),'Case switch preserves Graph canvas and panel handles');
 assert(await page.$(start+' .rdg-road-card > [data-plan-root-id="D2"]'));assert(await page.$('[data-placement-id="S-A2"]'));assert.equal(await page.$('[data-placement-id="S-A1"]'),null);assert.equal(await page.$$eval('[data-placement-id="S-COMMON"]',a=>a.length),1);assert(await page.$(end));assert.equal(JSON.stringify((await state()).plan),planBefore);assert.deepEqual((await state()).graph,graphBefore);
 await page.screenshot({path:path.join(base,'temporal-plan-shared-end.png'),fullPage:true});
 checks.push('Case switch is snapshot-only with view-session CAS, preserves Graph DOM and resize handles, keeps shared continuation once, and never selects Decisions or changes Plan/Graph');
 await click('Изменить ветвление',start);await field('Отметить конец ветвления',false);await click('Проверить ветвление');await save();row=await state();assert(!('end' in row.plan.forks[0]));assert.equal(await page.$(end),null);assert.equal(await page.$$eval('[data-placement-id="S-COMMON"]',a=>a.length),1);assert.deepEqual(row.graph,graphBefore);assert.equal(row.plan.forks[0].startAt,fork.startAt);
 checks.push('Removing an optional end hides only the boundary; common steps, exact start date/time, root groups and original Graph facts survive');
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),originalProcessId);await idle();
 }
 async function inheritedHistoryAcceptance(){
 const create=async(path,title)=>{const r=(await api({method:'schema',op:'create'})).request;Object.assign(r,{path,role:'working',title,scope:'Synthetic history identity test',coreModel:'rdg-decision-v1',rootReason:'Isolated source identity'});return (await writeExample(r)).packages[0].packageId;};
 const source=await create('processes/history-source','Исходная цель истории'),target=await create('processes/history-target','Другая локальная цель');
 const add=(await api({method:'schema',op:'core',packageId:source,command:'add'})).request;
 add.note='Source candidate';add.data={entity:{id:'SOURCE-D',kind:'decision',title:'Исходное решение',description:'Synthetic'},initialRelations:[{id:'SOURCE-RD',type:'DRIVES',from:'R1',to:'SOURCE-D'}]};await writeExample(add);
 const inserted=(await api({method:'schema',op:'insert_copy',packageId:target,sourcePackageId:source})).request;inserted.note='Copy source facts into another R1 owner';await writeExample(inserted);
 const history=await api({method:'history',packageId:target});const event=history.events.find(r=>r.inherited&&r.event.type==='created'&&r.historyView.createdIds.includes('SOURCE-D'));assert(event);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph',historyMode:'all'}),target);await idle();
 const row='[data-event-id="'+event.event.id+'"]';await page.waitForSelector(row);
 assert((await page.$eval(row,n=>n.textContent)).includes('Исходное решение'));
 assert((await page.$eval(row+' .rdg-road-side-left',n=>n.textContent)).includes('Исходная цель истории'));
 assert(!(await page.$eval(row,n=>n.textContent)).includes('Другая локальная цель'));
 assert.equal(await page.$(row+' [data-road-node-id="R1"]'),null,'A source R1 cannot navigate to unrelated local R1');
 await page.screenshot({path:path.join(base,'history-inherited-identity.png'),fullPage:true});
 checks.push('Inherited History keeps recorded source names and static source references when local R1 collides; no relation or actor lookup across identity spaces');
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),originalProcessId);await idle();
 }
 async function findingAcceptance(){
 const create=(await api({method:'schema',op:'create'})).request;
 Object.assign(create,{path:'processes/analysis-acceptance',role:'working',title:'Analysis acceptance',scope:'Synthetic analysis only',coreModel:'rdg-decision-v1',rootReason:'Synthetic fixture'});
 const made=await writeExample(create),pid=made.packages[0].packageId;
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),pid);await idle();const rootId=(await state()).graph.rootRequirementId;
 const core=async(command,data)=>{const r=(await api({method:'schema',op:'core',packageId:pid,nodeId:data.nodeId||rootId,command})).request;Object.assign(r,{note:'Synthetic analysis fixture',data});return writeExample(r);};
 await core('add',{entity:{id:'AN-D',kind:'decision',title:'Выбрать PostgreSQL',description:'A paper decision'},initialRelations:[{id:'AN-DR',type:'DRIVES',from:rootId,to:'AN-D'}]});
 await core('add',{entity:{id:'AN-CAN',kind:'canon',title:'Критерии применимости',description:'Methodology','guidance':'Проверить нагрузку и ограничения процесса'},initialRelations:[{id:'AN-CD',type:'CANON_FOR',from:'AN-CAN',to:'AN-D'}]});
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'AN-D'}),pid);await idle();await click('Сведения','.rdg-tools');
 await click('Контекст процесса','.rdg-tools');await click('Группа +','.rdg-context-bank');await field('Название группы','Сроки');await field('Основание изменения','Категоризировать факты');await click('Проверить группу');await save();
 let graph=(await state()).graph;const top=graph.contextGroups.find(g=>g.title==='Сроки').id;
 await click('Свернуть группу Сроки','.rdg-context-bank');await click('Группа +','.rdg-context-bank');await field('Название группы','Дедлайны');await field('Основание изменения','Вложенная категория');await click('Проверить группу');await save();
 graph=(await state()).graph;const child=graph.contextGroups.find(g=>g.title==='Дедлайны').id;assert.equal(graph.contextGroups.find(g=>g.id===child).parentId,top);
 await click('Добавить контекст процесса','.rdg-context-bank');await field('Название','Нагрузка сервиса');await field('Содержание','100 запросов/с');await field('Группа',child);await field('Основание изменения','Новый факт в группе');await click('Добавить контекст');await save();
 graph=(await state()).graph;const fact=graph.objects.find(n=>n.kind==='context');assert.equal(fact.contextGroupId,child);const factId=fact.id;
 const bankSearch=async value=>{await page.$eval('.rdg-context-bank-search input',(n,value)=>{n.value=value;n.dispatchEvent(new Event('input',{bubbles:true}));},value);};
 const beforeSearch=JSON.stringify(await state());await bankSearch('Сроки');assert(await page.$('.rdg-context-bank-item[data-context-id="'+factId+'"]'));await bankSearch('');assert.equal(await page.$('.rdg-context-bank-item[data-context-id="'+factId+'"]'),null,'search restores the collapsed parent');assert.equal(JSON.stringify(await state()),beforeSearch);
 await click('Раскрыть группу Сроки','.rdg-context-bank');await page.click('.rdg-context-bank-item[data-context-id="'+factId+'"]');await idle();
 await click('Переместить','.rdg-context-bank-entry');await field('Группа','');await field('Основание изменения','Факт без группы');await click('Проверить перенос');await save();assert(!((await state()).graph.objects.find(n=>n.id===factId).contextGroupId));
 await click('Переместить','.rdg-context-bank-entry');await field('Группа',child);await field('Основание изменения','Вернуть в подгруппу');await click('Проверить перенос');await save();
 await page.click('[data-context-group-id="'+child+'"] button:last-child');await idle();await field('Основание изменения','Удалить папку, сохранить факт');await click('Удалить группу');await save();graph=(await state()).graph;assert.equal(graph.objects.find(n=>n.id===factId).contextGroupId,top);assert(!graph.contextGroups.some(g=>g.id===child));
 await page.screenshot({path:path.join(base,'context-groups.png'),fullPage:true});await click('Закрыть банк контекстов');
 checks.push('Process context groups: nested creation, fact placement/move, search paths restore folds without writes; removing folder preserves real Context and links');
 await click('Теория принятия решения','.rdg-inspector-tabs');await click('Записать файндинг');await field('Название файндинга','Нагрузка может сделать выбор неуместным');await field('Содержание файндинга','Проверить поведение при росте нагрузки');await field('Тип файндинга','risk');await field('Обоснование находки','Есть механизм роста задержек');await field('Основание изменения','Зафиксировать анализ канона');await click('Проверить файндинг');await save();
 graph=(await state()).graph;const finding=graph.objects.find(n=>n.kind==='finding');assert.equal(finding.subjectId,'AN-D');assert.equal(finding.analysisSources[0].sourceId,'AN-CAN');assert.equal(await page.$eval('.rdg-inspector',n=>n.textContent.includes('Создать решение разрешить')),false);assert.equal(await page.$eval('.rdg-inspector',n=>n.textContent.includes('Добавить proposal')),false);
 await click('Зависимости','.rdg-finding-card');await click('+ Ручная зависимость L1/L2');await field('Источник зависимости',factId);await field('Основание изменения','Наблюдать основание находки');await click('Проверить зависимость');await save();await click('← К файндингам');
 await click('Контекст принятия решения','.rdg-inspector-tabs');assert.equal(await page.$$eval('[data-context-source-id]',rows=>rows.length),1);assert((await page.$eval('[data-context-source-id]',n=>n.textContent)).includes('Относится к файндингу'));
 assert.equal(await page.$eval('[data-context-source-id]',n=>[...n.querySelectorAll('button')].some(b=>b.textContent==='Убрать ручное участие')),false);
 await click('Изменить роль');await field('Роль элемента','Нагрузка ограничивает применимость');await field('Основание изменения','Уточнить роль факта');await click('Проверить контекст');await save();
 await click('Теория принятия решения','.rdg-inspector-tabs');await click('Добавить в контекст решения');await field('Элемент контекста',factId);await field('Роль элемента','Факт проверяет критерий канона');await field('Основание изменения','Ручное основание по канону');await click('Проверить контекст');await save();await click('Контекст принятия решения','.rdg-inspector-tabs');
 assert.equal(await page.$$eval('[data-context-source-id]',rows=>rows.length),1);assert.equal((await state()).decisionContexts['AN-D'][0].manual,true);await click('Убрать ручное участие');await field('Основание изменения','Сохранить только происхождение Finding');await click('Проверить контекст');await save();
 assert.equal((await state()).decisionContexts['AN-D'][0].manual,false);assert.equal((await state()).decisionContexts['AN-D'][0].comment,'Факт проверяет критерий канона');
 const jump=await page.evaluateHandle(()=>[...document.querySelectorAll('.rdg-context-dependency-row button')].find(b=>b.textContent.startsWith('Относится к файндингу')));await jump.asElement().click();await jump.dispose();await idle();assert(await page.$('[data-finding-id="'+finding.id+'"]'));await click('← К контексту решения');assert(await page.$('[data-context-source-id="'+factId+'"]'));
 await page.screenshot({path:path.join(base,'analysis-context.png'),fullPage:true});
 checks.push('Decision analysis: Canon creates Finding and context role with provenance; dependency sources inherit one protected context row; manual removal preserves Finding origin and commentary');
 // Inspector width remains view-only in both projections.
 const beforeResize=JSON.stringify(await state()),requestStart=requests.length;const width=()=>page.$eval('.rdg-inspector',n=>n.getBoundingClientRect().width);const oldWidth=await width();
 const handle=await page.$eval('[aria-label="Ширина сведений"]',n=>{const r=n.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+70};});await page.mouse.move(handle.x,handle.y);await page.mouse.down();await page.mouse.move(handle.x-90,handle.y,{steps:4});await page.mouse.up();await idle();assert(Math.abs(await width()-oldWidth-90)<2);
 await page.focus('[aria-label="Ширина сведений"]');await page.keyboard.press('ArrowLeft');await idle();assert(await page.$eval('[aria-label="Ширина сведений"]',n=>n===document.activeElement));assert.equal(JSON.stringify(await state()),beforeResize);assert(requests.slice(requestStart).every(m=>m==='view_session'));
 await click('Структура','.rdg-tools');const wide=await width();await click('Граф','.rdg-tools');assert.equal(await width(),wide);
 checks.push('Inspector resize preserves keyboard focus and model snapshot across Graph/Structure');
 await core('add',{entity:{id:'AN-R',kind:'requirement',title:'Сохранять подробный аудит',description:'Requirement whose necessity is in question',scope:'Synthetic'},initialRelations:[{id:'AN-RR',type:'DERIVES',from:rootId,to:'AN-R'}]});
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'AN-R'}),pid);await idle();await click('Сведения','.rdg-tools');assert.equal(await page.$('.rdg-inspector-tab[data-inspector-tab="findings"]'),null);await click('Обсудить обязательность');await field('Родительское основание',rootId);await field('Прямое обязательство','AN-RR');await field('Основание изменения','Сделать необходимость предметом выбора');await click('Проверить решение');await save();
 graph=(await state()).graph;const chosen=graph.edges.find(e=>e.type==='INTRODUCES'&&e.to==='AN-R').from;assert.equal(graph.nodes.find(n=>n.id===chosen).selectionState,'discovered');assert.equal(graph.nodes.filter(n=>n.id==='AN-R').length,1);assert(!graph.edges.some(e=>e.id==='AN-RR'));await click('Структура','.rdg-tools');await page.waitForSelector('.rdg-outline-row[data-entity-id="'+chosen+'"]');
 const unchanged=JSON.stringify((await state()).graph);await click('Контекст процесса','.rdg-tools');assert(await page.$('[data-context-group-id="'+top+'"]'));await click('Закрыть банк контекстов');await click('Граф','.rdg-tools');assert.equal(JSON.stringify((await state()).graph),unchanged);await page.screenshot({path:path.join(base,'requirement-decision.png'),fullPage:true});
 // Changing the actual fact still triggers ordinary Finding review.
 await core('edit',{nodeId:factId,changes:{value:'1000 запросов/с'},cosmetic:false});await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'AN-D'}),pid);await idle();await click('Сведения','.rdg-tools');await click('Файндинги','.rdg-inspector-tabs');assert((await state()).graph.objects.find(n=>n.id===finding.id).review.required);
 checks.push('Requirement necessity uses a real paper Decision with original R identity; no Finding creation on R; same process groups in both projections; fact content still invalidates Finding');
 // Regression: an ordinary paper branch plus Findings on several Decisions
 // must open from the landing Explorer, then permit opening another process.
 await core('add',{entity:{id:'AN-CHILD',kind:'requirement',title:'Продолжение варианта',description:'Synthetic branch',scope:'Synthetic'},initialRelations:[{id:'AN-D-CHILD',type:'INTRODUCES',from:'AN-D',to:'AN-CHILD'}]});
 await core('add',{entity:{id:'AN-D2',kind:'decision',title:'Второй вариант',description:'Synthetic analysis branch'},initialRelations:[{id:'AN-DR2',type:'DRIVES',from:rootId,to:'AN-D2'}]});
 await core('add',{entity:{id:'AN-F2',kind:'finding',title:'Риск второго варианта',description:'Synthetic',subjectId:'AN-D2',findingType:'risk',rationale:'Plausible synthetic mechanism',evidenceIds:[]}});
 await core('link',{relation:{id:'AN-XF2',type:'DEPENDS_ON',from:factId,to:'AN-F2',dependencyLevel:'L1'}});
 await page.reload({waitUntil:'load'});await page.waitForSelector('.rdg-explorer-home');await idle();
 await page.click('.rdg-tree-process > [data-package-id="'+pid+'"]');
 await page.waitForFunction(id=>!RDG_PORTABLE_EDITOR.busy&&RDG_PORTABLE_EDITOR.view?.package.packageId===id,{timeout:10000},pid);
 assert(await page.$('.rdg-decision svg'));assert.equal(await page.$eval('.rdg-status',n=>n.classList.contains('rdg-error')?n.textContent:''),'');
 assert((await state()).decisionContexts['AN-D2'].some(r=>r.sourceId===factId));
 await click('Структура','.rdg-tools');assert(await page.$('.rdg-outline-row[data-entity-id="AN-D"]'));assert((await state()).decisionContexts['AN-D2'].some(r=>r.sourceId===factId));
 await page.click('.rdg-brand');await idle();await page.click('.rdg-tree-process > [data-package-id="'+originalProcessId+'"]');
 await page.waitForFunction(id=>!RDG_PORTABLE_EDITOR.busy&&RDG_PORTABLE_EDITOR.view?.package.packageId===id,{timeout:10000},originalProcessId);
 checks.push('Explorer opens a branched existing process with multiple Decision Findings within the request budget; Graph/Structure show the same sources and another process opens afterwards');
 // Findings stay in the Decision inspector; ordinary process facts support
 // the disposition without a separate Evidence entity or a canvas image.
 const review=(await api({method:'schema',op:'core',packageId:pid,nodeId:finding.id,command:'review'})).request;review.note='Review supporting process data';review.data.basis=review.note;await writeExample(review);
 await page.evaluate(({pid,id})=>RDG_PORTABLE_EDITOR.open(pid,{kind:'focus',id}),{pid,id:finding.id});await idle();
 if(await page.$('.rdg-explorer:not(.rdg-explorer-home)')){await page.click('.rdg-brand');await idle();}
 assert.equal((await state()).view.spec.id,'AN-D');assert(await page.$('.rdg-inspector-tab[data-inspector-tab="findings"][aria-selected="true"]'));
 assert.equal(await page.$$eval('.rdg-node[data-kind="finding"],.rdg-node[data-kind="evidence"]',nodes=>nodes.length),0);
 await click('Указать итог рассмотрения','.rdg-finding-card[data-finding-id="'+finding.id+'"]');await field('Итог рассмотрения','resolved');await field('Обоснование итога','Проверенный результат подтверждён данными процесса');await field('Нагрузка сервиса',true);await click('Проверить итог');await save();
 assert.equal((await state()).graph.objects.find(n=>n.id===finding.id).disposition.code,'resolved');assert.deepEqual((await state()).graph.objects.find(n=>n.id===finding.id).disposition.evidenceIds,[factId]);
 await click('Структура','.rdg-tools');assert.equal(await page.$$eval('.rdg-outline-row[data-kind="finding"],.rdg-outline-row[data-kind="evidence"]',nodes=>nodes.length),0);
 await click('Контекст процесса','.rdg-tools');assert(await page.$('.rdg-context-bank-item[data-context-id="'+factId+'"]'));await page.screenshot({path:path.join(base,'confirmation-context-only.png'),fullPage:true});await click('Закрыть банк контекстов');
 checks.push('Findings are Decision-inspector records in Graph/Structure and direct-link navigation; ordinary process Context supports a verified disposition without a separate Evidence kind');
 }
 if(process.env.RDG_FINDINGS_ONLY==='1'){await findingAcceptance();assert.deepEqual(errors,[]);console.log(JSON.stringify({pass:true,cases:checks.length,checks,artifacts:base}));return;}
 const createExample=(await api({method:'schema',op:'create'})).request;
 Object.assign(createExample,{role:'working',path:'examples/decision-context-postgresql',
   title:'Пример процесса · выбор хранилища',scope:'Учебная ситуация текущего процесса',
   coreModel:'rdg-decision-v1',rootReason:'Различить родителей, факты и канон'});
 const createdExample=await writeExample(createExample);
 const exampleRow={packageId:createdExample.packages[0].packageId,role:'working'};
 const seedBlocks=[
  [{id:'R-COST',kind:'requirement',title:'Не увеличивать стоимость поддержки',
    description:'Текущее ограничение бюджета',scope:'Этот процесс'},
   {id:'E-R-COST',type:'DERIVES',from:'R1',to:'R-COST'}],
  [{id:'D-HOST',kind:'decision',title:'Размещать сервис на своём сервере',
    description:'Существующий вариант инфраструктуры'},
   {id:'E-D-HOST',type:'DRIVES',from:'R1',to:'D-HOST'}],
  [{id:'C-HOST',kind:'context',title:'На сервере уже работает PostgreSQL',
    description:'Факт этого процесса',value:'Существующая инфраструктура содержит PostgreSQL'},null],
  [{id:'D-STORE',kind:'decision',title:'Использовать PostgreSQL',
    description:'Кандидат, оцениваемый в условиях текущего процесса'},
   {id:'E-D-STORE',type:'DRIVES',from:'R1',to:'D-STORE'}],
  [{id:'CANON-STORE',kind:'canon',title:'Канон · выбор PostgreSQL',
    description:'Общие критерии, не факты процесса',guidance:'Подходит при сложных связях и транзакциях; сравнить поддержку и альтернативы.'},
   {id:'E-CANON-STORE',type:'CANON_FOR',from:'CANON-STORE',to:'D-STORE'}],
  [{id:'INFO-STORE',kind:'info',title:'Факты о транзакциях',
    description:'Наблюдение для оценки канона',value:'Ожидаются параллельные транзакции'},
   {id:'E-INFO-STORE',type:'INFO_FOR',from:'INFO-STORE',to:'CANON-STORE'}]
 ];
 for(const [entity,relation] of seedBlocks){const request=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,command:'add'})).request;
   request.note='Synthetic example, isolated browser owner';request.data={entity,location:'graph',...(relation?{initialRelations:[relation]}:{})};
   await writeExample(request);
 }
 const contextRequest=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,nodeId:'D-STORE',command:'edit'})).request;
 contextRequest.note='Link to actual objects of this synthetic process';
 contextRequest.data={nodeId:'D-STORE',changes:{decisionContextIds:['R-COST','D-HOST','C-HOST'],contextNotes:{'R-COST':'Budget constraint','D-HOST':'Chosen infrastructure','C-HOST':'Existing service'}},cosmetic:false};
 await writeExample(contextRequest);
 const exampleBefore=await api({method:'read',packageId:exampleRow.packageId});
 const contextChoice=exampleBefore.graph.nodes.find(n=>n.id==='D-STORE');
 assert.deepEqual(contextChoice.decisionContextIds,['R-COST','D-HOST','C-HOST']);
 assert.equal(exampleBefore.graph.objects.filter(n=>n.id==='C-HOST').length,1);
 assert.equal(exampleBefore.graph.objects.filter(n=>n.id==='CANON-STORE').length,1);
 assert.equal(exampleBefore.graph.objects.filter(n=>n.id==='INFO-STORE').length,1);
 assert(exampleBefore.graph.edges.some(e=>e.type==='CANON_FOR'&&e.from==='CANON-STORE'&&e.to==='D-STORE'));
 assert(exampleBefore.graph.edges.some(e=>e.type==='INFO_FOR'&&e.from==='INFO-STORE'&&e.to==='CANON-STORE'));
 assert(!exampleBefore.graph.edges.some(e=>e.to==='D-STORE'&&['R-COST','D-HOST','C-HOST'].includes(e.from)),
   'factual links must not masquerade as parents');
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'D-STORE'}),exampleRow.packageId);
 await idle();
 const exampleFocused=await state();
 assert.deepEqual(exampleFocused.view.visual.nodes.map(n=>n.entityId).sort(),
   ['R1','R-COST','D-HOST','C-HOST','D-STORE'].sort());
 assert(!exampleFocused.view.visual.nodes.some(n=>n.entityId==='CANON-STORE'),
   'Canon is no longer a graph image in Decision focus');
 assert.equal(await page.$$eval('.rdg-node[data-entity-id="C-HOST"]',n=>n.length),0,
  'factual process Ctx is in the process-wide bank, not displayed as a focus card');
 assert.equal(await page.$$eval('.rdg-graph [data-relation-id="E-CANON-STORE"]',n=>n.length),0,
  'hidden supporting objects are not given orphan visual connections');
 for(const id of ['R-COST','D-HOST','C-HOST'])
   assert(exampleFocused.view.visual.positions[id].x<exampleFocused.view.visual.positions['D-STORE'].x,
     'factual Decision context appears on the input side of the Decision');
 await page.$eval('[data-entity-id="D-STORE"]',n=>n.dispatchEvent(new MouseEvent('click',{bubbles:true})));
 await idle();
 const exampleInspector=await page.$eval('.rdg-inspector',n=>n.textContent);
 assert(exampleInspector.includes('Контекст принятия решения')&&
        exampleInspector.includes('На сервере уже работает PostgreSQL')&&
        exampleInspector.includes('Не увеличивать стоимость поддержки'));
 assert.deepEqual(await page.$$eval('.rdg-inspector-tab',nodes=>nodes.map(n=>n.textContent)),
   ['Рекомендации · 0','Контекст принятия решения','Теория принятия решения','Файндинги','Вопросы · 0','Зависимости']);
 const contextBadges=await page.$$eval('.rdg-inspector-tabpanel[data-inspector-panel="context"] .rdg-entity-reference',
   nodes=>nodes.map(n=>({kind:n.dataset.kind,code:n.querySelector('.rdg-entity-reference-kind')?.textContent})));
 assert.deepEqual(contextBadges,[{kind:'requirement',code:'R'},{kind:'decision',code:'D'},{kind:'context',code:'Ctx'}]);
 await page.screenshot({path:path.join(base,'decision-context-example.png'),fullPage:true});
 await click('Теория принятия решения','.rdg-inspector-tabs');
 const canonPanel=await page.$eval('.rdg-inspector-tabpanel[data-inspector-panel="canon"]',n=>n.textContent);
 assert(canonPanel.includes('Подходит при сложных связях и транзакциях'));
 assert(canonPanel.includes('Ожидаются параллельные транзакции'));
 assert.equal(await page.$$eval('.rdg-canon-info-row',nodes=>nodes.length),1);
 assert.equal(await page.$eval('.rdg-canon-info-row .rdg-entity-reference-kind',n=>n.textContent),'Inf');
 await page.screenshot({path:path.join(base,'decision-canon-example.png'),fullPage:true});
 await page.$eval('.rdg-canon-info-row .rdg-entity-reference',n=>n.click());await idle();
 await page.waitForFunction(()=>RDG_PORTABLE_EDITOR.view?.view?.spec?.id==='INFO-STORE',{timeout:10000});
 assert.equal((await state()).view.spec.id,'INFO-STORE','Canon-linked Info navigates to its original owner object');
 assert((await page.$eval('.rdg-inspector',n=>n.textContent)).includes('Ожидаются параллельные транзакции'));
 assert.deepEqual((await api({method:'read',packageId:exampleRow.packageId})).graph,exampleBefore.graph,
   'opening the illustrated focus never alters the Process Graph');
 // Canon/Info authoring from Inspector must create correctly linked owner objects:
 // no disconnected Canon becomes unreachable when the canvas hides Canon cards.
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'D-STORE'}),exampleRow.packageId);
 await idle();
 await page.$eval('[data-entity-id="D-STORE"]',n=>n.dispatchEvent(new MouseEvent('click',{bubbles:true})));await idle();
 await click('Теория принятия решения','.rdg-inspector-tabs');
 await click('Добавить информацию','.rdg-canon-actions');
 await field('Название','Новая справка Canon');
 await field('Значение Context или Info','Тестовая информация');
 await field('Основание изменения','Дописать связанную информацию из вкладки Canon');
 await click('Добавить блок','.rdg-modal');await save();
 let authored=await api({method:'read',packageId:exampleRow.packageId});
 const authoredInfo=authored.graph.objects.find(n=>n.title==='Новая справка Canon');
 assert(authoredInfo&&authoredInfo.kind==='info');
 assert(authored.graph.edges.some(e=>e.type==='INFO_FOR'&&e.from===authoredInfo.id&&e.to==='CANON-STORE'),
   'new Info is linked to the original Canon');
 assert.equal((await state()).view.visual.nodes.some(n=>n.entityId===authoredInfo.id),false,
   'new Canon-only Info does not become an orphan picture');
 await click('Теория принятия решения','.rdg-inspector-tabs');
 await click('Добавить теорию','.rdg-inspector-tabpanel');
 await field('Название','Новый канон из сведений');
 await field('Общее','Критерии оценки без блокировок');
 await field('Основание изменения','Добавить ещё один канон из вкладки');
 await click('Добавить блок','.rdg-modal');await save();
 authored=await api({method:'read',packageId:exampleRow.packageId});
 const authoredCanon=authored.graph.objects.find(n=>n.title==='Новый канон из сведений');
 assert(authoredCanon&&authoredCanon.kind==='canon'&&authoredCanon.guidance==='Критерии оценки без блокировок');
 assert(authored.graph.edges.some(e=>e.type==='CANON_FOR'&&e.from===authoredCanon.id&&e.to==='D-STORE'),
   'new Canon is directly linked to the selected Decision');
 assert.equal((await state()).view.visual.nodes.some(n=>n.entityId===authoredCanon.id),false);
 // Alternate outline: parent/child occurrences, Decision Group and shared
 // WorkGraph identity. All setup uses only normal public API in temporary data.
 const addOutline=async(entity,relation=null)=>{
  const request=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,command:'add'})).request;
  request.note='Isolated outline fixture, no live owner';request.data={entity,location:'graph',
    ...(relation?{initialRelations:[relation]}:{})};await writeExample(request);
 };
 await addOutline({id:'R-CHOICE',kind:'requirement',title:'Выбрать технологию хранения',
   description:'Alternative selection within this process',scope:'This process'},
   {id:'E-CHOICE',type:'DERIVES',from:'R1',to:'R-CHOICE'});
 await addOutline({id:'D-ALT',kind:'decision',title:'Использовать SQLite',
   description:'Alternative to PostgreSQL'});
 await addOutline({id:'R-POST',kind:'requirement',title:'Поддержать миграции',
   description:'Shared obligation of both structural parents',scope:'Current data'},
   {id:'E-POST',type:'INTRODUCES',from:'D-STORE',to:'R-POST'});
 const linkOutline=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,command:'link'})).request;
 linkOutline.note='Second true parent of shared Requirement';
 linkOutline.data={relation:{id:'E-POST-OTHER',type:'DERIVES',from:'R-CHOICE',to:'R-POST'}};
 await writeExample(linkOutline);
 const groupOutline=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,command:'decision_group'})).request;
 groupOutline.note='True reusable graph Decision Group with two members';
 groupOutline.data={group:{id:'G-CHOICE',parentId:'R-CHOICE',title:'Выбор технологии',
   selectionRequired:true,mutuallyExclusive:true,
   members:[{id:'GM-PG',decisionId:'D-STORE'},{id:'GM-SQ',decisionId:'D-ALT'}]}};
 await writeExample(groupOutline);
 const areaOutline=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,command:'work_graph'})).request;
 areaOutline.note='One view of the same process owner IDs';
 areaOutline.data={workGraph:{id:'WG-OUTLINE',title:'Тест дерева · общие блоки',rootIds:['R1'],
   memberIds:['R1','R-CHOICE','D-STORE','D-ALT','R-POST','C-HOST','CANON-STORE']}};
 await writeExample(areaOutline);
 const outlineOwner=await api({method:'read',packageId:exampleRow.packageId,includePlan:true});
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),exampleRow.packageId);await idle();
 const graphKey=(await state()).view.graphKey;
 // Decision Group must remain a readable, clickable caption on each real
 // DECISION_MEMBER edge, never an invented extra node (full process graph).
 const groupGraph=await page.evaluate(()=>{
  const svg=document.querySelector('svg.rdg-graph');
  const layer=svg?.querySelector('.rdg-decision-group-labels');
  const badges=[...svg.querySelectorAll('.rdg-decision-group-caption[data-group="G-CHOICE"]')];
  const rectangles=[...svg.querySelectorAll('.rdg-decision-group-badge[data-group="G-CHOICE"]')];
  const cards=[...svg.querySelectorAll('.rdg-node')];
  const routes=[...svg.querySelectorAll('path[data-relation-id]')].filter(n=>['GM-PG','GM-SQ'].includes(n.dataset.relationId));
  return {labels:badges.map(n=>({text:n.textContent,visibility:getComputedStyle(n).visibility,
    role:n.getAttribute('role'),tabindex:n.getAttribute('tabindex'),id:n.dataset.group,
    x:Number(n.getAttribute('x')),y:Number(n.getAttribute('y'))})),
   rectangles:rectangles.map(n=>({visibility:getComputedStyle(n).visibility,x:Number(n.getAttribute('x'))})),
   routeIds:routes.map(n=>n.dataset.relationId).sort(),nodes:cards.length,
   labelLayerLast:layer===svg.lastElementChild,
   noGroupNode:cards.every(n=>n.dataset.entityId!=='G-CHOICE')};
 });
 assert.equal(groupGraph.labels.length,2,'both group membership edges retain their labels');
 assert.equal(groupGraph.rectangles.length,2,'every label has a visible interaction pill');
 assert(groupGraph.labels.every(n=>n.visibility==='visible'&&n.role==='button'&&n.tabindex==='0'&&
  n.text.includes('G-CHOICE')&&Number.isFinite(n.x)&&Number.isFinite(n.y)));
 assert(groupGraph.rectangles.every(n=>n.visibility==='visible'));
 assert.deepEqual(groupGraph.routeIds,['GM-PG','GM-SQ']);
 assert(groupGraph.labelLayerLast,'group labels are painted in front of opaque Graph cards');
 assert(groupGraph.noGroupNode,'group representation remains a label on real membership links, not a synthetic DG card');
 await page.screenshot({path:path.join(base,'decision-group-graph-labels-restored.png'),fullPage:true});
 const beforeGroupClick=(await state()).view.spec;
 await page.$('.rdg-decision-group-caption[data-group="G-CHOICE"]').then(n=>n.click());await idle();
 assert.deepEqual((await state()).view.spec,beforeGroupClick,
  'a single click on the group label must only select its inspector, not change Graph scope');
 assert((await page.$eval('.rdg-inspector',n=>n.textContent)).includes('Выбор технологии'),
  'the label opens the existing group details');
 assert.equal(await page.$$eval('.rdg-inspector [data-open-decision-group="G-CHOICE"]',n=>n.length),1);
 assert.equal(await page.$$eval('.rdg-group-parent-crumb',n=>n.length),0,
  'mere selection never changes the view into an opened group');
 await page.screenshot({path:path.join(base,'decision-group-label-inspector-only.png'),fullPage:true});
 await click('Открыть группу','.rdg-inspector');
 assert.deepEqual((await state()).view.spec.groupIds,['G-CHOICE'],
  'explicit open switches to original group-filtered graph view');
 assert((await page.$eval('.rdg-canvas-head .rdg-crumb',n=>n.textContent)).includes('Открыта группа решений · Выбор технологии'));
 assert.equal(await page.$eval('.rdg-group-parent-crumb',n=>n.dataset.groupParentId),'R-CHOICE');
 assert((await page.$eval('.rdg-group-parent-crumb',n=>n.textContent)).includes('Родитель группы · R ·'));
 assert((await page.$eval('.rdg-tabs',n=>n.textContent)).includes('Открыта группа решений'),
  'the group view is labeled in the tab as well as in the canvas breadcrumb');
 assert((await page.$eval('.rdg-inspector',n=>n.textContent)).includes('Исходный Requirement:'));
 assert(await page.$eval('.rdg-inspector [data-open-decision-group="G-CHOICE"]',n=>n.disabled),
  'group-details button reflects that the group view is already open');
 assert((await state()).view.visual.nodes.some(n=>n.entityId==='R-CHOICE'),
  'the group view includes the actual source Requirement');
 const groupViewVisualIds=(await state()).view.visual.nodes.map(n=>n.entityId);
 assert(['D-STORE','D-ALT'].every(id=>groupViewVisualIds.includes(id)),
  'group view preserves the original decision IDs');
 await page.screenshot({path:path.join(base,'decision-group-explicit-open-parent.png'),fullPage:true});
 await click('← Назад','.rdg-view-trail');
 assert.deepEqual((await state()).view.spec,beforeGroupClick,
  'back returns to the exact previous Graph view after explicitly opening group');
 assert.equal(await page.$$eval('.rdg-group-parent-crumb',n=>n.length),0);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),exampleRow.packageId);await idle();
 assert.equal(await page.$$eval('.rdg-decision-group-caption[data-group="G-CHOICE"]',n=>n.length),2);
 // Both the automatic layout and existing manual layout must preserve the
 // identical interactive membership labels on the real relation routes.
 await click('Моя раскладка','.rdg-zoom');
 assert.equal((await state()).view.spec.compactGraph,false);
 assert.equal(await page.$$eval('.rdg-decision-group-caption[data-group="G-CHOICE"]',n=>n.length),2);
 assert(await page.$$eval('.rdg-decision-group-caption[data-group="G-CHOICE"]',
  a=>a.every(n=>getComputedStyle(n).visibility==='visible')));
 await click('Уплотнить обзор','.rdg-zoom');
 assert.equal(await page.$$eval('.rdg-decision-group-caption[data-group="G-CHOICE"]',n=>n.length),2);
 assert(await page.$$eval('.rdg-decision-group-caption[data-group="G-CHOICE"]',
  a=>a.every(n=>getComputedStyle(n).visibility==='visible')));
 await click('Структура','.rdg-presentation-modes');
 assert.equal(await page.$('.rdg-graph'),null,'structure is not a second SVG graph');
 // The same group detail→open flow also works from the semantic Structure
 // view; opening the group switches intentionally to Graph, Back restores
 // the exact prior Structure mode and graph scope.
 const structureBeforeGroup=(await state()).view.spec;
 const groupStructureRow=await page.$('.rdg-outline-row[data-entity-id="D-STORE"] .rdg-outline-group-caption[data-group-id="G-CHOICE"]');
 assert(groupStructureRow,'real Decision Group membership must have its property chip in Structure');
 await groupStructureRow.click();await idle();
 assert.deepEqual((await state()).view.spec,structureBeforeGroup,
  'a group row click opens its inspector without navigating away from Structure');
 assert.equal(await page.$('.rdg-graph'),null);
 await click('Открыть группу','.rdg-inspector');
 assert.equal(await page.$('.rdg-graph'),null,'explicit group open retains the user-selected Structure mode');
 assert.deepEqual((await state()).view.spec.groupIds,['G-CHOICE']);
 assert((await page.$eval('.rdg-outline-head strong',n=>n.textContent)).includes('Открыта группа решений'));
 assert((await page.$eval('.rdg-outline-head',n=>n.textContent)).includes('Родитель группы · R ·'));
 await click('← Назад','.rdg-outline-head');
 assert.equal(await page.$('.rdg-graph'),null,'Back restores Structure mode');
 const afterStructureBack=(await state()).view.spec;
 assert.deepEqual(Object.fromEntries(Object.entries(afterStructureBack).filter(([key])=>key!=='camera')),
  Object.fromEntries(Object.entries(structureBeforeGroup).filter(([key])=>key!=='camera')),
  'Back restores the structural scope; the ephemeral Graph camera is not a Structure requirement');
 assert((await page.$eval('.rdg-outline-head strong',n=>n.textContent)).includes('Весь процесс'));
 assert.equal((await page.evaluate(()=>RDG_PORTABLE_EDITOR.session.screens.find(s=>s.id===RDG_PORTABLE_EDITOR.session.activeScreenId).presentation.mode)),'structure');
 assert.equal((await state()).view.spec.kind,'graph','no new Graph view kind');
 assert.equal((await state()).view.graphKey,graphKey,'same owner layout key');
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="D-STORE"]',n=>n.length),2,
   'one decision repeats under DRIVES parent and an explicit group parent');
 assert.equal(await page.$$eval('.rdg-outline-row[data-outline-type=materials]',n=>n.length),0,
  'expanded Context/Info/Evidence are real lines, not a permanent Mat envelope');
 assert.equal(await page.$$eval('.rdg-outline-row[data-outline-type=section][data-outline-section=requirements]',n=>n.length),0,
  'expanded mandatory Requirement groups are not permanent section rows');
 assert.equal(await page.$$eval('.rdg-outline-row[data-outline-type=section][data-outline-section=decisions]',n=>n.length),0,
  'expanded Decision groups are not permanent type section rows');
 // The old protruding collapse chevrons are gone. Right-click on ANY
 // direct Requirement sibling opens our own menu (browser native suppressed),
 // while its ordinary child-disclosure remains inside the card.
 assert.equal(await page.$$eval('.rdg-outline-section-toggle',nodes=>nodes.length),0);
 const bareGroup=await page.$eval('.rdg-outline-row[data-section-context=requirements][data-entity-id="R-COST"]',row=>({
  key:row.dataset.sectionContextKey,entityId:row.dataset.entityId,
  ownDisclosure:!!row.querySelector('[data-outline-toggle]')}));
 assert(bareGroup.key&&bareGroup.entityId==='R-COST');
 assert.equal(await page.$$eval('.rdg-outline-row[data-section-context=requirements][data-section-context-key="'+bareGroup.key+'"]',nodes=>nodes.length),2,
  'both direct sibling Requirements expose identical view-only context-menu group keys');
 const groupCountsBefore=await page.$$eval('.rdg-outline-row[data-outline-type=entity][data-kind=requirement]',nodes=>nodes.length);
 await page.click('.rdg-outline-row[data-section-context=requirements][data-entity-id="R-COST"]',{button:'right'});
 assert(await page.$('[data-outline-context-menu][role=menu]'),'right click displays RDG menu rather than browser menu');
 assert((await page.$eval('[data-outline-context-menu]',n=>n.textContent)).includes('Свернуть элементы одного уровня'));
 await page.screenshot({path:path.join(base,'structure-custom-right-click-menu.png'),fullPage:true});
 await page.keyboard.press('Escape');
 assert.equal(await page.$$eval('[data-outline-context-menu]',nodes=>nodes.length),0,
  'Escape closes custom menu');
 const contextRow='.rdg-outline-row[data-section-context=requirements][data-entity-id="R-COST"]';
 await page.$eval(contextRow,row=>row.focus());
 await page.keyboard.down('Shift');await page.keyboard.press('F10');await page.keyboard.up('Shift');
 assert(await page.$('[data-outline-context-menu][role=menu]'),
  'Shift+F10 opens the same keyboard-accessible menu');
 await page.keyboard.press('Escape');
 assert.equal(await page.$eval(contextRow,row=>document.activeElement===row),true,
  'Escape restores keyboard focus to the originating Requirement');
 await page.click(contextRow,{button:'right'});
 await click('Свернуть элементы одного уровня','[data-outline-context-menu]');
 assert.equal(await page.$$eval('[data-outline-context-menu]',nodes=>nodes.length),0,
  'context action disposes its menu after changing only the view');
 const collapsedType=await page.$eval('.rdg-outline-row[data-outline-type=section][data-outline-section=requirements]',n=>({
  key:n.dataset.outlineKey,expanded:n.getAttribute('aria-expanded'),name:n.querySelector('.rdg-outline-title').textContent,
  detail:n.querySelector('.rdg-outline-meta')?.textContent
 }));
 assert.equal(collapsedType.key,bareGroup.key,'collapsed envelope retains the exact group identity');
 assert.equal(collapsedType.expanded,'false');
 assert(collapsedType.name==='Обязательные требования'&&collapsedType.detail.includes('элементов'));
 // Use actual browser-computed CSS: every synthetic collapsed type group
 // is darker than its corresponding real entity, preserves the left accent,
 // and retains the dashed envelope distinguishing it from real blocks.
 const collapsedTypePalette=await page.evaluate(()=>{
  const root=document.querySelector('.rdg-decision');
  const colors=['requirements','decisions','actions','context','info','evidence','groups'];
  const kinds={requirements:'requirement',decisions:'decision',actions:'action',
   context:'context',info:'info',evidence:'evidence',groups:null};
  const channels=color=>[...color.matchAll(/[0-9]+/g)].map(m=>Number(m[0])).slice(0,3);
  const read=element=>{
   const style=getComputedStyle(element),kind=element.querySelector('.rdg-outline-kind');
   return {background:channels(style.backgroundColor),accent:channels(style.borderLeftColor),
    dashed:style.borderTopStyle==='dashed',borderWidth:parseFloat(style.borderLeftWidth),
    label:kind?getComputedStyle(kind).color:null};
  };
  const rows=[];
  for(const name of colors){
   const collapsed=document.createElement('div');
   collapsed.className='rdg-outline-row';collapsed.dataset.outlineType='section';
   collapsed.dataset.outlineSection=name;collapsed.setAttribute('aria-expanded','false');
   const icon=document.createElement('span');icon.className='rdg-outline-kind';collapsed.append(icon);
   const real=document.createElement('div');real.className='rdg-outline-row';
   if(kinds[name])real.dataset.kind=kinds[name];else real.dataset.outlineType='group';
   root.append(real,collapsed);
   rows.push({name,real:read(real),collapsed:read(collapsed)});
   real.remove();collapsed.remove();
  }
  const parents=document.createElement('div');
  parents.className='rdg-outline-row';parents.dataset.outlineType='section';
  parents.dataset.outlineSection='parents';parents.setAttribute('aria-expanded','false');
  root.append(parents);const parent=read(parents);parents.remove();
  return {rows,parent};
 });
 for(const {name,real,collapsed} of collapsedTypePalette.rows){
  assert(collapsed.dashed&&collapsed.borderWidth>=3,name+' retains the collapsed group envelope');
  assert.deepEqual(collapsed.accent,real.accent,name+' uses the actual block accent color');
  assert(collapsed.background.every((component,i)=>component<=real.background[i]) &&
   collapsed.background.some((component,i)=>component<real.background[i]),
   name+' has a darker background in the same color family as the actual type');
 }
 assert.deepEqual(collapsedTypePalette.parent.background,[23,44,64],
  'the special Parents section retains its pre-existing neutral collapsed color');
 assert.deepEqual(collapsedTypePalette.parent.accent,[79,108,130],
  'the Parents section is not recolored to a Requirement, Decision or Action type');
 assert(await page.$$eval('.rdg-outline-row[data-outline-type=entity][data-kind=requirement]',n=>n.length)<groupCountsBefore,
  'collapsed section replaces its real sibling rows');
 await page.screenshot({path:path.join(base,'structure-type-envelope-collapsed.png'),fullPage:true});
 await page.$eval('.rdg-outline-row[data-outline-type=section][data-outline-section=requirements] [data-outline-toggle]',n=>n.click());
 await idle();
 assert.equal(await page.$$eval('.rdg-outline-row[data-outline-type=entity][data-kind=requirement]',n=>n.length),
  groupCountsBefore,'reopening the section restores the original real Requirement rows');
 assert.equal(await page.$$eval('.rdg-outline-row[data-outline-type=section][data-outline-section=requirements]',n=>n.length),0);
 assert.equal(await page.$$eval('.rdg-outline-section-toggle',nodes=>nodes.length),0,
  'reopening the type section never restores protruding group-collapse triangles');
 assert.equal(await page.$$eval('.rdg-outline-row[data-section-context=requirements][data-section-context-key="'+bareGroup.key+'"]',nodes=>nodes.length),2,
  'any restored sibling can request the next collapse via its own context menu');
 await page.screenshot({path:path.join(base,'structure-flat-groups-expanded.png'),fullPage:true});
 assert.deepEqual(await page.$$eval('.rdg-outline-row[data-outline-type=entity][data-kind=decision] .rdg-outline-kind',
   nodes=>[...new Set(nodes.map(n=>n.textContent))]),['D']);
 assert.deepEqual(await page.$$eval('.rdg-outline-row[data-outline-type=entity][data-kind=requirement] .rdg-outline-kind',
   nodes=>[...new Set(nodes.map(n=>n.textContent))]),['R']);
 assert.equal(await page.$$eval('.rdg-outline-row[data-outline-type=group]',n=>n.length),0,
   'Structure groups are frames around Decisions, not separate DG rows');
 const sectionCodes=await page.$$eval('.rdg-outline-row[data-outline-type=section] .rdg-outline-kind',
   a=>a.map(n=>n.textContent));
 assert(sectionCodes.every(code=>['R','D','DG','Act','Ctx','Inf','Ev'].includes(code)),
   'tree sections must use letter labels, not decorative icons');
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="CANON-STORE"]',n=>n.length),0,
   'Canon is not represented as a structure row');
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="R-POST"]',n=>n.length),2,
   'one Requirement repeats as a direct child and as Decision child');
 const groupTags=await page.$$eval('.rdg-outline-group-caption[data-group-id="G-CHOICE"]',nodes=>
  nodes.map(n=>{const row=n.closest('.rdg-outline-row'),strip=n.parentElement,
   card=row.querySelector('.rdg-outline-decision-content'),prev=row.previousElementSibling;
   return {caption:n.textContent,color:getComputedStyle(n).borderTopColor,
    textColor:getComputedStyle(n).color,fill:getComputedStyle(n).backgroundColor,
    decision:row.dataset.entityId,hasTitle:n.hasAttribute('title'),
    decisionFill:getComputedStyle(card).backgroundColor,
    decisionBorder:getComputedStyle(card).borderLeftColor,
    rowFill:getComputedStyle(row).backgroundColor,
    tagGap:Math.round(card.getBoundingClientRect().top-strip.getBoundingClientRect().bottom),
    precedingGap:prev?Math.round(row.getBoundingClientRect().top-prev.getBoundingClientRect().bottom):null};}));
 assert(groupTags.length>=2,'each visible group Decision has one property chip');
 assert(groupTags.every(n=>n.caption==='Взаимоисключающие · Выбрать ≥1'&&!n.hasTitle),
  'chips display choice rules only, without group names, IDs, parents, other decisions or tooltips');
 assert(groupTags.every(n=>n.decisionFill==='rgb(61, 57, 48)'&&n.decisionBorder==='rgb(214, 183, 126)'&&n.rowFill==='rgba(0, 0, 0, 0)'),
  'group property chips do not recolor the original Decision background and border');
 assert(groupTags.every(n=>n.tagGap===4&&n.precedingGap>n.tagGap),
  'property chips sit 4px above Decision, closer than the preceding structural row');
 assert(groupTags.every(n=>n.color===n.textColor&&n.fill!==n.decisionFill),
  'chips use muted property-color text and borders with their own subtle fill');
 assert.equal(new Set(groupTags.map(n=>n.color)).size,1,'one group color is stable across Decisions');
 assert(groupTags.some(n=>n.decision==='D-ALT')&&groupTags.some(n=>n.decision==='D-STORE'));
 // Every Structure row ends at the same right edge of the view; the only
 // depth offset is its external left margin. Group chips are above the card.
 const groupGeometry=await page.$$eval('.rdg-outline-row[data-kind=decision][data-group-tags=true]',nodes=>
  nodes.map(row=>{const card=row.querySelector('.rdg-outline-decision-content'),tags=row.querySelector('.rdg-outline-group-tags');
   const r=row.getBoundingClientRect(),c=card.getBoundingClientRect(),t=tags.getBoundingClientRect();
   return {left:r.left,right:r.right,cardLeft:c.left,cardRight:c.right,
    tagLeft:t.left,tagRight:t.right,treeRight:row.parentElement.getBoundingClientRect().right,
    rowWidth:r.width,cardWidth:c.width,depth:Number(row.style.getPropertyValue('--outline-depth'))};}));
 assert(groupGeometry.length>=2,'two grouped Decisions are visible');
 assert(groupGeometry.every(g=>Math.abs(g.right-g.treeRight)<=2&&
  Math.abs(g.cardRight-g.treeRight)<=3),
  'all grouped Decisions must fill their entire available width to the right: '+JSON.stringify(groupGeometry));
 assert(groupGeometry.every(g=>g.cardLeft>=g.left&&g.cardLeft-g.left<=4&&
  Math.abs(g.tagLeft-g.cardLeft)<3&&g.tagRight<=g.right+1),
  'group tags and Decision card share the same left depth margin: '+JSON.stringify(groupGeometry));
 const groupedControls=await page.$$eval('.rdg-outline-row[data-kind=decision][data-group-tags=true]',rows=>
  rows.map(row=>{const card=row.querySelector('.rdg-outline-decision-content'),
    disclosure=row.querySelector('[data-outline-toggle]'),kind=card.querySelector('.rdg-outline-kind');
   const rect=n=>n.getBoundingClientRect();
   return {id:row.dataset.entityId,hasDisclosure:!!disclosure,
    disclosureInside:disclosure?.parentElement===card,
    disclosureLeft:disclosure?rect(disclosure).left:null,
    disclosureRight:disclosure?rect(disclosure).right:null,
    cardLeft:rect(card).left,kindLeft:rect(kind).left,
    outsideControls:row.querySelectorAll('.rdg-outline-section-toggle').length};}));
 assert(groupedControls.every(g=>g.outsideControls===0),
  'Decision Groups have no protruding same-level collapse controls');
 assert(groupedControls.filter(g=>g.hasDisclosure).every(g=>g.disclosureInside&&
  g.disclosureLeft>=g.cardLeft&&g.disclosureRight<=g.kindLeft),
  'Decision child disclosure stays inside its own amber card');
 // Collapse a Decision group by RIGHT-CLICKING the second option, not the first.
 const optionRow='.rdg-outline-row[data-section-context=decisions][data-entity-id="D-ALT"]';
 assert(await page.$(optionRow),'later Decision sibling exposes a context menu action');
 await page.click(optionRow,{button:'right'});
 assert((await page.$eval('[data-outline-context-menu]',n=>n.textContent)).includes('Свернуть элементы одного уровня'));
 await click('Свернуть элементы одного уровня','[data-outline-context-menu]');
 assert(await page.$('.rdg-outline-row[data-outline-type=section][data-outline-section=decisions]'),
  'right click on a later Decision replaces that type group with a collapsed envelope');
 await page.click('.rdg-outline-row[data-outline-type=section][data-outline-section=decisions]',{button:'right'});
 assert((await page.$eval('[data-outline-context-menu]',n=>n.textContent)).includes('Развернуть элементы одного уровня'));
 await click('Развернуть элементы одного уровня','[data-outline-context-menu]');
 assert(await page.$(optionRow),'the same real Decision options are restored');
 const groupColorBeforeOverlap=groupTags[0].color;
 assert((await page.$eval('.rdg-outline-row[data-entity-id="D-STORE"] .rdg-outline-meta',n=>n.textContent)).includes('Несколько родителей'));
 await page.$eval('.rdg-outline-head input[type=search]',n=>{n.value='SQLite';});
 await click('Найти','.rdg-outline-head');
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="D-ALT"]',n=>n.length),1);
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="D-STORE"]',n=>n.length),0);
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="R-CHOICE"]',n=>n.length),1,
   'search keeps the matching Decision parent path');
 await click('Сбросить','.rdg-outline-head');
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="D-STORE"]',n=>n.length),2);
 // Structure draws no vertical/horizontal tree connectors at any depth.
 // All R/D/Act cards are physically indented 24px per nesting level,
 // not merely padded inside full-width invisible row hitboxes.
 const indentGeometry=await page.evaluate(()=>{
  const tree=document.querySelector('.rdg-outline-tree'),rows=[...tree.querySelectorAll('.rdg-outline-row')];
  const rect=n=>n.getBoundingClientRect();
  return {treeWidth:rect(tree).width,
   decorativeLines:tree.querySelectorAll('.rdg-outline-sibling-guide, [data-guide-depth]').length,
   rows:rows.map(row=>({id:row.dataset.entityId||row.dataset.outlineSection||'',
     depth:Number(row.style.getPropertyValue('--outline-depth')),left:rect(row).left,
     right:rect(row).right,width:rect(row).width,
     paddingLeft:parseFloat(getComputedStyle(row).paddingLeft),
     kind:row.dataset.kind,type:row.dataset.outlineType,
     parentRef:row.dataset.parentRef==='true',
     treeRight:rect(tree).right,
     groupTags:row.dataset.groupTags==='true'}))};
 });
 assert.equal(indentGeometry.decorativeLines,0,'the entire Structure tree contains no guide lines');
 const physical=indentGeometry.rows.filter(r=>r.type==='entity'&&!r.parentRef);
 assert(physical.some(r=>r.kind==='decision'&&r.groupTags)&&
  physical.some(r=>r.kind==='requirement'&&r.depth>=2));
 const rootLeft=physical.find(r=>r.id==='R1').left;
 assert(physical.every(r=>Math.abs(r.left-(rootLeft+24*r.depth))<=2),
  'every visible R/D/Action uses the same external 24px depth margin: '+JSON.stringify(physical));
 assert(physical.every(r=>r.paddingLeft<=11),
  'nesting must never be represented by invisible left padding inside the hit rectangle');
 assert(physical.every(r=>Math.abs(r.right-r.treeRight)<=2),
  'every R/D/Act row extends to the right edge; only the left side is indented: '+JSON.stringify(physical));
 // Deep paths keep a readable 420px row, overrun the visible pane to the
 // right, and expose horizontal scroll. Use only a temporary DOM depth style:
 // the original view state and Graph are not changed.
 const deep=await page.evaluate(()=>{
  const pane=document.querySelector('.rdg-outline-scroll');
  const row=document.querySelector('.rdg-outline-row[data-entity-id="R-COST"]');
  const original=row.style.getPropertyValue('--outline-depth');
  row.style.setProperty('--outline-depth','28');
  return {original,clientWidth:pane.clientWidth,scrollWidth:pane.scrollWidth,
   rowWidth:row.getBoundingClientRect().width,rowLeft:row.getBoundingClientRect().left,
   paneLeft:pane.getBoundingClientRect().left};
 });
 assert(deep.rowWidth>=419&&deep.scrollWidth>deep.clientWidth+200,
  'deep nested cards preserve minimum width and extend beyond visible right edge: '+JSON.stringify(deep));
 await page.mouse.move(165,350);
 const beforeHorizontal=await page.$eval('.rdg-outline-scroll',n=>({left:n.scrollLeft,top:n.scrollTop}));
 await page.keyboard.down('Shift');await page.mouse.wheel({deltaY:260});await page.keyboard.up('Shift');
 await page.waitForFunction(()=>document.querySelector('.rdg-outline-scroll').scrollLeft>0);
 const afterHorizontal=await page.$eval('.rdg-outline-scroll',n=>({left:n.scrollLeft,top:n.scrollTop}));
 assert(afterHorizontal.left>beforeHorizontal.left&&afterHorizontal.top===beforeHorizontal.top,
  'Shift+wheel horizontally scrolls Structure without moving its vertical position');
 await page.keyboard.down('Shift');await page.mouse.wheel({deltaY:-260});await page.keyboard.up('Shift');
 await page.evaluate(original=>{
  const row=document.querySelector('.rdg-outline-row[data-entity-id="R-COST"]');
  row.style.setProperty('--outline-depth',original);
  document.querySelector('.rdg-outline-scroll').scrollLeft=0;
 },deep.original);
 await page.screenshot({path:path.join(base,'structure-indented-cards-no-lines.png'),fullPage:true});
 // Collapse and reopen a nested branch; its direct children disappear and
 // return without connectors, while the remaining rows preserve their depth.
 const branchToggle=await page.$('.rdg-outline-row[data-entity-id="R-CHOICE"][aria-expanded="true"] [data-outline-toggle]');
 assert(branchToggle,'separated siblings still retain a working disclosure');
 await branchToggle.click();await idle();
 assert.equal(await page.$$eval('.rdg-outline-sibling-guide',nodes=>nodes.length),0);
 await page.$eval('.rdg-outline-row[data-entity-id="R-CHOICE"] [data-outline-toggle]',n=>n.click());await idle();
 assert.equal(await page.$$eval('.rdg-outline-sibling-guide',nodes=>nodes.length),0);
 const expandedPathsBefore=await page.$$eval('.rdg-outline-row[data-entity-id="D-STORE"]',nodes=>nodes.map(n=>({key:n.dataset.outlineKey,expanded:n.getAttribute('aria-expanded')})));
 assert.deepEqual(expandedPathsBefore.map(n=>n.expanded).sort(),['false','true'],
   'one occurrence begins expanded, the other collapsed');
 const unexpanded=await page.$('.rdg-outline-row[data-entity-id="D-STORE"][aria-expanded="false"] [data-outline-toggle]');
 assert(unexpanded,'second occurrence must be independently expandable');await unexpanded.click();await idle();
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="R-POST"]',n=>n.length),3,
   'expanding an occurrence reveals the same child identity a third time');
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="D-STORE"][aria-expanded="true"]',n=>n.length),2);
 const firstOpen=await page.$('.rdg-outline-row[data-entity-id="D-STORE"][aria-expanded="true"] [data-outline-toggle]');
 await firstOpen.click();await idle();
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="D-STORE"][aria-expanded="true"]',n=>n.length),1,
   'one branch can close while the other remains open');
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="R-POST"]',n=>n.length),2);
 await page.$eval('.rdg-outline-row[data-entity-id="D-STORE"] .rdg-outline-group-caption[data-group-id="G-CHOICE"]',n=>n.click());await idle();
 assert((await page.$eval('.rdg-inspector',n=>n.textContent)).includes('Выбор технологии'));
 assert(await page.$('.rdg-outline-group-caption[data-group-id="G-CHOICE"]'),
  'real Decision memberships remain visible as colored chips when type sections are flattened');
 await page.screenshot({path:path.join(base,'decision-structure-outline.png'),fullPage:true});
 await click('Фокус: Использовать PostgreSQL','.rdg-outline-scroll');
 assert.equal((await state()).view.spec.kind,'focus');
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="D-STORE"]',n=>n.length),1,
   'focused Decision is the single structural root, not copied under each parent');
 assert.equal(await page.$$eval('.rdg-outline-row[data-focus-root=true]',n=>n.length),1);
 const focusedDisclosure=await page.$eval('.rdg-outline-row[data-focus-root=true][data-group-tags=true]',row=>{
  const disclosure=row.querySelector('[data-outline-toggle]'),card=row.querySelector('.rdg-outline-decision-content');
  const scroller=row.closest('.rdg-outline-scroll');
  const kind=card.querySelector('.rdg-outline-kind');
  return {toggleLeft:disclosure.getBoundingClientRect().left,
   toggleRight:disclosure.getBoundingClientRect().right,
   cardLeft:card.getBoundingClientRect().left,
   kindLeft:kind.getBoundingClientRect().left,
   scrollerLeft:scroller.getBoundingClientRect().left,
   insideCard:disclosure.parentElement===card};
 });
 assert(focusedDisclosure.insideCard&&
  focusedDisclosure.toggleLeft>=focusedDisclosure.cardLeft&&
  focusedDisclosure.toggleRight<=focusedDisclosure.kindLeft&&
  focusedDisclosure.toggleLeft>=focusedDisclosure.scrollerLeft,
  'focused root Decision disclosure stays fully visible INSIDE its card: '+JSON.stringify(focusedDisclosure));
 const focusDecisionParents=await page.$$eval('.rdg-outline-row[data-parent-ref=true]',nodes=>nodes.map(n=>({
  id:n.dataset.entityId,code:n.querySelector('.rdg-outline-kind').textContent,
  expandable:n.hasAttribute('aria-expanded'),text:n.textContent})));
 assert.deepEqual(focusDecisionParents.map(n=>n.code),['Par R','Par R']);
 assert(await page.$('.rdg-outline-row[data-outline-type=section][data-outline-section=parents]'),
  'the special Parents section is retained in focus');
 assert.deepEqual(focusDecisionParents.map(n=>n.id).sort(),['R-CHOICE','R1']);
 assert(focusDecisionParents.every(n=>!n.expandable),'parent references must not copy their descendant subtrees');
 assert(focusDecisionParents.some(n=>n.text.includes('Группа «Выбор технологии»')),
  'the grouped parent remains explicit in the single-parent reference');
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="R-POST"]',n=>n.length),1);
 await page.screenshot({path:path.join(base,'decision-focus-single-parents.png'),fullPage:true});
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'R-POST'}),exampleRow.packageId);await idle();
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="R-POST"]',n=>n.length),1,
  'focused Requirement is also shown only once');
 const focusRequirementParents=await page.$$eval('.rdg-outline-row[data-parent-ref=true]',nodes=>nodes.map(n=>({
  id:n.dataset.entityId,code:n.querySelector('.rdg-outline-kind').textContent
 })));
 assert.deepEqual(focusRequirementParents.sort((a,b)=>a.id.localeCompare(b.id)),[
   {id:'D-STORE',code:'Par D'},{id:'R-CHOICE',code:'Par R'}]);
 assert.equal(await page.$$eval('.rdg-outline-row[data-parent-ref=true][aria-expanded]',n=>n.length),0);
 await page.screenshot({path:path.join(base,'requirement-focus-parent-types.png'),fullPage:true});
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'D-STORE'}),exampleRow.packageId);await idle();
 await click('Граф','.rdg-presentation-modes');
 assert(await page.$('.rdg-graph'),'switch restores original focus graph');
 await click('Структура','.rdg-presentation-modes');
 assert(await page.$('.rdg-outline-tree'),'focus switches back to outline without owner writes');
 await field('Область','WG-OUTLINE','.rdg-tools');
 assert.equal((await state()).view.spec.kind,'workGraph');
 assert.equal((await state()).view.graphKey,graphKey,'Working Graph is still a view of the same process Graph');
 assert.equal((await state()).graph.id,outlineOwner.graph.id);
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="D-STORE"]',n=>n.length),2,
   'same Decision appears through two parents in scoped WorkGraph');
 assert.equal((await state()).graph.workGraphs[0].memberIds.length,7);
 assert.deepEqual((await api({method:'read',packageId:exampleRow.packageId,includePlan:true})).graph,outlineOwner.graph,
   'outline/inspector/focus/workgraph never write graph data');
 await click('Граф','.rdg-presentation-modes');assert(await page.$('.rdg-graph'));
 assert.deepEqual(await page.$$eval('.rdg-decision-group-caption[data-group="G-CHOICE"]',
  a=>a.map(n=>getComputedStyle(n).visibility)),['visible','visible'],
  'Working Graph uses the same real DECISION_MEMBER captions as the full Process Graph');
 checks.push('structure mode: flat R/D/Act rows, custom right-click collapse from any sibling, min-width horizontal scrolling and Shift+wheel, group chips, focus, WorkGraph, no writes');
 // A real overlapping membership fixture: D-STORE belongs to two groups with
 // different peer choices and different rules. Their compact chips must remain
 // distinct without duplicating the canonical Decision or changing its color.
 const overlapRequest=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,command:'decision_group'})).request;
 overlapRequest.note='Browser-only overlapping decision-group visibility';
 overlapRequest.data={group:{id:'G-OVERLAP',parentId:'R-CHOICE',title:'Дополнительный выбор',
  selectionRequired:false,mutuallyExclusive:false,members:[
   {id:'GM-OV-STORE',decisionId:'D-STORE'},{id:'GM-OV-HOST',decisionId:'D-HOST'}]}};
 await writeExample(overlapRequest);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),exampleRow.packageId);await idle();
 await click('Структура','.rdg-presentation-modes');
 const nested=await page.$$eval('.rdg-outline-row[data-entity-id="D-STORE"]',nodes=>nodes.map(row=>({
  chips:[...row.querySelectorAll('.rdg-outline-group-caption')].map(n=>({
   id:n.dataset.groupId,label:n.textContent,
   border:getComputedStyle(n).borderTopColor,fill:getComputedStyle(n).backgroundColor,
   text:getComputedStyle(n).color,tooltip:n.hasAttribute('title')})),
  decisionFill:getComputedStyle(row.querySelector('.rdg-outline-decision-content')).backgroundColor,
  decisionTypeBorder:getComputedStyle(row.querySelector('.rdg-outline-decision-content')).borderLeftColor,
  tagGap:Math.round(row.querySelector('.rdg-outline-decision-content').getBoundingClientRect().top-
   row.querySelector('.rdg-outline-group-tags').getBoundingClientRect().bottom)
 })));
 assert.equal(nested.length,2,'multiple groups under one parent do not multiply the Decision occurrence');
 assert(nested.every(row=>row.chips.length===2&&row.chips.some(c=>c.id==='G-CHOICE')&&row.chips.some(c=>c.id==='G-OVERLAP')));
 assert(nested.every(row=>new Set(row.chips.map(c=>c.border)).size===2),
  'overlapping groups get different muted palette colors');
 assert(nested.every(row=>row.chips.every(c=>c.border===c.text&&!c.tooltip&&c.fill!=='rgba(0, 0, 0, 0)')),
  'chips use tinted backgrounds and colored borders, without supplementary tooltips');
 assert(nested.every(row=>row.decisionFill==='rgb(61, 57, 48)'&&row.decisionTypeBorder==='rgb(214, 183, 126)'&&row.tagGap===4),
  'Decision keeps its own amber background and border, just 4px below group chips');
 assert(nested.every(row=>row.chips.some(c=>c.id==='G-CHOICE'&&c.border===groupColorBeforeOverlap)),
  'newly created groups cannot change the existing group color');
 assert(nested.every(row=>row.chips.some(c=>c.label==='Взаимоисключающие · Выбрать ≥1')&&
  row.chips.some(c=>c.label==='Совместный выбор')),
  'optional choice is implied (never displayed as Выбор необязателен)');
 await page.$eval('.rdg-outline-row[data-entity-id="D-STORE"] .rdg-outline-group-caption[data-group-id="G-OVERLAP"]',n=>n.click());await idle();
 assert((await page.$eval('.rdg-inspector',n=>n.textContent)).includes('Дополнительный выбор'));
 await page.screenshot({path:path.join(base,'decision-structure-overlapping-chips.png'),fullPage:true});
 await click('Граф','.rdg-presentation-modes');
 checks.push('overlapping Decision Groups: two short colored property chips, optional choice omitted, stable 10-color hash palette after creating a group, unchanged amber Decision');
 // History modes affect only the history column; both rename meanings use the public writer.
 await addOutline({id:'H-NAME',kind:'info',title:'Название для истории',description:'Isolated rename fixture',value:'A note'});
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'H-NAME'}),exampleRow.packageId);await idle();
 await click('Сведения','.rdg-tools');
 for(const [title,cosmetic] of [['Уточнённое написание',true],['Изменённый смысл записи',false]]){
  await click('Переименовать блок','.rdg-inspector');await field('Название',title);await field('Без изменения смысла',cosmetic);await field('Основание изменения','Проверка явной семантики переименования');await click('Проверить переименование');await save();
 }
 const renameOwner=await api({method:'read',packageId:exampleRow.packageId,includePlan:true});
 const renameEvents=renameOwner.graph.events.filter(e=>e.historyDetail?.targetIds.includes('H-NAME')&&e.historyDetail.command==='edit');assert.equal(renameEvents.length,2);assert.deepEqual(renameEvents.map(e=>e.historyDetail.cosmetic),[true,false]);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph',historyMode:'important'}),exampleRow.packageId);await idle();
 const historyOwnerBefore=await api({method:'read',packageId:exampleRow.packageId,includePlan:true});
 const levels=await api({method:'history',packageId:exampleRow.packageId});
 for(const mode of ['important','meaningful','technical','all']){
  const planBefore=await page.$eval('[data-road=plan]',n=>n.textContent);await field('События истории',mode,'[data-road=history]');
  const shown=await page.$$eval('[data-road=history] [data-history-level]',rows=>rows.map(n=>n.dataset.historyLevel));
  assert(await page.$eval('[data-road=history] .rdg-road-section',n=>n.scrollWidth<=n.clientWidth+2),'History selector fits the road');
  assert(shown.length);assert(shown.every(l=>mode==='all'||mode==='important'&&l==='important'||mode==='technical'&&l==='technical'||mode==='meaningful'&&l!=='technical'));
  assert.equal(await page.$eval('[data-road=plan]',n=>n.textContent),planBefore);
  for(const event of renameEvents){const level=levels.events.find(r=>r.event.id===event.id).historyView.level;assert.equal(!!await page.$('[data-event-id="'+event.id+'"]'),mode==='all'||mode==='meaningful'&&level!=='technical'||mode==='technical'&&level==='technical'||mode==='important'&&level==='important');}
 }
 const historyOwnerAfter=await api({method:'read',packageId:exampleRow.packageId,includePlan:true});for(const k of ['graph','plan','layouts'])assert.deepEqual(historyOwnerAfter[k],historyOwnerBefore[k]);
 checks.push('Four History modes, explicit cosmetic/semantic rename in UI, no Graph/Plan/layout writes and unchanged Plan display');
 // Real temporary process owner: one work-area creation event with >12 actual
 // members, plus a real initialRelations event to check typed source/target.
 // Nothing from this fixture is written to installed user data.
 for(let i=1;i<=6;i++)await addOutline({id:'H-INFO-'+i,kind:'info',
  title:'Контрольный факт History '+i,
  description:'Изолированный член области для проверки большой карточки',value:'Тест '+i});
 const historyBefore=await api({method:'read',packageId:exampleRow.packageId,includePlan:true});
 const allMemberIds=[...historyBefore.graph.nodes,...historyBefore.graph.objects].map(n=>n.id);
 assert(allMemberIds.length>=16,'real History stress fixture must contain many actual owner entities');
 const historyArea=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,command:'work_graph'})).request;
 historyArea.note='Изолированное событие с большим количеством участников';
 historyArea.data={workGraph:{id:'WG-HISTORY-MANY',title:'Историческая область с многими участниками',
   rootIds:['R1'],memberIds:allMemberIds,colorKey:'teal'}};
 await writeExample(historyArea);
 const historyAfter=await api({method:'read',packageId:exampleRow.packageId,includePlan:true});
 const largeEvent=historyAfter.graph.events.find(e=>e.type==='work_graph_changed'&&
  e.workGraphChange?.workGraphId==='WG-HISTORY-MANY');
 const linkedEvent=historyAfter.graph.events.find(e=>e.type==='linked'&&e.relationIds?.includes('E-D-STORE'));
 const createdHost=historyAfter.graph.events.find(e=>e.type==='created'&&e.operationActionId&&e.relationIds?.includes('E-D-HOST'));
 assert(largeEvent&&linkedEvent&&createdHost,'typed History events must exist in the actual temporary owner');
 assert(createdHost.nodeIds.includes('R1')&&createdHost.nodeIds.includes('D-HOST')&&
   !createdHost.nodeIds.includes('R-COST'),
   'one-hop stale must not invent a distant affected Requirement in the creation event');
 await page.setViewport({width:1440,height:1000});
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),exampleRow.packageId);await idle();
 await field('События истории','all','[data-road=history]');
 const eventSel='[data-event-id="'+largeEvent.id+'"]';
 const linkedSel='[data-event-id="'+linkedEvent.id+'"]';
 const createdSel='[data-event-id="'+createdHost.id+'"]';
 assert(await page.$(createdSel),'the historic created event must be visible');
 assert.equal(await page.$eval(createdSel,n=>n.dataset.createdId),'D-HOST');
 assert((await page.$eval(createdSel+' .rdg-road-card',n=>n.textContent)).includes('Создано решение'));
 assert((await page.$eval(createdSel+' .rdg-road-card',n=>n.textContent)).includes('Размещать сервис на своём сервере'));
 assert((await page.$eval(createdSel+' .rdg-road-side-left',n=>n.textContent)).includes('Родители при создании'));
 assert((await page.$eval(createdSel+' .rdg-road-side-left',n=>n.textContent)).includes('Пример процесса'));
 assert(!(await page.$eval(createdSel,n=>n.textContent)).includes('Не увеличивать стоимость поддержки'),
  'unrelated sibling Requirement must not be shown as affected by creating a new Decision');
 assert.equal(await page.$$eval(createdSel+' [data-road-node-id]',a=>a.length),1,
  'the created Decision and the technical discovery Action are not misleading side participants');
 assert.equal(await page.$eval(createdSel+' .rdg-road-technical',n=>n.open),false);
 assert((await page.$eval(createdSel+' .rdg-road-technical',n=>n.textContent)).includes('discover_decision'));
 assert((await page.$eval(createdSel+' .rdg-road-event-relation',n=>n.textContent)).includes('DRIVES'));
 assert(await page.$(eventSel),'work-area creation appears in History');
 assert(await page.$(linkedSel),'initial relation appears as linked History');
 assert((await page.$eval(linkedSel+' .rdg-road-card',n=>n.textContent)).includes('DRIVES'));
 assert((await page.$eval(linkedSel+' .rdg-road-side-left',n=>n.textContent)).includes('Пример процесса'));
 assert((await page.$eval(linkedSel+' .rdg-road-side-right',n=>n.textContent)).includes('Использовать PostgreSQL'));
 assert(!(await page.$eval(linkedSel,n=>n.textContent)).includes('Затронутые блоки'),
  'the old generic side label has been replaced by typed endpoint roles');
 const initialLarge=await page.$eval(eventSel,n=>({
  visible:n.querySelectorAll('.rdg-road-side-left [data-road-node-id]').length,
  more:!!n.querySelector('[data-road-show-more]'),
  height:n.getBoundingClientRect().height
 }));
 assert.equal(initialLarge.visible,12);
 assert(initialLarge.more,'many affected members must not silently disappear after the fourth');
 await page.$eval(eventSel+' [data-road-show-more]',n=>n.click());await idle();
 const geometry=await page.$eval(eventSel,n=>{
  const box=e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,height:r.height}};
  const row=box(n),card=box(n.querySelector('.rdg-road-card'));
  const left=box(n.querySelector('.rdg-road-side-left'));
  const next=n.nextElementSibling?.classList.contains('rdg-road-row')?box(n.nextElementSibling):null;
  return {row,card,left,next,count:n.querySelectorAll('.rdg-road-side-left [data-road-node-id]').length,
   more:!!n.querySelector('[data-road-show-more]'),scrollWidth:n.scrollWidth,clientWidth:n.clientWidth};
 });
 assert.equal(geometry.count,allMemberIds.length,'every one of the actual affected entities is visible');
 assert(!geometry.more);
 assert(geometry.row.height>initialLarge.height,'expanding the side list increases the entire History capsule');
 assert(geometry.row.bottom>=geometry.left.bottom-1,'capsule contains the complete side list');
 assert(geometry.row.bottom>=geometry.card.bottom-1,'capsule contains the central event block');
 assert(geometry.scrollWidth<=geometry.clientWidth+2,'no horizontal overflow inside a large History capsule');
 if(geometry.next)assert(geometry.next.top>=geometry.row.bottom-1,'next event must not overlap expanded capsule');
 await page.$eval(eventSel,n=>n.scrollIntoView({block:'center'}));
 await page.screenshot({path:path.join(base,'history-many-affected-roles.png'),fullPage:true});
 // The road is resizable; narrow width must stack roles below the central
 // fact without losing any entity or making the document horizontally scroll.
 await page.$eval('.rdg-road',n=>n.style.width='330px');await idle();
 const narrow=await page.$eval(eventSel,n=>{
  const row=n.getBoundingClientRect(),card=n.querySelector('.rdg-road-card').getBoundingClientRect();
  const side=n.querySelector('.rdg-road-side-left').getBoundingClientRect();
  return {rowWidth:row.width,clientWidth:n.clientWidth,scrollWidth:n.scrollWidth,
   cardTop:card.top,cardBottom:card.bottom,sideTop:side.top,sideBottom:side.bottom,rowBottom:row.bottom};
 });
 assert(narrow.sideTop>=narrow.cardBottom-2,'narrow road puts related blocks below the event');
 assert(narrow.rowBottom>=narrow.sideBottom-1,'narrow capsule contains all related blocks');
 assert(narrow.scrollWidth<=narrow.clientWidth+2,'narrow History capsule does not overflow');
 await page.$eval('.rdg-road',n=>n.style.width='470px');
 assert.deepEqual((await api({method:'read',packageId:exampleRow.packageId,includePlan:true})).graph,
  historyAfter.graph,'history inspection and expansion must never edit owner Graph');
 checks.push('History roles from real relation IDs, >12 real members, expandable full-width event capsule, narrow adaptive layout and read-only inspection');
 // End-to-end native stale flow on the disposable Process Graph owner:
 // create a subscriber through Application API, clear its initial review,
 // change the source, inspect exact L1 cause, then explicitly review it again.
 const subscribedNode='R-STALE-UI';
 const subscriber=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,command:'add'})).request;
 subscriber.note='Isolated subscriber to a real source Requirement';
 subscriber.data={entity:{id:subscribedNode,kind:'requirement',title:'Проверить актуальность архитектуры',
   description:'Revalidate when source changes',scope:'Test dependency'},location:'graph'};
 await writeExample(subscriber);
 const dep=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,command:'link'})).request;
 dep.note='Create real L1 subscription for UI acceptance';
 dep.data={relation:{id:'DEP-STALE-UI',type:'DEPENDS_ON',from:'R-COST',to:subscribedNode,dependencyLevel:'L1'}};
 await writeExample(dep);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),exampleRow.packageId);await idle();
 await click('Зависимости','.rdg-tools');await idle();
 assert(await page.$('[data-dependency-workspace]'),'full-width dependencies workspace');
 assert.equal(await page.$('.rdg-road[data-detail]'),null,'timeline is not rendered in the dependencies workspace');
 assert.equal(await page.$$eval('[data-dependency-tab]',nodes=>nodes.length),2,'exactly two dependency tabs');
 assert(await page.$('[data-stale-node-id="R-STALE-UI"]'),'subscribed node requires initial review after link');
 const verifyStale=async basis=>{
  await page.$eval('[data-review-node-id="R-STALE-UI"]',n=>n.click());await idle();
  await field('Основание / наблюдение',basis);
  await click('Проверить действие','.rdg-modal');await save();
  const current=(await api({method:'read',packageId:exampleRow.packageId})).graph;
  assert.equal(current.nodes.find(n=>n.id===subscribedNode).review.required,false,
    'only actual review with observed pins clears the persisted stale flag');
  assert.equal(await page.$('[data-stale-node-id="R-STALE-UI"]'),null,
    'reviewed subscriber leaves the active stale list immediately after readback');
 };
 await verifyStale('Checked subscription and its current L1 inputs');
 const editSource=async(changes,cosmetic)=>{
  const edit=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,nodeId:'R-COST',command:'edit'})).request;
  edit.note='Synthetic semantic stale source change';
  edit.data={nodeId:'R-COST',changes,cosmetic};return writeExample(edit);
 };
 await editSource({title:'Издержки сопровождения (оформление)'},true);
 const cosmeticGraph=(await api({method:'read',packageId:exampleRow.packageId})).graph;
 assert.equal(cosmeticGraph.nodes.find(n=>n.id===subscribedNode).review.required,false,
  'explicit cosmetic title change does not invalidate L1 subscriber');
 await editSource({description:'Бюджет изменился: стоимость сопровождения должна быть ниже'},false);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),exampleRow.packageId);await idle();
 const staleGraph=(await api({method:'read',packageId:exampleRow.packageId})).graph;
 const staleItem=staleGraph.nodes.find(n=>n.id===subscribedNode);
 assert(staleItem.review.required,'semantic source change persists stale in graph owner');
 const change=staleGraph.events.find(e=>e.id===staleItem.review.causeEventIds.at(-1));
 assert.deepEqual(change.dependencyImpacts.filter(e=>e.dependentId===subscribedNode),[{
  edgeId:'DEP-STALE-UI',sourceId:'R-COST',dependentId:subscribedNode,
  level:'L1',changedParts:['definition']}]);
 await click('Зависимости','.rdg-tools');await idle();
 const reviewCard=await page.$eval('[data-stale-node-id="R-STALE-UI"]',n=>({
  text:n.textContent,causes:[...n.querySelectorAll('.rdg-stale-reason')].map(c=>c.dataset.causeEventId),
  actions:n.querySelectorAll('.rdg-policy-actions button').length
 }));
 assert(reviewCard.text.includes('Издержки сопровождения (оформление)')&&
  reviewCard.text.includes('L1')&&reviewCard.text.includes('содержание элемента'),
  'full-screen stale workspace identifies actual source, L1 rule and changed semantic part');
 assert(reviewCard.causes.includes(change.id));
 assert(reviewCard.actions>=2,'open entity and confirm review are independent actions');
 await page.screenshot({path:path.join(base,'decision-stale-dependencies-panel.png'),fullPage:true});
 await click('Политики','.rdg-policy-tabs');
 assert(await page.$('[data-policy-id="builtin:L1"]'),'built-in policy and usage are visible in catalog');
 await page.$eval('[data-dependency-tab=stale]',n=>n.click());await idle();
 assert(await page.$('[data-stale-node-id="R-STALE-UI"]'));
 await verifyStale('Reviewed changed budget requirement and confirmed subscription remains usable');
 await click('← К графу','.rdg-policy-header');
 assert(await page.$('.rdg-road[data-detail]'),'Plan/History remains separate from full-screen dependencies');
 checks.push('native stale: exact L1 cause -> full-screen workspace, system policy catalogue and pinned review; cosmetic no-hit');
 // New configurable dependency editor: convert an actual old Context ref in
 // the same owner transaction (no duplicate Graph context source), choose L2,
 // change the source and acknowledge the resulting review in the right panel.
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'D-STORE'}),exampleRow.packageId);await idle();
 await page.$eval('[data-entity-id="D-STORE"]',n=>n.dispatchEvent(new MouseEvent('click',{bubbles:true})));await idle();
 await click('Контекст принятия решения','.rdg-inspector-tabs');
 assert(await page.$('[data-legacy-dependency-id="C-HOST"]'),
  'old decisionContextIds is shown as an explicitly configurable legacy L1 subscription');
 await click('Настроить','[data-legacy-dependency-id="C-HOST"]');
 assert(await page.$('[data-dependency-rule-editor]'),'context editor uses ordinary Application form');
 let heldDraftRequest;let reportHeldDraft;const draftHeld=new Promise(resolve=>reportHeldDraft=resolve);
 await page.setRequestInterception(true);
 const holdDraft=req=>{let body;try{body=JSON.parse(req.postData()||'{}');}catch{}
  const draft=body?.value?.screens?.find(s=>s.id===body.value.activeScreenId)?.draft?.form;
  if(!heldDraftRequest&&body?.method==='view_session'&&body.action==='update'&&draft?.mode==='dependencyRule'&&draft.preset==='L2'){
   heldDraftRequest=req;reportHeldDraft();return;
  }void req.continue();};
 page.on('request',holdDraft);
 await field('Базовое наблюдение','L2');
 await Promise.race([draftHeld,new Promise((_,reject)=>setTimeout(()=>reject(Error('No background draft update captured')),5000))]);
 await field('Основание изменения','Explicitly convert existing fact to watched L2');
 await heldDraftRequest.continue();
 await click('Проверить зависимость','.rdg-modal');await save();
 page.off('request',holdDraft);await page.setRequestInterception(false);
 const converted=(await api({method:'read',packageId:exampleRow.packageId})).graph;
 const convertedDecision=converted.nodes.find(n=>n.id==='D-STORE');
 assert(!convertedDecision.decisionContextIds.includes('C-HOST'),
  'old context reference converted without duplicating the source');
 assert.equal(converted.events.at(-1).basis,'Explicitly convert existing fact to watched L2','typing during an in-flight draft update preserves both the choice and later text');
 const configured=converted.edges.find(e=>e.type==='DEPENDS_ON'&&e.from==='C-HOST'&&
  e.to==='D-STORE'&&e.dependencyPurpose==='decisionContext');
 assert(configured&&configured.dependencyRule.preset==='L2'&&
  configured.dependencyRule.watch.includes('directScope'),'editable preset persisted in Graph owner: '+JSON.stringify({configured,allContextEdges:converted.edges.filter(e=>e.type==='DEPENDS_ON'),legacyIds:convertedDecision.decisionContextIds}));
 const editableContext=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,
  nodeId:'C-HOST',command:'edit'})).request;
 editableContext.note='Changed a concrete process fact, not Decision presentation';
 editableContext.data={nodeId:'C-HOST',changes:{value:'Новый факт: сервер недостаточно производителен'},cosmetic:false};
 await writeExample(editableContext);
 const ruleState=(await api({method:'read',packageId:exampleRow.packageId})).graph;
 const contextHit=ruleState.events.at(-1).dependencyImpacts.find(r=>r.edgeId===configured.id&&r.dependentId==='D-STORE');
 assert(contextHit&&contextHit.changedParts.includes('definition'),
  'changing the configured Context causes an exact explicit stale hit');
 assert(ruleState.nodes.find(n=>n.id==='D-STORE').review.required);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),exampleRow.packageId);await idle();
 await click('Зависимости','.rdg-tools');await idle();
 assert((await page.$eval('[data-stale-node-id="D-STORE"]',n=>n.textContent)).includes('На сервере уже работает PostgreSQL'),
  'full-screen stale list explains the real changed Context source');
 await page.screenshot({path:path.join(base,'decision-custom-context-rule-stale.png'),fullPage:true});
 await page.$eval('[data-review-node-id="D-STORE"]',n=>n.click());await idle();
 await field('Основание / наблюдение','Reviewed new process conditions and PostgreSQL suitability');
 await click('Проверить действие','.rdg-modal');await save();
 const confirmed=(await api({method:'read',packageId:exampleRow.packageId})).graph;
 assert.equal(confirmed.nodes.find(n=>n.id==='D-STORE').review.required,false,
  'explicit pinned review clears only the verified stale decision');
 assert.equal(await page.$('[data-stale-node-id="D-STORE"]'),null);
 await click('← К графу','.rdg-policy-header');
 checks.push('configurable Decision context: in-flight draft update preserves L2 and later text; legacy ref converted atomically to L2, content change -> exact stale cause -> UI review clears; no duplicate reference');

 // Real policy catalog mutation flow through native UI forms -> core writer.
 // Every assertion reads the disposable process owner; no invented UI-only
 // preset, binding or stale explanation is accepted as a success.
 await click('Зависимости','.rdg-tools');await click('Политики','.rdg-policy-tabs');
 assert(await page.$('[data-dependency-panel=policies]'));
 assert.equal(await page.$$eval('.rdg-policy-nav button',ns=>ns.filter(n=>n.textContent.includes('Пресет')).length),0,'no separate preset entity in catalog');
 const helpCatalog=(await api({method:'read',packageId:exampleRow.packageId})).dependencyCatalog;
 for(const system of helpCatalog.systemPolicies){
  await page.$eval('[data-policy-id="'+system.id+'"]',n=>n.click());await idle();
  const explanation=await page.$eval('[data-policy-explanation]',n=>n.textContent);
  const expected=helpCatalog.capabilities.policyHelp[system.id];
  for(const key of ['applicability','observes','example'])assert(explanation.includes(expected[key]),system.id+' explains '+key);
  assert(explanation.includes('Активировать снова'),'applicability loss and explicit activation explained');
  if(system.automatic)assert(!(await page.$eval('.rdg-policy-schema',n=>n.textContent)).includes('Конкретный элемент выбирается'),
   'automatic participants are not described as a manual choice');
  for(const rule of system.rules){const card=await page.$eval('[data-rule-id="'+rule.id+'"]',n=>n.textContent);
   assert(card.includes('Наблюдаемый участник:')&&card.includes('Когда срабатывает:'),'rule explains participant and trigger');}
 }
 let policyGraph;
 await click('+ Новая политика','.rdg-policy-nav');
 const dictionary=await page.$eval('[data-policy-dictionary]',n=>n.textContent);
 for(const entry of [...helpCatalog.capabilities.relations,...helpCatalog.capabilities.observations,...helpCatalog.capabilities.eventDescriptions]){
  assert(dictionary.includes(entry.name)&&dictionary.includes(entry.description),'dictionary describes '+entry.id);
  if(entry.example)assert(dictionary.includes(entry.example),'dictionary gives example for '+entry.id);
 }
 const chosenObservation=await page.$eval('[data-policy-rule-index="0"]',n=>n.textContent);
 assert(chosenObservation.includes(helpCatalog.capabilities.observations.find(o=>o.id==='definition').description),
  'selected observation explains exact content directly in editor');
 await page.screenshot({path:path.join(base,'dependency-policy-descriptions-editor.png'),fullPage:true});
 await field('Название политики','Изменился процессный контекст');
 await field('Описание','Содержание источника изменилось; повторно оценить зависимый блок.');
 await field('Название условия (можно оставить предложенное)','Контекст изменён');
 await click('Проверить и сохранить политику','.rdg-modal');await save();
 policyGraph=(await api({method:'read',packageId:exampleRow.packageId})).graph;
 const policy=policyGraph.dependencyPolicies.find(p=>p.name==='Изменился процессный контекст');
 assert(policy&&policy.version===1&&policy.rules[0].name==='Контекст изменён',
  'versioned named policy and named rule persisted through core operation');
 const policyButton='[data-policy-id="'+policy.id+'"]';
 await page.$eval(policyButton,n=>n.click());await idle();
 assert(await page.$('[data-rule-id="'+policy.rules[0].id+'"]'),'policy catalog shows exact saved rule ID');
 await click('+ Применить политику','.rdg-policy-bindings');
 await field('Элемент для пересмотра','R-STALE-UI');
 await field('Источник изменений','C-HOST');
 await click('Проверить и сохранить применение','.rdg-modal');await save();
 policyGraph=(await api({method:'read',packageId:exampleRow.packageId})).graph;
 const binding=policyGraph.dependencyBindings.find(b=>b.policyId===policy.id&&b.targetId===subscribedNode);
 assert(binding&&binding.participantBindings.source==='C-HOST'&&binding.policyVersion===1&&binding.enabled,
  'real binding persisted with actual source/target IDs and pinned policy version');
 assert(await page.$('[data-binding-id="'+binding.id+'"]'),'usage list shows persisted participants');
 assert(!policyGraph.events.at(-1).dependencyImpacts?.some(h=>h.bindingId===binding.id),'registering an application does not fabricate a stale observation');
 const updateContext=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,nodeId:'C-HOST',command:'edit'})).request;
 updateContext.note='Actual context changed: triggers named policy';
 updateContext.data={nodeId:'C-HOST',changes:{value:'Изменение для пользовательской политики'},cosmetic:false};
 await writeExample(updateContext);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),exampleRow.packageId);await idle();
 await click('Зависимости','.rdg-tools');
 policyGraph=(await api({method:'read',packageId:exampleRow.packageId})).graph;
 const recorded=policyGraph.events.at(-1);
 const hits=(recorded.dependencyImpacts||[]).filter(x=>x.policyId===policy.id&&x.dependentId===subscribedNode);
 assert.equal(hits.length,1,'one matching rule produces one actual persisted trigger');
 assert.equal(hits[0].matchedParticipants.sourceId,'C-HOST');assert.equal(hits[0].matchedParticipants.targetId,subscribedNode);
 assert.equal(hits[0].ruleId,policy.rules[0].id);
 assert.equal(hits[0].policyVersion,1);
 await page.$eval('[data-dependency-tab=stale]',n=>n.click());await idle();
 const triggerCard=await page.$eval('[data-stale-node-id="R-STALE-UI"] [data-trigger-policy-id="'+policy.id+'"]',n=>n.textContent);
 assert(triggerCard.includes('Контекст изменён')&&triggerCard.includes('C-HOST'),
  'stale view shows exact named rule and concrete triggering participants, without fabricated checks');
 await click('Открыть политику и правило','[data-trigger-policy-id="'+policy.id+'"]');
 assert.equal(await page.$eval('.rdg-policy-main',n=>n.dataset.policyId),policy.id,
  'trigger links to named policy catalog');
 await click('Изменить — новая версия','.rdg-policy-main');
 await field('Название политики','Изменился процессный контекст · v2');
 await click('Проверить и сохранить политику','.rdg-modal');await save();
 const afterVersion=(await api({method:'read',packageId:exampleRow.packageId})).graph;
 assert.equal(afterVersion.dependencyPolicies.filter(p=>p.id===policy.id).length,2);
 assert.equal(afterVersion.dependencyBindings.find(b=>b.id===binding.id).policyVersion,1,
  'policy update creates a new version without silently migrating existing binding');
 await click('Отключить версию','.rdg-policy-main');await save();
 let lifecycle=(await api({method:'read',packageId:exampleRow.packageId})).graph;
 assert.equal(lifecycle.dependencyBindings.find(b=>b.id===binding.id).enabled,false,'disabling version suspends pinned applications');
 await click('Разрешить использование','.rdg-policy-main');await save();
 lifecycle=(await api({method:'read',packageId:exampleRow.packageId})).graph;
 assert.equal(lifecycle.dependencyBindings.find(b=>b.id===binding.id).enabled,false,'re-enabling a version does not resume applications');
 await click('Активировать снова','[data-binding-id="'+binding.id+'"]');await save();
 lifecycle=(await api({method:'read',packageId:exampleRow.packageId})).graph;
 assert.equal(lifecycle.dependencyBindings.find(b=>b.id===binding.id).enabled,true,'manual resume uses applicability check');
 assert(!lifecycle.events.at(-1).dependencyImpacts?.some(h=>h.bindingId===binding.id),'resume does not replay stale');
 await page.screenshot({path:path.join(base,'dependency-policy-v2-shared-catalog.png'),fullPage:true});
 await click('← К графу','.rdg-policy-header');
 await click('Сведения','.rdg-tools');
 await page.$eval('.rdg-inspector-tab[data-inspector-tab=dependencies]',n=>n.click());
 const actualInspector=await page.$eval('[data-entity-dependencies-id]',n=>n.textContent);
 assert(actualInspector.includes('Зависимости')&&actualInspector.includes('Влияния'),
  'selected block inspector exposes a separate Dependencies tab');
 await page.screenshot({path:path.join(base,'dependency-policy-v2-catalog.png'),fullPage:true});
 checks.push('policy v2: all system policies explain applicability, observation and example; complete human dictionary and editor help; shared catalog, actual binding, immutable versions and exact evidence');
 // Stage two: real inspector controls, exact pinned versions and return flow.
 const inspectorFor=async(id,workGraphId=null)=>{await page.evaluate(({pid,id,workGraphId})=>RDG_PORTABLE_EDITOR.open(pid,{kind:'focus',id,...(workGraphId?{workGraphId}:{})}),{pid:exampleRow.packageId,id,workGraphId});await idle();await click('Сведения','.rdg-tools');await click('Зависимости','.rdg-inspector-tabs');};
 const cardFor=id=>'[data-entity-dependencies-id] [data-dependency-application-id="'+id+'"]';
 const instanceFor=id=>'[data-policy-instances-dialog] [data-dependency-instance-id="'+id+'"]';
 const showInstances=async id=>{await click('Показать инстансы',cardFor(id));await page.waitForSelector('[data-policy-instances-dialog]');};
 const closeInstances=()=>click('Закрыть инстансы','[data-policy-instances-dialog]');
 const chooseDependencyGroup=async(direction,group)=>{await page.click('.rdg-inspector [data-dependency-filter="'+group+'"][data-dependency-direction="'+direction+'"]');await idle();};
 const stage2Core=async(command,data,nodeId='R1')=>{if(command==='delete'){const request=(await api({method:'schema',op:'delete',packageId:exampleRow.packageId})).request;request.nodeIds=[nodeId];request.note='Synthetic stage two removed source';return writeExample(request);}const request=(await api({method:'schema',op:'core',packageId:exampleRow.packageId,nodeId,command})).request;request.note='Synthetic stage two inspector acceptance';request.data=data;return writeExample(request);};
 await inspectorFor(subscribedNode);
 const inspectorBefore=JSON.stringify((await state()).graph),inspectorSpec=JSON.stringify((await state()).view.spec);
 assert.equal(await page.$eval(cardFor(binding.id),n=>n.dataset.dependencyStatus),'active');
 assert((await page.$eval(cardFor(binding.id),n=>n.textContent)).includes('Версия 1'));
 await click('Открыть политику · v1',cardFor(binding.id));
 assert.equal(await page.$eval('.rdg-policy-main',n=>n.dataset.policyVersion),'1','inspector opens the binding version even after a newer policy exists');
 await click('← К сведениям элемента','.rdg-policy-header');
 assert.equal(JSON.stringify((await state()).view.spec),inspectorSpec,'catalog return preserves focus and Working Graph');
 assert.equal(JSON.stringify((await state()).graph),inspectorBefore,'viewing dependency details and catalog return never write Graph');
 const instanceControls=await page.$('[data-dependency-filters]');requests.length=0;
 await showInstances(binding.id);
 assert(await page.$(instanceFor(binding.id)+' [data-instance-actor-id="C-HOST"] [data-instance-dependent-id="'+subscribedNode+'"]'));
 assert.equal(await page.$eval(instanceFor(binding.id),n=>n.dataset.instanceActive),'true');
 const simpleInstanceText=await page.$eval('[data-policy-instances-dialog]',node=>node.textContent);
 assert(simpleInstanceText.includes('Что меняется')&&simpleInstanceText.includes('Как именно')&&simpleInstanceText.includes('Что требует пересмотра'));
 for(const noise of ['ID применения','Условие действует','Что отслеживается:','Применимость, роли','Пример','C-HOST'])assert(!simpleInstanceText.includes(noise),'compact instance view omits '+noise);
 assert.equal(await page.$$eval('[data-policy-instances-dialog] details',nodes=>nodes.length),0);
 assert((await page.$eval('[data-policy-instances-dialog]',node=>node.textContent)).length<1500,'simple policy instance stays compact');
 assert(!requests.some(method=>['preflight','apply','read'].includes(method)),'instances use the already-read projection without domain commands or extra Graph reads');
 await page.keyboard.press('Escape');await idle();assert.equal(await page.$('[data-policy-instances-dialog]'),null);
 assert(await instanceControls.evaluate(node=>node===document.querySelector('[data-dependency-filters]')),'opening and closing instances preserve the filter controls');
 assert.equal(JSON.stringify((await state()).graph),inspectorBefore);assert.equal(JSON.stringify((await state()).view.spec),inspectorSpec);

 await click('Отключить',cardFor(binding.id));await save();
 assert.equal(await page.$eval(cardFor(binding.id),n=>n.dataset.dependencyStatus),'disabled');
 await click('Изменить применение',cardFor(binding.id));
 assert.equal(await page.$eval('[data-policy-binding-editor] select',n=>n.value),policy.id);
 await field('Версия','2');await click('Проверить и сохранить применение','.rdg-modal');await save();
 let stage2Graph=(await state()).graph;
 assert.equal(stage2Graph.dependencyBindings.find(b=>b.id===binding.id).policyVersion,2);
 assert.equal(stage2Graph.dependencyBindings.find(b=>b.id===binding.id).enabled,false,'editing never resumes a disabled binding');
 await click('Активировать снова',cardFor(binding.id));await save();
 await click('Удалить применение',cardFor(binding.id));await save();
 assert.equal(await page.$(cardFor(binding.id)),null);
 assert.equal((await state()).graph.dependencyBindings.find(b=>b.id===binding.id).status,'deleted','remove is a retained tombstone');
 await click('Создать новую политику','[data-entity-dependencies-id]');
 await field('Название политики','Политика из сведений');await field('Описание','Synthetic inspector return flow');
 await click('Проверить и сохранить политику','.rdg-modal');await save();
 assert(await page.$('[data-policy-binding-editor]'),'saving new policy returns directly to its application');
 await field('Источник изменений','C-HOST');
 await click('Проверить и сохранить применение','.rdg-modal');await save();
 stage2Graph=(await state()).graph;
 const fromInspector=stage2Graph.dependencyPolicies.find(p=>p.name==='Политика из сведений');
 const createdBinding=stage2Graph.dependencyBindings.find(b=>b.policyId===fromInspector.id);
 assert.equal(createdBinding.targetId,subscribedNode,'new policy remembers the selected dependent element');
 assert.equal(await page.$eval('[data-entity-dependencies-id]',n=>n.dataset.entityDependenciesId),subscribedNode);
 assert(await page.$(cardFor(createdBinding.id)));
 assert(!stage2Graph.events.at(-1).dependencyImpacts?.some(h=>h.bindingId===createdBinding.id));
 checks.push('inspector: pinned policy version and catalog return; explicit version edit while disabled; manual resume and tombstone removal; create policy -> apply -> same selected element without fabricated stale');

 // Applicability loss, failed activation, restored relation and removed source.
 await stage2Core('add',{entity:{id:'CTX-S2',kind:'context',title:'Источник этапа 2',value:'Synthetic',description:'Temporary browser owner only'},location:'graph'});
 const stage2Relation={id:'REL-S2',type:'CONTEXT_FOR',from:'CTX-S2',to:subscribedNode};
 await stage2Core('link',{relation:stage2Relation});
 const stage2Policy={id:'POL-S2',version:1,name:'Применимость в сведениях',description:'Observe only while relation exists',origin:'user',status:'active',pattern:'roles',sourceKinds:['context'],targetKinds:['requirement'],roles:[{id:'target',kinds:['requirement'],required:true},{id:'source',kinds:['context'],required:true}],relations:[{from:'source',to:'target',type:['CONTEXT_FOR','DECISION_CONTEXT']}],rules:[{id:'content',name:'Изменение содержания',role:'source',watch:'definition',operations:['changed'],enabled:true}]};
 await stage2Core('policy_change',{action:'policy_save',value:stage2Policy});
 await stage2Core('policy_change',{action:'binding_save',value:{id:'B-S2',policyId:'POL-S2',policyVersion:1,targetId:subscribedNode,sourceId:null,parentId:null,enabled:true,participantBindings:{source:'CTX-S2'}}});
 await stage2Core('unlink',{edgeId:'REL-S2'});await click('Обновить','.rdg-head');
 assert.equal(await page.$eval(cardFor('B-S2'),n=>n.dataset.dependencyStatus),'disabled');
 assert((await page.$eval(cardFor('B-S2'),n=>n.textContent)).includes('Нет обязательного отношения'));
 const failedActivationBefore=JSON.stringify((await state()).graph);
 await page.$eval(cardFor('B-S2'),n=>[...n.querySelectorAll('button')].find(b=>b.textContent==='Активировать снова').click());await idle();
 assert((await page.$eval('.rdg-status',n=>n.textContent)).includes('INAPPLICABLE'));
 assert.equal(JSON.stringify((await api({method:'read',packageId:exampleRow.packageId})).graph),failedActivationBefore,'failed activation leaves Graph unchanged');
 await stage2Core('link',{relation:{...stage2Relation,id:'REL-S2-RESTORED'}});await click('Обновить','.rdg-head');
 assert((await page.$eval(cardFor('B-S2'),n=>n.textContent)).includes('Сейчас условия применимости выполнены'));
 assert.equal((await state()).graph.dependencyBindings.find(b=>b.id==='B-S2').enabled,false);
 await click('Активировать снова',cardFor('B-S2'));await save();
 await stage2Core('delete',{},'CTX-S2');await click('Обновить','.rdg-head');
 await showInstances('B-S2');
 const missingSourceText=await page.$eval(instanceFor('B-S2'),n=>n.textContent);
 assert(missingSourceText.includes('Источник этапа 2')&&missingSourceText.includes('участник удалён или недоступен'));
 assert.equal(await page.$eval(instanceFor('B-S2'),n=>n.dataset.instanceActive),'false');await closeInstances();
 await stage2Core('link',{relation:{id:'REL-S2-REPLACEMENT',type:'CONTEXT_FOR',from:'C-HOST',to:subscribedNode}});
 await click('Обновить','.rdg-head');await click('Изменить применение',cardFor('B-S2'));
 await field('Источник изменений','C-HOST');await click('Проверить и сохранить применение','.rdg-modal');await save();
 assert.equal((await state()).graph.dependencyBindings.find(b=>b.id==='B-S2').enabled,false);
 await click('Активировать снова',cardFor('B-S2'));await save();
 const autoCard=await page.$eval('[data-entity-dependencies-id] [data-dependency-application-kind="automatic"]',n=>n.dataset.dependencyApplicationId);
 const edgeCount=(await state()).graph.edges.length;
 await click('Отключить',cardFor(autoCard));await save();
 await click('Активировать снова',cardFor(autoCard));await save();
 assert.equal((await state()).graph.edges.length,edgeCount,'automatic lifecycle does not duplicate physical dependencies');
 await page.screenshot({path:path.join(base,'dependency-inspector-lifecycle.png'),fullPage:true});
 checks.push('inspector: missing mandatory alternative relation -> disabled; activation fails without writes; restore does not resume; deleted source remains recorded and can be replaced; automatic disable/resume shares existing facts');

 // A member outside the active Working Graph and a real intermediate witness.
 await stage2Core('add',{entity:{id:'BRIDGE-S2',kind:'requirement',title:'Промежуточный участник',description:'Synthetic bridge',scope:'Stage two'},location:'graph'});
 for(const workGraph of [{id:'WG-S2-1',title:'First path segment',rootIds:['BRIDGE-S2'],memberIds:[subscribedNode,'BRIDGE-S2']},{id:'WG-S2-2',title:'Second path segment',rootIds:['BRIDGE-S2'],memberIds:['BRIDGE-S2','C-HOST']}])await stage2Core('work_graph',{workGraph});
 const pathPolicy={...stage2Policy,id:'POL-S2-PATH',name:'Динамический путь через две области',relations:[],roles:[{id:'target',kinds:['requirement'],required:true},{id:'source',kinds:['context'],required:true,selector:{anchor:'target',relation:'SHARED_WORK_GRAPH',direction:'out',minDepth:2,maxDepth:2}}]};
 await stage2Core('policy_change',{action:'policy_save',value:pathPolicy});
 await stage2Core('policy_change',{action:'binding_save',value:{id:'B-S2-PATH',policyId:pathPolicy.id,policyVersion:1,targetId:subscribedNode,sourceId:null,parentId:null,enabled:true,participantBindings:{}}});
 await inspectorFor('BRIDGE-S2','WG-S2-1');await chooseDependencyGroup('outgoing','participation');
 assert(await page.$('[data-dependency-direction="participation"] [data-dependency-application-id="B-S2-PATH"]'),'intermediate is visible without pretending its content is observed');
 await showInstances('B-S2-PATH');
 const pathText=await page.$eval(instanceFor('B-S2-PATH'),n=>n.textContent);
 assert(pathText.includes('На сервере уже работает PostgreSQL')&&pathText.includes('Изменится содержание контекста'));
 assert(!pathText.includes('workGraph:')&&!pathText.includes('ID применения')&&!pathText.includes('Поиск от роли'),'instance window shows concrete changes without paths and technical IDs');
 const beforeReference=JSON.stringify((await state()).graph),beforeReferenceSpec=JSON.stringify((await state()).view.spec);
 assert(await page.$('[data-instance-direction="participation"] [data-dependency-instance-id="B-S2-PATH"]'));
 assert.equal(await page.$(instanceFor('B-S2-PATH')+' [data-instance-actor-id="BRIDGE-S2"]'),null,'a path intermediate is not a data observer');
 await page.$eval(instanceFor('B-S2-PATH')+' [data-dependency-participant-id="C-HOST"] button',n=>n.click());await idle();
 assert.equal(await page.$eval('[data-entity-dependencies-id]',n=>n.dataset.entityDependenciesId),'C-HOST');
 await chooseDependencyGroup('outgoing','all');
 assert(await page.$('[data-dependency-direction="outgoing"] [data-dependency-application-id="B-S2-PATH"]'));
 assert.equal(JSON.stringify((await state()).view.spec),beforeReferenceSpec,'reference to an outside member preserves selected focus/area');
 assert.equal(JSON.stringify((await state()).graph),beforeReference,'links and dynamic paths remain read-only');
 await showInstances('B-S2-PATH');
 await page.screenshot({path:path.join(base,'dependency-inspector-dynamic-path.png'),fullPage:true});await closeInstances();
 checks.push('inspector: dynamic two-hop projection resolves the real outside source; compact instances omit path diagnostics and preserve intermediate participation separately; references preserve scope and never write');
 // Category controls remain the same DOM nodes above a single changing list.
 await inspectorFor('D-STORE');
 await page.$eval('.rdg-inspector',n=>n.scrollTop=0);
 const fixedControls=await page.$('[data-dependency-filters]');
 const toolbarSnapshot=()=>page.$eval('[data-dependency-filters]',n=>({text:n.textContent,rows:[...n.querySelectorAll('[data-dependency-filter-direction]')].map(row=>({direction:row.dataset.dependencyFilterDirection,first:row.querySelector('button').dataset.dependencyFilter,labels:[...row.querySelectorAll('button')].map(b=>({group:b.dataset.dependencyFilter,count:Number(b.dataset.count)}))}))}));
 const controlsBefore=await toolbarSnapshot();assert.deepEqual(controlsBefore.rows.map(row=>[row.direction,row.first]),[['incoming','all'],['outgoing','all']]);
 for(const row of controlsBefore.rows)assert.equal(row.labels.filter(group=>!['all','participation'].includes(group.group)).reduce((sum,group)=>sum+group.count,0),row.labels.find(group=>group.group==='all').count,'primary group counts partition the direction without double counting');
 const initialBounds=await fixedControls.evaluate(n=>{const b=n.getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height};});
 const graphBeforeFiltering=JSON.stringify((await state()).graph),specBeforeFiltering=JSON.stringify((await state()).view.spec);
 const applicationRows=(await state()).dependencyCatalog.localApplications;
 const graphContextEdges=new Set((await state()).graph.edges.filter(edge=>edge.type==='DEPENDS_ON'&&edge.to==='D-STORE'&&edge.dependencyPurpose==='decisionContext').map(edge=>edge.id));
 const expectedContext=applicationRows.filter(row=>row.targetId==='D-STORE'&&(row.kind==='legacy-context'||graphContextEdges.has(row.legacyEdgeId))).map(row=>row.id).sort();
 assert(expectedContext.includes(configured.id),'configured context link remains in the Decision context group after conversion');
 const expectedAutomatic=applicationRows.filter(row=>row.targetId==='D-STORE'&&row.kind==='automatic').map(row=>row.id).sort();
 assert(expectedContext.length>0&&expectedAutomatic.length>0,'fixture contains both context and automatic applications');
 requests.length=0;
 await chooseDependencyGroup('incoming','context');
 const renderedApplications=()=>page.$$eval('[data-dependency-results] [data-dependency-application-id]',nodes=>nodes.map(n=>n.dataset.dependencyApplicationId).sort());
 assert.deepEqual(await renderedApplications(),expectedContext,'context category shows only actual Decision context applications');
 assert.deepEqual(await toolbarSnapshot(),controlsBefore,'both rows and all counts remain unchanged after filtering');
 const contextBounds=await fixedControls.evaluate(n=>{const b=n.getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height};});
 assert.deepEqual(contextBounds,initialBounds,'filter controls stay at the same position');
 await page.screenshot({path:path.join(base,'dependency-groups-context.png'),fullPage:true});
 await chooseDependencyGroup('incoming','automatic');assert.deepEqual(await renderedApplications(),expectedAutomatic);
 await chooseDependencyGroup('incoming','all');
 assert.equal((await renderedApplications()).length,applicationRows.filter(row=>row.targetId==='D-STORE').length,'show all restores full incoming list');
 await chooseDependencyGroup('outgoing','all');
 assert.equal((await renderedApplications()).length,applicationRows.filter(row=>row.targetId!=='D-STORE'&&row.observedIds.includes('D-STORE')).length,'outgoing Show all counts only actual influences on dependents');
 assert.equal(await page.$$eval('[data-dependency-filters] button[aria-pressed="true"]',nodes=>nodes.length),1,'one category across both rows indicates the current result list');
 assert(await fixedControls.evaluate(n=>n===document.querySelector('[data-dependency-filters]')),'filtering replaces only results, never the controls');
 await chooseDependencyGroup('outgoing','participation');
 assert.equal((await renderedApplications()).length,applicationRows.filter(row=>row.targetId!=='D-STORE'&&row.nodeIds.includes('D-STORE')&&!row.observedIds.includes('D-STORE')).length,'participation remains accessible outside the influence total');
 assert.deepEqual(await toolbarSnapshot(),controlsBefore);
 assert.equal(JSON.stringify((await state()).graph),graphBeforeFiltering);assert.equal(JSON.stringify((await state()).view.spec),specBeforeFiltering);
 assert.equal(requests.length,0,'category selection is local and does not call the server');
 await inspectorFor(subscribedNode);
 const explicitRows=(await state()).dependencyCatalog.localApplications.filter(row=>row.targetId===subscribedNode&&row.kind!=='automatic'&&!row.decisionContext&&row.kind!=='legacy-context');
 assert(explicitRows.some(row=>row.kind==='legacy')&&explicitRows.some(row=>row.kind==='policy'),'fixture has both per-link settings and saved policy applications');
 const explicitGraphBefore=JSON.stringify((await state()).graph);
 await chooseDependencyGroup('incoming','explicit');
 assert.deepEqual(await renderedApplications(),explicitRows.map(row=>row.id).sort(),'explicit dependencies combine both configuration formats without losing or duplicating applications');
 assert((await page.$eval(cardFor('DEP-STALE-UI'),n=>n.textContent)).includes('настройки отдельной связи'));
 assert((await page.$eval(cardFor(createdBinding.id),n=>n.textContent)).includes('применение сохранённой политики'));
 for(const direction of ['incoming','outgoing'])assert.deepEqual(await page.$$eval('[data-dependency-filter-direction="'+direction+'"] button',nodes=>nodes.map(n=>n.dataset.dependencyFilter)),direction==='incoming'?['all','context','automatic','explicit']:['all','context','automatic','explicit','participation'],'both directions use one explicit group');
 assert.equal(JSON.stringify((await state()).graph),explicitGraphBefore);
 await page.screenshot({path:path.join(base,'dependency-groups-explicit.png'),fullPage:true});
 checks.push('dependency groups: two persistent rows start with Show all; merged explicit dependencies, exact category counts, context/automatic/outgoing filtering, unchanged controls and positions, one active selection and no server or owner writes');
 // All concrete uses of one version, scoped to the selected element in both roles.
 await stage2Core('add',{entity:{id:'CTX-INST-OTHER',kind:'context',title:'Другой наблюдаемый факт',description:'Unrelated instance source',value:'Synthetic'},location:'graph'});
 const makeInstance=(id,source,target,version=1)=>({id,policyId:fromInspector.id,policyVersion:version,targetId:target,sourceId:null,parentId:null,enabled:true,participantBindings:{source}});
 await stage2Core('policy_change',{action:'binding_save',value:makeInstance('B-INST-SECOND','C-HOST','R-COST')});
 await stage2Core('policy_change',{action:'binding_save',value:makeInstance('B-INST-OTHER','CTX-INST-OTHER','R-COST')});
 await stage2Core('policy_change',{action:'policy_save',value:{...fromInspector,version:2,name:'Политика из сведений · v2',rules:[...fromInspector.rules,{id:'target-result',name:'Результат зависимого',role:'target',watch:'result',operations:['changed'],enabled:true}]}});
 await stage2Core('policy_change',{action:'binding_save',value:makeInstance('B-INST-V2','C-HOST','R1',2)});
 // Open a context source through the existing application references.
 await inspectorFor(subscribedNode);await chooseDependencyGroup('incoming','explicit');await showInstances(createdBinding.id);
 await page.$eval(instanceFor(createdBinding.id)+' [data-instance-actor-id="C-HOST"] [data-dependency-participant-id="C-HOST"] button',node=>node.click());await idle();
 await chooseDependencyGroup('outgoing','explicit');
 const beforeInstancesGraph=JSON.stringify((await state()).graph),beforeInstancesSpec=JSON.stringify((await state()).view.spec);
 await showInstances(createdBinding.id);
 const concreteIds=()=>page.$$eval('[data-policy-instances-dialog] [data-dependency-instance-id]',nodes=>nodes.map(node=>node.dataset.dependencyInstanceId).sort());
 assert.deepEqual(await concreteIds(),[createdBinding.id,'B-INST-SECOND'].sort(),'source view includes all applications of this version with this source, excluding unrelated and other-version applications');
 assert(await page.$(instanceFor(createdBinding.id)+' [data-instance-actor-id="C-HOST"]'));
 assert(await page.$(instanceFor('B-INST-SECOND')+' [data-instance-dependent-id="R-COST"]'));
 assert(await page.$$eval('[data-policy-instances-dialog] [data-selected-instance-participant=true]',nodes=>nodes.length>=3));
 await page.screenshot({path:path.join(base,'policy-instances-source.png'),fullPage:true});
 await click('Открыть политику · v1','[data-policy-instances-dialog]');
 assert.equal(await page.$eval('.rdg-policy-main',node=>node.dataset.policyVersion),'1','instance navigation opens the pinned definition, not latest version two');
 assert(await page.$('[data-dependency-panel="policies"]'));await click('← К сведениям элемента','.rdg-policy-header');
 assert.equal(await page.$eval('[data-entity-dependencies-id]',node=>node.dataset.entityDependenciesId),'C-HOST');
 assert.equal(JSON.stringify((await state()).view.spec),beforeInstancesSpec);assert.equal(JSON.stringify((await state()).graph),beforeInstancesGraph);
 await inspectorFor('R-COST');await chooseDependencyGroup('incoming','explicit');await showInstances('B-INST-SECOND');
 assert.deepEqual(await concreteIds(),['B-INST-SECOND','B-INST-OTHER'].sort(),'dependent view resolves both concrete sources for this selected dependent');
 assert(await page.$(instanceFor('B-INST-OTHER')+' [data-instance-actor-id="CTX-INST-OTHER"]'));
 await closeInstances();
 await inspectorFor('R1');await chooseDependencyGroup('incoming','explicit');await showInstances('B-INST-V2');
 await page.$eval(instanceFor('B-INST-V2')+' [data-dependency-participant-id="C-HOST"] button',node=>node.click());await idle();
 assert.equal(await page.$eval('[data-entity-dependencies-id]',node=>node.dataset.entityDependenciesId),'C-HOST');
 await chooseDependencyGroup('outgoing','explicit');await showInstances('B-INST-V2');
 const sourceConditions=await page.$$eval(instanceFor('B-INST-V2')+' tr[data-instance-rule-id]',nodes=>nodes.map(node=>node.dataset.instanceRuleId));
 assert(!sourceConditions.includes('target-result'),'influences omit conditions on another participant of the same application');
 assert(sourceConditions.length>0);await closeInstances();
 await inspectorFor('R1');await chooseDependencyGroup('incoming','explicit');await showInstances('B-INST-V2');
 assert(await page.$(instanceFor('B-INST-V2')+' tr[data-instance-rule-id="target-result"]'),'dependent view retains the same rule when it really affects this element');
 await closeInstances();
 await inspectorFor('D-STORE');await chooseDependencyGroup('incoming','all');
 const sampleCanon=(await state()).dependencyCatalog.localApplications.find(row=>row.policyId==='builtin:automatic-canon'&&row.targetId==='D-STORE'&&row.enabled);
 assert(sampleCanon,'Canon screenshot fixture has an active concrete application');await showInstances(sampleCanon.id);
 assert((await page.$eval('[data-policy-instances-dialog]',node=>node.textContent)).includes('Изменится теория принятия решения: каноны'));
 await page.screenshot({path:path.join(base,'policy-instances-canon-simple.png'),fullPage:true});await closeInstances();
 const sampleStructural=(await state()).dependencyCatalog.localApplications.find(row=>row.policyId==='builtin:structural'&&row.targetId==='D-STORE'&&row.participants[row.binding.sourceId]?.kind==='requirement');
 assert(sampleStructural,'structural fixture has a Requirement parent');await showInstances(sampleStructural.id);
 for(const ruleId of ['context-content','context-membership','parent-withdrawn'])assert.equal(await page.$(instanceFor(sampleStructural.id)+' tr[data-instance-rule-id="'+ruleId+'"]'),null,'Requirement source omits Decision-only condition '+ruleId);
 await closeInstances();
 checks.push('policy instances: compact source / exact change / dependent table, one policy description and participant links; no repeated descriptions, examples or technical IDs; selected-direction and pinned-version scope, disabled history and intermediate participation; read-only navigation preserves scope and filters');

 // Stage three: full-width cards, exact recorded evidence and independent lifecycles.
 await stage2Core('add',{entity:{id:'R-I3',kind:'requirement',title:'Проверить решение по нагрузке',description:'Synthetic invalidation target',scope:'Stage three'},location:'graph'});
 await stage2Core('add',{entity:{id:'CTX-I3',kind:'context',title:'Нагрузка для проверки',description:'Synthetic source',value:'100'},location:'graph'});
 await stage2Core('link',{relation:{id:'REL-I3',type:'CONTEXT_FOR',from:'CTX-I3',to:'R-I3'}});
 const invPolicy={id:'POL-I3',version:1,name:'Наблюдение нагрузки',description:'Пересмотр при изменении наблюдаемой нагрузки.',origin:'user',status:'active',pattern:'roles',sourceKinds:['context'],targetKinds:['requirement'],roles:[{id:'target',kinds:['requirement'],required:true},{id:'source',kinds:['context'],required:true}],relations:[{from:'source',to:'target',type:'CONTEXT_FOR'}],rules:[{id:'content',name:'Изменение нагрузки',role:'source',watch:'definition',operations:['changed'],enabled:true}]};
 await stage2Core('policy_change',{action:'policy_save',value:invPolicy});
 await stage2Core('policy_change',{action:'binding_save',value:{id:'B-I3',policyId:invPolicy.id,policyVersion:1,targetId:'R-I3',sourceId:null,parentId:null,enabled:true,participantBindings:{source:'CTX-I3'}}});
 await stage2Core('edit',{nodeId:'CTX-I3',changes:{value:'200'},cosmetic:false});
 await stage2Core('edit',{nodeId:'CTX-I3',changes:{value:'300',title:'Нагрузка для проверки · уточнено'},cosmetic:false});
 await stage2Core('policy_change',{action:'policy_save',value:{...invPolicy,version:2,name:'Наблюдение нагрузки · новая версия'}});
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),exampleRow.packageId);await idle();await click('Зависимости','.rdg-tools');
 await page.$eval('[data-dependency-tab=stale]',n=>n.click());await idle();
 const invFilter=async value=>{await page.click('[data-invalidation-filter="'+value+'"]');await idle();};
 const invSelect=async(key,value)=>{await page.select('[data-invalidation-'+key+']',value);await idle();};
 await invSelect('element','R-I3');
 const invCard=kind=>'[data-invalidation-kind="'+kind+'"][data-invalidation-active=true]';
 assert.equal(await page.$$eval('[data-review-node-id="R-I3"]',nodes=>nodes.length),1,'multiple causes have one target-level review action');
 assert.equal(await page.$$eval(invCard('review')+' .rdg-stale-reason',nodes=>nodes.length),2);
 assert.deepEqual((await page.$$eval(invCard('review')+' [data-invalidation-participant-id="CTX-I3"] .rdg-entity-reference-title',nodes=>nodes.map(n=>n.textContent))).sort(),['Нагрузка для проверки','Нагрузка для проверки · уточнено'].sort(),'each cause uses its own event-time name');
 const cardGeometry=await page.$eval(invCard('review'),node=>({card:node.getBoundingClientRect().width,list:node.parentElement.getBoundingClientRect().width}));
 assert(cardGeometry.card>cardGeometry.list*.95,'invalidation cards use the full list width');
 assert((await page.$eval(invCard('review'),n=>n.textContent)).includes('Нагрузка для проверки'));
 const originalInvControls=await page.$('[data-invalidation-controls]'),beforeInvFilters=JSON.stringify((await state()).graph);requests.length=0;
 await invSelect('policy','POL-I3');await invSelect('version','1');await invSelect('cause','definition');
 assert.equal(await page.$$eval(invCard('review'),nodes=>nodes.length),1);
 assert(await originalInvControls.evaluate(n=>n===document.querySelector('[data-invalidation-controls]')),'filtering replaces the list, preserving controls');
 assert.equal(requests.length,0,'invalidation filters are local');assert.equal(JSON.stringify((await state()).graph),beforeInvFilters);
 await invSelect('policy','');await invSelect('cause','');
 await stage2Core('unlink',{edgeId:'REL-I3'});await click('Обновить','.rdg-head');
 assert(await page.$(invCard('review')));assert(await page.$(invCard('disabled')),'review and applicability loss are separate cards');
 assert.equal(await page.$(invCard('disabled')+' [data-review-node-id]'),null,'disabled application has no review action');
 const disabledSnapshot=JSON.stringify((await state()).graph);
 await page.$eval('[data-invalidation-activate="B-I3"]',node=>node.click());await idle();
 assert((await page.$eval('.rdg-status',n=>n.textContent)).includes('INAPPLICABLE'));
 assert.equal(JSON.stringify((await api({method:'read',packageId:exampleRow.packageId})).graph),disabledSnapshot,'failed activation writes no domain state');
 await page.$eval('[data-review-node-id="R-I3"]',node=>node.click());await idle();await field('Основание / наблюдение','Проверены фактические изменения нагрузки');await click('Проверить действие','.rdg-modal');await save();
 assert.equal((await state()).graph.dependencyBindings.find(b=>b.id==='B-I3').enabled,false,'review never activates a disabled application');
 assert.equal(await page.$(invCard('review')),null);assert(await page.$(invCard('disabled')));
 await stage2Core('link',{relation:{id:'REL-I3-RESTORED',type:'CONTEXT_FOR',from:'CTX-I3',to:'R-I3'}});await click('Обновить','.rdg-head');
 assert((await page.$eval(invCard('disabled'),n=>n.textContent)).includes('Условия сейчас выполнены'));
 await invFilter('disabled');await page.setViewport({width:1280,height:720});
 const invPosition=await page.$eval('.rdg-policy-scroll',node=>{node.scrollTop=100;node.dispatchEvent(new Event('scroll'));return node.scrollTop;});
 const invRecord=await page.$eval(invCard('disabled'),n=>n.dataset.invalidationId);
 await page.$eval(invCard('disabled')+' [data-invalidation-policy-id="POL-I3"]',node=>node.click());await idle();
 assert.equal(await page.$eval('.rdg-policy-main',n=>n.dataset.policyVersion),'1','event navigation opens recorded version one despite latest version two');
 await click('← К инвалидации','.rdg-policy-header');
 assert.equal(await page.$eval('[data-invalidation-element]',n=>n.value),'R-I3');
 assert.equal(await page.$eval('[data-invalidation-filter=disabled]',n=>n.getAttribute('aria-pressed')),'true');
 assert.equal(await page.$eval('[data-invalidation-selected=true]',n=>n.dataset.invalidationId),invRecord);
 assert.equal(await page.$eval('.rdg-policy-scroll',n=>n.scrollTop),invPosition,'return restores scroll');
 await page.screenshot({path:path.join(base,'invalidation-disabled-cards.png'),fullPage:true});
 await click('Открыть применение',invCard('disabled'));assert.equal(await page.$eval('[data-entity-dependencies-id]',n=>n.dataset.entityDependenciesId),'R-I3');
 await click('← К инвалидации','[data-entity-dependencies-id]');
 await click('Активировать снова',invCard('disabled'));await save();
 assert.equal((await state()).graph.dependencyBindings.find(b=>b.id==='B-I3').enabled,true);
 assert.equal(await page.$(invCard('disabled')),null);
 await invFilter('history');
 let invRows=(await state()).dependencyCatalog.invalidationRecords.filter(r=>r.nodeIds.includes('R-I3'));
 assert(invRows.some(r=>r.kind==='review'&&!r.active&&r.resolution==='reviewed'));
 assert(invRows.some(r=>r.bindingId==='B-I3'&&!r.active&&r.resolution==='activated'));
 await stage2Core('policy_change',{action:'binding_disable',value:{id:'B-I3'}});await click('Обновить','.rdg-head');await invFilter('disabled');
 assert.equal(await page.$$eval(invCard('disabled'),nodes=>nodes.length),1,'new disable cycle produces one current card');
 await click('Удалить применение',invCard('disabled'));await save();assert.equal((await state()).graph.dependencyBindings.find(b=>b.id==='B-I3').status,'deleted');
 await invFilter('history');invRows=(await state()).dependencyCatalog.invalidationRecords.filter(r=>r.bindingId==='B-I3');
 assert.equal(invRows.length,2);assert.deepEqual(invRows.map(r=>r.resolution).sort(),['activated','deleted']);
 await stage2Core('delete',{},'CTX-I3');await click('Обновить','.rdg-head');
 const oldSource=await page.$('[data-invalidation-kind=disabled][data-invalidation-active=false] [data-invalidation-participant-id="CTX-I3"]');
 assert(oldSource);assert((await oldSource.evaluate(n=>n.textContent)).includes('Нагрузка для проверки'));assert.equal(await oldSource.$('button'),null,'removed source stays recorded without a fabricated live link');
 await page.screenshot({path:path.join(base,'invalidation-history-cards.png'),fullPage:true});
 // Automatic theory dependencies belong to a Decision/Action, never a Requirement.
 await stage2Core('add',{entity:{id:'D-I3',kind:'decision',title:'Способ для проверки теории',description:'Synthetic automatic dependency target'},location:'graph',initialRelations:[{id:'D-I3-R',type:'DRIVES',from:'R-I3',to:'D-I3'}]});
 await stage2Core('add',{entity:{id:'CAN-I3',kind:'canon',title:'Критерий проверки',description:'Synthetic criterion',guidance:'Recorded constraints'},location:'graph'});
 await stage2Core('link',{relation:{id:'CAN-I3-D','type':'CANON_FOR',from:'CAN-I3',to:'D-I3'}});
 await click('Обновить','.rdg-head');await invSelect('element','D-I3');
 const invAuto=(await state()).dependencyCatalog.localApplications.find(r=>r.policyId==='builtin:automatic-canon'&&r.targetId==='D-I3'&&r.binding.sourceId==='CAN-I3');assert(invAuto);
 await stage2Core('policy_change',{action:'automatic_disable',value:{id:invAuto.id}});await click('Обновить','.rdg-head');await invFilter('disabled');
 await click('Удалить применение',invCard('disabled'));await save();assert.equal((await state()).graph.dependencyAutomaticStates[invAuto.id].status,'deleted');
 assert.equal(await page.$(invCard('disabled')),null);await invFilter('history');
 assert((await state()).dependencyCatalog.invalidationRecords.some(r=>r.bindingId===invAuto.id&&r.resolution==='deleted'));
 await invSelect('element','R-I3');
 const invOwnersBefore=JSON.stringify((await state()).graph);
 await invSelect('process',originalProcessId);assert.equal((await state()).package.packageId,originalProcessId);
 await invSelect('process',exampleRow.packageId);assert.equal((await state()).package.packageId,exampleRow.packageId);
 assert.equal(await page.$eval('[data-invalidation-element]',n=>n.value),'R-I3');assert.equal(JSON.stringify((await state()).graph),invOwnersBefore,'process navigation does not mutate owners');
 await page.setViewport({width:1440,height:1000});await click('← К графу','.rdg-policy-header');
 checks.push('invalidation: full-width review/disabled cards; local filters and exact recorded versions; failed activation is atomic, review independent from applicability; restoration waits for explicit activation; disable cycles and removals move to history; deleted participants stay recorded; automatic removal, navigation and scroll restoration');



 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),originalProcessId);await idle();
 checks.push('isolated Process Graph: separate context/Canon tabs, colored references, linked Info navigation and Canon/Info authoring through the existing writer');
 const checkpoint=JSON.parse(fs.readFileSync(path.join(ROOT,'tools/rdg-agent-lenses/checkpoint-decision.json'),'utf8'));
 const createReady=(await api({method:'schema',op:'create'})).request;
 Object.assign(createReady,{role:'ready',path:'ready/checkpoint-visibility-e2e',
   title:checkpoint.title,scope:'Isolated view smoke',coreModel:'rdg-decision-v1',graph:checkpoint});
 const readyPreview=await api({method:'preflight',request:createReady});
 const readyWrite=await api({method:'apply',request:createReady,expectedInputBinding:readyPreview.inputBinding});
 assert(readyWrite.published);
 const checkpointId=readyWrite.packages[0].packageId;
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),checkpointId);await idle();
 let check=await state();const ownerGraph=JSON.stringify(check.graph),ownerLayouts=JSON.stringify(check.layouts);
 assert.equal(check.view.spec.compactGraph,true);
 assert.equal(check.view.visual.nodes.length,9,'overview retains Requirement, Decisions and the three source-method Actions');
 assert(check.view.visual.nodes.every(v=>checkpoint.nodes.some(n=>n.id===v.entityId)), 'overview hides theory and Info objects');
 assert.equal(check.view.visual.routes.length,8,'overview retains DRIVES and REQUIRES_ACTION');
 assert.equal(await page.$$eval('.rdg-node',a=>a.length),9);
 assert((await page.$eval('[data-entity-id="CP-A1"]',n=>n.textContent)).includes('9 Info'));
 await field('Показать Info-блоки',true,'.rdg-tools');
 check=await state();assert.equal(check.view.spec.showAllBlocks,true);
 assert.equal(check.view.visual.nodes.length,16);assert.equal(check.view.visual.routes.length,15);
 assert.equal(await page.$$eval('.rdg-node',a=>a.length),16);
 for(const id of ['LS-SOURCE-CHECKPOINT','LS-MAP-CHECKPOINT','LS-WORKFLOW-CHECKPOINT'])assert(await page.$('.rdg-node[data-entity-id="'+id+'"]'),'expanded view exposes source provenance and mapping '+id);
 assert.equal(await page.$$eval('.rdg-node[data-entity-id^="CANON-"]',a=>a.length),0);
 assert.equal(await page.$$eval('.rdg-node[data-entity-id^="CP-C"]',a=>a.length),0,
   'Info only associated with Canon must not be orphan canvas cards');
 await field('Показать Info-блоки',false,'.rdg-tools');
 check=await state();assert.equal(check.view.visual.nodes.length,9);
 assert.equal(JSON.stringify(check.layouts),ownerLayouts);
 await page.$eval('[data-entity-id="R-LENS-CHECKPOINT"]',n=>n.dispatchEvent(new MouseEvent('click',{bubbles:true})));
 await page.waitForFunction(()=>RDG_PORTABLE_EDITOR.view?.view?.spec?.kind==='focus');await idle();
 assert((await state()).view.visual.nodes.some(n=>n.entityId==='INFO-DECISION-API-CHECKPOINT'),
   'Requirement focus gives access to API instructions');
 await page.$eval('[data-entity-id="CP-A1"]',n=>n.dispatchEvent(new MouseEvent('click',{bubbles:true})));
 await page.waitForFunction(()=>RDG_PORTABLE_EDITOR.view?.view?.spec?.id==='CP-A1');await idle();
 assert(!(await state()).view.visual.nodes.some(n=>n.entityId==='CANON-CP-A1'),
   'Decision focus no longer draws its Canon');
 assert.equal(await page.$('.rdg-inspector-tab[data-inspector-tab="context"]'),null,
   'ready graph must not expose process-specific Decision context in its inspector');
 await page.$eval('[data-entity-id="CP-A1"]',n=>n.dispatchEvent(new MouseEvent('click',{bubbles:true})));
 await idle();
 assert.deepEqual(await page.$$eval('.rdg-inspector-tab',nodes=>nodes.map(n=>n.textContent)),['Рекомендации · 0','Теория принятия решения','Зависимости'],
   'ready Decision exposes Canon and dependencies without a process-specific context tab');
 assert.equal(await page.$$eval('.rdg-canon-info-row',nodes=>nodes.length),7,
   'the Canon tab gives access to all seven linked Info objects');
 assert.equal(JSON.stringify((await state()).graph),ownerGraph);
 assert.equal(JSON.stringify((await state()).layouts),ownerLayouts);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),originalProcessId);await idle();
 checks.push('checkpoint retains source-method Actions: default 9 cards / 8 links; expanded 16 / 15 including source provenance and mapping, without theory or theory-only Info; Decision details expose theory and seven linked Info; no graph/layout write');
 let first=await state();const processId=first.package.packageId;assert.equal(await page.$('.rdg-explorer'),null);assert((await page.$eval('.rdg-project small',n=>n.textContent)).includes('Process Graph'));assert((await page.$eval('.rdg-crumb',n=>n.textContent)).includes('Процесс-граф'));assert.equal(first.graph.workGraphs.length,0);
 const savedLayout=JSON.stringify(first.layouts),initialRoutes=first.view.visual.routes.map(r=>r.edge.id).sort();
 let compact=await state();
 assert.equal(compact.view.spec.compactGraph,true,'Process Graph must open compact by default');
 assert.equal(compact.view.visual.compact,true);
 assert.deepEqual(compact.view.visual.routes.map(r=>r.edge.id).sort(),initialRoutes);
 assert.equal(JSON.stringify(compact.layouts),savedLayout,'Default compact view must not write layout');
 assert.equal(await page.$('.rdg-zoom [data-save-layout]'),null,'Compact view must not persist ephemeral coordinates');
 await click('Моя раскладка','.rdg-zoom');
 compact=await state();
 assert.equal(compact.view.spec.compactGraph,false);
 assert.equal(JSON.stringify(compact.layouts),savedLayout);
 await click('Уплотнить обзор','.rdg-zoom');
 assert.equal((await state()).view.spec.compactGraph,true);
 checks.push('default Process Graph uses compact branch layout; switching preserves routes and saved coordinates');
 const cameraBefore=await page.evaluate(()=>{
  const svg=document.querySelector('.rdg-graph'),b=svg.getBoundingClientRect();
  const [x,y,width,height]=svg.getAttribute('viewBox').split(' ').map(Number);
  return {camera:{x,y,width,height},box:{x:b.x,y:b.y,width:b.width,height:b.height}};
 });
 const anchor={x:cameraBefore.box.x+cameraBefore.box.width*.24,y:cameraBefore.box.y+cameraBefore.box.height*.38};
 await page.mouse.move(anchor.x,anchor.y);
 await page.keyboard.down('Control');await page.mouse.wheel({deltaY:120});await page.keyboard.up('Control');
 await page.waitForFunction(width=>{const v=document.querySelector('.rdg-graph')?.getAttribute('viewBox');
  return v&&Number(v.split(' ')[2])>width*1.01;},{timeout:6000},cameraBefore.camera.width);
 await idle();
 const cameraAfter=await page.$eval('.rdg-graph',svg=>{
  const [x,y,width,height]=svg.getAttribute('viewBox').split(' ').map(Number);return {x,y,width,height};
 });
 assert(cameraAfter.width>cameraBefore.camera.width);
 assert(Math.abs((cameraBefore.camera.x+cameraBefore.camera.width*.24)-(cameraAfter.x+cameraAfter.width*.24))<2);
 assert(Math.abs((cameraBefore.camera.y+cameraBefore.camera.height*.38)-(cameraAfter.y+cameraAfter.height*.38))<2);
 await click('Вписать','.rdg-zoom');
 checks.push('Ctrl+wheel zoom stays anchored to the pointer; Fit restores graph bounds');

 const beforeFocus=JSON.stringify((await state()).layouts);
 await page.$eval('[data-entity-id="R1"]',n=>n.dispatchEvent(new MouseEvent('click',{bubbles:true})));
 await page.waitForFunction(()=>RDG_PORTABLE_EDITOR.view?.view?.spec?.kind==='focus');
 await idle();
 let focusState=await state();
 assert.equal(focusState.view.spec.id,'R1');
 assert.equal((await page.evaluate(()=>RDG_PORTABLE_EDITOR.session.screens
   .find(s=>s.id===RDG_PORTABLE_EDITOR.session.activeScreenId).viewTrail?.length)),1);
 const focusBefore=focusState.view.visual.positions.R1;
 assert(focusBefore,'R1 must be visible in its focus');
 const dragNode=await page.$('[data-entity-id="R1"]'),dragBox=await dragNode.boundingBox();
 assert(dragBox);
 await page.mouse.move(dragBox.x+dragBox.width*.35,dragBox.y+dragBox.height*.35);
 await page.mouse.down();await page.mouse.move(dragBox.x+dragBox.width*.35+90,dragBox.y+dragBox.height*.35+40,{steps:7});await page.mouse.up();
 await page.waitForFunction(()=>!!RDG_PORTABLE_EDITOR.session.screens
   .find(s=>s.id===RDG_PORTABLE_EDITOR.session.activeScreenId).spec.focusPositions?.R1);
 await idle();
 focusState=await state();
 assert.equal(JSON.stringify(focusState.layouts),beforeFocus,'Moving a focus card cannot change the process owner layout');
 assert.notDeepEqual(focusState.view.visual.positions.R1,focusBefore);
 await click('← Назад','.rdg-view-trail');
 assert.equal((await state()).view.spec.kind,'graph');
 assert.equal((await state()).view.spec.compactGraph,true);
 assert.equal(JSON.stringify((await state()).layouts),beforeFocus);
 await page.$eval('[data-entity-id="R1"]',n=>n.dispatchEvent(new MouseEvent('click',{bubbles:true})));
 await page.waitForFunction(()=>RDG_PORTABLE_EDITOR.view?.view?.spec?.kind==='focus');await idle();
 const reopened=await state();
 assert.deepEqual(reopened.view.visual.positions.R1,focusState.view.visual.positions.R1,
   'Returning to the same focus must restore its manually moved node');
 await click('Сбросить расположение','.rdg-zoom');
 assert.deepEqual((await state()).view.visual.positions.R1,focusBefore,
   'Reset must restore the compact focus placement');
 await click('← Назад','.rdg-view-trail');
 assert.equal(JSON.stringify((await state()).layouts),beforeFocus);
 checks.push('focus drag is session-local, survives reentry, resets independently, and Back preserves owner layout');
 const frame=await page.$eval('.rdg-decision',n=>({top:n.getBoundingClientRect().top,left:n.getBoundingClientRect().left,bottom:n.getBoundingClientRect().bottom}));assert.deepEqual(frame,{top:0,left:0,bottom:1000});checks.push('manual launch: fullscreen three-strip desktop, explicit Process Graph, no synthetic Working Graph owner');
 await page.screenshot({path:path.join(base,'initial-process.png'),fullPage:true});
  await api({method:'view_session',sessionId:(await page.evaluate(()=>RDG_PORTABLE_EDITOR.session.id))});requests.length=0;let started=Date.now();await click('☷ RDG Viewer');await click('Закрыть Explorer');timings.explorerRoundTripMs=Date.now()-started;assert(requests.every(m=>m==='view_session'),JSON.stringify(requests));requests.length=0;started=Date.now();await click('Сведения','.rdg-tools');await click('Закрыть сведения');timings.inspectorRoundTripMs=Date.now()-started;assert(requests.every(m=>m==='view_session'),JSON.stringify(requests));requests.length=0;started=Date.now();await page.click('[data-entity-id="R1"]');await idle();timings.focusMs=Date.now()-started;assert.equal(requests.filter(m=>m==='read').length,1);assert(!requests.some(m=>['catalog','recommendation_catalog'].includes(m)),JSON.stringify(requests));await click('Весь процесс','.rdg-tools');await click('Закрыть сведения');checks.push('Explorer and inspector use view-state requests only; focus reads one current Graph without catalog rescans');
 await click('☷ RDG Viewer');const canvasBefore=await page.$eval('.rdg-canvas',n=>n.getBoundingClientRect().width);assert.equal(await page.$$eval('.rdg-tree-process[data-process-id="'+processId+'"]',a=>a.length),1);assert((await page.$eval('.rdg-tree-process[data-process-id="'+processId+'"]',n=>n.textContent)).includes('Рабочих областей пока нет'));
 await page.$eval('[data-package-id="'+processId+'"]',n=>{
   const button=[...n.parentElement.querySelectorAll('button')].find(b=>b.textContent.trim()==='+ Новая рабочая область');
   if(!button)throw Error('Process-specific add Working Graph not found');button.click();
 });await idle();await field('Название области','Подготовка окружения');await field('Основание','Нужна область для подготовки и проверки');await click('Проверить область');await save();let view=await state();const area1=view.graph.workGraphs[0];assert.equal(view.package.packageId,processId);assert.equal(view.view.spec.kind,'workGraph');assert.equal(view.view.spec.id,area1.id);assert.equal(await page.$eval('.rdg-canvas',n=>n.getBoundingClientRect().width),canvasBefore);assert(await page.$('.rdg-scope[data-workgraph-id="'+area1.id+'"]'));assert((await page.$eval('.rdg-road-head p',n=>n.textContent)).includes(first.graph.title));assert((await page.$eval('.rdg-tab[aria-selected=true] small',n=>n.textContent)).includes(area1.title));checks.push('Explorer creates nested Working Graph, opens it, preserves the owning process and common Plan / History');
 await click('Закрыть Explorer');
 await click('+ Блок','.rdg-tools');await field('Название','Проверить запуск');await field('Описание','Выбрать способ проверки запуска');await field('Основание изменения','Создание внутри рабочей области');await click('Добавить блок','.rdg-modal');await save();view=await state();const decision=view.graph.nodes.find(n=>n.title==='Проверить запуск');assert(decision);assert(view.graph.workGraphs[0].memberIds.includes(decision.id));
 await click('Весь процесс','.rdg-tools');await click('Рабочая область','.rdg-tools');await field('Название области','Проверка сценариев');await field('Проверить запуск',true);await field('Основание','Пересекающаяся область по ссылкам на блоки');await click('Проверить область');await save();view=await state();const area2=view.graph.workGraphs.find(w=>w.title==='Проверка сценариев');assert(area2);assert.equal(view.graph.nodes.filter(n=>n.id===decision.id).length,1);assert(view.graph.workGraphs.every(w=>w.memberIds.includes(decision.id)));const areaMarks=await page.$eval('.rdg-node[data-entity-id="'+decision.id+'"]',n=>({
  areas:[...n.querySelectorAll('.rdg-node-area-marker')].map(m=>m.dataset.workgraphId),
  outlined:n.querySelectorAll('rect[data-workgraph-id]:not(.rdg-node-area-marker)').length,
  markers:[...n.querySelectorAll('.rdg-node-area-marker')].map(m=>({x:Number(m.getAttribute('x')),y:Number(m.getAttribute('y'))})),
  border:n.querySelector('.rdg-node-border').getBoundingClientRect().toJSON(),
  markerRects:[...n.querySelectorAll('.rdg-node-area-marker')].map(m=>m.getBoundingClientRect().toJSON()),
  markerPaintOrder:[...n.querySelectorAll('.rdg-node-area-marker')].map(m=>
   [...n.children].indexOf(m)>[...n.children].indexOf(n.querySelector('.rdg-node-border')))
 }));
 assert.deepEqual(areaMarks.areas.sort(),[area1.id,area2.id].sort(),
  'the same Decision displays both overlapping work area markers');
 assert.equal(areaMarks.outlined,0,'the work area must not draw a second outline around the entity');
 assert(areaMarks.markerPaintOrder.every(Boolean),
   'SVG membership rectangles must be painted after opaque entity fills, otherwise all color markers disappear');
 assert(areaMarks.markers.every(p=>p.x>190&&p.x<220&&p.y>=0&&p.y<100));
 assert(areaMarks.markerRects.every(r=>r.left>=areaMarks.border.left-2&&r.right<=areaMarks.border.right+2
  &&r.top>=areaMarks.border.top-2&&r.bottom<=areaMarks.border.bottom+2),
  'work area markers are inside the semantic entity card');
 assert(areaMarks.markerRects.every(r=>r.width>=5&&r.height>=8),
   'color bars remain visible as compact rectangles even in the scaled-down overview');
 const markPaint=await page.$eval('.rdg-node[data-entity-id="'+decision.id+'"]',n=>{
  const border=[...n.children].indexOf(n.querySelector('.rdg-node-border'));
  return [...n.querySelectorAll('.rdg-node-area-marker')].map(m=>({
   fill:m.getAttribute('fill'),aboveBorder:[...n.children].indexOf(m)>border,
   height:Number(m.getAttribute('height')),width:Number(m.getAttribute('width'))
  }));
 });
 assert(markPaint.every(m=>m.aboveBorder&&m.width===10&&m.height>=13&&/^#[0-9a-f]{6}$/i.test(m.fill)),
  'membership rectangles are opaque, correctly colored and painted over the entity fill');
 await page.screenshot({path:path.join(base,'graph-workarea-visible-markers.png'),fullPage:true});
 checks.push('overlapping areas share Decision identity and display distinct visible painted color markers inside Graph, not outlines');
 await click('Добавить план во времени');await save();await click('+ Размещение','.rdg-tools');await field('Разместить блок',decision.id);await click('Проверить размещение','.rdg-modal');await save();const plan=JSON.stringify((await state()).plan);
 const ownerBeforeRoad=await api({method:'read',packageId:processId,includePlan:true});
 await click('Настройки временной дороги','.rdg-road-head-actions');
 assert.equal(await page.$$eval('[data-road-popover=settings] input[type=range]',a=>a.length),9);
 await page.$eval('[data-road-setting=centerWidth]',n=>{n.value='300';n.dispatchEvent(new Event('input',{bubbles:true}));});
 assert.equal((await page.$eval('.rdg-road',n=>n.style.getPropertyValue('--road-center-width'))),'300px');
 await field('Индикатор связи с Plan','label','.rdg-road-flyout');
 assert(await page.$('.rdg-road-label.planned'));
 await click('Сбросить настройки','.rdg-road-flyout');
 assert.equal((await page.$eval('.rdg-road',n=>n.style.getPropertyValue('--road-center-width'))),'220px');
 await click('Закрыть панель','.rdg-road-flyout');
 await click('Границы показа','.rdg-road-head-actions');
 assert.equal(await page.$$eval('[data-road-popover=windows] fieldset',a=>a.length),2);
 assert.equal(await page.$$eval('[data-road-popover=windows] .rdg-calendar',a=>a.length),2);
 const windows=await page.evaluate(()=>{const today=new Date(),iso=[today.getFullYear(),String(today.getMonth()+1).padStart(2,'0'),String(today.getDate()).padStart(2,'0')].join('-');
  const previous=new Date(iso+'T12:00:00Z');previous.setUTCDate(previous.getUTCDate()-1);
  return {today:iso,yesterday:previous.toISOString().slice(0,10)};});
 const editDate=iso=>iso.slice(8,10)+'.'+iso.slice(5,7)+'.'+iso.slice(0,4);
 const chooseDate=async(kind,edge,day)=>page.$eval('[data-road-bound="'+kind+'.'+edge+'"]',(n,value)=>{n.value=value;n.dispatchEvent(new Event('input',{bubbles:true}));},editDate(day));
 await chooseDate('historyWindow','from',windows.yesterday);await chooseDate('historyWindow','to',windows.yesterday);
 await click('Применить History','.rdg-road-flyout');
 assert.deepEqual((await state()).view.spec.historyWindow,{from:windows.yesterday,to:windows.yesterday});
 assert.equal(await page.$$eval('[data-road=history] [data-event-id]',a=>a.length),0);
 assert((await page.$$eval('[data-road=plan] [data-placement-id]',a=>a.length))>0,
   'Undated placements must remain visible when History is filtered');
 await chooseDate('planWindow','from',windows.today);await chooseDate('planWindow','to','31.02.2026');
 await click('Применить Plan','.rdg-road-flyout');
 assert(await page.$('[data-road-popover=windows] [role=alert]'),'Calendar must reject impossible dates');
 assert.equal((await state()).view.spec.planWindow,undefined,'Invalid Plan window cannot be accepted');
 await chooseDate('planWindow','to',windows.today);await click('Применить Plan','.rdg-road-flyout');
 assert.deepEqual((await state()).view.spec.planWindow,{from:windows.today,to:windows.today});
 assert((await page.$$eval('[data-road=plan] [data-placement-id]',a=>a.length))>0);
 await click('Закрыть панель','.rdg-road-flyout');
 const ownerAfterRoad=await api({method:'read',packageId:processId,includePlan:true});
 for(const key of ['graph','plan','layouts'])assert.deepEqual(ownerAfterRoad[key],ownerBeforeRoad[key]);
 checks.push('prototype Plan/History parity: nine road controls, badge mode, inline two calendars, inclusive windows, invalid-date guard, undated steps, no owner writes');
 await field('Область',area1.id,'.rdg-tools');assert.equal(JSON.stringify((await state()).plan),plan);assert.equal((await state()).view.graphKey,view.view.graphKey);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:RDG_PORTABLE_EDITOR.view.graph.rootRequirementId}),processId);await idle();await click('+ Блок','.rdg-tools');await field('Новый блок','requirement');await field('Название','Отдельная цель процесса');await field('Описание','Цель вне двух рабочих областей');await field('Основание изменения','Создание в процессе, не в области');await click('Добавить блок');await save();const outside=(await state()).graph.nodes.find(n=>n.title==='Отдельная цель процесса');assert(outside);assert((await state()).graph.workGraphs.every(w=>!w.memberIds.includes(outside.id)));checks.push('Plan / History and layout key belong to process; whole-process authoring does not alter existing area membership');
 await field('Область',area1.id,'.rdg-tools');await click('Внешние связи · 1');await click(outside.title,'.rdg-inspector');assert.equal((await state()).view.spec.id,outside.id);assert.equal((await state()).view.spec.workGraphId,area1.id);assert.equal(await page.$eval('[data-entity-id="'+outside.id+'"]',n=>n.dataset.outsideWorkgraph),'true');assert((await state()).graph.workGraphs.every(w=>!w.memberIds.includes(outside.id)));await click('Закрыть сведения');await field('Область',area1.id,'.rdg-tools');checks.push('external focus shows the real process block outside WG without changing area membership');await click('Вписать','.rdg-tools');await click('К границе');await click('☷ RDG Viewer');await page.screenshot({path:path.join(base,'process-and-working-areas.png'),fullPage:true});await click('Закрыть Explorer');await page.screenshot({path:path.join(base,'working-area-road.png'),fullPage:true});
 const frameBoxes=await page.$$eval('.rdg-head,.rdg-tabs,.rdg-tools,.rdg-status',nodes=>nodes.map(n=>({y:n.getBoundingClientRect().y,height:n.getBoundingClientRect().height})));assert(frameBoxes[2].height<=44);assert.equal(await page.$$eval('.rdg-road-scroll > [data-road],.rdg-road-scroll > .rdg-now',nodes=>nodes.map(n=>n.dataset.road||'now').join(',')),'history,now,plan');
 for(const width of [1024,1280,1440]){await page.setViewport({width,height:1000});const geometry=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth,canvas:document.querySelector('.rdg-canvas').getBoundingClientRect().width,road:document.querySelector('.rdg-road').getBoundingClientRect().width}));assert(geometry.scroll<=geometry.width,JSON.stringify(geometry));assert(geometry.canvas>=260&&geometry.road>=300,JSON.stringify(geometry));await page.screenshot({path:path.join(base,'desktop-'+width+'.png'),fullPage:true});}checks.push('reference desktop structure: compact strips, overlay Explorer, shared canvas and one History → now → Plan road at 1024 / 1280 / 1440');
 await click('☷ RDG Viewer');await click('+ Создать процесс','.rdg-explorer');await field('Название','Второй самостоятельный процесс');await field('Назначение процесса','Проверка навигации между процессами');await field('Основание процесса','Отдельная цель ручной проверки');await click('Проверить создание');await save();const second=await state();assert.notEqual(second.package.packageId,processId);assert.equal(second.graph.title,'Второй самостоятельный процесс');assert.equal(second.graph.workGraphs.length,0);assert.equal(second.plan,null);assert.equal(await page.$$eval('.rdg-tree-process',a=>a.length),3);assert.equal((await api({method:'catalog'})).packages.filter(p=>p.role==='lens').length,0);checks.push('create process opens its own Process Graph; two processes are distinct owners, Working Graph stays an inner scope');
 const stored=await api({method:'read',packageId:processId,includePlan:true});assert.equal(stored.graph.workGraphs.length,2);assert.equal(JSON.stringify(stored.plan),plan);await page.reload({waitUntil:'load'});await page.waitForSelector('.rdg-explorer-home .rdg-tree-process');await idle();assert.equal(await state(),null);assert.equal(await page.$('.rdg-graph'),null);await click(stored.graph.title,'.rdg-explorer');await idle();assert.deepEqual((await state()).graph,stored.graph);assert.deepEqual((await state()).plan,stored.plan);checks.push('reload returns to full-window Explorer; explicit selection reads the same process / overlapping areas / Plan');
 await click('Закрыть вкладку','.rdg-tabs');assert.equal(await state(),null);assert(await page.$('.rdg-explorer-home'));assert.deepEqual((await api({method:'read',packageId:processId,includePlan:true})).graph,stored.graph);await click('+ Создать процесс','.rdg-explorer');await field('Название','Создан из стартового Explorer');await field('Назначение процесса','Проверка пустого экрана');await field('Основание процесса','Явно создать выбранный процесс');await click('Проверить создание');assert.equal(await state(),null);await save();assert.equal((await state()).graph.title,'Создан из стартового Explorer');assert.equal(await page.$('.rdg-explorer-home'),null);checks.push('closing the last tab returns to Explorer; create/preflight/Save works without a selected graph');
 // Application→browser editor→focus roundtrip on an isolated process.
 // Process context is references to existing blocks, not cloned entities or
 // dependency edges, and never leaks into the original demo owner.
 const write=async request=>{const preview=await api({method:'preflight',request});
  assert.equal(preview.accepted,false);return api({method:'apply',request,expectedInputBinding:preview.inputBinding});};
 const contextCreate=(await api({method:'schema',op:'create'})).request;
 Object.assign(contextCreate,{role:'working',path:'processes/decision-context-visual-smoke',
   title:'Decision context smoke',scope:'Synthetic context scenario',coreModel:'rdg-decision-v1',
   rootReason:'Explicit isolated graph'});
 const contextWrite=await write(contextCreate);assert(contextWrite.published);
 const contextId=contextWrite.packages[0].packageId;
 const addContextBlock=async entity=>{
   const request=(await api({method:'schema',op:'core',packageId:contextId,command:'add'})).request;
   Object.assign(request,{op:'core',command:'add',note:'Explicit context smoke setup',
     data:{entity,location:'graph'}});
   const result=await write(request);assert(result.published);
 };
 await addContextBlock({id:'CT1',kind:'context',title:'Existing process fact',
   description:'Actual observed condition',value:'This process needs the constraint'});
 await addContextBlock({id:'D1',kind:'decision',title:'Decision being evaluated',
   description:'Candidate choice'});
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'D1'}),contextId);
 await idle();
 assert.equal((await state()).view.visual.nodes.some(n=>n.entityId==='CT1'),false,
   'unrelated Context should not appear as a Decision-context reference');
 await page.$eval('[data-entity-id="D1"]',n=>n.dispatchEvent(new MouseEvent('click',{bubbles:true})));
 await idle();
 assert((await page.$eval('.rdg-inspector',n=>n.textContent)).includes('Контекст принятия решения'));
 await click('Изменить контекст решения','.rdg-inspector');
 await field('Контекст процесса · Existing process fact',true);
 await field('Роль · Existing process fact','Material condition for this choice');
 await field('Основание изменения','Relate existing process fact to this Decision');
 await click('Проверить ссылки','.rdg-modal');
 await save();
 const contextAfter=await state();
 assert.deepEqual(contextAfter.graph.nodes.find(n=>n.id==='D1').decisionContextIds,['CT1']);
 assert.equal(contextAfter.graph.objects.filter(n=>n.id==='CT1').length,1);
 assert.equal(contextAfter.graph.edges.length,0,'no artificial dependency or D→D edge');
 assert(contextAfter.view.visual.nodes.some(n=>n.entityId==='CT1'),
   'Decision focus should show the existing process Context by reference');
 assert(contextAfter.view.visual.positions.CT1.x<contextAfter.view.visual.positions.D1.x,
   'Factual context should appear before the Decision, not among its children');
 assert((await page.$eval('.rdg-inspector',n=>n.textContent)).includes('Existing process fact'));
 await page.$eval('.rdg-inspector .rdg-entity-reference[data-kind="context"]',n=>n.click());await idle();
 assert.equal((await state()).view.spec.id,'D1','opening a process Ctx reference does not change the Decision focus');
 assert.equal(await page.$eval('.rdg-context-bank',n=>n.dataset.packageId),contextId);
 assert.equal(await page.$eval('.rdg-context-bank-item[data-context-id="CT1"]',n=>n.getAttribute('aria-pressed')),'true');
 assert((await page.$eval('.rdg-context-bank-entry',n=>n.textContent)).includes('This process needs the constraint'));
 assert(await page.$eval('.rdg-context-bank-entry',n=>n.textContent.includes('Decision being evaluated')));
 await page.screenshot({path:path.join(base,'process-context-bank-from-decision.png'),fullPage:true});
 // Bank ownership is process-wide: it must be identical from a focus and from
 // whole-process view, without creating a graph image or a duplicate entity.
 const bankBefore=await api({method:'read',packageId:contextId});
 await click('Закрыть банк контекстов','.rdg-context-bank');
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),contextId);await idle();
 assert.equal(await page.$$eval('.rdg-node[data-entity-id="CT1"]',n=>n.length),0);
 await click('Структура','.rdg-presentation-modes');
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="CT1"]',n=>n.length),0,
  'the process bank Ctx must not be displayed as a Structure row');
 assert.equal(await page.$$eval('.rdg-outline-row[data-outline-section="context"]',n=>n.length),0,
  'there is no orphan process-context type envelope');
 await click('Граф','.rdg-presentation-modes');
 const bankToggleButtons=await page.$$eval('.rdg-tools button',nodes=>nodes.map(n=>n.textContent));
 assert.equal(bankToggleButtons.indexOf('Контекст процесса'),bankToggleButtons.indexOf('Весь процесс')+1,
  'the process-wide bank control appears next to the Whole Process button');
 await click('Контекст процесса','.rdg-tools');
 assert.equal(await page.$eval('.rdg-context-bank',n=>n.dataset.packageId),contextId);
 assert.equal(await page.$$eval('.rdg-context-bank-item[data-context-id="CT1"]',n=>n.length),1);
 assert.deepEqual((await api({method:'read',packageId:contextId})).graph,bankBefore.graph,
  'opening the bank never mutates the canonical process owner');
 // An older saved direct Ctx focus must recover into the bank, not create an
 // empty isolated graph or silently move its one true process-owned record.
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'CT1'}),contextId);await idle();
 assert.equal((await state()).view.spec.kind,'graph','legacy Ctx focus is routed to the whole process');
 assert.equal(await page.$eval('.rdg-context-bank-item[data-context-id="CT1"]',n=>n.getAttribute('aria-pressed')),'true');
 // Even when an old Working Graph membership includes Ctx, the bank holds
 // the same fact once and the Working Graph shows only structural blocks.
 const wgReq=(await api({method:'schema',op:'core',packageId:contextId,command:'work_graph'})).request;
 wgReq.note='Process context bank belongs above WorkGraph boundaries';
 wgReq.data={workGraph:{id:'WG-BANK',title:'Область для проверки банка',rootIds:['R1'],
  memberIds:['R1','D1','CT1']}};
 await writeExample(wgReq);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'workGraph',id:'WG-BANK'}),contextId);await idle();
 assert.equal(await page.$$eval('.rdg-node[data-entity-id="CT1"]',n=>n.length),0);
 await click('Структура','.rdg-presentation-modes');
 assert.equal(await page.$$eval('.rdg-outline-row[data-entity-id="CT1"]',n=>n.length),0);
 await click('Граф','.rdg-presentation-modes');
 if(!await page.$('.rdg-context-bank'))await click('Контекст процесса','.rdg-tools');
 assert.equal(await page.$$eval('.rdg-context-bank-item[data-context-id="CT1"]',n=>n.length),1);
 assert.equal((await api({method:'read',packageId:contextId})).graph.workGraphs.find(w=>w.id==='WG-BANK').memberIds.includes('CT1'),true,
  'presentation filtering never changes real membership in the owning Process Graph');
 // Create a real context through the existing core add/preflight/apply writer,
 // with no parent, workGraph membership, new view kind or independent store.
 await click('Добавить контекст процесса','.rdg-context-bank');
 assert((await page.$eval('.rdg-modal',n=>n.textContent)).includes('всего Process Graph'));
 assert.equal(await page.$eval('.rdg-modal',n=>n.getAttribute('aria-label')),'Новый контекст процесса');
 assert.equal(await page.$$eval('.rdg-modal select',nodes=>nodes.length),1,
  'creating a process fact asks only for an organizational group, no graph kind/action/structural parent');
 assert.equal(await page.$eval('.rdg-modal select',n=>n.closest('label').firstChild.textContent.trim()),'Группа');
 await field('Название','Факт из банка');
 await field('Описание','Новая фактическая информация');
 await field('Содержание','Значение отдельного факта');
 await field('Основание изменения','Добавить факт всего процесса');
 await click('Добавить контекст','.rdg-modal');await save();
 let withBank=await api({method:'read',packageId:contextId});
 const createdContext=withBank.graph.objects.find(n=>n.title==='Факт из банка');
 assert(createdContext&&createdContext.kind==='context'&&createdContext.value==='Значение отдельного факта');
 assert(!withBank.graph.workGraphs.some(w=>w.memberIds.includes(createdContext.id)));
 assert(!withBank.graph.edges.some(e=>e.from===createdContext.id||e.to===createdContext.id),
  'context bank creation does not invent a graph relation');
 assert.equal(await page.$eval('.rdg-context-bank-entry',n=>n.dataset.contextId),createdContext.id,
  'the bank opens the newly created canonical object after readback');
 assert.equal(await page.$$eval('.rdg-node[data-entity-id="'+createdContext.id+'"]',n=>n.length),0);
 await click('Изменить содержание','.rdg-context-bank-entry');
 await field('Содержание','Обновлённое значение');
 await field('Основание изменения','Правка существующего Ctx');
 await click('Проверить содержание','.rdg-modal');await save();
 withBank=await api({method:'read',packageId:contextId});
 assert.equal(withBank.graph.objects.find(n=>n.id===createdContext.id)?.value,'Обновлённое значение');
 assert((await page.$eval('.rdg-context-bank-entry',n=>n.textContent)).includes('Обновлённое значение'));
 await page.screenshot({path:path.join(base,'process-context-bank-editor.png'),fullPage:true});
 await click('Удалить','.rdg-context-bank-entry');
 await field('Основание / наблюдение','Удалить изолированный тестовый контекст');
 await click('Проверить действие','.rdg-modal');await save();
 withBank=await api({method:'read',packageId:contextId});
 assert(!withBank.graph.objects.some(n=>n.id===createdContext.id));
 assert.equal(withBank.graph.objects.filter(n=>n.id==='CT1').length,1,
  'deletion of one fact does not delete another or alter decision links');
 assert.deepEqual(withBank.graph.nodes.find(n=>n.id==='D1').decisionContextIds,['CT1']);
 // Search navigates process-owned facts, without changing the active graph.
 await page.$eval('.rdg-context-bank-search input',n=>{n.value='существующий';n.dispatchEvent(new Event('input',{bubbles:true}));});
 assert.equal(await page.$$eval('.rdg-context-bank-item',n=>n.length),0);
 await page.$eval('.rdg-context-bank-search input',n=>{n.value='Existing';n.dispatchEvent(new Event('input',{bubbles:true}));});
 assert.equal(await page.$$eval('.rdg-context-bank-item',n=>n.length),1);
 await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'graph'}),originalProcessId);await idle();
 checks.push('process-wide context bank beside Whole Process: read-only overview, linked Decision lookup, hidden Graph/Structure Ctx, create/edit/delete via core writer, search and stable identity');
 await findingAcceptance();
 await inheritedHistoryAcceptance();
 await temporalPlanAcceptance();
  referenceServer=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');res.end(fs.readFileSync(path.join(ROOT,'tests/visual/rdg-ui-prototype.html')));});await new Promise(r=>referenceServer.listen(0,'127.0.0.1',r));const reference=page;await reference.setViewport({width:1440,height:1000});await reference.goto('http://127.0.0.1:'+referenceServer.address().port,{waitUntil:'load'});await reference.screenshot({path:path.join(base,'prototype-reference.png'),fullPage:true});assert.deepEqual(errors,[]);
 const result={pass:true,cases:checks.length,checks,timings,artifacts:base,windowsRuntimeVerified:false};fs.writeFileSync(path.join(base,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }catch(e){fs.writeFileSync(path.join(base,'failure.json'),JSON.stringify({error:safe(e),checks,errors},null,2));if(page)await page.screenshot({path:path.join(base,'failure.png'),fullPage:true}).catch(()=>{});console.error('Artifacts: '+base);throw e;}finally{if(referenceServer)await new Promise(r=>referenceServer.close(r));if(browser)await browser.close();if(child&&child.exitCode===null){const exit=new Promise(r=>child.once('exit',r));child.kill();await exit;}}})().catch(e=>{console.error(safe(e));process.exitCode=1;});
