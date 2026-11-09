# One-shot G4 single-Issue read-only preflight. No G2 data or mutating routes.
param(
    [Parameter(Mandatory=$false)][string]$Region,
    [Parameter(Mandatory=$false)][string[]]$Organizations
)
$ErrorActionPreference='Stop'
if ([string]::IsNullOrWhiteSpace($Region)) { $Region = Read-Host 'SonarCloud region (eu or us)' }
if ($Region -cnotin @('eu','us')) { throw 'Region must be eu or us. No token requested.' }
if (-not $Organizations -or $Organizations.Count -eq 0) {
    $value = Read-Host 'SonarCloud organization key (NOT project key)'
    $Organizations = @($value)
}
if ($Organizations.Count -lt 1 -or $Organizations.Count -gt 20) {
    throw 'Specify 1 to 20 organization keys. No token requested.'
}
$orgArgs=@()
foreach ($org in $Organizations) {
    if ($org -cnotmatch '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$') {
        throw 'Invalid organization key. No token requested.'
    }
    $orgArgs += '--organization'
    $orgArgs += $org
}
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI missing' }
Write-Host 'Building isolated G4 GET-only Issue preflight image from reviewed source.'
& docker build --pull=false -t fortis-g4-issuepreflight:local -f (Join-Path $root 'fortis_approvals/deploy/Dockerfile-G4-IssuePreflight') $root
if ($LASTEXITCODE -ne 0) { throw 'Docker build failed before requesting token.' }
Write-Host 'Enter token only at the LOCAL hidden PowerShell prompt.'
$token=Read-Host 'Sonar token' -AsSecureString
$bstr=[IntPtr]::Zero
$plain=$null
try {
    $bstr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($token)
    $plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($plain)) { throw 'Empty token' }
    # No mounts, published ports, G2 volumes, or privileged capabilities.
    # The PowerShell process briefly holds plaintext in .NET memory.
    $dockerArgs = @('run','--rm','-i','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges:true','--pids-limit','32','--memory','128m','--network','bridge','--entrypoint','python','fortis-g4-issuepreflight:local','-m','fortis_approvals.sonar_preflight','--region',$Region)
    $dockerArgs += $orgArgs
    $plain | & docker @dockerArgs
    if ($LASTEXITCODE -ne 0) { throw 'Issue preflight failed; no changes attempted' }
} finally {
    $plain=$null
    if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    if ($null -ne $token) { $token.Dispose() }
}
