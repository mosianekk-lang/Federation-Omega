from __future__ import annotations

import json
import tempfile
from pathlib import Path

try:
    from .fdof_hosted_state_v1 import export_capsule, restore_capsule, write_capsule
    from .sol_62_frontier_primitives import FenceError, IdempotencyCollision, digest, utc_now
    from .sol_62_runtime import Sol62Runtime
except ImportError:
    from fdof_hosted_state_v1 import export_capsule, restore_capsule, write_capsule
    from sol_62_frontier_primitives import FenceError, IdempotencyCollision, digest, utc_now
    from sol_62_runtime import Sol62Runtime


def run(output_dir: str = "runtime-output/fdof-hosted-state") -> dict[str, object]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = Sol62Runtime(root / "runner-a")
        second = Sol62Runtime(root / "runner-b")
        try:
            first.control.cas_put("fdof.hosted", "probe", {"phase": "runner-a"}, expected_version=0)
            first.control.append_event("mission-hosted-state", "FDOF_HOSTED_RUNNER_A", {"phase": 1})
            first.control.reserve_idempotency(
                "fdof-hosted-idem-1", {"operation": "READ", "target": "host:test"}, "AT_MOST_ONCE"
            )
            fence_a = first.acquire_execution_fence(
                "hosted-transition", "runner-a", ttl_seconds=60, now_epoch=1000
            )
            capsule = export_capsule(first, source_version="PROOF_RUNNER")
            capsule_path = output / "fdof-hosted-state-capsule.json"
            write_capsule(str(capsule_path), capsule)

            restore_capsule(second, capsule)
            stale_worker_blocked = False
            try:
                second.acquire_execution_fence(
                    "hosted-transition", "runner-b", ttl_seconds=60, now_epoch=1001
                )
            except FenceError:
                stale_worker_blocked = True

            fence_b = second.acquire_execution_fence(
                "hosted-transition", "runner-b", ttl_seconds=60, now_epoch=1061
            )
            replay = second.control.reserve_idempotency(
                "fdof-hosted-idem-1", {"operation": "READ", "target": "host:test"}, "AT_MOST_ONCE"
            )
            collision_blocked = False
            try:
                second.control.reserve_idempotency(
                    "fdof-hosted-idem-1", {"operation": "WRITE", "target": "host:test"}, "AT_MOST_ONCE"
                )
            except IdempotencyCollision:
                collision_blocked = True

            receipt = {
                "schema": "FDOF-HOSTED-STATE-PROOF-V1",
                "observed_at": utc_now(),
                "state": "VERIFIED" if all(
                    [
                        stale_worker_blocked,
                        collision_blocked,
                        int(fence_b["fencing_token"]) > int(fence_a["fencing_token"]),
                        second.control.verify_event_chain(),
                    ]
                ) else "FAILED",
                "cross_runtime_restore": True,
                "stale_worker_blocked": stale_worker_blocked,
                "fencing_token_a": int(fence_a["fencing_token"]),
                "fencing_token_b": int(fence_b["fencing_token"]),
                "monotonic_fencing": int(fence_b["fencing_token"]) > int(fence_a["fencing_token"]),
                "idempotent_replay_preserved": bool(replay.get("request_sha256")),
                "idempotency_collision_blocked": collision_blocked,
                "event_chain_valid": second.control.verify_event_chain(),
                "authority_transfer": False,
                "provider_effect": False,
                "external_effect": False,
                "capsule_sha256": capsule["capsule_sha256"],
            }
            receipt["receipt_sha256"] = digest(receipt)
            receipt_path = output / "receipt.json"
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if receipt["state"] != "VERIFIED":
                raise SystemExit("FDOF hosted-state proof failed")
            return receipt
        finally:
            first.close()
            second.close()


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
