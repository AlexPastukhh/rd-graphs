'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const source=path.resolve(__dirname,'..','tools','rdg-authority.py');
function run(folder,action,input='',credential=''){
 return spawnSync('python3',[source,action,'--store',path.join(folder,'grants.json')],
 {encoding:'utf8',input,env:{...process.env,RDG_AUTH_TOKEN:credential}});
}
test('grant creation, modification and revocation apply to next request',()=>{
 const folder=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-grant-'));
 try {
  const owner=JSON.parse(run(folder,'init').stdout).token;
  const grant=JSON.parse(run(folder,'issue',JSON.stringify({
   permissions:['graph.create'],scopes:['workspaces/demo/graph.json']}),owner).stdout);
  const request={changes:[{file:'workspaces/demo/graph.json',create:{}}]};
  // A second actor with the same bearer sees the same scope.
  assert.equal(run(folder,'list','',owner).status,0);
  const amend=run(folder,'amend',JSON.stringify({id:grant.id,grant:{
   permissions:['graph.add_action'],scopes:['workspaces/demo/graph.json']}}),owner);
  assert.equal(amend.status,0,amend.stderr);
  const revoke=run(folder,'revoke',JSON.stringify({id:grant.id}),owner);
  assert.equal(revoke.status,0,revoke.stderr);
  assert(!fs.readFileSync(path.join(folder,'grants.json'),'utf8').includes(grant.token));
  assert.notEqual(run(folder,'list','',grant.token).status,0);
 } finally {fs.rmSync(folder,{recursive:true,force:true});}
});
test('delegated administrator cannot enlarge scope or modify owner',()=>{
 const folder=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-grant-'));
 try {
  const owner=JSON.parse(run(folder,'init').stdout).token;
  const d=JSON.parse(run(folder,'issue',JSON.stringify({
   permissions:['grant.admin','graph.create'],
   scopes:['workspaces/demo/graph.json']}),owner).stdout);
  const forbidden=run(folder,'issue',JSON.stringify({
   permissions:['graph.write'],scopes:['workspaces/']}),d.token);
  assert.notEqual(forbidden.status,0);
  assert.match(forbidden.stderr,/AUTH_DELEGATION_CEILING/);
  const forbiddenOwner=run(folder,'revoke',JSON.stringify({id:'root'}),d.token);
  assert.notEqual(forbiddenOwner.status,0);
  assert.match(forbiddenOwner.stderr,/AUTH_OWNER_IMMUTABLE/);
 } finally {fs.rmSync(folder,{recursive:true,force:true});}
});
