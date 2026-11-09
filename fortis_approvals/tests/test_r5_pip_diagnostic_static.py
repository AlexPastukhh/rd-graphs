"""Static safety and identity checks for R5 Windows pip failure diagnostic.

PowerShell 5.1 / Docker not installed here; no Windows success claim.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / 'fortis_approvals/deploy/Diagnose-R5-Windows-PipCheck.ps1'
IMAGE_ID = 'sha256:5fa986d7e532639c5461a87e4a2c34ea8176ec58371f418758d0cd5dfc38bd02'


class R5PipDiagnosticStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = FILE.read_text(encoding='utf-8')
        cls.code = '\n'.join(
            line for line in cls.src.splitlines()
            if not line.lstrip().startswith('#'))

    def test_image_pinned_docker_commands_are_isolated(self):
        src = self.code
        invocations = re.findall(r'&\s+docker\s+([a-z][a-z-]*)',src,re.I)
        self.assertEqual(set(invocations), {'info', 'image', 'ps', 'run'})
        self.assertEqual(invocations.count('run'), 1)
        for item in (IMAGE_ID, '--rm', '--pull=never', '--network none',
                     '--read-only', "--user '10001:10001'",
                     '--cap-drop ALL', "--security-opt 'no-new-privileges:true'",
                     '--memory 256m', '--pids-limit 64',
                     '--entrypoint python', '-B -m pip check',
                     'R5_DIAGNOSTIC_CONTAINER_NOT_REMOVED'):
            self.assertIn(item,src)
        for forbidden in ('docker start','docker stop','docker restart',
                          'docker build','docker exec', 'docker compose',
                          'docker network','docker volume','docker cp',
                          '--publish','--mount','--volume','--privileged',
                          'Get-Content','Read-Host','Set-Content','Invoke-RestMethod'):
            self.assertNotIn(forbidden,src)
        self.assertNotIn('fortis-repo-test',src)
        self.assertNotIn('fortis-a3-synthetic-fortis-1',src)

    def test_exit_code_is_not_treated_as_stdout_or_assumed_success(self):
        src=self.code
        for item in ('FORTIS_R5_PIP_CHECK_EXIT_CODE=',
                     'FORTIS_R5_PIP_CHECK_OUTPUT_LENGTH=',
                     'FORTIS_R5_PIP_CHECK_LINE=',
                     'SUCCESS_EXACT_TEXT',
                     'SUCCESS_WITH_DIFFERENT_TEXT',
                     'DEPENDENCY_OR_RUNTIME_ERROR',
                     'R5_PIP_CHECK_OUTPUT_TOO_LARGE_FOR_CHAT',
                     'FORTIS_R5_TRUSTED_ADMISSION=OPEN'):
            self.assertIn(item,src)
        self.assertIn('$exitCode = $LASTEXITCODE',src)
        self.assertIn('$exitCode -eq 0',src)
        self.assertIn('$output -ceq',src)
        self.assertIn('$output.Length -gt 2048',src)


if __name__ == '__main__':
    unittest.main()
