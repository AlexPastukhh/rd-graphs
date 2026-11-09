# Owner-invoked ONLY after independently reviewing the source archive.
# Does NOT restart/modify G2, read its volume, open ports or POST to Sonar.
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('eu','us')]
    [string]$Region,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$')]
    [string]$ProjectKey
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI not found' }
Write-Host 'Building a separate, ephemeral Sonar READ-only image from the reviewed files.'
& docker build --pull=false -t fortis-g4-readprobe:local -f (Join-Path $root 'fortis_approvals\deploy\Dockerfile-G4-ReadOnly') $root
if ($LASTEXITCODE -ne 0) { throw 'G4 read-probe image build failed' }
Write-Host 'Paste a SonarQube Cloud token into the LOCAL hidden prompt. It will not be stored in a file or passed as a Docker argument/environment variable.'
$token = Read-Host 'Sonar token' -AsSecureString
$bstr = [IntPtr]::Zero
$plain = $null
try {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($token)
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($plain)) { throw 'Empty token' }
    # stdin-only; isolated disposable container, no mounts, no listening ports.
    # Note: PowerShell/.NET necessarily keep a short-lived plaintext string in
    # this process memory. Do not paste the token into chat or command history.
    $plain | & docker run --rm -i --read-only --user '10001:10001' `
        --cap-drop ALL --security-opt 'no-new-privileges:true' `
        --pids-limit 32 --memory 128m `
        --network bridge `
        fortis-g4-readprobe:local --region $Region --project $ProjectKey
    if ($LASTEXITCODE -ne 0) { throw 'Read-only Sonar probe failed; no mutation was attempted.' }
} finally {
    $plain = $null
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    $token.Dispose()
}
