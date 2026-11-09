'use strict';
// Documentation is a validated product interface, not a second RDG source.
const {test}=require('node:test'),assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const contents=name=>fs.readFileSync(path.join(root,name),'utf8');
const json=name=>JSON.parse(contents(name));
const sourceVersion=()=>contents('tools/rd-graph-viewer.user.js').match(/^\/\/ @version\s+(\d+\.\d+\.\d+)/m)?.[1];

test('authoritative documentation audit verifies policy classification, links, DRY, source parity',()=>{
 const result=spawnSync('python3',['-B','tools/rdg-docs-audit.py','--check','--json'],{
  cwd:root,encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},timeout:35000});
 assert.equal(result.status,0,result.stderr+'\n'+result.stdout);
 const report=JSON.parse(result.stdout);
 assert.equal(report.ok,true);assert.deepEqual(report.errors,[]);
 assert.equal(report.normativeFiles,json('docs/DOCS-POLICY.json').normative.length);
 // Retiring obsolete artifacts must not fail because the archive became smaller.
 assert(report.checkedLinks>0);
 assert(report.checkedAnchors>0);
 assert(report.checkedTestCases>0);
});

test('current documentation has one entry, separate active semantics and operations',()=>{
 const registry=json('docs/DOCS-POLICY.json');
 assert.equal(registry.schemaVersion,1);
 const normative=new Set(registry.normative);
 for(const file of ['README.md','docs/README.md','docs/guides/RDG-CURRENT-STATE.md',
  'docs/guides/RDG-ACTIVE-CONTRACT.md','docs/guides/RDG-OPERATIONS.md',
  'docs/guides/VIEWER-EXPLORER.md','docs/guides/RDG-LIVE-TEACHING-WORKSPACE.md',
  'docs/guides/RDG-MODULES.md','docs/guides/RDG-TEACHING-EXAMPLE-RESET.md',
  'docs/guides/RDG-GENDOCEN-REQUIREMENT-DEPENDENCIES.md']){
    assert(normative.has(file),'unregistered contract '+file);
    assert.match(contents(file).slice(0,600),/СТАТУС:/);
  }
 assert.match(sourceVersion(),/^\d+\.\d+\.\d+$/);
 assert(contents('README.md').includes('rdg-decision-v1'));
 assert(normative.has('docs/guides/RDG-FUNCTIONS-AND-TESTS.md'));
 assert(contents('README.md').includes(sourceVersion()));
 assert(contents('docs/guides/RDG-CURRENT-STATE.md').includes(sourceVersion()));
 assert.match(contents('docs/guides/RDG-OPERATIONS.md'),/Операционный регламент|операционный регламент/);
 assert.match(contents('docs/guides/RDG-ACTIVE-CONTRACT.md'),/не создаёт writer rights/);
});

test('present legacy entry points are unambiguously non-normative',()=>{
 const entries=[
  ['docs/handoffs/README.md',/НЕ ИНСТРУКЦИИ/],
  ['docs/examples/README.md',/НЕ АКТИВНЫЕ ГРАФЫ/],
  ['work-kit/README.md',/НЕ ИМПОРТИРОВАТЬ/],
  ['kit/README.md',/СТАТУС: АРХИВ/],
  ['tests/legacy-set-contract/README.md',/СТАТУС: АРХИВ/],
 ];
 for(const [file,warning] of entries){
  if(!fs.existsSync(path.join(root,file)))continue;
  assert.match(contents(file).slice(0,200),/^> \*\*СТАТУС: АРХИВ/,'missing archive warning in '+file);
  assert.match(contents(file),warning);
 }
 // This primary source is still consumed by graph/example tests and builders.
 assert(fs.existsSync(path.join(root,'docs/examples/requirements-decisions-graph-examples-v0.2.source.md')));
});

test('single training example fact source matches actual Graph/Plan/Gendocen owners',()=>{
 const slug='requirements-dependencies-demo';
 const graphPath=`graphs/workspaces/${slug}/graph.json`,planPath=`plans/${slug}/plan.json`;
 const graph=json(graphPath),plan=json(planPath);
 const publisher=json('tools/rdg-published-owners.json').owners[slug];
 const graphDigest=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,graphPath))).digest('hex');
 const planDigest=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,planPath))).digest('hex');
 assert.equal(publisher.graphSha256,graphDigest);
 assert.equal(publisher.planSha256,planDigest);
 assert.equal(graph.actionModel,'candidate-v6');
 assert.deepEqual([...new Set(graph.nodes.map(n=>n.kind))].sort(),['action','requirement']);
 assert(!graph.nodes.some(n=>n.id==='C-ASSURANCE'));
 assert.equal(json('graphs/catalog.json').entries[`workspaces/${slug}/graph.json`].folder,'examples');
 const live=contents('docs/guides/RDG-LIVE-TEACHING-WORKSPACE.md');
 assert(live.includes(`Graph revision ${graph.revision}`));
 assert(live.includes(`Plan revision ${plan.revision}`));
 assert(live.includes(`${publisher.history.length} первичных provenance-записей`));
 assert(live.includes(`${publisher.dependencies.rows.length} dependency targets`));
 for(const doc of ['README.md','docs/guides/RDG-ACTIVE-CONTRACT.md',
   'docs/guides/RDG-OPERATIONS.md','docs/guides/RDG-TEACHING-EXAMPLE-RESET.md'])
   assert.doesNotMatch(contents(doc),/\bGraph r\d+|\bPlan r\d+/);
});

