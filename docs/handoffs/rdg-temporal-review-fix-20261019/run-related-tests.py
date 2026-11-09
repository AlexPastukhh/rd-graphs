#!/usr/bin/env python3
"""Related Python regression; writers use only their temporary fixtures."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json, os, re, subprocess, sys, time
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
NAMES = ["temporal-placement.acceptance", "temporal-plan", "temporal-plan-owner",
 "temporal-impact", "shared-action-occurrences.acceptance", "joint-context",
 "gendocen-resources", "gendocen-dependencies", "gendocen-coverage-guard",
 "future-baseline", "exact-history", "event-owner", "event-gendocen",
 "event-consumer-guard", "two-time-scenario", "applicability-owner"]
def run(name):
 path = ROOT/("tests/rdg-"+name+".test.py")
 assert path.is_file(), str(path)
 command = [sys.executable, "-B", str(path), "-v"]
 start = time.monotonic()
 result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
  env={**os.environ, "PYTHONDONTWRITEBYTECODE":"1"}, timeout=180)
 log = result.stdout+result.stderr
 (OUT/(name+".log")).write_text(log)
 match = re.search(r"Ran (\d+) tests?",log)
 return name, {"command":command, "exitCode":result.returncode,
  "tests":int(match[1]) if match else None,
  "seconds":round(time.monotonic()-start,2), "log":name+".log"}
results = {}
with ThreadPoolExecutor(max_workers=3) as pool:
 for future in as_completed([pool.submit(run,name) for name in NAMES]):
  name,result = future.result();results[name] = result
  print(name, result["exitCode"], result["tests"], flush=True)
(OUT/"test-results.json").write_text(json.dumps({"results":results,
 "totalTests":sum(x["tests"] or 0 for x in results.values())},indent=2)+"\n")
sys.exit(int(any(x["exitCode"] for x in results.values())))
