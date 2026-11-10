# Owner-side R5 review image content/dependency audit (PowerShell 5.1).
# Existing R5 image ID only. No actual Sonar requests, tokens, volumes/ports,
# A3/Repo mutations, Guard scripts or Fortis service start.
# Three disposable --rm --network none containers: file hashes, pip list/check.
# Does NOT provide base image provenance, vulnerability audit, or owner GO.
$ErrorActionPreference = 'Stop'
$image = 'fortis-r5-sonar-read-candidate:review-20261101-e6aec453'
$expectedId = 'sha256:5fa986d7e532639c5461a87e4a2c34ea8176ec58371f418758d0cd5dfc38bd02'
$containerPrefix = 'fortis-r5-image-audit-20261101-'

# Exact source bytes from SHA-reviewed R5 Dockerfile COPY context.
$expectedFiles = [ordered]@{
    '/opt/requirements-owner.txt' = '3d61b1d4e5ee110d3e902d107a9c75839551a87c1643948305e37a00c57c77c1'
    '/opt/fortis/fortis_approvals/__init__.py' = 'c854047bc577b5ff7622c198aebbabf4c0cf06a2928c8c5d71fe83cf6b8000cc'
    '/opt/fortis/fortis_approvals/core.py' = 'ba7a8735d6ce9cc48c236fc35e2856ca7208020d8db1a97bd11bb9ecdfa3694e'
    '/opt/fortis/fortis_approvals/owner_auth.py' = '39ab0024fc38dbd3e543d85a86ac24b8eaec782dfacd1a85180ea4d0c56c9e3e'
    '/opt/fortis/fortis_approvals/owner_portal.py' = '0a315baf081d63f28cd7bee8fd049996d1a6efbcb3b11af0fdeb6a30ff6b8bf9'
    '/opt/fortis/fortis_approvals/repo_action_contract.py' = 'a270463e64fa1d44e7e0651758d622dfd2ab9f269e24502d7ad88c6e918a442c'
    '/opt/fortis/fortis_approvals/repo_ingress.py' = '5f67f16027580cf27cf2300a13b8814bc51b0e4d7a018c9be8535ecdf54705e0'
    '/opt/fortis/fortis_approvals/sonar.py' = '02c37f6ffae532bceeeacede47927b354f03c81ce2ddc8ad9560bb834facbf68'
    '/opt/fortis/fortis_approvals/sonar_inventory.py' = 'ddfee137bd32e6449a0b368220f64521e78054a74dd42d77d41e41891b1aee01'
    '/opt/fortis/fortis_approvals/sonar_read.py' = '9be71108e5febbb70a8781bccc4d3914e3bd4f0a1fcf23ed676620f8cfdfbf71'
    '/opt/fortis/fortis_approvals/r5_read_candidate.py' = 'c1d781e7f9130b9bca075b972a996d6abaf604b64cd16266b4382991991c935c'
    '/opt/fortis/fortis_approvals/r5_read_server.py' = 'fd89cb93aad09fac43295c3125367bf1d0cae26c486f02b9930bc7aef0c23927'
    '/opt/fortis/fortis_approvals/a3_server.py' = '08df4347778786bd2ee8f0fbad01e5771ea645a77604193337933d4824265014'
    '/opt/fortis/fortis_approvals/server.py' = 'b900f113f6f4bacb519755cf77df9bda0ccad215ec8c9b22633727e9b36d5b27'
    '/opt/fortis/fortis_approvals/static/app.js' = '74432894f0411e94ad549c403c9db4cdaa87503f1bdea43bc288edcfc431d6f2'
    '/opt/fortis/fortis_approvals/static/index.html' = 'fc6dc58e76e319056a53c425f766d27a66773228ad25a9ca0325427bdf079b50'
    '/opt/fortis/fortis_approvals/static/style.css' = 'aec28da05907508e182f1ce1c88db42c06b34692c0e584198cb29d8e368bb941'
}

$engine = (& docker info --format '{{.OSType}}' 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $engine -cne 'linux') {
    throw 'R5_DOCKER_LINUX_ENGINE_REQUIRED'
}
$id = (& docker image inspect --format '{{.Id}}' $image 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $id -cne $expectedId) {
    throw 'R5_REVIEW_IMAGE_ID_CHANGED'
}

$names = @(& docker ps -a --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0 -or
    @($names | Where-Object { $_ -match '^fortis-r5-' }).Count -ne 0) {
    throw 'R5_CANDIDATE_CONTAINER_EXISTS_OR_DOCKER_UNAVAILABLE'
}
Write-Host 'FORTIS_R5_OWNER_REVIEW_IMAGE_PIN_PASS'

