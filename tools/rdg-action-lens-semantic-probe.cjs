'use strict';
// Read-only semantic rehearsal for RDG Action/Lens Candidate v6.
// NOT the graph-apply schema, not a general canon evaluator, not an authorized writer.
function lensFromFixture(fixture, id) {
  const lens=fixture.lensDefinitions.find(item=>item.id===id);
  if (!lens) throw new Error('Unknown lens: '+id);
  const rIds=new Set([lens.rootRequirement.id,...lens.requirements.map(r=>r.id)]);
  const aIds=new Set(lens.actions.map(a=>a.id));
  if (rIds.size!==lens.requirements.length+1 || aIds.size!==lens.actions.length) throw new Error('Duplicate local IDs');
  const edges=lens.edges||[];
  for (const a of lens.actions) {
    if (!a.reaches.every(id=>rIds.has(id))) throw new Error('Orphan action result: '+a.id);
    // Simple Actions are valid without canons or QRPE. Validate them only if provided.
    if (a.canonBlock!==undefined && (!a.canonBlock ||
      !Array.isArray(a.canonBlock.recommended) || !Array.isArray(a.canonBlock.contraindicated)))
      throw new Error('Malformed optional canonBlock: '+a.id);
    if (a.qrpe!==undefined && !Array.isArray(a.qrpe))
      throw new Error('Malformed optional QRPE: '+a.id);
    if (!edges.some(e=>e.type==='DRIVES' && e.to===a.id && rIds.has(e.from))) throw new Error('Unreachable action: '+a.id);
    for(const result of a.reaches)if(!edges.some(e=>e.type==='INTRODUCES' && e.from===a.id && e.to===result))
      throw new Error('Missing introduced result: '+a.id+' -> '+result);
  }
  const reachable=new Set([lens.rootRequirement.id]),queue=[lens.rootRequirement.id];
  while(queue.length) {
    const from=queue.shift();
    for(const edge of edges.filter(e=>e.from===from))if(!reachable.has(edge.to)) {
      reachable.add(edge.to);queue.push(edge.to);
    }
  }
  if([...rIds,...aIds].some(id=>!reachable.has(id))) throw new Error('Disconnected Lens graph');
  // No iteration contract in this pilot: reject structural cycles, not all future iteration.
  const inPath=new Set(),finished=new Set();
  function checkCycle(id) {
    if(inPath.has(id)) throw new Error('Unbounded cycle in candidate Lens graph');
    if(finished.has(id)) return;
    inPath.add(id);
    for(const edge of edges.filter(e=>e.from===id)) checkCycle(edge.to);
    inPath.delete(id);
    finished.add(id);
  }
  checkCycle(lens.rootRequirement.id);
  return lens;
}
function targetFromFixture(fixture,id) {
  const target=fixture.targets.find(t=>t.id===id);
  if (!target) throw new Error('Unknown target: '+id);
  return target;
}
function readOnlyDryCheck(fixture,targetId) {
  const lens=lensFromFixture(fixture,'L-DRY'),target=targetFromFixture(fixture,targetId);
  const requirements=target.requirements,seen=new Map(),duplicates=[];
  const missingInput=!Array.isArray(requirements) ||
    requirements.some(r=>typeof r.concept!=='string' || !r.concept.trim());
  const unverifiedEmpty=Array.isArray(requirements) && requirements.length===0 &&
    target.context?.requirementsScopeVerified!==true;
  const verifiedEmpty=Array.isArray(requirements) && requirements.length===0 &&
    target.context?.requirementsScopeVerified===true;

  if(!missingInput && !unverifiedEmpty && !verifiedEmpty) {
    for(const r of requirements) {
      const earlier=seen.get(r.concept);
      if(earlier) duplicates.push([earlier.id,r.id]);
      else seen.set(r.concept,r);
    }
  }
  // No same-value inference from missing concepts, and no success from an unverified empty scope.
  const inputUnknown=missingInput || unverifiedEmpty;
  const needsResearch=!inputUnknown && !verifiedEmpty && duplicates.length>0 &&
    target.context?.separateBehaviors!==true;
  const achieved=!inputUnknown && !verifiedEmpty && !needsResearch;
  const result=inputUnknown?'needs_input':verifiedEmpty?'not_applicable':
    needsResearch?'needs_duplicate_research':'no_material_duplicate';
  const qrpe=inputUnknown?[{questionId:'Q-DRY-INPUT',status:'open',
    reason:'Установить полноту области и признаки сравнения Requirements'}]:
    needsResearch?[{questionId:'Q-DRY-DIVERGE',status:'open',
      reason:'Проверить, оправдано ли объединение и какова цена'}]:[];
  return {lensId:lens.id,targetId,rootRequirementId:lens.rootRequirement.id,
    achieved,achievedRequirements:inputUnknown||verifiedEmpty?[]:
      needsResearch?['R-L-DRY-OBS']:['R-L-DRY-OBS','R-L-DRY-ASSESS'],
    performedActionIds:inputUnknown||verifiedEmpty?[]:['A-L-DRY-SCAN','A-L-DRY-ASSESS'],
    conditionalSkipped:['R-L-DRY-REMEDY'],
    blockedRequirements:inputUnknown?['R-L-DRY-OBS','R-L-DRY-ASSESS']:
      needsResearch?['R-L-DRY-ASSESS']:[],
    result,qrpe,
    suggestions:needsResearch?[{kind:'examine_duplicate',pairs:duplicates}]:[],
    graphWrites:0,
    report:inputUnknown?'Недостаточно данных о Requirements для оценки DRY.':
      verifiedEmpty?'Область подтверждённо пуста: проверка DRY неприменима.':
      needsResearch?'Найдены возможные повторы; цель оценки ещё не достигнута, QRPE открыто.':
      'DRY проверена, материальных повторов не обнаружено.'};
}
function readOnlyMaintenanceCheck(fixture,targetId) {
  const lens=lensFromFixture(fixture,'L-MAINT'),target=targetFromFixture(fixture,targetId);
  const selected=target.actions.find(a=>a.id==='A-OLD'&&a.status==='selected');
  const discovered=target.researchFindings?.find(f=>f.kind==='previously_untracked_action'&&f.action.id==='A-NEW');
  const candidate=discovered?.action;
  if(!selected || !candidate || target.actions.some(a=>a.id===candidate.id))
    throw new Error('Missing genuinely untracked alternative');
  const evidence=target.actionEvidence||{};
  const oldE=evidence[selected.id],newE=evidence[candidate.id];
  const sufficient=[oldE,newE].every(e=>e && e.stale!==true &&
    Number.isFinite(e.cost) && e.cost>=0 && typeof e.outcomeCovered==='boolean');
  // This is a toy comparator, NOT a generic canon evaluation.
  const better=sufficient && newE.outcomeCovered &&
    (!oldE.outcomeCovered || newE.cost<oldE.cost);
  const establishedKeep=sufficient && oldE.outcomeCovered && !better;
  const known=sufficient && (better || establishedKeep);
  const shared=selected.introduces.filter(id=>target.actions.some(a=>a.id!==selected.id&&a.status==='selected'&&a.introduces.includes(id)));
  const orphaned=selected.introduces.filter(id=>id!=='R-REPORT'&&!shared.includes(id));
  const result=!known?'needs_evidence':better?'propose_reconsideration':'keep_selected';
  return {lensId:lens.id,targetId,rootRequirementId:lens.rootRequirement.id,
    achieved:known,achievedRequirements:known?['R-L-MAINT-CAUSE','R-L-MAINT-ALTS']:
      ['R-L-MAINT-CAUSE'],
    performedActionIds:['A-L-MAINT-CHECK','A-L-MAINT-DISCOVER'],
    conditionalSkipped:['R-L-MAINT-CHANGE'],result,
    blockedRequirements:known?[]:['R-L-MAINT-ALTS'],
    suggestions:better?[{kind:'consider_new_action',actionId:candidate.id,oldActionId:selected.id},
      {kind:'review_orphaned_requirements',requirementIds:orphaned,sharedRequirements:shared,
       candidateLensActionId:'A-L-MAINT-REVOKE'}]:[],
    qrpe:!known?[{questionId:'Q-MAINT-ALTERNATIVE',status:'open',
      reason:'Недостаточно достоверных данных о стоимости и способности вариантов обеспечить результат'}]:
      better?[{questionId:'Q-MAINT-EFFECTS',status:'open'}]:[],
    graphWrites:0,report:!known?'Оценка выбора не завершена: нужны достоверные данные по вариантам.':
      better?'Есть перспективная альтернатива и вопросы о зависимостях; выбор не изменён.':
      'Обоснованно оставлен прежний способ в рамках доступных сравнительных данных.'};
}
// Illustrative in-memory transition only: deliberately not connected to graph-apply.
// The caller must explicitly authorize the transition; unknown effects are not simulated.
function simulateAuthorizedReconsideration(fixture,targetId,options={}) {
  lensFromFixture(fixture,'L-MAINT');
  if (options.authorized!==true) throw new Error('Authorization required to change selection');
  if (options.effect!=='replace_selected_action') throw new Error('Unsupported effect');
  if(!Array.isArray(options.reviewedQrpe)||!options.reviewedQrpe.includes('Q-MAINT-EFFECTS'))
    throw new Error('QRPE consequences must be reviewed before the illustrative change');
  if(typeof options.reason!=='string'||!options.reason.trim()) throw new Error('Reason required');
  const old=targetFromFixture(fixture,targetId);
  // Fixture-only safeguards. A real writer must independently verify delegated authority
  // and canons against versioned evidence; this flag is NOT a permission system.
  if(old.context?.approval!=='granted') throw new Error('Target context has not granted this illustrative change');
  if(readOnlyMaintenanceCheck(fixture,targetId).result!=='propose_reconsideration')
    throw new Error('Insufficient evidence to replace selected Action');
  const copy=structuredClone(old);
  const selected=copy.actions.find(a=>a.id==='A-OLD'&&a.status==='selected');
  const discovered=copy.researchFindings?.find(f=>f.kind==='previously_untracked_action'&&f.action.id==='A-NEW');
  if(!selected||!discovered||copy.actions.some(a=>a.id==='A-NEW'))
    throw new Error('Selected/discovered-action mismatch');
  // This append exists solely in the in-memory demonstration, never in a real writer.
  const alt={...structuredClone(discovered.action),status:'selected'};
  copy.actions.push(alt);
  selected.status='superseded';
  // Dependency check: a child requirement must survive if another selected A still needs it.
  const remaining=new Set(copy.actions.filter(a=>a.status==='selected').flatMap(a=>a.introduces));
  const inactive=selected.introduces.filter(id=>!remaining.has(id));
  for(const r of copy.requirements)if(inactive.includes(r.id))r.status='inactive';
  const event={type:'illustrative_selection_reconsidered',previousActionId:selected.id,
    selectedActionId:alt.id,inactiveRequirementIds:inactive,
    reviewedQrpeIds:options.reviewedQrpe,reason:options.reason,illustrative:true};
  return {target:copy,event,graphWrites:0,sourceUnchanged:true};
}
module.exports={lensFromFixture,targetFromFixture,readOnlyDryCheck,readOnlyMaintenanceCheck,simulateAuthorizedReconsideration};

