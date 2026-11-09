'use strict';
// Actual Viewer registration, separate runtime processes and shared Authority.
// Synthetic credentials/owners only. This is not evidence of OS isolation.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const readline=require('node:readline'),{spawn}=require('node:child_process');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const ROOT=path.resolve(__dirname,'../..'),checks=[];
const PYTHON=process.env.RDG_WEBAUTHN_PYTHON||'/workspace/repo/.rdg-webauthn-venv/bin/python';
const env=Object.fromEntries(Object.entries(process.env).filter(([key])=>!key.startsWith('RDG_AUTH_')));
env.PYTHONDONTWRITEBYTECODE='1';env.PYTHONNOUSERSITE='1';
(async()=>{
 let bridge,browser,profile,stderr='',url;const pending=new Map();let serial=0;
 const query=(method,body={})=>new Promise((resolve,reject)=>{
  const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(Error('persistent fixture timeout'));},45000);
  pending.set(id,result=>{clearTimeout(timer);resolve(result);});
  bridge.stdin.write(JSON.stringify({id,method,body})+'\n');
 });
 const must=async(method,body)=>{const r=await query(method,body);assert.equal(r.ok,true,r.error);return r.result;};
 try{
  bridge=spawn(PYTHON,['-B','-u',path.join(ROOT,'tests/rdg-persistent-viewer-fixture.py'),'--synthetic-fixture'],
   {env,stdio:['pipe','pipe','pipe']});
  bridge.stderr.on('data',c=>{stderr+=c;});
  bridge.on('error',e=>{for(const done of pending.values())done({ok:false,error:e.message});pending.clear();});
  readline.createInterface({input:bridge.stdout}).on('line',line=>{
   const r=JSON.parse(line),done=pending.get(r.id);if(done){pending.delete(r.id);done(r);}
  });
  let ready=await must('ready');url=ready.url;const initialPID=ready.processId;
  profile=fs.mkdtempSync('/workspace/repo/rdg-persistent-browser-');
  browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,userDataDir:profile,
   headless:true,args:['--no-sandbox','--disable-dev-shm-usage'],env});
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const cdp=await page.createCDPSession();await cdp.send('WebAuthn.enable',{enableUI:false});
  await cdp.send('WebAuthn.addVirtualAuthenticator',{options:{protocol:'ctap2',transport:'internal',
   hasResidentKey:true,hasUserVerification:true,isUserVerified:true,automaticPresenceSimulation:true}});
  const load=async()=>{
   await page.goto(url,{waitUntil:'load'});
   await page.waitForFunction(()=>globalThis.RDG_PORTABLE_EDITOR&&document.querySelector('.rp-status')?.textContent.includes('Каталог прочитан'),{timeout:30000});
  };
  const click=async text=>{
   const handle=await page.evaluateHandle(text=>[...document.querySelectorAll('.rp-approvals button')].find(b=>b.textContent===text),text);
   const element=handle.asElement();assert(element,'button missing: '+text);
   assert.equal(await element.evaluate(b=>b.disabled),false,text+' disabled');
   await element.click();await handle.dispose();
   await page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy,{timeout:30000});
  };
  const open=async item=>{
   await click('Обновить запросы');
   await page.click('[data-approval-request="'+item.requestId+'"]');
   await page.waitForFunction(id=>!RDG_PORTABLE_EDITOR.busy&&RDG_PORTABLE_EDITOR.approval?.record.requestId===id,{},item.requestId);
  };
  const rpc=async body=>page.evaluate(async body=>{
   const response=await fetch(new URL('approval',location.href),{method:'POST',
    headers:{'Content-Type':'application/json','X-RDG-Session':RDG_SESSION},body:JSON.stringify(body)});
   return {status:response.status,value:await response.json()};
  },body);
  const state=()=>page.evaluate(()=>RDG_PORTABLE_EDITOR.approval?.record.state);
  await load();
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.enrollment.state),'issued');
  assert.notEqual((await rpc({method:'registration_begin',principalId:'attacker',executorGrantId:'root'})).status,200);
  const denied=await query('ordinary_invite');assert.equal(denied.ok,false);assert.match(denied.error,/OWNER_REQUIRED/);
  checks.push('ordinary Agent and client actor fields cannot issue or retarget an enrollment');

  await click('Зарегистрировать ключ');
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.enrollment.state),'completed');
  let metadata=await must('state');
  assert.equal(metadata.credentials.length,1);assert.equal(metadata.credentials[0].active,true);
  const registrationCounter=metadata.credentials[0].counter;
  assert(registrationCounter>=0);assert.equal(metadata.packageCount,0);assert.equal(metadata.ownerTokenInRuntimeConfig,false);
  const originalCredential=metadata.credentials[0].credentialId;
  checks.push('native Viewer registration consumes an owner invitation and saves only the public credential');

  const first=await must('setup');await open(first);
  await click('Подтвердить');assert.equal(await state(),'executed-approved');
  let observed=await must('inspect',{requestId:first.requestId});
  assert.equal(observed.graph.nodes[0].title,first.title);
  const firstProof=observed.receipt.receipt.authorizationContext.approver.proofSHA256;
  const firstCounter=(await must('state')).credentials[0].counter;
  assert(firstCounter>registrationCounter);
  checks.push('persistent credential authorizes exact execution and durably advances its counter');

  const second=await must('setup');await open(second);
  const oldBegin=await page.evaluate(async()=>{
   const response=await fetch(new URL('approval',location.href),{method:'POST',
    headers:{'Content-Type':'application/json','X-RDG-Session':RDG_SESSION},
    body:JSON.stringify({method:'choose',viewId:RDG_PORTABLE_EDITOR.approval.viewId,decision:'approve'})});
   return response.json();
  });
  const oldAssertion=await page.evaluate(async begin=>(await navigator.credentials.get({
   publicKey:PublicKeyCredential.parseRequestOptionsFromJSON(begin.options.publicKey)})).toJSON(),oldBegin);
  ready=await must('restart');assert.notEqual(ready.processId,initialPID);
  assert.equal(new URL(ready.url).origin,new URL(url).origin);url=ready.url;
  await load();
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.enrollment),null);
  assert.notEqual((await rpc({method:'registration_begin'})).status,200);
  const replay=await rpc({method:'complete',ceremonyId:oldBegin.ceremonyId,response:oldAssertion});
  assert.notEqual(replay.status,200);assert.match(replay.value.error,/CEREMONY_UNAVAILABLE/);
  assert.equal((await must('inspect',{requestId:second.requestId})).receipt.found,false);
  checks.push('real process restart preserves the binding but discards old ceremonies and invitations');

  metadata=await must('state');assert.equal(metadata.credentials[0].counter,firstCounter);
  await open(second);await click('Подтвердить');assert.equal(await state(),'executed-approved');
  observed=await must('inspect',{requestId:second.requestId});
  assert.equal(observed.graph.nodes[0].title,second.title);
  assert((await must('state')).credentials[0].counter>firstCounter);
  checks.push('a fresh ceremony after restart uses the saved key without registration');

  const audited=await must('audit',{proofSHA256:firstProof});
  assert.equal(audited.signatureVerified,true);assert.equal(audited.authorizesNewExecution,false);
  checks.push('saved assertion and public key independently verify exact consent after restart');

  const revoked=await must('setup');await open(revoked);
  await must('arm_revoke',{credentialId:originalCredential});
  await click('Подтвердить');
  observed=await must('inspect',{requestId:revoked.requestId});
  assert.equal(observed.receipt.found,false);assert.equal(observed.state,'pending');
  metadata=await must('state');assert.equal(metadata.credentials[0].active,false);
  assert.deepEqual(metadata.fixtureErrors,[]);
  checks.push('owner revocation after signature and staging blocks durable Graph acceptance');

  ready=await must('restart');url=ready.url;await load();await open(revoked);
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.approval.previewAvailable),false);
  const revokedAudit=await must('audit',{proofSHA256:firstProof});
  assert.equal(revokedAudit.signatureVerified,true);assert.equal(revokedAudit.credentialCurrentlyActive,false);
  const recovered=await rpc({method:'recover',requestId:first.requestId});
  assert.equal(recovered.status,200);assert.equal(recovered.value.idempotent,true);
  assert.equal((await must('inspect',{requestId:first.requestId})).graph.nodes[0].title,first.title);
  checks.push('revocation persists across restart while accepted historical recovery remains exact');

  ready=await must('reinvite');url=ready.url;await load();
  assert.equal(await page.evaluate(()=>RDG_PORTABLE_EDITOR.enrollment.state),'issued');
  await click('Зарегистрировать ключ');
  metadata=await must('state');
  assert.equal(metadata.credentials.length,2);assert.equal(metadata.credentials.filter(c=>c.active).length,1);
  const replacement=metadata.credentials.find(c=>c.active).credentialId;
  assert.notEqual(replacement,originalCredential);
  await open(revoked);await click('Подтвердить');assert.equal(await state(),'executed-approved');
  observed=await must('inspect',{requestId:revoked.requestId});
  assert.equal(observed.graph.nodes[0].title,revoked.title);
  assert.equal(observed.receipt.receipt.authorizationContext.approver.credentialId,replacement);
  checks.push('only a new owner invitation enrolls a replacement key and authorizes a fresh consent');

  await page.evaluate(id=>RDG_PORTABLE_EDITOR.open(id,{kind:'focus',id:'R1'}),revoked.packageId);
  await page.evaluate(()=>{
   const box=[...document.querySelectorAll('details')].find(d=>d.querySelector(':scope > summary')?.textContent==='Замок object+operation');
   if(!box)throw Error('lock controls missing');box.open=true;
   const label=[...box.querySelectorAll('label')].find(n=>n.textContent.includes('Причина снятия'));
   label.querySelector('textarea').value='Явное снятие замка через подтверждение';
   [...box.querySelectorAll('button')].find(n=>n.textContent==='Снять замок').click();
  });
  await page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy&&RDG_PORTABLE_EDITOR.approval?.record.request.op==='lock_remove');
  const lockRequest=await page.evaluate(()=>RDG_PORTABLE_EDITOR.approval.record.requestId);
  assert.equal((await must('inspect',{requestId:lockRequest})).graph.nodes[0].locks.edit.mode,'hard');
  await click('Подтвердить');assert.equal(await state(),'executed-approved');
  assert.equal((await must('inspect',{requestId:lockRequest})).graph.nodes[0].locks?.edit,undefined);
  checks.push('manual Viewer lock management creates a proposal and needs native consent before mutation');

  metadata=await must('state');
  assert.equal(metadata.grantsUnchanged,true);assert.equal(metadata.grantRevisionUnchanged,true);
  assert.equal(metadata.ownerTokenInRuntimeConfig,false);assert.deepEqual(metadata.fixtureErrors,[]);
  assert.deepEqual(errors,[]);
  checks.push('enrollment counters and revocation create no grants and expose no owner bearer to runtime');
  console.log(JSON.stringify({ok:true,cases:checks.length,checks,mainViewer:true,
   persistentCredentials:true,realProcessRestart:true,authenticator:'Chromium virtual CTAP2',
   realHumanProof:false,osIsolationVerified:false,liveOwnersTouched:false}));
 }catch(error){
  console.error(String(error.stack).split(url||'<none>').join('<synthetic-session>'));if(stderr)console.error(stderr);process.exitCode=1;
 }finally{
  if(browser)await browser.close();
  if(bridge){bridge.stdin.end();await new Promise(resolve=>{if(bridge.exitCode!==null)return resolve();bridge.once('exit',resolve);setTimeout(()=>{bridge.kill('SIGTERM');resolve();},15000).unref();});}
  if(profile)fs.rmSync(profile,{recursive:true,force:true});
 }
})();
