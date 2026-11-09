const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..');
function setup(){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-v7-package-'));
 fs.mkdirSync(path.join(dir,'tools'),{recursive:true});
 for(const n of ['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js','rdg-modules.py','rdg-module-registry.json','rdg-module-test.py','graph-apply.py','graph-index.py','rdg-catalog.py','graph-package.py','rdg-transaction-io.py','rdg-v7-model.py','rdg-context.py'])
   fs.copyFileSync(path.join(ROOT,'tools',n),path.join(dir,'tools',n));
 const graph=(id)=>({schemaVersion:1,id,identitySpace:'v7-transaction',rootRequirementId:'R-'+id,
  planningScale:'module',revision:1,title:'Project '+id,
  nodes:[{id:'R-'+id,kind:'requirement',title:'Goal '+id}],edges:[],events:[]});
 const create={schemaVersion:1,transactionId:'create-v7',changes:[
  {file:'workspaces/first/graph.json',create:graph('first')},
  {file:'workspaces/second/graph.json',create:graph('second')}]};
 const opts={schemaVersion:1,transactionId:'update-v7-1',changes:[
  {file:'workspaces/first/graph.json',patch:{schemaVersion:1,expectedRevision:1,operations:[
    {op:'add_option',requirementId:'R-first',option:{id:'O1',kind:'option',title:'Candidate',
     origin:'situational',canonBlock:{recommended:[{id:'p',text:'Positive',checkCollections:[{graphSlug:'second',collectionId:'TECH'},'UNKNOWN-GROUP']}],contraindicated:[]}}},
    {op:'append_qrpe',targetId:'O1',issue:{id:'Q1',text:'Is this suitable?',status:'open'}},
    {op:'add_composite',requirement:{id:'RC1',kind:'requirement',title:'Composed goal',compositeOf:'R-first',
      history:[{id:'T1',recordedAt:'T1',statement:'Composed goal',facts:[]}]}}
  ]}},
  {file:'workspaces/second/graph.json',patch:{schemaVersion:1,expectedRevision:1,operations:[
    {op:'add_node',node:{id:'R-TECH',kind:'requirement',title:'Tech requirement'}},
    {op:'add_collection',collection:{id:'TECH',title:'Tech collection',anchor:'R-second',memberRefs:['R-TECH']}},
    {op:'add_option',requirementId:'R-second',option:{id:'O2',kind:'option',title:'Prepared plan',
      origin:'prepared',canonBlock:{recommended:[],contraindicated:[]}}}
  ]}}
 ]};
 const patch=path.join(dir,'patch.json');
 const run=(pkg)=>{
   fs.writeFileSync(patch,JSON.stringify(pkg));
   return spawnSync('python3',[path.join(dir,'tools/graph-apply.py'),'--package','--patch',patch],{encoding:'utf8'});
 };
 const read=(slug)=>JSON.parse(fs.readFileSync(path.join(dir,'graphs/workspaces',slug,'graph.json')));
 const cleanup=()=>fs.rmSync(dir,{recursive:true,force:true});
 return {dir,patch,create,opts,run,read,cleanup};
}
test('v7 two-file update with option, composite, QRPE, collection keeps revision replay and context index consistent',()=>{
 const f=setup();try{
  assert.equal(f.run(f.create).status,0);
  let r=f.run(f.opts);assert.equal(r.status,0,r.stderr);
  assert.equal(f.read('first').revision,2);assert.equal(f.read('second').revision,2);
  assert.equal(f.read('first').nodes.find(x=>x.id==='O1').qrpe[0].id,'Q1');
  assert.equal(f.read('second').collections[0].memberRefs[0],'R-TECH');
  const manifest=JSON.parse(fs.readFileSync(path.join(f.dir,'graphs/index.json')));
  assert(manifest.projectContexts['v7-transaction'].records.some(n=>n.id==='R-TECH'));
  assert.equal(f.run(f.opts).status,0,'idempotent retry must succeed');
  assert.equal(f.read('first').revision,2);
  const different=structuredClone(f.opts);different.changes[0].patch.operations[0].option.title='Changed';
  r=f.run(different);
  assert.notEqual(r.status,0);assert.match(r.stderr,/TRANSACTION_ID_CONFLICT/);
 }finally{f.cleanup();}
});
test('v7 journal recovery completes interrupted two-file composite and collection update',()=>{
 const f=setup();try{
  assert.equal(f.run(f.create).status,0);
  fs.writeFileSync(f.patch,JSON.stringify(f.opts));
  const script=[
   'import importlib.machinery,json,hashlib',
   'm=importlib.machinery.SourceFileLoader("pkg","'+f.dir+'/tools/graph-package.py").load_module()',
   'p=json.load(open("'+f.patch+'"))',
   'records=m.prepare(p)',
   'journal={"schemaVersion":1,"state":"prepared","transactionId":p["transactionId"],"requestSHA256":hashlib.sha256(m.encoded(p).encode()).hexdigest(),"records":records}',
   'm.write_json(m.journal_dir()/(p["transactionId"]+".json"),journal)',
   'm.write_json(m.target_path(records[0]["file"]),records[0]["after"])'
  ].join('\n');
  const saved=path.join(f.dir,'crash-sim.py');fs.writeFileSync(saved,script);
  let r=spawnSync('python3',[saved],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);
  r=f.run(f.opts);assert.equal(r.status,0,r.stderr);assert.match(r.stdout,/recovered=1/);
  assert.equal(f.read('first').revision,2);assert.equal(f.read('second').revision,2);
  const index=JSON.parse(fs.readFileSync(path.join(f.dir,'graphs/index.json')));
  assert.equal(index.graphs.filter(x=>x.group==='workspaces').length,2);
  assert(index.projectContexts['v7-transaction'].collections.some(c=>c.id==='TECH'));
 }finally{f.cleanup();}
});
test('canon-directed context query uses project collections, distinguishes unknown and cannot access another project',()=>{
 const f=setup();try{
  assert.equal(f.run(f.create).status,0);
  assert.equal(f.run(f.opts).status,0);
  const query=(space)=>spawnSync('python3',[path.join(f.dir,'tools/rdg-context.py'),
    '--identity-space',space,'--graph-slug','first','--option-id','O1'],{encoding:'utf8'});
  let r=query('v7-transaction');assert.equal(r.status,0,r.stderr);
  const result=JSON.parse(r.stdout);
  assert.equal(result.overallVerdict,'not-evaluated');
  assert(result.canonChecks[0].queries.some(q=>q.collectionId==='TECH'&&q.status==='indexed-collection'));
  assert(result.canonChecks[0].uncertainties.some(q=>q.collectionId==='UNKNOWN-GROUP'&&q.status==='unknown'));
  assert(result.canonChecks[0].candidatesNeedingAssessment.some(q=>q.id==='R-TECH'),
    'undated and unscoped evidence is a search lead, not confirmed current applicability');
  r=query('another-project');assert.notEqual(r.status,0);
  assert.match(r.stderr,/identitySpace/);
 }finally{f.cleanup();}
});

