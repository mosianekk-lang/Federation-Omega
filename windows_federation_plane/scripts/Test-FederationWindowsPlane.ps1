$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_RUNTIME_REQUIRED' }
$plane = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repo = (Resolve-Path (Join-Path $plane '..')).Path
$env:PYTHONPATH = Join-Path $plane 'src'
python -m unittest discover -s (Join-Path $plane 'tests') -v
if ($LASTEXITCODE -ne 0) { throw 'WINDOWS_PLANE_TESTS_FAILED' }
& (Join-Path $PSScriptRoot 'Invoke-FederationWindowsTask.ps1') -Task health

# Optional, bounded FUSE AI-OS integration court. This reuses the existing
# hosted-Windows execution plane without adding a scheduler, task type, secret,
# network permission, or arbitrary-command surface. Absence of the AI-OS tree
# leaves the Windows plane behavior unchanged.
$aiosRoot = Join-Path $repo 'fuse_aios'
$aiosPreflight = Join-Path $aiosRoot 'windows\Invoke-FuseAiosPreflight.ps1'
if (Test-Path $aiosPreflight) {
    Write-Host 'FUSE AI-OS candidate detected; running bounded Windows preflight.'
    & $aiosPreflight -Root $aiosRoot
    if (-not $?) { throw 'FUSE_AIOS_WINDOWS_PREFLIGHT_FAILED' }
}
