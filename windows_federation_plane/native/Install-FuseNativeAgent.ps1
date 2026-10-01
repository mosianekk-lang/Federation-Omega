[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RelayUrl,
    [Parameter(Mandatory = $true)][string]$EnrollmentFile,
    [string]$SourceDirectory = $PSScriptRoot,
    [string]$Workspace = (Join-Path $env:USERPROFILE 'FUSE-Workspace'),
    [switch]$NoScheduledTask,
    [switch]$SkipFirstPoll
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_RUNTIME_REQUIRED' }
if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA_REQUIRED' }
if (-not $env:USERPROFILE) { throw 'USERPROFILE_REQUIRED' }

$relay = [Uri]$RelayUrl
if ($relay.Scheme -ne 'https') { throw 'RELAY_HTTPS_REQUIRED' }
if ($relay.UserInfo -or $relay.Query -or $relay.Fragment) { throw 'RELAY_URL_COMPONENT_INVALID' }

$source = (Resolve-Path -LiteralPath $SourceDirectory).Path
$enrollment = (Resolve-Path -LiteralPath $EnrollmentFile).Path
$enrollmentInfo = Get-Item -LiteralPath $enrollment
if ($enrollmentInfo.Length -lt 8 -or $enrollmentInfo.Length -gt 16384) { throw 'ENROLLMENT_FILE_INVALID' }

$required = @(
    'Fuse.Windows.Native.exe',
    'Fuse.Windows.Native.dll',
    'Fuse.Windows.Native.deps.json',
    'Fuse.Windows.Native.runtimeconfig.json'
)
foreach ($name in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $source $name) -PathType Leaf)) {
        throw "NATIVE_PACKAGE_FILE_MISSING:$name"
    }
}

$root = Join-Path $env:LOCALAPPDATA 'FUSE\SovereignRuntime'
$bin = Join-Path $root 'bin'
$state = Join-Path $root 'state'
$config = Join-Path $root 'agent-config.json'
New-Item -ItemType Directory -Force -Path $bin, $state, $Workspace | Out-Null

foreach ($name in $required) {
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $bin $name) -Force
}
$exe = Join-Path $bin 'Fuse.Windows.Native.exe'
$exeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash.ToLowerInvariant()

$sourceSha = 'UNBOUND_SOURCE'
try {
    $metadata = & $exe execute --task-json (Join-Path $state '__nonexistent_source_probe__.json') --state-dir $state 2>&1
} catch {
    # The executable source epoch is verified by signed runtime receipts after a real task.
}

$configuration = [ordered]@{
    schema = 'FUSE-WINDOWS-NATIVE-AGENT-CONFIG-V1'
    relay_origin = $relay.GetLeftPart([UriPartial]::Authority)
    state_directory = $state
    workspace = (Resolve-Path -LiteralPath $Workspace).Path
    executable_sha256 = $exeHash
    source_epoch = $sourceSha
    arbitrary_shell_enabled = $false
    inbound_listener_enabled = $false
    requires_elevation = $false
}
$configuration | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $config -Encoding utf8NoBOM

$agentArgs = @(
    'agent-loop',
    '--relay-url', ('"' + $relay.GetLeftPart([UriPartial]::Authority) + '"'),
    '--state-dir', ('"' + $state + '"'),
    '--workspace', ('"' + (Resolve-Path -LiteralPath $Workspace).Path + '"'),
    '--enrollment-file', ('"' + $enrollment + '"'),
    '--poll-seconds', '5'
) -join ' '

if (-not $NoScheduledTask) {
    $taskName = 'FUSE Sovereign Native Agent'
    $principalId = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } else { $env:USERNAME }
    $action = New-ScheduledTaskAction -Execute $exe -Argument $agentArgs
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $principalId
    $principal = New-ScheduledTaskPrincipal -UserId $principalId -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Days 30)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
}

if (-not $SkipFirstPoll) {
    & $exe agent-once --relay-url $relay.GetLeftPart([UriPartial]::Authority) --state-dir $state --workspace (Resolve-Path -LiteralPath $Workspace).Path --enrollment-file $enrollment --poll-seconds 5
    if ($LASTEXITCODE -ne 0) { throw "NATIVE_AGENT_FIRST_POLL_FAILED:$LASTEXITCODE" }
}

[ordered]@{
    schema = 'FUSE-WINDOWS-NATIVE-INSTALL-RECEIPT-V1'
    state = 'INSTALLED_CURRENT_USER'
    install_root = $root
    executable_sha256 = $exeHash
    relay_origin = $relay.GetLeftPart([UriPartial]::Authority)
    scheduled_task_registered = (-not $NoScheduledTask)
    first_poll_requested = (-not $SkipFirstPoll)
    admin_required = $false
    execution_policy_bypass = $false
    firewall_mutation = $false
    defender_mutation = $false
    inbound_listener = $false
    arbitrary_shell = $false
} | ConvertTo-Json -Compress
