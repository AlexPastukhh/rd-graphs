"""R5 one-container candidate tests, synthetic transport/private files only.

No real Sonar API token, no external Sonar network, no owner Windows volumes.
"""
from io import BytesIO
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
import uuid
from unittest.mock import patch

from fortis_approvals.core import Denied
from fortis_approvals.r5_read_candidate import build_r5_read_candidate
from fortis_approvals.r5_read_server import _organizations, _private_ascii
from test_sonar_read_adapter import FakeRemote


GRANT = 'R5_SYNTHETIC_MACHINE_GRANT_0000000001'
OWNER_ORIGIN = 'http://localhost:19103'
REPO_HOST = 'host.docker.internal:19104'


class R5CandidateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='fortis-r5-offline-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root/'private'
        self.state.mkdir(mode=0o700)
        self.state.chmod(0o700)
        self.remote = FakeRemote()

    def build(self, *, state=None, transport=None, grant=GRANT, organizations=('trusted_org',)):
        return build_r5_read_candidate(
            state=state or self.state, owner_origin=OWNER_ORIGIN,
            ingress_host=REPO_HOST, ingress_grant=grant,
            sonar_transport=transport or self.remote,
            organizations=organizations)

    def call(self, ingress, operation='list_issues', *,
             target='trusted_project_000', params=None, grant=GRANT,
             path='/v1/reads', scheme='https'):
        params = (params if params is not None else
                  {'page': 1, 'pageSize': 2})
        body = json.dumps({
            'requestId': str(uuid.uuid4()), 'service': 'sonarcloud',
            'operation': operation, 'target': target, 'params': params,
            'reason': 'R5 offline source acceptance',
        }).encode('utf-8')
        env = {
            'HTTP_HOST':REPO_HOST, 'REQUEST_METHOD':'POST',
            'PATH_INFO':path, 'QUERY_STRING':'',
            'wsgi.url_scheme':scheme, 'wsgi.input':BytesIO(body),
            'CONTENT_TYPE':'application/json', 'CONTENT_LENGTH':str(len(body)),
        }
        if grant is not None:
            env['HTTP_AUTHORIZATION']='Bearer '+grant
        result=[]
        out=b''.join(ingress(env,lambda status,headers:result.append(
            (int(status[:3]),dict(headers)))))
        return result[0][0], json.loads(out),result[0][1]

    def test_one_core_owner_portal_machine_read_and_no_mutation_adapters(self):
        core,owner,portal,ingress=self.build()
        self.assertIs(portal.core,core)
        self.assertIs(portal.auth,owner)
        self.assertIs(ingress.broker.core,core)
        self.assertIs(core.owner_verifier,owner)
        self.assertEqual(core.adapters,{})
        self.assertEqual(ingress.broker.actor_operations,{})
        self.assertTrue(all(k[1]=='sonarcloud' and v=='ALLOW'
                            for k,v in core.policies.items()))
        self.assertFalse(core.owner_list(pending=True))
        code,output,headers=self.call(ingress)
        self.assertEqual(code,200)
        self.assertEqual(output['data']['operation'],'list_issues')
        self.assertEqual(len(output['data']['issues']),2)
        self.assertNotIn('MUST_NOT_LEAK',json.dumps(output))
        self.assertNotIn(GRANT,json.dumps(output))
        self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertTrue(all(x[0]=='GET' for x in self.remote.calls))
        with core._db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)
        self.assertEqual(self.call(ingress,path='/v1/actions')[0],403)
        self.assertEqual(self.call(ingress,path='/v1/owner/pending')[0],404)
        self.assertEqual(self.call(ingress,path='/api/proxy')[0],404)

    def test_unknown_actor_missing_grant_and_http_denied_before_sonar(self):
        _core,_owner,_portal,ingress=self.build()
        for grant in (None,'random-wrong-grant'):
            with self.subTest(grant=grant):
                self.assertEqual(self.call(ingress,grant=grant)[0],401)
        self.assertEqual(self.call(ingress,scheme='http')[0],403)
        self.assertFalse(self.remote.calls)

    def test_private_state_is_new_no_adoption_and_stable_after_restart(self):
        self.build()
        state_files={f.name for f in self.state.iterdir()}
        self.assertIn('.fortis-r5-sonar-read-v1',state_files)
        self.assertIn('owner.sqlite',state_files)
        self.assertIn('approvals.sqlite',state_files)
        core2,_,_,_=self.build()
        self.assertFalse(core2.owner_list(pending=True))
        outside=self.root/'old-a3-state'
        outside.mkdir(mode=0o700)
        (outside/'owner.sqlite').write_text('LEGACY')
        with self.assertRaisesRegex(Denied,'R5_FRESH_STATE_ONLY_NO_ADOPTION'):
            self.build(state=outside)
        self.assertEqual((outside/'owner.sqlite').read_text(),'LEGACY')
        with self.assertRaisesRegex(Denied,'R5_NEW_PRIVATE_STATE_REQUIRED'):
            self.build(state=self.root/'missing')
        self.state.chmod(0o755)
        with self.assertRaisesRegex(Denied,'R5_NEW_PRIVATE_STATE_REQUIRED'):
            self.build()
        self.state.chmod(0o700)

    def test_fail_closed_invalid_trusted_config_before_creating_state(self):
        for orgs in ([],('trusted_org','trusted_org'),('evil/org',),('x',)*21):
            with self.subTest(orgs=orgs),self.assertRaises(ValueError):
                self.build(organizations=orgs)
        self.assertEqual(list(self.state.iterdir()),[])
        for grant in ('x','https://invalid.test','not a grant'):
            with self.subTest(grant=grant),self.assertRaises(Denied):
                self.build(grant=grant)
        self.assertEqual(list(self.state.iterdir()),[])

    def test_private_credential_file_mode_and_no_value_leak(self):
        value='TEST_ONLY_SONAR_CREDENTIAL_NOT_REAL'
        token=self.root/'token'
        token.write_text(value+'\n',encoding='ascii')
        token.chmod(0o600)
        self.assertEqual(_private_ascii(token,max_size=4097),value)
        token.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError,'R5_PRIVATE_FILE'):
            _private_ascii(token,max_size=4097)
        token.chmod(0o600)
        alias=self.root/'alias'
        alias.symlink_to(token)
        with self.assertRaisesRegex(RuntimeError,'R5_PRIVATE_FILE'):
            _private_ascii(alias,max_size=4097)
        token.write_bytes(b'LONG_VALUE_VALID\r\n')
        with self.assertRaisesRegex(RuntimeError,'R5_PRIVATE_FILE_INVALID'):
            _private_ascii(token,max_size=4097)
        token.write_bytes(b'\xff'*20)
        with self.assertRaisesRegex(RuntimeError,'R5_PRIVATE_FILE_INVALID'):
            _private_ascii(token,max_size=4097)

    def test_organization_configuration_exact_and_no_default(self):
        self.assertEqual(_organizations('trusted_org,example_org'),
                         ('trusted_org','example_org'))
        for invalid in ('', 'org,org', ' org', 'org,', 'x'*129, 'org/evil',
                        'org;evil', 'a'*130+'\n'):
            with self.subTest(invalid=invalid),self.assertRaises(RuntimeError):
                _organizations(invalid)


if __name__=='__main__':
    unittest.main()
