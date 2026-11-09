'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const P=require('../tools/rdg-visual-projection.js');
test('new Finding decisions reveal ancestors and type buckets without opening unrelated branches',()=>{
 const g=graph();g.nodes.push({id:'NEW',kind:'decision',title:'Resolve Finding',selectionState:'discovered'});
 g.edges.push({id:'FREL',type:'FINDING_RESPONSE',from:'D1',to:'NEW',findingId:'F1'});
 const v=view(g),before=JSON.stringify({g,v});
 const initial=P.decisionOutline(g,v);
 const r2=initial.rows.find(r=>r.entityId==='R2'),unrelated=initial.rows.find(r=>r.entityId==='R4');
 const collapsedPaths=['root:R1',r2.key,r2.sectionContext.key,unrelated.key];
 const reveal=P.decisionOutline(g,v,{collapsedPaths,revealEntityId:'NEW'});
 assert(reveal.rows.some(r=>r.entityId==='NEW'));
 assert(reveal.revealPaths.includes(r2.sectionContext.key),'hidden sibling bucket is reopened');
 assert(!reveal.revealPaths.includes(unrelated.key),'unrelated occurrence stays collapsed');
 const options={expandedPaths:reveal.revealPaths,collapsedPaths:collapsedPaths.filter(k=>!reveal.revealPaths.includes(k))};
 assert(P.decisionOutline(g,v,options).rows.some(r=>r.entityId==='NEW'),'returned keys persist the reveal');
 assert.equal(P.decisionOutline(g,v,{collapsedPaths}).rows.some(r=>r.entityId==='NEW'),false);
 assert.deepEqual(P.decisionOutline(g,v,{revealEntityId:'missing'}).revealPaths,[]);
 assert.equal(JSON.stringify({g,v}),before,'Graph and scope are unchanged');
});
const graph=()=>({id:'graph-struct',identitySpace:'11111111-1111-4111-8111-111111111111',revision:7,rootRequirementId:'R1',rootCauses:[{requirementId:'R1',enabled:true}],workGraphs:[
  {id:'WG1',title:'Only one view of the same objects',rootIds:['R2'],memberIds:['R2','D1','R4','A1','CTX1']}],
 nodes:[
  {id:'R1',kind:'requirement',title:'Root requirement'},
  {id:'R2',kind:'requirement',title:'First parent'},
  {id:'R3',kind:'requirement',title:'Second parent'},
  {id:'D1',kind:'decision',title:'Shared decision',selectionState:'selected',decisionContextIds:['CTX1','R2']},
  {id:'D2',kind:'decision',title:'Alternative',selectionState:'unselected'},
  {id:'R4',kind:'requirement',title:'Shared downstream requirement'},
  {id:'A1',kind:'action',title:'Actual action'}],
 objects:[{id:'CTX1',kind:'context',title:'One process fact'},{id:'CANON1',kind:'canon',title:'General guidance'},
  {id:'INFO1',kind:'info',title:'Canon-only reference'}],
 edges:[
  {id:'E1',type:'DERIVES',from:'R1',to:'R2'},
  {id:'E2',type:'DERIVES',from:'R1',to:'R3'},
  {id:'E3',type:'DRIVES',from:'R2',to:'D1'},
  {id:'E4',type:'DERIVES',from:'R2',to:'R4'},
  {id:'E5',type:'INTRODUCES',from:'D1',to:'R4'},
  {id:'E6',type:'REQUIRES_ACTION',from:'R4',to:'A1'},
  {id:'E7',type:'CANON_FOR',from:'CANON1',to:'D1'},
  {id:'E8',type:'INFO_FOR',from:'INFO1',to:'CANON1'}],
 decisionGroups:[{id:'G1',parentId:'R3',title:'Choose storage',selectionRequired:true,mutuallyExclusive:true,
   members:[{id:'GM1',decisionId:'D1'},{id:'GM2',decisionId:'D2'}]}]});
