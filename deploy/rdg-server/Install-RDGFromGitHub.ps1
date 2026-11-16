# Owner-run Windows PowerShell 5.1 entry point. Never writes to the Git checkout.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedCommitSha,
    [Parameter(Mandatory=$true)][ValidateRange(1,[long]::MaxValue)][long]$RunId,
    [Parameter(Mandatory=$true)][ValidateRange(1,10000)][int]$RunAttempt,
    [Parameter(Mandatory=$true)][ValidateRange(1,[long]::MaxValue)][long]$ArtifactId,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$PinnedArtifactSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{12,64}$')][string]$AgentContainer,
    [ValidateSet('Local','HTTPS')][string]$Mode = 'Local',
    [string]$Domain,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Repository = 'AlexPastukhh/rd-graphs'
$SourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$StateDirectory = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'RDG-Server/cicd'))
$Utf8 = New-Object Text.UTF8Encoding($false)
$GitProgram = (Get-Command git -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$GhProgram = (Get-Command gh -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$FixedFiles = @('Dockerfile','.dockerignore','compose.yaml','compose.local.yaml','compose.https.yaml',
    'Caddyfile','Caddyfile.local','Start-RDG.ps1','Stop-RDG.ps1','Update-RDG.ps1')
function Assert-PlainPath {
    param([string]$Path)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        $item = Get-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue
        if ($null -ne $item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'A selected path contains a junction or symlink.' }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
}
function Quote-Argument {
    param([string]$Value)
    $builder = New-Object Text.StringBuilder
    [void]$builder.Append([char]34)
    $slashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq [char]92) { $slashes++; continue }
        if ($character -eq [char]34) {
            [void]$builder.Append([char]92,[int](2*$slashes+1)); [void]$builder.Append([char]34)
        } else {
            [void]$builder.Append([char]92,[int]$slashes); [void]$builder.Append($character)
        }
        $slashes = 0
    }
    [void]$builder.Append([char]92,[int](2*$slashes)); [void]$builder.Append([char]34)
    return $builder.ToString()
}
function Invoke-Native {
    param([string]$Program,[string[]]$Arguments,[string]$OutputPath='')
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $Program
    $start.WorkingDirectory = $SourceRoot
    $start.Arguments = (($Arguments | ForEach-Object { Quote-Argument $_ }) -join ' ')
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.EnvironmentVariables['GIT_OPTIONAL_LOCKS'] = '0'
    $start.EnvironmentVariables['GIT_TERMINAL_PROMPT'] = '0'
    $start.EnvironmentVariables['GH_PROMPT_DISABLED'] = '1'
    $start.EnvironmentVariables['GH_DEBUG'] = ''
    foreach ($name in @('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES')) { [void]$start.EnvironmentVariables.Remove($name) }
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    $stream = if ($OutputPath) { [IO.File]::Open($OutputPath,[IO.FileMode]::CreateNew) } else { New-Object IO.MemoryStream }
    try {
        if (-not $process.Start()) { throw 'Cannot start the selected Git/gh application.' }
        $errors = $process.StandardError.ReadToEndAsync()
        $copy = $process.StandardOutput.BaseStream.CopyToAsync($stream)
        if (-not $process.WaitForExit(300000)) { try { $process.Kill() } catch {}; throw 'Git/gh timed out; no deployment was started.' }
        [void]$copy.GetAwaiter().GetResult()
        [void]$errors.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) { throw 'Git/gh failed. Check Windows GitHub CLI authentication and access; no alternate download is attempted.' }
        if (-not $OutputPath) { return $Utf8.GetString($stream.ToArray()).Trim() }
    } finally { $stream.Dispose(); $process.Dispose() }
}
function Read-Git {
    param([string[]]$Arguments)
    return Invoke-Native $GitProgram (@('--no-pager','-c','core.fsmonitor=false','-C',$SourceRoot) + $Arguments)
}
function Read-GitHub {
    param([string]$Endpoint)
    return (Invoke-Native $GhProgram @('api','--hostname','github.com','--method','GET',
        '-H','X-GitHub-Api-Version: 2022-11-28',('repos/' + $Repository + '/' + $Endpoint)) | ConvertFrom-Json)
}
function Assert-Source {
    Assert-PlainPath $SourceRoot
    if ((Read-Git @('rev-parse','HEAD')) -cne $ExpectedCommitSha -or
        (Read-Git @('symbolic-ref','--short','HEAD')) -cne 'main' -or
        (Read-Git @('rev-parse','--abbrev-ref','@{upstream}')) -cne 'origin/main' -or
        (Read-Git @('remote','get-url','origin')) -cne ('https://github.com/' + $Repository + '.git') -or
        (Read-Git @('status','--porcelain=v1','--untracked-files=all'))) { throw 'Expected a clean, pinned main checkout with canonical origin/upstream. Use Mirror first.' }
    $top = [IO.Path]::GetFullPath((Read-Git @('rev-parse','--show-toplevel')))
    if (-not $top.Equals($SourceRoot,[StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected source checkout root.' }
    foreach ($name in $FixedFiles) { Assert-PlainPath (Join-Path $PSScriptRoot $name) }
}
function Assert-GitHub {
    $main = Read-GitHub 'branches/main'
    if ($main.commit.sha -cne $ExpectedCommitSha) { throw 'GitHub main changed; obtain a fresh reviewed selection.' }
    $workflow = Read-GitHub 'actions/workflows/rdg-ci.yml'
    $run = Read-GitHub ('actions/runs/' + $RunId)
    if ($workflow.path -cne '.github/workflows/rdg-ci.yml' -or $workflow.state -cne 'active' -or
        $run.id -ne $RunId -or $run.run_attempt -ne $RunAttempt -or $run.workflow_id -ne $workflow.id -or
        $run.path -cne '.github/workflows/rdg-ci.yml' -or $run.head_sha -cne $ExpectedCommitSha -or
        $run.head_branch -cne 'main' -or $run.repository.full_name -cne $Repository -or
        $run.head_repository.full_name -cne $Repository -or $run.status -cne 'completed' -or
        $run.conclusion -cne 'success' -or $run.event -cnotin @('push','workflow_dispatch')) { throw 'Selected GitHub CI run is not a successful main run for this source.' }
    $artifact = Read-GitHub ('actions/artifacts/' + $ArtifactId)
    if ($artifact.id -ne $ArtifactId -or $artifact.name -cne ('rdg-server-' + $ExpectedCommitSha) -or
        $artifact.expired -ne $false -or $artifact.size_in_bytes -le 0 -or $artifact.size_in_bytes -gt 50000000 -or
        $artifact.digest -cne ('sha256:' + $PinnedArtifactSha256) -or
        $artifact.workflow_run.id -ne $RunId -or $artifact.workflow_run.head_sha -cne $ExpectedCommitSha -or
        $artifact.workflow_run.head_branch -cne 'main' -or
        $artifact.workflow_run.repository_id -ne $run.repository.id -or
        $artifact.workflow_run.head_repository_id -ne $run.repository.id) { throw 'GitHub artifact identity, digest or provenance mismatch (or artifact expired).' }
    return $artifact
}
Assert-Source
Assert-PlainPath $StateDirectory
if ($StateDirectory.Equals($SourceRoot,[StringComparison]::OrdinalIgnoreCase) -or $StateDirectory.StartsWith($SourceRoot.TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Runtime state must be outside the source checkout.' }
$artifact = Assert-GitHub
[void][IO.Directory]::CreateDirectory($StateDirectory)
$temporary = Join-Path $StateDirectory ('github-transfer-' + [guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($temporary)
try {
    $outerPath = Join-Path $temporary 'github-artifact.zip'
    Invoke-Native $GhProgram @('api','--hostname','github.com','--method','GET',
        '-H','X-GitHub-Api-Version: 2022-11-28',('repos/' + $Repository + '/actions/artifacts/' + $ArtifactId + '/zip')) $outerPath
    if ((Get-Item -LiteralPath $outerPath).Length -ne $artifact.size_in_bytes -or
        (Get-FileHash -LiteralPath $outerPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $PinnedArtifactSha256) { throw 'GitHub artifact ZIP hash/size mismatch.' }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($outerPath)
    try {
        if ($zip.Entries.Count -ne 2) { throw 'Expected exactly READY and one release ZIP.' }
        $seen = @{}
        [long]$expanded = 0
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName
            if (($name -cne 'ready.json' -and $name -cnotmatch '^RDG-Server-ci-[a-z0-9-]{10,100}\.zip$') -or
                $seen.ContainsKey($name) -or (($entry.ExternalAttributes -shr 16) -band 61440) -eq 40960) { throw 'Unexpected or unsafe GitHub artifact entry.' }
            $seen[$name] = $true
            $expanded += $entry.Length
            if ($expanded -gt 50010000 -or ($name -ceq 'ready.json' -and $entry.Length -gt 8192)) { throw 'GitHub artifact expanded size limit exceeded.' }
        }
        if (-not $seen.ContainsKey('ready.json')) { throw 'READY is missing.' }
        foreach ($entry in $zip.Entries) {
            $target = [IO.File]::Open((Join-Path $temporary $entry.FullName),[IO.FileMode]::CreateNew)
            $source = $entry.Open()
            try { $source.CopyTo($target) } finally { $source.Dispose(); $target.Dispose() }
        }
    } finally { $zip.Dispose() }
    $ready = Get-Content -Raw -LiteralPath (Join-Path $temporary 'ready.json') | ConvertFrom-Json
    if ($ready.kind -cne 'rdg-ci-release' -or $ready.schemaVersion -ne 1 -or $ready.checks -cne 'full' -or
        $ready.buildId -cnotmatch '^ci-[a-z0-9-]{10,100}$' -or $ready.sha256 -cnotmatch '^[a-f0-9]{64}$' -or
        $ready.artifact -cne ('RDG-Server-' + $ready.buildId + '.zip') -or -not $seen.ContainsKey($ready.artifact)) { throw 'Invalid full CI READY selection.' }
    $release = Join-Path $temporary $ready.artifact
    if ((Get-Item -LiteralPath $release).Length -ne $ready.bytes -or
        (Get-FileHash -LiteralPath $release -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ready.sha256) { throw 'CI payload ZIP hash/size mismatch.' }
    # The updater is copied from the approved checkout, never executed from the download.
    $bootstrap = Join-Path $temporary 'bootstrap'
    [void][IO.Directory]::CreateDirectory($bootstrap)
    $trustedFiles = @{}
    foreach ($name in $FixedFiles) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $bootstrap $name)
        $trustedFiles[$name] = (Get-FileHash -LiteralPath (Join-Path $bootstrap $name) -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    [IO.File]::WriteAllText((Join-Path $bootstrap 'BUILD.json'),(@{files=$trustedFiles} | ConvertTo-Json),$Utf8)
    Assert-Source
    $null = Assert-GitHub
    $updateArgs = @{AgentContainer=$AgentContainer;Mode=$Mode;ArtifactDirectory=$temporary;
        ExpectedBuildId=$ready.buildId;PinnedSha256=$ready.sha256;ExpectedRepositoryHead=$ExpectedCommitSha;StateDirectory=$StateDirectory;ValidateOnly=(-not $Apply)}
    if ($Mode -eq 'HTTPS') { $updateArgs.Domain = $Domain }
    & (Join-Path $bootstrap 'Update-RDG.ps1') @updateArgs
    if (-not $Apply) { Write-Host 'RDG_GITHUB_PREVIEW_PASS: package verified; use the same selection with -Apply to deploy.'; return }
    $receiptPath = Join-Path $StateDirectory ('github-install-' + [guid]::NewGuid().ToString('N') + '.json')
    $receipt = @{schemaVersion=1;kind='rdg-github-install';repository=$Repository;sourceCommit=$ExpectedCommitSha;
        runId=$RunId;runAttempt=$RunAttempt;artifactId=$ArtifactId;artifactSHA256=$PinnedArtifactSha256;
        buildId=$ready.buildId;payloadSHA256=$ready.sha256;healthVerified=$true;mode=$Mode;installedAt=[DateTime]::UtcNow.ToString('o')}
    [IO.File]::WriteAllText($receiptPath,($receipt | ConvertTo-Json),$Utf8)
    Write-Host ('RDG_GITHUB_INSTALL_READY: ' + $ready.buildId)
    Write-Host ('INSTALL_RECEIPT: ' + $receiptPath)
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
}
