# Owner-side one-time bootstrap refresh for a READY RDG CI release.
# This only prepares a matching bootstrap and invokes the existing Update-RDG.ps1.
# It does not modify or access RDG owner data except through the standard updater.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$AgentContainer,
    [Parameter(Mandatory=$true)][string]$ExpectedBuildId,
    [ValidateSet('Local','HTTPS')][string]$Mode='Local',
    [string]$PinnedSha256='',
    [string]$Domain
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if ($AgentContainer -notmatch '^[a-f0-9]{12,64}$') { throw 'Expected an exact running Repo Docker container ID.' }
if ($ExpectedBuildId -notmatch '^ci-[a-z0-9-]{10,100}$') { throw 'Invalid expected build ID.' }
if ($Mode -eq 'HTTPS' -and [string]::IsNullOrWhiteSpace($Domain)) { throw 'HTTPS requires Domain.' }

function Copy-Prepared {
    param([string]$Remote, [string]$Local)
    $previous=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        $result=@(& docker cp ($AgentContainer + ':' + $Remote) $Local 2>&1)
        $exitCode=$LASTEXITCODE
    } finally { $ErrorActionPreference=$previous }
    if ($exitCode -ne 0) { throw ('Docker cp failed for '+[IO.Path]::GetFileName($Remote)+': '+($result | Out-String).Trim()) }
}

$temporary=Join-Path $env:LOCALAPPDATA ('RDG-Server\bootstrap-transfer-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary -Force | Out-Null
try {
    # A checked archive digest pins a specific release even after CI publishes
    # newer ready.json versions. Otherwise use the latest published full READY.
    $artifact='RDG-Server-'+$ExpectedBuildId+'.zip'
    $expectedBytes=$null
    if ($PinnedSha256) {
        if ($PinnedSha256 -cnotmatch '^[a-f0-9]{64}$') { throw 'Invalid pinned SHA256.' }
        $expectedSha=$PinnedSha256
    } else {
        $readyPath=Join-Path $temporary 'ready.json'
        Copy-Prepared '/workspace/repo/Workfiles/rdg-ci/ready.json' $readyPath
        $ready=Get-Content -Raw -LiteralPath $readyPath | ConvertFrom-Json
        $required=@('buildId','artifact','sha256','bytes','sourceSHA256','checks')
        foreach ($field in $required) {
            if (-not ($ready.PSObject.Properties.Name -ccontains $field)) {
                throw ('READY metadata lacks '+$field+'; no update performed.')
            }
        }
        if ($ready.buildId -cne $ExpectedBuildId -or $ready.checks -cne 'full' -or
            $ready.sourceSHA256 -notmatch '^[a-f0-9]{64}$' -or
            $ready.artifact -cne $artifact -or $ready.sha256 -notmatch '^[a-f0-9]{64}$' -or
            $ready.bytes -lt 1 -or $ready.bytes -gt 50000000) {
            throw 'Expected build is not the published full-checked READY release. No update performed.'
        }
        $expectedSha=$ready.sha256
        $expectedBytes=[long]$ready.bytes
    }
    $archive=Join-Path $temporary 'release.zip'
    Copy-Prepared ('/workspace/repo/Workfiles/rdg-ci/'+$artifact) $archive
    $actualBytes=(Get-Item -LiteralPath $archive).Length
    if ($actualBytes -lt 1 -or $actualBytes -gt 50000000 -or
        ($null -ne $expectedBytes -and $actualBytes -ne $expectedBytes) -or
        (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expectedSha) {
        throw 'Release ZIP differs from the pinned checksum; no update performed.'
    }
    $expanded=Join-Path $temporary 'expanded'
    Expand-Archive -LiteralPath $archive -DestinationPath $expanded
    $bootstrap=Join-Path $expanded 'RDG-Server'
    $manifest=Get-Content -Raw -LiteralPath (Join-Path $bootstrap 'BUILD.json') | ConvertFrom-Json
    if ($manifest.serverBuild -cne $ExpectedBuildId -or $manifest.includesUserData -ne $false) {
        throw 'Release bootstrap identity mismatch.'
    }
    # The existing updater independently reads the *current* ready.json.
    # Fail closed if that pointer does not match the release we just checked.
    # This also prevents a false success report for the wrong build.
    $pointerPath=Join-Path $temporary 'updater-ready.json'
    Copy-Prepared '/workspace/repo/Workfiles/rdg-ci/ready.json' $pointerPath
    $pointer=Get-Content -Raw -LiteralPath $pointerPath | ConvertFrom-Json
    if ($pointer.PSObject.Properties.Name -cnotcontains 'buildId' -or
        $pointer.PSObject.Properties.Name -cnotcontains 'sha256' -or
        $pointer.buildId -cne $ExpectedBuildId -or $pointer.sha256 -cne $expectedSha) {
        throw ('READY now points to another CI release (' + $pointer.buildId +
               '). No update performed. Review that release before updating.')
    }
    $start=@{ AgentContainer=$AgentContainer;Mode=$Mode;ExpectedBuildId=$ExpectedBuildId;PinnedSha256=$expectedSha }
    if ($Mode -eq 'HTTPS') { $start.Domain=$Domain }
    Write-Host ('Updating RDG from verified READY build '+$ExpectedBuildId)
    & (Join-Path $bootstrap 'Update-RDG.ps1') @start
    # The updater enforces the same pin before starting a release even if READY
    # changes after our check. Independently verify the installed build as well.
    $origin=if($Mode -eq 'Local'){'http://localhost:18880'}else{'https://'+$Domain}
    $probe=[Net.HttpWebRequest]::Create($origin+'/healthz')
    $probe.Proxy=$null
    $probe.Timeout=10000
    $response=$probe.GetResponse()
    try {
        $reader=New-Object IO.StreamReader($response.GetResponseStream())
        try { $health=$reader.ReadToEnd() | ConvertFrom-Json }
        finally { $reader.Dispose() }
    } finally { $response.Dispose() }
    if ($health.status -cne 'ok' -or $health.service -cne 'rdg' -or
        $health.buildId -cne $ExpectedBuildId) {
        throw ('Installed build differs: expected '+$ExpectedBuildId+
               ', actual '+$health.buildId+'. The updater may have installed a newer CI release.')
    }
    Write-Host ('RDG updated: '+$ExpectedBuildId+'. Press F5 in the browser.')
} finally {
    if (Test-Path -LiteralPath $temporary) {
        Remove-Item -LiteralPath $temporary -Force -Recurse
    }
}
