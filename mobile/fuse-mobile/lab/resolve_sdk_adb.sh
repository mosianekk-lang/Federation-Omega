#!/usr/bin/env bash
set -euo pipefail

SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$SDK_ROOT" ]]; then
  echo "ANDROID_SDK_ROOT or ANDROID_HOME must identify the Android SDK" >&2
  exit 64
fi
if [[ "$SDK_ROOT" != /* ]]; then
  echo "Android SDK root must be an absolute path" >&2
  exit 64
fi

EXPECTED_ADB="$SDK_ROOT/platform-tools/adb"
if [[ ! -x "$EXPECTED_ADB" ]]; then
  echo "Exact SDK adb is missing or not executable: $EXPECTED_ADB" >&2
  exit 65
fi
EXPECTED_REAL="$(realpath -e "$EXPECTED_ADB")"

if [[ -n "${ADB_BIN:-}" ]]; then
  if [[ "$ADB_BIN" != /* ]]; then
    echo "ADB_BIN must be an absolute exact SDK adb path; ambient/bare adb is forbidden" >&2
    exit 66
  fi
  if [[ ! -x "$ADB_BIN" ]]; then
    echo "ADB_BIN is not executable: $ADB_BIN" >&2
    exit 66
  fi
  SUPPLIED_REAL="$(realpath -e "$ADB_BIN")"
  if [[ "$SUPPLIED_REAL" != "$EXPECTED_REAL" ]]; then
    echo "ADB_BIN does not match SDK_ROOT/platform-tools/adb" >&2
    exit 67
  fi
fi

printf '%s\n' "$EXPECTED_REAL"
