"""Single real-Issue preflight contract, tested with synthetic Sonar responses."""
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest import mock

from fortis_approvals.core import Denied
from fortis_approvals.sonar import SonarTransportError
from fortis_approvals.sonar_preflight import PreflightGetOnly, preflight, main, MAX_PROJECTS


class FakeSonar:
    def __init__(self, projects=None):
        self.projects = projects if projects is not None else {'org-one': ['p1', 'p2', 'p3']}
        self.rows = {'p1': [], 'p2': [self.issue('p2', 'ISSUE-1')], 'p3': []}
        self.transitions = ['accept', 'falsepositive']
        self.calls = []
        self.override = {}

    @staticmethod
    def issue(project, key, **values):
        return {'key': key, 'project': project, 'issueStatus': 'OPEN',
                'updateDate': '2026-10-31T10:11:12+0000', 'message': 'PRIVATE ISSUE MESSAGE',
                'rule': 'python:S1234', 'severity': 'MAJOR', 'component': project+':src/x.py',
                'assignee': None, 'type': 'CODE_SMELL', **values}

    def call(self, method, path, params):
        self.calls.append((method, path, dict(params)))
        if path in self.override:
            data = self.override[path]
            if isinstance(data, Exception):
                raise data
            return data
        if path == '/api/components/search':
            org = params['organization']
            rows = [{'key': key, 'qualifier': 'TRK', 'organization': org}
                    for key in self.projects[org]]
            return {'components': rows, 'paging': {'total': len(rows), 'pageIndex': 1}}
        if path == '/api/issues/search':
            project = params['componentKeys']
            rows = self.rows.get(project, [])
            if 'issues' in params:
                rows = [r for r in rows if r['key'] == params['issues']]
            if params.get('additionalFields') == 'transitions':
                rows = [{**r, 'transitions': self.transitions} for r in rows]
            return {'issues': rows[:int(params['ps'])]}
        raise AssertionError('Unexpected route: ' + path)


