param(
    [ValidateSet('All', 'Rinx', 'Preview')]
    [string]$Mode = 'All',
    [string]$DevRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) '.dev/vendor')
)

$ErrorActionPreference = 'Stop'
function Invoke-ToolBuild($Program, $Arguments, $LogPath) {
    # Windows PowerShell 5 wraps native stderr (including Cargo warnings) as
    # error records. The process exit code, not a warning, determines failure.
    $ErrorActionPreference = 'Continue'
    & $Program @Arguments *> $LogPath
    $taskBuildExit = $LASTEXITCODE
    if ($taskBuildExit -ne 0) { throw ('Build failed with exit ' + $taskBuildExit + '; inspect ' + $LogPath) }
}
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskVendor = (Resolve-Path -LiteralPath $DevRoot).Path
$taskLock = Get-Content -LiteralPath (Join-Path $taskRoot 'dev-dependencies.lock.json') -Raw | ConvertFrom-Json
foreach ($taskRepo in $taskLock.repositories) {
    $taskCheckout = Join-Path $taskVendor $taskRepo.name
    $taskRevision = & git -C $taskCheckout rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $taskRevision -ne $taskRepo.commit) {
        throw ('Expected pinned checkout for ' + $taskRepo.name + ' at ' + $taskRepo.commit)
    }
}
$taskVsRoot = & 'C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe' -latest -products '*' -property installationPath
if (-not $taskVsRoot) { throw 'Visual Studio C++ Build Tools were not found' }
Import-Module (Join-Path $taskVsRoot 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
Enter-VsDevShell -VsInstallPath $taskVsRoot -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
$env:Path = (Join-Path $taskVsRoot 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin') + ';' + (Join-Path $taskVsRoot 'Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja') + ';' + $env:Path
# Git's long-path option does not cover all Matrix build inputs. Keep the
# prepared vendor tree on a temporary short drive; binaries use adjacent assets.
$taskDrive = $null
foreach ($taskLetter in @('R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z')) {
    if (-not (Test-Path ($taskLetter + ':\'))) { $taskDrive = $taskLetter + ':'; break }
}
if (-not $taskDrive) { throw 'No free temporary drive letter for the Windows build' }
& subst $taskDrive $taskVendor
if ($LASTEXITCODE -ne 0) { throw 'Could not map the prepared vendor directory' }
$taskOriginalDirectory = (Get-Location).Path
$taskLogRoot = Join-Path $taskRoot 'build/dependency-update'
New-Item -ItemType Directory -Path $taskLogRoot -Force | Out-Null
try {
    $env:RUSTUP_TOOLCHAIN = $taskLock.toolchain.rinx_rust_channel
    $env:CARGO_HOME = $taskDrive + '/cargo-home'
    $env:CARGO_NET_GIT_FETCH_WITH_CLI = 'true'
    $env:GIT_CONFIG_COUNT = '1'
    $env:GIT_CONFIG_KEY_0 = 'core.longpaths'
    $env:GIT_CONFIG_VALUE_0 = 'true'
    $env:CMAKE_GENERATOR = 'Ninja'
    $env:MAKEPAD_PACKAGE_DIR = '.'
    $env:CARGO_BUILD_JOBS = '4'
    if ($Mode -ne 'Preview') {
        $taskRinx = $taskDrive + '/Rinx'
        Set-Location $taskRinx
        $env:CARGO_TARGET_DIR = $taskRinx + '/target'
        Write-Output ('Building pinned Rinx; log: ' + (Join-Path $taskLogRoot 'rinx.log'))
        Invoke-ToolBuild 'cargo' @('build', '--locked', '--release', '--bin', 'rinx', '--features', 'agent_chat') (Join-Path $taskLogRoot 'rinx.log')
        Write-Output ('Packaging matching Octos; log: ' + (Join-Path $taskLogRoot 'octos.log'))
        Invoke-ToolBuild 'python' @('tools/package-octos.py', 'desktop', '--app-binary', 'target/release/rinx.exe') (Join-Path $taskLogRoot 'octos.log')
        & ./target/release/octos.exe --version
        & (Join-Path $PSScriptRoot 'stage_windows_resources.ps1') -Mode Rinx -DevRoot ($taskDrive + '/')
    }
    if ($Mode -ne 'Rinx') {
        $taskHub = $taskDrive + '/OctoSense-App-Hub'
        Set-Location $taskHub
        $env:CARGO_TARGET_DIR = $taskHub + '/target'
        Write-Output ('Building pinned hub and card-host; log: ' + (Join-Path $taskLogRoot 'hub.log'))
        Invoke-ToolBuild 'cargo' @('build', '--locked', '--release', '-p', 'octosense-app-hub', '--bin', 'hub', '-p', 'octosense-card-host', '--bin', 'card-host') (Join-Path $taskLogRoot 'hub.log')
        & (Join-Path $PSScriptRoot 'stage_windows_resources.ps1') -DevRoot ($taskDrive + '/')
    }
} finally {
    Set-Location $taskOriginalDirectory
    & subst $taskDrive /D
}
