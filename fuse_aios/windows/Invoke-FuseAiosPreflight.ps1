[CmdletBinding()]
param([string]$Root = (Resolve-Path "$PSScriptRoot\.."))
$ErrorActionPreference = 'Stop'
$tools = @('git','python')
$result = [ordered]@{
  schema = 'FUSE-AIOS-WINDOWS-PREFLIGHT-V1'
  platform = [System.Environment]::OSVersion.VersionString
  powershell = $PSVersionTable.PSVersion.ToString()
  root = $Root
  tools = @{}
  wsl = $false
  qemu = $false
  truth = 'WINDOWS_PREFLIGHT_ONLY'
}
foreach ($t in $tools) {
  $cmd = Get-Command $t -ErrorAction SilentlyContinue
  $result.tools[$t] = [bool]$cmd
}
$result.wsl = [bool](Get-Command wsl.exe -ErrorAction SilentlyContinue)
$result.qemu = [bool](Get-Command qemu-system-x86_64.exe -ErrorAction SilentlyContinue)
$required = @('FUSE-AIOS-CONSTITUTION.md','architecture\SOVEREIGNTY-DEPENDENCY-GRAPH.json','architecture\CFBE-CAPABILITY-MATRIX.json')
$result.required_files_present = @($required | Where-Object { Test-Path (Join-Path $Root $_) }).Count
$result.required_files_total = $required.Count
$result.status = if ($result.tools.python -and $result.required_files_present -eq $required.Count) { 'PASS' } else { 'HOLD' }
$result | ConvertTo-Json -Depth 6
if ($result.status -ne 'PASS') { exit 2 }
