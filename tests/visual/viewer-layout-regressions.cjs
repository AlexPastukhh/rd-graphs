'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const out=path.resolve(process.env.RDG_SCREENSHOT_DIR||'/workspace/repo/rdg-layout-fixes-output');fs.mkdirSync(out,{recursive:true});
const shared=path.join(out,'shared-layouts.json'),inputFile=path.join(out,'manual-levels.json');
const fixture={schemaVersion:1,id:'browser-layout-fixes',revision:1,identitySpace:'browser-layout-fixes',rootRequirementId:'R',
 nodes:[{id:'R',kind:'requirement',title:'Root'},{id:'O',kind:'option',title:'Method'},...['A','B','C','DEEP'].map(id=>({id,kind:'requirement',title:id})),{id:'AO',kind:'option',title:'Child method'},{id:'DEEP-O',kind:'option',title:'Deep method'}],
 edges:[{id:'ro',type:'OPTION_FOR',from:'R',to:'O'},...['A','B','C'].map(id=>({id:'e'+id,type:'OUTCOME_OF',from:'O',to:id})),{id:'ao',type:'OPTION_FOR',from:'A',to:'AO'},{id:'deep',type:'OUTCOME_OF',from:'AO',to:'DEEP'},{id:'deep-o',type:'OPTION_FOR',from:'DEEP',to:'DEEP-O'}],
 collections:[{id:'list',title:'Requirements',anchor:'O',memberRefs:['A','B','C']}]};
