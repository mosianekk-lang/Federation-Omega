@echo off
setlocal
set "HERE=%~dp0"
if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
powershell.exe -NoLogo -NoProfile -File "%HERE%Install-FuseNativeAgent.ps1" -RelayUrl "%~1" -EnrollmentFile "%~2" -SourceDirectory "%HERE%"
set "RC=%ERRORLEVEL%"
exit /b %RC%

:usage
echo Usage: FUSE-Native-OneClick.cmd https://relay.example enrollment-bootstrap.json
echo This launcher does not request elevation and does not bypass PowerShell execution policy.
exit /b 2
