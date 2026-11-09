[CmdletBinding()]
param(
    [ValidateSet('Local', 'HTTPS')][string]$Mode = 'Local',
    [string]$Domain,
    [string]$AgentContainer,
    [string]$SecretsDirectory = (Join-Path $env:LOCALAPPDATA 'RDG-Server\secrets'),
    [string]$PackageDirectory = $PSScriptRoot,
    [switch]$SkipSetup
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$packageRoot = [IO.Path]::GetFullPath($PackageDirectory)
Set-Location -LiteralPath $packageRoot
if (-not (Test-Path -LiteralPath (Join-Path $packageRoot 'BUILD.json'))) {
    throw 'Use the complete extracted RDG-Server package.'
}
function Invoke-RDGDocker {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) {
        if ($DockerArgs -contains 'up') {
            & docker @compose ps
            & docker @compose logs --tail 35 --no-color rdg-api-gateway proxy
        }
        throw ('Docker failed: ' + ($DockerArgs -join ' '))
    }
}
$engine = & docker info --format '{{.OSType}}'
if ($LASTEXITCODE -ne 0 -or $engine.Trim() -ne 'linux') {
    throw 'Start Docker with Linux containers, then run this script again.'
}
if ($Mode -eq 'HTTPS') {
    if ($Domain -notmatch '^(?=.{1,253}$)([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$') {
        throw 'HTTPS mode needs a DNS name, for example rdg.example.com.'
    }
    $origin = 'https://' + $Domain.ToLowerInvariant()
    $override = 'compose.https.yaml'
} else {
    $origin = 'http://localhost:18880'
    $Domain = ''
    $override = 'compose.local.yaml'
}
$manifest = Get-Content -Raw -LiteralPath '.\BUILD.json' | ConvertFrom-Json
$imageTag = '20261029'
if ($manifest.PSObject.Properties.Name -contains 'imageTag') { $imageTag = $manifest.imageTag }
if ($imageTag -notmatch '^[a-z0-9][a-z0-9-]{0,110}$') { throw 'Invalid runtime image tag.' }
$runtimeImage = 'rdg-personal-server:' + $imageTag
foreach ($property in $manifest.files.PSObject.Properties) {
    $actual = (Get-FileHash -LiteralPath (Join-Path $packageRoot $property.Name) -Algorithm SHA256).Hash
    if ($actual -ne $property.Value) { throw ('Package hash mismatch: ' + $property.Name) }
}
$utf8 = New-Object System.Text.UTF8Encoding($false)
New-Item -ItemType Directory -Path $SecretsDirectory -Force | Out-Null
$setupPath = [IO.Path]::GetFullPath($SecretsDirectory).Replace('\', '/')
if ($setupPath -match "['`r`n]") { throw 'Choose a secrets directory without quotes or newlines.' }
$agentId = ''
if ($AgentContainer) {
    $inspectFormat = '{{.Id}}|{{.State.Running}}|{{.HostConfig.Privileged}}|{{.HostConfig.PidMode}}'
    $agentInfoRaw = & docker inspect --type container --format $inspectFormat $AgentContainer
    if ($LASTEXITCODE -ne 0) { throw 'The selected agent container was not found.' }
    $agentFields = $agentInfoRaw.Trim() -split '\|', 4
    if ($agentFields.Count -ne 4 -or $agentFields[1] -ne 'true' -or $agentFields[2] -ne 'false' -or $agentFields[3] -notin @('', 'private')) {
        throw 'Use a running agent container without privileged mode or a shared PID namespace.'
    }
    $mountsRaw = & docker inspect --type container --format '{{json .Mounts}}' $AgentContainer
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the selected agent container mounts.' }
    $agentMounts = $mountsRaw | ConvertFrom-Json
    foreach ($mount in $agentMounts) {
        $source = $mount.Source.Replace('\', '/').TrimEnd('/').ToLowerInvariant()
        $destination = $mount.Destination.Replace('\', '/').ToLowerInvariant()
        if ($destination -match '(^|/)docker\.sock$' -or $source -match '(^|/)docker\.sock$') {
            throw 'The agent container must not have the Docker socket.'
        }
        if ($mount.Type -eq 'volume' -and $mount.Name -in @('rdg-personal_rdg_gateway_secret', 'rdg-personal_rdg_data')) {
            throw 'The agent container must not mount RDG data or gateway credentials.'
        }
        if ($mount.Type -eq 'bind') {
            if ($source -match '^/(?:run/desktop/mnt/host|host_mnt)/([a-z])/(.*)$') {
                $source = $Matches[1] + ':/' + $Matches[2]
            }
            $privatePath = $setupPath.TrimEnd('/').ToLowerInvariant()
            if (-not $source -or $privatePath -eq $source -or $privatePath.StartsWith($source + '/')) {
                throw 'The agent container has a host bind mount that includes the RDG secrets directory.'
            }
        }
    }
    $agentId = $agentFields[0]
    $storageCheck = "import os,tempfile,urllib.request; fd,p=tempfile.mkstemp(prefix='rdg-gateway-check-',dir='/workspace/repo/Workfiles'); os.write(fd,b'rdg-check'); os.fsync(fd); os.close(fd); os.unlink(p); print('Agent workspace check: OK')"
    & docker exec --user 1000:1000 $agentId python3 -c $storageCheck
    if ($LASTEXITCODE -ne 0) { throw 'Restore writable Docker storage before starting the gateway.' }
}
[IO.File]::WriteAllText((Join-Path $packageRoot '.env'), "RDG_PUBLIC_ORIGIN=$origin`nRDG_DOMAIN=$Domain`nRDG_IMAGE_TAG=$imageTag`nRDG_SETUP_DIR='$setupPath'`n", $utf8)
$compose = @('compose', '--project-name', 'rdg-personal', '-f', 'compose.yaml', '-f', $override)
Invoke-RDGDocker -DockerArgs ($compose + @('config', '--quiet'))
Invoke-RDGDocker -DockerArgs ($compose + @('build', 'rdg'))
if (-not $SkipSetup) {
    Invoke-RDGDocker -DockerArgs ($compose + @('--profile', 'setup', 'run', '--rm', '--no-deps', 'setup'))
} elseif (-not (Test-Path -LiteralPath (Join-Path $SecretsDirectory 'namespace-id.txt'))) {
    throw 'Update requires an initialized namespace; run normal Start-RDG.ps1 for first installation.'
}
Invoke-RDGDocker -DockerArgs ($compose + @('up', '-d', '--wait'))
if ($agentId) {
    $gatewayId = (& docker @compose ps -q rdg-api-gateway).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $gatewayId) { throw 'The gateway container is unavailable.' }
    $networkRaw = & docker network inspect rdg-personal_agents --format '{{json .Containers}}'
    if ($LASTEXITCODE -ne 0) { throw 'The private RDG agent network is unavailable.' }
    $networkMembers = $networkRaw | ConvertFrom-Json
    $attached = $false
    if ($null -ne $networkMembers) {
        foreach ($member in $networkMembers.PSObject.Properties) {
            if ($member.Name -eq $agentId) { $attached = $true }
            elseif ($member.Name -ne $gatewayId) {
                throw ('Unexpected container on the RDG agent network: ' + $member.Value.Name + '. Review it before granting API access.')
            }
        }
    }
    if (-not $attached) {
        Invoke-RDGDocker -DockerArgs @('network', 'connect', 'rdg-personal_agents', $agentId)
    }
    $gatewayNetworkMember = $networkMembers.PSObject.Properties[$gatewayId].Value
    $gatewayPrivateIP = ($gatewayNetworkMember.IPv4Address -split '/')[0]
    if ($gatewayPrivateIP -notmatch '^[0-9]+(\.[0-9]+){3}$') { throw 'Cannot identify the private gateway IPv4 address for the isolation check.' }
    $isolationCode = @'
import socket,sys
try:
    connection=socket.create_connection((sys.argv[1],8081),timeout=4)
except OSError:
    print('Unrelated container isolation check: OK')
else:
    connection.close()
    sys.exit('Isolation check failed: a container outside the private agent network reached the gateway')
'@
    Invoke-RDGDocker -DockerArgs @('run', '--rm', '--pull', 'never', '--network', 'rdg-personal_edge', '--user', '10001:10001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--read-only', '--pids-limit', '16', '--memory', '64m', '--entrypoint', 'python3', $runtimeImage, '-c', $isolationCode, $gatewayPrivateIP)
    $expectedNamespace = (Get-Content -Raw -LiteralPath (Join-Path $SecretsDirectory 'namespace-id.txt')).Trim()
    $clientContext = @{profile='gateway';origin='http://rdg-api-gateway:8081';namespaceId=$expectedNamespace} | ConvertTo-Json -Compress
    $connectCode = @'
import json,os,sys,urllib.request,uuid
from pathlib import Path
context=json.loads(sys.stdin.buffer.read().decode('utf-8-sig'))
assert set(context)=={'profile','origin','namespaceId'} and context['profile']=='gateway' and context['origin']=='http://rdg-api-gateway:8081'
assert str(uuid.UUID(context['namespaceId']))==context['namespaceId']
with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(context['origin']+'/healthz',timeout=10) as response:
    ready=json.load(response)
assert ready.get('status')=='ok' and ready.get('service')=='rdg-agent-gateway' and ready.get('namespaceId')==context['namespaceId']
path=Path('/workspace/repo/Workfiles/rdg-gateway-context.json')
assert path.parent.is_dir() and not any(p.is_symlink() for p in (path,*path.parents))
raw=(json.dumps(context,indent=2)+'\n').encode()
if path.exists():
    assert json.loads(path.read_text())==context,'Existing gateway context belongs to a different namespace'
else:
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as out:
        out.write(raw)
print('Private API check: OK; client context contains no credential')
'@
    $clientContext | & docker exec -i --user 1000:1000 $agentId python3 -c $connectCode
    if ($LASTEXITCODE -ne 0) { throw 'Private API verification from the agent container failed.' }
    Write-Host 'Agent context: /workspace/repo/Workfiles/rdg-gateway-context.json'
}
if ($Mode -eq 'Local') {
    $reachable = $false
    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        $response = $null
        $reader = $null
        try {
            $probe = [Net.HttpWebRequest]::Create($origin + '/healthz')
            $probe.Proxy = $null
            $probe.Timeout = 3000
            $probe.ReadWriteTimeout = 3000
            $response = $probe.GetResponse()
            $reader = New-Object IO.StreamReader($response.GetResponseStream())
            $health = $reader.ReadToEnd() | ConvertFrom-Json
            $reachable = ($health.status -eq 'ok' -and $health.service -eq 'rdg')
        } catch {
            $reachable = $false
        } finally {
            if ($null -ne $reader) { $reader.Dispose() }
            if ($null -ne $response) { $response.Dispose() }
        }
        if ($reachable) { break }
        Start-Sleep -Seconds 1
    }
    if (-not $reachable) {
        & docker @compose ps
        throw 'RDG is not reachable from Windows at localhost:18880. Check the Docker context and proxy port; do not remove the data volume.'
    }
    Write-Host 'Windows HTTP check: OK'
    $machineStatus = 0
    $machineResponse = $null
    try {
        $machineProbe = [Net.HttpWebRequest]::Create($origin + '/api/capabilities')
        $machineProbe.Proxy = $null
        $machineProbe.Timeout = 5000
        $machineResponse = $machineProbe.GetResponse()
        $machineStatus = [int]$machineResponse.StatusCode
    } catch [Net.WebException] {
        if ($null -ne $_.Exception.Response) {
            $machineResponse = $_.Exception.Response
            $machineStatus = [int]$machineResponse.StatusCode
        }
    } finally {
        if ($null -ne $machineResponse) { $machineResponse.Dispose() }
    }
    if ($machineStatus -ne 404) { throw 'The browser ingress did not block the machine API.' }
    Write-Host 'Browser ingress machine API check: blocked'
}
Write-Host ('RDG: ' + $origin)
Write-Host 'Browser username: rdg'
Write-Host ('Browser password file: ' + (Join-Path $SecretsDirectory 'browser-token.txt'))
Write-Host 'Keep secrets private. Do not paste tokens into chat.'
if ($Mode -eq 'HTTPS') {
    Write-Host 'The DNS name must point to Fortis_M; incoming ports 80 and 443 must reach this proxy.'
}
