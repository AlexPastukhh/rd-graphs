'use strict';
// A prepared Lens is a reusable RDG graph. This adapter is semantics-only:
// it never writes the target and never invokes a Lens-specific mutation API.
const crypto=require('node:crypto');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
function validateOrdinaryLens(graph){
 // This is the same validator used by the material writer, not a second
 // relaxed Lens schema. Prepared semantic fixtures follow their own parser.
 const decision=graph.coreModel==='rdg-decision-v1';
 const validator=path.join(__dirname,decision?'rdg-model-profiles.py':'graph-apply.py');
 const code='import sys,json;from importlib.machinery import SourceFileLoader;'+
  'mod=SourceFileLoader("lens_source_validator",sys.argv[1]).load_module();'+
  (decision?'mod.validate_role(json.load(sys.stdin),\"lens\")':'mod.validate(json.load(sys.stdin))');
 const result=spawnSync('python3',['-c',code,validator],{
  input:JSON.stringify(graph),encoding:'utf8',maxBuffer:1024*1024});
 check(!result.error&&result.status===0,'INVALID_ORDINARY_GRAPH: '+
  (result.error?.message||result.stderr||result.stdout||'validator failed').slice(-550));
}

function canonical(x){return JSON.stringify(x,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?
 Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b,'en'))):v);}
