"""Static checks for the corrected owner-only R7 continuation preflight."""
from hashlib import sha256
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'fortis_approvals/deploy/Preflight-R7-P1-Scoped-Windows-ReadOnly-Resume-20261102.ps1'
EXPECTED_IMAGE = 'sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4'
EXPECTED_SCRIPT_SHA256 = '07315249b5e7dade0aec85599dc9948fc7d64e31b3c68434d609c1222d33d8b9'


class R7P1ScopedWindowsPreflightStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = SCRIPT.read_bytes()
        cls.source = cls.data.decode('utf-8')

    def test_exact_image_and_existing_volume_metadata_are_pinned(self):
        text = self.source
        self.assertEqual(sha256(self.data).hexdigest(), EXPECTED_SCRIPT_SHA256)
        self.assertIn(EXPECTED_IMAGE, text)
        self.assertIn('review-p1-scoped-20261102-fac3131e', text)
        self.assertIn("docker image inspect --format '{{.Id}}' $p1Image", text)
        self.assertIn('$id -cne $p1Id', text)
        expected = {
            'fortis-r7-state': '2026-11-01T08:15:45Z',
            'fortis-r7-identity': '2026-11-01T08:15:46Z',
            'fortis-r7-grant': '2026-11-01T08:15:46Z',
            'fortis-r7-sonar-token': '2026-11-01T08:15:46Z',
        }
        for volume, created in expected.items():
            with self.subTest(volume=volume):
                self.assertIn(volume, text)
                self.assertIn(f'{volume}|local|local|{created}', text)
        self.assertIn('FORTIS_R7_P1_SCOPED_EXISTING_VOLUME_METADATA_PASS', text)
        self.assertIn('FORTIS_R7_P1_SCOPED_EXISTING_VOLUMES_UNATTACHED_PASS', text)
        self.assertIn('FORTIS_R7_P1_SCOPED_VOLUME_STATE_PRIOR_ACCEPTANCE_REUSED=YES', text)

    def test_checks_no_attached_containers_and_reserved_ports(self):
        text = self.source
        for expected in (
            'docker ps -a --filter "volume=$volume"',
            'R7_P1_SCOPED_PREPARED_VOLUME_ATTACHED_CONTAINER_REVIEW_REQUIRED',
            '19103', '19104', 'Get-NetTCPConnection',
            'FORTIS_R7_P1_SCOPED_WINDOWS_TCP_PORTS_19103_19104_AVAILABLE_PASS',
            'FORTIS_REPO_RUNNING_PASS', 'FORTIS_A3_RUNNING_HEALTHY_PASS',
            'FORTIS_REPO_WORKSPACE_AND_TRUSTED_MOUNT_ISOLATION_PASS',
        ):
            self.assertIn(expected, text)

    def test_strictly_readonly_no_volume_mount_or_credential_operations(self):
        text = self.source.lower()
        for forbidden in (
            '& docker run', '& docker exec', '& docker build', '& docker start',
            '& docker stop', '& docker restart', '& docker compose', '& docker rm',
            '& docker cp', '& docker volume create', '& docker volume rm',
            '& docker volume prune', 'docker volume inspect $volume',
            'new-item', 'set-content', 'out-file', 'docker logs',
            'sonar_token=', '/state/private', '--mount',
        ):
            with self.subTest(command=forbidden):
                self.assertNotIn(forbidden.lower(), text)
        self.assertIn('docker volume inspect --format', text)
        self.assertIn('FORTIS_R7_P1_SCOPED_GUARD_PREVIEW=NOT_EXECUTED', self.source)
        self.assertIn('FORTIS_R7_P1_SCOPED_CREDENTIAL_PROVISIONING=NOT_EXECUTED', self.source)
        self.assertIn('FORTIS_R7_P1_SCOPED_LIVE_DEPLOYMENT=NOT_AUTHORIZED', self.source)
        self.assertIn('FORTIS_R7_P1_SCOPED_VOLUME_CONTENTS_READ=NO', self.source)
        self.assertIn('FORTIS_R7_P1_SCOPED_VOLUME_MUTATIONS=NONE', self.source)
        self.assertIn('FORTIS_R7_P1_SCOPED_WINDOWS_READONLY_PREFLIGHT_PASS', self.source)


if __name__ == '__main__':
    unittest.main()