const view=(g,spec={kind:'graph'})=>{
 const allowed=new Set(spec.kind==='workGraph'?g.workGraphs.find(w=>w.id===spec.id).memberIds:
  spec.kind==='focus'?['R2','R3','D1','D2','R4','A1','CTX1','CANON1','INFO1']:
   [...g.nodes,...g.objects].map(n=>n.id));
 const groups=g.decisionGroups.map(group=>({...group,members:group.members.filter(m=>allowed.has(m.decisionId))}))
   .filter(group=>allowed.has(group.parentId)&&group.members.length);
 return {spec,entities:[...g.nodes,...g.objects].filter(n=>allowed.has(n.id)),
  edges:g.edges.filter(e=>allowed.has(e.from)&&allowed.has(e.to)),
  decisionGroups:groups,groupVisibility:groups.map(group=>({groupId:group.id,visibleIds:['D1'],hiddenIds:['D2']}))};
};
const rowsFor=(outline,id)=>outline.rows.filter(r=>r.type==='entity'&&r.entityId===id);

test('same shared Decision appears under multiple real parents with independent occurrence keys',()=>{
 const g=graph(),original=JSON.stringify(g),v=view(g),a=P.decisionOutline(g,v);
 assert.equal(a.graphId,g.id);assert.equal(a.identitySpace,g.identitySpace);
 assert.deepEqual(a.roots,['R1']);assert.equal(a.viewOnly,true);
 const duplicates=rowsFor(a,'D1');
 assert.equal(duplicates.length,2,'one occurrence under R2 DRIVES, one under R3 Group');
 assert.equal(new Set(duplicates.map(x=>x.key)).size,2);
 assert(duplicates.every(row=>row.multipleParents));
 assert.deepEqual(duplicates.map(r=>r.relation).sort(),['DECISION_MEMBER','DRIVES']);
 const group=duplicates.find(r=>r.relation==='DECISION_MEMBER').groupMemberships[0];
 assert.equal(group.title,'Choose storage');assert.equal(group.selectionRequired,true);
 assert.equal(group.mutuallyExclusive,true);assert.equal(group.selectedCount,1);
 assert.deepEqual(group.otherDecisions,[{id:'D2',title:'Alternative'}]);
 assert(!a.rows.some(r=>r.type==='group'),'Decision Group is a frame on Decision rows, not a separate DG row');
 assert(rowsFor(a,'D2').some(row=>row.excluded),'alternatives stay visible even if hidden by the graph renderer');
 assert(!a.rows.some(row=>row.type==='entity'&&row.entityId==='CANON1'),'Canon is available from the target inspector, not as a structure row');
 assert(!rowsFor(a,'INFO1').length,'Canon-only Info belongs in the Canon tab, not an orphan structure row');
 assert.equal(a.materialCount,1,'only the process Context remains in the materials section');
 const expandedMaterials=P.decisionOutline(g,v,{expandedPaths:['materials']});
 assert(!rowsFor(expandedMaterials,'CANON1').length);
 assert(!rowsFor(expandedMaterials,'INFO1').length);
 assert(!expandedMaterials.rows.some(row=>row.type==='section'&&row.section==='canon'));
 assert.equal(P.decisionOutline(g,v,{query:'General guidance'}).rows.length,0,'Canon is not searchable as a tree row');
 assert.equal(a.rows.find(row=>row.entityId==='D1').supplemental.decisionContext,2);
 assert.equal(JSON.stringify(g),original,'presentation has no Graph writes');
});

