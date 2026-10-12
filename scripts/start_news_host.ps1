param(
    [string]$HostRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) '../../Rinx-main'),
    [switch]$Visible
)
$ErrorActionPreference = 'Stop'
$taskProject = Split-Path -Parent $PSScriptRoot
$taskHost = (Resolve-Path -LiteralPath $HostRoot).Path
$taskRelease = Join-Path $taskHost 'target/release'
$taskExecutable = Join-Path $taskRelease 'rinx-news.exe'
if (-not (Test-Path -LiteralPath $taskExecutable -PathType Leaf)) {
    throw 'Build the combined news/reader host first with scripts/build_news_refresh_host.ps1'
}
foreach ($taskResource in @('makepad_widgets/resources', 'rinx/resources')) {
    if (-not (Test-Path -LiteralPath (Join-Path $taskRelease $taskResource) -PathType Container)) {
        throw ('Stage the matching Rinx host resources first; missing: ' + $taskResource)
    }
}
# Inherit the user's data configuration; do not switch to a project test profile.
$taskWindowStyle = if ($Visible) { 'Normal' } else { 'Hidden' }
$taskProcess = Start-Process -FilePath $taskExecutable -WorkingDirectory $taskRelease -WindowStyle $taskWindowStyle -PassThru
Write-Output ('Started news/reader host, PID ' + $taskProcess.Id)
Write-Output ('Review and Run this bundle: ' + (Join-Path $taskProject 'bundle'))
