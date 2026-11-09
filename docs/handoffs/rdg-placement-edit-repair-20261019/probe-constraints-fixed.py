from pathlib import Path
from importlib.machinery import SourceFileLoader
import json
ROOT=Path(__file__).resolve().parents[3]
F=SourceFileLoader('review_constraint_fixture',str(ROOT/'tests/rdg-workflow.acceptance.test.py')).load_module()
H=SourceFileLoader('review_constraint_helper',str(ROOT/'tools/rdg-workflow-helper.py')).load_module()
f=F.Workflow('test_whole_future_execution_withdrawal_new_variant_and_history');f.setUp()
try:
 w=f.w;w.apply([w.add('A1')])
 op=f.place('S-A1','A1')
 op['timeConstraints']=[
  {'type':'notBefore','at':'2026-10-20','strength':'hard','basis':'Synthetic existing lower bound'},
  {'type':'deadline','at':'2026-10-25','strength':'hard','basis':'Synthetic candidate deadline'}]
 f.owner(f.placement_request([op]))
 e=H.Editor(f.root,f.rel,w.home/'graphs',w.rel,w.store,w.token,tools=w.home/'tools')
 v=e.snapshot();before=v['sources']['plan']['timeConstraints']
 result=e.dispatch({'action':'place','transactionId':'probe-constraints','nodeId':'A1','at':'2026-10-21',
   'note':'Change only the displayed start date','expectedGraphRevision':v['sources']['graphs'][w.rel]['revision'],
   'expectedPlanRevision':v['sources']['plan']['revision']})
 after=result['view']['sources']['plan']['timeConstraints']
 print(json.dumps({'before':before,'after':after,'saved':result['saved']},indent=2))
 expected=json.loads(json.dumps(before))
 next(x for x in expected if x['type']=='notBefore')['at']='2026-10-21'
 assert after==expected
finally:f.doCleanups()
