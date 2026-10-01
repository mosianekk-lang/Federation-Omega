from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Callable, Iterable, Mapping

SCHEMA = "FUSE-DURABLE-SCHEDULER-BUS-V1"
VERSION = "1.0.0"

class ScheduleKind(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    ONCE = "ONCE"
    INTERVAL = "INTERVAL"
    CONDITION_WATCH = "CONDITION_WATCH"

class MissionState(str, Enum):
    PENDING = "PENDING"
    LEASED = "LEASED"
    WAITING_CONDITION = "WAITING_CONDITION"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"
    HELD = "HELD"

@dataclass(frozen=True, slots=True)
class DurableMission:
    mission_id: str
    idempotency_key: str
    task_type: str
    objective: str
    schedule_kind: ScheduleKind = ScheduleKind.IMMEDIATE
    not_before: str = ""
    interval_seconds: int = 0
    authority_class: str = "A0_INTERNAL"
    effect_class: str = "NO_EFFECT"
    required_capabilities: tuple[str, ...] = ()
    payload: Mapping[str, object] = field(default_factory=dict)
    max_attempts: int = 3
    source_epoch: str = ""

    def validate(self) -> "DurableMission":
        if not self.mission_id.strip() or not self.idempotency_key.strip() or not self.task_type.strip() or not self.objective.strip():
            raise ValueError("DURABLE_MISSION_IDENTITY_INCOMPLETE")
        if self.max_attempts < 1:
            raise ValueError("DURABLE_MISSION_MAX_ATTEMPTS_INVALID")
        if self.schedule_kind in {ScheduleKind.ONCE, ScheduleKind.INTERVAL} and not self.not_before.strip():
            raise ValueError("DURABLE_MISSION_NOT_BEFORE_REQUIRED")
        if self.schedule_kind is ScheduleKind.INTERVAL and self.interval_seconds < 3600:
            raise ValueError("DURABLE_MISSION_INTERVAL_MINIMUM_ONE_HOUR")
        return self

    @property
    def digest(self) -> str:
        return "sha256:" + sha256(
            json.dumps(asdict(self), sort_keys=True, default=str, separators=(",", ":")).encode()
        ).hexdigest()

@dataclass(frozen=True, slots=True)
class MissionLease:
    mission_id: str
    worker_id: str
    generation: int
    lease_until: str
    mission_digest: str

@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    mission_id: str
    state: MissionState
    route_family: str
    worker_id: str
    attempt: int
    result: Mapping[str, object] = field(default_factory=dict)
    failure_fingerprint: str = ""
    next_route_required: bool = False
    readback_ref: str = ""

    @property
    def digest(self) -> str:
        return "sha256:" + sha256(
            json.dumps(asdict(self), sort_keys=True, default=str, separators=(",", ":")).encode()
        ).hexdigest()

def parse_time(value: str) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("DURABLE_MISSION_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)

def due(mission: DurableMission, *, now: datetime) -> bool:
    mission.validate()
    now = now.astimezone(timezone.utc)
    if mission.schedule_kind is ScheduleKind.IMMEDIATE:
        return True
    if mission.schedule_kind in {ScheduleKind.ONCE, ScheduleKind.INTERVAL, ScheduleKind.CONDITION_WATCH}:
        return now >= parse_time(mission.not_before) if mission.not_before else True
    return False

class HandlerRegistry:
    def __init__(self):
        self._handlers: dict[str, Callable[[DurableMission], Mapping[str, object]]] = {}

    def register(self, task_type: str, handler: Callable[[DurableMission], Mapping[str, object]]) -> None:
        self._handlers[task_type] = handler

    def has(self, task_type: str) -> bool:
        return task_type in self._handlers

    def run(self, mission: DurableMission) -> Mapping[str, object]:
        if mission.task_type not in self._handlers:
            raise KeyError(f"NO_DURABLE_HANDLER:{mission.task_type}")
        return self._handlers[mission.task_type](mission)

def default_handlers() -> HandlerRegistry:
    registry = HandlerRegistry()
    registry.register("NO_EFFECT_CANARY", lambda mission: {
        "status": "PASS",
        "mission_digest": mission.digest,
        "objective_sha256": sha256(mission.objective.encode()).hexdigest(),
        "effects": "NONE",
    })
    registry.register("DURABLE_QUEUE_HEARTBEAT", lambda mission: {
        "status": "ALIVE",
        "mission_digest": mission.digest,
        "effects": "NONE",
    })
    return registry

def next_route_family(prior_family: str, recurrence: int, candidates: Iterable[str]) -> str:
    items = tuple(candidates)
    if not items:
        return "DURABLE_QUEUE"
    if recurrence >= 2 and prior_family:
        changed = [item for item in items if item != prior_family]
        if changed:
            return changed[0]
    return items[0]

__all__ = [
    "DurableMission", "ExecutionReceipt", "HandlerRegistry", "MissionLease",
    "MissionState", "ScheduleKind", "SCHEMA", "VERSION", "default_handlers",
    "due", "next_route_family",
]
