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

# Detached MDTAF artifacts must be self-contained. A process that merely waits for
# Metro is not a valid launch, even if ActivityManager reports a drawn window.
unzip -Z1 "$APK" > "$EVIDENCE_DIR/apk-members.txt"
if ! grep -Fx 'assets/index.android.bundle' "$EVIDENCE_DIR/apk-members.txt" >/dev/null; then
  echo "EMBEDDED_JS_BUNDLE_MISSING" >&2
  exit 11
fi
BUNDLE_BYTES="$(unzip -p "$APK" assets/index.android.bundle | wc -c | tr -d ' ')"
if [[ "$BUNDLE_BYTES" -le 1024 ]]; then
  echo "EMBEDDED_JS_BUNDLE_TOO_SMALL:$BUNDLE_BYTES" >&2
  exit 11
fi
printf 'EMBEDDED_JS_BUNDLE_PRESENT bytes=%s\n' "$BUNDLE_BYTES" > "$EVIDENCE_DIR/embedded-js-bundle.txt"

PACKAGE_FIREWALL_USED=0
PACKAGE_FIREWALL_ACTIVE=0
PACKAGE_FIREWALL_RECOVERY=0
OFFLINE_FAULT_MODE="DEVICE_WIDE_RADIO"

restore_connectivity() {
  if [[ "$PACKAGE_FIREWALL_ACTIVE" -eq 1 ]]; then
    bash "$SCRIPT_DIR/run_android_package_network_fault.sh" restore \
      --package "$PACKAGE_ID" --evidence-dir "$EVIDENCE_DIR" >/dev/null 2>&1 || true
    PACKAGE_FIREWALL_ACTIVE=0
  fi
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
    --input "$dump" --expect "$expectation" --json-output "$receipt"
}

icmp_diagnostic() {
  "$ADB" shell ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1
}

launch_app() {
  "$ADB" shell monkey -p "$PACKAGE_ID" -c android.intent.category.LAUNCHER 1 >/dev/null
  sleep 6
  "$ADB" shell pidof "$PACKAGE_ID" | tr -d '\r'
}

