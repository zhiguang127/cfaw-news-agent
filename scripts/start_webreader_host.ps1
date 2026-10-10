param([string]$HostRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) '../../Rinx-main'))
$ErrorActionPreference = 'Stop'
$taskHost = (Resolve-Path -LiteralPath $HostRoot).Path
$taskExecutable = Join-Path $taskHost 'target/release/rinx-webreader.exe'
if (-not (Test-Path -LiteralPath $taskExecutable)) { throw 'Build the WebReader host first with build_webreader_host.ps1' }
# Interactive host window requested by this launcher; keep the user's app-data configuration.
Start-Process -FilePath $taskExecutable -WorkingDirectory (Join-Path $taskHost 'target/release') -WindowStyle Normal
