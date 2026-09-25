@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\build_windows.ps1"
if errorlevel 1 pause & exit /b %errorlevel%
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\install_current_user.ps1"
if errorlevel 1 pause & exit /b %errorlevel%
start "" "%LOCALAPPDATA%\Programs\FUSE LocalLLM\FUSE-LocalLLM-Desktop.exe"
