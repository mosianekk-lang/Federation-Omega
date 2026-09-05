from __future__ import annotations

"""ChatGov frontier execution-efficiency extensions v1.

This module is deliberately subordinate to the existing ChatGov/FUSE control plane.
It adds four reusable performance mechanisms without creating authority or a new
orchestrator:

* single-flight coalescing for duplicate concurrent pure/read-only work;
* execution-graph/message-graph separation through bounded context routing;
* ANY/QUORUM join planning with redundant-straggler cancellation hints;
* checkpoint-bound interrupt/resume contracts for exact continuation.

No class in this module executes provider effects or mints authorization.
"""

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from threading import Condition, RLock
from time import monotonic
from typing import Any, Callable, Mapping, Sequence


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


@dataclass
class _Flight:
    condition: Condition
    running: bool = True
    result: Any = None
    error: BaseException | None = None
    completed_at: float | None = None


class SingleFlightReadCoordinator:
    """Coalesce concurrent identical pure/read-only operations.

    The first caller executes ``fn``. Concurrent callers with the same key wait for
    the same result instead of duplicating connector/model work. Optional TTL keeps
    a just-completed result reusable for a short bounded window.
    """

    def __init__(self, *, reuse_ttl_seconds: float = 0.0) -> None:
        if reuse_ttl_seconds < 0:
            raise ValueError("SINGLEFLIGHT_TTL_NEGATIVE")
        self.reuse_ttl_seconds = float(reuse_ttl_seconds)
        self._lock = RLock()
        self._flights: dict[str, _Flight] = {}
        self.executions = 0
        self.coalesced_waiters = 0
        self.reuse_hits = 0

    def run(self, key: str, fn: Callable[[], Any], *, effect_class: str = "READ_ONLY") -> Any:
        key = str(key).strip()
        if not key:
            raise ValueError("SINGLEFLIGHT_KEY_REQUIRED")
        if effect_class not in {"READ_ONLY", "NO_EFFECT"}:
            raise ValueError("SINGLEFLIGHT_EFFECTFUL_OPERATION_FORBIDDEN")

        with self._lock:
            existing = self._flights.get(key)
            now = monotonic()
            if existing and not existing.running and existing.error is None and existing.completed_at is not None:
                if now - existing.completed_at <= self.reuse_ttl_seconds:
                    self.reuse_hits += 1
                    return existing.result
                self._flights.pop(key, None)
                existing = None

            if existing and existing.running:
                self.coalesced_waiters += 1
                while existing.running:
                    existing.condition.wait()
                if existing.error is not None:
                    raise existing.error
                return existing.result

            flight = _Flight(condition=Condition(self._lock))
            self._flights[key] = flight
            self.executions += 1

        try:
            result = fn()
        except BaseException as exc:
            with self._lock:
                flight.error = exc
                flight.running = False
                flight.completed_at = monotonic()
                flight.condition.notify_all()
            raise

        with self._lock:
            flight.result = result
            flight.running = False
            flight.completed_at = monotonic()
            flight.condition.notify_all()
        return result


@dataclass(frozen=True, slots=True)
class ContextMessage:
    message_id: str
    source: str
    content: str
    priority: int = 0
    mandatory: bool = False
    proof_ref: str = ""

    @property
    def chars(self) -> int:
        return len(self.content)


@dataclass(frozen=True, slots=True)
class ContextRoute:
    selected: tuple[ContextMessage, ...]
    omitted_ids: tuple[str, ...]
    total_chars: int
    route_sha256: str


class ContextMessageRouter:
    """Separate execution routing from message/context routing.

    Callers provide the sources a specialist is allowed to see. Mandatory messages
    are admitted first; optional messages are ranked by priority and then message ID.
    The router fails closed if mandatory context alone exceeds the hard budget.
    """

    def route(
        self,
        messages: Sequence[ContextMessage],
        *,
        allowed_sources: Sequence[str],
        max_chars: int,
    ) -> ContextRoute:
        if max_chars < 1:
            raise ValueError("CONTEXT_BUDGET_INVALID")
        allowed = {str(x).strip() for x in allowed_sources if str(x).strip()}
        if not allowed:
            raise ValueError("CONTEXT_ALLOWED_SOURCES_REQUIRED")

        eligible = [m for m in messages if m.source in allowed]
        mandatory = sorted((m for m in eligible if m.mandatory), key=lambda m: m.message_id)
        optional = sorted((m for m in eligible if not m.mandatory), key=lambda m: (-m.priority, m.message_id))
        required_chars = sum(m.chars for m in mandatory)
        if required_chars > max_chars:
            raise ValueError("MANDATORY_CONTEXT_EXCEEDS_BUDGET")

        selected = list(mandatory)
        used = required_chars
        for item in optional:
            if used + item.chars <= max_chars:
                selected.append(item)
                used += item.chars

        selected_ids = {m.message_id for m in selected}
        omitted = tuple(sorted(m.message_id for m in messages if m.message_id not in selected_ids))
        material = {
            "selected": [asdict(m) for m in selected],
            "omitted_ids": omitted,
            "total_chars": used,
            "allowed_sources": sorted(allowed),
            "max_chars": max_chars,
        }
        return ContextRoute(tuple(selected), omitted, used, _digest(material))


@dataclass(frozen=True, slots=True)
class JoinDecision:
    ready: bool
    mode: str
    successful: tuple[str, ...]
    pending: tuple[str, ...]
    cancel_candidates: tuple[str, ...]
    reason: str


