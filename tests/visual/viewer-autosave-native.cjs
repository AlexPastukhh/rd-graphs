'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const out=path.resolve(process.env.RDG_SCREENSHOT_DIR||'/workspace/repo/rdg-autosave-native-output');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--allow-file-access-from-files'],userDataDir:path.join(out,'isolated-profile')});
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.stack));page.on('dialog',d=>d.accept());
 await page.setViewport({width:1440,height:900});
 const start=async()=>{await page.goto('file://'+path.join(__dirname,'rdg-viewer.html'));await page.waitForFunction(()=>document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());await page.evaluate(()=>{const h=document.getElementById('rdg-viewer-root');h.shadowRoot.getElementById('launch').click();return h.rdgExplorer.openSet('example-prepared')})};
 const state=()=>page.evaluate(()=>document.getElementById('rdg-viewer-root').rdgLayout.status());
 const shot=async name=>{await page.screenshot({path:path.join(out,name+'.png')});console.log('SCREEN',name)};
 try{
  await start();
  const native=await page.evaluate(async()=>{
   if(!navigator.storage?.getDirectory)throw Error('Native OPFS unavailable');
   const dir=await navigator.storage.getDirectory(),handle=await dir.getFileHandle('rdg-native-layouts.json',{create:true});
   const api=document.getElementById('rdg-viewer-root').rdgLayout;
   const writer=await handle.createWritable();await writer.write(JSON.stringify(api.getDocument()));await writer.close();
   await api.attachFile(handle);globalThis.nativeLayoutHandle=handle;
   return {native:handle instanceof FileSystemFileHandle,queryPermission:await handle.queryPermission({mode:'readwrite'})};
  });
  assert.equal(native.native,true);assert.equal(native.queryPermission,'granted');console.log('NATIVE_HANDLE',JSON.stringify(native));
  const slug='reference-prepared-planning-tree';
  const box=await page.evaluate(slug=>{const h=document.getElementById('rdg-viewer-root'),s=h.shadowRoot,q=s.getElementById('search');q.value=slug;q.dispatchEvent(new Event('input'));q.value='';q.dispatchEvent(new Event('input'));const r=s.querySelector('[data-id="'+slug+'"]').getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}},slug);
  await page.mouse.move(box.x,box.y);await page.mouse.down();await page.mouse.move(box.x+110,box.y+40,{steps:10});await page.mouse.up();
  const expected=await page.evaluate(slug=>{const a=document.getElementById('rdg-viewer-root').rdgLayout;return a.getDocument().layouts[a.graphKey()].positions[slug]},slug);
  await page.waitForFunction(()=>{const a=document.getElementById('rdg-viewer-root').rdgLayout,s=a.status();return !s.dirty&&!s.saving&&s.lastSaved!==null},{timeout:10000});
  assert.equal((await state()).blocked,'');await shot('01-native-autosaved');
  const disk=await page.evaluate(async()=>JSON.parse(await (await nativeLayoutHandle.getFile()).text()));assert.deepEqual(disk.layouts[JSON.stringify({type:'graph-set',id:'example-prepared'})].positions[slug],expected);
  await start();
  const restored=await page.evaluate(slug=>{const h=document.getElementById('rdg-viewer-root'),a=h.rdgLayout;return {p:a.getDocument().layouts[a.graphKey()].positions[slug],status:h.shadowRoot.getElementById('layout-status').textContent}},slug);
  assert.deepEqual(restored.p,expected);assert.match(restored.status,/Файл подключён/);await shot('02-native-handle-restored');
  await page.evaluate(slug=>{const a=document.getElementById('rdg-viewer-root').rdgLayout;a.pause();a.apply({type:'set_positions',positions:{[slug]:{x:25,y:35}}})},slug);
  assert((await state()).dirty);await start();
  assert.match((await state()).blocked,/Восстановлен черновик расположения блоков/);assert((await state()).dirty);await shot('03-native-crash-draft');
  await page.evaluate(()=>document.getElementById('rdg-viewer-root').rdgLayout.save());assert.equal((await state()).dirty,false);
  await page.evaluate(()=>document.getElementById('rdg-viewer-root').rdgLayout.apply({type:'clear_layout'}));
  await page.waitForFunction(()=>!document.getElementById('rdg-viewer-root').rdgLayout.status().dirty,{timeout:10000});
  const cleared=await page.evaluate(()=>{const a=document.getElementById('rdg-viewer-root').rdgLayout;return a.getDocument().layouts[a.graphKey()]});assert.equal(cleared,undefined);await shot('04-native-reset-autosaved');
  assert.deepEqual(errors,[]);console.log('NATIVE_OPFS_AUTOSAVE_PASS pageerrors=0; isolated Chromium only, not Windows Tampermonkey');
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack);process.exitCode=1});
