const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const base='/workspace/repos/obs-planning-docs/planning/documentation/tools/tampermonkey/chat-command-palette/src/';
globalThis.ObsPlanningHelper=Object.assign({},...['command-definition-codec.js','command-catalog.js','helper-library-codec.js','command-body.js','semantic-projections.js','repository-catalog-service.js'].map(f=>require(base+f)));
const state=require(base+'planning-helper-state.js');Object.assign(globalThis.ObsPlanningHelper,state);
const runtime=require(base+'planning-helper-runtime.js'),parser=require(base+'chat-recovery.js'),resolver=require(base+'helper-module-resolver.js'),codec=require(base+'helper-library-codec.js');
const payload=parser.parseChatImport(fs.readFileSync(path.join(root,'work-kit/planning-helper-import.txt'),'utf8'));
const items=payload.patch.upsert.helperItems;
test('real Helper Import replaces same IDs, preserves outsiders and is unchanged on repeat',()=>{
 const older=items.map(i=>({...i,text:'STALE '+i.id}));
 const outside={...items[0],id:'outside.keep',kind:'prompt',title:'Unrelated prompt',text:'KEEP'};
 const snapshot=state.normalizePlanningHelperLocalSnapshot({schemaVersion:state.LOCAL_SNAPSHOT_SCHEMA_VERSION,savedAt:new Date().toISOString(),planningCommands:[],helperItems:[...older,outside].map(item=>state.normalizeHelperRecord({item,repositoryKnown:false})),useCases:[],semanticComponents:[],scenarios:[]});
 const merged=runtime.mergeChatImport(snapshot,payload,'import');assert.equal(merged.snapshot.helperItems.length,14);
 assert.equal(merged.snapshot.helperItems.find(r=>r.item.id===outside.id).item.text,'KEEP');
 assert.equal(merged.lines.filter(l=>l.startsWith('UPDATE')).length,13);
 const repeat=runtime.mergeChatImport(merged.snapshot,payload,'import');assert(repeat.lines.every(l=>l.startsWith('UNCHANGED')));
 assert.equal(repeat.snapshot.helperItems.length,14);
 const live=merged.snapshot.helperItems.map(r=>r.item);
 for(const p of live.filter(i=>i.kind==='prompt'&&i.id.startsWith('rdg.work.'))){
  const expanded=resolver.resolveModuleReferences(p.text,live).text;
  assert(!expanded.includes('[[module:'));assert(expanded.includes('Target Module (TM) — весь модуль'));
  assert(expanded.includes('planningScale=module|unit'));assert(expanded.includes('revise_decision'));
  assert(!expanded.includes('специальный протокол с сохранением прежнего ответа пока не реализован'));
 }
});
test('generated helper-library delivery bytes match the authoring payload',()=>{
 for(const item of items){
  const p=path.join('/workspace/repos/obs-planning-docs',codec.helperLibraryTargetPath(item));
  assert.equal(fs.readFileSync(p,'utf8'),codec.renderHelperLibraryDocument(item),item.id);
 }
});
