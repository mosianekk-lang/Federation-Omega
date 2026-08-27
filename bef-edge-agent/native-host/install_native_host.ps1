param(
  [Parameter(Mandatory=$true)][string]$HostExecutable,
  [switch]$EdgeOnly,
  [switch]$ChromeOnly
)

$ErrorActionPreference = 'Stop'
$HostName = 'com.sovara.bef_edge'
$ExpectedEdgeExtensionId = 'apokbhjjgiaceigelkedcelcecfmgnia'

$resolved = (Resolve-Path -LiteralPath $HostExecutable).Path
if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
  throw "NATIVE_HOST_EXECUTABLE_NOT_FOUND: $resolved"
}
if ([System.IO.Path]::GetExtension($resolved).ToLowerInvariant() -ne '.exe') {
  throw 'NATIVE_HOST_MUST_BE_EXE_FOR_PRODUCTION_REGISTRATION'
}

$root = Join-Path $env:LOCALAPPDATA 'SOVARA\BEF\native-host'
New-Item -ItemType Directory -Path $root -Force | Out-Null
$manifestPath = Join-Path $root "$HostName.json"

$manifest = [ordered]@{
  name = $HostName
  description = 'SOVARA BEF encrypted ChatBridge provenance courier'
  path = $resolved
  type = 'stdio'
  allowed_origins = @("chrome-extension://$ExpectedEdgeExtensionId/")
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$targets = @()
if (-not $ChromeOnly) {
  $targets += 'HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\' + $HostName
}
if (-not $EdgeOnly) {
  $targets += 'HKCU:\Software\Google\Chrome\NativeMessagingHosts\' + $HostName
}
foreach ($target in $targets) {
  New-Item -Path $target -Force | Out-Null
  Set-Item -Path $target -Value $manifestPath
}

$readback = foreach ($target in $targets) {
  [pscustomobject]@{
    RegistryPath = $target
    ManifestPath = (Get-Item -Path $target).GetValue('')
  }
}
$manifestReadback = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifestReadback.name -ne $HostName) { throw 'MANIFEST_NAME_READBACK_MISMATCH' }
if ($manifestReadback.path -ne $resolved) { throw 'MANIFEST_EXECUTABLE_READBACK_MISMATCH' }
if ($manifestReadback.allowed_origins.Count -ne 1 -or $manifestReadback.allowed_origins[0] -ne "chrome-extension://$ExpectedEdgeExtensionId/") {
  throw 'MANIFEST_ALLOWED_ORIGIN_READBACK_MISMATCH'
}

[pscustomobject]@{
  State = 'NATIVE_HOST_REGISTERED_VERIFIED'
  HostName = $HostName
  HostExecutable = $resolved
  ManifestPath = $manifestPath
  EdgeAgentExtensionId = $ExpectedEdgeExtensionId
  RegistryBindings = $readback
  TruthBoundary = 'Registration proves local native-host binding only; browser extension installation, live message delivery, DPF ingestion and whole-chat capture remain separate canaries.'
} | ConvertTo-Json -Depth 8
