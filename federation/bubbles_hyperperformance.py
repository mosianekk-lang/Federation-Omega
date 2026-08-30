from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence


class ContextPressureError(RuntimeError):
    """Raised when a workload exceeds the bounded interactive-context envelope."""


@dataclass(frozen=True)
class ContextPressureBudget:
    max_active_sources: int = 8
    max_heavy_sources: int = 3
    max_tool_results: int = 20
    max_tool_payload_chars: int = 120_000
    max_capsule_chars: int = 24_000


@dataclass(frozen=True)
class ContextPressureObservation:
    active_sources: int
    heavy_sources: int
    tool_results: int
    tool_payload_chars: int
    estimated_capsule_chars: int


@dataclass(frozen=True)
class ContextPressureDecision:
    admitted: bool
    action: str
    reasons: tuple[str, ...] = ()


class ContextPressureGovernor:
    """Fail-small admission controller for interactive Bubbles workloads.

    The governor does not discard canonical state. It decides whether the active
    chat should continue hydrating material or checkpoint/compact first.
    """

    def __init__(self, budget: ContextPressureBudget | None = None) -> None:
        self.budget = budget or ContextPressureBudget()

    def evaluate(self, obs: ContextPressureObservation) -> ContextPressureDecision:
        reasons: list[str] = []
        if obs.active_sources > self.budget.max_active_sources:
            reasons.append("ACTIVE_SOURCE_BUDGET")
        if obs.heavy_sources > self.budget.max_heavy_sources:
            reasons.append("HEAVY_SOURCE_BUDGET")
        if obs.tool_results > self.budget.max_tool_results:
            reasons.append("TOOL_RESULT_BUDGET")
        if obs.tool_payload_chars > self.budget.max_tool_payload_chars:
            reasons.append("TOOL_PAYLOAD_BUDGET")
        if obs.estimated_capsule_chars > self.budget.max_capsule_chars:
            reasons.append("CAPSULE_SIZE_BUDGET")
        if reasons:
            return ContextPressureDecision(False, "CHECKPOINT_COMPACT_REROUTE", tuple(reasons))
        return ContextPressureDecision(True, "CONTINUE", ())

    def require_admission(self, obs: ContextPressureObservation) -> None:
        decision = self.evaluate(obs)
        if not decision.admitted:
            raise ContextPressureError(";".join(decision.reasons))


_REQUIRED_CAPSULE_FIELDS = (
    "mission_id",
    "objective",
    "verified_state",
    "source_frontier",
    "authorities",
    "active_capabilities",
    "artifacts",
    "blockers",
    "next_action",
    "proof_refs",
    "freshness",
)


@dataclass(frozen=True)
class MissionCapsule:
    mission_id: str
    objective: str
    verified_state: str
    source_frontier: str
    authorities: tuple[str, ...] = ()
    active_capabilities: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    next_action: str = ""
    proof_refs: tuple[str, ...] = ()
    freshness: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def as_mapping(self) -> dict[str, object]:
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "verified_state": self.verified_state,
            "source_frontier": self.source_frontier,
            "authorities": list(self.authorities),
            "active_capabilities": list(self.active_capabilities),
            "artifacts": list(self.artifacts),
            "blockers": list(self.blockers),
            "next_action": self.next_action,
            "proof_refs": list(self.proof_refs),
            "freshness": self.freshness,
            "metadata": dict(self.metadata),
        }


class MissionCapsuleCompiler:
    """Compile a bounded working projection from canonical mission state."""

    def __init__(self, max_items_per_list: int = 12, max_text_chars: int = 4_000) -> None:
        self.max_items_per_list = max_items_per_list
        self.max_text_chars = max_text_chars

    def _text(self, value: object) -> str:
        return str(value or "")[: self.max_text_chars]

    def _items(self, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            values: Iterable[object] = (value,)
        else:
            values = value if isinstance(value, Iterable) else (value,)
        return tuple(self._text(item) for item in list(values)[: self.max_items_per_list])

    def compile(self, state: Mapping[str, object]) -> MissionCapsule:
        missing = [name for name in _REQUIRED_CAPSULE_FIELDS if name not in state]
        if missing:
            raise ValueError(f"MISSION_CAPSULE_MISSING_FIELDS:{','.join(missing)}")
        return MissionCapsule(
            mission_id=self._text(state["mission_id"]),
            objective=self._text(state["objective"]),
            verified_state=self._text(state["verified_state"]),
            source_frontier=self._text(state["source_frontier"]),
            authorities=self._items(state["authorities"]),
            active_capabilities=self._items(state["active_capabilities"]),
            artifacts=self._items(state["artifacts"]),
            blockers=self._items(state["blockers"]),
            next_action=self._text(state["next_action"]),
            proof_refs=self._items(state["proof_refs"]),
            freshness=self._text(state["freshness"]),
            metadata={str(k): self._text(v) for k, v in dict(state.get("metadata") or {}).items()},
        )


def bounded_slice(items: Sequence[str], limit: int) -> tuple[str, ...]:
    if limit < 0:
        raise ValueError("limit must be non-negative")
    return tuple(items[:limit])


def _aware_datetime(value: str, *, label: str) -> datetime:
    normalized = str(value).strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label}_ISO8601_REQUIRED") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label}_TIMEZONE_REQUIRED")
    return parsed


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


