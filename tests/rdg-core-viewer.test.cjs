'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {spawnSync}=require('node:child_process'),{simulate}=require('./viewer-test-helper.cjs');
function graph(){
 const r=spawnSync('python3',['-c',"from importlib.machinery import SourceFileLoader;import json,sys;s=SourceFileLoader('core_viewer_fixture',sys.argv[1]).load_module().Core();s.setUp();s.shared();print(json.dumps(s.g))",path.join(__dirname,'rdg-core-model.test.py')],{encoding:'utf8'});
 assert.equal(r.status,0,r.stderr);return JSON.parse(r.stdout);
}
test('ordinary JSON import opens core own graphs without invoking legacy one-driver layout',async()=>{
 const g=graph(),ui=simulate({useBundle:true});await ui.flush();await ui.loadFile(g);
 assert(!ui.text().startsWith('Ошибка:'),ui.text());assert.equal(ui.ids.content.hidden,true);
 assert(ui.ids['graph-pane'].textContent.includes('Собственные графы R, A и канонов'));
 assert.equal(ui.ids['workflow-graph-editor'].hidden,true,'file snapshot has no writer');
 const bad=structuredClone(g);bad.objects[0].kind='invented';await ui.loadFile(bad);
 assert(ui.text().includes('CORE_SNAPSHOT'),ui.text());
});
test('source Viewer shows graph-level textual advice in a reusable ready template',async()=>{
 const ready=graph();ready.presentation={usage:'ready'};ready.templateOnly=true;ready.readOnly=true;
 ready.lensRecommendations=[{lensKey:'review',text:'Before choosing a method, inspect current canon conditions.'}];
 const ui=simulate({useBundle:true});await ui.flush();await ui.loadFile(ready);
 assert(!ui.text().startsWith('Ошибка:'),ui.text());
 assert.match(ui.ids['graph-pane'].textContent,/Before choosing a method, inspect current canon conditions\./,
  'advice on a ready core graph must remain visible without invoking a Lens');
 assert.equal(ready.templateOnly,true);
});
test('prepared core Lens recommends another Lens in source Viewer without applying it',async()=>{
 const fs=require('node:fs'),lens=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../tools/rdg-agent-lenses/work.json'),'utf8'));
 const ui=simulate({useBundle:true});await ui.flush();await ui.loadFile(lens);
 assert(!ui.text().startsWith('Ошибка:'),ui.text());
 assert.match(ui.ids['graph-pane'].textContent,/Когда исполнение прервано или writer вернул неопределённый исход/);
});
test('core file Viewer shows graph-level advice without applying the recommended lens',async()=>{
 const g=graph();g.lensRecommendations=[{lensKey:'clarify',text:'Clarify required truth before reviewing this graph.'}];
 const ui=simulate({useBundle:true});await ui.flush();await ui.loadFile(g);
 assert(!ui.text().startsWith('Ошибка:'),ui.text());
 assert.match(ui.ids['graph-pane'].textContent,/Clarify required truth before reviewing this graph\./);
});
test('core import rejects unsupported selection, completion and falsification without real events',async()=>{
 const original=graph();
 const cases=[
  g=>{const a=g.nodes.find(n=>n.kind==='action');a.status='selected';a.selectedEventId='missing';},
  g=>{const a=g.nodes.find(n=>n.kind==='action');a.result={state:'confirmed',truth:'true',eventId:'missing'};},
  g=>{const r=g.nodes.find(n=>n.kind==='requirement');r.result={state:'open',truth:'false',eventId:'missing'};}
 ];
 for(const mutate of cases){
  const bad=structuredClone(original);mutate(bad);
  const ui=simulate({useBundle:true});await ui.flush();await ui.loadFile(bad);
  assert.match(ui.text(),/CORE_SNAPSHOT/,ui.text());
  assert.equal(ui.ids['graph-pane'].textContent.includes('Собственные графы R, A и канонов'),false,
    'invalid snapshot must not reach the graph renderer');
 }
});
test('catalog full entry for core routes to the same scope store and focused renderer',async()=>{
 const g=graph(),slug='core-viewer-proof',file='workspaces/'+slug+'/graph.json';
 const entry={slug,file,title:g.title,folder:'workspaces',identitySpace:g.identitySpace,rootRequirementId:g.rootRequirementId,actionModel:g.actionModel,coreModel:g.coreModel};
 const index={schemaVersion:1,graphs:[{...entry,kind:'graph',group:'workspaces',presentation:{}}],
  fullGraphs:[{...entry,kind:'full-graph',presentation:{}}],folders:[{id:'workspaces',kind:'folder',folder:'',title:'Working graphs',presentation:{}}],relations:[],defaultGraph:slug};
 const ui=simulate({useBundle:true,files:{'index.json':JSON.stringify(index),[file]:JSON.stringify(g)}});await ui.flush();
 await ui.host.rdgExplorer.openFull(slug,{fresh:true});
 assert.equal(ui.ids.content.hidden,true);assert(ui.ids['graph-pane'].textContent.includes('Собственные графы R, A и канонов'));
 assert(!ui.text().includes('Ошибка:'),ui.text());
});
