'use strict';
// No side effects by default: only explicit valuable pending work is persistable.
const {canonical,hash}=require('./rdg-lens-session.cjs');
function eligible(session,claim){
 if(!session||session.kind!=='working-lens-graph')throw Error('LENS_PERSIST_INVALID_SESSION');
 if(!claim||claim.persistRequested!==true)return {save:false,reason:'default-no-write'};
 const criteria=['materialUnresolvedWork','costlyToRecreate','likelyFutureUse',
  'notAlreadyAvailableInTarget','stableEnoughForReuse','maintenanceWorthwhile'];
 if(!criteria.every(k=>claim[k]===true))return {save:false,reason:'persistence-benefit-not-established'};
 // A completed, expensive assessment for an unselected target Action can
 // remain worth preserving even if the Lens issues themselves are all closed.
 // Do not mistake a caller's bare 'pending' flag for completed research.
 const assessed=session.canonAssessments.some(x=>
  ['applicable','inapplicable'].includes(x.result) &&
  Array.isArray(x.evidenceRefs)&&x.evidenceRefs.length&&x.reason?.trim()) ||
  session.requirementAssessments.some(x=>
   ['achieved','blocked'].includes(x.result)&&Array.isArray(x.evidenceRefs)&&x.evidenceRefs.length);
 const pendingWithEvidence=claim.pendingDecisionForActionId &&
  claim.pendingDecisionForActionId===session.bindings.targetActionId &&
  claim.pendingDecisionState==='unselected' && assessed;
 if(!session.unresolvedQrpe.length&&!session.unassessedOrStaleCanons.length&&
    !pendingWithEvidence)
  return {save:false,reason:'no-pending-research-to-preserve'};
 if(typeof claim.reason!=='string'||!claim.reason.trim())
  return {save:false,reason:'no-justification'};
 return {save:true,reason:claim.reason};
}
function capture(session,claim,recordedAt){
 const decision=eligible(session,claim);
 if(!decision.save)return {saved:false,decision};
 if(typeof recordedAt!=='string'||Number.isNaN(Date.parse(recordedAt)))
  throw Error('LENS_PERSIST_TIMESTAMP_REQUIRED');
 const metadata={
  recordedAt:new Date(recordedAt).toISOString(),lensId:session.lensId,
  definitionDigest:session.definitionDigest,
  targetGraphId:session.bindings.targetGraphId,
  targetActionId:session.bindings.targetActionId,
  targetRequirementId:session.bindings.targetRequirementId||null,
  arguments:structuredClone(session.bindings.arguments||{}),
  relevantInputsDigest:hash(session.bindings.relevantInputs),
  relevantInputs:structuredClone(session.bindings.relevantInputs),
  rootResult:session.rootResult,unresolvedQrpe:[...session.unresolvedQrpe],
  retentionReason:decision.reason,
  pendingDecisionForActionId:claim.pendingDecisionForActionId||null,
  pendingDecisionState:claim.pendingDecisionState||null,
  canonAssessmentCount:session.canonAssessments.length,
  requirementAssessmentCount:session.requirementAssessments.length,
 };
 // Small metadata may be listed without passing the full graph to the AI.
 const id=metadata.recordedAt.replace(/[-:.]/g,'').replace('T','-').replace('Z','')+
  '-'+hash({metadata,graph:session.graph}).slice(0,12);
 return {saved:true,id,metadata,workingGraph:structuredClone(session)};
}
function lastRelevant(metadatas,query){
 if(!Array.isArray(metadatas)||!query||!query.lensId||!query.targetGraphId||
  (query.targetActionId===undefined))throw Error('LENS_LOOKUP_SCOPE_REQUIRED');
 const a=canonical(query.arguments||{});
 const candidates=metadatas.filter(m=>m&&m.lensId===query.lensId&&
  m.targetGraphId===query.targetGraphId&&m.targetActionId===query.targetActionId&&
  (m.targetRequirementId||null)===(query.targetRequirementId||null)&&
  canonical(m.arguments||{})===a&&typeof m.recordedAt==='string');
 candidates.sort((x,y)=>y.recordedAt.localeCompare(x.recordedAt));
 if(!candidates.length)return {found:false};
 const latest=candidates[0],differences=[];
 if(latest.definitionDigest!==query.definitionDigest)differences.push('lens-definition-changed');
 if(latest.relevantInputsDigest!==hash(query.relevantInputs||{}))differences.push('relevant-inputs-changed');
 if(query.evidenceStillValid!==true)differences.push('evidence-freshness-unverified');
 return {found:true,metadata:structuredClone(latest),
  reuseStatus:differences.length?'needs-reassessment':'candidate-for-reuse',
  reasons:differences,fullGraphLoaded:false,
  disclaimer:'Последнее СОХРАНЁННОЕ подходящее применение, не последнее фактически выполненное.'};
}
module.exports={eligible,capture,lastRelevant};
