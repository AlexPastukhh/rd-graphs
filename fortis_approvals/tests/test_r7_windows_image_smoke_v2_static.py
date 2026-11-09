"""R7 v2 immutable owner-only isolated image preflight script audit.

Static test does NOT run PowerShell/Windows/Docker and does not admit image.
"""
from hashlib import sha256
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT/'fortis_approvals/deploy/Smoke-R7-Windows-ImageIsolated-v2.ps1'
OWNER_COPY = Path('/workspace/repo/Workfiles/Smoke-R7-Windows-ImageIsolated-v2-20261101.ps1')
SHA = '997b315733382158a3ae08677738bc746c808404349d2ff7cf21f5d8ec81cd3f'
IMAGE_ID = 'sha256:2a047aaa6ab74a0b3e47e3a02b3ac663301f8363515f0cd32ed3ad1a562d1b73'
IMAGE_TAG = 'fortis-r7-unified-read-ask-candidate:review-20261101-f9791fd1'
OLD_IMAGE_ID = 'sha256:d555bcd2baf10297e05547d8be7049fbbca80a40df4378e9912e0a3cbbdd9fba'
OLD_TAG = 'fortis-r7-unified-read-ask-candidate:review-20261101-b0055e19'


class R7V2IsolatedSmokeScriptReview(unittest.TestCase):
    def test_immutable_file_hash_and_owner_workfiles_copy(self):
        data=SRC.read_bytes()
        self.assertEqual(sha256(data).hexdigest(),SHA)
        self.assertEqual(data,OWNER_COPY.read_bytes())
        self.assertEqual(len(data),5319)

    def test_exact_new_image_pins_and_preflight_result(self):
        code=SRC.read_text(encoding='utf-8')
        for expected in (
            IMAGE_ID, IMAGE_TAG,
            'R7_IMAGE_ID_MISMATCH_STOP',
            'R7_IMAGE_DEFAULT_CMD_UNEXPECTED',
            'R7_IMAGE_SECRET_ENV_OR_OVERRIDE_DETECTED',
            "FORTIS_R7_V2_DISPOSABLE_CONTAINER_AUTO_REMOVED_PASS",
            "R7_V2_IMAGE_IMPORT_SMOKE_EXIT_NONZERO",
            "R7_IMAGE_IMPORT_SMOKE_SUCCESS_MARKER_MISSING",
            "R7_IMAGE_SONAR_WRITE_DISABLED_MARKER_MISSING",
            "FORTIS_R7_UNIFIED_READ_ASK_IMPORTS_PASS",
            "FORTIS_R7_SONAR_POST=DISABLED",
            "FORTIS_R7_V2_REVIEW_IMAGE_IMPORT_SMOKE_PASS",
            "FORTIS_R7_TRUSTED_ADMISSION=OPEN",
            "FORTIS_R7_SONAR_NETWORK_REQUESTS=NONE",
            "FORTIS_R7_V2_SMOKE_DIAGNOSTIC=",
            "'fortis-r7-v2-import-smoke-20261101'",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected,code)
        self.assertNotIn(OLD_IMAGE_ID,code)
        self.assertNotIn(OLD_TAG,code)
        self.assertLess(code.index('$runExit = $LASTEXITCODE'),
                        code.index('$after = @(& docker ps -a'))
        self.assertLess(code.index("Write-Host 'FORTIS_R7_V2_DISPOSABLE_CONTAINER_AUTO_REMOVED_PASS'"),
                        code.index('if ($runExit -ne 0)'))

    def test_one_ephemeral_offline_container_and_no_privileged_actions(self):
        code=SRC.read_text(encoding='utf-8')
        calls=[line for line in code.splitlines() if '& docker run' in line]
        self.assertEqual(len(calls),1)
        self.assertIn('& docker run --rm --pull=never',calls[0])
        for mandatory in (
            '--network none','--read-only',
            "--user '10001:10001'",'--cap-drop ALL',
            "--security-opt 'no-new-privileges:true'",
            '--pids-limit 64','--memory 256m','--cpus 1',
            '--tmpfs', '--entrypoint python',
            'fortis_approvals.r7_unified_server preflight-imports',
        ):
            self.assertIn(mandatory,code)
        for forbidden in (
            'docker compose','docker stop','docker start','docker restart',
            'docker exec','docker cp','docker volume create','docker update',
            '--privileged','--env-file','--mount','--network host',
            '-p 19103:', '-p 19104:', 'docker login',
            'SONAR_TOKEN_VALUE','docker pull',
        ):
            self.assertNotIn(forbidden,code)
        self.assertIn('if ($runExit -ne 0)',code)


if __name__=='__main__':
    unittest.main()
