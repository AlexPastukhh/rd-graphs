'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {spawnSync}=require('node:child_process'),path=require('node:path'),os=require('node:os');
const fixture=require('./fixtures/rdg-action-lens-pilot-v1.json');
const file=path.resolve(__dirname,'../tools/rdg-lens-session-cli.cjs');
test('AI-readable Lens CLI does not write any graph or session by default',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-lens-cli-'));
 try{
  const lens=fixture.lensDefinitions[0];
  fs.writeFileSync(path.join(dir,'lens.json'),JSON.stringify(lens));
  fs.writeFileSync(path.join(dir,'bind.json'),JSON.stringify({targetGraphId:'demo',
    targetActionId:'A1',relevantInputs:{costEvidence:'sample'}}));
  const before=fs.readdirSync(dir).sort();
  const r=spawnSync('node',[file,'--lens',path.join(dir,'lens.json'),
   '--bindings',path.join(dir,'bind.json')],{encoding:'utf8'});
  assert.equal(r.status,0,r.stderr);
  const out=JSON.parse(r.stdout);
  assert.equal(out.session.kind,'working-lens-graph');
  assert.equal(out.session.rootResult,'unknown');
  assert.equal(out.persistence.saved,false);
  assert.deepEqual(fs.readdirSync(dir).sort(),before);
 }finally{fs.rmSync(dir,{force:true,recursive:true});}
});
test('GitHub-backed Lens lookup requires explicit repository configuration and never silently writes',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-lens-github-cli-'));
 try{
  const lens=fixture.lensDefinitions[0];
  fs.writeFileSync(path.join(dir,'lens.json'),JSON.stringify(lens));
  fs.writeFileSync(path.join(dir,'bind.json'),JSON.stringify({targetGraphId:'no-real-owner',
   targetActionId:'A1',relevantInputs:{v:1}}));
  const argv=[file,'--lens',path.join(dir,'lens.json'),
   '--bindings',path.join(dir,'bind.json'),'--github-metadata'];
  const env={...process.env};delete env.RDG_GITHUB_REPOSITORY;delete env.GITHUB_TOKEN;
  const r=spawnSync('node',argv,{encoding:'utf8',env});
  assert.equal(r.status,2);
  assert.match(r.stderr,/RDG_GITHUB_REPOSITORY/);
  assert.deepEqual(fs.readdirSync(dir).sort(),['bind.json','lens.json']);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
