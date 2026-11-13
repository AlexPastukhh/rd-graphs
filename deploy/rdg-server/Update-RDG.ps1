[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$AgentContainer,
    [ValidateSet('Local','HTTPS')][string]$Mode = 'Local',
    [string]$Domain,
    [string]$ExpectedBuildId = '',
    [string]$PinnedSha256 = '',
    [switch]$Watch,
    [string]$StateDirectory = (Join-Path $env:LOCALAPPDATA 'RDG-Server\cicd')
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($ExpectedBuildId -or $PinnedSha256) {
    if ($ExpectedBuildId -cnotmatch '^ci-[a-z0-9-]{10,100}$' -or
        $PinnedSha256 -cnotmatch '^[a-f0-9]{64}$' -or $Watch) {
        throw 'Pinned updates require an exact ExpectedBuildId and PinnedSha256, without Watch.'
    }
}
$bootstrap = $PSScriptRoot
$trusted = Get-Content -Raw -LiteralPath (Join-Path $bootstrap 'BUILD.json') | ConvertFrom-Json
$fixedFiles = @('Dockerfile','.dockerignore','compose.yaml','compose.local.yaml','compose.https.yaml',
    'Caddyfile','Caddyfile.local','Start-RDG.ps1','Stop-RDG.ps1','Update-RDG.ps1')
foreach ($name in $fixedFiles) {
    $actual = (Get-FileHash -LiteralPath (Join-Path $bootstrap $name) -Algorithm SHA256).Hash
    if ($actual -ne $trusted.files.$name) { throw ('Bootstrap hash mismatch: ' + $name) }
}
New-Item -ItemType Directory -Path $StateDirectory -Force | Out-Null
$mutex = New-Object Threading.Mutex($false, 'Local\RDG-CICD-Updater')
if (-not $mutex.WaitOne(0)) { throw 'Another RDG updater is already running.' }
function Copy-RDGArtifact {
    param([string]$RemotePath, [string]$Destination)
    # Docker cp writes successful transfer statistics to stderr. Capture both
    # streams even under Windows PowerShell 5.1 (which can treat native stderr
    # as an error with ErrorActionPreference=Stop). Never hide a failed exit.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& docker cp ($AgentContainer + ':' + $RemotePath) $Destination 2>&1)
        $copyExitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    if ($copyExitCode -ne 0) {
        $detail = ($output | Out-String).Trim()
        if ($detail.Length -gt 500) { $detail = $detail.Substring(0, 500) + '...' }
        throw ('Cannot copy the prepared CI artifact from Repo Docker. ' + $detail)
    }
}
function Assert-RDGKeys {
    param($Value, [string[]]$Expected)
    $actual = @($Value.PSObject.Properties.Name | Sort-Object)
    $wanted = @($Expected | Sort-Object)
    if (@(Compare-Object $actual $wanted).Count -ne 0) { throw 'Unexpected release metadata fields.' }
}
function Read-RDGHealth {
    param([string]$Origin)
    $probe = [Net.HttpWebRequest]::Create($Origin + '/healthz')
    $probe.Proxy = $null
    $probe.Timeout = 10000
    $response = $probe.GetResponse()
    try {
        $reader = New-Object IO.StreamReader($response.GetResponseStream())
        try { return ($reader.ReadToEnd() | ConvertFrom-Json) } finally { $reader.Dispose() }
    } finally { $response.Dispose() }
}
function Update-RDGOnce {
    $temporary = Join-Path $StateDirectory ('transfer-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temporary | Out-Null
    try {
        $readyPath = Join-Path $temporary 'ready.json'
        Copy-RDGArtifact '/workspace/repo/Workfiles/rdg-ci/ready.json' $readyPath
        $ready = Get-Content -Raw -LiteralPath $readyPath | ConvertFrom-Json
        Assert-RDGKeys $ready @('schemaVersion','kind','buildId','artifact','sha256','bytes','sourceSHA256','checks','createdAt')
        if ($ready.schemaVersion -ne 1 -or $ready.kind -ne 'rdg-ci-release' -or $ready.checks -ne 'full' -or
            $ready.buildId -notmatch '^ci-[a-z0-9-]{10,100}$' -or
            $ready.artifact -cne ('RDG-Server-' + $ready.buildId + '.zip') -or
            $ready.sha256 -notmatch '^[a-f0-9]{64}$' -or $ready.sourceSHA256 -notmatch '^[a-f0-9]{64}$' -or
            $ready.bytes -le 0 -or $ready.bytes -gt 50000000) { throw 'Invalid CI release metadata.' }
        # Bind selection inside the updater before any installed release is used.
        # The local ready object then pins the filename and digest through deployment.
        if ($ExpectedBuildId -and ($ready.buildId -cne $ExpectedBuildId -or $ready.sha256 -cne $PinnedSha256)) {
            throw 'Pinned CI release mismatch; no update performed.'
        }
        $activePath = Join-Path $StateDirectory 'active.json'
        if (Test-Path -LiteralPath $activePath) {
            $active = Get-Content -Raw -LiteralPath $activePath | ConvertFrom-Json
            if ($active.sha256 -eq $ready.sha256) {
                $currentOrigin = if ($Mode -eq 'Local') { 'http://localhost:18880' } else { 'https://' + $Domain }
                try {
                    $currentHealth = Read-RDGHealth $currentOrigin
                    if ($currentHealth.status -eq 'ok' -and $currentHealth.service -eq 'rdg' -and
                        $currentHealth.buildId -ceq $ready.buildId) { return }
                } catch {
                    Write-Warning 'Recorded release is not verified on the running server; attempting an update.'
                }
            }
        }
        $archive = Join-Path $temporary 'release.zip'
        Copy-RDGArtifact ('/workspace/repo/Workfiles/rdg-ci/' + $ready.artifact) $archive
        if ((Get-Item -LiteralPath $archive).Length -ne $ready.bytes -or
            (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $ready.sha256) { throw 'Release ZIP hash/size mismatch.' }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::OpenRead($archive)
        try {
            $seen = @{}
            [long]$expanded = 0
            foreach ($entry in $zip.Entries) {
                $name = $entry.FullName
                if ($name -notmatch '^RDG-Server/[a-zA-Z0-9_./-]+$' -or $name.Contains('\') -or
                    ($name -split '/') -contains '..' -or ($name -split '/') -contains '.' -or
                    $name.EndsWith('/') -or $name.EndsWith('.') -or
                    (($entry.ExternalAttributes -shr 16) -band 61440) -eq 40960 -or
                    $seen.ContainsKey($name.ToLowerInvariant())) { throw 'Unsafe or duplicate ZIP entry.' }
                foreach ($part in ($name -split '/')) {
                    if ($part.EndsWith('.') -or $part -match '^(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)') { throw 'Unsafe Windows ZIP name.' }
                }
                $seen[$name.ToLowerInvariant()] = $true
                $expanded += $entry.Length
            }
            if ($expanded -gt 100000000) { throw 'Expanded release is too large.' }
        } finally { $zip.Dispose() }
        $expandedPath = Join-Path $temporary 'expanded'
        Expand-Archive -LiteralPath $archive -DestinationPath $expandedPath
        $package = Join-Path $expandedPath 'RDG-Server'
        $manifest = Get-Content -Raw -LiteralPath (Join-Path $package 'BUILD.json') | ConvertFrom-Json
        if ($manifest.kind -ne 'rdg-personal-server-package' -or $manifest.serverBuild -cne $ready.buildId -or
            $manifest.imageTag -cne $ready.buildId -or $manifest.includesUserData -ne $false) { throw 'Release manifest mismatch.' }
        foreach ($property in $manifest.files.PSObject.Properties) {
            $name = $property.Name
            if ($name -notmatch '^[a-zA-Z0-9_./-]+$' -or $name.StartsWith('/') -or
                ($name -split '/') -contains '..' -or ($name -split '/') -contains '.') { throw 'Unsafe manifest path.' }
            if ((Get-FileHash -LiteralPath (Join-Path $package $name) -Algorithm SHA256).Hash -ne $property.Value) { throw ('Release file hash mismatch: ' + $name) }
        }
        $expectedCount = @($manifest.files.PSObject.Properties).Count + 1
        if (@(Get-ChildItem -LiteralPath $package -File -Recurse -Force).Count -ne $expectedCount) { throw 'Unlisted package files.' }
        foreach ($name in $fixedFiles) {
            if ($manifest.files.$name -ne $trusted.files.$name) { throw ('Deployment config changed; install a reviewed new bootstrap first: ' + $name) }
        }
        $releasePath = Join-Path $StateDirectory $ready.buildId
        if (Test-Path -LiteralPath $releasePath) {
            foreach ($property in $manifest.files.PSObject.Properties) {
                if ((Get-FileHash -LiteralPath (Join-Path $releasePath $property.Name) -Algorithm SHA256).Hash -ne $property.Value) { throw 'An existing release directory has different bytes.' }
            }
            if ((Get-FileHash -LiteralPath (Join-Path $releasePath 'BUILD.json') -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath (Join-Path $package 'BUILD.json') -Algorithm SHA256).Hash) { throw 'Existing release manifest differs.' }
        } else { Move-Item -LiteralPath $package -Destination $releasePath }
        Write-Host ('Deploying tested RDG build: ' + $ready.buildId)
        $startArgs = @{Mode=$Mode;AgentContainer=$AgentContainer;PackageDirectory=$releasePath;SkipSetup=$true}
        if ($Mode -eq 'HTTPS') { $startArgs.Domain = $Domain }
        & (Join-Path $bootstrap 'Start-RDG.ps1') @startArgs
        $origin = if ($Mode -eq 'Local') { 'http://localhost:18880' } else { 'https://' + $Domain }
        $health = Read-RDGHealth $origin
        if ($health.status -ne 'ok' -or $health.service -ne 'rdg' -or
            $health.buildId -cne $ready.buildId) { throw 'The server is not running the requested build.' }
        $stateTemp = Join-Path $StateDirectory 'active.pending.json'
        $ready | ConvertTo-Json | Set-Content -LiteralPath $stateTemp -Encoding UTF8
        Move-Item -LiteralPath $stateTemp -Destination $activePath -Force
        Write-Host ('RDG updated: ' + $ready.buildId + '. Refresh the browser. Data volumes retained.')
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
    }
}
try {
    do {
        try { Update-RDGOnce } catch {
            if (-not $Watch) { throw }
            Write-Warning $_.Exception.Message
        }
        if ($Watch) { Start-Sleep -Seconds 5 }
    } while ($Watch)
} finally { $mutex.ReleaseMutex(); $mutex.Dispose() }