test('reset command and Helper setup are unique and do not appear in stale guide instructions',()=>{
 const runbook=contents('docs/guides/RDG-OPERATIONS.md');
 const reset=contents('docs/guides/RDG-TEACHING-EXAMPLE-RESET.md');
 assert(reset.includes('--reset requirements-dependencies-demo'));
 assert(reset.includes('--confirm requirements-dependencies-demo'));
 assert(!runbook.includes('--reset requirements-dependencies-demo'));
 assert(runbook.includes('--manual-session'));
 assert(!contents('docs/guides/RDG-LIVE-TEACHING-WORKSPACE.md').includes('--manual-session'));
 assert.doesNotMatch(contents('docs/guides/VIEWER-EXPLORER.md'),/Все связи и контекст \(\+1\)/);
 assert(contents('docs/guides/VIEWER-EXPLORER.md').includes('Инвалидация'));
});

test('registered report titles preserve archive status without accepting missing or misplaced banners',()=>{
 const code=[
  'import runpy',
  "f=runpy.run_path('tools/rdg-docs-audit.py')['archived_status']",
  "p='docs/reviews/sample.md'; patterns=[p]",
  "banner='> **СТАТУС: АРХИВ.** Снимок'",
  "report='# Review\\n\\n'+banner+'\\n'",
  'assert f(p,report,patterns)',
  'assert not f(p,report,[])',
  "assert not f(p,'# Review\\n\\nТолько заголовок',patterns)",
  "assert not f(p,'# Review\\n\\nПредисловие\\n'+banner,patterns)",
  "assert not f(p,'# Review\\n\\n> **СТАТУС: ДЕЙСТВУЮЩИЙ**',patterns)",
  'assert f(p,banner,[])',
 ].join('\n');
 const result=spawnSync('python3',['-B','-c',code],{cwd:root,encoding:'utf8'});
 assert.equal(result.status,0,result.stderr+'\n'+result.stdout);
});


test('documentation links validate actual heading fragments and selected test cases',()=>{
 const code=String.raw`import runpy,tempfile
from pathlib import Path
m=runpy.run_path('tools/rdg-docs-audit.py')
text='# Раздел с '+chr(96)+'кодом'+chr(96)+'\n## Повтор\n## Повтор\n'+chr(96)*3+'md\n# Не раздел\n'+chr(96)*3+'\n<a id="старый-якорь"></a>\n'
anchors=m['doc_anchors'](text)
assert {'раздел-с-кодом','повтор','повтор-1','старый-якорь'}<=anchors,anchors
assert 'не-раздел' not in anchors
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);source=root/'index.md';source.write_text('# Index')
 target=root/'guide.md';target.write_text(text)
 assert m['link_problem'](source,'guide.md#раздел-с-кодом') is None
 assert m['link_problem'](source,'guide.md#%D0%BF%D0%BE%D0%B2%D1%82%D0%BE%D1%80') is None
 assert 'BROKEN_DOC_ANCHOR' in m['link_problem'](source,'guide.md#исчез')
 assert 'BROKEN_DOC_LINK' in m['link_problem'](source,'missing.md#раздел')
 assert m['link_problem'](source,'#index') is None
 assert m['link_problem'](source,'https://example.invalid/page#remote') is None
 test=root/'test_feature.py';test.write_text('def test_keeps_real_fact():\n    pass\n')
 assert m['trace_problem'](root,'test_feature.py','test_keeps_real_fact') is None
 assert 'DOC_TEST_CASE_MISSING' in m['trace_problem'](root,'test_feature.py','test_removed')
 assert 'DOC_TEST_NOT_IN_CI' in m['trace_problem'](root,'test_feature.py','test_keeps_real_fact',mandatory=True)
 assert m['trace_problem'](root,'test_feature.py','test_keeps_real_fact',mandatory=True,ci_files={'test_feature.py'}) is None
`;
 const result=spawnSync('python3',['-B','-c',code],{cwd:root,encoding:'utf8'});
 assert.equal(result.status,0,result.stderr+'\n'+result.stdout);
});
