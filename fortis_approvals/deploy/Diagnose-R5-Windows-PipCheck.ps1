# R5 pip-check diagnosis only (Windows PowerShell 5.1).
# One disposable Docker container. NO network, volumes, ports or credentials.
# Does NOT modify the R5 image, A3, Fortis Repo, or Repo1/Repo2 Guards.
# Read the exit code separately from the output: a strict string comparison
# in the earlier audit may have caused a false-negative.
$ErrorActionPreference = 'Stop'
$image = 'fortis-r5-sonar-read-candidate:review-20261101-e6aec453'
$expectedId = 'sha256:5fa986d7e532639c5461a87e4a2c34ea8176ec58371f418758d0cd5dfc38bd02'
$smokeName = 'fortis-r5-pip-diagnostic-20261101'

if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'R5_DOCKER_CLI_MISSING'
}
$engine = (& docker info --format '{{.OSType}}' 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $engine -cne 'linux') {
    throw 'R5_DOCKER_LINUX_ENGINE_REQUIRED'
}
$id = (& docker image inspect --format '{{.Id}}' $image 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $id -cne $expectedId) {
    throw 'R5_PINNED_REVIEW_IMAGE_MISMATCH'
}
$names = @(& docker ps -a --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0 -or $names -ccontains $smokeName) {
    throw 'R5_DIAGNOSTIC_CONTAINER_EXISTS_OR_DOCKER_UNAVAILABLE'
}
Write-Host 'FORTIS_R5_DIAG_PINNED_IMAGE_PASS'
Write-Host 'FORTIS_R5_DIAG_START_ISOLATED_PIP_CHECK'

# Docker's pip check can emit warnings even when exit code is zero.
# The exact pip output is safe to show: no secrets are mounted or passed.
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $output = (& docker run --rm --pull=never --name $smokeName `
        --network none --read-only --user '10001:10001' `
        --cap-drop ALL --security-opt 'no-new-privileges:true' `
        --pids-limit 64 --memory 256m --cpus 1 `
        --tmpfs '/tmp:rw,nosuid,nodev,size=16m,mode=1777' `
        --entrypoint python $image -B -m pip check 2>&1 | Out-String).Trim()
    $exitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
if ($null -eq $exitCode) {
    throw 'R5_PIP_EXIT_CODE_UNAVAILABLE'
}
Write-Host ('FORTIS_R5_PIP_CHECK_EXIT_CODE=' + [string]$exitCode)

# Bound report size. No private environment, stdout of other apps,
# Docker full inspection or private paths are printed.
if ($output.Length -gt 2048) {
    throw 'R5_PIP_CHECK_OUTPUT_TOO_LARGE_FOR_CHAT'
}
Write-Host ('FORTIS_R5_PIP_CHECK_OUTPUT_LENGTH=' + [string]$output.Length)
if ($output.Length -eq 0) {
    Write-Host 'FORTIS_R5_PIP_CHECK_OUTPUT=EMPTY'
} else {
    foreach ($line in @($output -split '\r?\n')) {
        Write-Host ('FORTIS_R5_PIP_CHECK_LINE=' + [string]$line)
    }
}
$remaining = @(& docker ps -a --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0 -or $remaining -ccontains $smokeName) {
    throw 'R5_DIAGNOSTIC_CONTAINER_NOT_REMOVED'
}
Write-Host 'FORTIS_R5_DIAG_TEMPORARY_CONTAINER_REMOVED_PASS'
if ($exitCode -eq 0 -and $output -ceq 'No broken requirements found.') {
    Write-Host 'FORTIS_R5_PIP_CHECK_DIAGNOSIS=SUCCESS_EXACT_TEXT'
} elseif ($exitCode -eq 0) {
    Write-Host 'FORTIS_R5_PIP_CHECK_DIAGNOSIS=SUCCESS_WITH_DIFFERENT_TEXT'
} else {
    Write-Host 'FORTIS_R5_PIP_CHECK_DIAGNOSIS=DEPENDENCY_OR_RUNTIME_ERROR'
}
Write-Host 'FORTIS_R5_TRUSTED_ADMISSION=OPEN'