class CurrentStateLeaseError(ValueError):
    """Raised when a current-state projection is stale or insufficiently proved."""


@dataclass(frozen=True)
class CurrentStateLease:
    entity_id: str
    field_id: str
    value: object
    authority_source: str
    observed_at: str
    fresh_until: str
    proof_refs: tuple[str, ...]
    source_event_id: str

    def validate(self) -> None:
        if not self.entity_id or not self.field_id or not self.authority_source:
            raise CurrentStateLeaseError("CURRENT_STATE_LEASE_IDENTITY_REQUIRED")
        if not self.source_event_id:
            raise CurrentStateLeaseError("CURRENT_STATE_LEASE_SOURCE_EVENT_REQUIRED")
        if not self.proof_refs:
            raise CurrentStateLeaseError("CURRENT_STATE_LEASE_PROOF_REQUIRED")
        observed = _aware_datetime(self.observed_at, label="CURRENT_STATE_OBSERVED_AT")
        expiry = _aware_datetime(self.fresh_until, label="CURRENT_STATE_FRESH_UNTIL")
        if expiry <= observed:
            raise CurrentStateLeaseError("CURRENT_STATE_LEASE_WINDOW_INVALID")

    def is_fresh(self, *, now: str) -> bool:
        self.validate()
        current = _aware_datetime(now, label="CURRENT_STATE_NOW")
        observed = _aware_datetime(self.observed_at, label="CURRENT_STATE_OBSERVED_AT")
        expiry = _aware_datetime(self.fresh_until, label="CURRENT_STATE_FRESH_UNTIL")
        return observed <= current < expiry

    def require_fresh(self, *, now: str, expected_authority: str | None = None) -> None:
        self.validate()
        if expected_authority is not None and self.authority_source != expected_authority:
            raise CurrentStateLeaseError("CURRENT_STATE_AUTHORITY_MISMATCH")
        if not self.is_fresh(now=now):
            raise CurrentStateLeaseError("CURRENT_STATE_LEASE_EXPIRED_OR_NOT_YET_VALID")


@dataclass(frozen=True)
class TraceEvent:
    trace_id: str
    span_id: str
    mission_id: str
    stage: str
    state: str
    occurred_at: str
    parent_span_id: str = ""
    route: str = ""
    provider: str = ""
    proof_refs: tuple[str, ...] = ()
    sensitive_payload_present: bool = False


@dataclass(frozen=True)
class TraceAppendReceipt:
    state: str
    trace_id: str
    span_id: str
    event_count: int
    trace_digest: str


class TraceSpine:
    """Append-only privacy-safe mission trace metadata.

    It records correlation metadata and proof pointers only. It is not a payload,
    secret, provider-authority or evidence-content store.
    """

    def __init__(self) -> None:
        self._events: dict[str, TraceEvent] = {}
        self._order: list[str] = []
        self._trace_id = ""
        self._mission_id = ""

    def _digest(self) -> str:
        payload = [asdict(self._events[span_id]) for span_id in self._order]
        return sha256(_stable_json(payload).encode("utf-8")).hexdigest()

    def append(self, event: TraceEvent) -> TraceAppendReceipt:
        if not event.trace_id or not event.span_id or not event.mission_id or not event.stage:
            raise ValueError("TRACE_IDENTITY_REQUIRED")
        _aware_datetime(event.occurred_at, label="TRACE_OCCURRED_AT")
        if event.sensitive_payload_present:
            raise ValueError("TRACE_SENSITIVE_PAYLOAD_PROHIBITED")
        existing = self._events.get(event.span_id)
        if existing is not None:
            if existing != event:
                raise ValueError("TRACE_SPAN_CONFLICT")
            return TraceAppendReceipt(
                "IDEMPOTENT_REPLAY",
                event.trace_id,
                event.span_id,
                len(self._order),
                self._digest(),
            )
        if self._trace_id and event.trace_id != self._trace_id:
            raise ValueError("TRACE_ID_MISMATCH")
        if self._mission_id and event.mission_id != self._mission_id:
            raise ValueError("TRACE_MISSION_MISMATCH")
        if event.parent_span_id:
            parent = self._events.get(event.parent_span_id)
            if parent is None:
                raise ValueError("TRACE_PARENT_MISSING")
            if parent.trace_id != event.trace_id or parent.mission_id != event.mission_id:
                raise ValueError("TRACE_PARENT_LINEAGE_MISMATCH")
        if not self._trace_id:
            self._trace_id = event.trace_id
            self._mission_id = event.mission_id
        self._events[event.span_id] = event
        self._order.append(event.span_id)
        return TraceAppendReceipt(
            "APPENDED",
            event.trace_id,
            event.span_id,
            len(self._order),
            self._digest(),
        )

    def snapshot(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events[span_id] for span_id in self._order)


