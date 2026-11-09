"""R5 Windows image source SHA and pip audit static review.

No Docker CLI / Windows PowerShell are installed in this Repo runtime:
tests validate source contract only, NOT a real image audit.
"""
from hashlib import sha256
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'fortis_approvals/deploy/Audit-R5-Windows-ImageContents.ps1'
SRC_DIR = ROOT / 'fortis_approvals'
IMAGE_ID = 'sha256:5fa986d7e532639c5461a87e4a2c34ea8176ec58371f418758d0cd5dfc38bd02'


class R5ContentsAuditStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = SCRIPT.read_text(encoding='utf-8')
        cls.code = '\n'.join(
            line for line in cls.raw.splitlines()
            if not line.lstrip().startswith('#'))
        cls.files = dict(re.findall(
            r"'(/opt/[^']+)'\s*=\s*'([0-9a-f]{64})'",
            cls.code))

    def test_expected_source_hashes_match_exact_review_context(self):
        self.assertEqual(len(self.files), 17)
        self.assertEqual(len(self.files), len(set(self.files)))
        for image_path, digest in self.files.items():
            if image_path == '/opt/requirements-owner.txt':
                local = SRC_DIR / 'requirements-owner.txt'
            else:
                self.assertTrue(
                    image_path.startswith('/opt/fortis/fortis_approvals/'))
                local = SRC_DIR / image_path.split(
                    '/opt/fortis/fortis_approvals/', 1)[1]
            with self.subTest(image=image_path):
                self.assertTrue(local.is_file())
                self.assertFalse(local.is_symlink())
                self.assertEqual(sha256(local.read_bytes()).hexdigest(), digest)

    def test_binds_reported_image_identity_and_private_runtime(self):
        src = self.code
        for term in (
            IMAGE_ID, 'R5_REVIEW_IMAGE_ID_CHANGED',
            '--network\',\'none\'', '--read-only',
            '--pull=never', '--entrypoint sha256sum',
            '--entrypoint python', 'pip list --format freeze',
            'pip check', 'FORTIS_R5_IMAGE_17_INSTALLED_SOURCE_SHA256_PASS',
            'FORTIS_R5_IMAGE_FOUR_PINNED_PIP_VERSIONS_PASS',
            'FORTIS_R5_IMAGE_PIP_CHECK_PASS',
            'FORTIS_R5_IMAGE_BYTES_AND_DEPENDENCIES_OWNER_AUDIT_PASS',
            'FORTIS_R5_TRUSTED_ADMISSION=OPEN',
            'FORTIS_R5_IMAGE_BASE_PROVENANCE_VULNERABILITY_ADMISSION=OPEN',
            'FORTIS_R5_TLS_GRANT_LIFECYCLE=OPEN',
        ):
            with self.subTest(term=term):
                self.assertIn(term, src)

    def test_no_unsafe_container_mutation(self):
        src = self.code
        invocations = re.findall(r'&\s+docker\s+([a-z][a-z-]*)', src, re.I)
        self.assertEqual(invocations.count('run'), 3)
        self.assertEqual(set(invocations), {'info', 'image', 'ps', 'run'})
        for forbidden in (
            'docker compose', 'docker build', 'docker start',
            'docker stop', 'docker restart', 'docker exec',
            'docker volume', 'docker network', 'docker update',
            '--publish', '--mount', '--volume', '--privileged', '--entrypoint sh ',
            'Invoke-RestMethod', 'Invoke-WebRequest', 'Read-Host',
            'Set-Content', 'Get-Content', 'Remove-Item',
        ):
            self.assertNotIn(forbidden, src)
        self.assertNotIn('fortis-repo-test', src)
        self.assertNotIn('fortis-a3-synthetic-fortis-1', src)

    def test_pip_check_accepts_warning_wrapped_success_but_not_failure(self):
        # Windows PowerShell 5.1 wraps stderr as ErrorRecord even with
        # pip return code 0: never compare the entire output with one line.
        src = self.code
        self.assertIn("if ($checkExit -ne 0)", src)
        self.assertIn("$checkOutput -notmatch '(?m)^No broken requirements found\\.$'", src)
        self.assertNotIn("$checkOutput -cne 'No broken requirements found.'", src)
        success = "docker.exe : WARNING: pip cache cannot be used.\nNo broken requirements found."
        broken = "fido2 requires packageX, which is not installed."
        import re as regular_expression
        expression = r'(?m)^No broken requirements found\.$'
        self.assertIsNotNone(regular_expression.search(expression, success))
        self.assertIsNone(regular_expression.search(expression, broken))

    def test_required_packages_match_image_build_file(self):
        requirements = (SRC_DIR / 'requirements-owner.txt').read_text()
        for name, version in [('fido2','2.2.1'),('cryptography','50.0.2'),
                              ('cffi','2.1.1'),('pycparser','3.12')]:
            self.assertIn(name + '==' + version, requirements)
            self.assertIn(name + '==' + version, self.code)


if __name__ == '__main__':
    unittest.main()
