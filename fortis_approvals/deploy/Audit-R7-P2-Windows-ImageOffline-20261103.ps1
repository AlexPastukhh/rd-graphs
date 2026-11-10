# OWNER-RUN R7 P2 WebAuthn execute pinned image-only isolated audit (PowerShell 5.1).
# EXACT P2 source package; requires the owner-supplied post-build image digest.
# Two disposable --rm --network none containers; no volume/ports/credentials.
# Checks 19 installed source SHA256 and preflight imports only.
# Does NOT run pip check, reinstall packages, deploy or run Sonar.
param([Parameter(Mandatory=$true)][ValidatePattern('^sha256:[0-9a-f]{64}$')][string]$ExpectedImageId)
$ErrorActionPreference = 'Stop'
$image = 'fortis-r7-unified-read-ask-candidate:review-p2-20261103-a3e87c0c'
$expectedId = $ExpectedImageId
$containerPrefix = 'fortis-r7-p2-audit-20261103-'

$expectedFiles = [ordered]@{
    '/opt/fortis/fortis_approvals/__init__.py' = 'c854047bc577b5ff7622c198aebbabf4c0cf06a2928c8c5d71fe83cf6b8000cc'
    '/opt/fortis/fortis_approvals/a3_server.py' = '08df4347778786bd2ee8f0fbad01e5771ea645a77604193337933d4824265014'
    '/opt/fortis/fortis_approvals/core.py' = '8c18bd7f39e90144059387d57e0287261f3c5b38368985fa35fcc1dee4a0c61a'
    '/opt/fortis/fortis_approvals/owner_auth.py' = '39ab0024fc38dbd3e543d85a86ac24b8eaec782dfacd1a85180ea4d0c56c9e3e'
    '/opt/fortis/fortis_approvals/owner_portal.py' = 'a9b742ccdafe9fd41beb8aa1566533563258635e87cffb992f5d47268dab41ef'
    '/opt/fortis/fortis_approvals/r5_read_candidate.py' = 'c1d781e7f9130b9bca075b972a996d6abaf604b64cd16266b4382991991c935c'
    '/opt/fortis/fortis_approvals/r5_read_server.py' = 'fd89cb93aad09fac43295c3125367bf1d0cae26c486f02b9930bc7aef0c23927'
    '/opt/fortis/fortis_approvals/r7_unified_candidate.py' = '10cb23838441a1469c477d7f69a9a69f894944feebf52f09be7b9ace02267a10'
    '/opt/fortis/fortis_approvals/r7_unified_server.py' = '39c78071341edc2ad8fe91c5762f7b216d10f27e16711e1c1b4db41465cad0be'
    '/opt/fortis/fortis_approvals/repo_action_contract.py' = 'a270463e64fa1d44e7e0651758d622dfd2ab9f269e24502d7ad88c6e918a442c'
    '/opt/fortis/fortis_approvals/repo_ingress.py' = '5f67f16027580cf27cf2300a13b8814bc51b0e4d7a018c9be8535ecdf54705e0'
    '/opt/requirements-owner.txt' = '3d61b1d4e5ee110d3e902d107a9c75839551a87c1643948305e37a00c57c77c1'
    '/opt/fortis/fortis_approvals/server.py' = 'b900f113f6f4bacb519755cf77df9bda0ccad215ec8c9b22633727e9b36d5b27'
    '/opt/fortis/fortis_approvals/sonar.py' = '02c37f6ffae532bceeeacede47927b354f03c81ce2ddc8ad9560bb834facbf68'
    '/opt/fortis/fortis_approvals/sonar_inventory.py' = 'ddfee137bd32e6449a0b368220f64521e78054a74dd42d77d41e41891b1aee01'
    '/opt/fortis/fortis_approvals/sonar_read.py' = 'ad8edc32320e27f0babff8ff86bc88ba4844688254f01f67912dd49590bb834b'
    '/opt/fortis/fortis_approvals/static/app.js' = '74432894f0411e94ad549c403c9db4cdaa87503f1bdea43bc288edcfc431d6f2'
    '/opt/fortis/fortis_approvals/static/index.html' = 'fc6dc58e76e319056a53c425f766d27a66773228ad25a9ca0325427bdf079b50'
    '/opt/fortis/fortis_approvals/static/style.css' = 'aec28da05907508e182f1ce1c88db42c06b34692c0e584198cb29d8e368bb941'
}

$engine = (& docker info --format '{{.OSType}}' 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $engine -cne 'linux') {
    throw 'R7_P2_DOCKER_LINUX_ENGINE_REQUIRED'
}
$id = (& docker image inspect --format '{{.Id}}' $image 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $id -cne $expectedId) {
    throw 'R7_P2_REVIEW_IMAGE_ID_CHANGED'
}

$names = @(& docker ps -a --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0 -or
    @($names | Where-Object { $_ -match '^fortis-r7-p2-audit-20261102-' }).Count -ne 0) {
    throw 'R7_P2_CANDIDATE_CONTAINER_EXISTS_OR_DOCKER_UNAVAILABLE'
}
Write-Host 'FORTIS_R7_P2_OWNER_REVIEW_IMAGE_PIN_PASS'
Write-Host ('FORTIS_R7_P2_REVIEW_IMAGE_ID=' + $id)

$common = @('--rm','--pull=never','--network','none','--read-only',
            '--user','10001:10001','--cap-drop','ALL',
            '--security-opt','no-new-privileges:true',
            '--pids-limit','64','--memory','256m','--cpus','1',
            '--tmpfs','/tmp:rw,nosuid,nodev,size=16m,mode=1777')
