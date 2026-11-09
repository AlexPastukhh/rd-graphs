"""R2 Sonar READ only, fake transport, no credentials/network/Windo ws."""
from copy import deepcopy
import unittest
import uuid

from fortis_approvals.core import Authenticator, Denied
from fortis_approvals.repo_action_contract import RepoIntentBroker, SONAR_READ_OPERATIONS
from fortis_approvals.sonar import SonarHTTPTransport, SonarTransportError
from fortis_approvals.sonar_read import SonarReadAdapter, SonarReadOnlyTransport


class FakeRemote:
    def __init__(self):
        self.org_projects = {
            'trusted_org': ['trusted_project_%03d' % i for i in range(121)],
            'other_org': ['foreign_project'],
        }
        self.issues = {}
        for project in self.org_projects['trusted_org']:
            self.issues[project] = [
                {'key': '%s-I%03d' % (project, i), 'project': project,
                 'issueStatus': 'OPEN', 'updateDate': '2026-10-31T00:00:00+0000',
                 'message': 'Potential bug', 'severity': 'MAJOR',
                 'rule': 'python:S123', 'component': project + ':src/app.py',
                 'assignee': None, 'type': 'BUG', 'line': i + 1,
                 'token': 'MUST_NOT_LEAK'}
                for i in range(123)
            ]
        self.calls = []
        self.bad = None
        self.override_total = None

    def call(self, method, path, params):
        self.calls.append((method, path, deepcopy(params)))
        if method != 'GET':
            raise AssertionError('POST MUST NOT BE CALLED')
        if path == '/api/components/search':
            org = params['organization']
            data = list(self.org_projects[org])
            if 'q' in params:
                data = [k for k in data if k == params['q']]
            page, size = int(params['p']), int(params['ps'])
            chunk = data[(page - 1) * size:page * size]
            return {'paging': {'total': len(data), 'pageIndex': page,
                               'pageSize': size},
                    'components': [{'key': k, 'organization': org,
                                    'qualifier': 'TRK'} for k in chunk]}
        if path == '/api/issues/search':
            project = params['componentKeys']
            rows = deepcopy(self.issues.get(project, []))
            if 'issues' in params:
                rows = [r for r in rows if r['key'] == params['issues']]
            page, size = int(params['p']), int(params['ps'])
            count = len(rows) if self.override_total is None else self.override_total
            out = rows[(page - 1) * size:page * size]
            if self.bad == 'foreign' and out:
                out[0]['project'] = 'foreign_project'
            if self.bad == 'duplicate' and len(out) >= 2:
                out[1]['key'] = out[0]['key']
            if self.bad == 'bad_line' and out:
                out[0]['line'] = True
            if self.bad == 'wrong_key' and out:
                out[0]['key'] = 'other_project_issue'
            if self.bad == 'bad_status' and out:
                out[0]['issueStatus'] = {'unsafe': True}
            if self.bad == 'missing_page':
                out = []
            paging = {'total': count, 'pageIndex': page, 'pageSize': size}
            if self.bad == 'wrong_page':
                paging['pageIndex'] = page + 1
            return {'issues': out, 'paging': paging, 'total': count,
                    'secret': 'MUST_NOT_LEAK'}
        if path == '/api/qualitygates/project_status':
            if self.bad == 'bad_gate':
                return {'projectStatus': {'status': ['ERROR'], 'conditions': []}}
            return {'projectStatus': {
                'status': 'ERROR',
                'conditions': [{'status': 'ERROR', 'metricKey': 'new_coverage',
                                'actualValue': '63.5', 'errorThreshold': '80',
                                'privateField': 'MUST_NOT_LEAK'}],
                'privateToken': 'MUST_NOT_LEAK'}}
        raise AssertionError('UNEXPECTED_REMOTE_ROUTE')


class MinimalCore:
    def __init__(self):
        self.auth = Authenticator({'reader-credential': 'reader',
                                   'guest-credential': 'guest'})

    def _policy(self, actor, query):
        return ('ALLOW' if actor == 'reader' else 'DENY')


