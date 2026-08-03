from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from runtime import digest, utc_now


@dataclass
class CoordinationState:
    workers: dict[str, dict[str, Any]] = field(default_factory=dict)
    locks: dict[str, dict[str, Any]] = field(default_factory=dict)
    queues: dict[str, list[str]] = field(default_factory=dict)
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    leader: dict[str, Any] | None = None
    tenant_dispatch_count: dict[str, int] = field(default_factory=dict)


class DistributedCoordinator:
    """Durable coordination plane for concurrent SOL 6.1 workers.

    Implements worker epochs/fencing, atomic resource locks, leader leases,
    workstream affinity, fair tenant scheduling, and queue backpressure.
    """

    def __init__(self, root: str | Path, *, queue_high_watermark: int = 100) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_file = self.root / "coordination-events.jsonl"
        self.state_file = self.root / "coordination-state.json"
        self.queue_high_watermark = queue_high_watermark
        self.state = CoordinationState()
        self._replay()

    def register_worker(self, worker_id: str, *, capabilities: tuple[str, ...], affinity: tuple[str, ...] = ()) -> dict[str, Any]:
        current = self.state.workers.get(worker_id, {})
        epoch = int(current.get("epoch", 0)) + 1
        worker = {
            "worker_id": worker_id,
            "epoch": epoch,
            "capabilities": sorted(set(capabilities)),
            "affinity": sorted(set(affinity)),
            "status": "ACTIVE",
            "heartbeat_at": utc_now(),
        }
        self._append("WORKER_REGISTERED", worker)
        return worker

    def heartbeat(self, worker_id: str, epoch: int) -> dict[str, Any]:
        worker = self._require_worker(worker_id, epoch)
        payload = {"worker_id": worker_id, "epoch": epoch, "heartbeat_at": utc_now()}
        self._append("WORKER_HEARTBEAT", payload)
        return payload

    def submit_job(self, job_id: str, *, tenant_id: str, workstream_id: str, capability: str, priority: int = 50) -> dict[str, Any]:
        if job_id in self.state.jobs:
            return self.state.jobs[job_id]
        queued = sum(1 for job in self.state.jobs.values() if job["status"] == "QUEUED")
        if queued >= self.queue_high_watermark:
            raise RuntimeError("QUEUE_BACKPRESSURE")
        job = {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "workstream_id": workstream_id,
            "capability": capability,
            "priority": int(priority),
            "status": "QUEUED",
            "submitted_at": utc_now(),
            "assigned_worker": None,
            "assigned_epoch": None,
        }
        self._append("JOB_SUBMITTED", job)
        return job

    def elect_leader(self, worker_id: str, epoch: int, *, lease_seconds: int, now_epoch: float | None = None) -> dict[str, Any]:
        self._require_worker(worker_id, epoch)
        now_epoch = time.time() if now_epoch is None else now_epoch
        leader = self.state.leader
        if leader and float(leader["lease_expires_epoch"]) > now_epoch:
            if leader["worker_id"] != worker_id or int(leader["epoch"]) != epoch:
                return {"elected": False, "leader": leader}
        payload = {
            "worker_id": worker_id,
            "epoch": epoch,
            "lease_expires_epoch": now_epoch + lease_seconds,
            "elected_at": utc_now(),
        }
        self._append("LEADER_ELECTED", payload)
        return {"elected": True, "leader": payload}

    def acquire_lock(self, resource_id: str, worker_id: str, epoch: int, *, lease_seconds: int, now_epoch: float | None = None) -> dict[str, Any]:
        self._require_worker(worker_id, epoch)
        now_epoch = time.time() if now_epoch is None else now_epoch
        lock = self.state.locks.get(resource_id)
        if lock and float(lock["lease_expires_epoch"]) > now_epoch:
            same_owner = lock["worker_id"] == worker_id and int(lock["epoch"]) == epoch
            return {"acquired": same_owner, "lock": lock}
        payload = {
            "resource_id": resource_id,
            "worker_id": worker_id,
            "epoch": epoch,
            "lease_expires_epoch": now_epoch + lease_seconds,
            "fencing_token": int(lock.get("fencing_token", 0) if lock else 0) + 1,
            "acquired_at": utc_now(),
        }
        self._append("LOCK_ACQUIRED", payload)
        return {"acquired": True, "lock": payload}

    def dispatch_next(self, leader_id: str, leader_epoch: int, *, now_epoch: float | None = None) -> dict[str, Any] | None:
        self._require_leader(leader_id, leader_epoch, now_epoch=now_epoch)
        queued = [job for job in self.state.jobs.values() if job["status"] == "QUEUED"]
        if not queued:
            return None
        tenants = sorted({job["tenant_id"] for job in queued}, key=lambda tenant: (self.state.tenant_dispatch_count.get(tenant, 0), tenant))
        for tenant in tenants:
            candidates = [job for job in queued if job["tenant_id"] == tenant]
            candidates.sort(key=lambda job: (-job["priority"], job["submitted_at"], job["job_id"]))
            for job in candidates:
                workers = [worker for worker in self.state.workers.values() if worker["status"] == "ACTIVE" and job["capability"] in worker["capabilities"]]
                workers.sort(key=lambda worker: (job["workstream_id"] not in worker.get("affinity", []), worker["worker_id"]))
                if not workers:
                    continue
                worker = workers[0]
                payload = {
                    "job_id": job["job_id"],
                    "worker_id": worker["worker_id"],
                    "worker_epoch": worker["epoch"],
                    "tenant_id": tenant,
                    "dispatched_at": utc_now(),
                }
                self._append("JOB_DISPATCHED", payload)
                return self.state.jobs[job["job_id"]]
        return None

    def complete_job(self, job_id: str, worker_id: str, epoch: int, *, result: dict[str, Any]) -> dict[str, Any]:
        self._require_worker(worker_id, epoch)
        job = self.state.jobs[job_id]
        if job["status"] == "COMPLETED":
            return job
        if job["assigned_worker"] != worker_id or int(job["assigned_epoch"]) != epoch:
            raise RuntimeError("FENCED_WORKER")
        payload = {"job_id": job_id, "worker_id": worker_id, "worker_epoch": epoch, "result": result, "completed_at": utc_now()}
        self._append("JOB_COMPLETED", payload)
        return self.state.jobs[job_id]

    def verify_chain(self) -> bool:
        previous = "GENESIS"
        for event in self._events():
            if event["previous_hash"] != previous:
                return False
            payload = {key: value for key, value in event.items() if key != "event_hash"}
            if digest(payload) != event["event_hash"]:
                return False
            previous = event["event_hash"]
        return True

    def _require_worker(self, worker_id: str, epoch: int) -> dict[str, Any]:
        worker = self.state.workers.get(worker_id)
        if not worker or worker["status"] != "ACTIVE" or int(worker["epoch"]) != int(epoch):
            raise RuntimeError("FENCED_WORKER")
        return worker

    def _require_leader(self, worker_id: str, epoch: int, *, now_epoch: float | None = None) -> None:
        now_epoch = time.time() if now_epoch is None else now_epoch
        leader = self.state.leader
        if not leader or leader["worker_id"] != worker_id or int(leader["epoch"]) != int(epoch) or float(leader["lease_expires_epoch"]) <= now_epoch:
            raise RuntimeError("NOT_ACTIVE_LEADER")

    def _append(self, event_type: str, payload: dict[str, Any]) -> None:
        events = self._events()
        event = {
            "event_id": f"coord-{len(events)+1:08d}",
            "event_type": event_type,
            "payload": payload,
            "recorded_at": utc_now(),
            "previous_hash": events[-1]["event_hash"] if events else "GENESIS",
        }
        event["event_hash"] = digest(event)
        with self.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._apply(event)
        self._persist()

    def _events(self) -> list[dict[str, Any]]:
        if not self.events_file.exists():
            return []
        return [json.loads(line) for line in self.events_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _replay(self) -> None:
        self.state = CoordinationState()
        for event in self._events():
            self._apply(event)
        self._persist()

    def _apply(self, event: dict[str, Any]) -> None:
        kind, payload = event["event_type"], event["payload"]
        if kind == "WORKER_REGISTERED":
            self.state.workers[payload["worker_id"]] = payload
        elif kind == "WORKER_HEARTBEAT":
            self.state.workers[payload["worker_id"]]["heartbeat_at"] = payload["heartbeat_at"]
        elif kind == "JOB_SUBMITTED":
            self.state.jobs[payload["job_id"]] = payload
        elif kind == "LEADER_ELECTED":
            self.state.leader = payload
        elif kind == "LOCK_ACQUIRED":
            self.state.locks[payload["resource_id"]] = payload
        elif kind == "JOB_DISPATCHED":
            job = self.state.jobs[payload["job_id"]]
            job["status"] = "RUNNING"
            job["assigned_worker"] = payload["worker_id"]
            job["assigned_epoch"] = payload["worker_epoch"]
            self.state.tenant_dispatch_count[payload["tenant_id"]] = self.state.tenant_dispatch_count.get(payload["tenant_id"], 0) + 1
        elif kind == "JOB_COMPLETED":
            job = self.state.jobs[payload["job_id"]]
            job["status"] = "COMPLETED"
            job["result"] = payload["result"]
            job["completed_at"] = payload["completed_at"]

    def _persist(self) -> None:
        temp = self.state_file.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(self.state), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, self.state_file)