class CriticalPathJoinPlanner:
    """Plan ALL/ANY/QUORUM joins without owning worker execution.

    Once an ANY or QUORUM condition is satisfied, still-running redundant workers
    are returned as cancellation candidates. The host decides whether cancellation
    is safe; this class never cancels work itself.
    """

    def decide(
        self,
        *,
        workers: Sequence[str],
        completed: Mapping[str, bool],
        mode: str = "ALL",
        quorum: int | None = None,
        cancel_redundant: bool = True,
    ) -> JoinDecision:
        ordered = tuple(dict.fromkeys(str(w).strip() for w in workers if str(w).strip()))
        if not ordered:
            raise ValueError("JOIN_WORKERS_REQUIRED")
        if any(k not in ordered for k in completed):
            raise ValueError("JOIN_UNKNOWN_WORKER")
        mode = mode.upper().strip()
        if mode not in {"ALL", "ANY", "QUORUM"}:
            raise ValueError("JOIN_MODE_INVALID")

        successful = tuple(w for w in ordered if completed.get(w) is True)
        pending = tuple(w for w in ordered if w not in completed)

        if mode == "ALL":
            ready = len(completed) == len(ordered) and len(successful) == len(ordered)
            reason = "ALL_SUCCEEDED" if ready else "WAIT_ALL"
        elif mode == "ANY":
            ready = bool(successful)
            reason = "ANY_SUCCEEDED" if ready else "WAIT_ANY"
        else:
            q = quorum if quorum is not None else (len(ordered) // 2 + 1)
            if q < 1 or q > len(ordered):
                raise ValueError("JOIN_QUORUM_INVALID")
            ready = len(successful) >= q
            reason = "QUORUM_REACHED" if ready else "WAIT_QUORUM"

        cancel = pending if ready and cancel_redundant and mode in {"ANY", "QUORUM"} else ()
        return JoinDecision(ready, mode, successful, pending, cancel, reason)


@dataclass(frozen=True, slots=True)
class InterruptRecord:
    interrupt_id: str
    mission_id: str
    checkpoint_ref: str
    checkpoint_sha256: str
    payload: Mapping[str, Any]
    resumed: bool = False


@dataclass(frozen=True, slots=True)
class ResumeReceipt:
    interrupt_id: str
    mission_id: str
    checkpoint_sha256: str
    resume_value_sha256: str
    receipt_sha256: str


class CheckpointInterruptLedger:
    """Serializable, exact-checkpoint pause/resume contract.

    The ledger itself is in-memory; durable storage is explicitly delegated to the
    existing FDOF/SOL/ChatBridge persistence layer through ``dump``/``load``.
    """

    def __init__(self) -> None:
        self._records: dict[str, InterruptRecord] = {}

    def pause(
        self,
        *,
        mission_id: str,
        checkpoint_ref: str,
        checkpoint_sha256: str,
        payload: Mapping[str, Any],
    ) -> InterruptRecord:
        if not all(str(x).strip() for x in (mission_id, checkpoint_ref, checkpoint_sha256)):
            raise ValueError("INTERRUPT_IDENTITY_REQUIRED")
        material = {
            "mission_id": mission_id,
            "checkpoint_ref": checkpoint_ref,
            "checkpoint_sha256": checkpoint_sha256,
            "payload": dict(payload),
        }
        interrupt_id = "int_" + _digest(material)[:24]
        record = InterruptRecord(interrupt_id, mission_id, checkpoint_ref, checkpoint_sha256, dict(payload), False)
        prior = self._records.get(interrupt_id)
        if prior is not None and prior != record:
            raise ValueError("INTERRUPT_COLLISION")
        self._records[interrupt_id] = record
        return record

    def resume(
        self,
        *,
        interrupt_id: str,
        mission_id: str,
        checkpoint_sha256: str,
        resume_value: Any,
    ) -> ResumeReceipt:
        record = self._records.get(interrupt_id)
        if record is None:
            raise ValueError("INTERRUPT_UNKNOWN")
        if record.resumed:
            raise ValueError("INTERRUPT_ALREADY_RESUMED")
        if record.mission_id != mission_id or record.checkpoint_sha256 != checkpoint_sha256:
            raise ValueError("INTERRUPT_CHECKPOINT_MISMATCH")
        resumed = InterruptRecord(
            record.interrupt_id,
            record.mission_id,
            record.checkpoint_ref,
            record.checkpoint_sha256,
            record.payload,
            True,
        )
        self._records[interrupt_id] = resumed
        value_hash = _digest(resume_value)
        material = {
            "interrupt_id": interrupt_id,
            "mission_id": mission_id,
            "checkpoint_sha256": checkpoint_sha256,
            "resume_value_sha256": value_hash,
        }
        return ResumeReceipt(interrupt_id, mission_id, checkpoint_sha256, value_hash, _digest(material))

    def dump(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(asdict(self._records[k]) for k in sorted(self._records))

    @classmethod
    def load(cls, rows: Sequence[Mapping[str, Any]]) -> "CheckpointInterruptLedger":
        ledger = cls()
        for row in rows:
            record = InterruptRecord(
                interrupt_id=str(row["interrupt_id"]),
                mission_id=str(row["mission_id"]),
                checkpoint_ref=str(row["checkpoint_ref"]),
                checkpoint_sha256=str(row["checkpoint_sha256"]),
                payload=dict(row.get("payload", {})),
                resumed=bool(row.get("resumed", False)),
            )
            ledger._records[record.interrupt_id] = record
        return ledger


__all__ = [
    "CheckpointInterruptLedger",
    "ContextMessage",
    "ContextMessageRouter",
    "ContextRoute",
    "CriticalPathJoinPlanner",
    "InterruptRecord",
    "JoinDecision",
    "ResumeReceipt",
    "SingleFlightReadCoordinator",
]