test('expanded type groups show bare entities and collapse into a single section row',()=>{
 const g=graph(),v=view(g),before=JSON.stringify(g);
 const expanded=P.decisionOutline(g,v);
 assert(!expanded.rows.some(r=>r.type==='section'&&r.section!=='parents'),
   'expanded type buckets are hidden; they are only view grouping');
 assert(!expanded.rows.some(r=>r.type==='materials'),'Mat wrapper is not needed around actual Context/Info/Evidence');
 const parent=rowsFor(expanded,'R1')[0],r2=rowsFor(expanded,'R2')[0],r3=rowsFor(expanded,'R3')[0];
 assert.equal(r2.depth,parent.depth+1);
 assert.equal(r3.depth,parent.depth+1);
 const group=r2.sectionContext;
 assert(group&&group.expanded&&group.section==='requirements'&&group.count===2);
 assert.deepEqual(r3.sectionContext,group,'right-click collapse is available from EVERY sibling, not only first');
 assert.equal(group.title,'Обязательные требования');
 assert(expanded.rows.every(r=>!Object.hasOwn(r,'sectionToggle')),'obsolete protruding control metadata is absent');
 const collapsed=P.decisionOutline(g,v,{collapsedPaths:[group.key]});
 const section=collapsed.rows.find(r=>r.type==='section'&&r.key===group.key);
 assert(section&&!section.expanded&&section.count===2);
 assert.equal(section.depth,r2.depth);
 assert.equal(rowsFor(collapsed,'R2').length,0);
 assert.equal(rowsFor(collapsed,'R3').length,0);
 assert.equal(rowsFor(collapsed,'R1').length,1);
 const reopened=P.decisionOutline(g,v,{collapsedPaths:[group.key],expandedPaths:[group.key]});
 assert.equal(reopened.rows.some(r=>r.key===group.key&&r.type==='section'),false);
 assert(rowsFor(reopened,'R2').length&&rowsFor(reopened,'R3').length);
 assert.equal(rowsFor(reopened,'R3')[0].sectionContext.key,group.key,'context-menu group key survives collapse/reopen on any sibling');
 assert(rowsFor(expanded,'R4').some(r=>r.relation==='DERIVES'&&!r.sectionContext),
   'one-member Requirement group has no wrapper or group control');
 assert(rowsFor(expanded,'A1').every(r=>!r.sectionContext),
   'one-member Action group has no extra control');
 assert(rowsFor(expanded,'D2').some(r=>r.groupMemberships.some(g=>g.id==='G1')),
   'real Decision Group remains visible as a membership frame on Decisions');
 assert(!expanded.rows.some(r=>r.type==='section'&&r.section==='groups'));
 assert.equal(rowsFor(expanded,'CTX1').length,1);
 assert(!rowsFor(expanded,'CTX1')[0].sectionContext,'single process Context has no group control');
 assert.deepEqual(expanded.repeatedIds.sort(),reopened.repeatedIds.sort(),
   'type collapse is presentation-only, not an ownership or occurrence rewrite');
 assert.equal(JSON.stringify(g),before,'group collapse does not mutate graph data');
});

