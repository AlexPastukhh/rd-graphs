# Separate G4 credential, NEVER the existing G2. One-shot: no overwrite.
$ErrorActionPreference='Stop'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI missing' }
Write-Host 'WARNING: Token will persist UNENCRYPTED in fortis-approvals-g4_token Docker volume.'
Write-Host 'File owner UID 10001; permission 0600. Docker/host admins can still read it.'
Write-Host 'Token will not be in command args, environment, image or terminal output.'
$ack=Read-Host 'Type STORE to explicitly permit local Docker-volume token storage'
if ($ack -cne 'STORE') { throw 'Provisioning cancelled; no token requested' }
# List without generating an expected missing-object stderr error under
# Windows PowerShell $ErrorActionPreference=Stop.
$volumeNames = @(& docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0) { throw 'Unable to list Docker volumes.' }
if ($volumeNames -notcontains 'fortis-approvals-g4_token') {
    throw 'G4 token volume missing. Prepare candidate first.'
}
$imageNames = @(& docker image ls --format '{{.Repository}}:{{.Tag}}')
if ($LASTEXITCODE -ne 0) { throw 'Unable to list Docker images.' }
if ($imageNames -notcontains 'fortis-approvals-g4-candidate:local') {
    throw 'Reviewed G4 candidate image missing.'
}
# Verify private subdirectory before asking for the credential.
$privateMount='type=volume,source=fortis-approvals-g4_token,target=/run/g4-token'
& docker run --rm --network none --read-only --user '10001:10001' --cap-drop ALL --security-opt 'no-new-privileges:true' --mount $privateMount --entrypoint python 'fortis-approvals-g4-candidate:local' '-m' 'fortis_approvals.g4_volume_repair' 'verify' 'token'
if ($LASTEXITCODE -ne 0) { throw 'G4 private directory is not ready; DO NOT enter token' }
$secure=Read-Host 'Sonar token (LOCAL hidden input)' -AsSecureString
$ptr=[IntPtr]::Zero
$plain=$null
try {
    $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    if ([string]::IsNullOrWhiteSpace($plain)) { throw 'Empty token' }
    # This temporary container is offline; bootstrap reads ONLY stdin.
    $args=@('run','--rm','-i','--network','none','--read-only',
        '--user','10001:10001','--cap-drop','ALL',
        '--security-opt','no-new-privileges:true','--pids-limit','16',
        '--memory','64m','--mount',
        'type=volume,source=fortis-approvals-g4_token,target=/run/g4-token',
        '--entrypoint','python','fortis-approvals-g4-candidate:local',
        '-m','fortis_approvals.g4_secret_bootstrap')
    $plain | & docker @args
    if ($LASTEXITCODE -ne 0) { throw 'Credential provisioning failed/refused; no overwrite attempted' }
} finally {
    $plain=$null
    if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    if ($null -ne $secure) { $secure.Dispose() }
}
