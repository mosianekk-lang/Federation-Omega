[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [ValidateSet('Status','Restart','Suspend','Resume','Rollback')][string]$Action = 'Status',
  [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'FUSE\WindowsTunnel')
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'WINDOWS_RUNTIME_REQUIRED' }
$configPath = Join-Path $InstallRoot 'config.json'
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$stopPath = Join-Path $InstallRoot 'STOP'
$taskName = [string]$config.task_name
if ($Action -eq 'Status') { & (Join-Path $InstallRoot 'Test-FuseWindowsTunnel.ps1'); exit $LASTEXITCODE }
if (-not $PSCmdlet.ShouldProcess($taskName, $Action)) { return }
switch ($Action) {
  'Suspend' { New-Item -ItemType File -Force -Path $stopPath | Out-Null; Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue }
  'Resume' { Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue; Start-ScheduledTask -TaskName $taskName }
  'Restart' { Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue; Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue; Start-ScheduledTask -TaskName $taskName }
  'Rollback' {
    $previous = [string]$config.previous_release
    if (-not $previous -or -not (Test-Path -LiteralPath $previous -PathType Container)) { throw 'PREVIOUS_RELEASE_UNAVAILABLE' }
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    $current = [string]$config.current_release
    $config.current_release = $previous
    $config.previous_release = $current
    $venvPython = Join-Path $previous '.venv\Scripts\python.exe'
    $stdio = [System.Management.Automation.Language.CodeGeneration]::QuoteArgument($venvPython) + ' -m federation_windows_plane.tunnel_service --workspace ' + [System.Management.Automation.Language.CodeGeneration]::QuoteArgument([string]$config.workspace)
    $secure = Get-Content -LiteralPath (Join-Path $InstallRoot 'control-plane-key.dpapi') -Raw | ConvertTo-SecureString
    $plain = [Net.NetworkCredential]::new('', $secure).Password
    try { $env:CONTROL_PLANE_API_KEY=$plain; & ([string]$config.tunnel_client_path) init --sample sample_mcp_stdio_local --profile ([string]$config.profile) --tunnel-id ([string]$config.tunnel_id) --mcp-command $stdio; if($LASTEXITCODE-ne 0){throw'TUNNEL_ROLLBACK_PROFILE_FAILED'} } finally { $env:CONTROL_PLANE_API_KEY=$null; $plain=$null }
    $config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding utf8
    Start-ScheduledTask -TaskName $taskName
  }
}
[ordered]@{state=('RECOVERY_' + $Action.ToUpperInvariant());task_name=$taskName;current_release=[string]$config.current_release;rollback_available=[bool]([string]$config.previous_release)} | ConvertTo-Json -Depth 4
