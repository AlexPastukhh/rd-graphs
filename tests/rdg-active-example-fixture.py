#!/usr/bin/env python3
"""Read the real local example via the real bearer readers and Gendocen CLI.

The emitted read-only JSON is a browser QA transport fixture, not a separate
canonical Graph or a fabricated teaching history.
"""
from pathlib import Path
from importlib.machinery import SourceFileLoader
import json,sys,tempfile
BASE=Path(__file__).resolve().parents[1]
TOOLS=BASE/'tools'
AUTH=SourceFileLoader('active_demo_auth',str(TOOLS/'rdg-authority.py')).load_module()
WF=SourceFileLoader('active_demo_workflow',str(TOOLS/'rdg-workflow.py')).load_module()
GENDOCEN=SourceFileLoader('active_demo_gendocen',str(TOOLS/'rdg-requirement-gendocen.py')).load_module()
FILE='workspaces/requirements-dependencies-demo/graph.json'
PLAN='plans/requirements-dependencies-demo/plan.json'
ENGINE=BASE/'.rdg-gendocen-projects/requirements-dependencies-demo'
with tempfile.TemporaryDirectory(prefix='rdg-active-fixture-owner-') as folder:
    grants=Path(folder)/'auth.json'
    owner=AUTH.Authority(grants).init_local(plan_capable=True,graph_read_capable=True)
    token=owner['token']
    view=WF.read_workflow(BASE,PLAN,BASE/'graphs',str(grants),token,[FILE],include_sources=True)
    g=view['sources']['graphs'][FILE]
    assert g['actionModel']=='candidate-v6' and not g.get('readOnly')
    assert view['sources']['plan']['revision']>=1
    view.update(graphFile=FILE,planFile=PLAN,contextId='requirements-dependencies-demo',
                permissions=['graph.read','plan.read'],capabilities=['plan.place.from-read-sources'])
    report=GENDOCEN.report(ENGINE)
    assert report['engine']=='gendocen' and FILE in report['sourceGraphs']
    for event in g.get('events',[]):
        assert any(row['id']==FILE+'::'+event['id'] for row in view['history'])
    if '--summary' in sys.argv:
        print(json.dumps({'graphRevision':g['revision'],'planRevision':view['sources']['plan']['revision'],
           'historyKinds':[x['kind'] for x in view['history']],
           'futureIds':[x['nodeId'] for x in view['future']],
           'statuses':{x['nodeId']:x['status'] for x in report['rows']},
           'engineReceipts':sum(1 for x in (ENGINE/'docs/_dependency/receipts').glob('receipt-*.json'))},
           ensure_ascii=False))
    else:
        print(json.dumps({'view':view,'report':report},ensure_ascii=False))