test('overlapping groups decorate one Decision occurrence per parent, preserving every group and peer',()=>{
 const g=graph(),source=JSON.stringify(g);
 g.decisionGroups.push({id:'G2',parentId:'R3',title:'Optional common choices',selectionRequired:false,
  mutuallyExclusive:false,members:[{id:'GM3',decisionId:'D1'},{id:'GM4',decisionId:'D2'}]});
 g.decisionGroups.push({id:'G3',parentId:'R3',title:'Required shared',selectionRequired:true,
  mutuallyExclusive:false,members:[{id:'GM5',decisionId:'D1'}]});
 const before=JSON.stringify(g),out=P.decisionOutline(g,view(g));
 const d1=rowsFor(out,'D1'),d2=rowsFor(out,'D2');
 assert.equal(d1.length,2,'one under DRIVES parent R2 and one under all three groups of R3');
 assert.equal(d2.length,1,'same-parent multiple group memberships must not multiply an owner Decision');
 assert.equal(new Set(d1.map(r=>r.key)).size,2);
 assert.equal(d1.filter(r=>r.relation==='DECISION_MEMBER').length,1);
 for(const row of d1)assert.deepEqual(row.groupMemberships.map(m=>m.id),['G1','G2','G3'],
  'every Decision occurrence displays all its group memberships, even outside its local parent');
 assert.deepEqual(d2[0].groupMemberships.map(m=>m.id),['G1','G2']);
 assert.equal(d1[0].multipleParents,true,'multiple groups from R3 count as one structural parent');
 const g1=d1[0].groupMemberships[0],g2=d1[0].groupMemberships[1],g3=d1[0].groupMemberships[2];
 assert.equal(g1.parentTitle,'Second parent');
 assert.deepEqual(g1.otherDecisions,[{id:'D2',title:'Alternative'}]);
 assert.equal(g1.mutuallyExclusive,true);assert.equal(g1.selectionRequired,true);
 assert.equal(g2.mutuallyExclusive,false);assert.equal(g2.selectionRequired,false);
 assert.equal(g3.mutuallyExclusive,false);assert.equal(g3.selectionRequired,true);
 assert.deepEqual(g3.otherDecisions,[]);
 assert(!out.rows.some(row=>row.type==='group'),'all group outlines belong to real D occurrences');
 const onlyGroup=P.decisionOutline(g,view(g),{query:'Optional common choices'});
 assert(rowsFor(onlyGroup,'D1').length&&rowsFor(onlyGroup,'D2').length,
  'search for a group finds both peers without recreating a DG entity');
 const work=P.decisionOutline(g,view(g,{kind:'workGraph',id:'WG1'}));
 assert.deepEqual(rowsFor(work,'D1')[0].groupMemberships.map(x=>x.id),['G1','G2','G3'],
  'the same Decision still reports all groups when their parent is outside the Work Graph');
 const focus=P.decisionOutline(g,view(g,{kind:'focus',id:'D1'}));
 assert.deepEqual(rowsFor(focus,'D1')[0].groupMemberships.map(x=>x.id),['G1','G2','G3']);
 assert.equal(JSON.stringify(g),before,'membership outlines never mutate owner data');
 assert.notEqual(JSON.stringify(g),source,'test fixture adds three-group overlap');
});

test('two process context objects behave like all other collapsible type buckets',()=>{
 const g=graph();g.objects.push({id:'CTX2',kind:'context',title:'Second process fact'});
 const v=view(g),open=P.decisionOutline(g,v);
 const contexts=open.rows.filter(r=>r.type==='entity'&&r.kind==='context');
 assert.equal(contexts.length,2);
 assert.equal(contexts[0].depth,1);
 assert(contexts[0].sectionContext&&contexts[0].sectionContext.section==='context');
 assert.deepEqual(contexts[1].sectionContext,contexts[0].sectionContext,'context menu works from second context too');
 const key=contexts[0].sectionContext.key;
 const closed=P.decisionOutline(g,v,{collapsedPaths:[key]});
 assert.equal(closed.rows.filter(r=>r.type==='section'&&r.section==='context'&&!r.expanded).length,1);
 assert.equal(closed.rows.filter(r=>r.type==='entity'&&r.kind==='context').length,0);
 const search=P.decisionOutline(g,v,{query:'Second process fact',collapsedPaths:[key]});
 assert.deepEqual(rowsFor(search,'CTX2').map(r=>r.entityId),['CTX2'],
   'a search temporarily opens collapsed type groups');
 assert(!search.rows.some(r=>r.type==='section'&&r.section==='context'));
});

