"""R5 source candidate server: one process, separate owner / machine ports.

No bootstrap/installation side effects. Requires NEW independent R5 volumes,
manually provisioned TLS identity, machine grant and private Sonar token.
Never import existing G2/G4/A3 secrets or retry A3 bootstrap.
"""
import os
from pathlib import Path
import re
import socket
import ssl
import stat
import sys
from threading import Thread
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server

from .a3_server import TLSRepoServer
from .r5_read_candidate import build_r5_read_candidate
from .server import OwnerHTTPServer, OwnerRequestHandler
from .sonar import SonarHTTPTransport


OWNER_PORT = 19103
REPO_PORT = 19104
OWNER_ORIGIN = 'http://localhost:19103'
REPO_HOST = 'host.docker.internal:19104'


def _private_ascii(path, *, max_size):
    item = Path(path)
    if item.is_symlink() or not item.is_file():
        raise RuntimeError('R5_PRIVATE_FILE_REQUIRED')
    metadata = item.stat()
    if (not stat.S_ISREG(metadata.st_mode) or
            metadata.st_uid != os.geteuid() or
            stat.S_IMODE(metadata.st_mode) != 0o600 or
            not 12 <= metadata.st_size <= max_size):
        raise RuntimeError('R5_PRIVATE_FILE_PERMISSIONS_OR_SIZE')
    data = item.read_bytes()
    if len(data) != metadata.st_size:
        raise RuntimeError('R5_PRIVATE_FILE_CHANGED')
    try:
        value = data.decode('ascii')
    except UnicodeError:
        raise RuntimeError('R5_PRIVATE_FILE_INVALID') from None
    if value.endswith('\n'):
        value = value[:-1]
    if (not value or any(not (33 <= ord(ch) <= 126) for ch in value) or
            '\r' in value or '\n' in value):
        raise RuntimeError('R5_PRIVATE_FILE_INVALID')
    return value


def _organizations(value):
    if (type(value) is not str or
            not value or len(value) > 2600 or
            any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', org)
                for org in value.split(',')) or
            len(value.split(',')) > 20 or
            len(set(value.split(','))) != len(value.split(','))):
        raise RuntimeError('R5_ORGANIZATIONS_INVALID')
    return tuple(value.split(','))


def create_servers(*, state, grant_path, sonar_token_path, cert_path, key_path,
                   region, organizations, bind_host='0.0.0.0'):
    # Only a trusted owner process reads the private Sonar API token.
    machine_grant = _private_ascii(grant_path, max_size=257)
    if len(machine_grant) < 32:
        raise RuntimeError('R5_MACHINE_GRANT_INVALID')
    sonar_token = _private_ascii(sonar_token_path, max_size=4097)
    if len(sonar_token) < 12 or sonar_token == machine_grant:
        raise RuntimeError('R5_SONAR_TOKEN_INVALID')
    transport = SonarHTTPTransport(region=region, bearer_token=sonar_token)
    _, _, owner_app, repo_app = build_r5_read_candidate(
        state=state, owner_origin=OWNER_ORIGIN,
        ingress_host=REPO_HOST, ingress_grant=machine_grant,
        sonar_transport=transport, organizations=organizations, region=region)
    certificate = Path(cert_path)
    if certificate.is_symlink() or not certificate.is_file():
        raise RuntimeError('R5_PUBLIC_CERT_REQUIRED')
    identity_key = Path(key_path)
    if (identity_key.is_symlink() or not identity_key.is_file() or
            identity_key.stat().st_uid != os.geteuid() or
            stat.S_IMODE(identity_key.stat().st_mode) != 0o600):
        raise RuntimeError('R5_PRIVATE_KEY_REQUIRED')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.options |= ssl.OP_NO_COMPRESSION
    context.load_cert_chain(certfile=str(certificate), keyfile=str(identity_key))
    owner = make_server(bind_host, OWNER_PORT, owner_app,
                        server_class=OwnerHTTPServer,
                        handler_class=OwnerRequestHandler)
    try:
        repo = make_server(bind_host, REPO_PORT, repo_app,
                           server_class=TLSRepoServer,
                           handler_class=OwnerRequestHandler)
        repo.tls_context = context
    except BaseException:
        owner.server_close()
        raise
    return owner, repo


def health(*, cert_path):
    request = Request(
        'http://127.0.0.1:%d/' % OWNER_PORT,
        headers={'Host':'localhost:%d' % OWNER_PORT})
    with urlopen(request, timeout=2) as response:
        if response.status != 200:
            raise RuntimeError('R5_OWNER_NOT_READY')
    context = ssl.create_default_context(cafile=str(cert_path))
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    with socket.create_connection(('127.0.0.1', REPO_PORT), timeout=2) as raw:
        raw.settimeout(2)
        with context.wrap_socket(raw, server_hostname='host.docker.internal') as tls:
            tls.sendall((
                'GET /no-such-machine-route HTTP/1.1\r\n'
                'Host: %s\r\nConnection: close\r\n\r\n'
            % REPO_HOST).encode('ascii'))
            if not tls.recv(128).startswith(b'HTTP/1.0 404 '):
                raise RuntimeError('R5_MACHINE_NOT_READY')


def main():
    command = sys.argv[1:]
    if command == ['preflight-imports']:
        # Never load secret files, access network or initialize state in check.
        from .r5_read_candidate import build_r5_read_candidate
        from .sonar_read import SonarReadOnlyTransport
        print('FORTIS_R5_SONAR_READ_IMPORTS_PASS')
        return
    if command == ['health']:
        health(cert_path='/run/r5-identity/server.crt')
        return
    if command:
        raise SystemExit('Usage: r5_read_server [preflight-imports|health]')
    if os.geteuid() != 10001:
        raise RuntimeError('R5_RUNTIME_MUST_BE_UNPRIVILEGED')
    region = os.environ.get('FORTIS_SONAR_REGION', 'eu')
    organizations = _organizations(os.environ.get('FORTIS_SONAR_ORGANIZATIONS',''))
    owner, repo = create_servers(
        state='/state/private',
        grant_path='/run/r5-grant/grant',
        sonar_token_path='/run/r5-sonar-token/token',
        cert_path='/run/r5-identity/server.crt',
        key_path='/run/r5-identity/server.key',
        region=region, organizations=organizations)
    try:
        Thread(target=owner.serve_forever, daemon=True,
               name='r5-owner-portal').start()
        print('FORTIS_R5_READ_CANDIDATE_READY '
              'owner=http://localhost:19103 '
              'machine=https://host.docker.internal:19104',flush=True)
        repo.serve_forever()
    finally:
        owner.shutdown()
        repo.shutdown()
        owner.server_close()
        repo.server_close()


if __name__ == '__main__':
    main()
