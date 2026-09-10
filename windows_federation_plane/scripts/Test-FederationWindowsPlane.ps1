$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_RUNTIME_REQUIRED' }
$plane = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:PYTHONPATH = Join-Path $plane 'src'
python -m unittest discover -s (Join-Path $plane 'tests') -v
if ($LASTEXITCODE -ne 0) { throw 'WINDOWS_PLANE_TESTS_FAILED' }
& (Join-Path $PSScriptRoot 'Invoke-FederationWindowsTask.ps1') -Task health
