const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),folder=path.join(root,'graphs/examples');
const stems=['app','functionality','scenarios','realization','availability','reservation','scenario-create'];
const slug=s=>'reference-complete-'+s;
const graph=s=>JSON.parse(fs.readFileSync(path.join(folder,slug(s),'graph.json'),'utf8'));
const graphMap=new Map(stems.map(s=>[slug(s),graph(s)]));
const manifest=JSON.parse(fs.readFileSync(path.join(root,'graphs/index.json'),'utf8'));
const node=(g,id)=>g.nodes.find(n=>n.id==='SH-'+id);
const edges=(g,type)=>g.edges.filter(e=>e.type===type);
const typed=new Set([...graphMap.values()].flatMap(g=>g.edges.map(e=>e.type)));
const writerTypes=new Set(['DRIVES','INTRODUCES','DERIVES','CONTEXT_FOR','APPLIES_TO']);
const showcasedTypes=new Set(['DRIVES','INTRODUCES','DERIVES','CONTEXT_FOR','APPLIES_TO','INFORMS','IDENTIFIES','REVEALS_NEED',
 'USES_VARIANT','OPTION_FOR','USES_PREPARED','PER_ITEM_MODEL','GENERATES_ITEM_ROLE','INSTANCE_OF_MODEL',
 'GOVERNED_BY_SHARED_CHOICE','QRPE_FOR','RECONSIDERS']);

test('one coherent seven-level suite, stable distinct root Requirements, complete set of 17 relations',()=>{
 assert.deepEqual([...typed].sort(),[...showcasedTypes].sort());
 assert.equal(graphMap.size,7);
 let nodeCount=0,edgeCount=0;
 const roots=new Set();
 for(const [name,g] of graphMap){
  assert.equal(g.id,name);assert.equal(g.identitySpace,'showcase:booking-example-v1');
  assert.equal(g.rootRequirementId,g.nodes[0].id);
  assert.equal(g.nodes[0].kind,'requirement');assert(!roots.has(g.rootRequirementId));
  roots.add(g.rootRequirementId);
  assert.equal(g.readOnly,true);assert.equal(g.exampleOnly,true);
  assert.equal(g.selectedInProject,false);assert.equal(g.demonstrationGroup,'complete-booking-showcase');
  assert.equal(g.catalogHidden,name!==slug('app'));
  assert(g.sourceDocument.endsWith('COMPLETE-REFERENCE-GUIDE.md'));
  const ids=new Set(g.nodes.map(n=>n.id));
  const drivers=new Set(edges(g,'DRIVES').map(e=>e.from+'|'+e.to));
  assert.equal(ids.size,g.nodes.length);
  assert.equal(new Set(g.edges.map(e=>e.id)).size,g.edges.length);
  for(const e of g.edges){
   assert(ids.has(e.from)&&ids.has(e.to),name+' dangling edge '+e.id);
   assert(e.meaning?.length>15,name+' missing edge-specific explanation '+e.id);
   if(e.type==='INTRODUCES'){
    assert(ids.has(e.parent));
    assert(drivers.has(e.parent+'|'+e.from),'INTRODUCES parent driver '+e.id);
    assert.equal(g.nodes.find(n=>n.id===e.to).kind,'requirement');
   }
   if(e.type==='APPLIES_TO')assert.equal(g.nodes.find(n=>n.id===e.from).crosscutting,true);
  }
  for(const d of g.nodes.filter(n=>n.kind==='decision')){
   assert(d.status==='selected-in-example-only'||d.status==='superseded-in-example-only');
   assert.notEqual(d.selectedInProject,true);
  }
  assert(g.events.every(e=>e.exampleOnly===true&&e.by==='example-only'));
  nodeCount+=g.nodes.length;edgeCount+=g.edges.length;
 }
 assert.equal(nodeCount,73);assert.equal(edgeCount,73);
 assert([...writerTypes].every(t=>typed.has(t)));
 assert(!manifest.graphs.find(g=>g.slug===slug('app')).catalogHidden);
});

test('six separate Requirement-rooted graph levels derived from actual INTRODUCES, without manual arrows',()=>{
 const links=manifest.relations.filter(r=>r.from.startsWith('reference-complete-')&&r.relationKind==='selected'&&!r.to.startsWith('reference-complete-unit-'));
 const expected=[
  ['app','functionality','SH-R-FUNC'],['app','realization','SH-R-REALIZATION'],
  ['app','scenarios','SH-R-SCENARIOS'],['functionality','availability','SH-R-FEAT-AVAIL'],
  ['functionality','reservation','SH-R-FEAT-RES'],['scenarios','scenario-create','SH-R-SCREATE']
 ];
 assert.equal(links.length,expected.length);
 for(const [source,target,rid] of expected){
  const r=links.find(x=>x.from===slug(source)&&x.to===slug(target)&&x.requirementId===rid);
  assert(r,'missing relation '+source+' → '+target);
  const from=graph(source),to=graph(target);
  assert.equal(to.rootRequirementId,rid);
  assert(from.nodes.some(n=>n.id===rid&&n.kind==='requirement'));
  const intro=from.edges.find(e=>e.type==='INTRODUCES'&&e.to===rid);
  assert(intro);
  assert.equal(intro.from,r.introducedByDecisionId);
  assert.equal(intro.id,r.introductionEdgeId);
 }
 assert([...graphMap.values()].every(g=>g.parentGraphSlug===undefined&&
   g.nodes.every(n=>n.nextGraphSlug===undefined)));
});

