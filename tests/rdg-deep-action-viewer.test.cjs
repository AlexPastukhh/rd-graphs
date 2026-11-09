'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const {simulate}=require('./viewer-test-helper.cjs');
const ROOT=path.resolve(__dirname,'..'),slug='deep-action-viewer';
// Produce both scenes through the actual bearer writer in its temporary fixture.
const script=`
from importlib.machinery import SourceFileLoader
import json
m=SourceFileLoader("deep_view_fixture", "tests/rdg-deep-action.acceptance.test.py").load_module()
w=m.DeepAction("test_decomposition_execution_does_not_mean_its_subgoals_are_achieved")
w.setUp()
try:
 w.apply([w.add("D",action_type="decomposition"), w.prepare("D","R1"),
          w.add("A1","R1"), w.prepare("A1","R2","method_correctness"),
          w.add("A2","R2"), w.prepare("A2","R3","subgoal")])
 potential=w.read()
 w.apply([w.choose("D")])
 w.apply([w.result("D",action=True)])
 print(json.dumps({"potential":potential,"decompositionDone":w.read()}))
finally:
 w.tearDown()
`;
const run=spawnSync('python3',['-B','-c',script],{cwd:ROOT,encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
assert.equal(run.status,0,run.stderr);const scenes=JSON.parse(run.stdout);
async function open(g){
 const idx=JSON.parse(fs.readFileSync(path.join(ROOT,'graphs/index.json'),'utf8'));
 const file='workspaces/'+slug+'/graph.json';
 // The live catalog has unrelated full graphs. Keep this synthetic scene isolated.
 idx.graphs=[];idx.fullGraphs=[];idx.relations=[];
 idx.graphs.push({slug,title:g.title,group:'workspaces',folder:'workspaces',kind:'graph',
   identitySpace:g.identitySpace,rootRequirementId:g.rootRequirementId,file,planningScale:'module',presentation:{}});
 idx.fullGraphs.push({slug,kind:'full-graph',title:g.title,folder:'workspaces',
   identitySpace:g.identitySpace,rootRequirementId:g.rootRequirementId,file,presentation:{}});
 const ui=simulate({useBundle:true,files:{'index.json':JSON.stringify(idx),[file]:JSON.stringify(g),
   'examples/reference-action-time-plan/graph.json':fs.readFileSync(path.join(ROOT,'graphs/examples/reference-action-time-plan/graph.json'),'utf8')}});
 await ui.flush();await ui.host.rdgExplorer.openFull(slug,{fresh:true});return ui;
}
function nodes(ui){return ui.root.querySelectorAll('.node');}
function click(ui,id){const n=nodes(ui).find(n=>n.getAttribute('data-id')===id);assert(n,'missing '+id);
 n.listeners.click({stopPropagation(){}});return ui.info();}
test('deep paper branch is visible with variants and stays potential at every level',async()=>{
 const ui=await open(scenes.potential);
 assert.deepEqual(nodes(ui).map(n=>n.getAttribute('data-id')),['R0']);
 ui.ids['variants-all'].onclick();
 assert.deepEqual(nodes(ui).map(n=>n.getAttribute('data-id')).sort(),['R0','R1','R2','R3']);
 for(const n of nodes(ui).filter(n=>n.getAttribute('data-id')!=='R0'))
  assert.equal(n.getAttribute('data-branch-state'),'potential');
 ui.ids['edges-all'].onclick();const text=click(ui,'__cause__'+slug+'::A2');
 for(const expected of ['Action · candidate','C-A2','Q-A2','не выбран'])assert(text.includes(expected),expected);
 assert(!text.includes('Основание выбора'));
});
test('decomposition Action shows its type and execution history while subgoal is unfinished',async()=>{
 const ui=await open(scenes.decompositionDone);ui.ids['edges-all'].onclick();
 const action=click(ui,'__cause__'+slug+'::D');
 for(const expected of ['выделение подцели / связанного набора подцелей','История результатов','выполнен Action'])assert(action.includes(expected),expected);
 assert.deepEqual(nodes(ui).filter(n=>n.getAttribute('class')?.includes('requirement')).map(n=>n.getAttribute('data-id')).sort(),['R0','R1']);
 const child=click(ui,'R1');assert(!child.includes('достигнута R'));
});
test('generated root projection matches its source after potential Action support',()=>{
 const viewer=fs.readFileSync(path.join(ROOT,'tools/rd-graph-viewer.user.js'),'utf8');
 const begin='// BEGIN GENERATED RDG ROOT PROJECTION\n',end='// END GENERATED RDG ROOT PROJECTION\n';
 assert.equal(viewer.slice(viewer.indexOf(begin)+begin.length,viewer.indexOf(end)),
  fs.readFileSync(path.join(ROOT,'tools/rdg-root-projection.js'),'utf8'));
});
