# Inspect EXISTING G4 rejected ASK via readonly local DB and GET-only Sonar.
# NO G4/G2 restart; no local state write; no remote Sonar POST.
param([Parameter(Mandatory=$true)][string]$ProjectKey,
      [Parameter(Mandatory=$true)][string]$IssueKey,
      [Parameter(Mandatory=$true)][string]$RequestId)
$ErrorActionPreference='Stop'
if ($ProjectKey -cnotmatch '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$' -or
    $IssueKey -cnotmatch '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$') {
    throw 'G4_READBACK_INVALID_TARGET'
}
if ($RequestId -cnotmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') {
    throw 'G4_READBACK_EXACT_REQUEST_ID_REQUIRED'
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI missing' }
$image='fortis-approvals-g4-candidate:local'
$names=@(& docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0) { throw 'G4_VOLUME_DISCOVERY_FAILED' }
if ($names -notcontains 'fortis-approvals-g4_state' -or
    $names -notcontains 'fortis-approvals-g4_token') {
    throw 'G4_REQUIRED_VOLUMES_MISSING'
}
$images=@(& docker image ls --format '{{.Repository}}:{{.Tag}}')
if ($LASTEXITCODE -ne 0 -or $images -notcontains $image) {
    throw 'G4_REVIEWED_IMAGE_NOT_FOUND'
}
$source=Join-Path $PSScriptRoot 'G4-Readback-Probe.py'
if (-not (Test-Path $source -PathType Leaf)) { throw 'G4_READBACK_SOURCE_MISSING' }
# Source is piped through stdin, so PowerShell cannot discard Python quotes.
# Both volumes are mounted read-only. Bridge networking permits HTTPS GET.
Get-Content -Raw -Encoding UTF8 $source | & docker run --rm -i `
    --network bridge --read-only --user '10001:10001' `
    --cap-drop ALL --security-opt 'no-new-privileges:true' `
    --pids-limit 32 --memory 128m `
    --env PYTHONDONTWRITEBYTECODE=1 `
    --mount 'type=volume,source=fortis-approvals-g4_state,target=/state,readonly' `
    --mount 'type=volume,source=fortis-approvals-g4_token,target=/run/g4-token,readonly' `
    --entrypoint python $image - $ProjectKey $IssueKey $RequestId
if ($LASTEXITCODE -ne 0) {
    throw 'G4_READBACK_NOT_CONFIRMED: no Sonar POST attempted'
}
