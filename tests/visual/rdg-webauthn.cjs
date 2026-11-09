'use strict';
// Native WebAuthn + python-fido2, using a virtual authenticator in isolated Chromium.
// No actual human credentials, live grants/owners or installed Viewer are involved.
const assert=require('node:assert/strict'),http=require('node:http'),path=require('node:path');
const fs=require('node:fs'),readline=require('node:readline'),{spawn}=require('node:child_process');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'../..');
const PYTHON=process.env.RDG_WEBAUTHN_PYTHON||'/workspace/repo/.rdg-webauthn-venv/bin/python';
const env=Object.fromEntries(Object.entries(process.env).filter(([key])=>!key.startsWith('RDG_AUTH_')));
env.PYTHONDONTWRITEBYTECODE='1';env.PYTHONNOUSERSITE='1';
const checks=[],clone=value=>JSON.parse(JSON.stringify(value));
function clientData(response,change){
 const value=clone(response),data=JSON.parse(Buffer.from(value.response.clientDataJSON,'base64url'));
 change(data);value.response.clientDataJSON=Buffer.from(JSON.stringify(data)).toString('base64url');return value;
}
(async()=>{
 let browser,bridge,server,profile,stderr='';
 const pending=new Map();let serial=0;
 const query=(method,body={})=>new Promise((resolve,reject)=>{
  const id=++serial;
  const timer=setTimeout(()=>{pending.delete(id);reject(new Error('fixture reply timeout'));},12000);
  pending.set(id,value=>{clearTimeout(timer);resolve(value);});
  bridge.stdin.write(JSON.stringify({id,method,body})+'\n');
 });
 const must=async(method,body)=>{const r=await query(method,body);assert.equal(r.ok,true,r.error);return r.result;};
 const denied=async(method,body,pattern)=>{
  const r=await query(method,body);assert.equal(r.ok,false);assert.match(r.error,pattern);return r;
 };
 try{
  const html=[
   '<!doctype html><html lang="ru"><meta charset="utf-8"><title>RDG WebAuthn proof</title>',
   '<h1>Проверка подтверждения</h1><p>Изолированный тест. Ключ виртуальный. Живые Graph не изменяются.</p>',
   '<article><h2>Предложение ИИ</h2><p>Изменить название R1: «До» → «После».</p>',
   '<button id="register">Зарегистрировать тестовый ключ</button>',
   '<button id="approve">Подтвердить</button><button id="reject">Отклонить</button></article>',
   '<output id="result"></output><script>',
   'async function rpc(method,body={}){const r=await fetch("/api/"+method,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const v=await r.json();if(!v.ok)throw Error(v.error);return v.result;}',
   'async function createCredential(begin){const publicKey=PublicKeyCredential.parseCreationOptionsFromJSON(begin.options.publicKey);return(await navigator.credentials.create({publicKey})).toJSON();}',
   'async function signCredential(begin,abort=false){const publicKey=PublicKeyCredential.parseRequestOptionsFromJSON(begin.options.publicKey);const control=new AbortController();if(abort)setTimeout(()=>control.abort(),50);return(await navigator.credentials.get({publicKey,signal:control.signal})).toJSON();}',
   'window.createCredential=createCredential;window.signCredential=signCredential;',
   'register.onclick=async()=>{try{const b=await rpc("register_begin");const response=await createCredential(b);window.lastResult=await rpc("register_complete",{ceremonyId:b.ceremonyId,response});result.textContent="Тестовый ключ зарегистрирован";}catch(e){window.uiError=e.message;}};',
   'for(const decision of ["approve","reject"]){document.getElementById(decision).onclick=async()=>{try{const b=await rpc("decision_begin",{decision});const response=await signCredential(b);window.lastProof={ceremonyId:b.ceremonyId,response};window.lastResult=await rpc("decision_complete",window.lastProof);result.textContent="Подтверждение проверено. Это тест без исполнения Graph.";}catch(e){window.uiError=e.message;}};}',
   '</script></html>'
  ].join('');
  const routes=new Set(['register_begin','register_complete','decision_begin','decision_complete']);
  server=http.createServer(async(req,res)=>{
   res.setHeader('Cache-Control','no-store');
   if(req.method==='GET'&&req.url==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);return;}
   const method=req.url?.replace(/^\/api\//,'');
   if(req.method!=='POST'||!routes.has(method)){res.writeHead(404);res.end();return;}
   try{
    let raw='';for await(const chunk of req){raw+=chunk;if(raw.length>1000000)throw Error('request too large');}
    const reply=await query(method,JSON.parse(raw));res.setHeader('Content-Type','application/json');res.end(JSON.stringify(reply));
   }catch(e){res.writeHead(400);res.end(JSON.stringify({ok:false,error:e.message}));}
  });
  await new Promise(resolve=>server.listen(0,'localhost',resolve));
  const origin='http://localhost:'+server.address().port;
  bridge=spawn(PYTHON,['-B','-u',path.join(ROOT,'tests/rdg-webauthn-fixture.py'),'--synthetic-fixture','--origin',origin],{env,stdio:['pipe','pipe','pipe']});
  bridge.stderr.on('data',chunk=>{stderr+=chunk;});
  bridge.on('error',error=>{for(const done of pending.values())done({ok:false,error:error.message});pending.clear();});
  readline.createInterface({input:bridge.stdout}).on('line',line=>{
   const reply=JSON.parse(line),done=pending.get(reply.id);if(done){pending.delete(reply.id);done(reply);}
  });
  profile=fs.mkdtempSync('/workspace/repo/rdg-webauthn-browser-');
  browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,
   userDataDir:profile,headless:true,args:['--no-sandbox','--disable-dev-shm-usage'],env});
  const page=await browser.newPage(),pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message));
  const cdp=await page.createCDPSession();
  await cdp.send('WebAuthn.enable',{enableUI:false});
  const {authenticatorId}=await cdp.send('WebAuthn.addVirtualAuthenticator',{options:{
   protocol:'ctap2',transport:'internal',hasResidentKey:true,hasUserVerification:true,
   isUserVerified:true,automaticPresenceSimulation:true}});
  await page.goto(origin,{waitUntil:'load'});
  assert.deepEqual(await page.evaluate(()=>({secure:isSecureContext,available:!!window.PublicKeyCredential,
   parse:typeof PublicKeyCredential.parseRequestOptionsFromJSON})),{secure:true,available:true,parse:'function'});
  checks.push('native WebAuthn on a secure localhost origin');
  async function uiClick(id){
   await page.evaluate(()=>{delete window.lastResult;delete window.uiError;});
   await page.click('#'+id);
   await page.waitForFunction(()=>window.lastResult||window.uiError,{timeout:12000});
   const value=await page.evaluate(()=>({result:window.lastResult,error:window.uiError}));
   assert.equal(value.error,undefined,value.error);return value.result;
  }
  const registered=await uiClick('register');
  assert.equal(registered.userVerified,true);assert.equal(registered.attestationModelVerified,false);
  checks.push('browser registration with required user verification');
  // Only the newly-created virtual test authenticator is inspected. Its test-only
  // private key stays in this process: never logged, persisted or used by RDG.
  const virtual=await cdp.send('WebAuthn.getCredentials',{authenticatorId});
  const credential=virtual.credentials.find(row=>Buffer.from(row.credentialId,'base64')
   .equals(Buffer.from(registered.credentialId,'base64url')));
  assert(credential,'new virtual credential missing');
  const testKey=crypto.createPrivateKey({key:Buffer.from(credential.privateKey,'base64'),
   format:'der',type:'pkcs8'});
  const reSign=response=>{
   const data=Buffer.from(response.response.authenticatorData,'base64url');
   const clientHash=crypto.createHash('sha256').update(Buffer.from(response.response.clientDataJSON,'base64url')).digest();
   response.response.signature=crypto.sign('sha256',Buffer.concat([data,clientHash]),testKey).toString('base64url');
  };
  const approved=await uiClick('approve');
  assert.equal(approved.decision,'approve');assert.equal(approved.principalId,'synthetic-operator');
  assert.equal(approved.graphExecutionAuthorized,false);
  const firstProof=await page.evaluate(()=>window.lastProof);
  checks.push('explicit Approve button and verified assertion');
  const rejected=await uiClick('reject');
  assert.equal(rejected.decision,'reject');assert.equal(rejected.graphExecutionAuthorized,false);
  checks.push('explicit Reject button and verified assertion');
  await denied('decision_complete',firstProof,/CEREMONY_UNAVAILABLE/);
  checks.push('one-use ceremony rejects replay');
  const signed=async()=>{const b=await must('decision_begin',{decision:'approve'});
   const response=await page.evaluate(async b=>window.signCredential(b),b);return{ceremonyId:b.ceremonyId,response};};
  const signedControl=await signed();reSign(signedControl.response);
  assert.equal((await must('decision_complete',signedControl)).graphExecutionAuthorized,false);
  checks.push('valid re-signed test assertion is accepted as a negative-test control');
  async function invalid(name,mutate,pattern=/ASSERTION_INVALID/,validSignature=true){
   const proof=await signed();mutate(proof.response);
   if(validSignature)reSign(proof.response);
   await denied('decision_complete',proof,pattern);checks.push(name);
  }
  await invalid('wrong origin is rejected',r=>{Object.assign(r,clientData(r,d=>{d.origin='https://invalid.example';}));});
  await invalid('wrong challenge is rejected',r=>{Object.assign(r,clientData(r,d=>{d.challenge='AAAA';}));});
  await invalid('cross-origin framing is rejected',r=>{Object.assign(r,clientData(r,d=>{d.crossOrigin=true;}));});
  await invalid('topOrigin injection is rejected',r=>{Object.assign(r,clientData(r,d=>{d.topOrigin=origin;}));});
  await invalid('wrong RP ID hash is rejected',r=>{const b=Buffer.from(r.response.authenticatorData,'base64url');b[0]^=1;r.response.authenticatorData=b.toString('base64url');});
  await invalid('missing user presence is rejected',r=>{const b=Buffer.from(r.response.authenticatorData,'base64url');b[32]&=~1;r.response.authenticatorData=b.toString('base64url');});
  await invalid('missing user verification is rejected',r=>{const b=Buffer.from(r.response.authenticatorData,'base64url');b[32]&=~4;r.response.authenticatorData=b.toString('base64url');});
  await invalid('modified signature is rejected',r=>{const b=Buffer.from(r.response.signature,'base64url');b[b.length-1]^=1;r.response.signature=b.toString('base64url');},/ASSERTION_INVALID/,false);
  await invalid('unknown credential is rejected',r=>{r.rawId=Buffer.from('unknown-credential').toString('base64url');r.id=r.rawId;});
  await invalid('wrong user handle is rejected',r=>{r.response.userHandle=Buffer.from('wrong-user').toString('base64url');},/USER_HANDLE_MISMATCH/);
  await invalid('validly signed counter rollback is rejected',r=>{
   const b=Buffer.from(r.response.authenticatorData,'base64url');b.writeUInt32BE(0,33);
   r.response.authenticatorData=b.toString('base64url');
  },/COUNTER_NOT_INCREASING/);
  const stale=await signed();await must('change_preview',{digest:'2'.repeat(64)});
  await denied('decision_complete',stale,/PREVIEW_CHANGED/);
  checks.push('changed server preview invalidates prior proof');
  const expired=await signed();await must('advance_clock',{seconds:121});
  await denied('decision_complete',expired,/CEREMONY_UNAVAILABLE/);
  checks.push('expired ceremony is rejected without waiting in real time');
  await denied('unknown_principal',{},/PRINCIPAL_NOT_ENROLLED/);
  checks.push('no implicit enrollment for a claimed principal');
  const forged=await signed();
  await denied('decision_complete',{...forged,by:'user',decision:'reject'},/MESSAGE_FIELDS/);
  checks.push('client actor and decision claims are not accepted');
  const cancelled=await must('decision_begin',{decision:'approve'});
  await cdp.send('WebAuthn.setAutomaticPresenceSimulation',{authenticatorId,enabled:false});
  const cancel=await page.evaluate(async b=>{try{await window.signCredential(b,true);return null;}catch(e){return e.name;}},cancelled);
  assert.equal(cancel,'AbortError');
  await cdp.send('WebAuthn.setAutomaticPresenceSimulation',{authenticatorId,enabled:true});
  checks.push('native browser cancellation returns no assertion');
  const filePage=await browser.newPage();
  await filePage.goto('file://'+path.join(ROOT,'tests/visual/rdg-viewer.html'));
  const b=await must('register_begin');
  const fileResult=await filePage.evaluate(async b=>{
   try{await navigator.credentials.create({publicKey:PublicKeyCredential.parseCreationOptionsFromJSON(b.options.publicKey)});return 'unexpected-success';}
   catch(e){return e.name;}
  },b);
  assert.equal(fileResult,'SecurityError');await filePage.close();
  checks.push('existing file origin cannot use localhost RP credentials');
  const summary=await must('summary');
  assert.equal(summary.credentialCount,1);assert.equal(summary.realHumanProof,false);
  assert.equal(summary.noGraphWriterConnected,true);assert.deepEqual(pageErrors,[]);
  // Connect the same registered virtual credential to the actual shared writer,
  // exclusively on disposable synthetic Graph/Plan owners.
  const nativeProof=async(decision='approve')=>{
   const begin=await must('execution_begin',{decision});
   const response=await page.evaluate(async b=>window.signCredential(b),begin);
   return {begin,proof:{ceremonyId:begin.ceremonyId,response}};
  };
  const configured=await must('execution_setup',{operation:'edit'});
  const exact=await nativeProof();
  const executed=await must('execution_complete',exact.proof);
  assert.equal(executed.accepted,true);
  const nativeState=await must('execution_summary');
  assert.deepEqual(nativeState.graph,exact.begin.preview.owners[0].after.graph);
  assert.equal(nativeState.state,'executed-approved');
  checks.push('native signed approval executes exactly the previewed hard-locked edit');
  const chain=executed.packages[0].receipt.authorizationContext;
  assert.equal(chain.initiator.grantId,configured.initiatorGrantId);
  assert.equal(chain.approver.principalId,'synthetic-operator');
  assert.equal(chain.executor.grantId,configured.executorGrantId);
  assert.notEqual(chain.initiator.grantId,chain.executor.grantId);
  assert.equal(chain.previewSHA256,exact.begin.approvalSHA256);
  assert(!JSON.stringify(executed).includes('tokenSHA256'));
  checks.push('native assertion persists distinct initiator approver executor in receipt');
  assert.equal((await must('execution_replay')).idempotent,true);
  await denied('execution_complete',exact.proof,/CEREMONY_UNAVAILABLE/);
  assert.deepEqual((await must('execution_summary')).graph,nativeState.graph);
  checks.push('native approved action replays once and cannot reuse its assertion');

  await must('execution_setup',{operation:'edit'});
  const bad=await nativeProof(),beforeBad=await must('execution_summary');
  const badSignature=Buffer.from(bad.proof.response.response.signature,'base64url');
  badSignature[badSignature.length-1]^=1;
  bad.proof.response.response.signature=badSignature.toString('base64url');
  await denied('execution_complete',bad.proof,/ASSERTION_INVALID/);
  assert.deepEqual((await must('execution_summary')).graph,beforeBad.graph);
  checks.push('invalid native signature leaves the protected Graph unchanged');

  await must('execution_setup',{operation:'edit'});
  const reject=await nativeProof('reject'),beforeReject=await must('execution_summary');
  assert.equal((await must('execution_complete',reject.proof)).state,'rejected');
  await denied('execution_replay',{},/TRANSACTION_REJECTED/);
  assert.deepEqual((await must('execution_summary')).graph,beforeReject.graph);
  checks.push('native signed rejection changes no Graph and blocks same-id execution');

  await must('execution_setup',{operation:'replace'});
  const coupled=await nativeProof();
  const p2=await must('execution_new_plan');
  await denied('execution_complete',coupled.proof,/PREVIEW_CHANGED/);
  checks.push('new coupled Plan invalidates a native assertion for the old preview');
  const fresh=await nativeProof();
  assert(Object.hasOwn(fresh.begin.preview.effects.removedPlacements,p2.addedPlanPackageId));
  const replaced=await must('execution_complete',fresh.proof);
  assert.equal(replaced.packages.length,3);
  checks.push('fresh native approval commits the Graph and both coupled Plan owners');

  await must('execution_setup',{operation:'crash'});
  const interrupted=await nativeProof();
  await denied('execution_complete',interrupted.proof,/SYNTHETIC_AFTER_ACCEPTANCE/);
  const recovered=await must('execution_recover');
  assert.equal(recovered.accepted,true);assert.equal(recovered.idempotent,true);
  const afterRecovery=await must('execution_summary');
  assert.equal((await must('execution_replay')).idempotent,true);
  assert.deepEqual((await must('execution_summary')).graph,afterRecovery.graph);
  checks.push('native approved payload recovers after durable acceptance without duplicate effects');
  const finalSummary=await must('summary');
  assert.equal(finalSummary.noGraphWriterConnected,false);assert.deepEqual(pageErrors,[]);
  console.log(JSON.stringify({ok:true,cases:checks.length,checks,
   authenticator:'Chromium virtual CTAP2',fido2UserVerification:true,
   realHumanProof:false,syntheticGraphExecutionVerified:true,liveOwnersTouched:false}));
 }catch(error){
  console.error(error.stack);if(stderr)console.error(stderr);process.exitCode=1;
 }finally{
  if(browser)await browser.close();
  if(bridge){bridge.stdin.end();await new Promise(resolve=>{if(bridge.exitCode!==null)return resolve();bridge.once('exit',resolve);setTimeout(()=>{bridge.kill('SIGTERM');resolve();},3000).unref();});}
  if(server){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
  if(profile)fs.rmSync(profile,{recursive:true,force:true});
 }
})();
