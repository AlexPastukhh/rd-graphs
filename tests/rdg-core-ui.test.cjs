'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {spawnSync}=require('node:child_process'),UI=require('../tools/rdg-workflow-ui.js');
function scenario(){
 const code="from importlib.machinery import SourceFileLoader;import json;"+
  "x=SourceFileLoader('core_view_probe',__import__('sys').argv[1]).load_module();"+
  "s=x.Core();s.setUp();s.shared();s.qualify_output();"+
  "print(json.dumps({'graph':s.g,'views':{i:x.M.focused_view(s.g,i) for i in x.M.entities(s.g)}}))";
 const r=spawnSync('python3',['-c',code,path.join(__dirname,'rdg-core-model.test.py')],{encoding:'utf8'});
 assert.equal(r.status,0,r.stderr);return JSON.parse(r.stdout);
}
test('frontend and canonical core agree on every focus, origins and terminal boundary',()=>{
 const {graph,views}=scenario();
 for(const [id,expected] of Object.entries(views)){
  const actual=UI.coreFocusedView(graph,id);
  assert.deepEqual(actual.entities.map(n=>n.id).sort(),expected.entities.map(n=>n.id).sort(),id);
  assert.deepEqual(actual.terminalIds.sort(),expected.terminalIds.sort(),id);
  assert.deepEqual(actual.edges.map(e=>e.id).sort(),expected.edges.map(e=>e.id).sort(),id);
  assert.deepEqual(actual.origins.map(e=>e.id).sort(),expected.origins.map(e=>e.id).sort(),id);
  assert.deepEqual(actual.originDetails,expected.originDetails,id);
 }
});
test('qualified output blocks no diagram boundary and its role is visible',()=>{
 const {graph}=scenario(),parent=UI.coreFocusedView(graph,'R1'),child=UI.coreFocusedView(graph,'OUT');
 assert(!parent.entities.some(n=>n.id==='OUT'));assert(!child.entities.some(n=>n.id==='R2'));
 assert.deepEqual(child.originDetails[0].requirementIds,['R1']);
 const {container,ui}=mounted();ui.focus('OUT');
 assert(container.textContent.includes('Подцель через Action для:'));
});
test('Plan inventory does not hide stale previously confirmed work as completed',()=>{
 const {graph}=scenario(),file='workspaces/core/graph.json';
 const states={};for(const n of graph.nodes)states[n.id]={complete:false,eventId:'historical',reviewRequired:true,previouslyConfirmed:true};
 const v={sources:{graphs:{[file]:graph},completion:{[file]:states},plan:{steps:[],sequence:[],timeConstraints:[]}},future:[]};
 const result=UI.planningInventory(v);
 assert.equal(result.completedCount,0);assert(result.needsVerification.some(n=>n.nodeId==='R1'));
 assert.equal(UI.historyKind('requirement_falsified').group,'state');
 assert.equal(UI.historyKind('core_review_confirmed').group,'state');
});
function documentFixture(){
 function element(tag){
  let own='';const attrs={};
  const n={tag,tagName:tag.toUpperCase(),children:[],value:'',checked:false,style:{},hidden:false,disabled:false,
   appendChild(child){child.parentElement=n;n.children.push(child);if(n.tag==='select'&&!n.value&&child.tag==='option')n.value=child.value||'';return child;},
   replaceChildren(...children){n.children=children;},setAttribute(k,v){attrs[k]=String(v);},getAttribute(k){return attrs[k];},
   get textContent(){return own+n.children.map(c=>c.textContent).join('');},set textContent(v){own=String(v);n.children=[];},
   get ownText(){return own;},attrs};
  let selectedValue=n.value;Object.defineProperty(n,'value',{get(){return selectedValue;},set(v){selectedValue=v;if(tag==='option'&&n.parentElement?.tag==='select'&&!n.parentElement.value)n.parentElement.value=v;}});
  return n;
 }
 return {createElement:element,createElementNS:(_,tag)=>element(tag)};
}
function walk(n){return [n,...n.children.flatMap(walk)];}
function field(container,label){const row=walk(container).find(n=>n.tag==='label'&&n.ownText===label);assert(row,'field: '+label);return row.children[0];}
function mounted(){const {graph}=scenario(),d=documentFixture(),container=d.createElement('main'),requests=[];
 const ui=UI.mountCore(container,graph,{document:d,focusId:'A',onCommand:async req=>{requests.push(req);return {saved:true};}});
 // Native selects choose the first option automatically; emulate it where a mock has no platform behavior.
 for(const n of walk(container))if(n.tag==='select'&&!n.value&&n.children.length)n.value=n.children[0].value;
 return {graph,d,container,requests,ui};}
