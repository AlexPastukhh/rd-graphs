'use strict';
// Frozen extracted runtime + production WSGI process + native Basic auth + real API.
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs'),http=require('node:http'),path=require('node:path');
const {spawn,spawnSync}=require('node:child_process');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const root=path.resolve(__dirname,'../..'),base=fs.mkdtempSync(path.join(process.env.RDG_WORKFILES||'/workspace/repo/Workfiles','rdg-server-browser-'));
const archive=process.env.RDG_SERVER_ARCHIVE||'/workspace/repo/Workfiles/RDG-Server-20261029-candidate1.zip';
const python=process.env.RDG_SERVER_PYTHON||'/workspace/repo/Workfiles/rdg-server-test-venv/bin/python3';
const unpack=path.join(base,'code with spaces'),data=path.join(base,'data'),secrets=path.join(base,'secrets');
const env={...process.env,PYTHONDONTWRITEBYTECODE:'1',PYTHONNOUSERSITE:'1'};
for(const name of Object.keys(env))if(name.startsWith('RDG_AUTH_'))delete env[name];
const caddy=process.env.RDG_SERVER_CADDY;
const checks=[],errors=[];let child,proxy,gateway,browser,page,origin,backendOrigin,gatewayUrl,gatewayEnabled=false,stderr='',proxyStderr='',gatewayStderr='',namespace,browserToken,agentToken;
const safe=e=>String(e.stack||e).replace(/\/session\/[A-Za-z0-9_-]+\//g,'/session/[redacted]/');
// Every test daemon gets its OWN process group. Do not signal the caller's
// Node/Desktop Commander group when a test times out or fails.
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function boundedExit(proc,ms){
 if(!proc||proc.exitCode!==null||proc.signalCode!==null)return;
 let timer;try{await Promise.race([new Promise(resolve=>proc.once('exit',resolve)),
   new Promise(resolve=>{timer=setTimeout(resolve,ms);})]);}finally{clearTimeout(timer);}
}
async function stopTestProcess(proc){
 if(!proc)return;
 if(proc.exitCode===null&&proc.signalCode===null){
  proc.kill('SIGTERM');
  await boundedExit(proc,2500);
 }
 // Reap any Gunicorn workers / proxy children left after their master exits.
 if(process.platform!=='win32'&&Number.isInteger(proc.pid)){
  try{process.kill(-proc.pid,'SIGTERM');}catch(e){if(e.code!=='ESRCH')throw e;}
  await pause(150);
  try{process.kill(-proc.pid,'SIGKILL');}catch(e){if(e.code!=='ESRCH')throw e;}
 }
 if(proc.exitCode===null&&proc.signalCode===null){
  proc.kill('SIGKILL');await boundedExit(proc,1000);
 }
}
async function stop(){const proc=child;child=null;await stopTestProcess(proc);}
async function stopBrowser(){
 const active=browser;browser=null;page=null;
 if(!active)return;
 let timer;try{
  await Promise.race([active.close(),new Promise((_,reject)=>{
    timer=setTimeout(()=>reject(Error('Browser close timeout')),3500);})]);
 }catch{
  const proc=active.process();if(proc){proc.kill('SIGTERM');await boundedExit(proc,1000);
    if(proc.exitCode===null&&proc.signalCode===null)proc.kill('SIGKILL');}
 }finally{clearTimeout(timer);}
}
let cleaning;
function cleanup(){if(!cleaning)cleaning=(async()=>{
 await stopBrowser();await stopGateway();await stop();await stopProxy();
 })();return cleaning;}
for(const sig of ['SIGTERM','SIGINT'])process.once(sig,()=>{
 // Normally CI requests cooperative shutdown; group SIGKILL is a backstop.
 void cleanup().finally(()=>process.exit(sig==='SIGTERM'?143:130));
});
async function freePort(){const probe=http.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));return port;}
async function startProxy(){
 if(!caddy)return;
 const port=await freePort();backendOrigin='http://127.0.0.1:'+port;
 const adapted=spawnSync(caddy,['adapt','--config',path.join(unpack,'RDG-Server/Caddyfile.local'),'--adapter','caddyfile','--validate'],{env:{...env,XDG_CONFIG_HOME:path.join(base,'caddy-config'),XDG_DATA_HOME:path.join(base,'caddy-data')},encoding:'utf8'});
 assert.equal(adapted.status,0,adapted.stderr);const config=JSON.parse(adapted.stdout);let binds=0,dials=0;
 function testAddresses(value){if(!value||typeof value!=='object')return;for(const [key,item] of Object.entries(value)){if(key==='listen'&&Array.isArray(item))value[key]=item.map(address=>{if(address!==':8080')return address;binds++;return new URL(origin).host;});else if(key==='dial'&&item==='rdg:8080'){value[key]='127.0.0.1:'+port;dials++;}else testAddresses(item);}}
 testAddresses(config);assert.equal(binds,1);assert.equal(dials,1);
 const file=path.join(base,'caddy-test.json');fs.writeFileSync(file,JSON.stringify(config));
 proxy=spawn(caddy,['run','--config',file],{env:{...env,XDG_CONFIG_HOME:path.join(base,'caddy-config'),XDG_DATA_HOME:path.join(base,'caddy-data')},detached:true});proxy.stderr.on('data',v=>proxyStderr+=v);
}
async function stopProxy(){const proc=proxy;proxy=null;await stopTestProcess(proc);}
async function startGateway(){
 if(!gatewayEnabled)return null;
 if(!gatewayUrl)gatewayUrl='http://127.0.0.1:'+await freePort();
 const entry=path.join(base,'gateway_test_entry.py');
 const modulePath=path.join(unpack,'RDG-Server/runtime/tools/rdg-gateway.py');
 fs.writeFileSync(entry,'from importlib.machinery import SourceFileLoader\n'+'g=SourceFileLoader(\'frozen_gateway\','+JSON.stringify(modulePath)+').load_module()\n'+'application=g.Gateway('+JSON.stringify(path.join(base,'gateway-private/credentials.json'))+','+JSON.stringify(origin)+',upstream='+JSON.stringify(backendOrigin)+',origin='+JSON.stringify(gatewayUrl)+')\n');
 gatewayStderr='';gateway=spawn(python,['-m','gunicorn','--chdir',base,'--bind',new URL(gatewayUrl).host,'--workers','1','--threads','1','--timeout','65','--worker-tmp-dir',base,'--access-logfile','/dev/null','--log-level','warning','gateway_test_entry:application'],{env,detached:true});gateway.stderr.on('data',v=>gatewayStderr+=v);
 for(let i=0;i<100;i++){if(gateway.exitCode!==null)throw Error('Gateway exited: '+gatewayStderr.slice(-1500));try{const r=await fetch(gatewayUrl+'/healthz');if(r.ok){const value=await r.json();assert.equal(value.namespaceId,namespace);return gateway.pid;}}catch{}await new Promise(r=>setTimeout(r,150));}
 throw Error('Gateway startup timeout: '+gatewayStderr.slice(-1500));
}
async function stopGateway(){const proc=gateway;gateway=null;await stopTestProcess(proc);}
async function start(){stderr='';child=spawn(python,['-m','gunicorn','--chdir',path.join(unpack,'RDG-Server/runtime/tools'),'--bind',new URL(backendOrigin||origin).host,'--workers','1','--threads','1','--timeout','60','--worker-tmp-dir',base,'--access-logfile','/dev/null','--log-level','warning','rdg_server_entry:application'],{env:{...env,RDG_DATA_DIR:data,RDG_PUBLIC_ORIGIN:origin},detached:true});child.stderr.on('data',v=>stderr+=v);for(let i=0;i<120;i++){if(child.exitCode!==null)throw Error('Gunicorn exited: '+stderr.slice(-1500));if(proxy&&proxy.exitCode!==null)throw Error('Caddy exited: '+proxyStderr.slice(-1500));try{const r=await fetch(origin+'/healthz');if(r.ok)return child.pid;}catch{}await new Promise(r=>setTimeout(r,200));}throw Error('Gunicorn startup timeout: '+stderr.slice(-1500));}
const api=async message=>{const headers={'X-RDG-Namespace':namespace,'Content-Type':'application/json'};if(!gatewayEnabled)headers.Authorization='Bearer '+agentToken;else assert(!headers.Authorization);const response=await fetch((gatewayEnabled?gatewayUrl:origin)+'/api/command',{method:'POST',headers,body:JSON.stringify(message)});const value=await response.json();assert(response.ok,JSON.stringify(value));return value;};
(async()=>{try{
 const extracted=spawnSync('python3',['-c',"import pathlib,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert all(not pathlib.PurePosixPath(n).is_absolute() and '..' not in pathlib.PurePosixPath(n).parts for n in z.namelist()); z.extractall(sys.argv[2])",archive,unpack],{encoding:'utf8'});assert.equal(extracted.status,0,extracted.stderr);
 const packageRoot=path.join(unpack,'RDG-Server'),manifest=JSON.parse(fs.readFileSync(path.join(packageRoot,'BUILD.json'),'utf8'));assert.equal(manifest.includesUserData,false);assert.equal(JSON.parse(fs.readFileSync(path.join(packageRoot,'runtime/RDG-BUILD.json'),'utf8')).buildId,manifest.serverBuild);gatewayEnabled=!!manifest.files['runtime/tools/rdg-gateway.py'];if(gatewayEnabled)assert(caddy,'Set RDG_SERVER_CADDY for gateway/browser boundary verification');
 for(const [name,hash] of Object.entries(manifest.files))assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(packageRoot,name))).digest('hex'),hash,name);
 const initArgs=gatewayEnabled?[path.join(packageRoot,'runtime/tools/rdg-server-setup.py'),'--data-dir',data,'--credentials-dir',secrets,'--gateway-dir',path.join(base,'gateway-private')]:[path.join(packageRoot,'runtime/tools/rdg-server.py'),'init','--data-dir',data,'--credentials-dir',secrets];const init=spawnSync(python,initArgs,{env,encoding:'utf8'});assert.equal(init.status,0,init.stderr);assert.equal(JSON.parse(init.stdout).includesDemoGraphs,false);
 browserToken=fs.readFileSync(path.join(secrets,'browser-token.txt'),'utf8').trim();agentToken=fs.readFileSync(path.join(secrets,'agent-token.txt'),'utf8').trim();namespace=fs.readFileSync(path.join(secrets,'namespace-id.txt'),'utf8').trim();assert.notEqual(browserToken,agentToken);
 origin='http://127.0.0.1:'+await freePort();await startProxy();const firstPid=await start();const firstGatewayPid=await startGateway();
 if(caddy){const wrongHost=await new Promise((resolve,reject)=>{http.get(origin+'/healthz',{headers:{Host:'unexpected.example'}},response=>{response.resume();resolve(response.statusCode);}).on('error',reject);});assert.equal(wrongHost,403);checks.push('packaged Caddy config validated; real reverse proxy preserves Host checks and forwards browser/API traffic');}
 if(gatewayEnabled){
  for(const route of ['/api/capabilities','/api/command','/api%2Fcommand']){const response=await fetch(origin+route,{method:route.endsWith('capabilities')?'GET':'POST',headers:{Authorization:'Bearer '+agentToken,'Content-Type':'application/json','X-RDG-Namespace':namespace},...(route.endsWith('capabilities')?{}:{body:JSON.stringify({method:'catalog'})})});assert.equal(response.status,404,route);}
  assert.equal((await fetch(origin)).status,401);
  checks.push('public Caddy blocks machine API including encoded path; native browser login remains required; private gateway accepts tokenless client');
 }
 assert.equal((await fetch(origin+'/api/capabilities')).status,gatewayEnabled?404:401);assert.deepEqual((await api({method:'catalog'})).packages,[]);checks.push('archive hashes, empty separate namespace, production Gunicorn, and unauthenticated API denied');
 const launch=async name=>{browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,headless:true,userDataDir:path.join(base,name),args:['--no-sandbox','--disable-dev-shm-usage'],env});page=await browser.newPage();page.on('pageerror',e=>errors.push(e.message));await page.setViewport({width:1440,height:1000});await page.authenticate({username:'rdg',password:browserToken});await page.goto(origin,{waitUntil:'load'});await page.waitForFunction(()=>globalThis.RDG_PORTABLE_EDITOR&&!RDG_PORTABLE_EDITOR.busy&&RDG_PORTABLE_EDITOR.session&&!!document.querySelector('.rdg-explorer-home'));};
 const idle=()=>page.waitForFunction(()=>!RDG_PORTABLE_EDITOR.busy),state=()=>page.evaluate(()=>RDG_PORTABLE_EDITOR.view);
 const click=async(text,scope='.rdg-decision')=>{for(let i=0;i<8;i++){const summary=await page.evaluateHandle(({text,scope})=>{const b=[...document.querySelectorAll(scope+' button')].find(b=>(b.textContent===text||b.getAttribute('aria-label')===text)&&!b.disabled);let outer=null;for(let n=b?.parentElement;n;n=n.parentElement)if(n.tagName==='DETAILS'&&!n.open)outer=n;return outer?.querySelector(':scope > summary')||null;},{text,scope});if(!summary.asElement()){await summary.dispose();break;}await summary.asElement().click();await summary.dispose();await idle();}const h=await page.evaluateHandle(({text,scope})=>[...document.querySelectorAll(scope+' button')].find(b=>(b.textContent===text||b.getAttribute('aria-label')===text)&&!b.disabled),{text,scope});assert(h.asElement(),'Missing '+text);await h.asElement().click();await h.dispose();await idle();assert.equal(await page.$eval('.rdg-status',n=>n.classList.contains('rdg-error')?n.textContent:''),'',text);};
 const field=async(label,value)=>page.evaluate(({label,value})=>{const row=[...document.querySelectorAll('.rdg-modal label')].find(n=>n.firstChild?.textContent.trim()===label);if(!row)throw Error('Missing field '+label);const n=row.querySelector('input,textarea,select');n.value=value;n.dispatchEvent(new Event(n.tagName==='SELECT'?'change':'input',{bubbles:true}));},{label,value});
 const save=()=>click('Сохранить','.rdg-modal');
 await launch('browser');assert.equal(await page.evaluate(()=>RDG_BUILD_ID),manifest.serverBuild);assert.equal((await (await fetch(origin+'/healthz')).json()).buildId,manifest.serverBuild);assert.equal(await state(),null);const html=await page.content();assert(!html.includes(browserToken)&&!html.includes(agentToken));await page.screenshot({path:path.join(base,'server-explorer.png'),fullPage:true});
 await click('+ Создать процесс','.rdg-explorer');await field('Название','Общий сервер RDG');await field('Назначение процесса','Проверить общий API браузера и ИИ');await field('Основание процесса','Изолированная серверная проверка');await click('Проверить создание');assert.equal((await api({method:'catalog'})).packages.length,0);await save();let view=await state();const ident=view.package.packageId;assert.equal((await api({method:'catalog'})).packages.length,1);assert.deepEqual(view.graph.recommendationPackageIds,[]);assert(view.graph.events.some(e=>e.by==='user'));checks.push('native browser login opens the real Explorer; UI creates process through preflight/Save and shared writer');
 let request=(await api({method:'schema',op:'core',packageId:ident,nodeId:'R1',command:'add'})).request;request.data={entity:{id:'D-REMOTE',kind:'decision',title:'Создан ИИ через API',description:'Существующий Application'},initialRelations:[{id:'R-D-REMOTE',type:'DRIVES',from:'R1',to:'D-REMOTE'}]};request.note='Actual agent request';const preview=await api({method:'preflight',request});const applied=await api({method:'apply',request,expectedInputBinding:preview.inputBinding});assert(applied.published);assert((await api({method:'apply',request,expectedInputBinding:preview.inputBinding})).idempotent);await click('Обновить','.rdg-head');view=await state();assert(view.graph.nodes.some(n=>n.id==='D-REMOTE'));assert(view.graph.events.some(e=>e.by==='assistant'));checks.push('private tokenless AI client updates the same process; Viewer refresh sees assistant facts and exact retry adds no duplicate');
 await click('Добавить план во времени');await save();await click('+ Размещение','.rdg-tools');await field('Разместить блок','D-REMOTE');await click('Проверить размещение','.rdg-modal');await save();view=await state();assert.equal(view.plan.steps.length,1);assert.deepEqual(view.plan.timeConstraints,[]);assert.equal(view.view.spec.compactGraph,true,'Server Viewer must open compact by default');
 await click('Моя раскладка','.rdg-zoom');
 assert.equal((await state()).view.spec.compactGraph,false,
   'Owner layout writes require the explicit manual mode');
 await click('Вписать','.rdg-tools');const node=await page.$('[data-entity-id="D-REMOTE"]'),box=await node.boundingBox();assert(box);await page.mouse.move(box.x+60,box.y+30);await page.mouse.down();await page.mouse.move(box.x+110,box.y+70,{steps:6});await page.mouse.up();await idle();const saved=await api({method:'read',packageId:ident,includePlan:true});assert(saved.layouts);checks.push('authenticated UI Plan and persisted drag use the common writer; AI reads the same Plan/layout');
 await page.screenshot({path:path.join(base,'server-desktop.png'),fullPage:true});const oldTabUrl=page.url();await stopGateway();await stop();const nextPid=await start();assert.notEqual(firstPid,nextPid);const nextGatewayPid=await startGateway();if(gatewayEnabled)assert.notEqual(firstGatewayPid,nextGatewayPid);
 // The operator keeps the tab open across a code update and presses F5.
 // The prior document capability is stale; only the authenticated GET redirects.
 await page.reload({waitUntil:'load'});await page.waitForFunction(()=>globalThis.RDG_PORTABLE_EDITOR&&!RDG_PORTABLE_EDITOR.busy&&RDG_PORTABLE_EDITOR.session&&!!document.querySelector('.rdg-explorer-home'));
 assert.notEqual(page.url(),oldTabUrl);assert.equal(await page.evaluate(()=>RDG_BUILD_ID),manifest.serverBuild);
 await click('Общий сервер RDG','.rdg-explorer');const f5Restored=await state();for(const key of ['graph','plan','layouts','recommendations'])assert.deepEqual(f5Restored[key],saved[key]);checks.push('existing authenticated tab F5 after backend restart redirects stale document and restores exact Graph/Plan/layout');
 await browser.close();browser=null;await launch('fresh-browser');assert.equal(await state(),null);await click('Общий сервер RDG','.rdg-explorer');const restored=await state();for(const key of ['graph','plan','layouts','recommendations'])assert.deepEqual(restored[key],saved[key]);assert.deepEqual(errors,[]);checks.push('new production process + clean authenticated browser restore exact Graph/Plan/layout/registry');
 const result={pass:true,cases:checks.length,checks,artifacts:base,archiveSHA256:crypto.createHash('sha256').update(fs.readFileSync(archive)).digest('hex'),reverseProxyVerified:!!caddy,privateGatewayVerified:gatewayEnabled,clientCredentialRequired:!gatewayEnabled,dockerEngineVerified:false,publicHTTPSVerified:false,liveOwnersChanged:false};fs.writeFileSync(path.join(base,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }catch(e){fs.writeFileSync(path.join(base,'failure.json'),JSON.stringify({error:safe(e),checks,errors},null,2));if(page)await page.screenshot({path:path.join(base,'failure.png'),fullPage:true}).catch(()=>{});console.error('Artifacts: '+base);throw e;}finally{await cleanup();}})().catch(e=>{console.error(safe(e));process.exitCode=1;});
