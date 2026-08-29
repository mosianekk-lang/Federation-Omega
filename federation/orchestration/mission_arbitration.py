from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Iterable, Sequence

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9._:/@-]{1,256}$")
_REALITY_RANK = {"C0": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5}
_AUTHORITY_RANK = {
    "A0": 0,
    "A0_READ": 0,
    "A1": 1,
    "A1_INTERNAL": 1,
    "A2": 2,
    "A3": 3,
}
_OPEN_STATES = {"OPEN", "DRAFT", "RUNNING", "READY"}
_SCORE_WEIGHTS = {
    "quality": 0.16,
    "reliability": 0.22,
    "freshness": 0.15,
    "proof_strength": 0.20,
    "latency": 0.06,
    "cost": 0.05,
    "owner_burden": 0.06,
    "risk": 0.10,
}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _validate_id(value: str, field: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ValueError(f"{field} is invalid")
    return value


def _validate_sha(value: str, field: str = "sha") -> str:
    if not isinstance(value, str) or not _SHA40.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase 40-character Git SHA")
    return value


def _paths(values: Iterable[str]) -> tuple[str, ...]:
    out: set[str] = set()
    for raw in values:
        value = str(raw).strip().replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        if (
            not value
            or value.startswith("/")
            or any(part in {"", ".."} for part in value.split("/"))
        ):
            raise ValueError("repository paths must be relative and traversal-free")
        out.add(value.rstrip("/"))
    if not out:
        raise ValueError("at least one repository path is required")
    return tuple(sorted(out))


def _overlap(a: str, b: str) -> bool:
    a, b = a.rstrip("/"), b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def overlapping_paths(left: Iterable[str], right: Iterable[str]) -> tuple[str, ...]:
    lhs, rhs = _paths(left), _paths(right)
    return tuple(sorted({a for a in lhs for b in rhs if _overlap(a, b)}))


class ConcurrencyState(str, Enum):
    CLEAR = "CLEAR"
    MAIN_DRIFT_FAST_RECONVERGE = "MAIN_DRIFT_FAST_RECONVERGE"
    MAIN_DRIFT_OVERLAP_HOLD = "MAIN_DRIFT_OVERLAP_HOLD"
    ACTIVE_WORKSTREAM_OVERLAP_HOLD = "ACTIVE_WORKSTREAM_OVERLAP_HOLD"
    LEASE_EXPIRED = "LEASE_EXPIRED"


class FailureStatus(str, Enum):
    OPEN = "OPEN"
    MITIGATED = "MITIGATED"
    CLOSED = "CLOSED"


class RouteDisposition(str, Enum):
    SELECT = "SELECT"
    HOLD = "HOLD"


class ProofState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    AUTHORISED = "AUTHORISED"
    EXECUTED = "EXECUTED"
    READBACK_VERIFIED = "READBACK_VERIFIED"
    RECEIPT_VERIFIED = "RECEIPT_VERIFIED"


def _failure_state(value: str | FailureStatus) -> FailureStatus:
    if isinstance(value, FailureStatus):
        return value
    try:
        return FailureStatus(str(value).upper())
    except ValueError as exc:
        raise ValueError("unknown failure status") from exc


@dataclass(frozen=True)
class MissionLease:
    """Mission/path lease used as a fencing token, never as provider authority."""

    mission_id: str
    lane_id: str
    holder_id: str
    base_main_sha: str
    lease_epoch: int
    path_scope: tuple[str, ...]
    issued_at: str
    expires_at: str
    authority_ceiling: str
    fence_token: str

    @classmethod
    def create(
        cls,
        *,
        mission_id: str,
        lane_id: str,
        holder_id: str,
        base_main_sha: str,
        lease_epoch: int,
        path_scope: Iterable[str],
        issued_at: str,
        expires_at: str,
        authority_ceiling: str = "A1_INTERNAL",
        external_effect: bool = False,
    ) -> "MissionLease":
        _validate_id(mission_id, "mission_id")
        _validate_id(lane_id, "lane_id")
        _validate_id(holder_id, "holder_id")
        _validate_sha(base_main_sha, "base_main_sha")
        if not isinstance(lease_epoch, int) or lease_epoch < 1:
            raise ValueError("lease_epoch must be positive")
        if authority_ceiling not in _AUTHORITY_RANK:
            raise ValueError("unknown authority ceiling")
        if _AUTHORITY_RANK[authority_ceiling] > _AUTHORITY_RANK["A1_INTERNAL"] or external_effect:
            raise ValueError("mission lease cannot grant provider/external authority")
        issued, expires = _time(issued_at), _time(expires_at)
        if expires <= issued:
            raise ValueError("lease expiry must be after issuance")
        scope = _paths(path_scope)
        body = {
            "mission_id": mission_id,
            "lane_id": lane_id,
            "holder_id": holder_id,
            "base_main_sha": base_main_sha,
            "lease_epoch": lease_epoch,
            "path_scope": scope,
            "issued_at": issued.isoformat(),
            "expires_at": expires.isoformat(),
            "authority_ceiling": authority_ceiling,
        }
        return cls(fence_token=f"FEDOMEGA-FENCE-{_digest(body)[:32].upper()}", **body)

    def active_at(self, now: str) -> bool:
        instant = _time(now)
        return _time(self.issued_at) <= instant < _time(self.expires_at)

    def refresh(
        self,
        *,
        new_main_sha: str,
        new_epoch: int,
        issued_at: str,
        expires_at: str,
    ) -> "MissionLease":
        if new_epoch <= self.lease_epoch:
            raise ValueError("new lease epoch must increase")
        return MissionLease.create(
            mission_id=self.mission_id,
            lane_id=self.lane_id,
            holder_id=self.holder_id,
            base_main_sha=new_main_sha,
            lease_epoch=new_epoch,
            path_scope=self.path_scope,
            issued_at=issued_at,
            expires_at=expires_at,
            authority_ceiling=self.authority_ceiling,
        )


@dataclass(frozen=True)
class WorkstreamObservation:
    workstream_id: str
    base_sha: str
    head_sha: str
    paths: tuple[str, ...]
    state: str = "OPEN"

    @classmethod
    def create(
        cls,
        *,
        workstream_id: str,
        base_sha: str,
        head_sha: str,
        paths: Iterable[str],
        state: str = "OPEN",
    ) -> "WorkstreamObservation":
        _validate_id(workstream_id, "workstream_id")
        return cls(
            workstream_id=workstream_id,
            base_sha=_validate_sha(base_sha, "base_sha"),
            head_sha=_validate_sha(head_sha, "head_sha"),
            paths=_paths(paths),
            state=str(state).upper(),
        )


@dataclass(frozen=True)
class ConcurrencyDecision:
    state: ConcurrencyState
    write_allowed: bool
    overlapping_workstreams: tuple[str, ...]
    overlapping_paths: tuple[str, ...]
    next_action: str
    current_main_sha: str = ""
    lease_main_sha: str = ""


class ConcurrencyGuard:
    """Fail-closed source-write arbitration for moving-main and cross-lane work."""

    def evaluate(
        self,
        *,
        lease: MissionLease,
        current_main_sha: str,
        now: str,
        main_changed_paths: Iterable[str] = (),
        active_workstreams: Sequence[WorkstreamObservation] = (),
    ) -> ConcurrencyDecision:
        _validate_sha(current_main_sha, "current_main_sha")
        common = {
            "current_main_sha": current_main_sha,
            "lease_main_sha": lease.base_main_sha,
        }
        if not lease.active_at(now):
            return ConcurrencyDecision(
                ConcurrencyState.LEASE_EXPIRED,
                False,
                (),
                (),
                "RENEW_FROM_FRESH_MAIN",
                **common,
            )

        hits: set[str] = set()
        streams: set[str] = set()
        for work in active_workstreams:
            if work.state not in _OPEN_STATES:
                continue
            overlap = overlapping_paths(lease.path_scope, work.paths)
            if overlap:
                streams.add(work.workstream_id)
                hits.update(overlap)
        if streams:
            return ConcurrencyDecision(
                ConcurrencyState.ACTIVE_WORKSTREAM_OVERLAP_HOLD,
                False,
                tuple(sorted(streams)),
                tuple(sorted(hits)),
                "SERIALIZE_OR_RECONCILE",
                **common,
            )

        if current_main_sha != lease.base_main_sha:
            changed = tuple(str(x) for x in main_changed_paths if str(x).strip())
            overlap = overlapping_paths(lease.path_scope, changed) if changed else ()
            if overlap:
                return ConcurrencyDecision(
                    ConcurrencyState.MAIN_DRIFT_OVERLAP_HOLD,
                    False,
                    (),
                    overlap,
                    "RECONCILE_CHANGED_PATHS",
                    **common,
                )
            return ConcurrencyDecision(
                ConcurrencyState.MAIN_DRIFT_FAST_RECONVERGE,
                False,
                (),
                (),
                "RESTACK_ON_CURRENT_MAIN",
                **common,
            )

        return ConcurrencyDecision(
            ConcurrencyState.CLEAR,
            True,
            (),
            (),
            "WRITE_WITH_FENCE_AND_READBACK",
            **common,
        )


@dataclass(frozen=True)
class PreWriteFenceReceipt:
    mission_id: str
    base_main_sha: str
    current_main_sha: str
    fence_token: str
    intended_paths_sha256: str
    allowed: bool
    reason: str
    receipt_sha256: str
    lease_epoch: int = 0


class PreWriteFence:
    """CAS-style guard: a source mutation is valid only against fresh main truth."""

    def authorise(
        self,
        *,
        lease: MissionLease,
        decision: ConcurrencyDecision,
        current_main_sha: str | None = None,
        intended_paths: Iterable[str],
    ) -> PreWriteFenceReceipt:
        observed_main = current_main_sha or decision.current_main_sha or lease.base_main_sha
        _validate_sha(observed_main, "current_main_sha")
        paths = _paths(intended_paths)
        inside_scope = all(any(_overlap(path, scope) for scope in lease.path_scope) for path in paths)
        if not inside_scope:
            allowed, reason = False, "PATH_OUTSIDE_LEASE_SCOPE"
        elif not decision.write_allowed:
            allowed, reason = False, decision.state.value
        elif observed_main != lease.base_main_sha:
            allowed, reason = False, "STALE_MAIN_FENCE"
        else:
            allowed, reason = True, "PREWRITE_FENCE_VERIFIED"
        body = {
            "mission_id": lease.mission_id,
            "base_main_sha": lease.base_main_sha,
            "current_main_sha": observed_main,
            "fence_token": lease.fence_token,
            "intended_paths_sha256": _digest(paths),
            "allowed": allowed,
            "reason": reason,
            "lease_epoch": lease.lease_epoch,
        }
        receipt_hash = _digest(body)
        return PreWriteFenceReceipt(
            mission_id=lease.mission_id,
            base_main_sha=lease.base_main_sha,
            current_main_sha=observed_main,
            fence_token=lease.fence_token,
            intended_paths_sha256=body["intended_paths_sha256"],
            allowed=allowed,
            reason=reason,
            receipt_sha256=receipt_hash,
            lease_epoch=lease.lease_epoch,
        )


@dataclass(frozen=True)
class FailureMemoryRecord:
    fingerprint: str
    route_id: str
    status: str | FailureStatus
    failure_proof_ref: str
    retry_condition: str
    recovery_proof_ref: str = ""

    def validate(self) -> "FailureMemoryRecord":
        if len(self.fingerprint.strip()) < 6:
            raise ValueError("failure fingerprint is too short")
        _validate_id(self.route_id, "route_id")
        state = _failure_state(self.status)
        if not self.failure_proof_ref.strip() or not self.retry_condition.strip():
            raise ValueError("failure record requires proof and retry condition")
        if state == FailureStatus.CLOSED and not self.recovery_proof_ref.strip():
            raise ValueError("closed failure requires recovery proof")
        return self

    def blockers_for(self, route_id: str, retry_evidence_refs: Iterable[str]) -> tuple[str, ...]:
        if route_id != self.route_id:
            return ()
        self.validate()
        refs = set(retry_evidence_refs)
        state = _failure_state(self.status)
        if state == FailureStatus.OPEN:
            return (f"KNOWN_OPEN_FAILURE:{self.fingerprint}",)
        if state == FailureStatus.MITIGATED and (
            not self.recovery_proof_ref or self.recovery_proof_ref not in refs
        ):
            return (f"MITIGATION_PROOF_NOT_BOUND:{self.fingerprint}",)
        if state == FailureStatus.CLOSED and self.recovery_proof_ref not in refs:
            return (f"RECOVERY_PROOF_NOT_BOUND:{self.fingerprint}",)
        return ()


@dataclass(frozen=True)
class CapabilityRoute:
    route_id: str
    capability_id: str
    reality_state: str
    required_reality_state: str
    readiness: str
    authority_required: str
    proof_ref: str
    external_effect: bool = False
    retry_evidence_refs: tuple[str, ...] = ()
    fitness: float | None = None
    quality: float = 0.5
    reliability: float = 0.5
    freshness: float = 0.5
    proof_strength: float = 0.5
    latency: float = 0.5
    cost: float = 0.5
    owner_burden: float = 0.5
    risk: float = 0.5

    def validate(self) -> "CapabilityRoute":
        _validate_id(self.route_id, "route_id")
        _validate_id(self.capability_id, "capability_id")
        if self.reality_state not in _REALITY_RANK or self.required_reality_state not in _REALITY_RANK:
            raise ValueError("unknown capability reality state")
        if self.readiness not in {"READY", "HOLD", "BLOCKED", "STALE"}:
            raise ValueError("unknown readiness")
        if self.authority_required not in _AUTHORITY_RANK:
            raise ValueError("unknown authority requirement")
        if not self.proof_ref.strip():
            raise ValueError("route requires a proof reference")
        if self.fitness is not None and not 0.0 <= float(self.fitness) <= 1.0:
            raise ValueError("fitness must be in [0,1]")
        for name in _SCORE_WEIGHTS:
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0,1]")
        return self

    @property
    def score(self) -> float:
        self.validate()
        positive = (
            _SCORE_WEIGHTS["quality"] * self.quality
            + _SCORE_WEIGHTS["reliability"] * self.reliability
            + _SCORE_WEIGHTS["freshness"] * self.freshness
            + _SCORE_WEIGHTS["proof_strength"] * self.proof_strength
        )
        penalties = (
            _SCORE_WEIGHTS["latency"] * self.latency
            + _SCORE_WEIGHTS["cost"] * self.cost
            + _SCORE_WEIGHTS["owner_burden"] * self.owner_burden
            + _SCORE_WEIGHTS["risk"] * self.risk
        )
        return round(positive - penalties, 8)


