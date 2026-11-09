const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),vm=require('node:vm');
const {simulate}=require('./viewer-test-helper.cjs'),core=require('../tools/rdg-state.js');
const ROOT=path.resolve(__dirname,'..');
const snapshot={};vm.runInNewContext(fs.readFileSync(path.join(ROOT,'tools/rd-graph-data.js'),'utf8'),snapshot);
const manifest=JSON.parse(JSON.stringify(snapshot.RDG_EMBEDDED_GRAPHS));
const get=()=>core.collect({items:manifest.graphs,manifest,setId:'context-working'});
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
