param(
  [string]$RepoRoot = '',
  [string]$CanaryProfileDir = '',
  [string]$ConversationKey = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_RUNTIME_REQUIRED' }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $RepoRoot) { $RepoRoot = (Resolve-Path (Join-Path $scriptDir '..\..')).Path }
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $CanaryProfileDir) { $CanaryProfileDir = Join-Path $env:LOCALAPPDATA 'SOVARA\BEF\EdgeCanaryProfile' }

$chatId = 'kacbginamagliaddmlkffhcadpamomjb'
$edgeId = 'apokbhjjgiaceigelkedcelcecfmgnia'
$hostName = 'com.sovara.bef_edge'
$registryPath = 'HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\' + $hostName

$nativeRegistered = $false
$manifestValid = $false
$hostExecutableValid = $false
$manifestPath = $null
$hostExecutable = $null
$hostSha256 = $null
if (Test-Path $registryPath) {
  $manifestPath = (Get-Item -Path $registryPath).GetValue('')
  if ($manifestPath -and (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    $nativeRegistered = $true
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $manifestValid = (
      $manifest.name -eq $hostName -and
      @($manifest.allowed_origins).Count -eq 1 -and
      $manifest.allowed_origins[0] -eq "chrome-extension://$edgeId/"
    )
    $hostExecutable = [string]$manifest.path
    if ($hostExecutable -and (Test-Path -LiteralPath $hostExecutable -PathType Leaf)) {
      $hostExecutableValid = $true
      $hostSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $hostExecutable).Hash.ToLowerInvariant()
    }
  }
}

$preferences = Join-Path $CanaryProfileDir 'Default\Preferences'
$chatLoaded = $false
$edgeLoaded = $false
if (Test-Path -LiteralPath $preferences -PathType Leaf) {
  try {
    $prefs = Get-Content -LiteralPath $preferences -Raw | ConvertFrom-Json
    $settings = $prefs.extensions.settings
    $chatLoaded = $null -ne $settings.$chatId
    $edgeLoaded = $null -ne $settings.$edgeId
  } catch {
    $chatLoaded = $false
    $edgeLoaded = $false
  }
}

$spoolRoot = Join-Path $env:LOCALAPPDATA 'SOVARA\BEF\ChatBridgeSpool'
$receiptDir = Join-Path $spoolRoot 'receipts'
$receipts = @()
if (Test-Path -LiteralPath $receiptDir -PathType Container) {
  foreach ($path in Get-ChildItem -LiteralPath $receiptDir -Filter '*.json' -File | Sort-Object Name) {
    try {
      $row = Get-Content -LiteralPath $path.FullName -Raw | ConvertFrom-Json
      if (-not $ConversationKey -or [string]$row.conversationKey -eq $ConversationKey) {
        $receipts += $row
      }
    } catch { }
  }
}
$latest = $null
if ($receipts.Count -gt 0) {
  $latest = $receipts | Sort-Object @{Expression={ [int]$_.toAppendSequence }}, @{Expression={ [string]$_.observedAt }} | Select-Object -Last 1
}

$state = 'RUNTIME_NOT_BOUND'
if ($nativeRegistered -and $manifestValid -and $hostExecutableValid) { $state = 'NATIVE_HOST_REGISTERED_VERIFIED' }
if ($state -eq 'NATIVE_HOST_REGISTERED_VERIFIED' -and $chatLoaded -and $edgeLoaded) { $state = 'BROWSER_PROFILE_BINDING_VERIFIED' }
if ($state -eq 'BROWSER_PROFILE_BINDING_VERIFIED' -and $latest) { $state = 'LIVE_ENCRYPTED_SPOOL_RECEIPT_OBSERVED' }

$result = [ordered]@{
  schema = 'SOVARA-BEF-CHATBRIDGE-WINDOWS-RUNTIME-READBACK-1'
  state = $state
  observedAt = (Get-Date).ToUniversalTime().ToString('o')
  nativeHostRegistered = $nativeRegistered
  nativeHostManifestValid = $manifestValid
  nativeHostExecutableValid = $hostExecutableValid
  nativeHostManifestPath = $manifestPath
  nativeHostExecutable = $hostExecutable
  nativeHostSha256 = $hostSha256
  chatBridgeExtensionId = $chatId
  chatBridgeProfilePresent = $chatLoaded
  befEdgeExtensionId = $edgeId
  befEdgeProfilePresent = $edgeLoaded
  encryptedSpoolReceiptCount = $receipts.Count
  latestSpoolReceiptId = if ($latest) { [string]$latest.receiptId } else { $null }
  latestEnvelopeSha256 = if ($latest) { [string]$latest.envelopeSha256 } else { $null }
  latestToAppendSequence = if ($latest) { [int]$latest.toAppendSequence } else { $null }
  latestStoredEncrypted = if ($latest) { [bool]$latest.storedEncrypted } else { $false }
  conversationFilter = if ($ConversationKey) { $ConversationKey } else { $null }
  truthBoundary = 'Spool receipt proves browser-to-native encrypted courier delivery only for the recorded rendered-DOM scope. It does not prove provider-native hidden events, complete DPF reconciliation, successor-chat restore, or external provider execution.'
}

$result | ConvertTo-Json -Depth 8