test('same Collection ID on two graphs remains owner-scoped; explicit cross-file ref is separate',()=>{
 const f=setup();try{
  assert.equal(f.run(f.create).status,0);
  const pkg=structuredClone(f.opts);
  pkg.transactionId='local-collection-collision';
  pkg.changes[0].patch.operations.push(
    {op:'add_node',node:{id:'R-LOCAL',kind:'requirement',title:'Local requirement'}},
    {op:'add_collection',collection:{id:'TECH',title:'Local TECH',anchor:'R-first',memberRefs:['R-LOCAL']}}
  );
  pkg.changes[0].patch.operations[0].option.canonBlock.recommended=[
    {id:'local',text:'Local',checkCollections:['TECH']},
    {id:'remote',text:'Remote',checkCollections:[{graphSlug:'second',collectionId:'TECH'}]}
  ];
  let r=f.run(pkg);assert.equal(r.status,0,r.stderr);
  const call=spawnSync('python3',[path.join(f.dir,'tools/rdg-context.py'),
    '--identity-space','v7-transaction','--graph-slug','first','--option-id','O1',
    '--as-of','2026-10-15'],{encoding:'utf8'});
  assert.equal(call.status,0,call.stderr);
  const result=JSON.parse(call.stdout).canonChecks;
  assert.deepEqual(result[0].candidatesNeedingAssessment.map(x=>x.id),['R-LOCAL']);
  assert.deepEqual(result[1].candidatesNeedingAssessment.map(x=>x.id),['R-TECH']);
  assert(!result[0].candidatesNeedingAssessment.some(x=>x.graphSlug==='second'));
  assert(!result[1].candidatesNeedingAssessment.some(x=>x.graphSlug==='first'));
 }finally{f.cleanup();}
});
test('canon lookup never presents future/unrelated contexts as applicable',()=>{
 const f=setup();try{
  assert.equal(f.run(f.create).status,0);
  const pkg=structuredClone(f.opts);
  pkg.transactionId='temporal-context-probe';
  pkg.changes[0].patch.operations[0].option.canonBlock.recommended.push({
   id:'dated',text:'Dated candidates',
   checkRequirements:['C-FUTURE','C-NOW','C-OTHER','C-UNKNOWN']
  });
  pkg.changes[1].patch.operations.push(
   {op:'add_node',node:{id:'C-FUTURE',kind:'context',title:'Later',effectiveAt:'2032-01-01',scope:'area'}},
   {op:'add_node',node:{id:'C-NOW',kind:'context',title:'Effective',effectiveAt:'2025-01-01',scope:'area'}},
   {op:'add_node',node:{id:'C-OTHER',kind:'context',title:'Different scope',effectiveAt:'2025-01-01',scope:'other'}},
   {op:'add_node',node:{id:'C-UNKNOWN',kind:'context',title:'No time or scope'}}
  );
  let r=f.run(pkg);assert.equal(r.status,0,r.stderr);
  const call=spawnSync('python3',[path.join(f.dir,'tools/rdg-context.py'),
    '--identity-space','v7-transaction','--graph-slug','first','--option-id','O1',
    '--target-scope','area','--as-of','2026-10-15'],{encoding:'utf8'});
  assert.equal(call.status,0,call.stderr);
  const dated=JSON.parse(call.stdout).canonChecks.find(x=>x.caseId==='dated');
  assert.deepEqual(dated.relevantCandidates.map(x=>x.id),['C-NOW']);
  assert(dated.excludedCandidates.some(x=>x.id==='C-FUTURE'&&x.applicability.timeStatus==='future'));
  assert(dated.candidatesNeedingAssessment.some(x=>x.id==='C-OTHER'&&x.applicability.scopeStatus==='not-proven'));
  assert(dated.candidatesNeedingAssessment.some(x=>x.id==='C-UNKNOWN'));
  assert.equal(f.read('first').revision,2);
 }finally{f.cleanup();}
});