class PreflightTests(unittest.TestCase):
    def test_selects_first_open_issue_across_projects_with_exact_second_read(self):
        remote = FakeSonar()
        result = preflight(remote, ['org-one'], region='eu')
        self.assertEqual(result['status'], 'ISSUE_PREFLIGHT_READ_OK')
        self.assertEqual((result['projectKey'], result['issueKey']), ('p2', 'ISSUE-1'))
        self.assertEqual((result['visibleProjectCount'], result['projectsInspected']), (3, 2))
        self.assertEqual(result['issueStatus'], 'OPEN')
        self.assertEqual(result['updateDate'], '2026-10-31T10:11:12+0000')
        self.assertEqual(len(result['issueSha256']), 64)
        self.assertIn('rule', result['fieldsPresent'])
        self.assertIn('assignee', result['fieldsMissing'])
        self.assertEqual(result['availableTransitionKeys'], ['accept', 'falsepositive'])
        self.assertTrue(result['acceptOffered'])
        self.assertEqual(result['mutations'], 0)
        self.assertFalse(result['tokenPersisted'])
        self.assertFalse(result['allIssuesInspected'])
        self.assertNotIn('PRIVATE ISSUE MESSAGE', json.dumps(result))
        self.assertEqual([p for _, p, _ in remote.calls],
                         ['/api/components/search', '/api/issues/search',
                          '/api/issues/search', '/api/issues/search'])
        self.assertTrue(all(method == 'GET' for method, _, _ in remote.calls))
        self.assertEqual(remote.calls[3][2]['issues'], 'ISSUE-1')

    def test_scope_and_input_are_fail_closed(self):
        for orgs in ([], ['bad/path'], ['org-one', 'org-one'], ['x']*21):
            with self.subTest(orgs=orgs), self.assertRaises(Denied):
                preflight(FakeSonar(), orgs, region='eu')
        with self.assertRaises(Denied):
            preflight(FakeSonar(), ['org-one'], region='invalid')

    def test_no_open_within_bounded_sample_has_explicit_failure(self):
        remote = FakeSonar({'org-one': ['p1']})
        remote.rows = {'p1': [self._fixed('p1', 'ALREADY-1')]}
        with self.assertRaisesRegex(Denied, 'NO_OPEN_IN_BOUNDED_SAMPLE'):
            preflight(remote, ['org-one'], region='eu')

    @staticmethod
    def _fixed(project, key):
        return {**FakeSonar.issue(project, key), 'issueStatus': 'FIXED'}

    def test_rejects_cross_project_sample(self):
        remote = FakeSonar()
        remote.rows['p2'] = [FakeSonar.issue('foreign', 'ISSUE-1')]
        with self.assertRaisesRegex(Denied, 'SCOPE_INVALID'):
            preflight(remote, ['org-one'], region='eu')

    def test_rejects_stale_exact_status_and_missing_update_date(self):
        remote = FakeSonar({'org-one': ['p2']})
        old_call = remote.call
        def replaced(method, path, params):
            if path == '/api/issues/search' and 'issues' in params:
                return {'issues': [self._fixed('p2', 'ISSUE-1')]}
            return old_call(method, path, params)
        remote.call = replaced
        with self.assertRaisesRegex(Denied, 'ISSUE_CHANGED'):
            preflight(remote, ['org-one'], region='eu')
        remote = FakeSonar({'org-one': ['p2']})
        old_call = remote.call
        def no_update(method, path, params):
            if path == '/api/issues/search' and 'issues' in params:
                obj = FakeSonar.issue('p2', 'ISSUE-1')
                obj.pop('updateDate')
                return {'issues': [obj]}
            return old_call(method, path, params)
        remote.call = no_update
        with self.assertRaisesRegex(Denied, 'VERSION_MISSING'):
            preflight(remote, ['org-one'], region='eu')

    def test_exact_issue_requires_unique_key_and_project(self):
        for response in ({'issues': []},
                         {'issues': [FakeSonar.issue('elsewhere', 'ISSUE-1')]},
                         {'issues': [FakeSonar.issue('p2', 'ISSUE-OTHER')]}):
            remote = FakeSonar({'org-one': ['p2']})
            old_call = remote.call
            remote.call = lambda m,p,a, resp=response: (resp if p == '/api/issues/search'
                                and 'issues' in a else old_call(m,p,a))
            with self.subTest(response=response), self.assertRaises(Denied):
                preflight(remote, ['org-one'], region='eu')

    def test_rejects_bad_transitions_and_reports_no_accept(self):
        for transitions in ([{'key': 'accept'}, {'key': 'accept'}],
                            [{'key': '/malicious'}], [{'name': 'accept'}], [{}]):
            remote = FakeSonar({'org-one': ['p2']})
            remote.transitions = transitions
            with self.subTest(transitions=transitions), self.assertRaisesRegex(Denied, 'TRANSITIONS_INVALID'):
                preflight(remote, ['org-one'], region='eu')
        remote = FakeSonar({'org-one': ['p2']})
        remote.transitions = []
        self.assertFalse(preflight(remote, ['org-one'], region='eu')['acceptOffered'])

    def test_missing_transitions_never_grants_write(self):
        remote = FakeSonar({'org-one': ['p2']})
        original = remote.call
        def missing(method, path, params):
            data = original(method, path, params)
            if params.get('additionalFields') == 'transitions':
                data['issues'][0].pop('transitions')
            return data
        remote.call = missing
        result = preflight(remote, ['org-one'], region='eu')
        self.assertEqual(result['transitionState'], 'NOT_RETURNED')
        self.assertFalse(result['acceptOffered'])
        self.assertFalse(result['writeAuthorized'])

    def test_unsupported_optional_param_falls_back_read_only(self):
        remote = FakeSonar({'org-one': ['p2']})
        original = remote.call
        def unsupported(method, path, params):
            if params.get('additionalFields') == 'transitions':
                raise SonarTransportError('SONAR_HTTP_400')
            return original(method, path, params)
        remote.call = unsupported
        result = preflight(remote, ['org-one'], region='eu')
        self.assertEqual(result['status'], 'ISSUE_PREFLIGHT_READ_OK')
        self.assertEqual(result['transitionLookup'], 'ADDITIONAL_FIELDS_REJECTED')
        self.assertEqual(result['transitionState'], 'NOT_VERIFIED')
        self.assertFalse(result['acceptOffered'])
        self.assertFalse(result['writeAuthorized'])

    def test_unexpected_404_is_not_silently_accepted(self):
        remote = FakeSonar({'org-one': ['p2']})
        original = remote.call
        def missing_route(method, path, params):
            if params.get('additionalFields') == 'transitions':
                raise SonarTransportError('SONAR_HTTP_404')
            return original(method, path, params)
        remote.call = missing_route
        with self.assertRaisesRegex(SonarTransportError, 'EXACT_ISSUE_SONAR_HTTP_404'):
            preflight(remote, ['org-one'], region='eu')

    def test_transport_stage_403_does_not_echo_secret(self):
        remote = FakeSonar({'org-one': ['p2']})
        original = remote.call
        def fail_exact(method, path, params):
            if params.get('additionalFields') == 'transitions':
                raise SonarTransportError('SONAR_HTTP_403')
            return original(method, path, params)
        remote.call = fail_exact
        with self.assertRaises(SonarTransportError) as cm:
            preflight(remote, ['org-one'], region='eu')
        self.assertEqual(str(cm.exception), 'SONAR_PREFLIGHT_EXACT_ISSUE_SONAR_HTTP_403')

    def test_readonly_transport_rejects_any_write_or_unexpected_route(self):
        remote = FakeSonar()
        reader = PreflightGetOnly(remote)
        with self.assertRaises(Denied):
            reader.call('POST', '/api/issues/do_transition', {'issue': 'ISSUE-1', 'transition': 'accept'})
        with self.assertRaises(Denied):
            reader.call('GET', '/api/users/search', {'q': 'test'})
        with self.assertRaises(Denied):
            reader.call('GET', '/api/issues/search', {'componentKeys': 'p2', 'malicious': '1'})
        with self.assertRaises(Denied):
            reader.call('GET', '/api/issues/transitions', {'issue': 'ISSUE-1'})
        with self.assertRaises(Denied):
            reader.call('GET', '/api/issues/search', {'componentKeys': 'p2', 'issues':'ISSUE-1',
                           'p':'1', 'ps':'2', 'additionalFields':'comments'})
        self.assertEqual(remote.calls, [])

    def test_cli_uses_stdin_and_never_prints_token_or_message(self):
        remote = FakeSonar({'org-one': ['p2']})
        stdout, stderr = StringIO(), StringIO()
        with mock.patch('fortis_approvals.sonar_preflight.SonarHTTPTransport') as ctor:
            ctor.ORIGINS = {'eu': 'https://sonarcloud.io', 'us': 'https://sonarqube.us'}
            ctor.return_value = remote
            with mock.patch('sys.stdin', StringIO('synthetic-secret-token-abc\n')):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = main(['--region', 'eu', '--organization', 'org-one'])
        self.assertEqual(code, 0, stderr.getvalue())
        record = json.loads(stdout.getvalue())
        self.assertEqual(record['status'], 'ISSUE_PREFLIGHT_READ_OK')
        self.assertNotIn('synthetic-secret-token-abc', stdout.getvalue() + stderr.getvalue())
        self.assertNotIn('PRIVATE ISSUE MESSAGE', stdout.getvalue() + stderr.getvalue())
        self.assertEqual(ctor.call_args.kwargs['bearer_token'], 'synthetic-secret-token-abc')

    def test_project_scan_is_bounded(self):
        remote = FakeSonar({'org-one': [f'p{i:03d}' for i in range(MAX_PROJECTS+1)]})
        remote.rows = {}
        with self.assertRaisesRegex(Denied, 'NO_OPEN_IN_BOUNDED_SAMPLE'):
            preflight(remote, ['org-one'], region='eu')
        self.assertEqual(len([c for c in remote.calls if c[1]=='/api/issues/search']), MAX_PROJECTS)

    def test_docker_source_contract(self):
        deploy = Path(__file__).resolve().parents[1] / 'deploy'
        dockerfile = (deploy / 'Dockerfile-G4-IssuePreflight').read_text()
        powershell = (deploy / 'Probe-G4-IssuePreflight.ps1').read_text()
        self.assertIn('sonar_preflight.py', dockerfile)
        self.assertNotIn('owner_auth.py', dockerfile)
        for flag in ('--rm', '--read-only', '--cap-drop', '--entrypoint', '-AsSecureString'):
            self.assertIn(flag, powershell)
        self.assertNotIn('SONAR_TOKEN=', powershell)


if __name__ == '__main__':
    unittest.main()
