#!/usr/bin/env python3
"""Real writers and Gendocen on a scoped synthetic joint historical context."""
import argparse
import copy
import datetime as dt
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
JOINT = SourceFileLoader("joint_runtime_context",str(ROOT/"tools/rdg-joint-context.py")).load_module()
OWNER = JOINT.OWNER
PLANREL = "plans/demo/plan.json"
REL = "workspaces/temporal-fixture/graph.json"
TOOLS = ("rdg-authority.py graph-package.py graph-apply.py graph-index.py "
         "rdg-v7-model.py rdg-v6-action-reconsider.py rdg-v6-action-trust.py "
         "rdg-state.py rdg-state.js rdg-state-cli.cjs rdg-catalog.py "
         "rdg-catalog.js rdg-graph-api.py").split()


def require(ok,code):
    if not ok:raise AssertionError(code)


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+"\n")


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def smoke(engine_source):
    engine = Path(engine_source).resolve()/"src"
    require((engine/"docengine/cli.py").is_file(),"GENDOCEN_SOURCE_UNAVAILABLE")
    base_env = {k:v for k,v in os.environ.items()
                if k not in ("RDG_AUTH_TOKEN","RDG_AUTH_STORE","RDG_V6_TRUST_KEY")}
    with tempfile.TemporaryDirectory(prefix="rdg-joint-runtime-") as name:
        work = Path(name);(work/"tools").mkdir()
        for item in TOOLS:shutil.copy2(ROOT/"tools"/item,work/"tools"/item)
        plans,graphs,store = work/"owner",work/"graphs",work/"grants.json"
        plans.mkdir()
        auth = OWNER.AUTH.Authority(store)
        admin = auth.init_local(plan_capable=True,applicability_capable=True)["token"]
        def grant(perms,scopes):
            return auth.manage("issue",admin,{"permissions":perms,"scopes":scopes})["token"]
        graphwriter = grant(["graph.create","graph.add_action"],[REL])
        planwriter = grant(["plan.create","plan.edit","plan.branch"],[PLANREL])
        appwriter = grant(["plan.applicability.write","plan.read","graph.read"],[PLANREL,REL])
        claimant = grant(["plan.edit","plan.read"],[PLANREL])
        acceptor = grant(["plan.accept","plan.read"],[PLANREL])
        reader = grant(["plan.read","graph.read"],[PLANREL,REL])
        def write_graph(package):
            path = work/"graph-input.json";save(path,package)
            proc = subprocess.run([sys.executable,str(work/"tools/graph-apply.py"),
                "--package","--patch",str(path)],capture_output=True,text=True,
                env={**base_env,"PYTHONDONTWRITEBYTECODE":"1",
                     "RDG_AUTH_STORE":str(store),"RDG_AUTH_TOKEN":graphwriter})
            require(proc.returncode==0,"GRAPH_WRITER_FAILED "+proc.stderr)
        graph = {"schemaVersion":1,"revision":1,"id":"joint-synthetic","title":"Joint fixture",
            "identitySpace":"temporal-demo","planningScale":"module",
            "rootRequirementId":"R0","actionModel":"candidate-v6",
            "nodes":[{"id":"R0","kind":"requirement","title":"Root","status":"active"}]+[
                {"id":aid,"kind":"action","title":"Candidate "+aid,"status":"candidate","qrpe":[]}
                for aid in ("A1","A2")],
            "edges":[{"id":"E-"+aid,"type":"DRIVES","from":"R0","to":aid}
                     for aid in ("A1","A2")],"events":[]}
        write_graph({"schemaVersion":1,"transactionId":"graph-create",
                     "changes":[{"file":REL,"create":graph}]})
        graph = json.loads((graphs/REL).read_text())
        plan = json.loads((ROOT/"docs/examples/temporal-plan-candidate-v1.json").read_text())
        OWNER.apply_request(plans,store,planwriter,{"transactionId":"plan-r1","op":"create",
            "file":PLANREL,"expectedRevision":0,"plan":plan})
        def pin(revision):
            p = OWNER.read_snapshot(plans,PLANREL,revision)["provenance"]
            return {"file":PLANREL,"identitySpace":p["identitySpace"],"planId":p["planId"],
                    "revision":revision,"snapshotSHA256":p["snapshotSHA256"],
                    "recordDigest":p["recordDigest"]}
        source1 = {"schemaVersion":1,"mode":"exact-reference","lifecycle":"candidate",
            "plan":pin(1),"graphs":[{"graphFile":REL,"identitySpace":"temporal-demo",
                "revision":1,"snapshotSHA256":OWNER.digest(graph)}],
            "scenario":{"branchId":"B-RESULT","outcome":"positive"}}
        def app(ident,source,expected,supersedes=None):
            JOINT.APP.apply(plans,graphs,store,appwriter,{
                "transactionId":"app-"+ident,"file":PLANREL,"expectedRevision":expected,
                "assertion":{"id":ident,"effectiveAt":"2026-10-18T10:00:00+00:00"
                    if supersedes is None else "2026-10-18T10:30:00+00:00",
                    "supersedes":supersedes,"source":source,"eventClaim":None}})
        def event(ident,plan_pin,expected,supersedes=None,outcome="positive"):
            JOINT.EVENT_PROJECTION.EVENT.apply(plans,store,claimant,{
                "transactionId":"event-"+ident,"kind":"claim","file":PLANREL,
                "expectedRevision":expected,"payload":{"id":ident,"occurrenceId":"O1",
                    "planPin":plan_pin,"eventStepId":"S-RESULT","outcome":outcome,
                    "occurredAt":"2026-10-18T10:00:00+00:00",
                    "evidenceRefs":["EV-"+ident],"supersedes":supersedes}})
        app("A1",source1,0);event("E1",pin(1),0)
        JOINT.BASELINE.apply(plans,store,acceptor,{"transactionId":"baseline-r1","op":"accept",
            "file":PLANREL,"expectedStateRevision":0,"planPin":pin(1),
            "basis":"Synthetic technical baseline"})
        early = {"schemaVersion":1,"mode":"scoped-joint-context","lifecycle":"candidate",
            "planFile":PLANREL,"knownAt":now(),"effectiveAt":"2026-10-18T10:45:00+00:00",
            "scenario":source1["scenario"],"occurrenceId":"O1","baselineStateRevision":None}
        baseline = {**copy.deepcopy(early),"lifecycle":"accepted-future","baselineStateRevision":1}
        time.sleep(0.02)
        reconstruction = {**copy.deepcopy(early),"knownAt":now()}
        def resolve(query):
            return JOINT.resolve(plans,graphs,store,reader,query)
        def source_bytes():
            return {str(p.relative_to(work)):p.read_bytes()
                    for root in (plans,graphs) for p in root.rglob("*.json")}
        project = work/"gendocen";(project/"docengine_project").mkdir(parents=True)
        (project/"docs/review").mkdir(parents=True)
        (project/"docengine.toml").write_text(
            '[docengine]\nconfig_version = 1\ndocumentation_root = "docs"\n'
            'structured_dir = "_structured"\ndependency_dir = "_dependency"\n'
            'project_package = "docengine_project"\n')
        targets = [(target,"_structured/joint/"+target+".json")
                   for target in ("Early","Baseline","Reconstruction")]
        (project/"docengine_project/__init__.py").write_text(JOINT.project_config(targets))
        queries = {"Early":early,"Baseline":baseline,"Reconstruction":reconstruction}
        def reproject():
            before = source_bytes()
            contexts = {target:resolve(query) for target,query in queries.items()}
            for target,relative in targets:
                path = project/"docs"/relative
                resource = JOINT.project(contexts[target])
                if path.exists():
                    old = json.loads(path.read_text())
                    if old["$docengine"]["resource_id"] != resource["$docengine"]["resource_id"]:
                        archive = project/"docs/_structured/joint/archive"/(
                            old["$docengine"]["resource_id"]+".json")
                        require(not archive.exists(),"CONTEXT_RESOURCE_ID_REUSED")
                        archive.parent.mkdir(parents=True,exist_ok=True)
                        path.replace(archive)
                save(path,resource)
            require(before==source_bytes(),"CONSUMER_WROTE_SOURCES")
            return contexts
        contexts = reproject()
        early_bytes = (project/"docs/_structured/joint/Early.json").read_bytes()
        baseline_bytes = (project/"docs/_structured/joint/Baseline.json").read_bytes()
        docs = {target:project/("docs/review/"+target+".md") for target,_ in targets}
        for target,path in docs.items():path.write_text("# Synthetic "+target+" joint review\n")
        prose = {target:path.read_bytes() for target,path in docs.items()}
        engine_env = {**base_env,"PYTHONPATH":str(engine),"PYTHONDONTWRITEBYTECODE":"1"}
        cli_count = 0
        def cli(*parts):
            nonlocal cli_count
            before = source_bytes()
            proc = subprocess.run([sys.executable,"-m","docengine.cli",*parts,
                "--project-root",str(project),"--json"],env=engine_env,capture_output=True,text=True)
            cli_count += 1
            require(proc.stdout.strip(),"GENDOCEN_NO_JSON "+proc.stderr)
            result = json.loads(proc.stdout)
            require(result["meta"]["engine_version"]=="0.1.0.dev25","ENGINE_VERSION")
            require(before==source_bytes(),"GENDOCEN_WROTE_SOURCES")
            return proc.returncode,result
        def context_id(target):
            _,body = cli("explain","file://review/"+target+".md")
            return body["data"]["review_context_id"]
        def validate(target):
            code,body = cli("validate","file://review/"+target+".md",
                "--result","still-valid","--reason","Synthetic scoped context only",
                "--review-context",context_id(target))
            require(code==0 and body["ok"],"SYNTHETIC_REVIEW_FAILED")
        def expect(reconstruction_status):
            _,body = cli("check")
            actual = {x["target"].rsplit("/",1)[-1][:-3]:x["status"]
                      for x in body["data"]["results"]}
            require(actual=={"Early":"valid","Baseline":"valid",
                "Reconstruction":reconstruction_status},"WRONG_STATUSES "+json.dumps(body))
            require((project/"docs/_structured/joint/Early.json").read_bytes()==early_bytes and
                    (project/"docs/_structured/joint/Baseline.json").read_bytes()==baseline_bytes,
                    "OLD_CUTOFF_CONTEXT_CHANGED")
            require(all(p.read_bytes()==prose[t] for t,p in docs.items()),"PROSE_CHANGED")
        code,body = cli("sync")
        require(code in (0,2) and body["ok"] and len(body["data"]["attention_targets"])==3,
                "INITIAL_SYNC_FAILED "+json.dumps(body))
        for target in docs:validate(target)
        expect("valid")
        stale = context_id("Reconstruction")

        write_graph({"schemaVersion":1,"transactionId":"graph-add",
            "changes":[{"file":REL,"patch":{"schemaVersion":1,"expectedRevision":1,
                "operations":[{"op":"add_action","requirementId":"R0","action":{
                    "id":"A3","kind":"action","title":"Later candidate A3",
                    "status":"candidate","qrpe":[]}}]}}]})
        graph2 = json.loads((graphs/REL).read_text())
        plan2 = copy.deepcopy(plan);plan2["revision"]=2;plan2["title"]="Later candidate"
        for step in plan2["steps"]:
            if step["kind"]=="action":step["actionRef"]["observedGraphRevision"]=2
        OWNER.apply_request(plans,store,planwriter,{"transactionId":"plan-r2","op":"edit",
            "file":PLANREL,"expectedRevision":1,"plan":plan2})
        source2 = copy.deepcopy(source1);source2["plan"]=pin(2)
        source2["graphs"][0].update(revision=2,snapshotSHA256=OWNER.digest(graph2))
        app("A2",source2,1,"A1");event("E2",pin(2),1,"E1")
        queries["Reconstruction"]["knownAt"]=now()
        contexts = reproject()
        require(contexts["Reconstruction"]["plan"]["pin"]["revision"]==2 and
                contexts["Reconstruction"]["graphs"][0]["pin"]["revision"]==2,"LATE_REVISIONS")
        expect("review_required")
        state = project/"docs/_dependency/state/dependency_state.json"
        before_state = state.read_bytes()
        receipts = project/"docs/_dependency/receipts"
        before_receipts = sorted(p.name for p in receipts.glob("receipt-*.json"))
        code,body = cli("validate","file://review/Reconstruction.md","--result","still-valid",
            "--reason","Stale synthetic joint query","--review-context",stale)
        require(code!=0 and "stale" in json.dumps(body).lower(),"STALE_CONTEXT_ACCEPTED")
        require(state.read_bytes()==before_state and
                sorted(p.name for p in receipts.glob("receipt-*.json"))==before_receipts,
                "STALE_REJECTION_MUTATED_STATE")
        validate("Reconstruction");expect("valid")
        event("E3",pin(2),2,outcome="negative")
        conflicted = {**copy.deepcopy(queries["Reconstruction"]),"knownAt":now()}
        try:resolve(conflicted)
        except ValueError as error:require("EVENT_CLAIM_CONFLICT" in str(error),"WRONG_CONFLICT_ERROR")
        else:raise AssertionError("CONFLICTED_NEW_QUERY_RESOLVED")
        reproject();expect("valid")
        require(all(n.get("status")=="candidate" for n in graph2["nodes"] if n["kind"]=="action")
                and graph2["events"]==[],"ACTION_SELECTED")
        return {"status":"PASS","engine":"Gendocen 0.1.0.dev25","contract":JOINT.VERSION,
            "cliProcesses":cli_count,"temporarySourcesOnly":True,"realGraphWriter":True,
            "earlyPlanRdgEventContextPreserved":True,"exactBaselineContextPreserved":True,
            "lateReconstructionRequiresReview":True,"staleContextRejected":True,
            "conflictedNewQueryRejected":True,"sourceBytesUnchangedByConsumer":True,
            "automaticBaselineEffectiveSelectionComplete":False,
            "completeApplicableContextVerified":False,"factualEventVerified":False,
            "historicalT1KnowledgeVerified":False,"productionStage4Accepted":False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-source",required=True,type=Path)
    args = parser.parse_args()
    print(json.dumps(smoke(args.engine_source),ensure_ascii=False,sort_keys=True,indent=2))


if __name__=="__main__":main()
