#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const core=require('./rdg-layout-core.js');
function main(){
 const args=process.argv.slice(2),value=flag=>{const i=args.indexOf(flag);return i<0?undefined:args[i+1]};
 if(args.includes('--transform-stdin')){
  const req=JSON.parse(fs.readFileSync(0,'utf8'));let result;
  if(req.op==='project'){const graphKey=core.graphKey(req.graph.identitySpace,req.graph.id);result=require('./rdg-visual-projection.js').decisionProject(req.graph,req.view,req.document?.layouts?.[graphKey]||{});}
  else if(req.op==='empty')result=core.empty();
  else if(req.op==='validate')result=core.validate(req.document);
  else if(req.op==='remap')result=core.remap(req.document,req.spec);
  else if(req.op==='apply')result=core.commit(core.apply(req.document,req.commands),req.expectedRevision);
  else throw Error('LAYOUT_TRANSFORM_OPERATION');
  console.log(JSON.stringify(result));return;
 }
 const root=path.resolve(__dirname,'..'),file=path.resolve(value('--file')||path.join(root,'graphs/layouts.json'));
 if(args.includes('--show')){console.log(JSON.stringify(core.validate(JSON.parse(fs.readFileSync(file,'utf8'))),null,2));return;}
 const commandFile=value('--commands-file'),expected=Number(value('--expect-revision'));
 if(!commandFile||!Number.isSafeInteger(expected)||expected<0)throw Error('Use --commands-file FILE --expect-revision N [--file graphs/layouts.json]');
 const commands=JSON.parse(fs.readFileSync(commandFile,'utf8'));
 const manifest=require('./rdg-catalog.js').normalizeCatalog(JSON.parse(fs.readFileSync(path.join(root,'graphs/index.json'),'utf8')));
 for(const command of Array.isArray(commands)?commands:[commands]){
  const address=JSON.parse(command.graphKey);
  let allowed;
  if(address&& !Array.isArray(address)&&address.type==='graph-set'){
    if(command.graphKey!==core.setKey(address.id))throw Error('Некорректный ключ набора');
    const set=(manifest.graphSets||[]).find(s=>s.id===address.id);
    if(!set)throw Error('Неизвестный набор');
    allowed=new Set(set.members);
  }else{
    if(!Array.isArray(address)||![2,3].includes(address.length))throw Error('Некорректный ключ расположения');
    const [space,slug,rootRequirementId]=address;
    const entry=manifest.graphs.find(g=>g.slug===slug);
    if(!entry)throw Error('Неизвестный граф: '+slug);
    const target=path.resolve(root,'graphs',entry.file),base=fs.realpathSync(path.join(root,'graphs'));
    if(!target.startsWith(base+path.sep)||!fs.realpathSync(target).startsWith(base+path.sep))throw Error('Путь вне graphs');
    const graph=JSON.parse(fs.readFileSync(target,'utf8'));
    if((graph.identitySpace||'manual')!==space)throw Error('Неверный identitySpace');
    if(rootRequirementId!==undefined&&!graph.nodes.some(n=>n.id===rootRequirementId&&n.kind==='requirement'))throw Error('Неизвестная корневая R');
    allowed=new Set([...graph.nodes.map(n=>n.id),...graph.nodes.filter(n=>n.kind==='option'&&n.canonBlock).map(n=>'__canon__'+n.id),...(graph.collections||[]).map(c=>'__collection__'+c.id)]);
  }
  for(const id of Object.keys(command.positions||{}))if(!allowed.has(id))throw Error('Неизвестный узел: '+id);
 }
 const lock=file+'.lock',tmp=file+'.tmp-'+process.pid;
 let fd;
 try{
  fd=fs.openSync(lock,'wx');
  const before=core.validate(JSON.parse(fs.readFileSync(file,'utf8')));
  if(before.revision!==expected)throw Error('Конфликт ревизии: '+before.revision+' != '+expected);
  const after=core.commit(core.apply(before,commands),expected);
  fs.writeFileSync(tmp,JSON.stringify(after,null,2)+'\n',{flag:'wx'});
  fs.renameSync(tmp,file);
  const readback=core.validate(JSON.parse(fs.readFileSync(file,'utf8')));
  if(JSON.stringify(after)!==JSON.stringify(readback))throw Error('Read-back differs');
  if(file===path.join(root,'graphs/layouts.json'))cp.execFileSync('python3',[path.join(root,'tools/graph-index.py')],{stdio:'pipe'});
  console.log('LAYOUT_SAVED revision='+after.revision+' file='+file);
 }finally{
  if(fs.existsSync(tmp))fs.unlinkSync(tmp);
  if(fd!==undefined){fs.closeSync(fd);fs.unlinkSync(lock);}
 }
}
try{main();}catch(e){console.error('LAYOUT_ERROR',e.message);process.exitCode=1;}
