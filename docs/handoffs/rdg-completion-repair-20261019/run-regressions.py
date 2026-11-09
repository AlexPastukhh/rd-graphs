import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent
env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"}
pyfiles=sorted((root/"tests").glob("*.test.py"))
nodefiles=sorted((root/"tests").glob("*.test.cjs"))
commands=[(p.name,["python3","-B",str(p),"-v"]) for p in pyfiles]
commands.append(("node-all",["node","--test","--test-concurrency=3",*[str(p) for p in nodefiles]]))

def run(item):
 name,cmd=item
 try:
  result=subprocess.run(cmd,cwd=root,env=env,text=True,capture_output=True,timeout=240)
  log=result.stdout+result.stderr
  (out/(name+".log")).write_text(log)
  return {"suite":name,"exitCode":result.returncode,"log":name+".log"}
 except subprocess.TimeoutExpired:
  return {"suite":name,"exitCode":124,"timeoutSeconds":240}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 results=list(pool.map(run,commands))
(out/"regressions.json").write_text(json.dumps(results,indent=2)+"\n")
print(json.dumps({"pythonSuites":len(pyfiles),"nodeFiles":len(nodefiles),"failed":[r for r in results if r["exitCode"]]},indent=2),flush=True)
sys.exit(1 if any(r["exitCode"] for r in results) else 0)
