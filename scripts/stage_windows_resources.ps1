param(
    [ValidateSet('Preview', 'Rinx')]
    [string]$Mode = 'Preview',
    [string]$DevRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) '../demo-workspace/vendor')
)

$ErrorActionPreference = 'Stop'
$taskDevRoot = (Resolve-Path -LiteralPath $DevRoot).Path
$taskHostRoot = Join-Path $taskDevRoot $(if ($Mode -eq 'Rinx') { 'Rinx' } else { 'OctoSense-App-Hub' })
$taskRelease = Join-Path $taskHostRoot 'target/release'
$taskCount = 0
# Makepad build scripts write these files for desktop resource packaging.
foreach ($taskPathFile in Get-ChildItem -LiteralPath $taskRelease -Filter '*.path') {
    $taskSourceRoot = (Get-Content -LiteralPath $taskPathFile.FullName -Raw).Trim()
    $taskResources = Join-Path $taskSourceRoot 'resources'
    if (-not (Test-Path -LiteralPath $taskResources -PathType Container)) { continue }
    $taskCrateName = $taskPathFile.BaseName.Replace('-', '_')
    $taskCrateTarget = Join-Path $taskRelease $taskCrateName
    $null = New-Item -ItemType Directory -Path $taskCrateTarget -Force
    Copy-Item -LiteralPath $taskResources -Destination $taskCrateTarget -Recurse -Force
    $taskCount++
}
if (-not (Test-Path -LiteralPath (Join-Path $taskRelease 'makepad_widgets/resources'))) {
    throw 'Makepad widget resources are missing; build with MAKEPAD_PACKAGE_DIR=.'
}
if ($Mode -eq 'Rinx' -and -not (Test-Path -LiteralPath (Join-Path $taskRelease 'rinx/resources'))) {
    throw 'Rinx resources are missing; build the pinned host first'
}
Write-Output ('Staged resources for ' + $taskCount + ' crates beside the ' + $Mode + ' executable')