@dataclass(frozen=True)
class RouteGateDecision:
    route_id: str
    disposition: RouteDisposition
    eligible: bool
    score: float
    reasons: tuple[str, ...]


class FailureMemoryGate:
    """Known failed routes cannot be retried unchanged."""

    def evaluate(
        self,
        *,
        route: CapabilityRoute,
        memories: Sequence[FailureMemoryRecord],
        authority_ceiling: str = "A1_INTERNAL",
    ) -> RouteGateDecision:
        route.validate()
        if authority_ceiling not in _AUTHORITY_RANK:
            raise ValueError("unknown authority ceiling")
        reasons: list[str] = []
        if route.readiness != "READY":
            reasons.append(f"NOT_READY:{route.readiness}")
        if _REALITY_RANK[route.reality_state] < _REALITY_RANK[route.required_reality_state]:
            reasons.append(
                f"REALITY_STATE_INSUFFICIENT:{route.reality_state}<{route.required_reality_state}"
            )
        if _AUTHORITY_RANK[route.authority_required] > _AUTHORITY_RANK[authority_ceiling]:
            reasons.append("AUTHORITY_CEILING_EXCEEDED")
        if route.external_effect and _AUTHORITY_RANK[authority_ceiling] <= _AUTHORITY_RANK["A1_INTERNAL"]:
            reasons.append("EXTERNAL_EFFECT_NOT_AUTHORISED")
        for memory in memories:
            reasons.extend(memory.blockers_for(route.route_id, route.retry_evidence_refs))
        return RouteGateDecision(
            route_id=route.route_id,
            disposition=RouteDisposition.SELECT if not reasons else RouteDisposition.HOLD,
            eligible=not reasons,
            score=route.score,
            reasons=tuple(reasons),
        )


