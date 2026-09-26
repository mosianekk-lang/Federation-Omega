param()
$ErrorActionPreference='Stop'
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$Core=Join-Path $Here 'uninstall_core_current_user.ps1'
$Target=Join-Path $env:LOCALAPPDATA 'FUSE\LocalLLM'
Remove-Item (Join-Path $Target 'provider-fabric') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Target 'FUSE-LocalLLM-Hybrid.cmd') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Target 'HYBRID_INSTALL_RECEIPT.json') -Force -ErrorAction SilentlyContinue
if(Test-Path $Core){ & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Core }