test('multiple goals share one Decision identity and multiple Decisions share one Requirement identity',()=>{
 const g={id:'multi-parent-graph',identitySpace:'multi-parent-space',revision:1,rootRequirementId:'R1',
  workGraphs:[],nodes:[
   {id:'R1',kind:'requirement',title:'Goal one'},
   {id:'R2',kind:'requirement',title:'Goal two'},
   {id:'D1',kind:'decision',title:'One shared decision',selectionState:'discovered'},
   {id:'D2',kind:'decision',title:'Second decision',selectionState:'discovered'},
   {id:'R3',kind:'requirement',title:'One shared requirement'}],objects:[],
  edges:[
   {id:'E1',type:'DRIVES',from:'R1',to:'D1'},
   {id:'E2',type:'DRIVES',from:'R2',to:'D1'},
   {id:'E3',type:'DERIVES',from:'R1',to:'R3'},
   {id:'E4',type:'INTRODUCES',from:'D1',to:'R3'},
   {id:'E5',type:'INTRODUCES',from:'D2',to:'R3'}],decisionGroups:[]};
 const before=JSON.stringify(g),v={spec:{kind:'graph'},entities:g.nodes,edges:g.edges,decisionGroups:[],groupVisibility:[]};
 const out=P.decisionOutline(g,v),decisions=rowsFor(out,'D1'),requirements=rowsFor(out,'R3');
 assert.equal(decisions.length,2,'the same Decision is shown under both real DRIVES parents');
 assert.equal(new Set(decisions.map(r=>r.key)).size,2);
 assert(decisions.every(r=>r.entityId==='D1'&&r.multipleParents&&r.relation==='DRIVES'));
 assert.equal(requirements.length,4,'the shared Requirement is repeated under its goal, both presentations of D1, and D2');
 assert.equal(new Set(requirements.map(r=>r.key)).size,4);
 assert(requirements.every(r=>r.entityId==='R3'&&r.multipleParents));
 assert.deepEqual(requirements.map(r=>r.relation).sort(),['DERIVES','INTRODUCES','INTRODUCES','INTRODUCES']);
 assert.equal(JSON.stringify(g),before,'multiple parent occurrences are a read-only projection');
});

test('expand each occurrence independently; same downstream requirement uses same identity',()=>{
 const g=graph(),v=view(g),base=P.decisionOutline(g,v);
 const occurrences=rowsFor(base,'D1');assert.equal(occurrences.length,2);
 const one=P.decisionOutline(g,v,{expandedPaths:[occurrences[0].key]});
 assert.equal(rowsFor(one,'R4').length,2,'one direct R2 path and one opened D1 path');
 assert.equal(rowsFor(one,'D1').filter(n=>n.expanded).length,1);
 const two=P.decisionOutline(g,v,{expandedPaths:occurrences.map(n=>n.key)});
 assert.equal(rowsFor(two,'R4').length,3,'the shared child also occurs under both D1 presentations');
 assert.equal(new Set(rowsFor(two,'R4').map(n=>n.key)).size,3);
 assert.equal(new Set(rowsFor(two,'R4').map(n=>n.entityId)).size,1);
 const closed=P.decisionOutline(g,v,{expandedPaths:[occurrences[1].key],collapsedPaths:[occurrences[0].key]});
 assert.equal(rowsFor(closed,'R4').length,2,'closing one branch leaves the other open');
});

test('search finds all structural parent paths and group members without showing unrelated siblings',()=>{
 const g=graph(),v=view(g),source=JSON.stringify(g);
 const filtered=P.decisionOutline(g,v,{query:'Alternative'});
 assert.deepEqual(rowsFor(filtered,'D2').map(x=>x.entityId),['D2']);
 assert.equal(rowsFor(filtered,'D1').length,0,'unrelated option must not appear under the same group');
 assert(rowsFor(filtered,'R1').length&&rowsFor(filtered,'R3').length,'keep matching ancestor path');
 assert(rowsFor(filtered,'D2')[0].groupMemberships.some(g=>g.id==='G1'));
 const groupFiltered=P.decisionOutline(g,v,{query:'Choose storage'});
 assert.equal(rowsFor(groupFiltered,'D1').length,2,'all true parents remain visible even on a group-title search');
 assert.equal(rowsFor(groupFiltered,'D2').length,1);
 const nested=P.decisionOutline(g,v,{query:'Shared downstream requirement'});
 assert(rowsFor(nested,'R4').length>=3,'match visible under each true parent path');
 assert.equal(JSON.stringify(g),source);
});

