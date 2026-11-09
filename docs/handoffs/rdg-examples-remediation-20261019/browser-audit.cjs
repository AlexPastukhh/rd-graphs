'use strict';
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../../..'),out=path.join(__dirname,'browser'),index=require(path.join(root,'graphs/index.json'));
const puppeteer=require('/opt/dc/node_modules/puppeteer-core');
const chrome='/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell';
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--allow-file-access-from-files']});
 const rows=[],errors=[];
 try{
  const page=await browser.newPage();await page.setViewport({width:1440,height:900});page.on('pageerror',e=>errors.push(e.message));
  await page.goto('file://'+path.join(root,'tests/visual/rdg-viewer.html'),{waitUntil:'load'});
  await page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  const click=id=>page.evaluate(id=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById(id).click(),id);
  const inspect=()=>page.evaluate(()=>{
   const h=document.getElementById('rdg-viewer-root'),s=h.shadowRoot;
   const nodes=[...s.querySelectorAll('#canvas .node')].map(n=>{
    const p=n.getAttribute('transform').match(/[-\d.]+/g).map(Number);return {id:n.getAttribute('data-id'),kind:[...n.classList].find(x=>!['node','root','drill','selected','dim','appearing'].includes(x)),x:p[0],y:p[1]};
   }),overlaps=[];
   for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
    const a=nodes[i],b=nodes[j];if(Math.abs(a.x-b.x)<222-.01&&Math.abs(a.y-b.y)<72-.01)overlaps.push([a.id,b.id]);
   }
   return {version:h.dataset.rdgVersion,nodes:nodes.length,kinds:Object.fromEntries([...new Set(nodes.map(n=>n.kind))].map(k=>[k,nodes.filter(n=>n.kind===k).length])),
    overlaps,edges:s.querySelectorAll('#canvas .edge').length,
    annotations:s.querySelectorAll('#canvas .canon-attachment').length,message:s.getElementById('message').textContent};
  });
  await click('launch');
  for(const item of index.graphs){
   try{
    const graph=JSON.parse(fs.readFileSync(path.join(root,'graphs',item.file),'utf8'));
    await page.evaluate(g=>document.getElementById('rdg-viewer-root').rdgWorkflow.loadGraph(g),graph);await click('graph-tab');
    for(const mode of ['edges-core','edges-all']){await click(mode);rows.push({slug:item.slug,scope:'local',mode,...await inspect()});}
   }catch(error){rows.push({slug:item.slug,scope:'local',error:error.message});}
   if(rows.length%50===0)console.log('LOCAL_VIEWS',rows.length);
  }
  for(const item of index.fullGraphs){
   try{
    await page.evaluate(slug=>document.getElementById('rdg-viewer-root').rdgExplorer.openFull(slug),item.slug);
    for(const all of [false,true]){
     await page.evaluate(all=>{const s=document.getElementById('rdg-viewer-root').shadowRoot,b=s.getElementById('variants-all');
      if(!b.hidden&&b.getAttribute('aria-pressed')!==String(all))b.click();},all);
     for(const mode of ['edges-core','edges-all']){
      await click(mode);const state=await inspect();rows.push({slug:item.slug,scope:'full',allBranches:all,mode,...state});
      if(['reference-prepared-planning-tree','reference-mixed-active-work'].includes(item.slug)){
       await page.screenshot({path:path.join(out,item.slug+'-'+(all?'all':'current')+'-'+mode+'.png')});
      }
     }
    }
   }catch(error){rows.push({slug:item.slug,scope:'full',error:error.message});}
  }
  for(const slug of ['reference-prepared-feature-consistency','reference-mixed-feature-consistency','reference-mixed-contextual-split']){
   await page.evaluate(slug=>document.getElementById('rdg-viewer-root').rdgExplorer.openGraph(slug),slug);
   await click('variants-all');await click('edges-all');await click('fit');
   rows.push({slug,scope:'active-local-navigation',...await inspect()});
   await page.screenshot({path:path.join(out,slug+'.png')});
  }
  const result={viewerVersion:await page.evaluate(()=>document.getElementById('rdg-viewer-root').dataset.rdgVersion),views:rows.length,errors,renderErrors:rows.filter(x=>x.error),overlapViews:rows.filter(x=>x.overlaps?.length),rows};
  fs.writeFileSync(path.join(__dirname,'browser-results.json'),JSON.stringify(result,null,2)+'\n');
  console.log('BROWSER_AUDIT_RESULT',JSON.stringify({version:result.viewerVersion,views:result.views,pageErrors:errors.length,renderErrors:result.renderErrors.length,overlapViews:result.overlapViews.length}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
