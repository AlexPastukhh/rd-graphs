# Owner-only synthetic test request; not connected to any external service.
$ErrorActionPreference = 'Stop'
$compose = Join-Path $PSScriptRoot 'compose.yaml'
& docker compose --project-name fortis-approvals-g2 -f $compose run --rm --no-deps owner python -m fortis_approvals.operator seed
if ($LASTEXITCODE -ne 0) { throw 'Cannot seed synthetic request' }
