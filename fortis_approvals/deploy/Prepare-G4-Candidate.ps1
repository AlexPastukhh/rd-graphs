# Stage a separate reviewed G4 owner-candidate. Never touches G2 project/volumes.
$ErrorActionPreference='Stop'
$compose=Join-Path $PSScriptRoot 'compose-g4.yaml'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI missing' }
& docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose v2 required' }
# Refuse silently adopting an existing independently created Docker volume.
# `docker volume inspect` emits an error when a volume is absent (expected),
# and Windows PowerShell with ErrorActionPreference=Stop converts that into
# a terminating NativeCommandError before LASTEXITCODE can be inspected.
$volumeNames = @(& docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0) { throw 'Unable to list Docker volumes; aborting.' }
foreach ($volume in @('fortis-approvals-g4_state','fortis-approvals-g4_token')) {
    if ($volumeNames -contains $volume) {
        throw "Volume $volume already exists. Review before reuse; no changes made."
    }
}
& docker build --pull=false -t fortis-approvals-g4-candidate:local -f (Join-Path $root 'fortis_approvals/deploy/Dockerfile-G4-Candidate') $root
if ($LASTEXITCODE -ne 0) { throw 'G4 build failed; no G2 changes' }
foreach ($volume in @('fortis-approvals-g4_state','fortis-approvals-g4_token')) {
    & docker volume create $volume | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed creating new G4 volume $volume" }
}
# Each volume root can stay root:755; initialize and check a private
# directory within that volume, never the mount root.
$image='fortis-approvals-g4-candidate:local'
foreach ($volume in @('fortis-approvals-g4_state','fortis-approvals-g4_token')) {
    $kind = if ($volume -ceq 'fortis-approvals-g4_state') { 'state' } else { 'token' }
    $target = if ($kind -ceq 'state') { '/state' } else { '/run/g4-token' }
    $mount = "type=volume,source=$volume,target=$target"
    & docker run --rm --network none --user 0 --mount $mount --entrypoint python $image '-m' 'fortis_approvals.g4_volume_repair' 'initialize' $kind
    if ($LASTEXITCODE -ne 0) { throw "G4 private subdirectory initialization failed: $volume" }
    & docker run --rm --network none --read-only --user '10001:10001' --cap-drop ALL --mount $mount --entrypoint python $image '-m' 'fortis_approvals.g4_volume_repair' 'verify' $kind
    if ($LASTEXITCODE -ne 0) { throw "G4 subdirectory write check failed: $volume" }
}
Write-Host 'G4_CANDIDATE_PREPARED. Private subdirectories verified; no token stored; no service started.'
Write-Host 'Next: owner reviews separate volume token storage, then runs Provision-G4-Token.ps1.'
