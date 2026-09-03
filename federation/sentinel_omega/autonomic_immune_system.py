"""Sentinel Ω autonomic immune-system control primitives.

Current-main transplant of the previously developed Sentinel v2 donor semantics.
Provider-neutral, deterministic controls for keeping routine Federation
maintenance away from the owner's creative work. This module plans and governs
repairs; provider-specific executors remain separate and must supply their own
authority and semantic readback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
from typing import Iterable, Mapping, Sequence


class AuthorityTier(str, Enum):
    A0_OBSERVE = "A0_OBSERVE"
    A1_INTERNAL = "A1_INTERNAL"
    A2_REVERSIBLE_PROVIDER = "A2_REVERSIBLE_PROVIDER"
    A3_OWNER_RESERVED = "A3_OWNER_RESERVED"


class IncidentSeverity(str, Enum):
    INFO = "INFO"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class BreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class RemediationDisposition(str, Enum):
    OBSERVE = "OBSERVE"
    AUTO_REPAIR = "AUTO_REPAIR"
    REROUTE = "REROUTE"
    HOLD_PROVIDER_EDGE = "HOLD_PROVIDER_EDGE"
    ESCALATE_OWNER = "ESCALATE_OWNER"


@dataclass(frozen=True)
class EventEnvelope:
    source: str
    target: str
    signal: str
    observed_state: str
    occurred_at: datetime
    proof_refs: tuple[str, ...] = ()
    change_anchor: str = ""
    trace_id: str = ""

    def event_key(self) -> str:
        payload = {
            "source": self.source.strip().lower(),
            "target": self.target.strip().lower(),
            "signal": self.signal.strip().lower(),
            "observed_state": self.observed_state.strip(),
            "change_anchor": self.change_anchor.strip(),
            "trace_id": self.trace_id.strip(),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class FailureFingerprint:
    target: str
    failure_class: str
    error_signature: str
    dependency_epoch: str = ""
    provider_epoch: str = ""
    source_epoch: str = ""

    def digest(self) -> str:
        payload = {
            "target": self.target.strip().lower(),
            "failure_class": self.failure_class.strip().lower(),
            "error_signature": " ".join(self.error_signature.split()).lower(),
            "dependency_epoch": self.dependency_epoch.strip(),
            "provider_epoch": self.provider_epoch.strip(),
            "source_epoch": self.source_epoch.strip(),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class RepairRunbook:
    runbook_id: str
    failure_classes: tuple[str, ...]
    max_authority: AuthorityTier
    reversible: bool
    requires_canary: bool = True
    requires_semantic_readback: bool = True
    rollback_ref: str = ""
    route_family: str = ""
    expected_owner_burden_minutes: float = 0.0

    def matches(self, fingerprint: FailureFingerprint) -> bool:
        failure = fingerprint.failure_class.strip().lower()
        return failure in {x.strip().lower() for x in self.failure_classes}


@dataclass(frozen=True)
class RepairAttempt:
    fingerprint_digest: str
    runbook_id: str
    route_family: str
    attempted_at: datetime
    result: str
    proof_refs: tuple[str, ...] = ()
    state_epoch: str = ""


class RepairMemory:
    """Immutable-style attempt memory used to prevent blind repeated retries."""

    def __init__(self, attempts: Iterable[RepairAttempt] = ()) -> None:
        self._attempts = tuple(attempts)

    @property
    def attempts(self) -> tuple[RepairAttempt, ...]:
        return self._attempts

    def with_attempt(self, attempt: RepairAttempt) -> "RepairMemory":
        return RepairMemory(self._attempts + (attempt,))

    def unchanged_route_failed(
        self,
        fingerprint: FailureFingerprint,
        runbook: RepairRunbook,
        *,
        state_epoch: str,
    ) -> bool:
        digest = fingerprint.digest()
        for attempt in reversed(self._attempts):
            if attempt.fingerprint_digest != digest:
                continue
            if attempt.runbook_id != runbook.runbook_id:
                continue
            if attempt.route_family != runbook.route_family:
                continue
            if attempt.state_epoch != state_epoch:
                return False
            return attempt.result.upper() in {"FAILED", "BLOCKED", "NO_EFFECT"}
        return False

    def tried_route_families(self, fingerprint: FailureFingerprint) -> frozenset[str]:
        digest = fingerprint.digest()
        return frozenset(
            a.route_family for a in self._attempts if a.fingerprint_digest == digest
        )


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    cooldown: timedelta = timedelta(minutes=15)
    state: BreakerState = BreakerState.CLOSED
    consecutive_failures: int = 0
    opened_at: datetime | None = None

    def record_success(self) -> None:
        self.state = BreakerState.CLOSED
        self.consecutive_failures = 0
        self.opened_at = None

    def record_failure(self, now: datetime) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.state = BreakerState.OPEN
            self.opened_at = now

    def allow_probe(self, now: datetime) -> bool:
        if self.state == BreakerState.CLOSED:
            return True
        if self.state == BreakerState.HALF_OPEN:
            return True
        if self.opened_at is not None and now - self.opened_at >= self.cooldown:
            self.state = BreakerState.HALF_OPEN
            return True
        return False


class DependencyGraph:
    """Directed graph for deterministic blast-radius and reroute reasoning."""

    def __init__(self, edges: Mapping[str, Iterable[str]] | None = None) -> None:
        self._edges = {
            str(source): frozenset(map(str, targets))
            for source, targets in (edges or {}).items()
        }

    def downstream(self, node: str) -> tuple[str, ...]:
        seen: set[str] = set()
        stack = list(self._edges.get(node, ()))
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self._edges.get(current, ()))
        return tuple(sorted(seen))

    def blast_radius(self, node: str) -> int:
        return len(self.downstream(node))


@dataclass(frozen=True)
class CreativeTimeSample:
    incident_id: str
    detected_at: datetime
    resolved_at: datetime | None
    owner_interrupted: bool
    routine_technical: bool = True


@dataclass(frozen=True)
class CreativeTimeMetrics:
    routine_incidents: int
    auto_resolved_without_owner: int
    owner_interruptions: int
    protection_rate: float | None
    mean_time_to_resolve_seconds: float | None


class CreativeTimeSLO:
    def evaluate(self, samples: Sequence[CreativeTimeSample]) -> CreativeTimeMetrics:
        routine = [s for s in samples if s.routine_technical]
        protected = [s for s in routine if not s.owner_interrupted and s.resolved_at is not None]
        interrupted = [s for s in routine if s.owner_interrupted]
        durations = [
            (s.resolved_at - s.detected_at).total_seconds()
            for s in routine
            if s.resolved_at is not None
        ]
        return CreativeTimeMetrics(
            routine_incidents=len(routine),
            auto_resolved_without_owner=len(protected),
            owner_interruptions=len(interrupted),
            protection_rate=(len(protected) / len(routine)) if routine else None,
            mean_time_to_resolve_seconds=(sum(durations) / len(durations) if durations else None),
        )


@dataclass(frozen=True)
class SelfTestCheck:
    check_id: str
    ok: bool
    proof_ref: str = ""
    detail: str = ""


@dataclass(frozen=True)
class SelfTestReport:
    checked_at: datetime
    checks: tuple[SelfTestCheck, ...]

    @property
    def healthy(self) -> bool:
        return bool(self.checks) and all(check.ok for check in self.checks)

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.ok)


@dataclass(frozen=True)
class RemediationDecision:
    disposition: RemediationDisposition
    reason: str
    runbook_id: str = ""
    authority: AuthorityTier = AuthorityTier.A0_OBSERVE
    affected_nodes: tuple[str, ...] = ()
    owner_interrupt_required: bool = False
    proof_requirements: tuple[str, ...] = ()


class AutonomicImmuneController:
    """Select the smallest safe repair while protecting owner attention."""

    _ORDER = {
        AuthorityTier.A0_OBSERVE: 0,
        AuthorityTier.A1_INTERNAL: 1,
        AuthorityTier.A2_REVERSIBLE_PROVIDER: 2,
        AuthorityTier.A3_OWNER_RESERVED: 3,
    }

    def __init__(
        self,
        *,
        runbooks: Sequence[RepairRunbook],
        dependency_graph: DependencyGraph | None = None,
        memory: RepairMemory | None = None,
    ) -> None:
        self.runbooks = tuple(runbooks)
        self.graph = dependency_graph or DependencyGraph()
        self.memory = memory or RepairMemory()

    def decide(
        self,
        fingerprint: FailureFingerprint,
        *,
        authority_ceiling: AuthorityTier,
        state_epoch: str,
        safe_alternate_routes: Sequence[str] = (),
    ) -> RemediationDecision:
        affected = self.graph.downstream(fingerprint.target)
        matching = [r for r in self.runbooks if r.matches(fingerprint)]
        eligible = [
            r
            for r in matching
            if self._ORDER[r.max_authority] <= self._ORDER[authority_ceiling]
            and (r.reversible or r.max_authority == AuthorityTier.A0_OBSERVE)
            and not self.memory.unchanged_route_failed(fingerprint, r, state_epoch=state_epoch)
        ]
        eligible.sort(
            key=lambda r: (
                self._ORDER[r.max_authority],
                r.expected_owner_burden_minutes,
                r.runbook_id,
            )
        )

        if eligible:
            chosen = eligible[0]
            requirements: list[str] = []
            if chosen.requires_canary:
                requirements.append("CANARY")
            if chosen.requires_semantic_readback:
                requirements.append("SEMANTIC_READBACK")
            if chosen.rollback_ref:
                requirements.append(f"ROLLBACK:{chosen.rollback_ref}")
            return RemediationDecision(
                disposition=RemediationDisposition.AUTO_REPAIR,
                reason="smallest_safe_untried_repair",
                runbook_id=chosen.runbook_id,
                authority=chosen.max_authority,
                affected_nodes=affected,
                owner_interrupt_required=False,
                proof_requirements=tuple(requirements),
            )

        if safe_alternate_routes:
            tried = self.memory.tried_route_families(fingerprint)
            unused = tuple(route for route in safe_alternate_routes if route not in tried)
            if unused:
                return RemediationDecision(
                    disposition=RemediationDisposition.REROUTE,
                    reason=f"safe_alternate_route:{unused[0]}",
                    authority=authority_ceiling,
                    affected_nodes=affected,
                    owner_interrupt_required=False,
                    proof_requirements=("SEMANTIC_READBACK",),
                )

        if matching and all(
            self._ORDER[r.max_authority] > self._ORDER[authority_ceiling]
            for r in matching
        ):
            return RemediationDecision(
                disposition=(
                    RemediationDisposition.ESCALATE_OWNER
                    if authority_ceiling != AuthorityTier.A3_OWNER_RESERVED
                    else RemediationDisposition.HOLD_PROVIDER_EDGE
                ),
                reason="repair_requires_higher_authority",
                authority=AuthorityTier.A3_OWNER_RESERVED,
                affected_nodes=affected,
                owner_interrupt_required=authority_ceiling != AuthorityTier.A3_OWNER_RESERVED,
            )

        return RemediationDecision(
            disposition=RemediationDisposition.HOLD_PROVIDER_EDGE,
            reason="no_new_safe_route_for_current_fingerprint",
            authority=authority_ceiling,
            affected_nodes=affected,
            owner_interrupt_required=False,
        )

    def record_attempt(self, attempt: RepairAttempt) -> None:
        self.memory = self.memory.with_attempt(attempt)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "AuthorityTier",
    "AutonomicImmuneController",
    "BreakerState",
    "CircuitBreaker",
    "CreativeTimeMetrics",
    "CreativeTimeSLO",
    "CreativeTimeSample",
    "DependencyGraph",
    "EventEnvelope",
    "FailureFingerprint",
    "IncidentSeverity",
    "RemediationDecision",
    "RemediationDisposition",
    "RepairAttempt",
    "RepairMemory",
    "RepairRunbook",
    "SelfTestCheck",
    "SelfTestReport",
    "utc_now",
]
