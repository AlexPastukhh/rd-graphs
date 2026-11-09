# Starts ONLY isolated compose project fortis-approvals-g4. G2 untouched.
$ErrorActionPreference='Stop'
$compose=Join-Path $PSScriptRoot 'compose-g4.yaml'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI missing' }
& docker compose --project-name fortis-approvals-g4 -f $compose up -d --no-deps --no-build owner
if ($LASTEXITCODE -ne 0) { throw 'G4 candidate start failed; G2 untouched' }
$ready=$false
for ($try=0;$try -lt 25;$try++) {
    try {
        $status=Invoke-WebRequest 'http://localhost:18991/' -UseBasicParsing -TimeoutSec 2
        if ($status.StatusCode -eq 200) { $ready=$true; break }
    } catch { Start-Sleep -Milliseconds 400 }
}
if (-not $ready) {
    & docker compose --project-name fortis-approvals-g4 -f $compose ps
    throw 'G4 candidate not healthy; inspect G4 logs only. Do not modify G2.'
}
Write-Host 'G4_CANDIDATE_READONLY_READY: http://localhost:18991/'
Write-Host 'Separate G4 invitation: Invite-G4-Candidate.ps1'
Start-Process 'http://localhost:18991/'
