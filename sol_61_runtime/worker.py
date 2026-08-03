from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from runtime import atomic_json, digest, utc_now


@dataclass(frozen=True)
class Job:
    job_id: str
    mission_id: str
    workstream_id: str
    action_class: str
    payload: dict[str, Any]
    idempotency_key: str
    max_attempts: int = 3
    priority: int = 50
    checkpoint_id: str | None = None


@dataclass
class WorkerState:
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    workers: dict[str, dict[str, Any]] = field(default_factory=dict)
    dead_letters: dict[str, dict[str, Any]] = field(default_factory=dict)
    idempotency: dict[str, str] = field(default_factory=dict)


class DurableWorkerPlane:
    """Provider-neutral durable worker plane for SOL 6.1.

    Supports queue leasing, heartbeats, idempotency, expired-lease recovery,
    bounded retries, dead-letter routing, and checkpoint-aware continuation.
    External providers still need an authorised worker process to call this API.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_file = self.root / "worker-events.jsonl"
        self.state_file = self.root / "worker-state.json"
        self.state = WorkerState()
        self._replay()

    @staticmethod
    def _parse(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _events(self) -> list[dict[str, Any]]:
        if not self.events_file.exists():
            return []
        return [json.loads(line) for line in self.events_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._events()
        event = {
            "event_id": f"wevt-{len(rows)+1:08d}",
            "event_type": event_type,
            "payload": payload,
            "recorded_at": utc_now(),
            "previous_hash": rows[-1]["event_hash"] if rows else "GENESIS",
        }
        event["event_hash"] = digest(event)
        with self.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._apply(event)
        atomic_json(self.state_file, asdict(self.state))
        return event

    def enqueue(self, job: Job) -> dict[str, Any]:
        if job.job_id in self.state.jobs:
            return self.state.jobs[job.job_id]
        if job.idempotency_key in self.state.idempotency:
            existing = self.state.idempotency[job.idempotency_key]
            return self.state.jobs[existing]
        row = asdict(job) | {
            "status": "QUEUED",
            "attempts": 0,
            "leased_by": None,
            "lease_expires_at": None,
            "next_eligible_at": utc_now(),
            "created_at": utc_now(),
            "last_error": None,
        }
        self._append("JOB_ENQUEUED", row)
        return row

    def heartbeat(self, worker_id: str, capabilities: tuple[str, ...]) -> dict[str, Any]:
        body = {
            "worker_id": worker_id,
            "capabilities": sorted(set(capabilities)),
            "observed_at": utc_now(),
            "status": "HEALTHY",
        }
        self._append("WORKER_HEARTBEAT", body)
        return body

    def lease(self, worker_id: str, capability: str, lease_seconds: int = 60) -> dict[str, Any] | None:
        self.recover_expired_leases()
        now = datetime.now(timezone.utc)
        eligible = [
            row for row in self.state.jobs.values()
            if row["status"] in {"QUEUED", "RETRY_READY"}
            and row["action_class"] == capability
            and self._parse(row["next_eligible_at"]) <= now
        ]
        eligible.sort(key=lambda row: (-int(row["priority"]), row["created_at"], row["job_id"]))
        if not eligible:
            return None
        job = eligible[0]
        lease = {
            "job_id": job["job_id"],
            "worker_id": worker_id,
            "lease_expires_at": (now + timedelta(seconds=lease_seconds)).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "attempt": int(job["attempts"]) + 1,
        }
        self._append("JOB_LEASED", lease)
        return dict(self.state.jobs[job["job_id"]])

    def complete(self, job_id: str, worker_id: str, result: dict[str, Any]) -> dict[str, Any]:
        job = self.state.jobs[job_id]
        if job["status"] == "COMPLETED":
            return self.state.results[job_id]
        if job["leased_by"] != worker_id or job["status"] != "LEASED":
            raise ValueError("worker does not hold active lease")
        receipt = {
            "job_id": job_id,
            "worker_id": worker_id,
            "idempotency_key": job["idempotency_key"],
            "checkpoint_id": job.get("checkpoint_id"),
            "result": result,
            "completed_at": utc_now(),
        }
        receipt["sha256"] = digest(receipt)
        self._append("JOB_COMPLETED", receipt)
        return receipt

    def fail(self, job_id: str, worker_id: str, failure_class: str, message: str, backoff_seconds: int = 30) -> dict[str, Any]:
        job = self.state.jobs[job_id]
        if job["leased_by"] != worker_id or job["status"] != "LEASED":
            raise ValueError("worker does not hold active lease")
        terminal = int(job["attempts"]) >= int(job["max_attempts"])
        payload = {
            "job_id": job_id,
            "worker_id": worker_id,
            "failure_class": failure_class,
            "message": message,
            "terminal": terminal,
            "next_eligible_at": (datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "failed_at": utc_now(),
        }
        self._append("JOB_FAILED", payload)
        return dict(self.state.jobs[job_id])

    def recover_expired_leases(self, as_of: str | None = None) -> list[str]:
        point = self._parse(as_of) if as_of else datetime.now(timezone.utc)
        recovered: list[str] = []
        for row in list(self.state.jobs.values()):
            expiry = row.get("lease_expires_at")
            if row["status"] == "LEASED" and expiry and self._parse(expiry) <= point:
                self._append("LEASE_EXPIRED", {"job_id": row["job_id"], "expired_at": expiry, "recovered_at": utc_now()})
                recovered.append(row["job_id"])
        return recovered

    def stale_workers(self, max_age_seconds: int = 120, as_of: str | None = None) -> list[str]:
        point = self._parse(as_of) if as_of else datetime.now(timezone.utc)
        return sorted(
            worker_id for worker_id, row in self.state.workers.items()
            if (point - self._parse(row["observed_at"])).total_seconds() > max_age_seconds
        )

    def verify_event_chain(self) -> bool:
        previous = "GENESIS"
        for event in self._events():
            if event["previous_hash"] != previous:
                return False
            body = {k: v for k, v in event.items() if k != "event_hash"}
            if digest(body) != event["event_hash"]:
                return False
            previous = event["event_hash"]
        return True

    def _replay(self) -> None:
        self.state = WorkerState()
        for event in self._events():
            self._apply(event)
        atomic_json(self.state_file, asdict(self.state))

    def _apply(self, event: dict[str, Any]) -> None:
        kind, p = event["event_type"], event["payload"]
        if kind == "JOB_ENQUEUED":
            self.state.jobs[p["job_id"]] = p
            self.state.idempotency[p["idempotency_key"]] = p["job_id"]
        elif kind == "WORKER_HEARTBEAT":
            self.state.workers[p["worker_id"]] = p
        elif kind == "JOB_LEASED":
            job = self.state.jobs[p["job_id"]]
            job["status"] = "LEASED"
            job["leased_by"] = p["worker_id"]
            job["lease_expires_at"] = p["lease_expires_at"]
            job["attempts"] = p["attempt"]
        elif kind == "JOB_COMPLETED":
            job = self.state.jobs[p["job_id"]]
            job["status"] = "COMPLETED"
            job["leased_by"] = None
            job["lease_expires_at"] = None
            self.state.results[p["job_id"]] = p
        elif kind == "JOB_FAILED":
            job = self.state.jobs[p["job_id"]]
            job["last_error"] = {"class": p["failure_class"], "message": p["message"], "failed_at": p["failed_at"]}
            job["leased_by"] = None
            job["lease_expires_at"] = None
            if p["terminal"]:
                job["status"] = "DEAD_LETTER"
                self.state.dead_letters[p["job_id"]] = dict(job)
            else:
                job["status"] = "RETRY_READY"
                job["next_eligible_at"] = p["next_eligible_at"]
        elif kind == "LEASE_EXPIRED":
            job = self.state.jobs[p["job_id"]]
            job["status"] = "RETRY_READY" if int(job["attempts"]) < int(job["max_attempts"]) else "DEAD_LETTER"
            job["leased_by"] = None
            job["lease_expires_at"] = None
            job["next_eligible_at"] = utc_now()
            if job["status"] == "DEAD_LETTER":
                self.state.dead_letters[p["job_id"]] = dict(job)
