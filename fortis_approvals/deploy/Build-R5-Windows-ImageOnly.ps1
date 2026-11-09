# Owner-initiated R5 REVIEW IMAGE BUILD ONLY (PowerShell 5.1).
# Never docker run/start/stop/restart/compose up, never open a network port.
# Builds from exact 18-source-file review ZIP; no trusted/private volumes.
# Build MAY download python base image and pinned pip dependencies from
# external registries; base/image supply-chain trust and R5 GO are still OPEN.
# It may use disk/network and create build cache and a REVIEW-ONLY image.
param([string]$PackagePath = '')
$ErrorActionPreference = 'Stop'
if (-not $PackagePath) {
    $PackagePath = Join-Path $HOME 'Downloads\fortis-r5-read-source-review-20261101.zip'
}
$expectedZip = 'e6aec45335cc3df17dfa58c3d4692177b99ccac7310b8e1d52dacf997d076bfa'
$expectedManifest = 'e6a1240d005f2d6f7cbb90e4832d15b2fa645ce0d26a9a86e98b942bf6a09f6d'
$expectedDockerfile = '91dac44f20ddc68a858e6d2d774c9bb83b6583bec9b6288f0eb7baae4efa2769'
$imageTag = 'fortis-r5-sonar-read-candidate:review-20261101-e6aec453'
$expectedNames = @(
    'fortis_approvals/__init__.py',
    'fortis_approvals/a3_server.py',
    'fortis_approvals/core.py',
    'fortis_approvals/deploy/Dockerfile-R5-Sonar-Read-Candidate',
    'fortis_approvals/owner_auth.py',
    'fortis_approvals/owner_portal.py',
    'fortis_approvals/r5_read_candidate.py',
    'fortis_approvals/r5_read_server.py',
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
    throw 'R5_REVIEW_SOURCE_PACKAGE_MISSING'
}
$zipHash = (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($zipHash -cne $expectedZip) {
    throw 'R5_SOURCE_PACKAGE_SHA256_MISMATCH'
}
Write-Host 'FORTIS_R5_REVIEW_ZIP_SHA256_PASS'

if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'R5_DOCKER_NOT_AVAILABLE'
}
$os = (& docker info --format '{{.OSType}}' 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $os -cne 'linux') {
    throw 'R5_DOCKER_LINUX_ENGINE_REQUIRED'
}
$images = @(& docker images --format '{{.Repository}}:{{.Tag}}' 2>$null)
if ($LASTEXITCODE -ne 0) {
    throw 'R5_IMAGE_LIST_FAILED'
}
if ($images -ccontains $imageTag) {
    throw 'R5_REVIEW_IMAGE_TAG_ALREADY_EXISTS_NO_OVERWRITE'
}

# Historical Windows disk-full incidents: do not build if system disk is low.
$systemDriveName = $env:SystemDrive.TrimEnd(':')
$systemDisk = Get-PSDrive -Name $systemDriveName -ErrorAction Stop
if ($systemDisk.Free -lt 8GB) {
    throw 'R5_WINDOWS_SYSTEM_DISK_LOW_DO_NOT_BUILD'
}
Write-Host 'FORTIS_R5_DISK_8G_FREE_PASS'

# Fresh, unique Windows-only extraction directory; no workspace or volume writes.
$workspace = Join-Path $env:TEMP ('Fortis-R5-Review-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $workspace -ErrorAction Stop
Expand-Archive -LiteralPath $PackagePath -DestinationPath $workspace -ErrorAction Stop
$manifestPath = Join-Path $workspace 'SOURCE-MANIFEST.sha256'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw 'R5_MANIFEST_MISSING'
}
$manifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($manifestHash -cne $expectedManifest) {
    throw 'R5_MANIFEST_SHA256_MISMATCH'
}
$manifestLines = @(Get-Content -LiteralPath $manifestPath -Encoding UTF8)
if ($manifestLines.Count -ne 18) {
    throw 'R5_SOURCE_FILE_COUNT_MISMATCH'
}
$seen = @{}
foreach ($line in $manifestLines) {
    if ($line -cnotmatch '^([0-9a-f]{64})  ([A-Za-z0-9_./-]+)$') {
        throw 'R5_MANIFEST_LINE_INVALID'
    }
    $hash = $Matches[1]
    $rel = $Matches[2]
    if ($expectedNames -cnotcontains $rel -or $seen.ContainsKey($rel)) {
        throw 'R5_UNEXPECTED_OR_DUPLICATE_SOURCE'
    }
    $seen[$rel] = $true
    $file = Join-Path $workspace $rel.Replace('/', '\')
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw 'R5_SOURCE_FILE_MISSING'
    }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hash) {
        throw 'R5_SOURCE_FILE_SHA256_MISMATCH'
    }
}
if ($seen.Count -ne $expectedNames.Count) {
    throw 'R5_SOURCE_ALLOWLIST_INCOMPLETE'
}
$files = @(Get-ChildItem -LiteralPath $workspace -Recurse -File)
if ($files.Count -ne 19) {
    throw 'R5_BUILD_CONTEXT_HAS_UNEXPECTED_FILES'
}
$dockerfile = Join-Path $workspace 'fortis_approvals\deploy\Dockerfile-R5-Sonar-Read-Candidate'
if ((Get-FileHash -LiteralPath $dockerfile -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expectedDockerfile) {
    throw 'R5_DOCKERFILE_SHA256_MISMATCH'
}
Write-Host 'FORTIS_R5_EXACT_BUILD_CONTEXT_AND_MANIFEST_PASS'
Write-Host 'FORTIS_REPO_GUARDS_NOT_CHANGED_OR_RESTARTED'
Write-Host 'FORTIS_R5_BUILD_BEGIN_IMAGE_ONLY'

# PowerShell 5.1 treats native stderr (BuildKit progress) as an error
# with ErrorActionPreference=Stop, even when docker build returns zero.
# Honor the Docker exit code, while allowing normal build progress output.
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    & docker build --no-cache --pull=false --tag $imageTag --file $dockerfile $workspace
    $buildExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
if ($buildExitCode -ne 0) {
    throw 'R5_IMAGE_BUILD_FAILED_NO_DEPLOY'
}
$id = (& docker image inspect --format '{{.Id}}' $imageTag 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $id -notmatch '^sha256:[0-9a-f]{64}$') {
    throw 'R5_IMAGE_INSPECT_FAILED'
}
Write-Host 'FORTIS_R5_IMAGE_ONLY_BUILD_PASS'
Write-Host ('FORTIS_R5_REVIEW_IMAGE_TAG=' + $imageTag)
Write-Host ('FORTIS_R5_REVIEW_IMAGE_ID=' + $id)
Write-Host 'FORTIS_R5_CONTAINERS_STARTED=NONE'
Write-Host 'FORTIS_R5_SONAR_TOKEN_PROVISIONED=NO'
Write-Host 'FORTIS_R5_TRUSTED_ADMISSION=OPEN'
