# Preserves the separate G4 owner key, token and request history in volumes.
$ErrorActionPreference='Stop'
$compose=Join-Path $PSScriptRoot 'compose-g4.yaml'
& docker compose --project-name fortis-approvals-g4 -f $compose stop owner
if ($LASTEXITCODE -ne 0) { throw 'G4 stop failed' }
Write-Host 'G4_CANDIDATE_STOPPED. G2 untouched. No volume deleted.'
