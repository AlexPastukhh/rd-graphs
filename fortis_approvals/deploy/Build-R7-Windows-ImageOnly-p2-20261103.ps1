# OWNER-RUN R7 P2 IMAGE-ONLY BUILD (Windows PowerShell 5.1).
# P2 packages the current WebAuthn-gated source after the recorded source change.
# This is an image-only review build, not a live deployment.
# Historical R7 v1/v2 image tags MUST NOT be overwritten.
# This is NOT a live Fortis update. Does not launch/start/stop/restart
# any service, create/modify private volumes, publish ports, touch A3,
# issue machine grants, load Sonar tokens or run Sonar POST/GET.
# docker build MAY use network to download base image and pinned pip wheels;
# supply-chain provenance/admission remains OPEN. Emits only review image ID.
param([string]$PackagePath = '')
$ErrorActionPreference = 'Stop'

if (-not $PackagePath) {
    $PackagePath = Join-Path $HOME 'Downloads\fortis-r7-unified-source-review-p2-20261103.zip'
}
$expectedZip = 'a3e87c0c8643e79db48655aae9e100029b6f0bd6683369e565e59ec995718748'
$expectedManifest = 'd766c28b9d2ea52e40f613614d85962e8eeee61393bbf80d8acf7be6ae05c1db'
$expectedDockerfile = '0bb5f19ff8d40642946c64dbc46a7759607aa60bd9648cd48a605570ff908b86'
$imageTag = 'fortis-r7-unified-read-ask-candidate:review-p2-20261103-a3e87c0c'
$expectedNames = @(
    'fortis_approvals/__init__.py',
    'fortis_approvals/a3_server.py',
    'fortis_approvals/core.py',
    'fortis_approvals/deploy/Dockerfile-R7-Unified-Read-Ask-Candidate',
    'fortis_approvals/owner_auth.py',
    'fortis_approvals/owner_portal.py',
    'fortis_approvals/r5_read_candidate.py',
    'fortis_approvals/r5_read_server.py',
    'fortis_approvals/r7_unified_candidate.py',
    'fortis_approvals/r7_unified_server.py',
    'fortis_approvals/repo_action_contract.py',
    'fortis_approvals/repo_ingress.py',
    'fortis_approvals/requirements-owner.txt',
    'fortis_approvals/server.py',
    'fortis_approvals/sonar.py',
    'fortis_approvals/sonar_inventory.py',
    'fortis_approvals/sonar_read.py',
    'fortis_approvals/static/app.js',
    'fortis_approvals/static/index.html',
    'fortis_approvals/static/style.css'
)

if (-not (Test-Path -LiteralPath $PackagePath -PathType Leaf)) {
    throw 'R7_P2_REVIEW_SOURCE_PACKAGE_MISSING'
}
$zipHash = (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($zipHash -cne $expectedZip) {
    throw 'R7_P2_SOURCE_PACKAGE_SHA256_MISMATCH'
}
Write-Host 'FORTIS_R7_P2_REVIEW_ZIP_SHA256_PASS'

if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'R7_DOCKER_NOT_AVAILABLE'
}
$os = (& docker info --format '{{.OSType}}' 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $os -cne 'linux') {
    throw 'R7_DOCKER_LINUX_ENGINE_REQUIRED'
}
$images = @(& docker images --format '{{.Repository}}:{{.Tag}}' 2>$null)
if ($LASTEXITCODE -ne 0) {
    throw 'R7_IMAGE_LIST_FAILED'
}
if ($images -ccontains $imageTag) {
    throw 'R7_P2_REVIEW_IMAGE_TAG_ALREADY_EXISTS_NO_OVERWRITE'
}

$systemDriveName = $env:SystemDrive.TrimEnd(':')
$systemDisk = Get-PSDrive -Name $systemDriveName -ErrorAction Stop
if ($systemDisk.Free -lt 8GB) {
    throw 'R7_WINDOWS_SYSTEM_DISK_LOW_DO_NOT_BUILD'
}
Write-Host 'FORTIS_R7_P2_DISK_8G_FREE_PASS'

