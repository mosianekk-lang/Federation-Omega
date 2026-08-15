[CmdletBinding()]
param(
    [string]$ExtensionPath = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-PolicyValue {
    param([string]$Path, [string]$Name)
    try {
        return (Get-ItemProperty -LiteralPath $Path -Name $Name -ErrorAction Stop).$Name
    }
    catch {
        return $null
    }
}

function Get-PolicyList {
    param([string]$Path)
    try {
        $item = Get-ItemProperty -LiteralPath $Path -ErrorAction Stop
        return @(
            $item.PSObject.Properties |
                Where-Object { $_.Name -notlike "PS*" } |
                ForEach-Object { [string]$_.Value }
        )
    }
    catch {
        return @()
    }
}

function Get-DefaultInstallationMode {
    param([object]$RawValue)
    if ($null -eq $RawValue -or [string]::IsNullOrWhiteSpace([string]$RawValue)) {
        return $null
    }
    try {
        $settings = ([string]$RawValue) | ConvertFrom-Json
        $defaultProperty = $settings.PSObject.Properties["*"]
        if ($null -eq $defaultProperty -or $null -eq $defaultProperty.Value) {
            return $null
        }
        return [string]$defaultProperty.Value.installation_mode
    }
    catch {
        return "INVALID_JSON"
    }
}

function Find-FirstExistingPath {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return $candidate
        }
    }
    return $null
}

function Get-BrowserAssessment {
    param(
        [string]$Name,
        [string]$PolicyRoot,
        [string[]]$ExecutableCandidates,
        [bool]$HasDeveloperModePolicy
    )

    $developerMode = if ($HasDeveloperModePolicy) { Get-PolicyValue $PolicyRoot "ExtensionDeveloperModeSettings" } else { $null }
    $developerTools = Get-PolicyValue $PolicyRoot "DeveloperToolsAvailability"
    $blockExternal = Get-PolicyValue $PolicyRoot "BlockExternalExtensions"
    $blocklist = Get-PolicyList "$PolicyRoot\ExtensionInstallBlocklist"
    $allowlist = Get-PolicyList "$PolicyRoot\ExtensionInstallAllowlist"
    $typeBlocklist = Get-PolicyList "$PolicyRoot\ExtensionInstallTypeBlocklist"
    $extensionSettingsRaw = Get-PolicyValue $PolicyRoot "ExtensionSettings"
    $defaultMode = Get-DefaultInstallationMode $extensionSettingsRaw
    $signals = [System.Collections.Generic.List[string]]::new()

    if ($HasDeveloperModePolicy -and $developerMode -eq 1) {
        $signals.Add("DEVELOPER_MODE_DISALLOWED")
    }
    elseif ($HasDeveloperModePolicy -and $null -eq $developerMode -and $developerTools -eq 2) {
        $signals.Add("DEVELOPER_TOOLS_POLICY_DISALLOWS_EXTENSION_DEVELOPER_MODE")
    }
    if ($blocklist -contains "*") {
        $signals.Add("ALL_EXTENSIONS_BLOCKLISTED")
    }
    if ($defaultMode -eq "blocked" -or $defaultMode -eq "removed") {
        $signals.Add("EXTENSION_SETTINGS_DEFAULT_$($defaultMode.ToUpperInvariant())")
    }
    if ($blockExternal -eq 1) {
        $signals.Add("EXTERNAL_EXTENSIONS_BLOCKED")
    }
    if ($defaultMode -eq "INVALID_JSON") {
        $signals.Add("EXTENSION_SETTINGS_INVALID_JSON")
    }

    $executable = Find-FirstExistingPath $ExecutableCandidates
    $decision = if ($null -eq $executable) {
        "BROWSER_NOT_FOUND"
    }
    elseif ($signals.Count -gt 0) {
        "IT_MANAGED_DEPLOYMENT_REQUIRED"
    }
    else {
        "NO_EXPLICIT_POLICY_BLOCK_FOUND"
    }

    return [ordered]@{
        name = $Name
        executable = $executable
        policyRoot = $PolicyRoot
        policies = [ordered]@{
            extensionDeveloperModeSettings = $developerMode
            developerToolsAvailability = $developerTools
            blockExternalExtensions = $blockExternal
            extensionInstallBlocklist = $blocklist
            extensionInstallAllowlist = $allowlist
            extensionInstallTypeBlocklist = $typeBlocklist
            extensionSettingsDefaultInstallationMode = $defaultMode
        }
        blockingSignals = @($signals)
        decision = $decision
    }
}

