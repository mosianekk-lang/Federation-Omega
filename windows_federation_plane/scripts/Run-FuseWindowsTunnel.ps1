$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'WINDOWS_RUNTIME_REQUIRED' }
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = Join-Path $root 'config.json'
$secretPath = Join-Path $root 'control-plane-key.dpapi'
$stopPath = Join-Path $root 'STOP'
$logPath = Join-Path $root 'supervisor.jsonl'
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { throw 'TUNNEL_CONFIG_MISSING' }
if (-not (Test-Path -LiteralPath $secretPath -PathType Leaf)) { throw 'TUNNEL_SECRET_MISSING' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$secure = Get-Content -LiteralPath $secretPath -Raw | ConvertTo-SecureString
$plain = [Net.NetworkCredential]::new('', $secure).Password
$delay = 1
try {
  $env:CONTROL_PLANE_API_KEY = $plain
  while (-not (Test-Path -LiteralPath $stopPath)) {
    $started = [DateTime]::UtcNow
    & ([string]$config.tunnel_client_path) run --profile ([string]$config.profile)
    $exitCode = $LASTEXITCODE
    [ordered]@{time=[DateTime]::UtcNow.ToString('o');event='TUNNEL_CLIENT_EXIT';exit_code=$exitCode;runtime_seconds=[math]::Round(([DateTime]::UtcNow-$started).TotalSeconds,3);restart_delay_seconds=$delay} | ConvertTo-Json -Compress | Add-Content -LiteralPath $logPath -Encoding utf8
    if (Test-Path -LiteralPath $stopPath) { break }
    Start-Sleep -Seconds $delay
    $delay = [math]::Min(60, $delay * 2)
  }
} finally {
  $env:CONTROL_PLANE_API_KEY = $null
  $plain = $null
}
