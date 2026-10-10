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
& $Python (Join-Path $PSScriptRoot 'patch_webreader_host.py') --makepad-root $taskMakepad
if ($LASTEXITCODE -ne 0) { throw 'WebReader host patch failed' }
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
    cargo +1.98.0 clean --offline --release -p makepad-platform -p makepad-draw -p makepad-widgets *> clean-webreader-host.log
    if ($LASTEXITCODE -ne 0) { throw 'Could not invalidate patched dependency artifacts' }
    $ErrorActionPreference = 'Continue'
    cargo +1.98.0 build --offline --release *> build-webreader-host.log
    $taskExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($taskExit -ne 0) { throw 'Build failed; inspect Rinx-main/build-webreader-host.log' }
    Copy-Item -LiteralPath 'target/release/rinx.exe' -Destination 'target/release/rinx-webreader.exe'
} finally { Pop-Location }