if ($env:OS -ne "Windows_NT") {
    $unsupported = [ordered]@{
        schema = "chatbridge.windows-readiness.v1"
        decision = "UNSUPPORTED_OS"
        reason = "This assessor is read-only and supports Windows only."
        externalExecutionClaimed = $false
        installed = $false
        browserBound = $false
        manualUserTasks = @()
        ownerActionRequired = $false
    }
    $unsupported | ConvertTo-Json -Depth 6
    exit 2
}

$manifestPath = Join-Path $ExtensionPath "manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "manifest.json was not found at the supplied ExtensionPath."
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

$edgeCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:LOCALAPPDATA "Microsoft\Edge\Application\msedge.exe")
)
$chromeCandidates = @(
    (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
    (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
)

$browserAssessments = @(
    (Get-BrowserAssessment "Microsoft Edge (machine policy)" "Registry::HKEY_LOCAL_MACHINE\Software\Policies\Microsoft\Edge" $edgeCandidates $true),
    (Get-BrowserAssessment "Microsoft Edge (user policy)" "Registry::HKEY_CURRENT_USER\Software\Policies\Microsoft\Edge" $edgeCandidates $true),
    (Get-BrowserAssessment "Google Chrome (machine policy)" "Registry::HKEY_LOCAL_MACHINE\Software\Policies\Google\Chrome" $chromeCandidates $false),
    (Get-BrowserAssessment "Google Chrome (user policy)" "Registry::HKEY_CURRENT_USER\Software\Policies\Google\Chrome" $chromeCandidates $false)
)

$found = @($browserAssessments | Where-Object { $null -ne $_.executable })
$blocked = @($found | Where-Object { $_.decision -eq "IT_MANAGED_DEPLOYMENT_REQUIRED" })
$decision = if ($found.Count -eq 0) {
    "NO_SUPPORTED_BROWSER_FOUND"
}
elseif ($blocked.Count -gt 0) {
    "IT_MANAGED_DEPLOYMENT_REQUIRED"
}
else {
    "USER_PROFILE_SIDELOAD_NOT_EXPLICITLY_BLOCKED"
}

$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
$isAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$result = [ordered]@{
    schema = "chatbridge.windows-readiness.v1"
    evaluatedAt = (Get-Date).ToUniversalTime().ToString("o")
    mode = "READ_ONLY_NO_ELEVATION"
    decision = $decision
    currentUserIsAdministrator = $isAdministrator
    extension = [ordered]@{
        path = (Resolve-Path -LiteralPath $ExtensionPath).Path
        name = [string]$manifest.name
        version = [string]$manifest.version
        manifestVersion = [int]$manifest.manifest_version
        permissions = @($manifest.permissions)
        hostPermissions = @($manifest.host_permissions)
    }
    browsers = $browserAssessments
    verificationBoundary = "Registry policy inspection cannot prove the current edge://policy UI, successful installation, signed-in ChatGPT binding, warning interception, or successor-chat semantic readback."
    nextMachineRoute = if ($decision -eq "IT_MANAGED_DEPLOYMENT_REQUIRED") { "ENTERPRISE_ALLOWLIST_OR_MANAGED_INSTALL" } else { "TARGET_BROWSER_UI_CANARY_REQUIRED" }
    externalExecutionClaimed = $false
    installed = $false
    browserBound = $false
    manualUserTasks = @()
    ownerActionRequired = $false
}

$json = $result | ConvertTo-Json -Depth 10
if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
    $resolvedOutput = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputPath)
    [IO.File]::WriteAllText($resolvedOutput, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}
$json

