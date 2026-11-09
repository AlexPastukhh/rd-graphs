'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const UI=require('../tools/rdg-portable-ui.js');
function document(){
  function element(tag){
    let text='';const attrs={},classes=new Set();
    return {tag,children:[],value:'',hidden:false,disabled:false,style:{},
      classList:{add(...items){items.forEach(x=>classes.add(x));},remove(...items){items.forEach(x=>classes.delete(x));},contains(x){return classes.has(x);},toggle(x,force){const yes=force??!classes.has(x);if(yes)classes.add(x);else classes.delete(x);return yes;}},
      get className(){return [...classes].join(' ');},set className(value){classes.clear();String(value).split(/\s+/).filter(Boolean).forEach(x=>classes.add(x));},
      appendChild(n){this.children.push(n);return n;},replaceChildren(...nodes){this.children=nodes;text='';},
      setAttribute(k,v){attrs[k]=String(v);},getAttribute(k){return attrs[k];},
      getBoundingClientRect(){return {width:1000,height:600};},
      get textContent(){return text+this.children.map(n=>n.textContent).join('');},
      set textContent(value){text=String(value);this.children=[];}};
  }
  return {createElement:element,createElementNS:(_ns,tag)=>element(tag)};
}
function all(root,predicate){return [...(predicate(root)?[root]:[]),...root.children.flatMap(n=>all(n,predicate))];}
test('actual Helper → portable controller → exact preflight/apply → detached Graph and Plan',
  {skip:!process.env.RDG_PORTABLE_TEST_URL&&'Run from the isolated Python transport suite'},async()=>{
    const base=process.env.RDG_PORTABLE_TEST_URL,cap=new URL(base).pathname.split('/').filter(Boolean).at(-1),calls=[];
    const call=async message=>{
      calls.push(structuredClone(message));
      const response=await fetch(new URL('command',base),{method:'POST',headers:{'Content-Type':'application/json',
        'Origin':new URL(base).origin,'X-RDG-Session':cap},body:JSON.stringify(message)});
      const result=await response.json();if(!response.ok)throw Error(result.error);return result;
    };
    const doc=document(),container=doc.createElement('main'),ui=UI.mount(container,{call},{document:doc});
    await ui.refresh();const rows=(await call({method:'catalog'})).packages;
    assert(all(container,n=>n.tag==='summary'&&n.textContent==='working').length>0);
    const working=rows.find(r=>r.role==='working'),ready=rows.find(r=>r.role==='ready');assert(working&&ready);
    await ui.open(ready.packageId);
    assert.equal(all(container,n=>n.tag==='summary'&&n.textContent==='План во времени').length,0);
    assert.equal(all(container,n=>n.tag==='summary'&&n.textContent==='История Graph и версии Plan').length,0);
    await ui.open(working.packageId);
    const line=all(container,n=>n.tag==='line')[0],node=all(container,n=>n.tag==='g')[0];assert(line&&node);
    const beforeLine=['x1','y1','x2','y2'].map(k=>line.getAttribute(k));
    node.onpointerdown({clientX:0,clientY:0,pointerId:1});node.onpointermove({clientX:30,clientY:40});node.onpointerup();
    assert.notDeepEqual(['x1','y1','x2','y2'].map(k=>line.getAttribute(k)),beforeLine);assert(ui.switchBlocked);
    await all(container,n=>n.tag==='button'&&n.textContent==='Отменить изменения раскладки')[0].onclick();assert.equal(ui.switchBlocked,false);
    const beforeCopies=all(container,n=>n.tag==='g'&&n.getAttribute('data-entity-id')==='R1').length;
    await all(container,n=>n.tag==='button'&&n.textContent==='Повторить только блок')[0].onclick();
    const repeats=all(container,n=>n.tag==='g'&&n.getAttribute('data-entity-id')==='R1');
    assert.equal(repeats.length,beforeCopies+1);
    assert(repeats.every(n=>n.getAttribute('aria-label').includes('визуально повторён')));
    assert(ui.switchBlocked,'visual occurrences are a draft until layout_edit');
    await all(container,n=>n.tag==='button'&&n.textContent==='Сохранить раскладку')[0].onclick();
    assert.equal(ui.pending.request.op,'layout_edit');
    const occurrenceCommand=ui.pending.request.commands.find(c=>c.type==='set_occurrences');
    assert.equal(Object.values(occurrenceCommand.occurrences).filter(o=>o.entityId==='R1').length,1);
    await all(container,n=>n.tag==='button'&&n.textContent==='Отменить подготовку')[0].onclick();
    await all(container,n=>n.tag==='button'&&n.textContent==='Отменить изменения раскладки')[0].onclick();
    assert.equal(ui.switchBlocked,false);
    const request=(await call({method:'schema',op:'apply_ready',packageId:working.packageId,sourcePackageId:ready.packageId})).request;
    request.mode='REPLACE_R';request.targetRequirementId='R1';request.note='Actual isolated controller replacement';
    await ui.prepare(request);assert.equal(calls.filter(r=>r.method==='apply').length,0);
    const button=all(container,n=>n.tag==='button'&&n.textContent==='Сохранить')[0];assert(button);await button.onclick();
    const before=calls.findLast(r=>r.method==='preflight'),after=calls.findLast(r=>r.method==='apply');assert.deepEqual(after.request,before.request);
    assert.equal(ui.pending,null);assert.equal(ui.view.graph.nodes.some(n=>n.id==='R1'),false);
    assert(ui.view.detached.some(c=>c.memberIds.includes('A')));assert(ui.view.completion.A.reviewRequired);
    assert.equal(ui.view.graph.nodes.find(n=>n.id==='A').status,'selected');
    assert(ui.view.plan.steps.every(s=>s.ref.nodeId!=='R1'));
    const retained=all(container,n=>n.tag==='button'&&n.textContent==='Retained action');assert(retained.length>0);
    await retained[0].onclick();assert.equal(ui.view.view.spec.id,'A');
    const readHistory=all(container,n=>n.tag==='button'&&n.textContent==='Прочитать историю')[0];await readHistory.onclick();
    const historical=all(container,n=>n.tag==='button'&&n.textContent==='Открыть Graph на момент события')[0];assert(historical);await historical.onclick();
    assert(calls.some(r=>r.method==='source_snapshot'));assert(container.textContent.includes('только чтение'));
    assert.equal(ui.view.view.spec.id,'A');assert.equal(all(container,n=>n.tag==='button'&&n.textContent==='Сохранить раскладку').length,1);
    const saveLayout=all(container,n=>n.tag==='button'&&n.textContent==='Сохранить раскладку')[0];await saveLayout.onclick();
    assert.equal(ui.pending.request.op,'layout_edit');assert.equal(JSON.parse(ui.pending.request.commands[0].graphKey).at(-1),'A');
  });

