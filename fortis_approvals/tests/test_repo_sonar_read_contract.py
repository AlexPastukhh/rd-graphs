"""R1 Sonar READ typed contract only. No HTTP route, remote calls or tokens."""
from copy import deepcopy
import unittest
import uuid

from fortis_approvals.core import Authenticator, Denied
from fortis_approvals.repo_action_contract import (
    RepoIntentBroker, SONAR_READ_OPERATIONS, validate_intent,
    validate_read_query,
)


class NoDispatchCore:
    def __init__(self):
        self.auth = Authenticator({
            'read-client-credential': 'reader',
            'other-client-credential': 'other',
        })
        self.policy = 'ALLOW'
        self.calls = 0

    def _policy(self, actor, request):
        self.calls += 1
        if actor != 'reader':
            return 'DENY'
        return self.policy

    def client(self, *_args, **_kwargs):
        raise AssertionError('READ_MUST_NOT_ENTER_CORE_EXECUTE')


class SonarReadContractTests(unittest.TestCase):
    def setUp(self):
        self.core = NoDispatchCore()
        self.broker = RepoIntentBroker(
            self.core, actor_operations={},
            actor_read_operations={'reader': SONAR_READ_OPERATIONS})

    def query(self, operation, *, target=None, params=None):
        spec = {
            'list_projects': ('trusted_org', {'page': 1, 'pageSize': 20}),
            'list_issues': ('trusted_org_project', {'page': 1, 'pageSize': 20}),
            'get_issue': ('ISSUE-123', {'projectKey': 'trusted_org_project'}),
            'get_quality_gate': ('trusted_org_project', {}),
        }
        default_target, default_params = spec[operation]
        return {
            'requestId': str(uuid.uuid4()),
            'service': 'sonarcloud', 'operation': operation,
            'target': default_target if target is None else target,
            'params': deepcopy(default_params) if params is None else params,
            'reason': 'Inspect code quality; no write authorized',
        }

    def test_all_read_shapes_pass_without_remote_calls(self):
        for operation in ('list_projects', 'list_issues',
                          'get_issue', 'get_quality_gate'):
            with self.subTest(operation=operation):
                original = self.query(operation)
                approved = self.broker.authorize_read('read-client-credential', original)
                self.assertEqual(original, approved)
                self.assertIsNot(original, approved)
                self.assertIsNot(original['params'], approved['params'])
                self.assertEqual(self.core.calls >= 1, True)
                with self.assertRaisesRegex(Denied, 'REPO_OPERATION_NOT_SUPPORTED'):
                    validate_intent(original)

    def test_read_is_not_eligible_for_submit_even_with_broad_grants(self):
        q = self.query('get_issue')
        with self.assertRaisesRegex(Denied, 'REPO_OPERATION_NOT_SUPPORTED'):
            self.broker.submit('read-client-credential', q)

    def test_malformed_envelope_and_untrusted_authority_rejected(self):
        original = self.query('list_issues')
        for extra, value in (
            ('sonarToken', 'sensitive'), ('approved', True),
            ('actor', 'reader'), ('policy', 'ALLOW'),
            ('method', 'POST'), ('url', 'https://invalid.test'),
            ('owner', 'admin'), ('headers', {'Authorization': 'secret'}),
        ):
            bad = deepcopy(original)
            bad[extra] = value
            with self.subTest(extra=extra), self.assertRaisesRegex(
                    Denied, 'REPO_INTENT_SCHEMA_DENIED'):
                validate_read_query(bad)
        variants = (
            dict(original, service='github'),
            dict(original, operation='accept_issue'),
            dict(original, requestId=str(uuid.uuid4()).upper()),
            dict(original, target='https://invalid.test/issue'),
            dict(original, target=''),
            dict(original, params=[]),
            dict(original, reason=''),
            dict(original, reason='wrong-\ud800'),
        )
        for bad in variants:
            with self.subTest(bad=repr(bad)[:70]), self.assertRaises(Denied):
                validate_read_query(bad)
        self.assertEqual(self.core.calls, 0)

    def test_pagination_requires_exact_bounded_integers(self):
        for operation in ('list_projects', 'list_issues'):
            for bad in (
                {'page': 0, 'pageSize': 20},
                {'page': 10001, 'pageSize': 20},
                {'page': True, 'pageSize': 20},
                {'page': 1, 'pageSize': False},
                {'page': 1, 'pageSize': 0},
                {'page': 1, 'pageSize': 101},
                {'page': '1', 'pageSize': 20},
                {'page': 1, 'pageSize': 20, 'url': 'https://evil.invalid'},
                {'page': 1, 'pageSize': 20, 'token': 'fake'},
                {'page': 1, 'pageSize': 20, 'method': 'POST'},
            ):
                with self.subTest(operation=operation, params=bad):
                    with self.assertRaisesRegex(Denied,
                                                'REPO_SONAR_READ_PARAMS_DENIED'):
                        validate_read_query(self.query(operation, params=bad))

    def test_exact_issue_and_gate_params(self):
        for bad in (
            {}, {'projectKey': ''}, {'projectKey': 42},
            {'projectKey': 'https://evil.invalid'},
            {'projectKey': 'one', 'transition': 'accept'},
            {'projectKey': 'one', 'expectedIssueSha256': '0'*64},
        ):
            with self.subTest(params=bad), self.assertRaisesRegex(
                    Denied, 'REPO_SONAR_READ_PARAMS_DENIED'):
                validate_read_query(self.query('get_issue', params=bad))
        for bad in ({'page': 1}, {'projectKey': 'other'},
                    {'method': 'POST'}):
            with self.subTest(params=bad), self.assertRaisesRegex(
                    Denied, 'REPO_SONAR_READ_PARAMS_DENIED'):
                validate_read_query(self.query('get_quality_gate', params=bad))

    def test_actor_grant_and_trusted_allow_policy(self):
        query = self.query('get_issue')
        with self.assertRaisesRegex(Denied, 'CLIENT_UNAUTHORIZED'):
            self.broker.authorize_read('unknown', query)
        with self.assertRaisesRegex(Denied, 'REPO_READ_GRANT_DENIED'):
            self.broker.authorize_read('other-client-credential', query)
        self.assertEqual(self.core.calls, 0)
        for policy in ('ASK', 'DENY', 'UNKNOWN'):
            self.core.policy = policy
            with self.subTest(policy=policy), self.assertRaisesRegex(
                    Denied, 'REPO_SONAR_READ_ALLOW_REQUIRED'):
                self.broker.authorize_read('read-client-credential', query)

    def test_trusted_resource_scope_denies_foreign_org_project_and_issue(self):
        # Policy is trusted Fortis configuration; caller cannot set ALLOW.
        def resource_policy(_actor, query):
            op = query['operation']
            if op == 'list_projects':
                return 'ALLOW' if query['target'] == 'trusted_org' else 'DENY'
            if op == 'get_issue':
                return ('ALLOW' if query['params']['projectKey'] ==
                        'trusted_org_project' else 'DENY')
            return ('ALLOW' if query['target'] == 'trusted_org_project'
                    else 'DENY')
        self.core._policy = resource_policy
        accepted = self.broker.authorize_read(
            'read-client-credential', self.query('get_issue'))
        self.assertEqual(accepted['operation'], 'get_issue')
        denied = (
            self.query('list_projects', target='foreign_org'),
            self.query('list_issues', target='foreign_org_project'),
            self.query('get_issue', params={'projectKey': 'foreign_project'}),
            self.query('get_quality_gate', target='foreign_project'),
        )
        for query in denied:
            with self.subTest(operation=query['operation']), self.assertRaisesRegex(
                    Denied, 'REPO_SONAR_READ_ALLOW_REQUIRED'):
                self.broker.authorize_read('read-client-credential', query)

    def test_default_is_no_read_grant_and_invalid_grant_declarations_denied(self):
        empty = RepoIntentBroker(self.core, actor_operations={})
        with self.assertRaisesRegex(Denied, 'REPO_READ_GRANT_DENIED'):
            empty.authorize_read('read-client-credential', self.query('list_projects'))
        for grants in (
            {'reader': {('sonarcloud', 'accept_issue')}},
            {'reader': {('synthetic', 'set_free')}},
            {'reader': {('sonarcloud', 'get_issue', 'extra')}},
            {'reader': ['get_issue']},
            {'reader': 'get_issue'},
            {'': SONAR_READ_OPERATIONS},
            {'reader': None},
        ):
            with self.subTest(grants=grants), self.assertRaises(ValueError):
                RepoIntentBroker(self.core, actor_operations={},
                                 actor_read_operations=grants)


if __name__ == '__main__':
    unittest.main()
