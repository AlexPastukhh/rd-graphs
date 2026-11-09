from pathlib import Path
import concurrent.futures,json,os,subprocess
root=Path(__file__).resolve().parents[3];out=Path(__file__).resolve().parent
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','RDG_WORKFLOW_TEST_LOG_DIR':str(out),
     'RDG_PLACEMENT_TEST_LOG':str(out/'live-controller.log')}
names=['rdg-placement-edit.acceptance.test.py','rdg-workflow-helper.test.py',
       'rdg-workflow.acceptance.test.py','rdg-cross-file-completion.test.py',
       'rdg-temporal-placement.acceptance.test.py','rdg-temporal-plan-owner.test.py']
commands=[(n,['python3','-B',str(root/'tests'/n),'-v']) for n in names]
commands.append(('node-all',['node','--test','--test-concurrency=3',
    *[str(p) for p in sorted((root/'tests').glob('*.test.cjs'))]]))
commands.extend((n,['python3','-B',str(out/(n+'.py'))]) for n in ['probe-placement-fixed','probe-constraints-fixed'])
commands.append(('viewer-smoke',['node','tools/rd-graph-viewer-smoke.test.cjs']))
def run(item):
 name,cmd=item
 result=subprocess.run(cmd,cwd=root,env=env,capture_output=True,text=True,timeout=240)
 (out/(name+'.log')).write_text(result.stdout+result.stderr)
 return {'name':name,'exitCode':result.returncode,'log':name+'.log'}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(run,commands))
(out/'regression-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
raise SystemExit(int(any(r['exitCode'] for r in results)))
