const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const base=path.resolve(__dirname,'..'),kit=path.join(base,'work-kit');
const owner=path.join(base,'../obs-planning-docs/planning/documentation/tools/tampermonkey/chat-command-palette/src');
const parse=require(path.join(owner,'chat-recovery.js')).parseChatImport;
const resolver=require(path.join(owner,'helper-module-resolver.js'));
const patch=fs.readFileSync(path.join(kit,'planning-helper-import.txt'),'utf8');
const data=parse(patch).patch;
const items=data.upsert.helperItems;
test('working bundle includes 4 prompts + 9 modules, no pilot entries',()=>{
 assert.equal(items.filter(x=>x.kind==='prompt').length,4);
 assert.equal(items.filter(x=>x.kind==='module').length,9);
 assert(items.every(x=>x.id.startsWith('rdg.work.')));
 assert.equal(data.delete.helperItems.length,0);
});
test('all working prompts expand the right modules',()=>{
 for(const item of items.filter(x=>x.kind==='prompt')){
  const result=resolver.resolveModuleReferences(item.text,items);
  assert(result.references.length>=4,item.id);
  assert(!result.text.includes('[[module:'),item.id);
 }
});
test('bootstrap includes nine modules and covers runtime storage',()=>{
 const item=items.find(x=>x.id==='rdg.work.bootstrap');
 assert.equal(resolver.findModuleReferences(item.text).length,9);
 const expanded=resolver.resolveModuleReferences(item.text,items).text;
 for(const word of ['DRY','APPLIES_TO','INTRODUCES','graph-apply.py','STATUS','IMPACT','HOST Tunnel'])
  assert(expanded.includes(word),word);
});
test('specialized working prompts contain correct boundaries',()=>{
 const byId=Object.fromEntries(items.map(i=>[i.id,i]));
 assert.match(byId['rdg.work.plan'].text,/не записывай/);
 assert.match(byId['rdg.work.commit'].text,/--dry-run/);
 assert.match(byId['rdg.work.commit'].text,/decision_selected/);
 assert.match(byId['rdg.work.crosscut'].text,/APPLIES_TO/);
 assert.match(byId['rdg.work.crosscut'].text,/не копируй узел/);
});
test('import text mirrors editable sources',()=>{
 for(const i of items){
  const sub=i.kind==='prompt'?'prompts':'modules';
  const suffix=i.kind==='prompt'?'.prompt.md':'.module.md';
  assert.equal(i.text,fs.readFileSync(path.join(kit,sub,i.id+suffix),'utf8'),i.id);
 }
});
test('try-it remains uncommitted before real user selection',()=>{
 const g=JSON.parse(fs.readFileSync(path.join(base,'graphs/workspaces/try-it/graph.json'),'utf8'));
 assert.equal(g.revision,1);assert.equal(g.nodes.length,1);
 assert.equal(g.edges.length,0);assert.equal(g.events.length,0);
});
