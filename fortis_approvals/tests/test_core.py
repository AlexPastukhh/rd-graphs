"""G1 isolated acceptance: not a live owner proof or integration test."""
import hashlib
import hmac
from pathlib import Path
import tempfile
import threading
import unittest
import uuid

from fortis_approvals.core import Core, Authenticator, Denied, Conflict
from fortis_approvals.synthetic import SyntheticAdapter


class SyntheticOwnerVerifier:
    """TEST ONLY. Deliberately not shipped in the production core package."""
    def __init__(self, secret=b'synthetic-owner-secret'):
        self.secret = secret

    def proof(self, request_id, fingerprint, decision, owner='test-owner'):
        msg = f'{request_id}/{fingerprint}/{decision}/{owner}'.encode()
        return {'owner': owner, 'mac': hmac.new(self.secret, msg, hashlib.sha256).hexdigest()}

    def verify(self, request_id, fingerprint, decision, proof):
        if not isinstance(proof, dict) or set(proof) != {'owner', 'mac'}:
            raise Denied('OWNER_PROOF_REQUIRED')
        owner = proof['owner']
        if owner != 'test-owner' or not isinstance(proof['mac'], str):
            raise Denied('OWNER_PROOF_INVALID')
        expected = self.proof(request_id, fingerprint, decision, owner)['mac']
        if not hmac.compare_digest(expected, proof['mac']):
            raise Denied('OWNER_PROOF_INVALID')
        return owner


