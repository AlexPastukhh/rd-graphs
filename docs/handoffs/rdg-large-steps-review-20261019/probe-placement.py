from pathlib import Path
from importlib.machinery import SourceFileLoader
import json
ROOT=Path(__file__).resolve().parents[3]
F=SourceFileLoader('review_fixture',str(ROOT/'tests/rdg-workflow.acceptance.test.py')).load_module()
H=SourceFileLoader('review_helper',str(ROOT/'tools/rdg-workflow-helper.py')).load_module()

def run(with_date):
 f=F.Workflow('test_whole_future_execution_withdrawal_new_variant_and_history');f.setUp()
 try:
  w=f.w;w.apply([w.add('A1'),w.add('A2')])
  editor=H.Editor(f.root,f.rel,w.home/'graphs',w.rel,w.store,w.token,tools=w.home/'tools')
  index=0
  def command(nid,**extra):
   nonlocal index
   index+=1;v=editor.snapshot()
   return editor.dispatch({'action':'place','transactionId':'probe-'+str(index),'nodeId':nid,
     'expectedGraphRevision':v['sources']['graphs'][w.rel]['revision'],
     'expectedPlanRevision':v['sources']['plan']['revision'],'note':'Synthetic date edit',**extra})
  command('A1',at='2026-10-20')
  command('A2',at='2026-10-21' if with_date else '',afterStepId='S-A1')
  before=editor.snapshot()['sources']['plan'];graph_before=w.sources()
  error=None
  try:command('A1',at='2026-10-22')
  except ValueError as exc:error=str(exc)
  after=editor.snapshot()['sources']['plan']
  return {'case':'A2 has date and order' if with_date else 'A2 has only order',
   'beforeSequence':before['sequence'],'afterSequence':after['sequence'],
   'error':error,'planUnchanged':before==after,'graphUnchanged':graph_before==w.sources()}
 finally:f.doCleanups()

result=[run(True),run(False)]
print(json.dumps(result,ensure_ascii=False,indent=2))
assert result[0]['beforeSequence'] and not result[0]['afterSequence'] and result[0]['error'] is None
assert result[1]['error'] and result[1]['planUnchanged']
