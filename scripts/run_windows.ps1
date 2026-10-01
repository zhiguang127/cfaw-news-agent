param(
    [ValidateSet('Preview', 'Rinx')]
    [string]$Mode = 'Preview',
    [string]$DevRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) '../demo-workspace/vendor')
)

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskDevRoot = (Resolve-Path -LiteralPath $DevRoot).Path
$taskLock = Get-Content -LiteralPath (Join-Path $taskRoot 'dev-dependencies.lock.json') -Raw | ConvertFrom-Json
$taskHubRoot = Join-Path $taskDevRoot 'OctoSense-App-Hub'
$taskHub = Join-Path $taskHubRoot 'target/release/hub.exe'
$taskHostRoot = if ($Mode -eq 'Rinx') { Join-Path $taskDevRoot 'Rinx' } else { $taskHubRoot }
$taskHost = Join-Path $taskHostRoot ('target/release/' + $(if ($Mode -eq 'Rinx') { 'rinx.exe' } else { 'card-host.exe' }))

foreach ($taskRepo in $taskLock.repositories) {
    if ($taskRepo.name -eq 'Rinx' -and $Mode -ne 'Rinx') { continue }
    $taskCheckout = Join-Path $taskDevRoot $taskRepo.name
    $taskRevision = & git -C $taskCheckout rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $taskRevision -ne $taskRepo.commit) {
        throw ('Expected pinned checkout for ' + $taskRepo.name + ' at ' + $taskRepo.commit)
    }
}
foreach ($taskFile in @($taskHub, $taskHost)) {
    if (-not (Test-Path -LiteralPath $taskFile -PathType Leaf)) { throw ('Build the pinned tools first; missing: ' + $taskFile) }
}
$taskRequiredResources = @('makepad_widgets/resources')
if ($Mode -eq 'Rinx') { $taskRequiredResources += 'rinx/resources' }
foreach ($taskResource in $taskRequiredResources) {
    $taskResourcePath = Join-Path $taskHostRoot ('target/release/' + $taskResource)
    if (-not (Test-Path -LiteralPath $taskResourcePath -PathType Container)) {
        throw ('Stage the Windows host resources first; missing: ' + $taskResourcePath)
    }
}

$taskPreviousHub = $env:OCTO_HUB
try {
    $env:OCTO_HUB = $taskHub
    & python (Join-Path $PSScriptRoot 'package.py')
    if ($LASTEXITCODE -ne 0) { throw 'Application packaging failed' }
} finally {
    $env:OCTO_HUB = $taskPreviousHub
}

if ($Mode -eq 'Preview') {
    $taskData = Join-Path $taskRoot '.local-state/windows-preview'
    $taskBundle = Join-Path $taskRoot 'bundle'
    $taskArgs = @('--bundle', ('"' + $taskBundle + '"'), '--allow-unsigned', '--app-data', ('"' + $taskData + '"'), '--size', '430x860')
} else {
    $taskArgs = @()
}
# This is the interactive application the user requested, so show its window.
$taskPreviousRinxData = $env:RINX_DATA_DIR
try {
    if ($Mode -eq 'Rinx' -and -not $env:RINX_DATA_DIR -and -not $env:ROBRIX_DATA_DIR) {
        $env:RINX_DATA_DIR = Join-Path $taskRoot '.local-state/rinx'
    }
    $taskProcess = if ($taskArgs.Count) {
        Start-Process -FilePath $taskHost -ArgumentList $taskArgs -WorkingDirectory $taskHostRoot -WindowStyle Normal -PassThru
    } else {
        Start-Process -FilePath $taskHost -WorkingDirectory $taskHostRoot -WindowStyle Normal -PassThru
    }
} finally {
    $env:RINX_DATA_DIR = $taskPreviousRinxData
}
Write-Output ('Started ' + $Mode + ', PID ' + $taskProcess.Id)
Write-Output ('Bundle folder: ' + (Join-Path $taskRoot 'bundle'))
