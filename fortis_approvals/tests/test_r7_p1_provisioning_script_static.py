"""Static/offline checks for the owner-only R7 P1 GO-1 provisioner.

This suite never invokes PowerShell, Docker, SonarCloud or real credentials.
The embedded bootstrap is exercised only against temporary test directories.
"""
from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import os
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "fortis_approvals/deploy/Provision-R7-P1-Trusted-20261102.ps1"
IMAGE_ID = (
    "sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024"
    "f2c062bac0a18ce4"
)


def load_bootstrap(script_text):
    match = re.search(r"\$bootstrap = @'\n(.*?)\n'@", script_text, re.S)
    if not match:
        raise AssertionError("embedded Python bootstrap not found")
    source = match.group(1)
    compile(source, str(SCRIPT) + ":bootstrap", "exec")
    namespace = {"__name__": "r7_p1_test_bootstrap"}
    exec(compile(source, str(SCRIPT) + ":bootstrap", "exec"), namespace)
    return source, namespace


class R7P1ProvisioningScriptStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")
        cls.bootstrap, cls.ns = load_bootstrap(cls.text)

    def test_exact_scoped_image_and_no_deployment_commands(self):
        self.assertIn(IMAGE_ID, self.text)
        self.assertIn(
            "fortis-r7-unified-read-ask-candidate:"
            "review-p1-scoped-20261102-fac3131e", self.text)
        for forbidden in (
            "docker compose", "docker build", "docker pull",
            "docker start", "docker stop", "docker restart", "docker rm ",
            "docker volume rm", "docker network create",
            "Invoke-WebRequest", "Invoke-RestMethod",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.text)

    def test_no_network_root_readonly_and_bounded_helper_containers(self):
        for expected in (
            "'--network','none'", "'--read-only'",
            "'--pull=never'", "'--cap-drop','ALL'",
            "'--security-opt','no-new-privileges:true'",
            "'--pids-limit','16'", "'--memory','128m'",
            "'--cap-add','CHOWN'", "'--cap-add','FOWNER'",
            "'--cap-add','DAC_OVERRIDE'",
        ):
            self.assertIn(expected, self.text)
    def test_volume_mounts_are_separated_by_mode(self):
        preflight_matches = list(re.finditer(r"if \(\$Mode -eq 'preflight'\) \{", self.text))
        provision_matches = list(re.finditer(r"elseif \(\$Mode -eq 'provision'\) \{", self.text))
        preflight_start = preflight_matches[1].start()
        preflight_end = provision_matches[1].start()
        preflight = self.text[preflight_start:preflight_end]
        provision_start = provision_matches[1].start()
        verify_start = self.text.index("    else {", provision_start)
        provision = self.text[provision_start:verify_start]
        verify_end = self.text.index("    $dockerArgs += @(\n        '--entrypoint'", verify_start)
        verify = self.text[verify_start:verify_end]
        self.assertIn("fortis-r7-state,target=/state,readonly", preflight)
        self.assertIn("fortis-r7-identity,target=/run/r7-identity,readonly", preflight)
        self.assertIn("fortis-r7-grant,target=/run/r7-grant,readonly", preflight)
        self.assertIn("fortis-r7-sonar-token,target=/run/r7-sonar-token,readonly", preflight)
        self.assertNotIn("fortis-r7-state", provision)
        for volume in ("fortis-r7-identity", "fortis-r7-grant",
                       "fortis-r7-sonar-token", "fortis-r7-client"):
            self.assertIn(volume, provision)
            self.assertIn(volume, verify)
        self.assertNotIn("fortis-r7-state", verify)

    def test_hidden_token_stays_out_of_argv_environment_and_text(self):
        for expected in (
            "Read-Host 'New owner-approved SonarCloud API token (hidden local input)' -AsSecureString",
            "SecureStringToBSTR", "ReadInt16($ptr, 2 * $i)",
            "ZeroFreeBSTR", "[Array]::Clear($secretBytes",
            "RedirectStandardInput = $true",
            "StandardInput.BaseStream.Write($payloadBytes",
            "PROVISION-R7-P1",
        ):
            self.assertIn(expected, self.text)
        for forbidden in (
            "PtrToStringBSTR", "$plain", "--env", "-e FORTIS_",
            "SONAR_TOKEN=", "FORTIS_SONAR_TOKEN=",
        ):
            self.assertNotIn(forbidden, self.text)
    def _test_volume_paths(self, root):
        paths = {}
        for key in ("identity", "grant", "token", "client"):
            path = root / key
            path.mkdir(mode=0o755)
            paths[key] = str(path)
        return paths

    def _patch_test_owners(self):
        original = self.ns["_open_root"]
        def open_as_test_owner(path, expected_uid=0, expected_gid=0):
            return original(path, os.geteuid(), os.getegid())
        self.ns["_open_root"] = open_as_test_owner
        return original

    def test_provision_and_verify_file_ownership_without_secret_output(self):
        token = b"TEST-SONAR-READ-ONLY-0123456789"
        with tempfile.TemporaryDirectory() as raw:
            paths = self._test_volume_paths(Path(raw))
            original_open = self._patch_test_owners()
            original_build = self.ns["_build_tls"]
            original_verify = self.ns["_verify_tls"]
            self.ns["_build_tls"] = lambda: (
                b"K" * 256, b"L" * 256, b"C" * 256,
                "ab" * 32, "cd" * 32, "2099-01-01T00:00:00Z")
            self.ns["_verify_tls"] = lambda *_: (
                "ab" * 32, "cd" * 32, "2099-01-01T00:00:00Z")
            output = StringIO()
            try:
                with redirect_stdout(output):
                    self.ns["provision"](
                        paths=paths, token=token,
                        server_uid=os.geteuid(), server_gid=os.getegid(),
                        client_uid=os.geteuid(), client_gid=os.getegid())
                    self.ns["verify"](
                        paths=paths, server_uid=os.geteuid(),
                        server_gid=os.getegid(), client_uid=os.geteuid(),
                        client_gid=os.getegid())
            finally:
                self.ns["_open_root"] = original_open
                self.ns["_build_tls"] = original_build
                self.ns["_verify_tls"] = original_verify
            self.assertNotIn(token.decode("ascii"), output.getvalue())
            self.assertIn("R7_P1_METADATA_AND_TLS_VERIFY_PASS", output.getvalue())
            self.assertEqual(
                set(os.listdir(paths["identity"])), {"server.crt", "server.key"})
            self.assertEqual(set(os.listdir(paths["grant"])), {"grant"})
            self.assertEqual(set(os.listdir(paths["token"])), {"token"})
            self.assertEqual(
                set(os.listdir(paths["client"])), {"grant", "server.crt"})
            server_grant = (Path(paths["grant"]) / "grant").read_bytes()
            client_grant = (Path(paths["client"]) / "grant").read_bytes()
            self.assertEqual(server_grant, client_grant)
            self.assertEqual((Path(paths["token"]) / "token").read_bytes(), token + b"\n")
            for directory, filename, mode in (
                ("identity", "server.key", 0o600),
                ("grant", "grant", 0o600),
                ("token", "token", 0o600),
                ("client", "grant", 0o600),
                ("client", "server.crt", 0o644),
            ):
                info = (Path(paths[directory]) / filename).stat()
                self.assertEqual(info.st_uid, os.geteuid())
                self.assertEqual(info.st_gid, os.getegid())
                self.assertEqual(info.st_mode & 0o777, mode)

    def test_invalid_token_and_existing_files_fail_without_overwrite(self):
        with tempfile.TemporaryDirectory() as raw:
            paths = self._test_volume_paths(Path(raw))
            original_open = self._patch_test_owners()
            try:
                with self.assertRaises(self.ns["BootstrapStop"]):
                    self.ns["provision"](
                        paths=paths, token=b"bad",
                        server_uid=os.geteuid(), server_gid=os.getegid(),
                        client_uid=os.geteuid(), client_gid=os.getegid())
                self.assertTrue(all(not os.listdir(path) for path in paths.values()))
                target = Path(paths["identity"]) / "server.key"
                target.write_bytes(b"do-not-overwrite")
                with self.assertRaises(self.ns["BootstrapStop"]):
                    self.ns["provision"](
                        paths=paths, token=b"TEST-SONAR-READ-ONLY-0123456789",
                        server_uid=os.geteuid(), server_gid=os.getegid(),
                        client_uid=os.geteuid(), client_gid=os.getegid())
                self.assertEqual(target.read_bytes(), b"do-not-overwrite")
            finally:
                self.ns["_open_root"] = original_open
    def test_tls_profile_and_one_actor_scope_are_pinned_in_source(self):
        for expected in (
            "ec.SECP256R1()", "datetime.timedelta(days=90)",
            "x509.BasicConstraints(ca=True, path_length=0)",
            "x509.DNSName('host.docker.internal')",
            "ExtendedKeyUsageOID.SERVER_AUTH",
            "x509.KeyUsage(", "serialization.PrivateFormat.PKCS8",
            "del ca_key", "token_urlsafe(48)",
            "server_uid=10001", "client_uid=1000",
        ):
            self.assertIn(expected, self.bootstrap)
        self.assertNotIn("ca_key.private_bytes", self.bootstrap)
        self.assertIn("os.O_EXCL", self.bootstrap)
        self.assertIn("getattr(os, 'O_NOFOLLOW'", self.bootstrap)
        self.assertIn("os.link(", self.bootstrap)

    def test_script_never_touches_state_during_provision_or_verify(self):
        self.assertIn("R7_STATE_PRIVATE_NOT_EMPTY", self.bootstrap)
        self.assertIn("info.st_uid != 10001", self.bootstrap)
        self.assertIn("stat.S_IMODE(info.st_mode) != 0o700", self.bootstrap)
        self.assertIn("fortis-r7-state,target=/state,readonly", self.text)
        provision_index = list(re.finditer(r"elseif \(\$Mode -eq 'provision'\) \{", self.text))[1].start()
        self.assertNotIn("fortis-r7-state", self.text[provision_index:])
        self.assertIn("R7_P1_DEPLOYMENT=NOT_AUTHORIZED", self.text)

    def test_owner_ack_and_unique_volume_label_fail_closed(self):
        for expected in (
            "PROVISION-R7-P1",
            "com.fortis.r7.p1.role=client-only",
            "com.fortis.r7.p1.provision-id",
            "R7_P1_CLIENT_VOLUME_NOT_CREATED_BY_THIS_RUN_STOP",
            "R7_P1_CLIENT_VOLUME_ALREADY_EXISTS_STOP",
        ):
            self.assertIn(expected, self.text)


    def test_docker_process_uses_one_explicit_executable_path(self):
        self.assertIn('Get-Command docker.exe -CommandType Application', self.text)
        self.assertIn('Select-Object -First 1).Source', self.text)
        self.assertIn('Test-Path -LiteralPath $dockerPath -PathType Leaf', self.text)
        self.assertNotIn('Get-Command docker -CommandType Application', self.text)
        self.assertIn('$startInfo.FileName = $dockerPath', self.text)

    def test_python_loader_is_a_single_windows_process_argument(self):
        match = re.search(r'^\$pythonLoader = "(.*)"$', self.text, re.M)
        self.assertIsNotNone(match)
        loader = match.group(1)
        self.assertFalse(any(char.isspace() for char in loader))
        self.assertNotIn('"', loader)
        self.assertIn("sys').stdin.buffer.readline()", loader)
        self.assertIn("validate=True", loader)


if __name__ == "__main__":
    unittest.main()
