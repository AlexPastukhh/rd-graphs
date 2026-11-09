"""Exact R7 P1 scoped-project source package and owner image-only build review.

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

from fortis_approvals.deploy.package_r7_p1_scoped_20261102 import NAMES

ROOT = Path(__file__).resolve().parents[2]
WORKFILES = Path('/workspace/repo/Workfiles')
PACKAGE = WORKFILES/'fortis-r7-unified-source-review-p1-scoped-20261102.zip'
BUILD = ROOT/'fortis_approvals/deploy/Build-R7-Windows-ImageOnly-p1-scoped-20261102.ps1'
TRANSFER = WORKFILES/'Build-R7-Windows-ImageOnly-p1-scoped-20261102.ps1'
EXPECTED_PACKAGE = 'fac3131e52cf2ca549d40f6037645519e33e61d332dd70e659a06d0b3dd27f83'
EXPECTED_MANIFEST = 'e58bde24a1a7ca714c2202879367d944bf90c14cd76dba94f121641b33b7ad74'
EXPECTED_BUILD = '83a87c9bc1d5104fc6200f1fc04b55de4112e9c87bb9baa1c8f15f8c638d68a0'
EXPECTED_TAG = 'fortis-r7-unified-read-ask-candidate:review-p1-scoped-20261102-fac3131e'
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


class R7P1ScopedReleaseTests(unittest.TestCase):
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

    def test_live_compose_requires_exact_project_runtime_configuration(self):
        compose=(ROOT/'fortis_approvals/deploy/compose-r7-unified-read-ask.yaml').read_text()
        self.assertIn('FORTIS_SONAR_PROJECT_KEY:',compose)
        self.assertIn('owner_exact_project_required',compose)
        server=(ROOT/'fortis_approvals/r7_unified_server.py').read_text()
        self.assertIn('R7_P1_EXACT_PROJECT_KEY_REQUIRED',server)
        self.assertIn('project_keys=(project_key,)',server)

    def test_owner_build_script_exact_copy_and_image_only_guardrails(self):
        source = BUILD.read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), EXPECTED_BUILD)
        self.assertEqual(source, TRANSFER.read_bytes())
        text = source.decode('utf-8')
        for required in (
            EXPECTED_PACKAGE, EXPECTED_MANIFEST, EXPECTED_TAG,
            'fortis-r7-unified-source-review-p1-scoped-20261102.zip',
            'R7_P1_SCOPED_REVIEW_IMAGE_TAG_ALREADY_EXISTS_NO_OVERWRITE',
            'R7_P1_SCOPED_SOURCE_FILE_COUNT_MISMATCH',
            'R7_P1_SCOPED_BUILD_CONTEXT_HAS_UNEXPECTED_FILES',
            '--no-cache --pull=false',
            'FORTIS_R7_P1_SCOPED_CONTAINERS_STARTED=NONE',
            'FORTIS_R7_P1_SCOPED_SONAR_TOKEN_PROVISIONED=NO',
            'FORTIS_R7_P1_SCOPED_SONAR_POST=DISABLED',
            'FORTIS_R7_P1_SCOPED_TRUSTED_ADMISSION=OPEN',
            'FORTIS_R7_P1_SCOPED_DEPLOYMENT=NOT_AUTHORIZED',
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
