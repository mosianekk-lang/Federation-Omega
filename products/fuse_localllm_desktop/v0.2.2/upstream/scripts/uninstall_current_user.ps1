$ErrorActionPreference="SilentlyContinue"
Stop-Process -Name "FUSE-LocalLLM" -Force
$dst=Join-Path $env:LOCALAPPDATA "Programs\FUSE LocalLLM"
Remove-Item $dst -Recurse -Force
Remove-Item (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\FUSE LocalLLM.lnk") -Force
Remove-Item (Join-Path ([Environment]::GetFolderPath("Desktop")) "FUSE LocalLLM.lnk") -Force
Write-Host "Removed app binaries and shortcuts. Models/data under %LOCALAPPDATA%\FUSE\LocalLLM are preserved."