capture_semantic_ui() {
  local label="$1"
  local screenshot="$EVIDENCE_DIR/${label}.png"
  local remote="/sdcard/fuse-${label}.xml"
  local local_xml="$EVIDENCE_DIR/ui-${label}.xml"
  "$ADB" exec-out screencap -p > "$screenshot"
  "$ADB" shell uiautomator dump "$remote" >/dev/null
  "$ADB" pull "$remote" "$local_xml" >/dev/null
  "$ADB" shell rm -f "$remote" >/dev/null 2>&1 || true
  if ! grep -Eiq 'text="FUSE"|content-desc="FUSE"|One workspace|Owner connection required|Connect owner|Ask FUSE' "$local_xml"; then
    echo "SEMANTIC_FUSE_UI_MISSING:$label" >&2
    return 1
  fi
  printf 'SEMANTIC_FUSE_UI_PRESENT %s\n' "$label" > "$EVIDENCE_DIR/ui-${label}.proof.txt"
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
FIRST_UI=0
if capture_semantic_ui first-launch; then FIRST_UI=1; fi
"$ADB" shell dumpsys activity activities > "$EVIDENCE_DIR/activity-first-launch.txt"
"$ADB" shell dumpsys meminfo "$PACKAGE_ID" > "$EVIDENCE_DIR/meminfo-first-launch.txt"
if [[ "$FIRST_UI" -ne 1 ]]; then exit 12; fi

"$ADB" shell am force-stop "$PACKAGE_ID"
SECOND_PID="$(launch_app)"
if [[ -z "$SECOND_PID" ]]; then
  echo "Relaunch did not leave an application process" >&2
  exit 5
fi
RELAUNCH_UI=0
if capture_semantic_ui relaunch; then RELAUNCH_UI=1; fi
if [[ "$RELAUNCH_UI" -ne 1 ]]; then exit 13; fi

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
else
  OFFLINE_FAULT_MODE="PACKAGE_UID_FIREWALL_DENY"
  PACKAGE_FIREWALL_USED=1
  PACKAGE_FIREWALL_ACTIVE=1
  if bash "$SCRIPT_DIR/run_android_package_network_fault.sh" apply \
      --package "$PACKAGE_ID" --evidence-dir "$EVIDENCE_DIR"; then
    CONNECTIVITY_LOSS=1
  else
    echo "Connectivity-loss injection was not verified; refusing offline PASS" >&2
    exit 7
  fi
fi

"$ADB" shell am force-stop "$PACKAGE_ID"
OFFLINE_PID="$(launch_app)"
if [[ -z "$OFFLINE_PID" ]]; then
  echo "Offline relaunch did not leave an application process" >&2
  exit 8
fi
OFFLINE_UI=0
if capture_semantic_ui offline-launch; then OFFLINE_UI=1; fi
if [[ "$OFFLINE_UI" -ne 1 ]]; then exit 14; fi

if [[ "$PACKAGE_FIREWALL_USED" -eq 1 ]]; then
  if bash "$SCRIPT_DIR/run_android_package_network_fault.sh" restore \
      --package "$PACKAGE_ID" --evidence-dir "$EVIDENCE_DIR"; then
    PACKAGE_FIREWALL_RECOVERY=1
    PACKAGE_FIREWALL_ACTIVE=0
  else
    echo "Package-network recovery was not verified after offline test" >&2
    exit 9
  fi
fi
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
if [[ "$AIRPLANE_OFF" -eq 1 && "$RECOVERY_VALIDATED" -eq 1 ]]; then
  if [[ "$PACKAGE_FIREWALL_USED" -eq 0 || "$PACKAGE_FIREWALL_RECOVERY" -eq 1 ]]; then
    NETWORK_RECOVERY=1
  fi
fi
if [[ "$NETWORK_RECOVERY" -ne 1 ]]; then
  echo "Validated Android network recovery was not verified after offline test" >&2
  exit 9
fi

"$ADB" shell am force-stop "$PACKAGE_ID"
RECOVERY_PID="$(launch_app)"
if [[ -z "$RECOVERY_PID" ]]; then
  echo "Post-recovery relaunch did not leave an application process" >&2
  exit 10
fi
RECOVERY_UI=0
if capture_semantic_ui recovery-launch; then RECOVERY_UI=1; fi
if [[ "$RECOVERY_UI" -ne 1 ]]; then exit 15; fi

"$ADB" shell dumpsys package "$PACKAGE_ID" > "$EVIDENCE_DIR/package-dumpsys.txt"
"$ADB" shell getprop > "$EVIDENCE_DIR/device-getprop.txt"
"$ADB" shell wm size > "$EVIDENCE_DIR/device-wm-size.txt"
"$ADB" shell wm density > "$EVIDENCE_DIR/device-wm-density.txt"
"$ADB" shell dumpsys meminfo "$PACKAGE_ID" > "$EVIDENCE_DIR/meminfo-final.txt"
"$ADB" logcat -d > "$EVIDENCE_DIR/logcat.txt"

# React soft exceptions can leave a process alive and a window drawn. These boot
# failures are therefore release-blocking even when no FATAL EXCEPTION/ANR exists.
REACT_BOOT_ERROR=0
if grep -Eiq 'Unable to load script|Make sure you.re running Metro|index\.android\.bundle.*packaged correctly' "$EVIDENCE_DIR/logcat.txt"; then
  REACT_BOOT_ERROR=1
  grep -Ein 'Unable to load script|Make sure you.re running Metro|index\.android\.bundle.*packaged correctly' \
    "$EVIDENCE_DIR/logcat.txt" > "$EVIDENCE_DIR/react-boot-errors.txt" || true
fi
if [[ "$REACT_BOOT_ERROR" -ne 0 ]]; then
  echo "REACT_BOOT_ERROR: detached app did not load embedded JS" >&2
  exit 16
fi

python - "$APK" "$EVIDENCE_DIR" "$PACKAGE_ID" "$FIRST_PID" "$SECOND_PID" "$OFFLINE_PID" "$RECOVERY_PID" "$NETWORK_BASELINE" "$CONNECTIVITY_LOSS" "$NETWORK_RECOVERY" "$AIRPLANE_CMD" "$WIFI_OFF" "$DATA_OFF" "$OFFLINE_VALIDATED_ABSENT" "$AIRPLANE_OFF" "$RECOVERY_VALIDATED" "$BASELINE_PING_DIAGNOSTIC" "$OFFLINE_PING_BLOCKED" "$RECOVERY_PING_DIAGNOSTIC" "$OFFLINE_FAULT_MODE" "$PACKAGE_FIREWALL_USED" "$PACKAGE_FIREWALL_RECOVERY" "$FIRST_UI" "$RELAUNCH_UI" "$OFFLINE_UI" "$RECOVERY_UI" "$REACT_BOOT_ERROR" "$BUNDLE_BYTES" <<'PY'
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
flags = [x == "1" for x in sys.argv[8:20]]
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
) = flags
offline_fault_mode = sys.argv[20]
package_firewall_used = sys.argv[21] == "1"
package_firewall_recovery = sys.argv[22] == "1"
first_ui, relaunch_ui, offline_ui, recovery_ui = [x == "1" for x in sys.argv[23:27]]
react_boot_error = sys.argv[27] == "1"
bundle_bytes = int(sys.argv[28])
log = (evidence / "logcat.txt").read_text(encoding="utf-8", errors="replace")

