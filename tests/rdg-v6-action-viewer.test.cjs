'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {simulate}=require('./viewer-test-helper.cjs');
const BASE=path.resolve(__dirname,'..');
const actionGraph=JSON.parse(fs.readFileSync(path.join(BASE,'tests/fixtures/rdg-v6-action-optin/graph.json'),'utf8'));
const baselineIndex=JSON.parse(fs.readFileSync(path.join(BASE,'graphs/index.json'),'utf8'));
const slug='action-optin-visual-test';
function nodes(ui){return ui.root.querySelectorAll('.node');}
function node(ui,id){return nodes(ui).find(n=>n.getAttribute('data-id')===id);}
async function open(g=actionGraph){
 const idx=structuredClone(baselineIndex);
 const file='workspaces/'+slug+'/graph.json';
 idx.graphs.push({slug,title:g.title,group:'workspaces',folder:'workspaces',kind:'graph',
   identitySpace:g.identitySpace,rootRequirementId:g.rootRequirementId,file,
   planningScale:'module',presentation:{}});
 idx.fullGraphs.push({slug,kind:'full-graph',title:g.title,folder:'workspaces',
   identitySpace:g.identitySpace,rootRequirementId:g.rootRequirementId,file,presentation:{}});
 const ui=simulate({useBundle:true,files:{'index.json':JSON.stringify(idx),[file]:JSON.stringify(g)}});
 await ui.flush();
 await ui.host.rdgExplorer.openFull(slug,{fresh:true});
 return ui;
}
function click(ui,id){const n=node(ui,id);assert(n,'missing '+id);n.listeners.click({stopPropagation(){}});return ui.info();}
test('viewer embeds the same root projection as the source module',()=>{
 const viewer=fs.readFileSync(path.join(BASE,'tools/rd-graph-viewer.user.js'),'utf8');
 const begin='// BEGIN GENERATED RDG ROOT PROJECTION\n',end='// END GENERATED RDG ROOT PROJECTION\n';
 const part=viewer.slice(viewer.indexOf(begin)+begin.length,viewer.indexOf(end));
 assert.equal(part,fs.readFileSync(path.join(BASE,'tools/rdg-root-projection.js'),'utf8'));
});
test('R-only full mode includes selected Action child Rs, without turning A into R',async()=>{
 const ui=await open();assert.deepEqual(nodes(ui).map(n=>n.getAttribute('data-id')).sort(),['R0','R1','R2']);
});
test('detailed Viewer reveals Action, canon, QRPE, T1 without a new Decision',async()=>{
 const ui=await open();ui.ids['edges-all'].onclick();
 const details=click(ui,'__cause__'+slug+'::A1');
 for(const expected of ['A1 · Action · selected','выбран, не доказано исполнение','Канонические ситуации','C1','Q1','actionSnapshot'])assert(details.includes(expected),expected);
 assert(!nodes(ui).some(n=>n.getAttribute('class')?.includes('node decision')));
});
test('legacy Decision presentation continues to work',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();
 await ui.host.rdgExplorer.openFull('reference-mixed-active-work');
 ui.ids['edges-all'].onclick();
 const details=click(ui,'__cause__reference-mixed-active-work::D-A');
 assert.match(details,/Decision/);assert.match(details,/Основание выбора/);
});
test('candidate Action can be explored without being represented as chosen',async()=>{
 const g=structuredClone(actionGraph),a=g.nodes.find(n=>n.id==='A1');
 a.status='candidate';delete a.selectionBasis;g.events=[];
 g.edges=g.edges.filter(e=>e.type!=='INTRODUCES');g.nodes=g.nodes.filter(n=>!['R1','R2'].includes(n.id));
 const ui=await open(g);
 assert.deepEqual(nodes(ui).map(n=>n.getAttribute('data-id')),['R0']);
 ui.ids['variants-all'].onclick();ui.ids['edges-all'].onclick();
 const text=click(ui,'__cause__'+slug+'::A1');
 assert.match(text,/Action · candidate/);assert.doesNotMatch(text,/выбран, не доказано исполнение/);
});
test('tampered T1 cannot make an Action accepted in Viewer',async()=>{
 const altered=structuredClone(actionGraph);
 altered.nodes.find(n=>n.id==='A1').selectionBasis.actionSnapshot.id='OTHER';
 const ui=await open(altered);
 assert.deepEqual(nodes(ui).map(n=>n.getAttribute('data-id')),['R0']);
 ui.ids['variants-all'].onclick();ui.ids['edges-all'].onclick();
 const record=click(ui,'__cause__'+slug+'::A1');
 assert.match(record,/Action/);
});
test('local file Viewer shows opt-in A and canon without producing a Decision',async()=>{
 const ui=simulate();await ui.flush();await ui.loadFile(actionGraph);
 const ids=nodes(ui).map(n=>n.getAttribute('data-id'));
 assert(ids.includes('A1'));assert(ids.includes('__canon__A1'));
 assert(!ids.some(x=>x.startsWith('D-')));
 const detail=click(ui,'A1');
 assert.match(detail,/action · selected/i);assert.match(detail,/Q1/);
});
test('Viewer shows reconsidered Action as historical while independently supported R survives',async()=>{
 const reviewed=JSON.parse(fs.readFileSync(path.join(BASE,
   'tests/fixtures/rdg-v6-action-reconsidered/graph.json'),'utf8'));
 const ui=await open(reviewed);
 assert.deepEqual(nodes(ui).map(n=>n.getAttribute('data-id')).sort(),['R0','R1']);
 ui.ids['variants-all'].onclick();ui.ids['edges-all'].onclick();
 const old=click(ui,'__cause__'+slug+'::A1');
 assert.match(old,/Action · superseded/);
 assert.match(old,/Исторический Action/);
 assert.match(old,/EV-RECONSIDER/);
 assert.match(old,/A-REVIEW/);
 const other=click(ui,'__cause__'+slug+'::A3');
 assert.match(other,/Action · selected/);
 assert.doesNotMatch(other,/исторически выбран, затем пересмотрен/);
});