@dataclass(frozen=True)
class RouteDecision:
    selected_route_id: str
    blocked_routes: tuple[str, ...]
    reasons: tuple[str, ...]
    next_action: str
    selected_capability_id: str = ""
    selected_score: float = 0.0
    decisions: tuple[RouteGateDecision, ...] = ()


RouteSelection = RouteDecision


class CapabilitySelector:
    """CFBE tournament after reality, authority and current failure-memory gates."""

    def __init__(self) -> None:
        self.gate = FailureMemoryGate()

    def select(
        self,
        *,
        routes: Sequence[CapabilityRoute],
        memories: Sequence[FailureMemoryRecord],
        authority_ceiling: str = "A1_INTERNAL",
    ) -> RouteDecision:
        if not routes:
            raise ValueError("at least one route is required")
        decisions = tuple(
            self.gate.evaluate(
                route=route,
                memories=memories,
                authority_ceiling=authority_ceiling,
            )
            for route in routes
        )
        by_id = {route.route_id: route for route in routes}
        eligible = [item for item in decisions if item.eligible]
        blocked = tuple(sorted(item.route_id for item in decisions if not item.eligible))
        all_reasons = tuple(
            sorted(f"{item.route_id}:{reason}" for item in decisions for reason in item.reasons)
        )
        if not eligible:
            return RouteDecision(
                "",
                blocked,
                all_reasons,
                "FORM_OR_REPAIR_ROUTE",
                decisions=decisions,
            )

        def rank(item: RouteGateDecision) -> tuple[float, float, str]:
            route = by_id[item.route_id]
            legacy = float(route.fitness) if route.fitness is not None else -1.0
            return item.score, legacy, item.route_id

        winner = max(eligible, key=rank)
        route = by_id[winner.route_id]
        return RouteDecision(
            selected_route_id=route.route_id,
            blocked_routes=blocked,
            reasons=all_reasons,
            next_action="EXECUTE_SELECTED_ROUTE",
            selected_capability_id=route.capability_id,
            selected_score=winner.score,
            decisions=decisions,
        )