$workspace = Join-Path $env:TEMP ('Fortis-R7-Review-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $workspace -ErrorAction Stop
Expand-Archive -LiteralPath $PackagePath -DestinationPath $workspace -ErrorAction Stop
$manifestPath = Join-Path $workspace 'SOURCE-MANIFEST.sha256'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw 'R7_P2_MANIFEST_MISSING'
}
$manifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($manifestHash -cne $expectedManifest) {
    throw 'R7_P2_MANIFEST_SHA256_MISMATCH'
}
$manifestLines = @(Get-Content -LiteralPath $manifestPath -Encoding UTF8)
if ($manifestLines.Count -ne 20) {
    throw 'R7_P2_SOURCE_FILE_COUNT_MISMATCH'
}
$seen = @{}
foreach ($line in $manifestLines) {
    if ($line -cnotmatch '^([0-9a-f]{64})  ([A-Za-z0-9_./-]+)$') {
        throw 'R7_P2_MANIFEST_LINE_INVALID'
    }
    $hash = $Matches[1]
    $rel = $Matches[2]
    if ($expectedNames -cnotcontains $rel -or $seen.ContainsKey($rel)) {
        throw 'R7_P2_UNEXPECTED_OR_DUPLICATE_SOURCE'
    }
    $seen[$rel] = $true
    $file = Join-Path $workspace $rel.Replace('/', '\')
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw 'R7_P2_SOURCE_FILE_MISSING'
    }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hash) {
        throw 'R7_P2_SOURCE_FILE_SHA256_MISMATCH'
    }
}
if ($seen.Count -ne $expectedNames.Count) {
    throw 'R7_P2_SOURCE_ALLOWLIST_INCOMPLETE'
}
$files = @(Get-ChildItem -LiteralPath $workspace -Recurse -File)
if ($files.Count -ne 21) {
    throw 'R7_P2_BUILD_CONTEXT_HAS_UNEXPECTED_FILES'
}
$dockerfile = Join-Path $workspace 'fortis_approvals\deploy\Dockerfile-R7-Unified-Read-Ask-Candidate'
if ((Get-FileHash -LiteralPath $dockerfile -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expectedDockerfile) {
    throw 'R7_P2_DOCKERFILE_SHA256_MISMATCH'
}
Write-Host 'FORTIS_R7_P2_EXACT_BUILD_CONTEXT_AND_MANIFEST_PASS'
Write-Host 'FORTIS_REPO_GUARDS_NOT_CHANGED_OR_RESTARTED'
Write-Host 'FORTIS_R7_P2_BUILD_BEGIN_IMAGE_ONLY'

# PowerShell 5.1 may wrap native build-progress stderr in ErrorRecords.
# The docker exit code determines build success, not exact merged text.
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    & docker build --no-cache --pull=false --tag $imageTag --file $dockerfile $workspace
    $buildExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
if ($buildExitCode -ne 0) {
    throw 'R7_P2_IMAGE_BUILD_FAILED_NO_DEPLOY'
}
$id = (& docker image inspect --format '{{.Id}}' $imageTag 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $id -notmatch '^sha256:[0-9a-f]{64}$') {
    throw 'R7_P2_IMAGE_INSPECT_FAILED'
}
Write-Host 'FORTIS_R7_P2_IMAGE_ONLY_BUILD_PASS'
Write-Host ('FORTIS_R7_P2_REVIEW_IMAGE_TAG=' + $imageTag)
Write-Host ('FORTIS_R7_P2_REVIEW_IMAGE_ID=' + $id)
Write-Host 'FORTIS_R7_P2_CONTAINERS_STARTED=NONE'
Write-Host 'FORTIS_R7_P2_SONAR_TOKEN_PROVISIONED=NO'
Write-Host 'FORTIS_R7_P2_SONAR_POST=DISABLED'
Write-Host 'FORTIS_R7_P2_TRUSTED_ADMISSION=OPEN'
Write-Host 'FORTIS_R7_P2_DEPLOYMENT=NOT_AUTHORIZED'
