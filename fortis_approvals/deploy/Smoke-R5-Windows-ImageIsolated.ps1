# R5 image import smoke on OWNER Windows Docker (PowerShell 5.1).
# Creates ONE disposable container (--rm) with NO network, volumes, ports
# or secrets. Does NOT run the default Fortis server or install R5.
# No changes to A3, G2/G4, Fortis Repo or Repo1/Repo2 launchers.
# Requires exact owner-reported Windows image ID; fail closed otherwise.
$ErrorActionPreference = 'Stop'
$imageTag = 'fortis-r5-sonar-read-candidate:review-20261101-e6aec453'
$expectedId = 'sha256:5fa986d7e532639c5461a87e4a2c34ea8176ec58371f418758d0cd5dfc38bd02'
$smokeName = 'fortis-r5-import-smoke-20261101'

if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'R5_DOCKER_CLI_REQUIRED'
}
$engine = (& docker info --format '{{.OSType}}' 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $engine -cne 'linux') {
    throw 'R5_LINUX_DOCKER_ENGINE_REQUIRED'
}
$id = (& docker image inspect --format '{{.Id}}' $imageTag 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $id -cne $expectedId) {
    throw 'R5_IMAGE_ID_MISMATCH_STOP'
}
Write-Host 'FORTIS_R5_REVIEW_IMAGE_ID_MATCH_PASS'

# Inspect image metadata only; never print Env entries or private values.
$cfgRaw = (& docker image inspect --format '{{json .Config}}' $imageTag 2>$null |
           Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $cfgRaw) {
    throw 'R5_IMAGE_CONFIG_INSPECT_FAILED'
}
$config = ConvertFrom-Json -InputObject $cfgRaw
if ([string]$config.User -cne '10001:10001') {
    throw 'R5_IMAGE_USER_UNEXPECTED'
}
if ($null -ne $config.Entrypoint -and @($config.Entrypoint).Count -gt 0) {
    throw 'R5_IMAGE_ENTRYPOINT_UNEXPECTED'
}
$cmd = @($config.Cmd)
if ($cmd.Count -ne 3 -or $cmd[0] -cne 'python' -or
    $cmd[1] -cne '-m' -or $cmd[2] -cne 'fortis_approvals.r5_read_server') {
    throw 'R5_IMAGE_DEFAULT_CMD_UNEXPECTED'
}
if ($null -ne $config.Volumes) {
    throw 'R5_IMAGE_DECLARED_VOLUMES_UNEXPECTED'
}
$ports = @($config.ExposedPorts.PSObject.Properties.Name | Sort-Object)
if ($ports.Count -ne 2 -or $ports[0] -cne '19103/tcp' -or
    $ports[1] -cne '19104/tcp') {
    throw 'R5_IMAGE_EXPOSED_PORTS_UNEXPECTED'
}
foreach ($entry in @($config.Env)) {
    # No service credentials, caller grant, owner proof or trust-bound
    # host overrides may be baked into this review image configuration.
    if ([string]$entry -match '(?i)(SECRET|TOKEN|PASSWORD|CREDENTIAL|GRANT|PRIVATE_KEY|AUTHORIZATION)') {
        throw 'R5_IMAGE_SECRET_ENV_OR_OVERRIDE_DETECTED'
    }
}
Write-Host 'FORTIS_R5_REVIEW_IMAGE_METADATA_PASS'

$names = @(& docker ps -a --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0) {
    throw 'R5_CONTAINER_LIST_UNAVAILABLE'
}
if ($names -ccontains $smokeName -or
    @($names | Where-Object { $_ -match '^fortis-r5-' }).Count -ne 0) {
    throw 'R5_EXISTING_CANDIDATE_CONTAINER_REVIEW_REQUIRED'
}
Write-Host 'FORTIS_R5_SMOKE_BEGIN_NO_NETWORK_NO_MOUNTS_NO_PORTS'

# The only Docker mutation: temporary container auto-removed on exit.
# --entrypoint overrides default server; preflight-imports does not access
# state/secret paths or make outbound Sonar requests.
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $output = (& docker run --rm --pull=never --name $smokeName --network none --read-only `
        --user '10001:10001' --cap-drop ALL --security-opt 'no-new-privileges:true' `
        --pids-limit 64 --memory 256m --cpus 1 `
        --tmpfs '/tmp:rw,nosuid,nodev,size=16m,mode=1777' `
        --entrypoint python $imageTag -B -m fortis_approvals.r5_read_server preflight-imports 2>&1 |
        Out-String).Trim()
    $runExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
if ($runExit -ne 0 -or $output -cne 'FORTIS_R5_SONAR_READ_IMPORTS_PASS') {
    throw 'R5_IMAGE_IMPORT_SMOKE_FAILED_REVIEW_DOCKER_OUTPUT_LOCALLY'
}
Write-Host $output

$namesAfter = @(& docker ps -a --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0 -or $namesAfter -ccontains $smokeName) {
    throw 'R5_SMOKE_CONTAINER_NOT_REMOVED'
}
Write-Host 'FORTIS_R5_DISPOSABLE_CONTAINER_AUTO_REMOVED_PASS'
Write-Host 'FORTIS_R5_REVIEW_IMAGE_IMPORT_SMOKE_PASS'
Write-Host 'FORTIS_R5_RUNNING_SERVICES_NOT_MODIFIED_BY_SCRIPT'
Write-Host 'FORTIS_R5_SONAR_NETWORK_REQUESTS=NONE'
Write-Host 'FORTIS_R5_SERVICE_TOKEN_PROVISIONED=NO'
Write-Host 'FORTIS_R5_REPO_GUARDS_PREVIEW=NOT_EXECUTED'
Write-Host 'FORTIS_R5_TRUSTED_ADMISSION=OPEN'
