"""Offline G4 Windows deployment, credential and separate owner-port contracts."""
from io import StringIO
import os
from pathlib import Path
from contextlib import redirect_stdout
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from fortis_approvals.core import Denied
from fortis_approvals.g4_secret_bootstrap import provision
from fortis_approvals.g4_server import config
from fortis_approvals.g4_candidate import build_candidate, propose_issue
from test_g4_candidate import FakeScopedSonar, G4CandidateTests
from test_owner_portal import VirtualKey


class G4DeployTests(TestCase):
    def test_offline_secret_provision_is_atomic_private_and_never_overwrites(self):
        with TemporaryDirectory(prefix='g4-secret-test-') as folder:
            root=Path(folder)
            root.chmod(0o700)
            target=root/'sonar_token'
            secret='synthetic-local-only-not-real'
            self.assertTrue(provision(stream=StringIO(secret+'\n'),target=target))
            self.assertEqual(target.read_text(),secret)
            self.assertEqual(target.stat().st_mode & 0o777,0o600)
            with self.assertRaises(ValueError):
                provision(stream=StringIO('another-secret-not-real\n'),target=target)
            self.assertEqual(target.read_text(),secret)
            self.assertFalse(any(p.name.startswith('.new-g4-token-') for p in root.iterdir()))

    def test_secret_rejects_weak_permissions_and_symlink(self):
        with TemporaryDirectory(prefix='g4-secret-test-') as folder:
            root=Path(folder);target=root/'sonar_token'
            for value in ('short','invalid token contains space','x'*4097):
                with self.subTest(value=len(value)),self.assertRaises(ValueError):
                    provision(stream=StringIO(value+'\n'),target=target)
            root.chmod(0o755)
            with self.assertRaisesRegex(ValueError,'NOT_PRIVATE'):
                provision(stream=StringIO('synthetic-valid-token-1\n'),target=target)
            root.chmod(0o700)
            existing=root/'original';existing.write_text('unrelated')
            target.symlink_to(existing)
            with self.assertRaisesRegex(ValueError,'NOT_PRIVATE'):
                provision(stream=StringIO('synthetic-valid-token-1\n'),target=target)
            self.assertEqual(existing.read_text(),'unrelated')

    def test_live_candidate_uses_independent_port_and_web_authn_origin(self):
        case=G4CandidateTests(methodName='test_no_write_transport_always_denies_post_even_if_direct')
        case.setUp()
        try:
            with mock.patch.dict(os.environ,{'FORTIS_PORT':'18991',
                'FORTIS_OWNER_ORIGIN':'http://localhost:18991'}):
                core,owner,adapter,portal,port=case.build()
                self.assertEqual(port,18991)
                self.assertEqual(portal.origin,'http://localhost:18991')
                self.assertEqual(set(core.adapters),{'sonarcloud'})
                self.assertEqual(set(core.policies),{('sonarcloud','accept_issue')})
                self.assertEqual(set(core.auth._credentials),{'trusted-g4-proposal-cli-only'})
                row=propose_issue(core,adapter,project_key='AlexPastukhh_gd-cap',
                                  issue_key='S1',reason='Owner-only read-only proposal')
                self.assertEqual(row['state'],'PENDING')
                self.assertEqual(case.remote.posts,0)
        finally:
            case.doCleanups()

    def test_real_g4_port_owner_login_and_readonly_banner(self):
        from io import BytesIO
        import json
        case=G4CandidateTests(methodName='test_no_write_transport_always_denies_post_even_if_direct')
        case.setUp()
        try:
            with mock.patch.dict(os.environ,{'FORTIS_PORT':'18991',
                'FORTIS_OWNER_ORIGIN':'http://localhost:18991'}):
                core,owner,adapter,portal,_=case.build()
                def call(path,body=None,cookie=None,csrf=None):
                    raw=json.dumps(body or {}).encode()
                    env={'HTTP_HOST':'localhost:18991',
                        'REQUEST_METHOD':'POST' if body is not None else 'GET',
                        'PATH_INFO':path,'QUERY_STRING':'','wsgi.input':BytesIO(raw),
                        'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json'}
                    if body is not None:env['HTTP_ORIGIN']='http://localhost:18991'
                    if cookie:env['HTTP_COOKIE']='fortis_owner='+cookie
                    if csrf:env['HTTP_X_FORTIS_CSRF']=csrf
                    result=[]
                    response=b''.join(portal(env,lambda status,head:result.append((status,dict(head)))))
                    code=int(result[0][0][:3])
                    return code,(response if path=='/' else json.loads(response)),result[0][1]
                code,page,_=call('/')
                self.assertEqual(code,200)
                self.assertIn(b'G4 READ ONLY',page)
                self.assertEqual(call('/v1/owner/pending')[0],403)
                class Key18991(VirtualKey):
                    def client_data(self,opts,typ,*,origin='http://localhost:18991',cross_origin=False):
                        return super().client_data(opts,typ,origin=origin,cross_origin=cross_origin)
                key=Key18991()
                code,b,_=call('/v1/enroll/begin',{'invitation':owner.issue_invitation()})
                self.assertEqual(code,200)
                self.assertEqual(call('/v1/enroll/finish',
                    {'ceremonyId':b['ceremonyId'],'response':key.enroll(b)})[0],200)
                code,b,_=call('/v1/login/begin',{})
                self.assertEqual(code,200)
                code,session,head=call('/v1/login/finish',
                    {'ceremonyId':b['ceremonyId'],
                     'response':key.assert_(b,origin='http://localhost:18991')})
                self.assertEqual(code,200)
                cookie=head['Set-Cookie'].split(';')[0].split('=',1)[1]
                row=propose_issue(core,adapter,project_key='AlexPastukhh_gd-cap',
                                  issue_key='S1',reason='G4 distinct owner login proof')
                code,rows,_=call('/v1/owner/pending',cookie=cookie)
                self.assertEqual(code,200)
                self.assertEqual(rows[0]['requestId'],row['requestId'])
                self.assertFalse(rows[0]['approvalAllowed'])
                code,error,_=call('/v1/owner/decision/begin',
                    {'requestId':row['requestId'],'decision':'approve'},
                    cookie=cookie,csrf=session['csrf'])
                self.assertEqual(code,403)
                self.assertEqual(error['error'],'OWNER_OPERATION_WRITE_NOT_ENABLED')
                self.assertEqual(case.remote.posts,0)
        finally:
            case.doCleanups()

    def test_environment_only_carries_token_path_not_token(self):
        with mock.patch.dict(os.environ,{'FORTIS_G4_TOKEN_FILE':'/run/g4-token/private/sonar_token',
            'FORTIS_G4_REGION':'eu','FORTIS_G4_ORGANIZATIONS':'alexpastukhh'}):
            args=config()
            self.assertEqual(args,{'token_file':'/run/g4-token/private/sonar_token',
                'region':'eu','organizations':['alexpastukhh']})

    def test_docker_and_powershell_contract_independent_of_g2(self):
        deploy=Path(__file__).resolve().parents[1]/'deploy'
        compose=(deploy/'compose-g4.yaml').read_text()
        dockerfile=(deploy/'Dockerfile-G4-Candidate').read_text()
        self.assertIn('127.0.0.1:18991:18991',compose)
        self.assertIn('fortis-approvals-g4_state',compose)
        self.assertIn('fortis-approvals-g4_token',compose)
        self.assertIn('g4_token:/run/g4-token:ro',compose)
        self.assertIn('external: true',compose)
        self.assertEqual(compose.count('external: true'), 2)
        self.assertIn('init: true',compose)
        self.assertIn('read_only: true',compose)
        self.assertIn('cap_drop: [ALL]',compose)
        self.assertIn('no-new-privileges:true',compose)
        self.assertIn('restart: unless-stopped',compose)
        self.assertIn('FORTIS_G4_ORGANIZATIONS: alexpastukhh',compose)
        self.assertIn('FORTIS_STATE_DIR: /state/private',compose)
        self.assertIn('FORTIS_G4_TOKEN_FILE: /run/g4-token/private/sonar_token',compose)
        self.assertNotIn('g2_state',compose)
        self.assertNotIn('18990',compose)
        self.assertNotIn('docker.sock',compose)
        self.assertNotIn('SONAR_TOKEN',compose)
        self.assertIn('g4_secret_bootstrap.py',dockerfile)
        self.assertIn('g4_server.py',dockerfile)
        self.assertNotIn('fortis_approvals/tests',dockerfile)
        self.assertNotIn('fortis_approvals/operator.py',dockerfile)
        self.assertNotIn('fortis_approvals/deploy/',dockerfile.split('COPY fortis_approvals/static')[0])
        names=('Prepare-G4-Candidate.ps1','Provision-G4-Token.ps1',
               'Start-G4-Candidate.ps1','Invite-G4-Candidate.ps1',
               'Propose-G4-Issue.ps1','Stop-G4-Candidate.ps1')
        scripts=[(deploy/n).read_text() for n in names]
        for script in scripts:
            self.assertNotIn('--project-name fortis-approvals-g2',script)
            self.assertNotIn('g2_state',script)
            self.assertNotIn('down --volumes',script)
        self.assertIn("docker volume ls --format '{{.Name}}'",scripts[0])
        self.assertNotIn('    & docker volume inspect $volume',scripts[0])
        self.assertNotIn('foreach ($item in @(@(',scripts[0])
        for required in ('g4_volume_repair', "'initialize' $kind", "'verify' $kind",
                         'subdirectory', '10001:10001'):
            self.assertIn(required,scripts[0])
        repair=(deploy/'Repair-G4-Existing-Volumes.ps1').read_text()
        for required in ("docker ps --filter 'label=com.docker.compose.project=fortis-approvals-g4'",
                         'g4_volume_repair', "'initialize' $kind", "'verify' $kind",
                         'G4_PRIVATE_DIRECTORIES_READY'):
            self.assertIn(required,repair)
        self.assertNotIn('g2_state',repair)
        self.assertNotIn('docker volume rm',repair)
        self.assertIn("'verify' 'token'",scripts[1])
        self.assertIn('g4_volume_repair.py',dockerfile)
        self.assertIn("docker volume ls --format '{{.Name}}'",scripts[1])
        self.assertIn("docker image ls --format '{{.Repository}}:{{.Tag}}'",scripts[1])
        provisioner=scripts[1]
        for expected in ('-AsSecureString','SecureStringToBSTR','ZeroFreeBSTR',
                         '--network','none','--cap-drop','--entrypoint',
                         '-m','fortis_approvals.g4_secret_bootstrap',"-cne 'STORE'"):
            self.assertIn(expected,provisioner)
        self.assertNotIn('SONAR_TOKEN=',provisioner)
        self.assertIn('G4_CANDIDATE_READONLY_READY',scripts[2])
        self.assertIn('--no-deps -T owner',scripts[3])
        self.assertIn('--no-deps -T owner',scripts[4])


if __name__=='__main__':
    import unittest
    unittest.main()
