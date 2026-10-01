"""FUSE convergence, compaction, and bottleneck-removal primitives.

This module is a bounded extension of the existing vNext mission execution
kernel. It creates no scheduler, truth root, authority root, proof root, or
provider authority. It supplies deterministic coordination primitives for:

* semantic transition fan-in across lease/source/effect/proof/reducer/receivers;
* scoped fencing so independent source domains need not serialize globally;
* negative route memory that suppresses unchanged failed routes;
* causal descendant invalidation instead of broad global invalidation;
* live-graph compaction while preserving immutable historical identities;
* exact fast-path eligibility for simple already-qualified actions; and
* cross-plane invariant auditing.

All functions are provider-neutral and effect-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping


SCHEMA = "FUSE-BOTTLENECK-CONVERGENCE-COMPACTOR-1"


class ConvergenceError(ValueError):
    """Fail-closed convergence contract error."""


class LeaseState(StrEnum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"


class EffectState(StrEnum):
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"
    READBACK_VERIFIED = "READBACK_VERIFIED"
    APPLIED = "APPLIED"


class ProofState(StrEnum):
    PENDING = "PENDING"
    PASS = "PASS"
    FAIL = "FAIL"


class ProjectionState(StrEnum):
    PENDING = "PENDING"
    APPLIED = "APPLIED"
    ACKED = "ACKED"


LIVE_GRAPH_STATES = frozenset(
    {
        "OPEN",
        "ACTIVE",
        "READY",
        "RUNNING",
        "WAITING_AUTOMATICALLY",
        "HOLD",
        "PARTIAL_PROVEN",
        "BLOCKED_EXTERNAL_AUTHORITY",
    }
)
DORMANT_GRAPH_STATES = frozenset({"DORMANT", "WAITING_EVENT", "WAITING_EXACT_CAPABILITY"})
HISTORICAL_GRAPH_STATES = frozenset(
    {
        "RELEASED",
        "COMPLETE_VERIFIED",
        "SUPERSEDED",
        "CANCELLED",
        "ARCHIVED",
        "TERMINAL",
    }
)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _identifier(value: str, label: str) -> str:
    candidate = str(value).strip()
    if not candidate or len(candidate) > 240:
        raise ConvergenceError(f"{label.upper()}_REQUIRED")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*", candidate):
        raise ConvergenceError(f"{label.upper()}_INVALID")
    return candidate


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _normalize_scope(value: str) -> str:
    return _identifier(value, "scope").rstrip("/").casefold()


def scopes_overlap(left: str, right: str) -> bool:
    """Return True only when two canonical resource scopes can touch same state."""
    a = _normalize_scope(left)
    b = _normalize_scope(right)
    if a == b:
        return True
    return a.startswith(b + "/") or b.startswith(a + "/")


@dataclass(frozen=True, slots=True)
class TransitionEnvelope:
    transition_id: str
    mission_id: str
    mission_version: int
    lease_id: str
    fencing_token: int
    scopes: tuple[str, ...]
    source_before: str
    source_after: str = ""
    source_admitted: bool = False
    lease_state: LeaseState = LeaseState.ACTIVE
    effect_state: EffectState = EffectState.NONE
    proof_state: ProofState = ProofState.PENDING
    reducer_state: ProjectionState = ProjectionState.PENDING
    required_receivers: tuple[str, ...] = ()
    receiver_states: Mapping[str, ProjectionState] = field(default_factory=dict)
    transition_sha256: str = ""

    @classmethod
    def create(cls, **kwargs: object) -> "TransitionEnvelope":
        kwargs = dict(kwargs)
        kwargs["scopes"] = _clean(kwargs.get("scopes", ()))
        kwargs["required_receivers"] = _clean(kwargs.get("required_receivers", ()))
        kwargs["receiver_states"] = dict(kwargs.get("receiver_states", {}))
        item = cls(**kwargs)
        item.validate()
        return cls(**{**item._body(), "transition_sha256": _digest(item._body())})

    def _body(self) -> dict[str, object]:
        return {
            "transition_id": self.transition_id,
            "mission_id": self.mission_id,
            "mission_version": self.mission_version,
            "lease_id": self.lease_id,
            "fencing_token": self.fencing_token,
            "scopes": list(self.scopes),
            "source_before": self.source_before,
            "source_after": self.source_after,
            "source_admitted": self.source_admitted,
            "lease_state": self.lease_state,
            "effect_state": self.effect_state,
            "proof_state": self.proof_state,
            "reducer_state": self.reducer_state,
            "required_receivers": list(self.required_receivers),
            "receiver_states": {k: v for k, v in sorted(self.receiver_states.items())},
        }

    def validate(self) -> "TransitionEnvelope":
        _identifier(self.transition_id, "transition id")
        _identifier(self.mission_id, "mission id")
        _identifier(self.lease_id, "lease id")
        if isinstance(self.mission_version, bool) or not isinstance(self.mission_version, int) or self.mission_version < 1:
            raise ConvergenceError("MISSION_VERSION_INVALID")
        if isinstance(self.fencing_token, bool) or not isinstance(self.fencing_token, int) or self.fencing_token < 1:
            raise ConvergenceError("FENCING_TOKEN_INVALID")
        if not self.scopes:
            raise ConvergenceError("SCOPED_FENCE_REQUIRED")
        for scope in self.scopes:
            _normalize_scope(scope)
        if not str(self.source_before).strip():
            raise ConvergenceError("SOURCE_BEFORE_REQUIRED")
        if self.source_admitted and not str(self.source_after).strip():
            raise ConvergenceError("SOURCE_AFTER_REQUIRED_FOR_ADMISSION")
        if self.source_admitted and self.lease_state is not LeaseState.RELEASED:
            raise ConvergenceError("SOURCE_ADMISSION_REQUIRES_RELEASED_LEASE")
        if self.lease_state is LeaseState.RELEASED and self.effect_state is EffectState.UNKNOWN:
            raise ConvergenceError("UNKNOWN_EFFECT_BLOCKS_RELEASE")
        unknown_receivers = set(self.receiver_states) - set(self.required_receivers)
        if unknown_receivers:
            raise ConvergenceError("UNDECLARED_RECEIVER_STATE")
        if self.transition_sha256 and self.transition_sha256 != _digest(self._body()):
            raise ConvergenceError("TRANSITION_HASH_MISMATCH")
        return self

    def pending_predicates(self) -> tuple[str, ...]:
        self.validate()
        pending: list[str] = []
        if self.lease_state is not LeaseState.RELEASED:
            pending.append("LEASE_RELEASE")
        if self.effect_state is EffectState.UNKNOWN:
            pending.append("EFFECT_READBACK")
        if self.proof_state is not ProofState.PASS:
            pending.append("PROOF_PASS")
        if self.reducer_state is not ProjectionState.APPLIED:
            pending.append("REDUCER_APPLY")
        for receiver in self.required_receivers:
            if self.receiver_states.get(receiver) is not ProjectionState.ACKED:
                pending.append(f"RECEIVER_ACK:{receiver}")
        if self.source_admitted and not self.source_after:
            pending.append("SOURCE_READBACK")
        return tuple(pending)

    @property
    def coordination_complete(self) -> bool:
        return not self.pending_predicates()

    def assert_commit_ready(self) -> "TransitionEnvelope":
        pending = self.pending_predicates()
        if pending:
            raise ConvergenceError("TRANSITION_NOT_CONVERGED:" + "|".join(pending))
        return self


@dataclass(frozen=True, slots=True)
class ScopedFence:
    lease_id: str
    fencing_token: int
    scopes: tuple[str, ...]
    state: LeaseState = LeaseState.ACTIVE

    def validate(self) -> "ScopedFence":
        _identifier(self.lease_id, "lease id")
        if isinstance(self.fencing_token, bool) or not isinstance(self.fencing_token, int) or self.fencing_token < 1:
            raise ConvergenceError("FENCING_TOKEN_INVALID")
        if not self.scopes:
            raise ConvergenceError("SCOPED_FENCE_REQUIRED")
        for scope in self.scopes:
            _normalize_scope(scope)
        return self


class ScopedFenceSet:
    """In-memory deterministic overlap court; persistence remains caller-owned."""

    def __init__(self, fences: Iterable[ScopedFence] = ()) -> None:
        self._fences: dict[str, ScopedFence] = {}
        self._max_token = 0
        for fence in fences:
            self._insert_existing(fence)

    def _insert_existing(self, fence: ScopedFence) -> None:
        fence.validate()
        self._fences[fence.lease_id] = fence
        self._max_token = max(self._max_token, fence.fencing_token)

    def conflicts(self, candidate: ScopedFence) -> tuple[str, ...]:
        candidate.validate()
        conflicts: list[str] = []
        for current in self._fences.values():
            if current.state is not LeaseState.ACTIVE or current.lease_id == candidate.lease_id:
                continue
            if any(scopes_overlap(a, b) for a in candidate.scopes for b in current.scopes):
                conflicts.append(current.lease_id)
        return tuple(sorted(conflicts))

    def acquire(self, candidate: ScopedFence) -> ScopedFence:
        candidate.validate()
        if candidate.state is not LeaseState.ACTIVE:
            raise ConvergenceError("NEW_FENCE_MUST_BE_ACTIVE")
        if candidate.fencing_token <= self._max_token:
            raise ConvergenceError("NON_MONOTONIC_FENCING_TOKEN")
        conflicts = self.conflicts(candidate)
        if conflicts:
            raise ConvergenceError("FENCE_SCOPE_CONFLICT:" + ",".join(conflicts))
        self._fences[candidate.lease_id] = candidate
        self._max_token = candidate.fencing_token
        return candidate

    def release(self, lease_id: str) -> ScopedFence:
        current = self._fences.get(lease_id)
        if current is None:
            raise ConvergenceError("LEASE_UNKNOWN")
        released = ScopedFence(current.lease_id, current.fencing_token, current.scopes, LeaseState.RELEASED)
        self._fences[lease_id] = released
        return released

    @property
    def active(self) -> tuple[ScopedFence, ...]:
        return tuple(sorted((f for f in self._fences.values() if f.state is LeaseState.ACTIVE), key=lambda f: f.fencing_token))


@dataclass(frozen=True, slots=True)
class NegativeRouteFact:
    route_id: str
    operation_key: str
    context_sha256: str
    failure_fingerprint: str
    wake_signals: tuple[str, ...]

    def validate(self) -> "NegativeRouteFact":
        _identifier(self.route_id, "route id")
        _identifier(self.operation_key, "operation key")
        if not re.fullmatch(r"[0-9a-f]{64}", self.context_sha256):
            raise ConvergenceError("CONTEXT_SHA256_INVALID")
        if not str(self.failure_fingerprint).strip():
            raise ConvergenceError("FAILURE_FINGERPRINT_REQUIRED")
        if not self.wake_signals:
            raise ConvergenceError("WAKE_SIGNAL_REQUIRED")
        return self

    def suppresses(self, *, operation_key: str, context_sha256: str, material_signals: Iterable[str] = ()) -> bool:
        self.validate()
        if operation_key != self.operation_key or context_sha256 != self.context_sha256:
            return False
        signals = set(_clean(material_signals))
        return not bool(signals.intersection(self.wake_signals))


class NegativeRouteMemory:
    def __init__(self, facts: Iterable[NegativeRouteFact] = ()) -> None:
        self._facts: dict[tuple[str, str], NegativeRouteFact] = {}
        for fact in facts:
            self.record(fact)

    def record(self, fact: NegativeRouteFact) -> None:
        fact.validate()
        self._facts[(fact.route_id, fact.operation_key)] = fact

    def is_suppressed(
        self,
        route_id: str,
        operation_key: str,
        *,
        context_sha256: str,
        material_signals: Iterable[str] = (),
    ) -> bool:
        fact = self._facts.get((route_id, operation_key))
        return bool(
            fact
            and fact.suppresses(
                operation_key=operation_key,
                context_sha256=context_sha256,
                material_signals=material_signals,
            )
        )

    def eligible_routes(
        self,
        routes: Iterable[str],
        operation_key: str,
        *,
        context_sha256: str,
        material_signals: Iterable[str] = (),
    ) -> tuple[str, ...]:
        return tuple(
            route
            for route in routes
            if not self.is_suppressed(
                route,
                operation_key,
                context_sha256=context_sha256,
                material_signals=material_signals,
            )
        )


class CausalInvalidationGraph:
    """Dependency-indexed invalidation: only causal descendants are invalidated."""

    def __init__(self, node_dependencies: Mapping[str, Iterable[str]]) -> None:
        self._dependents: dict[str, set[str]] = {}
        self._nodes = set(node_dependencies)
        for node, dependencies in node_dependencies.items():
            _identifier(node, "causal node")
            for dependency in _clean(dependencies):
                _identifier(dependency, "causal dependency")
                self._dependents.setdefault(dependency, set()).add(node)
                self._nodes.add(dependency)

    def descendants(self, changed_nodes: Iterable[str]) -> tuple[str, ...]:
        roots = _clean(changed_nodes)
        queue = list(roots)
        seen = set(roots)
        affected: set[str] = set()
        while queue:
            current = queue.pop(0)
            for dependent in sorted(self._dependents.get(current, ())):
                if dependent in seen:
                    continue
                seen.add(dependent)
                affected.add(dependent)
                queue.append(dependent)
        return tuple(sorted(affected))


@dataclass(frozen=True, slots=True)
class GraphRecord:
    record_id: str
    state: str
    payload_sha256: str

    def validate(self) -> "GraphRecord":
        _identifier(self.record_id, "record id")
        if not str(self.state).strip():
            raise ConvergenceError("GRAPH_STATE_REQUIRED")
        if not re.fullmatch(r"[0-9a-f]{64}", self.payload_sha256):
            raise ConvergenceError("PAYLOAD_SHA256_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class CompactionReceipt:
    active_ids: tuple[str, ...]
    dormant_ids: tuple[str, ...]
    historical_ids: tuple[str, ...]
    unknown_ids: tuple[str, ...]
    history_sha256: str


def compact_active_graph(records: Iterable[GraphRecord]) -> CompactionReceipt:
    records = tuple(item.validate() for item in records)
    active, dormant, historical, unknown = [], [], [], []
    history_payload: list[dict[str, str]] = []
    for item in sorted(records, key=lambda value: value.record_id):
        state = item.state.strip().upper()
        history_payload.append(
            {"record_id": item.record_id, "state": state, "payload_sha256": item.payload_sha256}
        )
        if state in LIVE_GRAPH_STATES:
            active.append(item.record_id)
        elif state in DORMANT_GRAPH_STATES:
            dormant.append(item.record_id)
        elif state in HISTORICAL_GRAPH_STATES:
            historical.append(item.record_id)
        else:
            unknown.append(item.record_id)
    return CompactionReceipt(
        active_ids=tuple(active),
        dormant_ids=tuple(dormant),
        historical_ids=tuple(historical),
        unknown_ids=tuple(unknown),
        history_sha256=_digest(history_payload),
    )


@dataclass(frozen=True, slots=True)
class FastPathRequest:
    action_id: str
    capability_id: str
    current: bool
    callable_now: bool
    authority_ok: bool
    proof_scope_matches: bool
    readback_supported: bool
    effectful: bool = False
    rollback_supported: bool = True


@dataclass(frozen=True, slots=True)
class FastPathDecision:
    direct: bool
    reasons: tuple[str, ...]


def evaluate_fast_path(request: FastPathRequest) -> FastPathDecision:
    _identifier(request.action_id, "action id")
    _identifier(request.capability_id, "capability id")
    reasons: list[str] = []
    if not request.current:
        reasons.append("CURRENTNESS_REQUIRED")
    if not request.callable_now:
        reasons.append("CALLABILITY_REQUIRED")
    if not request.authority_ok:
        reasons.append("AUTHORITY_REQUIRED")
    if not request.proof_scope_matches:
        reasons.append("PROOF_SCOPE_MISMATCH")
    if not request.readback_supported:
        reasons.append("READBACK_REQUIRED")
    if request.effectful and not request.rollback_supported:
        reasons.append("ROLLBACK_REQUIRED_FOR_EFFECT_FAST_PATH")
    return FastPathDecision(direct=not reasons, reasons=tuple(reasons))


@dataclass(frozen=True, slots=True)
class LeaseProjection:
    lease_id: str
    mission_id: str
    fencing_token: int
    state: LeaseState
    scopes: tuple[str, ...]

    def validate(self) -> "LeaseProjection":
        _identifier(self.lease_id, "lease id")
        if isinstance(self.fencing_token, bool) or not isinstance(self.fencing_token, int) or self.fencing_token < 1:
            raise ConvergenceError("FENCING_TOKEN_INVALID")
        if self.state is LeaseState.ACTIVE:
            _identifier(self.mission_id, "mission id")
        if not self.scopes:
            raise ConvergenceError("SCOPED_FENCE_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class InvariantAudit:
    defects: tuple[str, ...]

    @property
    def clean(self) -> bool:
        return not self.defects


def audit_cross_plane_invariants(
    mission_ids: Iterable[str],
    leases: Iterable[LeaseProjection],
) -> InvariantAudit:
    missions = set(_clean(mission_ids))
    leases = tuple(item.validate() for item in leases)
    defects: list[str] = []
    active = [item for item in leases if item.state is LeaseState.ACTIVE]
    for item in active:
        if item.mission_id not in missions:
            defects.append(f"ACTIVE_LEASE_WITHOUT_MISSION:{item.lease_id}:{item.mission_id}")
    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            if any(scopes_overlap(a, b) for a in left.scopes for b in right.scopes):
                defects.append(f"OVERLAPPING_ACTIVE_FENCES:{left.lease_id}:{right.lease_id}")
    tokens = [item.fencing_token for item in leases]
    if len(tokens) != len(set(tokens)):
        defects.append("DUPLICATE_FENCING_TOKEN")
    return InvariantAudit(tuple(sorted(defects)))


@dataclass(frozen=True, slots=True)
class TransitionDecision:
    state: str
    pending: tuple[str, ...]
    receipt_sha256: str


def evaluate_transition(envelope: TransitionEnvelope) -> TransitionDecision:
    envelope.validate()
    pending = envelope.pending_predicates()
    state = "COMMIT_READY" if not pending else "HOLD"
    body = {
        "schema": SCHEMA,
        "transition_sha256": envelope.transition_sha256 or _digest(envelope._body()),
        "state": state,
        "pending": list(pending),
    }
    return TransitionDecision(state=state, pending=pending, receipt_sha256=_digest(body))