const hash=x=>crypto.createHash('sha256').update(canonical(x)).digest('hex');
function check(ok,msg){if(!ok)throw Error('LENS_SESSION_'+msg);}
function parsePreparedLens(lens){
 // Ordinary candidate-v6 graph.json is accepted as a Lens definition too;
 // the older semantic fixture remains supported as a compatibility input.
 if(lens&&Array.isArray(lens.nodes)&&typeof lens.rootRequirementId==='string'){
  check(lens.actionModel==='candidate-v6'&&lens.schemaVersion===1,
   'UNSUPPORTED_ORDINARY_GRAPH');
  validateOrdinaryLens(lens);
  if(lens.coreModel==='rdg-decision-v1')return {...structuredClone(lens),
   rootRequirement:structuredClone(lens.nodes.find(n=>n.id===lens.rootRequirementId)),
   requirements:lens.nodes.filter(n=>n.kind==='requirement'&&n.id!==lens.rootRequirementId),
   decisions:lens.nodes.filter(n=>n.kind==='decision'),actions:lens.nodes.filter(n=>n.kind==='action')};
  const root=lens.nodes.find(n=>n.id===lens.rootRequirementId&&n.kind==='requirement');
  const actions=lens.nodes.filter(n=>n.kind==='action').map(a=>({...structuredClone(a),
   reaches:lens.edges.filter(e=>['INTRODUCES','OUTCOME_OF'].includes(e.type)&&e.from===a.id&&
    e.archived!==true).map(e=>e.to)}));
  lens={id:lens.id,rootRequirement:root,coreModel:lens.coreModel,objects:structuredClone(lens.objects||[]),
   requirements:lens.nodes.filter(n=>n.kind==='requirement'&&n.id!==root?.id),
   actions,edges:lens.edges.filter(e=>e.archived!==true&&
    ['DRIVES','INTRODUCES','OUTCOME_OF'].includes(e.type))};
 }
 check(lens&&typeof lens==='object'&&typeof lens.id==='string'&&
  lens.rootRequirement?.id&&Array.isArray(lens.requirements)&&
  Array.isArray(lens.actions)&&Array.isArray(lens.edges),'PREPARED_GRAPH_REQUIRED');
 const nodes=[lens.rootRequirement,...lens.requirements,...lens.actions];
 const nodeIds=new Set(nodes.map(x=>x.id));
 check(nodes.length===nodeIds.size,'DUPLICATE_NODE');
 const reqs=new Set([lens.rootRequirement.id,...lens.requirements.map(r=>r.id)]);
 const acts=new Set(lens.actions.map(a=>a.id));
 const arcs=[];
 for(const edge of lens.edges){
  check(edge&&reqs.has(edge.from)&&acts.has(edge.to)&&edge.type==='DRIVES'||
       edge&&acts.has(edge.from)&&reqs.has(edge.to)&&['INTRODUCES','OUTCOME_OF'].includes(edge.type),
       'EDGE_KIND_OR_TARGET_INVALID');
  arcs.push([edge.from,edge.to]);
 }
 for(const act of lens.actions){
  check(lens.edges.some(e=>e.type==='DRIVES'&&e.to===act.id),'ACTION_UNREACHABLE');
  check(Array.isArray(act.reaches)&&act.reaches.every(r=>reqs.has(r)&&
   lens.edges.some(e=>['INTRODUCES','OUTCOME_OF'].includes(e.type)&&e.from===act.id&&e.to===r)),'ACTION_RESULTS_UNBOUND');
 }
 const visited=new Set(),active=new Set(),adj=new Map();
 for(const [f,t] of arcs){if(!adj.has(f))adj.set(f,[]);adj.get(f).push(t);}
 function visit(id){check(!active.has(id),'CYCLIC_GRAPH');if(visited.has(id))return;
  active.add(id);for(const to of adj.get(id)||[])visit(to);active.delete(id);visited.add(id);}
 visit(lens.rootRequirement.id);
 check(visited.size===nodeIds.size,'UNREACHABLE_NODES');
 return structuredClone(lens);
}
function createSession(lens,bindings,{canonAssessments=[],qrpeUpdates=[],requirementAssessments=[],
  rootAssessment=null}={}){
 const prepared=parsePreparedLens(lens);
 check(bindings&&typeof bindings==='object'&&typeof bindings.targetGraphId==='string'&&
  bindings.targetGraphId.trim()&&
  (bindings.targetActionId===undefined||bindings.targetActionId===null||
   typeof bindings.targetActionId==='string')&&
  bindings.relevantInputs&&typeof bindings.relevantInputs==='object'&&
  !Array.isArray(bindings.relevantInputs),'BINDINGS_REQUIRED');
 check(!prepared.coreModel||canonAssessments.length===0,'CORE_ASSESSMENT_REQUIRES_EXPLICIT_TYPED_WORKING_SITUATION');
 if(prepared.coreModel==='rdg-decision-v1'){
  check(canonAssessments.length===0&&qrpeUpdates.length===0&&requirementAssessments.length===0&&!rootAssessment,'DECISION_SESSION_READ_ONLY');
  return {kind:'working-lens-graph',schemaVersion:1,lensId:lens.id,definitionDigest:hash(lens),
   bindings:structuredClone(bindings),bindingDigest:hash(bindings.relevantInputs),rootRequirementId:lens.rootRequirementId,
   graph:structuredClone(lens),rootResult:'unknown',unresolvedQrpe:[],
   unassessedOrStaleCanons:lens.objects.filter(n=>n.kind==='canon').map(n=>n.id),
   materialGraphOperations:[],persisted:false};
 }
 const byAction=new Map(prepared.actions.map(a=>[a.id,a]));
 const byR=new Set([prepared.rootRequirement.id,...prepared.requirements.map(r=>r.id)]);
 const seenAssessment=new Set(),assessments=[];
 for(const entry of canonAssessments){
  const a=byAction.get(entry.actionId);
  check(a&&['applicable','inapplicable','unknown','stale'].includes(entry.result),
   'CANON_ACTION_OR_RESULT_INVALID');
  const cases=[...(a.canonBlock?.recommended||[]),...(a.canonBlock?.contraindicated||[])];
  check(cases.some(c=>c.id===entry.caseId),'CANON_CASE_UNKNOWN');
  const id=entry.actionId+'/'+entry.caseId;
  check(!seenAssessment.has(id),'CANON_DUPLICATED');seenAssessment.add(id);
  check(entry.result==='unknown'||entry.result==='stale'||
   (Array.isArray(entry.evidenceRefs)&&entry.evidenceRefs.length>0&&
   typeof entry.reason==='string'&&entry.reason.trim()),'CANON_EVIDENCE_REQUIRED');
  assessments.push(structuredClone(entry));
 }
 const byIssue=new Map();
 for(const a of prepared.actions)for(const issue of a.qrpe||[]){
  check(typeof issue.id==='string'&&!byIssue.has(a.id+'/'+issue.id),'DUPLICATE_QRPE');
  byIssue.set(a.id+'/'+issue.id,{action:a,issue});
 }
 for(const item of qrpeUpdates){
  const found=byIssue.get(item.actionId+'/'+item.issueId);
  check(found&&['open','resolved','accepted-risk'].includes(item.status),'QRPE_TARGET_OR_STATUS_INVALID');
  check(item.status==='open'||(Array.isArray(item.evidenceRefs)&&item.evidenceRefs.length&&
   typeof item.reason==='string'&&item.reason.trim()),'QRPE_RESOLUTION_EVIDENCE_REQUIRED');
  found.issue.status=item.status;
  if(item.reason)found.issue.reason=item.reason;
  if(item.evidenceRefs)found.issue.resolutionEvidenceRefs=structuredClone(item.evidenceRefs);
 }
 const byRReview=new Map();
 for(const r of requirementAssessments){
  check(byR.has(r.requirementId)&&['achieved','blocked','unknown','not_applicable'].includes(r.result),
   'REQUIREMENT_ASSESSMENT_INVALID');
  check(!byRReview.has(r.requirementId),'DUPLICATE_R_ASSESSMENT');
  check(r.result==='unknown'||r.result==='not_applicable'||
   (Array.isArray(r.evidenceRefs)&&r.evidenceRefs.length),'REQUIREMENT_EVIDENCE_REQUIRED');
  byRReview.set(r.requirementId,structuredClone(r));
 }
 let rootResult='unknown';
 if(rootAssessment){
  check(rootAssessment.requirementId===prepared.rootRequirement.id&&
   ['achieved','blocked','unknown'].includes(rootAssessment.result),'ROOT_ASSESSMENT_INVALID');
  check(rootAssessment.result!=='achieved'||
   (Array.isArray(rootAssessment.evidenceRefs)&&rootAssessment.evidenceRefs.length),
   'ROOT_EVIDENCE_REQUIRED');
  rootResult=rootAssessment.result;
 }
 // An explicit root result is still only the provided assessment, not a
 // machine-verified proof. Missing/unknown canons and unresolved QRPE block
 // a successful result unless an accountable qualified assessment explains it.
 const unresolved=[...byIssue].filter(([,v])=>['candidate','open'].includes(v.issue.status))
  .map(([ref])=>ref);
 const canonsUnknown=prepared.coreModel?prepared.objects.filter(n=>n.kind==='canon').flatMap(n=>n.arguments.map(a=>n.id+'/'+a.id)):prepared.actions.flatMap(a=>
  [...(a.canonBlock?.recommended||[]),...(a.canonBlock?.contraindicated||[])]
  .filter(c=>!seenAssessment.has(a.id+'/'+c.id) || assessments.some(x=>x.actionId===a.id&&
   x.caseId===c.id&&['unknown','stale'].includes(x.result))).map(c=>a.id+'/'+c.id));
 // Local assessment references are not independently authenticated evidence.
 // Until a real canon/QRPE verification contract exists, never turn a claimed
 // root achievement into a verified conclusion on this adapter alone.
 if(rootResult==='achieved'||rootResult==='blocked')rootResult='unknown';
 const result={kind:'working-lens-graph',schemaVersion:1,
  lensId:prepared.id,definitionDigest:hash(lens),
  bindings:structuredClone(bindings),bindingDigest:hash(bindings.relevantInputs),
  rootRequirementId:prepared.rootRequirement.id,
  graph:(Array.isArray(lens.nodes)?{...structuredClone(lens),
   nodes:lens.nodes.map(n=>n.kind==='action'&&byAction.has(n.id)?
    {...structuredClone(n),qrpe:structuredClone(byAction.get(n.id).qrpe||[])}:
    structuredClone(n))}:prepared),
  canonAssessments:assessments,requirementAssessments:[...byRReview.values()],
  rootAssessment:rootAssessment?structuredClone(rootAssessment):null,
  rootResult,unresolvedQrpe:unresolved,unassessedOrStaleCanons:canonsUnknown,
  materialGraphOperations:[], // via general Graph API, not here
  persisted:false};
 return result;
}
module.exports={canonical,hash,parsePreparedLens,createSession};