$fileList = @($expectedFiles.Keys)

# Public image config only. Never dump the full Env or other secret metadata.
$configRaw = (& docker image inspect --format '{{json .Config}}' $image 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $configRaw) {
    throw 'R7_P2_IMAGE_CONFIG_INSPECT_FAILED'
}
$config = ConvertFrom-Json -InputObject $configRaw
if ([string]$config.User -cne '10001:10001') {
    throw 'R7_P2_IMAGE_USER_UNEXPECTED'
}
if ($null -ne $config.Entrypoint -and @($config.Entrypoint).Count -gt 0) {
    throw 'R7_P2_IMAGE_ENTRYPOINT_UNEXPECTED'
}
$cmd = @($config.Cmd)
if ($cmd.Count -ne 3 -or $cmd[0] -cne 'python' -or
    $cmd[1] -cne '-m' -or $cmd[2] -cne 'fortis_approvals.r7_unified_server') {
    throw 'R7_P2_IMAGE_DEFAULT_CMD_UNEXPECTED'
}
if ($null -ne $config.Volumes) {
    throw 'R7_P2_IMAGE_DECLARED_VOLUMES_UNEXPECTED'
}
$ports = @($config.ExposedPorts.PSObject.Properties.Name | Sort-Object)
if ($ports.Count -ne 2 -or $ports[0] -cne '19103/tcp' -or
    $ports[1] -cne '19104/tcp') {
    throw 'R7_P2_IMAGE_EXPOSED_PORTS_UNEXPECTED'
}
foreach ($entry in @($config.Env)) {
    if ([string]$entry -match '(?i)(SECRET|TOKEN|PASSWORD|CREDENTIAL|GRANT|PRIVATE_KEY|AUTHORIZATION)') {
        throw 'R7_P2_IMAGE_SECRET_ENV_OR_OVERRIDE_DETECTED'
    }
}
Write-Host 'FORTIS_R7_P2_IMAGE_METADATA_PASS'


$fileContainer = $containerPrefix + 'files'
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    # Direct binary, not shell evaluation. No files are modified.
    $hashOutput = (& docker run @common --name $fileContainer `
        --entrypoint sha256sum $image @fileList 2>&1 | Out-String).Trim()
    $hashExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previous
}
if ($hashExit -ne 0) {
    throw 'R7_P2_IMAGE_SOURCE_HASH_PROCESS_FAILED'
}
$seen = @{}
foreach ($line in @($hashOutput -split '\r?\n')) {
    if ($line -cnotmatch '^([0-9a-f]{64})  (/opt/[^\s]+)$') {
        throw 'R7_P2_IMAGE_SOURCE_HASH_OUTPUT_INVALID'
    }
    $digest = $Matches[1]
    $name = $Matches[2]
    if (-not $expectedFiles.Contains($name) -or $seen.ContainsKey($name) -or
        $expectedFiles[$name] -cne $digest) {
        throw 'R7_P2_IMAGE_SOURCE_HASH_MISMATCH'
    }
    $seen[$name] = $true
}
if ($seen.Count -ne $expectedFiles.Count) {
    throw 'R7_P2_IMAGE_SOURCE_FILES_MISSING'
}
Write-Host 'FORTIS_R7_P2_IMAGE_19_INSTALLED_SOURCE_SHA256_PASS'

# One temporary isolated import preflight on the exact image; never starts service.
$smokeContainer = $containerPrefix + 'import'
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $smokeOutput = (& docker run @common --name $smokeContainer `
        --entrypoint python $image -B -m fortis_approvals.r7_unified_server preflight-imports 2>&1 |
        Out-String).Trim()
    $smokeExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previous
}
if ($smokeExit -ne 0 -or
    $smokeOutput -notmatch '(?m)^FORTIS_R7_UNIFIED_READ_ASK_EXECUTE_IMPORTS_PASS\r?$' -or
    $smokeOutput -notmatch '(?m)^FORTIS_R7_SONAR_POST=OWNER_WEBAUTHN_APPROVAL_REQUIRED\r?$') {
    throw 'R7_P2_IMAGE_IMPORT_SMOKE_FAILED'
}
Write-Host 'FORTIS_R7_P2_EXACT_IMAGE_IMPORTS_PASS'
Write-Host 'FORTIS_R7_P2_SONAR_POST_DISABLED_IMPORT_PASS'

$after = @(& docker ps -a --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0 -or
    @($after | Where-Object { $_ -match '^fortis-r7-p2-audit-20261102-' }).Count -ne 0) {
    throw 'R7_P2_DISPOSABLE_CONTAINER_NOT_REMOVED'
}
Write-Host 'FORTIS_R7_P2_AUDIT_DISPOSABLE_CONTAINERS_REMOVED_PASS'
Write-Host 'FORTIS_R7_P2_IMAGE_OFFLINE_IMPORT_AND_SOURCE_AUDIT_PASS'
Write-Host 'FORTIS_R7_P2_NO_LIVE_CONTAINER_DEPLOYMENT'
Write-Host 'FORTIS_R7_P2_SONAR_TOKEN_PROVISIONED=NO'
Write-Host 'FORTIS_R7_P2_SONAR_NETWORK_REQUESTS=NONE'
Write-Host 'FORTIS_R7_P2_PINNED_PIP_AND_PIP_CHECK=NOT_REPEATED'
Write-Host 'FORTIS_R7_P2_TRUSTED_ADMISSION=OPEN'
