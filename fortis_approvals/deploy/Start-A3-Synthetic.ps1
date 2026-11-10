# OWNER-OPERATED only. Review independently before running.
# No down/rebuild of G2/G4/RDG; fresh A3 volumes/ports only.
$ErrorActionPreference = 'Stop'
$compose = Join-Path $PSScriptRoot 'compose-a3.yaml'
$project = 'fortis-a3-synthetic'
$image = 'fortis-a3-synthetic:local'
$names = @('fortis-a3-state','fortis-a3-identity','fortis-a3-grant')
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker CLI unavailable'
}
foreach ($port in (19093,19094)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "A3 port $port already listening; no existing container will be changed"
    }
}
& docker version --format 'Server={{.Server.Version}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker engine unavailable' }
$existingVolumes = @(& docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0) { throw 'Cannot read existing Docker volumes' }
foreach ($name in $names) {
    if ($existingVolumes -contains $name) {
        throw "Volume $name already exists: do not adopt or overwrite; inspect manually"
    }
}
# Build is isolated to a new image tag. The owner must have reviewed the source.
& docker compose --project-name $project -f $compose build fortis
if ($LASTEXITCODE -ne 0) { throw 'A3 image build failed' }
foreach ($name in $names) {
    & docker volume create $name | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Volume create failed: $name" }
}
# Ephemeral bootstrap helper; not another persistent trusted executor.
& docker run --rm --network none --user 0 `
    --mount 'type=volume,source=fortis-a3-state,target=/state' `
    --mount 'type=volume,source=fortis-a3-identity,target=/run/a3-identity' `
    --mount 'type=volume,source=fortis-a3-grant,target=/run/a3-grant' `
    $image python -m fortis_approvals.a3_operator provision
if ($LASTEXITCODE -ne 0) {
    throw 'A3 bootstrap failed; volumes retained for manual diagnosis (no cleanup)'
}
& docker compose --project-name $project -f $compose up -d --no-deps --no-build fortis
if ($LASTEXITCODE -ne 0) { throw 'A3 start failed; G2/G4 untouched' }
$containerName = 'fortis-a3-synthetic-fortis-1'
$healthy = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    $health = (& docker inspect --format '{{.State.Health.Status}}' $containerName 2>$null)
    if ($LASTEXITCODE -eq 0 -and $health -eq 'healthy') {
        $healthy = $true
        break
    }
    if ($health -eq 'unhealthy') { break }
    Start-Sleep -Milliseconds 500
}
& docker compose --project-name $project -f $compose ps fortis
if ($LASTEXITCODE -ne 0) { throw 'A3 status unavailable' }
if (-not $healthy) {
    throw 'A3 not healthy; inspect ONLY the A3 container and its logs'
}
Write-Host 'FORTIS_A3_HEALTHY'
Write-Host 'FORTIS_A3_OWNER_URL=http://localhost:19093/'
Write-Host 'FORTIS_A3_REPO_URL=https://host.docker.internal:19094/'
Write-Host 'Read-only public cert: docker exec fortis-a3-synthetic-fortis-1 python -m fortis_approvals.a3_operator public'
Write-Host 'Owner invitation: docker exec fortis-a3-synthetic-fortis-1 python -m fortis_approvals.a3_operator invite'
Write-Host 'A3 synthetic grant: docker exec fortis-a3-synthetic-fortis-1 python -m fortis_approvals.a3_operator lab-grant'
