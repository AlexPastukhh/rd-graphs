#!/usr/bin/env python3
"""Focused plan review checks; all writers use temporary synthetic roots."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SUITES = [
 ("plan-owner", "tests/rdg-temporal-plan-owner.test.py"),
 ("joint-context", "tests/rdg-joint-context.test.py"),
 ("branch-acceptance", "docs/handoffs/rdg-prework-v4.1-final-20261018/tests/rdg-gendocen-branch-membership.acceptance.test.py"),
 ("coverage-guard", "tests/rdg-gendocen-coverage-guard.test.py"),
]
results = {}
for name, relative in SUITES:
 start = time.monotonic()
 command = [sys.executable, relative, "-v"]
 run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
     env={**os.environ, "PYTHONDONTWRITEBYTECODE":"1"}, timeout=150)
 (OUT/(name+".log")).write_text(run.stdout+run.stderr)
 results[name] = {"command":command, "exitCode":run.returncode,
     "seconds":round(time.monotonic()-start,2), "log":name+".log"}
 print(name, "exit", run.returncode, flush=True)
(OUT/"test-results.json").write_text(json.dumps({"checkedAtUTC":dt.datetime.now(dt.timezone.utc).isoformat(),"results":results},indent=2)+"\n")
sys.exit(int(any(r["exitCode"] for r in results.values())))
