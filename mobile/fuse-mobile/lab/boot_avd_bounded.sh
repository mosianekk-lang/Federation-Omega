#!/usr/bin/env bash
set -euo pipefail

API_LEVEL="${API_LEVEL:?API_LEVEL is required}"
EVIDENCE_DIR="${EVIDENCE_DIR:-mobile/fuse-mobile/mdtaf-evidence}"
DEVICE_TIMEOUT_SECONDS="${DEVICE_TIMEOUT_SECONDS:-180}"
BOOT_TIMEOUT_SECONDS="${BOOT_TIMEOUT_SECONDS:-240}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-2}"
KVM_DEVICE="${KVM_DEVICE:-/dev/kvm}"
SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
AVD_HOME="${ANDROID_AVD_HOME:-}"
AVD_NAME="fuse-mdtaf-api-${API_LEVEL}"

[[ -n "$SDK_ROOT" ]] || { echo "Android SDK root is not set" >&2; exit 2; }
[[ -n "$AVD_HOME" ]] || { echo "ANDROID_AVD_HOME is not set" >&2; exit 2; }
[[ "$DEVICE_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || { echo "invalid DEVICE_TIMEOUT_SECONDS" >&2; exit 2; }
[[ "$BOOT_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || { echo "invalid BOOT_TIMEOUT_SECONDS" >&2; exit 2; }

ADB="$SDK_ROOT/platform-tools/adb"
EMULATOR="$SDK_ROOT/emulator/emulator"
INI="$AVD_HOME/${AVD_NAME}.ini"
LOG="$EVIDENCE_DIR/emulator-api-${API_LEVEL}.log"
mkdir -p "$EVIDENCE_DIR"

[[ -x "$ADB" ]] || { echo "exact SDK adb is not executable: $ADB" >&2; exit 2; }
[[ -x "$EMULATOR" ]] || { echo "SDK emulator is not executable: $EMULATOR" >&2; exit 2; }
[[ -s "$INI" ]] || { echo "AVD ini missing from stable ANDROID_AVD_HOME: $INI" >&2; exit 3; }

AVD_LIST="$EVIDENCE_DIR/emulator-list-avds-api-${API_LEVEL}.txt"
"$EMULATOR" -list-avds | tee "$AVD_LIST"
grep -Fx -- "$AVD_NAME" "$AVD_LIST" >/dev/null || {
  echo "AVD not discoverable from stable ANDROID_AVD_HOME: $AVD_NAME" >&2
  exit 3
}

"$ADB" start-server
"$ADB" version > "$EVIDENCE_DIR/adb-version-api-${API_LEVEL}.txt"
"$ADB" devices -l > "$EVIDENCE_DIR/adb-devices-prelaunch-api-${API_LEVEL}.txt"

{
  printf 'kvm_device=%s\n' "$KVM_DEVICE"
  ls -l "$KVM_DEVICE"
} > "$EVIDENCE_DIR/kvm-api-${API_LEVEL}.txt" 2>&1 || {
  echo "KVM device unavailable: $KVM_DEVICE" >&2
  exit 4
}

"$EMULATOR" -accel-check > "$EVIDENCE_DIR/emulator-accel-api-${API_LEVEL}.txt" 2>&1 || {
  cat "$EVIDENCE_DIR/emulator-accel-api-${API_LEVEL}.txt" >&2 || true
  echo "emulator acceleration preflight failed" >&2
  exit 4
}

EMULATOR_PID=""
SERIAL=""

capture_diagnostics() {
  local reason="$1"
  printf '%s\n' "$reason" > "$EVIDENCE_DIR/readiness-failure-api-${API_LEVEL}.txt"
  "$ADB" devices -l > "$EVIDENCE_DIR/adb-devices-failure-api-${API_LEVEL}.txt" 2>&1 || true
  "$EMULATOR" -list-avds > "$EVIDENCE_DIR/emulator-list-avds-failure-api-${API_LEVEL}.txt" 2>&1 || true
  "$EMULATOR" -accel-check > "$EVIDENCE_DIR/emulator-accel-failure-api-${API_LEVEL}.txt" 2>&1 || true
  {
    printf 'ANDROID_AVD_HOME=%s\n' "$AVD_HOME"
    ls -la "$AVD_HOME"
  } > "$EVIDENCE_DIR/avd-home-failure-api-${API_LEVEL}.txt" 2>&1 || true
  ps -ef > "$EVIDENCE_DIR/processes-failure-api-${API_LEVEL}.txt" 2>&1 || true
  if [[ -f "$LOG" ]]; then
    tail -200 "$LOG" > "$EVIDENCE_DIR/emulator-tail-failure-api-${API_LEVEL}.txt" 2>&1 || true
  fi
}

fail_after_launch() {
  local code="$1"
  local reason="$2"
  capture_diagnostics "$reason"
  if [[ -n "$EMULATOR_PID" ]] && kill -0 "$EMULATOR_PID" 2>/dev/null; then
    kill "$EMULATOR_PID" 2>/dev/null || true
    wait "$EMULATOR_PID" 2>/dev/null || true
  fi
  echo "$reason" >&2
  exit "$code"
}

"$EMULATOR" \
  -avd "$AVD_NAME" \
  -no-window -no-audio -no-boot-anim -no-snapshot \
  -gpu swiftshader_indirect -memory 3072 -cores 2 \
  > "$LOG" 2>&1 &
EMULATOR_PID=$!
printf '%s\n' "$EMULATOR_PID" > "$EVIDENCE_DIR/emulator-pid-api-${API_LEVEL}.txt"

DEVICE_DEADLINE=$((SECONDS + DEVICE_TIMEOUT_SECONDS))
while (( SECONDS < DEVICE_DEADLINE )); do
  kill -0 "$EMULATOR_PID" 2>/dev/null || fail_after_launch 5 "emulator process exited before adb device readiness"
  "$ADB" devices -l > "$EVIDENCE_DIR/adb-devices-current-api-${API_LEVEL}.txt" 2>&1 || true
  SERIAL="$(awk 'NR>1 && $2=="device" && $1 ~ /^emulator-/ {print $1; exit}' "$EVIDENCE_DIR/adb-devices-current-api-${API_LEVEL}.txt")"
  if [[ -n "$SERIAL" ]]; then
    break
  fi
  sleep "$POLL_INTERVAL_SECONDS"
done
[[ -n "$SERIAL" ]] || fail_after_launch 6 "bounded adb device readiness timeout after ${DEVICE_TIMEOUT_SECONDS}s"
printf '%s\n' "$SERIAL" > "$EVIDENCE_DIR/emulator-serial-api-${API_LEVEL}.txt"

BOOT_DEADLINE=$((SECONDS + BOOT_TIMEOUT_SECONDS))
BOOT_READY=0
while (( SECONDS < BOOT_DEADLINE )); do
  kill -0 "$EMULATOR_PID" 2>/dev/null || fail_after_launch 7 "emulator process exited before sys.boot_completed"
  if [[ "$("$ADB" -s "$SERIAL" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then
    BOOT_READY=1
    break
  fi
  sleep "$POLL_INTERVAL_SECONDS"
done
[[ "$BOOT_READY" -eq 1 ]] || fail_after_launch 8 "bounded sys.boot_completed timeout after ${BOOT_TIMEOUT_SECONDS}s"

"$ADB" -s "$SERIAL" shell input keyevent 82 || true
"$ADB" -s "$SERIAL" shell getprop ro.build.version.sdk | tr -d '\r' | tee "$EVIDENCE_DIR/android-api.txt"
"$ADB" -s "$SERIAL" shell getprop ro.product.cpu.abi | tr -d '\r' | tee "$EVIDENCE_DIR/android-abi.txt"
"$ADB" -s "$SERIAL" devices -l > "$EVIDENCE_DIR/adb-devices-ready-api-${API_LEVEL}.txt"
printf '%s\n' "READY" > "$EVIDENCE_DIR/avd-readiness-api-${API_LEVEL}.txt"
