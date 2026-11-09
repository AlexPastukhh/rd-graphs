# Owner-only key invitation: copy the one-time token to the browser form.
$ErrorActionPreference = 'Stop'
$compose = Join-Path $PSScriptRoot 'compose.yaml'
& docker compose --project-name fortis-approvals-g2 -f $compose run --rm --no-deps owner python -m fortis_approvals.operator invite
if ($LASTEXITCODE -ne 0) { throw 'Cannot issue invitation' }
