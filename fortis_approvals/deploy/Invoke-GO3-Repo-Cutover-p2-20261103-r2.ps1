#requires -Version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

# GO-3 P2 only. No volume contents are read. R7 is never restarted by this script.
$CutoverId = '20261103-p2-20261103'
$OldName = 'fortis-repo-test'
$RollbackName = 'fortis-repo-test-go3-rollback-20261103-p2-20261103'
$ImageRef = 'fortis-repo-mode:dc-0.2.52'
$ImageId = 'sha256:2c84fabebb34265e53b020f21a11683a4c68cbb41a08f5f11f9b01c7de5ed8c9'
$OldContainerId = '0c0f8cb2d608679b4c3de51c527cbe2aca687cbf1360e6bf116444b2a0928cc2'
$R7ImageId = 'sha256:e751f6ca0cfe6ce290cf580de2f243071ee1f3e681baa8827c6cea41a16fa402'
$StateDir = Join-Path $env:LOCALAPPDATA 'Fortis\GO3-Cutover\20261103-p2-20261103'
$StatePath = Join-Path $StateDir 'go3-cutover-state.json'
$SnapshotPath = Join-Path $env:LOCALAPPDATA 'Fortis\GO3-Cutover\20261102-144258\fortis-repo-test.inspect.dpapi'
$SnapshotSha256 = '31d12e32e2f7cade1cb1f058e31e57b6819489bfb0b8d3888144d7507badcc74'
$EgressNetworkId = '65a8a1d816e3c6e5703d976d31514ecd657dfb14f5e5fafaba0e5208046e3ffd'
$InternalNetworkId = 'a4b5b7e37facafe180b5bb572ea3d228e3349b77f6babb760452708082566524'
$script:R7ContainerId = ''

if ($PSVersionTable.PSEdition -ne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
    throw 'STOP: Windows PowerShell 5.1 required'
}
$dockerCommand = Get-Command docker.exe -CommandType Application | Select-Object -First 1
if ($null -eq $dockerCommand -or -not (Test-Path -LiteralPath $dockerCommand.Source -PathType Leaf)) {
    throw 'STOP: docker.exe not found'
}
$script:DockerExe = $dockerCommand.Source

