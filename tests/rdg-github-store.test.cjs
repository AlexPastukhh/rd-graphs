'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process'),path=require('node:path');
test('GitHub adapter uses SHA CAS, signed common Graph API and optional Lens research in offline fake',()=>{
 const r=spawnSync('python3',[path.resolve(__dirname,'../tools/rdg-github-store-smoke.py')],{encoding:'utf8'});
 assert.equal(r.status,0,r.stderr||r.stdout);
 assert.match(r.stdout,/GITHUB_STORE_FAKE_PASS/);
});
