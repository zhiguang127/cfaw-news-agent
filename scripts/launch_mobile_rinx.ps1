$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskPython = 'C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython = (Get-Command python -ErrorAction Stop).Source }
$env:Path = (Split-Path -Parent $taskPython) + ';' + $env:Path
if (Test-Path 'build/git-safe-directories.config') { $env:GIT_CONFIG_GLOBAL = (Resolve-Path 'build/git-safe-directories.config').Path }
# Restore the user's existing host account without exporting its credentials.
$env:RINX_DATA_DIR = Join-Path $env:APPDATA 'octosense/rinx/data'
Remove-Item Env:RINX_OCTOS_BIN -ErrorAction SilentlyContinue
& "$PSScriptRoot/run_windows.ps1" -Mode Rinx
