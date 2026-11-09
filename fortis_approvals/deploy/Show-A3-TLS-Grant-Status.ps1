# Owner-side read-only diagnostic for the EXISTING A3 SYNTHETIC container.
# Run manually on Windows Fortis_M. No secret values, token bytes or private keys are printed.
# No credential changes, no re-bootstrap, no Docker restart, no scheduler.
$ErrorActionPreference = 'Stop'
$name = 'fortis-a3-synthetic-fortis-1'

$inspectRaw = (& docker inspect $name | Out-String)
if ($LASTEXITCODE -ne 0) {
    throw 'FORTIS_A3_INSPECT_UNAVAILABLE'
}
$found = @(ConvertFrom-Json -InputObject $inspectRaw)
if ($found.Count -ne 1) {
    throw 'FORTIS_A3_INSPECT_UNEXPECTED'
}
$container = $found[0]
Write-Host ('FORTIS_CONTAINER_RUNNING=' + [string][bool]$container.State.Running)
Write-Host ('FORTIS_CONTAINER_HEALTH=' + [string]$container.State.Health.Status)
if (-not $container.State.Running) {
    Write-Host 'FORTIS_NEXT_ACTION=ACTION_REQUIRED: container stopped; check Docker before TLS or grant status'
    return
}

$check = @'
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import os
import socket
import ssl
import stat

from cryptography import x509
from cryptography.hazmat.primitives import hashes

now = datetime.now(timezone.utc)
crt = Path('/run/a3-identity/server.crt')
grant = Path('/run/a3-grant/grant')
if crt.is_symlink() or not crt.is_file():
    raise RuntimeError('CERTIFICATE_FILE_MISSING_OR_UNSAFE')
cert = x509.load_pem_x509_certificate(crt.read_bytes())
expires = cert.not_valid_after_utc
begins = cert.not_valid_before_utc
fingerprint = cert.fingerprint(hashes.SHA256()).hex()
hours = (expires - now).total_seconds() / 3600
if now < begins:
    tls_status = 'NOT_YET_VALID'
elif hours <= 0:
    tls_status = 'EXPIRED'
elif hours <= 72:
    tls_status = 'ACTION_SOON'
else:
    tls_status = 'OK'

print('FORTIS_TLS_NOT_AFTER_UTC=' + expires.isoformat(), flush=True)
print('FORTIS_TLS_REMAINING_HOURS=' + format(hours, '.1f'), flush=True)
print('FORTIS_TLS_CERT_SHA256=' + fingerprint, flush=True)
print('FORTIS_TLS_CERT_STATUS=' + tls_status, flush=True)

# Verify the LIVE HTTPS endpoint, not only the certificate file.
live_ok = False
try:
    ctx = ssl.create_default_context(cafile=str(crt))
    with socket.create_connection(('127.0.0.1', 19094), timeout=4) as raw:
        raw.settimeout(4)
        with ctx.wrap_socket(raw, server_hostname='host.docker.internal') as peer:
            live_ok = (
                hashlib.sha256(peer.getpeercert(binary_form=True)).hexdigest()
                == fingerprint
            )
except (OSError, ssl.SSLError):
    pass
print('FORTIS_TLS_LIVE_MATCH=' + ('YES' if live_ok else 'NO'), flush=True)

# Metadata only: NEVER open, read, hash or print the bearer grant.
grant_ok = False
try:
    info = grant.lstat()
    grant_ok = (
        stat.S_ISREG(info.st_mode)
        and not grant.is_symlink()
        and info.st_uid == 10001
        and stat.S_IMODE(info.st_mode) == 0o600
        and info.st_size == 65
    )
except FileNotFoundError:
    pass
print('FORTIS_MACHINE_AUTH_METHOD=BEARER_GRANT', flush=True)
print('FORTIS_GRANT_FILE='
      + ('PROVISIONED_PRIVATE' if grant_ok else 'MISSING_OR_UNSAFE'), flush=True)
print('FORTIS_GRANT_EXPIRY=NOT_CONFIGURED', flush=True)
print('FORTIS_GRANT_REVOKE_ROTATE=NOT_IMPLEMENTED_IN_A3', flush=True)
print('FORTIS_GRANT_USAGE=NOT_TESTED_BY_READ_ONLY_CHECK', flush=True)

if not live_ok or tls_status in ('EXPIRED', 'NOT_YET_VALID') or not grant_ok:
    print('FORTIS_NEXT_ACTION=ACTION_REQUIRED: TLS or grant needs investigation; do not disable verification', flush=True)
elif tls_status == 'ACTION_SOON':
    print('FORTIS_NEXT_ACTION=ACTION_SOON: owner must arrange TLS replacement before expiry', flush=True)
else:
    print('FORTIS_NEXT_ACTION=TLS_OK_NOW: plan replacement before listed date; machine grant needs no scheduled renewal because no expiry exists', flush=True)
print('FORTIS_PRODUCTION_ADMISSION=NOT_YET_APPROVED', flush=True)
print('FORTIS_A3_TLS_GRANT_READONLY_STATUS_COMPLETE', flush=True)
'@

$check | & docker exec -i --user 10001 $name python -B -
if ($LASTEXITCODE -ne 0) {
    throw 'FORTIS_A3_STATUS_READ_FAILED'
}
