#!/usr/bin/env python3
"""In-memory source probes. Does not write a user graph."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import copy
import json
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
MODEL = SourceFileLoader("temporal_semantics_graph",
    str(ROOT/"tools/graph-apply.py")).load_module()
API = SourceFileLoader("temporal_semantics_api",
    str(ROOT/"tools/rdg-graph-api.py")).load_module()
base = {"schemaVersion":1,"revision":1,"identitySpace":"topology-review",
    "id":"review","rootRequirementId":"R0","actionModel":"candidate-v6",
    "nodes":[{"id":"R0","kind":"requirement","title":"Goal","status":"active"},
             {"id":"A1","kind":"action","title":"Method","status":"candidate"}],
    "edges":[{"id":"d1","type":"DRIVES","from":"R0","to":"A1"}],"events":[]}

def check(label, graph):
    try:
        MODEL.validate(graph)
        return {"probe":label,"accepted":True}
    except ValueError as error:
        return {"probe":label,"accepted":False,"reason":str(error)}

results = [check("candidate Action under R",base)]
for kind in ("INTRODUCES","OUTCOME_OF"):
    graph = copy.deepcopy(base)
    graph["nodes"].append({"id":"R1","kind":"requirement",
                           "title":"Future child","status":"potential"})
    graph["edges"].append({"id":"child","type":kind,"from":"A1","to":"R1",
                           "parent":"R0","childRole":"method_correctness"})
    results.append(check("candidate Action future child via "+kind,graph))
graph = copy.deepcopy(base)
graph["nodes"][1]["status"] = "performed"
results.append(check("performed Action status",graph))
graph = copy.deepcopy(base)
API.apply(graph,{"action":"create_requirement","parentRequirementId":"R0",
    "edgeId":"created-child","node":{"id":"R1","kind":"requirement","title":"Child"},
    "event":{"id":"EV-CREATE","type":"graph_changed","operation":"create_requirement",
             "by":"assistant","authorityPrincipal":"synthetic-source-probe",
             "note":"In-memory topology review only"}})
result = check("Graph API create_requirement",graph)
result["createdEdgeType"] = graph["edges"][-1]["type"]
results.append(result)
print(json.dumps({"scope":"in-memory source probes, not new behavior acceptance",
                  "results":results},ensure_ascii=False,indent=2))
