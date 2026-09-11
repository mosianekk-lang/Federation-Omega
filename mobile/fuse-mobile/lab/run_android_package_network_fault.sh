#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
shift || true
PACKAGE_ID="com.federationomega.fusemobile"
EVIDENCE_DIR="mdtaf-evidence"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ADB="$(bash "$SCRIPT_DIR/resolve_sdk_adb.sh")"
test -x "$ADB"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --package) PACKAGE_ID="$2"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$EVIDENCE_DIR"

read_chain() {
  "$ADB" shell cmd connectivity get-chain3-enabled 2>/dev/null | tr -d '\r'
}

read_package_rule() {
  "$ADB" shell cmd connectivity get-package-networking-enabled "$PACKAGE_ID" 2>/dev/null | tr -d '\r'
}

case "$MODE" in
  apply)
    "$ADB" shell cmd connectivity help > "$EVIDENCE_DIR/package-network-fault-help.txt" 2>&1
    grep -F "set-chain3-enabled" "$EVIDENCE_DIR/package-network-fault-help.txt" >/dev/null
    grep -F "set-package-networking-enabled" "$EVIDENCE_DIR/package-network-fault-help.txt" >/dev/null
    grep -F "get-package-networking-enabled" "$EVIDENCE_DIR/package-network-fault-help.txt" >/dev/null

    "$ADB" shell cmd connectivity set-chain3-enabled true \
      > "$EVIDENCE_DIR/package-network-chain-enable.txt"
    CHAIN="$(read_chain)"
    printf '%s\n' "$CHAIN" > "$EVIDENCE_DIR/package-network-chain-enable-readback.txt"
    test "$CHAIN" = "chain:enabled"

    "$ADB" shell cmd connectivity set-package-networking-enabled false "$PACKAGE_ID" \
      > "$EVIDENCE_DIR/package-network-deny.txt"
    RULE="$(read_package_rule)"
    printf '%s\n' "$RULE" > "$EVIDENCE_DIR/package-network-deny-readback.txt"
    test "$RULE" = "$PACKAGE_ID:deny"
    ;;
  restore)
    "$ADB" shell cmd connectivity set-package-networking-enabled true "$PACKAGE_ID" \
      > "$EVIDENCE_DIR/package-network-restore.txt" 2>&1 || true
    RULE="$(read_package_rule || true)"
    printf '%s\n' "$RULE" > "$EVIDENCE_DIR/package-network-restore-readback.txt"

    "$ADB" shell cmd connectivity set-chain3-enabled false \
      > "$EVIDENCE_DIR/package-network-chain-disable.txt" 2>&1 || true
    CHAIN="$(read_chain || true)"
    printf '%s\n' "$CHAIN" > "$EVIDENCE_DIR/package-network-chain-disable-readback.txt"

    test "$RULE" = "$PACKAGE_ID:allow"
    test "$CHAIN" = "chain:disabled"
    ;;
  *)
    echo "Usage: $0 apply|restore [--package PACKAGE] [--evidence-dir DIR]" >&2
    exit 2
    ;;
esac
