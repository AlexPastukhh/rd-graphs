"""R7 explicit-source image allowlist and offline SOURCE review.

Does NOT build, run, admit, scan or deploy any Docker image.
"""
import hashlib
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = (ROOT/'fortis_approvals/deploy'/
              'Dockerfile-R7-Unified-Read-Ask-Candidate')
COMPOSE = ROOT/'fortis_approvals/deploy/compose-r7-unified-read-ask.yaml'
MODULES = frozenset((
    '__init__.py','core.py','owner_auth.py','owner_portal.py',
    'repo_action_contract.py','repo_ingress.py','sonar.py',
    'sonar_inventory.py','sonar_read.py','r5_read_candidate.py',
    'r5_read_server.py','r7_unified_candidate.py',
    'r7_unified_server.py','a3_server.py','server.py',
))


class R7ImageSourceAuditTests(unittest.TestCase):
    def test_explicit_fortis_module_image_copy_and_trusted_runtime_only(self):
        src=DOCKERFILE.read_text()
        lines=[line for line in src.splitlines()
               if line.startswith('COPY fortis_approvals/')]
        self.assertEqual(len(lines),3)
        files=lines[1].split()
        self.assertEqual(files[0],'COPY')
        self.assertEqual(files[-1],'/opt/fortis/fortis_approvals/')
        file_names=[item.removeprefix('fortis_approvals/')
                    for item in files[1:-1]]
        self.assertEqual(set(file_names),MODULES)
        self.assertEqual(len(file_names),len(set(file_names)))
        for name in MODULES:
            self.assertTrue((ROOT/'fortis_approvals'/name).is_file())
        self.assertEqual(
            lines[0],
            'COPY fortis_approvals/requirements-owner.txt /opt/requirements-owner.txt')
        self.assertEqual(
            lines[2],
            'COPY fortis_approvals/static /opt/fortis/fortis_approvals/static')
        for forbidden in (
            'COPY . ', 'ADD ', 'ARG ', 'ENV SONAR', 'COPY fortis_approvals/tests',
            'COPY fortis_approvals/repo_sonar_tools.py', 'docker.sock',
            'COPY fortis_approvals/runtime.py',
            'COPY fortis_approvals/g4_candidate.py',
            'COPY fortis_approvals/synthetic.py',
            'COPY fortis_approvals/operator.py',
        ):
            self.assertNotIn(forbidden,src)
        self.assertIn('USER 10001:10001',src)
        self.assertIn('r7_unified_server',src)

    def test_compose_only_new_volumes_no_live_mutation(self):
        src=COMPOSE.read_text()
        for item in ('fortis-r7-state','fortis-r7-identity',
                     'fortis-r7-grant','fortis-r7-sonar-token',
                     'read_only: true','restart: "no"',
                     '127.0.0.1:19103:19103',
                     '127.0.0.1:19104:19104',
                     'cap_drop: [ALL]',
                     'no-new-privileges:true',
                     'external: true'):
            self.assertIn(item,src)
        for forbidden in (
            'fortis-r5-state','fortis-a3','g2_state',
            'g4_state', '/var/run/docker.sock',
            'privileged: true','network_mode: host',
        ):
            self.assertNotIn(forbidden,src)

    def test_all_explicit_image_sources_sha256_record(self):
        sources=sorted('fortis_approvals/'+name for name in MODULES)
        sources += ['fortis_approvals/requirements-owner.txt']
        sources += sorted('fortis_approvals/static/'+p.name
                          for p in (ROOT/'fortis_approvals/static').iterdir()
                          if p.is_file())
        self.assertGreaterEqual(len(sources),19)
        manifest=''.join(
            hashlib.sha256((ROOT/name).read_bytes()).hexdigest()+'  '+name+'\n'
            for name in sources)
        print('R7_SOURCE_ONLY_MANIFEST_SHA256='+
              hashlib.sha256(manifest.encode()).hexdigest())
        self.assertNotIn('repo_sonar_tools.py',manifest)


if __name__=='__main__':
    unittest.main()
