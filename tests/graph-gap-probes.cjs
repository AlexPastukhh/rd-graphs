// Diagnostic probes of invalid graphs accepted by the current viewer.
// Exit code 0 means probes ran; ACCEPTED_INVALID is NOT a pass.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const base=path.resolve(__dirname,'..');
const original=JSON.parse(fs.readFileSync(path.join(base,'graphs/examples/example/graph.json'),'utf8'));
const script=fs.readFileSync(path.join(base,'tools/rd-graph-viewer.user.js'),'utf8');
const start=script.indexOf('  function validate(g) {');
const end=script.indexOf('  function make(',start);
const validate=vm.runInNewContext('('+script.slice(start,end).trim()+')');
const clone=()=>JSON.parse(JSON.stringify(original));
const probes=[
 ['G06 parent points to Context',g=>{
   g.edges.find(e=>e.type==='INTRODUCES').parent='C-001';
 }],
 ['G07 DRIVES Requirement-to-Requirement',g=>{
   g.edges[0].to='R-002';
 }],
 ['G08 cyclic decomposition R→D→R',g=>{
   g.edges.push({id:'E-009',type:'INTRODUCES',from:'D-001',to:'R-001',parent:'R-001'});
 }],
 ['G09 proposed Decision introduces current child',g=>{
   g.nodes.find(n=>n.id==='D-001').status='proposed';
 }],
 ['G12 invalid revision',g=>{g.revision='not-an-integer';}],
 ['G12 events is not array',g=>{g.events={bad:'shape'};}],
 ['G06 INTRODUCES edge from Requirement',g=>{
   g.edges.find(e=>e.type==='INTRODUCES').from='R-003';
 }],
 ['G07 unknown relationship type',g=>{g.edges[0].type='WHATEVER';}]
];
for(const [name,mutate] of probes){
  const g=clone();mutate(g);
  try{validate(g);console.log('ACCEPTED_INVALID | '+name);}
  catch(e){console.log('REJECTED | '+name+' | '+e.message);}
}
