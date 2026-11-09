"""R5 image-only Windows smoke static contract.

No Windows PowerShell or Docker runtime is available in Fortis Repo; results
are source review only, never a claim of live image import acceptance.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / 'fortis_approvals/deploy/Smoke-R5-Windows-ImageIsolated.ps1'
IMAGE_ID = 'sha256:5fa986d7e532639c5461a87e4a2c34ea8176ec58371f418758d0cd5dfc38bd02'
IMAGE_TAG = 'fortis-r5-sonar-read-candidate:review-20261101-e6aec453'


class R5ImageSmokeStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = FILE.read_text(encoding='utf-8')
        cls.code = '\n'.join(
            line for line in cls.src.splitlines()
            if not line.lstrip().startswith('#'))

    def test_exact_image_identity_and_metadata(self):
        for required in (
            IMAGE_ID, IMAGE_TAG,
            'R5_IMAGE_ID_MISMATCH_STOP', 'R5_IMAGE_USER_UNEXPECTED',
            'R5_IMAGE_DEFAULT_CMD_UNEXPECTED',
            'R5_IMAGE_EXPOSED_PORTS_UNEXPECTED',
            'R5_IMAGE_SECRET_ENV_OR_OVERRIDE_DETECTED',
            'R5_IMAGE_DECLARED_VOLUMES_UNEXPECTED',
            '19103/tcp', '19104/tcp',
            'FORTIS_R5_REVIEW_IMAGE_METADATA_PASS',
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.src)

    def test_isolated_only_one_ephemeral_container_run(self):
        invocations = re.findall(r'&\s+docker\s+([a-z][a-z-]*)',
                                 self.code, re.I)
        self.assertEqual(invocations.count('run'), 1)
        self.assertEqual(set(invocations), {'info', 'image', 'ps', 'run'})
        for option in ('--rm', '--pull=never', '--network none', '--read-only',
                       '--user \'10001:10001\'',
                       '--cap-drop ALL', '--security-opt \'no-new-privileges:true\'',
                       '--pids-limit 64', '--memory 256m', '--cpus 1',
                       '--tmpfs ', '--entrypoint python',
                       'fortis_approvals.r5_read_server preflight-imports'):
            self.assertIn(option, self.code)
        for forbidden in ('docker build', 'docker create', 'docker start',
                          'docker stop', 'docker restart', 'docker exec',
                          'docker cp', 'docker network', 'docker volume',
                          'docker compose', 'docker update', '--publish',
                          '--expose', '--mount', '--volume', '--privileged',
                          'FORTIS_SONAR_TOKEN=', 'Read-Host', 'Invoke-Expression'):
            self.assertNotIn(forbidden, self.code)
        self.assertNotIn('fortis-repo-test', self.code)
        self.assertNotIn('fortis-a3-synthetic-fortis-1', self.code)

    def test_fail_closed_no_premature_trust(self):
        for required in (
            'R5_EXISTING_CANDIDATE_CONTAINER_REVIEW_REQUIRED',
            'R5_IMAGE_IMPORT_SMOKE_FAILED_REVIEW_DOCKER_OUTPUT_LOCALLY',
            'R5_SMOKE_CONTAINER_NOT_REMOVED',
            'FORTIS_R5_SONAR_READ_IMPORTS_PASS',
            'FORTIS_R5_DISPOSABLE_CONTAINER_AUTO_REMOVED_PASS',
            'FORTIS_R5_REVIEW_IMAGE_IMPORT_SMOKE_PASS',
            'FORTIS_R5_SONAR_NETWORK_REQUESTS=NONE',
            'FORTIS_R5_REPO_GUARDS_PREVIEW=NOT_EXECUTED',
            'FORTIS_R5_TRUSTED_ADMISSION=OPEN',
            'FORTIS_R5_SERVICE_TOKEN_PROVISIONED=NO',
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.code)


if __name__ == '__main__':
    unittest.main()
