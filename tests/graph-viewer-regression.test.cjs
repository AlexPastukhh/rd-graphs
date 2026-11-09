const {test}=require('node:test');
const assert=require('node:assert/strict');
const {simulate,fixture,clone,code,loaderCode}=require('./viewer-test-helper.cjs');
const byId=(app,id)=>app.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')===id);
const press=(app,id)=>byId(app,id).listeners.click({stopPropagation(){}});
const graph=(id,group='examples')=>require('../graphs/'+group+'/'+id+'/graph.json');
const walk=(root,pred)=>{const result=[];const go=x=>{if(pred(x))result.push(x);for(const c of x.children||[])go(c);};go(root);return result;};

test('V01 graph file: title, number and revision',async()=>{
 const app=simulate();await app.loadFile(fixture);
 assert.match(app.info(),/5 узлов \/ 3 связей/);
 assert.match(app.info(),/Revision: 1/);
 assert.equal(app.root.querySelectorAll('.node').length,4);app.ids['edges-all'].onclick();
 assert.equal(app.root.querySelectorAll('.node').length,5);
  const seen=new Set();await app.visitLevels(()=>{for(const edge of walk(app.ids.canvas,n=>n.classList?.contains('edge')))seen.add(edge.getAttribute('data-edge-id'));});
  assert.deepEqual([...seen].sort(),fixture.edges.map(e=>e.id).sort());
});
test('V02 inspect decision and requirement, show type and end points',async()=>{
 const app=simulate();await app.loadFile(fixture);
 press(app,'D-001');
 assert.match(app.info(),/D-001/);assert.match(app.info(),/R-001/);assert.match(app.info(),/R-002/);
 press(app,'R-002');await app.flush();press(app,'R-004');await app.flush();press(app,'R-005');await app.flush();
 press(app,'D-003');
 assert.match(app.info(),/Достаточность средства пока не проверена/);
 assert.match(app.info(),/CONTEXT_FOR/);
});
test('V03 search by ID and title, clearing restores overview',async()=>{
 const app=simulate();await app.loadFile(fixture);
 app.ids.search.value='R-005';app.ids.search.oninput({target:app.ids.search});
 assert.match(app.info(),/R-005/);
 app.ids.search.value='сценарии';app.ids.search.oninput({target:app.ids.search});
 assert.match(app.info(),/R-002/);
 app.ids.search.value='';app.ids.search.oninput({target:app.ids.search});
 assert.match(app.info(),/3 узлов/);
 await app.ids['level-up'].onclick();await app.ids['level-up'].onclick();assert.match(app.info(),/5 узлов/);
});
test('V04 zoom and Fit restore viewport',async()=>{
 const app=simulate();await app.loadFile(fixture);
 app.ids.fit.onclick();
 const scene=app.root.getElementById('scene'),before=scene.getAttribute('transform');
 app.ids.canvas.listeners.wheel({preventDefault(){},clientX:300,clientY:200,deltaY:-120});
 assert.notEqual(scene.getAttribute('transform'),before);
 app.ids.fit.onclick();assert.equal(scene.getAttribute('transform'),before);
});
test('V05 loads local catalog and refreshes changed revision',async()=>{
 const current=clone(fixture);
 const catalog={schemaVersion:1,defaultGraph:'example',graphs:[{slug:'example',title:'Пример',file:'example/graph.json'}],fullGraphs:[]};
 const files={'index.json':JSON.stringify(catalog),'example/graph.json':JSON.stringify(current)};
 const app=simulate({files});await app.flush();
 assert.equal(app.ids.catalog.hidden,false);
 await app.openCard('example');
 assert.match(app.info(),/Revision: 1/);
 current.revision=2;current.nodes.push({id:'R-006',kind:'requirement',title:'Ещё одно требование'});
 files['example/graph.json']=JSON.stringify(current);
 await app.ids.reload.onclick();
 assert.match(app.info(),/6 узлов/);assert.match(app.info(),/Revision: 2/);
});
test('V06 file refresh requires explicitly selecting file again',async()=>{
 const app=simulate();await app.loadFile(fixture);await app.ids.reload.onclick();
 assert.match(app.text(),/укажите его повторно/);
});
test('V07 invalid JSON preserves prior rendering',async()=>{
 const app=simulate();await app.loadFile(fixture);
 await app.loadFile('{broken');
 assert.match(app.text(),/Ошибка:/);assert.match(app.info(),/5 узлов/);
});
test('V08 switching graphs removes previous nodes',async()=>{
 const app=simulate();await app.loadFile(fixture);
 const x={schemaVersion:1,id:'next',revision:3,nodes:[{id:'R-N',kind:'requirement',title:'Другая цель'}],edges:[],events:[]};
 await app.loadFile(x);
 assert.equal(app.root.querySelectorAll('.node').length,1);
 assert.match(app.info(),/1 узлов/);
});
test('V09 empty graph gets finite transform',async()=>{
 const app=simulate();await app.loadFile({schemaVersion:1,id:'empty',revision:1,nodes:[],edges:[],events:[]});
 assert.match(app.info(),/0 узлов/);
 assert(!/Infinity|NaN/.test(app.root.getElementById('scene').getAttribute('transform')));
});
test('V10 built-in bundle defaults to folders and workspace is available',async()=>{
 const app=simulate({useBundle:true});await app.flush();
 assert.equal(app.ids['folder-list'].children.length,3);
 app.openFolder('workspaces');
 assert.equal(app.ids['graph-list'].children.length,1);
 await app.openCard('try-it');
 assert.match(app.info(),/Revision: 1/);
});
test('V11 rejects graph with duplicate node ID',async()=>{
 const app=simulate(),bad=clone(fixture);bad.nodes.push({...bad.nodes[0]});
 await app.loadFile(bad);
 assert.match(app.text(),/Некорректный или повторный узел/);
});
test('V12 rejects graph with dangling edge',async()=>{
 const app=simulate(),bad=clone(fixture);bad.edges[0].to='MISSING';
 await app.loadFile(bad);assert.match(app.text(),/Некорректная связь/);
});
test('V13 rejects graph with missing INTRODUCES parent',async()=>{
 const app=simulate(),bad=clone(fixture);bad.edges.find(e=>e.type==='INTRODUCES').parent='MISSING';
 await app.loadFile(bad);assert.match(app.text(),/Нет parent/);
});
test('V14 HTML injection is inert plain text in inspector',async()=>{
 const app=simulate(),g=clone(fixture);g.nodes[0].description='<img src=x onerror=alert(1)>';
 await app.loadFile(g);press(app,'R-001');
 assert.match(app.info(),/<img src=x onerror=alert\(1\)>/);
});
test('V15 rejects unsupported schemaVersion',async()=>{
 const app=simulate();await app.loadFile({...clone(fixture),schemaVersion:2});
 assert.match(app.text(),/schemaVersion=1/);
});
test('V16 accepts optional events without inventing state',async()=>{
 const app=simulate(),g=clone(fixture);g.events=[{id:'EV-1',type:'context_changed',note:'Только иллюстрация'}];
 await app.loadFile(g);assert.match(app.info(),/События \(1\)/);
 assert.match(app.info(),/EV-1/);
});
test('V17 selects a node and records selection only in DOM',async()=>{
 const app=simulate(),g=clone(fixture);await app.loadFile(g);
 press(app,'R-001');
 assert(byId(app,'R-001').classList.contains('selected'));
 assert.equal(g.nodes[0].id,'R-001');
});
test('V18 opens local bundled graph without file XHR',async()=>{
 const app=simulate({useBundle:true});await app.flush();
 await app.openCard('example');
 assert.match(app.info(),/5 узлов/);
 assert.equal(app.ids.content.hidden,false);
});
test('V19 folder card goes back to correct group',async()=>{
 const app=simulate({useBundle:true});await app.flush();
 app.openFolder('examples');
 await app.openCard('reference-app-definition');
 app.ids.back.onclick();
 assert.equal(app.ids.catalog.hidden,false);
 assert.equal(app.ids['catalog-title'].textContent,'Архивные примеры');
});
test('V20 graph card safely exposes read-only status',async()=>{
 const app=simulate({useBundle:true});await app.flush();
 app.openFolder('examples');await app.openCard('reference-delegation-status');
 assert.match(app.info(),/Эталон · только чтение/);
});
test('V21 2D Target Module has complete source display',async()=>{
 const app=simulate({useBundle:true});await app.flush();
 app.openFolder('2d');
 const slug='template-tm-2d-31-pixel-art-construction';
 await app.openCard(slug);
 assert.match(app.info(),/НЕ ПРИНЯТО/);
 assert.equal(app.ids.source.hidden,false);
 const unit=app.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')==='RU-PX-01');
 assert(unit);unit.listeners.click({stopPropagation(){}});await app.flush();
 const rootUnit=app.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')==='RU-PX-01');
 rootUnit.listeners.click({stopPropagation(){}});
 assert.match(app.info(),/Готовая Unit-specific Guidance/);
 app.ids.source.onclick();assert.equal(app.ids['source-view'].hidden,false);
 assert.match(app.ids['source-text'].textContent,/Module-defined Unit Inventory/);
 app.ids.source.onclick();assert.equal(app.ids.content.hidden,false);
});
test('V22 go from neutral parent R to functionality R with choices',async()=>{
 const app=simulate({useBundle:true});await app.flush();
 await app.openCard('reference-feature-root');
 press(app,'DEMO-R-FUNCTIONALITY');
 await app.flush();
 assert(byId(app,'DEMO-R-FUNCTIONALITY'));
 app.ids['edges-all'].onclick();
 assert(byId(app,'DEMO-V-BY-FEATURE'));
 assert(byId(app,'DEMO-V-OTHER'));
 assert(!byId(app,'DEMO-R-APP'));
});
test('V23 go to specific Feature and back preserving Requirement ID',async()=>{
 const app=simulate({useBundle:true});await app.flush();
 await app.openCard('reference-feature-root');
 press(app,'DEMO-R-FUNCTIONALITY');await app.flush();
 press(app,'DEMO-R-FEATURE-AUTH');await app.flush();
 assert(byId(app,'DEMO-R-FEATURE-AUTH'));
 assert.equal(app.ids['level-up'].hidden,false);
 await app.ids['level-up'].onclick();
 assert(byId(app,'DEMO-R-FUNCTIONALITY'));
});
test('V24 2D folder lists ten graph sets',async()=>{
 const app=simulate({useBundle:true});await app.flush();
 app.openFolder('2d');
 assert.equal(app.ids['graph-list'].children.length,10);
});
test('V28 malicious nested path is rejected',async()=>{
 const files={'index.json':JSON.stringify({schemaVersion:1,defaultGraph:'evil',graphs:[
  {slug:'evil',group:'examples',file:'examples/../evil/graph.json'}],fullGraphs:[]})};
 const app=simulate({files});await app.flush();
 assert.match(app.text(),/Недопустимый путь/);
});
test('V28b cross-file root inspector reports exact introducing Decision',async()=>{
 const app=simulate({useBundle:true});await app.flush();
 await app.openCard('reference-feature-root');
 press(app,'DEMO-R-FUNCTIONALITY');await app.flush();
 press(app,'DEMO-R-FUNCTIONALITY');
 assert.match(app.info(),/DEMO-D-APP/);
});
