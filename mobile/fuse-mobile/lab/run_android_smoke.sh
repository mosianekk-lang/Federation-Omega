#!/usr/bin/env bash
set -euo pipefail

APK=""
EVIDENCE_DIR="mdtaf-evidence"
PACKAGE_ID="com.federationomega.fusemobile"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ADB="$(bash "$SCRIPT_DIR/resolve_sdk_adb.sh")"
test -x "$ADB"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apk) APK="$2"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="$2"; shift 2 ;;
    --package) PACKAGE_ID="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$APK" || ! -s "$APK" ]]; then
  echo "--apk must point to a non-empty APK" >&2
  exit 2
fi

mkdir -p "$EVIDENCE_DIR"
exec > >(tee "$EVIDENCE_DIR/smoke-console.log") 2>&1

if [[ "$("$ADB" get-state 2>/dev/null || true)" != "device" ]]; then
  echo "ADB target is not ready" >&2
  exit 3
fi

ADB_COUNT="$("$ADB" devices | awk 'NR>1 && $2=="device" {count++} END {print count+0}')"
if [[ "$ADB_COUNT" -ne 1 ]]; then
  echo "Expected exactly one ready ADB target, found $ADB_COUNT" >&2
  "$ADB" devices -l || true
  exit 3
fi

restore_connectivity() {
  "$ADB" shell cmd connectivity airplane-mode disable >/dev/null 2>&1 || true
  "$ADB" shell svc wifi enable >/dev/null 2>&1 || true
  "$ADB" shell svc data enable >/dev/null 2>&1 || true
}
trap restore_connectivity EXIT

capture_connectivity_state() {
  local label="$1"
  local expectation="$2"
  local dump="$EVIDENCE_DIR/connectivity-${label}.txt"
  local receipt="$EVIDENCE_DIR/connectivity-${label}.json"
  "$ADB" shell dumpsys connectivity > "$dump"
  python "$SCRIPT_DIR/probe_android_connectivity.py" \
    --input "$dump" \
    --expect "$expectation" \
    --json-output "$receipt"
}

icmp_diagnostic() {
  "$ADB" shell ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1
}

launch_app() {
  "$ADB" shell monkey -p "$PACKAGE_ID" -c android.intent.category.LAUNCHER 1 >/dev/null
  sleep 5
  "$ADB" shell pidof "$PACKAGE_ID" | tr -d '\r'
}

"$ADB" logcat -c
"$ADB" shell pm clear "$PACKAGE_ID" >/dev/null 2>&1 || true
"$ADB" install -r -t "$APK"
"$ADB" shell pm list packages "$PACKAGE_ID" | tee "$EVIDENCE_DIR/package-installed.txt"

FIRST_PID="$(launch_app)"
if [[ -z "$FIRST_PID" ]]; then
  echo "First launch did not leave an application process" >&2
  exit 4
fi
"$ADB" exec-out screencap -p > "$EVIDENCE_DIR/first-launch.png"
"$ADB" shell dumpsys activity activities > "$EVIDENCE_DIR/activity-first-launch.txt"
"$ADB" shell dumpsys meminfo "$PACKAGE_ID" > "$EVIDENCE_DIR/meminfo-first-launch.txt"

"$ADB" shell am force-stop "$PACKAGE_ID"
SECOND_PID="$(launch_app)"
if [[ -z "$SECOND_PID" ]]; then
  echo "Relaunch did not leave an application process" >&2
  exit 5
fi
"$ADB" exec-out screencap -p > "$EVIDENCE_DIR/relaunch.png"

NETWORK_BASELINE=0
if capture_connectivity_state baseline online; then NETWORK_BASELINE=1; fi
BASELINE_PING_DIAGNOSTIC=0
if icmp_diagnostic; then BASELINE_PING_DIAGNOSTIC=1; fi
if [[ "$NETWORK_BASELINE" -ne 1 ]]; then
  echo "Cannot prove a validated Android default-network baseline before offline-fault injection" >&2
  exit 6
fi

