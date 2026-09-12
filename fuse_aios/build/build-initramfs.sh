#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUSYBOX_BIN="${BUSYBOX_BIN:-}"
OUTPUT="${1:-$ROOT/out/fuse-aios-initramfs.cpio.gz}"
OUTPUT="$(realpath -m "$OUTPUT")"
BOOT_MODE="${FUSE_AIOS_BOOT_MODE:-healthy}"
RELEASE_VERSION="${FUSE_AIOS_RELEASE_VERSION:-0.1.0}"
[[ "$BOOT_MODE" == "healthy" || "$BOOT_MODE" == "fail_health" ]] || { echo 'FUSE_AIOS_BOOT_MODE must be healthy or fail_health' >&2; exit 46; }
[[ "$RELEASE_VERSION" =~ ^[A-Za-z0-9._+-]+$ ]] || { echo 'FUSE_AIOS_RELEASE_VERSION contains unsupported characters' >&2; exit 47; }
[[ -n "$BUSYBOX_BIN" && -x "$BUSYBOX_BIN" ]] || { echo 'BUSYBOX_BIN must point to an executable static BusyBox' >&2; exit 42; }
if ldd "$BUSYBOX_BIN" 2>&1 | grep -q '=>'; then
  echo 'BUSYBOX_BIN must be statically linked for the sovereign bootstrap initramfs' >&2
  exit 43
fi
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP"/{bin,dev,etc,proc,sys,tmp}
cp "$BUSYBOX_BIN" "$TMP/bin/busybox"
cp "$ROOT/rootfs/init" "$TMP/init"
printf '%s\n' "$BOOT_MODE" > "$TMP/etc/fuse-aios-boot-mode"
printf '%s\n' "$RELEASE_VERSION" > "$TMP/etc/fuse-aios-release"
chmod 0755 "$TMP/init" "$TMP/bin/busybox"
chmod 0644 "$TMP/etc/fuse-aios-boot-mode" "$TMP/etc/fuse-aios-release"
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-0}"
find "$TMP" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
mkdir -p "$(dirname "$OUTPUT")"
(
  cd "$TMP"
  find . -print0 | LC_ALL=C sort -z | cpio --null --create --format=newc --reproducible 2>/dev/null | gzip -n -9 > "$OUTPUT"
)
sha256sum "$OUTPUT"
