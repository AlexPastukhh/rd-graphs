# G4 organization-scoped, ALL-project READ-only discovery.
param(
    [Parameter(Mandatory=$false)][string]$Region,
    [Parameter(Mandatory=$false)][string[]]$Organizations,
    [switch]$ReadIssues
)
$ErrorActionPreference='Stop'
if ([string]::IsNullOrWhiteSpace($Region)) { $Region = Read-Host 'SonarCloud region (eu or us)' }
if ($Region -cnotin @('eu','us')) { throw 'Region must be eu or us. No token requested.' }
if (-not $Organizations -or $Organizations.Count -eq 0) {
    $value = Read-Host 'SonarCloud organization key (NOT project key)'
    $Organizations = @($value)
}
if ($Organizations.Count -lt 1 -or $Organizations.Count -gt 20) {
    throw 'Specify 1 to 20 organization keys.'
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
Write-Host 'Building one-shot READ-only inventory image from reviewed source.'
& docker build --pull=false -t fortis-g4-readprobe:local -f (Join-Path $root 'fortis_approvals/deploy/Dockerfile-G4-ReadOnly') $root
if ($LASTEXITCODE -ne 0) { throw 'Docker build failed' }
Write-Host 'Enter token only at the LOCAL hidden PowerShell prompt.'
$token=Read-Host 'Sonar token' -AsSecureString
$bstr=[IntPtr]::Zero
$plain=$null
try {
    $bstr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($token)
    $plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($plain)) { throw 'Empty token' }
    # One-shot isolated container, no G2 volumes, no open ports, no POST.
    # PowerShell/.NET briefly holds plaintext in process memory.
    $dockerArgs = @('run','--rm','-i','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges:true','--pids-limit','32','--memory','128m','--network','bridge','--entrypoint','python','fortis-g4-readprobe:local','-m','fortis_approvals.sonar_inventory','--region',$Region)
    $dockerArgs += $orgArgs
    if ($ReadIssues) { $dockerArgs += '--read-issues' }
    $plain | & docker @dockerArgs
    if ($LASTEXITCODE -ne 0) { throw 'Discovery failed; no mutation attempted' }
} finally {
    $plain=$null
    if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    if ($null -ne $token) { $token.Dispose() }
}
