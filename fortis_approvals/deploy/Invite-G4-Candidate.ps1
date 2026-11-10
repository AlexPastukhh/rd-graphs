# Run in trusted owner PowerShell only. G4 has separate WebAuthn credentials.
$ErrorActionPreference='Stop'
$compose=Join-Path $PSScriptRoot 'compose-g4.yaml'
& docker compose --project-name fortis-approvals-g4 -f $compose run --rm --no-deps -T owner python -m fortis_approvals.g4_operator invite
if ($LASTEXITCODE -ne 0) { throw 'G4 owner invitation failed' }
