param()
$ErrorActionPreference="Stop"
Set-Location "$PSScriptRoot\.."
$dst=Join-Path $env:LOCALAPPDATA "Programs\FUSE LocalLLM"
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item "dist\FUSE-LocalLLM.exe" $dst -Force
Copy-Item "dist\FUSE-LocalLLM-Desktop.exe" $dst -Force
Copy-Item "dist\BUILD_RECEIPT.json" $dst -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force (Join-Path $env:LOCALAPPDATA "FUSE\LocalLLM\models") | Out-Null

$ws=New-Object -ComObject WScript.Shell
$startMenu=Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$link=$ws.CreateShortcut((Join-Path $startMenu "FUSE LocalLLM.lnk"))
$link.TargetPath=Join-Path $dst "FUSE-LocalLLM-Desktop.exe"
$link.WorkingDirectory=$dst
$link.Description="FUSE LocalLLM Desktop"
$link.Save()

$desktop=[Environment]::GetFolderPath("Desktop")
$dlink=$ws.CreateShortcut((Join-Path $desktop "FUSE LocalLLM.lnk"))
$dlink.TargetPath=Join-Path $dst "FUSE-LocalLLM-Desktop.exe"
$dlink.WorkingDirectory=$dst
$dlink.Description="FUSE LocalLLM Desktop"
$dlink.Save()

Write-Host "Installed FUSE LocalLLM Desktop."
Write-Host "Launch from Start Menu or Desktop: FUSE LocalLLM"