function Invoke-DockerText {
    param([string[]]$Arguments)
    $lines = @(& $script:DockerExe @Arguments 2>&1)
    $exitCode = $LASTEXITCODE
    $text = ($lines | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    if ($exitCode -ne 0) {
        throw ("docker {0} failed with exit {1}: {2}" -f ($Arguments -join ' '),$exitCode,$text)
    }
    return $text.Trim()
}
function Get-DockerLines {
    param([string[]]$Arguments)
    $text = Invoke-DockerText -Arguments $Arguments
    if ([string]::IsNullOrWhiteSpace($text)) { return @() }
    return @($text -split '\r?\n' | Where-Object { $_.Trim() })
}
function Get-DockerJson {
    param([string[]]$Arguments)
    return ((Invoke-DockerText -Arguments $Arguments) | ConvertFrom-Json)
}
function Get-Prop {
    param($Object,[string]$Name,$Default='')
    if ($null -eq $Object) { return $Default }
    $p = $Object.PSObject.Properties[$Name]
    if ($null -eq $p -or $null -eq $p.Value) { return $Default }
    return $p.Value
}
function Assert-Equal {
    param($Actual,$Expected,[string]$Label)
    if ([string]$Actual -cne [string]$Expected) {
        throw ("STOP: {0} mismatch: actual='{1}' expected='{2}'" -f $Label,$Actual,$Expected)
    }
}
function Assert-Set {
    param([string[]]$Actual,[string[]]$Expected,[string]$Label)
    $a=@($Actual | Sort-Object -CaseSensitive); $e=@($Expected | Sort-Object -CaseSensitive)
    if ($a.Count -ne $e.Count -or (Compare-Object -ReferenceObject $e -DifferenceObject $a -CaseSensitive)) {
        throw ("STOP: {0} mismatch: actual=[{1}] expected=[{2}]" -f $Label,($a -join ';'),($e -join ';'))
    }
}
function Get-EffectiveMounts {
    param($Info)
    $m=@($Info.Mounts | Where-Object { $_.Type -cne 'tmpfs' })
    return @($m | ForEach-Object { '{0}|{1}|{2}|rw={3}' -f $_.Type,$_.Name,$_.Destination,$_.RW })
}
function Get-RequestedMounts {
    param($Info)
    $m=@($Info.HostConfig.Mounts | Where-Object { $null -ne $_ })
    return @($m | ForEach-Object {
        $sub=[string](Get-Prop $_.VolumeOptions 'Subpath' '')
        $ro=$false
        $rp=$_.PSObject.Properties['ReadOnly']
        if ($null -ne $rp -and $rp.Value -eq $true) { $ro=$true }
        '{0}|{1}|{2}|ro={3}|subpath={4}' -f $_.Type,$_.Source,$_.Target,$ro,$sub
    })
}
function Get-Count {
    param($Value)
    if ($null -eq $Value) { return 0 }
    $items=@($Value | Where-Object { $null -ne $_ })
    return $items.Count
}
function Get-ObjectPropertyCount {
    param($Value)
    if ($null -eq $Value) { return 0 }
    $properties=@($Value.PSObject.Properties)
    return $properties.Count
}
function Assert-RepoPolicy {
    param($Info,$ImageInfo,[bool]$WithClient)
    Assert-Equal $Info.Image $ImageId 'Repo image ID'
    Assert-Equal $Info.Config.User '1000:1000' 'Repo UID'
    Assert-Equal $Info.Config.WorkingDir '/workspace/repos' 'Repo working directory'
    if ($Info.HostConfig.ReadonlyRootfs -ne $true) { throw 'STOP: Repo rootfs is not read-only' }
    if ($Info.HostConfig.Privileged -ne $false) { throw 'STOP: Repo privileged flag changed' }
    Assert-Set @($Info.HostConfig.CapDrop) @('ALL') 'Repo CapDrop'
    if ((Get-Count $Info.HostConfig.CapAdd) -ne 0) { throw 'STOP: Repo CapAdd is non-empty' }
    if ((Get-Count $Info.HostConfig.Binds) -ne 0) { throw 'STOP: Repo bind mounts are forbidden' }
    if ((Get-Count $Info.HostConfig.VolumesFrom) -ne 0) { throw 'STOP: Repo volumes-from is forbidden' }
    if ((Get-Count $Info.HostConfig.Devices) -ne 0 -or (Get-Count $Info.HostConfig.DeviceRequests) -ne 0) { throw 'STOP: Repo devices are forbidden' }
    $securityOptions=@($Info.HostConfig.SecurityOpt | Where-Object { $null -ne $_ })
    if ($securityOptions.Count -ne 1 -or $securityOptions[0] -notmatch '^no-new-privileges(:true)?$') {
        throw 'STOP: SecurityOpt must contain exactly one no-new-privileges option and no extras'
    }
    Assert-Equal $Info.HostConfig.NetworkMode 'fortis-repo-egress' 'Repo primary network'
    Assert-Equal $Info.HostConfig.RestartPolicy.Name 'unless-stopped' 'Repo restart policy'
    Assert-Equal $Info.HostConfig.RestartPolicy.MaximumRetryCount 0 'Repo restart retries'
    Assert-Equal $Info.HostConfig.Memory 4294967296 'Repo memory'
    Assert-Equal $Info.HostConfig.MemorySwap 5368709120 'Repo memory+swap'
    Assert-Equal $Info.HostConfig.NanoCpus 2000000000 'Repo CPU'
    Assert-Equal $Info.HostConfig.PidsLimit 512 'Repo PIDs'
    Assert-Equal $Info.HostConfig.ShmSize 67108864 'Repo shm'
    Assert-Equal $Info.HostConfig.MemoryReservation 0 'Repo memory reservation'
    Assert-Equal $Info.HostConfig.CpuShares 0 'Repo CPU shares'
    Assert-Equal $Info.HostConfig.CpuQuota 0 'Repo CPU quota'
    Assert-Equal $Info.HostConfig.CpuPeriod 0 'Repo CPU period'
    Assert-Equal $Info.HostConfig.OomScoreAdj 0 'Repo OOM score adjustment'
    if ($null -ne $Info.HostConfig.OomKillDisable) { throw 'STOP: Repo OOM kill override must remain unset' }
    Assert-Equal $Info.HostConfig.IpcMode 'private' 'Repo IPC'
    Assert-Equal $Info.HostConfig.CgroupnsMode 'private' 'Repo cgroup namespace'
    Assert-Equal ([string](Get-Prop $Info.HostConfig 'PidMode' '')) '' 'Repo PID namespace mode'
    Assert-Equal ([string](Get-Prop $Info.HostConfig 'UtsMode' '')) '' 'Repo UTS namespace mode'
    Assert-Equal ([string](Get-Prop $Info.HostConfig 'UsernsMode' '')) '' 'Repo user namespace mode'
    Assert-Equal $Info.HostConfig.Runtime 'runc' 'Repo runtime'
    Assert-Equal $Info.HostConfig.LogConfig.Type 'json-file' 'Repo log driver'
    if ($Info.HostConfig.AutoRemove -ne $false) { throw 'STOP: Repo AutoRemove must be false' }
    $portProperties=@()
    if ($null -ne $Info.HostConfig.PortBindings) { $portProperties=@($Info.HostConfig.PortBindings.PSObject.Properties) }
    if ($portProperties.Count -ne 0) { throw 'STOP: Repo published ports forbidden' }
    if ($Info.HostConfig.PublishAllPorts -ne $false) { throw 'STOP: Repo PublishAllPorts must be false' }
    if ((Get-Count $Info.HostConfig.ExtraHosts) -ne 0) { throw 'STOP: Repo ExtraHosts must be empty' }
    if ((Get-ObjectPropertyCount $Info.HostConfig.Sysctls) -ne 0) { throw 'STOP: Repo Sysctls must be empty' }
    if ((Get-Count $Info.HostConfig.Ulimits) -ne 0) { throw 'STOP: Repo Ulimits must be empty' }
    if ((Get-ObjectPropertyCount $Info.HostConfig.LogConfig.Config) -ne 0) { throw 'STOP: Repo LogConfig.Config must be empty' }
    Assert-Equal ([string](Get-Prop $Info.HostConfig.Tmpfs '/tmp' '')) 'rw,nosuid,nodev,noexec,mode=1777,size=128m' 'Repo /tmp tmpfs'
    Assert-Equal ([string](Get-Prop $Info.HostConfig.Tmpfs '/home/node' '')) 'rw,nosuid,nodev,noexec,uid=1000,gid=1000,mode=700,size=128m' 'Repo /home/node tmpfs'
    $tmpfsProperties=@($Info.HostConfig.Tmpfs.PSObject.Properties)
    Assert-Equal $tmpfsProperties.Count 2 'Repo tmpfs count'
    Assert-Equal (ConvertTo-Json -InputObject @($Info.Config.Env) -Compress -Depth 8) (ConvertTo-Json -InputObject @($ImageInfo.Config.Env) -Compress -Depth 8) 'Repo environment defaults'
    Assert-Equal (ConvertTo-Json -InputObject $Info.Config.Entrypoint -Compress -Depth 8) (ConvertTo-Json -InputObject $ImageInfo.Config.Entrypoint -Compress -Depth 8) 'Repo entrypoint defaults'
    Assert-Equal (ConvertTo-Json -InputObject $Info.Config.Cmd -Compress -Depth 8) (ConvertTo-Json -InputObject $ImageInfo.Config.Cmd -Compress -Depth 8) 'Repo command defaults'

    $effective=@(
        'volume|fortis-repo-workspace|/workspace/files|rw=True'
        'volume|fortis-repo-workspace|/workspace/repo|rw=True'
        'volume|fortis-repo-workspace|/workspace/repos|rw=True'
    )
    $requested=@(
        'volume|fortis-repo-workspace|/workspace/repo|ro=False|subpath='
        'volume|fortis-repo-workspace|/workspace/repos|ro=False|subpath=Repos'
        'volume|fortis-repo-workspace|/workspace/files|ro=False|subpath=Workfiles'
    )
    if ($WithClient) {
        $effective += 'volume|fortis-r7-client|/run/fortis-client|rw=False'
        $requested += 'volume|fortis-r7-client|/run/fortis-client|ro=True|subpath='
    }
    Assert-Set (Get-EffectiveMounts $Info) $effective 'Repo effective mounts'
    Assert-Set (Get-RequestedMounts $Info) $requested 'Repo requested mounts'
    Assert-Set @($Info.NetworkSettings.Networks.PSObject.Properties.Name) @('fortis-repo-egress','rdg-personal_agents') 'Repo networks'
}
function Assert-Networks {
    $e=Get-DockerJson @('network','inspect','--format','{{json .}}','fortis-repo-egress')
    $i=Get-DockerJson @('network','inspect','--format','{{json .}}','rdg-personal_agents')
    Assert-Equal $e.Id $EgressNetworkId 'fortis-repo-egress ID'
    Assert-Equal $e.Internal $false 'fortis-repo-egress Internal'
    Assert-Equal $i.Id $InternalNetworkId 'rdg-personal_agents ID'
    Assert-Equal $i.Internal $true 'rdg-personal_agents Internal'
}
function Assert-Volumes {
    foreach ($name in @('fortis-repo-workspace','fortis-r7-state','fortis-r7-identity','fortis-r7-grant','fortis-r7-sonar-token','fortis-r7-client')) {
        $v=Get-DockerJson @('volume','inspect','--format','{{json .}}',$name)
        Assert-Equal $v.Name $name ("volume " + $name)
        Assert-Equal $v.Driver 'local' ("driver " + $name)
        Assert-Equal $v.Scope 'local' ("scope " + $name)
    }
    $c=Get-DockerJson @('volume','inspect','--format','{{json .}}','fortis-r7-client')
    Assert-Equal (Get-Prop $c.Labels 'com.fortis.r7.p1.role' '') 'client-only' 'client volume role'
    if ([string](Get-Prop $c.Labels 'com.fortis.r7.p1.provision-id' '') -notmatch '^[0-9a-fA-F]{32}$') { throw 'STOP: client provision ID invalid' }
    $attached=Get-DockerLines @('ps','-a','--no-trunc','--filter','volume=fortis-r7-client','--format','{{.ID}}')
    if ($attached.Count -ne 0) { throw 'STOP: client volume already attached' }
}
function Assert-R7 {
    $ids=Get-DockerLines @('ps','-a','--no-trunc','--filter','label=com.docker.compose.project=fortis-r7-p1','--filter','label=com.docker.compose.service=fortis','--format','{{.ID}}')
    if ($ids.Count -ne 1) { throw 'STOP: expected exactly one R7 service container' }
    if ([string]::IsNullOrWhiteSpace($script:R7ContainerId)) { $script:R7ContainerId=$ids[0] }
    else { Assert-Equal $ids[0] $script:R7ContainerId 'R7 container ID unchanged' }
    $r=Get-DockerJson @('inspect','--type','container','--format','{{json .}}',$ids[0])
    if ($r.State.Running -ne $true) { throw 'STOP: R7 is not running' }
    Assert-Equal $r.State.Health.Status 'healthy' 'R7 health'
    Assert-Equal $r.Image $R7ImageId 'R7 image ID'
    Assert-Set (Get-EffectiveMounts $r) @(
        'volume|fortis-r7-state|/state|rw=True'
        'volume|fortis-r7-grant|/run/r7-grant|rw=False'
        'volume|fortis-r7-identity|/run/r7-identity|rw=False'
        'volume|fortis-r7-sonar-token|/run/r7-sonar-token|rw=False'
    ) 'R7 mounts'
    Assert-Set @($r.HostConfig.Binds) @(
        'fortis-r7-state:/state:rw'
        'fortis-r7-identity:/run/r7-identity:ro'
        'fortis-r7-grant:/run/r7-grant:ro'
        'fortis-r7-sonar-token:/run/r7-sonar-token:ro'
    ) 'R7 binds'
}
function Save-State {
    param($State)
    $json=ConvertTo-Json -InputObject $State -Depth 8
    $tmp=$StatePath + '.tmp'
    $encoding=New-Object -TypeName System.Text.UTF8Encoding -ArgumentList $false
    [System.IO.File]::WriteAllText($tmp,$json,$encoding)
    if (Test-Path -LiteralPath $StatePath) { [System.IO.File]::Replace($tmp,$StatePath,$null) }
    else { [System.IO.File]::Move($tmp,$StatePath) }
}

# Read-only preflight; no Docker mutation before the explicit confirmation.
if (-not (Test-Path -LiteralPath $SnapshotPath -PathType Leaf)) { throw 'STOP: DPAPI rollback snapshot missing' }
if (-not (Test-Path -LiteralPath $StateDir -PathType Container)) {
    $null = New-Item -ItemType Directory -Path $StateDir -Force
}
$snapshotHash=(Get-FileHash -LiteralPath $SnapshotPath -Algorithm SHA256).Hash.ToLowerInvariant()
Assert-Equal $snapshotHash $SnapshotSha256 'DPAPI snapshot SHA256'
if (Test-Path -LiteralPath $StatePath) { throw 'STOP: GO-3 state file already exists' }

$rollbackMatches=Get-DockerLines @('ps','-a','--no-trunc','--filter',("name=^/{0}$" -f $RollbackName),'--format','{{.ID}}')
if ($rollbackMatches.Count -ne 0) { throw 'STOP: rollback name already exists' }
$oldId=Invoke-DockerText @('inspect','--type','container','--format','{{.Id}}',$OldName)
Assert-Equal $oldId $OldContainerId 'existing Repo full ID'
$old=Get-DockerJson @('inspect','--type','container','--format','{{json .}}',$OldName)
if ($old.State.Running -ne $true) { throw 'STOP: existing Repo is not running' }
$imageId=Invoke-DockerText @('image','inspect','--format','{{.Id}}',$ImageRef)
Assert-Equal $imageId $ImageId 'local image tag->ID'
$imageInfo=Get-DockerJson @('image','inspect','--format','{{json .}}',$ImageRef)
Assert-RepoPolicy $old $imageInfo $false
Assert-Networks
Assert-Volumes
Assert-R7
$diff=Get-DockerLines @('diff',$OldContainerId)
Assert-Set $diff @('C /workspace','A /workspace/repos','A /workspace/files') 'Repo writable-layer diff'

Write-Output 'GO3_CUTOVER_READONLY_PREFLIGHT_PASS'
Write-Output 'OLD_REPO_POLICY_IMAGE_NETWORK_VOLUME_R7_SNAPSHOT_PASS'
Write-Output 'NO_VOLUME_CONTENT_READ'
Write-Output 'NO_SONAR_REQUEST'
$confirmation=Read-Host 'Type RECREATE-FORTIS-REPO to authorize GO-3 cutover'
if ($confirmation -cne 'RECREATE-FORTIS-REPO') {
    Write-Output 'CUTOVER_NOT_AUTHORIZED'
    return
}

$script:CutoverState=[ordered]@{
    Schema=1; CutoverId=$CutoverId; OldName=$OldName; RollbackName=$RollbackName
    OldContainerId=$OldContainerId; NewContainerId=''; R7ContainerId=$script:R7ContainerId; ImageRef=$ImageRef; ImageId=$ImageId
    SnapshotPath=$SnapshotPath; SnapshotSha256=$SnapshotSha256
    Phase='PreflightPassed'; UpdatedAt=(Get-Date).ToString('o')
}
Save-State $script:CutoverState

try {
    Invoke-DockerText @('stop','--time','30',$OldName) | Out-Null
    $stopped=Get-DockerJson @('inspect','--type','container','--format','{{json .}}',$OldName)
    if ($stopped.State.Running -ne $false) { throw 'STOP: old Repo did not stop' }
    $script:CutoverState.Phase='OldStopped'; $script:CutoverState.UpdatedAt=(Get-Date).ToString('o'); Save-State $script:CutoverState

    Invoke-DockerText @('rename',$OldName,$RollbackName) | Out-Null
    $preserved=Get-DockerJson @('inspect','--type','container','--format','{{json .}}',$RollbackName)
    Assert-Equal $preserved.Id $OldContainerId 'preserved old Repo ID'
    if ($preserved.State.Running -ne $false) { throw 'STOP: old rollback Repo is running' }
    $script:CutoverState.Phase='OldRenamed'; $script:CutoverState.UpdatedAt=(Get-Date).ToString('o'); Save-State $script:CutoverState

    $createArgs=@(
        'create','--pull=never','--name',$OldName,
        '--user','1000:1000','--workdir','/workspace/repos',
        '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--network','fortis-repo-egress','--restart','unless-stopped',
        '--memory','4g','--memory-swap','5g','--cpus','2','--pids-limit','512','--shm-size','64m',
        '--ipc','private','--cgroupns','private','--runtime','runc','--log-driver','json-file',
        '--tmpfs','/home/node:rw,nosuid,nodev,noexec,uid=1000,gid=1000,mode=700,size=128m',
        '--tmpfs','/tmp:rw,nosuid,nodev,noexec,mode=1777,size=128m',
        '--mount','type=volume,source=fortis-repo-workspace,target=/workspace/repo',
        '--mount','type=volume,source=fortis-repo-workspace,target=/workspace/repos,volume-subpath=Repos',
        '--mount','type=volume,source=fortis-repo-workspace,target=/workspace/files,volume-subpath=Workfiles',
        '--mount','type=volume,source=fortis-r7-client,target=/run/fortis-client,readonly',
        $ImageRef
    )
    $newId=Invoke-DockerText $createArgs
    if ($newId -notmatch '^[0-9a-f]{64}$') { throw 'STOP: docker create did not return one full ID' }
    $script:CutoverState.NewContainerId=$newId
    $script:CutoverState.Phase='ReplacementCreated'
    $script:CutoverState.UpdatedAt=(Get-Date).ToString('o')
    Save-State $script:CutoverState

    Invoke-DockerText @('network','connect','rdg-personal_agents',$newId) | Out-Null
    $new=Get-DockerJson @('inspect','--type','container','--format','{{json .}}',$newId)
    if ($new.State.Running -ne $false) { throw 'STOP: replacement must be inspected before start' }
    Assert-RepoPolicy $new $imageInfo $true
    $script:CutoverState.Phase='ReplacementCreatedAndVerified'
    $script:CutoverState.UpdatedAt=(Get-Date).ToString('o')
    Save-State $script:CutoverState

    Invoke-DockerText @('start',$newId) | Out-Null
    $running=Get-DockerJson @('inspect','--type','container','--format','{{json .}}',$newId)
    if ($running.State.Running -ne $true) { throw 'STOP: replacement Repo did not start' }
    Assert-RepoPolicy $running $imageInfo $true
    Assert-R7
    $preserved=Get-DockerJson @('inspect','--type','container','--format','{{json .}}',$RollbackName)
    Assert-Equal $preserved.Id $OldContainerId 'retained rollback Repo ID'
    if ($preserved.State.Running -ne $false) { throw 'STOP: old rollback Repo unexpectedly running' }
    $clientAttached=Get-DockerLines @('ps','-a','--no-trunc','--filter','volume=fortis-r7-client','--format','{{.ID}}')
    Assert-Set $clientAttached @($newId) 'client volume attachment'
    $script:CutoverState.Phase='ReplacementRunningVerified'
    $script:CutoverState.UpdatedAt=(Get-Date).ToString('o')
    Save-State $script:CutoverState

    Write-Output 'GO3_REPO_RECREATE_AND_CLIENT_RO_MOUNT_PASS'
    Write-Output ("NEW_REPO_CONTAINER_ID=" + $newId)
    Write-Output ("ROLLBACK_REPO_CONTAINER_ID=" + $OldContainerId)
    Write-Output 'OLD_REPO_PRESERVED_STOPPED=YES'
    Write-Output 'R7_UNCHANGED_HEALTHY=YES'
    Write-Output 'GUARD_PREVIEWS_AND_REPO_RECONNECT_PENDING'
    Write-Output 'SONAR_REQUESTS=NONE'
    Write-Output 'SONAR_POST=0'
}
catch {
    Write-Output 'GO3_CUTOVER_FAILED_STOP'
    Write-Output ("LAST_RECORDED_PHASE=" + $script:CutoverState.Phase)
    Write-Output ("ROLLBACK_SCRIPT=" + (Join-Path $PSScriptRoot 'Restore-GO3-Repo-Rollback.ps1'))
    Write-Output 'Do not remove volumes or restart R7. Review the state file before rollback.'
    throw
}
