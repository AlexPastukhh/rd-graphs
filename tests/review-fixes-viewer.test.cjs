const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {simulate,clone,fixture}=require('./viewer-test-helper.cjs');
const root=path.resolve(__dirname,'..');
const walk=(n,p)=>{const out=[];const go=x=>{if(p(x))out.push(x);for(const c of x.children||[])go(c);};go(n);return out;};
const pick=(app,id)=>walk(app.ids.canvas,n=>n.getAttribute?.('data-id')===id)[0];
const press=(app,id)=>pick(app,id).listeners.click({stopPropagation(){}});
test('fresh reload after embedded bundle never returns to older revision and preserves data on read failure',async()=>{
 const fresh=JSON.parse(fs.readFileSync(path.join(root,'graphs/workspaces/try-it/graph.json'),'utf8'));
 fresh.revision=2;fresh.nodes[0].title='Newer data';
 const files={'workspaces/try-it/graph.json':JSON.stringify(fresh)};
 const app=simulate({useBundle:true,files});await app.flush();await app.openCard('try-it');
 assert.match(app.text(),/revision 1/);
 await app.ids.reload.onclick();assert.match(app.text(),/revision 2/);
 await app.ids.reload.onclick();assert.match(app.text(),/revision 2/);
 fresh.revision=3;files['workspaces/try-it/graph.json']=JSON.stringify(fresh);
 await app.ids.reload.onclick();assert.match(app.text(),/revision 3/);
 delete files['workspaces/try-it/graph.json'];
 await app.ids.reload.onclick();
 assert.match(app.text(),/Сохраняется ранее открытый граф/);
 assert.match(app.info(),/Revision: 3/);
});
test('invalid events shape, duplicate event or wrong Decision reference reject without poisoning node inspector',async()=>{
 const app=simulate();await app.loadFile(fixture);
 for(const events of [{bad:'shape'},[{id:'e',type:'decision_selected',decisionId:'R-001'}],
   [{id:'e',type:'note'},{id:'e',type:'note'}],[{id:'',type:'note'}]]){
  const bad=clone(fixture);bad.events=events;await app.loadFile(bad);
  assert.match(app.text(),/Ошибка/);
  assert.doesNotThrow(()=>press(app,'D-001'));
  assert.match(app.info(),/D-001/);
 }
});
test('real workspace history is not labelled illustration; hypothetical history still is',async()=>{
 const app=simulate();const g=clone(fixture);
 g.exampleOnly=false;
 g.events=[{id:'real',type:'decision_selected',decisionId:'D-001',by:'user',note:'Actual selection'}];
 await app.loadFile(g);press(app,'D-001');
 assert.match(app.info(),/История:/);assert(!app.info().includes('История (иллюстрация)'));
 g.exampleOnly=true;g.events[0].by='example-only';g.events[0].exampleOnly=true;
 await app.loadFile(g);press(app,'D-001');assert.match(app.info(),/История \(иллюстрация\)/);
});
test('all bundled graphs have distinct label rectangles outside node rectangles in both edge modes',async()=>{
 const app=simulate({useBundle:true});await app.flush();
 const catalog=JSON.parse(fs.readFileSync(path.join(root,'graphs/index.json'),'utf8'));
 const xy=n=>(n.getAttribute('transform').match(/[-\d.]+/g)||[]).map(Number);
 const hit=(a,b)=>a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y;
 for(const item of catalog.graphs){
  const g=JSON.parse(fs.readFileSync(path.join(root,'graphs',item.file),'utf8'));await app.loadFile(g);
  for(const mode of ['edges-all','edges-core']){
   app.ids[mode].onclick();
   const scene=app.root.getElementById('scene');
   assert(scene.children.findIndex(n=>n.getAttribute?.('id')==='edge-label-leaders')<scene.children.findIndex(n=>n.getAttribute?.('id')==='edge-labels'));
   const labels=walk(app.ids.canvas,n=>n.classList?.contains('edge-label')).map(n=>{
    const [x,y]=xy(n),r=n.children.find(c=>c.tag==='rect');
    return {id:n.getAttribute('data-edge-id'),x:x+Number(r.getAttribute('x')),y:y+Number(r.getAttribute('y')),w:Number(r.getAttribute('width')),h:Number(r.getAttribute('height'))};
   });
   const nodes=walk(app.ids.canvas,n=>n.classList?.contains('node')).map(n=>{const [x,y]=xy(n);return {id:n.getAttribute('data-id'),x,y,w:222,h:72};});
   const visibleIds=new Set(nodes.map(n=>n.id));
   if(!g.collections?.length && !g.nodes.some(n=>n.kind==='option'))
    assert.equal(labels.length,g.edges.filter(e=>e.archived!==true&&visibleIds.has(e.from)&&visibleIds.has(e.to)&&(mode==='edges-all'||['DRIVES','INTRODUCES','DERIVES'].includes(e.type))).length);
   for(let i=0;i<labels.length;i++){
    for(let j=i+1;j<labels.length;j++)assert(!hit(labels[i],labels[j]),item.slug+': overlapping '+labels[i].id+' '+labels[j].id);
    for(const n of nodes)assert(!hit(labels[i],n),item.slug+': label on node '+labels[i].id+' '+n.id);
   }
  }
 }
});
test('reference inspector reads the one owner, opens that exact ID, and returns to the origin',async()=>{
 const app=simulate({useBundle:true});await app.flush();await app.openCard('reference-complete-app');
 press(app,'SH-R-FUNC');await app.flush();app.ids['edges-all'].onclick();
 press(app,'SH-R-FEAT-RES');await app.flush();
 app.ids.search.oninput({target:{value:'SH-D-STATUS'}});press(app,'SH-D-STATUS');
 assert.match(app.info(),/не превращать в отказ/);
 assert.match(app.info(),/SH-R-ERRORS/);
 const link=app.ids.info.children.find(n=>n.getAttribute?.('data-record-source')==='reference-complete-scenario-create');
 assert(link);await link.onclick();
 assert(pick(app,'SH-R-RESULT'));assert.match(app.info(),/SH-D-STATUS/);
 assert.equal(app.ids['level-up'].textContent,'← К предыдущему графу');
 await app.ids['level-up'].onclick();
 assert(pick(app,'SH-R-ERRORS'));assert.match(app.info(),/SH-D-STATUS/);
 const manual=JSON.parse(fs.readFileSync(path.join(root,'graphs/examples/reference-complete-reservation/graph.json'),'utf8'));
 await app.loadFile(manual);app.ids.search.oninput({target:{value:'SH-D-STATUS'}});press(app,'SH-D-STATUS');
 await app.ids.info.children.find(n=>n.getAttribute?.('data-record-source')==='reference-complete-scenario-create').onclick();
 await app.ids['level-up'].onclick();assert(pick(app,'SH-R-ERRORS'));assert.match(app.info(),/SH-D-STATUS/);
 delete manual.identitySpace;await app.loadFile(manual);app.ids.search.oninput({target:{value:'SH-D-STATUS'}});press(app,'SH-D-STATUS');
 assert(!app.ids.info.children.some(n=>n.getAttribute?.('data-record-source')));
});
test('Scenario-to-Feature information and one shared Behavior choice are concrete, not enum coverage',()=>{
 const read=s=>JSON.parse(fs.readFileSync(path.join(root,'graphs/examples/reference-complete-'+s+'/graph.json'),'utf8'));
 const fun=read('functionality'),res=read('reservation'),av=read('availability'),sc=read('scenario-create'),sets=read('scenarios');
 assert(fun.edges.some(e=>e.type==='INFORMS'&&e.from==='SH-D-DESCRIBE'&&e.to==='SH-D-CHOOSE-FEATURES'&&e.usedParts.includes('SH-CREATE-SLOT')));
 assert(fun.edges.some(e=>e.type==='INFORMS'&&e.from==='SH-D-CANCEL'&&e.usedParts.includes('SH-CANCEL-RESULT')));
 const shared=fun.nodes.find(n=>n.id==='SH-D-BEHAVIOR-SHARED');assert.match(shared.scope,/Availability.*Reservation/);
 for(const g of [av,res]){
  const ref=g.nodes.find(n=>n.id===shared.id);assert.equal(ref.projectionOf.graphSlug,fun.id);
  assert.equal(ref.scope,shared.scope);
 }
 const intro=res.edges.find(e=>e.type==='INTRODUCES'&&e.to==='SH-R-ERRORS');
 assert.equal(intro.from,shared.id);assert.equal(intro.parent,'SH-R-BEHAVIOR');
 assert(res.edges.some(e=>e.type==='DRIVES'&&e.from==='SH-R-ERRORS'&&e.to==='SH-D-STATUS'));
 assert(res.edges.some(e=>e.type==='DRIVES'&&e.from==='SH-R-RESULT'&&e.to==='SH-D-STATUS'));
 assert.equal(res.nodes.find(n=>n.id==='SH-D-STATUS').projectionOf.graphSlug,sc.id);
 const status=sc.nodes.find(n=>n.id==='SH-D-STATUS');
 assert(status.answerBindings.some(b=>b.requirementId==='SH-R-ERRORS'&&b.sufficiency.startsWith('partial')));
 assert(status.answerParts.some(p=>p.id==='SH-STATUS-CORRELATE'));
 assert(status.answerParts.some(p=>p.id==='SH-STATUS-NO-DUP'));
 const delegated=sets.nodes.find(n=>n.id==='SH-R-SCREATE');
 assert.equal(delegated.delegations[0].requirementId,delegated.id);
 assert.equal(delegated.delegations[0].targetModuleInstance,'SH-TM-SCREATE');
 assert.equal(delegated.delegations[0].fulfillment,'unverified');
 assert(av.nodes.some(n=>n.id==='SH-D-STATE-SELECTION'));
 assert(res.nodes.some(n=>n.id==='SH-D-STATE-RESERVATION'));
 assert.equal(res.nodes.find(n=>n.id==='SH-PR-STATE').status,'pending');
});
