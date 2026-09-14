[CmdletBinding()]
param([string]$Root = (Resolve-Path "$PSScriptRoot\.."))
$ErrorActionPreference = 'Stop'
$tools = @('git','python')
$result = [ordered]@{
  schema = 'FUSE-AIOS-WINDOWS-PREFLIGHT-V1'
  platform = [System.Environment]::OSVersion.VersionString
  powershell = $PSVersionTable.PSVersion.ToString()
  root = (Resolve-Path $Root).Path
  tools = @{}
  wsl = $false
  qemu = $false
  source_validation = $null
  cpu_inference = $null
  transactional_update = $null
  truth = 'WINDOWS_PREFLIGHT_CPU_INFERENCE_AND_TRANSACTIONAL_STATE_MACHINE_ONLY'
}
foreach ($t in $tools) {
  $cmd = Get-Command $t -ErrorAction SilentlyContinue
  $result.tools[$t] = [bool]$cmd
}
$result.wsl = [bool](Get-Command wsl.exe -ErrorAction SilentlyContinue)
$result.qemu = [bool](Get-Command qemu-system-x86_64.exe -ErrorAction SilentlyContinue)
$required = @('FUSE-AIOS-CONSTITUTION.md','architecture\SOVEREIGNTY-DEPENDENCY-GRAPH.json','architecture\CFBE-CAPABILITY-MATRIX.json','boot\boot-contract.json','ai\smoke-model.json','ai\inference_smoke.py','update\transactional_host.py','update\run_transactional_court.py')
$result.required_files_present = @($required | Where-Object { Test-Path (Join-Path $Root $_) }).Count
$result.required_files_total = $required.Count
if (-not $result.tools.python -or $result.required_files_present -ne $required.Count) {
  $result.status = 'HOLD'
  $result | ConvertTo-Json -Depth 10
  exit 2
}
$validate = & python (Join-Path $Root 'tests\validate_candidate.py') --root $Root 2>&1
if ($LASTEXITCODE -ne 0) { throw "FUSE_AIOS_SOURCE_VALIDATION_FAILED: $validate" }
$result.source_validation = ($validate -join "`n")
$inference = & python (Join-Path $Root 'ai\inference_smoke.py') --model (Join-Path $Root 'ai\smoke-model.json') 2>&1
if ($LASTEXITCODE -ne 0) { throw "FUSE_AIOS_CPU_INFERENCE_FAILED: $inference" }
$result.cpu_inference = ($inference -join "`n")
$transactional = & python (Join-Path $Root 'update\run_transactional_court.py') 2>&1
if ($LASTEXITCODE -ne 0) { throw "FUSE_AIOS_TRANSACTIONAL_UPDATE_COURT_FAILED: $transactional" }
$result.transactional_update = ($transactional -join "`n")
$result.status = 'PASS'
$result | ConvertTo-Json -Depth 10
