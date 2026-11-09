"""Owner-only bootstrap for a disposable A3 synthetic candidate.

Runs only under an owner-operated Docker CLI. Never creates Sonar tokens.
No network access or Docker socket required inside the helper.
"""
import base64
import socket
import ssl
from urllib.request import Request, urlopen
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import secrets
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .repo_synthetic_candidate import build_synthetic_candidate


STATE = Path("/state")
IDENTITY = Path("/run/a3-identity")
GRANT = Path("/run/a3-grant")
UID = 10001
_MARKER = ".fortis-a3-identity-v1"


def _write(path, data, mode=0o600):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                 mode)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        try:
            Path(path).unlink()
        except FileNotFoundError:
            pass
        raise
    os.chown(path, UID, UID)
    os.chmod(path, mode)


def provision():
    if os.geteuid() != 0:
        raise RuntimeError("A3_OWNER_BOOTSTRAP_REQUIRES_ROOT")
    for root in (STATE, IDENTITY, GRANT):
        if not root.is_mount() or root.is_symlink():
            raise RuntimeError("A3_EXPECTS_OWNER_MOUNTED_VOLUMES")
    if any(IDENTITY.iterdir()) or any(GRANT.iterdir()) or any(STATE.iterdir()):
        raise RuntimeError("A3_FRESH_VOLUMES_REQUIRED_NO_ADOPTION")
    for root in (STATE, IDENTITY, GRANT):
        os.chown(root, UID, UID)
        os.chmod(root, 0o700)
    private_state = STATE / "private"
    private_state.mkdir(mode=0o700)
    os.chown(private_state, UID, UID)

    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(
        NameOID.COMMON_NAME, "host.docker.internal")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=7))
        .add_extension(x509.SubjectAlternativeName(
            [x509.DNSName("host.docker.internal")]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None),
                       critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False,
            key_encipherment=True, data_encipherment=False,
            key_agreement=False, key_cert_sign=False, crl_sign=False,
            encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage(
            [ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    _write(IDENTITY / "server.key", key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    _write(IDENTITY / "server.crt", cert.public_bytes(
        serialization.Encoding.PEM), mode=0o600)
    _write(IDENTITY / _MARKER, b"fortis-a3-private-identity-v1\n")
    _write(GRANT / "grant", (secrets.token_urlsafe(48) + "\n").encode())
    print("FORTIS_A3_PROVISIONED isolated_state synthetic_only")
    print("FORTIS_A3_CERT_SHA256=" + cert.fingerprint(hashes.SHA256()).hex())


def _candidate():
    credential = (GRANT / "grant").read_text(encoding="ascii").strip()
    return build_synthetic_candidate(
        state=STATE / "private",
        owner_origin="http://localhost:19093",
        ingress_host="host.docker.internal:19094",
        ingress_grant=credential)


def health(*, owner_port=19093, repo_port=19094, cert_path=None):
    request = Request("http://127.0.0.1:%d/" % owner_port,
                      headers={"Host": "localhost:19093"})
    with urlopen(request, timeout=2) as response:
        if response.status != 200:
            raise RuntimeError("A3_OWNER_NOT_READY")
    ctx = ssl.create_default_context(
        cafile=str(cert_path or IDENTITY / "server.crt"))
    with socket.create_connection(("127.0.0.1", repo_port), timeout=2) as raw:
        raw.settimeout(2)
        with ctx.wrap_socket(raw, server_hostname="host.docker.internal") as tls:
            tls.sendall(b"GET /health-test-non-route HTTP/1.1\r\n"
                        b"Host: host.docker.internal:19094\r\n"
                        b"Connection: close\r\n\r\n")
            if not tls.recv(128).startswith(b"HTTP/1.0 404 "):
                raise RuntimeError("A3_MACHINE_NOT_READY")


def main():
    command = sys.argv[1:] if len(sys.argv) > 1 else []
    if command == ["preflight-imports"]:
        # No mounts, secrets, state or ports required. Check the exact minimal
        # image's import graph before owner-side volume provisioning.
        from .a3_server import create_servers
        from .repo_action_contract import validate_intent
        print("FORTIS_A3_IMPORTS_PASS")
    elif command == ["provision"]:
        provision()
    elif command == ["health"]:
        health()
    elif command == ["public"]:
        certificate = x509.load_pem_x509_certificate(
            (IDENTITY / "server.crt").read_bytes())
        public = certificate.public_bytes(serialization.Encoding.DER)
        print("FORTIS_A3_CERT_SHA256=" +
              certificate.fingerprint(hashes.SHA256()).hex())
        print("FORTIS_A3_PUBLIC_CERT_BASE64=" +
              base64.b64encode(public).decode("ascii"))
    elif command == ["invite"]:
        owner = _candidate()[1]
        print("FORTIS_A3_OWNER_INVITATION=" + owner.issue_invitation())
    elif command == ["lab-grant"]:
        # Scoped to A3 synthetic only; DO NOT use as a real service token.
        _candidate()
        print("FORTIS_A3_SYNTHETIC_INGRESS_GRANT=" +
              (GRANT / "grant").read_text(encoding="ascii").strip())
    else:
        raise SystemExit("Usage: a3_operator {provision|public|invite|lab-grant}")


if __name__ == "__main__":
    main()
