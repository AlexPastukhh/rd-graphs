#!/usr/bin/env python3
"""Real temporary Plan owner/authority transactions; no project graph writes."""
import copy
from importlib.machinery import SourceFileLoader
import json
import multiprocessing as mp
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
OWNER = SourceFileLoader("test_plan_owner", str(ROOT / "tools/rdg-temporal-plan-owner.py")).load_module()
ADAPTER = SourceFileLoader("test_owned_adapter", str(ROOT / "tools/rdg-gendocen-adapter.py")).load_module()
REL = "plans/demo/plan.json"
PERMS = ["plan.create", "plan.edit", "plan.branch", "plan.read"]


def worker(root, store, token, request, queue, ready=None, proceed=None):
    def pause():
        ready.set()
        if not proceed.wait(15):
            raise RuntimeError("test barrier timeout")
    try:
        result = OWNER.apply_request(root, store, token, request, pause if ready else None)
        queue.put(("ok", result))
    except Exception as exc:
        queue.put(("error", str(exc)))


class PlanOwnerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdg-owner-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "plans-owner"
        self.root.mkdir()
        self.store = self.base / "grants.json"
        self.auth = OWNER.AUTH.Authority(self.store)
        self.admin = self.auth.init_local(plan_capable=True,
            event_verify_capable=getattr(self, "event_verify_capable", False), graph_read_capable=True)["token"]
        self.author_id, self.author = self.grant(PERMS)
        self.plan = json.loads((ROOT / "docs/examples/temporal-plan-candidate-v1.json").read_text())
        core = SourceFileLoader('plan_owner_reference_fixture_core', str(ROOT/'tools/rdg-core-model.py')).load_module()
        graph = core.blank('synthetic-reference-owner', 'Synthetic reference owner', 'temporal-demo',
                           'R1', 'Synthetic result', 'Isolated Plan writer tests')
        for ident in ('A1', 'A2'):
            graph, _ = core.apply(graph, {'schemaVersion':1,'expectedRevision':graph['revision'],
                'operations':[{'op':'graph_edit','action':'core_add',
                    'data':{'entity':{'id':ident,'kind':'action','title':ident}},
                    'event':{'id':'ADD-'+ident,'type':'requested','by':'assistant','note':'Synthetic reference fixture','verifiedTrustReceipt':{'mode':'test-only'}}}]}, True)
        self.graph_path = self.root/'graphs/workspaces/temporal-fixture/graph.json'
        self.graph_path.parent.mkdir(parents=True)
        self.graph_path.write_text(json.dumps(graph))

    def grant(self, permissions, scopes=None):
        permissions = list(permissions)
        if any(p.startswith('plan.') for p in permissions) and 'graph.read' not in permissions:
            permissions.append('graph.read')
        result = self.auth.manage("issue", self.admin, {"permissions": permissions,
            "scopes": scopes or ["plans/", "workspaces/"]})
        return result["id"], result["token"]

    def request(self, op="create", expected=0, plan=None, tx=None, file=REL):
        return {"transactionId": tx or op + "-" + str(expected), "op": op,
                "file": file, "expectedRevision": expected, "plan": copy.deepcopy(plan or self.plan)}

    def apply(self, request, token=None):
        return OWNER.apply_request(self.root, self.store, token or self.author, request)

    def source_bytes(self, root=None):
        root = root or self.root
        return {str(f.relative_to(root)): f.read_bytes() for f in root.rglob("*.json")}

    def test_current_placement_requires_existing_graph_identity_and_node(self):
        original = self.graph_path.read_bytes()
        for change in ('missing-graph', 'identity', 'missing-node', 'wrong-kind'):
            self.graph_path.write_bytes(original)
            graph = json.loads(original)
            if change == 'missing-graph':self.graph_path.unlink()
            else:
                if change == 'identity':graph['identitySpace'] = 'wrong-owner'
                if change == 'missing-node':graph['nodes'] = [n for n in graph['nodes'] if n['id'] != 'A1']
                if change == 'wrong-kind':next(n for n in graph['nodes'] if n['id'] == 'A1')['kind'] = 'requirement'
                self.graph_path.write_text(json.dumps(graph))
            before = self.source_bytes()
            with self.assertRaisesRegex(ValueError, 'PLAN_REFERENCE_'):
                self.apply(self.request(tx='invalid-reference-'+change))
            self.assertEqual(before, self.source_bytes())
            self.assertFalse((self.root/OWNER.JOURNAL).exists())
        self.graph_path.write_bytes(original)

    def test_reference_graph_final_cas_prevents_raw_concurrent_removal(self):
        def external_edit():
            graph = json.loads(self.graph_path.read_bytes())
            graph['nodes'] = [n for n in graph['nodes'] if n['id'] != 'A1']
            self.graph_path.write_text(json.dumps(graph))
        with self.assertRaisesRegex(ValueError, 'REFERENCE_CHANGED_DURING_PREPARE'):
            OWNER.apply_request(self.root, self.store, self.author, self.request(), before_prepare=external_edit)
        self.assertFalse((self.root/REL).exists())
        self.assertFalse((self.root/OWNER.JOURNAL).exists())

    def test_create_edit_history_exact_snapshot_and_idempotency(self):
        create = self.request()
        self.apply(create)
        original = OWNER.read_snapshot(self.root, REL, 1)
        changed = copy.deepcopy(self.plan)
        changed["revision"] = 2
        changed["title"] = "Synthetic next version"
        self.apply(self.request("edit", 1, changed))
        before = self.source_bytes()
        repeated = self.apply(create)
        self.assertTrue(repeated["idempotent"])
        self.assertEqual(before, self.source_bytes())
        self.assertEqual(OWNER.read_snapshot(self.root, REL, 1), original)
        self.assertEqual(OWNER.read_snapshot(self.root, REL)["plan"]["title"], changed["title"])
        self.assertTrue(original["provenance"]["exactPlanSnapshotResolved"])
        self.assertFalse(original["provenance"]["historicalRdgSnapshotResolved"])
        self.assertNotIn(self.author, (self.root / REL).read_text())
        conflicting = copy.deepcopy(create)
        conflicting["plan"]["title"] = "Different retry"
        with self.assertRaisesRegex(ValueError, "TRANSACTION_REPLAY_CONFLICT"):
            self.apply(conflicting)
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_NOT_FOUND"):
            OWNER.read_snapshot(self.root, REL, 999)

    def test_recorded_placement_history_includes_schedule_only_revisions(self):
        self.apply(self.request())
        first=OWNER.read_placement_history(self.root,REL)
        self.assertEqual(len([r for r in first if r['kind']=='plan_created']),1)
        self.assertEqual(len([r for r in first if r['kind']=='plan_placement_saved']),2)
        changed=copy.deepcopy(self.plan)
        changed['revision']=2
        changed['timeConstraints'].append({'stepId':'S-A1','type':'notBefore',
            'at':'2026-11-10','strength':'soft','basis':'A new actual schedule edit'})
        self.apply(self.request('edit',1,changed,tx='plan-change-time-only'))
        recorded=OWNER.read_placement_history(self.root,REL)
        moved=[r for r in recorded if r.get('planRevision')==2 and
            r['kind']=='plan_placement_saved']
        self.assertEqual([r['stepId'] for r in moved],['S-A1'])
        self.assertEqual(moved[0]['previousPlacementSnapshot']['timeConstraints'],[])
        self.assertEqual(moved[0]['newPlacementSnapshot']['timeConstraints'][0]['at'],'2026-11-10')
        self.assertEqual(moved[0]['transactionId'],'plan-change-time-only')

    def test_latest_plan_has_post_write_availability_receipt(self):
        create = self.request()
        self.apply(create)
        saved = OWNER.read_snapshot(self.root, REL, 1)
        receipt = OWNER.read_availability(self.root, REL, 1,
                                          saved["provenance"]["recordDigest"])
        self.assertEqual(receipt["sourcePath"], REL)
        self.assertEqual(receipt["revision"], 1)
        self.assertGreaterEqual(OWNER.instant(receipt["availableBy"]),
                                OWNER.instant(saved["provenance"]["recordedAt"]))
        before = self.source_bytes()
        self.assertTrue(self.apply(create)["idempotent"])
        self.assertEqual(self.source_bytes(), before)
        with self.assertRaisesRegex(ValueError, "AVAILABILITY_RECORD_MISMATCH"):
            OWNER.read_availability(self.root, REL, 1, "0"*64)

    def test_recovery_after_availability_receipt_preserves_its_time(self):
        self.apply(self.request())
        self.crash_edit("after-availability-write")
        witness = self.root / "plans/demo/.rdg-plan-available-r2.json"
        before = witness.read_bytes()
        with self.assertRaisesRegex(ValueError, "RECOVERY_REQUIRED"):
            OWNER.read_snapshot(self.root, REL, 2)
        self.assertTrue(OWNER.recover(self.root)["recovered"])
        self.assertEqual(witness.read_bytes(), before)
        saved = OWNER.read_snapshot(self.root, REL, 2)
        self.assertEqual(OWNER.read_availability(self.root, REL, 2,
                         saved["provenance"]["recordDigest"])["availableBy"],
                         json.loads(before)["availableBy"])

    def test_corrupt_availability_receipt_fails_closed(self):
        self.apply(self.request())
        witness = self.root / "plans/demo/.rdg-plan-available-r1.json"
        data = json.loads(witness.read_text())
        data["recordDigest"] = "0"*64
        witness.write_text(json.dumps(data))
        meta = OWNER.read_snapshot(self.root, REL, 1)["provenance"]
        with self.assertRaisesRegex(ValueError, "AVAILABILITY_RECEIPT_INVALID"):
            OWNER.read_availability(self.root, REL, 1, meta["recordDigest"])

    def test_branch_permission_and_graph_permissions_remain_separate(self):
        _, create_only = self.grant(["plan.create"])
        before = self.source_bytes()
        with self.assertRaisesRegex(ValueError, "MISSING_PERMISSION: plan.branch"):
            self.apply(self.request(), create_only)
        self.assertEqual(before, self.source_bytes())
        self.apply(self.request())
        changed = copy.deepcopy(self.plan)
        changed["revision"] = 2
        cases = changed["branches"][0]["cases"]
        cases[0]["stepIds"], cases[1]["stepIds"] = cases[1]["stepIds"], cases[0]["stepIds"]
        _, editor = self.grant(["plan.edit"])
        before = self.source_bytes()
        with self.assertRaisesRegex(ValueError, "MISSING_PERMISSION: plan.branch"):
            self.apply(self.request("edit", 1, changed), editor)
        self.assertEqual(before, self.source_bytes())
        self.apply(self.request("branch", 1, changed))
        _, graph_only = self.grant(["graph.write"], ["plans/", "workspaces/"])
        with self.assertRaisesRegex(ValueError, "MISSING_PERMISSION: plan.create"):
            self.apply(self.request(file="plans/other/plan.json"), graph_only)
        _, plan_only = self.grant(PERMS, ["plans/", "workspaces/"])
        with self.assertRaisesRegex(ValueError, "MISSING_PERMISSION: graph.create"):
            self.auth.authorize_package(plan_only, {"changes": [{"file": "workspaces/x/graph.json", "create": {"nodes": [], "events": []}}]})

    def test_cosmetic_case_reorder_does_not_require_branch_permission(self):
        self.apply(self.request())
        changed = copy.deepcopy(self.plan)
        changed["revision"] = 2
        changed["branches"][0]["cases"].reverse()
        for step in changed["steps"]:
            if step["kind"] == "event":
                step["outcomes"].reverse()
        _, editor = self.grant(["plan.edit"])
        self.apply(self.request("edit", 1, changed, tx="cosmetic"), editor)
        self.assertEqual(OWNER.read_snapshot(self.root, REL)["plan"]["revision"], 2)

    def test_unexpected_source_edit_during_prepare_is_not_overwritten(self):
        self.apply(self.request())
        changed = copy.deepcopy(self.plan)
        changed["revision"] = 2
        path = self.root / REL
        def external_edit():
            path.write_text(path.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "SOURCE_CHANGED_DURING_PREPARE"):
            OWNER.apply_request(self.root, self.store, self.author,
                self.request("edit", 1, changed), before_prepare=external_edit)
        self.assertTrue(path.read_text().endswith(" "))
        self.assertFalse((self.root / OWNER.JOURNAL).exists())

    def test_accepted_and_actual_event_claims_fail_unchanged(self):
        self.apply(self.request())
        before = self.source_bytes()
        for op in ("accept", "event_attest", "select_action"):
            with self.assertRaisesRegex(ValueError, "CANDIDATE_OPERATIONS_ONLY"):
                self.apply(self.request(op, 1))
        for key, value in [("status", "accepted"), ("actualEvents", []), ("selectedCase", "positive")]:
            plan = copy.deepcopy(self.plan)
            plan["revision"] = 2
            plan[key] = value
            with self.assertRaises(ValueError):
                self.apply(self.request("edit", 1, plan, tx="invalid-" + key))
        self.assertEqual(before, self.source_bytes())

    def test_owner_binding_collision_paths_and_symlinks(self):
        self.apply(self.request())
        before = self.source_bytes()
        with self.assertRaisesRegex(ValueError, "DUPLICATE_WRITABLE_OWNER"):
            self.apply(self.request(file="plans/copy/plan.json", tx="duplicate"))
        for path in ("../plan.json", "/tmp/plan.json", "plans/x/../../plan.json"):
            with self.assertRaisesRegex(ValueError, "PATH_INVALID"):
                self.apply(self.request(file=path, tx="badpath"))
        outside = self.base / "outside"
        outside.mkdir()
        (self.root / "plans/link").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "SYMLINK_DENIED"):
            self.apply(self.request(file="plans/link/plan.json", tx="symlink"))
        self.assertEqual(before, self.source_bytes())
        self.assertEqual(list(outside.iterdir()), [])

    def test_identity_change_and_stale_cas_fail_without_writes(self):
        self.apply(self.request())
        before = self.source_bytes()
        changed = copy.deepcopy(self.plan)
        changed["revision"] = 2
        changed["id"] = "P-OTHER"
        with self.assertRaisesRegex(ValueError, "OWNER_IDENTITY_IMMUTABLE"):
            self.apply(self.request("edit", 1, changed))
        changed["id"] = self.plan["id"]
        with self.assertRaisesRegex(ValueError, "CAS_MISMATCH"):
            self.apply(self.request("edit", 0, changed))
        self.assertEqual(before, self.source_bytes())

    def test_two_real_processes_have_one_cas_winner(self):
        self.apply(self.request())
        queue = mp.Queue()
        processes = []
        for i in range(2):
            changed = copy.deepcopy(self.plan)
            changed["revision"] = 2
            changed["title"] = "Writer " + str(i)
            process = mp.Process(target=worker, args=(self.root, self.store, self.author,
                self.request("edit", 1, changed, tx="race-" + str(i)), queue))
            process.start()
            processes.append(process)
        for process in processes:
            process.join(20)
            self.assertFalse(process.is_alive())
        results = [queue.get(timeout=2) for _ in processes]
        self.assertEqual(sum(kind == "ok" for kind, _ in results), 1)
        self.assertTrue(any("CAS_MISMATCH" in str(value) for kind, value in results if kind == "error"))
        store = json.loads((self.root / REL).read_text())
        self.assertEqual(len(store["versions"]), 2)

    def test_revoke_before_durable_prepare_denies_real_process(self):
        self.apply(self.request())
        before = self.source_bytes()
        ident, token = self.grant(["plan.edit"])
        changed = copy.deepcopy(self.plan)
        changed["revision"] = 2
        ready, proceed, queue = mp.Event(), mp.Event(), mp.Queue()
        process = mp.Process(target=worker, args=(self.root, self.store, token,
            self.request("edit", 1, changed, tx="revoke-before"), queue, ready, proceed))
        process.start()
        try:
            self.assertTrue(ready.wait(10))
            self.auth.manage("revoke", self.admin, {"id": ident})
            proceed.set()
            process.join(15)
            kind, result = queue.get(timeout=2)
            self.assertEqual(kind, "error")
            self.assertIn("TOKEN_REVOKED", result)
            self.assertEqual(before, self.source_bytes())
        finally:
            proceed.set()
            if process.is_alive():
                process.terminate()
                process.join()

    def crash_edit(self, phase):
        changed = copy.deepcopy(self.plan)
        changed["revision"] = 2
        changed["title"] = "Accepted technical transaction before crash"
        ident, token = self.grant(["plan.edit"])
        request = self.base / "crash-request.json"
        request.write_text(json.dumps(self.request("edit", 1, changed, tx="crash-" + phase)))
        result = subprocess.run([sys.executable, str(ROOT / "tools/rdg-temporal-plan-owner.py"),
            "apply", "--root", str(self.root), "--store", str(self.store), "--request", str(request)],
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "RDG_AUTH_TOKEN": token, "RDG_PLAN_TEST_CRASH": phase},
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 91, result.stderr)
        return ident

    def test_crash_after_prepare_recover_after_revoke_is_idempotent(self):
        self.apply(self.request())
        original = OWNER.read_snapshot(self.root, REL, 1)
        ident = self.crash_edit("prepared")
        with self.assertRaisesRegex(ValueError, "RECOVERY_REQUIRED"):
            OWNER.read_snapshot(self.root, REL)
        self.auth.manage("revoke", self.admin, {"id": ident})
        self.assertTrue(OWNER.recover(self.root)["recovered"])
        self.assertEqual(OWNER.read_snapshot(self.root, REL)["plan"]["revision"], 2)
        self.assertEqual(OWNER.read_snapshot(self.root, REL, 1), original)
        before = self.source_bytes()
        self.assertTrue(OWNER.recover(self.root)["idempotent"])
        self.assertEqual(before, self.source_bytes())

    def test_crash_after_source_write_blocks_projection_until_recover(self):
        self.apply(self.request())
        self.crash_edit("after-plan-write")
        with self.assertRaisesRegex(ValueError, "RECOVERY_REQUIRED"):
            ADAPTER.plan_resource(self.root / REL, plan_root=self.root)
        OWNER.recover(self.root)
        projection = ADAPTER.plan_resource(self.root / REL, plan_root=self.root)
        self.assertEqual(projection["data"]["sourceRevision"], 2)
        self.assertEqual(projection["data"]["sourcePath"], REL)
        self.assertTrue(projection["data"]["ownerVersion"]["exactPlanSnapshotResolved"])
        meta = OWNER.read_snapshot(self.root, REL, 2)["provenance"]
        self.assertIsNotNone(OWNER.read_availability(self.root, REL, 2,
                                                     meta["recordDigest"]))

    def test_corrupt_journal_does_not_overwrite_source(self):
        self.apply(self.request())
        original = (self.root / REL).read_bytes()
        self.crash_edit("prepared")
        journal_path = self.root / OWNER.JOURNAL
        journal = json.loads(journal_path.read_text())
        journal["writes"][0]["after"]["versions"][-1]["plan"]["title"] = "Corrupted"
        journal_path.write_text(json.dumps(journal))
        with self.assertRaisesRegex(ValueError, "HISTORY_HASH_OR_IDENTITY"):
            OWNER.recover(self.root)
        self.assertEqual((self.root / REL).read_bytes(), original)
        self.assertTrue(journal_path.exists())

    def test_recovery_conflict_preserves_unexpected_bytes(self):
        self.apply(self.request())
        self.crash_edit("prepared")
        path = self.root / REL
        path.write_text(path.read_text() + " ")
        before = self.source_bytes()
        with self.assertRaisesRegex(ValueError, "RECOVERY_CONFLICT"):
            OWNER.recover(self.root)
        self.assertEqual(before, self.source_bytes())

    def test_owned_projection_requires_explicit_root_and_detects_corrupt_history(self):
        self.apply(self.request())
        with self.assertRaisesRegex(ValueError, "PLAN_OWNER_ROOT_REQUIRED"):
            ADAPTER.plan_resource(self.root / REL)
        projection = ADAPTER.plan_resource(self.root / REL, plan_root=self.root)
        self.assertEqual(projection["data"]["planStatus"], "candidate")
        store = json.loads((self.root / REL).read_text())
        store["versions"][0]["plan"]["title"] = "Tampered old snapshot"
        (self.root / REL).write_text(json.dumps(store))
        with self.assertRaisesRegex(ValueError, "HISTORY_HASH_OR_IDENTITY"):
            ADAPTER.plan_resource(self.root / REL, plan_root=self.root)


if __name__ == "__main__":
    unittest.main()
