"""Static source/allowlist audit for owner-run R7 v2 Windows image inspection.

This test does not run Docker or inspect a Windows image. It checks the exact
owner-approved ZIP manifest vs expected sha256sum files on the future image,
three ephemeral no-network commands, and immutable owner-side transfer bytes.
"""
from hashlib import sha256
from pathlib import Path
import re
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT/'fortis_approvals/deploy/'
          'Audit-R7-v2-Windows-ImageContents.ps1')
COPY = Path('/workspace/repo/Workfiles/Audit-R7-v2-Windows-ImageContents-20261101.ps1')
ZIP = Path('/workspace/repo/Workfiles/fortis-r7-unified-source-review-v2-20261101.zip')
IMAGE_ID = 'sha256:2a047aaa6ab74a0b3e47e3a02b3ac663301f8363515f0cd32ed3ad1a562d1b73'
IMAGE_TAG = 'fortis-r7-unified-read-ask-candidate:review-20261101-f9791fd1'
OLD_ID = 'sha256:d555bcd2baf10297e05547d8be7049fbbca80a40df4378e9912e0a3cbbdd9fba'
OLD_TAG = 'fortis-r7-unified-read-ask-candidate:review-20261101-b0055e19'


class R7V2OwnerImageContentAuditStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=SOURCE.read_text(encoding='utf-8')

    def test_explicit_image_sources_match_exact_review_zip_manifest(self):
        with ZipFile(ZIP) as z:
            manifest = [x.split('  ',1)
                        for x in z.read('SOURCE-MANIFEST.sha256')
                                    .decode('ascii').splitlines()]
        expected = {
            ('/opt/requirements-owner.txt' if name==
             'fortis_approvals/requirements-owner.txt' else '/opt/fortis/'+name):
             digest
            for digest,name in manifest if
            not name.startswith('fortis_approvals/deploy/')
        }
        actual = dict(re.findall(
            r"^    '(/opt/[^']+)' = '([0-9a-f]{64})'$",
            self.text,re.M))
        self.assertEqual(len(actual),19)
        self.assertEqual(actual,expected)
        self.assertNotIn('/opt/fortis/fortis_approvals/g4_candidate.py',
                         actual)
        self.assertIn('/opt/fortis/fortis_approvals/r7_unified_server.py',
                      actual)

    def test_owner_only_image_pin_and_three_disposable_offline_probes(self):
        s=self.text
        for mandatory in (
            IMAGE_ID, IMAGE_TAG,
            'R7_V2_REVIEW_IMAGE_ID_CHANGED',
            "FORTIS_R7_V2_OWNER_REVIEW_IMAGE_PIN_PASS",
            "FORTIS_R7_V2_IMAGE_19_INSTALLED_SOURCE_SHA256_PASS",
            "FORTIS_R7_V2_IMAGE_FOUR_PINNED_PIP_VERSIONS_PASS",
            "FORTIS_R7_V2_IMAGE_PIP_CHECK_PASS",
            "FORTIS_R7_V2_AUDIT_DISPOSABLE_CONTAINERS_REMOVED_PASS",
            "FORTIS_R7_V2_IMAGE_BYTES_AND_DEPENDENCIES_OWNER_AUDIT_PASS",
            "FORTIS_R7_V2_TRUSTED_ADMISSION=OPEN",
            "'--rm','--pull=never','--network','none','--read-only'",
            "'--user','10001:10001'",
            "'--cap-drop','ALL'",
            "'--security-opt','no-new-privileges:true'",
            "'--pids-limit','64','--memory','256m','--cpus','1'",
            "--entrypoint sha256sum",
            "pip list --format freeze",
            "-B -m pip check",
            "fido2==2.2.1",
            "cryptography==50.0.2",
            "cffi==2.1.1",
            "pycparser==3.12",
        ):
            with self.subTest(mandatory=mandatory):
                self.assertIn(mandatory,s)
        self.assertNotIn(OLD_ID,s)
        self.assertNotIn(OLD_TAG,s)
        self.assertEqual(len(re.findall(r'& docker run @common',s)),3)
        for prohibited in (
            '& docker stop','& docker restart','& docker start','& docker exec',
            '& docker compose','& docker update','& docker volume',
            '--mount', '-p 19103:', '-p 19104:', '--privileged',
            'SONAR_TOKEN_VALUE',
        ):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited,s)

    def test_script_does_not_execute_token_or_owner_routes(self):
        self.assertIn('R7_V2_IMAGE_SOURCE_HASH_MISMATCH',self.text)
        self.assertIn('R7_V2_IMAGE_PINNED_PIP_DEPENDENCY_MISMATCH',self.text)
        self.assertIn('R7_V2_IMAGE_PIP_DEPENDENCY_GRAPH_FAILED',self.text)
        self.assertIn('R7_V2_IMAGE_AUDIT_CONTAINER_NOT_REMOVED',self.text)
        self.assertIn('R7_V2_IMAGE_BASE_PROVENANCE_VULNERABILITY_ADMISSION=OPEN',
                      self.text)
        self.assertIn("if ($checkExit -ne 0)",self.text)
        self.assertIn("if ($hashExit -ne 0)",self.text)
        self.assertIn("if ($pipExit -ne 0)",self.text)

    def test_immutable_owner_workfiles_copy(self):
        # Exact digest is pinned here only after owner-file copy is created.
        self.assertEqual(COPY.read_bytes(),SOURCE.read_bytes())


if __name__ == '__main__':
    unittest.main()
