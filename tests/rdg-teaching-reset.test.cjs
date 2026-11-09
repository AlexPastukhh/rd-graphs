'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const root=path.resolve(__dirname,'..');
const slug='requirements-dependencies-demo';
const config=()=>JSON.parse(fs.readFileSync(path.join(root,'tools/rdg-resettable-examples.json'),'utf8'));
const run=(args)=>cp.spawnSync('python3',['-B',path.join(root,'tools/rdg-rebuild-teaching-example.py'),...args],
 {cwd:root,encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},timeout:25000});

test('only an explicitly registered example is resettable; no normal project or archive may be erased',()=>{
 const registry=config();assert.equal(registry.schemaVersion,1);
 assert.deepEqual(Object.keys(registry.examples),[slug]);
 const entry=registry.examples[slug];
 assert.equal(entry.graphFile,'workspaces/'+slug+'/graph.json');
 assert.equal(entry.planFile,'plans/'+slug+'/plan.json');
 assert.equal(entry.expectedPurpose,'real-api-teaching-workflow');
 const catalog=JSON.parse(fs.readFileSync(path.join(root,'graphs/catalog.json'),'utf8'));
 assert.equal(catalog.entries[entry.graphFile].folder,'examples');
 const open=run([]);assert.equal(open.status,0,open.stderr);
 assert.match(open.stdout,/DRY_RUN/);assert.match(open.stdout,/requirements-dependencies-demo/);
 for(const args of [['--reset','try-it','--confirm','try-it'],
                    ['--reset','reference-action-time-plan','--confirm','reference-action-time-plan'],
                    ['--reset',slug],['--reset',slug,'--confirm','try-it']]){
  const rejected=run(args);
  assert.notEqual(rejected.status,0,args.join(' '));
  assert.match(rejected.stderr,/TEACHING_RESET_DENIED/);
 }
});

test('initial teaching build stays verifiable in immutable history while current owners may evolve',()=>{
 const graph=JSON.parse(fs.readFileSync(path.join(root,'graphs/workspaces',slug,'graph.json'),'utf8'));
 const journals=fs.readdirSync(path.join(root,'graphs/workspaces/.transactions'))
  .filter(x=>x.endsWith('.json')).map(name=>JSON.parse(fs.readFileSync(
   path.join(root,'graphs/workspaces/.transactions',name),'utf8')));
 const initial=journals.find(j=>j.transactionId==='demo-reformulate-canon');
 assert(initial&&initial.state==='completed','the accepted end of the original teaching build remains');
 const baseline=initial.records.find(r=>r.file==='workspaces/'+slug+'/graph.json').after;
 // Fixed numbers describe this immutable original build, not the evolving live owner.
 assert.equal(baseline.revision,10);assert.equal(baseline.nodes.length,8);
 assert.equal(baseline.events.length,4);
 assert(baseline.nodes.every(n=>['requirement','action'].includes(n.kind)));
 assert(!baseline.nodes.some(n=>n.id==='C-ASSURANCE'));
 assert(!baseline.edges.some(e=>e.type==='CONTEXT_FOR'));
 assert(baseline.events.every(e=>!['action_executed','requirement_achieved'].includes(e.type)));
 const originalRecords=journals.flatMap(j=>j.records.filter(r=>
  r.file==='workspaces/'+slug+'/graph.json'&&r.changed&&r.after.revision<=baseline.revision));
 assert.equal(originalRecords.length,10);
 assert.equal(graph.actionModel,'candidate-v6');assert(graph.revision>=baseline.revision);
 const plan=JSON.parse(fs.readFileSync(path.join(root,'plans',slug,'plan.json'),'utf8'));
 assert.equal(plan.kind,'temporalPlanOwner');assert(plan.revision>=4);
 assert.deepEqual(plan.versions[0].plan.steps,[]);
 assert.equal(plan.versions[3].plan.steps.length,3,'original placements are preserved in their version');
 const source=JSON.parse(fs.readFileSync(path.join(root,'tools/rdg-published-owners.json'),'utf8')).owners[slug];
 assert.equal(source.graphRevision,graph.revision);assert.equal(source.planRevision,plan.revision);
 const oldGraph=fs.readFileSync(path.join(root,'graphs/examples/reference-mixed-active-work/graph.json'),'utf8');
 assert(oldGraph.includes('reference-mixed-active-work'),'archived old-model sources remain');
});
