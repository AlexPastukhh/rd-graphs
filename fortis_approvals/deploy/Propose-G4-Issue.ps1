# Prepare a real Sonar Issue ASK in the G4-only portal. CANNOT WRITE SONAR.
param([Parameter(Mandatory=$true)][string]$ProjectKey,
      [Parameter(Mandatory=$true)][string]$IssueKey)
$ErrorActionPreference='Stop'
if ($ProjectKey -cnotmatch '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$' -or
    $IssueKey -cnotmatch '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$') {
    throw 'Invalid project/Issue key. No call attempted.'
}
$reason=Read-Host 'Reason shown to owner in G4 ASK preview (not a secret)'
if ([string]::IsNullOrWhiteSpace($reason) -or $reason.Length -gt 1500) {
    throw 'Reason must contain 1-1500 characters.'
}
$compose=Join-Path $PSScriptRoot 'compose-g4.yaml'
$reason | & docker compose --project-name fortis-approvals-g4 -f $compose run --rm --no-deps -T owner python -m fortis_approvals.g4_operator propose --project $ProjectKey --issue $IssueKey
if ($LASTEXITCODE -ne 0) { throw 'G4 READ/ASK proposal failed. No Sonar mutations.' }
Write-Host 'Refresh http://localhost:18991/ to review G4 Pending. Approve is disabled.'
