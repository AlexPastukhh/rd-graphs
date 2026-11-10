"""R5 static source/compose and stripped-import checks; Docker is NOT run."""
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT/'fortis_approvals/deploy/Dockerfile-R5-Sonar-Read-Candidate'
COMPOSE = ROOT/'fortis_approvals/deploy/compose-r5-sonar-read.yaml'
EXPECTED = frozenset((
    '__init__.py','core.py','owner_auth.py','owner_portal.py',
    'repo_action_contract.py','repo_ingress.py','sonar.py',
    'sonar_inventory.py','sonar_read.py','r5_read_candidate.py',
    'r5_read_server.py','a3_server.py','server.py',
))


class R5ManifestTests(unittest.TestCase):
    def _sources(self):
        lines = [x.strip() for x in DOCKERFILE.read_text().splitlines()
                 if x.strip() and not x.startswith('#')]
        copy = [shlex.split(x)[1:] for x in lines if x.startswith('COPY ')]
        self.assertEqual(len(copy),3)
        self.assertEqual(copy[0], ['fortis_approvals/requirements-owner.txt',
                                   '/opt/requirements-owner.txt'])
        self.assertEqual(copy[1][-1],'/opt/fortis/fortis_approvals/')
        self.assertEqual(copy[2], ['fortis_approvals/static',
                                   '/opt/fortis/fortis_approvals/static'])
        parts = [Path(x) for x in copy[1][:-1]]
        self.assertEqual({p.name for p in parts},EXPECTED)
        self.assertEqual(len(parts),len(EXPECTED))
        for part in parts:
            self.assertTrue((ROOT/part).is_file())
            self.assertFalse((ROOT/part).is_symlink())
        for forbidden in ('repo_synthetic_candidate.py','synthetic.py',
                          'g4_candidate.py','g4_secret_bootstrap.py',
                          'g4_operator.py','r5-private','server.key','grant'):
            self.assertFalse(any(forbidden in str(part) for part in parts),
                             'unexpected deploy artifact: '+forbidden)
        self.assertEqual(lines[0],'FROM python:3.11-slim')
        self.assertIn('USER 10001:10001',lines)
        self.assertTrue(lines[-1].startswith('CMD ["python","-m",'))
        self.assertEqual(sum(x.startswith('COPY ') for x in lines),3)
        self.assertFalse(any(x.startswith(('ADD ','ARG ','VOLUME ')) for x in lines))
        return parts

    def test_manifest_has_no_legacy_secret_or_synthetic_module(self):
        self._sources()

    def test_separate_compose_volumes_ports_and_frozen_no_restart(self):
        data=COMPOSE.read_text()
        for line in ('restart: "no"','read_only: true','user: "10001:10001"',
                     'cap_drop: [ALL]','no-new-privileges:true',
                     '127.0.0.1:19103:19103','127.0.0.1:19104:19104',
                     'name: fortis-r5-state','name: fortis-r5-identity',
                     'name: fortis-r5-grant','name: fortis-r5-sonar-token',
                     '/run/r5-sonar-token:ro','owner_allowlist_required'):
            self.assertIn(line,data)
        for forbidden in ('fortis-a3-state','fortis-a3-identity',
                          'fortis-a3-grant','docker.sock',
                          'FORTIS_SONAR_TOKEN:', '18990:', '19093:'):
            self.assertNotIn(forbidden,data)

    def test_exact_modules_import_without_full_repo(self):
        parts=self._sources()
        with TemporaryDirectory(prefix='fortis-r5-minimal-import-') as tmp:
            package=Path(tmp)/'fortis_approvals'
            package.mkdir()
            manifest=[]
            for rel in parts:
                dest=package/rel.name
                shutil.copyfile(ROOT/rel,dest)
                digest=hashlib.sha256(dest.read_bytes()).hexdigest()
                self.assertEqual(digest,hashlib.sha256((ROOT/rel).read_bytes()).hexdigest())
                manifest.append(rel.name+':'+digest)
            src=(
                f"import sys; sys.path.insert(0,{tmp!r});"
                "import fortis_approvals.r5_read_server as s;"
                "from fortis_approvals import r5_read_candidate as c;"
                f"assert s.__file__.startswith({tmp!r});"
                "assert 'fortis_approvals.synthetic' not in sys.modules;"
                "assert 'fortis_approvals.repo_synthetic_candidate' not in sys.modules;"
                "assert 'fortis_approvals.runtime' not in sys.modules;"
                "assert s.OWNER_PORT==19103 and s.REPO_PORT==19104;"
                "print('R5_STRIPPED_IMPORT_PASS')"
            )
            completed=subprocess.run(
                [sys.executable,'-I','-B','-c',src],
                cwd=tmp,
                env={'PATH':os.environ.get('PATH',''), 'HOME':tmp,
                     'LANG':'C.UTF-8'},
                capture_output=True,text=True,timeout=20,check=False)
            self.assertEqual(completed.returncode,0,
                             completed.stdout+'\n'+completed.stderr)
            self.assertIn('R5_STRIPPED_IMPORT_PASS',completed.stdout)
            print('R5_EXACT_SOURCE_MANIFEST_SHA256='+hashlib.sha256(
                '\n'.join(sorted(manifest)).encode()).hexdigest())


if __name__ == '__main__':
    unittest.main()
