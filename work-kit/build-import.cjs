#!/usr/bin/env node
// Build a local-only Planning Helper import from the editable working sources.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=__dirname;
const manifest=[
 ['module','rdg.work.semantics','RDG — смысл R, D и связей'],
 ['module','rdg.work.planning','RDG — планирование и пересмотр'],
 ['module','rdg.work.examples','RDG — примеры и их интерпретация'],
 ['module','rdg.work.crosscutting','RDG — сквозной Requirement'],
 ['module','rdg.work.storage','RDG — физический граф JSON и запись'],
 ['module','rdg.work.repository','RDG — Fortis Repo и безопасная работа'],
 ['module','rdg.work.rste','RDG — R-STE (язык и точность)'],
 ['module','rdg.work.value','RDG — Work Value and Proportionality'],
 ['module','rdg.work.output','RDG — формат рабочего ответа'],
 ['prompt','rdg.work.bootstrap','RDG — Bootstrap: цели, решения, граф и хранение'],
 ['prompt','rdg.work.plan','RDG — Спланировать достижение Requirement'],
 ['prompt','rdg.work.commit','RDG — Зафиксировать принятое решение'],
 ['prompt','rdg.work.crosscut','RDG — Создать сквозной Requirement']
];
const timestamp=new Date().toISOString();
const outputPath=path.join(root,'planning-helper-import.txt');
let previous=new Map();
if(fs.existsSync(outputPath)){
 const match=fs.readFileSync(outputPath,'utf8').match(/\[PLANNING_HELPER_PATCH\]\s*([\s\S]*?)\s*\[\/PLANNING_HELPER_PATCH\]/);
 if(match)previous=new Map(JSON.parse(match[1]).upsert.helperItems.map(x=>[x.id,x]));
}
const items=manifest.map(([kind,id,title])=>{
 const file=path.join(root,kind==='module'?'modules':'prompts',
   id+(kind==='module'?'.module.md':'.prompt.md'));
 const content=fs.readFileSync(file,'utf8');
 assert(content.trim(),'Empty item '+id);
 const old=previous.get(id);
 return {schemaVersion:1,kind,id,title,text:content,createdAt:old?.createdAt||timestamp,updatedAt:old&&old.text===content&&old.title===title?old.updatedAt:timestamp};
});
const modules=new Map(items.filter(x=>x.kind==='module').map(x=>[x.id,x]));
function expand(text,trail=[]){
 return text.replace(/\[\[module:([a-z0-9._-]+)\]\]/g,(_all,id)=>{
   assert(!trail.includes(id),'module cycle '+[...trail,id].join(' -> '));
   assert(modules.has(id),'missing module: '+id);
   return expand(modules.get(id).text,[...trail,id]);
 });
}
for(const p of items.filter(x=>x.kind==='prompt')){
 const output=expand(p.text);
 assert(!output.includes('[[module:'),'unresolved references '+p.id);
 assert(output.length<=100000,'expanded prompt too large '+p.id);
}
const payload={schemaVersion:1,upsert:{helperItems:items}};
const output='[PLANNING_HELPER_PATCH]\n'+JSON.stringify(payload,null,2)+'\n[/PLANNING_HELPER_PATCH]\n';
fs.writeFileSync(path.join(root,'planning-helper-import.txt'),output);
console.log('WORK_KIT_OK: '+items.length+' items ('+
  items.filter(x=>x.kind==='prompt').length+' prompts, '+
  items.filter(x=>x.kind==='module').length+' modules), '+output.length+' bytes');
