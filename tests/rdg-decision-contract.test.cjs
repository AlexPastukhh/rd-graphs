'use strict';
// Contract/fixture validation plus bounded independent oracles; no production reducer/writer.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const read=name=>JSON.parse(fs.readFileSync(path.join(root,name),'utf8'));
let Ajv;
if(process.env.RDG_AJV_PACKAGE)Ajv=require(process.env.RDG_AJV_PACKAGE);
else {try{Ajv=require('ajv/dist/2020');}catch(error){if(error.code!=='MODULE_NOT_FOUND')throw error;Ajv=require('/opt/dc/node_modules/ajv/dist/2020');}}
Ajv=Ajv.default||Ajv;
const schema=read('tools/contracts/rdg-decision-v1.schema.json');
const refs=read('tools/contracts/rdg-decision-v1.refs.json');
const fixtures=read('tests/fixtures/rdg-decision-v1/contract-cases.json');
const ajv=new Ajv({strict:true,strictRequired:false,allErrors:true});
ajv.addSchema(schema);
const validator=name=>{const v=ajv.getSchema(schema.$id+'#/$defs/'+name);assert(v,'missing definition '+name);return v;};
const valid=(name,value)=>{const v=validator(name);assert(v(value),JSON.stringify(v.errors));};
const seeds=new Map(fixtures.positive.map(v=>[v.id,v]));
const clone=value=>JSON.parse(JSON.stringify(value));

test('policy v2 commands publish typed roles, relation alternatives and lifecycle without a preset step',()=>{
 const policy={id:'P-v2',version:1,name:'Typed policy',description:'Synthetic',status:'active',origin:'user',
  pattern:'roles',sourceKinds:['context'],targetKinds:['decision'],
  roles:[{id:'target',kinds:['decision']},{id:'source',name:'Context source',kinds:['context'],required:false,
   selector:{anchor:'target',relation:['CONTEXT_FOR','DECISION_CONTEXT'],direction:'in',minDepth:1,maxDepth:2}}],
  relations:[],rules:[{id:'R1',name:'Member removed',role:'source',watch:'membership',operations:['removed'],enabled:true}]};
 valid('dependencyPolicy',policy);
 const request={op:'core',transactionId:crypto.randomUUID(),targetPackageId:crypto.randomUUID(),
  expectedPackageRevision:1,expectedGraphRevision:1,expectedDependencyCatalogRevision:0,
  command:'policy_change',note:'Test policy lifecycle',data:{action:'policy_save',value:policy}};
 valid('coreRequest',request);
 for(const action of ['binding_activate','binding_disable','binding_remove','automatic_activate'])
  valid('coreRequest',{...request,data:{action,value:{id:'binding',expectedRevision:2}}});
 assert.equal(validator('coreRequest')({...request,data:{action:'unknown',value:{}}}),false);
});

test('v1 schema is well-formed and compiles with strict Draft 2020 validation',()=>{
 assert.equal(schema.$schema,'https://json-schema.org/draft/2020-12/schema');
 assert.equal(ajv.validateSchema(schema),true,JSON.stringify(ajv.errors));
 for(const name of Object.keys(schema.$defs))validator(name);
 assert.equal(schema.$defs.graph.properties.coreModel.const,fixtures.contractId);
 assert.equal(refs.contractId,fixtures.contractId);
});
for(const item of fixtures.positive)test('contract accepts '+item.id,()=>valid(item.definition,item.value));
test('work-area color is optional for old records and constrained to the shared palette',()=>{
 const base={id:'WG-COLOR',title:'Storage',rootIds:['R1'],memberIds:['R1']};
 valid('workGraph',base);valid('workGraph',{...base,colorKey:'teal'});
 const v=validator('workGraph');assert.equal(v({...base,colorKey:'ultraviolet'}),false);
});
test('work-area history event carries explicit immutable before/after snapshots',()=>{
 const event={id:'evt-work-area',type:'work_graph_changed',transactionId:'123e4567-e89b-42d3-a456-426614174000',
  recordedAt:'2026-11-03T12:00:00Z',by:'assistant',nodeIds:['R1'],basis:'Set area color',
  workGraphChange:{action:'updated',workGraphId:'WG1',title:'Storage',
   before:{title:'Storage',rootIds:['R1'],memberIds:['R1'],colorKey:'blue'},
   after:{title:'Storage',rootIds:['R1'],memberIds:['R1'],colorKey:'teal'}}};
 valid('event',event);
 const invalid=clone(event);invalid.workGraphChange.after.colorKey='ultraviolet';
 const v=validator('event');assert.equal(v(invalid),false);
});
for(const item of fixtures.schemaNegative)test('contract rejects '+item.id,()=>{
 const v=validator(item.definition);assert.equal(v(item.value),false,'unexpectedly accepted '+item.id);assert(v.errors.length);
});

