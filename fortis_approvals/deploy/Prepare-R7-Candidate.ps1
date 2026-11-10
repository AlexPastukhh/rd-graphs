# SOURCE-ONLY owner preflight. Creates fresh R7 volumes and the private state directory.
# Never starts R7, provisions tokens, touches A3/G2/G4/R5, or runs compose up.
[CmdletBinding()]
param(
    [string]$Image = 'fortis-r7-unified-read-ask-candidate:review-20261101-f9791fd1'
)
$ErrorActionPreference = 'Stop'
$volumes = @(
    'fortis-r7-state',
    'fortis-r7-identity',
    'fortis-r7-grant',
    'fortis-r7-sonar-token'
)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker CLI missing'
}
& docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose v2 required' }
& docker image inspect $Image | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Pinned R7 image missing: $Image" }
$existing = @(& docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0) { throw 'Unable to list Docker volumes' }
foreach ($volume in $volumes) {
    if ($existing -contains $volume) {
        throw "R7 volume already exists; refusing reuse: $volume"
    }
}
foreach ($volume in $volumes) {
    & docker volume create $volume | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed creating volume: $volume" }
}
$bootstrap = @'
from pathlib import Path
import os
paths = (
    '/state/private',
)
for raw in paths:
    path = Path(raw)
    if path.exists():
        raise SystemExit('R7_PRIVATE_PATH_ALREADY_EXISTS:' + raw)
    path.mkdir(mode=0o700)
    os.chown(path, 10001, 10001)
    os.chmod(path, 0o700)
print('R7_STATE_PRIVATE_SUBDIRECTORY_INITIALIZED')
'@
$mounts = @(
    '--mount', 'type=volume,source=fortis-r7-state,target=/state',
    '--mount', 'type=volume,source=fortis-r7-identity,target=/run/r7-identity',
    '--mount', 'type=volume,source=fortis-r7-grant,target=/run/r7-grant',
    '--mount', 'type=volume,source=fortis-r7-sonar-token,target=/run/r7-sonar-token'
)
& docker run --rm --network none --user 0 @mounts --entrypoint python $Image -c $bootstrap
if ($LASTEXITCODE -ne 0) { throw 'R7 private subdirectory initialization failed' }
$verify = @'
from pathlib import Path
import os
for raw in ('/state/private',):
    path = Path(raw)
    info = path.stat()
    if info.st_uid != 10001 or (info.st_mode & 0o777) != 0o700:
        raise SystemExit('R7_PRIVATE_SUBDIRECTORY_PERMISSIONS:' + raw)
marker = Path('/state/private/.preflight-marker')
marker.write_text('ok')
marker.unlink()
print('R7_STATE_PRIVATE_SUBDIRECTORY_VERIFY_PASS')
'@
$verifyMounts = @(
    '--mount', 'type=volume,source=fortis-r7-state,target=/state',
    '--mount', 'type=volume,source=fortis-r7-identity,target=/run/r7-identity,readonly',
    '--mount', 'type=volume,source=fortis-r7-grant,target=/run/r7-grant,readonly',
    '--mount', 'type=volume,source=fortis-r7-sonar-token,target=/run/r7-sonar-token,readonly'
)
& docker run --rm --network none --read-only --user 10001:10001 --cap-drop ALL @verifyMounts --entrypoint python $Image -c $verify
if ($LASTEXITCODE -ne 0) { throw 'R7 private subdirectory verification failed' }
Write-Host 'R7_CANDIDATE_VOLUMES_PREPARED. State private directory ready; no service started; no credentials stored.'
Write-Host 'Next owner gates: image/base admission, TLS identity, machine grant, Sonar READ token, Guard Preview, then separate R7 start.'

