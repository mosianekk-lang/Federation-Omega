#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCH=""; KERNEL=""; INITRAMFS=""; EVIDENCE_DIR="${ROOT}/out/boot-evidence"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --arch) ARCH="${2:-}"; shift 2 ;;
    --kernel) KERNEL="${2:-}"; shift 2 ;;
    --initramfs) INITRAMFS="${2:-}"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ "$ARCH" == x86_64 || "$ARCH" == arm64 ]] || { echo 'arch must be x86_64 or arm64' >&2; exit 2; }
[[ -s "$KERNEL" && -s "$INITRAMFS" ]] || { echo 'kernel and initramfs must exist and be non-empty' >&2; exit 42; }
if [[ "$ARCH" == x86_64 ]]; then
  QEMU=qemu-system-x86_64
  MACHINE='q35,accel=tcg'
  CONSOLE=ttyS0
  CPU=()
  EARLY='earlyprintk=ttyS0'
else
  QEMU=qemu-system-aarch64
  MACHINE='virt,accel=tcg'
  CONSOLE=ttyAMA0
  CPU=(-cpu cortex-a57)
  EARLY=''
fi
command -v "$QEMU" >/dev/null || { echo "$QEMU unavailable" >&2; exit 42; }
mkdir -p "$EVIDENCE_DIR"
BOOT_KERNEL="$KERNEL"
KERNEL_STAGED=false
if [[ ! -r "$KERNEL" ]]; then
  if command -v sudo >/dev/null && sudo -n test -r "$KERNEL"; then
    BOOT_KERNEL="$EVIDENCE_DIR/${ARCH}-kernel.bin"
    sudo -n cat "$KERNEL" > "$BOOT_KERNEL"
    chmod 0644 "$BOOT_KERNEL"
    KERNEL_STAGED=true
  else
    echo 'kernel exists but is unreadable and bounded sudo staging is unavailable' >&2
    exit 45
  fi
fi
[[ -r "$BOOT_KERNEL" && -s "$BOOT_KERNEL" ]] || { echo 'staged kernel is not readable and non-empty' >&2; exit 45; }
LOG="$EVIDENCE_DIR/${ARCH}-serial.log"; RECEIPT="$EVIDENCE_DIR/${ARCH}-boot-receipt.json"
"$QEMU" -machine "$MACHINE" "${CPU[@]}" -m 256 -smp 1 -nographic -no-reboot \
  -kernel "$BOOT_KERNEL" -initrd "$INITRAMFS" \
  -append "console=$CONSOLE,115200 panic=-1 $EARLY" >"$LOG" 2>&1 &
PID=$!
FOUND=0
for _ in $(seq 1 180); do
  if grep -Fq 'FUSE_AIOS_BOOT_OK' "$LOG" 2>/dev/null; then FOUND=1; break; fi
  if ! kill -0 "$PID" 2>/dev/null; then break; fi
  sleep 0.25
done
if kill -0 "$PID" 2>/dev/null; then kill "$PID" 2>/dev/null || true; fi
wait "$PID" 2>/dev/null || true
[[ "$FOUND" == 1 ]] || { cat "$LOG" >&2; echo 'boot sentinel not observed' >&2; exit 44; }
python3 - "$ARCH" "$BOOT_KERNEL" "$INITRAMFS" "$LOG" "$RECEIPT" "$QEMU" "${FUSE_AIOS_SOURCE_SHA:-UNKNOWN}" "$KERNEL_STAGED" "$(basename "$KERNEL")" <<'PY'
import hashlib, json, pathlib, subprocess, sys
arch,kernel,initramfs,log,receipt,qemu,source_sha,kernel_staged,kernel_source_name=sys.argv[1:]
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
version=subprocess.check_output([qemu,'--version'],text=True,errors='replace').splitlines()[0]
out={
    'schema':'FUSE-AIOS-QEMU-BOOT-RECEIPT-V1',
    'source_sha':source_sha,
    'arch':arch,
    'kernel_sha256':sha(kernel),
    'kernel_source_name':kernel_source_name,
    'kernel_staged_from_protected_boot':kernel_staged.lower() == 'true',
    'initramfs_sha256':sha(initramfs),
    'serial_log_sha256':sha(log),
    'qemu_version':version,
    'sentinel':'FUSE_AIOS_BOOT_OK',
    'truth':'EMULATED_BOOT_SENTINEL_PROVED',
    'physical_hardware_proved':False
}
pathlib.Path(receipt).write_text(json.dumps(out,sort_keys=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,sort_keys=True))
PY
