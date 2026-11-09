#!/usr/bin/env python3
"""Decision analysis/context organization acceptance in disposable pure Graphs."""
import copy
import json
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from importlib.machinery import SourceFileLoader
ROOT=Path(__file__).resolve().parents[1]
K=SourceFileLoader('analysis_test_kernel',str(ROOT/'tools/rdg-decision-model.py')).load_module()
P=SourceFileLoader('analysis_test_copy',str(ROOT/'tools/rdg-portable-model.py')).load_module()

class Analysis(unittest.TestCase):
 def setUp(self):
  self.g=K.blank('G','Analysis',str(uuid.uuid4()),'R','Goal','Scope',root_reason='Synthetic test')
  self.add('D','decision',relations=[{'id':'RD','type':'DRIVES','from':'R','to':'D'}])
  self.add('X','context',value='100')
 def do(self,cmd,data):
  before=copy.deepcopy(self.g);event={'id':str(uuid.uuid4()),'by':'assistant','note':'Synthetic acceptance','recordedAt':'2026-11-06T00:00:00Z','verifiedTrustReceipt':{'mode':'test-only','transactionId':str(uuid.uuid4())}}
  if cmd=='review':event['reviewPinContext']={'packageId':str(uuid.uuid4()),'graphRevision':self.g['revision'],'sha256':K._digest(self.g)}
  try:self.g,_=K.apply(self.g,{'schemaVersion':1,'expectedRevision':self.g['revision'],'operations':[{'op':'graph_edit','action':'core_'+cmd,'data':data,'event':event}]},True,coordinated=True)
  except Exception:self.assertEqual(self.g,before);raise
  return self.g['events'][-1]
 def add(self,i,kind,relations=None,**v):
  node={'id':i,'kind':kind,'title':i,'description':'Synthetic',**v}
  if kind=='requirement':node.setdefault('scope','Scope')
  if kind=='action':node.update(actionType='task',lowLevel=False,targetIds=[],groupIds=[])
  self.do('add',{'entity':node,**({'initialRelations':relations} if relations else {})})
 def finding(self,i='F',subject='D'):
  self.add(i,'finding',subjectId=subject,findingType='risk',rationale='Plausible mechanism',evidenceIds=[])
 def dep(self,f='F',source='X'):
  self.do('link',{'relation':{'id':source+f,'type':'DEPENDS_ON','from':source,'to':f,'dependencyLevel':'L1'}})
 def group(self,i,parent=None):self.do('context_group',{'action':'save','id':i,'title':i,'parentId':parent})
 def rows(self):return K.decision_context(self.g,'D')
 def test_legacy_finding_can_be_explicitly_transferred_without_changing_id(self):
  self.finding();f=K.entities(self.g)['F'];r=K.entities(self.g)['R'];f['subjectId']='R';f['subjectSnapshot']={k:r[k] for k in ('id','kind','title','revision')};K.validate(self.g)
  before=copy.deepcopy(self.g);K.validate(self.g);self.assertEqual(self.g,before)
  ev=self.do('finding_transfer',{'nodeId':'F','subjectId':'D'});f=K.entities(self.g)['F'];self.assertEqual(f['id'],'F');self.assertEqual(f['subjectId'],'D');self.assertTrue(f['review']['required']);self.assertEqual(ev['findingChange']['before']['subjectId'],'R')

 def test_legacy_transfer_detaches_only_with_explicit_consent_and_keeps_decisions(self):
  old=SourceFileLoader('analysis_legacy_fixture',str(ROOT/'tests/rdg-findings.test.py')).load_module();fixture=old.Findings();fixture.setUp();fixture.finding();fixture.response();fixture.proposal();fixture.review_all();fixture.do('select',{'nodeId':'RES'});fixture.review_all();fixture.do('select',{'nodeId':'PROP'})
  self.g=copy.deepcopy(fixture.g);self.add('NEW','decision',relations=[{'id':'NEW-BASIS','type':'DRIVES','from':'R','to':'NEW'}])
  with self.assertRaisesRegex(ValueError,'LEGACY_FINDING_COMPOSITION_REQUIRES_UNLINK'):self.do('finding_transfer',{'nodeId':'F','subjectId':'NEW'})
  self.do('finding_transfer',{'nodeId':'F','subjectId':'NEW','detachLegacy':True})
  self.assertTrue({'F','RES','PROP'}<=set(K.entities(self.g)));self.assertEqual(K.entities(self.g)['F']['subjectId'],'NEW');self.assertFalse(any(e.get('findingId')=='F' for e in self.g['edges']));self.assertEqual(K.entities(self.g)['RES']['selectionState'],'unselected');self.assertTrue(K.entities(self.g)['PROP']['findingOrigin']['recordedOnly'])

 def test_only_decision_accepts_new_findings(self):
  self.add('A','action')
  for subject in ('R','A'):
   with self.assertRaisesRegex(ValueError,'FINDING_SUBJECT_REQUIRED'):self.finding('BAD',subject)
  for typ in K.FINDINGS.TYPES:self.add('F-'+typ,'finding',subjectId='D',findingType=typ,rationale='Material',evidenceIds=[])
 def test_retired_workflow_rejected_in_writer_and_new_link(self):
  self.finding()
  for cmd in ('finding_response','finding_proposal'):
   self.assertNotIn(cmd,K.COMMANDS)
   with self.assertRaisesRegex(ValueError,'OPERATION_REQUIRED'):self.do(cmd,{'findingId':'F','decisionId':'BAD','title':'Bad'})
  self.add('D2','decision')
  with self.assertRaisesRegex(ValueError,'FINDING_WORKFLOW_RETIRED'):self.do('link',{'relation':{'id':'BAD','type':'FINDING_RESPONSE','from':'D','to':'D2','findingId':'F'}})
 def test_finding_sources_are_derived_and_self_is_excluded(self):
  self.finding();self.dep();rows=self.rows();self.assertEqual([r['sourceId'] for r in rows],['X']);self.assertFalse(rows[0]['manual']);self.assertEqual(rows[0]['provenance'][0]['findingId'],'F')
  self.assertFalse(any(e.get('dependencyPurpose')=='decisionContext' for e in self.g['edges']))
  before=copy.deepcopy(self.g);K.pins(self.g,'D');K.POLICIES.describe_applications(self.g,K);K.focused_view(self.g,'D');self.assertEqual(self.g,before)
  self.assertIn('X',{n['id'] for n in K.focused_view(self.g,'D')['entities']})
 def test_comment_required_for_every_new_manual_writer(self):
  with self.assertRaisesRegex(ValueError,'CONTEXT_COMMENT_REQUIRED'):self.do('edit',{'nodeId':'D','changes':{'decisionContextIds':['X']},'cosmetic':False})
  with self.assertRaisesRegex(ValueError,'CONTEXT_COMMENT_REQUIRED'):self.do('decision_context',{'nodeId':'D','sourceId':'X','action':'save','comment':' '})
  with self.assertRaisesRegex(ValueError,'CONTEXT_COMMENT_REQUIRED'):self.do('link',{'relation':{'id':'BAD','type':'DEPENDS_ON','from':'X','to':'D','dependencyPurpose':'decisionContext','dependencyLevel':'L1'}})
 def test_two_findings_and_manual_share_one_row_and_keep_role(self):
  self.finding();self.finding('F2');self.dep();self.dep('F2');self.do('decision_context',{'nodeId':'D','sourceId':'X','action':'save','comment':'Supports D'})
  self.assertEqual(len(self.rows()),1);self.assertEqual({p['findingId'] for p in self.rows()[0]['provenance']},{'F','F2'})
  self.do('remove',{'nodeIds':['F']});self.assertEqual(len(self.rows()[0]['provenance']),1)
  self.do('decision_context',{'nodeId':'D','sourceId':'X','action':'remove'});self.assertEqual(self.rows()[0]['comment'],'Supports D')
  with self.assertRaisesRegex(ValueError,'DERIVED_CONTEXT_READONLY'):self.do('decision_context',{'nodeId':'D','sourceId':'X','action':'remove'})
  self.do('remove',{'nodeIds':['F2']});self.assertEqual(self.rows(),[]);self.assertEqual(K.entities(self.g)['D'].get('contextNotes'),{})
 def test_role_belongs_to_each_decision_and_is_context_observation(self):
  self.add('D2','decision');self.do('decision_context',{'nodeId':'D','sourceId':'X','action':'save','comment':'Supports'})
  old=K._context_sources(self.g,'D');self.do('decision_context',{'nodeId':'D2','sourceId':'X','action':'save','comment':'Challenges'})
  self.assertEqual(K._context_sources(self.g,'D'),old)
  self.do('decision_context',{'nodeId':'D','sourceId':'X','action':'note','comment':'More precise role'})
  self.assertNotEqual(K._context_sources(self.g,'D'),old);self.assertNotIn('contextNotes',K._native_definition(self.g,'D'))
 def test_existing_manual_role_cannot_be_cleared_via_generic_edit(self):
  self.do('decision_context',{'nodeId':'D','sourceId':'X','action':'save','comment':'Material role'})
  with self.assertRaisesRegex(ValueError,'CONTEXT_COMMENT_REQUIRED'):self.do('edit',{'nodeId':'D','changes':{'contextNotes':{}},'cosmetic':False})

 def test_invalid_note_is_not_silently_discarded(self):
  with self.assertRaisesRegex(ValueError,'CONTEXT_NOTE_REFERENCE'):self.do('edit',{'nodeId':'D','changes':{'contextNotes':{'BAD':'role'}},'cosmetic':False})
 def test_groups_move_delete_and_cycles_preserve_context_identity(self):
  self.group('TOP');self.group('CHILD','TOP');self.group('LEAF','CHILD');self.do('edit',{'nodeId':'X','changes':{'contextGroupId':'CHILD'},'cosmetic':False});definition=K._native_definition(self.g,'X')
  with self.assertRaisesRegex(ValueError,'CONTEXT_GROUP_CYCLE'):self.group('TOP','LEAF')
  self.do('context_group',{'action':'remove','id':'CHILD'});self.assertEqual(K.entities(self.g)['X']['contextGroupId'],'TOP');self.assertEqual(next(r for r in self.g['contextGroups'] if r['id']=='LEAF')['parentId'],'TOP')
  self.do('context_group',{'action':'remove','id':'TOP'});self.assertNotIn('contextGroupId',K.entities(self.g)['X']);self.assertEqual(K._native_definition(self.g,'X'),definition)
 def test_grouping_does_not_invalidate_content_but_fact_edit_does(self):
  self.finding();self.dep();self.do('review',{'nodeIds':['F'],'observed':K.pins(self.g,'F'),'basis':'Checked'})
  self.group('TOP');self.do('edit',{'nodeId':'X','changes':{'contextGroupId':'TOP'},'cosmetic':False});self.assertFalse(K.entities(self.g)['F']['review']['required'])
  self.do('context_group',{'action':'save','id':'TOP','title':'Deadlines','parentId':None});self.assertFalse(K.entities(self.g)['F']['review']['required'])
  self.do('edit',{'nodeId':'X','changes':{'value':'1000'},'cosmetic':False});self.assertTrue(K.entities(self.g)['F']['review']['required'])
 def test_group_lock_and_invalid_membership_are_atomic(self):
  self.group('TOP');K.entities(self.g)['X']['locks']={'edit':{'mode':'hard','principals':['user'],'message':'Locked'}}
  with self.assertRaisesRegex(ValueError,'LOCK'):self.do('edit',{'nodeId':'X','changes':{'contextGroupId':'TOP'},'cosmetic':False})
  with self.assertRaisesRegex(ValueError,'CONTEXT_GROUP_REFERENCE'):self.add('BAD','context',value='x',contextGroupId='missing')
 def test_requirement_necessity_uses_existing_r_and_explicit_basis(self):
  self.add('NEED','requirement',relations=[{'id':'RN','type':'DERIVES','from':'R','to':'NEED'}])
  self.do('requirement_decision',{'nodeId':'NEED','parentId':'R','decisionId':'CHOOSE','title':'Need requirement','replaceEdgeId':'RN'})
  self.assertEqual(K.entities(self.g)['CHOOSE']['selectionState'],'discovered');self.assertEqual(K.entities(self.g)['NEED']['kind'],'requirement');self.assertFalse(any(e['id']=='RN' for e in self.g['edges']))
  self.finding('F','CHOOSE');self.assertEqual(K.entities(self.g)['F']['subjectId'],'CHOOSE')
 def test_requirement_can_reuse_existing_decision_without_overwriting_its_content(self):
  self.add('NEED','requirement',relations=[{'id':'RN','type':'DERIVES','from':'R','to':'NEED'}]);before=copy.deepcopy(K.entities(self.g)['D'])
  self.do('requirement_decision',{'nodeId':'NEED','parentId':'R','decisionId':'D','title':'Ignored replacement title','replaceEdgeId':'RN'})
  self.assertEqual({k:K.entities(self.g)['D'][k] for k in ('title','description','selectionState','result')},{k:before[k] for k in ('title','description','selectionState','result')});self.assertEqual(len([e for e in self.g['edges'] if e['type']=='DRIVES' and e['to']=='D']),1);self.assertTrue(any(e['type']=='INTRODUCES' and e['to']=='NEED' for e in self.g['edges']))

 def test_requirement_decision_reuse_handles_multiple_requirements_and_parents(self):
  for i in ('N1','N2','P2'):self.add(i,'requirement',relations=[{'id':'R-'+i,'type':'DERIVES','from':'R','to':i}])
  for need,parent in (('N1','R'),('N2','P2')):
   self.do('requirement_decision',{'nodeId':need,'parentId':parent,'decisionId':'D','title':'D'})
  self.assertEqual({e['to'] for e in self.g['edges'] if e['type']=='INTRODUCES' and e['from']=='D'},{'N1','N2'})
  self.assertEqual({e['from'] for e in self.g['edges'] if e['type']=='DRIVES' and e['to']=='D'},{'R','P2'})
  self.assertEqual(len({e['id'] for e in self.g['edges']}),len(self.g['edges']))

 def test_requirement_cycle_and_wrong_edge_rejected(self):
  self.add('NEED','requirement',relations=[{'id':'RN','type':'DERIVES','from':'R','to':'NEED'}])
  with self.assertRaisesRegex(ValueError,'REQUIREMENT_DECISION_CYCLE'):self.do('requirement_decision',{'nodeId':'R','parentId':'NEED','decisionId':'C','title':'Bad cycle'})
 def test_canon_provenance_is_recorded_without_becoming_evidence(self):
  self.add('CAN','canon',guidance='When appropriate')
  self.do('decision_context',{'nodeId':'D','sourceId':'X','action':'save','comment':'Observed criterion','analysisSources':[{'sourceId':'CAN','revision':1,'excerpt':'When appropriate'}]})
  self.assertEqual(K.entities(self.g)['D']['analysisSources'][0]['sourceId'],'CAN');self.assertEqual([r['sourceId'] for r in self.rows()],['X'])
 def test_full_copy_remaps_notes_groups_and_derived_sources(self):
  self.finding();self.dep();self.group('TOP');self.group('CHILD','TOP');self.do('edit',{'nodeId':'X','changes':{'contextGroupId':'CHILD'},'cosmetic':False});self.do('decision_context',{'nodeId':'D','sourceId':'X','action':'note','comment':'Material context'})
  fragment,_=P.decision_fragment(self.g,{'kind':'decision','id':'D'},K)
  definitions=P.definitions(fragment);mapping={name:{i:name+'-'+str(index) for index,i in enumerate(ids)} for name,ids in definitions.items()}
  copied=P.decision_remap(fragment,mapping);K.validate(copied)
  d=K.entities(copied)[mapping['entity']['D']];x=mapping['entity']['X'];self.assertEqual(d['contextNotes'][x],'Material context');self.assertEqual(K.entities(copied)[x]['contextGroupId'],mapping['contextGroup']['CHILD'])
 def test_dynamic_source_retains_recorded_provenance_while_disabled(self):
  self.finding();self.dep()
  policy={'id':'P','version':1,'name':'Dynamic facts','description':'Synthetic','status':'active','pattern':'roles','sourceKinds':['context'],'targetKinds':['finding'],
    'roles':[{'id':'target','kinds':['finding'],'required':True},{'id':'source','kinds':['context'],'required':True,'selector':{'anchor':'target','relation':'DEPENDS_ON','direction':'in','minDepth':1,'maxDepth':1}}],
    'relations':[],'rules':[{'id':'content','name':'Fact','role':'source','watch':'definition','operations':['changed'],'enabled':True}]}
  self.do('policy_change',{'action':'policy_save','value':policy});self.do('policy_change',{'action':'binding_save','value':{'id':'B','policyId':'P','policyVersion':1,'targetId':'F','sourceId':None,'parentId':None,'participantBindings':{},'enabled':True}})
  self.assertEqual({p['applicationId'] for p in self.rows()[0]['provenance']},{'XF','B'})
  self.do('unlink',{'edgeId':'XF'});row=self.rows()[0];self.assertEqual(row['sourceId'],'X');self.assertTrue(row['present']);self.assertFalse(row['provenance'][0]['enabled'])
  self.dep();self.assertFalse(next(b for b in self.g['dependencyBindings'] if b['id']=='B')['enabled'])
  self.do('remove',{'nodeIds':['X']});row=self.rows()[0];self.assertFalse(row['present']);self.assertFalse(any(p['enabled'] for p in row['provenance']))

 def test_existing_branch_with_multiple_findings_opens_with_bounded_shared_resolver(self):
  old=SourceFileLoader('analysis_open_legacy_fixture',str(ROOT/'tests/rdg-findings.test.py')).load_module();fixture=old.Findings();fixture.setUp();fixture.finding();fixture.response();fixture.proposal();fixture.proposal('PROP2')
  self.g=copy.deepcopy(fixture.g)
  self.add('X','context',value='100')
  for i in ('D1','D2'):
   self.add(i,'decision',relations=[{'id':'BASIS-'+i,'type':'DRIVES','from':'R','to':i}]);self.finding('F-'+i,i)
  self.add('R2','requirement',relations=[{'id':'D1-R2','type':'INTRODUCES','from':'D1','to':'R2'}])
  self.dep('F-D2')
  before=copy.deepcopy(self.g)
  code='''from importlib.machinery import SourceFileLoader
from pathlib import Path
import json,sys
K=SourceFileLoader('bounded_read_kernel',str(Path(sys.argv[1])/'tools/rdg-decision-model.py')).load_module()
g=json.load(sys.stdin);before=json.dumps(g,sort_keys=True)
for _ in range(2):
 apps=K.POLICIES.describe_applications(g,K)
 rows={n['id']:K.decision_context(g,n['id']) for n in g['nodes'] if n['kind']=='decision'}
 assert any(r['sourceId']=='X' and r['provenance'] for r in rows['D2'])
assert json.dumps(g,sort_keys=True)==before
print('opened')
'''
  result=subprocess.run([sys.executable,'-B','-c',code,str(ROOT)],input=json.dumps(self.g),text=True,capture_output=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'opened');self.assertEqual(self.g,before)

 def test_l2_decision_context_does_not_reenter_finding_inheritance(self):
  self.finding();self.dep();self.add('D2','decision');self.finding('F2','D2')
  rule={'preset':'L2','watch':['definition','directScope']}
  self.do('decision_context',{'nodeId':'D2','sourceId':'D','action':'save','comment':'Related choice','rule':rule})
  self.do('decision_context',{'nodeId':'D','sourceId':'D2','action':'save','comment':'Related analysis','rule':rule})
  before=copy.deepcopy(self.g);apps=K.POLICIES.describe_applications(self.g,K)
  self.assertTrue(apps);self.assertEqual(self.g,before)
  self.assertIn('X',{r['sourceId'] for r in K.decision_context(self.g,'D')})

 def test_context_projection_cache_expires_between_reads_and_graphs(self):
  self.finding();self.dep();first=K._context_sources(self.g,'D')
  other=copy.deepcopy(self.g);K.entities(other)['X']['value']='1000'
  self.assertNotEqual(first,K._context_sources(other,'D'))
  K.entities(self.g)['X']['value']='2000'
  self.assertNotEqual(first,K._context_sources(self.g,'D'))

 def test_new_confirmation_data_is_context_and_separate_evidence_creation_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'EVIDENCE_RETIRED_USE_CONTEXT'):self.add('EV','evidence',claim='Observed',scope='Synthetic',version='1',source='Test')
  self.finding();self.do('edit',{'nodeId':'F','changes':{'evidenceIds':['X']},'cosmetic':False})
  self.do('review',{'nodeIds':['F'],'observed':K.pins(self.g,'F'),'basis':'Reviewed the supporting process data'})
  self.do('finding_disposition',{'nodeId':'F','observed':K.pins(self.g,'F'),'disposition':{'code':'resolved','basis':'Verified outcome in the process data','evidenceIds':['X']}})
  self.assertEqual(K.entities(self.g)['F']['disposition']['code'],'resolved');self.assertEqual(K.entities(self.g)['X']['kind'],'context')
  self.do('edit',{'nodeId':'X','changes':{'scope':'Synthetic measurement','version':'1','source':'Test log'},'cosmetic':False})
  self.assertEqual(K.entities(self.g)['X']['source'],'Test log')

 def test_legacy_evidence_conversion_keeps_identity_data_artifact_and_references(self):
  ev={'id':'EV','kind':'evidence','title':'Measurement','description':'Observed result','revision':1,'claim':'p95=350ms','scope':'Synthetic','version':'1','source':'Log','artifact':{'path':'evidence/result','sha256':'a'*64}}
  self.g['objects'].append(ev);self.finding();self.dep(source='EV');self.do('edit',{'nodeId':'F','changes':{'evidenceIds':['EV']},'cosmetic':False})
  definition=K._native_definition(self.g,'EV');before=copy.deepcopy(self.g);K.validate(self.g);self.assertEqual(self.g,before)
  self.do('context_record',{'nodeId':'EV'});n=K.entities(self.g)['EV']
  self.assertEqual(n['kind'],'context');self.assertEqual(n['value'],'p95=350ms');self.assertEqual(n['artifact'],ev['artifact']);self.assertEqual(n['source'],'Log');self.assertEqual(K._native_definition(self.g,'EV'),definition)
  self.assertEqual(K.entities(self.g)['F']['evidenceIds'],['EV']);self.assertTrue(any(e['from']=='EV' and e['to']=='F' for e in self.g['edges']));self.assertTrue(any(g['id']==n['contextGroupId'] for g in self.g['contextGroups']))
  fragment,_=P.decision_fragment(self.g,{'kind':'decision','id':'D'},K);definitions=P.definitions(fragment);mapping={name:{i:name+'-'+str(j) for j,i in enumerate(ids)} for name,ids in definitions.items()};copied=P.decision_remap(fragment,mapping);K.validate(copied)
  self.assertEqual(K.entities(copied)[mapping['entity']['EV']]['artifact'],ev['artifact'])

 def test_legacy_kind_policy_disables_on_conversion_without_changing_definition_or_reactivating(self):
  self.g['objects'].append({'id':'EV','kind':'evidence','title':'Measurement','description':'Synthetic','revision':1,'claim':'Observed','scope':'Synthetic','version':'1','source':'Log'});self.finding()
  policy={'id':'PE','version':1,'name':'Legacy record kind','description':'Synthetic','status':'active','pattern':'direct','sourceKinds':['evidence'],'targetKinds':['finding'],'rules':[{'id':'content','name':'Observed fact','watch':'definition','operations':['changed'],'enabled':True}]}
  self.do('policy_change',{'action':'policy_save','value':policy});self.do('policy_change',{'action':'binding_save','value':{'id':'BE','policyId':'PE','policyVersion':1,'targetId':'F','sourceId':'EV','parentId':None,'enabled':True}})
  if K.entities(self.g)['F'].get('review',{}).get('required'):self.do('review',{'nodeIds':['F'],'observed':K.pins(self.g,'F'),'basis':'Reviewed old record'})
  self.do('context_record',{'nodeId':'EV'});b=next(b for b in self.g['dependencyBindings'] if b['id']=='BE')
  self.assertEqual(b['status'],'disabled');self.assertEqual(b['reasonCode'],'applicability');self.assertFalse(K.entities(self.g)['F'].get('review',{}).get('required'))
  self.assertEqual(self.g['dependencyPolicies'][0]['sourceKinds'],['evidence']);self.assertEqual(b['observedSources']['content'][0]['kind'],'evidence')
  self.do('edit',{'nodeId':'EV','changes':{'value':'More precise observation'},'cosmetic':False});self.assertFalse(next(b for b in self.g['dependencyBindings'] if b['id']=='BE')['enabled'])

 def test_conversion_requires_edit_rights_and_bad_group_is_atomic(self):
  self.g['objects'].append({'id':'EV','kind':'evidence','title':'Measurement','description':'Synthetic','revision':1,'claim':'Observed','scope':'Synthetic','version':'1','source':'Log'})
  with self.assertRaisesRegex(ValueError,'CONTEXT_GROUP_UNKNOWN'):self.do('context_record',{'nodeId':'EV','contextGroupId':'missing'})
  K.entities(self.g)['EV']['locks']={'edit':{'mode':'hard','principals':['user'],'message':'Locked'}}
  with self.assertRaisesRegex(ValueError,'LOCK'):self.do('context_record',{'nodeId':'EV'})

 def test_selected_decision_may_keep_findings_without_auto_withdrawal(self):
  for i,n in K.entities(self.g).items():
   if n.get('review',{}).get('required'):self.do('review',{'nodeIds':[i],'observed':K.pins(self.g,i),'basis':'Checked'})
  self.do('select',{'nodeId':'D'});self.finding();self.assertEqual(K.entities(self.g)['D']['selectionState'],'selected');self.assertEqual(K.entities(self.g)['F']['disposition']['code'],'unresolved')

if __name__=='__main__':unittest.main()
