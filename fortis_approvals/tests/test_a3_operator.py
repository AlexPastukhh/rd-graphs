"""Owner-side A3 bootstrap emulation: no Docker, Windows or real secrets."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import ssl
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cryptography import x509
from cryptography.x509.oid import ExtensionOID

from fortis_approvals import a3_operator


class A3BootstrapTests(unittest.TestCase):
    def test_fresh_isolated_material_only_and_no_secret_output(self):
        with TemporaryDirectory(prefix="fortis-a3-provision-") as td:
            paths = [Path(td) / name for name in ("state", "identity", "grant")]
            for path in paths:
                path.mkdir()
            output = io.StringIO()
            with (patch.object(a3_operator, "STATE", paths[0]),
                  patch.object(a3_operator, "IDENTITY", paths[1]),
                  patch.object(a3_operator, "GRANT", paths[2]),
                  patch.object(a3_operator.os, "geteuid", return_value=0),
                  patch.object(a3_operator.os, "chown"),
                  patch.object(Path, "is_mount", return_value=True)):
                with redirect_stdout(output):
                    a3_operator.provision()
                with self.assertRaisesRegex(RuntimeError, "FRESH_VOLUMES"):
                    a3_operator.provision()
            key_path = paths[1] / "server.key"
            cert_path = paths[1] / "server.crt"
            grant_path = paths[2] / "grant"
            self.assertEqual(key_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(grant_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(paths[0].stat().st_mode & 0o777, 0o700)
            self.assertEqual((paths[0] / "private").stat().st_mode & 0o777,
                             0o700)
            self.assertEqual(len(grant_path.read_text().strip()), 64)
            cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
            san = cert.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
            self.assertIn("host.docker.internal", san.get_values_for_type(x509.DNSName))
            self.assertNotIn(grant_path.read_text().strip(), output.getvalue())
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(cert_path), str(key_path))
            self.assertIn("FORTIS_A3_PROVISIONED", output.getvalue())


if __name__ == "__main__":
    unittest.main()
