from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from coordinator import DistributedCoordinator
from runtime import digest, utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    root = out / "coordination-runtime"
    plane = DistributedCoordinator(root, queue_high_watermark=4)
    w1 = plane.register_worker("worker-a", capabilities=("build", "audit"), affinity=("ws-a",))
    w2 = plane.register_worker("worker-b", capabilities=("build",), affinity=("ws-b",))

    gates = {}
    gates["leader_election"] = plane.elect_leader("worker-a", w1["epoch"], lease_seconds=30, now_epoch=100)["elected"]
    gates["split_brain_rejected"] = not plane.elect_leader("worker-b", w2["epoch"], lease_seconds=30, now_epoch=101)["elected"]

    lock1 = plane.acquire_lock("resource-x", "worker-a", w1["epoch"], lease_seconds=10, now_epoch=100)
    lock2 = plane.acquire_lock("resource-x", "worker-b", w2["epoch"], lease_seconds=10, now_epoch=101)
    lock3 = plane.acquire_lock("resource-x", "worker-b", w2["epoch"], lease_seconds=10, now_epoch=111)
    gates["atomic_resource_lock"] = lock1["acquired"] and not lock2["acquired"]
    gates["fencing_token_advances"] = lock3["acquired"] and lock3["lock"]["fencing_token"] > lock1["lock"]["fencing_token"]

    plane.submit_job("job-a1", tenant_id="tenant-a", workstream_id="ws-a", capability="build", priority=90)
    plane.submit_job("job-a2", tenant_id="tenant-a", workstream_id="ws-a", capability="build", priority=80)
    plane.submit_job("job-b1", tenant_id="tenant-b", workstream_id="ws-b", capability="build", priority=10)
    first = plane.dispatch_next("worker-a", w1["epoch"], now_epoch=101)
    plane.complete_job(first["job_id"], first["assigned_worker"], first["assigned_epoch"], result={"ok": True})
    second = plane.dispatch_next("worker-a", w1["epoch"], now_epoch=102)
    gates["affinity_routing"] = first["assigned_worker"] == "worker-a" and second["assigned_worker"] == "worker-b"
    gates["fair_tenant_scheduling"] = first["tenant_id"] == "tenant-a" and second["tenant_id"] == "tenant-b"

    plane.submit_job("job-c1", tenant_id="tenant-c", workstream_id="ws-c", capability="audit", priority=50)
    backpressure = False
    try:
        plane.submit_job("job-d1", tenant_id="tenant-d", workstream_id="ws-d", capability="build", priority=50)
    except RuntimeError as exc:
        backpressure = str(exc) == "QUEUE_BACKPRESSURE"
    gates["queue_backpressure"] = backpressure

    restarted = plane.register_worker("worker-b", capabilities=("build",), affinity=("ws-b",))
    fenced = False
    try:
        plane.complete_job(second["job_id"], "worker-b", w2["epoch"], result={"stale": True})
    except RuntimeError as exc:
        fenced = str(exc) == "FENCED_WORKER"
    gates["duplicate_worker_fencing"] = fenced and restarted["epoch"] > w2["epoch"]

    replayed = DistributedCoordinator(root, queue_high_watermark=4)
    gates["restart_replay"] = replayed.verify_chain() and replayed.state.jobs[first["job_id"]]["status"] == "COMPLETED"

    receipt = {
        "status": "DISTRIBUTED_COORDINATION_VERIFIED" if all(gates.values()) else "DISTRIBUTED_COORDINATION_FAILED",
        "generated_at": utc_now(),
        "gates": gates,
        "metrics": {
            "workers": len(replayed.state.workers),
            "jobs": len(replayed.state.jobs),
            "locks": len(replayed.state.locks),
            "events": len(replayed._events()),
        },
        "truth_boundary": {
            "github_actions_execution": True,
            "multi_process_local_reference": True,
            "cloud_distributed_runtime": False,
            "always_on_leader": False,
        },
    }
    receipt["sha256"] = digest(receipt)
    (out / "sol-61-coordination-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
