const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const crypto=require('node:crypto');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..');
function setup(){
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-v7-'));
 const tools=path.join(temp,'tools');
 fs.mkdirSync(tools,{recursive:true});
 for(const file of ['rdg-state.py','rdg-state-cli.cjs','rdg-state.js','rdg-catalog.js','rdg-modules.py','rdg-module-registry.json','rdg-module-test.py','graph-apply.py','graph-index.py','rdg-catalog.py','graph-package.py','rdg-transaction-io.py','rdg-v7-model.py'])
  fs.copyFileSync(path.join(ROOT,'tools',file),path.join(tools,file));
 const dir=path.join(temp,'graphs','workspaces','v7-integration');
 fs.mkdirSync(dir,{recursive:true});
 const graph=path.join(dir,'graph.json');
 fs.writeFileSync(graph,JSON.stringify({schemaVersion:1,id:'v7-work',
  identitySpace:'v7-scope',rootRequirementId:'R0',
  title:'Isolated real writer test',planningScale:'module',revision:1,
  nodes:[{id:'R0',kind:'requirement',title:'Разбить функциональность'}],edges:[],events:[]},null,2));
 const preparedDir=path.join(temp,'graphs/examples/reference-prepared');
 fs.mkdirSync(preparedDir,{recursive:true});
 fs.writeFileSync(path.join(preparedDir,'graph.json'),JSON.stringify({
  schemaVersion:1,id:'reference-prepared',revision:1,title:'Library',readOnly:true,
  exampleOnly:true,templateOnly:true,planningScale:'module',
  identitySpace:'isolated-library',rootRequirementId:'R-REF',events:[],edges:[],
  nodes:[{id:'R-REF',kind:'requirement',title:'Library root'},
   {id:'O-PREP',kind:'option',title:'Library option',origin:'prepared',
    canonBlock:canon}]
 }));
 const patchPath=path.join(temp,'patch.json');
 return {
  run(ops,revision){
   fs.writeFileSync(patchPath,JSON.stringify({schemaVersion:1,expectedRevision:revision,operations:ops}));
   return spawnSync('python3',[path.join(tools,'graph-apply.py'),'--graph',graph,'--patch',patchPath],{encoding:'utf8',env:{...process.env,RDG_ISOLATED_TEST_ONLY:'1'}});
  },
  read(){return JSON.parse(fs.readFileSync(graph,'utf8'));},
  clean(){fs.rmSync(temp,{force:true,recursive:true});}
 };
}
const canon={recommended:[{id:'plus1',text:'Параллельная проработка функционала',checkCategories:['features']}],
 contraindicated:[{id:'minus1',text:'Сильные сквозные зависимости',checkCategories:['consistency']}]};
const stable=x=>Array.isArray(x)?x.map(stable):x&&typeof x==='object'?
 Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>[k,stable(v)])):x;
const canonHash=crypto.createHash('sha256').update(JSON.stringify(stable(canon))).digest('hex');
const optA={id:'O-A' ,kind:'option',title:'Разбивать по Features',status:'candidate',
 origin:'prepared',preparedSource:{graphSlug:'reference-prepared',sourceOptionId:'O-PREP',version:'1',canonHash},
 canonBlock:canon};
const optB={id:'O-B',kind:'option',title:'Разбивать по сценариям',status:'candidate',
 origin:'situational',canonBlock:{recommended:[],contraindicated:[]}};
const composite={id:'R-C',kind:'requirement',title:'Разбить с параллельной работой и согласованностью',
 status:'candidate',compositeOf:'R0',
 history:[{id:'T1',recordedAt:'2026-10-15',statement:'Разбить с параллельной работой и согласованностью',
 facts:[{ref:'R-TECH',state:'checked-present'}]}]};
const base=[
 {op:'add_node',node:{id:'R-TECH',kind:'requirement',title:'Согласованность всех Features',status:'active'}},
 {op:'add_option',requirementId:'R0',option:optA},
 {op:'add_option',requirementId:'R0',option:optB},
 {op:'add_composite',requirement:composite},
 {op:'append_qrpe',targetId:'O-A',issue:{id:'Q1',text:'Сквозная целостность под вопросом',status:'open',recordedAt:'2026-10-15'}},
 {op:'append_qrpe',targetId:'O-B',issue:{id:'Q2',text:'Дублирование проработки?',status:'resolved'}},
 {op:'add_collection',collection:{id:'COL-TECH',title:'Технические требования',anchor:'R0',memberRefs:['R-TECH']}}
];
const chosen={op:'select_option',optionId:'O-A',driverId:'R-C',
 decision:{id:'D-A',kind:'decision',title:'Принято разбиение по Features',status:'committed'},
 event:{id:'EV-A',type:'decision_selected',by:'user',note:'Пользователь явно принял Features, сохранив риск Q1',decisionId:'D-A'},
 children:[{role:'subgoal',requirement:{id:'R1',kind:'requirement',title:'Проработать Availability'}},
           {role:'method_correctness',requirement:{id:'R2',kind:'requirement',title:'Согласовать Features'}}]};
