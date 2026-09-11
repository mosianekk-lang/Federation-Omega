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
if [[ "$ARCH" == x86_64 ]]; then QEMU=qemu-system-x86_64; MACHINE='q35,accel=tcg'; CONSOLE=ttyS0; CPU=(); else QEMU=qemu-system-aarch64; MACHINE='virt,accel=tcg'; CONSOLE=ttyAMA0; CPU=(-cpu cortex-a57); fi
command -v "$QEMU" >/dev/null || { echo "$QEMU unavailable" >&2; exit 42; }
mkdir -p "$EVIDENCE_DIR"
LOG="$EVIDENCE_DIR/${ARCH}-serial.log"; RECEIPT="$EVIDENCE_DIR/${ARCH}-boot-receipt.json"
"$QEMU" -machine "$MACHINE" "${CPU[@]}" -m 256 -smp 1 -nographic -no-reboot -kernel "$KERNEL" -initrd "$INITRAMFS" -append "console=$CONSOLE panic=-1" >"$LOG" 2>&1 &
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
python3 - "$ARCH" "$KERNEL" "$INITRAMFS" "$LOG" "$RECEIPT" "$QEMU" <<'PY'
import hashlib, json, pathlib, subprocess, sys
arch,kernel,initramfs,log,receipt,qemu=sys.argv[1:]
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
version=subprocess.check_output([qemu,'--version'],text=True,errors='replace').splitlines()[0]
out={'schema':'FUSE-AIOS-QEMU-BOOT-RECEIPT-V1','arch':arch,'kernel_sha256':sha(kernel),'initramfs_sha256':sha(initramfs),'serial_log_sha256':sha(log),'qemu_version':version,'sentinel':'FUSE_AIOS_BOOT_OK','truth':'EMULATED_BOOT_SENTINEL_PROVED','physical_hardware_proved':False}
pathlib.Path(receipt).write_text(json.dumps(out,sort_keys=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,sort_keys=True))
PY