test('core component navigates its actual terminal and builds version-pinned review requests',async()=>{
 const {container,requests,graph,ui}=mounted();
 assert(ui.projection().terminalIds.includes('OUT'));ui.focus('OUT');assert.equal(ui.projection().focusId,'OUT');
 assert(ui.projection().origins.some(e=>e.from==='A'));
 const command=field(container,'Действие');command.value='review';command.onchange();
 field(container,'Основание действия / результат проверки').value='Reviewed current declaration and all actual inputs';
 const submit=walk(container).find(n=>n.tag==='button'&&n.textContent==='Записать и перечитать');await submit.onclick();
 assert.equal(requests.length,1);const req=requests[0];
 assert.equal(req.action,'core_review');assert.equal(req.expectedGraphRevision,graph.revision);
 assert.deepEqual(req.data.nodeIds,['OUT']);assert.equal(req.data.observed.A,graph.nodes.find(n=>n.id==='A').revision);
});
test('core editor constructs comment-only canon without hidden working references',async()=>{
 const {container,requests}=mounted(),command=field(container,'Действие');command.value='add';command.onchange();
 const kind=field(container,'Роль блока');kind.value='canon';kind.onchange();
 field(container,'Смысловой заголовок').value='External transfer needs review';
 field(container,'Подробное описание').value='The Canon comment remains human-readable';
 field(container,'Комментарий к применимости Action').value='Содержательный комментарий без программного veto';
 field(container,'Основание действия / результат проверки').value='Explicit comment-only Canon';
 await walk(container).find(n=>n.tag==='button'&&n.textContent==='Записать и перечитать').onclick();
 const entity=requests[0].data.entity;assert.equal(entity.kind,'canon');
 assert.equal(entity.evaluationMode,'comment-only-v1');assert.equal(entity.comment,'Содержательный комментарий без программного veto');
 assert.deepEqual(entity.arguments,[]);assert(!JSON.stringify(entity).includes('graphFile'));
});
test('manual core editor records output origin as metadata without adding DERIVES',async()=>{
 const {container,requests}=mounted(),command=field(container,'Действие');
 command.value='output_origin';command.onchange();
 field(container,'Исходные R: ID через запятую').value='R2';
 field(container,'Основание действия / результат проверки').value='The output now contributes only to R2';
 await walk(container).find(n=>n.tag==='button'&&n.textContent==='Записать и перечитать').onclick();
 assert.equal(requests.length,1);assert.equal(requests[0].action,'core_output_origin');
 assert.deepEqual(requests[0].data.origin,{role:'subgoal',requirementIds:['R2']});
 assert(!JSON.stringify(requests[0].data).includes('DERIVES'));
});
test('manual necessity change sends linked, confirmed decision Action rather than an ungrounded inactive state',async()=>{
 const code="from importlib.machinery import SourceFileLoader;import json;"+
  "s=SourceFileLoader('need_fixture',__import__('sys').argv[1]).load_module().Core();s.setUp();"+
  "s.add('CHECK','action',description='Check necessity');s.edge('DRIVES','R1','CHECK');"+
  "s.review();s.do('select',nodeId='CHECK');s.do('complete',nodeId='CHECK');"+
  "print(json.dumps(s.g))";
 const result=spawnSync('python3',['-c',code,path.join(__dirname,'rdg-core-model.test.py')],{encoding:'utf8'});
 assert.equal(result.status,0,result.stderr);
 const graph=JSON.parse(result.stdout),d=documentFixture(),container=d.createElement('main'),requests=[];
 UI.mountCore(container,graph,{document:d,focusId:'R1',onCommand:async req=>{requests.push(req);return {saved:true};}});
 const cmd=field(container,'Действие');cmd.value='requirement_state';cmd.onchange();
 const state=field(container,'Необходимость R'),decision=field(container,'Подтверждённый Action решения о ненужности');
 assert.equal(decision.parentElement.hidden,true);
 state.value='inactive';state.onchange();
 assert.equal(decision.parentElement.hidden,false);
 assert.equal(decision.value,'CHECK');
 field(container,'Основание и последствия для общей работы').value='Confirmed by actual decision Action';
 field(container,'Основание действия / результат проверки').value='Necessity verified';
 await walk(container).find(n=>n.tag==='button'&&n.textContent==='Записать и перечитать').onclick();
 assert.equal(requests.length,1);assert.equal(requests[0].action,'core_requirement_state');
 assert.equal(requests[0].data.decisionActionId,'CHECK');
 assert.equal(requests[0].data.state,'inactive');
});

test('text-only recommendations refer to whole graph or exact R/A/Canon without applying a Lens',async()=>{
 const {container,requests,graph,ui}=mounted();
 graph.lensRecommendations=[
  {lensKey:'review',text:'Inspect Action canon before select.',targetId:'A'},
  {lensKey:'clarify',text:'Clarify the whole work scope.'}
 ];
 ui.focus('A');assert(container.textContent.includes('Inspect Action canon before select.'));
 ui.focus('R1');assert(!container.textContent.includes('Inspect Action canon before select.'));
 assert(container.textContent.includes('Clarify the whole work scope.'));
 const cmd=field(container,'Действие');cmd.value='lens_recommendations';cmd.onchange();
 field(container,'Ключ рекомендуемой линзы (из каталога)').value='shape';
 field(container,'Когда и для чего её использовать').value='Before splitting this R into technical blocks.';
 field(container,'Основание действия / результат проверки').value='Text-only advice for the current graph';
 await walk(container).find(n=>n.tag==='button'&&n.textContent==='Записать и перечитать').onclick();
 assert.equal(requests.length,1);assert.equal(requests[0].action,'core_lens_recommendations');
 assert.deepEqual(requests[0].data.recommendations.at(-1),{
  lensKey:'shape',text:'Before splitting this R into technical blocks.',targetId:'R1'});
 assert.equal(graph.events.some(e=>e.type==='action_selected'),false);
});

if(process.env.RDG_CORE_SVG_OUTPUT){
 const {container}=mounted();const svg=walk(container).find(n=>n.tag==='svg');
 const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
 const serialize=n=>'<'+n.tag+Object.entries({...n.attrs,...(n===svg?{xmlns:'http://www.w3.org/2000/svg'}:{})}).map(([k,v])=>' '+k+'="'+escape(v)+'"').join('')+'>'+escape(n.ownText)+n.children.map(serialize).join('')+'</'+n.tag+'>';
 require('node:fs').writeFileSync(process.env.RDG_CORE_SVG_OUTPUT,serialize(svg));
}
