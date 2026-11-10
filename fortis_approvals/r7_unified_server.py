"""Owner-review SOURCE ONLY R7: Sonar READ + WebAuthn ASK/EXECUTE server.

Not a permitted deployment by itself. Sonar POST requires the exact owner
WebAuthn approval; the machine ingress has no decision or execute route.
No tokens are included; no Docker/host changes. R7 uses its own private state
and must NEVER attach old A3/R5/G2/G4 volumes or auto-provision credentials.
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
from .r5_read_server import _private_ascii, _organizations
from .r7_unified_candidate import build_r7_unified_candidate
from .server import OwnerHTTPServer, OwnerRequestHandler
from .sonar import SonarHTTPTransport


OWNER_PORT = 19103
MACHINE_PORT = 19104
OWNER_ORIGIN = 'http://localhost:19103'
MACHINE_HOST = 'host.docker.internal:19104'


def create_servers(*, state, grant_path, sonar_token_path, cert_path,
                   key_path,region,organizations,project_key,
                   bind_host='0.0.0.0'):
    # P1 requires exactly one owner-pinned project; no organization-wide fallback.
    if (type(project_key) is not str or
            not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', project_key)):
        raise RuntimeError('R7_P1_EXACT_PROJECT_KEY_REQUIRED')
    # Owner-only confidential provisioning: read exact private files; never print.
    grant = _private_ascii(grant_path,max_size=257)
    if len(grant) < 32:
        raise RuntimeError('R7_MACHINE_GRANT_INVALID')
    sonar_token = _private_ascii(sonar_token_path,max_size=4097)
    if len(sonar_token) < 12 or sonar_token == grant:
        raise RuntimeError('R7_SONAR_TOKEN_INVALID')
    transport = SonarHTTPTransport(region=region,bearer_token=sonar_token)
    _,_,portal,ingress = build_r7_unified_candidate(
        state=state,owner_origin=OWNER_ORIGIN,ingress_host=MACHINE_HOST,
        ingress_grant=grant,sonar_transport=transport,
        organizations=organizations,region=region,
        project_keys=(project_key,))
    cert = Path(cert_path)
    if cert.is_symlink() or not cert.is_file():
        raise RuntimeError('R7_PUBLIC_CERT_REQUIRED')
    key = Path(key_path)
    if (key.is_symlink() or not key.is_file() or
            key.stat().st_uid != os.geteuid() or
            stat.S_IMODE(key.stat().st_mode) != 0o600):
        raise RuntimeError('R7_PRIVATE_KEY_REQUIRED')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.options |= ssl.OP_NO_COMPRESSION
    context.load_cert_chain(certfile=str(cert),keyfile=str(key))
    owner = make_server(bind_host,OWNER_PORT,portal,
                        server_class=OwnerHTTPServer,
                        handler_class=OwnerRequestHandler)
    try:
        machine = make_server(bind_host,MACHINE_PORT,ingress,
                              server_class=TLSRepoServer,
                              handler_class=OwnerRequestHandler)
        machine.tls_context = context
    except BaseException:
        owner.server_close()
        raise
    return owner,machine


def health(*,cert_path):
    request = Request(
        'http://127.0.0.1:%d/' % OWNER_PORT,
        headers={'Host':'localhost:%d' % OWNER_PORT})
    with urlopen(request,timeout=2) as response:
        if response.status != 200:
            raise RuntimeError('R7_OWNER_NOT_READY')
    context = ssl.create_default_context(cafile=str(cert_path))
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    with socket.create_connection(('127.0.0.1',MACHINE_PORT),timeout=2) as raw:
        raw.settimeout(2)
        with context.wrap_socket(raw,server_hostname='host.docker.internal') as tls:
            tls.sendall((
                'GET /no-such-machine-route HTTP/1.1\r\n'
                'Host: %s\r\nConnection: close\r\n\r\n'
                % MACHINE_HOST).encode('ascii'))
            if not tls.recv(128).startswith(b'HTTP/1.0 404 '):
                raise RuntimeError('R7_MACHINE_NOT_READY')


def main():
    command=sys.argv[1:]
    if command==['preflight-imports']:
        from .r7_unified_candidate import build_r7_unified_candidate
        from .sonar import SonarHTTPTransport, SonarIssueAdapter
        print('FORTIS_R7_UNIFIED_READ_ASK_EXECUTE_IMPORTS_PASS')
        print('FORTIS_R7_SONAR_POST=OWNER_WEBAUTHN_APPROVAL_REQUIRED')
        return
    if command==['health']:
        health(cert_path='/run/r7-identity/server.crt')
        return
    if command:
        raise SystemExit('Usage: r7_unified_server [preflight-imports|health]')
    if os.geteuid()!=10001:
        raise RuntimeError('R7_RUNTIME_MUST_BE_UNPRIVILEGED')
    region=os.environ.get('FORTIS_SONAR_REGION','eu')
    organizations=_organizations(os.environ.get('FORTIS_SONAR_ORGANIZATIONS',''))
    project_key=os.environ.get('FORTIS_SONAR_PROJECT_KEY','')
    owner,machine=create_servers(
        state='/state/private',
        grant_path='/run/r7-grant/grant',
        sonar_token_path='/run/r7-sonar-token/token',
        cert_path='/run/r7-identity/server.crt',
        key_path='/run/r7-identity/server.key',
        region=region,organizations=organizations,
        project_key=project_key)
    try:
        Thread(target=owner.serve_forever,daemon=True,
               name='r7-owner-portal').start()
        print('FORTIS_R7_READ_ASK_EXECUTE_CANDIDATE_READY '
              'owner=http://localhost:19103 '
              'machine=https://host.docker.internal:19104 '
              'sonar_write=OWNER_WEBAUTHN_APPROVAL_REQUIRED',flush=True)
        machine.serve_forever()
    finally:
        owner.shutdown()
        machine.shutdown()
        owner.server_close()
        machine.server_close()


if __name__=='__main__':
    main()
