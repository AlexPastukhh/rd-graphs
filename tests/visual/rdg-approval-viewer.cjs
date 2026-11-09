'use strict';
// Actual generated Viewer + actual Helper + native WebAuthn + shared writer.
// All credentials and owners are disposable synthetic fixtures.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const readline=require('node:readline'),{spawn}=require('node:child_process');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const ROOT=path.resolve(__dirname,'../..'),checks=[];
const PYTHON=process.env.RDG_WEBAUTHN_PYTHON||'/workspace/repo/.rdg-webauthn-venv/bin/python';
const env=Object.fromEntries(Object.entries(process.env).filter(([k])=>!k.startsWith('RDG_AUTH_')));
env.PYTHONDONTWRITEBYTECODE='1';env.PYTHONNOUSERSITE='1';
(async()=>{
 let bridge,browser,profile,stderr='';const pending=new Map();let serial=0;
 const query=(method,body={})=>new Promise((resolve,reject)=>{
  const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(Error('synthetic fixture timeout'));},30000);
  pending.set(id,value=>{clearTimeout(timer);resolve(value);});
  bridge.stdin.write(JSON.stringify({id,method,body})+'\n');
 });
 const must=async(method,body)=>{const reply=await query(method,body);assert.equal(reply.ok,true,reply.error);return reply.result;};
 try{
  bridge=spawn(PYTHON,['-B','-u',path.join(ROOT,'tests/rdg-approval-viewer-fixture.py'),'--synthetic-fixture'],
   {env,stdio:['pipe','pipe','pipe']});
  bridge.stderr.on('data',c=>{stderr+=c;});
  bridge.on('error',error=>{for(const done of pending.values())done({ok:false,error:error.message});pending.clear();});
  readline.createInterface({input:bridge.stdout}).on('line',line=>{
   const value=JSON.parse(line),done=pending.get(value.id);if(done){pending.delete(value.id);done(value);}
  });
  const config=await must('ready');assert.equal(config.realHumanProof,false);
  profile=fs.mkdtempSync('/workspace/repo/rdg-approval-viewer-browser-');
  browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,userDataDir:profile,
   headless:true,args:['--no-sandbox','--disable-dev-shm-usage'],env});
  const page=await browser.newPage(),pageErrors=[],dialogs=[];
  page.on('pageerror',e=>pageErrors.push(e.message));
  page.on('dialog',async d=>{dialogs.push(d.type());await d.dismiss();});
  await page.setViewport({width:1280,height:940});
  const cdp=await page.createCDPSession();await cdp.send('WebAuthn.enable',{enableUI:false});
  const {authenticatorId}=await cdp.send('WebAuthn.addVirtualAuthenticator',{options:{protocol:'ctap2',transport:'internal',
   hasResidentKey:true,hasUserVerification:true,isUserVerified:true,automaticPresenceSimulation:true}});
  await page.goto(config.url,{waitUntil:'load'});
  await page.waitForFunction(()=>globalThis.RDG_PORTABLE_EDITOR&&document.querySelector('.rp-status')?.textContent.includes('Каталог прочитан'));
  assert(await page.evaluate(()=>!!globalThis.RDGPortableUI&&!!globalThis.RDG_APPROVAL_AVAILABLE&&isSecureContext));
  checks.push('actual generated Viewer loads the configured approval surface through Helper');

  const registration=await must('register_begin');
  const response=await page.evaluate(async b=>(await navigator.credentials.create({
   publicKey:PublicKeyCredential.parseCreationOptionsFromJSON(b.options.publicKey)})).toJSON(),registration);
  assert.equal((await must('register_complete',{ceremonyId:registration.ceremonyId,response})).userVerified,true);
  await page.evaluate(()=>{
   const original=navigator.credentials.get.bind(navigator.credentials);window.nativeAssertions=0;
   navigator.credentials.get=options=>{window.nativeAssertions++;return original(options);};
  });
  checks.push('trusted fixture enrollment uses a native credential on the same Viewer origin');

  const click=async(text,within='.rp-approvals')=>{
   const handle=await page.evaluateHandle(({text,within})=>[...document.querySelectorAll(within+' button')].find(b=>b.textContent===text),{text,within});
   const element=handle.asElement();assert(element,'button missing: '+text);assert.equal(await element.evaluate(b=>b.disabled),false,text+' disabled');
   await element.click();await handle.dispose();
   await page.waitForFunction(()=>!globalThis.RDG_PORTABLE_EDITOR.busy,{timeout:30000});
  };
  const open=async setup=>{
   await click('Обновить запросы');
   await page.click('[data-approval-request="'+setup.requestId+'"]');
   await page.waitForFunction(id=>!RDG_PORTABLE_EDITOR.busy&&document.querySelector('[data-approval-current="'+id+'"]'),{},setup.requestId);
  };
  const state=()=>page.evaluate(()=>RDG_PORTABLE_EDITOR.approval?.record.state);
  const message=()=>page.$eval('.rp-approvals',n=>n.textContent);

  const edit=await must('setup',{scenario:'edit'});
  await click('Обновить каталог','.rp-bar');
  await page.click('.rp-catalog [data-package-id="'+edit.targetPackageId+'"]');
  await page.waitForFunction(id=>!RDG_PORTABLE_EDITOR.busy&&RDG_PORTABLE_EDITOR.view?.package.packageId===id,{},edit.targetPackageId);
  await open(edit);
  assert.equal(await page.$$eval('[data-approval-owner]',els=>els.length),1);
  assert((await message()).includes(edit.desiredTitle));
  assert((await message()).includes('Было')&&(await message()).includes('Станет'));
  assert.equal(await page.$$eval('.rp-approvals img',els=>els.length),0);
  assert.equal(await page.$$eval('.rp-diff tr td:first-child',els=>els.some(n=>n.textContent.includes('graph.events'))),false);
  assert.equal(await page.$$eval('[data-approval-audit]',els=>els.every(n=>!n.open)),true);
  assert.deepEqual(dialogs,[]);
  const before=await must('inspect',{requestId:edit.requestId});
  assert.equal(before.receipt.found,false);
  checks.push('main Viewer displays exact before/after rationale and all owners without interpreting request HTML');
  const screenDir=process.env.RDG_SCREENSHOT_DIR||'/workspace/repo/rdg-visual-output';
  fs.mkdirSync(screenDir,{recursive:true});
  await page.screenshot({path:path.join(screenDir,'rdg-approval-viewer-desktop.png')});
  await page.setViewport({width:430,height:900});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'mobile page overflows');
  await page.screenshot({path:path.join(screenDir,'rdg-approval-viewer-mobile.png')});
  await page.setViewport({width:1280,height:940});
  checks.push('approval comparison fits desktop and narrow mobile viewports');
  await click('Подтвердить');
  assert.equal(await state(),'executed-approved',await message());
  const after=await must('inspect',{requestId:edit.requestId});
  assert.equal(after.graph.nodes[0].title,edit.desiredTitle);
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.view.graph.nodes[0].title),edit.desiredTitle);
  assert(after.receipt.receipt.authorizationContext);
  checks.push('Approve button obtains native assertion and executes the protected operation');

  const rejected=await must('setup',{scenario:'reject'});await open(rejected);
  const beforeReject=await must('inspect',{requestId:rejected.requestId});
  await page.evaluate(()=>{
   window.creationParser=PublicKeyCredential.parseRequestOptionsFromJSON;
   window.credentialJSON=PublicKeyCredential.prototype.toJSON;
   PublicKeyCredential.parseRequestOptionsFromJSON=undefined;PublicKeyCredential.prototype.toJSON=undefined;
  });
  await click('Отклонить');
  await page.evaluate(()=>{PublicKeyCredential.parseRequestOptionsFromJSON=window.creationParser;PublicKeyCredential.prototype.toJSON=window.credentialJSON;});
  checks.push('native assertion works through the built-in JSON conversion fallback');
  assert.equal(await state(),'rejected',await message());
  const afterReject=await must('inspect',{requestId:rejected.requestId});
  assert.deepEqual(afterReject.graph,beforeReject.graph);assert.equal(afterReject.receipt.found,false);
  checks.push('Reject button records rejection without a Graph transaction');

  const cancelled=await must('setup',{scenario:'edit'});await open(cancelled);
  await cdp.send('WebAuthn.setAutomaticPresenceSimulation',{authenticatorId,enabled:false});
  await page.evaluate(()=>{
   window.nativeGet=navigator.credentials.get.bind(navigator.credentials);
   navigator.credentials.get=options=>{const control=new AbortController();setTimeout(()=>control.abort(),30);return window.nativeGet({...options,signal:control.signal});};
  });
  await click('Подтвердить');
  await page.evaluate(()=>{navigator.credentials.get=window.nativeGet;});
  await cdp.send('WebAuthn.setAutomaticPresenceSimulation',{authenticatorId,enabled:true});
  assert((await message()).includes('Подтверждение отменено в браузере'));
  assert.equal((await must('inspect',{requestId:cancelled.requestId})).receipt.found,false);
  checks.push('browser cancellation leaves the proposal pending without sending execution');

  const coupled=await must('setup',{scenario:'replace'});await open(coupled);
  assert.equal(await page.$$eval('[data-approval-owner]',els=>els.length),2);
  await must('add_plan',{requestId:coupled.requestId});
  const assertions=await page.evaluate(()=>window.nativeAssertions);
  await click('Подтвердить');
  assert.equal(await page.evaluate(()=>window.nativeAssertions),assertions);
  assert((await message()).includes('Данные изменились'));
  assert.equal((await must('inspect',{requestId:coupled.requestId})).receipt.found,false);
  checks.push('new P2 invalidates displayed consent before opening another WebAuthn prompt');
  await click('Обновить изменения');
  assert.equal(await page.$$eval('[data-approval-owner]',els=>els.length),3);
  await click('Подтвердить');assert.equal(await state(),'executed-approved',await message());
  assert.equal((await must('inspect',{requestId:coupled.requestId})).receipt.receipt.authorizationContext.approver.principalId,'synthetic-operator');
  checks.push('explicitly refreshed Viewer preview commits the Graph and both Plan effects');

  const stale=await must('setup',{scenario:'stale'});await open(stale);
  await must('change_target',{requestId:stale.requestId});
  const beforeStale=await page.evaluate(()=>window.nativeAssertions);
  await click('Подтвердить');
  assert.equal(await page.evaluate(()=>window.nativeAssertions),beforeStale);
  assert((await message()).includes('Инициатор должен подготовить новый запрос'));
  await click('Обновить изменения');
  assert((await message()).includes('Инициатор должен подготовить новый запрос'));
  assert.equal((await must('inspect',{requestId:stale.requestId})).receipt.found,false);
  checks.push('changed target revision requires a new request rather than repeated preview refresh');

  const crash=await must('setup',{scenario:'crash'});await open(crash);
  await click('Подтвердить');
  assert.equal(await state(),'approved-awaiting-recovery',await message());
  const signedBeforeRecovery=await page.evaluate(()=>window.nativeAssertions);
  await click('Завершить принятую операцию');
  assert.equal(await state(),'executed-approved',await message());
  assert.equal(await page.evaluate(()=>window.nativeAssertions),signedBeforeRecovery);
  assert.equal((await must('inspect',{requestId:crash.requestId})).graph.nodes[0].title,crash.desiredTitle);
  checks.push('main Viewer recovers an accepted transaction without a second consent');

  const dropped=await must('setup',{scenario:'drop'});await open(dropped);
  await click('Подтвердить');
  assert.equal(await state(),'executed-approved',await message());
  assert((await message()).includes('результат подтверждён чтением состояния'));
  const droppedState=await must('inspect',{requestId:dropped.requestId});
  assert.equal(droppedState.graph.nodes[0].title,dropped.desiredTitle);
  const signedAfterDrop=await page.evaluate(()=>window.nativeAssertions);
  await click('Прочитать состояние');
  assert.equal(await page.evaluate(()=>window.nativeAssertions),signedAfterDrop);
  checks.push('lost completion response is resolved by status read without replaying consent');

  const base=new URL(config.url),session=base.pathname.split('/').filter(Boolean).at(-1);
  const rpc=async(body,origin=base.origin)=>{
   const r=await fetch(new URL('approval',base),{method:'POST',headers:{'Content-Type':'application/json','Origin':origin,'X-RDG-Session':session},body:JSON.stringify(body)});
   return {status:r.status,body:await r.json()};
  };
  assert.notEqual((await rpc({method:'list'},'https://invalid.example')).status,200);
  assert.notEqual((await rpc({method:'choose',viewId:'fake',decision:'approve',principalId:'synthetic-operator'})).status,200);
  checks.push('actual Helper rejects foreign origin and client actor claims');

  const barePage=await browser.newPage();await barePage.goto(config.bareUrl,{waitUntil:'load'});
  await barePage.waitForSelector('.rp-approvals');
  assert((await barePage.$eval('.rp-approvals',n=>n.textContent)).includes('Подтверждение недоступно'));
  assert.equal(await barePage.$$eval('.rp-approvals button',els=>els.length),0);
  await barePage.close();
  checks.push('ordinary Helper advertises no approval capability without trusted host configuration');

  const revoked=await must('setup',{scenario:'revoked'});await open(revoked);
  await must('revoke_executor');
  const signatures=await page.evaluate(()=>window.nativeAssertions);
  await click('Подтвердить');
  assert.equal(await page.evaluate(()=>window.nativeAssertions),signatures);
  assert.equal((await must('inspect',{requestId:revoked.requestId})).receipt.found,false);
  assert((await message()).includes('Право исполнения недоступно'));
  checks.push('revoked executor cannot prompt or execute the displayed request');
  assert.deepEqual(pageErrors,[]);assert.deepEqual(dialogs,[]);
  console.log(JSON.stringify({ok:true,cases:checks.length,checks,mainViewer:true,
   authenticator:'Chromium virtual CTAP2',realHumanProof:false,liveOwnersTouched:false,
   screenshots:['rdg-approval-viewer-desktop.png','rdg-approval-viewer-mobile.png']}));
 }catch(error){
  console.error(error.stack);if(stderr)console.error(stderr);process.exitCode=1;
 }finally{
  if(browser)await browser.close();
  if(bridge){bridge.stdin.end();await new Promise(resolve=>{if(bridge.exitCode!==null)return resolve();bridge.once('exit',resolve);setTimeout(()=>{bridge.kill('SIGTERM');resolve();},6000).unref();});}
  if(profile)fs.rmSync(profile,{recursive:true,force:true});
 }
})();
