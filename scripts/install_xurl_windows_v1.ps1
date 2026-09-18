$ErrorActionPreference = 'Stop'
$Version = '1.3.1'
$ExpectedSha256 = '6b5e7435daa98d03a620b2a31b8c78162601959a63274e945ae372c799073305'
$Uri = "https://github.com/xdevplatform/xurl/releases/download/v$Version/xurl_Windows_x86_64.zip"
$Root = Join-Path $env:LOCALAPPDATA 'FUSE\X\xurl\v1.3.1'
$Zip = Join-Path $env:TEMP "fuse_xurl_$Version.zip"
New-Item -ItemType Directory -Force -Path $Root | Out-Null
Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $Zip
$Actual = (Get-FileHash -Algorithm SHA256 $Zip).Hash.ToLowerInvariant()
if ($Actual -ne $ExpectedSha256) { Remove-Item -Force $Zip -ErrorAction SilentlyContinue; throw 'xurl release hash mismatch' }
Expand-Archive -Force -Path $Zip -DestinationPath $Root
Remove-Item -Force $Zip
$Exe = Get-ChildItem -Path $Root -Filter 'xurl.exe' -Recurse | Select-Object -First 1
if (-not $Exe) { throw 'xurl.exe missing after extraction' }
$VersionText = (& $Exe.FullName --version 2>&1 | Out-String).Trim()
Write-Output ('FUSE_XURL_READY=true')
Write-Output ('FUSE_XURL_VERSION=' + $VersionText)
Write-Output ('FUSE_XURL_PATH=' + $Exe.FullName)
# Do not inspect ~/.xurl, credentials, tokens, or browser cookies.
