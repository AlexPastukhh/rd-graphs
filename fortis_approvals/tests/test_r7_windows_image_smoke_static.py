"""Static audit of R7 Windows Docker image isolated preflight script.

A passing static test does not replace owner Windows execution or image review.
"""
from hashlib import sha256
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'fortis_approvals/deploy/Smoke-R7-Windows-ImageIsolated.ps1'
WORKFILES = Path('/workspace/repo/Workfiles/Smoke-R7-Windows-ImageIsolated-20261101.ps1')
EXPECTED_SCRIPT_HASH = 'ecc76e667d467bb729393ce88939da71ea6140f84f6f3a0f49c3cf8421f3d0ae'
EXPECTED_IMAGE = 'sha256:d555bcd2baf10297e05547d8be7049fbbca80a40df4378e9912e0a3cbbdd9fba'
EXPECTED_TAG = 'fortis-r7-unified-read-ask-candidate:review-20261101-b0055e19'


class R7SmokeStaticTests(unittest.TestCase):
    def test_exact_script_hash_and_workfiles_copy(self):
        raw = SOURCE.read_bytes()
        self.assertEqual(sha256(raw).hexdigest(), EXPECTED_SCRIPT_HASH)
        self.assertEqual(WORKFILES.read_bytes(), raw)
        self.assertEqual(len(raw), 4469)

    def test_pin_metadata_and_failclosed_import(self):
        s = SOURCE.read_text()
        for must in (
            EXPECTED_IMAGE, EXPECTED_TAG,
            'R7_IMAGE_ID_MISMATCH_STOP',
            'R7_IMAGE_DEFAULT_CMD_UNEXPECTED',
            'R7_IMAGE_SECRET_ENV_OR_OVERRIDE_DETECTED',
            'R7_IMAGE_IMPORT_SMOKE_EXIT_NONZERO',
            'R7_IMAGE_IMPORT_SMOKE_SUCCESS_MARKER_MISSING',
            'R7_IMAGE_SONAR_WRITE_DISABLED_MARKER_MISSING',
            "FORTIS_R7_TRUSTED_ADMISSION=OPEN",
            "FORTIS_R7_DISPOSABLE_CONTAINER_AUTO_REMOVED_PASS",
            "--rm --pull=never", "--network none", "--read-only",
            "--cap-drop ALL", "--pids-limit 64", "--memory 256m",
            "--security-opt 'no-new-privileges:true'",
            "fortis_approvals.r7_unified_server preflight-imports",
            "FORTIS_R7_UNIFIED_READ_ASK_IMPORTS_PASS",
            "FORTIS_R7_SONAR_POST=DISABLED",
            "if ($runExit -ne 0)",
            "if ($LASTEXITCODE -ne 0 -or $after -ccontains $smokeName)",
        ):
            with self.subTest(must=must):
                self.assertIn(must, s)

    def test_one_disposable_container_no_operator_actions(self):
        s = SOURCE.read_text()
        # Comments can describe absent actions, so check command invocation only.
        command_lines = [
            line.strip() for line in s.splitlines()
            if '& docker run' in line
        ]
        self.assertEqual(len(command_lines), 1)
        self.assertIn('& docker run --rm --pull=never', command_lines[0])
        for dangerous in (
            '--publish', '-p 19103:', '-p 19104:', '--mount', '-v ',
            '--network host', '--privileged', '--env-file', '--env ',
            '-e FORTIS_SONAR', 'docker compose up',
            'docker container stop', 'docker container restart',
            '--entrypoint sh', '--entrypoint bash', 'docker exec',
        ):
            with self.subTest(dangerous=dangerous):
                self.assertNotIn(dangerous, s)


if __name__ == '__main__':
    unittest.main()
