# READ-ONLY owner verifier. Never starts R7 or prints credential contents.
[CmdletBinding()]
param(
    [string]$Image = 'fortis-r7-unified-read-ask-candidate:review-20261101-f9791fd1',
    [switch]$RequireCredentials
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
& docker image inspect $Image | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Pinned R7 image missing: $Image" }
$existing = @(& docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0) { throw 'Unable to list Docker volumes' }
foreach ($volume in $volumes) {
    if ($existing -notcontains $volume) {
        throw "Required R7 volume missing: $volume"
    }
}
$checkCredentials = if ($RequireCredentials) { 'True' } else { 'False' }
$verify = @'
from pathlib import Path
import os
import stat
import sys
state = Path('/state/private')
info = state.stat()
if info.st_uid != 10001 or stat.S_IMODE(info.st_mode) != 0o700:
    raise SystemExit('R7_STATE_PRIVATE_PERMISSIONS')
if any(state.iterdir()):
    raise SystemExit('R7_STATE_PRIVATE_NOT_EMPTY')
if sys.argv[1] == 'True':
    checks = (
        ('/run/r7-identity/server.crt', 12, 16384, False),
        ('/run/r7-identity/server.key', 1, 16384, True),
        ('/run/r7-grant/grant', 32, 257, True),
        ('/run/r7-sonar-token/token', 12, 4097, True),
    )
    for raw, minimum, maximum, private in checks:
        item = Path(raw)
        if item.is_symlink() or not item.is_file():
            raise SystemExit('R7_CREDENTIAL_FILE_MISSING:' + raw)
        metadata = item.stat()
        if metadata.st_uid != 10001 or metadata.st_size < minimum or metadata.st_size > maximum:
            raise SystemExit('R7_CREDENTIAL_FILE_METADATA:' + raw)
        if private and stat.S_IMODE(metadata.st_mode) != 0o600:
            raise SystemExit('R7_CREDENTIAL_FILE_MODE:' + raw)
print('R7_CANDIDATE_READONLY_VERIFY_PASS')
'@
$mounts = @(
    '--mount', 'type=volume,source=fortis-r7-state,target=/state,readonly',
    '--mount', 'type=volume,source=fortis-r7-identity,target=/run/r7-identity,readonly',
    '--mount', 'type=volume,source=fortis-r7-grant,target=/run/r7-grant,readonly',
    '--mount', 'type=volume,source=fortis-r7-sonar-token,target=/run/r7-sonar-token,readonly'
)
& docker run --rm --network none --read-only --user 10001:10001 --cap-drop ALL @mounts --entrypoint python $Image -c $verify $checkCredentials
if ($LASTEXITCODE -ne 0) { throw 'R7 read-only verification failed' }
Write-Host 'R7_CANDIDATE_READONLY_VERIFY_COMPLETE. No service started; no credential values displayed.'

