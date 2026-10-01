param()
$ErrorActionPreference='Stop'
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$Core=Join-Path $Here 'install_core_current_user.ps1'
if(Test-Path $Core){ & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Core; if($LASTEXITCODE -ne 0){ throw 'CORE_INSTALL_FAILED' } }
$Target=Join-Path $env:LOCALAPPDATA 'FUSE\LocalLLM'
$Fabric=Join-Path $Target 'provider-fabric'
New-Item -ItemType Directory -Force -Path $Fabric | Out-Null
Copy-Item (Join-Path $Here 'provider-fabric\*') $Fabric -Recurse -Force
$cmd=Join-Path $Target 'FUSE-LocalLLM-Hybrid.cmd'
$content='@echo off'+[Environment]::NewLine+'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%LOCALAPPDATA%\FUSE\LocalLLM\provider-fabric\FUSE-LocalLLM-ProviderFabric.ps1" %*'
[IO.File]::WriteAllText($cmd,$content,[Text.ASCIIEncoding]::new())
$receipt=[ordered]@{schema='FUSE_LOCALLLM_HYBRID_INSTALL_RECEIPT_V1';overlay_version='0.3.0';target=$Target;provider_fabric=$Fabric;hybrid_command=$cmd;installed_at_utc=(Get-Date).ToUniversalTime().ToString('o')}
$receipt | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $Target 'HYBRID_INSTALL_RECEIPT.json') -Encoding UTF8
$receipt | ConvertTo-Json -Depth 6