$common = @('--rm','--pull=never','--network','none','--read-only',
            '--user','10001:10001','--cap-drop','ALL',
            '--security-opt','no-new-privileges:true',
            '--pids-limit','64','--memory','256m','--cpus','1',
            '--tmpfs','/tmp:rw,nosuid,nodev,size=16m,mode=1777')
$fileList = @($expectedFiles.Keys)
$fileContainer = $containerPrefix + 'files'
$packageContainer = $containerPrefix + 'packages'
$checkContainer = $containerPrefix + 'pipcheck'
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
    throw 'R5_IMAGE_SOURCE_HASH_PROCESS_FAILED'
}
$seen = @{}
foreach ($line in @($hashOutput -split '\r?\n')) {
    if ($line -cnotmatch '^([0-9a-f]{64})  (/opt/[^\s]+)$') {
        throw 'R5_IMAGE_SOURCE_HASH_OUTPUT_INVALID'
    }
    $digest = $Matches[1]
    $name = $Matches[2]
    if (-not $expectedFiles.Contains($name) -or $seen.ContainsKey($name) -or
        $expectedFiles[$name] -cne $digest) {
        throw 'R5_IMAGE_SOURCE_HASH_MISMATCH'
    }
    $seen[$name] = $true
}
if ($seen.Count -ne $expectedFiles.Count) {
    throw 'R5_IMAGE_SOURCE_FILES_MISSING'
}
Write-Host 'FORTIS_R5_IMAGE_17_INSTALLED_SOURCE_SHA256_PASS'

$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $pipOutput = (& docker run @common --name $packageContainer `
        --entrypoint python $image -B -m pip list --format freeze 2>&1 |
        Out-String).Trim()
    $pipExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previous
}
if ($pipExit -ne 0) {
    throw 'R5_IMAGE_PIP_LIST_FAILED'
}
$packages = @($pipOutput -split '\r?\n')
foreach ($needed in @('fido2==2.2.1','cryptography==50.0.2',
                     'cffi==2.1.1','pycparser==3.12')) {
    if (@($packages | Where-Object { $_ -ieq $needed }).Count -ne 1) {
        throw 'R5_IMAGE_PINNED_PIP_DEPENDENCY_MISMATCH'
    }
}
Write-Host 'FORTIS_R5_IMAGE_FOUR_PINNED_PIP_VERSIONS_PASS'

$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $checkOutput = (& docker run @common --name $checkContainer `
        --entrypoint python $image -B -m pip check 2>&1 | Out-String).Trim()
    $checkExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previous
}
# pip check's exit code is authoritative (0 = satisfied requirements).
# PowerShell 5.1 wraps native stderr warnings into ErrorRecords, which can
# append script locations/line numbers even when pip exits successfully.
# Require the success line but do not compare the entire merged output.
if ($checkExit -ne 0) {
    throw 'R5_IMAGE_PIP_DEPENDENCY_GRAPH_FAILED'
}
if ($checkOutput -notmatch '(?m)^No broken requirements found\.$') {
    throw 'R5_IMAGE_PIP_SUCCESS_TEXT_NOT_FOUND'
}
Write-Host 'FORTIS_R5_IMAGE_PIP_CHECK_PASS'

$after = @(& docker ps -a --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0 -or
    @($after | Where-Object { $_ -match '^fortis-r5-' }).Count -ne 0) {
    throw 'R5_IMAGE_AUDIT_CONTAINER_NOT_REMOVED'
}
Write-Host 'FORTIS_R5_AUDIT_DISPOSABLE_CONTAINERS_REMOVED_PASS'
Write-Host 'FORTIS_R5_IMAGE_BYTES_AND_DEPENDENCIES_OWNER_AUDIT_PASS'
Write-Host 'FORTIS_R5_EXISTING_FORTIS_AND_REPO_GUARDS_UNCHANGED_BY_SCRIPT'
Write-Host 'FORTIS_R5_IMAGE_BASE_PROVENANCE_VULNERABILITY_ADMISSION=OPEN'
Write-Host 'FORTIS_R5_TLS_GRANT_LIFECYCLE=OPEN'
Write-Host 'FORTIS_R5_SONAR_TOKEN_PROVISIONED=NO'
Write-Host 'FORTIS_R5_TRUSTED_ADMISSION=OPEN'
