param(
    [ValidateSet('Preview', 'Rinx')]
    [string]$Mode = 'Preview',
    [string]$DevRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) '.dev/vendor'),
    [switch]$Diagnostic,
    [ValidateSet('Sdf', 'Default')]
    [string]$RinxTextRasterizer = 'Sdf'
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
if ($Mode -eq 'Rinx') {
    & python (Join-Path $PSScriptRoot 'patch_gesture_host.py') --dev-root $taskDevRoot --check-artifacts
    if ($LASTEXITCODE -ne 0) { throw 'Build the long-press host fix first: scripts/build_windows_tools.ps1 -Mode Rinx' }
    & python (Join-Path $PSScriptRoot 'patch_windows_render_host.py') --dev-root $taskDevRoot --check-artifacts
    if ($LASTEXITCODE -ne 0) { throw 'Build the recorded D3D11 host fix first: scripts/build_windows_tools.ps1 -Mode Rinx' }
}
if ($Mode -eq 'Preview') {
    & python (Join-Path $PSScriptRoot 'patch_preview_gesture_host.py') --dev-root $taskDevRoot --check-artifacts
    if ($LASTEXITCODE -ne 0) { throw 'Build the Preview gesture fix first: scripts/build_windows_tools.ps1 -Mode Preview -DevRoot <vendor directory>' }
}
if ($Mode -eq 'Rinx' -and $RinxTextRasterizer -eq 'Sdf') {
    & python (Join-Path $PSScriptRoot 'build_windows_sdf_host.py') --dev-root $taskDevRoot
    if ($LASTEXITCODE -ne 0) { throw 'SDF host build failed; see Windows development instructions' }
    $taskSdfInfo = Get-Content -LiteralPath (Join-Path $taskRoot 'build/windows-rinx-sdf/build-info.json') -Raw | ConvertFrom-Json
    if ($taskSdfInfo.build_id -notmatch '^[a-f0-9]{12}$' -or $taskSdfInfo.executable -ne ('rinx-sdf-' + $taskSdfInfo.build_id + '.exe')) { throw 'Invalid SDF build output; rebuild the host' }
    $taskSdfDirectory = Join-Path (Join-Path $taskRoot 'build/windows-rinx-sdf') $taskSdfInfo.build_id
    $taskHost = Join-Path $taskSdfDirectory $taskSdfInfo.executable
    Write-Output 'Rinx text rasterizer: SDF (temporary Windows white-screen workaround)'
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
if ($Diagnostic) {
    $taskDiagnosticRoot = Join-Path $taskRoot ('.local-state/diagnostics/' + $Mode.ToLower() + '-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
    New-Item -ItemType Directory -Path $taskDiagnosticRoot -Force | Out-Null
    # The native Makepad diagnostic API binds only to loopback by default.
    $taskListener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $taskListener.Start()
    $taskRemotePort = $taskListener.LocalEndpoint.Port
    $taskListener.Stop()
    $taskArgs += @('--remote=' + $taskRemotePort)
}
# This is the interactive application the user requested, so show its window.
$taskPreviousRinxData = $env:RINX_DATA_DIR
try {
    if ($Mode -eq 'Rinx' -and -not $env:RINX_DATA_DIR -and -not $env:ROBRIX_DATA_DIR) {
        $env:RINX_DATA_DIR = Join-Path $taskRoot '.local-state/rinx'
    }
    $taskProcess = if ($Diagnostic) {
        Start-Process -FilePath $taskHost -ArgumentList $taskArgs -WorkingDirectory $taskHostRoot -WindowStyle Normal -RedirectStandardOutput (Join-Path $taskDiagnosticRoot 'stdout.log') -RedirectStandardError (Join-Path $taskDiagnosticRoot 'stderr.log') -PassThru
    } elseif ($taskArgs.Count) {
        Start-Process -FilePath $taskHost -ArgumentList $taskArgs -WorkingDirectory $taskHostRoot -WindowStyle Normal -PassThru
    } else {
        Start-Process -FilePath $taskHost -WorkingDirectory $taskHostRoot -WindowStyle Normal -PassThru
    }
} finally {
    $env:RINX_DATA_DIR = $taskPreviousRinxData
}
Write-Output ('Started ' + $Mode + ', PID ' + $taskProcess.Id)
Write-Output ('Bundle folder: ' + (Join-Path $taskRoot 'bundle'))
if ($Diagnostic) {
    $taskDiagnosticInfo = @{mode = $Mode; pid = $taskProcess.Id; port = $taskRemotePort; logs = $taskDiagnosticRoot}
    $taskDiagnosticInfo | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskDiagnosticRoot 'session.json') -Encoding UTF8
    Write-Output ('Diagnostic logs: ' + $taskDiagnosticRoot)
    Write-Output ('Native diagnostic API: http://127.0.0.1:' + $taskRemotePort)
    Write-Output 'Diagnostic mode redirects host output to stdout.log / stderr.log; the host console can remain empty.'
    Write-Output ('Live log: Get-Content -LiteralPath "' + (Join-Path $taskDiagnosticRoot 'stdout.log') + '" -Tail 40 -Wait')
}
