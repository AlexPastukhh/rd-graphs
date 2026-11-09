const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const {simulate}=require('./viewer-test-helper.cjs');
const ROOT=path.resolve(__dirname,'..');
const prepared=JSON.parse(fs.readFileSync(path.join(ROOT,'graphs/examples/reference-prepared-planning-tree/graph.json')));
const mixed=JSON.parse(fs.readFileSync(path.join(ROOT,'graphs/examples/reference-mixed-active-work/graph.json')));
function rendered(ui){return ui.root.querySelectorAll('.node').map(x=>x.getAttribute('data-id'));}
test('prepared tree shows two-R lists inline and stops before their own variants',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();await ui.openCard(prepared.id);
 const ids=rendered(ui);assert(ids.includes('O-FEATURE')&&ids.includes('O-SCENARIO'));
 assert(ids.includes('RF-1')&&ids.includes('RF-2'));assert(!ids.includes('__collection__FEATURE-POTENTIAL'));
 assert(!ids.includes('RF-1-O1')&&!ids.includes('RF-DEEP'));
 assert.equal(prepared.nodes.find(x=>x.id==='RF-1').status,'candidate');
});
test('mixed working sample: selected root hides options; undecided child shows both even under selected ancestor',async()=>{
 const ui=simulate();await ui.loadFile(mixed);assert(!rendered(ui).includes('D-A'));
 ui.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')==='R-COMP').listeners.click({stopPropagation(){}});await ui.flush();
 let ids=rendered(ui);
 assert(ids.includes('D-A'),'actual selected D visible');
 assert(!ids.includes('O-A'),'root option hidden after selection');
 assert(ids.includes('R-ACT-1'),'the child Requirement remains visible in parent');
 assert(!ids.includes('O-ACT-1'),'child options belong to the child graph, not parent');
 await ui.ids['level-up'].onclick();
 ui.ids['variants-all'].onclick();
 ids=rendered(ui);
 assert(ids.includes('O-A'));assert(ids.includes('O-B'));assert(ids.includes('O-C'));
 assert(ids.includes('__collection__COL-FEATURE'),'ten potential candidates are one collapsed collection');
 assert(!ids.includes('R-PREV-FEATURE-1'));
 assert.equal(ui.ids['variants-all'].getAttribute('aria-pressed'),'true');
 ui.ids['edges-all'].onclick();
 assert.equal(ui.ids['variants-all'].getAttribute('aria-pressed'),'true','edge mode does not reset variants');
 ui.ids['variants-all'].onclick();
 assert.equal(ui.ids['variants-all'].getAttribute('aria-pressed'),'false');
 assert(!rendered(ui).includes('O-B'),'All Relations must not reveal unselected root options');
 const linked=simulate({useBundle:true});await linked.flush();
 await linked.openLevel('reference-mixed-active-work','R-COMP');
 const jump=linked.root.querySelectorAll('.node').find(x=>x.getAttribute('data-id')==='R-ACT-1');
 assert(jump.classList.contains('drill'),'same-R navigation available');
 jump.listeners.click({stopPropagation(){}});await linked.flush();
 const childIds=rendered(linked);
 assert(childIds.includes('O-ACT-1')&&childIds.includes('O-ACT-2'),'undecided child shows both options by default');
 assert(!childIds.some(x=>x.startsWith('D-')),'child has no chosen Decision');
});
test('workspace initializer supports real goal dry-run and creates writable graph with zero Decisions',()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-v7-init-'));
 try{
  const tools=path.join(temp,'tools');fs.mkdirSync(tools,{recursive:true});
  for(const file of ['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js','graph-index.py','rdg-catalog.py','rdg-modules.py','rdg-module-registry.json','rdg-module-test.py','graph-apply.py','graph-package.py','rdg-transaction-io.py','rdg-v7-model.py','rdg-new-workspace.py'])
    fs.copyFileSync(path.join(ROOT,'tools',file),path.join(tools,file));
  fs.mkdirSync(path.join(temp,'graphs/workspaces'),{recursive:true});
  const argv=[path.join(tools,'rdg-new-workspace.py'),'--slug','real-project','--title','Реальный проект',
    '--root-id','R-MAIN','--root-title','Создать приложение','--identity-space','real-project-isolated'];
  let result=spawnSync('python3',[...argv,'--dry-run'],{encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  assert(!fs.existsSync(path.join(temp,'graphs/workspaces/real-project')));
  result=spawnSync('python3',argv,{encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  const graph=JSON.parse(fs.readFileSync(path.join(temp,'graphs/workspaces/real-project/graph.json')));
  assert.equal(graph.nodes.length,1);assert.equal(graph.events.length,0);assert.equal(graph.readOnly,undefined);
  assert.equal(graph.rootRequirementId,'R-MAIN');
  const manifest=JSON.parse(fs.readFileSync(path.join(temp,'graphs/index.json')));
  assert(manifest.projectContexts['real-project-isolated'].records.some(r=>r.id==='R-MAIN'));
  result=spawnSync('python3',argv,{encoding:'utf8'});
  assert.notEqual(result.status,0,'workspace cannot be overwritten');
 }finally{fs.rmSync(temp,{recursive:true,force:true});}
});