fs.writeFileSync(shared,JSON.stringify({schemaVersion:1,revision:0,layouts:{}}));fs.writeFileSync(inputFile,JSON.stringify(fixture));
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--allow-file-access-from-files'],userDataDir:path.join(out,'isolated-profile')});
 const errors=[];
 const configure=async p=>{
  await p.setViewport({width:1440,height:900});p.on('pageerror',e=>errors.push(e.stack));p.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await p.exposeFunction('readTestLayouts',()=>fs.readFileSync(shared,'utf8'));await p.exposeFunction('writeTestLayouts',text=>fs.writeFileSync(shared,text));
  await p.evaluateOnNewDocument(()=>{
   globalThis.layoutTestHandle={name:'shared-layouts.json',getFile:async()=>({text:()=>readTestLayouts()}),createWritable:async()=>{let pending;return{write:async text=>{pending=text;globalThis.testWriteEntered=true;if(globalThis.pauseTestWrite)await new Promise(r=>globalThis.releaseTestWrite=r)},close:()=>writeTestLayouts(pending),abort:async()=>{}}}};
   window.showSaveFilePicker=async()=>layoutTestHandle;window.showOpenFilePicker=async()=>[layoutTestHandle];
   globalThis.GM_xmlhttpRequest=r=>{if(!r.url.endsWith('/layouts.json'))return r.onerror({});readTestLayouts().then(responseText=>r.onload({status:0,responseText}),r.onerror)};
  });
 };
 const page=await browser.newPage();await configure(page);
 const el=(p,selector)=>p.evaluateHandle(sel=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector(sel),selector);
 const click=async(p,selector)=>{const h=await el(p,selector);assert(h.asElement(),'missing '+selector);await h.asElement().click();await h.dispose();};
 const upload=async p=>{const h=await el(p,'#picker');await h.asElement().uploadFile(inputFile);await h.dispose();await p.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('[data-id="R"]'))};
 const go=async p=>{await p.goto('file://'+path.join(__dirname,'rdg-viewer.html'));await p.waitForFunction(()=>document.getElementById('rdg-viewer-root')?.shadowRoot?.querySelector('[data-folder]'));await click(p,'#launch');await upload(p)};
 const world=(p,id)=>p.evaluate(id=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('[data-id="'+id+'"]').getAttribute('transform'),id);
 const camera=p=>p.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('scene').getAttribute('transform'));
 const ids=p=>p.evaluate(()=>[...document.getElementById('rdg-viewer-root').shadowRoot.querySelectorAll('#canvas .node')].map(n=>n.getAttribute('data-id')));
 const drag=async(p,id,dx,dy)=>{const box=await p.evaluate(id=>{const r=document.getElementById('rdg-viewer-root').shadowRoot.querySelector('[data-id="'+id+'"]').getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}},id);await p.mouse.move(box.x,box.y);await p.mouse.down();await p.mouse.move(box.x+dx,box.y+dy,{steps:10});await p.mouse.up()};
 const save=async p=>{await p.evaluate(()=>document.getElementById('rdg-viewer-root').rdgLayout.save())};
 const attach=async p=>p.evaluate(async()=>{const a=document.getElementById('rdg-viewer-root').rdgLayout;await a.attachFile(layoutTestHandle);a.pause()});
 const shot=async name=>{await page.screenshot({path:path.join(out,name+'.png')});console.log('SCREEN',name)};
 try{
  await go(page);await attach(page);assert(!(await ids(page)).includes('AO'));
  const initialCamera=await camera(page),rootBefore=await world(page,'R');await click(page,'[data-id="__collection__list"]');
  assert.deepEqual((await ids(page)).sort(),['R','O','A','B','C'].sort());assert.equal(await camera(page),initialCamera);assert.equal(await world(page,'R'),rootBefore);
  await click(page,'#collections-collapse');await drag(page,'__collection__list',60,45);const header=await world(page,'__collection__list');await save(page);await shot('01-group-saved');await go(page);assert.equal(await world(page,'__collection__list'),header);await shot('02-group-restored');console.log('PASS group roundtrip');
  await attach(page);await page.evaluate(()=>{const a=document.getElementById('rdg-viewer-root').rdgLayout;a.apply({type:'set_positions',positions:{R:{x:48,y:72}}});globalThis.pauseTestWrite=true;globalThis.testWriteEntered=false;globalThis.pendingTestSave=a.save()});
  await page.waitForFunction(()=>globalThis.testWriteEntered===true);await drag(page,'R',80,35);const later=await world(page,'R');await page.evaluate(async()=>{releaseTestWrite();await pendingTestSave;globalThis.pauseTestWrite=false});
  const state=await page.evaluate(()=>{const h=document.getElementById('rdg-viewer-root'),a=h.rdgLayout;return{p:a.getDocument().layouts[a.graphKey()].positions.R,dirty:h.shadowRoot.getElementById('layout-save').textContent.includes('*')}});assert.equal(later,'translate('+state.p.x+' '+state.p.y+')');assert(state.dirty);await shot('03-new-edit-remains-dirty');await save(page);await go(page);assert.equal(await world(page,'R'),later);console.log('PASS async save retains actual mouse movement');
  await click(page,'[data-id="__collection__list"]');await click(page,'[data-id="A"]');assert.deepEqual((await ids(page)).sort(),['A','AO','DEEP'].sort());await click(page,'[data-id="DEEP"]');assert.deepEqual((await ids(page)).sort(),['DEEP','DEEP-O'].sort());await click(page,'#level-up');await click(page,'#level-up');assert((await ids(page)).includes('R'));console.log('PASS manual local levels');
  await page.evaluate(()=>{globalThis.nativeFileChanges=0;document.getElementById('rdg-viewer-root').shadowRoot.getElementById('picker').addEventListener('change',()=>nativeFileChanges++)});
  fixture.revision=2;fs.writeFileSync(inputFile,JSON.stringify(fixture));await upload(page);await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('picker').value==='');await upload(page);await page.waitForFunction(()=>nativeFileChanges===2);assert.equal(await page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('picker').value),'');console.log('PASS same native file selected twice');
  await page.evaluate(()=>{const h=document.getElementById('rdg-viewer-root');h.rdgLayout.apply({type:'set_positions',positions:{R:{x:-600,y:-300},O:{x:-200,y:-300},__collection__list:{x:200,y:-300}}});h.shadowRoot.getElementById('fit').click()});
  const clipped=await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot,c=s.getElementById('canvas').getBoundingClientRect();return[...s.querySelectorAll('.edge-label')].filter(n=>{const b=n.getBoundingClientRect();return b.left<c.left||b.right>c.right||b.top<c.top||b.bottom>c.bottom}).map(n=>n.getAttribute('data-edge-id'))});assert.deepEqual(clipped,[]);await shot('04-negative-layout');console.log('PASS negative geometry and label fit');
  await page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('layout-discard').click());
  await page.evaluate(()=>document.getElementById('rdg-viewer-root').rdgExplorer.openGraph('reference-mixed-active-work'));await page.mouse.move(450,450);await page.mouse.wheel({deltaY:-160});const before=await camera(page),r0=await world(page,'R0');await click(page,'#variants-all');assert.equal(await camera(page),before);assert.equal(await world(page,'R0'),r0);await shot('05-alternatives-camera');console.log('PASS alternatives retain camera');
  // Use the real Web Locks implementation in two same-origin tabs when present.
  if(await page.evaluate(()=>typeof navigator.locks?.request==='function')){
   await go(page);await attach(page);const other=await browser.newPage();await configure(other);await go(other);await attach(other);
   await page.evaluate(()=>{const a=document.getElementById('rdg-viewer-root').rdgLayout;a.apply({type:'set_positions',positions:{R:{x:101,y:102}}});globalThis.pauseTestWrite=true;globalThis.testWriteEntered=false;globalThis.pendingTestSave=a.save()});await page.waitForFunction(()=>testWriteEntered===true);
   await other.evaluate(()=>{const a=document.getElementById('rdg-viewer-root').rdgLayout;a.apply({type:'set_positions',positions:{R:{x:901,y:902}}});globalThis.testWriteEntered=false;globalThis.pendingOtherSave=a.save().then(()=>({ok:true}),e=>({ok:false,message:e.message}))});
   await page.evaluate(async()=>{releaseTestWrite();await pendingTestSave});const result=await other.evaluate(()=>pendingOtherSave);assert.equal(result.ok,false);assert.match(result.message,/изменён извне/);assert.equal(Object.values(JSON.parse(fs.readFileSync(shared)).layouts).find(l=>l.positions.R)?.positions.R.x,101);await other.close();console.log('PASS native Web Locks serializes connected tabs');
  }else console.log('LIMIT native Web Locks unavailable; sequential writer policy applies');
  assert.deepEqual(errors,[]);console.log('LAYOUT_BROWSER_REGRESSIONS_PASS pageerrors=0');
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack);process.exitCode=1});
