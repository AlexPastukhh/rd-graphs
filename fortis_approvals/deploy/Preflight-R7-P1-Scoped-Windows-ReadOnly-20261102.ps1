# P1 scoped R7 Windows owner preflight. READ-ONLY; safe for working A3,
# Repo1/Repo2 tunnels, and G2/G4. No mutation or real Sonar request.
# PowerShell 5.1. Run only after reviewing this exact file and SHA256.
# Does NOT verify Guard Preview or authorize Docker build/start/credential provisioning.
# Pins the exact owner-audited P1 scoped image; no secrets or Docker mutation.
$ErrorActionPreference = 'Stop'
$repoName = 'fortis-repo-test'
$a3Name = 'fortis-a3-synthetic-fortis-1'
$r7Volumes = @('fortis-r7-state', 'fortis-r7-identity',
               'fortis-r7-grant', 'fortis-r7-sonar-token')
$r7Ports = @(19103, 19104)
$p1Image = 'fortis-r7-unified-read-ask-candidate:review-p1-scoped-20261102-fac3131e'
$p1Id = 'sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4'

if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'R7_P1_SCOPED_DOCKER_CLI_MISSING'
}
$dockerOS = (& docker info --format '{{.OSType}}' 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $dockerOS -cne 'linux') {
    throw 'R7_P1_SCOPED_DOCKER_LINUX_ENGINE_UNAVAILABLE'
}
Write-Host 'FORTIS_R7_P1_SCOPED_DOCKER_LINUX_ENGINE_PASS'
# Read ONLY the exact immutable image ID; no full metadata or environment dump.
$id = (& docker image inspect --format '{{.Id}}' $p1Image 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $id -cne $p1Id) {
    throw 'R7_P1_SCOPED_EXACT_IMAGE_MISSING_OR_CHANGED'
}
Write-Host 'FORTIS_R7_P1_SCOPED_EXACT_IMAGE_PIN_PASS'


$allNames = @(& docker ps -a --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'R7_P1_SCOPED_DOCKER_PS_ALL_FAILED' }
if ($allNames -cnotcontains $repoName -or $allNames -cnotcontains $a3Name) {
    throw 'R7_P1_SCOPED_EXPECTED_EXISTING_CONTAINERS_MISSING'
}
if (@($allNames | Where-Object { $_ -match '^fortis-r7-' }).Count -ne 0) {
    throw 'R7_P1_SCOPED_CANDIDATE_CONTAINER_ALREADY_EXISTS_REVIEW_REQUIRED'
}

function Read-InspectField([string]$name, [string]$field) {
    # Only metadata fields, never Config.Env, secrets or full inspect output.
    $format = '{{json .' + $field + '}}'
    $raw = (& docker inspect --type container --format $format $name 2>$null |
            Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $raw) {
        throw 'R7_P1_SCOPED_DOCKER_METADATA_UNAVAILABLE'
    }
    $parsed = ConvertFrom-Json -InputObject $raw
    return $parsed
}

$repoState = Read-InspectField $repoName 'State'
$a3State = Read-InspectField $a3Name 'State'
if (-not $repoState.Running) { throw 'R7_P1_SCOPED_REPO_CONNECTION_CONTAINER_NOT_RUNNING' }
if (-not $a3State.Running -or $a3State.Health.Status -cne 'healthy') {
    throw 'R7_P1_SCOPED_A3_CONTAINER_NOT_HEALTHY'
}
Write-Host 'FORTIS_REPO_RUNNING_PASS'
Write-Host 'FORTIS_A3_RUNNING_HEALTHY_PASS'

$repoMounts = @(Read-InspectField $repoName 'Mounts')
$workspaceMount = @($repoMounts | Where-Object {
    $_.Type -ceq 'volume' -and $_.Name -ceq 'fortis-repo-workspace' -and
    $_.Destination -ceq '/workspace/repo'
})
if ($workspaceMount.Count -ne 1) {
    throw 'R7_P1_SCOPED_REPO_WORKSPACE_VOLUME_UNEXPECTED'
}
foreach ($mount in $repoMounts) {
    $path = [string]$mount.Destination
    $name = [string]$mount.Name
    $source = [string]$mount.Source
    if (($path + ' ' + $name + ' ' + $source) -match
        '(?i)(docker[./\\]sock|fortis-(a3|r5|r7)-(state|identity|grant|sonar-token)|/run/(a3|r5|r7)-)') {
        throw 'R7_P1_SCOPED_REPO_MOUNT_ISOLATION_FAILED'
    }
}
Write-Host 'FORTIS_REPO_WORKSPACE_AND_TRUSTED_MOUNT_ISOLATION_PASS'

$volumeNames = @(& docker volume ls --format '{{.Name}}' 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'R7_P1_SCOPED_VOLUME_LIST_FAILED' }
foreach ($volume in $r7Volumes) {
    if ($volumeNames -ccontains $volume) {
        throw 'R7_P1_SCOPED_RESERVED_VOLUME_ALREADY_EXISTS_REVIEW_REQUIRED'
    }
}
Write-Host 'FORTIS_R7_P1_SCOPED_NEW_VOLUME_NAMES_AVAILABLE_PASS'

$runningNames = @(& docker ps --format '{{.Names}}' 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'R7_P1_SCOPED_RUNNING_CONTAINER_LIST_FAILED' }
foreach ($name in $runningNames) {
    $bindings = Read-InspectField $name 'HostConfig.PortBindings'
    if ($null -ne $bindings) {
        foreach ($entry in @($bindings.PSObject.Properties)) {
            foreach ($binding in @($entry.Value)) {
                foreach ($port in $r7Ports) {
                    if ([string]$binding.HostPort -ceq [string]$port) {
                        throw 'R7_P1_SCOPED_PORT_ALREADY_PUBLISHED_BY_DOCKER'
                    }
                }
            }
        }
    }
}
Write-Host 'FORTIS_R7_P1_SCOPED_DOCKER_PUBLISHED_PORTS_AVAILABLE_PASS'

if ($null -eq (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
    throw 'R7_P1_SCOPED_WINDOWS_TCP_LISTENER_CHECK_UNAVAILABLE'
}
$listen = @(Get-NetTCPConnection -State Listen -ErrorAction Stop)
foreach ($port in $r7Ports) {
    if (@($listen | Where-Object { $_.LocalPort -eq $port }).Count -ne 0) {
        throw 'R7_P1_SCOPED_WINDOWS_TCP_PORT_OCCUPIED'
    }
}
Write-Host 'FORTIS_R7_P1_SCOPED_WINDOWS_TCP_PORTS_19103_19104_AVAILABLE_PASS'
Write-Host 'FORTIS_REPO_GUARD_REPO1_REPO2_PREVIEW=NOT_EXECUTED'
Write-Host 'FORTIS_R7_P1_SCOPED_IMAGE_REBUILD=NOT_EXECUTED'
Write-Host 'FORTIS_R7_P1_SCOPED_TLS_GRANT_TOKEN_PROVISIONING=NOT_EXECUTED'
Write-Host 'FORTIS_R7_P1_SCOPED_WINDOWS_READONLY_PREFLIGHT_PASS'
Write-Host 'FORTIS_R7_P1_SCOPED_LIVE_DEPLOYMENT=NOT_AUTHORIZED'
Write-Host 'FORTIS_R7_P1_SCOPED_NEW_VOLUMES_CREATED=NONE'
Write-Host 'FORTIS_R7_P1_SCOPED_NEXT=OWNER_GUARD_PREVIEW_AND_EXACT_TLS_GRANT_SONAR_TOKEN_PROVISIONING_REVIEW'