test('work-area outline contains exactly the same owner-local nodes, no duplicated owner or external parent',()=>{
 const g=graph(),v=view(g,{kind:'workGraph',id:'WG1'}),before=JSON.stringify(g),out=P.decisionOutline(g,v);
 assert.equal(out.roots[0],'R2');
 assert.equal(out.structuralCount,4);assert.equal(out.materialCount,1);
 assert.equal(out.graphId,g.id);assert.equal(out.identitySpace,g.identitySpace);
 assert(!rowsFor(out,'R1').length);assert(!rowsFor(out,'R3').length);
 assert.equal(rowsFor(out,'D1').length,1);
 assert.deepEqual(rowsFor(out,'D1')[0].outsideParentIds,['R3'],'parent outside work area is still acknowledged');
 const expanded=P.decisionOutline(g,v,{expandedPaths:[rowsFor(out,'D1')[0].key]});
 assert(rowsFor(expanded,'R4').length>=2);
 assert.equal(JSON.stringify(g),before);
});

test('focus R/D presents direct parent references before one focused tree, while process outline repeats shared IDs',()=>{
 const g=graph(),unchanged=JSON.stringify(g);
 const decision=P.decisionOutline(g,view(g,{kind:'focus',id:'D1'}));
 assert.deepEqual(decision.roots,['D1'],'focus has one real root');
 assert.equal(rowsFor(decision,'D1').length,1,'same focused Decision is not repeated for its two parents');
 assert.equal(decision.rows.filter(row=>row.parentRef).length,2);
 assert.deepEqual(decision.rows.filter(row=>row.parentRef).map(row=>row.entityId).sort(),['R2','R3']);
 assert(decision.rows.filter(row=>row.parentRef).every(row=>row.kind==='requirement'&&!row.hasChildren&&row.depth===1));
 assert.deepEqual(decision.rows.find(row=>row.parentRef&&row.entityId==='R2').parentRelations,['DRIVES']);
 assert.deepEqual(decision.rows.find(row=>row.parentRef&&row.entityId==='R3').parentRelations,['DECISION_MEMBER']);
 assert(decision.rows.find(row=>row.parentRef&&row.entityId==='R3').parentGroups.includes('Choose storage'));
 assert.equal(decision.rows.findIndex(row=>row.parentRef)<decision.rows.findIndex(row=>row.entityId==='D1'),true);
 assert.equal(rowsFor(decision,'R4').length,1,'shared descendant must not duplicate in focus');
 assert(rowsFor(decision,'CTX1').length===1,'process Context is a direct material row with no expanded Mat wrapper');

 const requirement=P.decisionOutline(g,view(g,{kind:'focus',id:'R4'}));
 assert.deepEqual(requirement.roots,['R4']);
 assert.equal(rowsFor(requirement,'R4').length,1);
 assert.deepEqual(requirement.rows.filter(row=>row.parentRef).map(row=>[row.entityId,row.kind,row.parentRelations.join(',')]).sort(),
  [['D1','decision','INTRODUCES'],['R2','requirement','DERIVES']]);
 assert(requirement.rows.some(row=>row.entityId==='A1'&&row.type==='entity'&&!row.parentRef),
  'children of a focused Requirement still appear once below its own tree');
 const parentless=P.decisionOutline(g,view(g,{kind:'focus',id:'R2'}));
 assert(!parentless.rows.some(row=>row.parentRef));
 assert.equal(rowsFor(parentless,'R4').length,1,'focus never clones a shared downstream requirement');
 assert.equal(JSON.stringify(g),unchanged,'parent references do not alter owner Graph or relationship identity');
});

test('full process occurrences and malformed cycles keep their existing safe behavior',()=>{
 const g=graph();
 g.edges.push({id:'CYCLE1',type:'DRIVES',from:'R4',to:'D1'});
 const first=P.decisionOutline(g,view(g));
 const expandedPaths=first.rows.filter(row=>row.type==='entity').map(row=>row.key);
 const second=P.decisionOutline(g,view(g),{expandedPaths,maxRows:120});
 assert.equal(second.viewOnly,true);assert(second.rows.length<=120);
 assert(!second.rows.some(row=>row.cycle&&row.expanded),'a path may never recursively expand itself');
});