fatal_patterns = [
    re.compile(r"FATAL EXCEPTION", re.I),
    re.compile(r"ANR in\s+" + re.escape(package), re.I),
    re.compile(r"Force finishing activity.*" + re.escape(package), re.I),
]
relevant_lines = [line for line in log.splitlines() if package in line or "FATAL EXCEPTION" in line]
fatal_hits = [line for line in relevant_lines if any(p.search(line) for p in fatal_patterns)]

core_pass = all([
    bool(first_pid), bool(second_pid), network_baseline, connectivity_loss,
    bool(offline_pid), network_recovery, bool(recovery_pid), not fatal_hits,
    first_ui, relaunch_ui, offline_ui, recovery_ui, not react_boot_error,
    bundle_bytes > 1024,
])
receipt = {
    "schema": "FUSE_MOBILE_MDTAF_SMOKE_RECEIPT_V2",
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "state": "ANDROID_SMOKE_PASS" if core_pass else "ANDROID_SMOKE_FAIL",
    "package_id": package,
    "apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
    "embedded_js_bundle_state": "PASS" if bundle_bytes > 1024 else "FAIL",
    "embedded_js_bundle_bytes": bundle_bytes,
    "install_state": "PASS",
    "first_launch_state": "PASS" if first_pid else "FAIL",
    "first_launch_ui_state": "PASS" if first_ui else "FAIL",
    "relaunch_state": "PASS" if second_pid else "FAIL",
    "relaunch_ui_state": "PASS" if relaunch_ui else "FAIL",
    "network_baseline_state": "PASS" if network_baseline else "FAIL",
    "connectivity_loss_state": "PASS" if connectivity_loss else "FAIL",
    "offline_launch_state": "PASS" if offline_pid else "FAIL",
    "offline_launch_ui_state": "PASS" if offline_ui else "FAIL",
    "network_recovery_state": "PASS" if network_recovery else "FAIL",
    "recovery_launch_state": "PASS" if recovery_pid else "FAIL",
    "recovery_launch_ui_state": "PASS" if recovery_ui else "FAIL",
    "react_boot_error_state": "FAIL" if react_boot_error else "PASS",
    "offline_fault_mode": offline_fault_mode,
    "connectivity_probe": (
        "PACKAGE_UID_FIREWALL_DENY_WITH_EXACT_READBACK" if package_firewall_used
        else "ANDROID_ACTIVE_DEFAULT_NETWORK_INTERNET_VALIDATED"
    ),
    "connectivity_controls": {
        "airplane_mode_enable_supported": airplane_cmd,
        "wifi_disable_supported": wifi_off,
        "mobile_data_disable_supported": data_off,
        "offline_validated_default_absent": offline_validated_absent,
        "airplane_mode_disable_readback": airplane_off,
        "recovery_validated_default_present": recovery_validated,
        "package_firewall_fallback": package_firewall_used,
        "package_firewall_recovery": package_firewall_recovery,
        "baseline_ping_diagnostic_only": baseline_ping_diagnostic,
        "offline_ping_blocked_diagnostic_only": offline_ping_blocked,
        "recovery_ping_diagnostic_only": recovery_ping_diagnostic,
    },
    "fatal_or_anr_hits": fatal_hits[:50],
    "screenshots": ["first-launch.png", "relaunch.png", "offline-launch.png", "recovery-launch.png"],
    "semantic_ui_evidence": [
        "ui-first-launch.xml", "ui-relaunch.xml", "ui-offline-launch.xml", "ui-recovery-launch.xml"
    ],
    "truth_boundary": {
        "activity_process_liveness_alone_is_not_semantic_ui_proof": True,
        "embedded_bundle_required_for_detached_apk_court": True,
        "package_firewall_mode_is_package_uid_scoped": package_firewall_used,
        "package_firewall_mode_is_not_device_wide_offline_proof": package_firewall_used,
        "offline_process_survival_alone_is_not_offline_proof": True,
    },
    "personal_data_captured": False,
    "provider_effect_executed": False,
}
(evidence / "smoke-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(receipt, sort_keys=True))
if not core_pass:
    raise SystemExit("MDTAF smoke semantic gate failed")
PY

trap - EXIT
restore_connectivity
