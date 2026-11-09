"""Static review of the R7 P1 trusted-provisioning design; never provisions."""
from hashlib import sha256
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "fortis_approvals/deploy"
COMPOSE = DEPLOY / "compose-r7-p1-scoped.yaml"
TRANSFER = Path(
    "/workspace/repo/Workfiles/_fortis_windows_transfer_tmp/"
    "20261102-r7-p1-compose-review/compose-r7-p1-scoped.yaml"
)
RUNBOOK = DEPLOY / "R7-P1-MINIMAL-TRUSTED-PROVISIONING-20261102.md"
EXPECTED_COMPOSE_SHA256 = (
    "115e283aaee3a6771f0a879008f4048c03150a7422f6b03757fb5105f6c4a5be"
)
IMAGE = (
    "fortis-r7-unified-read-ask-candidate:"
    "review-p1-scoped-20261102-fac3131e"
)
IMAGE_ID = (
    "sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024"
    "f2c062bac0a18ce4"
)


class R7P1TrustedProvisioningStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose = COMPOSE.read_text(encoding="utf-8")
        cls.runbook = RUNBOOK.read_text(encoding="utf-8")

    def test_compose_is_exact_image_only_and_never_builds_or_pulls(self):
        text = self.compose
        data = COMPOSE.read_bytes()
        self.assertEqual(sha256(data).hexdigest(), EXPECTED_COMPOSE_SHA256)
        self.assertEqual(data, TRANSFER.read_bytes())
        self.assertIn(f"image: {IMAGE}", text)
        self.assertIn("pull_policy: never", text)
        self.assertNotRegex(text, r"(?m)^\s*build\s*:")
        self.assertNotIn(":local", text)
        self.assertIn(IMAGE_ID, self.runbook)
        self.assertIn('restart: "no"', text)

    def test_compose_pins_only_nonsecret_single_project_configuration(self):
        text = self.compose
        self.assertIn('FORTIS_SONAR_REGION: "eu"', text)
        self.assertIn('FORTIS_SONAR_ORGANIZATIONS: "alexpastukhh"', text)
        self.assertIn(
            'FORTIS_SONAR_PROJECT_KEY: "AlexPastukhh_obs-planning-docs"',
            text,
        )
        environment = text.split("    environment:\n", 1)[1].split("    ports:\n", 1)[0]
        for secret_env in (
            "SONAR_TOKEN", "FORTIS_SONAR_TOKEN",
            "FORTIS_MACHINE_GRANT", "PRIVATE_KEY", "AUTHORIZATION",
        ):
            self.assertNotIn(secret_env, environment.upper())

    def test_server_compose_preserves_existing_four_volumes_readonly_except_state(self):
        text = self.compose
        for volume in (
            "fortis-r7-state", "fortis-r7-identity",
            "fortis-r7-grant", "fortis-r7-sonar-token",
        ):
            with self.subTest(volume=volume):
                self.assertIn(f"name: {volume}", text)
        self.assertEqual(text.count("    external: true"), 4)
        self.assertEqual(text.count("        read_only: true"), 3)
        self.assertNotIn("fortis-r7-client", text)
        self.assertIn("target: /state", text)

    def test_compose_keeps_loopback_and_container_hardening(self):
        text = self.compose
        for expected in (
            '"127.0.0.1:19103:19103"',
            '"127.0.0.1:19104:19104"',
            'user: "10001:10001"',
            "read_only: true",
            "cap_drop: [ALL]",
            '"no-new-privileges:true"',
            'pids_limit: 100',
            'fortis_approvals.r7_unified_server", "health"',
        ):
            self.assertIn(expected, text)

    def test_runbook_requires_split_uid_client_volume_and_separate_repo_go(self):
        text = self.runbook
        for expected in (
            "fortis-r7-client", "UID 10001", "UID 1000",
            "server.key", "CA certificate",
            "Repo container", "explicit owner GO",
            "Repo client mount", "rollback",
            "не запускать старый preflight повторно",
            "G4 READ ONLY",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)
        self.assertIn("Нельзя монтировать в Repo весь", text)

    def test_runbook_preserves_no_write_and_one_actor_scope(self):
        text = self.runbook
        for expected in (
            "один AI actor", "repo-sonar-read-proposal-actor",
            "NoWriteTransport", "blocked_approvals",
            "Sonar POST = 0", "P1-02", "P1-C",
            "GO-1", "GO-2", "GO-3", "GO-4",
            "docker compose --project-name fortis-r7-p1",
            "config --quiet", "NOT AUTHORIZED",
        ):
            self.assertIn(expected, text)

    def test_invitation_is_after_state_initialization_and_no_execution_authorized(self):
        text = self.runbook
        self.assertIn("только **после** первого старта R7", text)
        self.assertIn("не является согласием на запись секретов", text)
        self.assertIn("Sonar network requests = 0", text)
        self.assertIn("TLS/grant/token не provisioned", text)


if __name__ == "__main__":
    unittest.main()
