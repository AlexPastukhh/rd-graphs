"""R5 Windows image-only source bundle/build script static acceptance.

There is no Windows PowerShell interpreter or Docker CLI in Fortis Repo.
These tests do NOT claim a Windows Docker build or trust admission.
"""
from hashlib import sha256
from pathlib import Path
import re
import shlex
from zipfile import ZipFile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = Path('/workspace/repo/Workfiles/fortis-r5-read-source-review-20261101.zip')
SCRIPT = ROOT / 'fortis_approvals/deploy/Build-R5-Windows-ImageOnly.ps1'
DOCKERFILE = ROOT / 'fortis_approvals/deploy/Dockerfile-R5-Sonar-Read-Candidate'
EXPECTED_ZIP_SHA = 'e6aec45335cc3df17dfa58c3d4692177b99ccac7310b8e1d52dacf997d076bfa'
EXPECTED_MANIFEST_SHA = 'e6a1240d005f2d6f7cbb90e4832d15b2fa645ce0d26a9a86e98b942bf6a09f6d'
EXPECTED_DOCKER_SHA = '91dac44f20ddc68a858e6d2d774c9bb83b6583bec9b6288f0eb7baae4efa2769'


class R5WindowsBuildOnlyTests(unittest.TestCase):
    def test_zip_matches_exact_dockerfile_sources_and_manifest(self):
        self.assertEqual(sha256(BUNDLE.read_bytes()).hexdigest(), EXPECTED_ZIP_SHA)
        paths = set()
        for line in DOCKERFILE.read_text().splitlines():
            if line.startswith('COPY '):
                for rel in shlex.split(line)[1:-1]:
                    path = ROOT/rel
                    if path.is_dir():
                        paths.update(p.relative_to(ROOT).as_posix()
                                     for p in path.rglob('*') if p.is_file())
                    else:
                        paths.add(rel)
        paths.add(DOCKERFILE.relative_to(ROOT).as_posix())
        self.assertEqual(len(paths), 18)
        self.assertEqual(sha256(DOCKERFILE.read_bytes()).hexdigest(),
                         EXPECTED_DOCKER_SHA)
        with ZipFile(BUNDLE) as bundle:
            names = bundle.namelist()
            self.assertEqual(set(names), paths | {'SOURCE-MANIFEST.sha256'})
            self.assertEqual(len(names), 19)
            self.assertEqual(len(names), len(set(names)))
            manifest = bundle.read('SOURCE-MANIFEST.sha256')
            self.assertEqual(sha256(manifest).hexdigest(),
                             EXPECTED_MANIFEST_SHA)
            expected_lines = {
                sha256((ROOT/rel).read_bytes()).hexdigest() + '  ' + rel
                for rel in paths
            }
            self.assertEqual(set(manifest.decode().splitlines()), expected_lines)
            for rel in paths:
                self.assertEqual(bundle.read(rel), (ROOT/rel).read_bytes())
                self.assertFalse((ROOT/rel).is_symlink())

    def test_build_script_pins_zip_manifest_dockerfile_hashes(self):
        src = SCRIPT.read_text()
        for sha in (EXPECTED_ZIP_SHA, EXPECTED_MANIFEST_SHA,
                    EXPECTED_DOCKER_SHA):
            self.assertIn(sha, src)
        self.assertIn('R5_EXACT_BUILD_CONTEXT_AND_MANIFEST_PASS', src)
        self.assertIn('R5_WINDOWS_SYSTEM_DISK_LOW_DO_NOT_BUILD', src)
        self.assertIn('FORTIS_R5_IMAGE_ONLY_BUILD_PASS', src)
        self.assertIn('FORTIS_R5_CONTAINERS_STARTED=NONE', src)
        self.assertIn('Expand-Archive', src)
        self.assertIn('SOURCE-MANIFEST.sha256', src)
        self.assertIn('docker build --no-cache --pull=false', src)

    def test_script_only_mutates_new_image_and_local_staging(self):
        src = SCRIPT.read_text()
        without_comments = '\n'.join(
            x for x in src.splitlines() if not x.lstrip().startswith('#'))
        invocations = re.findall(r'&\s+docker\s+([a-z][a-z-]*)',
                                 without_comments, flags=re.I)
        self.assertEqual(set(invocations), {'info', 'images', 'build', 'image'})
        self.assertEqual(invocations.count('build'), 1)
        for word in ('docker compose','docker run','docker stop',
                     'docker restart','docker cp','docker network',
                     'docker volume', 'docker update', 'Invoke-RestMethod',
                     'Invoke-WebRequest', 'Read-Host', 'Get-Content -Path /run'):
            self.assertNotIn(word, without_comments)
        self.assertIn('FORTIS_REPO_GUARDS_NOT_CHANGED_OR_RESTARTED', without_comments)
        self.assertNotIn('fortis-a3-synthetic', without_comments)


if __name__ == '__main__':
    unittest.main()
