#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 [--output-env FILE]" >&2
}

OUTPUT_ENV=""
if [[ $# -gt 0 ]]; then
  if [[ $# -eq 2 && "$1" == "--output-env" ]]; then
    OUTPUT_ENV="$2"
  else
    usage
    exit 64
  fi
fi

SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$SDK_ROOT" ]]; then
  echo "ANDROID_SDK_ROOT or ANDROID_HOME must identify the Android SDK" >&2
  exit 2
fi
if [[ ! -d "$SDK_ROOT" ]]; then
  echo "Android SDK root does not exist: $SDK_ROOT" >&2
  exit 3
fi
SDK_ROOT="$(realpath -e "$SDK_ROOT")"
CMDLINE_ROOT="$SDK_ROOT/cmdline-tools"
if [[ ! -d "$CMDLINE_ROOT" ]]; then
  echo "Android SDK cmdline-tools directory is missing: $CMDLINE_ROOT" >&2
  exit 4
fi
CMDLINE_ROOT_REAL="$(realpath -e "$CMDLINE_ROOT")"

best_revision=""
best_root=""
shopt -s nullglob
for candidate in "$CMDLINE_ROOT"/*; do
  [[ -d "$candidate" ]] || continue
  # Convenience aliases such as `latest` are not stable provenance. Only
  # concrete, non-symlink installations may satisfy the exact-toolchain court.
  [[ -L "$candidate" ]] && continue
  [[ "$(basename "$candidate")" != "latest" ]] || continue

  sdkmanager="$candidate/bin/sdkmanager"
  avdmanager="$candidate/bin/avdmanager"
  props="$candidate/source.properties"
  [[ -x "$sdkmanager" && -x "$avdmanager" && -f "$props" ]] || continue

  candidate_real="$(realpath -e "$candidate")"
  case "$candidate_real/" in
    "$CMDLINE_ROOT_REAL"/*/) ;;
    *) continue ;;
  esac
  [[ "$(realpath -e "$sdkmanager")" == "$candidate_real/bin/sdkmanager" ]] || continue
  [[ "$(realpath -e "$avdmanager")" == "$candidate_real/bin/avdmanager" ]] || continue

  revision="$(awk -F= '/^[[:space:]]*Pkg\.Revision[[:space:]]*=/{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}' "$props")"
  [[ "$revision" =~ ^[0-9]+([.][0-9]+)*$ ]] || continue

  if [[ -z "$best_revision" ]] || [[ "$(printf '%s\n%s\n' "$best_revision" "$revision" | sort -V | tail -n1)" == "$revision" && "$revision" != "$best_revision" ]]; then
    best_revision="$revision"
    best_root="$candidate_real"
  fi
done

if [[ -z "$best_root" ]]; then
  echo "no concrete Android cmdline-tools installation provides sdkmanager+avdmanager+valid Pkg.Revision" >&2
  exit 5
fi

SDKMANAGER="$best_root/bin/sdkmanager"
AVDMANAGER="$best_root/bin/avdmanager"

emit() {
  printf 'SDK_ROOT=%s\n' "$SDK_ROOT"
  printf 'CMDLINE_TOOLS_ROOT=%s\n' "$best_root"
  printf 'CMDLINE_TOOLS_REVISION=%s\n' "$best_revision"
  printf 'SDKMANAGER=%s\n' "$SDKMANAGER"
  printf 'AVDMANAGER=%s\n' "$AVDMANAGER"
}

if [[ -n "$OUTPUT_ENV" ]]; then
  mkdir -p "$(dirname "$OUTPUT_ENV")"
  emit > "$OUTPUT_ENV"
fi
emit
