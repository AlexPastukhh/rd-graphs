"""A3 synthetic HTTPS wire acceptance in Linux only. No Windows or Sonar."""
import datetime
import hashlib
import http.client
import json
from pathlib import Path
import socket
import ssl
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from fortis_approvals import a3_operator, a3_server


class A3ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="fortis-a3-tls-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        state = root / "state"
        state.mkdir(mode=0o700)
        grant = root / "grant"
        grant.write_text("temporary-synthetic-test-only-grant-00001")
        grant.chmod(0o600)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(
            NameOID.COMMON_NAME, "host.docker.internal")])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName(
                [x509.DNSName("host.docker.internal")]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None),
                           critical=True)
            .add_extension(x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
        cert_path = root / "cert.pem"
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path = root / "key.pem"
        key_path.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        key_path.chmod(0o600)
        self.grant = grant.read_text()
        self.cert_path = cert_path
        with (patch.object(a3_server, "OWNER_PORT", 0),
              patch.object(a3_server, "REPO_PORT", 0)):
            self.owner, self.repo = a3_server.create_servers(
                state=state, grant_path=grant, cert_path=cert_path,
                key_path=key_path, bind_host="127.0.0.1")
        self.addCleanup(self.owner.server_close)
        self.addCleanup(self.repo.server_close)
        self.threads = []
        for server in (self.owner, self.repo):
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)
        self.addCleanup(self.shutdown)
        self.repo_port = self.repo.server_port
        self.owner_port = self.owner.server_port

    def shutdown(self):
        for server in (self.repo, self.owner):
            server.shutdown()
        for thread in self.threads:
            thread.join(timeout=3)

    def request(self, path, *, method="GET", payload=None, grant=None,
                cert=True, hostname="host.docker.internal"):
        ctx = (ssl.create_default_context(cafile=str(self.cert_path)) if cert
               else ssl.create_default_context())
        headers = {"Host": "host.docker.internal:19094"}
        if grant is not None:
            headers["Authorization"] = "Bearer " + grant
        if payload is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(payload).encode()
        with socket.create_connection(("127.0.0.1", self.repo_port), timeout=3) as sock:
            sock.settimeout(3)
            with ctx.wrap_socket(sock, server_hostname=hostname) as tls:
                conn = http.client.HTTPConnection("127.0.0.1")
                conn.sock = tls
                conn.request(method, path, body=payload, headers=headers)
                response = conn.getresponse()
                return response.status, json.loads(response.read())

    @staticmethod
    def intent(operation, target):
        return {"requestId": str(uuid.uuid4()), "service": "synthetic",
                "operation": operation, "target": target,
                "params": {"value": "changed", "expectedVersion": 0},
                "reason": "A3 TLS synthetic acceptance"}

    def test_tls_identity_negative_and_separated_routes(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.request("/not-route", cert=False)
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.request("/not-route", hostname="wrong-host.invalid")
        a3_operator.health(owner_port=self.owner_port, repo_port=self.repo_port,
                           cert_path=self.cert_path)
        self.assertEqual(self.request("/v1/owner/pending")[0], 404)
        self.assertEqual(self.request("/v1/execute")[0], 404)
        # A synthetic-only image must fail closed on a Sonar intent; no
        # Sonar adapter is packaged, and no import should be required.
        sonar = {"requestId": str(uuid.uuid4()), "service": "sonarcloud",
                 "operation": "accept_issue", "target": "SONAR-TEST-1",
                 "params": {"projectKey": "test_project"}, "reason": "denied"}
        self.assertEqual(self.request("/v1/actions", method="POST",
                                      payload=sonar, grant=self.grant)[0], 403)
        self.assertEqual(self.request("/v1/actions", method="POST",
                                      payload=self.intent("set_free", "SYN-ALLOW"))[0],
                         401)
        conn = http.client.HTTPConnection("127.0.0.1", self.owner_port,
                                          timeout=3)
        try:
            conn.request("GET", "/", headers={"Host": "localhost:19093"})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn(b"Fortis Approvals", response.read())
        finally:
            conn.close()

    def test_synthetic_allow_ask_deny_wire(self):
        allow = self.intent("set_free", "SYN-ALLOW")
        status, result = self.request("/v1/actions", method="POST",
                                      payload=allow, grant=self.grant)
        self.assertEqual((status, result["state"]), (200, "EXECUTED"))
        self.assertEqual(self.request("/v1/requests/" + allow["requestId"],
                                      grant=self.grant)[1]["state"], "EXECUTED")
        ask = self.intent("set_ask", "SYN-ASK")
        self.assertEqual(self.request("/v1/actions", method="POST",
                                      payload=ask, grant=self.grant)[1]["state"],
                         "PENDING")
        self.assertEqual(self.request("/v1/actions", method="POST",
                                      payload=self.intent("set_deny","SYN-DENY"),
                                      grant=self.grant)[0], 403)


if __name__ == "__main__":
    unittest.main()
