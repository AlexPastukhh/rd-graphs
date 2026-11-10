# Run manually by owner after independent source review. No RDG/Sonar access.
# This script DOES NOT start or stop unrelated Docker services.
$ErrorActionPreference = 'Stop'
$compose = Join-Path $PSScriptRoot 'compose.yaml'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI not found' }
& docker compose --project-name fortis-approvals-g2 -f $compose build
if ($LASTEXITCODE -ne 0) { throw 'Docker build failed' }
# Initial volume permissions: do this outside the cap_drop: ALL runtime.
# A regular docker run has CAP_CHOWN; compose run inherits cap_drop: ALL and
# cannot chown even as root. Only the G2 named volume is mounted here.
& docker volume create 'fortis-approvals-g2_g2_state' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Volume create failed' }
& docker run --rm --network none --user 0 --mount 'type=volume,source=fortis-approvals-g2_g2_state,target=/state' fortis-approvals-g2:local sh -c 'chown 10001:10001 /state && chmod 0700 /state'
if ($LASTEXITCODE -ne 0) { throw 'Volume initialization failed' }
& docker compose --project-name fortis-approvals-g2 -f $compose up -d --no-deps owner
if ($LASTEXITCODE -ne 0) { throw 'Docker start failed' }
$ready = $false
for ($attempt = 0; $attempt -lt 25; $attempt++) {
    try {
        $check = Invoke-WebRequest -Uri 'http://localhost:18990/' -UseBasicParsing -TimeoutSec 2
        if ($check.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 400 }
}
if (-not $ready) {
    & docker compose --project-name fortis-approvals-g2 -f $compose ps
    throw 'G2 owner UI did not become reachable. No unrelated services were changed.'
}
Write-Host 'G2 owner UI: http://localhost:18990/'
Write-Host 'Register key: run .\fortis_approvals\deploy\Invite-G2.ps1'
Write-Host 'Seed synthetic request: run .\fortis_approvals\deploy\Seed-G2.ps1'
Write-Host 'Docker Desktop must be configured to start on login for service restart.'
Start-Process 'http://localhost:18990/'
