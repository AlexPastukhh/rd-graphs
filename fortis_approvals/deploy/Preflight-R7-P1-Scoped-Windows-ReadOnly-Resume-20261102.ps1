# P1 scoped R7 read-only continuation preflight.
# Reuses the four owner-prepared R7 volumes; it NEVER creates, mounts or reads their contents.
# PowerShell 5.1. Pins the exact scoped image and owner-observed volume metadata.
# Does not run Guard Preview, provision credentials, start containers or deploy R7.
$ErrorActionPreference = 'Stop'
$repoName = 'fortis-repo-test'
$a3Name = 'fortis-a3-synthetic-fortis-1'
$p1Image = 'fortis-r7-unified-read-ask-candidate:review-p1-scoped-20261102-fac3131e'
$p1Id = 'sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4'
$r7Ports = @(19103, 19104)
$expectedVolumeMetadata = [ordered]@{
    'fortis-r7-state'       = 'fortis-r7-state|local|local|2026-11-01T08:15:45Z'
    'fortis-r7-identity'    = 'fortis-r7-identity|local|local|2026-11-01T08:15:46Z'
    'fortis-r7-grant'       = 'fortis-r7-grant|local|local|2026-11-01T08:15:46Z'
    'fortis-r7-sonar-token' = 'fortis-r7-sonar-token|local|local|2026-11-01T08:15:46Z'
}
$r7Volumes = @($expectedVolumeMetadata.Keys)

if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'R7_P1_SCOPED_DOCKER_CLI_MISSING'
}
$dockerOS = (& docker info --format '{{.OSType}}' 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $dockerOS -cne 'linux') {
    throw 'R7_P1_SCOPED_DOCKER_LINUX_ENGINE_UNAVAILABLE'
}
Write-Host 'FORTIS_R7_P1_SCOPED_DOCKER_LINUX_ENGINE_PASS'

# Inspect only the immutable image ID; do not dump full image metadata or environment.
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
    # Only the requested metadata field; never Config.Env, secrets or full inspect output.
    $format = '{{json .' + $field + '}}'
    $raw = (& docker inspect --type container --format $format $name 2>$null |
            Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $raw) {
        throw 'R7_P1_SCOPED_DOCKER_METADATA_UNAVAILABLE'
    }
    return (ConvertFrom-Json -InputObject $raw)
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

# The four volumes were prepared and state-preflighted previously (see current HANDOFF).
# Compare only name/driver/scope/CreatedAt and check attachment names; never inspect contents.
$volumeNames = @(& docker volume ls --format '{{.Name}}' 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'R7_P1_SCOPED_VOLUME_LIST_FAILED' }
$unexpectedR7Volumes = @($volumeNames | Where-Object {
    $_ -match '^fortis-r7-' -and $r7Volumes -cnotcontains $_
})
if ($unexpectedR7Volumes.Count -ne 0) {
    throw 'R7_P1_SCOPED_UNEXPECTED_R7_VOLUME_NAMES_REVIEW_REQUIRED'
}
foreach ($volume in $r7Volumes) {
    if ($volumeNames -cnotcontains $volume) {
        throw 'R7_P1_SCOPED_PREPARED_VOLUME_MISSING_REVIEW_REQUIRED'
    }
    $meta = (& docker volume inspect --format '{{.Name}}|{{.Driver}}|{{.Scope}}|{{.CreatedAt}}' $volume 2>$null |
             Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $meta -cne $expectedVolumeMetadata[$volume]) {
        throw 'R7_P1_SCOPED_PREPARED_VOLUME_METADATA_CHANGED_REVIEW_REQUIRED'
    }
    $refs = @(& docker ps -a --filter "volume=$volume" --format '{{.Names}}|{{.Status}}' 2>$null)
    if ($LASTEXITCODE -ne 0) { throw 'R7_P1_SCOPED_VOLUME_REFERENCE_CHECK_FAILED' }
    if ($refs.Count -ne 0) {
        throw 'R7_P1_SCOPED_PREPARED_VOLUME_ATTACHED_CONTAINER_REVIEW_REQUIRED'
    }
}
Write-Host 'FORTIS_R7_P1_SCOPED_EXISTING_VOLUME_METADATA_PASS'
Write-Host 'FORTIS_R7_P1_SCOPED_EXISTING_VOLUMES_UNATTACHED_PASS'
Write-Host 'FORTIS_R7_P1_SCOPED_VOLUME_STATE_PRIOR_ACCEPTANCE_REUSED=YES'

# Check Docker-published ports without changing containers or networks.
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

Write-Host 'FORTIS_R7_P1_SCOPED_GUARD_PREVIEW=NOT_EXECUTED'
Write-Host 'FORTIS_R7_P1_SCOPED_CREDENTIAL_PROVISIONING=NOT_EXECUTED'
Write-Host 'FORTIS_R7_P1_SCOPED_LIVE_DEPLOYMENT=NOT_AUTHORIZED'
Write-Host 'FORTIS_R7_P1_SCOPED_CONTAINERS_STARTED=NONE'
Write-Host 'FORTIS_R7_P1_SCOPED_VOLUME_CONTENTS_READ=NO'
Write-Host 'FORTIS_R7_P1_SCOPED_VOLUME_MUTATIONS=NONE'
Write-Host 'FORTIS_R7_P1_SCOPED_WINDOWS_READONLY_PREFLIGHT_PASS'
