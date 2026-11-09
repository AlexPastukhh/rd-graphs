"""G4 organization-scoped all-project discovery: simulated Sonar only."""
import json
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from fortis_approvals.core import Denied
from fortis_approvals.sonar import SonarTransportError, SonarIssueAdapter
from fortis_approvals.sonar_inventory import ReadOnlyTransport, discover, inventory, main


class FakeProjects:
    def __init__(self, totals=None):
        self.totals=totals or {'org-one':237,'org-two':2}
        self.calls=[]
        self.broken=None
    def call(self,method,path,params):
        self.calls.append((method,path,dict(params)))
        assert method=='GET' and path=='/api/components/search'
        assert {'organization','p','ps'} <= set(params) <= {'organization','p','ps','q'}
        org=params['organization'];page=int(params['p']);ps=int(params['ps'])
        keys=[f'{org}_project_{i}' for i in range(self.totals[org])]
        if 'q' in params:
            keys=[key for key in keys if key==params['q']]
        count=len(keys);start=(page-1)*ps
        rows=[{'key':key,'organization':org,'qualifier':'TRK'}
              for key in keys[start:start+ps]]
        if self.broken=='wrong_org' and rows:rows[0]['organization']='foreign'
        if self.broken=='duplicate' and len(rows)>1:rows[1]['key']=rows[0]['key']
        if self.broken=='missing':rows=[]
        return {'components':rows,'paging':{'total':count,'pageIndex':page,'pageSize':ps}}


