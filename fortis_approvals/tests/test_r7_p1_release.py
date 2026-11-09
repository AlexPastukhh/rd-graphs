"""Exact R7 P1 source package and owner image-only build review.

This is offline-only: it never runs PowerShell/Docker, deploys a service,
provisions credentials, or calls SonarCloud.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from fortis_approvals.deploy.package_r7_p1_20261102 import NAMES

ROOT = Path(__file__).resolve().parents[2]
WORKFILES = Path('/workspace/repo/Workfiles')
PACKAGE = WORKFILES/'fortis-r7-unified-source-review-p1-20261102.zip'
BUILD = ROOT/'fortis_approvals/deploy/Build-R7-Windows-ImageOnly-p1-20261102.ps1'
TRANSFER = WORKFILES/'Build-R7-Windows-ImageOnly-p1-20261102.ps1'
EXPECTED_PACKAGE = '7755e84ecb2a4abf23c66d97707a81838cadc2424c2c24700a499aa3b9a1d0d5'
EXPECTED_MANIFEST = 'eeac1cb7847fb8c99f949b878d69968c311556fc5a27c91851db459f5e1db3cb'
EXPECTED_BUILD = '409a8062ea6ed8cc4378ac2e7e7e2b73f1572036a39679741a564b23cf04734f'
EXPECTED_TAG = 'fortis-r7-unified-read-ask-candidate:review-p1-20261102-7755e84e'
EXPECTED_IMPORT = (
    'FORTIS_R7_UNIFIED_READ_ASK_IMPORTS_PASS\n'
    'FORTIS_R7_SONAR_POST=DISABLED\n')
P2_SUPERSEDED = frozenset({
    'fortis_approvals/core.py',
    'fortis_approvals/owner_portal.py',
    'fortis_approvals/r7_unified_candidate.py',
    'fortis_approvals/r7_unified_server.py',
    'fortis_approvals/deploy/Dockerfile-R7-Unified-Read-Ask-Candidate',
})


def isolated_import():
    with TemporaryDirectory(prefix='r7-p1-exact-package-') as tmp:
        with ZipFile(PACKAGE) as archive:
            archive.extractall(tmp)
        env = dict(os.environ)
        env['PYTHONPATH'] = tmp
        env['PYTHONNOUSERSITE'] = '1'
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        return subprocess.run(
            [sys.executable, '-B', '-m',
             'fortis_approvals.r7_unified_server', 'preflight-imports'],
            cwd=tmp, env=env, timeout=12, capture_output=True, text=True)


class R7P1ReleaseTests(unittest.TestCase):
    def test_historical_package_manifest_is_intact_and_p2_sources_are_superseded(self):
        self.assertEqual(hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
                         EXPECTED_PACKAGE)
        with ZipFile(PACKAGE) as archive:
            self.assertEqual(len(archive.namelist()), 21)
            self.assertEqual(len(set(archive.namelist())), 21)
            self.assertEqual(set(archive.namelist()),
                             set(NAMES) | {'SOURCE-MANIFEST.sha256'})
            manifest = archive.read('SOURCE-MANIFEST.sha256')
            self.assertEqual(hashlib.sha256(manifest).hexdigest(),
                             EXPECTED_MANIFEST)
            for line, expected_name in zip(
                    manifest.decode('ascii').splitlines(), NAMES, strict=True):
                digest, name = line.split('  ', 1)
                self.assertEqual(name, expected_name)
                archived = archive.read(name)
                self.assertEqual(hashlib.sha256(archived).hexdigest(), digest)
                if name in P2_SUPERSEDED:
                    self.assertNotEqual(archived, (ROOT/name).read_bytes())
            for name in archive.namelist():
                lowered = name.lower()
                self.assertNotIn('secret', lowered)
                self.assertNotIn('token', lowered)
                self.assertNotIn('grant', lowered)
            self.assertNotIn('fortis_approvals/repo_sonar_tools.py',
                             archive.namelist())

    def test_exact_minimal_archive_imports_without_checkout_fallback(self):
        result = isolated_import()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, EXPECTED_IMPORT)
        self.assertEqual(result.stderr, '')

    def test_owner_build_script_exact_copy_and_image_only_guardrails(self):
        source = BUILD.read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), EXPECTED_BUILD)
        self.assertEqual(source, TRANSFER.read_bytes())
        text = source.decode('utf-8')
        for required in (
            EXPECTED_PACKAGE, EXPECTED_MANIFEST, EXPECTED_TAG,
            'fortis-r7-unified-source-review-p1-20261102.zip',
            'R7_P1_REVIEW_IMAGE_TAG_ALREADY_EXISTS_NO_OVERWRITE',
            'R7_P1_SOURCE_FILE_COUNT_MISMATCH',
            'R7_P1_BUILD_CONTEXT_HAS_UNEXPECTED_FILES',
            '--no-cache --pull=false',
            'FORTIS_R7_P1_CONTAINERS_STARTED=NONE',
            'FORTIS_R7_P1_SONAR_TOKEN_PROVISIONED=NO',
            'FORTIS_R7_P1_SONAR_POST=DISABLED',
            'FORTIS_R7_P1_TRUSTED_ADMISSION=OPEN',
            'FORTIS_R7_P1_DEPLOYMENT=NOT_AUTHORIZED',
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertEqual(text.count("    'fortis_approvals/"), 20)
        self.assertEqual(text.count('& docker build --no-cache'), 1)
        for forbidden in (
            '& docker run', '& docker stop', '& docker start',
            '& docker restart', '& docker compose', '& docker exec',
            '& docker volume', '& docker update', 'SONAR_TOKEN=',
            'approve=true',
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.lower(), text.lower())
        self.assertNotIn('review-20261101-f9791fd1', text)
        self.assertNotIn('fortis-r7-unified-source-review-v2-20261101.zip',
                         text)


if __name__ == '__main__':
    unittest.main()
