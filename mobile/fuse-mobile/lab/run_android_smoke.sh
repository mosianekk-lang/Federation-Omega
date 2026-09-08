#!/usr/bin/env bash
set -euo pipefail

APK=""
EVIDENCE_DIR="mdtaf-evidence"
PACKAGE_ID="com.federationomega.fusemobile"

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

if [[ "$(adb get-state 2>/dev/null || true)" != "device" ]]; then
  echo "ADB target is not ready" >&2
  exit 3
fi

ADB_COUNT="$(adb devices | awk 'NR>1 && $2=="device" {count++} END {print count+0}')"
if [[ "$ADB_COUNT" -ne 1 ]]; then
  echo "Expected exactly one ready ADB target, found $ADB_COUNT" >&2
  adb devices -l || true
  exit 3
fi

adb logcat -c
adb shell pm clear "$PACKAGE_ID" >/dev/null 2>&1 || true
adb install -r -t "$APK"
adb shell pm list packages "$PACKAGE_ID" | tee "$EVIDENCE_DIR/package-installed.txt"

launch_app() {
  adb shell monkey -p "$PACKAGE_ID" -c android.intent.category.LAUNCHER 1 >/dev/null
  sleep 5
  adb shell pidof "$PACKAGE_ID" | tr -d '\r'
}

FIRST_PID="$(launch_app)"
if [[ -z "$FIRST_PID" ]]; then
  echo "First launch did not leave an application process" >&2
  exit 4
fi
adb exec-out screencap -p > "$EVIDENCE_DIR/first-launch.png"
adb shell dumpsys activity activities > "$EVIDENCE_DIR/activity-first-launch.txt"
adb shell dumpsys meminfo "$PACKAGE_ID" > "$EVIDENCE_DIR/meminfo-first-launch.txt"

adb shell am force-stop "$PACKAGE_ID"
SECOND_PID="$(launch_app)"
if [[ -z "$SECOND_PID" ]]; then
  echo "Relaunch did not leave an application process" >&2
  exit 5
fi
adb exec-out screencap -p > "$EVIDENCE_DIR/relaunch.png"

# Reproduce a basic connectivity-loss condition without assuming privileged root.
WIFI_OFF=0
DATA_OFF=0
if adb shell svc wifi disable >/dev/null 2>&1; then WIFI_OFF=1; fi
if adb shell svc data disable >/dev/null 2>&1; then DATA_OFF=1; fi
sleep 2
adb shell am force-stop "$PACKAGE_ID"
OFFLINE_PID="$(launch_app)"
if [[ -z "$OFFLINE_PID" ]]; then
  echo "Offline relaunch did not leave an application process" >&2
  [[ "$WIFI_OFF" -eq 1 ]] && adb shell svc wifi enable >/dev/null 2>&1 || true
  [[ "$DATA_OFF" -eq 1 ]] && adb shell svc data enable >/dev/null 2>&1 || true
  exit 6
fi
adb exec-out screencap -p > "$EVIDENCE_DIR/offline-launch.png"
[[ "$WIFI_OFF" -eq 1 ]] && adb shell svc wifi enable >/dev/null 2>&1 || true
[[ "$DATA_OFF" -eq 1 ]] && adb shell svc data enable >/dev/null 2>&1 || true
sleep 2

adb shell dumpsys package "$PACKAGE_ID" > "$EVIDENCE_DIR/package-dumpsys.txt"
adb shell getprop > "$EVIDENCE_DIR/device-getprop.txt"
adb shell wm size > "$EVIDENCE_DIR/device-wm-size.txt"
adb shell wm density > "$EVIDENCE_DIR/device-wm-density.txt"
adb shell dumpsys meminfo "$PACKAGE_ID" > "$EVIDENCE_DIR/meminfo-final.txt"
adb logcat -d > "$EVIDENCE_DIR/logcat.txt"

python - "$APK" "$EVIDENCE_DIR" "$PACKAGE_ID" "$FIRST_PID" "$SECOND_PID" "$OFFLINE_PID" "$WIFI_OFF" "$DATA_OFF" <<'PY'
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

apk = Path(sys.argv[1])
evidence = Path(sys.argv[2])
package = sys.argv[3]
first_pid, second_pid, offline_pid = sys.argv[4:7]
wifi_off, data_off = [x == "1" for x in sys.argv[7:9]]
log = (evidence / "logcat.txt").read_text(encoding="utf-8", errors="replace")

fatal_patterns = [
    re.compile(r"FATAL EXCEPTION", re.I),
    re.compile(r"ANR in\s+" + re.escape(package), re.I),
    re.compile(r"Force finishing activity.*" + re.escape(package), re.I),
]
relevant_lines = [line for line in log.splitlines() if package in line or "FATAL EXCEPTION" in line]
fatal_hits = [line for line in relevant_lines if any(p.search(line) for p in fatal_patterns)]

receipt = {
    "schema": "FUSE_MOBILE_MDTAF_SMOKE_RECEIPT_V1",
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "state": "ANDROID_SMOKE_PASS" if not fatal_hits else "ANDROID_SMOKE_FAIL",
    "package_id": package,
    "apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
    "install_state": "PASS",
    "first_launch_state": "PASS" if first_pid else "FAIL",
    "relaunch_state": "PASS" if second_pid else "FAIL",
    "offline_launch_state": "PASS" if offline_pid else "FAIL",
    "connectivity_controls": {"wifi_disable_supported": wifi_off, "mobile_data_disable_supported": data_off},
    "fatal_or_anr_hits": fatal_hits[:50],
    "screenshots": ["first-launch.png", "relaunch.png", "offline-launch.png"],
    "personal_data_captured": False,
    "provider_effect_executed": False,
}
(evidence / "smoke-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(receipt, sort_keys=True))
if fatal_hits:
    raise SystemExit("FATAL/ANR evidence detected")
PY
