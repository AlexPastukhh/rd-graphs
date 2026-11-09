/* Real Chromium: native OPFS directory handles round-trip through IndexedDB.
 * Picker and permission decisions are simulated; no user folders are accessed. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const puppeteer=require('/opt/dc/node_modules/puppeteer-core');
const root=path.resolve(__dirname,'../..'),out=path.resolve(process.env.RDG_SCREENSHOT_DIR||'/workspace/repo/rdg-session-memory-browser');
const chrome=process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell';
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const allowed=new Map([['/',path.join(__dirname,'rdg-viewer.html')],
  ['/tools/rd-graph-viewer.user.js',path.join(root,'tools/rd-graph-viewer.user.js')],
  ['/tools/rd-graph-data.js',path.join(root,'tools/rd-graph-data.js')]]);
 const server=http.createServer((req,res)=>{
  const file=allowed.get(req.url);if(!file){res.writeHead(404);return res.end();}
  res.setHeader('content-type',req.url==='/'?'text/html; charset=utf-8':'text/javascript; charset=utf-8');res.end(fs.readFileSync(file));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let browser;
 try{
  browser=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.setViewport({width:1440,height:900});
  const graph=JSON.parse(fs.readFileSync(path.join(root,'graphs/examples/example/graph.json'),'utf8'));
  await page.evaluateOnNewDocument(graph=>{
   window.__picks=0;window.__requests=0;window.__reads=0;window.__permission='granted';window.__choice='session-primary';
   window.__snapshot={title:'Проверка сохранения папки',graphFile:'workspaces/synthetic/graph.json',permissions:['graph.read','plan.read'],
    future:[],history:[],unresolved:[],sources:{graphs:{'workspaces/synthetic/graph.json':graph},completion:{},
    plan:{revision:1,steps:[],timeConstraints:[],sequence:[]}}};
   const permissionKey='rdg-test-permission';
   window.__permission=sessionStorage.getItem(permissionKey)||'granted';
   Object.defineProperty(FileSystemHandle.prototype,'queryPermission',{configurable:true,value:async()=>window.__permission});
   Object.defineProperty(FileSystemHandle.prototype,'requestPermission',{configurable:true,value:async()=>{
    window.__requests++;if(window.__permission==='denied')return 'denied';
    window.__permission='granted';sessionStorage.setItem(permissionKey,'granted');return 'granted';
   }});
   const put=async(folder,name,text)=>{const f=await folder.getFileHandle(name,{create:true}),w=await f.createWritable();await w.write(text);await w.close();};
   const folders=navigator.storage.getDirectory().then(async root=>{
    const list=[];
    for(const name of ['session-primary','session-other']){
     const folder=await root.getDirectoryHandle(name,{create:true});list.push(folder);
     try{await folder.getFileHandle('session.json');}catch(_){await put(folder,'session.json',JSON.stringify({schemaVersion:1,
      kind:'rdg-local-manual-session',active:true,session:'isolated-test-session'}));}
    }
    return list;
   });
   window.__setActive=async active=>put((await folders)[0],'session.json',JSON.stringify({schemaVersion:1,kind:'rdg-local-manual-session',
    active,...(active?{session:'isolated-test-session'}:{})}));
   Object.defineProperty(window,'showDirectoryPicker',{configurable:true,value:async()=>{
    window.__picks++;if(window.__choice==='cancel')throw new DOMException('Cancelled','AbortError');
    return (await folders).find(f=>f.name===window.__choice);
   }});
   let working=false;
   setInterval(async()=>{
    if(working)return;working=true;
    try{for(const folder of await folders)for await(const [name] of folder.entries()){
     if(!name.startsWith('request-')||!name.endsWith('.ready'))continue;
     const response=name.replace('request-','response-').replace('.ready','.json');
     try{await folder.getFileHandle(response);continue;}catch(_){}
     window.__reads++;await put(folder,response,JSON.stringify({ok:true,result:window.__snapshot}));
    }}catch(error){console.error(error);}finally{working=false;}
   },30);
  },graph);
  const url='http://127.0.0.1:'+server.address().port+'/';
  const ui=fn=>page.evaluate(fn);
  const click=id=>page.evaluate(id=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById(id).click(),id);
  const waitStatus=async text=>{
   try{await page.waitForFunction(text=>document.getElementById('rdg-viewer-root')?.shadowRoot.getElementById('workflow-connection').textContent.includes(text),{timeout:15000},text);}
   catch(error){
    console.error('SESSION_MEMORY_STATUS',text,await page.evaluate(()=>{
     const s=document.getElementById('rdg-viewer-root')?.shadowRoot;
     return {connection:s?.getElementById('workflow-connection').textContent,
      panel:s?.getElementById('workflow-panel').textContent,connectDisabled:s?.getElementById('workflow-connect').disabled,
      picks:window.__picks,requests:window.__requests,reads:window.__reads,permission:window.__permission};
    }));
    await page.screenshot({path:path.join(out,'failure.png')});throw error;
   }
  };
  const ready=()=>page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  const reload=async()=>{await page.reload({waitUntil:'load'});await ready();await waitStatus('Сохранена папка');};
  const note=()=>ui(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-folder-note').textContent);
  await page.goto(url,{waitUntil:'load'});await ready();await click('launch');await click('workflow-toggle');
  await click('workflow-connect');await waitStatus('подключена.');assert.match(await note(),/session-primary.*запомнена/);
  assert.equal(await ui(()=>window.__picks),1);assert.equal(await ui(()=>window.__requests),0);
  await reload();
  assert.equal(await ui(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-page').hidden),true);
  assert.equal(await ui(()=>window.__picks+window.__requests+window.__reads),0,'reload does not prompt or send a Helper request');
  await click('workflow-toggle');await waitStatus('подключена.');
  assert.equal(await ui(()=>window.__picks+window.__requests),0,'saved permission restores without picker or prompt');
  assert(await ui(()=>window.__reads)>0);
  await ui(()=>sessionStorage.setItem('rdg-test-permission','prompt'));await reload();await click('workflow-toggle');await waitStatus('Для доступа нажмите');
  assert.equal(await ui(()=>window.__picks+window.__requests+window.__reads),0);
  await click('workflow-reconnect');await waitStatus('подключена.');assert.equal(await ui(()=>window.__requests),1);
  await ui(()=>{window.__choice='cancel';});await click('workflow-connect');await waitStatus('отменены');assert.match(await note(),/session-primary.*запомнена/);
  await ui(()=>{window.__choice='session-other';window.__permission='denied';});await click('workflow-connect');await waitStatus('Нет разрешения');
  assert.match(await note(),/session-primary.*запомнена/,'denial preserves previous folder');
  await ui(()=>{window.__permission='granted';});await click('workflow-connect');await waitStatus('подключена.');assert.match(await note(),/session-other.*запомнена/);
  await reload();await click('workflow-toggle');await waitStatus('session-other» подключена.');
  await ui(()=>{window.__choice='session-primary';});await click('workflow-connect');await waitStatus('session-primary» подключена.');
  await ui(()=>window.__setActive(false));await reload();await click('workflow-toggle');
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-panel').textContent.includes('Сессия Helper завершена'));
  assert.match(await note(),/session-primary.*запомнена/);assert.equal(await ui(()=>window.__picks),0);
  await page.screenshot({path:path.join(out,'remembered-expired.png')});
  await click('workflow-forget');await waitStatus('Папка забыта');await page.reload({waitUntil:'load'});await ready();await click('workflow-toggle');
  assert.equal(await ui(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-reconnect').hidden),true);
  assert.equal(await ui(()=>window.__picks+window.__requests+window.__reads),0);
  assert.deepEqual(errors,[]);console.log('BROWSER_SESSION_MEMORY_PASS: native directory handle + real IndexedDB, reload, permissions, cancel, replacement, expiry, forget; pageerrors=0');
 }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