class G1Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='fortis-g1-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.adapter = SyntheticAdapter(self.path / 'synthetic.sqlite')
        self.adapter.seed('record', 'before')
        self.owner = SyntheticOwnerVerifier()
        self.auth = Authenticator({'client-1-secret': 'agent-1', 'client-2-secret': 'agent-2'})
        self.policies = {
            ('synthetic', 'set_free'): 'ALLOW',
            ('synthetic', 'set_ask'): 'ASK',
            ('synthetic', 'set_deny'): 'DENY',
        }
        self.now = 1000
        self.core = self.new_core()

    def new_core(self, **kwargs):
        return Core(self.path / 'approvals.sqlite', adapters={'synthetic': self.adapter},
                    policies=self.policies, authenticator=self.auth,
                    owner_verifier=kwargs.get('owner_verifier', self.owner),
                    policy_version=kwargs.get('policy_version', 'v1'),
                    clock=lambda: self.now, expiry_seconds=kwargs.get('expiry_seconds', 3600))

    def request(self, op='set_ask', value='after', version=0, **extra):
        return dict(requestId=str(uuid.uuid4()), service='synthetic', operation=op,
                    target='record', params={'value': value}, expectedVersion=version,
                    reason='synthetic change', **extra)

    def submit(self, value, credential='client-1-secret'):
        return self.core.client(credential, 'submit', value)

    def approve(self, view, decision='approve', core=None):
        core = core or self.core
        proof = self.owner.proof(view['requestId'], view['fingerprint'], decision)
        return core.owner_decide(view['requestId'], decision, proof)

    def test_allow_is_immediate_one_executor(self):
        req = self.request(op='set_free')
        v = self.submit(req)
        self.assertEqual(v['state'], 'EXECUTED')
        self.assertEqual(self.adapter.get('record'), {'value': 'after', 'version': 1})
        self.assertEqual([x['state'] for x in self.core.events(req['requestId'])],
                         ['APPROVED', 'DISPATCHED', 'EXECUTED'])

    def test_ask_holds_until_verified_owner_decision(self):
        v = self.submit(self.request())
        self.assertEqual(v['state'], 'PENDING')
        self.assertEqual(self.adapter.get('record')['value'], 'before')
        v = self.approve(v)
        self.assertEqual(v['state'], 'EXECUTED')
        self.assertEqual(v['owner'], 'test-owner')
        self.assertEqual(self.adapter.get('record')['value'], 'after')
        self.assertEqual([x['state'] for x in self.core.events(v['requestId'])],
                         ['PENDING', 'APPROVED', 'DISPATCHED', 'EXECUTED'])

    def test_reject_does_not_execute(self):
        v = self.submit(self.request())
        out = self.approve(v, 'reject')
        self.assertEqual(out['state'], 'REJECTED')
        self.assertEqual(self.adapter.get('record')['version'], 0)
        self.assertIsNone(self.adapter.receipt(v['requestId']))
        with self.assertRaises(Denied):
            self.approve(v)

    def test_unknown_and_denied_operations_fail_closed(self):
        for operation in ('set_deny', 'unknown'):
            with self.subTest(operation=operation), self.assertRaises(Denied):
                self.submit(self.request(op=operation))
        self.assertEqual(self.adapter.get('record')['version'], 0)

    def test_untrusted_payload_identity_and_fields_rejected(self):
        for field, value in [('actor', 'user'), ('approved', True), ('url', 'http://rdg')]:
            req = self.request()
            req[field] = value
            with self.subTest(field=field), self.assertRaises(Denied):
                self.submit(req)
        with self.assertRaises(Denied):
            self.core.client('unknown-secret', 'submit', self.request())
        with self.assertRaises(Denied):
            self.core.client('client-1-secret', 'owner_decide', {'approved': True})

    def test_cannot_self_approve_or_forge_owner(self):
        v = self.submit(self.request())
        for proof in ({'approved': True, 'by': 'user'}, {},
                      self.owner.proof(v['requestId'], v['fingerprint'], 'reject')):
            with self.assertRaises(Denied):
                self.core.owner_decide(v['requestId'], 'approve', proof)
        self.assertEqual(self.core.client('client-1-secret', 'status', v['requestId'])['state'], 'PENDING')
        no_verifier = self.new_core(owner_verifier=None)
        with self.assertRaises(Denied):
            no_verifier.owner_decide(v['requestId'], 'approve', {})

    def test_fingerprint_binds_frozen_preview(self):
        v = self.submit(self.request())
        import hashlib
        from fortis_approvals.core import canonical
        expected = hashlib.sha256(canonical({
            'actor':'agent-1', 'request':v['request'], 'policyVersion':'v1',
            'preview':v['preview']}).encode()).hexdigest()
        self.assertEqual(v['fingerprint'], expected)
        alternate = hashlib.sha256(canonical({
            'actor':'agent-1', 'request':v['request'], 'policyVersion':'v1',
            'preview':{**v['preview'], 'after':{'value':'tampered','version':1}}}).encode()).hexdigest()
        self.assertNotEqual(expected, alternate)

    def test_exact_replay_and_request_id_conflict(self):
        request = self.request()
        a = self.submit(request)
        self.assertEqual(a['fingerprint'], self.submit(request)['fingerprint'])
        altered = {**request, 'params': {'value': 'different'}}
        with self.assertRaises(Conflict):
            self.submit(altered)
        with self.assertRaises(Conflict):
            self.submit(request, 'client-2-secret')
        self.assertEqual(len(self.core.events(a['requestId'])), 1)

    def test_status_is_requester_scoped(self):
        v = self.submit(self.request())
        with self.assertRaises(Denied):
            self.core.client('client-2-secret', 'status', v['requestId'])
        self.assertEqual(self.core.client('client-1-secret', 'status', v['requestId'])['state'], 'PENDING')

    def test_stale_after_external_change(self):
        v = self.submit(self.request())
        self.adapter.seed('other', 'irrelevant')
        # Simulate another legitimate writer using a separate object transaction.
        with self.adapter._db() as db:
            db.execute('UPDATE objects SET value=?,version=? WHERE id=?', ('changed', 1, 'record'))
        out = self.approve(v)
        self.assertEqual(out['state'], 'STALE')
        self.assertEqual(self.adapter.get('record')['value'], 'changed')
        self.assertIsNone(self.adapter.receipt(v['requestId']))

    def test_expiration_is_durable_and_no_execution(self):
        self.core = self.new_core(expiry_seconds=5)
        v = self.submit(self.request())
        self.now += 6
        out = self.approve(v)
        self.assertEqual(out['state'], 'EXPIRED')
        self.assertEqual(self.adapter.get('record')['version'], 0)
        with self.assertRaises(Denied):
            self.approve(v)

    def test_initiator_revocation_blocks_waiting_action(self):
        v = self.submit(self.request())
        self.auth.revoke('client-1-secret')
        with self.assertRaises(Denied):
            self.core.client('client-1-secret', 'status', v['requestId'])
        self.assertEqual(self.approve(v)['state'], 'REVOKED')
        self.assertEqual(self.adapter.get('record')['version'], 0)

    def test_actor_target_policy_and_parameter_predicate(self):
        self.core.policies[('agent-1', 'synthetic', 'set_ask', 'record')] = (
            lambda actor, req: 'DENY' if req['params']['value'] == 'forbidden' else 'ASK')
        with self.assertRaises(Denied):
            self.submit(self.request(value='forbidden'))
        v = self.submit(self.request())
        self.assertEqual(v['state'], 'PENDING')
        self.assertEqual(self.approve(v)['state'], 'EXECUTED')

    def test_approved_request_expires_before_execution(self):
        v = self.submit(self.request())
        with self.core._db() as db:
            db.execute('UPDATE requests SET state=?, decision=?,owner=? WHERE id=?',
                       ('APPROVED', 'approve', 'test-owner', v['requestId']))
        self.now = v['expiresAt'] + 1
        self.assertEqual(self.core.execute(v['requestId'])['state'], 'EXPIRED')
        self.assertEqual(self.adapter.get('record')['version'], 0)

    def test_domain_revalidation_failure_is_terminal(self):
        v = self.submit(self.request())
        original = self.adapter.prepare
        def forbidden(_):
            raise Denied('DOMAIN_RESTRICTED')
        self.adapter.prepare = forbidden
        self.assertEqual(self.approve(v)['state'], 'STALE')
        self.assertEqual(self.adapter.get('record')['version'], 0)
        self.adapter.prepare = original
        self.assertEqual(self.core.execute(v['requestId'])['state'], 'STALE')

    def test_policy_revocation_or_version_change_blocks_pending(self):
        v = self.submit(self.request())
        self.core.policies[('synthetic', 'set_ask')] = 'DENY'
        with self.assertRaisesRegex(Denied, 'OWNER_POLICY_CHANGED'):
            self.approve(v)
        self.assertEqual(self.core._read(v['requestId'])['state'], 'PENDING')
        self.assertIsNone(self.adapter.receipt(v['requestId']))

    def test_policy_version_change_blocks_pending(self):
        v = self.submit(self.request())
        fresh_core = self.new_core(policy_version='v2')
        with self.assertRaisesRegex(Denied, 'OWNER_POLICY_CHANGED'):
            self.approve(v, core=fresh_core)
        self.assertEqual(fresh_core._read(v['requestId'])['state'], 'PENDING')

    def test_restart_preserves_pending_and_executes_once(self):
        v = self.submit(self.request())
        restart = self.new_core()
        out = self.approve(v, core=restart)
        self.assertEqual(out['state'], 'EXECUTED')
        self.assertEqual(self.new_core().client('client-1-secret', 'status', v['requestId'])['state'], 'EXECUTED')
        self.assertEqual(restart.execute(v['requestId'])['state'], 'EXECUTED')
        self.assertEqual(self.adapter.get('record')['version'], 1)

    def test_timeout_after_durable_remote_commit_never_double_applies(self):
        v = self.submit(self.request())
        self.adapter.fail_after_commit_once = True
        out = self.approve(v)
        self.assertEqual(out['state'], 'UNCERTAIN')
        self.assertEqual(self.adapter.get('record')['version'], 1)
        self.assertEqual(self.new_core().execute(v['requestId'])['state'], 'UNCERTAIN')
        self.assertEqual(self.core.reconcile(v['requestId'])['state'], 'EXECUTED')
        self.assertEqual(self.adapter.get('record')['version'], 1)
        self.assertEqual([e['state'] for e in self.core.events(v['requestId'])][-2:],
                         ['UNCERTAIN', 'EXECUTED'])

    def test_unknown_outcome_without_receipt_never_retries(self):
        v = self.submit(self.request())
        original_apply = self.adapter.apply
        def drop_before_effect(_):
            raise TimeoutError('outcome not known')
        self.adapter.apply = drop_before_effect
        self.assertEqual(self.approve(v)['state'], 'UNCERTAIN')
        self.adapter.apply = original_apply
        self.assertEqual(self.core.reconcile(v['requestId'])['state'], 'UNCERTAIN')
        self.assertEqual(self.core.execute(v['requestId'])['state'], 'UNCERTAIN')
        self.assertEqual(self.adapter.get('record')['version'], 0)

    def test_atomic_version_cas_prevents_race(self):
        v = self.submit(self.request())
        original_prepare = self.adapter.prepare
        called = False
        def racing_prepare(request):
            nonlocal called
            result = original_prepare(request)
            if not called:
                called = True
                with self.adapter._db() as db:
                    db.execute('UPDATE objects SET version=version+1,value=? WHERE id=?',
                               ('competing-write', 'record'))
            return result
        self.adapter.prepare = racing_prepare
        self.assertEqual(self.approve(v)['state'], 'STALE')
        self.assertEqual(self.adapter.get('record')['version'], 1)

    def test_concurrent_decisions_only_one_is_accepted(self):
        v = self.submit(self.request())
        results = []
        def worker():
            try:
                results.append(self.approve(v)['state'])
            except Denied:
                results.append('DENIED')
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertCountEqual(results, ['EXECUTED', 'DENIED'])
        self.assertEqual(self.adapter.get('record')['version'], 1)

    def test_pending_does_not_allow_client_execution(self):
        v = self.submit(self.request())
        with self.assertRaises(Denied):
            self.core.client('client-1-secret', 'execute', v['requestId'])
        self.assertEqual(self.core.execute(v['requestId'])['state'], 'PENDING')
        self.assertEqual(self.adapter.get('record')['version'], 0)

    def test_completed_allow_replay_and_second_owner_decision_are_terminal(self):
        request = self.request(op='set_free')
        first = self.submit(request)
        self.assertEqual(first['state'], 'EXECUTED')
        events_before = self.core.events(first['requestId'])
        replay = self.submit(request)
        self.assertEqual(replay['state'], 'EXECUTED')
        self.assertEqual(self.adapter.get('record')['version'], 1)
        self.assertEqual(self.core.events(first['requestId']), events_before)
        with self.assertRaises(Denied):
            self.approve(first)

    def test_nested_or_invalid_unicode_payloads_fail_closed(self):
        nested = self.request()
        value = current = {}
        for _ in range(1200):
            child = {}
            current['child'] = child
            current = child
        nested['params'] = value
        with self.assertRaises(Denied):
            self.submit(nested)
        invalid_unicode = self.request()
        invalid_unicode['reason'] = 'invalid-' + chr(0xD800)
        with self.assertRaises(Denied):
            self.submit(invalid_unicode)
        self.assertEqual(self.adapter.get('record')['version'], 0)

    def test_reconciliation_rejects_non_uncertain_states_without_receipt_lookup(self):
        pending = self.submit(self.request())
        receipt_calls = []
        original_receipt = self.adapter.receipt
        self.adapter.receipt = lambda request_id: receipt_calls.append(request_id)
        with self.assertRaises(Denied):
            self.core.reconcile(pending['requestId'])
        self.assertEqual(receipt_calls, [])
        self.adapter.receipt = original_receipt

    def test_mismatched_reconciliation_receipt_never_executes_or_retries(self):
        pending = self.submit(self.request())
        original_apply = self.adapter.apply
        self.adapter.apply = lambda _request: (_ for _ in ()).throw(TimeoutError())
        self.assertEqual(self.approve(pending)['state'], 'UNCERTAIN')
        self.adapter.apply = original_apply
        self.adapter.receipt = lambda request_id: {
            'requestId': request_id, 'target': 'foreign-target', 'version': 99}
        self.adapter.confirm = lambda _request_id, _result: False
        self.assertEqual(self.core.reconcile(pending['requestId'])['state'], 'UNCERTAIN')
        self.assertEqual(self.core.execute(pending['requestId'])['state'], 'UNCERTAIN')
        self.assertEqual(self.adapter.get('record')['version'], 0)

    def test_reconciliation_lookup_failure_preserves_uncertain_state(self):
        pending = self.submit(self.request())
        original_apply = self.adapter.apply
        self.adapter.apply = lambda _request: (_ for _ in ()).throw(TimeoutError())
        self.assertEqual(self.approve(pending)['state'], 'UNCERTAIN')
        self.adapter.apply = original_apply
        original_receipt = self.adapter.receipt
        self.adapter.receipt = lambda _request_id: (_ for _ in ()).throw(OSError('offline'))
        with self.assertRaises(OSError):
            self.core.reconcile(pending['requestId'])
        self.assertEqual(self.core.client(
            'client-1-secret', 'status', pending['requestId'])['state'], 'UNCERTAIN')
        self.assertEqual(self.core.execute(pending['requestId'])['state'], 'UNCERTAIN')
        self.assertEqual(self.adapter.get('record')['version'], 0)
        self.adapter.receipt = original_receipt


if __name__ == '__main__':
    unittest.main()
