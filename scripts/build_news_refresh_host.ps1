param(
    [string]$HostRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) '../../Rinx-main'),
    [Parameter(Mandatory=$true)][string]$CargoHome,
    [Parameter(Mandatory=$true)][string]$Python
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskHost = (Resolve-Path -LiteralPath $HostRoot).Path
$taskCargo = (Resolve-Path -LiteralPath $CargoHome).Path
$taskMakepad = Join-Path $taskCargo 'git/checkouts/makepad-5b6485c20cc788f9/1f3b1de'
& $Python (Join-Path $PSScriptRoot 'patch_reader_host.py') --makepad-root $taskMakepad
if ($LASTEXITCODE -ne 0) { throw 'Reader host patch failed' }
& $Python (Join-Path $PSScriptRoot 'patch_webreader_host.py') --makepad-root $taskMakepad
if ($LASTEXITCODE -ne 0) { throw 'WebReader host patch failed' }
& $Python (Join-Path $PSScriptRoot 'patch_news_gc_host.py') --makepad-root $taskMakepad
if ($LASTEXITCODE -ne 0) { throw 'News heap patch failed' }
$taskVs = & 'C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe' -latest -products '*' -property installationPath
Import-Module (Join-Path $taskVs 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
Enter-VsDevShell -VsInstallPath $taskVs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
$env:Path = (Join-Path $taskVs 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin') + ';' + (Join-Path $taskVs 'Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja') + ';' + $env:Path
$env:CARGO_HOME = $taskCargo
$env:CMAKE_GENERATOR = 'Ninja'
$env:MAKEPAD_PACKAGE_DIR = '.'
$env:CARGO_BUILD_JOBS = '4'
Push-Location -LiteralPath $taskHost
try {
    # Cargo caches Git dependencies as immutable. Rebuild every reader and heap
    # dependency patched above; existing host processes can stay open.
    cargo +1.98.0 clean --offline --release -p makepad-script -p makepad-platform -p makepad-draw -p makepad-widgets *> clean-news-gc-host.log
    if ($LASTEXITCODE -ne 0) { throw 'Could not invalidate the patched reader and script crates' }
    $taskBuildStart = Get-Date
    $ErrorActionPreference = 'Continue'
    cargo +1.98.0 build --offline --locked --release --bin rinx *> build-news-refresh-host.log
    $taskExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    $taskBuilt = Join-Path $taskHost 'target/release/deps/rinx.exe'
    if ($taskExit -ne 0) {
        $taskLog = Get-Content -LiteralPath build-news-refresh-host.log -Raw
        if (-not ($taskLog -match 'failed to remove file' -and $taskLog -match 'os error 5' -and (Test-Path -LiteralPath $taskBuilt) -and (Get-Item -LiteralPath $taskBuilt).LastWriteTime -gt $taskBuildStart)) {
            throw 'Build failed; inspect Rinx-main/build-news-refresh-host.log'
        }
    }
    Copy-Item -LiteralPath $taskBuilt -Destination (Join-Path $taskHost 'target/release/rinx-news.exe')
} finally { Pop-Location }
