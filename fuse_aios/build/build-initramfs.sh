#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUSYBOX_BIN="${BUSYBOX_BIN:-}"
OUTPUT="${1:-$ROOT/out/fuse-aios-initramfs.cpio.gz}"
OUTPUT="$(realpath -m "$OUTPUT")"
[[ -n "$BUSYBOX_BIN" && -x "$BUSYBOX_BIN" ]] || { echo 'BUSYBOX_BIN must point to an executable static BusyBox' >&2; exit 42; }
if ldd "$BUSYBOX_BIN" 2>&1 | grep -q '=>'; then
  echo 'BUSYBOX_BIN must be statically linked for the sovereign bootstrap initramfs' >&2
  exit 43
fi
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP"/{bin,dev,etc,proc,sys,tmp}
cp "$BUSYBOX_BIN" "$TMP/bin/busybox"
cp "$ROOT/rootfs/init" "$TMP/init"
chmod 0755 "$TMP/init" "$TMP/bin/busybox"
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-0}"
find "$TMP" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
mkdir -p "$(dirname "$OUTPUT")"
(
  cd "$TMP"
  find . -print0 | LC_ALL=C sort -z | cpio --null --create --format=newc --reproducible 2>/dev/null | gzip -n -9 > "$OUTPUT"
)
sha256sum "$OUTPUT"
