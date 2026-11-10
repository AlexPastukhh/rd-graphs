# A3-specific recovery after the ORIGINAL first bootstrap failed at import time.
# Owner must independently review this and the corrected source package.
# NEVER delete or adopt nonempty volumes; never change G2/G4/RDG.
$ErrorActionPreference = 'Stop'
$project = 'fortis-a3-synthetic'
$container = 'fortis-a3-synthetic-fortis-1'
$image = 'fortis-a3-synthetic:local'
$compose = Join-Path $PSScriptRoot 'compose-a3.yaml'
$volumes = @('fortis-a3-state','fortis-a3-identity','fortis-a3-grant')

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker CLI unavailable'
}
& docker version --format 'Server={{.Server.Version}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker Engine unavailable' }
$containers = @(& docker container ls -a --format '{{.Names}}')
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect containers' }
if ($containers -contains $container) {
    throw 'A3 container already exists; no automatic replacement'
}
foreach ($port in (19093,19094)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Port $port is listening; no existing listener will be changed"
    }
}
$existing = @(& docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect Docker volumes' }
foreach ($volume in $volumes) {
    if ($existing -notcontains $volume) {
        throw "Expected A3 volume absent: $volume. Do not create or adopt automatically."
    }
}
& docker image inspect $image --format '{{.Id}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Original A3 image missing; manual review required' }

# Read-only verification of EACH previously created A3 volume.
# A nonempty volume is not adopted; no files are removed.
foreach ($volume in $volumes) {
    # Native PowerShell 5.1 strips inner Python -c quotes when calling docker.
    # POSIX ls -A has NO script/quote args, and lists dotfiles too.
    $entries = @(& docker run --rm --network none --read-only --user 10001 `
        --mount "type=volume,source=$volume,target=/check,readonly" `
        $image ls -A /check)
    if ($LASTEXITCODE -ne 0) {
        throw "Cannot read A3 volume $volume; no writes performed"
    }
    if ($entries.Count -ne 0) {
        throw "A3 volume $volume is NOT empty; refusing reuse (no files removed)"
    }
    Write-Host "FORTIS_A3_EMPTY_VOLUME=$volume"
}

# Build corrected A3 image from this *reviewed* isolated source package.
& docker compose --project-name $project -f $compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Corrected A3 compose invalid' }
& docker compose --project-name $project -f $compose build fortis
if ($LASTEXITCODE -ne 0) { throw 'Corrected A3 image build failed' }
# Catch unresolved imports BEFORE private bootstrap creates any state.
& docker run --rm --network none --read-only --user 10001 `
    $image python -B -m fortis_approvals.a3_operator preflight-imports
if ($LASTEXITCODE -ne 0) { throw 'Corrected A3 import test failed; no state written' }

# Exactly one owner-controlled, network-isolated bootstrap. No Docker socket.
& docker run --rm --network none --user 0 `
    --mount 'type=volume,source=fortis-a3-state,target=/state' `
    --mount 'type=volume,source=fortis-a3-identity,target=/run/a3-identity' `
    --mount 'type=volume,source=fortis-a3-grant,target=/run/a3-grant' `
    $image python -B -m fortis_approvals.a3_operator provision
if ($LASTEXITCODE -ne 0) {
    throw 'Corrected A3 bootstrap failed; preserve A3 volumes for diagnosis'
}

& docker compose --project-name $project -f $compose up -d --no-deps --no-build fortis
if ($LASTEXITCODE -ne 0) { throw 'A3 start failed; do not touch G2/G4' }

$healthy = $false
for ($i = 0; $i -lt 90; $i++) {
    $health = (& docker inspect --format '{{.State.Health.Status}}' $container 2>$null)
    if ($LASTEXITCODE -ne 0) { break }
    if ($health -eq 'healthy') { $healthy = $true; break }
    if ($health -eq 'unhealthy') { break }
    Start-Sleep -Seconds 1
}
& docker compose --project-name $project -f $compose ps fortis
if ($LASTEXITCODE -ne 0) { throw 'A3 status unavailable' }
if (-not $healthy) {
    throw 'A3 not healthy; inspect ONLY this A3 container, no restarts'
}
Write-Host 'FORTIS_A3_HEALTHY'
Write-Host 'FORTIS_A3_OWNER_URL=http://localhost:19093/'
Write-Host 'FORTIS_A3_REPO_URL=https://host.docker.internal:19094/'
Write-Host 'Next read-only public cert: docker exec fortis-a3-synthetic-fortis-1 python -m fortis_approvals.a3_operator public'
