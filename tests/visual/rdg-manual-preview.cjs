'use strict';
// Manual launcher, the real Viewer/transport/writer, and a disposable native key.
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs'),path=require('node:path');
const {spawn,spawnSync}=require('node:child_process'),readline=require('node:readline');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const ROOT=path.resolve(__dirname,'../..'),PYTHON=process.env.RDG_WEBAUTHN_PYTHON||'/workspace/repo/.rdg-webauthn-venv/bin/python';
const canonical=value=>Array.isArray(value)?'['+value.map(canonical).join(',')+']':value&&typeof value==='object'?'{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}':JSON.stringify(value);
const digest=value=>crypto.createHash('sha256').update(canonical(value)).digest('hex');
const env={...process.env,PYTHONDONTWRITEBYTECODE:'1',PYTHONNOUSERSITE:'1'};
for(const key of Object.keys(env))if(key.startsWith('RDG_AUTH_'))delete env[key];
const checks=[];
(async()=>{
 let child,browser,base=fs.mkdtempSync('/workspace/repo/rdg-manual-preview-test-'),stderr='';
 const data=path.join(base,'data');
 async function start(){
  return new Promise((resolve,reject)=>{
   stderr='';child=spawn(PYTHON,['-B','-u',path.join(ROOT,'tools/rdg-preview.py'),'--test-preview','--data-dir',data],{env,stdio:['ignore','pipe','pipe']});
   const timer=setTimeout(()=>reject(Error('preview startup timeout: '+stderr.slice(-1500))),30000);
   child.stderr.on('data',x=>stderr+=x);child.once('error',reject);
   child.once('exit',code=>{if(code){clearTimeout(timer);reject(Error('preview exit '+code+': '+stderr.slice(-1500)));}});
   readline.createInterface({input:child.stdout}).on('line',line=>{
    if(line.startsWith('{"url":')){clearTimeout(timer);resolve(JSON.parse(line));}
   });
  });
 }
 async function stop(){
  if(child&&child.exitCode===null){const closed=new Promise(r=>child.once('exit',r));child.kill();await closed;}
 }
 try{
  let ready=await start();assert.equal(ready.previewOnly,true);assert.equal(ready.osIsolationVerified,false);
  browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,headless:true,
   userDataDir:path.join(base,'browser'),args:['--no-sandbox','--disable-dev-shm-usage'],env});
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewport({width:1280,height:940});
  const cdp=await page.createCDPSession();await cdp.send('WebAuthn.enable',{enableUI:false});
  await cdp.send('WebAuthn.addVirtualAuthenticator',{options:{protocol:'ctap2',transport:'internal',
   hasResidentKey:true,hasUserVerification:true,isUserVerified:true,automaticPresenceSimulation:true}});
  const visit=async()=>{await page.goto(ready.url,{waitUntil:'load'});
   await page.waitForFunction(()=>globalThis.RDG_PORTABLE_EDITOR&&document.querySelectorAll('[data-approval-request]').length>=2);};
  const click=async text=>{
   const h=await page.evaluateHandle(t=>[...document.querySelectorAll('.rp-approvals button')].find(b=>b.textContent===t),text);
   const button=h.asElement();assert(button,'button missing: '+text);await button.click();await h.dispose();
   await page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy);
  };
  const api=async message=>page.evaluate(async message=>{
   const res=await fetch('command',{method:'POST',headers:{'Content-Type':'application/json','X-RDG-Session':RDG_SESSION},body:JSON.stringify(message)});
   const body=await res.json();if(body.error)throw Error(body.error);return body;
  },message);
  const list=async()=>page.evaluate(async()=>{
   const res=await fetch('approval',{method:'POST',headers:{'Content-Type':'application/json','X-RDG-Session':RDG_SESSION},body:JSON.stringify({method:'list'})});return res.json();
  });
  const open=async item=>{
   await page.click('[data-approval-request="'+item.requestId+'"]');
   await page.waitForFunction(id=>!RDG_PORTABLE_EDITOR.busy&&
    RDG_PORTABLE_EDITOR.approval?.record.requestId===id&&RDG_PORTABLE_EDITOR.approval.previewAvailable,{},item.requestId);
   assert.equal(await page.$eval('[data-approval-request="'+item.requestId+'"]',n=>n.getAttribute('aria-pressed')),'true');
   assert.equal(await page.$eval('.rp-status',n=>n.classList.contains('rp-error')),false);
  };
  const clickText=async(selector,text)=>{
   const handle=await page.evaluateHandle(({selector,text})=>{
    const node=[...document.querySelectorAll(selector)].find(n=>n.textContent===text);
    if(!node)throw Error('element missing: '+text);
    return node;
   },{selector,text});
   const node=handle.asElement();assert(node,'element missing: '+text);await node.click();await handle.dispose();
  };
  const focusField=async(labelPrefix,selector='input')=>page.evaluate(({labelPrefix,selector})=>{
   const label=[...document.querySelectorAll('main label')].find(n=>n.textContent.trim().startsWith(labelPrefix));
   if(!label)throw Error('field missing: '+labelPrefix);
   const control=label.querySelector(selector);
   if(!control)throw Error('control missing: '+labelPrefix);
   control.focus();if(typeof control.select==='function')control.select();
  },{labelPrefix,selector});
  const typeField=async(labelPrefix,value,selector='input')=>{
   await focusField(labelPrefix,selector);await page.keyboard.type(value);
  };
  const packageByTitle=async title=>{
   const row=(await api({method:'catalog'})).packages.find(item=>item.title===title);
   assert(row,'package missing: '+title);return row;
  };
  const choosePackage=async row=>{
   await page.click('[data-package-id="'+row.packageId+'"]');
   await page.waitForFunction(id=>!RDG_PORTABLE_EDITOR.busy&&
    RDG_PORTABLE_EDITOR.view?.package?.packageId===id,{},row.packageId);
  };
  await visit();
  assert((await page.$eval('body',n=>n.textContent)).includes('Тестовый пример'));
  assert.equal((await api({method:'catalog'})).packages.length,4);
  await click('Зарегистрировать ключ');
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.enrollment.state),'completed');
  const shared=await packageByTitle('Общий критерий и зависимость');await choosePackage(shared);
  await clickText('main summary','Изменить Graph');await clickText('main summary','Нативные зависимости L1/L2');
  await page.evaluate(()=>{
   const control=(prefix,selector)=>{
    const label=[...document.querySelectorAll('main label')].find(node=>node.textContent.startsWith(prefix+' '));
    const input=label?.querySelector(selector);if(!input)throw Error('dependency control missing: '+prefix);return input;
   };
   control('Источник','select').value='C3';control('Зависимый блок','select').value='Y';control('Уровень','select').value='L2';
   control('Основание зависимости','textarea').value='Shared criterion has a direct semantic dependency';
  });
  const sharedBefore=await api({method:'dependencies',packageId:shared.packageId});assert.equal(sharedBefore.edges.length,0);
  await clickText('main button','Добавить L1/L2 зависимость');
  await page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy&&!!RDG_PORTABLE_EDITOR.pending);
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.pending.request.sourceId),'C3');
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.pending.request.dependentId),'Y');
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.pending.request.dependencyLevel),'L2');
  assert.equal((await api({method:'dependencies',packageId:shared.packageId})).edges.length,0);
  await clickText('.rdgp > section.rp-card:not(.rp-approvals) button','Сохранить');
  await page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy&&!RDG_PORTABLE_EDITOR.pending);
  const sharedAfter=await api({method:'dependencies',packageId:shared.packageId});
  assert.deepEqual(sharedAfter.edges.map(edge=>[edge.from,edge.to,edge.dependencyLevel]),[['C3','Y','L2']]);
  checks.push('portable Viewer adds a shared info → Requirement L2 dependency through preflight, then reads it back after Save');
  checks.push('launcher creates four disposable examples and registers a native key in the actual Viewer');
  const items=(await list()).requests,approve=items.find(r=>r.rationale.startsWith('Проверка подтверждения')),reject=items.find(r=>r.rationale.startsWith('Проверка отказа'));
  assert(approve&&reject);
  const registeredText=await page.$eval('[data-enrollment-state="completed"]',n=>n.textContent);
  assert.equal(registeredText.match(/Ключ зарегистрирован/g).length,1);
  const cards=await page.$$eval('[data-approval-request]',nodes=>nodes.map(n=>n.textContent));
  assert(cards.some(text=>text.includes('Согласовать план работ')));
  assert(cards.some(text=>text.includes('Сохранить исходный вариант')));
  assert(cards.every(text=>!text.includes(approve.targetPackageId)&&!text.includes(reject.targetPackageId)));
  let held,intercepted;
  const opening=new Promise(resolve=>intercepted=resolve);
  await page.setRequestInterception(true);
  const intercept=request=>{
   if(request.url().endsWith('/approval')&&request.method()==='POST'&&JSON.parse(request.postData()).method==='open'){
    held=request;intercepted();
   }else void request.continue();
  };
  page.on('request',intercept);
  try{
   await page.click('[data-approval-request="'+approve.requestId+'"]');await opening;
   assert((await page.$eval('.rp-approval-status',n=>n.textContent)).includes('Открываем запрос'));
   assert.equal(await page.$$eval('[data-approval-request]',nodes=>nodes.every(n=>n.disabled)),true);
   await held.respond({status:400,contentType:'application/json',body:JSON.stringify({error:'SYNTHETIC_OPEN_FAILURE',definite:true})});held=null;
   await page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy);
   assert((await page.$eval('.rp-approval-status',n=>n.textContent)).includes('Не удалось открыть запрос'));
   assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.approval),null);
   assert.equal(await page.$$eval('[data-approval-request]',nodes=>nodes.every(n=>!n.disabled)),true);
  }finally{
   if(held)await held.continue();
   await page.setRequestInterception(false);page.off('request',intercept);
  }
  checks.push('named request cards expose loading and local errors, then allow retry by a real click');
  await open(approve);
  const screenDir=process.env.RDG_SCREENSHOT_DIR||'/workspace/repo/rdg-visual-output';fs.mkdirSync(screenDir,{recursive:true});
  await page.screenshot({path:path.join(screenDir,'rdg-manual-preview.png')});
  await click('Подтвердить');
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.approval.record.state),'executed-approved');
  assert.equal((await api({method:'read',packageId:approve.targetPackageId})).graph.nodes[0].title,'Согласовать план после проверки пользователем');
  await open(reject);await click('Отклонить');
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.approval.record.state),'rejected');
  assert.equal((await api({method:'read',packageId:reject.targetPackageId})).graph.nodes[0].title,'Сохранить исходный вариант');
  checks.push('native Approve commits the common writer and Reject leaves the other Graph unchanged');
  const free=await packageByTitle('Свободная правка');await choosePackage(free);
  await clickText('main summary','Изменить Graph');
  const freeBefore=(await api({method:'read',packageId:free.packageId})).graph;
  const freeR1=freeBefore.nodes.find(node=>node.id==='R1');assert(freeR1);
  const ordinaryTitle='Free edit title after preflight',ordinaryDescription='Free edit description after preflight';
  await typeField('Основание изменения','Ordinary free edit reason','textarea');
  await typeField('Название',ordinaryTitle);
  await typeField('Описание',ordinaryDescription,'textarea');
  assert.equal(await page.$eval('main label input[type="checkbox"]',node=>node.checked),false);
  await clickText('main button','Изменить выбранный блок');
  await page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy&&!!RDG_PORTABLE_EDITOR.pending);
  const beforeSave=(await api({method:'read',packageId:free.packageId})).graph;
  assert.equal(beforeSave.nodes.find(node=>node.id==='R1').title,freeR1.title);
  assert((await page.$eval('.rdgp > section.rp-card:not(.rp-approvals)',node=>node.textContent)).includes('Предварительная проверка'));
  await clickText('.rdgp > section.rp-card:not(.rp-approvals) button','Сохранить');
  await page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy&&!RDG_PORTABLE_EDITOR.pending);
  let freeAfter=(await api({method:'read',packageId:free.packageId})).graph;
  assert.equal(freeAfter.nodes.find(node=>node.id==='R1').title,ordinaryTitle);
  assert.equal(freeAfter.nodes.find(node=>node.id==='R1').description,ordinaryDescription);
  checks.push('free edit uses the real form, leaves data unchanged during preflight, then saves through the common writer');
  await page.reload({waitUntil:'load'});await page.waitForFunction(()=>globalThis.RDG_PORTABLE_EDITOR&&document.querySelectorAll('[data-approval-request]').length>=2);
  await choosePackage(free);await clickText('main summary','Изменить Graph');
  const reloaded=(await api({method:'read',packageId:free.packageId})).graph;
  assert.equal(reloaded.nodes.find(node=>node.id==='R1').title,ordinaryTitle);
  assert.equal(await page.$eval('main label input[type="checkbox"]',node=>node.checked),false);
  const cosmeticTitle='Free cosmetic title',cosmeticDescription='Free cosmetic description';
  await typeField('Основание изменения','Cosmetic free edit reason','textarea');
  await typeField('Название',cosmeticTitle);
  await typeField('Описание',cosmeticDescription,'textarea');
  await page.click('main label input[type="checkbox"]');
  assert.equal(await page.$eval('main label input[type="checkbox"]',node=>node.checked),true);
  await clickText('main button','Изменить выбранный блок');
  await page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy&&!!RDG_PORTABLE_EDITOR.pending);
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.pending.request.data.cosmetic),true);
  assert((await page.$eval('.rdgp > section.rp-card:not(.rp-approvals)',node=>node.textContent)).includes('Косметическая правка'));
  const beforeCosmetic=(await api({method:'read',packageId:free.packageId})).graph;
  assert.equal(beforeCosmetic.nodes.find(node=>node.id==='R1').title,ordinaryTitle);
  await clickText('.rdgp > section.rp-card:not(.rp-approvals) button','Сохранить');
  await page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy&&!RDG_PORTABLE_EDITOR.pending);
  const cosmeticAfter=(await api({method:'read',packageId:free.packageId})).graph;
  const cosmeticEvent=cosmeticAfter.events.find(event=>event.cosmetic===true);
  assert(cosmeticEvent,'cosmetic audit event missing');
  assert.equal(cosmeticEvent.before.R1.title,ordinaryTitle);
  assert.equal(cosmeticEvent.after.R1.title,cosmeticTitle);
  assert.equal(cosmeticAfter.nodes.find(node=>node.id==='R1').description,cosmeticDescription);
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.view.plan!==null),true);
  await clickText('main summary','План во времени');
  await clickText('main summary','История Graph и версии Plan');
  await clickText('main button','Прочитать историю');
  await page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy&&document.querySelector('main').textContent.includes('cosmetic'));
  checks.push('the same Viewer exposes the saved Plan and History, including the cosmetic audit event');
  checks.push('cosmetic marker is visible, default-off, included in preflight, and persisted in the audit event');
  const oldOrigin=new URL(ready.url).origin;await stop();ready=await start();
  assert.equal(new URL(ready.url).origin,oldOrigin);await visit();
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.enrollment),null);
  const restartedFree=(await api({method:'read',packageId:free.packageId})).graph;
  assert.equal(restartedFree.nodes.find(node=>node.id==='R1').title,cosmeticTitle);
  assert.equal(restartedFree.nodes.find(node=>node.id==='R1').description,cosmeticDescription);
  checks.push('free edit survives page reload and preview process restart with the same data and origin');
  const current=await api({method:'read',packageId:approve.targetPackageId});
  const request={op:'core',transactionId:crypto.randomUUID(),targetPackageId:approve.targetPackageId,
   expectedPackageRevision:current.package.revision,expectedGraphRevision:current.graph.revision,
   command:'edit',data:{nodeId:'R1',changes:{title:'Повторная правка после перезапуска'}},note:'Проверка restart'};
  const proposed=await api({method:'approval_request',request,rationale:'Проверка нового подтверждения после restart'});
  await click('Обновить запросы');await open({requestId:proposed.requestId});await click('Подтвердить');
  const createApprovalRequest={op:'create',transactionId:crypto.randomUUID(),path:'working/browser-approved-create',
   role:'working',title:'Browser approved create',scope:'Synthetic browser approval'};
  const proposedCreate=await api({method:'approval_request',request:createApprovalRequest,
   rationale:'Browser targetless create approval'});
  await click('Обновить запросы');await open({requestId:proposedCreate.requestId});
  const createdPackageId=await page.evaluate(()=>RDG_PORTABLE_EDITOR.approval.preview.owners[0].packageId);
  await click('Подтвердить');
  const createdPackage=await api({method:'read',packageId:createdPackageId});
  assert.equal(createdPackage.package.role,'working');
  assert.equal(createdPackage.graph.title,'Browser approved create');
  const sourceForCopy=await api({method:'read',packageId:free.packageId});
  const copyApprovalRequest={op:'copy',transactionId:crypto.randomUUID(),sourcePackageId:free.packageId,
   sourcePin:{revision:sourceForCopy.package.revision,sha256:digest(sourceForCopy.graph)},
   focus:{kind:'graph'},includeDescendants:true,path:'copies/browser-approved-copy',
   note:'Browser targetless copy approval'};
  const proposedCopy=await api({method:'approval_request',request:copyApprovalRequest,
   rationale:'Browser targetless copy approval'});
  await click('Обновить запросы');await open({requestId:proposedCopy.requestId});
  const copiedPackageId=await page.evaluate(()=>RDG_PORTABLE_EDITOR.approval.preview.owners[0].packageId);
  await click('Подтвердить');
  const copiedPackage=await api({method:'read',packageId:copiedPackageId});
  assert.equal(copiedPackage.package.role,'copy');
  assert.equal(copiedPackage.graph.title,sourceForCopy.graph.title);
  checks.push('Viewer approval creates and copies new packages without an existing target');
  const foreign=path.join(base,'foreign');fs.mkdirSync(foreign);fs.writeFileSync(path.join(foreign,'keep.txt'),'keep');
  const refused=spawnSync(PYTHON,['-B',path.join(ROOT,'tools/rdg-preview.py'),'--test-preview','--data-dir',foreign],{env,encoding:'utf8'});
  assert.notEqual(refused.status,0);assert(refused.stderr.includes('EXISTING_DATA_REFUSED'));
  assert.equal(fs.readFileSync(path.join(foreign,'keep.txt'),'utf8'),'keep');
  checks.push('preview refuses existing unmarked data instead of initializing it');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({ok:true,cases:checks.length,checks,mainViewer:true,authenticator:'Chromium virtual CTAP2',realHumanProof:false,osIsolationVerified:false,liveOwnersTouched:false}));
 }finally{
  if(browser)await browser.close();await stop();fs.rmSync(base,{recursive:true,force:true});
 }
})().catch(e=>{console.error(String(e.stack||e).replace(/http:\/\/localhost:\d+\/session\/[^\s'"]+/g,'[preview session]'));process.exitCode=1;});
