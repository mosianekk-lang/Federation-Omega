from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from federation.durable_scheduler_bus_v1 import (
    DurableMission,
    ExecutionReceipt,
    MissionState,
    ScheduleKind,
    default_handlers,
    due,
)

SCHEMA = "FUSE-VIRTUAL-ORG-DURABLE-ADAPTER-V1"


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _safe_relative(root: Path, value: str) -> Path:
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("DURABLE_CONDITION_PATH_OUTSIDE_REPOSITORY")
    target = (root / rel).resolve()
    root_resolved = root.resolve()
    if root_resolved != target and root_resolved not in target.parents:
        raise ValueError("DURABLE_CONDITION_PATH_OUTSIDE_REPOSITORY")
    return target


def mission_from_dict(payload: Mapping[str, Any]) -> DurableMission:
    if payload.get("schema") not in {None, "FUSE_DURABLE_MISSION_V1"}:
        raise ValueError("DURABLE_MISSION_SCHEMA_INVALID")
    return DurableMission(
        mission_id=str(payload["mission_id"]),
        idempotency_key=str(payload["idempotency_key"]),
        task_type=str(payload["task_type"]),
        objective=str(payload["objective"]),
        schedule_kind=ScheduleKind(str(payload.get("schedule_kind", "IMMEDIATE"))),
        not_before=str(payload.get("not_before", "")),
        interval_seconds=int(payload.get("interval_seconds", 0)),
        authority_class=str(payload.get("authority_class", "A0_INTERNAL")),
        effect_class=str(payload.get("effect_class", "NO_EFFECT")),
        required_capabilities=tuple(str(x) for x in payload.get("required_capabilities", [])),
        payload=dict(payload.get("payload", {})),
        max_attempts=int(payload.get("max_attempts", 3)),
        source_epoch=str(payload.get("source_epoch", "")),
    ).validate()


def evaluate_condition(mission: DurableMission, repository_root: Path) -> tuple[bool, str]:
    condition = dict(mission.payload.get("condition") or {})
    kind = str(condition.get("kind", "")).upper()
    if not kind:
        return False, "CONDITION_SPEC_MISSING"
    if kind == "ALWAYS_TRUE":
        return True, "ALWAYS_TRUE"
    if kind == "FILE_EXISTS":
        target = _safe_relative(repository_root, str(condition.get("path", "")))
        return target.exists(), f"FILE_EXISTS:{target.relative_to(repository_root.resolve())}"
    if kind == "JSON_FIELD_EQUALS":
        target = _safe_relative(repository_root, str(condition.get("path", "")))
        if not target.exists():
            return False, "CONDITION_SOURCE_MISSING"
        value: Any = json.loads(target.read_text(encoding="utf-8"))
        field = str(condition.get("field", ""))
        for part in field.split("."):
            if not part:
                continue
            if not isinstance(value, dict) or part not in value:
                return False, "CONDITION_FIELD_MISSING"
            value = value[part]
        expected = condition.get("expected")
        return value == expected, "JSON_FIELD_EQUALS"
    raise ValueError(f"DURABLE_CONDITION_KIND_UNSUPPORTED:{kind}")


