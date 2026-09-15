[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [Parameter(Mandatory = $true)][ValidatePattern('^tunnel_[A-Za-z0-9_-]{16,128}$')][string]$TunnelId,
  [Security.SecureString]$ControlPlaneApiKey,
  [string]$Workspace = '',
  [string]$PlaneRoot = '',
  [string]$TunnelClientPath = '',
  [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')][string]$Profile = 'fuse-windows',
  [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'FUSE\WindowsTunnel'),
  [switch]$NoStart
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'WINDOWS_RUNTIME_REQUIRED' }
if (-not $PlaneRoot) { $PlaneRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
if (-not $Workspace) { $Workspace = (Resolve-Path (Join-Path $PlaneRoot '..')).Path }
$Workspace = (Resolve-Path -LiteralPath $Workspace).Path
if (-not (Test-Path -LiteralPath $Workspace -PathType Container)) { throw 'WORKSPACE_DIRECTORY_REQUIRED' }
if (-not $TunnelClientPath) { $TunnelClientPath = (Get-Command tunnel-client -ErrorAction Stop).Source }
$TunnelClientPath = (Resolve-Path -LiteralPath $TunnelClientPath).Path
if (-not $ControlPlaneApiKey) {
  if (-not $env:CONTROL_PLANE_API_KEY) { throw 'CONTROL_PLANE_API_KEY_REQUIRED' }
  $ControlPlaneApiKey = ConvertTo-SecureString $env:CONTROL_PLANE_API_KEY -AsPlainText -Force
}
$python = (Get-Command python -ErrorAction Stop).Source
$sourceSha = if ($env:FEDERATION_SOURCE_SHA) { $env:FEDERATION_SOURCE_SHA } else { 'local-' + (Get-Date -Format 'yyyyMMddHHmmss') }
if ($sourceSha -notmatch '^[A-Za-z0-9_.-]{8,80}$') { throw 'SOURCE_SHA_INVALID' }
$releaseRoot = Join-Path $InstallRoot ('releases\' + $sourceSha)
$configPath = Join-Path $InstallRoot 'config.json'
$secretPath = Join-Path $InstallRoot 'control-plane-key.dpapi'
$runnerPath = Join-Path $InstallRoot 'Run-FuseWindowsTunnel.ps1'
$taskName = 'FUSE Windows Secure MCP Tunnel'

if (-not $PSCmdlet.ShouldProcess($InstallRoot, 'Install and supervise FUSE Windows Secure MCP Tunnel')) { return }
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $PlaneRoot 'src') -Destination $releaseRoot -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PlaneRoot 'pyproject.toml') -Destination $releaseRoot -Force
Copy-Item -LiteralPath (Join-Path $PlaneRoot 'requirements-relay.lock') -Destination $releaseRoot -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Run-FuseWindowsTunnel.ps1') -Destination $runnerPath -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Test-FuseWindowsTunnel.ps1') -Destination (Join-Path $InstallRoot 'Test-FuseWindowsTunnel.ps1') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Repair-FuseWindowsTunnel.ps1') -Destination (Join-Path $InstallRoot 'Repair-FuseWindowsTunnel.ps1') -Force

$venv = Join-Path $releaseRoot '.venv'
& $python -m venv $venv
if ($LASTEXITCODE -ne 0) { throw 'VENV_CREATION_FAILED' }
$venvPython = Join-Path $venv 'Scripts\python.exe'
& $venvPython -m pip install --disable-pip-version-check --require-hashes -r (Join-Path $releaseRoot 'requirements-relay.lock')
if ($LASTEXITCODE -ne 0) { throw 'HASH_LOCKED_DEPENDENCY_INSTALL_FAILED' }
& $venvPython -m pip install --disable-pip-version-check --no-deps $releaseRoot
if ($LASTEXITCODE -ne 0) { throw 'FUSE_PACKAGE_INSTALL_FAILED' }
& $venvPython -m federation_windows_plane.tunnel_service --workspace $Workspace --self-test
if ($LASTEXITCODE -ne 0) { throw 'LOCAL_TUNNEL_SELF_TEST_FAILED' }

$previousRelease = ''
if (Test-Path -LiteralPath $configPath -PathType Leaf) {
  $old = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
  $previousRelease = [string]$old.current_release
}
$encrypted = ConvertFrom-SecureString $ControlPlaneApiKey
Set-Content -LiteralPath $secretPath -Value $encrypted -Encoding ascii -NoNewline
$acl = Get-Acl -LiteralPath $secretPath
$acl.SetAccessRuleProtection($true, $false)
$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$rule = New-Object Security.AccessControl.FileSystemAccessRule($currentIdentity, 'FullControl', 'Allow')
$acl.SetAccessRule($rule)
Set-Acl -LiteralPath $secretPath -AclObject $acl

$stdio = [System.Management.Automation.Language.CodeGeneration]::QuoteArgument($venvPython) + ' -m federation_windows_plane.tunnel_service --workspace ' + [System.Management.Automation.Language.CodeGeneration]::QuoteArgument($Workspace)
$plain = [Net.NetworkCredential]::new('', $ControlPlaneApiKey).Password
try {
  $env:CONTROL_PLANE_API_KEY = $plain
  & $TunnelClientPath init --sample sample_mcp_stdio_local --profile $Profile --tunnel-id $TunnelId --mcp-command $stdio
  if ($LASTEXITCODE -ne 0) { throw 'TUNNEL_PROFILE_INIT_FAILED' }
  & $TunnelClientPath doctor --profile $Profile --explain
  if ($LASTEXITCODE -ne 0) { throw 'TUNNEL_PROFILE_DOCTOR_FAILED' }
} finally {
  $env:CONTROL_PLANE_API_KEY = $null
  $plain = $null
}

[ordered]@{
  schema = 'FUSE-WINDOWS-TUNNEL-INSTALL-V1'
  version = '2.5.0'
  tunnel_id = $TunnelId
  profile = $Profile
  workspace = $Workspace
  tunnel_client_path = $TunnelClientPath
  current_release = $releaseRoot
  previous_release = $previousRelease
  installed_at = [DateTime]::UtcNow.ToString('o')
  source_sha = $sourceSha
  task_name = $taskName
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding utf8

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoLogo -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File "' + $runnerPath + '"')
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User $env:USERNAME -RunLevel Limited -Force | Out-Null
if (-not $NoStart) { Start-ScheduledTask -TaskName $taskName }

[ordered]@{
  state = if ($NoStart) { 'INSTALLED_NOT_STARTED' } else { 'INSTALLED_AND_START_REQUESTED' }
  profile = $Profile
  task_name = $taskName
  current_release = $releaseRoot
  secret_storage = 'CURRENT_USER_DPAPI_ACL_RESTRICTED'
  inbound_listener = $false
  arbitrary_shell = $false
  manual_user_tasks = @()
} | ConvertTo-Json -Depth 5