test('one prepared PER_ITEM 1..N proposal leads to exactly two actual branches; one TM model with two applications',()=>{
 const app=graph('app'),g=graph('functionality');
 assert(!app.nodes.find(n=>n.id==='SH-V-BY-FEATURES'));
 assert.equal(node(app,'R-FUNC').title,'Расписать функционал');
 const prepared=node(g,'V-BY-FEATURES'),accepted=node(g,'D-CHOOSE-FEATURES');
 assert.equal(prepared.status,'reusable-unselected');
 assert.equal(prepared.repetition.cardinality,'1..N');
 assert.equal(prepared.repetition.mode,'PER_ITEM');
 assert.equal(accepted.concreteBranchCount,2);
 assert.equal(accepted.modelApplicationCount,2);
 assert.equal(edges(g,'INTRODUCES').length,2);
 assert.equal(edges(g,'INTRODUCES').filter(e=>e.from===accepted.id).length,2);
 assert(!edges(g,'INTRODUCES').some(e=>e.from===prepared.id));
 assert.equal(node(g,'R-FEATURE-ROLE').templateOnly,true);
 assert.equal(g.nodes.filter(n=>n.preparedModelId==='TM-FEATURE').length,1);
 const applications=g.nodes.filter(n=>n.kind==='application');
 assert.equal(applications.length,2);
 assert.deepEqual(new Set(applications.map(n=>n.targetRequirementId)),new Set(['SH-R-FEAT-AVAIL','SH-R-FEAT-RES']));
 assert.equal(new Set(applications.map(n=>n.governingDecisionRef)).size,1);
 assert.equal(edges(g,'GOVERNED_BY_SHARED_CHOICE').length,2);
 assert.equal(edges(g,'INSTANCE_OF_MODEL').length,2);
 assert(node(g,'V-BY-SCENARIOS').status==='reusable-unselected');
});

test('origins are NOT children; crosscutting has one ID, distinct scope edges; shared decision serves two Rs',()=>{
 const rr=graph('realization'),sc=graph('scenario-create');
 assert.equal(edges(rr,'INTRODUCES').length,0);
 assert.equal(edges(rr,'IDENTIFIES').length,1);
 assert.equal(edges(rr,'DERIVES').length,1);
 assert.equal(node(rr,'R-INDEPENDENT').crosscutting,true);
 assert.equal(edges(rr,'APPLIES_TO').length,2);
 assert(edges(rr,'APPLIES_TO').every(e=>e.from==='SH-R-INDEPENDENT'));
 for(const id of ['R-FEAT-AVAIL','R-FEAT-RES']){
  assert.equal(node(rr,id).referenceOnly,true);
  assert.equal(node(rr,id).title,node(graph(id.endsWith('AVAIL')?'availability':'reservation'),id).title);
 }
 assert.equal(edges(sc,'REVEALS_NEED').length,1);
 assert.equal(edges(sc,'INTRODUCES').length,0,'R-RESULT was discovered, not introduced as child of scenario writing');
 assert.equal(edges(sc,'INFORMS').length,1);
 assert.match(edges(sc,'INFORMS')[0].meaning,/только содержание/);
 assert.equal(edges(sc,'DRIVES').filter(e=>e.to==='SH-D-STATUS').length,2);
 assert.equal(sc.nodes.filter(n=>n.id==='SH-D-STATUS').length,1);
 assert(edges(sc,'QRPE_FOR').some(e=>e.to==='SH-D-STATUS'));
});

test('open candidate is distinct from actual historical revision in another level',()=>{
 const av=graph('availability'),rs=graph('reservation');
 assert.equal(edges(av,'INTRODUCES').length,0,'A direct D is valid');
 assert.equal(node(av,'D-AVAIL-OLD').status,'superseded-in-example-only');
 assert.equal(node(av,'D-AVAIL-NEW').status,'selected-in-example-only');
 assert.equal(av.events.filter(e=>e.type==='decision_revised').length,1);
  assert(av.events.some(e=>e.type==='decision_selected'&&e.decisionId==='SH-D-AVAIL-OLD'));
 assert.equal(node(rs,'PR-STATE').status,'pending');
 assert(edges(rs,'RECONSIDERS').some(e=>e.from==='SH-PR-STATE'));
 assert(!rs.events.some(e=>e.type==='decision_revised'));
 assert(rs.events.some(e=>e.type==='proposal_considered'));
 assert.equal(node(rs,'D-BEHAVIOR').status,'selected-in-example-only');
 assert(edges(rs,'USES_VARIANT').some(e=>e.from==='SH-PR-STATE'));
});

test('generator idempotence, writer strict restrictions and preserved original/real graphs',()=>{
 const py=spawnSync('python3',[path.join(root,'tools/build-complete-reference.py'),'--check'],{encoding:'utf8'});
 assert.equal(py.status,0,py.stderr);
 const expectedKinds=new Set(['requirement','decision','context','question','proposal']);
 assert([...graphMap.values()].some(g=>g.nodes.some(n=>!expectedKinds.has(n.kind))));
 const writer=fs.readFileSync(path.join(root,'tools/graph-apply.py'),'utf8');
 for(const type of writerTypes)assert(writer.includes('"'+type+'"'));
 assert(!writer.includes('"USES_VARIANT"'),'The writer must not silently acquire illustrative capabilities');
 const original=fs.readFileSync(path.join(root,'docs/examples/requirements-decisions-graph-examples-v0.2.source.md'),'utf8');
 assert(!original.includes('SH-R-APP'));
 const active=JSON.parse(fs.readFileSync(path.join(root,'graphs/workspaces/try-it/graph.json'),'utf8'));
 assert.equal(active.revision,1);assert.equal(active.nodes.length,1);assert.deepEqual(active.events,[]);
});
