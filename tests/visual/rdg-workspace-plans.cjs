/* Browser E2E A -> B -> A for independent candidate-v6 Graph/Plan owners.
 * Second independent owner is injected only into this browser test; no old-model
 * graph is ever made active, and no canonical workspace is written by test. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.RDG_PUPPETEER_PACKAGE||'/opt/dc/node_modules/puppeteer-core');
const source=fs.readFileSync(path.resolve(__dirname,'../../tools/rd-graph-data.js'),'utf8');
const match=source.match(/globalThis\.RDG_EMBEDDED_GRAPHS\s*=\s*(\{[\s\S]*\});?/);
assert(match,'read actual delivered bundle');
const bundle=JSON.parse(match[1]);
const A=bundle.fullGraphs[0],graphA=bundle.graphs.find(x=>x.slug===A.slug);
assert(A&&graphA?.graph?.actionModel==='candidate-v6');
const B={...structuredClone(A),slug:'synthetic-independent-v6',file:'workspaces/synthetic-independent-v6/graph.json',
 identitySpace:'separate-test-workspace-identity',title:'Независимый граф B',
 presentation:{usage:'working',title:'Независимый граф B'}};
const graphB={...structuredClone(graphA),slug:B.slug,file:B.file,identitySpace:B.identitySpace,title:B.title,
 graph:{...structuredClone(graphA.graph),id:B.slug,title:B.title,identitySpace:B.identitySpace,
  catalogSlug:B.slug,presentation:{usage:'working'}}};
bundle.graphs.push(graphB);bundle.fullGraphs.push(B);
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.RDG_CHROME_PATH||'/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--allow-file-access-from-files']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewport({width:1200,height:820});
  await page.setRequestInterception(true);
  page.on('request',r=>r.url().endsWith('/rd-graph-data.js')?
   r.respond({status:200,contentType:'text/javascript',body:'globalThis.RDG_EMBEDDED_GRAPHS = '+JSON.stringify(bundle)+';'}):r.continue());
  const contexts=[A,B].map(row=>({rootSlug:row.slug,graphFile:row.file,rootRequirementId:row.rootRequirementId,
    identitySpace:row.identitySpace,planFile:'plans/'+row.slug+'/plan.json'}));
  const snapshots={};
  for(const [i,ctx] of contexts.entries()){
   const g=i===0?graphA.graph:graphB.graph;
   const plan={schemaVersion:1,kind:'temporalPlan',id:ctx.rootSlug,title:'PLAN_'+i,
    revision:1,identitySpace:ctx.identitySpace,status:'candidate',steps:[],sequence:[],branches:[],timeConstraints:[]};
   snapshots[ctx.rootSlug]={schemaVersion:1,contextId:ctx.rootSlug,title:'PLAN_'+i,
    graphFile:ctx.graphFile,planFile:ctx.planFile,permissions:['graph.read','plan.read'],
    future:[],history:[],unresolved:[],sources:{graphs:{[ctx.graphFile]:g},plan,completion:{}}};
  }
  await page.evaluateOnNewDocument(config=>{
   const files=new Map([['session.json',JSON.stringify({schemaVersion:1,kind:'rdg-local-manual-session',
      active:true,session:'synthetic-twov6-scopes',contexts:config.contexts})]]);
   Object.defineProperty(window,'showDirectoryPicker',{configurable:true,value:async()=>({name:'session',kind:'directory',
    queryPermission:async()=>'granted',requestPermission:async()=>'granted',
    async getFileHandle(name,opt={}){
     if(!opt.create&&!files.has(name))throw new DOMException('not found','NotFoundError');
     return {getFile:async()=>({text:async()=>files.get(name)}),createWritable:async()=>{let data='';return {
      write:async x=>{data=x;},close:async()=>{
       files.set(name,data);
       if(name.endsWith('.ready')){
        const request=JSON.parse(files.get(name.replace('.ready','.json'))),which=request.body?.contextId;
        const response=request.kind==='state'&&config.snapshots[which]?{ok:true,result:config.snapshots[which]}:
          {ok:false,error:'WORKSPACE_NOT_REGISTERED',definite:true};
        files.set(name.replace('request-','response-').replace('.ready','.json'),JSON.stringify(response));
       }
      }};}};
    },async removeEntry(name){files.delete(name);}
   })});
  },{contexts,snapshots});
  await page.goto('file://'+path.join(__dirname,'rdg-viewer.html'),{waitUntil:'load'});
  await page.waitForFunction(()=>!!document.getElementById('rdg-viewer-root')?.rdgExplorer?.getCatalog());
  const available=await page.evaluate(()=>document.getElementById('rdg-viewer-root').rdgExplorer.getCatalog().fullGraphs.map(g=>g.slug));
  assert.deepEqual(available,[A.slug,B.slug]);
  async function open(slug){await page.evaluate(async slug=>document.getElementById('rdg-viewer-root').rdgExplorer.openFull(slug),slug);}
  const content=()=>page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-panel').textContent);
  await page.evaluate(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('launch').click());
  await open(A.slug);
  await page.evaluate(()=>{const s=document.getElementById('rdg-viewer-root').shadowRoot;
   s.getElementById('workflow-toggle').click();s.getElementById('workflow-settings').open=true;s.getElementById('workflow-connect').click();});
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-panel').textContent.includes('PLAN_0'),{timeout:15000});
  await open(B.slug);
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-panel').textContent.includes('PLAN_1'),{timeout:15000});
  assert.doesNotMatch(await content(),/PLAN_0/);
  await open(A.slug);
  await page.waitForFunction(()=>document.getElementById('rdg-viewer-root').shadowRoot.getElementById('workflow-panel').textContent.includes('PLAN_0'),{timeout:15000});
  assert.doesNotMatch(await content(),/PLAN_1/);
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('BROWSER_NEW_MODEL_TWO_WORKSPACES_SWITCH_PASS',JSON.stringify({contexts:available,pageErrors:errors.length}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
