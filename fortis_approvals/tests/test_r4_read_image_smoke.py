"""R4 disposable exact-file smoke; imports only the declared COPY modules.

Run with python -I -S from an isolated source tree, or inside the disposable
Dockerfile-R4-Sonar-Read-Check image. All API data and grants are synthetic.
"""
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid

from fortis_approvals.core import Authenticator, Core
from fortis_approvals.repo_action_contract import RepoIntentBroker, SONAR_READ_OPERATIONS
from fortis_approvals.repo_ingress import RepoIngress
from fortis_approvals.sonar_read import SonarReadAdapter


class OfflineSonar:
    def __init__(self):
        self.calls = []
        self.posts = 0
        self.bad = False

    def call(self, method, path, params):
        self.calls.append((method, path, dict(params)))
        if method != 'GET':
            self.posts += 1
            raise AssertionError('R4_POST_MUST_NEVER_DISPATCH')
        if self.bad:
            # The exception reason must not appear in machine response.
            raise RuntimeError('SIMULATED_UPSTREAM_SECRET_MUST_NOT_LEAK')
        if path == '/api/components/search':
            projects = ['project_A', 'project_B']
            if 'q' in params:
                projects = [p for p in projects if p == params['q']]
            page, size = int(params['p']), int(params['ps'])
            return {'components': [
                {'key': p, 'organization': 'example_org', 'qualifier': 'TRK'}
                for p in projects[(page-1)*size:page*size]
            ], 'paging': {'total': len(projects), 'pageIndex': page,
                          'pageSize': size}}
        if path == '/api/issues/search':
            project = params['componentKeys']
            issues = [
                {'key': project+'-I'+str(i), 'project': project,
                 'issueStatus': 'OPEN', 'updateDate': '2026-11-01T00:00:00Z',
                 'message': 'synthetic bug', 'rule': 'python:S100',
                 'severity': 'MAJOR', 'component': project+':src/a.py',
                 'line': i+1, 'assignee': None, 'type': 'BUG',
                 'upstreamPrivate': 'SENTINEL_MUST_NOT_LEAK'}
                for i in range(3)
            ]
            if 'issues' in params:
                issues = [r for r in issues if r['key'] == params['issues']]
            page, size = int(params['p']), int(params['ps'])
            return {'issues': issues[(page-1)*size:page*size],
                    'paging': {'total': len(issues), 'pageIndex': page,
                               'pageSize': size},
                    'total': len(issues),
                    'rawBearer': 'SENTINEL_MUST_NOT_LEAK'}
        if path == '/api/qualitygates/project_status':
            return {'projectStatus': {
                'status': 'ERROR', 'conditions': [
                    {'status':'ERROR','metricKey':'new_coverage',
                     'actualValue':'60','errorThreshold':'80',
                     'secret':'SENTINEL_MUST_NOT_LEAK'}]}}
        raise AssertionError('R4_UNEXPECTED_ROUTE')


