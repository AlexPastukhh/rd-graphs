const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {simulate}=require('./viewer-test-helper.cjs');
const root=path.resolve(__dirname,'..');
const walk=(n,p)=>{const out=[];const visit=x=>{if(p(x))out.push(x);for(const c of x.children||[])visit(c);};visit(n);return out;};
const nodes=app=>walk(app.ids.canvas,n=>n.classList?.contains('node'));
const labels=app=>walk(app.ids.canvas,n=>n.classList?.contains('edge-label'));
const coordinates=n=>(n.getAttribute('transform').match(/[-\d.]+/g)||[]).map(Number);
const read=slug=>JSON.parse(fs.readFileSync(path.join(root,'graphs/examples',slug,'graph.json'),'utf8'));
test('a crowded functionality graph opens on its actual root and answer, not auxiliary records',async()=>{
 const app=simulate(),g=read('reference-complete-functionality'),before=JSON.stringify(g);
 await app.loadFile(g);
 assert.equal(app.ids['edges-core'].getAttribute('aria-pressed'),'true');
 assert.deepEqual(nodes(app).map(n=>n.getAttribute('data-id')).sort(),['SH-R-FUNC','SH-D-CHOOSE-FEATURES','SH-R-FEAT-AVAIL','SH-R-FEAT-RES'].sort());
 const xy=new Map(nodes(app).map(n=>[n.getAttribute('data-id'),coordinates(n)]));
 assert(xy.get('SH-R-FUNC')[0]<xy.get('SH-D-CHOOSE-FEATURES')[0]);
 assert(xy.get('SH-D-CHOOSE-FEATURES')[0]<xy.get('SH-R-FEAT-AVAIL')[0]);
 assert.equal(xy.get('SH-R-FUNC')[1],xy.get('SH-D-CHOOSE-FEATURES')[1]);
 assert.equal(labels(app).length,3);
 assert.match(app.ids['edge-label-hint'].textContent,/4 из 18/);
 assert.equal(JSON.stringify(g),before);
});
test('all relations keeps one level, and every original record and relationship remains accessible through levels',async()=>{
 const app=simulate(),g=read('reference-complete-functionality');await app.loadFile(g);
 app.ids['edges-all'].onclick();
 assert.equal(nodes(app).length,g.nodes.length-1);assert(!nodes(app).some(n=>n.getAttribute('data-id')==='SH-D-BEHAVIOR-SHARED'));
 const seenNodes=new Set(),seenEdges=new Set();await app.visitLevels(()=>{for(const n of nodes(app))seenNodes.add(n.getAttribute('data-id'));for(const n of labels(app))seenEdges.add(n.getAttribute('data-edge-id'));});
 assert.deepEqual([...seenNodes].sort(),g.nodes.map(n=>n.id).sort());assert.deepEqual([...seenEdges].sort(),g.edges.map(e=>e.id).sort());
 const bands=walk(app.ids.canvas,n=>n.getAttribute?.('data-layout-band')).map(n=>n.textContent);
 for(const text of ['Основания и контекст','Готовые варианты и применения','Вопросы и пересмотр'])assert(bands.includes(text));
 const xy=new Map(nodes(app).map(n=>[n.getAttribute('data-id'),coordinates(n)]));
 assert(xy.get('SH-C-SCOPE')[1]>xy.get('SH-R-FUNC')[1]);
 assert(xy.get('SH-V-BY-FEATURES')[1]>xy.get('SH-C-SCOPE')[1]);
 app.ids['edges-core'].onclick();assert.equal(nodes(app).length,4);assert.equal(labels(app).length,3);
});
test('searching a hidden auxiliary record exposes that record instead of dropping its inspector',async()=>{
 const app=simulate();await app.loadFile(read('reference-complete-functionality'));
 app.ids.search.oninput({target:{value:'SH-C-SCOPE'}});
 assert(nodes(app).some(n=>n.getAttribute('data-id')==='SH-C-SCOPE'));
 assert.match(app.info(),/SH-C-SCOPE/);assert.equal(app.ids['edges-all'].getAttribute('aria-pressed'),'true');
});
test('routed arrows do not cut through unrelated node rectangles in any bundled graph or view',async()=>{
 const app=simulate(),catalog=JSON.parse(fs.readFileSync(path.join(root,'graphs/index.json'),'utf8'));
 for(const entry of catalog.graphs){
  const g=JSON.parse(fs.readFileSync(path.join(root,'graphs',entry.file),'utf8'));await app.loadFile(g);
  for(const mode of ['edges-core','edges-all']){
   app.ids[mode].onclick();
   const boxes=nodes(app).map(n=>{const [x,y]=coordinates(n);return {id:n.getAttribute('data-id'),x,y,w:222,h:72};});
   for(const edge of walk(app.ids.canvas,n=>n.classList?.contains('edge'))){
    let e=g.edges.find(e=>e.id===edge.getAttribute('data-edge-id'));
    if(!e && edge.getAttribute('data-edge-id').startsWith('__group__')){
      const id=edge.getAttribute('data-edge-id').slice('__group__'.length);
      const collection=(g.collections||[]).find(c=>c.id===id);
      assert(collection,'virtual collection edge must reference a persisted grouping');
      e={from:collection.anchor,to:'__collection__'+collection.id};
    }
    if(!e && edge.getAttribute('data-edge-id').startsWith('__viewcanon__')){
      const id=edge.getAttribute('data-edge-id').slice('__viewcanon__'.length);
      const selected=g.nodes.find(n=>n.kind==='decision'&&
        ['committed','selected-in-example-only'].includes(n.status)&&n.selectedOptionId===id);
      const visibleIds=new Set(boxes.map(n=>n.id));
      e={from:visibleIds.has(id)?id:selected?.id,to:'__canon__'+id};
      assert(e.from&&g.nodes.some(n=>n.id===id&&['option','action'].includes(n.kind)&&n.canonBlock),
        'virtual canon edge must originate in one persisted option or Action');
    }
    if(!e && edge.getAttribute('data-edge-id').startsWith('__groupmember__')){
      const key=edge.getAttribute('data-edge-id').slice('__groupmember__'.length);
      const collection=(g.collections||[]).find(c=>key.startsWith(c.id+'__'));
      assert(collection);const member=key.slice(collection.id.length+2);assert(collection.memberRefs.includes(member));
      e={from:collection.anchor,to:member};
    }
    assert(e,'unknown visible edge');
    const raw=edge.getAttribute('d').match(/[-\d.]+/g).map(Number),points=[];
    for(let i=0;i<raw.length;i+=2)points.push([raw[i],raw[i+1]]);
    for(let i=1;i<points.length;i++){
     const [a,b]=[points[i-1],points[i]];assert(a[0]===b[0]||a[1]===b[1]);
     for(const n of boxes){
      if(n.id===e.from||n.id===e.to)continue;
      const hit=a[0]===b[0]?a[0]>n.x&&a[0]<n.x+n.w&&Math.max(a[1],b[1])>n.y&&Math.min(a[1],b[1])<n.y+n.h:
       a[1]>n.y&&a[1]<n.y+n.h&&Math.max(a[0],b[0])>n.x&&Math.min(a[0],b[0])<n.x+n.w;
      assert(!hit,entry.slug+' '+mode+' '+e.id+' crosses '+n.id);
     }
    }
   }
  }
 }
});
test('missing root and a self reference do not collapse or crash the renderer',async()=>{
 const app=simulate();await app.loadFile({schemaVersion:1,id:'loose',revision:1,nodes:[{id:'C1',kind:'context',title:'One'},{id:'C2',kind:'context',title:'Two'}],edges:[]});
 assert.equal(nodes(app).length,2);assert.notDeepEqual(coordinates(nodes(app)[0]),coordinates(nodes(app)[1]));
 const g={schemaVersion:1,id:'loop',revision:1,rootRequirementId:'R1',nodes:[{id:'R1',kind:'requirement',title:'Root'}],edges:[{id:'L',type:'APPLIES_TO',from:'R1',to:'R1'}]};
 await app.loadFile(g);app.ids['edges-all'].onclick();assert.equal(labels(app).length,1);assert(!app.text().startsWith('Ошибка'));
});