AIRPLANE_CMD=0
WIFI_OFF=0
DATA_OFF=0
if "$ADB" shell cmd connectivity airplane-mode enable >/dev/null 2>&1; then AIRPLANE_CMD=1; fi
if "$ADB" shell svc wifi disable >/dev/null 2>&1; then WIFI_OFF=1; fi
if "$ADB" shell svc data disable >/dev/null 2>&1; then DATA_OFF=1; fi
sleep 3
AIRPLANE_ON_RAW="$("$ADB" shell cmd connectivity airplane-mode 2>/dev/null | tr -d '\r' || true)"
AIRPLANE_ON="$(printf '%s' "$AIRPLANE_ON_RAW" | tr '[:upper:]' '[:lower:]')"
OFFLINE_VALIDATED_ABSENT=0
if capture_connectivity_state offline offline; then OFFLINE_VALIDATED_ABSENT=1; fi
OFFLINE_PING_BLOCKED=0
if ! icmp_diagnostic; then OFFLINE_PING_BLOCKED=1; fi
CONNECTIVITY_LOSS=0
if [[ "$AIRPLANE_CMD" -eq 1 && "$AIRPLANE_ON" == *"enabled"* && "$OFFLINE_VALIDATED_ABSENT" -eq 1 ]]; then
  CONNECTIVITY_LOSS=1
fi
if [[ "$CONNECTIVITY_LOSS" -ne 1 ]]; then
  echo "Connectivity-loss injection was not verified; refusing offline PASS" >&2
  exit 7
fi

"$ADB" shell am force-stop "$PACKAGE_ID"
OFFLINE_PID="$(launch_app)"
if [[ -z "$OFFLINE_PID" ]]; then
  echo "Offline relaunch did not leave an application process" >&2
  exit 8
fi
"$ADB" exec-out screencap -p > "$EVIDENCE_DIR/offline-launch.png"

restore_connectivity
AIRPLANE_OFF=0
RECOVERY_VALIDATED=0
RECOVERY_PING_DIAGNOSTIC=0
for _ in $(seq 1 30); do
  AIRPLANE_OFF_RAW="$("$ADB" shell cmd connectivity airplane-mode 2>/dev/null | tr -d '\r' || true)"
  AIRPLANE_OFF_NORMALIZED="$(printf '%s' "$AIRPLANE_OFF_RAW" | tr '[:upper:]' '[:lower:]')"
  if [[ "$AIRPLANE_OFF_NORMALIZED" == *"disabled"* ]]; then AIRPLANE_OFF=1; fi
  if capture_connectivity_state recovery online; then RECOVERY_VALIDATED=1; fi
  if icmp_diagnostic; then RECOVERY_PING_DIAGNOSTIC=1; fi
  if [[ "$AIRPLANE_OFF" -eq 1 && "$RECOVERY_VALIDATED" -eq 1 ]]; then break; fi
  sleep 2
done
NETWORK_RECOVERY=0
if [[ "$AIRPLANE_OFF" -eq 1 && "$RECOVERY_VALIDATED" -eq 1 ]]; then NETWORK_RECOVERY=1; fi
if [[ "$NETWORK_RECOVERY" -ne 1 ]]; then
  echo "Validated Android default-network recovery was not verified after offline test" >&2
  exit 9
fi

"$ADB" shell am force-stop "$PACKAGE_ID"
RECOVERY_PID="$(launch_app)"
if [[ -z "$RECOVERY_PID" ]]; then
  echo "Post-recovery relaunch did not leave an application process" >&2
  exit 10
fi
"$ADB" exec-out screencap -p > "$EVIDENCE_DIR/recovery-launch.png"

"$ADB" shell dumpsys package "$PACKAGE_ID" > "$EVIDENCE_DIR/package-dumpsys.txt"
"$ADB" shell getprop > "$EVIDENCE_DIR/device-getprop.txt"
"$ADB" shell wm size > "$EVIDENCE_DIR/device-wm-size.txt"
"$ADB" shell wm density > "$EVIDENCE_DIR/device-wm-density.txt"
"$ADB" shell dumpsys meminfo "$PACKAGE_ID" > "$EVIDENCE_DIR/meminfo-final.txt"
"$ADB" logcat -d > "$EVIDENCE_DIR/logcat.txt"