class VirtualOrgDurableQueue:
    def __init__(
        self,
        repository_root: str | Path,
        *,
        queue_dir: str = "virtual-org/durable-queue",
        runtime_dir: str = "virtual-org/runtime/durable-bus",
        worker_id: str = "FUSE-VIRTUAL-ORG-DURABLE-WORKER-V1",
    ):
        self.root = Path(repository_root).resolve()
        self.queue_dir = self.root / queue_dir
        self.runtime_dir = self.root / runtime_dir
        self.state_dir = self.runtime_dir / "state"
        self.receipt_dir = self.runtime_dir / "receipts"
        self.worker_id = worker_id
        self.handlers = default_handlers()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.receipt_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, mission: DurableMission) -> str:
        return _hash(mission.idempotency_key)[:32]

    def _state_path(self, mission: DurableMission) -> Path:
        return self.state_dir / f"{self._key(mission)}.json"

    def _load_state(self, mission: DurableMission) -> dict[str, Any]:
        path = self._state_path(mission)
        if not path.exists():
            return {
                "schema": "FUSE-DURABLE-MISSION-STATE-V1",
                "mission_id": mission.mission_id,
                "idempotency_key": mission.idempotency_key,
                "mission_digest": mission.digest,
                "generation": 0,
                "attempt": 0,
                "state": MissionState.PENDING.value,
            }
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("idempotency_key") != mission.idempotency_key:
            raise ValueError("DURABLE_STATE_IDEMPOTENCY_IDENTITY_MISMATCH")
        if state.get("mission_digest") != mission.digest:
            raise ValueError("DURABLE_IDEMPOTENCY_PARAMETER_MISMATCH")
        return state

    def _write_state(self, mission: DurableMission, state: dict[str, Any]) -> None:
        self._state_path(mission).write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _receipt_path(self, mission: DurableMission, attempt: int) -> Path:
        return self.receipt_dir / f"{self._key(mission)}-attempt-{attempt:04d}.json"

    def _write_receipt(self, receipt: ExecutionReceipt, mission: DurableMission, *, executed_at: str) -> dict[str, Any]:
        value = {
            "schema": "FUSE-DURABLE-SCHEDULER-RECEIPT-V1",
            "executed_at": executed_at,
            "mission_digest": mission.digest,
            "mission": {
                "mission_id": mission.mission_id,
                "idempotency_key": mission.idempotency_key,
                "task_type": mission.task_type,
                "schedule_kind": mission.schedule_kind.value,
                "authority_class": mission.authority_class,
                "effect_class": mission.effect_class,
                "source_epoch": mission.source_epoch,
            },
            "receipt": {
                **asdict(receipt),
                "state": receipt.state.value,
                "digest": receipt.digest,
            },
        }
        value["receipt_file_sha256"] = _hash(_canonical(value))
        self._receipt_path(mission, receipt.attempt).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return value

    def tick(self, *, now: datetime | None = None) -> dict[str, Any]:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        processed: list[dict[str, Any]] = []
        if not self.queue_dir.exists():
            queue_files: list[Path] = []
        else:
            queue_files = sorted(self.queue_dir.glob("*.json"))

        for source in queue_files:
            try:
                mission = mission_from_dict(json.loads(source.read_text(encoding="utf-8")))
                state = self._load_state(mission)

                if state["state"] == MissionState.SUCCEEDED.value and mission.schedule_kind in {
                    ScheduleKind.IMMEDIATE, ScheduleKind.ONCE, ScheduleKind.CONDITION_WATCH
                }:
                    processed.append({
                        "mission_id": mission.mission_id,
                        "state": "IDEMPOTENT_TERMINAL_REPLAY_SUPPRESSED",
                        "source": str(source.relative_to(self.root)),
                    })
                    continue

                next_run_at = str(state.get("next_run_at", ""))
                if next_run_at and now < datetime.fromisoformat(next_run_at.replace("Z", "+00:00")).astimezone(timezone.utc):
                    processed.append({
                        "mission_id": mission.mission_id,
                        "state": "NOT_DUE",
                        "next_run_at": next_run_at,
                    })
                    continue

                if not due(mission, now=now):
                    processed.append({"mission_id": mission.mission_id, "state": "NOT_DUE"})
                    continue

                if mission.schedule_kind is ScheduleKind.CONDITION_WATCH:
                    met, condition_reason = evaluate_condition(mission, self.root)
                    if not met:
                        state["state"] = MissionState.WAITING_CONDITION.value
                        state["last_condition_readback"] = condition_reason
                        state["updated_at"] = now.isoformat()
                        self._write_state(mission, state)
                        processed.append({
                            "mission_id": mission.mission_id,
                            "state": MissionState.WAITING_CONDITION.value,
                            "condition_readback": condition_reason,
                        })
                        continue

                if mission.effect_class != "NO_EFFECT":
                    state["state"] = MissionState.HELD.value
                    state["hold_reason"] = "EFFECTFUL_MISSION_REQUIRES_QUALIFIED_EXECUTOR_AND_AUTHORITY"
                    state["updated_at"] = now.isoformat()
                    self._write_state(mission, state)
                    processed.append({
                        "mission_id": mission.mission_id,
                        "state": MissionState.HELD.value,
                        "reason": state["hold_reason"],
                    })
                    continue

                if not self.handlers.has(mission.task_type):
                    state["state"] = MissionState.HELD.value
                    state["hold_reason"] = "NO_QUALIFIED_HANDLER"
                    state["updated_at"] = now.isoformat()
                    self._write_state(mission, state)
                    processed.append({
                        "mission_id": mission.mission_id,
                        "state": MissionState.HELD.value,
                        "reason": state["hold_reason"],
                    })
                    continue

                attempt = int(state.get("attempt", 0)) + 1
                generation = int(state.get("generation", 0)) + 1
                lease_until = now + timedelta(minutes=10)
                state.update({
                    "attempt": attempt,
                    "generation": generation,
                    "state": MissionState.LEASED.value,
                    "lease_until": lease_until.isoformat(),
                    "worker_id": self.worker_id,
                    "updated_at": now.isoformat(),
                })
                self._write_state(mission, state)

                try:
                    result = dict(self.handlers.run(mission))
                except Exception as exc:
                    fingerprint = _hash(f"{type(exc).__name__}:{exc}")
                    terminal = attempt >= mission.max_attempts
                    state.update({
                        "state": MissionState.DEAD_LETTER.value if terminal else MissionState.FAILED.value,
                        "failure_fingerprint": fingerprint,
                        "updated_at": now.isoformat(),
                    })
                    self._write_state(mission, state)
                    processed.append({
                        "mission_id": mission.mission_id,
                        "state": state["state"],
                        "failure_fingerprint": fingerprint,
                        "changed_route_required": not terminal,
                    })
                    continue

                receipt_state = MissionState.SUCCEEDED
                receipt = ExecutionReceipt(
                    mission_id=mission.mission_id,
                    state=receipt_state,
                    route_family="FUSE_VIRTUAL_ORG_SCHEDULED_EXECUTOR",
                    worker_id=self.worker_id,
                    attempt=attempt,
                    result=result,
                    readback_ref=f"runtime-state:{self._state_path(mission).relative_to(self.root)}",
                )
                receipt_value = self._write_receipt(receipt, mission, executed_at=now.isoformat())

                state["last_receipt_digest"] = receipt.digest
                state["last_receipt_file_sha256"] = receipt_value["receipt_file_sha256"]
                state["updated_at"] = now.isoformat()
                state["lease_until"] = ""

                if mission.schedule_kind is ScheduleKind.INTERVAL:
                    state["state"] = MissionState.PENDING.value
                    state["next_run_at"] = (now + timedelta(seconds=mission.interval_seconds)).isoformat()
                else:
                    state["state"] = MissionState.SUCCEEDED.value
                    state["next_run_at"] = ""

                self._write_state(mission, state)
                processed.append({
                    "mission_id": mission.mission_id,
                    "state": receipt_state.value,
                    "attempt": attempt,
                    "receipt_digest": receipt.digest,
                    "receipt_file_sha256": receipt_value["receipt_file_sha256"],
                    "source": str(source.relative_to(self.root)),
                })

            except Exception as exc:
                processed.append({
                    "source": str(source.relative_to(self.root)),
                    "state": "REJECTED",
                    "error": f"{type(exc).__name__}:{exc}",
                })

        report = {
            "schema": SCHEMA,
            "generated_at": now.isoformat(),
            "worker_id": self.worker_id,
            "queue_count": len(queue_files),
            "processed_count": len(processed),
            "processed": processed,
            "truth_boundary": (
                "Runtime receipt files prove only the executed no-effect handler and persisted "
                "Virtual Organization state. Effectful missions remain held pending qualified authority."
            ),
        }
        report["report_sha256"] = _hash(_canonical(report))
        report_path = self.runtime_dir / "latest-report.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return report
