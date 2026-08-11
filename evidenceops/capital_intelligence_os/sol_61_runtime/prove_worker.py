from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from worker import DurableWorkerPlane, Job


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp:
        plane = DurableWorkerPlane(temp)
        job = Job(
            job_id="proof-job-001",
            mission_id="sol-61-worker-plane",
            workstream_id="durable-worker-proof",
            action_class="runtime.proof",
            payload={"scope": "provider-neutral-ci"},
            idempotency_key="proof-idem-001",
            max_attempts=3,
            priority=100,
            checkpoint_id="cp-provider-proof-001",
        )
        first = plane.enqueue(job)
        duplicate = plane.enqueue(job)
        heartbeat = plane.heartbeat("github-actions-worker", ("runtime.proof",))
        lease = plane.lease("github-actions-worker", "runtime.proof", lease_seconds=1)
        future = (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
        recovered = plane.recover_expired_leases(future)
        lease2 = plane.lease("github-actions-worker-2", "runtime.proof", lease_seconds=60)
        receipt = plane.complete("proof-job-001", "github-actions-worker-2", {"status": "verified"})
        replay = DurableWorkerPlane(temp)

        gates = {
            "idempotent_enqueue": first["job_id"] == duplicate["job_id"],
            "heartbeat_recorded": heartbeat["worker_id"] in plane.state.workers,
            "lease_acquired": lease is not None and lease["status"] == "LEASED",
            "expired_lease_recovered": recovered == ["proof-job-001"],
            "cross_worker_continuation": lease2 is not None and lease2["leased_by"] == "github-actions-worker-2",
            "checkpoint_continuity": receipt["checkpoint_id"] == "cp-provider-proof-001",
            "idempotent_result_persistence": replay.state.results["proof-job-001"]["sha256"] == receipt["sha256"],
            "event_chain_integrity": replay.verify_event_chain(),
        }
        result = {
            "status": "DURABLE_WORKER_REFERENCE_VERIFIED" if all(gates.values()) else "FAILED",
            "gates": gates,
            "truth_boundary": {
                "github_actions_worker_execution": True,
                "queue_leasing_reference": True,
                "continuous_external_worker": False,
                "cloud_run_live": False,
                "apps_script_live": False,
            },
            "receipt": receipt,
        }
        (output / "sol-61-worker-receipt.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (output / "worker-events.jsonl").write_text(Path(temp, "worker-events.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
        (output / "worker-state.json").write_text(Path(temp, "worker-state.json").read_text(encoding="utf-8"), encoding="utf-8")
        if not all(gates.values()):
            raise SystemExit("worker proof gates failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
