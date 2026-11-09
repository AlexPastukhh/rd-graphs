"""A3 isolated synthetic Fortis: one process/Core, two strictly separate routes.

Owner controls installation and volumes; source does not install itself.
No Sonar adapters, no real tokens, no Docker access, no second executor.
"""
import os
from pathlib import Path
import ssl
from threading import Thread
from wsgiref.simple_server import make_server

from .server import OwnerHTTPServer, OwnerRequestHandler


OWNER_PORT = 19093
REPO_PORT = 19094
OWNER_ORIGIN = "http://localhost:19093"
REPO_HOST = "host.docker.internal:19094"


class TLSRepoServer(OwnerHTTPServer):
    """Handshake in a bounded worker, not on the accept loop."""

    def setup_environ(self):
        super().setup_environ()
        # This field is set by the trusted TLS server, never from HTTP headers.
        self.base_environ["HTTPS"] = "on"  # wsgiref.handlers derives scheme from this
        self.base_environ["wsgi.url_scheme"] = "https"

    def process_request_thread(self, request, client_address):
        secured = None
        try:
            secured = self.tls_context.wrap_socket(
                request, server_side=True, do_handshake_on_connect=False)
            secured.settimeout(5)
            secured.do_handshake()
        except (OSError, ssl.SSLError):
            if secured is not None:
                secured.close()
            else:
                request.close()
            self._slots.release()
            return
        try:
            super().process_request_thread(secured, client_address)
        finally:
            secured.close()


def _private_file(path):
    target = Path(path)
    if target.is_symlink() or not target.is_file():
        raise RuntimeError("A3_PRIVATE_FILE_REQUIRED")
    if target.stat().st_uid != os.geteuid() or target.stat().st_mode & 0o077:
        raise RuntimeError("A3_PRIVATE_FILE_PERMISSIONS")
    return target


def create_servers(*, state, grant_path, cert_path, key_path,
                   bind_host="0.0.0.0"):
    # Keep synthetic assembly lazy so read-only R5 can reuse the same
    # hardened TLS server without importing synthetic execution modules.
    from .repo_synthetic_candidate import build_synthetic_candidate
    grant = _private_file(grant_path).read_text(encoding="ascii").strip()
    _, _, _, owner_app, repo_app = build_synthetic_candidate(
        state=state, owner_origin=OWNER_ORIGIN, ingress_host=REPO_HOST,
        ingress_grant=grant)

    cert = Path(cert_path)
    key = _private_file(key_path)
    if cert.is_symlink() or not cert.is_file():
        raise RuntimeError("A3_PUBLIC_CERT_REQUIRED")
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_context.minimum_version = ssl.TLSVersion.TLSv1_2
    tls_context.options |= ssl.OP_NO_COMPRESSION
    tls_context.load_cert_chain(certfile=str(cert), keyfile=str(key))

    owner_http = make_server(bind_host, OWNER_PORT, owner_app,
                             server_class=OwnerHTTPServer,
                             handler_class=OwnerRequestHandler)
    try:
        repo_https = make_server(bind_host, REPO_PORT, repo_app,
                                 server_class=TLSRepoServer,
                                 handler_class=OwnerRequestHandler)
        repo_https.tls_context = tls_context
    except BaseException:
        owner_http.server_close()
        raise
    return owner_http, repo_https


def main():
    if os.geteuid() != 10001:
        raise RuntimeError("A3_RUNTIME_MUST_BE_NONROOT")
    with_servers = create_servers(
        state="/state/private", grant_path="/run/a3-grant/grant",
        cert_path="/run/a3-identity/server.crt",
        key_path="/run/a3-identity/server.key")
    owner_http, repo_https = with_servers
    try:
        Thread(target=owner_http.serve_forever, daemon=True,
               name="a3-owner-ui").start()
        print("FORTIS_A3_SYNTHETIC_READY owner=http://localhost:19093 "
              "ingress=https://host.docker.internal:19094", flush=True)
        repo_https.serve_forever()
    finally:
        owner_http.shutdown()
        repo_https.shutdown()
        owner_http.server_close()
        repo_https.server_close()


if __name__ == "__main__":
    main()
