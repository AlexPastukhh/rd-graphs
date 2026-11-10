'use strict';
// Candidate v6 stage 3: compare two identity and canon strategies against real legacy RDG.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'..');
const SCRIPT=path.join(ROOT,'tools/rdg-v6-stage3-comparison.py');
const EXAMPLE=path.join(ROOT,'graphs/examples/reference-mixed-active-work/graph.json');
const PREPARED=path.join(ROOT,'graphs/examples/reference-prepared-planning-tree/graph.json');
const canonical=x=>crypto.createHash('sha256').update(x).digest('hex');

function cli(args,expected=0){
 const r=spawnSync('python3',[SCRIPT,...args],{encoding:'utf8'});
 assert.equal(r.status,expected,r.stderr||r.stdout);
 return r;
}
function compare(file){return JSON.parse(cli(['--graph',file]).stdout);}
function caseEval(kind,obj){return JSON.parse(cli(['--case',kind,'--payload',JSON.stringify(obj)]).stdout);}
function temporaryGraph(edit,run) {
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-v6-stage3-'));
 const file=path.join(dir,'graph.json');
 try {
  const graph=structuredClone(JSON.parse(fs.readFileSync(EXAMPLE,'utf8')));
  edit(graph);
  fs.writeFileSync(file,JSON.stringify(graph));
  return run(file,graph);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
}

test('real v7 prepared/planning example: original bytes remain untouched',()=>{
 const before=canonical(fs.readFileSync(EXAMPLE));
 const rows=compare(EXAMPLE);
 assert.equal(rows.length,2);
 assert(rows.every(x=>x.checks.traceVerified));
 assert.equal(canonical(fs.readFileSync(EXAMPLE)),before);
 assert.equal(rows[0].projection.sourceDigest,rows[1].projection.sourceDigest);
 assert.equal(rows[0].projection.sourceGraphId,'reference-mixed-active-work');
});

test('Option ID reuse is a stable Action ID, with historical D as separate occurrence',()=>{
 const p=compare(EXAMPLE)[0].projection;
 assert.equal(p.strategy,'reuse-option-id');
 assert.equal(p.actions.length,13);
 const selected=p.selectionOccurrences.find(s=>s.legacyDecisionId==='D-A');
 assert(selected);
 assert.equal(selected.actionId,'O-A');
 assert.equal(selected.legacyOptionId,'O-A');
 assert.equal(selected.sourceAuthority,'illustrative');
 assert.equal(selected.selectionBasis.optionSnapshot.id,'O-A');
 assert.equal(selected.selectionBasis.compositeSnapshot.history[0].id,'T1');
 assert(selected.decisionQrpe.length>0);
 assert.equal(p.introducedRequirements.filter(r=>r.legacyDecisionId==='D-A').length,3);
 assert.equal(p.actions.find(a=>a.legacyOptionId==='O-A').sourceVersionPin.version,'6');
 assert.equal(p.actions.find(a=>a.legacyOptionId==='O-A').qualifiedActionRef.graphIdentitySpace,'rdg-example-mixed-v7');
});

test('New Action IDs need alias mapping; never misattribute a legacy Decision',()=>{
 const p=compare(EXAMPLE)[1].projection;
 assert.equal(p.strategy,'new-action-id');
 assert.equal(p.actions.length,13);
 const action=p.actions.find(a=>a.legacyOptionId==='O-A');
 assert.equal(action.actionId,'action:O-A');
 assert.equal(action.qualifiedActionRef.localActionId,action.actionId);
 assert.equal(p.selectionOccurrences[0].actionId,'action:O-A');
 assert.equal(p.selectionOccurrences[0].legacyDecisionId,'D-A');
 assert.deepEqual(p.unmappedDecisions.map(x=>x.legacyDecisionId),['D-OTHER']);
 assert.equal(p.unmappedDecisions[0].reason,'NO_VERIFIED_OPTION_LINK');
});

test('A graph of candidates has no actual decision occurrence',()=>{
 const p=compare(PREPARED)[0].projection;
 assert.equal(p.actions.length,12);
 assert.deepEqual(p.selectionOccurrences,[]);
 assert.deepEqual(p.unmappedDecisions,[]);
 assert.equal(p.introducedRequirements.length,0);
 assert.equal(p.originalCounts.decisions,0);
});

test('no status promotion or outcome claim is invented from historical example',()=>{
 for(const row of compare(EXAMPLE)) {
  const p=row.projection;
  assert.equal(row.checks.migrationFullyResolved,false);
  assert.deepEqual(row.checks.unmappedDecisionIds,['D-OTHER']);
  assert(p.actions.find(x=>x.legacyOptionId==='O-A').candidateStatus==='candidate');
  assert(p.selectionOccurrences.every(x=>x.sourceAuthority==='illustrative'));
  assert(!('performed' in p.actions[0]));
 }
});

test('source T1 conflicting selected option is rejected, without rewriting source',()=>{
 temporaryGraph(g=>{
  const d=g.nodes.find(n=>n.id==='D-A');
  d.selectionBasis.optionSnapshot.id='O-B';
 },file=>{
  const r=cli(['--graph',file],1);
  assert.match(r.stderr,/optionSnapshot disagrees/);
 });
});

test('new generated Action ID collision fails instead of stealing an existing R identity',()=>{
 temporaryGraph(g=>{
  g.nodes.push({id:'action:O-A',kind:'requirement',title:'reserved ID'});
 },file=>{
  const r=cli(['--graph',file,'--strategy','new-action-id'],1);
  assert.match(r.stderr,/Action ID collision/);
  assert.equal(JSON.parse(cli(['--graph',file,'--strategy','reuse-option-id']).stdout).length,1);
 });
});

test('qualified source refs differ between definitions and applications',()=>{
 const p1=compare(EXAMPLE)[0].projection;
 const p2=compare(PREPARED)[0].projection;
 const x=p1.actions.find(a=>a.legacyOptionId==='O-A');
 const y=p2.actions.find(a=>a.legacyOptionId==='O-FEATURE');
 assert.equal(x.sourceVersionPin.sourceOptionId,y.legacyOptionId);
 assert.notDeepEqual(x.qualifiedActionRef,y.qualifiedActionRef);
 assert.equal(x.sourceVersionPin.canonHash.length,64);
});

test('candidate assessment has rationale, context version and evidence; engine does not claim truth',()=>{
 const canon={id:'CAN-MAINT',text:'Выгода способа достаточна'};
 const got=caseEval('assessment',{canon,assessment:{result:'applicable',rationale:'Данные соответствуют канону',
   evidenceRefs:['graph:work/R-1','report:cost-1'],contextVersion:'T2'}});
 assert.equal(got.status,'applicable');
 assert.equal(got.verifiedByEngine,false);
 assert.deepEqual(got.evidenceRefs,['graph:work/R-1','report:cost-1']);
 const unknown=caseEval('assessment',{canon,assessment:{result:'unknown',
   rationale:'Отсутствуют достоверные данные',evidenceRefs:[],contextVersion:'T2'}});
 assert.equal(unknown.status,'unknown');
});

test('cannot assert a definite canon result without evidence or context version',()=>{
 const canon={id:'X',text:'Some check'};
 for(const assessment of [
  {result:'applicable',rationale:'No proof',evidenceRefs:[],contextVersion:'T2'},
  {result:'applicable',rationale:'Proof',evidenceRefs:['R-1']},
  {result:'applicable',rationale:'',evidenceRefs:['R-1'],contextVersion:'T2'},
 ]) {
  const r=cli(['--case','assessment','--payload',JSON.stringify({canon,assessment})],1);
  assert.match(r.stderr,/ValueError/);
 }
});

test('minimal typed predicate handles present/missing/stale versioned inputs',()=>{
 const predicate={op:'requirement_present',field:'R-TECH'};
 assert.equal(caseEval('typed',{predicate,inputs:{version:'T1',requirements:['R-TECH']}}).status,'applicable');
 assert.equal(caseEval('typed',{predicate,inputs:{version:'T1',requirements:['R-OTHER']}}).status,'inapplicable');
 assert.equal(caseEval('typed',{predicate,inputs:{version:'T1'}}).status,'unknown');
 assert.equal(caseEval('typed',{predicate,inputs:{version:'T2',requirements:['R-TECH'],stale:true}}).status,'stale');
 const contextPred={op:'context_equals',field:'approved',equals:true};
 assert.equal(caseEval('typed',{predicate:contextPred,inputs:{version:'T2',context:{approved:true}}}).status,'applicable');
 assert.equal(caseEval('typed',{predicate:contextPred,inputs:{version:'T2',context:{}}}).status,'unknown');
});

test('typed approach does not pretend to evaluate legacy natural-language canon text',()=>{
 const r=cli(['--case','typed','--payload',JSON.stringify({
  predicate:{op:'semantic_adequacy',text:'This is a free-form canon'},inputs:{version:'T1'}
 })],1);
 assert.match(r.stderr,/Unsupported typed predicate/);
});
test('unmatched historical Decision keeps its child links and event snapshots',()=>{
 for(const row of compare(EXAMPLE)){
  const p=row.projection,unmapped=p.unmappedDecisions.find(x=>x.legacyDecisionId==='D-OTHER');
  assert(unmapped && row.checks.traceVerified);
  assert.equal(unmapped.relatedEdges.filter(e=>e.type==='INTRODUCES').length,3);
  assert(unmapped.relatedEdges.some(e=>e.type==='DRIVES'));
  assert.equal(unmapped.eventSnapshots[0].decisionId,'D-OTHER');
  assert.equal(unmapped.decisionSnapshot.selectedOptionId,undefined);
  assert.equal(p.originalCounts.introducedEdges,
    p.introducedRequirements.length + unmapped.relatedEdges.filter(e=>e.type==='INTRODUCES').length);
 }
});

test('older Decision-only graph remains historical, not fabricated into an Action',()=>{
 const path0=path.join(ROOT,'graphs/examples/reference-complete-availability/graph.json');
 for(const row of compare(path0)){
  assert.equal(row.projection.actions.length,0);
  assert.equal(row.projection.selectionOccurrences.length,0);
  assert.equal(row.projection.unmappedDecisions.length,4);
  assert.equal(row.checks.migrationFullyResolved,false);
 }
});

test('a user-authored event can be linked but never auto-implies performed Action',()=>{
 temporaryGraph(g=>{
  const d=g.nodes.find(n=>n.id==='D-A');
  d.status='committed';
  delete d.selectedInExampleOnly;
  for(const ev of g.events.filter(e=>e.decisionId==='D-A')) {
   ev.by='user';delete ev.exampleOnly;delete ev.hypothetical;
  }
 },file=>{
  for(const row of compare(file)){
   assert.equal(row.projection.selectionOccurrences[0].sourceAuthority,'event-backed');
   assert(!('performed' in row.projection.selectionOccurrences[0]));
  }
 });
});

test('tampered selection binding or downstream-child evidence is rejected',()=>{
 const script=`
import json,sys,importlib.machinery
m=importlib.machinery.SourceFileLoader('candidate',sys.argv[1]).load_module()
graph=json.load(open(sys.argv[2]))
original=m.identity_projection(graph,'reuse-option-id')
assert m.check_projection(graph,original)['traceVerified'] is True
p=json.loads(json.dumps(original))
p['selectionOccurrences'][0]['actionId']='WRONG-A'
try:m.check_projection(graph,p)
except ValueError as exc: assert 'SELECTION_LINK_MISMATCH' in str(exc)
else:raise AssertionError('tampered selection binding accepted')
p=json.loads(json.dumps(original))
p['unmappedDecisions'][0]['relatedEdges']=[]
try:m.check_projection(graph,p)
except ValueError as exc: assert 'UNMAPPED_DECISION_EDGES_LOST' in str(exc)
else:raise AssertionError('legacy child links lost silently')
print('BOUND REFERENCES VERIFIED')
`;
 const r=spawnSync('python3',['-c',script,SCRIPT,EXAMPLE],{encoding:'utf8'});
 assert.equal(r.status,0,r.stderr);
 assert.match(r.stdout,/BOUND REFERENCES VERIFIED/);
});

