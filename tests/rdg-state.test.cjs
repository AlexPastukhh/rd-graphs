const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),cp=require('node:child_process');
const core=require('../tools/rdg-state.js');
function fixture(){
 const ref={graphSlug:'alpha',fieldId:'deadline'},extra={graphSlug:'alpha',fieldId:'details'};
 const base=id=>({schemaVersion:1,id,identitySpace:'state-test',planningScale:'module',rootRequirementId:'R-'+id,revision:1,title:id,nodes:[{id:'R-'+id,kind:'requirement',title:'Goal'}],edges:[],events:[],contextFieldsComplete:true});
 const a=base('alpha'),b=base('beta');
 a.contextFields=[{id:'deadline',title:'Срок',explanation:'Когда нужен результат',sourceRefs:[{graphSlug:'alpha',sourceId:'theory'}]},{id:'details',title:'Детали',explanation:'Подробности исполнения'}];
 a.knowledgeSources=[{id:'theory',title:'Теория концепта',url:'https://example.org/concept'}];
 a.contextUses=[{fieldRef:ref,purpose:'Оценить варианты'}];
 a.nodes.push({id:'O',kind:'option',title:'Option',origin:'situational',canonBlock:{recommended:[],contraindicated:[]}});
 a.edges.push({id:'o',type:'OPTION_FOR',from:'R-alpha',to:'O'});
 b.contextUses=[{fieldRef:ref,purpose:'Переиспользовать ответ'},{fieldRef:extra,purpose:'Подготовить исполнение',when:{allSelected:[{graphSlug:'alpha',optionId:'O'}]}}];
 a.nodes.push({id:'C',kind:'context',title:'Ранний ответ',contextFieldRef:ref,contextValue:{value:'До декабря',source:'Получено раньше подключения beta',scope:'project'}});
 return {a,b,ref,extra,items:[{slug:'alpha',group:'workspaces',graph:a},{slug:'beta',group:'workspaces',graph:b}]};
}
test('shared owner fixture: earlier answer, theory, several consumers and conditional questions',()=>{
 const f=fixture();assert.equal(core.validate(f.items),true);
 let r=core.collect({items:f.items,graphSlug:'beta'});
 const deadline=r.fields.find(x=>x.fieldRef.fieldId==='deadline'),details=r.fields.find(x=>x.fieldRef.fieldId==='details');
 assert.equal(deadline.answer.value,'До декабря');assert.equal(deadline.question,false);assert.equal(deadline.sources[0].title,'Теория концепта');
 assert.equal(details.state,'later');assert.equal(details.question,false);
 f.a.nodes.push({id:'D',kind:'decision',title:'Chosen',status:'committed',selectedOptionId:'O'});
 r=core.collect({items:f.items,graphSlug:'beta'});
 assert.equal(r.fields.find(x=>x.fieldRef.fieldId==='details').question,true);
 f.a.nodes.at(-1).status='superseded';
 assert.equal(core.collect({items:f.items,graphSlug:'beta'}).fields.find(x=>x.fieldRef.fieldId==='deadline').answer.value,'До декабря');
});
test('definitions/sources update once; same names do not merge; current value stays shared',()=>{
 const f=fixture();f.a.contextFields[1].title='Срок';f.a.contextFields[0].explanation='Единое обновлённое объяснение';
 const one=core.collect({items:f.items,graphSlug:'alpha'}),two=core.collect({items:f.items,graphSlug:'beta'});
 assert.equal(one.fields[0].explanation,two.fields.find(x=>x.fieldRef.fieldId==='deadline').explanation);
 assert.equal(two.fields.length,2);assert.equal(f.a.nodes.find(n=>n.id==='C').contextValue.value,'До декабря');
});
test('negative contract rejects source execution, duplicate answer owners and invalid refs',()=>{
 for(const mutate of [
 f=>f.a.knowledgeSources[0].url='javascript:alert(1)',
 f=>f.a.contextFields.push(structuredClone(f.a.contextFields[0])),
 f=>f.b.nodes.push({...structuredClone(f.a.nodes.find(n=>n.id==='C')),id:'C-copy'}),
 f=>f.b.contextUses[0].fieldRef.fieldId='missing',
 f=>f.b.contextUses[1].when.allSelected[0].optionId='missing']){
 const f=fixture();mutate(f);assert.throws(()=>core.validate(f.items),/CONTEXT_CONTRACT/);
 }
});
test('unknown completeness, more than forty fields, project boundary, scoped value and freeform candidates',()=>{
 const f=fixture();delete f.b.contextFieldsComplete;
 f.b.nodes.push({id:'raw',kind:'context',title:'Свободный ответ'});
 let r=core.collect({items:f.items,graphSlug:'beta'});assert(r.incomplete.length);assert.equal(r.freeformCandidates.length,1);
 f.a.nodes.find(n=>n.id==='C').contextValue.scope='other-branch';
 assert.equal(core.collect({items:f.items,graphSlug:'beta'}).fields.find(x=>x.fieldRef.fieldId==='deadline').answerStatus,'needs-assessment');
 f.a.nodes.find(n=>n.id==='C').contextValue.scope='project';
 f.a.identitySpace='another';assert.throws(()=>core.validate(f.items),/cross-project/);
 f.a.identitySpace='state-test';
 for(let i=0;i<45;i++){f.a.contextFields.push({id:'f'+i,title:'F'+i,explanation:'Meaning'});f.b.contextUses.push({fieldRef:{graphSlug:'alpha',fieldId:'f'+i},purpose:'Use'});}
 assert.equal(core.collect({items:f.items,graphSlug:'beta'}).fields.length,47);
});
test('real writer package replaces current Context value, readback and replay without answer history',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-state-'));
 try{
 fs.mkdirSync(path.join(dir,'tools'));
 for(const f of ['rdg-modules.py','rdg-module-registry.json','rdg-module-test.py','graph-apply.py','graph-package.py','rdg-transaction-io.py','graph-index.py','rdg-catalog.py','rdg-v7-model.py','rdg-context.py','rdg-state.py','rdg-state.js','rdg-state-cli.cjs','rdg-catalog.js'])
 fs.copyFileSync(path.join(__dirname,'../tools',f),path.join(dir,'tools',f));
 const {a,b,ref}=fixture();const p=path.join(dir,'patch.json');
 const run=(v,flags=[])=>{fs.writeFileSync(p,JSON.stringify(v));return cp.spawnSync('python3',[path.join(dir,'tools/graph-apply.py'),'--package','--patch',p,...flags],{encoding:'utf8'});};
 const create={schemaVersion:1,transactionId:'state-create',changes:[{file:'workspaces/alpha/graph.json',create:a},{file:'workspaces/beta/graph.json',create:b}]};
 let r=run(create);assert.equal(r.status,0,r.stderr);
 const patch={schemaVersion:1,transactionId:'state-answer',changes:[{file:'workspaces/alpha/graph.json',patch:{schemaVersion:1,expectedRevision:1,operations:[{op:'set_context_value',contextId:'C',fieldRef:ref,value:{value:'До января',source:'Уточнение',scope:'project'}}]}}]};
 r=run(patch);assert.equal(r.status,0,r.stderr);assert.equal(run(patch).status,0,'replay');
 const graph=JSON.parse(fs.readFileSync(path.join(dir,'graphs/workspaces/alpha/graph.json')));
 assert.equal(graph.nodes.find(n=>n.id==='C').contextValue.value,'До января');assert(!('contextAnswers' in graph.nodes.find(n=>n.id==='C')));
 const bad=structuredClone(patch);bad.transactionId='bad';bad.changes[0].patch.expectedRevision=2;bad.changes[0].patch.operations=[{op:'update_node',id:'C',changes:{title:'Changed'}}];
 assert.notEqual(run(bad).status,0);
 const duplicate=structuredClone(patch);duplicate.transactionId='dup';duplicate.changes[0].patch.expectedRevision=2;duplicate.changes[0].patch.operations[0].contextId='OTHER';
 assert.notEqual(run(duplicate).status,0);
 const incomplete=structuredClone(patch);incomplete.transactionId='missing-value';incomplete.changes[0].patch.expectedRevision=2;
 delete incomplete.changes[0].patch.operations[0].value;
 assert.notEqual(run(incomplete).status,0,'missing value must not silently clear the field');
 const clear=structuredClone(patch);clear.transactionId='clear';clear.changes[0].patch.expectedRevision=2;clear.changes[0].patch.operations[0].value=null;
 r=run(clear);assert.equal(r.status,0,r.stderr);
 const empty=JSON.parse(fs.readFileSync(path.join(dir,'graphs/workspaces/alpha/graph.json')));
 assert.equal(empty.revision,3);assert(!('contextValue' in empty.nodes.find(n=>n.id==='C')));
 const fill=structuredClone(patch);fill.transactionId='refill';fill.changes[0].patch.expectedRevision=3;
 r=run(fill);assert.equal(r.status,0,r.stderr);
 const filled=JSON.parse(fs.readFileSync(path.join(dir,'graphs/workspaces/alpha/graph.json')));
 assert.equal(filled.nodes.find(n=>n.id==='C').contextValue.value,'До января');
 assert.equal(filled.nodes.find(n=>n.id==='C').contextFieldRef.fieldId,'deadline');
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
module.exports={fixture};

test('freeform mapping needs an explicit note; selected D snapshots survive later shared definition changes',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-state-t1-'));
 try{
 fs.mkdirSync(path.join(dir,'tools'));
 for(const f of ['graph-apply.py','graph-package.py','rdg-transaction-io.py','graph-index.py','rdg-catalog.py','rdg-v7-model.py','rdg-context.py','rdg-state.py','rdg-state.js','rdg-state-cli.cjs','rdg-catalog.js'])
 fs.copyFileSync(path.join(__dirname,'../tools',f),path.join(dir,'tools',f));
 const {a,b,ref}=fixture();a.nodes.push({id:'RAW',kind:'context',title:'Unmapped answer'});
 const p=path.join(dir,'patch.json');
 const run=v=>{fs.writeFileSync(p,JSON.stringify(v));return cp.spawnSync('python3',[path.join(dir,'tools/graph-apply.py'),'--package','--patch',p],{encoding:'utf8'});};
 let r=run({schemaVersion:1,transactionId:'create',changes:[{file:'workspaces/alpha/graph.json',create:a},{file:'workspaces/beta/graph.json',create:b}]});assert.equal(r.status,0,r.stderr);
 const patch=(tid,rev,operations)=>({schemaVersion:1,transactionId:tid,changes:[{file:'workspaces/alpha/graph.json',patch:{schemaVersion:1,expectedRevision:rev,operations}}]});
 // Mapping an existing title-only freeform record must also preserve its original text.
 const map={op:'set_context_value',contextId:'RAW',fieldRef:{graphSlug:'alpha',fieldId:'details'},value:{value:'Known detail',source:'Earlier discussion',scope:'project'}};
 assert.notEqual(run(patch('bad-map',1,[map])).status,0);
 map.mappingNote='This earlier answer describes the detail field';
 r=run(patch('map',1,[map]));assert.equal(r.status,0,r.stderr);
 const select={op:'select_option',optionId:'O',driverId:'R-alpha',decision:{id:'D',kind:'decision',title:'Chosen',status:'committed'},event:{id:'choose',type:'decision_selected',decisionId:'D',by:'assistant',note:'Explicit test choice'},children:[]};
 r=run(patch('select',2,[select]));assert.equal(r.status,0,r.stderr);
 const file=path.join(dir,'graphs/workspaces/alpha/graph.json'),chosen=JSON.parse(fs.readFileSync(file));
 const t1=chosen.nodes.find(n=>n.id==='D').selectionBasis.contextSnapshot;assert(t1.fields.some(f=>f.answer?.value==='До декабря'));
 const updated=structuredClone(chosen.contextFields);updated[0].explanation='Updated theory explanation';
 r=run(patch('definition',3,[{op:'set_context_contract',contract:{contextFields:updated}}]));assert.equal(r.status,0,r.stderr);
 assert.deepEqual(JSON.parse(fs.readFileSync(file)).nodes.find(n=>n.id==='D').selectionBasis.contextSnapshot,t1);
 assert.equal(chosen.nodes.find(n=>n.id==='RAW').contextMapping.originalText,'Unmapped answer');
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
