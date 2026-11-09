const {test}=require('node:test');
const assert=require('node:assert/strict');
const {simulate,fixture,clone}=require('./viewer-test-helper.cjs');

test('V29 relationship types are labeled in Russian directly on arrows and explained on click',async()=>{
  const app=simulate({useBundle:true});await app.flush();
  await app.openCard('reference-app-definition');app.ids['edges-all'].onclick();
  assert.equal(app.ids['edge-toolbar'].hidden,false);
  const collect=(node,predicate)=>{
    const out=[];const walk=x=>{
      if(predicate(x))out.push(x);
      for(const child of x.children||[])walk(child);
    };
    walk(node);return out;
  };
  const expected=require('../graphs/examples/reference-app-definition/graph.json'),seen=new Set(),texts=new Set(),groups=new Set();let inspected=false;
  await app.visitLevels(()=>{
    const labels=collect(app.ids.canvas,x=>x.classList?.contains('edge-label'));
    for(const n of labels){seen.add(n.getAttribute('data-edge-id'));texts.add(n.children.find(c=>c.tag==='text')?.textContent);for(const g of ['core','ground','origin','review'])if(n.classList.contains('g-'+g))groups.add(g);}
    const informar=labels.find(n=>n.getAttribute('aria-label')?.startsWith('INFORMS')&&n.getAttribute('data-edge-id')===expected.edges.find(e=>e.from==='EX-D-SCREATE'&&e.to==='EX-D-FEATURES').id);
    if(informar){informar.listeners.click({stopPropagation(){}});assert.match(app.info(),/передаёт содержание в D \(INFORMS\)/);assert.match(app.info(),/Содержательная часть одного ответа/);assert.match(app.info(),/Доступность, подтверждение, отказ/);assert.match(app.info(),/EX-D-SCREATE → EX-D-FEATURES/);inspected=true;}
  });
  assert.deepEqual([...seen].sort(),expected.edges.map(e=>e.id).sort(),'Every original relation has a label in its level');
  for(const text of ['требует ответа от D','вводит дочерний R','передаёт содержание в D','выявляет требование','задаёт условия выбора','ставит вопрос к R или D'])assert(texts.has(text),'Missing semantic label: '+text);
  assert(inspected);assert.deepEqual([...groups].sort(),['core','ground','origin','review'].sort());
});

test('V30 filter keeps plan/decomposition only; all view restores all labeled relations',async()=>{
  const app=simulate({useBundle:true});await app.flush();
  await app.openCard('reference-app-definition');app.ids['edges-all'].onclick();
  const count=()=>{
    let k=0;const walk=n=>{
      if(n.classList?.contains('edge-label'))k++;
      for(const c of n.children||[])walk(c);
    };walk(app.ids.canvas);return k;
  };
  assert.equal(count(),10);
  app.ids['edges-core'].onclick();
  assert.equal(app.ids['edges-core'].getAttribute('aria-pressed'),'true');
  assert.equal(count(),8,'root DRIVES + seven first-level INTRODUCES; deeper answers use own levels');
  assert.equal(app.ids['edge-legend'].children.length,1);
  app.ids['edges-all'].onclick();
  assert.equal(count(),10);
  assert.equal(app.ids['edges-all'].getAttribute('aria-pressed'),'true');
  app.ids.source.hidden; // no raw Markdown in this graph
});

test('V31 proposed reconsideration and QRPE are visually distinguished from ready variants',async()=>{
  const app=simulate({useBundle:true});await app.flush();
  await app.openCard('reference-behavior-review');app.ids['edges-all'].onclick();
  const labels=[];
  const walk=n=>{if(n.classList?.contains('edge-label'))labels.push(n);
    for(const child of n.children||[])walk(child);};
  walk(app.ids.canvas);
  assert.equal(labels.length,9);
  const expected=require('../graphs/examples/reference-behavior-review/graph.json'),seen=new Set();await app.visitLevels(()=>{const each=[];const collect=n=>{if(n.classList?.contains('edge-label'))each.push(n);for(const c of n.children||[])collect(c)};collect(app.ids.canvas);for(const n of each)seen.add(n.getAttribute('data-edge-id'));});assert.deepEqual([...seen].sort(),expected.edges.map(e=>e.id).sort());
  const present=new Map(labels.map(x=>[x.getAttribute('aria-label').split(' — ')[0],x]));
  for(const t of ['DRIVES','INTRODUCES','CONTEXT_FOR','USES_VARIANT','QRPE_FOR','RECONSIDERS'])
    assert(present.has(t),'Missing relation: '+t);
  assert(present.get('RECONSIDERS').classList.contains('g-review'));
  assert(present.get('USES_VARIANT').classList.contains('g-ready'));
  assert(present.get('CONTEXT_FOR').classList.contains('g-ground'));
  present.get('RECONSIDERS').listeners.click({stopPropagation(){}});
  assert.match(app.info(),/предлагает пересмотр/);
  assert.match(app.info(),/ещё не пересмотренное Decision/);
  present.get('USES_VARIANT').listeners.click({stopPropagation(){}});
  assert.match(app.info(),/ссылается на готовый переиспользуемый способ/);
});

