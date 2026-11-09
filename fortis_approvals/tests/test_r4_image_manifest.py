"""R4 reproducible exact-COPY isolation audit; Docker is NOT required.

The checked Dockerfile is an ephemeral test image, not a deployment. The
identical allowlisted files are copied into a fresh directory and the smoke
tests run with Python -I -S: no Repo, site-packages or unknown modules.
"""
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / 'fortis_approvals/deploy/Dockerfile-R4-Sonar-Read-Check'
MODULES = (
    'fortis_approvals/__init__.py',
    'fortis_approvals/core.py',
    'fortis_approvals/repo_action_contract.py',
    'fortis_approvals/repo_ingress.py',
    'fortis_approvals/sonar.py',
    'fortis_approvals/sonar_inventory.py',
    'fortis_approvals/sonar_read.py',
)
SMOKE = 'fortis_approvals/tests/test_r4_read_image_smoke.py'
EXPECTED_COPY = (
    (MODULES, '/opt/r4/fortis_approvals/'),
    ((SMOKE,), '/opt/r4/tests/'),
)


class ImageManifestTests(unittest.TestCase):
    def _inspect(self):
        text = DOCKERFILE.read_text(encoding='utf-8')
        lines = [line.strip() for line in text.splitlines()
                 if line.strip() and not line.strip().startswith('#')]
        commands = [line.split(' ', 1)[0] for line in lines]
        self.assertEqual(commands.count('COPY'), 2)
        self.assertEqual(commands.count('CMD'), 1)
        for forbidden in ('ADD', 'EXPOSE', 'VOLUME', 'ENTRYPOINT', 'ARG'):
            self.assertNotIn(forbidden, commands)
        for line in lines:
            self.assertNotIn('$', line, 'build args/env substitutions forbidden')
            self.assertNotIn('*', line, 'no broad wildcard file selection')
            self.assertNotIn('docker.sock', line)
        self.assertEqual(lines[0], 'FROM python:3.11-slim')
        self.assertIn('USER 10001:10001', lines)
        self.assertTrue(lines[-1].startswith('CMD ["python","-B","-m","unittest"'))
        self.assertFalse(any('pip install' in line for line in lines))
        copies = []
        for line in lines:
            if line.startswith('COPY '):
                parts = shlex.split(line)[1:]
                copies.append((tuple(parts[:-1]), parts[-1]))
        self.assertEqual(tuple(copies), EXPECTED_COPY)
        for sources, _dest in copies:
            for rel in sources:
                original = ROOT / rel
                self.assertTrue(original.is_file(), rel)
                self.assertFalse(original.is_symlink(), rel)
                self.assertEqual(original.resolve().relative_to(ROOT).as_posix(), rel)
        return copies

    def test_exact_allowlist_and_absent_deployable_secrets(self):
        copies = self._inspect()
        all_src = {item for part, _dest in copies for item in part}
        self.assertEqual(all_src, set(MODULES) | {SMOKE})
        self.assertFalse(any(
            name.endswith(('.pem', '.crt', '.key', '.env', '.sqlite', '.ps1'))
            or 'token' in name.lower() or 'operator' in name.lower()
            or 'a3_server' in name.lower() or 'owner_portal' in name.lower()
            for name in all_src))
        self.assertFalse(any('requirements' in name for name in all_src))

    def test_stripped_copy_passes_own_minimal_core_and_read_http_smoke(self):
        copies = self._inspect()
        with tempfile.TemporaryDirectory(prefix='fortis-r4-copy-') as workspace:
            root = Path(workspace)
            copied = []
            for sources, dest in copies:
                subdir = dest.removeprefix('/opt/r4/').strip('/')
                for rel in sources:
                    src = ROOT / rel
                    target = root / subdir / src.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, target)
                    copied.append((rel, hashlib.sha256(target.read_bytes()).hexdigest()))
            self.assertEqual(len(copied), 8)
            for rel, sha in copied:
                self.assertEqual(sha, hashlib.sha256((ROOT/rel).read_bytes()).hexdigest())
            child_script = (
                "import sys, unittest; "
                f"sys.path.insert(0, {str(root)!r}); "
                "import fortis_approvals.core, fortis_approvals.repo_ingress, "
                "fortis_approvals.sonar_read; "
                f"root={str(root)!r}; "
                "assert all(m.__file__.startswith(root) for m in "
                "(fortis_approvals.core, fortis_approvals.repo_ingress, "
                "fortis_approvals.sonar_read)); "
                "suite=unittest.defaultTestLoader.discover(root+'/tests', "
                "pattern='test_r4_read_image_smoke.py'); "
                "result=unittest.TextTestRunner(verbosity=0).run(suite); "
                "sys.exit(0 if result.wasSuccessful() and result.testsRun >= 5 else 1)"
            )
            env = {'PATH': os.environ.get('PATH',''), 'HOME':workspace,
                   'LANG':'C.UTF-8'}
            child = subprocess.run(
                [sys.executable, '-I', '-S', '-B', '-c', child_script],
                cwd=workspace, env=env, text=True, capture_output=True,
                timeout=20, check=False)
            self.assertEqual(child.returncode,0,
                             child.stdout+'\n'+child.stderr)
            print('R4_EXACT_COPY_STRIPPED_STDLIB_SMOKE_PASS')
            print('R4_COPIED_SHA256_MANIFEST=' + hashlib.sha256(
                '\n'.join(f'{rel}:{digest}' for rel,digest in copied).encode()
            ).hexdigest())


if __name__ == '__main__':
    unittest.main()
