param(
    [Parameter(Mandatory=$false)]
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,

    [Parameter(Mandatory=$false)]
    [string]$Endpoint = "http://127.0.0.1:8765/v1/front-facing-status",

    [Parameter(Mandatory=$false)]
    [int]$PollSeconds = 5,

    [Parameter(Mandatory=$false)]
    [int]$StallSeconds = 60
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$KnownStatuses = @(
    "Connection interrupted. Waiting for the complete answer",
    "Connection interrupted",
    "Waiting for the complete answer",
    "Thinking",
    "Called tool",
    "Generating",
    "Reconnecting",
    "Something went wrong",
    "Error generating"
)

$LastFingerprint = @{}
$LastLength = @{}
$LastProgressAt = @{}

function Get-Sha256Hex {
    param([string]$Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
        $hash = $sha.ComputeHash($bytes)
        return ([System.BitConverter]::ToString($hash)).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Ensure-FuseObserverHost {
    try {
        Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8765/healthz" -TimeoutSec 2 | Out-Null
        return
    }
    catch {
        $python = (Get-Command pythonw.exe -ErrorAction SilentlyContinue)
        if (-not $python) {
            $python = (Get-Command python.exe -ErrorAction SilentlyContinue)
        }
        if (-not $python) {
            throw "FUSE front-facing observer host requires Python on the authorized Windows host."
        }

        $args = @(
            "-m",
            "client_observer.front_facing_status_host_v1",
            "--stall-seconds",
            "$StallSeconds"
        )
        Start-Process -FilePath $python.Source -ArgumentList $args -WorkingDirectory $RepoRoot -WindowStyle Hidden
        Start-Sleep -Seconds 2
        Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8765/healthz" -TimeoutSec 3 | Out-Null
    }
}

function Get-ChatGptWindowSnapshot {
    param([System.Diagnostics.Process]$Process)

    if ($Process.MainWindowHandle -eq 0) {
        return $null
    }

    try {
        $root = [System.Windows.Automation.AutomationElement]::FromHandle($Process.MainWindowHandle)
        if (-not $root) { return $null }

        $all = $root.FindAll(
            [System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.Condition]::TrueCondition
        )

        $status = ""
        $stopVisible = $false
        $thinkingVisible = $false
        $toolVisible = $false
        $chatGptEvidence = $false
        $digestParts = New-Object System.Collections.Generic.List[string]
        $visibleLength = 0
        $maxElements = [Math]::Min($all.Count, 2500)

        for ($i = 0; $i -lt $maxElements; $i++) {
            $element = $all.Item($i)
            try {
                $name = [string]$element.Current.Name
                if ([string]::IsNullOrWhiteSpace($name)) { continue }

                if (
                    $name -like "*Ask ChatGPT*" -or
                    $name -like "*chatgpt.com*" -or
                    $name -eq "ChatGPT"
                ) {
                    $chatGptEvidence = $true
                }

                foreach ($candidate in $KnownStatuses) {
                    if ($name.IndexOf($candidate, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                        $status = $candidate
                        if ($candidate -eq "Thinking") { $thinkingVisible = $true }
                        if ($candidate -eq "Called tool") { $toolVisible = $true }
                    }
                }

                $controlType = $element.Current.ControlType
                if (
                    $controlType -eq [System.Windows.Automation.ControlType]::Button -and
                    $name.IndexOf("Stop", [System.StringComparison]::OrdinalIgnoreCase) -ge 0
                ) {
                    $stopVisible = $true
                }

                # Privacy: use accessible text only to derive a one-way aggregate
                # fingerprint and length. Raw names are never sent or persisted.
                $visibleLength += $name.Length
                if ($digestParts.Count -lt 2500) {
                    $digestParts.Add((Get-Sha256Hex -Text $name))
                }
            }
            catch {
                continue
            }
        }

        if (-not $chatGptEvidence) {
            return $null
        }

        $aggregate = ($digestParts -join "|")
        $fingerprint = "sha256:" + (Get-Sha256Hex -Text $aggregate)
        $sourceId = "FUSE-WINDOWS-EDGE-UIA-" + $Process.Id + "-" + $Process.MainWindowHandle
        $now = [System.Diagnostics.Stopwatch]::GetTimestamp() / [double][System.Diagnostics.Stopwatch]::Frequency

        $priorFp = $LastFingerprint[$sourceId]
        $priorLen = $LastLength[$sourceId]
        $changed = ($fingerprint -ne $priorFp -or $visibleLength -ne $priorLen)

        if (-not $LastProgressAt.ContainsKey($sourceId) -or $changed) {
            $LastProgressAt[$sourceId] = $now
        }
        $noProgress = [Math]::Max(0, $now - [double]$LastProgressAt[$sourceId])
        $ownerVisibleProgress = ($changed -or $noProgress -lt 15)

        $LastFingerprint[$sourceId] = $fingerprint
        $LastLength[$sourceId] = $visibleLength

        $interrupted = ($status -like "Connection interrupted*")
        $responseInflight = ($stopVisible -or $thinkingVisible -or $toolVisible)

        return @{
            source_id = $sourceId
            observed_monotonic = $now
            page_family = "chatgpt-web-windows-uia"
            status_text = $status
            response_inflight = $responseInflight
            stop_button_visible = $stopVisible
            thinking_visible = $thinkingVisible
            tool_activity_visible = $toolVisible
            connection_interrupted = $interrupted
            visible_output_fingerprint = $fingerprint
            visible_output_length = $visibleLength
            owner_visible_progress = $ownerVisibleProgress
            local_no_progress_seconds = $noProgress
            privacy_mode = "WINDOWS_UIA_HASHED_FRONT_FACING_STATE_ONLY"
        }
    }
    catch {
        return $null
    }
}

Ensure-FuseObserverHost

while ($true) {
    $edge = Get-Process msedge -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 }
    foreach ($process in $edge) {
        $snapshot = Get-ChatGptWindowSnapshot -Process $process
        if (-not $snapshot) { continue }

        try {
            $body = $snapshot | ConvertTo-Json -Depth 6 -Compress
            $result = Invoke-RestMethod -Method Post -Uri $Endpoint -ContentType "application/json" -Body $body -TimeoutSec 5

            # Keep user-facing progress local and minimal. No conversation body is logged.
            if ($result.owner_visible_progress_required -eq $true) {
                Write-Output (
                    "[FUSE FRONT STATUS] {0} | no_progress={1}s | auto_continue={2}" -f
                    $result.state,
                    $result.no_progress_seconds,
                    $result.auto_continue_intent
                )
            }
        }
        catch {
            # Re-establish the local observer host and continue; do not terminate
            # monitoring because one telemetry delivery failed.
            try { Ensure-FuseObserverHost } catch {}
        }
    }

    Start-Sleep -Seconds $PollSeconds
}