class R4MinimalSmoke(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='fortis-r4-stripped-')
        self.addCleanup(self.temp.cleanup)
        self.remote = OfflineSonar()
        self.core = Core(
            Path(self.temp.name)/'state.sqlite', adapters={},
            policies={( 'read-actor', 'sonarcloud', name): 'ALLOW'
                      for _, name in SONAR_READ_OPERATIONS},
            authenticator=Authenticator({
                'r4-synthetic-machine-grant': 'read-actor',
                'r4-other-grant': 'other-actor',
            }))
        self.reader = SonarReadAdapter(
            self.remote, organization_keys={'example_org'})
        self.broker = RepoIntentBroker(
            self.core, actor_operations={},
            actor_read_operations={'read-actor': SONAR_READ_OPERATIONS},
            read_adapter=self.reader)
        self.ingress = RepoIngress(
            self.broker, host='localhost:19440', allow_http_local_test=True)

    def call(self, operation, target, params, *, credential='r4-synthetic-machine-grant',
             route='/v1/reads', extra=None):
        body = json.dumps({
            'requestId': str(uuid.uuid4()), 'service': 'sonarcloud',
            'operation': operation, 'target': target, 'params': params,
            'reason': 'synthetic no secrets',
        }).encode()
        env = {
            'HTTP_HOST': 'localhost:19440', 'QUERY_STRING': '',
            'REQUEST_METHOD': 'POST', 'PATH_INFO': route,
            'wsgi.url_scheme': 'http', 'REMOTE_ADDR': '127.0.0.1',
            'CONTENT_TYPE': 'application/json',
            'CONTENT_LENGTH': str(len(body)), 'wsgi.input': BytesIO(body),
            'HTTP_AUTHORIZATION': 'Bearer '+credential,
        }
        if extra:
            env.update(extra)
        codes = []
        output = b''.join(self.ingress(env, lambda status, headers:
                                      codes.append(int(status[:3]))))
        return codes[0], json.loads(output)

    def test_all_four_read_operations_are_paged_and_filtered(self):
        requests = [
            ('list_projects', 'example_org', {'page':1, 'pageSize':1}),
            ('list_issues', 'project_A', {'page':1, 'pageSize':2}),
            ('get_issue', 'project_A-I1', {'projectKey':'project_A'}),
            ('get_quality_gate', 'project_A', {}),
        ]
        for operation,target,params in requests:
            with self.subTest(operation=operation):
                status,output = self.call(operation,target,params)
                self.assertEqual(status,200)
                self.assertEqual(output['data']['operation'],operation)
                self.assertNotIn('SENTINEL_MUST_NOT_LEAK',json.dumps(output))
        status, output = self.call('list_issues','project_A',
                                   {'page':2,'pageSize':2})
        self.assertEqual(status,200)
        self.assertEqual((output['data']['total'],
                          len(output['data']['issues']),
                          output['data']['nextPage']), (3,1,None))
        self.assertEqual(self.remote.posts,0)
        self.assertTrue(all(call[0]=='GET' for call in self.remote.calls))
        with self.core._db() as db:
            count=db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]
        self.assertEqual(count,0)

    def test_foreign_org_and_project_never_read_issues(self):
        status,_ = self.call('list_projects','other_org',
                             {'page':1,'pageSize':2})
        self.assertEqual(status,403)
        self.assertFalse(self.remote.calls)
        status,_ = self.call('list_issues','not_owner_project',
                             {'page':1,'pageSize':2})
        self.assertEqual(status,403)
        self.assertTrue(all(c[1]=='/api/components/search'
                            for c in self.remote.calls))

    def test_auth_and_ask_denied_before_remote_get(self):
        self.assertEqual(self.call('get_quality_gate','project_A',{},
                         credential='r4-other-grant')[0],403)
        self.core.policies[('read-actor','sonarcloud','get_quality_gate')]='ASK'
        self.assertEqual(self.call('get_quality_gate','project_A',{})[0],403)
        self.assertFalse(self.remote.calls)

    def test_read_cannot_open_action_owner_or_proxy_routes(self):
        for route,expected in (('/v1/actions',403),
                               ('/v1/owner/pending',404),
                               ('/api/proxy',404)):
            with self.subTest(route=route):
                self.assertEqual(self.call('get_issue','project_A-I0',
                    {'projectKey':'project_A'},route=route)[0],expected)
        self.assertFalse(self.remote.calls)

    def test_upstream_error_redacted_without_state_mutation(self):
        self.remote.bad=True
        code,out=self.call('get_quality_gate','project_A',{})
        self.assertEqual((code,out),(500,{'error':'REPO_OUTCOME_UNCONFIRMED'}))
        self.assertNotIn('SIMULATED_UPSTREAM_SECRET',str(out))
        self.assertEqual(self.remote.posts,0)


if __name__ == '__main__':
    unittest.main()
