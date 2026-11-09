"""G4 read-only provisioning probe: no real tokens, hosts, Docker or Sonar."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock
import json
import unittest

from fortis_approvals.core import Denied
from fortis_approvals.sonar import SonarTransportError
from fortis_approvals.sonar_probe import ReadOnlySonarProbe, probe, main


class FakeReadTransport:
    def __init__(self, *, total=2, issues=None, component='gd-cap'):
        self.calls=[]
        self.total=total
        self.component=component
        self.issues=issues if issues is not None else [
            {'key':'S1','project':'gd-cap','issueStatus':'OPEN'},
            {'key':'S2','project':'gd-cap','issueStatus':'ACCEPTED'}]

    def call(self, method, path, params):
        self.calls.append((method, path, params.copy()))
        if path=='/api/components/show':
            return {'component':{'key':self.component,'qualifier':'TRK'}}
        if path=='/api/issues/search':
            return {'issues':self.issues,'paging':{'total':self.total}}
        raise AssertionError('Unexpected endpoint')


class G4ReadProbeTests(unittest.TestCase):
    def test_reads_project_and_bounded_issues_without_any_mutation(self):
        remote=FakeReadTransport()
        report=probe(transport=remote, project_key='gd-cap',region='eu')
        self.assertEqual(report,{'status':'READ_OK','region':'eu','project':'gd-cap',
            'projectVerified':True,'pageSize':2,'totalIssues':2,
            'sampleStatusCounts':{'ACCEPTED':1,'OPEN':1},
            'mutationRequests':0,'tokenPersisted':False})
        self.assertEqual(remote.calls,[
            ('GET','/api/components/show',{'component':'gd-cap'}),
            ('GET','/api/issues/search',{'componentKeys':'gd-cap','p':'1','ps':'5'})])

    def test_zero_issues_still_proves_project_visible(self):
        result=probe(transport=FakeReadTransport(total=0,issues=[]),
                     project_key='gd-cap',region='us')
        self.assertTrue(result['projectVerified'])
        self.assertEqual(result['pageSize'],0)

    def test_read_probes_never_support_write_even_when_transport_does(self):
        reader=ReadOnlySonarProbe(FakeReadTransport())
        for method,path in [('POST','/api/issues/do_transition'),
                            ('PUT','/api/issues/search'),('GET','/api/issues/transitions')]:
            with self.subTest(method=method,path=path),self.assertRaises(Denied):
                reader.call(method,path,{'issue':'S1'})

    def test_deny_untrusted_projects_and_bad_json_response(self):
        for project in ('', 'bad?key', 'https://evil.com', '../x'):
            with self.subTest(project=project),self.assertRaises(Denied):
                probe(transport=FakeReadTransport(),project_key=project,region='eu')
        with self.assertRaises(Denied):
            probe(transport=FakeReadTransport(component='another'),project_key='gd-cap',region='eu')
        with self.assertRaises(Denied):
            probe(transport=FakeReadTransport(issues=[{'key':'S1','project':'another','status':'OPEN'}]),
                  project_key='gd-cap',region='eu')
        with self.assertRaises(Denied):
            probe(transport=FakeReadTransport(issues=[{'key':'S1','project':'gd-cap'}]),
                  project_key='gd-cap',region='eu')
        with self.assertRaises(Denied):
            probe(transport=FakeReadTransport(total=0),project_key='gd-cap',region='eu')

    def test_operator_stdout_never_contains_token_and_does_not_require_disk(self):
        fake=FakeReadTransport()
        with mock.patch('fortis_approvals.sonar_probe.SonarHTTPTransport') as t:
            t.ORIGINS={'eu':'https://sonarcloud.io','us':'https://sonarqube.us'}
            t.return_value=fake
            with mock.patch('sys.stdin',StringIO('synthetic-fake-token\n')):
                stdout=StringIO()
                with redirect_stdout(stdout):
                    rc=main(['--region','eu','--project','gd-cap'])
            self.assertEqual(rc,0)
            out=stdout.getvalue()
            self.assertEqual(json.loads(out)['status'],'READ_OK')
            self.assertNotIn('synthetic-fake-token',out)
            self.assertEqual(t.call_args.kwargs['bearer_token'],'synthetic-fake-token')
            self.assertEqual(set(call[0] for call in fake.calls),{'GET'})

    def test_missing_token_fails_closed_with_no_upstream_requests(self):
        for secret in ('', 'small', 'x'*4097, 'bad token containing space'):
            with mock.patch('sys.stdin',StringIO(secret+'\n')):
                stdout,stderr=StringIO(),StringIO()
                with redirect_stdout(stdout),redirect_stderr(stderr):
                    rc=main(['--region','eu','--project','gd-cap'])
            self.assertEqual(rc,3)
            self.assertEqual(stdout.getvalue(),'')
            if secret:
                self.assertNotIn(secret,stderr.getvalue())

    def test_http_404_is_attributed_to_specific_read_stage_without_leaking_params(self):
        class Failing(FakeReadTransport):
            def __init__(self, blocked):
                super().__init__()
                self.blocked=blocked
            def call(self, method, path, params):
                if path == self.blocked:
                    raise SonarTransportError('SONAR_HTTP_404')
                return super().call(method,path,params)
        for blocked, prefix in [
            ('/api/components/show','SONAR_PROJECT_LOOKUP_SONAR_HTTP_404'),
            ('/api/issues/search','SONAR_ISSUES_SEARCH_SONAR_HTTP_404')
        ]:
            with self.subTest(blocked=blocked):
                with self.assertRaises(SonarTransportError) as failure:
                    probe(transport=Failing(blocked),project_key='gd-cap',region='eu')
                self.assertEqual(str(failure.exception),prefix)

    def test_docker_probe_does_not_copy_credential_or_owner_modules(self):
        dockerfile=Path(__file__).resolve().parents[1]/'deploy/Dockerfile-G4-ReadOnly'
        content=dockerfile.read_text()
        self.assertNotIn('COPY fortis_approvals /',content)
        self.assertIn('USER 10001:10001',content)
        self.assertIn('sonar_probe.py',content)
        self.assertNotIn('owner_auth.py',content)
        powershell=(Path(__file__).resolve().parents[1]/'deploy/Probe-G4-ReadOnly.ps1').read_text()
        self.assertIn('Read-Host',powershell)
        self.assertIn('--read-only',powershell)
        self.assertIn('--cap-drop ALL',powershell)
        self.assertNotIn('SONAR_TOKEN=',powershell)


if __name__=='__main__': unittest.main()