@dataclass(frozen=True)
class ExecutionEnvelope:
    mission_id: str
    operation_id: str
    authorization_ref: str = ""
    execution_ref: str = ""
    target_readback_ref: str = ""
    expected_target_digest: str = ""
    observed_target_digest: str = ""
    receipt_ref: str = ""
    external_effect: bool = False

    @property
    def proof_state(self) -> ProofState:
        if not self.authorization_ref:
            return ProofState.UNVERIFIED
        if not self.execution_ref:
            return ProofState.AUTHORISED
        if (
            not self.target_readback_ref
            or not self.expected_target_digest
            or self.expected_target_digest != self.observed_target_digest
        ):
            return ProofState.EXECUTED
        if not self.receipt_ref:
            return ProofState.READBACK_VERIFIED
        return ProofState.RECEIPT_VERIFIED

    @property
    def completion_claim_allowed(self) -> bool:
        return self.proof_state == ProofState.RECEIPT_VERIFIED


@dataclass(frozen=True)
class NearMissEvent:
    mission_id: str
    event_type: str
    prevented_action: str
    signal: str
    control: str
    proof_refs: tuple[str, ...]
    event_id: str

    @classmethod
    def create(
        cls,
        *,
        mission_id: str,
        event_type: str,
        prevented_action: str,
        signal: str,
        control: str,
        proof_refs: Iterable[str],
    ) -> "NearMissEvent":
        _validate_id(mission_id, "mission_id")
        refs = tuple(sorted({str(item).strip() for item in proof_refs if str(item).strip()}))
        body = {
            "mission_id": mission_id,
            "event_type": str(event_type).strip(),
            "prevented_action": str(prevented_action).strip(),
            "signal": str(signal).strip(),
            "control": str(control).strip(),
            "proof_refs": refs,
        }
        if not refs or not all(
            body[key] for key in ("event_type", "prevented_action", "signal", "control")
        ):
            raise ValueError("near miss requires non-empty fields and proof refs")
        return cls(event_id=f"FMACF-NEARMISS-{_digest(body)[:24].upper()}", **body)


