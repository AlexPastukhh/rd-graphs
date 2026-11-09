'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const projection = require('../tools/rdg-root-projection.js');
const root = path.join(__dirname, '../graphs');
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'index.json')));
const bundled = {...catalog, graphs:catalog.graphs.map(g=>({...g,graph:JSON.parse(fs.readFileSync(path.join(root,g.file)))}))};
test('sixteen migrated historical entry roots remain discoverable without set membership',()=>{
  const entries=projection.listEntries(bundled);
  const expected=['template-tm-2d-10-visual-requirements','template-tm-2d-15-prepared-visual-material-set',
    'template-tm-2d-20-whole-visual-design','template-tm-2d-30-visual-construction',
    'template-tm-2d-31-editable-raster-construction','template-tm-2d-31-painterly-raster-construction',
    'template-tm-2d-31-pixel-art-construction','template-tm-2d-31-procedural-construction',
    'template-tm-2d-31-vector-construction','template-tm-2d-50-delivery-adaptation',
    'archive-booking','archive-features','context-prepared','context-working','example-prepared','example-working'];
  const translated=new Map([['archive-booking','reference-complete-app'],['archive-features','reference-feature-root'],
    ['context-prepared','context-prepared-root'],['context-working','context-working-root'],
    ['example-prepared','reference-prepared-planning-tree'],['example-working','reference-mixed-active-work']]);
  for(const old of expected){const slug=translated.get(old)||old.replace('set-','');
    assert(entries.some(e=>e.slug===slug),'lost entry '+slug);}
});
test('prepared multiwave prospective R are visible without acceptance',()=>{
  const g=projection.project(bundled, 'reference-prepared-planning-tree');
  assert(g.nodes.some(n=>n.id==='RF-DEEP'&&n.branchState==='potential'));
  assert(g.nodes.every(n=>n.kind==='requirement'));
  assert(g.edges.some(e=>e.kind==='potential'));
  const chosen=projection.project(bundled,'reference-prepared-planning-tree',{includePotential:false});
  assert(!chosen.nodes.some(n=>n.id==='RF-1'));
});
test('independent projects sharing a Requirement id do not mix due to identitySpace',()=>{
  const a=projection.project(bundled,'template-tm-2d-10-visual-requirements');
  assert.equal(a.nodes.filter(n=>n.id==='TEMPLATE-R-TARGET-RESULT').length,1);
  assert(a.nodes.every(n=>!n.sourceGraphSlug.includes('template-tm-2d-15')));
  assert(a.edges.some(e=>e.kind==='prepared'));
});
test('source graphs are not mutated by read-only projections',()=>{
  const before=JSON.stringify(bundled.graphs);
  projection.project(bundled,'reference-mixed-active-work');
  assert.equal(JSON.stringify(bundled.graphs),before);
});
test('writable paper branches, deeper local choice and unrelated root stay in correct scope',()=>{
  const g=(slug,folder,root,nodes,edges)=>({slug,folder,graph:{identitySpace:'my-work',rootRequirementId:root,nodes,edges}});
  const req=(id,status,extra={})=>({id,kind:'requirement',title:id,status,...extra});
  const opt=id=>({id,kind:'option',title:id,status:'candidate',origin:'situational'});
  const e=(type,from,to,extra={})=>({id:type+':'+from+':'+to,type,from,to,...extra});
  const items=[
    g('root','work', 'R0', [req('R0','active'),opt('O-A'),opt('O-B'),req('R1','candidate'),req('R2','candidate')],[
      e('OPTION_FOR','R0','O-A'),e('OPTION_FOR','R0','O-B'),e('OUTCOME_OF','O-A','R1'),e('OUTCOME_OF','O-B','R2')]),
    g('r1','elsewhere', 'R1', [req('R1','candidate',{projectionOf:{graphSlug:'root',nodeId:'R1'}}),
      {id:'D-LOCAL',kind:'decision',status:'committed',title:'Local decision'},req('R3','candidate')],[
      e('DRIVES','R1','D-LOCAL'),e('INTRODUCES','D-LOCAL','R3',{parent:'R1'})]),
    g('unrelated','work', 'R-UNRELATED', [req('R-UNRELATED','active')],[])
  ];
  const all=projection.project({graphs:items},'root');
  assert.deepEqual(new Set(all.nodes.map(n=>n.id)),new Set(['R0','R1','R2','R3']));
  assert(all.nodes.filter(n=>n.id!=='R0').every(n=>n.branchState==='potential'));
  assert.equal(all.edges.find(e=>e.to==='R3').kind,'selected'); // Locally selected, not main-actual.
  const actual=projection.project({graphs:items},'root',{includePotential:false});
  assert.deepEqual(actual.nodes.map(n=>n.id),['R0']);
  assert(!all.nodes.some(n=>n.id==='R-UNRELATED'));
});
test('non-causal source views remain navigable but are never invented R descendants',()=>{
  const g=projection.project(bundled,'reference-complete-app');
  assert(g.supplementaryViews.some(v=>v.relationKind==='derived'));
  assert(g.supplementaryViews.some(v=>v.relationKind==='same-requirement'));
  assert(!g.edges.some(e=>e.kind==='same-requirement'));
  assert(!g.nodes.some(n=>n.id==='SH-R-RESULT'));
});
test('root closure works without graphSets metadata',()=>{
  const noSets={...bundled,graphSets:[]};
  const actual=projection.project(noSets,'reference-prepared-planning-tree');
  assert(actual.nodes.some(n=>n.id==='RF-DEEP'));
});
