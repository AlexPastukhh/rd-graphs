'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..');
const CMD=path.join(ROOT,'tools/rdg-v6-action-reconsider-preflight.py');
const fixture=JSON.parse(fs.readFileSync(path.join(ROOT,'tests/fixtures/rdg-v6-action-optin/graph.json'),'utf8'));
function run(g,actionId='A1'){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'rdg-preflight-')),file=path.join(dir,'graph.json');
 try{fs.writeFileSync(file,JSON.stringify(g));const p=spawnSync('python3',[CMD,'--graph',file,'--action-id',actionId],{encoding:'utf8'});
  return {status:p.status,err:p.stderr,report:p.status===0?JSON.parse(p.stdout):null};
 }finally{fs.rmSync(dir,{force:true,recursive:true});}
}
test('a selected Action with real child R and open QRPE cannot be silently revoked',()=>{
 const before=JSON.stringify(fixture),r=run(fixture);
 assert.equal(r.status,0,r.err);assert.equal(r.report.canExecuteRevocation,false);
 assert.deepEqual(r.report.unresolvedRequirementIds,['R1','R2']);
 assert.deepEqual(r.report.openQrpeIds,['Q1']);
 assert.equal(r.report.authorityVerified,false);
 assert.equal(r.report.externalEffectsVerifiedAbsent,false);
 assert.equal(JSON.stringify(fixture),before);
});
test('another selected Action can independently justify one of multiple introduced R',()=>{
 const copy=structuredClone(fixture);
 const a=structuredClone(copy.nodes.find(n=>n.id==='A1'));
 a.id='A2';a.title='Another selected way';a.selectionBasis.actionSnapshot.id='A2';
 copy.nodes.push(a);
 copy.edges.push({id:'drive-A2',type:'DRIVES',from:'R0',to:'A2'});
 copy.edges.push({id:'shared-R1',type:'INTRODUCES',from:'A2',to:'R1',parent:'R0'});
 copy.events.push({id:'EV2',type:'action_selected',actionId:'A2',driverRequirementId:'R0',by:'assistant',note:'Synthetic second choice'});
 const out=run(copy);assert.equal(out.status,0,out.err);
 assert.deepEqual(out.report.introducedRequirements[0].independentSelectedActionIds,['A2']);
 assert.equal(out.report.introducedRequirements[0].disposition,'separately-justified');
 assert.deepEqual(out.report.unresolvedRequirementIds,['R2']);
});
test('even an Action without child R is not automatically authorized for revocation',()=>{
 const copy=structuredClone(fixture);copy.edges=copy.edges.filter(e=>e.type!=='INTRODUCES');
 copy.nodes=copy.nodes.filter(n=>!['R1','R2'].includes(n.id));
 const out=run(copy);assert.equal(out.status,0,out.err);
 assert.deepEqual(out.report.unresolvedRequirementIds,[]);
 assert.equal(out.report.canExecuteRevocation,false);
 assert.equal(out.report.authorityVerified,false);
});
test('preflight rejects legacy graphs and missing Action IDs',()=>{
 const legacy=structuredClone(fixture);delete legacy.actionModel;
 assert.notEqual(run(legacy).status,0);
 assert.notEqual(run(fixture,'A-MISSING').status,0);
});
