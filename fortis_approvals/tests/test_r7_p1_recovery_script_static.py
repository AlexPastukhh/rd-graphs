"""Offline guards for GO-1 recovery after creation of the client-only volume.

These tests never call Docker, Windows PowerShell, SonarCloud or live secrets.
"""
from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import re
import tempfile
import unittest

from fortis_approvals.tests.test_r7_p1_provisioning_script_static import load_bootstrap

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
RESUME = DEPLOY / "Resume-R7-P1-Trusted-20261102.ps1"
ORIGINAL = DEPLOY / "Provision-R7-P1-Trusted-20261102.ps1"


class RecoveryScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = RESUME.read_text(encoding="utf-8")
        cls.original = ORIGINAL.read_text(encoding="utf-8")
        cls.bootstrap, cls.ns = load_bootstrap(cls.text)

    def test_same_provision_verify_and_tls_implementation(self):
        unchanged_start = "def _build_tls():"
        unchanged_end = "def main():"
        self.assertEqual(
            self.original.split(unchanged_start, 1)[1].split(unchanged_end, 1)[0],
            self.text.split(unchanged_start, 1)[1].split(unchanged_end, 1)[0],
        )

    def test_recovery_reuses_volume_and_checks_incident_labels(self):
        for required in (
            "Get-R7RecoveryClientProvisionId",
            "docker volume inspect $ClientVolume",
            "ConvertFrom-Json -InputObject $jsonText",
            "com.fortis.r7.p1.role",
            "com.fortis.r7.p1.provision-id",
            "R7_P1_RECOVERY_CLIENT_LABEL_SET_MISMATCH_STOP",
            "R7_P1_RECOVERY_CLIENT_PROVISION_ID_CHANGED_BEFORE_WRITE_STOP",
            "R7_P1_RECOVERY_CLIENT_VOLUME_MISSING_STOP",
            "RESUME-R7-P1",
        ):
            self.assertIn(required, self.text)
        for forbidden in (
            "docker volume create", "docker volume rm",
            "docker compose", "docker build", "docker pull",
            "docker start", "docker stop",
            "index .Labels", "Get-Command docker -CommandType Application",
            "PROVISION-R7-P1",
        ):
            self.assertNotIn(forbidden, self.text)

    def test_preflight_client_mounts_read_only_and_scope(self):
        prefix = self.text.split("    elseif ($Mode -eq 'provision') {", 2)[1]
        self.assertIn("source=fortis-r7-client,target=/run/r7-client,readonly", prefix)
        self.assertIn("source=fortis-r7-state,target=/state,readonly", prefix)
        provision = self.text.split("    elseif ($Mode -eq 'provision') {", 2)[2].split("    else {", 1)[0]
        self.assertNotIn("source=fortis-r7-state", provision)
        self.assertIn("source=fortis-r7-client,target=/run/r7-client", provision)
        self.assertIn("for key in ('identity', 'grant', 'token', 'client'):", self.bootstrap)
        self.assertIn("R7_P1_RECOVERY_ALL_FIVE_VOLUMES_READONLY_EMPTY_PASS", self.text)
        self.assertEqual(self.text.count("Invoke-R7Bootstrap -Mode preflight"), 2)

    def test_existing_client_file_fails_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {key: str(root/key)
                     for key in ("state", "identity", "grant", "token", "client")}
            for name in paths:
                (root/name).mkdir(mode=0o755)
            (root/"state"/"private").mkdir(mode=0o700)
            original_root = self.ns["_open_root"]
            original_private = self.ns["_open_private_state"]

            def _root_as_test_owner(path, expected_uid=0, expected_gid=0):
                return original_root(path, os.geteuid(), os.getegid())

            def _private_as_test_owner(fd):
                return os.open("private", os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd)

            self.ns["_open_root"] = _root_as_test_owner
            self.ns["_open_private_state"] = _private_as_test_owner
            try:
                with redirect_stdout(StringIO()) as output:
                    self.ns["preflight"](paths=paths)
                self.assertIn("R7_P1_EXISTING_VOLUMES_READONLY_PREFLIGHT_PASS", output.getvalue())
                (root/"client"/"unexpected").write_bytes(b"data")
                with self.assertRaises(self.ns["BootstrapStop"]) as raised:
                    self.ns["preflight"](paths=paths)
                self.assertEqual(raised.exception.code, "R7_PRIVATE_VOLUME_NOT_EMPTY")
            finally:
                self.ns["_open_root"] = original_root
                self.ns["_open_private_state"] = original_private

    def test_secret_and_owner_control_unchanged(self):
        for required in (
            "Read-Host 'New owner-approved SonarCloud API token (hidden local input)' -AsSecureString",
            "Read-Host 'Type RESUME-R7-P1",
            "Get-Command docker.exe -CommandType Application",
            "Select-Object -First 1).Source",
            "StandardInput.BaseStream.Write($payloadBytes",
            "ZeroFreeBSTR",
            "Get-R7RecoveryClientProvisionId",
            "Invoke-R7Bootstrap -Mode provision -SecretBytes $secretBytes",
            "Invoke-R7Bootstrap -Mode verify",
            "FORTIS_R7_P1_DEPLOYMENT=NOT_AUTHORIZED",
        ):
            self.assertIn(required, self.text)


if __name__ == "__main__":
    unittest.main()