function patch(value,operations=[]){
 const out=clone(value);
 for(const op of operations){
  const parts=op.path.slice(1).split('/').map(v=>v.replace(/~1/g,'/').replace(/~0/g,'~'));
  let parent=out;for(const p of parts.slice(0,-1)){assert(parent&&Object.hasOwn(parent,p),'missing setup parent '+op.path);parent=parent[p];}
  const key=parts.at(-1);
  if(op.op==='remove'){assert(Object.hasOwn(parent,key));if(Array.isArray(parent))parent.splice(Number(key),1);else delete parent[key];}
  else if(op.op==='add'&&Array.isArray(parent)&&key==='-')parent.push(clone(op.value));
  else {if(op.op==='replace')assert(Object.hasOwn(parent,key),'missing replacement '+op.path);parent[key]=clone(op.value);}
 }
 return out;
}
test('expectations have concrete seeds, valid setup/requests, disjoint assertions and real verification owners',()=>{
 const ids=new Set(),axes=new Set();let concrete=0;
 for(const item of fixtures.expectations){
  valid('case',item);assert(!ids.has(item.id));ids.add(item.id);axes.add(item.axis);
  const seed=seeds.get(item.seed);assert(seed,'unknown seed '+item.seed);valid(seed.definition,patch(seed.value,item.setup));
  for(const request of item.requests||item.request&&[item.request]||[]){valid('request',request);concrete++;}
  if(item.view)valid('view',item.view);
  const ex=item.expect;
  assertExpectedReferences(item,patch(seed.value,item.setup));
  for(const [left,right] of [['activeIds','inactiveIds'],['visibleIds','hiddenIds']])assert(!(ex[left]||[]).some(id=>(ex[right]||[]).includes(id)),item.id+' contradicts itself');
  for(const owner of item.verification)assert(fs.existsSync(path.join(root,owner)),'missing verification owner '+owner);
  if(ex.outcome==='reject')for(const key of ['graphWrites','planWrites','layoutWrites'])assert.equal(ex[key],0);
 }
 assert.equal(axes.size,12);assert(concrete>=20);
 for(const id of ['cancel-chain','cancel-shared-source','cancel-last-shared-source','no-rootless-cycle',
  'reselect-does-not-reselect-children','semantic-reconnect-separate','visibility-unselected-not-hidden',
  'visibility-exclusive-only','visibility-nonexclusive','visibility-optional-exclusive','visibility-withdraw-restores',
  'visibility-checkbox-view-only','visibility-overlap','action-multiple-targets-atomic','create-working-area-atomic',
  'plan-first-order-only','plan-alternative-fork','layout-copy-remaps-occurrence-ids',
  'package-edit-live-history-pinned','registry-graph-atomic-recovery','cas-stale-client'])assert(ids.has(id),id);
 assert.deepEqual(fixtures.sequencePolicy,{expectedRevisions:'previous-receipt',transactionIds:'as-stored'});
});
function pick(value,selector){
 let values=[value];
 for(const raw of selector.split('.')){
  const m=raw.match(/^([^\[{]+)(\[\]|\[(?:action|evidence)\]|\{\}|\{key\})?$/);assert(m,'unsupported slot '+selector);
  values=values.flatMap(parent=>{
   const v=parent?.[m[1]];if(v===undefined||v===null)return [];
   if(m[2]==='[]'){assert(Array.isArray(v),selector+' expects array');return v;}
   if(m[2]?.startsWith('[')){assert(Array.isArray(v));return v.filter(x=>x.kind===m[2].slice(1,-1));}
   if(m[2]==='{}'){assert(!Array.isArray(v)&&typeof v==='object');return Object.values(v);}
   if(m[2]==='{key}')return Object.keys(v);
   return [v];
  });
 }
 return values;
}
test('the typed reference inventory resolves all strict current Graph slots in positive fixtures',()=>{
 const paths=new Set();
 for(const slot of refs.slots){assert(!paths.has(slot.path),'duplicate slot '+slot.path);paths.add(slot.path);assert(['current','observed','historical'].includes(slot.mode));assert(slot.missing&&slot.copy);}
 for(const item of fixtures.positive.filter(x=>x.definition==='graph')){
  const context={graph:item.value},defined={};
  for(const [ns,slots] of Object.entries(refs.definitionNamespaces)){
   const values=slots.filter(s=>s.startsWith('graph.')).flatMap(s=>pick(context,s));
   assert.equal(new Set(values).size,values.length,item.id+' duplicated '+ns);defined[ns]=new Set(values);
  }
  for(const slot of refs.slots.filter(s=>s.path.startsWith('graph.')&&s.mode==='current'&&s.missing==='reject'))
   for(const value of pick(context,slot.path))assert(defined[slot.namespace].has(value),slot.path+' unresolved '+value);
 }
 assert(refs.slots.some(s=>s.path==='graph.externalActions[].targetIds[]'));
 assert(refs.slots.some(s=>s.path==='registry.packages[].rules[].anchor'&&s.missing==='inactive-rule'));
 assert(refs.slots.some(s=>s.path==='graph.events[].placementIds[]'&&s.mode==='historical'));
});

// The fixture's declared IDs must exist even when its behavior has no executable runtime yet.
function assertExpectedReferences(item,value){
 const ids=new Set(),entities=new Map(),groups=new Map();
 function collect(v){if(!v||typeof v!=='object')return;if(typeof v.id==='string')ids.add(v.id);for(const child of Object.values(v))if(typeof child==='object')collect(child);}
 collect(value);
 for(const n of [...(value.nodes||[]),...(value.objects||[]),...(value.externalActions||[])])entities.set(n.id,n);
 for(const g of value.decisionGroups||[])groups.set(g.id,g);
 for(const q of item.requests||item.request&&[item.request]||[]){
  if(q.command==='add'){collect(q.data.entity);entities.set(q.data.entity.id,q.data.entity);collect(q.data.initialRelations);}
 }
 const ex=item.expect;
 for(const key of ['activeIds','inactiveIds','visibleIds','hiddenIds','unselectedIds','preservedIds'])
  for(const id of ex[key]||[]){assert(ids.has(id),item.id+': unknown expected '+key+' '+id);if(key!=='preservedIds')assert(entities.has(id),item.id+': expected entity '+id);if(key==='unselectedIds')assert.equal(entities.get(id).kind,'decision');}
 for(const id of ex.conflictingGroupIds||[])assert(groups.has(id),item.id+': unknown conflicting group '+id);
 for(const mask of ex.groupVisibility||[]){
  const g=groups.get(mask.groupId);assert(g,item.id+': unknown visibility group '+mask.groupId);
  const members=new Set(g.members.map(m=>m.decisionId));
  for(const id of [...mask.visibleIds,...mask.hiddenIds])assert(members.has(id),item.id+': visibility ID outside group '+id);
  assert(!mask.visibleIds.some(id=>mask.hiddenIds.includes(id)),item.id+': contradictory group mask');
  assert.deepEqual([...mask.visibleIds,...mask.hiddenIds].sort(),[...members].sort(),item.id+': incomplete group mask');
 }
}
test('fixture integrity rejects the previously undetected non-existent expected ID',()=>{
 const c=clone(fixtures.expectations.find(x=>x.id==='cancel-chain'));
 c.expect.activeIds=['D-does-not-exist'];
 assert.throws(()=>assertExpectedReferences(c,patch(seeds.get(c.seed).value,c.setup)),/unknown expected activeIds/);
 const overlap=clone(fixtures.expectations.find(x=>x.id==='visibility-overlap'));
 overlap.expect.groupVisibility[0].visibleIds=['D-does-not-exist'];
 assert.throws(()=>assertExpectedReferences(overlap,seeds.get(overlap.seed).value),/visibility ID outside group/);
});

function checkedCompletion(context){
 valid('completionContext',context);
 assert.equal(context.entity.id,context.request.data.nodeId,'completion target differs from snapshot');
 if(context.decisionTargets){
  assert.deepEqual(context.decisionTargets.map(n=>n.id).sort(),[...context.entity.targetIds].sort(),'resolved selection targets differ');
  assert.equal(new Set(context.decisionTargets.map(n=>n.id)).size,context.decisionTargets.length,'duplicate resolved target');
 }
}
test('actual acceptance outcome comes from complete, targets from the authoritative snapshot',()=>{
 for(const id of ['complete-acceptance-selected','complete-acceptance-unselected'])checkedCompletion(clone(seeds.get(id).value));
 const c=clone(seeds.get('complete-acceptance-selected').value);
 c.entity.id='A-other';assert.throws(()=>checkedCompletion(c),/differs from snapshot/);
 c.entity.id=c.request.data.nodeId;c.decisionTargets[0].id='D1';assert.throws(()=>checkedCompletion(c),/resolved selection targets differ/);
 const select=clone(seeds.get('complete-acceptance-selected').value);
 select.entity.actionType='select_decision';delete select.request.data.decisionOutcome;checkedCompletion(select);
 select.request.data.decisionOutcome='unselected';assert.equal(validator('completionContext')(select),false);
 for(const kind of ['requirement','decision']){
  const entity=clone(seeds.get('graph-chain').value.nodes.find(n=>n.kind===kind));
  const c={entity,request:clone(seeds.get('request-complete').value)};c.request.data.nodeId=entity.id;
  checkedCompletion(c);c.request.data.decisionOutcome='selected';assert.equal(validator('completionContext')(c),false);
 }
});

// Bounded support/group oracle: equations independent of any future mutation engine.
function activeSet(g){
 const nodes=new Map(g.nodes.map(n=>[n.id,n]));
 const arcs=g.edges.filter(e=>refs.composition.includes(e.type)).map(e=>[e.from,e.to]);
 arcs.push(...g.decisionGroups.flatMap(x=>x.members.map(m=>[x.parentId,m.decisionId])));
 const active=new Set(g.rootCauses.filter(c=>c.enabled).map(c=>c.requirementId));
 for(let prior=-1;prior!==active.size;){prior=active.size;for(const [a,b] of arcs)if(active.has(a)&&nodes.has(b)){
  const n=nodes.get(b);if(n.kind!=='decision'||n.selectionState==='selected')active.add(b);
 }}return active;
}
function conflicts(g,id){
 const nodes=new Map(g.nodes.map(n=>[n.id,n]));
 return g.decisionGroups.filter(x=>x.mutuallyExclusive&&x.members.some(m=>m.decisionId===id)&&x.members.some(m=>m.decisionId!==id&&nodes.get(m.decisionId).selectionState==='selected')).map(x=>x.id).sort();
}
function groupMask(g,group,show){
 const nodes=new Map(g.nodes.map(n=>[n.id,n])),members=group.members.map(m=>m.decisionId);
 const selected=members.filter(id=>nodes.get(id).selectionState==='selected');
 const hiddenIds=group.mutuallyExclusive&&selected.length&&!show?members.filter(id=>!selected.includes(id)):[];
 return {groupId:group.id,visibleIds:members.filter(id=>!hiddenIds.includes(id)).sort(),hiddenIds:hiddenIds.sort()};
}
function oracleRequest(g,q){
 const before=activeSet(g),byId=new Map(g.nodes.map(n=>[n.id,n]));
 if(q.op==='unlink')g.edges=g.edges.filter(e=>e.id!==q.data.edgeId);
 else if(q.command==='withdraw')byId.get(q.data.nodeId).selectionState='unselected';
 else if(q.command==='select'){
  if(conflicts(g,q.data.nodeId).length)return 'DECISION_GROUP_CONFLICT';
  byId.get(q.data.nodeId).selectionState='selected';
 }else if(q.command==='link')g.edges.push(clone(q.data.relation));
 else throw Error('oracle command outside bounded scope');
 while(true){const now=activeSet(g),cancel=[...before].filter(id=>!now.has(id)&&byId.get(id)?.kind==='decision'&&byId.get(id).selectionState==='selected');if(!cancel.length)break;for(const id of cancel)byId.get(id).selectionState='unselected';}
 return null;
}
const oracleCases=fixtures.expectations.filter(c=>['activity','visibility','commands'].includes(c.axis)&&seeds.get(c.seed)?.definition==='graph'&&
 (c.requests||c.request&&[c.request]||[]).every(q=>q.op==='unlink'||['withdraw','select','link'].includes(q.command))&&
 ['activeIds','inactiveIds','unselectedIds','visibleIds','hiddenIds','groupVisibility','conflictingGroupIds'].some(k=>c.expect[k]));
for(const c of oracleCases)test('bounded support/group oracle: '+c.id,()=>{
 const graph=patch(seeds.get(c.seed).value,c.setup);let error=null;
 for(const q of c.requests||c.request&&[c.request]||[]){error=oracleRequest(graph,q);if(error)break;}
 const ex=c.expect;
 if(ex.outcome==='reject'){assert.equal(error,ex.errorCode);}
 else {
  assert.equal(error,null);const active=activeSet(graph);
  for(const id of ex.activeIds||[])assert(active.has(id),c.id+' inactive '+id);
  for(const id of ex.inactiveIds||[])assert(!active.has(id),c.id+' active '+id);
  for(const id of ex.unselectedIds||[])assert.equal(graph.nodes.find(n=>n.id===id).selectionState,'unselected');
  if(c.axis==='visibility'){
   const show=c.view?.showExcludedAlternatives||false;
   for(const mask of ex.groupVisibility||[])assert.deepEqual(groupMask(graph,graph.decisionGroups.find(g=>g.id===mask.groupId),show),{...mask,visibleIds:[...mask.visibleIds].sort(),hiddenIds:[...mask.hiddenIds].sort()});
   if(ex.visibleIds||ex.hiddenIds){const mask=groupMask(graph,graph.decisionGroups.find(g=>g.id==='G1'),show);for(const id of ex.visibleIds||[])assert(mask.visibleIds.includes(id));for(const id of ex.hiddenIds||[])assert(mask.hiddenIds.includes(id));}
  }
 }
 if(ex.conflictingGroupIds)assert.deepEqual(conflicts(graph,'D3'),[...ex.conflictingGroupIds].sort());
});

function initialRelationError(g,q){
 const data=q.data,entity=data.entity,byId=new Map([...g.nodes,...g.objects].map(n=>[n.id,n]));
 const entityIds=new Set([...byId.keys(),...g.externalActions.map(n=>n.id)]);
 const existingRelations=new Set([...g.edges.map(e=>e.id),...g.decisionGroups.flatMap(x=>x.members.map(m=>m.id))]);
 if(entityIds.has(entity.id))return 'ENTITY_ID_CONFLICT';
 byId.set(entity.id,entity);const relationIds=new Set();
 for(const e of data.initialRelations||[]){
  if(existingRelations.has(e.id)||relationIds.has(e.id))return 'ENTITY_ID_CONFLICT';relationIds.add(e.id);
  if(!byId.has(e.from)||!byId.has(e.to))return 'REFERENCE_MISSING';
  if(e.from===e.to||![e.from,e.to].includes(entity.id))return 'INITIAL_RELATION_UNRELATED';
  const p=refs.relationPairs[e.type],a=byId.get(e.from).kind,b=byId.get(e.to).kind;
  if(!p||!p.from.includes(a)||!p.to.includes(b)||refs.forbiddenEndpointPairs.some(([x,y])=>a===x&&b===y))return 'RELATION_ENDPOINT_TYPES';
 }
 return null;
}
test('connected add has one request and rejects partial or invalid initial composition',()=>{
 const graph=seeds.get('graph-chain').value;
 for(const id of ['request-add-connected-action','request-add-connected-requirement'])assert.equal(initialRelationError(graph,seeds.get(id).value),null);
 for(const c of fixtures.expectations.filter(c=>c.id.startsWith('create-connected-')&&c.axis==='commands'))assert.equal(initialRelationError(graph,c.request),c.expect.errorCode,c.id);
 const q=clone(seeds.get('request-add-connected-action').value);q.data.initialRelations[0].to='D3';q.data.entity=clone(graph.nodes[1]);q.data.entity.id='D-new';q.data.initialRelations[0].from='D-new';
 assert.equal(initialRelationError(graph,q),'RELATION_ENDPOINT_TYPES');
 const r=clone(seeds.get('request-add-connected-requirement').value);r.data.initialRelations[0].type='DERIVES';r.data.initialRelations[0].from='R0';assert.equal(initialRelationError(graph,r),null);
 const a=clone(seeds.get('request-add-connected-action').value);a.data.initialRelations[0].from='R0';assert.equal(initialRelationError(graph,a),null);
});

test('typed selectors traverse object maps, array filters and every qualified instance component',()=>{
 const sample={layouts:{layouts:{process:{positions:{R1:{x:1,y:2}},occurrences:{'occ-1':{entityId:'D1',parentId:'R0',viaEdgeId:'M-G1-D1'}}}}},graph:seeds.get('graph-chain').value,registry:seeds.get('registry-qualified-instances').value};
 for(const [selector,expected] of [['layouts.layouts{key}',['process']],['layouts.layouts{}.positions{key}',['R1']],['layouts.layouts{}.occurrences{}.entityId',['D1']],['graph.nodes[action].id',['A1']],['graph.objects[evidence].id',['EV1']]])assert.deepEqual(pick(sample,selector),expected);
 for(const p of ['registry.packages[].instance.graphBinding','registry.packages[].instance.sourceDefinition','registry.packages[].instance.memberIds[]','registry.packages[].instance.rootIds[]'])assert(refs.slots.some(s=>s.path===p),p);
 const bindings=pick(sample,'registry.packages[].instance.graphBinding');assert.equal(bindings.length,2);assert.notDeepEqual(bindings[0],bindings[1]);
 assert.equal(refs.slots.find(s=>s.path==='graph.recommendationPackageIds[]').copy,'preserve-shared-fork-owned-instance');
});

const sameGraph=(a,b)=>a.packageId===b.packageId&&a.identitySpace===b.identitySpace;
// A test-only reference interpreter for the declared transfer policy, not the reuse factory.
function transferDefinitions(v){
 const packages=clone(v.packages),source=JSON.stringify(packages),ids=[];let localPackage,foreignPackage=null;
 for(const p of packages){
  if(!p.instance){ids.push(p.id);continue;}
  const instance=p.instance;
  if(!sameGraph(instance.graphBinding,v.source)){
   if(v.mode==='template')throw Error('FOREIGN_TEMPLATE_ANCHOR');
   ids.push(p.id);foreignPackage=p;continue;
  }
  for(const rule of p.rules)if(rule.anchor&&!sameGraph(rule.anchor,v.source)&&v.mode==='template')throw Error('FOREIGN_TEMPLATE_ANCHOR');
  const oldId=p.id;assert(v.definitionMap[oldId]&&v.sourceHashes[oldId]);
  const artifact=v.sourceArtifacts[oldId];assert.equal(crypto.createHash('sha256').update(artifact).digest('hex'),v.sourceHashes[oldId],'source definition hash mismatch');
  assert.deepEqual(JSON.parse(artifact),v.packages.find(x=>x.id===oldId),'source artifact differs from definition');
  p.id=v.definitionMap[oldId];p.revision=1;p.supplied=false;
  instance.sourceDefinition={packageId:oldId,revision:v.packages.find(x=>x.id===oldId).revision,sha256:v.sourceHashes[oldId]};
  instance.graphBinding=clone(v.target);
  const mapped=id=>{assert(v.entityMap[id],'missing remap '+id);return v.entityMap[id];};
  for(const key of ['memberIds','rootIds'])instance[key]=instance[key].map(mapped);
  for(const rule of p.rules)if(rule.anchor&&sameGraph(rule.anchor,v.source))rule.anchor={...v.target,nodeId:mapped(rule.anchor.nodeId)};
  ids.push(p.id);localPackage=p;
 }
 assert.equal(JSON.stringify(v.packages),source,'source bytes changed');
 return {connectionIds:ids,localPackage,foreignPackage};
}
for(const vector of fixtures.transferVectors)test('qualified transfer golden vector: '+vector.id,()=>{
 for(const p of vector.packages)valid('recommendationPackage',p);
 if(vector.expect.errorCode)assert.throws(()=>transferDefinitions(vector),new RegExp(vector.expect.errorCode));
 else {const actual=transferDefinitions(vector);assert.deepEqual(actual,vector.expect);valid('recommendationPackage',actual.localPackage);assert(!actual.localPackage.instance.rootIds.includes('R0'));}
});
test('same short ID never matches another Graph binding; repeated inserts are independent',()=>{
 const [copy,first,again]=fixtures.transferVectors;assert.notEqual(first.expect.localPackage.id,again.expect.localPackage.id);
 assert.notDeepEqual(first.expect.localPackage.instance.memberIds,again.expect.localPackage.instance.memberIds);
 const foreign=copy.expect.foreignPackage.instance.graphBinding;
 assert(!sameGraph(foreign,copy.source));assert(!sameGraph({...copy.source,identitySpace:foreign.identitySpace},copy.source));
 assert.deepEqual(transferDefinitions(copy).foreignPackage,copy.packages[2]);
 const empty=clone(first);empty.packages[1].instance.memberIds=[];empty.packages[1].instance.rootIds=[];
 const emptySource=empty.packages[1].id,emptyArtifact=JSON.stringify(empty.packages[1]);
 empty.sourceArtifacts[emptySource]=emptyArtifact;empty.sourceHashes[emptySource]=crypto.createHash('sha256').update(emptyArtifact).digest('hex');
 assert.deepEqual(transferDefinitions(empty).localPackage.instance.rootIds,[]);
 const bad=clone(first);bad.sourceHashes[first.packages[1].id]='0'.repeat(64);
 assert.throws(()=>transferDefinitions(bad),/source definition hash mismatch/);
});
test('composition endpoints cannot introduce D to D, external mandatory Actions or a duplicate membership owner',()=>{
 const pairs=refs.relationPairs;
 assert(refs.forbiddenEndpointPairs.some(([a,b])=>a==='decision'&&b==='decision'));
 assert.deepEqual(pairs.DECISION_MEMBER,{from:['requirement'],to:['decision']});
 assert.deepEqual(pairs.REQUIRES_ACTION,{from:['requirement','decision'],to:['action']});
 for(const type of refs.composition)assert(!(pairs[type].from.includes('decision')&&pairs[type].to.includes('decision')));
 for(const item of fixtures.positive.filter(x=>x.definition==='graph')){
  const graph=item.value,byId=new Map([...graph.nodes,...graph.objects].map(n=>[n.id,n]));
  for(const edge of graph.edges){const p=pairs[edge.type],from=byId.get(edge.from)?.kind,to=byId.get(edge.to)?.kind;assert(p.from.includes(from));assert(p.to.includes(to));assert(!refs.forbiddenEndpointPairs.some(([a,b])=>a===from&&b===to));}
  assert(!graph.edges.some(e=>e.type==='DECISION_MEMBER'));
  for(const group of graph.decisionGroups){assert.equal(byId.get(group.parentId).kind,'requirement');for(const m of group.members)assert.equal(byId.get(m.decisionId).kind,'decision');}
 }
});
test('Plan fixtures place an undated first step and preserve a separately anchored alternative fork',()=>{
 for(const id of ['plan-first-undated','plan-branches']){
  const plan=seeds.get(id).value,ids=plan.steps.map(s=>s.id),placed=[...plan.mainStepIds,...plan.forks.flatMap(f=>f.cases.flatMap(c=>c.stepIds))];
  assert.equal(new Set(placed).size,placed.length);assert.deepEqual([...ids].sort(),[...placed].sort());assert.deepEqual(plan.timeConstraints,[]);
  for(const f of plan.forks)assert(f.afterStepId===null||plan.mainStepIds.includes(f.afterStepId));
 }
 assert.equal(seeds.get('plan-first-undated').value.steps[0].kind,'decision');
});
test('typed input binding pins its canonical payload and distinguishes namespace registry owners',()=>{
 const binding=clone(seeds.get('typed-input-binding').value),expected=binding.sha256;delete binding.sha256;
 const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])])):value;
 assert.equal(crypto.createHash('sha256').update(JSON.stringify(canonical(binding))).digest('hex'),expected);
 valid('ownerPin',{kind:'recommendationRegistry',namespaceId:binding.namespaceId,revision:1,sha256:'e'.repeat(64)});
});
function occurrenceId(space,anchor,route,target){
 const namespace=Buffer.from(space.replaceAll('-',''),'hex');
 const h=crypto.createHash('sha1').update(namespace).update(JSON.stringify([anchor,route,target])).digest().subarray(0,16);
 h[6]=(h[6]&15)|80;h[8]=(h[8]&63)|128;
 const x=h.toString('hex');return 'occ-'+[x.slice(0,8),x.slice(8,12),x.slice(12,16),x.slice(16,20),x.slice(20)].join('-');
}
test('UUIDv5 occurrence contract vectors survive deterministic replay and distinguish a copied namespace/path',()=>{
 for(const v of fixtures.occurrenceVectors)assert.equal(occurrenceId(v.identitySpace,v.anchor,v.path,v.entityId),v.expectedId);
 assert.notEqual(fixtures.occurrenceVectors[0].expectedId,fixtures.occurrenceVectors[1].expectedId);
 const layout=require('../tools/rdg-layout-core.js'),g=seeds.get('graph-chain').value;
 assert.equal(layout.graphKey(g.identitySpace,g.id),JSON.stringify([g.identitySpace,g.id]));
});
test('lock lifecycle events and typed Decision binding match the published schema',()=>{
 const event=clone(seeds.get('acceptance-result-event').value);
 delete event.operationActionId;delete event.actionResult;
 for(const type of ['lock_set','lock_removed'])valid('event',{...event,type});
 valid('inputBinding',clone(seeds.get('typed-input-binding').value));
});


