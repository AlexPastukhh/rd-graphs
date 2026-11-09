const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const {simulate}=require('./viewer-test-helper.cjs');
const ROOT=path.resolve(__dirname,'..');
const fixture=name=>JSON.parse(fs.readFileSync(path.join(ROOT,'graphs/examples',name,'graph.json'),'utf8'));
const visible=ui=>ui.root.querySelectorAll('.node').map(n=>n.getAttribute('data-id'));
const click=(ui,id)=>ui.root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')===id)?.listeners.click({stopPropagation(){}});
test('promoted current R stays visible despite archived potential edge',async()=>{
  const g=fixture('reference-mixed-active-work');
  g.edges.push({id:'previous-potential',type:'OUTCOME_OF',from:'O-A',to:'R-ACT-1',archived:true});
  const ui=simulate();await ui.loadFile(g);assert(!visible(ui).includes('D-A'));click(ui,'R-COMP');await ui.flush();
  assert(visible(ui).includes('R-ACT-1'),'accepted child is shown in normal mode');
  // The undecided child owns its options in a separate R-root graph.
  const root=ui.root.querySelectorAll('.node').find(x=>x.getAttribute('data-id')==='R-ACT-1');
  assert(root,'chosen D still shows R-ACT-1');
  const linked=simulate({useBundle:true});
  await linked.flush();await linked.openLevel('reference-mixed-active-work','R-COMP');
  const jump=linked.root.querySelectorAll('.node').find(x=>x.getAttribute('data-id')==='R-ACT-1');
  assert(jump.classList.contains('drill'),'R-ACT-1 links to own planning graph');
  jump.listeners.click({stopPropagation(){}});await linked.flush();
  assert(visible(linked).includes('O-ACT-1'),'undecided child options remain visible in own graph');
});
test('a group containing an option is rejected because Collections list only Requirements',async()=>{
 const g=fixture('reference-prepared-planning-tree');
 g.collections.push({id:'INNER',title:'Invalid list',anchor:'RF-1',memberRefs:['RF-1-O1']});
 const ui=simulate();await ui.loadFile(g);assert.match(ui.text(),/должна содержать только R/);
});
test('inspector distinguishes prepared and situational options',async()=>{
  const g=fixture('reference-mixed-active-work');
  const opt=g.nodes.find(n=>n.id==='O-C');opt.title='Neutral';opt.origin='situational';
  const ui=simulate();await ui.loadFile(g);ui.ids['variants-all'].onclick();click(ui,'O-C');
  assert.match(ui.info(),/Происхождение: ситуативный/);
});
test('QRPE transitions and dependent invalidation retain prior state',()=>{
 const script=[
 'import importlib.machinery as m, json',
 "x=m.SourceFileLoader('w',"+JSON.stringify(path.join(ROOT,'tools/graph-apply.py'))+").load_module()",
 "g={'schemaVersion':1,'id':'r','revision':1,'rootRequirementId':'R','identitySpace':'review', 'nodes':[{'id':'R','kind':'requirement','title':'Root'},{'id':'R-TECH','kind':'requirement','title':'Tech','status':'active'}],'edges':[],'events':[]}",
 "o={'id':'O','kind':'option','title':'Option','origin':'situational','canonBlock':{'recommended':[{'id':'K','text':'Tech relevant','checkRequirements':['R-TECH']}],'contraindicated':[]}}",
 "ops=[{'op':'add_option','requirementId':'R','option':o},{'op':'append_qrpe','targetId':'O','issue':{'id':'Q','text':'Tech conflict','status':'open','ref':'R-TECH'}}]",
 "g,_=x.apply(g,{'schemaVersion':1,'expectedRevision':1,'operations':ops})",
 "g,_=x.apply(g,{'schemaVersion':1,'expectedRevision':2,'operations':[{'op':'transition_qrpe','targetId':'O','issueId':'Q','transition':{'id':'t2','status':'resolved','recordedAt':'2026-10-15','note':'reviewed evidence'}}]})",
 "issue=next(n for n in g['nodes'] if n['id']=='O')['qrpe'][0]",
 "assert issue['status']=='resolved' and [h['status'] for h in issue['statusHistory']]==['open','resolved']",
 "g,_=x.apply(g,{'schemaVersion':1,'expectedRevision':3,'operations':[{'op':'deactivate_requirement','requirementId':'R-TECH','event':{'id':'E','type':'requirement_deactivated','requirementId':'R-TECH','by':'user','note':'synthetic isolated test'}}]})",
 "option=next(n for n in g['nodes'] if n['id']=='O')",
 "assert option['needsReview'] is True and option['impactSources']==['E']",
 "print('OK transition and invalidation')"
 ].join('\n');
 const out=cp.spawnSync('python3',['-c',script],{encoding:'utf8'});
 assert.equal(out.status,0,out.stderr);assert.match(out.stdout,/OK transition/);
});
test('forged or missing prepared source is rejected by writer',()=>{
 const script=[
 'import importlib.machinery as m',
 "x=m.SourceFileLoader('w',"+JSON.stringify(path.join(ROOT,'tools/graph-apply.py'))+").load_module()",
 "g={'schemaVersion':1,'id':'r','revision':1,'nodes':[{'id':'R','kind':'requirement','title':'Root'}],'edges':[],'events':[]}",
 "o={'id':'O','kind':'option','title':'Fake prepared','origin':'prepared','status':'candidate','preparedSource':{'graphSlug':'missing-source','version':'1','sourceOptionId':'O','canonHash':'fake'},'canonBlock':{'recommended':[],'contraindicated':[]}}",
 "ops=[{'op':'add_option','requirementId':'R','option':o},{'op':'select_option','optionId':'O','driverId':'R','decision':{'id':'D','kind':'decision','title':'D','status':'committed'},'event':{'id':'E','type':'decision_selected','decisionId':'D','by':'user','note':'synthetic'}}]",
 'try:',
 " x.apply(g,{'schemaVersion':1,'expectedRevision':1,'operations':ops})",
 " raise AssertionError('forged source accepted')",
 'except ValueError as e:',
 " assert 'PREPARED_SOURCE_MISSING' in str(e), str(e)",
 "print('OK missing source rejected')"
 ].join('\n');
 const out=cp.spawnSync('python3',['-c',script],{encoding:'utf8'});
 assert.equal(out.status,0,out.stderr);assert.match(out.stdout,/OK missing source/);
});
test('T2 composite is the current project statement, not the T1 title',()=>{
 const script=[
 'import importlib.machinery as m',
 "w=m.SourceFileLoader('w',"+JSON.stringify(path.join(ROOT,'tools/graph-apply.py'))+").load_module()",
 "idx=m.SourceFileLoader('idx',"+JSON.stringify(path.join(ROOT,'tools/graph-index.py'))+").load_module()",
 "g={'schemaVersion':1,'id':'g','title':'Temporary','revision':1,'planningScale':'module','rootRequirementId':'R','identitySpace':'review-only', 'nodes':[{'id':'R','kind':'requirement','title':'Root'}],'edges':[],'events':[]}",
 "ops=[{'op':'add_composite','requirement':{'id':'RC','kind':'requirement','title':'T1','status':'candidate','compositeOf':'R','history':[{'id':'T1','recordedAt':'T1','statement':'T1','facts':[]}]}}]",
 "g,_=w.apply(g,{'schemaVersion':1,'expectedRevision':1,'operations':ops})",
 "g,_=w.apply(g,{'schemaVersion':1,'expectedRevision':2,'operations':[{'op':'append_composite_revision','requirementId':'RC','revision':{'id':'T2','recordedAt':'T2','statement':'T2','facts':[]}}]})",
 "next(n for n in g['nodes'] if n['id']=='RC')['status']='active'",
 "manifest,_=idx.build_catalog({'workspaces/try-it/graph.json':g})",
 "ctx=manifest['projectContexts']['review-only']['records']",
 "assert next(n for n in ctx if n['id']=='RC')['currentStatement']=='T2'",
 "assert next(n for n in ctx if n['id']=='RC')['title']=='T1'",
 "print('OK current statement retains historical title')"
 ].join('\n');
 const out=cp.spawnSync('python3',['-c',script],{encoding:'utf8'});
 assert.equal(out.status,0,out.stderr);assert.match(out.stdout,/OK current/);
});
test('two distinct scope names require explicit disjointness evidence',()=>{
 const script=[
 'import importlib.machinery as m',
 "w=m.SourceFileLoader('w',"+JSON.stringify(path.join(ROOT,'tools/graph-apply.py'))+").load_module()",
 "g={'schemaVersion':1,'id':'g','revision':1,'nodes':[{'id':'R','kind':'requirement','title':'Root'}],'edges':[],'events':[]}",
 "opt=lambda i:{'id':i,'kind':'option','title':i,'origin':'situational','canonBlock':{'recommended':[],'contraindicated':[]}}",
 "ops=[{'op':'add_option','requirementId':'R','option':opt('O1')},{'op':'add_option','requirementId':'R','option':opt('O2')}]",
 "g,_=w.apply(g,{'schemaVersion':1,'expectedRevision':1,'operations':ops})",
 "select=lambda i,s:{'op':'select_option','optionId':'O'+str(i),'driverId':'R','decision':{'id':'D'+str(i),'kind':'decision','title':'Answer','status':'committed','scope':s},'event':{'id':'E'+str(i),'type':'decision_selected','decisionId':'D'+str(i),'by':'user','note':'isolated synthetic test'}}",
 "g,_=w.apply(g,{'schemaVersion':1,'expectedRevision':2,'operations':[select(1,'mobile')]})",
 'try:',
 " w.apply(g,{'schemaVersion':1,'expectedRevision':3,'operations':[select(2,'mobile/app')]})",
 " raise AssertionError('overlap unknown accepted')",
 'except ValueError as e:',
 " assert 'SCOPE_OVERLAP' in str(e),str(e)",
 "print('OK overlapping scope needs explicit evidence')"
 ].join('\n');
 const out=cp.spawnSync('python3',['-c',script],{encoding:'utf8'});
 assert.equal(out.status,0,out.stderr);assert.match(out.stdout,/OK overlapping/);
});
test('project context flags cross-file options whose referenced R became inactive',()=>{
 const script=[
 'import importlib.machinery as m',
 "idx=m.SourceFileLoader('idx',"+JSON.stringify(path.join(ROOT,'tools/graph-index.py'))+").load_module()",
 "g=lambda slug,rid,nodes,edges: {'schemaVersion':1,'id':slug,'title':slug,'revision':1,'planningScale':'module','identitySpace':'one-project','rootRequirementId':rid,'nodes':nodes,'edges':edges,'events':[]}",
 "parent=g('review-parent','R0',[{'id':'R0','kind':'requirement','title':'Root'}, {'id':'R-TECH','kind':'requirement','title':'Changed tech','status':'inactive','active':False}],[])",
 "child=g('review-child','R1',[{'id':'R1','kind':'requirement','title':'Child'},{'id':'O1','kind':'option','title':'Choice','origin':'situational','canonBlock':{'recommended':[{'id':'K','text':'Check tech','checkRequirements':['R-TECH']}],'contraindicated':[]}}],[{'id':'E','type':'OPTION_FOR','from':'R1','to':'O1'}])",
 "catalog,_=idx.build_catalog({'workspaces/review-parent/graph.json':parent,'workspaces/review-child/graph.json':child})",
 "alerts=catalog['projectContexts']['one-project']['reviewAlerts']",
 "assert any(x['nodeId']=='O1' and x['sourceRequirementIds']==['R-TECH'] for x in alerts), alerts",
 "print('OK cross-file impact alert')"
 ].join('\n');
 const out=cp.spawnSync('python3',['-c',script],{encoding:'utf8'});
 assert.equal(out.status,0,out.stderr);assert.match(out.stdout,/OK cross-file/);
});
test('T2 composite revision triggers review of T1 decision and cross-file referenced option',()=>{
 const script=[
 'import importlib.machinery as m',
 "idx=m.SourceFileLoader('idx',"+JSON.stringify(path.join(ROOT,'tools/graph-index.py'))+").load_module()",
 "g=lambda slug,rid,nodes,edges,cols=[]:{'schemaVersion':1,'id':slug,'title':slug,'revision':2,'planningScale':'module','identitySpace':'project-t2','rootRequirementId':rid,'nodes':nodes,'edges':edges,'events':[],'collections':cols}",
 "r={'id':'R0','kind':'requirement','title':'Parent'}",
 "t1={'id':'T1','recordedAt':'T1','statement':'Initial constraints','facts':[]}",
 "t2={'id':'T2','recordedAt':'T2','statement':'New crosscutting constraint','facts':[]}",
 "comp={'id':'RC','kind':'requirement','title':'Initial constraints','compositeOf':'R0','status':'active','history':[t1,t2],'currentStatement':'New crosscutting constraint'}",
 "opt={'id':'O','kind':'option','title':'Choice','origin':'situational','canonBlock':{'recommended':[],'contraindicated':[]}}",
 "d={'id':'D','kind':'decision','title':'Selected','status':'committed','selectedOptionId':'O','selectionBasis':{'compositeSnapshot':{'id':'RC','history':[t1]}}}",
 "parent=g('parent','R0',[r,comp,opt,d],[{'id':'E1','type':'DERIVES','from':'R0','to':'RC'}, {'id':'E2','type':'OPTION_FOR','from':'R0','to':'O'},{'id':'E3','type':'DRIVES','from':'RC','to':'D'}])",
 "parent['events']=[{'id':'EV','type':'decision_selected','decisionId':'D','by':'user','note':'synthetic test'}]",
 "child=g('child','R1',[{'id':'R1','kind':'requirement','title':'Next'}, {'id':'O-NEXT','kind':'option','title':'Alternative','origin':'situational','canonBlock':{'recommended':[{'id':'canon','text':'Check parent','checkRequirements':['R0']}],'contraindicated':[]}}],[{'id':'E4','type':'OPTION_FOR','from':'R1','to':'O-NEXT'}])",
 "catalog,_=idx.build_catalog({'workspaces/parent/graph.json':parent,'workspaces/child/graph.json':child})",
 "alerts=catalog['projectContexts']['project-t2']['reviewAlerts']",
 "assert any(a['nodeId']=='D' and 'RC' in a['sourceRequirementIds'] for a in alerts),alerts",
 "assert any(a['nodeId']=='O-NEXT' and 'R0' in a['sourceRequirementIds'] for a in alerts),alerts",
 "print('OK T2 changes are review alerts, not decision revisions')"
 ].join('\n');
 const out=cp.spawnSync('python3',['-c',script],{encoding:'utf8'});
 assert.equal(out.status,0,out.stderr);assert.match(out.stdout,/OK T2/);
});