@dataclass(frozen=True)
class MissionSnapshot:
    mission_id: str
    current_main_sha: str
    concurrency_state: str
    selected_route_id: str
    blocked_routes: tuple[str, ...]
    next_action: str
    snapshot_sha256: str
    lease_epoch: int = 0
    fence_token: str = ""
    active_failure_fingerprints: tuple[str, ...] = ()
    near_miss_ids: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        lease: MissionLease,
        current_main_sha: str | None = None,
        concurrency: ConcurrencyDecision,
        selection: RouteDecision,
        memories: Sequence[FailureMemoryRecord] = (),
        near_misses: Sequence[NearMissEvent] = (),
    ) -> "MissionSnapshot":
        observed_main = current_main_sha or concurrency.current_main_sha or lease.base_main_sha
        _validate_sha(observed_main, "current_main_sha")
        active_failures = tuple(
            sorted(
                memory.fingerprint
                for memory in memories
                if _failure_state(memory.status) in {FailureStatus.OPEN, FailureStatus.MITIGATED}
            )
        )
        body = {
            "mission_id": lease.mission_id,
            "current_main_sha": observed_main,
            "concurrency_state": concurrency.state.value,
            "selected_route_id": selection.selected_route_id,
            "blocked_routes": selection.blocked_routes,
            "next_action": (
                concurrency.next_action if not concurrency.write_allowed else selection.next_action
            ),
            "lease_epoch": lease.lease_epoch,
            "fence_token": lease.fence_token,
            "active_failure_fingerprints": active_failures,
            "near_miss_ids": tuple(sorted(item.event_id for item in near_misses)),
        }
        return cls(snapshot_sha256=_digest(body), **body)

    @property
    def snapshot_digest(self) -> str:
        return self.snapshot_sha256

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


__all__ = [
    "CapabilityRoute",
    "CapabilitySelector",
    "ConcurrencyDecision",
    "ConcurrencyGuard",
    "ConcurrencyState",
    "ExecutionEnvelope",
    "FailureMemoryGate",
    "FailureMemoryRecord",
    "FailureStatus",
    "MissionLease",
    "MissionSnapshot",
    "NearMissEvent",
    "PreWriteFence",
    "PreWriteFenceReceipt",
    "ProofState",
    "RouteDecision",
    "RouteDisposition",
    "RouteGateDecision",
    "RouteSelection",
    "WorkstreamObservation",
    "overlapping_paths",
]
