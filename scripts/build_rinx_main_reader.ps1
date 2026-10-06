param(
    [string]$HostRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) '../../Rinx-main'),
    [string]$Python = 'C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskHost = (Resolve-Path -LiteralPath $HostRoot).Path
$taskCargo = Join-Path $taskRoot '.dev/vendor/cargo-home'
$taskMakepad = Join-Path $taskCargo 'git/checkouts/makepad-5b6485c20cc788f9/1f3b1de'
& $Python (Join-Path $PSScriptRoot 'patch_reader_host.py') --makepad-root $taskMakepad
if ($LASTEXITCODE -ne 0) { throw 'Reader host patch failed' }
$taskVs = & 'C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe' -latest -products '*' -property installationPath
Import-Module (Join-Path $taskVs 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
Enter-VsDevShell -VsInstallPath $taskVs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
$env:Path = (Join-Path $taskVs 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin') + ';' + (Join-Path $taskVs 'Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja') + ';' + $env:Path
$env:CARGO_HOME = $taskCargo
$env:CMAKE_GENERATOR = 'Ninja'
$env:MAKEPAD_PACKAGE_DIR = '.'
$env:CARGO_BUILD_JOBS = '4'
$taskPrevious = Get-Location
try {
    Set-Location -LiteralPath $taskHost
    # Git dependency timestamps alone do not invalidate Cargo's immutable cache.
    cargo +1.98.0 clean --release -p makepad-platform -p makepad-draw -p makepad-widgets
    if ($LASTEXITCODE -ne 0) { throw 'Could not invalidate the patched dependency artifacts' }
    $ErrorActionPreference = 'Continue'
    $taskBuildStart = Get-Date
    cargo +1.98.0 build --offline --locked --release *> build-reader-host.log
    $taskExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    $taskBuilt = Join-Path $taskHost 'target/release/deps/rinx.exe'
    if ($taskExit -ne 0) {
        $taskLog = Get-Content -LiteralPath build-reader-host.log -Raw
        if (-not ($taskLog -match 'failed to remove file' -and $taskLog -match 'os error 5' -and (Test-Path -LiteralPath $taskBuilt) -and (Get-Item -LiteralPath $taskBuilt).LastWriteTime -gt $taskBuildStart)) {
            throw 'Build failed; inspect Rinx-main/build-reader-host.log'
        }
        Write-Output 'Linked successfully; active original executable prevented Cargo promotion. Staging independent reader executable.'
    }
    Copy-Item -LiteralPath $taskBuilt -Destination (Join-Path $taskHost 'target/release/rinx-reader.exe')
} finally { Set-Location -LiteralPath $taskPrevious }