test('outline encodes nesting exclusively with row.depth and never emits decorative connectors',()=>{
 const g={id:'indent-fixture',identitySpace:'indent-test',revision:1,rootRequirementId:'R1',rootCauses:[{requirementId:'R1',enabled:true}],workGraphs:[],
  nodes:[{id:'R1',kind:'requirement',title:'root'},
   {id:'R2',kind:'requirement',title:'branch A'},
   {id:'R3',kind:'requirement',title:'branch B'},
   {id:'D1',kind:'decision',title:'PostgreSQL'},
   {id:'D2',kind:'decision',title:'SQLite'},
   {id:'R4',kind:'requirement',title:'nested'}],
  objects:[],edges:[
   {id:'E1',type:'DERIVES',from:'R1',to:'R2'},
   {id:'E2',type:'DERIVES',from:'R1',to:'R3'},
   {id:'E3',type:'INTRODUCES',from:'D1',to:'R4'}],
  decisionGroups:[{id:'G1',parentId:'R2',title:'Options',selectionRequired:true,mutuallyExclusive:true,
   members:[{id:'GM1',decisionId:'D1'},{id:'GM2',decisionId:'D2'}]}]};
 const before=JSON.stringify(g),v=view(g),base=P.decisionOutline(g,v);
 const open=P.decisionOutline(g,v,{expandedPaths:[rowsFor(base,'D1')[0].key]});
 const item=(out,id)=>rowsFor(out,id)[0];
 assert.equal(item(open,'R1').depth,0);
 assert.equal(item(open,'R2').depth,1);
 assert.equal(item(open,'R3').depth,1);
 assert.equal(item(open,'D1').depth,2);
 assert.equal(item(open,'D2').depth,2);
 assert.equal(item(open,'R4').depth,3);
 assert(item(open,'D1').groupMemberships.some(m=>m.id==='G1'));
 assert(open.rows.every(row=>!Object.hasOwn(row,'siblingGuides')),
  'even interrupted siblings and nested children must have no line metadata');
 const closed=P.decisionOutline(g,v,{collapsedPaths:[item(open,'D1').key]});
 assert(!closed.rows.some(row=>row.entityId==='R4'),'collapsed Decision hides its descendants');
 assert.equal(item(closed,'D2').depth,2,'sibling identity and depth do not shift on collapse');
 const grouped=P.decisionOutline(g,v,{collapsedPaths:[item(open,'R2').key]});
 assert(grouped.rows.every(row=>!Object.hasOwn(row,'siblingGuides')));
 assert.equal(JSON.stringify(g),before,'read-only outline never edits Graph');
});

test('process context bank projection omits Ctx from all tree scopes but preserves canonical IDs and Decision references',()=>{
 const g=graph();
 g.objects.push({id:'CTX2',kind:'context',title:'Another process-wide fact'});
 const before=JSON.stringify(g);
 for(const spec of [{kind:'graph'},{kind:'workGraph',id:'WG1'},{kind:'focus',id:'D1'}]){
  const v=view(g,spec),normal=P.decisionOutline(g,v);
  const bank=P.decisionOutline(g,v,{hideProcessContexts:true});
  assert(bank.rows.every(row=>row.kind!=='context'&&row.section!=='context'),spec.kind+' omits Ctx');
  assert(bank.materialCount===normal.materialCount-
   normal.rows.filter(row=>row.kind==='context').length || bank.materialCount<normal.materialCount,
   'only process Ctx materials disappear from Structure');
  assert(bank.rows.some(row=>row.entityId==='D1')||spec.kind==='workGraph');
  const d=bank.rows.find(row=>row.entityId==='D1');
  if(d)assert.equal(d.supplemental?.decisionContext,2,
   'Decision references remain visible as metadata, without fabricating parents or destroying Ctx');
 }
 assert.deepEqual(g.nodes.find(n=>n.id==='D1').decisionContextIds,['CTX1','R2']);
 assert.equal(g.objects.filter(n=>n.kind==='context').length,2);
 assert.equal(JSON.stringify(g),before,'read-only bank projection preserves owner Graph');
});