test('portable dependency form exposes shared info sources with explicit levels',async()=>{
  const calls=[];
  const entities=[
    {id:'R1',kind:'requirement',title:'R1',description:'Root',scope:'Synthetic',revision:1,status:'selected'},
    {id:'Y',kind:'requirement',title:'Y',description:'Dependent',scope:'Synthetic',revision:1},
    {id:'C3',kind:'info',title:'Shared criterion C3',description:'Shared',revision:1},
  ];
  const view={
    package:{role:'working'},path:'working/native-info',
    graph:{title:'Native info fixture',revision:1,nodes:entities.slice(0,2),objects:[entities[2]],edges:[],rootRequirementId:'R1',
      workGraphs:[{id:'WG-1',title:'Working',memberIds:entities.map(n=>n.id)}]},
    view:{graphKey:'graph',entities,edges:[],spec:{kind:'graph'}},layouts:{layouts:{}},detached:[],external:{states:[]},
    completion:{},plan:null,planView:{placements:[],sequence:[],branches:[]}
  };
  const call=async message=>{
    calls.push(structuredClone(message));
    if(message.method==='catalog')return {packages:[{packageId:'P1',role:'working',title:'Native info fixture',path:'working/native-info'}],folders:[]};
    if(message.method==='migration_sources')return {sources:[]};
    if(message.method==='read')return structuredClone(view);
    if(message.method==='schema')return {request:{op:message.op,transactionId:'tx-'+message.op,targetPackageId:'P1',expectedPackageRevision:1,expectedGraphRevision:1}};
    if(message.method==='preflight')return {effects:{}};
    throw Error('unexpected method '+message.method);
  };
  const doc=document(),container=doc.createElement('main'),ui=UI.mount(container,{call},{document:doc});
  await ui.refresh();await ui.open('P1');
  const native=all(container,n=>n.tag==='details'&&n.children[0]?.textContent==='Нативные зависимости L1/L2')[0];
  assert(native);
  const labels=all(native,n=>n.tag==='label');
  const control=title=>labels.find(n=>n.textContent.startsWith(title+' ')).children[0];
  const source=control('Источник'),target=control('Зависимый блок'),level=control('Уровень');
  assert(source.children.some(option=>option.value==='C3'));
  assert(!target.children.some(option=>option.value==='C3'));
  source.value='C3';target.value='Y';level.value='L2';
  const reason=labels.find(n=>n.textContent.startsWith('Основание зависимости ')).children[0];reason.value='Shared criterion has a direct semantic dependency';
  const add=all(native,n=>n.tag==='button'&&n.textContent==='Добавить L1/L2 зависимость')[0];assert(add);
  await add.onclick();
  assert.equal(ui.pending.request.op,'dependency_add');
  assert.equal(ui.pending.request.sourceId,'C3');
  assert.equal(ui.pending.request.dependentId,'Y');
  assert.equal(ui.pending.request.dependencyLevel,'L2');
  assert.equal(ui.pending.request.note,reason.value);
  assert.equal(calls.filter(message=>message.method==='apply').length,0);
  const preflight=calls.findLast(message=>message.method==='preflight');
  assert.deepEqual(preflight.request,ui.pending.request);
});
