# A3 security-boundary snapshot, OWNER REVIEW REQUIRED BEFORE EXECUTION.
# READ-ONLY: docker inspect and docker exec for metadata only.
# No secrets printed, volumes modified, containers restarted, or network access opened.
# Passing THIS snapshot is not independent source provenance, token revocation,
# production CA trust, or authorization to enable real Sonar credentials.
$ErrorActionPreference = 'Stop'
$a3Name = 'fortis-a3-synthetic-fortis-1'
$repoName = 'fortis-repo-test'

function Read-ContainerInspect([string]$name) {
    $raw = (& docker inspect $name | Out-String)
    if ($LASTEXITCODE -ne 0) {
        throw "A3_INSPECT_FAILED=$name"
    }
    $items = @(ConvertFrom-Json -InputObject $raw)
    if ($items.Count -ne 1) {
        throw "A3_INSPECT_COUNT_UNEXPECTED=$name"
    }
    return $items[0]
}

$a3 = Read-ContainerInspect $a3Name
$repo = Read-ContainerInspect $repoName

if (-not $a3.State.Running -or $a3.State.Health.Status -ne 'healthy') {
    throw 'A3_NOT_HEALTHY'
}
if ($a3.Config.Image -ne 'fortis-a3-synthetic:local') {
    throw 'A3_IMAGE_TAG_UNEXPECTED'
}
if ($a3.Config.User -ne '10001:10001') {
    throw 'A3_USER_UNEXPECTED'
}
if ($a3.HostConfig.Privileged -or -not $a3.HostConfig.ReadonlyRootfs) {
    throw 'A3_PRIVILEGED_OR_WRITABLE_ROOTFS'
}
if (@($a3.HostConfig.CapDrop) -notcontains 'ALL') {
    throw 'A3_CAPABILITIES_NOT_DROPPED'
}
if (@($a3.HostConfig.SecurityOpt) -notcontains 'no-new-privileges:true') {
    throw 'A3_NEW_PRIVILEGES_NOT_BLOCKED'
}

$bindings = @($a3.HostConfig.PortBindings.PSObject.Properties)
if ($bindings.Count -ne 2) {
    throw 'A3_UNEXPECTED_PORT_COUNT'
}
foreach ($port in @(19093, 19094)) {
    $key = "${port}/tcp"
    $binding = @($bindings | Where-Object { $_.Name -ceq $key })
    if ($binding.Count -ne 1) {
        throw "A3_UNEXPECTED_PORT=$key"
    }
    $destinations = @($binding[0].Value)
    if ($destinations.Count -ne 1 -or
        $destinations[0].HostIp -ne '127.0.0.1' -or
        $destinations[0].HostPort -ne [string]$port) {
        throw "A3_NOT_LOOPBACK_ONLY=$key"
    }
}
Write-Host 'FORTIS_A3_LOOPBACK_PORTS_PASS'

$expectedMounts = @{
    '/state' = @('fortis-a3-state', $true)
    '/run/a3-identity' = @('fortis-a3-identity', $false)
    '/run/a3-grant' = @('fortis-a3-grant', $false)
}
$mounts = @($a3.Mounts)
if ($mounts.Count -ne 3) {
    throw 'A3_EXTRA_MOUNT_DETECTED'
}
foreach ($mount in $mounts) {
    $rule = $expectedMounts[$mount.Destination]
    if ($null -eq $rule -or $mount.Type -ne 'volume' -or
        $mount.Name -ne $rule[0] -or
        [bool]$mount.RW -ne [bool]$rule[1]) {
        throw 'A3_MOUNT_INCORRECT'
    }
}
Write-Host 'FORTIS_A3_ISOLATED_VOLUMES_PASS'

if ($repo.HostConfig.Privileged) {
    throw 'REPO_PRIVILEGED_UNEXPECTED'
}
foreach ($mount in @($repo.Mounts)) {
    $source = [string]$mount.Source
    $target = [string]$mount.Destination
    if (($source + ' ' + $target) -match '(?i)(docker\.sock|/run/a3-|fortis-a3-(?:state|grant|identity))') {
        throw 'REPO_TRUSTED_MOUNT_EXPOSURE'
    }
}
Write-Host 'FORTIS_REPO_NO_A3_VOLUME_OR_DOCKER_SOCKET_MOUNT_PASS'

$metadataCheck = @'
import os
import stat
from pathlib import Path
from datetime import datetime, timezone
from cryptography import x509
from cryptography.hazmat.primitives import hashes

assert os.geteuid() == 10001, 'A3_EUID_MISMATCH'
files = [
    ('/run/a3-identity/server.key', 0o600),
    ('/run/a3-identity/server.crt', 0o600),
    ('/run/a3-grant/grant', 0o600),
]
for label, expected in files:
    path = Path(label)
    s = path.lstat()
    assert stat.S_ISREG(s.st_mode) and not path.is_symlink(), 'A3_NOT_REGULAR_FILE'
    assert s.st_uid == 10001, 'A3_PRIVATE_FILE_BAD_OWNER'
    assert stat.S_IMODE(s.st_mode) == expected, 'A3_PRIVATE_FILE_BAD_MODE'
print('FORTIS_A3_PRIVATE_FILE_ACL_PASS')

state = Path('/state/private')
s = state.lstat()
assert stat.S_ISDIR(s.st_mode) and s.st_uid == 10001, 'A3_STATE_NOT_PRIVATE'
assert stat.S_IMODE(s.st_mode) == 0o700, 'A3_PRIVATE_STATE_BAD_MODE'
print('FORTIS_A3_PRIVATE_STATE_DIR_PASS')

certificate = x509.load_pem_x509_certificate(
    Path('/run/a3-identity/server.crt').read_bytes())
fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
expected = '63ec4b1bdc5bca321a992f592b70cdc1cb9c8b3df4ad13b5de65246263384838'
assert fingerprint == expected, 'A3_CERT_PIN_CHANGED'
assert certificate.not_valid_after_utc > datetime.now(timezone.utc), 'A3_CERT_EXPIRED'
print('FORTIS_A3_CERT_PIN_PASS')
print('FORTIS_A3_CERT_EXPIRES_UTC=' + certificate.not_valid_after_utc.isoformat())
for label in ('/run/a3-identity', '/run/a3-grant'):
    s = Path(label).stat()
    private = (s.st_uid == 10001 and stat.S_IMODE(s.st_mode) == 0o700)
    print('FORTIS_A3_MOUNT_ROOT_PRIVATE=' + label + ':' + str(private))
'@
$metadataCheck | & docker exec -i --user 10001 $a3Name python -B -
if ($LASTEXITCODE -ne 0) {
    throw 'A3_FILE_ACL_OR_CERT_CHECK_FAILED'
}
Write-Host 'FORTIS_A3_READONLY_RUNTIME_SNAPSHOT_PASS'
Write-Host 'FORTIS_A3_GATE_OPEN: owner must separately review source admission, trust provisioning, grant rotation/revocation, backup/log security'
