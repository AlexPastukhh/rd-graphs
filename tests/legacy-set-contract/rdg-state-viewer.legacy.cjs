const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),vm=require('node:vm');
const {simulate}=require('./viewer-test-helper.cjs'),core=require('../tools/rdg-state.js');
const ROOT=path.resolve(__dirname,'..');
const snapshot={};vm.runInNewContext(fs.readFileSync(path.join(ROOT,'tools/rd-graph-data.js'),'utf8'),snapshot);
const manifest=JSON.parse(JSON.stringify(snapshot.RDG_EMBEDDED_GRAPHS));
const get=()=>core.collect({items:manifest.graphs,manifest,setId:'context-working'});
test('set aggregation includes hidden branch, reuses prepared definitions and earlier project answer',()=>{
 const r=get(),access=r.fields.find(f=>f.fieldRef.fieldId==='accessibility'),later=r.fields.find(f=>f.fieldRef.fieldId==='alternative-details');
 assert.equal(access.answerStatus,'known');assert.equal(access.usages.length,4);assert.equal(access.state,'now');
 assert.equal(later.state,'later');assert.equal(later.question,false);assert.equal(access.fieldRef.graphSlug,'context-prepared-root');
 assert(r.incomplete.some(i=>i.reason==='canon-fields-incomplete'));
 assert(r.fields.find(f=>f.fieldRef.fieldId==='delivery').nextAction==='check-known-context-or-ask');
 const child=core.collect({items:manifest.graphs,manifest,graphSlug:'context-working-alternative'});
 assert(child.fields.every(f=>f.state==='later'),'opening alternative does not make its fields current');
});
test('CLI and embedded Viewer consume the same core and report equivalent fields',async()=>{
 const u=simulate({useBundle:true});await u.flush();await u.openSet('context-working');
 const r=cp.spawnSync('python3',[path.join(ROOT,'tools/rdg-context.py'),'--fields','--set-id','context-working'],{encoding:'utf8'});
 assert.equal(r.status,0,r.stderr);
 assert.deepEqual(JSON.parse(JSON.stringify(u.host.rdgState.list())),JSON.parse(r.stdout));
 const code=fs.readFileSync(path.join(ROOT,'tools/rd-graph-viewer.user.js'),'utf8'),shared=fs.readFileSync(path.join(ROOT,'tools/rdg-state.js'),'utf8');
 assert(code.includes('// BEGIN GENERATED RDG STATE\n'+shared+'// END GENERATED RDG STATE'));
});
test('context mode inspects without navigation, aggregate stays clickable, off restores navigation',async()=>{
 const u=simulate({useBundle:true});await u.flush();await u.openSet('context-working');const key=u.host.rdgLayout.graphKey(),before=u.host.rdgLayout.getDocument();
 assert.equal(u.root.querySelectorAll('.node').length,2,'alternative is hidden');
 assert(u.root.getElementById('context-summary'));
 u.ids['context-mode'].onclick();
 const n=u.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')==='context-working-current');
 n.listeners.click({stopPropagation(){}});await u.flush();
 assert.equal(u.host.rdgLayout.graphKey(),key);assert(u.info().includes('Поля графа: context-working-current'));assert(u.info().includes('поле заполнено'));
 u.root.getElementById('context-summary').listeners.click({stopPropagation(){}});
 assert(u.info().includes('После выбора ветки'));assert(u.info().includes('Теория')||u.info().includes('W3C'));assert(u.info().includes('НЕПОЛНЫЙ'));
 assert.deepEqual(u.host.rdgLayout.getDocument(),before,'inspection is read-only');
 u.ids['context-mode'].onclick();n.listeners.click({stopPropagation(){}});await u.flush();
 assert.notEqual(u.host.rdgLayout.graphKey(),key);u.ids['context-fields'].onclick();assert(u.info().includes('Контекст графа'));
});
test('theory links and link-only canon are inspectable; no extra R or saved layout keys',async()=>{
 const u=simulate({useBundle:true});await u.flush();await u.openCard('context-prepared-root');
 const count=u.root.querySelectorAll('.node').length;u.ids['context-fields'].onclick();assert(u.info().includes('Контекст доступности'));
 const n=u.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')==='__canon__O-CTX-B');assert(n);n.listeners.click({stopPropagation(){}});
 assert(u.info().includes('пока только ссылка'));assert(u.info().includes('W3C'));
 assert.equal(u.root.querySelectorAll('.node').length,count);
 assert(!JSON.stringify(u.host.rdgLayout.getDocument()).includes('__state_info__'));
});
test('empty/unavailable metadata stays incomplete rather than a false success',()=>{
 const r=core.collect({items:[],graphSlug:'unavailable'});
 assert.equal(r.fields.length,0);assert(r.incomplete.some(i=>i.reason==='graph-unavailable'));
});
