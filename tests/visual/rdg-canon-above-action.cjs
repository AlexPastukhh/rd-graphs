'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require('/opt/dc/node_modules/puppeteer-core');
const out=path.resolve(process.env.RDG_SCREENSHOT_DIR||'/workspace/repo/rdg-canon-attachment-browser');
const chrome=process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell';
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--allow-file-access-from-files']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.setViewport({width:1440,height:900});
  await page.goto('file://'+path.join(__dirname,'rdg-viewer.html'),{waitUntil:'load'});
  await page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  const run=(fn,arg)=>page.evaluate(fn,arg),click=id=>run(id=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById(id).click(),id);
  const g=JSON.parse(fs.readFileSync(path.join(__dirname,'../fixtures/rdg-v6-action-optin/graph.json'),'utf8'));
  const a=structuredClone(g.nodes.find(n=>n.id==='A1'));a.id='A2';a.title='Другой способ достижения цели';a.status='candidate';delete a.selectionBasis;
  g.nodes.push(a);g.edges.push({id:'dA2',type:'DRIVES',from:'R0',to:'A2'});
  await click('launch');await run(g=>document.getElementById('rdg-viewer-root').rdgWorkflow.loadGraph(g),g);
  await click('graph-tab');await click('variants-all');await click('fit');
  const pairs=()=>run(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   return [...s.querySelectorAll('#canvas .node.canon')].map(n=>{
    const id=n.getAttribute('data-canon-for'),c=n.getBoundingClientRect(),owner=s.querySelector('#canvas .node[data-id="'+id+'"]'),a=owner.getBoundingClientRect();
    const edge=s.querySelector('#canvas .edge[data-edge-id="__viewcanon__'+id+'"]');
    return {id,canon:{x:c.x,y:c.y,w:c.width,h:c.height},owner:{x:a.x,y:a.y,w:a.width,h:a.height},
     marker:edge.getAttribute('marker-end'),path:edge.getAttribute('d')};
   });
  });
  const validate=rows=>{assert.equal(rows.length,2);for(const p of rows){
   assert(Math.abs(p.canon.x-p.owner.x)<1);assert(p.canon.y+p.canon.h<p.owner.y);assert.equal(p.marker,null);
   const route=p.path.match(/[-\d.]+/g).map(Number);assert.equal(route[0],route[2]);
  }};
  validate(await pairs());await page.screenshot({path:path.join(out,'actions-canons-above.png')});
  const before=(await pairs()).find(p=>p.id==='A2'),b=before.owner;
  await page.mouse.move(b.x+b.w*.4,b.y+b.h*.7);await page.mouse.down();await page.mouse.move(b.x+b.w*.4+90,b.y+b.h*.7+45,{steps:8});await page.mouse.up();
  const moved=(await pairs()).find(p=>p.id==='A2');validate(await pairs());assert(moved.owner.x>before.owner.x+80);
  const c=moved.canon;
  await page.mouse.move(c.x+c.w*.3,c.y+c.h*.5);await page.mouse.down();await page.mouse.move(c.x+c.w*.3+50,c.y+c.h*.5+30,{steps:8});await page.mouse.up();
  const movedByCanon=(await pairs()).find(p=>p.id==='A2');validate(await pairs());assert(movedByCanon.owner.x>moved.owner.x+40);
  await page.screenshot({path:path.join(out,'drag-pair.png')});
  await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('#canvas .node[data-id="__canon__A2"]').dispatchEvent(new MouseEvent('click',{bubbles:true})));
  // Wait until drag-click suppression passes, then use keyboard activation of canon.
  await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.querySelector('#canvas .node[data-id="__canon__A2"]').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})));
  assert.match(await run(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('info').textContent),/Канонические ситуации/);
  const legacy=JSON.parse(fs.readFileSync(path.join(__dirname,'../../graphs/examples/reference-mixed-contextual-split/graph.json'),'utf8'));
  await run(g=>document.getElementById('rdg-viewer-root').rdgWorkflow.loadGraph(g),legacy);await click('graph-tab');await click('fit');
  const legacyPair=()=>run(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   const a=s.querySelector('#canvas .node[data-id="D-A"]').getBoundingClientRect(),c=s.querySelector('#canvas .node[data-id="__canon__O-A"]').getBoundingClientRect();
   return {a:{x:a.x,y:a.y,w:a.width,h:a.height},c:{x:c.x,y:c.y,w:c.width,h:c.height}};
  });
  const old=await legacyPair();assert(Math.abs(old.a.x-old.c.x)<1);assert(old.c.y+old.c.h<old.a.y);
  await page.screenshot({path:path.join(out,'selected-decision-canon.png')});
  for(let i=0;i<2;i++){
   await click('variants-all');const pair=await legacyPair();
   assert(Math.abs(pair.a.x-pair.c.x)<1);assert(pair.c.y+pair.c.h<pair.a.y);
  }

  // Reproduce the user's old 124px rows, where the second canon covered A1.
  const dense=structuredClone(g);dense.id='dense-canons-browser';dense.events=[];
  dense.nodes=dense.nodes.filter(n=>['R0','A1','A2'].includes(n.id));
  dense.nodes.forEach(n=>{if(n.kind==='action'){n.status='candidate';delete n.selectionBasis;}});
  dense.edges=dense.edges.filter(e=>dense.nodes.some(n=>n.id===e.from)&&dense.nodes.some(n=>n.id===e.to));
  await run(g=>document.getElementById('rdg-viewer-root').rdgWorkflow.loadGraph(g),dense);await click('graph-tab');
  await run(async()=>{
   const h=document.getElementById('rdg-viewer-root'),empty={schemaVersion:1,revision:0,layouts:{}};
   window.__layoutText=JSON.stringify(empty);
   const file={name:'isolated-layouts.json',getFile:async()=>({text:async()=>window.__layoutText}),
    createWritable:async()=>{let text;return {write:async value=>{text=value;},close:async()=>{window.__layoutText=text;}};}};
   h.shadowRoot.getElementById('layout-discard').click();
   await h.rdgLayout.attachFile(file);
   h.rdgLayout.apply({type:'set_positions',positions:{R0:{x:48,y:300},A1:{x:468,y:190},A2:{x:468,y:314}}});
  });
  await click('fit');
  const world=()=>run(()=>{
   const s=document.getElementById('rdg-viewer-root').shadowRoot;
   return Object.fromEntries([...s.querySelectorAll('#canvas .node')].map(n=>[n.getAttribute('data-id'),n.getAttribute('transform').match(/[-\d.]+/g).map(Number)]));
  });
  const clear=positions=>{
   const boxes=Object.entries(positions);
   for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
    const [id,a]=boxes[i],[other,b]=boxes[j];assert(!(Math.abs(a[0]-b[0])<222&&Math.abs(a[1]-b[1])<72),'dense overlap: '+id+' / '+other);
   }
  };
  validate(await pairs());clear(await world());await page.screenshot({path:path.join(out,'dense-layout-repaired.png')});
  const first=(await pairs()).find(p=>p.id==='A1').owner;
  await page.mouse.move(first.x+first.w*.4,first.y+first.h*.7);await page.mouse.down();
  await page.mouse.move(first.x+first.w*.4,first.y+first.h*.7+20,{steps:5});await page.mouse.up();
  clear(await world());const displayed=await world();
  const saved=await run(async()=>{
   const h=document.getElementById('rdg-viewer-root');await h.rdgLayout.save({interactive:false});
   return JSON.parse(window.__layoutText);
  });
  await page.reload({waitUntil:'load'});
  await page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  await run(({g,layout})=>{const h=document.getElementById('rdg-viewer-root');h.rdgLayout.load(layout);return h.rdgWorkflow.loadGraph(g);},{g:dense,layout:saved});
  await click('graph-tab');await click('fit');clear(await world());validate(await pairs());
  assert.deepEqual(await world(),displayed,'automatic save/reload preserves repaired geometry including pushed pairs');
  await page.screenshot({path:path.join(out,'dense-drag-saved-reload.png')});

  assert.deepEqual(errors,[]);console.log('BROWSER_CANON_ABOVE_PASS: aligned pairs, dense saved-row collision repair, real dragging, automatic save/reload, inspector, selected legacy Decision; pageerrors=0');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
