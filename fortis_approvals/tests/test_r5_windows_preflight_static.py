"""Static contract checks for the read-only Windows R5 owner preflight.

No Windows PowerShell interpreter in Fortis Repo; these tests do NOT claim
to execute the PS1 or to verify actual Windows Docker status.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'fortis_approvals/deploy/Preflight-R5-Windows-ReadOnly.ps1'
COMPOSE = ROOT / 'fortis_approvals/deploy/compose-r5-sonar-read.yaml'


class R5WindowsPreflightStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding='utf-8')
        cls.code = '\n'.join(
            line for line in cls.source.splitlines()
            if not line.lstrip().startswith('#'))
        cls.compose = COMPOSE.read_text(encoding='utf-8')

    def test_docker_commands_are_read_only(self):
        invocations = re.findall(r'&\s+docker\s+([a-z][a-z-]*)',
                                 self.code, flags=re.I)
        self.assertGreaterEqual(len(invocations), 5)
        self.assertEqual(set(invocations), {'info', 'ps', 'inspect', 'volume'})
        self.assertNotRegex(self.code, r'(?i)\bdocker\s+(?:exec|run|build|'
                            r'up|stop|start|restart|rm|rmi|create|update|'
                            r'network|cp|compose|pull|push|volume\s+create)')
        self.assertIn("docker volume ls --format '{{.Name}}'", self.code)
        self.assertIn("docker info --format '{{.OSType}}'", self.code)
        self.assertIn('docker inspect --type container --format', self.code)
        self.assertNotIn('Config.Env', self.code)
        self.assertNotIn('docker inspect $name', self.code)

    def test_checks_guards_before_future_restart_without_running_them(self):
        for required in (
            "fortis-repo-test", "fortis-a3-synthetic-fortis-1",
            "fortis-repo-workspace", "R5_REPO_MOUNT_ISOLATION_FAILED",
            "R5_REPO_CONNECTION_CONTAINER_NOT_RUNNING",
            "R5_A3_CONTAINER_NOT_HEALTHY",
            "FORTIS_REPO_GUARD_REPO1_REPO2_PREVIEW=NOT_EXECUTED",
            "FORTIS_R5_DOCKER_IMAGE_BUILD=NOT_EXECUTED",
            "FORTIS_R5_TLS_GRANT_TOKEN_PROVISIONING=NOT_EXECUTED",
            "FORTIS_R5_WINDOWS_READONLY_PREFLIGHT_PASS",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.code)
        for forbidden in ('Read-Host','Start-Process', 'Set-ExecutionPolicy',
                          'Invoke-Expression', 'Invoke-WebRequest',
                          'Invoke-RestMethod', 'New-Item', 'Set-Content'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.code)
        self.assertIn('$ErrorActionPreference = \'Stop\'', self.code)

    def test_port_volume_names_match_r5_candidate(self):
        for vol in ('fortis-r5-state','fortis-r5-identity',
                    'fortis-r5-grant','fortis-r5-sonar-token'):
            self.assertIn(vol, self.source)
            self.assertIn('name: '+vol, self.compose)
        for port in (19103,19104):
            self.assertIn(str(port), self.source)
            self.assertIn('127.0.0.1:%d:%d' % (port,port), self.compose)
        self.assertIn("Get-NetTCPConnection -State Listen", self.code)
        self.assertIn("'HostConfig.PortBindings'", self.code)
        self.assertIn("docker ps -a --format '{{.Names}}'", self.code)

    def test_does_not_include_token_values_or_windows_mutations(self):
        for bad in ('FORTIS_SONAR_TOKEN=', 'Authorization:', 'Bearer ',
                    'docker.sock:/', 'Get-Content', 'server.key',
                    'grant).read', 'docker logs', 'docker exec'):
            self.assertNotIn(bad, self.code)
        self.assertIn("FORTIS_R5_NEXT=OWNER_REVIEW_EXACT_DOCKER_BUILD_AND_GUARD_IMPACT",
                      self.code)


if __name__ == '__main__':
    unittest.main()
