#!/usr/bin/env python3
"""The canonical teaching process uses the real writer in an isolated store."""
import copy
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('current_example_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
E=SourceFileLoader('current_example',str(ROOT/'tools/rdg-current-example.py')).load_module()

class CurrentExample(unittest.TestCase):
 setUp=T.PortableApplication.setUp
 config=T.PortableApplication.config
 app=T.PortableApplication.app
 def test_full_example_retry_and_plan_views_preserve_actual_choices(self):
  app=self.app();journal=self.base/'operator-example.json'
  req=app.schema('create',core_model='rdg-decision-v1',role='lens')['request'];req.update(path='lenses/test-work',role='lens',lensKey='work',coreModel='rdg-decision-v1',rootReason='Isolated example fixture',graph=json.loads((ROOT/'tools/rdg-agent-lenses/work-decision.json').read_text()));app.request(req)
  class Interrupted:
   failed=False
   def call(inner,msg):
    result=app.call(msg)
    if msg['method']=='apply' and msg['request'].get('note')=='Учебный сценарий: add-R-STORE' and not inner.failed:
     inner.failed=True;raise ConnectionError('Synthetic response lost after accepted apply')
    return result
  client=Interrupted()
  with self.assertRaisesRegex(RuntimeError,'preserved transactionId'):E.run(client,journal,progress=lambda _:None)
  pending=json.loads(journal.read_text())['operations']['add-R-STORE'];tx=pending['request']['transactionId']
  result=E.run(client,journal,progress=lambda _:None);pid=result['packageId'];row=app.read(pid,True);g=row['graph'];plan=row['plan'];ns={n['id']:n for n in g['nodes']+g['objects']}
  self.assertGreaterEqual(len(g['nodes']),25);self.assertEqual(result['verified']['contexts'],8);self.assertEqual(result['verified']['findings'],4);self.assertEqual(len(plan['forks']),2);self.assertIsNone(plan['forks'][0]['afterStepId']);self.assertIn('end',plan['forks'][0]);self.assertNotIn('end',plan['forks'][1]);self.assertEqual(len(plan['steps']),19);self.assertNotIn('A-ANALYSIS',ns)
  self.assertEqual(result['verified']['questions'],2);self.assertTrue(ns['Q-PEAK']['assessmentReviewRequired']);self.assertEqual(ns['Q-BUDGET']['answers'],[]);self.assertEqual(ns['A-MEASURE']['estimates']['time'],{'minSeconds':60,'maxSeconds':180})
  self.assertEqual(result['verified']['focusReadCases'],4);self.assertEqual(result['verified']['branchReadCases'],1)
  self.assertEqual(result['verified']['planningMetaActions'],2);self.assertEqual(result['verified']['authoredRecommendations'],2);self.assertEqual(len(row['recommendations']['matches']),2)
  self.assertEqual(result['verified']['theorySections'],3);self.assertTrue(ns['CAN-SQL']['canons']);self.assertEqual(len(ns['CAN-SQL']['knownErrors']),2);self.assertEqual(ns['CAN-SQL']['knownErrors'][1]['description'],'');self.assertNotIn('knownErrors',ns['CAN-REPL'])
  self.assertTrue(app.receipt(pid,tx)['found']);self.assertEqual(json.loads(journal.read_text())['operations']['add-R-STORE']['request']['transactionId'],tx)
  self.assertEqual(ns['D-UP']['selectionState'],'discovered');self.assertEqual(ns['D-OUT']['selectionState'],'discovered');self.assertEqual(ns['D-SQL']['result']['state'],'confirmed')
  for index in (0,1):
   shown={fork['id']:fork['cases'][index]['id'] for fork in plan['forks']}
   viewed=app.read(pid,True,{'kind':'graph','shownCases':shown,'historyMode':'technical'})
   self.assertEqual(viewed['graph'],g);self.assertEqual(viewed['plan'],plan)
  history=app.history(pid)['events'];self.assertTrue(all(r['historyView']['detailSource']=='recorded' for r in history))
  choices=[r for r in history if r['event']['type']=='decision_selected'];sql=next(r for r in choices if 'D-SQL' in r['historyView']['targetIds']);self.assertEqual(sql['historyView']['activatedRequirementIds'],['R-DDL','R-DOC'])
  cancel=next(r for r in history if r['event']['type']=='decision_unselected' and 'D-TEMP' in r['historyView']['targetIds']);self.assertNotIn('R-SAFE',cancel['historyView']['deactivatedRequirementIds'])
  nested=copy.deepcopy(plan);nested['forks'][1]['afterStepId']=nested['forks'][0]['cases'][0]['stepIds'][0]
  with self.assertRaisesRegex(ValueError,'PLAN_FORK'):T.P.validate_plan(nested)
  E.run(client,journal,progress=lambda _:None);after=app.read(pid,True);self.assertEqual(after['graph'],g);self.assertEqual(after['plan'],plan)

if __name__=='__main__':unittest.main()