class InventoryTests(unittest.TestCase):
    def test_paginates_all_accessible_projects_across_two_organizations(self):
        api=FakeProjects()
        result=inventory(api,['org-one','org-two'],region='eu')
        self.assertEqual(result['status'],'DISCOVERY_OK')
        self.assertEqual(result['visibleProjectCount'],239)
        self.assertEqual(len(result['sampleProjectKeys']),12)
        self.assertEqual(result['mutations'],0)
        self.assertEqual(result['tokenPersisted'],False)
        self.assertEqual([(c[2]['organization'],c[2]['p']) for c in api.calls],
                         [('org-one','1'),('org-one','2'),('org-one','3'),('org-two','1')])
        self.assertTrue(all(c[0]=='GET' for c in api.calls))
    def test_future_projects_are_discovered_on_new_scan(self):
        api=FakeProjects({'org-one':1})
        self.assertEqual(len(discover(api,'org-one')),1)
        api.totals['org-one']=2
        self.assertEqual(len(discover(api,'org-one')),2)

    def test_empty_organization_returns_zero_without_writes(self):
        api=FakeProjects({'org-one':0})
        self.assertEqual(discover(api,'org-one'),[])
        self.assertEqual(len(api.calls),1)

    def test_fails_closed_for_wrong_org_duplicates_and_missing_pages(self):
        for broken in ('wrong_org','duplicate','missing'):
            api=FakeProjects({'org-one':2});api.broken=broken
            with self.subTest(broken=broken),self.assertRaises(Denied):
                discover(api,'org-one')

    def test_rejects_arbitrary_organizations_and_unbounded_inputs(self):
        for org in ('','/etc/passwd','org?evil','http://example.com','x'*130):
            with self.subTest(org=org),self.assertRaises(Denied):
                discover(FakeProjects(),org)
        with self.assertRaises(Denied):
            inventory(FakeProjects(),['org-one','org-one'],region='eu')
        with self.assertRaises(Denied):
            inventory(FakeProjects(),['org-one'],region='not-a-region')
        with self.assertRaises(Denied):
            inventory(FakeProjects(),[],region='eu')
        with self.assertRaises(Denied):
            discover(FakeProjects({'org-one':20000}),'org-one')

    def test_http_error_stage_does_not_include_token_or_parameters(self):
        class Fail:
            def call(self,*args):
                raise SonarTransportError('SONAR_HTTP_404')
        with self.assertRaises(SonarTransportError) as failure:
            discover(Fail(),'org-one')
        self.assertEqual(str(failure.exception),'SONAR_PROJECT_DISCOVERY_SONAR_HTTP_404')
    def test_cli_uses_token_only_from_stdin_and_prints_no_secret(self):
        fake=FakeProjects({'org-one':1})
        stdout,stderr=StringIO(),StringIO()
        with mock.patch('fortis_approvals.sonar_inventory.SonarHTTPTransport') as c:
            c.ORIGINS={'eu':'https://sonarcloud.io','us':'https://sonarqube.us'}
            c.return_value=fake
            with mock.patch('sys.stdin',StringIO('synthetic-credential-value\n')):
                with redirect_stdout(stdout),redirect_stderr(stderr):
                    rc=main(['--region','eu','--organization','org-one'])
        self.assertEqual(rc,0,stderr.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())['visibleProjectCount'],1)
        self.assertNotIn('synthetic-credential-value',stdout.getvalue())
        self.assertNotIn('synthetic-credential-value',stderr.getvalue())
        self.assertEqual(c.call_args.kwargs['bearer_token'],'synthetic-credential-value')

    def test_dynamic_ask_scope_follows_owner_organizations_without_wildcard(self):
        api=FakeProjects({'org-one':1})
        with TemporaryDirectory(prefix='fortis-dynamic-scope-') as tmp:
            adapter=SonarIssueAdapter(api,organization_keys={'org-one'},
                                      receipt_store=Path(tmp)/'r.sqlite')
            self.assertEqual(adapter._check_project('org-one_project_0'),'org-one_project_0')
            with self.assertRaises(Denied):
                adapter._check_project('foreign_project_0')
            api.totals['org-one']=2
            self.assertEqual(adapter._check_project('org-one_project_1'),'org-one_project_1')
            api.totals['org-one']=1
            with self.assertRaises(Denied):
                adapter._check_project('org-one_project_1')

    def test_inventory_read_only_wrapper_rejects_write(self):
        reader=ReadOnlyTransport(FakeProjects())
        with self.assertRaises(Denied):
            reader.call('POST','/api/issues/do_transition',
                        {'issue':'S1','transition':'accept'})
        with self.assertRaises(Denied):
            reader.call('GET','/api/components/show',{'component':'S1'})

    def test_issue_read_for_all_three_projects_does_not_post(self):
        class FakeIssueRemote(FakeProjects):
            def call(self,method,path,params):
                if path=='/api/issues/search':
                    self.calls.append((method,path,dict(params)))
                    key=params['componentKeys']
                    return {'issues':[{'key':key+'_issue_0','project':key,'issueStatus':'OPEN'}]}
                return super().call(method,path,params)
        remote=FakeIssueRemote({'org-one':3})
        report=inventory(ReadOnlyTransport(remote),['org-one'],region='eu',read_issues=True)
        self.assertEqual(report['status'],'ISSUES_READ_OK')
        self.assertEqual(report['issuesCheckedProjects'],3)
        self.assertTrue(report['allProjectsChecked'])
        self.assertEqual(len(report['issuesReadResults']),3)
        self.assertEqual(len([c for c in remote.calls if c[1]=='/api/issues/search']),3)
        self.assertTrue(all(c[0]=='GET' for c in remote.calls))
        self.assertEqual(report['mutations'],0)

    def test_issue_read_rejects_cross_project_response(self):
        class WrongProject(FakeProjects):
            def call(self,method,path,params):
                if path=='/api/issues/search':
                    return {'issues':[{'key':'S1','project':'other','status':'OPEN'}]}
                return super().call(method,path,params)
        with self.assertRaises(Denied):
            inventory(ReadOnlyTransport(WrongProject({'org-one':1})),
                      ['org-one'],region='eu',read_issues=True)

    def test_issue_read_limit_reports_partial_instead_of_complete(self):
        class EmptyIssues(FakeProjects):
            def call(self,method,path,params):
                if path=='/api/issues/search':
                    return {'issues':[]}
                return super().call(method,path,params)
        report=inventory(ReadOnlyTransport(EmptyIssues({'org-one':31})),
                         ['org-one'],region='eu',read_issues=True)
        self.assertEqual(report['issuesCheckedProjects'],30)
        self.assertFalse(report['allProjectsChecked'])
        self.assertEqual(report['visibleProjectCount'],31)

    def test_docker_probe_has_no_privileged_mount_or_write(self):
        base=Path(__file__).resolve().parents[1]/'deploy'
        dockerfile=(base/'Dockerfile-G4-ReadOnly').read_text()
        powershell=(base/'Probe-G4-AllProjects.ps1').read_text()
        self.assertIn('sonar_inventory.py',dockerfile)
        self.assertNotIn('owner_auth.py',dockerfile)
        for flag in ('--read-only','--cap-drop','--entrypoint','-AsSecureString'):
            self.assertIn(flag,powershell)
        self.assertNotIn('SONAR_TOKEN=',powershell)


if __name__=='__main__':
    unittest.main()
