param(
  [string]$RepoRoot = '',
  [string]$HostExecutable = '',
  [string]$EdgeExecutable = '',
  [string]$CanaryProfileDir = '',
  [string]$ConversationUrl = 'https://chatgpt.com/',
  [int]$ReadbackTimeoutSeconds = 20,
  [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_RUNTIME_REQUIRED' }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $RepoRoot) { $RepoRoot = (Resolve-Path (Join-Path $scriptDir '..\..')).Path }
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$chatBridge = Join-Path $RepoRoot 'chatbridge-companion'
$edgeAgent = Join-Path $RepoRoot 'bef-edge-agent'
$nativeHost = Join-Path $edgeAgent 'native-host'
$buildScript = Join-Path $nativeHost 'build_native_host.ps1'
$installScript = Join-Path $nativeHost 'install_native_host.ps1'
$chatManifestPath = Join-Path $chatBridge 'manifest.json'
$edgeManifestPath = Join-Path $edgeAgent 'manifest.json'

foreach ($path in @($chatManifestPath, $edgeManifestPath, $buildScript, $installScript)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "RUNTIME_SOURCE_MISSING: $path" }
}

function Get-ChromiumExtensionId([string]$ManifestPath) {
  $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
  if (-not $manifest.key) { throw "MANIFEST_KEY_REQUIRED: $ManifestPath" }
  $bytes = [Convert]::FromBase64String([string]$manifest.key)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try { $digest = $sha.ComputeHash($bytes) } finally { $sha.Dispose() }
  $alphabet = 'abcdefghijklmnop'
  $chars = New-Object System.Collections.Generic.List[char]
  for ($i = 0; $i -lt 16; $i++) {
    $chars.Add($alphabet[($digest[$i] -shr 4) -band 0x0F])
    $chars.Add($alphabet[$digest[$i] -band 0x0F])
  }
  return -join $chars
}

function Quote-ProcessArgument([string]$Value) {
  if ($null -eq $Value) { return '""' }
  return '"' + ($Value -replace '"', '\"') + '"'
}

$chatId = Get-ChromiumExtensionId $chatManifestPath
$edgeId = Get-ChromiumExtensionId $edgeManifestPath
if ($chatId -ne 'kacbginamagliaddmlkffhcadpamomjb') { throw "CHATBRIDGE_EXTENSION_ID_DRIFT: $chatId" }
if ($edgeId -ne 'apokbhjjgiaceigelkedcelcecfmgnia') { throw "BEF_EDGE_EXTENSION_ID_DRIFT: $edgeId" }

$edgeManifest = Get-Content -LiteralPath $edgeManifestPath -Raw | ConvertFrom-Json
if (@($edgeManifest.externally_connectable.ids).Count -ne 1 -or $edgeManifest.externally_connectable.ids[0] -ne $chatId) {
  throw 'BEF_EXTERNALLY_CONNECTABLE_BINDING_DRIFT'
}

if (-not $HostExecutable) {
  $buildJson = & $buildScript
  if ($LASTEXITCODE -ne 0) { throw 'NATIVE_HOST_BUILD_FAILED' }
  $build = $buildJson | ConvertFrom-Json
  if ($build.State -ne 'NATIVE_HOST_EXE_BUILT_SELF_TEST_VERIFIED') { throw 'NATIVE_HOST_BUILD_NOT_VERIFIED' }
  $HostExecutable = [string]$build.Executable
}
$HostExecutable = (Resolve-Path -LiteralPath $HostExecutable).Path
if ([IO.Path]::GetExtension($HostExecutable).ToLowerInvariant() -ne '.exe') { throw 'NATIVE_HOST_EXE_REQUIRED' }

$installJson = & $installScript -HostExecutable $HostExecutable -EdgeOnly
if ($LASTEXITCODE -ne 0) { throw 'NATIVE_HOST_REGISTRATION_FAILED' }
$install = $installJson | ConvertFrom-Json
if ($install.State -ne 'NATIVE_HOST_REGISTERED_VERIFIED') { throw 'NATIVE_HOST_REGISTRATION_NOT_VERIFIED' }
if ($install.EdgeAgentExtensionId -ne $edgeId) { throw 'NATIVE_HOST_ALLOWED_ORIGIN_ID_DRIFT' }

if (-not $EdgeExecutable) {
  $candidates = New-Object System.Collections.Generic.List[string]
  $roots = @(${env:ProgramFiles(x86)}, $env:ProgramFiles, $env:LOCALAPPDATA)
  foreach ($root in $roots) {
    if (-not $root) { continue }
    $candidate = Join-Path $root 'Microsoft\Edge\Application\msedge.exe'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { $candidates.Add($candidate) }
  }
  if ($candidates.Count -eq 0) { throw 'MICROSOFT_EDGE_EXECUTABLE_NOT_FOUND' }
  $EdgeExecutable = $candidates[0]
}
$EdgeExecutable = (Resolve-Path -LiteralPath $EdgeExecutable).Path

if (-not $CanaryProfileDir) { $CanaryProfileDir = Join-Path $env:LOCALAPPDATA 'SOVARA\BEF\EdgeCanaryProfile' }
New-Item -ItemType Directory -Path $CanaryProfileDir -Force | Out-Null

$receiptRoot = Join-Path $env:LOCALAPPDATA 'SOVARA\BEF\runtime-receipts'
New-Item -ItemType Directory -Path $receiptRoot -Force | Out-Null
$timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$receiptPath = Join-Path $receiptRoot "bef-chatbridge-bootstrap-$timestamp.json"

$receipt = [ordered]@{
  schema = 'SOVARA-BEF-CHATBRIDGE-WINDOWS-CANARY-BOOTSTRAP-1'
  state = 'NATIVE_HOST_REGISTERED_CANARY_PROFILE_PREPARED'
  observedAt = (Get-Date).ToUniversalTime().ToString('o')
  repoRoot = $RepoRoot
  chatBridgeExtensionId = $chatId
  befEdgeExtensionId = $edgeId
  chatBridgeManifestSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $chatManifestPath).Hash.ToLowerInvariant()
  befEdgeManifestSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $edgeManifestPath).Hash.ToLowerInvariant()
  nativeHostExecutable = $HostExecutable
  nativeHostSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $HostExecutable).Hash.ToLowerInvariant()
  nativeHostRegistrationState = [string]$install.State
  nativeHostManifestPath = [string]$install.ManifestPath
  edgeExecutable = $EdgeExecutable
  canaryProfileDir = $CanaryProfileDir
  edgeLaunched = $false
  extensionReadback = 'NOT_ATTEMPTED'
  truthBoundary = 'Build and native-host registration are local-runtime evidence. Browser extension load, ChatGPT authentication, live cross-extension delivery, DPAPI spool capture and DPF reconstruction remain separate readback gates.'
}