test('declared non-overlap cannot override nested scope; other disjointness remains explicitly unverified',()=>{
 const path=require('node:path'),cp=require('node:child_process');
 const script=[
  'import importlib.machinery as m',
  "w=m.SourceFileLoader('w',"+JSON.stringify(path.join('/workspace/repos/rd-graphs','tools/graph-apply.py'))+").load_module()",
  "g={'schemaVersion':1,'id':'scope-probe','revision':1,'nodes':[{'id':'R','kind':'requirement','title':'Goal'}],'edges':[],'events':[]}",
  "c={'recommended':[],'contraindicated':[]}",
  "g,_=w.apply(g,{'schemaVersion':1,'expectedRevision':1,'operations':[{'op':'add_option','requirementId':'R','option':{'id':i,'kind':'option','title':i,'origin':'situational','canonBlock':c}} for i in ('O1','O2')]})",
  "def pick(opt,did,scope,extra={}): return {'op':'select_option','optionId':opt,'driverId':'R','decision':{'id':did,'kind':'decision','title':did,'status':'committed','scope':scope,**extra},'event':{'id':'EV-'+did,'type':'decision_selected','decisionId':did,'by':'user','note':'fixture choice'}}",
  "g,_=w.apply(g,{'schemaVersion':1,'expectedRevision':2,'operations':[pick('O1','D1','mobile')]})",
  "try:w.apply(g,{'schemaVersion':1,'expectedRevision':3,'operations':[pick('O2','D2','mobile/app',{'disjointFromScopes':['mobile'],'scopeDisjointReason':'claim only'})]})",
  "except ValueError as e:assert 'SCOPE_OVERLAP' in str(e),e",
  "else:raise AssertionError('hierarchical overlap accepted')",
  "g,_=w.apply(g,{'schemaVersion':1,'expectedRevision':3,'operations':[pick('O2','D2','web',{'disjointFromScopes':['mobile'],'scopeDisjointReason':'different channels'})]})",
  "assert next(n for n in g['nodes'] if n['id']=='D2')['scopeCompatibility']=='declared-unverified'",
  "print('SCOPE_SAFE')"
 ].join('\n');
 const r=cp.spawnSync('python3',['-c',script],{encoding:'utf8'});
 assert.equal(r.status,0,r.stderr);
 assert.match(r.stdout,/SCOPE_SAFE/);
});
