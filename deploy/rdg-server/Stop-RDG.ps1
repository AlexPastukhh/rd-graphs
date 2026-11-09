[CmdletBinding()]
param([ValidateSet('Local', 'HTTPS')][string]$Mode = 'Local')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$override = if ($Mode -eq 'HTTPS') { 'compose.https.yaml' } else { 'compose.local.yaml' }
& docker compose --project-name rdg-personal -f compose.yaml -f $override stop
if ($LASTEXITCODE -ne 0) { throw 'RDG stop failed.' }
# Persistent volumes are deliberately retained.
