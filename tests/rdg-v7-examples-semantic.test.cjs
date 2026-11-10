const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {simulate}=require('./viewer-test-helper.cjs');
const ROOT=path.resolve(__dirname,'..');
const load=s=>JSON.parse(fs.readFileSync(path.join(ROOT,'graphs/examples',s,'graph.json'),'utf8'));
const parent=load('reference-mixed-active-work'),source=load('reference-prepared-planning-tree');
const children=[load('reference-mixed-feature-availability'),load('reference-mixed-feature-consistency')];
const find=(g,id)=>{const n=g.nodes.find(x=>x.id===id);assert(n,`${g.id}: missing ${id}`);return n;};
const sort=v=>Array.isArray(v)?v.map(sort):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sort(v[k])])):v;
test('two child R own their alternatives; index links exact R without a fabricated project commit',()=>{
 const index=JSON.parse(fs.readFileSync(path.join(ROOT,'graphs/index.json'),'utf8'));
 assert.equal(index.graphs.length,101);assert.equal(index.projectContexts[parent.identitySpace],undefined);
 for(const child of children){
  assert.equal(child.identitySpace,parent.identitySpace);
  assert.deepEqual(find(child,child.rootRequirementId).projectionOf,{graphSlug:parent.id,nodeId:child.rootRequirementId});
  assert(Array.isArray(find(child,child.rootRequirementId).qrpe));
  assert.equal(find(parent,child.rootRequirementId).kind,'requirement');
  const link=index.relations.find(r=>r.from==='reference-mixed-contextual-split'&&r.to===child.id);
  assert(!index.relations.some(r=>r.from===parent.id&&r.to===child.id),'root must stop before the contextual R children');
  assert(link&&link.relationKind==='selected'&&link.requirementId===child.rootRequirementId);
  assert.equal(link.introducedByDecisionId,'D-A');assert.equal(child.selectedInProject,false);
 }
 assert.deepEqual(children[0].nodes.filter(x=>x.kind==='option').map(x=>x.id),['O-ACT-1','O-ACT-2']);
 assert.equal(children[0].nodes.filter(x=>x.kind==='decision').length,0);
 assert.equal(find(children[1],'D-ACT-2').status,'selected-in-example-only');
 assert(!children[1].edges.some(x=>x.type==='INTRODUCES'),'direct answer has no fake child R');
 assert(!parent.nodes.some(x=>['O-ACT-1','O-ACT-2','D-ACT-2'].includes(x.id)));
});
test('prepared option pins source revision/hash and canon; T1 uses that same evidence',()=>{
 for(const [id,sourceId] of [['O-A','O-FEATURE'],['O-B','O-SCENARIO']]){
  const option=find(parent,id),template=find(source,sourceId);
  assert.deepEqual(option.canonBlock,template.canonBlock);
  assert.equal(option.preparedSource.graphSlug,source.id);
  assert.equal(option.preparedSource.sourceOptionId,sourceId);
  assert.equal(option.preparedSource.version,String(source.revision));
  assert.equal(option.preparedSource.canonHash,crypto.createHash('sha256').update(JSON.stringify(sort(template.canonBlock))).digest('hex'));
 }
 assert.equal(find(source,'RF-1-O1').directAnswer,true);
 assert(!source.nodes.some(x=>x.kind==='decision'));
});
test('T1 immutable at source revision 3 while current options pin the current revision (historical T1 still 3); T2/T3 preserved',()=>{
 const option=find(parent,'O-A'),d=find(parent,'D-A'),composite=find(parent,'R-COMP');
 assert.equal(d.status,'selected-in-example-only');assert.equal(d.selectedOptionId,'O-A');
 assert.deepEqual(d.selectionBasis.compositeSnapshot.history,[composite.history[0]]);
 assert.deepEqual(d.selectionBasis.optionSnapshot.canonBlock,option.canonBlock);
 assert.equal(d.selectionBasis.optionSnapshot.preparedSource.version,'3');
 assert.equal(option.preparedSource.version,String(source.revision));
 assert.equal(d.selectionBasis.optionSnapshot.preparedSource.canonHash,option.preparedSource.canonHash);
 const oldSource=fs.readFileSync(path.join(ROOT,'graphs/source-versions/reference-prepared-planning-tree-rev3.json'));
 assert.equal(crypto.createHash('sha256').update(oldSource).digest('hex'),'5247eadf78d1423e19f031a11fc68f453676a71d89b479a0fc41c32a45d7151f');
 assert.equal(JSON.parse(oldSource).revision,3);
 assert(d.selectionBasis.rationale.includes('риск')&&d.selectionBasis.rationale.includes('R-ACT-2'));
 assert(d.selectionBasis.acceptedContraindicationCaseIds.includes('O-FEATURE-minus-1'));
 assert.equal(option.qrpe.find(q=>q.id==='QR-A').status,'open');
 assert.equal(d.qrpe.find(q=>q.id==='QR-A').status,'open');
 assert.deepEqual(d.qrpe.find(q=>q.id==='QR-A-RES'),option.qrpe.find(q=>q.id==='QR-A-RES'));
 assert.deepEqual(option.qrpe.find(q=>q.id==='QR-A-RES').statusHistory.map(h=>h.status),['open','resolved']);
 assert.deepEqual(composite.history.map(h=>h.id),['T1','T2','T3']);
 assert(!composite.history[0].facts.some(f=>['R-LEGACY-API','D-OTHER'].includes(f.ref)));
 assert(composite.history[1].facts.some(f=>f.ref==='R-LEGACY-API'));
 assert(composite.history[2].facts.some(f=>f.ref==='R-AUDIT-CONSISTENCY'));
 assert.equal(find(parent,'R-LEGACY-API').knownAt,'T2');
 assert.equal(find(parent,'R-LEGACY-API').effectiveAt,'T0');
 assert.equal(find(parent,'R-AUDIT-CONSISTENCY').effectiveAt,'T3');
 for(const rev of composite.history)assert(rev.sourceRef&&rev.recordedAt&&rev.knownAt&&rev.effectiveAt);
});
test('reparent and inactive R retain archived relations and do not spawn another accepted D',()=>{
 const edges=parent.edges.filter(e=>e.to==='R-RELINK');
 assert.equal(edges.filter(e=>e.archived).length,1);
 assert.equal(edges.filter(e=>!e.archived&&e.from==='D-A'&&e.parent==='R-COMP').length,1);
 assert.equal(find(parent,'R-INACTIVE').status,'inactive');
 assert(parent.edges.some(e=>e.to==='R-INACTIVE'&&e.archived));
 const changes=parent.events.filter(e=>['requirement_deactivated','requirement_reparented'].includes(e.type));
 assert.equal(changes.length,2);assert(changes.every(e=>e.exampleOnly&&e.by==='example'));
 assert.equal(parent.nodes.filter(x=>x.kind==='decision').length,2);
 assert.equal(parent.nodes.filter(x=>x.id.startsWith('R-PREV-')&&x.status==='candidate').length,30);
});
test('Viewer sees selected canon with actual newlines and navigates to undecided child options',async()=>{
 const ui=simulate({useBundle:true});await ui.flush();await ui.openLevel('reference-mixed-active-work','R-COMP');
 const nodes=()=>ui.root.querySelectorAll('.node');
 const selected=nodes().find(n=>n.getAttribute('data-id')==='D-A');
 assert(selected);selected.listeners.click({stopPropagation(){}});
 const info=ui.info(),start=info.indexOf('Канон выбранного варианта');
 assert(start>=0&&info.slice(start,start+150).includes('\n'));
 assert(!info.slice(start,start+150).includes('\\n'),'literal backslash-n must not leak');
 const child=nodes().find(n=>n.getAttribute('data-id')==='R-ACT-1');
 assert(child&&child.classList.contains('drill'));
 child.listeners.click({stopPropagation(){}});await ui.flush();
 assert(ui.ids['bar-title'].textContent.includes('Availability'));
 const visible=nodes().map(n=>n.getAttribute('data-id'));
 assert(visible.includes('O-ACT-1')&&visible.includes('O-ACT-2'));
 assert(!visible.includes('D-ACT-2'));
});
