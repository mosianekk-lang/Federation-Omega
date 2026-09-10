param(
  [ValidateSet('health','inventory','hash_workspace_file')]
  [string]$Task = 'health',
  [string]$RelativePath = '',
  [string]$RepoRoot = '',
  [string]$ReceiptPath = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_RUNTIME_REQUIRED' }
if (-not $RepoRoot) { $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path }
$plane = Join-Path $RepoRoot 'windows_federation_plane'
if (-not (Test-Path -LiteralPath $plane -PathType Container)) { throw 'WINDOWS_PLANE_SOURCE_MISSING' }
if (-not $ReceiptPath) { $ReceiptPath = Join-Path $plane 'receipts\windows-plane-receipt.json' }
$python = Get-Command python -ErrorAction Stop
$env:PYTHONPATH = Join-Path $plane 'src'
$arguments = @('-m','federation_windows_plane.cli','--workspace',$RepoRoot,'--task',$Task,'--receipt',$ReceiptPath)
if ($Task -eq 'hash_workspace_file') {
  if (-not $RelativePath) { throw 'RELATIVE_PATH_REQUIRED' }
  $arguments += @('--relative-path',$RelativePath)
}
& $python.Source @arguments
if ($LASTEXITCODE -ne 0) { throw 'WINDOWS_PLANE_TASK_FAILED' }
$receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
if ($receipt.schema -ne 'FEDERATION-WINDOWS-RECEIPT-V1' -or $receipt.state -ne 'COMPLETED_VERIFIED_LOCAL') {
  throw 'WINDOWS_PLANE_RECEIPT_INVALID'
}
[pscustomobject]@{
  State = 'WINDOWS_PLANE_TASK_READBACK_VERIFIED'
  TaskId = [string]$receipt.task_id
  CorrelationId = [string]$receipt.correlation_id
  ResultSha256 = [string]$receipt.result_sha256
  ReceiptPath = (Resolve-Path -LiteralPath $ReceiptPath).Path
  TruthBoundary = [string]$receipt.truth_boundary
} | ConvertTo-Json -Depth 6
