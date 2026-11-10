#!/usr/bin/env python3
"""Synthetic staged event history without factual outcome or Action selection."""
import copy
import datetime as dt
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVENT = SourceFileLoader("test_event_owner", str(ROOT / "tools/rdg-event-owner.py")).load_module()
FIXTURE = SourceFileLoader("event_plan_fixture", str(ROOT / "tests/rdg-temporal-plan-owner.test.py")).load_module()
PLANREL = FIXTURE.REL


class EventOwnerTest(unittest.TestCase):
    def setUp(self):
        self.fixture = FIXTURE.PlanOwnerTest("test_create_edit_history_exact_snapshot_and_idempotency")
        self.fixture.event_verify_capable = True
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.apply(self.fixture.request())
        self.root, self.store = self.fixture.root, self.fixture.store
        self.admin = self.fixture.admin
        self.claimant = self.fixture.author
        self.attester = self.fixture.grant(["plan.event_attest", "plan.read"])[1]
        self.verifier = self.fixture.grant(["plan.event_verify", "plan.read"])[1]
        self.reader = self.fixture.grant(["plan.read"])[1]
        meta = EVENT.OWNER.read_snapshot(self.root, PLANREL, 1)["provenance"]
        self.pin = {"file": PLANREL, "identitySpace": meta["identitySpace"],
                    "planId": meta["planId"], "revision": 1,
                    "snapshotSHA256": meta["snapshotSHA256"],
                    "recordDigest": meta["recordDigest"]}
        self.claim = self.make_claim("C1", "positive")

    def make_claim(self, ident, outcome, supersedes=None, when="2026-10-18T10:00:00+00:00"):
        return {"id": ident, "occurrenceId": "O1", "planPin": copy.deepcopy(self.pin),
                "eventStepId": "S-RESULT", "outcome": outcome, "occurredAt": when,
                "evidenceRefs": ["EV-"+ident], "supersedes": supersedes}

    def request(self, kind, payload, expected, tx=None):
        return {"transactionId": tx or kind+"-"+payload["id"], "kind": kind,
                "file": PLANREL, "expectedRevision": expected,
                "payload": copy.deepcopy(payload)}

    def apply(self, kind, payload, expected, token=None, tx=None, callback=None):
        actor = token or {"claim": self.claimant, "attest": self.attester,
                          "verify": self.verifier}[kind]
        return EVENT.apply(self.root, self.store, actor,
                           self.request(kind, payload, expected, tx),
                           before_prepare=callback)

    def attest(self, ident="A1", claim="C1"):
        return {"id": ident, "claimId": claim, "evidenceRefs": ["EV-"+ident]}

    def verify(self, ident="V1", attestation="A1", decision="reviewed-supported"):
        return {"id": ident, "attestationId": attestation,
                "decision": decision, "evidenceRefs": ["EV-"+ident]}

    def read(self, known=None, token=None, callback=None):
        return EVENT.read(self.root, self.store, token or self.reader, PLANREL,
                          "O1", known_at=known, before_return=callback)

    def receipt(self, revision):
        return json.loads(EVENT.receipt_path(self.root, PLANREL, revision).read_text())

    @staticmethod
    def after(value, millis=1):
        return (EVENT.OWNER.instant(value) + dt.timedelta(milliseconds=millis)).isoformat()

    def test_verifier_opt_in_does_not_upgrade_existing_store(self):
        path = self.fixture.base / "legacy-grants.json"
        auth = EVENT.OWNER.AUTH.Authority(path)
        admin = auth.init_local(plan_capable=True)["token"]
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "DELEGATION_CEILING"):
            auth.manage("issue", admin, {"permissions": ["plan.event_verify"],
                "scopes": [PLANREL]})
        self.assertEqual(path.read_bytes(), before)

    def test_three_stages_are_durable_but_never_factual(self):
        original = (self.root / PLANREL).read_bytes()
        self.apply("claim", self.claim, 0)
        self.apply("attest", self.attest(), 1)
        self.apply("verify", self.verify(), 2)
        result = self.read()
        self.assertEqual([x["payload"]["id"] for x in result["claims"]], ["C1"])
        self.assertEqual([x["payload"]["id"] for x in result["attestations"]], ["A1"])
        self.assertEqual([x["payload"]["decision"] for x in result["reviews"]],
                         ["reviewed-supported"])
        self.assertEqual(result["unresolvedClaimIds"], ["C1"])
        self.assertEqual(result["claims"][0]["availableBy"], self.receipt(1)["availableBy"])
        self.assertEqual(result["attestations"][0]["availableBy"], self.receipt(2)["availableBy"])
        self.assertFalse(result["claimConflict"])
        self.assertFalse(result["provenance"]["humanIdentityVerified"])
        self.assertFalse(result["provenance"]["evidenceContentsVerified"])
        self.assertFalse(result["provenance"]["factualEventVerified"])
        self.assertFalse(result["provenance"]["factualBranchResolved"])
        self.assertFalse(result["provenance"]["actionSelected"])
        self.assertEqual((self.root / PLANREL).read_bytes(), original)

    def test_permissions_and_distinct_bearers_are_enforced(self):
        before = (self.root / PLANREL).read_bytes()
        with self.assertRaisesRegex(ValueError, "MISSING_PERMISSION: plan.event_attest"):
            self.apply("attest", self.attest(), 0, token=self.claimant)
        with self.assertRaisesRegex(ValueError, "MISSING_PERMISSION: plan.event_verify"):
            self.apply("verify", self.verify(), 0, token=self.attester)
        with self.assertRaisesRegex(ValueError, "MISSING_PERMISSION: plan.edit"):
            self.apply("claim", self.claim, 0, token=self.verifier)
        self.assertFalse(EVENT.target_path(self.root, PLANREL).exists())
        self.apply("claim", self.claim, 0, token=self.admin)
        with self.assertRaisesRegex(ValueError, "ACTOR_SEPARATION_REQUIRED"):
            self.apply("attest", self.attest(), 1, token=self.admin)
        self.apply("attest", self.attest(), 1)
        with self.assertRaisesRegex(ValueError, "ACTOR_SEPARATION_REQUIRED"):
            self.apply("verify", self.verify(), 2, token=self.admin)
        self.assertEqual((self.root / PLANREL).read_bytes(), before)

    def test_correction_preserves_old_claim_and_unlinked_conflict(self):
        self.apply("claim", self.claim, 0)
        original = EVENT.target_path(self.root, PLANREL).read_bytes()
        corrected = self.make_claim("C2", "negative", supersedes="C1",
                                     when="2026-10-18T10:30:00+00:00")
        self.apply("claim", corrected, 1)
        result = self.read()
        self.assertEqual(result["unresolvedClaimIds"], ["C2"])
        self.assertFalse(result["claimConflict"])
        self.assertEqual(json.loads(EVENT.target_path(self.root, PLANREL).read_text())[
            "records"][0], json.loads(original)["records"][0])
        unrelated = self.make_claim("C3", "positive")
        self.apply("claim", unrelated, 2)
        result = self.read()
        self.assertEqual(set(result["unresolvedClaimIds"]), {"C2", "C3"})
        self.assertTrue(result["claimConflict"])
        self.assertFalse(result["provenance"]["factualBranchResolved"])

    def test_late_claim_and_attestation_excluded_by_early_known_at(self):
        self.apply("claim", self.claim, 0)
        early = self.after(self.receipt(1)["availableBy"])
        time.sleep(0.02)
        self.apply("attest", self.attest(), 1)
        self.assertLess(EVENT.OWNER.instant(early),
                        EVENT.OWNER.instant(self.receipt(2)["availableBy"]))
        self.assertEqual(len(self.read(early)["attestations"]), 0)
        self.assertEqual(len(self.read(self.after(self.receipt(2)["availableBy"]))[
            "attestations"]), 1)
        with self.assertRaisesRegex(ValueError, "KNOWN_AT_INSTANT_REQUIRED"):
            self.read("2026-10-18")

    def test_bad_pin_outcome_time_and_reference_fail_without_write(self):
        bad = copy.deepcopy(self.claim)
        bad["planPin"]["snapshotSHA256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "PLAN_PIN_MISMATCH"):
            self.apply("claim", bad, 0)
        bad = copy.deepcopy(self.claim)
        bad["outcome"] = "unknown"
        with self.assertRaisesRegex(ValueError, "EVENT_OUTCOME_NOT_IN_PLAN"):
            self.apply("claim", bad, 0)
        bad = copy.deepcopy(self.claim)
        bad["occurredAt"] = None
        with self.assertRaisesRegex(ValueError, "EFFECTIVE_AT_REQUIRED"):
            self.apply("claim", bad, 0)
        self.assertFalse(EVENT.target_path(self.root, PLANREL).exists())
        self.apply("claim", self.claim, 0)
        with self.assertRaisesRegex(ValueError, "CLAIM_REFERENCE_INVALID"):
            self.apply("attest", self.attest(claim="Missing"), 1)
        with self.assertRaisesRegex(ValueError, "ATTESTATION_REFERENCE_INVALID"):
            self.apply("verify", self.verify(), 1)

    def test_concurrent_claim_one_cas_winner(self):
        before = (self.root / PLANREL).read_bytes()
        paths = [self.fixture.base / ("event-"+n+".json") for n in ("a", "b")]
        for path, ident in zip(paths, ("C1", "C2")):
            path.write_text(json.dumps(self.request("claim",
                self.make_claim(ident, "positive"), 0)))
        env = dict(os.environ, RDG_AUTH_TOKEN=self.claimant,
                   PYTHONDONTWRITEBYTECODE="1")
        processes = [subprocess.Popen([sys.executable,
            str(ROOT / "tools/rdg-event-owner.py"), "apply",
            "--root", str(self.root), "--store", str(self.store),
            "--request", str(path)], env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True) for path in paths]
        results = [(p.returncode, out, err) for p in processes
                   for out, err in [p.communicate(timeout=15)]]
        self.assertEqual(sorted(code for code, _, _ in results), [0, 1])
        self.assertTrue(any("CAS_MISMATCH" in err for _, _, err in results))
        self.assertEqual(len(self.read()["claims"]), 1)
        self.assertEqual((self.root / PLANREL).read_bytes(), before)

    def test_missing_prior_receipt_blocks_next_stage(self):
        self.apply("claim", self.claim, 0)
        EVENT.receipt_path(self.root, PLANREL, 1).unlink()
        with self.assertRaisesRegex(ValueError, "PREVIOUS_AVAILABILITY_BOUND_NOT_AVAILABLE"):
            self.apply("attest", self.attest(), 1)
        self.assertFalse(EVENT.journal_path(self.root).exists())

    def test_mixed_time_precision_same_occurrence_is_rejected(self):
        self.apply("claim", self.claim, 0)
        date_claim = self.make_claim("C2", "negative", when="2026-10-18")
        with self.assertRaisesRegex(ValueError, "OCCURRENCE_SCOPE_CONFLICT"):
            self.apply("claim", date_claim, 1)
        self.assertEqual(self.read()["unresolvedClaimIds"], ["C1"])

    def test_revocation_cas_and_idempotency(self):
        ident, revocable = self.fixture.grant(["plan.event_attest", "plan.read"])
        self.apply("claim", self.claim, 0)
        saved = EVENT.target_path(self.root, PLANREL).read_bytes()
        with self.assertRaisesRegex(ValueError, "AUTH_TOKEN_REVOKED"):
            self.apply("attest", self.attest(), 1, token=revocable,
                callback=lambda: self.fixture.auth.manage("revoke", self.admin, {"id": ident}))
        self.assertEqual(EVENT.target_path(self.root, PLANREL).read_bytes(), saved)
        self.apply("attest", self.attest(), 1)
        self.assertTrue(self.apply("attest", self.attest(), 1)["idempotent"])
        with self.assertRaisesRegex(ValueError, "CAS_MISMATCH"):
            self.apply("verify", self.verify(), 1)
        with self.assertRaisesRegex(ValueError, "TRANSACTION_REPLAY_CONFLICT"):
            self.apply("attest", self.attest("A2"), 1, tx="attest-A1")
        ident, reader = self.fixture.grant(["plan.read"])
        with self.assertRaisesRegex(ValueError, "AUTH_TOKEN_REVOKED"):
            self.read(token=reader,
                callback=lambda: self.fixture.auth.manage("revoke", self.admin, {"id": ident}))

    def crash(self, point):
        request_file = self.fixture.base / "event-request.json"
        request_file.write_text(json.dumps(self.request("claim", self.claim, 0)))
        env = dict(os.environ, RDG_AUTH_TOKEN=self.claimant,
                   RDG_EVENT_TEST_CRASH=point, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(ROOT / "tools/rdg-event-owner.py"),
            "apply", "--root", str(self.root), "--store", str(self.store),
            "--request", str(request_file)], env=env, capture_output=True, text=True)

    def test_recovery_prepared(self):
        p = self.crash("prepared")
        self.assertEqual(p.returncode, 91, p.stderr)
        with self.assertRaisesRegex(ValueError, "RECOVERY_REQUIRED"):
            self.read()
        self.assertTrue(EVENT.recover(self.root)["recovered"])
        self.assertEqual(self.read()["claims"][0]["payload"]["id"], "C1")
        self.assertFalse(EVENT.recover(self.root)["recovered"])

    def test_recovery_after_store(self):
        p = self.crash("after-store-write")
        self.assertEqual(p.returncode, 91, p.stderr)
        self.assertFalse(EVENT.receipt_path(self.root, PLANREL, 1).exists())
        self.assertTrue(EVENT.recover(self.root)["recovered"])
        self.assertTrue(self.apply("claim", self.claim, 0)["idempotent"])

    def test_recovery_after_receipt_preserves_time(self):
        p = self.crash("after-availability-write")
        self.assertEqual(p.returncode, 91, p.stderr)
        witness = EVENT.receipt_path(self.root, PLANREL, 1)
        original = witness.read_bytes()
        self.assertTrue(EVENT.recover(self.root)["recovered"])
        self.assertEqual(witness.read_bytes(), original)
        self.assertEqual(self.read()["unresolvedClaimIds"], ["C1"])


if __name__ == "__main__":
    unittest.main()
