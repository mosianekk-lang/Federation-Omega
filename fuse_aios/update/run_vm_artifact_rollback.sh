#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCH=""; KERNEL=""; EVIDENCE_DIR="${ROOT}/out/boot-evidence"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --arch) ARCH="${2:-}"; shift 2 ;;
    --kernel) KERNEL="${2:-}"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ "$ARCH" == x86_64 || "$ARCH" == arm64 ]] || { echo 'arch must be x86_64 or arm64' >&2; exit 2; }
[[ -s "$KERNEL" ]] || { echo 'kernel must exist and be non-empty' >&2; exit 42; }
BUSYBOX_BIN="${BUSYBOX_BIN:-/bin/busybox}"
[[ -x "$BUSYBOX_BIN" ]] || { echo 'static BusyBox is required' >&2; exit 42; }
mkdir -p "$EVIDENCE_DIR"
BASE_IMAGE="$EVIDENCE_DIR/${ARCH}-txn-base-0.1.0.cpio.gz"
BAD_IMAGE="$EVIDENCE_DIR/${ARCH}-txn-candidate-0.1.1-bad.cpio.gz"
BUSYBOX_BIN="$BUSYBOX_BIN" SOURCE_DATE_EPOCH=0 FUSE_AIOS_BOOT_MODE=healthy FUSE_AIOS_RELEASE_VERSION=0.1.0 \
  bash "$ROOT/build/build-initramfs.sh" "$BASE_IMAGE"
BUSYBOX_BIN="$BUSYBOX_BIN" SOURCE_DATE_EPOCH=0 FUSE_AIOS_BOOT_MODE=fail_health FUSE_AIOS_RELEASE_VERSION=0.1.1-bad \
  bash "$ROOT/build/build-initramfs.sh" "$BAD_IMAGE"
bash "$ROOT/boot/run-qemu-smoke.sh" --arch "$ARCH" --kernel "$KERNEL" --initramfs "$BASE_IMAGE" \
  --evidence-dir "$EVIDENCE_DIR" --label "${ARCH}-txn-base-initial" --expect-sentinel FUSE_AIOS_BOOT_OK
bash "$ROOT/boot/run-qemu-smoke.sh" --arch "$ARCH" --kernel "$KERNEL" --initramfs "$BAD_IMAGE" \
  --evidence-dir "$EVIDENCE_DIR" --label "${ARCH}-txn-candidate-bad" --expect-sentinel FUSE_AIOS_HEALTH_FAIL
bash "$ROOT/boot/run-qemu-smoke.sh" --arch "$ARCH" --kernel "$KERNEL" --initramfs "$BASE_IMAGE" \
  --evidence-dir "$EVIDENCE_DIR" --label "${ARCH}-txn-base-restored" --expect-sentinel FUSE_AIOS_BOOT_OK
python3 - "$ROOT" "$ARCH" "$BASE_IMAGE" "$BAD_IMAGE" "$EVIDENCE_DIR" "${FUSE_AIOS_SOURCE_SHA:-UNKNOWN}" <<'PY'
import hashlib, json, pathlib, sys
root,arch,base,bad,evidence,source_sha=sys.argv[1:]
root=pathlib.Path(root); evidence=pathlib.Path(evidence)
sys.path.insert(0,str(root/'update'))
from transactional_host import TransactionalHost
sha=lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
base_sha=sha(base); bad_sha=sha(bad)
initial=json.loads((evidence/f'{arch}-txn-base-initial-boot-receipt.json').read_text())
candidate=json.loads((evidence/f'{arch}-txn-candidate-bad-boot-receipt.json').read_text())
restored=json.loads((evidence/f'{arch}-txn-base-restored-boot-receipt.json').read_text())
assert initial['observed_sentinel']=='FUSE_AIOS_BOOT_OK'
assert candidate['observed_sentinel']=='FUSE_AIOS_HEALTH_FAIL'
assert restored['observed_sentinel']=='FUSE_AIOS_BOOT_OK'
assert initial['initramfs_sha256']==restored['initramfs_sha256']==base_sha
assert candidate['initramfs_sha256']==bad_sha
host=TransactionalHost('0.1.0',base_sha)
host.stage('0.1.1-bad',bad_sha); host.activate(); host.evaluate_health(False)
assert host.state=='ROLLED_BACK' and host.active_slot=='A'
out={
  'schema':'FUSE-AIOS-VM-ARTIFACT-ROLLBACK-RECEIPT-V1',
  'source_sha':source_sha,
  'arch':arch,
  'status':'PASS',
  'base_initramfs_sha256':base_sha,
  'failed_candidate_initramfs_sha256':bad_sha,
  'initial_boot_receipt':initial,
  'failed_candidate_boot_receipt':candidate,
  'restored_boot_receipt':restored,
  'transactional_state_machine':host.receipt(),
  'truth':'VM_ARTIFACT_ROLLBACK_PROVED',
  'network_devices':'NONE',
  'real_block_device_rollback_proved':False,
  'firmware_or_bootloader_rollback_proved':False,
  'physical_hardware_proved':False
}
path=evidence/f'{arch}-vm-rollback-receipt.json'
path.write_text(json.dumps(out,sort_keys=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','arch':arch,'receipt':str(path),'truth':out['truth'],'base_sha256':base_sha,'failed_candidate_sha256':bad_sha},sort_keys=True))
PY
