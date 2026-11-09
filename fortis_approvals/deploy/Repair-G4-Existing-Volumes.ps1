# ONLY the already-created G4 volumes. No Sonar credential and no G2 changes.
# Upgrade G4 image code, then initialize NEW /private subdirs inside each volume.
# Never delete a file, reformat a volume, or touch G2 Compose/project.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI missing' }
$volumes=@('fortis-approvals-g4_state','fortis-approvals-g4_token')
$names=@(& docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0) { throw 'Docker volume list unavailable' }
foreach ($name in $volumes) {
    if ($names -notcontains $name) { throw "Expected existing G4 volume missing: $name" }
}
$running=@(& docker ps --filter 'label=com.docker.compose.project=fortis-approvals-g4' --format '{{.ID}}')
if ($LASTEXITCODE -ne 0) { throw 'Cannot check running G4 containers' }
if ($running.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace(($running -join ''))) {
    throw 'G4 service is running. Refusing to change its image or storage.'
}
$image='fortis-approvals-g4-candidate:local'
& docker build --pull=false -t $image -f (Join-Path $root 'fortis_approvals/deploy/Dockerfile-G4-Candidate') $root
if ($LASTEXITCODE -ne 0) { throw 'G4-only image rebuild failed' }
foreach ($name in $volumes) {
    $kind=if ($name -ceq 'fortis-approvals-g4_state') { 'state' } else { 'token' }
    $target=if ($kind -ceq 'state') { '/state' } else { '/run/g4-token' }
    $mount="type=volume,source=$name,target=$target"
    & docker run --rm --network none --user 0 --mount $mount --entrypoint python $image '-m' 'fortis_approvals.g4_volume_repair' 'initialize' $kind
    if ($LASTEXITCODE -ne 0) { throw "Private directory creation denied in $name" }
    & docker run --rm --network none --read-only --user '10001:10001' --cap-drop ALL --security-opt 'no-new-privileges:true' --mount $mount --entrypoint python $image '-m' 'fortis_approvals.g4_volume_repair' 'verify' $kind
    if ($LASTEXITCODE -ne 0) { throw "Private subdirectory uid 10001 write verification failed in $name" }
}
Write-Host 'G4_PRIVATE_DIRECTORIES_READY. No Sonar token read or written. G2 untouched.'
Write-Host 'Next: reviewed Provision-G4-Token.ps1 with STORE consent and hidden token prompt.'
