#!/usr/bin/env node
'use strict';
/** Candidate v6: apply a prepared Lens definition to a real opt-in graph.
 * Read-only reports always require no graph writes or persisted LensRun.
 * A material change is delegated exclusively to graph-package's trust gate.
 * This is a bounded adapter for two concrete Lens Actions, NOT a DSL/AI runner.
 */
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const probes=require('./rdg-action-lens-semantic-probe.cjs');
const ROOT=path.resolve(__dirname,'..');
const DEFINITION=path.join(ROOT,'tests/fixtures/rdg-action-lens-pilot-v1.json');
const sha=buf=>crypto.createHash('sha256').update(buf).digest('hex');
const canonical=obj=>JSON.stringify(obj,(_,value)=>value&&typeof value==='object'&&!Array.isArray(value)?
  Object.fromEntries(Object.keys(value).sort().map(k=>[k,value[k]])):value);

function argumentsMap(argv){
 const opts={};
 for(let i=0;i<argv.length;i+=2){
  const k=argv[i];
  if(!k||!k.startsWith('--')||argv[i+1]===undefined)throw Error('Expected --key value pairs');
  opts[k.slice(2)]=argv[i+1];
 }
 return opts;
}
function validateGraphWithWriter(graph){
 // A Lens must not report root attainment on data rejected by the writer.
 // Reuse the same semantic validator; do not create a competing JS schema.
 const code=`import json,sys
from importlib.machinery import SourceFileLoader
mod=SourceFileLoader('rdg_lens_validation',sys.argv[1]).load_module()
mod.validate(json.load(sys.stdin))`;
 const check=spawnSync('python3',['-c',code,path.join(ROOT,'tools/graph-apply.py')],{
  input:JSON.stringify(graph),encoding:'utf8'});
 if(check.status!==0)throw Error('LENS_INVALID_SOURCE_GRAPH: '+(check.stderr||check.stdout).slice(-700));
}
function actualRequirements(graph){
 return graph.nodes.filter(n=>n.kind==='requirement'&&n.status!=='inactive'&&
   n.status!=='superseded'&&n.active!==false&&!n.projectionOf).map(n=>({
    id:n.id,title:n.title,concept:n.concept,status:n.status}));
}
function runInspection(source,graph,mode){
 if(graph.schemaVersion!==1||graph.actionModel!=='candidate-v6')
  throw Error('Lens application currently requires a candidate-v6 graph');
 if(!graph.identitySpace||!graph.rootRequirementId)throw Error('Unqualified graph owner');
 if(!Array.isArray(graph.nodes)||!Array.isArray(graph.edges)||!Array.isArray(graph.events)||
    !graph.nodes.some(n=>n.id===graph.rootRequirementId&&n.kind==='requirement')||
    new Set(graph.nodes.map(n=>n.id)).size!==graph.nodes.length)
  throw Error('Malformed target graph: no trustworthy root Requirement or graph structure');
 validateGraphWithWriter(graph);
 if(!['dry','maintenance'].includes(mode))throw Error('Unknown prepared Lens');
 const lensId=mode==='dry'?'L-DRY':'L-MAINT';
 const lens=probes.lensFromFixture(source,lensId);
 const target={id:graph.id,context:{},requirements:actualRequirements(graph),actions:[],actionEvidence:{}};
 let result;
 if(mode==='dry'){
  target.context=graph.lensContext||{};
  result=probes.readOnlyDryCheck({...source,targets:[target]},graph.id);
 }else{
  const evidenceNode=graph.nodes.find(n=>n.kind==='context'&&n.maintenanceComparison);
  if(!evidenceNode){
   result={achieved:false,result:'needs_evidence',performedActionIds:['A-L-MAINT-CHECK'],
    blockedRequirements:['R-L-MAINT-ALTS'],conditionalSkipped:['R-L-MAINT-CHANGE'],
    suggestions:[],qrpe:[{questionId:'Q-MAINT-ALTERNATIVE',status:'open'}],
    report:'Нет контекстных сравнительных evidence в рабочем графе.'};
  }else{
   const e=evidenceNode.maintenanceComparison;
   const selected=graph.nodes.find(n=>n.id===e.selectedActionId&&n.kind==='action'&&n.status==='selected');
   if(!selected)throw Error('Maintenance evidence lacks actual selected Action');
   const introduced=graph.edges.filter(edge=>edge.type==='INTRODUCES'&&
     edge.from===selected.id&&!edge.archived).map(edge=>edge.to);
   target.actions=[{id:'A-OLD',status:'selected',introduces:introduced},
     ...graph.nodes.filter(n=>n.kind==='action'&&n.status==='selected'&&n.id!==selected.id)
       .map(n=>({id:n.id,status:'selected',introduces:graph.edges.filter(edge=>
         edge.type==='INTRODUCES'&&edge.from===n.id&&!edge.archived).map(edge=>edge.to)}))];
   target.researchFindings=[{kind:'previously_untracked_action',action:{id:'A-NEW',
     introduces:e.alternative?.introduces||[]}}];
   if(graph.nodes.some(n=>n.id===e.alternative?.id))throw Error('Alternative is already in current Action list');
   target.actionEvidence={'A-OLD':e.current, 'A-NEW':e.alternative?.evidence};
   result=probes.readOnlyMaintenanceCheck({...source,targets:[target]},graph.id);
   result.targetSelectedActionId=selected.id;
   result.targetResearchActionId=e.alternative?.id;
   result.evidenceSource={kind:'graph-node',nodeId:evidenceNode.id,sha256:sha(Buffer.from(canonical(evidenceNode)))};
   if(evidenceNode.maintenanceComparison?.stale===true){
    result.achieved=false;result.result='needs_evidence';result.suggestions=[];
    result.qrpe=[{questionId:'Q-MAINT-ALTERNATIVE',status:'open'}];
    result.report='Context evidence is marked stale; do not adopt any alternative.';
   }
  }
 }
 return {lensId: lens.id,rootRequirementId:lens.rootRequirement.id,
  definitionDigest:sha(Buffer.from(canonical(lens))),
  targetIdentitySpace:graph.identitySpace,targetGraphId:graph.id,
  targetRevision:graph.revision,semanticResult:result.result,
  rootAchieved:result.achieved===true,performedLensActionIds:result.performedActionIds||[],
  skippedConditionalRequirements:result.conditionalSkipped||[],
  openQrpe:result.qrpe||[],suggestions:result.suggestions||[],
  report:result.report,sourceStatus:'candidate-reusable-definition',
  evidenceSource:result.evidenceSource||null,
  targetSelectedActionId:result.targetSelectedActionId||null,
  targetResearchActionId:result.targetResearchActionId||null,
  graphWrites:0,persistedLensRun:false,
  scope:'specialized adapter; graph-local assessments are provisional, not independently fact-checked',
  assessedResultProvisional:true};
}
function main(argv){
 const args=argumentsMap(argv);
 if(!args.graph||!args.lens)throw Error('--graph and --lens required');
 const graphPath=path.resolve(args.graph),source=JSON.parse(fs.readFileSync(DEFINITION,'utf8'));
 const graphBytes=fs.readFileSync(graphPath),graph=JSON.parse(graphBytes);
 const output=runInspection(source,graph,args.lens);
 output.sourceGraphSHA256=sha(graphBytes);
 const intent=args.mode||'report';
 if(intent==='report')return output;
 if(intent!=='apply'||args.lens!=='maintenance')throw Error('Only bounded Maintenance Lens supports trusted package application');
 if(output.semanticResult!=='propose_reconsideration'||!output.rootAchieved)
  throw Error('LENS_NOT_READY: evidence/research does not support material change');
 if(!args.package)throw Error('LENS_APPLY_REQUIRES_SIGNED_PACKAGE');
 const pkg=JSON.parse(fs.readFileSync(path.resolve(args.package),'utf8'));
 if(!pkg.transactionId||pkg.changes?.length!==1)throw Error('LENS_PACKAGE_SCOPE_INVALID');
 const change=pkg.changes[0],ops=change.patch?.operations;
 if(!Array.isArray(ops)||ops.length!==1||ops[0].op!=='reconsider_action')
  throw Error('LENS_PACKAGE_ACTION_MISMATCH');
 const op=ops[0];
 if(op.actionId!==output.targetSelectedActionId||change.patch.expectedRevision!==graph.revision||
    path.resolve(path.dirname(graphPath))!==path.resolve(ROOT,'graphs',path.dirname(change.file))||
    path.basename(graphPath)!=='graph.json')
  throw Error('LENS_PACKAGE_TARGET_MISMATCH');
 if(!change.file.startsWith('workspaces/'))throw Error('LENS_PACKAGE_WRITES_NON_WORKSPACE');
 // This Lens's prepared effect Action and QRPE must be resolved independently
 // from the target Action's review QRPE. A valid target review is not enough.
 const effect=op.event?.lensApplication;
 const proofRef=`graph-node:${output.evidenceSource?.nodeId}@${output.evidenceSource?.sha256}`;
 if(!effect||effect.lensId!==output.lensId||
    effect.lensActionId!=='A-L-MAINT-REVOKE'||
    effect.conditionalRequirementId!=='R-L-MAINT-CHANGE'||
    effect.lensRootRequirementId!==output.rootRequirementId||
    effect.definitionDigest!==output.definitionDigest||
    effect.targetGraphId!==graph.id||
    effect.targetRevision!==graph.revision||
    effect.effectQrpe?.questionId!=='Q-MAINT-EFFECTS'||
    !['resolved','accepted-risk'].includes(effect.effectQrpe.status)||
    typeof effect.effectQrpe.reason!=='string'||!effect.effectQrpe.reason.trim()||
    !Array.isArray(effect.effectQrpe.evidenceRefs)||
    !effect.effectQrpe.evidenceRefs.includes(proofRef))
  throw Error('LENS_EFFECT_QRPE_NOT_RESOLVED: expected explicit bound evidence and authorized Lens Action');
 const cli=spawnSync('python3',[path.join(ROOT,'tools/graph-apply.py'),
   '--package','--patch',path.resolve(args.package)],{encoding:'utf8',env:process.env});
 if(cli.status!==0)throw Error('LENS_WRITER_REJECTED: '+(cli.stderr||cli.stdout).slice(-900));
 const after=fs.readFileSync(graphPath),updated=JSON.parse(after);
 const persisted=updated.events.find(e=>e.id===op.event.id && e.type==='action_reconsidered');
 if(!persisted||!persisted.lensApplication||persisted.lensApplication.lensActionId!==effect.lensActionId)
  throw Error('LENS_EFFECT_HISTORY_MISSING: applied change not traceable to prepared Lens Action');
 output.graphWrites=1;output.appliedTransactionId=pkg.transactionId;
 output.performedLensActionIds=[...new Set([...output.performedLensActionIds,effect.lensActionId])];
 output.skippedConditionalRequirements=output.skippedConditionalRequirements.filter(id=>id!==effect.conditionalRequirementId);
 output.achievedLensRequirements=[effect.conditionalRequirementId];
 output.openQrpe=output.openQrpe.filter(q=>q.questionId!==effect.effectQrpe.questionId);
 output.resolvedEffectQrpe=effect.effectQrpe;
 output.semanticResult='reconsideration_applied';
 output.afterRevision=updated.revision;
 output.afterSHA256=sha(after);
 output.persistedLensRun=false;
 return output;
}
if(require.main===module){try{console.log(JSON.stringify(main(process.argv.slice(2)),null,2));}
 catch(error){console.error(error.message);process.exitCode=1;}}
module.exports={runInspection,main};
