# OWNER-RUN R7 IMAGE REVIEW smoke only. PowerShell 5.1.
# ONE disposable (--rm) offline container; NO service deployment, private
# files/volumes, TLS setup, published ports, real Sonar requests, or WRITE.
# Expected image ID is pinned to the owner-reported 2026-11-01 build.
$ErrorActionPreference = 'Stop'
$imageTag = 'fortis-r7-unified-read-ask-candidate:review-20261101-b0055e19'
$expectedId = 'sha256:d555bcd2baf10297e05547d8be7049fbbca80a40df4378e9912e0a3cbbdd9fba'
$smokeName = 'fortis-r7-import-smoke-20261101'

if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'R7_DOCKER_CLI_REQUIRED'
}
$engine = (& docker info --format '{{.OSType}}' 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $engine -cne 'linux') {
    throw 'R7_LINUX_DOCKER_ENGINE_REQUIRED'
}
$id = (& docker image inspect --format '{{.Id}}' $imageTag 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $id -cne $expectedId) {
    throw 'R7_IMAGE_ID_MISMATCH_STOP'
}
Write-Host 'FORTIS_R7_REVIEW_IMAGE_ID_MATCH_PASS'

# Public image config only. Never dump the full Env or other secret metadata.
$configRaw = (& docker image inspect --format '{{json .Config}}' $imageTag 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $configRaw) {
    throw 'R7_IMAGE_CONFIG_INSPECT_FAILED'
}
$config = ConvertFrom-Json -InputObject $configRaw
if ([string]$config.User -cne '10001:10001') {
    throw 'R7_IMAGE_USER_UNEXPECTED'
}
if ($null -ne $config.Entrypoint -and @($config.Entrypoint).Count -gt 0) {
    throw 'R7_IMAGE_ENTRYPOINT_UNEXPECTED'
}
$cmd = @($config.Cmd)
if ($cmd.Count -ne 3 -or $cmd[0] -cne 'python' -or
    $cmd[1] -cne '-m' -or $cmd[2] -cne 'fortis_approvals.r7_unified_server') {
    throw 'R7_IMAGE_DEFAULT_CMD_UNEXPECTED'
}
if ($null -ne $config.Volumes) {
    throw 'R7_IMAGE_DECLARED_VOLUMES_UNEXPECTED'
}
$ports = @($config.ExposedPorts.PSObject.Properties.Name | Sort-Object)
if ($ports.Count -ne 2 -or $ports[0] -cne '19103/tcp' -or
    $ports[1] -cne '19104/tcp') {
    throw 'R7_IMAGE_EXPOSED_PORTS_UNEXPECTED'
}
foreach ($entry in @($config.Env)) {
    if ([string]$entry -match '(?i)(SECRET|TOKEN|PASSWORD|CREDENTIAL|GRANT|PRIVATE_KEY|AUTHORIZATION)') {
        throw 'R7_IMAGE_SECRET_ENV_OR_OVERRIDE_DETECTED'
    }
}
Write-Host 'FORTIS_R7_REVIEW_IMAGE_METADATA_PASS'

$names = @(& docker ps -a --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0) {
    throw 'R7_CONTAINER_LIST_UNAVAILABLE'
}
if ($names -ccontains $smokeName -or
    @($names | Where-Object { $_ -match '^fortis-r7-' }).Count -ne 0) {
    throw 'R7_EXISTING_CANDIDATE_CONTAINER_REVIEW_REQUIRED'
}

Write-Host 'FORTIS_R7_SMOKE_BEGIN_NO_NETWORK_NO_MOUNTS_NO_PORTS'
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $result = (& docker run --rm --pull=never --name $smokeName --network none --read-only `
        --user '10001:10001' --cap-drop ALL --security-opt 'no-new-privileges:true' `
        --pids-limit 64 --memory 256m --cpus 1 `
        --tmpfs '/tmp:rw,nosuid,nodev,size=16m,mode=1777' `
        --entrypoint python $imageTag -B -m fortis_approvals.r7_unified_server preflight-imports 2>&1 |
        Out-String).Trim()
    $runExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
# A PowerShell 5.1 NativeCommandError warning can wrap stderr while the
# program exits 0. Require BOTH exact success markers as separate lines,
# but do not demand an exact merged stdout+stderr transcript.
if ($runExit -ne 0) {
    throw 'R7_IMAGE_IMPORT_SMOKE_EXIT_NONZERO'
}
if ($result -notmatch '(?m)^FORTIS_R7_UNIFIED_READ_ASK_IMPORTS_PASS\r?$') {
    throw 'R7_IMAGE_IMPORT_SMOKE_SUCCESS_MARKER_MISSING'
}
if ($result -notmatch '(?m)^FORTIS_R7_SONAR_POST=DISABLED\r?$') {
    throw 'R7_IMAGE_SONAR_WRITE_DISABLED_MARKER_MISSING'
}
Write-Host 'FORTIS_R7_UNIFIED_READ_ASK_IMPORTS_PASS'
Write-Host 'FORTIS_R7_SONAR_POST=DISABLED'

$after = @(& docker ps -a --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0 -or $after -ccontains $smokeName) {
    throw 'R7_SMOKE_TEMPORARY_CONTAINER_NOT_REMOVED'
}
Write-Host 'FORTIS_R7_DISPOSABLE_CONTAINER_AUTO_REMOVED_PASS'
Write-Host 'FORTIS_R7_REVIEW_IMAGE_IMPORT_SMOKE_PASS'
Write-Host 'FORTIS_R7_RUNNING_SERVICES_NOT_MODIFIED_BY_SCRIPT'
Write-Host 'FORTIS_R7_SONAR_NETWORK_REQUESTS=NONE'
Write-Host 'FORTIS_R7_SERVICE_TOKEN_PROVISIONED=NO'
Write-Host 'FORTIS_R7_REPO_GUARDS_PREVIEW=NOT_EXECUTED'
Write-Host 'FORTIS_R7_TRUSTED_ADMISSION=OPEN'
