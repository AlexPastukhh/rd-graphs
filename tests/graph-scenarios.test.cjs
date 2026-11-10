const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const original=JSON.parse(fs.readFileSync(path.join(__dirname,'../graphs/examples/example/graph.json'),'utf8'));
const clone=x=>JSON.parse(JSON.stringify(x));
const forwardTypes=new Set(['DRIVES','INTRODUCES','DERIVES']);
function pathBetween(graph,from,to) {
 const nodes=new Set(graph.nodes.map(x=>x.id)), queue=[[from]],seen=new Set([from]);
 while(queue.length){
   const p=queue.shift(),current=p[p.length-1];if(current===to)return p;
   for(const edge of graph.edges)if(forwardTypes.has(edge.type)&&edge.from===current&&
      nodes.has(edge.to)&&!seen.has(edge.to)){
       seen.add(edge.to);queue.push([...p,edge.to]);
   }
 }
 return null;
}
test('S03 fixture supports multi-level origin trace of requirement',()=>{
 const path=pathBetween(original,'R-001','R-005');
 assert.deepEqual(path,['R-001','D-001','R-002','D-002','R-004','R-005']);
});
test('S04 requirement may have a direct decision without decomposition',()=>{
 const d=original.nodes.find(n=>n.id==='D-003');
 assert(d);
 assert(original.edges.some(e=>e.type==='DRIVES'&&e.from==='R-005'&&e.to===d.id));
 assert(!original.edges.some(e=>e.type==='INTRODUCES'&&e.from===d.id));
});
test('S10 fixture has context attached to a decision without extra Requirement',()=>{
 const context=original.nodes.find(n=>n.id==='C-001');
 assert.equal(context.kind,'context');
 assert(original.edges.some(e=>e.from===context.id&&e.to==='D-003'&&e.type==='CONTEXT_FOR'));
});
test('S16 storage round-trip with separate test copy and manual change',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-test-'));
 try {
   const filename=path.join(dir,'graph.json');
   fs.writeFileSync(filename,JSON.stringify(original,null,2));
   const saved=JSON.parse(fs.readFileSync(filename,'utf8'));
   assert.equal(saved.revision,1);
   saved.revision=2;
   saved.nodes.push({id:'R-TEST',kind:'requirement',title:'Testing update visibility'});
   fs.writeFileSync(filename,JSON.stringify(saved,null,2));
   const next=JSON.parse(fs.readFileSync(filename,'utf8'));
   assert.equal(next.revision,2);assert(next.nodes.some(n=>n.id==='R-TEST'));
   assert.equal(original.revision,1);assert.equal(original.nodes.length,9);
 } finally {fs.rmSync(dir,{recursive:true,force:true});}
});
