#!/usr/bin/env python3
"""Deterministic failure-first canary for SOVARA durable recovery v40."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile

from durable_runtime import DurableMissionRuntime, LeaseConflict


class CanaryClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 22, 15, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def run_canary(output: Path) -> dict[str, object]:
    clock = CanaryClock()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        database = root / "runtime.sqlite"
        backup = root / "backup.sqlite"
        restored = root / "restored.sqlite"

        runtime = DurableMissionRuntime(database, clock=clock)
        runtime.create_mission(
            "SOVARA-V40-CANARY", {"objective": "crash-restart-recover"},
            idempotency_key="mission-create",
        )
        first_task = runtime.enqueue_task(
            "SOVARA-V40-CANARY", "TASK-RESUME", {"work": "checkpointed"},
            idempotency_key="task-resume",
        )
        duplicate_task = runtime.enqueue_task(
            "SOVARA-V40-CANARY", "TASK-RESUME", {"work": "checkpointed"},
            idempotency_key="task-resume",
        )
        stale = runtime.acquire_lease(
            "SOVARA-V40-CANARY", "RESOURCE-A", "WORKER-1", ttl_seconds=1
        )
        runtime.start_task("TASK-RESUME", stale)
        before_crash = runtime.checkpoint("SOVARA-V40-CANARY")
        runtime.close()

        clock.advance(2)
        runtime = DurableMissionRuntime(database, clock=clock)
        recovery = runtime.recover_orphaned_tasks(
            "SOVARA-V40-CANARY", idempotency_key="orphan-recovery-1"
        )
        recovery_replay = runtime.recover_orphaned_tasks(
            "SOVARA-V40-CANARY", idempotency_key="orphan-recovery-1"
        )
        clock.advance(1)
        fresh = runtime.acquire_lease(
            "SOVARA-V40-CANARY", "RESOURCE-A", "WORKER-2", ttl_seconds=10
        )
        stale_fence_denied = False
        try:
            runtime.start_task("TASK-RESUME", stale)
        except LeaseConflict:
            stale_fence_denied = True
        resumed = runtime.start_task("TASK-RESUME", fresh)
        runtime.complete_task(
            "TASK-RESUME", {"ok": True}, idempotency_key="task-complete"
        )
        runtime.complete_mission(
            "SOVARA-V40-CANARY", {"status": "recovered"},
            idempotency_key="mission-complete",
        )
        chain = runtime.verify_event_chain("SOVARA-V40-CANARY")
        backup_receipt = runtime.backup(backup)
        runtime.close()

        restore_receipt = DurableMissionRuntime.restore(backup, restored)
        restored_runtime = DurableMissionRuntime(restored, clock=clock)
        restored_chain = restored_runtime.verify_event_chain("SOVARA-V40-CANARY")
        restored_runtime.close()

        assertions = {
            "duplicateSuppression": first_task["task_id"] == duplicate_task["task_id"],
            "restartRecovery": recovery["retryWaitCount"] == 1,
            "idempotentRecoveryReceipt": recovery == recovery_replay,
            "staleFenceDenied": stale_fence_denied,
            "resumedOnNewFence": resumed["attempt"] == 2 and fresh.fence == stale.fence + 1,
            "eventChainVerified": bool(chain["valid"]),
            "backupIntegrity": backup_receipt.integrity == "ok",
            "restoreExact": restored_chain == chain and restore_receipt.integrity == "ok",
        }
        result: dict[str, object] = {
            "contract": "SOVARA_DURABLE_RECOVERY_CANARY_V40",
            "status": "PASS" if all(assertions.values()) else "FAIL",
            "assertions": assertions,
            "checkpointBeforeCrash": before_crash,
            "recoveryReceipt": recovery,
            "finalEventChain": chain,
            "backupSha256": backup_receipt.sha256,
            "restoreSha256": restore_receipt.sha256,
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output.write_text(encoded, encoding="utf-8")
    result["proofPath"] = str(output)
    result["proofSha256"] = hashlib.sha256(encoded.encode()).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path,
        default=Path("DURABLE_RECOVERY_CANARY_V40.json"),
    )
    args = parser.parse_args()
    result = run_canary(args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