if (-not $NoLaunch) {
  $userDataArg = '--user-data-dir=' + (Quote-ProcessArgument $CanaryProfileDir)
  $extensionsArg = '--load-extension=' + (Quote-ProcessArgument ($chatBridge + ',' + $edgeAgent))
  $arguments = @(
    $userDataArg,
    $extensionsArg,
    '--no-first-run',
    '--no-default-browser-check',
    (Quote-ProcessArgument $ConversationUrl)
  )
  $process = Start-Process -FilePath $EdgeExecutable -ArgumentList $arguments -PassThru
  $receipt.edgeLaunched = $true
  $receipt.edgeProcessId = $process.Id

  $preferences = Join-Path $CanaryProfileDir 'Default\Preferences'
  $deadline = (Get-Date).AddSeconds([Math]::Max(1, $ReadbackTimeoutSeconds))
  $readback = 'PENDING'
  do {
    Start-Sleep -Milliseconds 500
    if (Test-Path -LiteralPath $preferences -PathType Leaf) {
      try {
        $prefs = Get-Content -LiteralPath $preferences -Raw | ConvertFrom-Json
        $settings = $prefs.extensions.settings
        $chatLoaded = $null -ne $settings.$chatId
        $edgeLoaded = $null -ne $settings.$edgeId
        if ($chatLoaded -and $edgeLoaded) { $readback = 'BOTH_EXTENSIONS_PRESENT_IN_PROFILE_PREFERENCES'; break }
      } catch {
        $readback = 'PREFERENCES_PRESENT_READBACK_PENDING'
      }
    }
  } while ((Get-Date) -lt $deadline)
  $receipt.extensionReadback = $readback
  if ($readback -eq 'BOTH_EXTENSIONS_PRESENT_IN_PROFILE_PREFERENCES') {
    $receipt.state = 'BROWSER_EXTENSIONS_PROFILE_READBACK_VERIFIED'
  }
}

$receiptJson = $receipt | ConvertTo-Json -Depth 10
$receiptJson | Set-Content -LiteralPath $receiptPath -Encoding UTF8
$receiptSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $receiptPath).Hash.ToLowerInvariant()

[pscustomobject]@{
  State = $receipt.state
  ReceiptPath = $receiptPath
  ReceiptSha256 = $receiptSha
  ChatBridgeExtensionId = $chatId
  BefEdgeExtensionId = $edgeId
  ExtensionReadback = $receipt.extensionReadback
  TruthBoundary = $receipt.truthBoundary
} | ConvertTo-Json -Depth 8