@dataclass(frozen=True)
class IdempotencyEnvelope:
    operation_id: str
    command_sha256: str
    target_alias: str
    action_scope: str
    effect_class: str
    expires_at: str
    replay_policy: str = "REPLAY_SAME_RESULT"

    def validate(self, *, now: str) -> None:
        if not self.operation_id or not self.target_alias or not self.action_scope or not self.effect_class:
            raise ValueError("IDEMPOTENCY_IDENTITY_REQUIRED")
        if len(self.command_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in self.command_sha256.lower()):
            raise ValueError("IDEMPOTENCY_COMMAND_SHA256_REQUIRED")
        if self.replay_policy != "REPLAY_SAME_RESULT":
            raise ValueError("IDEMPOTENCY_REPLAY_POLICY_UNSUPPORTED")
        current = _aware_datetime(now, label="IDEMPOTENCY_NOW")
        expiry = _aware_datetime(self.expires_at, label="IDEMPOTENCY_EXPIRES_AT")
        if current >= expiry:
            raise ValueError("IDEMPOTENCY_ENVELOPE_EXPIRED")

    def fingerprint(self) -> str:
        payload = {
            "operation_id": self.operation_id,
            "command_sha256": self.command_sha256,
            "target_alias": self.target_alias,
            "action_scope": self.action_scope,
            "effect_class": self.effect_class,
            "replay_policy": self.replay_policy,
        }
        return sha256(_stable_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IdempotencyDecision:
    state: str
    execute: bool
    operation_id: str
    fingerprint: str
    result_ref: str = ""
    reason: str = ""


class IdempotencyLedger:
    """Provider-neutral replay guard over the existing Bubbles command hash.

    The ledger does not grant write authority. Existing route proofs, the one-use
    execution lease and provider-native semantic readback remain mandatory.
    """

    def __init__(self) -> None:
        self._fingerprints: dict[str, str] = {}
        self._results: dict[str, str] = {}

    def admit(self, envelope: IdempotencyEnvelope, *, now: str) -> IdempotencyDecision:
        envelope.validate(now=now)
        fingerprint = envelope.fingerprint()
        known = self._fingerprints.get(envelope.operation_id)
        if known is None:
            self._fingerprints[envelope.operation_id] = fingerprint
            return IdempotencyDecision(
                "ACCEPT_FIRST",
                True,
                envelope.operation_id,
                fingerprint,
                reason="First exact operation envelope admitted; execution authority remains external.",
            )
        if known != fingerprint:
            return IdempotencyDecision(
                "REJECT_CONFLICT",
                False,
                envelope.operation_id,
                fingerprint,
                reason="Operation ID was reused with a different command, target, scope or effect.",
            )
        result_ref = self._results.get(envelope.operation_id, "")
        if result_ref:
            return IdempotencyDecision(
                "REPLAY_SAME_RESULT",
                False,
                envelope.operation_id,
                fingerprint,
                result_ref=result_ref,
                reason="Exact duplicate reuses the durable result reference; no duplicate effect is authorized.",
            )
        return IdempotencyDecision(
            "HOLD_DUPLICATE_IN_FLIGHT",
            False,
            envelope.operation_id,
            fingerprint,
            reason="Exact duplicate arrived before a durable result was recorded.",
        )

    def record_result(self, operation_id: str, result_ref: str) -> None:
        if operation_id not in self._fingerprints:
            raise ValueError("IDEMPOTENCY_OPERATION_NOT_ADMITTED")
        if not result_ref:
            raise ValueError("IDEMPOTENCY_RESULT_REF_REQUIRED")
        existing = self._results.get(operation_id)
        if existing is not None and existing != result_ref:
            raise ValueError("IDEMPOTENCY_RESULT_CONFLICT")
        self._results[operation_id] = result_ref
