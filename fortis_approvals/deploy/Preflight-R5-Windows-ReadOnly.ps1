# R5 Windows owner preflight. READ-ONLY; safe for the current working A3,
# Repo1/Repo2 tunnels, and G2/G4. No mutation or real Sonar request.
# PowerShell 5.1. Run only after reviewing this exact file and SHA256.
# Does NOT verify Guard Preview or authorize a Docker build/start.
$ErrorActionPreference = 'Stop'
$repoName = 'fortis-repo-test'
$a3Name = 'fortis-a3-synthetic-fortis-1'
$r5Volumes = @('fortis-r5-state', 'fortis-r5-identity',
               'fortis-r5-grant', 'fortis-r5-sonar-token')
$r5Ports = @(19103, 19104)

if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'R5_DOCKER_CLI_MISSING'
}
$dockerOS = (& docker info --format '{{.OSType}}' 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $dockerOS -cne 'linux') {
    throw 'R5_DOCKER_LINUX_ENGINE_UNAVAILABLE'
}
Write-Host 'FORTIS_R5_DOCKER_LINUX_ENGINE_PASS'

$allNames = @(& docker ps -a --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'R5_DOCKER_PS_ALL_FAILED' }
if ($allNames -cnotcontains $repoName -or $allNames -cnotcontains $a3Name) {
    throw 'R5_EXPECTED_EXISTING_CONTAINERS_MISSING'
}
if (@($allNames | Where-Object { $_ -match '^fortis-r5-' }).Count -ne 0) {
    throw 'R5_CANDIDATE_CONTAINER_ALREADY_EXISTS_REVIEW_REQUIRED'
}

function Read-InspectField([string]$name, [string]$field) {
    # Only metadata fields, never Config.Env, secrets or full inspect output.
    $format = '{{json .' + $field + '}}'
    $raw = (& docker inspect --type container --format $format $name 2>$null |
            Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $raw) {
        throw 'R5_DOCKER_METADATA_UNAVAILABLE'
    }
    $parsed = ConvertFrom-Json -InputObject $raw
    return $parsed
}

$repoState = Read-InspectField $repoName 'State'
$a3State = Read-InspectField $a3Name 'State'
if (-not $repoState.Running) { throw 'R5_REPO_CONNECTION_CONTAINER_NOT_RUNNING' }
if (-not $a3State.Running -or $a3State.Health.Status -cne 'healthy') {
    throw 'R5_A3_CONTAINER_NOT_HEALTHY'
}
Write-Host 'FORTIS_REPO_RUNNING_PASS'
Write-Host 'FORTIS_A3_RUNNING_HEALTHY_PASS'

$repoMounts = @(Read-InspectField $repoName 'Mounts')
$workspaceMount = @($repoMounts | Where-Object {
    $_.Type -ceq 'volume' -and $_.Name -ceq 'fortis-repo-workspace' -and
    $_.Destination -ceq '/workspace/repo'
})
if ($workspaceMount.Count -ne 1) {
    throw 'R5_REPO_WORKSPACE_VOLUME_UNEXPECTED'
}
foreach ($mount in $repoMounts) {
    $path = [string]$mount.Destination
    $name = [string]$mount.Name
    $source = [string]$mount.Source
    if (($path + ' ' + $name + ' ' + $source) -match
        '(?i)(docker[./\\]sock|fortis-(a3|r5)-(state|identity|grant|sonar-token)|/run/(a3|r5)-)') {
        throw 'R5_REPO_MOUNT_ISOLATION_FAILED'
    }
}
Write-Host 'FORTIS_REPO_WORKSPACE_AND_TRUSTED_MOUNT_ISOLATION_PASS'

$volumeNames = @(& docker volume ls --format '{{.Name}}' 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'R5_VOLUME_LIST_FAILED' }
foreach ($volume in $r5Volumes) {
    if ($volumeNames -ccontains $volume) {
        throw 'R5_RESERVED_VOLUME_ALREADY_EXISTS_REVIEW_REQUIRED'
    }
}
Write-Host 'FORTIS_R5_NEW_VOLUME_NAMES_AVAILABLE_PASS'

$runningNames = @(& docker ps --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'R5_RUNNING_CONTAINER_LIST_FAILED' }
foreach ($name in $runningNames) {
    $bindings = Read-InspectField $name 'HostConfig.PortBindings'
    if ($null -ne $bindings) {
        foreach ($entry in @($bindings.PSObject.Properties)) {
            foreach ($binding in @($entry.Value)) {
                foreach ($port in $r5Ports) {
                    if ([string]$binding.HostPort -ceq [string]$port) {
                        throw 'R5_PORT_ALREADY_PUBLISHED_BY_DOCKER'
                    }
                }
            }
        }
    }
}
Write-Host 'FORTIS_R5_DOCKER_PUBLISHED_PORTS_AVAILABLE_PASS'

if ($null -eq (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
    throw 'R5_WINDOWS_TCP_LISTENER_CHECK_UNAVAILABLE'
}
$listen = @(Get-NetTCPConnection -State Listen -ErrorAction Stop)
foreach ($port in $r5Ports) {
    if (@($listen | Where-Object { $_.LocalPort -eq $port }).Count -ne 0) {
        throw 'R5_WINDOWS_TCP_PORT_OCCUPIED'
    }
}
Write-Host 'FORTIS_R5_WINDOWS_TCP_PORTS_19103_19104_AVAILABLE_PASS'
Write-Host 'FORTIS_REPO_GUARD_REPO1_REPO2_PREVIEW=NOT_EXECUTED'
Write-Host 'FORTIS_R5_DOCKER_IMAGE_BUILD=NOT_EXECUTED'
Write-Host 'FORTIS_R5_TLS_GRANT_TOKEN_PROVISIONING=NOT_EXECUTED'
Write-Host 'FORTIS_R5_WINDOWS_READONLY_PREFLIGHT_PASS'
Write-Host 'FORTIS_R5_NEXT=OWNER_REVIEW_EXACT_DOCKER_BUILD_AND_GUARD_IMPACT'