python - "$APK" "$EVIDENCE_DIR" "$PACKAGE_ID" "$FIRST_PID" "$SECOND_PID" "$OFFLINE_PID" "$RECOVERY_PID" "$NETWORK_BASELINE" "$CONNECTIVITY_LOSS" "$NETWORK_RECOVERY" "$AIRPLANE_CMD" "$WIFI_OFF" "$DATA_OFF" "$OFFLINE_VALIDATED_ABSENT" "$AIRPLANE_OFF" "$RECOVERY_VALIDATED" "$BASELINE_PING_DIAGNOSTIC" "$OFFLINE_PING_BLOCKED" "$RECOVERY_PING_DIAGNOSTIC" <<'PY'
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

apk = Path(sys.argv[1])
evidence = Path(sys.argv[2])
package = sys.argv[3]
first_pid, second_pid, offline_pid, recovery_pid = sys.argv[4:8]
(
    network_baseline,
    connectivity_loss,
    network_recovery,
    airplane_cmd,
    wifi_off,
    data_off,
    offline_validated_absent,
    airplane_off,
    recovery_validated,
    baseline_ping_diagnostic,
    offline_ping_blocked,
    recovery_ping_diagnostic,
) = [x == "1" for x in sys.argv[8:20]]
log = (evidence / "logcat.txt").read_text(encoding="utf-8", errors="replace")

fatal_patterns = [
    re.compile(r"FATAL EXCEPTION", re.I),
    re.compile(r"ANR in\s+" + re.escape(package), re.I),
    re.compile(r"Force finishing activity.*" + re.escape(package), re.I),
]
relevant_lines = [line for line in log.splitlines() if package in line or "FATAL EXCEPTION" in line]
fatal_hits = [line for line in relevant_lines if any(p.search(line) for p in fatal_patterns)]

core_pass = all(
    [
        bool(first_pid),
        bool(second_pid),
        network_baseline,
        connectivity_loss,
        bool(offline_pid),
        network_recovery,
        bool(recovery_pid),
        not fatal_hits,
    ]
)
receipt = {
    "schema": "FUSE_MOBILE_MDTAF_SMOKE_RECEIPT_V1",
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "state": "ANDROID_SMOKE_PASS" if core_pass else "ANDROID_SMOKE_FAIL",
    "package_id": package,
    "apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
    "install_state": "PASS",
    "first_launch_state": "PASS" if first_pid else "FAIL",
    "relaunch_state": "PASS" if second_pid else "FAIL",
    "network_baseline_state": "PASS" if network_baseline else "FAIL",
    "connectivity_loss_state": "PASS" if connectivity_loss else "FAIL",
    "offline_launch_state": "PASS" if offline_pid else "FAIL",
    "network_recovery_state": "PASS" if network_recovery else "FAIL",
    "recovery_launch_state": "PASS" if recovery_pid else "FAIL",
    "connectivity_probe": "ANDROID_ACTIVE_DEFAULT_NETWORK_INTERNET_VALIDATED",
    "connectivity_controls": {
        "airplane_mode_enable_supported": airplane_cmd,
        "wifi_disable_supported": wifi_off,
        "mobile_data_disable_supported": data_off,
        "offline_validated_default_absent": offline_validated_absent,
        "airplane_mode_disable_readback": airplane_off,
        "recovery_validated_default_present": recovery_validated,
        "baseline_ping_diagnostic_only": baseline_ping_diagnostic,
        "offline_ping_blocked_diagnostic_only": offline_ping_blocked,
        "recovery_ping_diagnostic_only": recovery_ping_diagnostic,
    },
    "connectivity_evidence": [
        "connectivity-baseline.txt",
        "connectivity-baseline.json",
        "connectivity-offline.txt",
        "connectivity-offline.json",
        "connectivity-recovery.txt",
        "connectivity-recovery.json",
    ],
    "fatal_or_anr_hits": fatal_hits[:50],
    "screenshots": [
        "first-launch.png",
        "relaunch.png",
        "offline-launch.png",
        "recovery-launch.png",
    ],
    "personal_data_captured": False,
    "provider_effect_executed": False,
}
(evidence / "smoke-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(receipt, sort_keys=True))
if not core_pass:
    raise SystemExit("MDTAF smoke core gate failed")
PY

trap - EXIT
restore_connectivity
