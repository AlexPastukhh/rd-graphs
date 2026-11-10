#!/usr/bin/env python3
"""Synthetic, isolated coordinator/authority conformance. No live owners or grants."""
import copy
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import tempfile
import shutil
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
def load(name, filename):return SourceFileLoader(name, str(ROOT / 'tools' / filename)).load_module()
M = load('store_test_core', 'rdg-core-model.py')
P = load('store_test_model', 'rdg-portable-model.py')
IO = load('store_test_io', 'rdg-transaction-io.py')
S = load('store_test_backend', 'rdg-portable-store.py')
AUTH = load('store_test_authority', 'rdg-authority.py')
PERMISSIONS = ['graph.read', 'graph.write', 'plan.read', 'plan.create', 'plan.edit', 'plan.branch',
               'package.create', 'package.copy', 'package.move', 'folder.write']


class PortableStore(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='rdg-portable-store-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name);self.root = self.base / 'packages'
        self.namespace = str(uuid.uuid4())
        self.authority = AUTH.Authority(self.base / 'synthetic-authority.json')
        self.admin = self.authority.init_local(plan_capable=True, graph_read_capable=True,
                                              portable_roots=[self.namespace])['token']
        grant = self.authority.manage('issue', self.admin, {'permissions': PERMISSIONS,
            'scopes': ['packages/' + self.namespace + '/']})
        self.token = grant['token'];self.grant_id = grant['id']
        self.store = S.FileStore(self.root, self.namespace, IO, P, self.base)

    def graph(self, name, paper=False):
        graph = M.blank('graph-' + name, name, 'space-' + name, 'R1', 'Result ' + name, 'Synthetic scope')
        if paper:graph['nodes'][0]['status'] = 'potential'
        return graph

    def plan(self, name, target=None, graph=None):
        return {'schemaVersion': 2, 'kind': 'temporalPlan', 'id': 'plan-' + name, 'title': name,
            'identitySpace': 'plan-space-' + name, 'revision': 1, 'status': 'candidate',
            'steps': [] if target is None else [{'id': 'OLD', 'title': 'Old requirement', 'kind': 'requirement',
                'state': 'planned', 'ref': P.reference(target, graph, 'R1')}],
            'sequence': [], 'branches': [], 'timeConstraints': [] if target is None else [
                {'stepId': 'OLD', 'type': 'deadline', 'at': '2026-11-01', 'strength': 'soft', 'basis': 'Synthetic test'}]}

    def checks(self, changes):
        return [{'namespaceId': self.namespace, 'packageId': ident, 'path': change['path'],
                 'permissions': change['permissions']} for ident, change in changes.items()]

    def commit(self, changes, tx=None, request=None, token=None, expected=None, fail=None):
        tx = tx or str(uuid.uuid4());request = request or {'transactionId': tx, 'operation': 'synthetic'}
        token = token or self.token;checks = self.checks(changes)
        def before():
            for item in checks:self.authority.authorize_portable(token, item['permissions'], self.namespace,
                                                                 item['packageId'], item['path'])
        # Permission failure cannot even create a new reference barrier.
        before()
        with self.store.lock(True):
            return self.store.commit(tx, P.digest(request), changes, AUTH.token_digest(token), before,
                lambda: self.authority.checked_portable_transaction(token, checks), expected or {}, fail)

    def create(self, name, role='working', graph=None, plan=None):
        tx = str(uuid.uuid4());ident = str(uuid.uuid5(uuid.UUID(tx), 'package'))
        value = graph or self.graph(name, role in ('ready', 'lens'))
        change = {'path': role + '/' + name, 'role': role, 'graph': value,
                  'permissions': ['package.create', 'graph.write']}
        if role not in ('ready', 'lens'):
            change['plan'] = plan if plan is not None else self.plan(name)
            change['permissions'].append('plan.create')
        result = self.commit({ident: change}, tx)
        return ident, self.store.read(ident), result

    def edit(self, snapshot, title='Changed'):
        graph = copy.deepcopy(snapshot['graph']);graph['title'] = title;graph['revision'] += 1
        return {snapshot['packageId']: {'path': snapshot['path'], 'before': snapshot, 'graph': graph,
                                       'permissions': ['graph.write']}}

    def fail_at(self, point):
        def failure(name):
            if name == point:raise RuntimeError('Injected fault ' + name)
        return failure

    def test_creation_has_verified_receipt_inventory_and_no_credentials(self):
        ident, snapshot, result = self.create('first')
        M.validate(snapshot['graph']);P.validate_plan(snapshot['plan'])
        self.assertTrue(result['accepted'] and result['published'])
        self.assertFalse(result['recovery_required'])
        self.assertEqual(snapshot['head']['packageId'], ident)
        self.assertTrue(self.store.inventory(snapshot))
        for path in self.root.rglob('*.json'):
            self.assertNotIn(self.token, path.read_text())
            self.assertNotIn(self.admin, path.read_text())

    def test_exact_replay_returns_old_receipt_without_reverting_later_changes(self):
        ident, initial, _ = self.create('replay')
        tx = str(uuid.uuid4());request = {'transactionId': tx, 'operation': 'edit-first'}
        changes = self.edit(initial, 'First accepted edit')
        first = self.commit(changes, tx, request)
        current = self.store.read(ident)
        self.commit(self.edit(current, 'Later legitimate edit'))
        before = (self.root / initial['path'] / 'package.json').read_bytes()
        repeated = self.commit(changes, tx, request)
        self.assertTrue(repeated['idempotent'])
        self.assertEqual(repeated['packages'][0]['receipt'], first['packages'][0]['receipt'])
        self.assertEqual((self.root / initial['path'] / 'package.json').read_bytes(), before)
        self.assertEqual(self.store.read(ident)['graph']['title'], 'Later legitimate edit')
        self.assertIsNone(repeated['packages'][0]['path'])
        with self.assertRaisesRegex(ValueError, 'TRANSACTION_ID_CONFLICT'):
            self.commit(changes, tx, {'transactionId': tx, 'operation': 'different-intent'})

    def test_preacceptance_fault_keeps_old_head_and_exact_retry_can_finish(self):
        ident, initial, _ = self.create('before-accept')
        tx = str(uuid.uuid4());request = {'transactionId': tx, 'operation': 'edit'}
        changes = self.edit(initial)
        with self.assertRaisesRegex(RuntimeError, 'Injected fault staged'):
            self.commit(changes, tx, request, fail=self.fail_at('staged'))
        self.assertEqual(self.store.read(ident)['headBytes'], initial['headBytes'])
        self.assertIsNone(self.store.replay(tx, P.digest(request), AUTH.token_digest(self.token)))
        result = self.commit(changes, tx, request)
        self.assertTrue(result['published'])
        self.assertEqual(self.store.read(ident)['graph']['title'], 'Changed')

    def test_accepted_recovery_restores_lost_new_bytes_after_revocation(self):
        ident, initial, _ = self.create('recover')
        tx = str(uuid.uuid4());request = {'transactionId': tx, 'operation': 'edit'}
        changes = self.edit(initial)
        with self.assertRaisesRegex(RuntimeError, 'Injected fault prepared'):
            self.commit(changes, tx, request, fail=self.fail_at('prepared'))
        with self.assertRaises(S.RecoveryRequired):self.store.read(ident)
        payload = json.loads(self.store.metadata_path('staged', tx).read_bytes())
        graph_path = payload['entries'][0]['afterHead']['current']['graph']
        (self.root / initial['path'] / graph_path).unlink()
        self.authority.manage('revoke', self.admin, {'id': self.grant_id})
        with self.assertRaisesRegex(ValueError, 'TOKEN_REVOKED'):
            self.authority.authorize_portable(self.token, ['graph.read'], self.namespace, ident)
        with self.store.lock(True):result = self.store.replay(tx, P.digest(request), AUTH.token_digest(self.token))
        self.assertTrue(result['published'] and result['idempotent'])
        self.assertEqual(self.store.read(ident)['graph']['title'], 'Changed')
        self.assertTrue((self.root / initial['path'] / graph_path).is_file())

    def test_multiowner_partial_head_publication_is_not_healthy(self):
        target, before, _ = self.create('target')
        other_graph = self.graph('other')
        other, other_before, _ = self.create('other', graph=other_graph,
            plan=self.plan('other', target, before['graph']))
        ready, template, _ = self.create('template', 'ready')
        tx = str(uuid.uuid4())
        command = {'op': 'apply_ready', 'sourcePackageId': ready, 'targetPackageId': target,
            'expectedGraphRevision': before['graph']['revision'], 'expectedPackageRevision': before['head']['revision'],
            'sourcePin': {'revision': template['head']['revision'], 'sha256': P.digest(template['graph'])},
            'mode': 'REPLACE_R', 'targetRequirementId': 'R1', 'note': 'Synthetic complete replacement'}
        allocation = {'idMap': {kind: {i: 'new-' + kind + '-' + i for i in ids}
                               for kind, ids in P.definitions(template['graph']).items()},
                      'eventId': 'APPLY', 'removalEventId': 'REMOVE', 'scopeId': 'aggregate',
                      'recordedAt': '2026-10-23T10:00:00+07:00'}
        source_rows = {target: before, other: other_before, ready: template}
        snapshots = {'packages': {key: {'graph': row['graph'], 'role': row['head']['role'],
            'revision': row['head']['revision']} for key, row in source_rows.items()},
            'plans': {key: {'plan': row['plan']} for key, row in source_rows.items() if row['plan'] is not None},
            'incomingComplete': True}
        effects = P.prepare_effects(command, snapshots, {'kernel': M}, allocation).value
        changes = {target: {'path': before['path'], 'before': before, 'graph': effects['graphs'][target],
                           'permissions': ['graph.write']},
                   other: {'path': other_before['path'], 'before': other_before, 'plan': effects['plans'][other],
                           'permissions': ['plan.edit']}}
        with self.assertRaisesRegex(RuntimeError, 'Injected fault head:1'):
            self.commit(changes, tx, command, fail=self.fail_at('head:1'))
        for package_id in (target, other):
            with self.assertRaises(S.RecoveryRequired):self.store.read(package_id)
        with self.store.lock(True):self.store.replay(tx, P.digest(command), AUTH.token_digest(self.token))
        self.assertNotIn('R1', M.entities(self.store.read(target)['graph']))
        self.assertEqual(self.store.read(other)['plan']['steps'], [])
        old = self.store.historical_graph(target, before['graph']['identitySpace'],
                                          before['graph']['revision'], P.digest(before['graph']))
        self.assertIn('R1', M.entities(old))

    def test_plan_only_write_needs_no_graph_write_and_reuses_exact_graph_bytes(self):
        ident, initial, _ = self.create('plan-only')
        grant = self.authority.manage('issue', self.admin, {'permissions': ['plan.read', 'plan.edit'],
            'scopes': ['packages/' + self.namespace + '/' + ident]})
        plan = copy.deepcopy(initial['plan']);plan['revision'] += 1;plan['title'] = 'Plan only changed'
        changes = {ident: {'path': initial['path'], 'before': initial, 'plan': plan, 'permissions': ['plan.edit']}}
        self.commit(changes, token=grant['token'])
        current = self.store.read(ident)
        self.assertEqual(current['head']['current']['graph'], initial['head']['current']['graph'])
        self.assertEqual(current['graph'], initial['graph'])
        self.assertEqual(current['plan']['title'], 'Plan only changed')

    def test_missing_plan_permission_and_legacy_token_do_not_gain_access(self):
        ident, initial, _ = self.create('permission')
        graph_only = self.authority.manage('issue', self.admin, {'permissions': ['graph.write', 'graph.read'],
            'scopes': ['packages/' + self.namespace + '/']})['token']
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*.json')}
        changes = {ident: {'path': initial['path'], 'before': initial, 'plan': initial['plan'], 'permissions': ['plan.edit']}}
        with self.assertRaisesRegex(ValueError, 'MISSING_PERMISSION: plan.edit'):self.commit(changes, token=graph_only)
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*.json')})
        legacy = AUTH.Authority(self.base / 'legacy-authority.json')
        token = legacy.init_local(plan_capable=True, graph_read_capable=True)['token']
        with self.assertRaisesRegex(ValueError, 'PORTABLE_SCOPE_DENIED'):
            legacy.authorize_portable(token, ['graph.read'], self.namespace, ident)
        with self.assertRaisesRegex(ValueError, 'DELEGATION_CEILING'):
            legacy.manage('issue', token, {'permissions': ['graph.read'], 'scopes': ['packages/' + self.namespace + '/']})

    def test_path_scope_does_not_follow_identity_to_another_path(self):
        ident, initial, _ = self.create('path-scope')
        grant = self.authority.manage('issue', self.admin, {'permissions': ['graph.read'],
            'scopes': ['package-paths/' + self.namespace + '/working/']})['token']
        first = self.authority.authorize_portable(grant, ['graph.read'], self.namespace, ident, initial['path'])
        self.assertEqual(first['scopeMode'], 'path')
        with self.assertRaisesRegex(ValueError, 'PORTABLE_SCOPE_DENIED'):
            self.authority.authorize_portable(grant, ['graph.read'], self.namespace, ident, 'moved/path-scope')

    def test_duplicate_identity_and_corruption_are_not_empty_success(self):
        import shutil
        ident, initial, _ = self.create('duplicate')
        shutil.copytree(self.root / initial['path'], self.root / 'duplicate-copy')
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_IDENTITY'):self.store.read(ident)
        shutil.rmtree(self.root / 'duplicate-copy')
        graph = self.root / initial['path'] / initial['head']['current']['graph']
        graph.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'CURRENT_HASH_MISMATCH'):self.store.read(ident)

    def test_completed_package_rename_preserves_identity_and_historical_pins(self):
        ident, initial, _ = self.create('rename')
        self.commit(self.edit(initial, 'Second generation'))
        current = self.store.read(ident);before_bytes = current['headBytes']
        (self.root / current['path']).rename(self.root / 'renamed-package')
        moved = self.store.read(ident)
        self.assertEqual(moved['path'], 'renamed-package')
        self.assertEqual(moved['headBytes'], before_bytes)
        self.assertEqual(self.store.historical_graph(ident, initial['graph']['identitySpace'],
            initial['graph']['revision'], P.digest(initial['graph'])), initial['graph'])
        self.assertTrue(self.store.inventory(moved))


    def test_half_published_package_cannot_become_healthy_in_another_root(self):
        ident,initial,_=self.create('portable-proof')
        tx=str(uuid.uuid4());request={'transactionId':tx,'operation':'edit'}
        with self.assertRaisesRegex(RuntimeError,'Injected fault witness:1'):
            self.commit(self.edit(initial),tx,request,fail=self.fail_at('witness:1'))
        foreign=self.base/'foreign';foreign.mkdir();root=foreign/'packages'
        shutil.copytree(self.root/initial['path'],root/'working/proof')
        backend=S.FileStore(root,self.namespace,IO,P,foreign)
        with self.assertRaises(S.RecoveryRequired):backend.read(ident)
        with self.store.lock(True):self.store.replay(tx,P.digest(request),AUTH.token_digest(self.token))
        # The completion certificate is issued only after all participant heads and witnesses.
        final=self.root/initial['path']/'.rdg/completed'/(tx+'.json')
        target=root/'working/proof/.rdg/completed'/(tx+'.json');target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(final,target)
        acceptance=self.root/initial['path']/'.rdg/acceptances'/(tx+'.json')
        destination=root/'working/proof/.rdg/acceptances'/(tx+'.json')
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(acceptance,destination)
        loaded=backend.read(ident)
        self.assertEqual(loaded['graph']['title'],'Changed')
        self.assertEqual(loaded['acceptance'],json.loads(acceptance.read_bytes()))
        self.assertIn('.rdg/acceptances/'+tx+'.json',backend.inventory(loaded))

    def test_replay_finishes_finalization_after_root_completion_and_survives_rename(self):
        ident,initial,_=self.create('finalize-proof');tx=str(uuid.uuid4());request={'transactionId':tx,'operation':'edit'}
        with self.assertRaisesRegex(RuntimeError,'Injected fault completed'):
            self.commit(self.edit(initial),tx,request,fail=self.fail_at('completed'))
        with self.assertRaises(S.RecoveryRequired):self.store.read(ident)
        with self.store.lock(True):self.store.replay(tx,P.digest(request),AUTH.token_digest(self.token))
        current=self.store.read(ident);destination=self.root/'working/renamed-finalized'
        (self.root/current['path']).rename(destination)
        with self.store.lock(True):result=self.store.replay(tx,P.digest(request),AUTH.token_digest(self.token))
        self.assertTrue(result['idempotent']);self.assertIsNone(result['packages'][0]['path'])
        self.assertEqual(self.store.read(ident)['path'],'working/renamed-finalized')


if __name__ == '__main__':unittest.main()
