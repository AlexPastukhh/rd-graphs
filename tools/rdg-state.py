"""Bridge to the same context contract used by Node CLI and embedded Viewer."""
import json
import subprocess
from pathlib import Path

def state_call(payload):
    run = subprocess.run(["node", str(Path(__file__).with_name("rdg-state-cli.cjs"))],
                         input=json.dumps(payload, ensure_ascii=False), text=True, capture_output=True)
    if run.returncode:
        raise ValueError(run.stderr.strip() or "context core failed")
    return json.loads(run.stdout)

def has_state(graph):
    return any(k in graph for k in ("contextFields", "contextUses", "knowledgeSources", "contextFieldsComplete")) or any(
        any(k in n for k in ("contextFieldRef", "contextValue", "contextAnswers", "contextUses")) or
        any(k in n.get("canonBlock", {}) for k in ("sourceRefs", "preparation", "fieldsComplete", "interpretation", "contextUses")) or
        any("contextUses" in c or "sourceRefs" in c for p in ("recommended","contraindicated")
            for c in n.get("canonBlock", {}).get(p, [])) for n in graph.get("nodes", []))

def validate_items(items, partial=False):
    if any(has_state(i["graph"]) for i in items):
        return state_call({"action":"validate", "items":items, "options":{"partial":partial}})
    return True