test('Finding response/proposal composition is the same identity in graph and structure',()=>{
 const g=graph();g.nodes.push({id:'RES',kind:'decision',title:'Finding response',selectionState:'discovered'},{id:'PROP',kind:'decision',title:'Finding proposal',selectionState:'discovered'});
 g.objects.push({id:'F',kind:'finding',title:'Finding problem',subjectId:'D1',findingType:'problem'});
 g.edges.push({id:'FR',type:'FINDING_RESPONSE',from:'D1',to:'RES',findingId:'F'},{id:'FP',type:'FINDING_PROPOSAL',from:'RES',to:'PROP',findingId:'F'},{id:'FC',type:'DEPENDS_ON',from:'F',to:'PROP',dependencyPurpose:'decisionContext',dependencyLevel:'L1'});
 const before=JSON.stringify(g),v=view(g),outline=P.decisionOutline(g,v,{query:'Finding'});
 const res=rowsFor(outline,'RES'),props=rowsFor(outline,'PROP');assert(res.length>0&&props.length>0);
 assert(res.every(r=>r.relation==='FINDING_RESPONSE'));assert(props.every(r=>r.relation==='FINDING_PROPOSAL'));
 assert(props.every(r=>r.selectionState==='discovered'));assert.equal(rowsFor(outline,'F').length,0);
 const picture=P.decisionProject(g,v,{positions:Object.fromEntries(v.entities.map((n,i)=>[n.id,{x:i*20,y:i*20}]))});
 assert(picture.nodes.some(n=>n.entityId==='RES'));assert(picture.nodes.some(n=>n.entityId==='PROP'));assert(!picture.nodes.some(n=>n.entityId==='F'));
 assert.equal(JSON.stringify(g),before,'both projections are read-only');
});


test('process context groups preserve real IDs, paths, fold state and read-only search',()=>{
 const g=graph();g.contextGroups=[{id:'TOP',title:'Сроки',parentId:null},{id:'CHILD',title:'Дедлайны',parentId:'TOP'},{id:'EMPTY',title:'Пустая',parentId:null}];
 g.objects.find(n=>n.id==='CTX1').contextGroupId='CHILD';const before=JSON.stringify(g);
 const closed=P.contextTree(g,{collapsedIds:['TOP']});assert(!closed.some(r=>r.id==='CTX1'));assert(closed.some(r=>r.id==='EMPTY'));
 const found=P.contextTree(g,{collapsedIds:['TOP'],query:'Сроки'});const ctx=found.find(r=>r.id==='CTX1');assert.equal(ctx.path,'Сроки / Дедлайны');assert.equal(ctx.depth,2);assert.equal(found.filter(r=>r.id==='CTX1').length,1);
 assert(P.contextTree(g,{query:'One process fact'}).some(r=>r.id==='TOP'));assert(!P.contextTree(g,{collapsedIds:['TOP']}).some(r=>r.id==='CTX1'));
 assert.equal(JSON.stringify(g),before);
});

test('Findings and legacy Evidence are inspector or bank data in every Decision projection',()=>{
 const g=graph();g.objects.push({id:'F',kind:'finding',title:'Challenge',subjectId:'D1'},{id:'EV',kind:'evidence',title:'Recorded observation',claim:'Actual data'});
 g.edges.push({id:'EF',type:'EVIDENCE_FOR',from:'EV',to:'F'});
 const before=JSON.stringify(g);
 for(const kind of ['graph','workGraph','focus']){
  const v=view(g);v.spec={kind,...(kind==='focus'?{id:'D1'}:{}),showAllBlocks:true};
  const picture=P.decisionProject(g,v,{});const outline=P.decisionOutline(g,v,{hideProcessContexts:true});
  assert(!picture.nodes.some(n=>['F','EV'].includes(n.entityId)));assert(!outline.rows.some(n=>['F','EV'].includes(n.entityId)));
 }
 assert.equal(JSON.stringify(g),before);assert(g.objects.some(n=>n.id==='F'));
});
