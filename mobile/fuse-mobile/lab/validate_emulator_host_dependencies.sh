#!/usr/bin/env bash
set -euo pipefail

SDK_ROOT=""
EVIDENCE_DIR=""
API_LEVEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sdk-root)
      SDK_ROOT="${2:-}"
      shift 2
      ;;
    --evidence-dir)
      EVIDENCE_DIR="${2:-}"
      shift 2
      ;;
    --api-level)
      API_LEVEL="${2:-}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

[[ -n "$SDK_ROOT" && -n "$EVIDENCE_DIR" && -n "$API_LEVEL" ]] || {
  echo "--sdk-root, --evidence-dir and --api-level are required" >&2
  exit 2
}

SDK_ROOT="$(realpath -e "$SDK_ROOT")"
EMULATOR_ROOT="$SDK_ROOT/emulator"
QEMU="$EMULATOR_ROOT/qemu/linux-x86_64/qemu-system-x86_64"
EMULATOR="$EMULATOR_ROOT/emulator"
[[ -x "$QEMU" && -x "$EMULATOR" ]] || {
  echo "exact emulator/qemu executables are unavailable under SDK root" >&2
  exit 42
}

LDD_BIN="${LDD_BIN:-ldd}"
if [[ "$LDD_BIN" != /* ]]; then
  LDD_BIN="$(command -v "$LDD_BIN")"
fi
[[ -x "$LDD_BIN" ]] || {
  echo "ldd executable unavailable" >&2
  exit 42
}

mkdir -p "$EVIDENCE_DIR"
AFTER="$EVIDENCE_DIR/emulator-host-libs-after-api-${API_LEVEL}.txt"
CLASSIFY="$EVIDENCE_DIR/emulator-host-dependency-classification-api-${API_LEVEL}.txt"
VERSION="$EVIDENCE_DIR/emulator-version-api-${API_LEVEL}.txt"

"$LDD_BIN" "$QEMU" | tee "$AFTER"
: > "$CLASSIFY"
missing_host=0
while IFS= read -r line; do
  [[ -n "$line" ]] || continue
  soname="$(awk '{print $1}' <<<"$line")"
  [[ -n "$soname" ]] || continue
  bundled="$(find "$EMULATOR_ROOT" \( -type f -o -type l \) -name "$soname" -print -quit 2>/dev/null || true)"
  if [[ -z "$bundled" ]]; then
    printf 'HOST_MISSING\t%s\n' "$soname" | tee -a "$CLASSIFY"
    missing_host=1
    continue
  fi
  bundled_real="$(realpath -e "$bundled")"
  case "$bundled_real" in
    "$EMULATOR_ROOT"/*)
      printf 'BUNDLED_INTERNAL\t%s\t%s\n' "$soname" "$bundled_real" | tee -a "$CLASSIFY"
      ;;
    *)
      printf 'INVALID_BUNDLE_PATH\t%s\t%s\n' "$soname" "$bundled_real" | tee -a "$CLASSIFY"
      missing_host=1
      ;;
  esac
done < <(grep -F '=> not found' "$AFTER" || true)

if (( missing_host != 0 )); then
  echo "Android emulator still has unresolved host shared-library dependencies" >&2
  exit 43
fi

"$EMULATOR" -version 2>&1 | head -n 4 | tee "$VERSION"