test('inspecting one full-view relation dims other arrows but preserves both endpoint records',async()=>{
 const app=simulate();await app.loadFile(read('reference-complete-functionality'));app.ids['edges-all'].onclick();
 const edge=labels(app).find(n=>n.getAttribute('data-edge-id')==='SH-E-FUN-15');
 edge.listeners.click({stopPropagation(){}});
 assert.match(app.info(),/SH-D-DESCRIBE → SH-D-CHOOSE-FEATURES/);
 for(const n of labels(app))assert.equal(n.classList.contains('dim'),n.getAttribute('data-edge-id')!=='SH-E-FUN-15');
 for(const n of nodes(app))assert.equal(n.classList.contains('dim'),!['SH-D-DESCRIBE','SH-D-CHOOSE-FEATURES'].includes(n.getAttribute('data-id')));
});

test('a fitted full graph stays inside the real viewport even at a fractional scale',async()=>{
 const app=simulate();app.ids.canvas.clientWidth=1227;app.ids.canvas.clientHeight=1605;
 await app.loadFile(read('reference-complete-functionality'));app.ids['edges-all'].onclick();
 const tr=coordinates(app.root.getElementById('scene'));
 for(const n of nodes(app)){
  const [x,y]=coordinates(n);
  assert(x*tr[2]+tr[0]>=0&&y*tr[2]+tr[1]>=0);
  assert((x+222)*tr[2]+tr[0]<=1227&&(y+72)*tr[2]+tr[1]<=1605,'cropped '+n.getAttribute('data-id'));
 }
});
