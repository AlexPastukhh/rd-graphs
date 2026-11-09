from pathlib import Path
import subprocess,concurrent.futures,json
r=Path(__file__).resolve().parents[3];out=Path(__file__).resolve().parent
commands=json.loads((out/'verification-commands.json').read_text())
def run(item):
 name,cmd=item
 res=subprocess.run(cmd,cwd=r,capture_output=True,text=True,timeout=180)
 (out/(name+'.log')).write_text(res.stdout+res.stderr)
 return {'name':name,'exitCode':res.returncode,'log':name+'.log'}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(run,commands))
(out/'verification-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
raise SystemExit(int(any(e['exitCode'] for e in results)))