class SonarReadAdapterTests(unittest.TestCase):
    def setUp(self):
        self.remote = FakeRemote()
        self.adapter = SonarReadAdapter(
            self.remote, organization_keys={'trusted_org'}, region='eu')
        self.core = MinimalCore()
        self.broker = RepoIntentBroker(
            self.core, actor_operations={},
            actor_read_operations={'reader': SONAR_READ_OPERATIONS})

    @staticmethod
    def query(operation, target, params):
        return {'requestId': str(uuid.uuid4()), 'service': 'sonarcloud',
                'operation': operation, 'target': target,
                'params': deepcopy(params),
                'reason': 'Read authorized SonarCloud test data'}

    def read(self, operation, target, params, *, credential='reader-credential'):
        query = self.query(operation, target, params)
        request = self.broker.authorize_read(credential, query)
        return self.adapter.read(request)

    def test_list_projects_all_visible_and_pages_without_truncation(self):
        r = self.read('list_projects', 'trusted_org', {'page': 1, 'pageSize': 100})
        self.assertEqual((r['total'], len(r['projects']), r['hasMore'],
                          r['nextPage']), (121, 100, True, 2))
        second = self.read('list_projects', 'trusted_org',
                           {'page': 2, 'pageSize': 100})
        self.assertEqual((len(second['projects']), second['hasMore'],
                          second['nextPage']), (21, False, None))
        self.assertEqual({x['key'] for x in r['projects'] + second['projects']},
                         set(self.remote.org_projects['trusted_org']))
        self.assertTrue(all(m == 'GET' for m, _, _ in self.remote.calls))

    def test_single_project_scope_filters_project_discovery_and_denies_foreign_key(self):
        project='trusted_project_000'
        self.adapter = SonarReadAdapter(
            self.remote,organization_keys={'trusted_org'},
            allowed_project_keys=(project,),region='eu')
        one=self.read('list_projects','trusted_org',{'page':1,'pageSize':100})
        self.assertEqual(one['projects'],[{'key':project}])
        self.assertEqual((one['total'],one['hasMore']),(1,False))
        self.assertTrue(all('q' in params for _,path,params in self.remote.calls
                            if path == '/api/components/search'))
        before=len(self.remote.calls)
        foreign='trusted_project_001'
        for operation, target, params in (
            ('list_issues',foreign,{'page':1,'pageSize':20}),
            ('get_quality_gate',foreign,{}),
            ('get_issue',foreign+'-I000',{'projectKey':foreign}),
        ):
            with self.subTest(operation=operation), self.assertRaisesRegex(
                    Denied,'SONAR_READ_PROJECT_DENIED'):
                self.read(operation,target,params)
        self.assertEqual(len(self.remote.calls),before)
        assert self.read('get_quality_gate',project,{})['projectKey']==project

    def test_single_project_scope_rejects_invalid_inputs(self):
        for invalid in ((),[],['trusted_project_000','trusted_project_000'],
                        ['invalid/project'],['x']*21,'trusted_project_000'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                SonarReadAdapter(self.remote,organization_keys={'trusted_org'},
                                 allowed_project_keys=invalid)

    def test_issue_pages_complete_with_explicit_total_and_no_secret(self):
        project = 'trusted_project_000'
        results = [self.read('list_issues', project, {'page': i, 'pageSize': 50})
                   for i in (1, 2, 3)]
        self.assertEqual([len(r['issues']) for r in results], [50, 50, 23])
        self.assertEqual([r['nextPage'] for r in results], [2, 3, None])
        self.assertTrue(all(r['total'] == 123 for r in results))
        self.assertEqual(results[-1]['coverage'],
                         'LIVE_PAGE_NOT_CROSS_PAGE_SNAPSHOT')
        self.assertEqual(len({i['key'] for r in results for i in r['issues']}), 123)
        self.assertNotIn('MUST_NOT_LEAK', str(results))
        self.assertEqual(results[0]['issues'][0]['line'], 1)

    def test_get_exact_issue_and_project_gate(self):
        project = 'trusted_project_000'
        key = project + '-I007'
        issue = self.read('get_issue', key, {'projectKey': project})
        self.assertEqual(issue['issue']['key'], key)
        self.assertEqual(issue['issue']['line'], 8)
        self.assertNotIn('MUST_NOT_LEAK', str(issue))
        gate = self.read('get_quality_gate', project, {})
        self.assertEqual((gate['status'], gate['scope'],
                          gate['prShaBinding']),
                         ('ERROR', 'CURRENT_DEFAULT_BRANCH', 'NOT_VERIFIED_D2'))
        self.assertEqual(gate['conditions'][0]['metricKey'], 'new_coverage')
        self.assertNotIn('MUST_NOT_LEAK', str(gate))
        self.assertEqual(self.remote.calls[-1][1],
                         '/api/qualitygates/project_status')

    def test_unknown_org_rejected_before_remote(self):
        with self.assertRaisesRegex(Denied, 'SONAR_READ_ORGANIZATION_DENIED'):
            self.read('list_projects', 'other_org',
                      {'page': 1, 'pageSize': 10})
        self.assertEqual(self.remote.calls, [])

    def test_foreign_projects_denied_before_issues_and_gate(self):
        for operation, params in (
            ('list_issues', {'page': 1, 'pageSize': 20}),
            ('get_quality_gate', {}),
            ('get_issue', {'projectKey': 'foreign_project'}),
        ):
            with self.subTest(operation=operation), self.assertRaisesRegex(
                    Denied, 'SONAR_READ_PROJECT_DENIED'):
                self.read(operation, 'foreign_project', params)
        self.assertTrue(all(path == '/api/components/search'
                            for _, path, _ in self.remote.calls))

    def test_auth_checks_occur_before_any_sonar_get(self):
        q = self.query('list_projects', 'trusted_org',
                       {'page': 1, 'pageSize': 20})
        for cred in ('unknown-credential', 'guest-credential'):
            with self.subTest(cred=cred), self.assertRaises(Denied):
                self.broker.authorize_read(cred, q)
        self.assertFalse(self.remote.calls)

    def test_get_issue_missing_or_foreign_key_is_not_returned(self):
        project = 'trusted_project_000'
        with self.assertRaisesRegex(Denied, 'SONAR_READ_ISSUE_NOT_UNIQUE'):
            self.read('get_issue', 'UNKNOWN-I1', {'projectKey': project})
        self.remote.bad = 'wrong_key'
        with self.assertRaisesRegex(Denied, 'SONAR_READ_ISSUE_MISMATCH'):
            self.read('get_issue', project + '-I001', {'projectKey': project})

    def test_malformed_pages_and_foreign_data_rejected(self):
        for bad in ('foreign', 'duplicate', 'bad_line', 'bad_status',
                    'wrong_page', 'missing_page'):
            self.remote.bad = bad
            with self.subTest(bad=bad), self.assertRaises(Denied):
                self.read('list_issues', 'trusted_project_000',
                          {'page': 1, 'pageSize': 20})

    def test_issues_api_cap_reported_not_falsely_complete(self):
        self.remote.override_total = 12000
        first = self.read('list_issues', 'trusted_project_000',
                          {'page': 1, 'pageSize': 100})
        self.assertEqual((first['coverage'], first['total'], first['nextPage']),
                         ('CAPPED_AT_10000', 12000, 2))
        with self.assertRaisesRegex(Denied, 'SONAR_READ_PAGE_WINDOW_EXCEEDED'):
            self.read('list_issues', 'trusted_project_000',
                      {'page': 101, 'pageSize': 100})

    def test_invalid_quality_gate_fail_closed(self):
        self.remote.bad = 'bad_gate'
        with self.assertRaises(Denied):
            self.read('get_quality_gate', 'trusted_project_000', {})

    def test_get_only_guard_forbids_mutating_and_arbitrary_routes(self):
        guard = SonarReadOnlyTransport(self.remote)
        for method, path, params in (
            ('POST', '/api/issues/do_transition',
             {'issue': 'S1', 'transition': 'accept'}),
            ('GET', '/api/components/show', {'component': 'S1'}),
            ('GET', '/api/issues/search',
             {'componentKeys': 'S1', 'method': 'POST'}),
            ('GET', '/api/qualitygates/project_status',
             {'projectKey': 'S1', 'token': 'secret'}),
        ):
            with self.subTest(path=path), self.assertRaisesRegex(
                    Denied, 'SONAR_READ_ONLY_ROUTE_DENIED'):
                guard.call(method, path, params)
        self.assertFalse(self.remote.calls)

    def test_quality_gate_transport_is_fixed_get_https_and_project_key_only(self):
        from urllib.parse import parse_qs, urlsplit

        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self, _limit):
                return b'{"projectStatus":{"status":"OK","conditions":[]}}'

        class Opener:
            def __init__(self):
                self.requests = []
            def open(self, req, timeout):
                self.requests.append((req, timeout))
                return Response()

        transport = SonarHTTPTransport(
            region='eu', bearer_token='SYNTHETIC-TEST-ONLY')
        opener = Opener()
        transport._opener = opener
        reader = SonarReadOnlyTransport(transport)
        result = reader.call('GET', '/api/qualitygates/project_status',
                             {'projectKey': 'trusted_project_000'})
        self.assertEqual(result['projectStatus']['status'], 'OK')
        req, _timeout = opener.requests[0]
        parsed = urlsplit(req.full_url)
        self.assertEqual((parsed.scheme, parsed.hostname, req.get_method()),
                         ('https', 'sonarcloud.io', 'GET'))
        self.assertEqual(parse_qs(parsed.query),
                         {'projectKey': ['trusted_project_000']})
        self.assertIsNone(req.data)
        for invalid in ({'projectId': 'other'}, {'projectKey': 'one',
                                                 'pullRequest': 'foreign'}):
            with self.assertRaises(Denied):
                reader.call('GET', '/api/qualitygates/project_status', invalid)
        self.assertEqual(len(opener.requests), 1)

    def test_wrong_region_and_empty_owner_scope_refused(self):
        with self.assertRaises(ValueError):
            SonarReadAdapter(self.remote, organization_keys=[], region='eu')
        with self.assertRaises(ValueError):
            SonarReadAdapter(self.remote,
                             organization_keys={'trusted_org'}, region='invalid')
        self.assertIn(('GET', '/api/qualitygates/project_status'),
                      SonarHTTPTransport.ROUTES)


if __name__ == '__main__':
    unittest.main()
