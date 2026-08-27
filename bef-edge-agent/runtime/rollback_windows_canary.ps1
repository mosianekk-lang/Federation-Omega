param(
  [string]$CanaryProfileDir = '',
  [switch]$RemoveCanaryProfile,
  [switch]$RemoveNativeHostFiles
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_RUNTIME_REQUIRED' }
if (-not $CanaryProfileDir) { $CanaryProfileDir = Join-Path $env:LOCALAPPDATA 'SOVARA\BEF\EdgeCanaryProfile' }

$hostName = 'com.sovara.bef_edge'
$registryPath = 'HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\' + $hostName
$manifestPath = $null
if (Test-Path $registryPath) {
  try { $manifestPath = (Get-Item -Path $registryPath).GetValue('') } catch { }
  Remove-Item -Path $registryPath -Recurse -Force
}

# Stop only Edge processes whose command line is bound to this dedicated canary profile.
$stopped = @()
try {
  $escaped = [Regex]::Escape($CanaryProfileDir)
  $processes = Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" | Where-Object {
    $_.CommandLine -and $_.CommandLine -match $escaped
  }
  foreach ($process in $processes) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    $stopped += [int]$process.ProcessId
  }
} catch { }

$profileRemoved = $false
if ($RemoveCanaryProfile -and (Test-Path -LiteralPath $CanaryProfileDir)) {
  Remove-Item -LiteralPath $CanaryProfileDir -Recurse -Force
  $profileRemoved = $true
}

$nativeFilesRemoved = $false
if ($RemoveNativeHostFiles) {
  $root = Join-Path $env:LOCALAPPDATA 'SOVARA\BEF\native-host'
  if (Test-Path -LiteralPath $root) {
    Remove-Item -LiteralPath $root -Recurse -Force
    $nativeFilesRemoved = $true
  }
}

$spoolRoot = Join-Path $env:LOCALAPPDATA 'SOVARA\BEF\ChatBridgeSpool'
[pscustomobject]@{
  Schema = 'SOVARA-BEF-CHATBRIDGE-WINDOWS-ROLLBACK-1'
  State = 'CANARY_RUNTIME_BINDING_ROLLED_BACK'
  RegistryBindingRemoved = -not (Test-Path $registryPath)
  StoppedCanaryEdgeProcessIds = $stopped
  CanaryProfileRemoved = $profileRemoved
  NativeHostFilesRemoved = $nativeFilesRemoved
  EncryptedSpoolPreserved = (Test-Path -LiteralPath $spoolRoot)
  TruthBoundary = 'Rollback removes the local canary binding without deleting the encrypted evidence spool by default. Spool deletion requires a separate explicit retention decision.'
} | ConvertTo-Json -Depth 8
