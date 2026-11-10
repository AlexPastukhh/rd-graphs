#!/usr/bin/env python3
"""Real Gendocen dev25 smoke for technical event projections on temporary roots."""
import argparse
import copy
import datetime as dt
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
PROJECTION = SourceFileLoader("event_runtime_projection",
    str(ROOT / "tools/rdg-event-gendocen.py")).load_module()
EVENT, OWNER = PROJECTION.EVENT, PROJECTION.EVENT.OWNER
PLANREL = "plans/demo/plan.json"


def require(value, code):
    if not value:
        raise AssertionError(code)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+"\n")


def smoke(engine_source):
    engine = Path(engine_source).resolve() / "src"
    require((engine / "docengine/cli.py").is_file(), "GENDOCEN_SOURCE_UNAVAILABLE")
    env = {k:v for k,v in os.environ.items() if k not in ("RDG_AUTH_TOKEN", "RDG_AUTH_STORE")}
    env.update(PYTHONPATH=str(engine), PYTHONDONTWRITEBYTECODE="1")
    with tempfile.TemporaryDirectory(prefix="rdg-event-runtime-") as name:
        base = Path(name)
        owner_root, store = base/"owner", base/"grants.json"
        owner_root.mkdir()
        authority = OWNER.AUTH.Authority(store)
        admin = authority.init_local(plan_capable=True, event_verify_capable=True)["token"]
        def grant(permissions):
            return authority.manage("issue", admin, {
                "permissions":permissions, "scopes":[PLANREL]})["token"]
        creator = grant(["plan.create","plan.branch"])
        claimant = grant(["plan.edit","plan.read"])
        attester = grant(["plan.event_attest","plan.read"])
        verifier = grant(["plan.event_verify","plan.read"])
        reader = grant(["plan.read"])
        plan = json.loads((ROOT/"docs/examples/temporal-plan-candidate-v1.json").read_text())
        OWNER.apply_request(owner_root, store, creator, {
            "transactionId":"plan-create","op":"create","file":PLANREL,
            "expectedRevision":0,"plan":plan})
        plan_before = (owner_root/PLANREL).read_bytes()
        meta = OWNER.read_snapshot(owner_root, PLANREL, 1)["provenance"]
        pin = {"file":PLANREL,"identitySpace":meta["identitySpace"],"planId":meta["planId"],
               "revision":1,"snapshotSHA256":meta["snapshotSHA256"],
               "recordDigest":meta["recordDigest"]}
        revision = 0
        def append(kind, payload, token):
            nonlocal revision
            result = EVENT.apply(owner_root, store, token, {
                "transactionId":kind+"-"+payload["id"],"kind":kind,
                "file":PLANREL,"expectedRevision":revision,"payload":payload})
            revision += 1
            require(result["revision"]==revision, "EVENT_REVISION_MISMATCH")
        def claim(ident, occurrence, outcome="positive", supersedes=None):
            return {"id":ident,"occurrenceId":occurrence,"planPin":copy.deepcopy(pin),
                    "eventStepId":"S-RESULT","outcome":outcome,
                    "occurredAt":"2026-10-18T10:00:00+00:00",
                    "evidenceRefs":["EV-"+ident],"supersedes":supersedes}
        append("claim", claim("C1","O1"), claimant)
        witness = json.loads(EVENT.receipt_path(owner_root,PLANREL,1).read_text())
        cutoff = (OWNER.instant(witness["availableBy"])+dt.timedelta(milliseconds=1)).isoformat()
        time.sleep(0.02)

        project = base/"gendocen"
        (project/"docengine_project").mkdir(parents=True)
        (project/"docs/review").mkdir(parents=True)
        (project/"docengine.toml").write_text(
            '[docengine]\nconfig_version = 1\ndocumentation_root = "docs"\n'
            'structured_dir = "_structured"\ndependency_dir = "_dependency"\n'
            'project_package = "docengine_project"\n')
        targets = [("Current","_structured/events/current.json"),
                   ("Historic","_structured/events/historic.json")]
        (project/"docengine_project/__init__.py").write_text(PROJECTION.project_config(targets))
        docs = {target:project/("docs/review/"+target+".md") for target,_ in targets}
        for target,path in docs.items():
            path.write_text("# Synthetic "+target+" event context\n\nNo factual approval.\n")
        prose = {target:path.read_bytes() for target,path in docs.items()}
        def source_bytes():
            return {str(p.relative_to(owner_root)):p.read_bytes()
                    for p in owner_root.rglob("*.json")}
        def reproject():
            before = source_bytes()
            current = PROJECTION.from_owner(owner_root,store,reader,PLANREL,"O1")
            historical = PROJECTION.from_owner(owner_root,store,reader,PLANREL,"O1",cutoff)
            save(project/"docs/_structured/events/current.json",current)
            save(project/"docs/_structured/events/historic.json",historical)
            require(source_bytes()==before,"PROJECTION_WROTE_OWNER")
            return current,historical
        current,historical = reproject()
        historical_bytes = (project/"docs/_structured/events/historic.json").read_bytes()
        event_ref = PROJECTION.resource_ref(current)
        cli_count = 0
        def cli(*parts):
            nonlocal cli_count
            before = source_bytes()
            proc = subprocess.run([sys.executable,"-m","docengine.cli",*parts,
                "--project-root",str(project),"--json"],env=env,capture_output=True,text=True)
            cli_count += 1
            require(proc.stdout.strip(),"GENDOCEN_NO_JSON "+proc.stderr)
            body = json.loads(proc.stdout)
            require(body["meta"]["engine_version"]=="0.1.0.dev25","ENGINE_VERSION")
            require(source_bytes()==before,"ENGINE_WROTE_EVENT_OWNER")
            return proc.returncode,body
        def statuses():
            _,body = cli("check")
            return {x["target"].rsplit("/",1)[-1][:-3]:x["status"]
                    for x in body["data"]["results"]}
        def context(target):
            _,body = cli("explain","file://review/"+target+".md")
            return body["data"]["review_context_id"]
        def validate(target):
            code,body = cli("validate","file://review/"+target+".md",
                "--result","still-valid","--reason","Synthetic event-context review only",
                "--review-context",context(target))
            require(code==0 and body["ok"],"SYNTHETIC_REVIEW_FAILED")
        def expect(current_status):
            actual = statuses()
            require(actual=={"Current":current_status,"Historic":"valid"},
                    "UNEXPECTED_STATUSES "+repr(actual))
            require((project/"docs/_structured/events/historic.json").read_bytes()==historical_bytes,
                    "HISTORICAL_PROJECTION_CHANGED")
            require(all(path.read_bytes()==prose[target] for target,path in docs.items()),
                    "REVIEW_PROSE_CHANGED")
        def changed():
            _,body = cli("explain","file://review/Current.md")
            return sorted(body["data"]["changed_dependencies"])

        initial_code,initial = cli("sync")
        require(initial_code in (0, 2) and initial.get("ok") and
                "attention_targets" in initial.get("data", {}),
                "INITIAL_SYNC_FAILED " + json.dumps(initial, ensure_ascii=False))
        require(set(initial["data"]["attention_targets"])==
                {"file://review/Current.md","file://review/Historic.md"},"INITIAL_REVIEW")
        validate("Current");validate("Historic")
        expect("valid")
        append("claim",claim("C-OTHER","O2"),claimant)
        reproject()
        expect("valid")

        append("attest",{"id":"A1","claimId":"C1","evidenceRefs":["EV-A1"]},attester)
        reproject();expect("review_required")
        require(changed()==[event_ref+"#/reviewInputs/attestations"],"ATTESTATION_NOT_PRECISE")
        validate("Current");expect("valid")
        stale = context("Current")
        append("verify",{"id":"V1","attestationId":"A1",
               "decision":"reviewed-supported","evidenceRefs":["EV-V1"]},verifier)
        reproject();expect("review_required")
        require(changed()==[event_ref+"#/reviewInputs/reviews"],"REVIEW_NOT_PRECISE")
        state = project/"docs/_dependency/state/dependency_state.json"
        state_before = state.read_bytes()
        receipt_dir = project/"docs/_dependency/receipts"
        receipts_before = sorted(p.name for p in receipt_dir.glob("receipt-*.json"))
        code,body = cli("validate","file://review/Current.md","--result","still-valid",
            "--reason","Stale synthetic context","--review-context",stale)
        require(code!=0 and "stale" in json.dumps(body).lower(),"STALE_CONTEXT_ACCEPTED")
        require(state.read_bytes()==state_before and
                sorted(p.name for p in receipt_dir.glob("receipt-*.json"))==receipts_before,
                "STALE_REJECTION_MUTATED_RECEIPTS")
        validate("Current");expect("valid")

        append("claim",claim("C2","O1","negative","C1"),claimant)
        current,_ = reproject();expect("review_required")
        require(changed()==sorted([event_ref+"#/reviewInputs/claims",
                                  event_ref+"#/reviewInputs/resolution"]),"CORRECTION_COVERAGE")
        require(current["data"]["reviewInputs"]["resolution"]["unresolvedClaimIds"]==["C2"],
                "CORRECTION_NOT_LINKED")
        validate("Current");expect("valid")
        append("claim",claim("C3","O1"),claimant)
        current,_ = reproject();expect("review_required")
        require(current["data"]["reviewInputs"]["resolution"]["claimConflict"],"CONFLICT_HIDDEN")
        require(not current["data"]["reviewInputs"]["boundaries"]["factualEventVerified"] and
                not current["data"]["reviewInputs"]["boundaries"]["actionSelected"],
                "TECHNICAL_REVIEW_PROMOTED_TO_FACT")
        require((owner_root/PLANREL).read_bytes()==plan_before,"PLAN_CHANGED")
        require(revision==6,"EVENT_HISTORY_COUNT")
        return {"status":"PASS","engine":"Gendocen 0.1.0.dev25",
                "contract":PROJECTION.VERSION,"cliProcesses":cli_count,
                "eventOwnerRecords":revision,"temporarySourcesOnly":True,
                "attestationRequiresCurrentReview":True,
                "reviewRequiresCurrentReview":True,"staleContextRejected":True,
                "lateCorrectionRequiresCurrentReview":True,"conflictExplicit":True,
                "otherOccurrenceDoesNotInvalidate":True,
                "fixedEarlyKnownAtProjectionPreserved":True,
                "fixedEventContextReviewRemainsValid":True,
                "planAndOwnerBytesUnchangedByConsumer":True,
                "factualEventVerified":False,"historicalPlanRdgAsOfResolved":False,
                "productionStage4Accepted":False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-source",required=True,type=Path)
    args = parser.parse_args()
    print(json.dumps(smoke(args.engine_source),ensure_ascii=False,sort_keys=True,indent=2))


if __name__=="__main__":
    main()