test('v7 workspace: candidate canons, shared composite, QRPE before selection, chosen D with risk and two child roles',()=>{
 const w=setup();try{
  let r=w.run(base,1);assert.equal(r.status,0,r.stderr);
  let g=w.read();assert.equal(g.revision,2);assert.equal(g.nodes.filter(n=>n.kind==='option').length,2);
  assert.equal(g.collections[0].anchor,'R0');
  assert.equal(g.nodes.find(n=>n.id==='R-C').history[0].id,'T1');
  r=w.run([chosen],2);assert.equal(r.status,0,r.stderr);
  g=w.read();assert.equal(g.revision,3);
  const d=g.nodes.find(n=>n.id==='D-A');
  assert.equal(d.selectedOptionId,'O-A');assert.equal(d.qrpe[0].status,'open');
  assert.equal(d.selectionBasis.compositeSnapshot.history[0].id,'T1');
  assert.deepEqual(g.edges.filter(e=>e.type==='INTRODUCES').map(e=>e.childRole),['subgoal','method_correctness']);
  assert.equal(g.events[0].by,'user');
  const extend=[
   {op:'append_composite_revision',requirementId:'R-C',revision:{id:'T2',recordedAt:'2026-10-16',
     effectiveAt:'2026-10-10',statement:'Учитывая ранее упущенную сквозную зависимость',facts:[{ref:'R-TECH',state:'checked-present'}]}},
   {op:'append_qrpe',targetId:'D-A',issue:{id:'Q-T2',text:'Было известно объективно, но не замечено',status:'open',recordedAt:'2026-10-16',effectiveAt:'2026-10-10'}}
  ];
  r=w.run(extend,3);assert.equal(r.status,0,r.stderr);
  g=w.read();assert.equal(g.revision,4);assert.equal(g.nodes.find(n=>n.id==='R-C').history.length,2);
  assert.equal(g.nodes.find(n=>n.id==='R-C').title,composite.title,'stable R title');
  assert.match(g.nodes.find(n=>n.id==='R-C').currentStatement,/ранее упущенную/);
  assert.equal(g.nodes.find(n=>n.id==='D-A').selectionBasis.compositeSnapshot.history.length,1);
  assert.equal(g.nodes.find(n=>n.id==='D-A').qrpe.length,2);
 }finally{w.clean();}
});
test('v7 writer rejects selection without actual event and retains previous candidate state',()=>{
 const w=setup();try{
  assert.equal(w.run(base,1).status,0);
  const bad=structuredClone(chosen);bad.event.by='template';
  const previous=JSON.stringify(w.read());const r=w.run([bad],2);
  assert.notEqual(r.status,0);assert.match(r.stderr,/user|assistant|selection/i);
  assert.equal(JSON.stringify(w.read()),previous);
 }finally{w.clean();}
});
test('v7 writer rejects canonless option, forged collection owner, and direct QRPE history overwrite',()=>{
 const w=setup();try{
  let r=w.run([{op:'add_option',requirementId:'R0',option:{id:'O',kind:'option',title:'No canon',origin:'situational'}}],1);
  assert.notEqual(r.status,0);assert.match(r.stderr,/canonBlock/);
  assert.equal(w.run(base,1).status,0);
  r=w.run([{op:'add_collection',collection:{id:'bad',title:'Fake owner',anchor:'R0',memberRefs:['R-TECH'],rootRequirementId:'R-OTHER'}}],2);
  assert.notEqual(r.status,0);assert.match(r.stderr,/semantic owner/);
  r=w.run([{op:'update_node',id:'R-C',changes:{history:[]}}],2);
  assert.notEqual(r.status,0);assert.match(r.stderr,/HISTORY_GUARD/);
  assert.equal(w.read().revision,2);
 }finally{w.clean();}
});
test('v7 selected options cannot conflict in one scope; reviewed R can become inactive without rewriting choice',()=>{
 const w=setup();try{
  assert.equal(w.run(base,1).status,0);
  assert.equal(w.run([chosen],2).status,0);
  const previous=w.read().nodes.find(n=>n.id==='D-A').selectionBasis;
  const bad={op:'select_option',optionId:'O-B',driverId:'R-C',
    decision:{id:'D-B',kind:'decision',title:'Контекстный способ',status:'committed'},
    event:{id:'EV-B',type:'decision_selected',decisionId:'D-B',by:'user',note:'Санкционированное изменение не сделано'}}; 
  let r=w.run([bad],3);
  assert.notEqual(r.status,0);assert.match(r.stderr,/CONFLICTING_SELECTED_OPTIONS/);
  r=w.run([{op:'deactivate_requirement',requirementId:'R-TECH',event:{
    id:'EV-DEACT',type:'requirement_deactivated',requirementId:'R-TECH',by:'user',
    note:'В этом изолированном тесте пользователь вывел техническую R из актуального состава'}}],3);
  assert.equal(r.status,0,r.stderr);
  const g=w.read();
  assert.equal(g.nodes.find(n=>n.id==='R-TECH').status,'inactive');
  assert(g.nodes.find(n=>n.id==='R-C').needsReview);
  assert(g.nodes.find(n=>n.id==='D-A').needsReview);
  assert.deepEqual(g.nodes.find(n=>n.id==='D-A').selectionBasis,previous);
  assert.equal(g.nodes.find(n=>n.id==='D-A').status,'committed','review never auto-revokes D');
  assert.equal(g.events.at(-1).previousRequirementSnapshot.status,'active');
 }finally{w.clean();}
});
test('v7 actual child may be reparented with authorized event and archived lineage',()=>{
 const w=setup();try{
  assert.equal(w.run(base,1).status,0);assert.equal(w.run([chosen],2).status,0);
  const adopt=[
   {op:'add_node',node:{id:'D-PARENT',kind:'decision',status:'committed',title:'Другой способ правильного обеспечения'}},
   {op:'add_edge',edge:{id:'E-PARENT',type:'DRIVES',from:'R0',to:'D-PARENT'}},
   {op:'append_event',event:{id:'EV-PARENT',type:'decision_selected',decisionId:'D-PARENT',by:'user',note:'Изолированный тестовый выбор другого способа'}}
  ];
  assert.equal(w.run(adopt,3).status,0);
  const change={op:'reparent_requirement',requirementId:'R1',newDecisionId:'D-PARENT',newParentId:'R0',
    childRole:'subgoal',event:{id:'EV-REPARENT',type:'requirement_reparented',by:'user',
    note:'Изолированная санкционированная корректировка происхождения',requirementId:'R1'}};
  const out=w.run([change],4);assert.equal(out.status,0,out.stderr);
  const g=w.read();
  assert(g.edges.find(x=>x.id==='introduces-D-A-R1').archived);
  assert(g.edges.find(x=>x.id==='reparent-EV-REPARENT'));
  assert.equal(g.events.at(-1).previousEdges[0].from,'D-A');
  assert.equal(g.nodes.find(x=>x.id==='D-A').status,'committed','previous D remains chosen');
 }finally{w.clean();}
});
test('v7 promotes preplanned candidate R from selected option with same identity and QRPE; other branches stay potential',()=>{
 const w=setup();try{
  const candidate=[
   ...base,
   {op:'add_node',node:{id:'R-PREP-A',kind:'requirement',title:'Предварительно проработанная Feature',status:'candidate',
     qrpe:[{id:'QR-CHILD',text:'Достаточно ли определены границы?',status:'open'}]}},
   {op:'add_edge',edge:{id:'POT-A',type:'OUTCOME_OF',from:'O-A',to:'R-PREP-A'}},
   {op:'add_node',node:{id:'R-PREP-B',kind:'requirement',title:'Другая потенциальная R',status:'candidate'}},
   {op:'add_edge',edge:{id:'POT-B',type:'OUTCOME_OF',from:'O-B',to:'R-PREP-B'}},
   {op:'add_collection',collection:{id:'COL-POT',title:'Выборочное разбиение',anchor:'O-A',memberRefs:['R-PREP-A']}}
  ];
  assert.equal(w.run(candidate,1).status,0);
  const accepted=structuredClone(chosen);accepted.children=[
   {candidateRequirementId:'R-PREP-A',role:'subgoal'},
   {role:'method_correctness',requirement:{id:'R-IMPL',kind:'requirement',title:'Корректно реализовать выбранный метод'}}
  ];
  let out=w.run([accepted],2);assert.equal(out.status,0,out.stderr);
  const g=w.read();
  const promoted=g.nodes.filter(n=>n.id==='R-PREP-A');
  assert.equal(promoted.length,1,'R identity must not be duplicated');
  assert.equal(promoted[0].status,'active');
  assert.equal(promoted[0].qrpe[0].id,'QR-CHILD');
  assert.equal(g.edges.find(e=>e.id==='POT-A').archived,true);
  assert.equal(g.edges.find(e=>e.id==='introduces-D-A-R-PREP-A').parent,'R-C');
  assert.equal(g.nodes.find(n=>n.id==='R-PREP-B').status,'candidate');
  assert.equal(g.events[0].promotedCandidateChildren[0].requirementSnapshot.status,'candidate');
  assert(g.collections.some(x=>x.memberRefs.includes('R-PREP-A')));
 }finally{w.clean();}
});
test('v7 refuses promotion of a candidate belonging to an unselected option',()=>{
 const w=setup();try{
  const candidate=[...base,
   {op:'add_node',node:{id:'R-B',kind:'requirement',title:'Option B child',status:'candidate'}},
   {op:'add_edge',edge:{id:'POT-B',type:'OUTCOME_OF',from:'O-B',to:'R-B'}}
  ];
  assert.equal(w.run(candidate,1).status,0);
  const accepted=structuredClone(chosen);accepted.children=[{candidateRequirementId:'R-B',role:'subgoal'}];
  const before=JSON.stringify(w.read());
  const out=w.run([accepted],2);assert.notEqual(out.status,0);assert.match(out.stderr,/another or multiple possible options/);
  assert.equal(JSON.stringify(w.read()),before);
 }finally{w.clean();}
});