test('B02A file schema and kernel agree on legacy and structured theory shapes',()=>{
 const base={id:'CAN-THEORY',kind:'canon',title:'Theory',description:'',revision:1,guidance:'Old general'};
 const error={id:'local',title:'Assuming capacity',description:''};
 const cases=[base,{...base,guidance:'',canons:'Mixed suitability'},{...base,guidance:'',knownErrors:[error]},
  {...base,guidance:''},{...base,guidance:' ',canons:' '},{...base,guidance:null},
  {...base,canons:2},{...base,knownErrors:null},{...base,knownErrors:[{...error,title:' '}]},
  {...base,knownErrors:[{...error,description:null}]},{...base,knownErrors:[{...error,extra:true}]},
  {...base,knownErrors:[error,error]}];
 const actual=JSON.parse(require('node:child_process').execFileSync('python3',['-B','-c',`
import json,sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
m=SourceFileLoader('theory_schema_parity',str(Path.cwd()/'tools/rdg-decision-model.py')).load_module()
out=[]
for node in json.load(sys.stdin):
 try:m._validate_entity(node,'canon',{});out.append(True)
 except ValueError:out.append(False)
print(json.dumps(out))
 `],{cwd:root,input:JSON.stringify(cases),encoding:'utf8',env:{...process.env,PYTHONWARNINGS:'ignore'}}));
 assert.deepEqual(cases.map(v=>!!validator('canon')(v)),actual);
 assert.deepEqual(actual,[true,true,true,false,false,false,false,false,false,false,false,false]);
 const request={op:'core',transactionId:crypto.randomUUID(),targetPackageId:crypto.randomUUID(),expectedPackageRevision:1,expectedGraphRevision:1,command:'edit',note:'Explicit clear, validated against current entity by kernel',data:{nodeId:base.id,changes:{guidance:'',canons:'Retained',knownErrors:[]},cosmetic:false}};
 valid('coreRequest',request);
 assert.equal(validator('coreRequest')({...request,data:{...request.data,changes:{knownErrors:[{...error,title:''}]}}}),false);
});

test('Planning Meta Action uses ordinary task fields and shared qualified subjects',()=>{
 const ref={schemaVersion:1,kind:'process',packageId:crypto.randomUUID(),identitySpace:crypto.randomUUID(),graphRevision:1,sha256:'a'.repeat(64)};
 const req={op:'plan_action',transactionId:crypto.randomUUID(),targetPackageId:ref.packageId,expectedPackageRevision:1,expectedGraphRevision:1,expectedPlanRevision:null,note:'Explicit work',entity:{kind:'action',actionType:'task',lowLevel:false,title:'Review the process',description:'',subjectRefs:[ref],resultCondition:'Useful conclusions'},placement:{afterStepId:null}};
 valid('request',req);assert.equal(validator('request')({...req,entity:{...req.entity,workflow:{targetRefs:[]}}}),false);
 assert.equal(validator('request')({...req,entity:{...req.entity,actionType:'select_decision'}}),false);
});
