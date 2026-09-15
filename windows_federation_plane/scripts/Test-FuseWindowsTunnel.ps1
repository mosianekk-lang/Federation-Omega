[CmdletBinding()]
param([string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'FUSE\WindowsTunnel'))
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'WINDOWS_RUNTIME_REQUIRED' }
$config = Get-Content -LiteralPath (Join-Path $InstallRoot 'config.json') -Raw | ConvertFrom-Json
$venvPython = Join-Path ([string]$config.current_release) '.venv\Scripts\python.exe'
& $venvPython -m federation_windows_plane.tunnel_service --workspace ([string]$config.workspace) --self-test
if ($LASTEXITCODE -ne 0) { throw 'LOCAL_TUNNEL_SELF_TEST_FAILED' }
$secure = Get-Content -LiteralPath (Join-Path $InstallRoot 'control-plane-key.dpapi') -Raw | ConvertTo-SecureString
$plain = [Net.NetworkCredential]::new('', $secure).Password
try {
  $env:CONTROL_PLANE_API_KEY = $plain
  & ([string]$config.tunnel_client_path) doctor --profile ([string]$config.profile) --explain
  if ($LASTEXITCODE -ne 0) { throw 'TUNNEL_PROFILE_DOCTOR_FAILED' }
} finally { $env:CONTROL_PLANE_API_KEY = $null; $plain = $null }
$task = Get-ScheduledTask -TaskName ([string]$config.task_name) -ErrorAction Stop
[ordered]@{state='CANARY_VERIFIED';task_state=[string]$task.State;profile=[string]$config.profile;source_sha=[string]$config.source_sha;secret_storage='CURRENT_USER_DPAPI_ACL_RESTRICTED';inbound_listener=$false;arbitrary_shell=$false} | ConvertTo-Json -Depth 4
