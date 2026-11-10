'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {simulate}=require('./viewer-test-helper.cjs');
const projector=require('../tools/rdg-root-projection.js');
const graphDir=path.join(__dirname,'../graphs');
const index=JSON.parse(fs.readFileSync(path.join(graphDir,'index.json'),'utf8'));
const copy=x=>JSON.parse(JSON.stringify(x));
const ids=ui=>ui.root.querySelectorAll('.node').map(n=>n.getAttribute('data-id'));
function workingFiles(overrides={},sourceIndex=index){
  const files={'index.json':JSON.stringify(sourceIndex)};
  const space='rdg-example-mixed-v7';
  for(const entry of sourceIndex.graphs.filter(g=>g.identitySpace===space)){
    const graph=overrides[entry.slug]||JSON.parse(fs.readFileSync(path.join(graphDir,entry.file),'utf8'));
    files[entry.file]=JSON.stringify(graph);
  }
  return files;
}
async function opened(files){
  const ui=simulate({useBundle:true,files});await ui.flush();
  await ui.host.rdgExplorer.openFull('reference-mixed-active-work');return ui;
}
test('refresh re-reads the index and all scoped files, never using a bundled R0',async()=>{
  const fresh=JSON.parse(fs.readFileSync(path.join(graphDir,'examples/reference-mixed-active-work/graph.json')));
  fresh.nodes.find(n=>n.id==='R0').title='R0 ON DISK AFTER CLI';
  const ui=await opened(workingFiles({'reference-mixed-active-work':fresh}));
  assert(!ids(ui).some(id=>id==='R-FRESH'));
  assert.equal(ui.ids.reload.hidden,false);
  assert.match(ui.text(),/встроенная копия/);
  assert.equal(await ui.ids.reload.onclick(),true);
  assert.match(ui.text(),/перечитано из файлов/);
  assert(ui.root.querySelectorAll('.node').some(n=>n.textContent.includes('R0 ON DISK AFTER CLI')));
  assert.equal(ui.host.rdgExplorer.getCatalog().graphs.find(g=>g.slug==='reference-mixed-active-work').graph.nodes.find(n=>n.id==='R0').title,'R0 ON DISK AFTER CLI');
});
test('refresh fails closed on missing source without partially publishing new catalog',async()=>{
  const files=workingFiles(),ui=await opened(files);
  const previous=ui.host.rdgExplorer.getCatalog();
  const missing=Object.keys(files).find(x=>x.endsWith('reference-mixed-feature-consistency/graph.json'));
  assert(missing);delete files[missing];
  const ok=await ui.ids.reload.onclick();
  assert.equal(ok,false);
  assert.match(ui.text(),/не выполнено|прежняя копия/);
  assert.deepEqual(ui.host.rdgExplorer.getCatalog(),previous);
  assert(ids(ui).includes('R0'));
  assert.match(ui.ids['edge-legend'].textContent,/Встроенная копия/);
});
test('fresh index discovers a new causal R in the same identity space',async()=>{
  const src=copy(index),fresh=JSON.parse(fs.readFileSync(path.join(graphDir,'examples/reference-mixed-active-work/graph.json')));
  fresh.nodes.push({id:'R-FRESH-202',kind:'requirement',title:'Next level added after reindex',status:'candidate'});
  fresh.nodes.push({id:'O-FRESH-202',kind:'option',title:'Unselected next route',origin:'situational',status:'candidate'});
  fresh.edges.push({id:'edge-fresh-opt',type:'OPTION_FOR',from:'R0',to:'O-FRESH-202'});
  fresh.edges.push({id:'edge-fresh-r',type:'OUTCOME_OF',from:'O-FRESH-202',to:'R-FRESH-202'});
  const ui=await opened(workingFiles({'reference-mixed-active-work':fresh},src));
  assert(!ids(ui).includes('R-FRESH-202'));
  assert.equal(await ui.ids.reload.onclick(),true);
  ui.ids['variants-all'].onclick();
  assert(ids(ui).includes('R-FRESH-202'),'new scope records must be visible after fresh reload');
});
test('templateOnly and inactive projected owners are never a selected R path',()=>{
  const req=(id,extra={})=>({kind:'requirement',id,title:id,...extra});
  const edge=(id,type,from,to,extra={})=>({id,type,from,to,...extra});
  const g=(slug,nodes,edges,extra={})=>({slug,graph:{identitySpace:'test',rootRequirementId:'R0',nodes,edges,...extra}});
  const root=g('root',[req('R0'),{kind:'decision',id:'D',status:'committed',title:'decision'},req('R1')],[
    edge('drive','DRIVES','R0','D'),edge('intro','INTRODUCES','D','R1',{parent:'R0'})],
    {templateOnly:true,readOnly:true});
  let result=projector.project({graphs:[root]},'root');
  assert.equal(result.nodes.find(n=>n.id==='R1').branchState,'potential');
  assert.equal(result.edges.find(e=>e.to==='R1').kind,'prepared');
  assert(!projector.project({graphs:[root]},'root',{includePotential:false}).nodes.some(n=>n.id==='R1'));
  root.graph.templateOnly=false;root.graph.nodes[1].active=false;
  result=projector.project({graphs:[root]},'root');
  assert(!result.nodes.some(n=>n.id==='R1'));
});
test('projection owner activity and candidate template status fail closed',()=>{
  const req=(id,extra={})=>({kind:'requirement',id,title:id,...extra});
  const owner={slug:'owner',graph:{identitySpace:'scope',rootRequirementId:'R0',nodes:[req('R0'),{id:'D',kind:'decision',title:'Owner',active:false,status:'committed'}],edges:[]}};
  const child={slug:'child',graph:{identitySpace:'scope',rootRequirementId:'R0',nodes:[req('R0',{projectionOf:{graphSlug:'owner',nodeId:'R0'}}),{id:'D',kind:'decision',title:'Projection',status:'committed',projectionOf:{graphSlug:'owner',nodeId:'D'}},req('R1')],edges:[{id:'drv',type:'DRIVES',from:'R0',to:'D'},{id:'intro',type:'INTRODUCES',from:'D',to:'R1',parent:'R0'}]}};
  const result=projector.project({graphs:[owner,child]},'owner');
  assert(!result.nodes.some(n=>n.id==='R1'));
  assert(!result.edges.some(e=>e.kind==='selected'));
  assert.equal(projector.decisionActive({status:'committed',templateOnly:true},{exampleOnly:false}),false);
  assert.equal(projector.decisionActive({status:'committed',active:false},{exampleOnly:false}),false);
});
test('teaching Decision causal edge has an explicit instructional label',async()=>{
  const ui=await opened(workingFiles());
  ui.ids['edges-all'].onclick();
  const labels=[];
  function walk(n){if(n.getAttribute?.('data-edge-id')?.includes('__r_details_from__'))labels.push(n.textContent);for(const c of n.children||[])walk(c);}
  walk(ui.ids.canvas);
  assert(labels.some(t=>t.includes('R от учебно выбранного D')));
  assert(!labels.some(t=>t.startsWith('R от принятого D')));
});
test('fresh index extends scope to a newly indexed source file',async()=>{
  const src=copy(index),files=workingFiles();
  const entry=src.graphs.find(g=>g.slug==='reference-mixed-active-work');
  const added={slug:'test-new-after-reindex',file:'examples/test-new-after-reindex/graph.json',
    folder:entry.folder,group:entry.group,identitySpace:entry.identitySpace,rootRequirementId:'R0'};
  src.graphs.push(added);
  const graph={schemaVersion:1,id:added.slug,identitySpace:entry.identitySpace,rootRequirementId:'R0',
    nodes:[{kind:'requirement',id:'R0',title:'Root',projectionOf:{graphSlug:entry.slug,nodeId:'R0'}},
      {kind:'option',id:'O-FILE',title:'New file option'},
      {kind:'requirement',id:'R-ADDED-FILE',title:'Discovered continuation',status:'candidate'}],
    edges:[{id:'option-file',type:'OPTION_FOR',from:'R0',to:'O-FILE'},
      {id:'outcome-file',type:'OUTCOME_OF',from:'O-FILE',to:'R-ADDED-FILE'}]};
  files['index.json']=JSON.stringify(src);files[added.file]=JSON.stringify(graph);
  const ui=await opened(files);
  assert(!ids(ui).includes('R-ADDED-FILE'));
  assert.equal(await ui.ids.reload.onclick(),true);
  ui.ids['variants-all'].onclick();
  assert(ids(ui).includes('R-ADDED-FILE'),'refresh must include newly indexed same-scope sources');
});
test('a projected Decision cannot substitute a different selected option',()=>{
  const owner={slug:'owner',graph:{identitySpace:'s',rootRequirementId:'R0',
    nodes:[{kind:'requirement',id:'R0',title:'Root'},{kind:'decision',id:'D',title:'Chosen',status:'committed',selectedOptionId:'O-CAN'}],edges:[]}};
  const child={slug:'child',graph:{identitySpace:'s',rootRequirementId:'R0',
    nodes:[{kind:'requirement',id:'R0',title:'Root',projectionOf:{graphSlug:'owner',nodeId:'R0'}},
      {kind:'decision',id:'D',title:'Changed',status:'committed',selectedOptionId:'O-OTHER',
        projectionOf:{graphSlug:'owner',nodeId:'D'}},
      {kind:'requirement',id:'R1',title:'R1'}],
    edges:[{id:'drive',type:'DRIVES',from:'R0',to:'D'},
      {id:'intro',type:'INTRODUCES',from:'D',to:'R1',parent:'R0'}]}};
  const project=()=>projector.project({graphs:[owner,child]},'owner');
  assert(!project().nodes.some(n=>n.id==='R1'));
  child.graph.nodes[1].selectedOptionId='O-CAN';
  assert(project().nodes.some(n=>n.id==='R1'&&n.branchState==='actual'));
});
