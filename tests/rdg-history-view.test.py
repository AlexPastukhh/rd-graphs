#!/usr/bin/env python3
"""History facts and visibility are independent of Plan and current view state."""
import copy
import unittest
from pathlib import Path
from importlib.machinery import SourceFileLoader
ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('history_fixture',str(ROOT/'tests/rdg-analysis.test.py')).load_module();K=T.K;H=K.HISTORY

class History(unittest.TestCase):
 setUp=T.Analysis.setUp
 do=T.Analysis.do
 add=T.Analysis.add
 finding=T.Analysis.finding
 dep=T.Analysis.dep
 def branch(self):
  self.add('R2','requirement',relations=[{'id':'D-R2','type':'INTRODUCES','from':'D','to':'R2'}]);self.add('R3','requirement',relations=[{'id':'R2-R3','type':'DERIVES','from':'R2','to':'R3'}])
 def review(self):
  for n in list(K.entities(self.g).values()):
   if n.get('review',{}).get('required'):self.do('review',{'nodeIds':[n['id']],'observed':K.pins(self.g,n['id']),'basis':'Reviewed synthetic inputs'})
 def test_selection_and_withdrawal_record_real_transitive_requirement_activity(self):
  self.branch();self.review();ev=self.do('select',{'nodeId':'D'});v=H.classify(ev,ev['historyDetail']);self.assertEqual(v['level'],'important');self.assertEqual(v['activatedRequirementIds'],['R2','R3']);self.assertNotIn('selectionState',K.entities(self.g)['R2'])
  ev=self.do('withdraw',{'nodeId':'D'});events=[e for e in self.g['events'] if e['transactionId']==ev['transactionId']];self.assertEqual(set(i for e in events for i in e['historyDetail']['deactivatedRequirementIds']),{'R2','R3'})
 def test_other_real_basis_prevents_false_requirement_cancellation(self):
  self.branch();self.do('root_cause',{'cause':{'id':'OTHER','requirementId':'R2','reason':'Independent actual basis','enabled':True}});self.review();self.do('select',{'nodeId':'D'});ev=self.do('withdraw',{'nodeId':'D'});events=[e for e in self.g['events'] if e['transactionId']==ev['transactionId']];self.assertFalse(any(e['historyDetail']['deactivatedRequirementIds'] for e in events))
 def test_context_content_and_organization_have_different_levels(self):
  ev=self.do('edit',{'nodeId':'X','changes':{'value':'1000'},'cosmetic':False});v=H.classify(ev,ev['historyDetail']);self.assertEqual(v['level'],'important');self.assertEqual(v['edits'][0]['before'],'100');self.assertEqual(v['edits'][0]['after'],'1000')
  ev=self.do('context_group',{'action':'save','id':'CG','title':'Facts','parentId':None});self.assertEqual(H.classify(ev,ev['historyDetail'])['level'],'technical')
  ev=self.do('edit',{'nodeId':'X','changes':{'contextGroupId':'CG'},'cosmetic':False});self.assertEqual(H.classify(ev,ev['historyDetail'])['level'],'technical')
 def test_cosmetic_and_semantic_rename_are_explicit_and_only_semantic_invalidates(self):
  self.finding();self.dep();self.review()
  ev=self.do('edit',{'nodeId':'X','changes':{'title':'Readable name'},'cosmetic':True});self.assertEqual(H.classify(ev,ev['historyDetail'])['level'],'technical');self.assertFalse(K.entities(self.g)['F'].get('review',{}).get('required'))
  ev=self.do('edit',{'nodeId':'X','changes':{'title':'Changed meaning'},'cosmetic':False});self.assertEqual(H.classify(ev,ev['historyDetail'])['level'],'important');self.assertTrue(K.entities(self.g)['F']['review']['required'])
 def test_low_level_discovery_record_does_not_hide_business_creation(self):
  self.add('D2','decision',relations=[{'id':'RD2','type':'DRIVES','from':'R','to':'D2'}]);tx=self.g['events'][-1]['transactionId'];events=[e for e in self.g['events'] if e['transactionId']==tx]
  primary=next(e for e in events if e['type']=='created');self.assertEqual(primary['historyDetail']['createdIds'],['D2']);self.assertEqual(H.classify(primary,primary['historyDetail'])['level'],'semantic')
  ops=[e for e in events if e['type']=='action_executed'];self.assertTrue(ops);self.assertTrue(all(H.classify(e,e['historyDetail'])['level']=='technical' for e in ops))
 def test_dependency_assignment_is_technical_and_finding_data_is_semantic(self):
  self.finding();ev=self.do('link',{'relation':{'id':'XF','type':'DEPENDS_ON','from':'X','to':'F','dependencyLevel':'L1'}});self.assertEqual(H.classify(ev,ev['historyDetail'])['level'],'technical')
  ev=self.do('edit',{'nodeId':'F','changes':{'rationale':'More precise actual mechanism'},'cosmetic':False});self.assertEqual(H.classify(ev,ev['historyDetail'])['level'],'semantic')
 def test_role_comment_edit_is_semantic_without_reassigning_participation(self):
  self.do('decision_context',{'nodeId':'D','sourceId':'X','action':'save','comment':'Input role'})
  ev=self.do('decision_context',{'nodeId':'D','sourceId':'X','action':'save','comment':'A more precise analytical role'})
  self.assertEqual(ev['historyDetail']['fields'],['contextNotes']);self.assertEqual(H.classify(ev,ev['historyDetail'])['level'],'semantic')
 def test_relation_endpoint_snapshot_keeps_its_name_after_later_rename(self):
  ev=self.do('add',{'entity':{'id':'NEW','kind':'decision','title':'Historical candidate','description':'Synthetic'},'initialRelations':[{'id':'RNEW','type':'DRIVES','from':'R','to':'NEW'}]})
  original=ev['historyDetail']['subjects']['R']['title'];self.do('edit',{'nodeId':'R','changes':{'title':'Later name'},'cosmetic':True})
  self.assertEqual(ev['historyDetail']['subjects']['R']['title'],original);self.assertNotEqual(original,K.entities(self.g)['R']['title'])
 def test_unknown_old_rename_is_not_guessed_cosmetic(self):
  before=copy.deepcopy(self.g);after=copy.deepcopy(before);K.entities(after)['X']['title']='Historical name';ev={'id':'old','type':'edited','nodeIds':['X']};d=H.legacy_details(before,after,[ev],K)['old'];v=H.classify(ev,d);self.assertEqual(v['level'],'unknown');self.assertTrue(H.accepts(v['level'],'meaningful'));self.assertFalse(H.accepts(v['level'],'technical'))
 def test_old_partial_creation_does_not_invent_a_new_context(self):
  ev={'id':'captured','type':'created','nodeIds':['R','D','X']};d=H.legacy_details(None,self.g,[ev],K)['captured'];self.assertFalse(d['createdIds']);self.assertNotEqual(H.classify(ev,d)['level'],'important')
 def test_recorded_snapshots_survive_entity_deletion_and_read_is_pure(self):
  self.add('C','context',value='Observed');ev=copy.deepcopy(self.g['events'][-1]);self.do('remove',{'nodeIds':['C']});before=copy.deepcopy(self.g);v=H.classify(ev,ev['historyDetail']);self.assertEqual(v['subjects']['C']['title'],'C');self.assertEqual(v['level'],'important');self.assertEqual(self.g,before)
 def test_acceptance_action_records_its_execution_and_both_decision_outcomes(self):
  self.branch();self.do('add',{'entity':{'id':'AA','kind':'action','title':'Review acceptance','description':'Synthetic','actionType':'decide_acceptance','lowLevel':False,'targetIds':['D'],'groupIds':[]},'initialRelations':[{'id':'RA','type':'REQUIRES_ACTION','from':'R','to':'AA'}]});self.review()
  for outcome,typ in [('selected','decision_selected'),('unselected','decision_unselected')]:
   if K.entities(self.g)['AA']['result']['state']=='confirmed':self.do('reopen',{'nodeId':'AA','basis':'Revisit acceptance'});self.review()
   ev=self.do('complete',{'nodeId':'AA','basis':'Observed acceptance outcome','evidenceIds':['X'],'decisionOutcome':outcome});events=[e for e in self.g['events'] if e['transactionId']==ev['transactionId']]
   self.assertEqual(len([e for e in events if e['type']=='action_executed']),1);choice=next(e for e in events if e['type']==typ);self.assertEqual(choice['nodeIds'],['D']);self.assertEqual(H.classify(choice,choice['historyDetail'])['level'],'important')
   self.assertEqual(choice['historyDetail']['activatedRequirementIds'] if outcome=='selected' else choice['historyDetail']['deactivatedRequirementIds'],['R2','R3'])

 def test_modes_partition_technical_and_keep_unknown_in_meaningful(self):
  for level in ('important','semantic','unknown','technical'):
   self.assertTrue(H.accepts(level,'all'));self.assertEqual(H.accepts(level,'technical'),level=='technical');self.assertEqual(H.accepts(level,'important'),level=='important');self.assertEqual(H.accepts(level,'meaningful'),level!='technical')
  with self.assertRaisesRegex(ValueError,'HISTORY_MODE'):H.accepts('important','invalid')

if __name__=='__main__':unittest.main()
